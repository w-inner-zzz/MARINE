"""Run a scenario second by second and record what happened."""

import math
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

from marine_guard import GnssEpoch, GnssGuard, GuardConfig, GuardResult, ShipSensors, State

from .scenarios import SCENARIOS, Scenario
from .world import World

Point = Tuple[float, float]

DEFAULT_SEED = 2


@dataclass(frozen=True)
class Row:
    t: float
    true_position: Point
    gnss_position: Optional[Point]
    guard_position: Point
    naive_position: Point
    """A receiver that blindly trusts GNSS and holds its last fix."""
    guard_error: float
    naive_error: float
    true_heading_deg: float
    result: GuardResult
    epoch: GnssEpoch
    sensors: ShipSensors


@dataclass(frozen=True)
class Run:
    scenario: Scenario
    rows: Tuple[Row, ...]
    config: GuardConfig


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def run_scenario(key: str, seed: int = DEFAULT_SEED, config: Optional[GuardConfig] = None) -> Run:
    scenario = SCENARIOS[key]
    config = replace(config or GuardConfig(),
                     use_radar_fixes=scenario.fixes_enabled,
                     use_depth_fixes=scenario.fixes_enabled)
    world = World(scenario, seed)
    guard = GnssGuard(chart=world.chart, config=config)

    rows: List[Row] = []
    naive: Point = world.true_position
    for step in range(scenario.duration):
        if step > 0:
            world.advance()
        epoch, sensors = world.epoch(), world.sensors()
        result = guard.update(epoch, sensors)
        if epoch.position is not None:
            naive = epoch.position
        truth = world.true_position
        rows.append(Row(
            t=world.t,
            true_position=truth,
            gnss_position=epoch.position,
            guard_position=result.position,
            naive_position=naive,
            guard_error=_distance(result.position, truth),
            naive_error=_distance(naive, truth),
            true_heading_deg=world.true_heading_deg,
            result=result,
            epoch=epoch,
            sensors=sensors,
        ))
    return Run(scenario, tuple(rows), config)


@dataclass(frozen=True)
class Summary:
    detection_s: Optional[float]
    """Seconds from event start to the first non-TRUSTED state."""
    back_to_trusted_s: Optional[float]
    """Seconds from event end until TRUSTED for good."""
    worst_guard_error_m: float
    worst_naive_error_m: float
    seconds_not_trusted: int


def summarize(run: Run) -> Summary:
    sc, rows = run.scenario, run.rows
    detection = back = None
    if sc.event_start is not None:
        alarm = next((r.t for r in rows
                      if r.t >= sc.event_start and r.result.state != State.TRUSTED), None)
        if alarm is not None:
            detection = alarm - sc.event_start
        last_bad = max((r.t for r in rows if r.result.state != State.TRUSTED), default=None)
        if last_bad is not None and last_bad < rows[-1].t:
            back = max(0.0, last_bad + 1 - sc.event_end)
    return Summary(
        detection_s=detection,
        back_to_trusted_s=back,
        worst_guard_error_m=max(r.guard_error for r in rows),
        worst_naive_error_m=max(r.naive_error for r in rows),
        seconds_not_trusted=sum(r.result.state != State.TRUSTED for r in rows),
    )
