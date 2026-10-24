"""Run a scenario second by second and record what happened."""

import math
from dataclasses import dataclass, replace
from typing import List, Optional, Tuple

from marine_guard import GnssEpoch, GnssGuard, GuardConfig, GuardResult, ShipSensors, State
from marine_guard.geometry import LocalFrame

from .chart import SyntheticChart
from .scenarios import SCENARIOS, VOYAGE_SCENARIOS, Scenario
from .solutions import AidReport, make_aid
from .world import World

Point = Tuple[float, float]

DEFAULT_SEED = 2
VOYAGE_SEED = 8


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
    true_latlon: Point
    gnss_latlon: Optional[Point]
    guard_latlon: Point
    aid: Optional[AidReport] = None
    """What the chosen navigation aid offered this second (None without an aid)."""


@dataclass(frozen=True)
class Run:
    scenario: Scenario
    rows: Tuple[Row, ...]
    config: GuardConfig
    chart: object
    voyage: bool
    solution: str = "none"

    @property
    def frame(self) -> LocalFrame:
        return LocalFrame(self.config.origin_lat_deg, self.config.origin_lon_deg)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def run_scenario(key: str, seed: Optional[int] = None, config: Optional[GuardConfig] = None,
                 voyage: bool = False, solution: str = "none") -> Run:
    """Short 900 s test run on the synthetic chart, or (voyage=True) a 3-hour
    voyage in the Gulf of Finland starting at config.origin_lat/lon_deg."""
    scenario = (VOYAGE_SCENARIOS if voyage else SCENARIOS)[key]
    if seed is None:
        seed = VOYAGE_SEED if voyage else DEFAULT_SEED
    config = replace(config or GuardConfig(),
                     use_radar_fixes=scenario.fixes_enabled,
                     use_depth_fixes=scenario.fixes_enabled)
    if voyage:
        from .baltic import baltic_chart  # loads the land mask: only when needed
        chart = baltic_chart(config.origin_lat_deg, config.origin_lon_deg)
    else:
        chart = SyntheticChart()
    frame = LocalFrame(config.origin_lat_deg, config.origin_lon_deg)
    world = World(scenario, seed, chart)
    guard = GnssGuard(chart=chart, config=config)
    aid = make_aid(solution, scenario, frame, config, seed)

    rows: List[Row] = []
    naive: Point = world.true_position
    for step in range(scenario.duration):
        if step > 0:
            world.advance()
        epoch, sensors = world.epoch(), world.sensors()
        report = aid.measure(world)
        result = guard.update(epoch, sensors, report.fixes)
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
            true_latlon=frame.to_latlon(*truth),
            gnss_latlon=(None if epoch.position is None
                         else (result.gnss_lat_deg, result.gnss_lon_deg)),
            guard_latlon=(result.lat_deg, result.lon_deg),
            aid=None if solution == "none" else report,
        ))
    return Run(scenario, tuple(rows), config, chart, voyage, solution)


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
