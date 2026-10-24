"""Independent position fixes from non-GNSS aids.

pseudolite_fix: ranging from shore stations (pseudolites / R-Mode style
    transmitters). Same idea as GNSS: each station gives a pseudorange
    (true range + the receiver's clock error), solved by iterative least
    squares. The ship is at sea level, so the unknowns are east, north and
    the clock term (3 unknowns: at least 3 stations).
peer_fix: our position from a nearby ship's broadcast position and our own
    radar range and bearing to it. Broadcasts are unencrypted: a spoofed
    ship reports a wrong position, and so does the fix built from it.
"""

import math
from typing import Optional, Sequence, Tuple

from .geometry import invert
from .types import AuxFix, Position

MIN_STATIONS = 3


def pseudolite_fix(stations: Sequence[Tuple[float, float, float]],
                   pseudoranges: Sequence[float], sigmas: Sequence[float],
                   guess: Position, max_hdop: float,
                   max_iter: int = 20, tol_m: float = 1e-3) -> Optional[AuxFix]:
    """Least-squares position from pseudoranges to stations at (x, y, height).

    Each iteration linearises rho_i = |s_i - r| + b around the current guess
    and solves (G^T W G) dx = G^T W d with weights 1/sigma_i^2. Returns None
    with fewer than 3 stations, a degenerate geometry or HDOP above max_hdop.
    """
    if len(stations) < MIN_STATIONS:
        return None
    x, y, clock = guess[0], guess[1], 0.0
    weights = [1.0 / (s * s) for s in sigmas]
    inverse = None
    for _ in range(max_iter):
        rows, residuals = [], []
        for (sx, sy, sh), rho in zip(stations, pseudoranges):
            dist = max(math.sqrt((x - sx) ** 2 + (y - sy) ** 2 + sh * sh), 1e-6)
            rows.append(((x - sx) / dist, (y - sy) / dist, 1.0))
            residuals.append(rho - (dist + clock))
        normal = [[sum(w * r[i] * r[j] for w, r in zip(weights, rows)) for j in range(3)]
                  for i in range(3)]
        rhs = [sum(w * r[i] * d for w, r, d in zip(weights, rows, residuals)) for i in range(3)]
        inverse = invert(normal)
        if inverse is None:
            return None
        step = [sum(inverse[i][j] * rhs[j] for j in range(3)) for i in range(3)]
        x, y, clock = x + step[0], y + step[1], clock + step[2]
        if math.hypot(step[0], step[1]) < tol_m and abs(step[2]) < tol_m:
            break
    # With weights, (G^T W G)^-1 is already the covariance of the solution.
    sigma = math.sqrt(max(inverse[0][0] + inverse[1][1], 0.0) / 2.0)
    unweighted = invert([[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)])
    if unweighted is None:
        return None
    hdop = math.sqrt(max(unweighted[0][0] + unweighted[1][1], 0.0))
    if hdop > max_hdop:
        return None
    return AuxFix("pseudolite", (x, y), sigma)


def peer_fix(source: str, peer_position: Position, range_m: float, bearing_deg: float,
             sigma_range_m: float, sigma_bearing_deg: float) -> AuxFix:
    """Our position = the other ship's reported position minus the radar
    vector from us to it (range, true bearing clockwise from north)."""
    bearing = math.radians(bearing_deg)
    x = peer_position[0] - range_m * math.sin(bearing)
    y = peer_position[1] - range_m * math.cos(bearing)
    sigma = math.hypot(sigma_range_m, range_m * math.radians(sigma_bearing_deg))
    return AuxFix(source, (x, y), sigma)
