"""
Google Open Buildings 2.5D Temporal — per-building heights for Brazil.

Source: public GCS bucket `open-buildings-temporal-data` (v1, 2023-06-30
snapshot): 0.5 m rasters per UTM zone, band 2 = building_height (m),
nodata -99. Tiles are located via the published Earth Engine manifests
(sharded per zone), which carry each tile's affine transform — so any
lat/lon resolves to one COG and a windowed read.

Used to refine urban obstruction heights beyond the 30 m Copernicus DSM
(which smears individual towers). Point queries only — the dataset is
far too large to mirror.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import urllib.request
from collections import OrderedDict
from pathlib import Path

from python.api.services.terrain_tiles import default_tile_root, in_brazil

logger = logging.getLogger(__name__)

BUCKET = "https://storage.googleapis.com/open-buildings-temporal-data"
LIST_URL = (
    "https://storage.googleapis.com/storage/v1/b/open-buildings-temporal-data/o"
    "?maxResults=500&prefix=v1/manifests/"
)
SNAPSHOT = "2023_06_30"
NODATA = -99.0
_HANDLE_CACHE = 8


def zone_epsg(lat: float, lon: float) -> int:
    """UTM zone EPSG for a coordinate (326xx north / 327xx south)."""
    zone = int(math.floor((lon + 180) / 6)) + 1
    return (32600 if lat >= 0 else 32700) + zone


class BuildingHeights:
    """Lazy manifest-indexed reader for the 2.5D building-height rasters."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = (cache_dir or default_tile_root()) / "buildings"
        self._indexes: dict[int, list[dict]] = {}
        self._handles: OrderedDict[str, object] = OrderedDict()
        self._transformers: dict[int, object] = {}
        self._lock = threading.Lock()

    # -- manifest index ------------------------------------------------

    def _index_for(self, epsg: int) -> list[dict]:
        with self._lock:
            if epsg in self._indexes:
                return self._indexes[epsg]
        cache_file = self.cache_dir / f"index_{epsg}_{SNAPSHOT}.json"
        if cache_file.exists():
            index = json.loads(cache_file.read_text())
        else:
            index = self._build_index(epsg)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(index))
        with self._lock:
            self._indexes[epsg] = index
        return index

    def _build_index(self, epsg: int) -> list[dict]:
        """Fetch every manifest shard for this zone/snapshot and flatten to
        [{x0, y1, w, h, url}] (0.5 m pixels, y1 = north edge)."""
        names, token = [], None
        while True:
            url = LIST_URL + (f"&pageToken={token}" if token else "")
            with urllib.request.urlopen(url, timeout=60) as resp:
                d = json.load(resp)
            names += [i["name"] for i in d.get("items", [])]
            token = d.get("nextPageToken")
            if not token:
                break
        shards = [n for n in names if f"EPSG_{epsg}_{SNAPSHOT}" in n]
        index = []
        for shard in shards:
            with urllib.request.urlopen(f"{BUCKET}/{shard}", timeout=120) as resp:
                man = json.load(resp)
            prefix = man["uriPrefix"].replace(
                "gs://open-buildings-temporal-data/", f"{BUCKET}/"
            )
            for s in man["tilesets"][0]["sources"]:
                a = s["affineTransform"]
                index.append(
                    {
                        "x0": a["translateX"],
                        "y1": a["translateY"],
                        "w": s["dimensions"]["width"],
                        "h": s["dimensions"]["height"],
                        "url": prefix + s["uris"][0],
                    }
                )
        logger.info("Open Buildings index EPSG:%s — %d tiles", epsg, len(index))
        return index

    @staticmethod
    def find_source(index: list[dict], x: float, y: float) -> dict | None:
        """Locate the tile whose extent contains a projected point."""
        for s in index:
            if (
                s["x0"] <= x < s["x0"] + s["w"] * 0.5
                and s["y1"] - s["h"] * 0.5 <= y < s["y1"]
            ):
                return s
        return None

    # -- reads -----------------------------------------------------------

    def _open(self, url: str):
        import rasterio

        with self._lock:
            if url in self._handles:
                self._handles.move_to_end(url)
                return self._handles[url]
        ds = rasterio.open(url)
        with self._lock:
            self._handles[url] = ds
            self._handles.move_to_end(url)
            while len(self._handles) > _HANDLE_CACHE:
                _, old = self._handles.popitem(last=False)
                try:
                    old.close()
                except Exception:
                    pass
        return ds

    def _project(self, epsg: int, lon: float, lat: float) -> tuple[float, float]:
        from pyproj import Transformer

        with self._lock:
            tr = self._transformers.get(epsg)
        if tr is None:
            tr = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
            with self._lock:
                self._transformers[epsg] = tr
        return tr.transform(lon, lat)

    def height_at(self, lat: float, lon: float, box_m: float = 15.0) -> float | None:
        """Max building height (m) within a box around the point.

        Returns 0.0 where no building exists, None when the point is
        outside coverage or the read fails. The box (default 15 m) makes
        the value robust to GPS/pixel offsets at 30 m planning grids.
        """
        if not in_brazil(lat, lon):
            return None
        try:
            epsg = zone_epsg(lat, lon)
            index = self._index_for(epsg)
            x, y = self._project(epsg, lon, lat)
            src_info = self.find_source(index, x, y)
            if src_info is None:
                return None
            import numpy as np
            import rasterio.windows

            ds = self._open(src_info["url"])
            row, col = ds.index(x, y)
            half = max(1, int(box_m / 0.5 / 2))
            win = rasterio.windows.Window(
                max(0, col - half), max(0, row - half), 2 * half, 2 * half
            )
            heights = ds.read(2, window=win, boundless=True, fill_value=NODATA)
            valid = heights[heights > 0]
            return float(valid.max()) if valid.size else 0.0
        except Exception as e:
            logger.warning("Building height read failed at %.4f,%.4f: %s", lat, lon, e)
            return None


_reader: BuildingHeights | None = None
_reader_lock = threading.Lock()


def get_buildings_reader() -> BuildingHeights:
    global _reader
    with _reader_lock:
        if _reader is None:
            _reader = BuildingHeights()
        return _reader
