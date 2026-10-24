"""Simulated navigation aids that give the guard independent position fixes.

pseudolites - hypothetical shore ranging stations on the Finnish and Estonian
    coasts (pseudolite / R-Mode style). They transmit near the GNSS band, so a
    jammer weakens them too, but they start much stronger than satellites
    20,000 km away. A spoofer only imitates satellites; the stations are not
    faked. They are received on their own antenna, so a GNSS antenna fault
    does not affect them.
peers - four nearby ships tracked by radar (range and bearing) that broadcast
    their own GNSS positions without encryption. Three share our attack area:
    when we are jammed they broadcast drifting dead-reckoned positions, when we
    are spoofed they broadcast the same fake positions, and can lead us the
    wrong way. The fourth is further away, outside the attack area.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from marine_guard import AuxFix, GuardConfig
from marine_guard.aids import peer_fix, pseudolite_fix
from marine_guard.geometry import LocalFrame

from .scenarios import Scenario
from .world import (COMPASS_BIAS_DEG, JAMMING_AGC_RISE_DB, SMART_SPOOF_DRAG_MPS,
                    TRACKING_THRESHOLD_DBHZ, World)

SOLUTIONS = {
    "none": "None (guard only)",
    "pseudolites": "Pseudolites",
    "peers": "Nearby ships",
}

# --- Pseudolites ---------------------------------------------------------
# Hypothetical sites on headlands and islands around the route.
PSEUDOLITE_SITES = (
    ("Porkkala", 59.980, 24.380),
    ("Suomenlinna", 60.145, 24.985),
    ("Söderskär", 60.110, 25.420),
    ("Emäsalo", 60.200, 25.630),
    ("Pakri", 59.385, 24.040),
    ("Naissaar", 59.560, 24.520),
    ("Prangli", 59.620, 24.980),
    ("Juminda", 59.620, 25.580),
)
STATION_HEIGHT_M = 30.0
MAX_RANGE_M = 45_000.0          # radio horizon for 30 m masts and a ship's antenna
CN0_AT_10_KM_DBHZ = 55.0        # pseudolites are far louder than satellites
RANGE_SIGMA_AT_REF_M = 3.0      # ranging noise at CN0_AT_10_KM_DBHZ
CLOCK_START_M = 100.0           # receiver clock offset, as a distance
CLOCK_DRIFT_MPS = 0.02
CLOCK_WALK_M = 0.3

# --- Nearby ships ----------------------------------------------------------
# (name, east offset m, north offset m, extra east m/s, extra north m/s, in attack area)
PEERS = (
    ("Ship A", -2500.0, 1500.0, 0.00, 0.05, True),
    ("Ship B", 4000.0, -3000.0, -0.20, 0.00, True),
    ("Ship C", 7000.0, 4000.0, 0.10, -0.05, True),
    ("Ship D", -12000.0, -7000.0, 0.30, 0.10, False),
)
RADAR_RANGE_M = 20_000.0
RADAR_RANGE_SIGMA_M = 15.0
RADAR_BEARING_SIGMA_DEG = 0.5
PEER_GNSS_NOISE_M = 2.0
PEER_DR_DRIFT_MPS = 0.15        # how fast a jammed ship's own position drifts


def _distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass(frozen=True)
class AidReport:
    """What the aid offered this second (for display)."""

    fixes: Tuple[AuxFix, ...]
    stations_heard: Tuple[int, ...] = ()
    """Pseudolites: indices of the stations heard."""
    peers: Tuple[Tuple[float, float, bool], ...] = ()
    """Nearby ships: (reported x, reported y, within radar range)."""


class PseudoliteNetwork:
    def __init__(self, frame: LocalFrame, config: GuardConfig, seed: int):
        self.rng = np.random.default_rng(seed + 1000)
        self.config = config
        self.stations = [(*frame.to_xy(lat, lon), STATION_HEIGHT_M) for _, lat, lon in PSEUDOLITE_SITES]
        self.clock_m = CLOCK_START_M
        self.last_fix: Optional[Tuple[float, float]] = None

    def measure(self, world: World) -> AidReport:
        self.clock_m += CLOCK_DRIFT_MPS + self.rng.normal(0, CLOCK_WALK_M)
        jam_db = JAMMING_AGC_RISE_DB if (world.scenario.kind == "jamming"
                                         and world.scenario.in_event(world.t)) else 0.0
        heard, ranges, sigmas = [], [], []
        for i, (sx, sy, sh) in enumerate(self.stations):
            true_range = math.sqrt((world.true_x - sx) ** 2 + (world.true_y - sy) ** 2 + sh * sh)
            if true_range > MAX_RANGE_M:
                continue
            cn0 = CN0_AT_10_KM_DBHZ - 20 * math.log10(true_range / 10_000.0) - jam_db
            if cn0 < TRACKING_THRESHOLD_DBHZ:
                continue
            sigma = RANGE_SIGMA_AT_REF_M * 10 ** ((CN0_AT_10_KM_DBHZ - cn0) / 20)
            heard.append(i)
            sigmas.append(sigma)
            ranges.append(true_range + self.clock_m + self.rng.normal(0, sigma))
        guess = self.last_fix or self._centroid(heard)
        fix = pseudolite_fix([self.stations[i] for i in heard], ranges, sigmas, guess,
                             self.config.max_pseudolite_hdop) if heard else None
        if fix is not None:
            self.last_fix = fix.position
        return AidReport(fixes=(fix,) if fix else (), stations_heard=tuple(heard))

    def _centroid(self, heard: List[int]) -> Tuple[float, float]:
        if not heard:
            return (0.0, 0.0)
        return (sum(self.stations[i][0] for i in heard) / len(heard),
                sum(self.stations[i][1] for i in heard) / len(heard))


class PeerFleet:
    def __init__(self, scenario: Scenario, seed: int):
        self.rng = np.random.default_rng(seed + 2000)
        self.scenario = scenario
        self.drift = [np.zeros(2) for _ in PEERS]
        self.drift_bias = [self.rng.normal(0, PEER_DR_DRIFT_MPS, 2) for _ in PEERS]

    def true_position(self, i: int, world: World) -> Tuple[float, float]:
        _, dx, dy, vx, vy, _ = PEERS[i]
        return (world.true_x + dx + vx * world.t, world.true_y + dy + vy * world.t)

    def reported_position(self, i: int, world: World) -> Tuple[float, float]:
        """What ship i broadcasts: its own (possibly attacked) GNSS position."""
        sc = self.scenario
        x, y = self.true_position(i, world)
        attacked = PEERS[i][5] and sc.in_event(world.t)
        if attacked and sc.kind == "jamming":
            self.drift[i] += self.drift_bias[i] + self.rng.normal(0, 0.05, 2)
            return (x + self.drift[i][0], y + self.drift[i][1])
        self.drift[i] = np.zeros(2)
        noise = self.rng.normal(0, PEER_GNSS_NOISE_M, 2)
        if attacked and sc.kind == "crude_spoof":
            ox, oy = sc.spoof_offset_m
            return (x + ox + noise[0], y + oy + noise[1])
        if attacked and sc.kind == "smart_spoof":
            return (x + noise[0], y + SMART_SPOOF_DRAG_MPS * (world.t - sc.event_start) + noise[1])
        return (x + noise[0], y + noise[1])

    def measure(self, world: World) -> AidReport:
        fixes, peers = [], []
        for i, (name, *_rest) in enumerate(PEERS):
            reported = self.reported_position(i, world)
            tx, ty = self.true_position(i, world)
            true_range = math.hypot(tx - world.true_x, ty - world.true_y)
            in_range = true_range <= RADAR_RANGE_M
            peers.append((reported[0], reported[1], in_range))
            if not in_range:
                continue
            measured_range = true_range + self.rng.normal(0, RADAR_RANGE_SIGMA_M)
            bearing = (math.degrees(math.atan2(tx - world.true_x, ty - world.true_y))
                       + COMPASS_BIAS_DEG + self.rng.normal(0, RADAR_BEARING_SIGMA_DEG))
            fixes.append(peer_fix(f"peer:{i}", reported, measured_range, bearing,
                                  RADAR_RANGE_SIGMA_M, RADAR_BEARING_SIGMA_DEG))
        return AidReport(fixes=tuple(fixes), peers=tuple(peers))


class NoAid:
    def measure(self, world: World) -> AidReport:
        return AidReport(fixes=())


def make_aid(solution: str, scenario: Scenario, frame: LocalFrame, config: GuardConfig,
             seed: int):
    if solution == "pseudolites":
        return PseudoliteNetwork(frame, config, seed)
    if solution == "peers":
        return PeerFleet(scenario, seed)
    if solution == "none":
        return NoAid()
    raise ValueError(f"unknown solution {solution!r}; choose from {list(SOLUTIONS)}")


def station_latlons() -> Dict[str, Tuple[float, float]]:
    return {name: (lat, lon) for name, lat, lon in PSEUDOLITE_SITES}
