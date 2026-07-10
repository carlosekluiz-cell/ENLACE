"""
Terrain tile acquisition for nationwide Brazil propagation modelling.

Two elevation surfaces, both 1-arc-second (~30 m), stored as SRTM-style
``.hgt`` tiles (3601x3601 big-endian int16) so the Rust engine
(pulso-terrain) and the Python fallback reader share one format:

- **DTM** (bare earth): SRTM GL1 from OpenTopography's public S3
  (served as GeoTIFF — the legacy pipeline requested ``.hgt`` keys that
  do not exist, which is why no tiles were ever ingested).
- **DSM** (surface — buildings/vegetation): Copernicus GLO-30 from the
  AWS open-data bucket (Cloud-Optimized GeoTIFF, float32).

Tiles are fetched on demand for any coordinate inside Brazil, converted
with GDAL to ``.hgt``, and cached under ``TERRAIN_TILE_DIR`` in per-surface
subdirectories (``dtm/``, ``dsm/``). Ocean tiles (404 upstream) are
recorded as ``<tile>.ocean`` markers so they are never re-requested;
readers treat them as elevation 0.
"""

from __future__ import annotations

import logging
import math
import os
import tempfile
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Brazil bounding box (IBGE extremes, padded ~0.5 deg).
BRAZIL_BOUNDS = {
    "min_lat": -34.5,
    "max_lat": 6.0,
    "min_lon": -74.5,
    "max_lon": -28.5,
}

# dtm = SRTM GL1 (C-band radar: partially includes canopy/buildings)
# dsm = Copernicus GLO-30 (surface: buildings + vegetation)
# ground = ANADEM v1 (ML bare-earth, vegetation/building bias removed)
SURFACES = ("dtm", "dsm", "ground")

SRTM_GL1_URL = (
    "https://opentopography.s3.sdsc.edu/raster/SRTM_GL1/SRTM_GL1_srtm/{tile}.tif"
)
COPERNICUS_DSM_URL = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{lat_tag}_00_{lon_tag}_00_DEM/"
    "Copernicus_DSM_COG_10_{lat_tag}_00_{lon_tag}_00_DEM.tif"
)
# MapBiomas Collection 9 nationwide land-cover COG (30 m, uint8 class codes).
# Tiled 512x512 with overviews — windowed HTTP reads fetch only needed blocks.
MAPBIOMAS_COG_URL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
    "collection_9/lclu/coverage/brasil_coverage_2023.tif"
)
# ANADEM v1 bare-earth DTM for South America (30 m float32 COG, ~71 GB,
# EPSG:4674, nodata -9999) — windowed reads only, never bulk-downloaded.
ANADEM_COG_URL = (
    "https://opentopography.s3.sdsc.edu/raster/ANADEM/ANADEM_be/"
    "anadem_v1_compressed_COG.tif"
)

HGT_SIZE = 3601  # SRTM1 grid
DOWNLOAD_TIMEOUT_S = 120
MAX_TILES_PER_REQUEST = 25  # 1x1 deg tiles; guardrail for ensure endpoints


def default_tile_root() -> Path:
    return Path(os.getenv("TERRAIN_TILE_DIR", "data/terrain"))


def tile_name(lat: float, lon: float) -> str:
    """SRTM tile name for the 1x1 degree cell containing (lat, lon)."""
    lat_i = math.floor(lat)
    lon_i = math.floor(lon)
    ns = "S" if lat_i < 0 else "N"
    ew = "W" if lon_i < 0 else "E"
    return f"{ns}{abs(lat_i):02d}{ew}{abs(lon_i):03d}"


def tile_origin(name: str) -> tuple[int, int]:
    """(lat, lon) of the SW corner of a tile, from its name."""
    lat = int(name[1:3])
    lon = int(name[4:7])
    if name[0] == "S":
        lat = -lat
    if name[3] == "W":
        lon = -lon
    return lat, lon


def in_brazil(lat: float, lon: float) -> bool:
    b = BRAZIL_BOUNDS
    return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]


