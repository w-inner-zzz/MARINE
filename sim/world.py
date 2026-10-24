"""Simulated ship, sea, satellites and attackers.

Truth moves with the hidden sea current; sensors report it with bias and
noise. Every attack only changes what the GNSS receiver and sensors report.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

import numpy as np

from marine_guard import GnssEpoch, SatInfo, ShipSensors

from .chart import SyntheticChart
from .scenarios import Scenario

KNOT_MPS = 0.514444

# Ship and sea
SHIP_SPEED_MPS = 12 * KNOT_MPS
SHIP_HEADING_DEG = 90.0
SEA_CURRENT_MPS = (0.0, 0.4)  # (east, north), unknown to the guard
COMPASS_BIAS_DEG = 0.3
COMPASS_NOISE_DEG = 0.2
SPEED_LOG_NOISE_MPS = 0.05
DEPTH_NOISE_M = 1.0
RADAR_NOISE_M = 15.0

# Satellites and receiver
SATELLITE_COUNT = 12
VISIBLE_COUNT = 10
TRACKING_THRESHOLD_DBHZ = 28.0  # keep tracking a locked satellite down to this
ACQUISITION_THRESHOLD_DBHZ = 33.0  # (re)acquiring a satellite needs more signal
CN0_NOISE_DB = 1.0
BLOCKED_CN0_DBHZ = 20.0  # satellites hidden behind the superstructure
AGC_NORMAL_DB = 20.0
AGC_NOISE_DB = 0.3
GNSS_NOISE_M = 2.0
CLOCK_ERROR_S = 0.01
CLOCK_NOISE_S = 0.002
MIN_SATS_FOR_FIX = 4

# Attacks
INTERFERENCE_SUBSET = 4
INTERFERENCE_LOCK_LOSS = 2
INTERFERENCE_WOBBLE_DB = 1.5
INTERFERENCE_AGC_RISE_DB = 1.0
INTERFERENCE_MULTIPATH_M = 5.7  # with the 2 m receiver noise: about 3x normal
MULTIPATH_CORRELATION_S = 30.0  # multipath error wanders slowly, not white
JAMMING_CN0_DROP_DB = 20.0
JAMMING_AGC_RISE_DB = 15.0
JAMMED_FIX_NOISE_M = 50.0
SPOOF_CN0_DBHZ = 52.0
SPOOF_CN0_STD_DB = 0.6
SPOOF_AZIMUTH_SPREAD_DEG = 3.0
SPOOF_AGC_RISE_DB = 1.5
SPOOF_OFFSET_M = (1500.0, 2000.0)
SMART_SPOOF_DRAG_MPS = 1.2


@dataclass(frozen=True)
class Satellite:
    id: int
    azimuth_deg: float
    elevation_deg: float
    visible: bool

    @property
    def healthy_cn0(self) -> float:
        return 35.0 + 15.0 * math.sin(math.radians(self.elevation_deg))


class World:
    """One simulated run. Call advance() then epoch() and sensors() each second."""

    def __init__(self, scenario: Scenario, seed: int):
        self.scenario = scenario
        self.chart = SyntheticChart()
        self.rng = np.random.default_rng(seed)
        self.t = 0.0
        self.true_x = 0.0
        self.true_y = 0.0
        self.true_heading_deg = SHIP_HEADING_DEG
        self.constellation = self._make_constellation()
        self._locked_ids: Set[int] = set()

        visible_ids = [s.id for s in self.constellation if s.visible]
        subset = self.rng.choice(visible_ids, INTERFERENCE_SUBSET, replace=False)
        self._weakening_db = {int(i): float(self.rng.uniform(3.0, 6.0)) for i in subset}
        self._lock_loss_ids = {int(i) for i in subset[:INTERFERENCE_LOCK_LOSS]}
        self._multipath_error = np.zeros(2)
        self._spoof_azimuth = float(self.rng.uniform(0.0, 360.0))
        self._spoof_elevations = self.rng.uniform(15.0, 75.0, SATELLITE_COUNT)

    def _make_constellation(self) -> List[Satellite]:
        azimuths = self.rng.uniform(0.0, 360.0, SATELLITE_COUNT)
        # Stratified uniform draw over 10-80 deg: still random, but the
        # elevations (and so the signal strengths) never bunch together.
        strata = (np.arange(SATELLITE_COUNT) + self.rng.uniform(0, 1, SATELLITE_COUNT))
        elevations = self.rng.permutation(10.0 + 70.0 * strata / SATELLITE_COUNT)
        return [Satellite(i + 1, float(az), float(el), i < VISIBLE_COUNT)
                for i, (az, el) in enumerate(zip(azimuths, elevations))]

    # ------------------------------------------------------------- truth

    @property
    def true_position(self) -> Tuple[float, float]:
        return (self.true_x, self.true_y)

    def advance(self, dt: float = 1.0) -> None:
        heading = math.radians(self.true_heading_deg)
        self.true_x += (SHIP_SPEED_MPS * math.sin(heading) + SEA_CURRENT_MPS[0]) * dt
        self.true_y += (SHIP_SPEED_MPS * math.cos(heading) + SEA_CURRENT_MPS[1]) * dt
        self.t += dt

    # ----------------------------------------------------------- sensors

    def sensors(self) -> ShipSensors:
        noise = self.rng.normal
        return ShipSensors(
            heading_deg=self.true_heading_deg + COMPASS_BIAS_DEG + noise(0, COMPASS_NOISE_DEG),
            speed_through_water_mps=SHIP_SPEED_MPS + noise(0, SPEED_LOG_NOISE_MPS),
            depth_m=self.chart.depth_at(*self.true_position) + noise(0, DEPTH_NOISE_M),
            radar_range_to_coast_m=self._radar_range(noise(0, RADAR_NOISE_M)),
        )

    def _radar_range(self, noise_m: float) -> Optional[float]:
        coast_y = self.chart.coast_y_at(*self.true_position)
        return None if coast_y is None else coast_y - self.true_y + noise_m

    # -------------------------------------------------------------- GNSS

    def epoch(self) -> GnssEpoch:
        attack = self.scenario.kind if self.scenario.in_event(self.t) else "normal"
        builders = {
            "normal": self._normal_epoch,
            "interference": self._interference_epoch,
            "jamming": self._jamming_epoch,
            "crude_spoof": self._crude_spoof_epoch,
            "smart_spoof": self._smart_spoof_epoch,
            "lost": self._lost_epoch,
        }
        return builders[attack]()

    def _cn0_readings(self) -> List[Tuple[Satellite, float]]:
        readings = []
        for sat in self.constellation:
            base = sat.healthy_cn0 if sat.visible else BLOCKED_CN0_DBHZ
            readings.append((sat, base + self.rng.normal(0, CN0_NOISE_DB)))
        return readings

    def _make_epoch(self, readings: List[Tuple[Satellite, float]], agc_db: float,
                    position_noise_m: float,
                    offset: Tuple[float, ...] = (0.0, 0.0)) -> GnssEpoch:
        """Assemble an epoch; the receiver keeps satellites it has locked while
        C/N0 >= 28, (re)acquires them at >= 33, and produces a position once
        4 or more are tracked."""
        sats = tuple(
            SatInfo(s.id, s.azimuth_deg, s.elevation_deg, round(cn0, 2),
                    self._is_tracked(s.id, cn0))
            for s, cn0 in readings
        )
        self._locked_ids = {s.id for s in sats if s.tracked}
        position: Optional[Tuple[float, float]] = None
        clock: Optional[float] = None
        if sum(s.tracked for s in sats) >= MIN_SATS_FOR_FIX:
            position = (
                self.true_x + offset[0] + self.rng.normal(0, position_noise_m),
                self.true_y + offset[1] + self.rng.normal(0, position_noise_m),
            )
            clock = CLOCK_ERROR_S + self.rng.normal(0, CLOCK_NOISE_S)
        return GnssEpoch(self.t, sats, agc_db, position, clock)

    def _is_tracked(self, sat_id: int, cn0: float) -> bool:
        if sat_id in self._locked_ids:
            return cn0 >= TRACKING_THRESHOLD_DBHZ
        return cn0 >= ACQUISITION_THRESHOLD_DBHZ

    def _agc(self, rise_db: float = 0.0) -> float:
        return AGC_NORMAL_DB + rise_db + self.rng.normal(0, AGC_NOISE_DB)

    def _normal_epoch(self) -> GnssEpoch:
        return self._make_epoch(self._cn0_readings(), self._agc(), GNSS_NOISE_M)

    def _interference_epoch(self) -> GnssEpoch:
        readings = []
        for sat, cn0 in self._cn0_readings():
            if sat.id in self._weakening_db:
                cn0 -= self._weakening_db[sat.id] + abs(self.rng.normal(0, INTERFERENCE_WOBBLE_DB))
            if sat.id in self._lock_loss_ids:
                cn0 = min(cn0, TRACKING_THRESHOLD_DBHZ - 1.0)  # multipath breaks lock
            readings.append((sat, cn0))
        # First-order (AR-1) random walk: correlated over about 30 s.
        keep = math.exp(-1.0 / MULTIPATH_CORRELATION_S)
        self._multipath_error = (keep * self._multipath_error + math.sqrt(1 - keep ** 2)
                                 * self.rng.normal(0, INTERFERENCE_MULTIPATH_M, 2))
        return self._make_epoch(readings, self._agc(INTERFERENCE_AGC_RISE_DB),
                                GNSS_NOISE_M, tuple(self._multipath_error))

    def _jamming_epoch(self) -> GnssEpoch:
        readings = [(s, cn0 - JAMMING_CN0_DROP_DB) for s, cn0 in self._cn0_readings()]
        return self._make_epoch(readings, self._agc(JAMMING_AGC_RISE_DB), JAMMED_FIX_NOISE_M)

    def _crude_spoof_epoch(self) -> GnssEpoch:
        """One transmitter imitates 12 satellites: all equally strong, all
        arriving from roughly the same direction."""
        readings = []
        for i in range(SATELLITE_COUNT):
            azimuth = (self._spoof_azimuth
                       + self.rng.normal(0, SPOOF_AZIMUTH_SPREAD_DEG)) % 360.0
            fake = Satellite(i + 1, azimuth, float(self._spoof_elevations[i]), True)
            readings.append((fake, self.rng.normal(SPOOF_CN0_DBHZ, SPOOF_CN0_STD_DB)))
        return self._make_epoch(readings, self._agc(SPOOF_AGC_RISE_DB), GNSS_NOISE_M,
                                SPOOF_OFFSET_M)

    def _smart_spoof_epoch(self) -> GnssEpoch:
        drag = SMART_SPOOF_DRAG_MPS * (self.t - self.scenario.event_start)
        return self._make_epoch(self._cn0_readings(), self._agc(), GNSS_NOISE_M,
                                (0.0, drag))

    def _lost_epoch(self) -> GnssEpoch:
        self._locked_ids = set()
        return GnssEpoch(self.t, (), self._agc(), None, None)
