"""Navigation aids: pseudolites and nearby ships (unencrypted)."""

import math
from functools import lru_cache

import pytest

from marine_guard import AuxFix, GnssGuard, GnssEpoch, ShipSensors, State
from marine_guard.aux import peer_fix, pseudolite_fix
from sim.runner import run_scenario


@lru_cache(maxsize=None)
def run_with(key, solution):
    return run_scenario(key, solution=solution)


def event_rows(run):
    sc = run.scenario
    return [r for r in run.rows if sc.event_start <= r.t < sc.event_end + 120]


def worst_event_error(run):
    return max(r.guard_error for r in event_rows(run))


def test_pseudolite_solver_recovers_position_and_ignores_clock():
    stations = [(-20000, 25000, 30), (15000, -20000, 30), (40000, -8000, 30), (-10000, -40000, 30)]
    truth, clock = (1200.0, -300.0), 150.0
    ranges = [math.sqrt((truth[0] - x) ** 2 + (truth[1] - y) ** 2 + h * h) + clock
              for x, y, h in stations]
    fix = pseudolite_fix(stations, ranges, [5.0] * 4, (0.0, 0.0), max_hdop=5.0)
    assert math.hypot(fix.position[0] - truth[0], fix.position[1] - truth[1]) < 0.01
    assert pseudolite_fix(stations[:2], ranges[:2], [5.0] * 2, (0.0, 0.0), 5.0) is None


def test_peer_fix_subtracts_the_radar_vector():
    fix = peer_fix("peer:0", (5000.0, 3000.0), 5000.0, 90.0, 15.0, 0.5)
    assert fix.position == pytest.approx((0.0, 3000.0), abs=1e-6)
    assert fix.sigma_m > 15.0


def test_no_solution_changes_nothing(run):
    for key in ("jamming", "smart_spoof"):
        base, none = run(key), run_with(key, "none")
        assert [r.guard_position for r in base.rows] == [r.guard_position for r in none.rows]


def test_guard_rejects_an_implausible_fix_and_ignores_fixes_while_trusted():
    guard = GnssGuard()
    sensors = ShipSensors(90.0, 5.0, None, None)
    from marine_guard import SatInfo
    sats = tuple(SatInfo(i, 36.0 * i, 15 + 7 * i, 38 + 1.3 * i, True) for i in range(10))
    far = (AuxFix("pseudolite", (50_000.0, 0.0), 5.0),)
    result = guard.update(GnssEpoch(0, sats, 20.0, (0.0, 0.0), 0.01), sensors, far)
    assert result.state == State.TRUSTED and result.aux_used == ()
    result = guard.update(GnssEpoch(1, (), 20.0, None, None), sensors, far)
    assert result.state == State.LOST and result.aux_used == ()  # 50 km away: rejected
    near = (AuxFix("pseudolite", (6.0, 1.0), 5.0),)
    result = guard.update(GnssEpoch(2, (), 20.0, None, None), sensors, near)
    assert result.aux_used == ("pseudolite",)


def test_pseudolites_keep_the_ship_accurate_without_satellites(run):
    with_pl = run_with("lost_no_fixes", "pseudolites")
    assert worst_event_error(with_pl) < 20.0
    assert worst_event_error(with_pl) < worst_event_error(run("lost_no_fixes"))
    used = [r for r in event_rows(with_pl) if r.result.aux_used]
    assert len(used) > 250


def test_pseudolites_still_work_while_jammed():
    jam = run_with("jamming", "pseudolites")
    in_event = [r for r in jam.rows if jam.scenario.in_event(r.t)]
    assert all(r.aid.stations_heard for r in in_event)
    # Jamming weakens the stations too: with fewer than 3 heard there is no fix.
    assert all(not r.aid.fixes for r in in_event if len(r.aid.stations_heard) < 3)
    assert sum(bool(r.result.aux_used) for r in in_event) > 0.75 * len(in_event)
    assert worst_event_error(jam) < 40.0


def test_spoofed_nearby_ships_can_lead_the_ship_astray():
    peers, pseudolites = run_with("smart_spoof", "peers"), run_with("smart_spoof", "pseudolites")
    assert worst_event_error(peers) > 200.0       # dragged along by spoofed neighbours
    assert worst_event_error(pseudolites) < 50.0  # shore stations are not spoofed


def test_crude_spoofed_neighbours_are_rejected_only_the_honest_one_is_used():
    crude = run_with("crude_spoof", "peers")
    used = {s for r in crude.rows if crude.scenario.in_event(r.t) for s in r.result.aux_used}
    assert used == {"peer:3"}  # the ship outside the attack area
    assert worst_event_error(crude) < 60.0


def test_nearby_ships_help_when_only_our_receiver_fails(run):
    assert worst_event_error(run_with("lost_no_fixes", "peers")) < 30.0
