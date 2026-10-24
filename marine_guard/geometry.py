"""Geometry: satellite HDOP and the local metres <-> latitude/longitude frame.

HDOP says how much the satellite geometry magnifies range errors into
horizontal position error. Under 2 is good, over 5 is poor.
"""

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from .types import SatInfo

Matrix = List[List[float]]

_SINGULAR_PIVOT = 1e-12


def geometry_row(sat: SatInfo) -> List[float]:
    """Line-of-sight row [east, north, up, clock] of the geometry matrix G."""
    az = math.radians(sat.azimuth_deg)
    el = math.radians(sat.elevation_deg)
    return [
        -math.cos(el) * math.sin(az),
        -math.cos(el) * math.cos(az),
        -math.sin(el),
        1.0,
    ]


def invert(matrix: Sequence[Sequence[float]]) -> Optional[Matrix]:
    """Gauss-Jordan inverse of a square matrix with partial pivoting. None if singular."""
    n = len(matrix)
    work = [list(map(float, row)) + [1.0 if i == j else 0.0 for j in range(n)]
            for i, row in enumerate(matrix)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(work[r][col]))
        if abs(work[pivot_row][col]) < _SINGULAR_PIVOT:
            return None
        work[col], work[pivot_row] = work[pivot_row], work[col]
        pivot = work[col][col]
        work[col] = [v / pivot for v in work[col]]
        for r in range(n):
            if r != col:
                factor = work[r][col]
                work[r] = [a - factor * b for a, b in zip(work[r], work[col])]
    return [row[n:] for row in work]


def invert_4x4(matrix: Sequence[Sequence[float]]) -> Optional[Matrix]:
    """Inverse of the 4x4 normal matrix used for HDOP. None if singular."""
    if len(matrix) != 4:
        raise ValueError("expected a 4x4 matrix")
    return invert(matrix)


def hdop(satellites: Iterable[SatInfo]) -> Optional[float]:
    """HDOP from the tracked satellites; None with fewer than 4 or a
    degenerate geometry (for example, every signal from one direction)."""
    rows = [geometry_row(s) for s in satellites if s.tracked]
    if len(rows) < 4:
        return None
    gtg = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]
    inverse = invert_4x4(gtg)
    if inverse is None:
        return None
    variance = inverse[0][0] + inverse[1][1]
    if variance <= 0.0:
        return None
    return math.sqrt(variance)


# ------------------------------------------------------- local lat/lon frame

EARTH_RADIUS_M = 6371000.0


@dataclass(frozen=True)
class LocalFrame:
    """Converts local metres (x east, y north) around a reference point to
    latitude/longitude and back.

    This is a flat-Earth (equirectangular) approximation around the reference
    point: fine for tens of kilometres, increasingly wrong over hundreds.
    """

    lat0_deg: float
    lon0_deg: float

    @property
    def _metres_per_rad_lon(self) -> float:
        return EARTH_RADIUS_M * math.cos(math.radians(self.lat0_deg))

    def to_latlon(self, x: float, y: float) -> Tuple[float, float]:
        lat = self.lat0_deg + math.degrees(y / EARTH_RADIUS_M)
        lon = self.lon0_deg + math.degrees(x / self._metres_per_rad_lon)
        return lat, lon

    def to_xy(self, lat: float, lon: float) -> Tuple[float, float]:
        x = math.radians(lon - self.lon0_deg) * self._metres_per_rad_lon
        y = math.radians(lat - self.lat0_deg) * EARTH_RADIUS_M
        return x, y
