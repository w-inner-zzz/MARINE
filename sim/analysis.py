"""After-the-fact analysis of a run for the map: the red path (what GNSS
reported while it was not trusted), the green path (the guard's backup
track), detection moments and 'what would have happened' if GNSS had been
trusted."""

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from marine_guard import State

from .runner import Row, Run

DANGER_DEPTH_M = 10.0
DANGER_LAND_DISTANCE_M = 500.0


def _distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def not_trusted(row: Row) -> bool:
    return row.result.state != State.TRUSTED


@dataclass(frozen=True)
class PathErrors:
    red_worst_m: float
    """Worst distance between the GNSS-reported position and the truth while
    GNSS was not trusted (0 if GNSS reported nothing)."""
    green_worst_m: float
    """Worst distance between the guard's backup position and the truth
    while GNSS was not trusted."""


def path_errors(run: Run) -> PathErrors:
    rows = [r for r in run.rows if not_trusted(r)]
    red = [_distance(r.gnss_position, r.true_position) for r in rows if r.gnss_position]
    green = [r.guard_error for r in rows]
    return PathErrors(max(red, default=0.0), max(green, default=0.0))


@dataclass(frozen=True)
class Detection:
    t: float
    latlon: Tuple[float, float]
    state: State
    reason: str


def detections(run: Run) -> List[Detection]:
    """Every moment the guard stopped trusting GNSS."""
    found, previous = [], State.TRUSTED
    for row in run.rows:
        state = row.result.state
        if previous == State.TRUSTED and state != State.TRUSTED:
            failed = next((c for c in row.result.checks if c.passed is False), None)
            reason = failed.name if failed else row.result.reason
            found.append(Detection(row.t, row.guard_latlon, state, reason))
        previous = state
    return found


@dataclass(frozen=True)
class Danger:
    t: float
    latlon: Tuple[float, float]
    what: str
    distance_to_land_m: float
    depth_m: float
    off_by_m: float
    """How far the GNSS-reported position was from the real ship."""


def first_danger(run: Run, step: int = 5) -> Optional[Danger]:
    """First point of the red path that is on land, in water shallower than
    10 m, or within 500 m of land. Needs a chart with lat/lon questions."""
    chart = run.chart
    if not hasattr(chart, "distance_to_land_m"):
        return None
    for row in run.rows[::step]:
        if not not_trusted(row) or row.gnss_latlon is None:
            continue
        lat, lon = row.gnss_latlon
        depth = chart.depth_latlon(lat, lon)
        land_m = chart.distance_to_land_m(lat, lon, limit_m=2 * DANGER_LAND_DISTANCE_M)
        if land_m == 0.0:
            what = "on land"
        elif depth < DANGER_DEPTH_M:
            what = f"in water only {depth:.1f} m deep"
        elif land_m < DANGER_LAND_DISTANCE_M:
            what = f"{land_m:.0f} m from land"
        else:
            continue
        return Danger(row.t, row.gnss_latlon, what, land_m, depth,
                      _distance(row.gnss_position, row.true_position))
    return None


def downsample(rows: Sequence[Row], every: int) -> List[Row]:
    """Every n-th row, always keeping the last one."""
    picked = list(rows[::every])
    if rows and picked[-1] is not rows[-1]:
        picked.append(rows[-1])
    return picked
