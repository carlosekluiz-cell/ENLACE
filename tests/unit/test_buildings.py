"""Tests for the Open Buildings 2.5D reader (no network)."""

from __future__ import annotations

from python.api.services.buildings import BuildingHeights, zone_epsg


def test_zone_epsg_brazil():
    assert zone_epsg(-23.55, -46.63) == 32723  # São Paulo, UTM 23S
    assert zone_epsg(-3.10, -60.02) == 32720  # Manaus, UTM 20S
    assert zone_epsg(2.82, -60.67) == 32620  # Boa Vista (north), UTM 20N
    assert zone_epsg(-8.05, -34.9) == 32725  # Recife, UTM 25S


def test_find_source_bbox():
    index = [
        {"x0": 330000.0, "y1": 7400000.0, "w": 25000, "h": 25000, "url": "a"},
        {"x0": 342500.0, "y1": 7400000.0, "w": 25000, "h": 25000, "url": "b"},
    ]
    # Tile a spans x 330000..342500, y 7387500..7400000
    assert BuildingHeights.find_source(index, 331000, 7393000)["url"] == "a"
    assert BuildingHeights.find_source(index, 343000, 7393000)["url"] == "b"
    assert BuildingHeights.find_source(index, 400000, 7393000) is None
    # North edge inclusive-exclusive convention
    assert BuildingHeights.find_source(index, 330000, 7400000 - 1)["url"] == "a"


def test_height_at_outside_brazil():
    r = BuildingHeights()
    assert r.height_at(51.5, -0.1) is None
