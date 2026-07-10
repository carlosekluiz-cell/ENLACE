"""Tests for the nationwide terrain core (tile store + local reader).

Covers:
- SRTM tile naming and bbox/radius tile enumeration
- Brazil coverage bounds
- .hgt reading with bilinear interpolation (synthetic SRTM3 tile)
- Terrain profile extraction with earth curvature and obstruction count
- Fresnel-zone link analysis
- Ocean-marker handling
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from python.api.services.terrain_tiles import (
    TerrainTileStore,
    in_brazil,
    tile_name,
    tile_origin,
    tiles_for_bbox,
    tiles_for_path,
    tiles_for_radius,
)
from python.api.services.terrain_reader import (
    HgtReader,
    analyze_link,
    extract_profile,
    haversine_m,
)


# ---------------------------------------------------------------------------
# Tile naming / enumeration
# ---------------------------------------------------------------------------


def test_tile_name_south_west():
    # São Paulo city
    assert tile_name(-23.55, -46.63) == "S24W047"
    # Manaus
    assert tile_name(-3.10, -60.02) == "S04W061"
    # Northern hemisphere corner of Roraima
    assert tile_name(4.5, -60.5) == "N04W061"


def test_tile_origin_roundtrip():
    for name in ("S24W047", "N04W061", "S01W050"):
        lat, lon = tile_origin(name)
        assert tile_name(lat + 0.5, lon + 0.5) == name


def test_tiles_for_bbox_counts():
    tiles = tiles_for_bbox(-23.9, -46.9, -23.1, -46.1)
    assert tiles == ["S24W047"]
    tiles = tiles_for_bbox(-23.9, -46.9, -22.5, -45.5)
    assert len(tiles) == 4


def test_tiles_for_path_spans_endpoints():
    tiles = tiles_for_path(-23.55, -46.63, -22.90, -43.17)
    assert "S24W047" in tiles and "S23W044" in tiles


def test_tiles_for_radius_expands():
    tiles = tiles_for_radius(-23.999, -46.999, 5000)
    assert "S24W047" in tiles
    assert len(tiles) == 4  # 5 km past both SW edges


def test_in_brazil_bounds():
    assert in_brazil(-23.55, -46.63)  # São Paulo
    assert in_brazil(-3.1, -60.0)  # Manaus
    assert not in_brazil(51.5, -0.1)  # London
    assert not in_brazil(-34.6, -58.4)  # Buenos Aires (south of bounds)


# ---------------------------------------------------------------------------
# Reader (synthetic SRTM3 tile: 1201x1201 keeps the fixture small)
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return TerrainTileStore(root=tmp_path)


def _write_tile(store, name, surface, fill):
    """Write a synthetic SRTM3 tile. `fill(row, col)` -> elevation int."""
    side = 1201
    rows = np.fromfunction(lambda r, c: fill(r, c), (side, side)).astype(">i2")
    path = store.tile_path(name, surface)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.tofile(path)


def test_reader_flat_tile(store):
    _write_tile(store, "S24W047", "dtm", lambda r, c: 0 * r + 500)
    reader = HgtReader(store=store, surface="dtm")
    assert reader.elevation(-23.5, -46.5) == pytest.approx(500.0)


def test_reader_bilinear_gradient(store):
    # Elevation increases 1 m per column (west -> east)
    _write_tile(store, "S24W047", "dtm", lambda r, c: c)
    reader = HgtReader(store=store, surface="dtm")
    # Halfway across the tile in longitude -> ~600 m
    assert reader.elevation(-23.5, -46.5) == pytest.approx(600.0, abs=1.0)
    # Quarter across
    assert reader.elevation(-23.5, -46.75) == pytest.approx(300.0, abs=1.0)


def test_reader_missing_tile_returns_none(store):
    reader = HgtReader(store=store, surface="dtm")
    assert reader.elevation(-10.5, -55.5) is None


def test_reader_ocean_marker_returns_zero(store):
    name = "S24W046"
    store.surface_dir("dtm").mkdir(parents=True, exist_ok=True)
    store.ocean_marker(name, "dtm").touch()
    reader = HgtReader(store=store, surface="dtm")
    assert reader.elevation(-23.5, -45.5) == 0.0


def test_reader_dsm_and_dtm_are_separate(store):
    _write_tile(store, "S24W047", "dtm", lambda r, c: 0 * r + 100)
    _write_tile(store, "S24W047", "dsm", lambda r, c: 0 * r + 130)
    dtm = HgtReader(store=store, surface="dtm")
    dsm = HgtReader(store=store, surface="dsm")
    assert dsm.elevation(-23.5, -46.5) - dtm.elevation(-23.5, -46.5) == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Profile extraction
# ---------------------------------------------------------------------------


def test_profile_flat_terrain_no_obstructions(store):
    _write_tile(store, "S24W047", "dtm", lambda r, c: 0 * r + 500)
    reader = HgtReader(store=store, surface="dtm")
    profile = extract_profile(
        -23.6, -46.8, -23.6, -46.2, step_m=500, reader=reader
    )
    assert profile is not None
    assert profile["num_obstructions"] == 0
    assert profile["max_elevation_m"] == pytest.approx(500.0, abs=1)
    expected = haversine_m(-23.6, -46.8, -23.6, -46.2)
    assert profile["total_distance_m"] == pytest.approx(expected, rel=1e-6)
    # Curvature bulge at midpoint of a ~61 km path: d^2/(8kR) ~ 55 m
    mid = profile["points"][len(profile["points"]) // 2]
    assert mid["curved_elevation_m"] > mid["elevation_m"] + 30


def test_profile_hill_obstructs(store):
    # A 400 m ridge in the middle of the tile (columns 550-650)
    _write_tile(
        store,
        "S24W047",
        "dtm",
        lambda r, c: 100 + 400 * ((c > 550) & (c < 650)),
    )
    reader = HgtReader(store=store, surface="dtm")
    profile = extract_profile(
        -23.5, -46.9, -23.5, -46.1, step_m=200, reader=reader
    )
    assert profile is not None
    assert profile["num_obstructions"] > 0
    assert profile["max_elevation_m"] == pytest.approx(500.0, abs=1)


def test_profile_missing_tile_returns_none(store):
    reader = HgtReader(store=store, surface="dtm")
    assert extract_profile(-10.5, -55.5, -10.4, -55.4, reader=reader) is None


# ---------------------------------------------------------------------------
# Fresnel link analysis
# ---------------------------------------------------------------------------


def _flat_profile(distance_m=10_000.0, elev=500.0, n=50):
    pts = []
    for i in range(n + 1):
        d = distance_m * i / n
        pts.append(
            {
                "distance_m": d,
                "elevation_m": elev,
                "curved_elevation_m": elev,  # ignore curvature for test clarity
                "latitude": 0.0,
                "longitude": 0.0,
            }
        )
    return {"points": pts, "total_distance_m": distance_m}


def test_analyze_link_clear_path():
    result = analyze_link(_flat_profile(), tx_height_m=30, rx_height_m=30, frequency_mhz=5800)
    assert result["line_of_sight"] is True
    assert result["fresnel_clear"] is True
    # First Fresnel radius at midpoint of 10 km @ 5.8 GHz ~ 11.4 m < 30 m clearance
    mid = result["fresnel"][len(result["fresnel"]) // 2]
    assert mid["fresnel_radius_m"] == pytest.approx(11.4, abs=0.5)


def test_analyze_link_obstructed():
    profile = _flat_profile()
    # 100 m spike in the middle
    profile["points"][25]["curved_elevation_m"] = 600.0
    result = analyze_link(profile, tx_height_m=30, rx_height_m=30, frequency_mhz=5800)
    assert result["line_of_sight"] is False
    assert result["fresnel_clear"] is False
    assert result["worst_clearance_ratio"] < 0


def test_analyze_link_buildings_block_los():
    # Flat 500 m terrain, clear LOS at 30/30 m antennas — until a 60 m
    # building at the midpoint is considered.
    profile = _flat_profile()
    profile["points"][25]["building_height_m"] = 60.0
    without = analyze_link(profile, 30, 30, 5800, use_buildings=False)
    with_b = analyze_link(profile, 30, 30, 5800, use_buildings=True)
    assert without["line_of_sight"] is True
    assert with_b["line_of_sight"] is False
    assert with_b["buildings_used"] is True


def test_analyze_link_buildings_ignored_at_endpoints():
    # A tall building at the TX endpoint must not block its own antenna.
    profile = _flat_profile()
    profile["points"][0]["building_height_m"] = 80.0
    result = analyze_link(profile, 30, 30, 5800, use_buildings=True)
    assert result["line_of_sight"] is True


def test_analyze_link_low_antennas_marginal():
    # 900 MHz over 20 km with 5 m antennas: LOS grazes, Fresnel violated
    result = analyze_link(
        _flat_profile(distance_m=20_000), tx_height_m=5, rx_height_m=5, frequency_mhz=900
    )
    assert result["line_of_sight"] is True
    assert result["fresnel_clear"] is False


# ---------------------------------------------------------------------------
# Store bookkeeping
# ---------------------------------------------------------------------------


def test_store_status_counts(store):
    _write_tile(store, "S24W047", "dtm", lambda r, c: 0 * r + 1)
    store.ocean_marker("S24W046", "dtm").touch()
    status = store.status()
    assert status["surfaces"]["dtm"]["tiles_cached"] == 1
    assert status["surfaces"]["dtm"]["ocean_markers"] == 1
    assert status["surfaces"]["dsm"]["tiles_cached"] == 0


def test_store_rejects_unknown_surface(store):
    with pytest.raises(ValueError):
        store.tile_path("S24W047", "dem")


def test_ensure_outside_brazil_skipped(store):
    results = store.ensure_tiles(["N51W001"], "dtm")
    assert results[0].status == "outside_coverage"


# ---------------------------------------------------------------------------
# Clutter (MapBiomas land cover)
# ---------------------------------------------------------------------------


def test_clutter_classify_core_classes():
    from python.api.services.clutter import classify

    assert classify(24).key == "urban"
    assert classify(3).key == "forest"
    assert classify(15).key == "agriculture"
    assert classify(33).key == "water"
    assert classify(255).key == "open"  # unknown code falls back


def test_clutter_environment_inference():
    from python.api.services.clutter import infer_environment

    assert infer_environment([24] * 50 + [15] * 50) == "urban"  # 50% urban
    assert infer_environment([24] * 15 + [15] * 85) == "suburban"  # 15%
    assert infer_environment([15] * 100) == "rural"
    assert infer_environment([]) == "rural"


def test_clutter_summarize_path():
    from python.api.services.clutter import summarize_path

    codes = [3] * 60 + [15] * 30 + [24] * 10  # 60% forest, 30% agri, 10% urban
    s = summarize_path(codes, step_m=100)
    assert s["fractions"]["forest"] == 0.6
    assert s["vegetation_depth_m"] == 6000.0
    assert s["environment"] == "suburban"  # 10% urban


def test_landcover_reader(store):
    import numpy as np
    from python.api.services.terrain_reader import LandcoverReader

    grid = np.full((3601, 3601), 15, dtype=np.uint8)  # pasture everywhere
    grid[:, 1800:] = 24  # east half urban
    store.landcover_dir().mkdir(parents=True, exist_ok=True)
    grid.tofile(store.landcover_path("S24W047"))

    lc = LandcoverReader(store=store)
    assert lc.code(-23.5, -46.9) == 15  # west: pasture
    assert lc.code(-23.5, -46.1) == 24  # east: urban
    assert lc.code(-10.5, -55.5) is None  # no tile


def test_profile_carries_landcover(store):
    import numpy as np
    from python.api.services.terrain_reader import HgtReader, LandcoverReader, extract_profile

    _write_tile(store, "S24W047", "dtm", lambda r, c: 0 * r + 500)
    grid = np.full((3601, 3601), 3, dtype=np.uint8)  # forest
    store.landcover_dir().mkdir(parents=True, exist_ok=True)
    grid.tofile(store.landcover_path("S24W047"))

    profile = extract_profile(
        -23.6, -46.8, -23.6, -46.2, step_m=500,
        reader=HgtReader(store=store, surface="dtm"),
        landcover=LandcoverReader(store=store),
    )
    assert profile is not None
    assert all(p["lc"] == 3 for p in profile["points"])
