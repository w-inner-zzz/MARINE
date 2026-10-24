"""Depth grids for the Gulf of Finland chart.

Preferred: a real bathymetry subset from EMODnet Bathymetry, downloaded once
with `python -m sim.bathymetry download` and cached under data/. If that file
is missing, a SYNTHETIC Baltic-like grid is generated instead and clearly
labelled as synthetic everywhere it is shown.
"""

import pathlib
import sys
import urllib.request
from dataclasses import dataclass

import numpy as np

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
REAL_GRID_PATH = DATA_DIR / "emodnet_gulf_of_finland.asc"

# Area covered by the chart (degrees).
LAT_MIN, LAT_MAX = 59.2, 60.7
LON_MIN, LON_MAX = 23.0, 27.5
DLAT, DLON = 0.0025, 0.005  # about 280 m x 280 m at 60 deg N

EMODNET_WCS = (
    "https://ows.emodnet-bathymetry.eu/wcs?service=WCS&version=1.0.0&request=GetCoverage"
    "&coverage=emodnet:mean&crs=EPSG:4326&format=ArcGrid"
    f"&bbox={LON_MIN},{LAT_MIN},{LON_MAX},{LAT_MAX}&resx={DLON}&resy={DLAT}"
)
EMODNET_PAGE = "https://emodnet.ec.europa.eu/en/bathymetry"


@dataclass(frozen=True)
class DepthGrid:
    """Water depth in metres (0 on land) on a regular lat/lon grid.
    Row 0 is the southern edge (lat_min), column 0 the western edge (lon_min);
    values are cell centres."""

    lat_min: float
    lon_min: float
    dlat: float
    dlon: float
    depth: np.ndarray
    source: str
    synthetic: bool

    @property
    def shape(self):
        return self.depth.shape

    def cell_centres(self):
        rows, cols = self.depth.shape
        lats = self.lat_min + (np.arange(rows) + 0.5) * self.dlat
        lons = self.lon_min + (np.arange(cols) + 0.5) * self.dlon
        return lats, lons

    def depth_at(self, lat: float, lon: float) -> float:
        """Bilinear interpolation between the four surrounding cell centres."""
        rows, cols = self.depth.shape
        fr = min(max((lat - self.lat_min) / self.dlat - 0.5, 0.0), rows - 1.000001)
        fc = min(max((lon - self.lon_min) / self.dlon - 0.5, 0.0), cols - 1.000001)
        r, c = int(fr), int(fc)
        wr, wc = fr - r, fc - c
        d = self.depth
        top = d[r, c] * (1 - wc) + d[r, c + 1] * wc
        bottom = d[r + 1, c] * (1 - wc) + d[r + 1, c + 1] * wc
        return float(top * (1 - wr) + bottom * wr)


# ------------------------------------------------------------- real data


def parse_ascii_grid(text: str, source: str) -> DepthGrid:
    """Parse an ESRI ASCII grid of elevations (negative below sea level)."""
    lines = text.strip().splitlines()
    header = {}
    while lines and lines[0].split()[0][0].isalpha():  # header keys start with a letter
        key, value = lines.pop(0).split()[:2]
        header[key.lower()] = float(value)
    nodata = header.get("nodata_value", -99999.0)
    values = np.array([[float(v) for v in line.split()] for line in lines])
    values = values[::-1]  # file rows run north to south
    values[values == nodata] = np.nan
    depth = np.where(np.isnan(values), 0.0, np.clip(-values, 0.0, None))
    dx = header.get("dx", header.get("cellsize"))
    dy = header.get("dy", header.get("cellsize"))
    return DepthGrid(header["yllcorner"], header["xllcorner"], dy, dx, depth, source, False)


def download_real_grid(path: pathlib.Path = REAL_GRID_PATH) -> pathlib.Path:
    """Fetch the EMODnet subset for the chart area and cache it under data/."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(EMODNET_WCS, timeout=120) as response:
        path.write_bytes(response.read())
    return path


# --------------------------------------------------------- synthetic data


def _distance_to_land_cells(land: np.ndarray, max_cells: int) -> np.ndarray:
    """Approximate distance (in cells) from every cell to the nearest land cell,
    by growing the land one cell at a time (capped at max_cells)."""
    distance = np.full(land.shape, float(max_cells))
    reached = land.copy()
    distance[reached] = 0.0
    for step in range(1, max_cells):
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        distance[grown & ~reached] = step
        reached = grown
    return distance


def synthetic_grid(land: np.ndarray, seed: int = 2024) -> DepthGrid:
    """A Baltic-like seabed: 20-100 m in open water with ridges and hollows a
    few kilometres across, shoaling to a few metres near the coast."""
    rows, cols = land.shape
    rng = np.random.default_rng(seed)
    north_m = (np.arange(rows)[:, None] + 0.5) * DLAT * 111_195.0
    east_m = (np.arange(cols)[None, :] + 0.5) * DLON * 111_195.0 * np.cos(np.radians(60.0))
    depth = np.full((rows, cols), 60.0)
    for _ in range(8):
        wavelength = rng.uniform(1_500.0, 9_000.0)
        angle = rng.uniform(0.0, np.pi)
        k = 2 * np.pi / wavelength
        depth += rng.uniform(4.0, 9.0) * np.sin(
            k * (east_m * np.cos(angle) + north_m * np.sin(angle)) + rng.uniform(0, 2 * np.pi))
    depth = np.clip(depth, 20.0, 100.0)
    shore_cells = 10  # shoal over the last ~2.8 km before land
    near_shore = _distance_to_land_cells(land, shore_cells) / shore_cells
    depth = depth * np.clip(near_shore, 0.08, 1.0)
    depth[land] = 0.0
    return DepthGrid(LAT_MIN, LON_MIN, DLAT, DLON, depth,
                     "SYNTHETIC Baltic-like depth grid (not real survey data)", True)


def load_depth_grid(land: np.ndarray) -> DepthGrid:
    """Real EMODnet grid if it has been downloaded, otherwise synthetic."""
    if REAL_GRID_PATH.exists():
        return parse_ascii_grid(REAL_GRID_PATH.read_text(), "EMODnet Bathymetry (real survey data)")
    return synthetic_grid(land)


if __name__ == "__main__":
    if sys.argv[1:] == ["download"]:
        print(f"Saved {download_real_grid()}")
    else:
        print("usage: python -m sim.bathymetry download")
