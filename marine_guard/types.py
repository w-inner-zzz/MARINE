"""Input and output records of the guard.

Coordinates are local metres: x = east, y = north. Headings are degrees
clockwise from north. Signal strength (C/N0) is in dB-Hz, noise floor in dB.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, Tuple

Position = Tuple[float, float]


class State(str, Enum):
    TRUSTED = "TRUSTED"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    LOST = "LOST"
    JAMMING = "JAMMING"
    SPOOFING = "SPOOFING"


HARD_STATES = frozenset({State.LOST, State.JAMMING, State.SPOOFING})
BACKUP_STATES = HARD_STATES | {State.RECOVERING}


class Chart(Protocol):
    """Anything that can answer depth and water questions about a position
    in local metres.

    A chart may also offer coast_y_at(x, y) -> Optional[float]: the north
    coordinate of the first coast straight north of (x, y). The radar fix
    uses it; without it the guard assumes a straight coast at config.coast_y.
    """

    def depth_at(self, x: float, y: float) -> float: ...

    def is_water(self, x: float, y: float) -> bool: ...


# ---------------------------------------------------------------- inputs


@dataclass(frozen=True)
class SatInfo:
    id: int
    azimuth_deg: float
    elevation_deg: float
    cn0_dbhz: float
    tracked: bool


@dataclass(frozen=True)
class GnssEpoch:
    timestamp: float
    satellites: Tuple[SatInfo, ...]
    agc_db: float
    position: Optional[Position]
    gnss_time_error_s: Optional[float]
    hdop: Optional[float] = None
    """Computed from the tracked satellites when not given."""

    @property
    def tracked(self) -> Tuple[SatInfo, ...]:
        return tuple(s for s in self.satellites if s.tracked)


@dataclass(frozen=True)
class ShipSensors:
    heading_deg: float
    speed_through_water_mps: float
    depth_m: Optional[float]
    radar_range_to_coast_m: Optional[float]


@dataclass(frozen=True)
class AuxFix:
    """An independent position fix from a non-GNSS aid, for example shore
    pseudolites or a nearby ship tracked by radar. The guard checks it for
    plausibility and uses it only while GNSS is not trusted."""

    source: str
    """Short name, e.g. "pseudolite" or "peer:2"."""
    position: Position
    sigma_m: float
    """Accuracy (one standard deviation, m): east-west, and also north-south
    unless sigma_north_m is given. math.inf means no information on that axis."""
    sigma_north_m: Optional[float] = None
    """North-south accuracy when it differs from east-west (m)."""

    @property
    def sigma_north(self) -> float:
        return self.sigma_m if self.sigma_north_m is None else self.sigma_north_m


# ---------------------------------------------------------------- outputs


@dataclass(frozen=True)
class CheckResult:
    """One health check. passed is None when the check could not be run
    (for example, no GNSS position to compare)."""

    name: str
    passed: Optional[bool]
    value: Optional[float]
    threshold: Optional[float]
    text: str
    verdict_if_failed: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "value": self.value,
            "threshold": self.threshold,
            "text": self.text,
            "verdict_if_failed": self.verdict_if_failed,
        }


@dataclass(frozen=True)
class Action:
    """What the boat and crew should do in a given state."""

    position_source: str
    autopilot_mode: str
    recommended_speed_kn: str
    lookout_level: str
    crew_instructions: Tuple[str, ...]
    alerts: Tuple[str, ...]
    why_it_matters: str = ""
    steps: Tuple[str, ...] = ()
    """Ordered checklist for the bridge team."""
    rules: Tuple[str, ...] = ()
    """Short references to the rules that still apply."""

    def to_dict(self) -> dict:
        return {
            "position_source": self.position_source,
            "autopilot_mode": self.autopilot_mode,
            "recommended_speed_kn": self.recommended_speed_kn,
            "lookout_level": self.lookout_level,
            "crew_instructions": list(self.crew_instructions),
            "alerts": list(self.alerts),
            "why_it_matters": self.why_it_matters,
            "steps": list(self.steps),
            "rules": list(self.rules),
        }


@dataclass(frozen=True)
class GuardResult:
    timestamp: float
    state: State
    position: Position
    uncertainty_m: float
    reason: str
    checks: Tuple[CheckResult, ...]
    hdop: Optional[float]
    satellite_count: int
    action: Action
    verdict: str = "OK"
    """Raw verdict of the health checks this second (before the state machine)."""
    clean_seconds: int = 0
    clean_needed: int = 0
    fixes: Tuple[str, ...] = field(default_factory=tuple)
    """Backup fixes applied this second: "radar" and/or "depth"."""
    lat_deg: Optional[float] = None
    lon_deg: Optional[float] = None
    """Output position as latitude/longitude."""
    gnss_position: Optional[Position] = None
    gnss_lat_deg: Optional[float] = None
    gnss_lon_deg: Optional[float] = None
    """What the receiver reported, in local metres and latitude/longitude."""
    baseline_cn0_dbhz: Optional[float] = None
    baseline_agc_db: Optional[float] = None
    baseline_clock_s: Optional[float] = None
    """The learned 'normal' this second was compared with."""
    aux_used: Tuple[str, ...] = field(default_factory=tuple)
    """Sources of the independent fixes (AuxFix) accepted this second."""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "state": self.state.value,
            "position": list(self.position),
            "uncertainty_m": self.uncertainty_m,
            "reason": self.reason,
            "checks": [c.to_dict() for c in self.checks],
            "hdop": self.hdop,
            "satellite_count": self.satellite_count,
            "action": self.action.to_dict(),
            "verdict": self.verdict,
            "clean_seconds": self.clean_seconds,
            "clean_needed": self.clean_needed,
            "fixes": list(self.fixes),
            "lat_deg": self.lat_deg,
            "lon_deg": self.lon_deg,
            "gnss_position": None if self.gnss_position is None else list(self.gnss_position),
            "gnss_lat_deg": self.gnss_lat_deg,
            "gnss_lon_deg": self.gnss_lon_deg,
            "baseline_cn0_dbhz": self.baseline_cn0_dbhz,
            "baseline_agc_db": self.baseline_agc_db,
            "baseline_clock_s": self.baseline_clock_s,
            "aux_used": list(self.aux_used),
        }
