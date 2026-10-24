"""Backup navigation: dead reckoning, uncertainty growth and position fixes
from radar (range to coast) and depth-profile matching against the chart."""

import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .config import GuardConfig
from .types import Chart, Position


@dataclass(frozen=True)
class DepthSample:
    """Dead-reckoning position and sounder depth at one second."""

    x: float
    y: float
    depth: float


def fuse(est: float, sigma: float, meas: float, meas_sigma: float) -> Tuple[float, float]:
    """Combine an estimate with a measurement, weighting by their accuracy
    (a one-dimensional Kalman update). Returns (new_estimate, new_sigma)."""
    gain = sigma ** 2 / (sigma ** 2 + meas_sigma ** 2)
    return est + gain * (meas - est), sigma * math.sqrt(1.0 - gain)


def depth_search_reach(sigma_x: float, cfg: GuardConfig) -> float:
    """How far east/west to search, rounded down to a whole number of steps."""
    reach = max(cfg.depth_min_reach_m, min(int(3 * sigma_x), cfg.depth_max_reach_m))
    return cfg.depth_step_m * math.floor(reach / cfg.depth_step_m)


def match_depth_profile(samples: Sequence[DepthSample], chart: Chart,
                        sigma_x: float, cfg: GuardConfig) -> Optional[float]:
    """Slide the recorded depth profile east/west over the chart and return
    the shift (m) that fits best, or None if there is no trustworthy match."""
    if len(samples) < cfg.depth_window_s:
        return None
    depths = [s.depth for s in samples]
    if max(depths) - min(depths) < cfg.depth_min_range_m:
        return None  # flat seabed: every shift fits equally well

    reach = depth_search_reach(sigma_x, cfg)
    steps = int(round(reach / cfg.depth_step_m))
    best_shift, best_cost = 0.0, math.inf
    for k in range(-steps, steps + 1):
        shift = k * cfg.depth_step_m
        cost = sum((s.depth - chart.depth_at(s.x + shift, s.y)) ** 2
                   for s in samples) / len(samples)
        if cost < best_cost:
            best_shift, best_cost = shift, cost

    if best_cost < cfg.depth_max_cost and abs(best_shift) < reach:
        return best_shift
    return None


class DeadReckoner:
    """Position from heading, speed and learned sea current, with a growing
    uncertainty per axis and a short history for depth matching."""

    def __init__(self, position: Position, config: GuardConfig):
        self._cfg = config
        self.x, self.y = position
        self.sigma_x = self.sigma_y = config.start_sigma
        self.current_east = 0.0
        self.current_north = 0.0
        self.history: deque = deque(maxlen=config.depth_window_s)

    @property
    def position(self) -> Position:
        return (self.x, self.y)

    @property
    def total_uncertainty(self) -> float:
        return math.hypot(self.sigma_x, self.sigma_y)

    def step(self, heading_deg: float, speed_mps: float, dt: float,
             depth_m: Optional[float]) -> None:
        heading = math.radians(heading_deg)
        self.x += (speed_mps * math.sin(heading) + self.current_east) * dt
        self.y += (speed_mps * math.cos(heading) + self.current_north) * dt
        growth = (self._cfg.drift_per_speed * speed_mps + self._cfg.drift_floor) * dt
        self.sigma_x += growth
        self.sigma_y += growth
        if depth_m is not None:
            self.history.append(DepthSample(self.x, self.y, depth_m))

    def move_by(self, dx: float, dy: float) -> None:
        """Correct the position; the recorded track moves with it so later
        depth matches compare a consistent profile."""
        self.x += dx
        self.y += dy
        self.history = deque((DepthSample(s.x + dx, s.y + dy, s.depth)
                              for s in self.history), maxlen=self.history.maxlen)

    def anchor_to(self, position: Position) -> None:
        """Snap to a trusted GNSS position and reset the uncertainty."""
        self.move_by(position[0] - self.x, position[1] - self.y)
        self.sigma_x = self.sigma_y = self._cfg.start_sigma

    def learn_current(self, gnss: Position, seconds_since_anchor: float) -> None:
        """The drift since the last anchor is mostly unmodelled sea current."""
        if seconds_since_anchor <= 0:
            return
        gain = self._cfg.current_learn_gain
        self.current_east += gain * (gnss[0] - self.x) / seconds_since_anchor
        self.current_north += gain * (gnss[1] - self.y) / seconds_since_anchor

    def radar_fix(self, range_to_coast_m: float, coast_y: float) -> bool:
        """The radar measures the range straight north to the coast, which
        lies at coast_y: that gives our north coordinate. Returns True if the
        fix was accepted."""
        cfg = self._cfg
        measured_y = coast_y - range_to_coast_m
        if abs(measured_y - self.y) >= cfg.radar_gate_k * self.sigma_y + cfg.radar_gate_floor_m:
            return False
        new_y, self.sigma_y = fuse(self.y, self.sigma_y, measured_y, cfg.radar_sigma)
        self.move_by(0.0, new_y - self.y)
        return True

    def aux_fix(self, position: Position, sigma_east_m: float, sigma_north_m: float) -> bool:
        """Fuse an independent position fix if it is plausible on both axes.
        Returns True if it was accepted. An axis with infinite sigma carries
        no information: it always passes and is not changed."""
        cfg = self._cfg
        for gap, own, other in ((position[0] - self.x, self.sigma_x, sigma_east_m),
                                (position[1] - self.y, self.sigma_y, sigma_north_m)):
            if abs(gap) >= cfg.aux_gate_k * math.hypot(own, other) + cfg.aux_gate_floor_m:
                return False
        new_x, self.sigma_x = fuse(self.x, self.sigma_x, position[0], sigma_east_m)
        new_y, self.sigma_y = fuse(self.y, self.sigma_y, position[1], sigma_north_m)
        self.move_by(new_x - self.x, new_y - self.y)
        return True

    def depth_fix(self, chart: Chart) -> bool:
        """Correct the east coordinate by matching the depth profile.
        Returns True if the fix was accepted."""
        shift = match_depth_profile(list(self.history), chart, self.sigma_x, self._cfg)
        if shift is None:
            return False
        new_x, self.sigma_x = fuse(self.x, self.sigma_x, self.x + shift,
                                   self._cfg.depth_fix_sigma)
        self.move_by(new_x - self.x, 0.0)
        return True
