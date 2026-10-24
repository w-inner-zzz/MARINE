"""Gulf of Finland chart: real land mask (global-land-mask) and a depth grid,
answering questions in local metres through a LocalFrame."""

import math
from functools import lru_cache
from typing import Optional, Tuple

import numpy as np
from global_land_mask import globe

from marine_guard.geometry import LocalFrame

from .bathymetry import DLAT, DLON, LAT_MAX, LAT_MIN, LON_MAX, LON_MIN, DepthGrid, load_depth_grid

LAND_MASK_SOURCE = ("global-land-mask (GLOBE 1 km land/sea mask, real data, "
                    "small islands may be missing)")
LAND_MASK_URL = "https://pypi.org/project/global-land-mask/"


class BalticChart:
    """Chart object for the guard: depth_at, is_water and coast_y_at in local
    metres. Land comes from the real land mask, sampled on the depth grid."""

    def __init__(self, frame: LocalFrame, land: np.ndarray, grid: DepthGrid):
        self.frame = frame
        self.grid = grid
        self.land = land
        self._next_land_row = self._next_land_row_north(land)

    @staticmethod
    def _next_land_row_north(land: np.ndarray) -> np.ndarray:
        """For every cell, the row index of the first land cell at or north of
        it in the same column (-1 if none inside the chart)."""
        rows, cols = land.shape
        result = np.full((rows, cols), -1, dtype=np.int32)
        nearest = np.full(cols, -1, dtype=np.int32)
        for r in range(rows - 1, -1, -1):
            nearest = np.where(land[r], r, nearest)
            result[r] = nearest
        return result

    # --------------------------------------------------- lat/lon questions

    def cell(self, lat: float, lon: float) -> Optional[Tuple[int, int]]:
        r = int((lat - LAT_MIN) / DLAT)
        c = int((lon - LON_MIN) / DLON)
        rows, cols = self.land.shape
        if 0 <= r < rows and 0 <= c < cols:
            return r, c
        return None

    def is_land_latlon(self, lat: float, lon: float) -> bool:
        cell = self.cell(lat, lon)
        if cell is None:
            return bool(globe.is_land(lat, lon))
        return bool(self.land[cell])

    def depth_latlon(self, lat: float, lon: float) -> float:
        if self.is_land_latlon(lat, lon):
            return 0.0
        return self.grid.depth_at(lat, lon)

    def distance_to_land_m(self, lat: float, lon: float, limit_m: float = 2000.0) -> float:
        """Distance to the nearest land cell centre, searched up to limit_m."""
        if self.is_land_latlon(lat, lon):
            return 0.0
        cell = self.cell(lat, lon)
        if cell is None:
            return limit_m
        r0, c0 = cell
        reach_r = int(limit_m / (DLAT * 111_195.0)) + 1
        reach_c = int(limit_m / (DLON * 111_195.0 * math.cos(math.radians(lat)))) + 1
        rows, cols = self.land.shape
        window = self.land[max(0, r0 - reach_r):min(rows, r0 + reach_r + 1),
                           max(0, c0 - reach_c):min(cols, c0 + reach_c + 1)]
        land_r, land_c = np.nonzero(window)
        if land_r.size == 0:
            return limit_m
        lats = LAT_MIN + (land_r + max(0, r0 - reach_r) + 0.5) * DLAT
        lons = LON_MIN + (land_c + max(0, c0 - reach_c) + 0.5) * DLON
        dy = (lats - lat) * 111_195.0
        dx = (lons - lon) * 111_195.0 * math.cos(math.radians(lat))
        return float(min(np.min(np.hypot(dx, dy)), limit_m))

    # ------------------------------------------- the guard's chart interface

    def depth_at(self, x: float, y: float) -> float:
        return self.depth_latlon(*self.frame.to_latlon(x, y))

    def is_water(self, x: float, y: float) -> bool:
        return not self.is_land_latlon(*self.frame.to_latlon(x, y))

    def coast_y_at(self, x: float, y: float) -> Optional[float]:
        """North coordinate (m) of the first coast straight north of (x, y)."""
        lat, lon = self.frame.to_latlon(x, y)
        cell = self.cell(lat, lon)
        if cell is None:
            return None
        row = self._next_land_row[cell]
        if row < 0:
            return None
        coast_lat = LAT_MIN + row * DLAT  # southern edge of the land cell
        return self.frame.to_xy(coast_lat, lon)[1]


def land_raster() -> np.ndarray:
    lats = LAT_MIN + (np.arange(round((LAT_MAX - LAT_MIN) / DLAT)) + 0.5) * DLAT
    lons = LON_MIN + (np.arange(round((LON_MAX - LON_MIN) / DLON)) + 0.5) * DLON
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    return globe.is_land(lat_grid, lon_grid)


@lru_cache(maxsize=4)
def baltic_chart(lat0_deg: float, lon0_deg: float) -> BalticChart:
    land = land_raster()
    return BalticChart(LocalFrame(lat0_deg, lon0_deg), land, load_depth_grid(land))
