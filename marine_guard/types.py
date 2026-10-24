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
    """Anything that can answer depth and water questions about a position."""

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

    def to_dict(self) -> dict:
        return {
            "position_source": self.position_source,
            "autopilot_mode": self.autopilot_mode,
            "recommended_speed_kn": self.recommended_speed_kn,
            "lookout_level": self.lookout_level,
            "crew_instructions": list(self.crew_instructions),
            "alerts": list(self.alerts),
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
        }
