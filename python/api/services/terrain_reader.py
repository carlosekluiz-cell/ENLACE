"""
Local .hgt elevation reader + terrain profile extraction.

Mirrors the Rust pulso-terrain crate (same tile format, same earth-curvature
math) so terrain queries return real data even when the gRPC engine is not
running. Used by the design router for elevation lookups and as the honest
fallback for /design/profile.

Physics:
- Effective-earth curvature bulge: d1*d2 / (2*k*R), k defaults to 4/3.
- First Fresnel zone radius: sqrt(lambda * d1 * d2 / (d1 + d2)).
- An obstruction is a sample whose (elevation + curvature bulge) crosses the
  TX->RX line-of-sight line; clearance is reported as a fraction of the first
  Fresnel radius (>= 0.6 is the standard "clear" criterion).
"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

from python.api.services.terrain_tiles import (
    TerrainTileStore,
    get_tile_store,
    tile_name,
    tile_origin,
)

EARTH_RADIUS_M = 6_371_000.0
DEFAULT_K_FACTOR = 4.0 / 3.0
VOID = -32768
_CACHE_TILES = 16  # memmaps kept open per reader (~26 MB each of address space)


class HgtReader:
    """Memory-mapped SRTM1/SRTM3 .hgt reader with bilinear interpolation."""

    def __init__(self, store: TerrainTileStore | None = None, surface: str = "dtm"):
        self.store = store or get_tile_store()
        self.surface = surface
        self._tiles: OrderedDict[str, np.ndarray | None] = OrderedDict()
        self._lock = threading.Lock()

    def _load(self, name: str) -> np.ndarray | None:
        with self._lock:
            if name in self._tiles:
                self._tiles.move_to_end(name)
                return self._tiles[name]
        path = self.store.tile_path(name, self.surface)
        grid = None
        if path.exists():
            n_bytes = path.stat().st_size
            side = int(math.isqrt(n_bytes // 2))
            if side * side * 2 == n_bytes and side in (1201, 3601):
                grid = np.memmap(path, dtype=">i2", mode="r", shape=(side, side))
        with self._lock:
            self._tiles[name] = grid
            self._tiles.move_to_end(name)
            while len(self._tiles) > _CACHE_TILES:
                self._tiles.popitem(last=False)
        return grid

    def elevation(self, lat: float, lon: float) -> float | None:
        """Bilinear-interpolated elevation in metres.

        Returns 0.0 for known-ocean tiles, None when the tile has never
        been downloaded (caller decides whether to fetch it).
        """
        name = tile_name(lat, lon)
        grid = self._load(name)
        if grid is None:
            if self.store.ocean_marker(name, self.surface).exists():
                return 0.0
            return None
        side = grid.shape[0]
        lat0, lon0 = tile_origin(name)
        # Row 0 is the NORTH edge (lat0 + 1); pixel-is-point grid.
        x = (lon - lon0) * (side - 1)
        y = (lat0 + 1 - lat) * (side - 1)
        x0 = min(int(x), side - 2)
        y0 = min(int(y), side - 2)
        fx, fy = x - x0, y - y0
        q = grid[y0 : y0 + 2, x0 : x0 + 2].astype(np.float64)
        if (q == VOID).any():
            valid = q[q != VOID]
            if valid.size == 0:
                return 0.0
            q[q == VOID] = valid.mean()
        return float(
            q[0, 0] * (1 - fx) * (1 - fy)
            + q[0, 1] * fx * (1 - fy)
            + q[1, 0] * (1 - fx) * fy
            + q[1, 1] * fx * fy
        )


class LandcoverReader:
    """Memory-mapped MapBiomas .lc reader (uint8, 3601x3601, nearest lookup)."""

    def __init__(self, store: TerrainTileStore | None = None):
        self.store = store or get_tile_store()
        self._tiles: OrderedDict[str, np.ndarray | None] = OrderedDict()
        self._lock = threading.Lock()

    def _load(self, name: str) -> np.ndarray | None:
        with self._lock:
            if name in self._tiles:
                self._tiles.move_to_end(name)
                return self._tiles[name]
        path = self.store.landcover_path(name)
        grid = None
        if path.exists() and path.stat().st_size == 3601 * 3601:
            grid = np.memmap(path, dtype=np.uint8, mode="r", shape=(3601, 3601))
        with self._lock:
            self._tiles[name] = grid
            self._tiles.move_to_end(name)
            while len(self._tiles) > _CACHE_TILES:
                self._tiles.popitem(last=False)
        return grid

    def code(self, lat: float, lon: float) -> int | None:
        """MapBiomas class code at a point (nearest pixel), None if no tile."""
        name = tile_name(lat, lon)
        grid = self._load(name)
        if grid is None:
            return None
        lat0, lon0 = tile_origin(name)
        side = grid.shape[0]
        x = min(side - 1, max(0, round((lon - lon0) * (side - 1))))
        y = min(side - 1, max(0, round((lat0 + 1 - lat) * (side - 1))))
        return int(grid[y, x])


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))


def extract_profile(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    step_m: float = 30.0,
    k_factor: float = DEFAULT_K_FACTOR,
    surface: str = "dtm",
    reader: HgtReader | None = None,
    landcover: "LandcoverReader | None" = None,
) -> dict | None:
    """Terrain profile between two points from local tiles.

    Returns None if any required tile is absent locally (caller should
    ensure tiles first). Matches the Rust engine's response shape.
    When a landcover reader is given, each point also carries its
    MapBiomas class code (lc) and points where the tile is missing get -1.
    """
    reader = reader or HgtReader(surface=surface)
    distance_m = haversine_m(start_lat, start_lon, end_lat, end_lon)
    n = max(2, int(distance_m / max(1.0, step_m)))

    points = []
    for i in range(n + 1):
        frac = i / n
        lat = start_lat + frac * (end_lat - start_lat)
        lon = start_lon + frac * (end_lon - start_lon)
        elev = reader.elevation(lat, lon)
        if elev is None:
            return None
        d = frac * distance_m
        # Effective-earth bulge relative to the chord between endpoints.
        bulge = (d * (distance_m - d)) / (2 * k_factor * EARTH_RADIUS_M)
        point = {
            "distance_m": round(d, 1),
            "elevation_m": round(elev, 1),
            "curved_elevation_m": round(elev + bulge, 1),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
        }
        if landcover is not None:
            code = landcover.code(lat, lon)
            point["lc"] = -1 if code is None else code
        points.append(point)

    elevs = [p["elevation_m"] for p in points]
    # Terrain-only obstruction count (no curvature, antenna heights 0);
    # curvature- and Fresnel-aware analysis is analyze_link's job.
    e0, e1 = elevs[0], elevs[-1]
    obstructions = sum(
        1
        for i, p in enumerate(points[1:-1], start=1)
        if p["elevation_m"] > e0 + (e1 - e0) * (i / n)
    )
    return {
        "points": points,
        "total_distance_m": round(distance_m, 1),
        "max_elevation_m": max(elevs),
        "min_elevation_m": min(elevs),
        "num_obstructions": obstructions,
        "surface": surface,
        "source": "local_tiles",
    }


def analyze_link(
    profile: dict,
    tx_height_m: float,
    rx_height_m: float,
    frequency_mhz: float,
    use_buildings: bool = False,
) -> dict:
    """Fresnel-zone clearance analysis over an extracted profile.

    Adds per-point LOS line and first-Fresnel radius, and summarizes the
    worst clearance. Works on profiles from either the Rust engine or the
    local reader (uses curved_elevation_m when present).

    With `use_buildings`, interior points that carry `building_height_m`
    (Open Buildings 2.5D annotation) obstruct at terrain + building height —
    rooftop diffraction instead of bare terrain. Endpoints are exempt
    (antennas are assumed mounted above their own building/mast).
    """
    pts = profile["points"]
    total = profile["total_distance_m"]
    wavelength = 299_792_458.0 / (frequency_mhz * 1e6)

    def curved(p, d, interior=True):
        base = (
            p["curved_elevation_m"]
            if "curved_elevation_m" in p
            else p["elevation_m"]
            + (d * (total - d)) / (2 * DEFAULT_K_FACTOR * EARTH_RADIUS_M)
        )
        if use_buildings and interior:
            base += p.get("building_height_m") or 0.0
        return base

    tx_amsl = curved(pts[0], 0.0, interior=False) + tx_height_m
    rx_amsl = curved(pts[-1], total, interior=False) + rx_height_m

    worst_clearance_ratio = math.inf
    worst_at_m = 0.0
    obstructed = False
    fresnel = []
    for i, p in enumerate(pts):
        d = p["distance_m"]
        los = tx_amsl + (rx_amsl - tx_amsl) * (d / total if total else 0.0)
        d2 = total - d
        r1 = math.sqrt(wavelength * d * d2 / total) if 0 < d < total else 0.0
        terrain = curved(p, d, interior=0 < i < len(pts) - 1)
        clearance = los - terrain
        fresnel.append(
            {
                "distance_m": d,
                "los_m": round(los, 1),
                "fresnel_radius_m": round(r1, 1),
                "clearance_m": round(clearance, 1),
            }
        )
        if r1 > 0:
            ratio = clearance / r1
            if ratio < worst_clearance_ratio:
                worst_clearance_ratio = ratio
                worst_at_m = d
            if clearance < 0:
                obstructed = True

    if not math.isfinite(worst_clearance_ratio):
        worst_clearance_ratio = 1.0
    return {
        "tx_height_m": tx_height_m,
        "rx_height_m": rx_height_m,
        "frequency_mhz": frequency_mhz,
        "buildings_used": use_buildings,
        "line_of_sight": not obstructed,
        "fresnel_clear": worst_clearance_ratio >= 0.6,
        "worst_clearance_ratio": round(worst_clearance_ratio, 3),
        "worst_clearance_at_m": round(worst_at_m, 1),
        "fresnel": fresnel,
    }


_readers: dict[str, HgtReader] = {}
_readers_lock = threading.Lock()
_lc_reader: LandcoverReader | None = None


def get_reader(surface: str = "dtm") -> HgtReader:
    with _readers_lock:
        if surface not in _readers:
            _readers[surface] = HgtReader(surface=surface)
        return _readers[surface]


def get_landcover_reader() -> LandcoverReader:
    global _lc_reader
    with _readers_lock:
        if _lc_reader is None:
            _lc_reader = LandcoverReader()
        return _lc_reader
