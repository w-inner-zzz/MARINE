"""Synthetic nautical chart: rolling seabed, straight coast to the north."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticChart:
    coast_y: float = 3000.0

    def depth_at(self, x: float, y: float) -> float:
        return 60.0 + 25.0 * math.sin(x / 1500.0) + 15.0 * math.cos(y / 1100.0)

    def is_water(self, x: float, y: float) -> bool:
        return y < self.coast_y
