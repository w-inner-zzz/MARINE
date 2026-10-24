"""End-to-end behaviour of the guard in every simulated scenario."""

import pytest

from marine_guard import State
from sim.scenarios import SCENARIOS

HARD = {State.LOST, State.JAMMING, State.SPOOFING}


def first_time(run, condition, after):
    return next((r.t for r in run.rows if r.t >= after and condition(r.result)), None)


def seconds_until(run, state, after):
    t = first_time(run, lambda res: res.state == state, after)
    assert t is not None, f"never reached {state.value} after {after} s"
    return t - after


def worst_errors(run):
    return (max(r.guard_error for r in run.rows), max(r.naive_error for r in run.rows))


def test_normal_stays_trusted(run):
    r = run("normal")
    assert all(row.result.state == State.TRUSTED for row in r.rows)
    assert worst_errors(r)[0] < 10.0


def test_regular_interference_raises_no_hard_alarm(run):
    r = run("interference")
    assert not any(row.result.state in HARD for row in r.rows)


@pytest.mark.parametrize("key, alarm, detect_s, guard_max, naive_min", [
    ("jamming", State.JAMMING, 2, 40.0, 200.0),
    ("crude_spoof", State.SPOOFING, 2, 50.0, 2000.0),
    ("smart_spoof", State.SPOOFING, 60, 50.0, 300.0),
    ("lost", State.LOST, 2, 50.0, 1500.0),
])
def test_attack_detected_and_recovered(run, key, alarm, detect_s, guard_max, naive_min):
    r = run(key)
    sc = r.scenario
    assert seconds_until(r, alarm, sc.event_start) <= detect_s
    assert seconds_until(r, State.TRUSTED, sc.event_end) <= 70
    guard_worst, naive_worst = worst_errors(r)
    assert guard_worst < guard_max
    assert naive_worst > naive_min


def test_smart_spoof_noticed_early(run):
    r = run("smart_spoof")
    t = first_time(r, lambda res: res.state != State.TRUSTED, r.scenario.event_start)
    assert t - r.scenario.event_start <= 20


def _uncertainty_at_end_of_outage(r):
    end = r.scenario.event_end - 1
    return next(row.result.uncertainty_m for row in r.rows if row.t == end)


def test_fixes_shrink_the_uncertainty_circle(run):
    assert _uncertainty_at_end_of_outage(run("lost_no_fixes")) > 60.0
    assert _uncertainty_at_end_of_outage(run("lost")) < 25.0


@pytest.mark.parametrize("key", list(SCENARIOS))
def test_sixty_second_rule(run, key):
    """GNSS is never trusted again sooner than 60 clean seconds after a hard failure."""
    last_hard = None
    previous = State.TRUSTED
    for row in run(key).rows:
        state = row.result.state
        if state in HARD:
            last_hard = row.t
        if state == State.TRUSTED and previous != State.TRUSTED and last_hard is not None:
            assert row.t - last_hard >= 60, f"trusted at {row.t} s, hard failure at {last_hard} s"
            last_hard = None
        previous = state
