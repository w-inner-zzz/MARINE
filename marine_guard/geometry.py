"""Satellite geometry: horizontal dilution of precision (HDOP).

HDOP says how much the satellite geometry magnifies range errors into
horizontal position error. Under 2 is good, over 5 is poor.
"""

import math
from typing import Iterable, List, Optional, Sequence

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


def invert_4x4(matrix: Sequence[Sequence[float]]) -> Optional[Matrix]:
    """Gauss-Jordan inverse with partial pivoting. None if singular."""
    n = 4
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