def tiles_for_bbox(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float
) -> list[str]:
    """All 1x1 degree tiles intersecting a bbox."""
    names = []
    for lat in range(math.floor(min_lat), math.floor(max_lat) + 1):
        for lon in range(math.floor(min_lon), math.floor(max_lon) + 1):
            names.append(tile_name(lat + 0.5, lon + 0.5))
    return names


def tiles_for_path(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> list[str]:
    return tiles_for_bbox(
        min(start_lat, end_lat),
        min(start_lon, end_lon),
        max(start_lat, end_lat),
        max(start_lon, end_lon),
    )


def tiles_for_radius(lat: float, lon: float, radius_m: float) -> list[str]:
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.1, math.cos(math.radians(lat))))
    return tiles_for_bbox(lat - dlat, lon - dlon, lat + dlat, lon + dlon)


@dataclass
class TileStatus:
    tile: str
    surface: str
    status: str  # "cached" | "downloaded" | "ocean" | "error" | "outside_coverage"
    detail: str = ""


class TerrainTileStore:
    """Downloads, converts, and tracks .hgt tiles for both surfaces."""

    def __init__(self, root: Path | None = None):
        self.root = root or default_tile_root()
        self._lock = threading.Lock()

    def surface_dir(self, surface: str) -> Path:
        if surface not in SURFACES:
            raise ValueError(f"unknown surface {surface!r} (expected dtm|dsm)")
        return self.root / surface

    def tile_path(self, name: str, surface: str) -> Path:
        return self.surface_dir(surface) / f"{name}.hgt"

    def ocean_marker(self, name: str, surface: str) -> Path:
        return self.surface_dir(surface) / f"{name}.ocean"

    def is_available(self, name: str, surface: str) -> bool:
        return self.tile_path(name, surface).exists()

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def ensure_tiles(self, names: list[str], surface: str = "dtm") -> list[TileStatus]:
        """Make sure the given tiles exist locally, downloading if needed.

        Serialized with a lock: concurrent requests for overlapping areas
        would otherwise download the same ~25 MB tile twice.
        """
        results = []
        with self._lock:
            for name in dict.fromkeys(names):  # dedupe, keep order
                results.append(self._ensure_one(name, surface))
        return results

    def ensure_for_bbox(
        self,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        surface: str = "dtm",
    ) -> list[TileStatus]:
        names = tiles_for_bbox(min_lat, min_lon, max_lat, max_lon)
        if len(names) > MAX_TILES_PER_REQUEST:
            raise ValueError(
                f"area spans {len(names)} tiles; max {MAX_TILES_PER_REQUEST} "
                "per request — split into smaller areas"
            )
        return self.ensure_tiles(names, surface)

    def _ensure_one(self, name: str, surface: str) -> TileStatus:
        lat, lon = tile_origin(name)
        if not in_brazil(lat + 0.5, lon + 0.5):
            return TileStatus(name, surface, "outside_coverage", "outside Brazil bounds")
        if self.tile_path(name, surface).exists():
            return TileStatus(name, surface, "cached")
        if self.ocean_marker(name, surface).exists():
            return TileStatus(name, surface, "ocean", "no land data (cached marker)")

        if surface == "ground":
            # ANADEM ships as one continental COG: window-read, no download.
            try:
                all_nodata = self._extract_ground(name)
            except Exception as e:
                logger.error("Ground tile %s failed: %s", name, e)
                return TileStatus(name, surface, "error", str(e))
            if all_nodata:
                self.surface_dir(surface).mkdir(parents=True, exist_ok=True)
                self.ocean_marker(name, surface).touch()
                return TileStatus(name, surface, "ocean", "no land data (ANADEM nodata)")
            return TileStatus(name, surface, "downloaded")

        url = self._source_url(name, surface)
        try:
            raw = self._download(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # No tile upstream = open water. Remember it.
                self.surface_dir(surface).mkdir(parents=True, exist_ok=True)
                self.ocean_marker(name, surface).touch()
                return TileStatus(name, surface, "ocean", "no land data upstream")
            logger.error("Tile %s (%s) download failed: HTTP %s", name, surface, e.code)
            return TileStatus(name, surface, "error", f"HTTP {e.code}")
        except Exception as e:
            logger.error("Tile %s (%s) download failed: %s", name, surface, e)
            return TileStatus(name, surface, "error", str(e))

        try:
            self._convert_to_hgt(raw, name, surface)
        except Exception as e:
            logger.error("Tile %s (%s) conversion failed: %s", name, surface, e)
            return TileStatus(name, surface, "error", f"conversion: {e}")
        finally:
            try:
                os.unlink(raw)
            except OSError:
                pass

        return TileStatus(name, surface, "downloaded")

    def _source_url(self, name: str, surface: str) -> str:
        if surface == "dtm":
            return SRTM_GL1_URL.format(tile=name)
        lat, lon = tile_origin(name)
        lat_tag = f"{'S' if lat < 0 else 'N'}{abs(lat):02d}"
        lon_tag = f"{'W' if lon < 0 else 'E'}{abs(lon):03d}"
        return COPERNICUS_DSM_URL.format(lat_tag=lat_tag, lon_tag=lon_tag)

    def _download(self, url: str) -> str:
        """Download to a temp file, return its path."""
        fd, tmp_path = tempfile.mkstemp(suffix=".tif")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "enlace-terrain/1.0"})
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_S) as resp:
                with os.fdopen(fd, "wb") as out:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return tmp_path

    def _convert_to_hgt(self, src_tif: str, name: str, surface: str) -> None:
        """GeoTIFF -> SRTM1 .hgt (3601x3601, int16 big-endian).

        Snaps to the exact 1-degree pixel-is-point grid so both sources land
        on the same raster regardless of upstream registration (SRTM GL1 is
        pixel-is-point 3601^2 int16; Copernicus is pixel-is-area 3600^2
        float32). Row 0 is the north edge, per the SRTM convention.
        """
        import numpy as np
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.vrt import WarpedVRT

        lat, lon = tile_origin(name)
        half_px = 0.5 / 3600
        transform = from_origin(lon - half_px, lat + 1 + half_px, 1 / 3600, 1 / 3600)

        with rasterio.open(src_tif) as src:
            with WarpedVRT(
                src,
                crs="EPSG:4326",
                transform=transform,
                width=HGT_SIZE,
                height=HGT_SIZE,
                resampling=Resampling.bilinear,
            ) as vrt:
                data = vrt.read(1, masked=True)

        grid = np.ma.filled(data.astype(np.float64), np.nan)
        grid = np.where(np.isfinite(grid), np.round(grid), -32768)
        grid = np.clip(grid, -32768, 32767).astype(">i2")

        out_dir = self.surface_dir(surface)
        out_dir.mkdir(parents=True, exist_ok=True)
        final_path = out_dir / f"{name}.hgt"
        fd, tmp_path = tempfile.mkstemp(dir=out_dir, suffix=".hgt.part")
        try:
            with os.fdopen(fd, "wb") as f:
                grid.tofile(f)
            os.chmod(tmp_path, 0o644)  # mkstemp defaults to 0600
            os.replace(tmp_path, final_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _extract_ground(self, name: str) -> bool:
        """Window-read ANADEM into an .hgt tile. Returns True if all-nodata."""
        import numpy as np
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.vrt import WarpedVRT

        lat, lon = tile_origin(name)
        half_px = 0.5 / 3600
        transform = from_origin(lon - half_px, lat + 1 + half_px, 1 / 3600, 1 / 3600)

        with rasterio.open(ANADEM_COG_URL) as src:
            with WarpedVRT(
                src,
                crs="EPSG:4326",
                transform=transform,
                width=HGT_SIZE,
                height=HGT_SIZE,
                resampling=Resampling.bilinear,
            ) as vrt:
                data = vrt.read(1, masked=True)

        grid = np.ma.filled(data.astype(np.float64), np.nan)
        grid[grid <= -9000] = np.nan  # ANADEM nodata -9999
        if np.all(np.isnan(grid)):
            return True
        grid = np.where(np.isfinite(grid), np.round(grid), -32768)
        grid = np.clip(grid, -32768, 32767).astype(">i2")

        out_dir = self.surface_dir("ground")
        out_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=out_dir, suffix=".hgt.part")
        try:
            with os.fdopen(fd, "wb") as f:
                grid.tofile(f)
            os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, out_dir / f"{name}.hgt")
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        return False

    # ------------------------------------------------------------------
    # Land cover (MapBiomas clutter)
    # ------------------------------------------------------------------

    def landcover_dir(self) -> Path:
        return self.root / "landcover"

    def landcover_path(self, name: str) -> Path:
        return self.landcover_dir() / f"{name}.lc"

    def ensure_landcover(self, names: list[str]) -> list[TileStatus]:
        """Extract MapBiomas land-cover for 1x1 degree tiles.

        Stored as raw uint8 grids on the same 3601x3601 pixel-is-point grid
        as the .hgt tiles (nearest-neighbour, row 0 = north edge), so the
        readers can index elevation and clutter identically.
        """
        results = []
        with self._lock:
            for name in dict.fromkeys(names):
                results.append(self._ensure_landcover_one(name))
        return results

    def _ensure_landcover_one(self, name: str) -> TileStatus:
        lat, lon = tile_origin(name)
        if not in_brazil(lat + 0.5, lon + 0.5):
            return TileStatus(name, "landcover", "outside_coverage", "outside Brazil bounds")
        if self.landcover_path(name).exists():
            return TileStatus(name, "landcover", "cached")
        try:
            self._extract_landcover(name)
        except Exception as e:
            logger.error("Landcover tile %s failed: %s", name, e)
            return TileStatus(name, "landcover", "error", str(e))
        return TileStatus(name, "landcover", "downloaded")

    def _extract_landcover(self, name: str) -> None:
        import numpy as np
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_origin
        from rasterio.vrt import WarpedVRT

        lat, lon = tile_origin(name)
        half_px = 0.5 / 3600
        transform = from_origin(lon - half_px, lat + 1 + half_px, 1 / 3600, 1 / 3600)

        with rasterio.open(MAPBIOMAS_COG_URL) as src:
            with WarpedVRT(
                src,
                crs="EPSG:4326",
                transform=transform,
                width=HGT_SIZE,
                height=HGT_SIZE,
                resampling=Resampling.nearest,  # class codes: never interpolate
            ) as vrt:
                grid = vrt.read(1).astype(np.uint8)

        out_dir = self.landcover_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=out_dir, suffix=".lc.part")
        try:
            with os.fdopen(fd, "wb") as f:
                grid.tofile(f)
            os.chmod(tmp_path, 0o644)
            os.replace(tmp_path, out_dir / f"{name}.lc")
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Cache inventory per surface."""
        out: dict = {"tile_dir": str(self.root), "surfaces": {}}
        for surface in SURFACES:
            d = self.surface_dir(surface)
            tiles = sorted(p.stem for p in d.glob("*.hgt")) if d.exists() else []
            ocean = len(list(d.glob("*.ocean"))) if d.exists() else 0
            size = sum(p.stat().st_size for p in d.glob("*.hgt")) if d.exists() else 0
            out["surfaces"][surface] = {
                "tiles_cached": len(tiles),
                "ocean_markers": ocean,
                "disk_bytes": size,
                "tiles": tiles,
                "source": {
                    "dtm": "SRTM GL1 (OpenTopography)",
                    "dsm": "Copernicus GLO-30 DSM (AWS Open Data)",
                    "ground": "ANADEM v1 bare-earth (OpenTopography)",
                }[surface],
            }
        lc_dir = self.landcover_dir()
        lc_tiles = sorted(p.stem for p in lc_dir.glob("*.lc")) if lc_dir.exists() else []
        out["landcover"] = {
            "tiles_cached": len(lc_tiles),
            "disk_bytes": sum(p.stat().st_size for p in lc_dir.glob("*.lc")) if lc_dir.exists() else 0,
            "tiles": lc_tiles,
            "source": "MapBiomas Collection 9 (2023, 30 m)",
        }
        return out


_store: TerrainTileStore | None = None
_store_lock = threading.Lock()


def get_tile_store() -> TerrainTileStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = TerrainTileStore()
        return _store
