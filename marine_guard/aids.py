"""Independent position fixes from non-GNSS aids.

pseudolite_fix: ranging from shore stations (pseudolites / R-Mode style
    transmitters). Same idea as GNSS: each station gives a pseudorange
    (true range + the receiver's clock error), solved by iterative least
    squares. The ship is at sea level, so the unknowns are east, north and
    the clock term (3 unknowns: at least 3 stations).
peer_fix: our position from a nearby ship's broadcast position and our own
    radar range and bearing to it. Broadcasts are unencrypted: a spoofed
    ship reports a wrong position, and so does the fix built from it.
seabed_fix: our position from matching a short track of depth soundings
    against the chart in both directions (terrain-referenced navigation).
"""

import math
from typing import Callable, Optional, Sequence, Tuple

from .geometry import invert
from .types import AuxFix, Position

MIN_STATIONS = 3
CHI2_2DOF_99 = 9.21  # 99% point of a chi-square with 2 degrees of freedom


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


def seabed_fix(track: Sequence[Tuple[float, float]], depths: Sequence[float],
               depth_at: Callable[[float, float], float], center: Position, radius_m: float,
               coarse_step_m: float = 50.0, fine_step_m: float = 10.0,
               depth_noise_m: float = 1.0, max_rms_m: float = 2.0,
               min_relief_m: float = 2.0, min_sigma_m: float = 15.0) -> Optional[AuxFix]:
    """Seabed signature matching (terrain-referenced navigation).

    track[i] is where sounding i was taken relative to the ship's current
    position (from heading and log, so the shape is right even if the
    absolute position is not). Every offset (east, north) within radius_m of
    center is scored by the sum of squared differences between the measured
    depths and the chart; the best offset, refined on a finer grid, gives
    the position. Returns None if the seabed is too flat, the match is
    ambiguous on both axes or the depths do not fit the chart.

    The accuracy comes from the match itself, per axis: every coarse
    candidate that fits almost as well as the best (cost within the 99% band
    of a chi-square with 2 unknowns, 9.21 x noise^2, assuming Gaussian
    sounder noise) counts as possible, and each axis' sigma is their RMS
    distance from the best along that axis. If the possible region reaches
    the edge of the search along an axis, that axis is ambiguous and gets an
    infinite sigma (no information); if both are, no fix is returned.
    Reporting the search radius instead would shrink as the estimate improves
    and make ambiguous fixes look ever better.
    """
    if len(depths) < 2 or max(depths) - min(depths) < min_relief_m:
        return None

    def cost(ox: float, oy: float) -> float:
        cx, cy = center[0] + ox, center[1] + oy
        return sum((d - depth_at(cx + tx, cy + ty)) ** 2 for (tx, ty), d in zip(track, depths))

    steps = max(1, int(radius_m // coarse_step_m))
    coarse = {(i * coarse_step_m, j * coarse_step_m): 0.0
              for i in range(-steps, steps + 1) for j in range(-steps, steps + 1)}
    for offset in coarse:
        coarse[offset] = cost(*offset)
    best = min(coarse, key=coarse.get)

    fine_steps = int(coarse_step_m // fine_step_m)
    fine = [(best[0] + i * fine_step_m, best[1] + j * fine_step_m)
            for i in range(-fine_steps, fine_steps + 1) for j in range(-fine_steps, fine_steps + 1)]
    fine_costs = [cost(*o) for o in fine]
    best_cost = min(fine_costs)
    ox, oy = fine[fine_costs.index(best_cost)]
    if math.sqrt(best_cost / len(depths)) > max_rms_m:
        return None  # the soundings do not fit the chart anywhere nearby

    limit = coarse[best] + CHI2_2DOF_99 * depth_noise_m ** 2
    plausible = [o for o, c in coarse.items() if c <= limit]
    edge = steps * coarse_step_m
    offset, sigmas = [ox, oy], []
    for axis in (0, 1):
        if any(abs(o[axis]) >= edge for o in plausible):
            sigmas.append(math.inf)  # equally good matches continue beyond the search
            offset[axis] = 0.0       # no information: keep the ship's own estimate
        else:
            spread = math.sqrt(sum((o[axis] - offset[axis]) ** 2 for o in plausible) / len(plausible))
            sigmas.append(max(min_sigma_m, spread))
    if math.isinf(sigmas[0]) and math.isinf(sigmas[1]):
        return None
    return AuxFix("seabed", (center[0] + offset[0], center[1] + offset[1]), sigmas[0], sigmas[1])
