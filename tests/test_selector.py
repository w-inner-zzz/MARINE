"""The automatic choice of correction method (marine_guard.selector)."""

from marine_guard import AuxFix, State
from marine_guard.selector import (BAN_S, PEERS, PSEUDOLITES, REJECT_LIMIT, SEABED,
                                   AidSelector)
from sim.runner import run_scenario

PL = (AuxFix("pseudolite", (0.0, 0.0), 5.0),)
PEER = (AuxFix("peer:0", (0.0, 0.0), 30.0),)
SB = (AuxFix("seabed", (0.0, 0.0), 25.0),)
ALL = {PSEUDOLITES: PL, PEERS: PEER, SEABED: SB}


def test_gnss_while_trusted_and_blend_while_degraded():
    sel = AidSelector()
    assert sel.choose(0, State.TRUSTED, ALL, ()).methods == ("gnss",)
    choice = sel.choose(1, State.DEGRADED, ALL, ())
    assert choice.methods == ("blend",) and choice.fixes == ()


def test_spoofing_and_jamming_never_trust_nearby_ships():
    for state in (State.SPOOFING, State.JAMMING):
        choice = AidSelector().choose(0, state, ALL, ())
        assert choice.methods == (PSEUDOLITES, SEABED)
        assert all(not f.source.startswith("peer") for f in choice.fixes)


def test_signal_lost_uses_nearby_ships_too():
    choice = AidSelector().choose(0, State.LOST, ALL, ())
    assert choice.methods == (PSEUDOLITES, PEERS, SEABED)
    only_peers = AidSelector().choose(0, State.LOST, {PEERS: PEER}, ())
    assert only_peers.methods == (PEERS,)


def test_falls_back_to_dead_reckoning_when_nothing_is_available():
    choice = AidSelector().choose(0, State.SPOOFING, {PEERS: PEER}, ())
    assert choice.methods == ("dead_reckoning",) and choice.fixes == ()
    assert "dead reckoning" in choice.reason


def test_recovering_keeps_the_rules_of_the_alarm():
    sel = AidSelector()
    sel.choose(0, State.SPOOFING, ALL, ())
    assert PEERS not in sel.choose(1, State.RECOVERING, ALL, ()).methods


def test_a_method_whose_fixes_keep_being_rejected_is_dropped_for_a_while():
    sel = AidSelector()
    for t in range(REJECT_LIMIT + 1):
        choice = sel.choose(t, State.JAMMING, {PSEUDOLITES: PL}, ())  # never accepted
    assert choice.methods == ("dead_reckoning",)
    assert "Dropped" in choice.reason
    later = sel.choose(REJECT_LIMIT + BAN_S + 1, State.JAMMING, {PSEUDOLITES: PL}, ())
    assert later.methods == (PSEUDOLITES,)


def _event_rows(run):
    sc = run.scenario
    return [r for r in run.rows if sc.event_start <= r.t < sc.event_end + 120]


def test_auto_avoids_the_spoofed_ships_and_matches_the_best_method():
    auto = run_scenario("smart_spoof", solution="auto")
    rows = _event_rows(auto)
    assert not any(s.startswith("peer") for r in rows for s in r.result.aux_used)
    assert max(r.guard_error for r in rows) < 50.0


def test_auto_falls_back_while_jammed_shore_stations_are_too_few():
    rows = _event_rows(run_scenario("jamming", solution="auto"))
    first_backup = next(r for r in rows if r.aid.selection.methods[0] not in ("gnss", "blend"))
    assert PSEUDOLITES not in first_backup.aid.selection.methods  # only 2 stations heard
    assert any(PSEUDOLITES in r.aid.selection.methods for r in rows)
