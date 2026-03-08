"""Tests for fiber routing modules.

Covers:
- BOM (Bill of Materials) generation
- Cable type constants
- Splitter spacing rules
- Junction counting from GeoJSON
"""

from __future__ import annotations

import math

import pytest

from python.ml.routing.bom_generator import (
    generate_bom,
    CABLE_TYPES,
    EQUIPMENT_COSTS,
    SPLITTER_SPACING,
    SPLICE_INTERVAL_KM,
    OLT_CAPACITY,
    _count_junctions_from_geojson,
    _select_trunk_cable,
)


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------


class TestBOMConstants:
    """Tests for BOM constant data."""

    def test_cable_types_present(self):
        assert "drop" in CABLE_TYPES
        assert "distribution_12" in CABLE_TYPES
        assert "distribution_48" in CABLE_TYPES
        assert "backbone_144" in CABLE_TYPES

    def test_cable_costs_positive(self):
        for name, cable in CABLE_TYPES.items():
            assert cable["cost_per_m"] > 0, f"{name} has non-positive cost"

    def test_equipment_costs_positive(self):
        for name, equip in EQUIPMENT_COSTS.items():
            assert equip["unit_cost_brl"] > 0, f"{name} has non-positive cost"

    def test_splitter_spacing_values(self):
        assert SPLITTER_SPACING["urban"] == 0.5
        assert SPLITTER_SPACING["suburban"] == 1.0
        assert SPLITTER_SPACING["rural"] == 2.0

    def test_olt_capacity(self):
        assert OLT_CAPACITY == 256


# ---------------------------------------------------------------------------
# Trunk cable selection
# ---------------------------------------------------------------------------


class TestSelectTrunkCable:
    """Tests for _select_trunk_cable."""

    def test_rural_gets_12_fiber(self):
        cable = _select_trunk_cable("rural")
        assert cable["fiber_count"] == 12

    def test_urban_gets_48_fiber(self):
        cable = _select_trunk_cable("urban")
        assert cable["fiber_count"] == 48

    def test_suburban_gets_48_fiber(self):
        cable = _select_trunk_cable("suburban")
        assert cable["fiber_count"] == 48


# ---------------------------------------------------------------------------
# Junction counting
# ---------------------------------------------------------------------------


class TestCountJunctions:
    """Tests for _count_junctions_from_geojson."""

    def test_none_geojson(self):
        assert _count_junctions_from_geojson(None) == 0

    def test_empty_coords(self):
        geojson = {"geometry": {"coordinates": []}}
        assert _count_junctions_from_geojson(geojson) == 0

    def test_two_points_no_junction(self):
        geojson = {
            "geometry": {
                "coordinates": [[-46.6, -23.5], [-46.7, -23.6]],
            },
        }
        assert _count_junctions_from_geojson(geojson) == 0

    def test_straight_line_no_junction(self):
        """Points along a straight line should have zero junctions."""
        geojson = {
            "geometry": {
                "coordinates": [
                    [-46.6, -23.5],
                    [-46.7, -23.5],
                    [-46.8, -23.5],
                    [-46.9, -23.5],
                ],
            },
        }
        assert _count_junctions_from_geojson(geojson) == 0

    def test_right_angle_turn(self):
        """A 90 degree turn should count as a junction."""
        geojson = {
            "geometry": {
                "coordinates": [
                    [-46.6, -23.5],
                    [-46.6, -23.6],
                    [-46.7, -23.6],
                ],
            },
        }
        junctions = _count_junctions_from_geojson(geojson)
        assert junctions >= 1


# ---------------------------------------------------------------------------
# BOM generation
# ---------------------------------------------------------------------------


class TestGenerateBOM:
    """Tests for generate_bom."""

    def test_returns_dict_with_expected_keys(self):
        bom = generate_bom(
            route_geojson=None,
            total_length_km=5.0,
            target_subscribers=200,
            area_type="urban",
        )
        assert "items" in bom
        assert "grand_total_brl" in bom
        assert "summary" in bom

    def test_items_list_nonempty(self):
        bom = generate_bom(
            route_geojson=None,
            total_length_km=3.0,
            target_subscribers=100,
        )
        assert len(bom["items"]) > 0

    def test_grand_total_positive(self):
        bom = generate_bom(
            route_geojson=None,
            total_length_km=5.0,
            target_subscribers=200,
        )
        assert bom["grand_total_brl"] > 0

    def test_grand_total_equals_sum_of_items(self):
        bom = generate_bom(
            route_geojson=None,
            total_length_km=10.0,
            target_subscribers=500,
        )
        item_total = sum(item["total_cost_brl"] for item in bom["items"])
        assert bom["grand_total_brl"] == pytest.approx(item_total, rel=1e-6)

    def test_zero_length_zero_subs(self):
        """Edge case: nothing to build."""
        bom = generate_bom(
            route_geojson=None,
            total_length_km=0,
            target_subscribers=0,
        )
        assert bom["grand_total_brl"] == 0.0

    def test_longer_route_costs_more(self):
        short = generate_bom(None, 2.0, 200, "urban")
        long = generate_bom(None, 20.0, 200, "urban")
        assert long["grand_total_brl"] > short["grand_total_brl"]

    def test_more_subscribers_costs_more(self):
        few = generate_bom(None, 5.0, 50, "urban")
        many = generate_bom(None, 5.0, 500, "urban")
        assert many["grand_total_brl"] > few["grand_total_brl"]

    def test_rural_uses_different_splitter(self):
        """Rural areas should use 1:16 splitters."""
        rural_bom = generate_bom(None, 10.0, 200, "rural")
        # Find the splitter item
        splitter_items = [i for i in rural_bom["items"] if "splitter" in i["name"].lower()]
        assert any("1x16" in i["name"] for i in splitter_items)

    def test_urban_uses_1x32_splitter(self):
        urban_bom = generate_bom(None, 10.0, 500, "urban")
        splitter_items = [i for i in urban_bom["items"] if "splitter" in i["name"].lower()]
        assert any("1x32" in i["name"] for i in splitter_items)

    def test_backbone_added_for_long_route(self):
        """Routes > 5 km should include backbone cable."""
        bom = generate_bom(None, 8.0, 300, "urban")
        item_names = [i["name"].lower() for i in bom["items"]]
        assert any("backbone" in n for n in item_names)

    def test_no_backbone_for_short_route(self):
        """Routes <= 5 km should NOT include backbone cable."""
        bom = generate_bom(None, 3.0, 100, "urban")
        item_names = [i["name"].lower() for i in bom["items"]]
        assert not any("backbone" in n for n in item_names)

    def test_includes_ont_for_subscribers(self):
        bom = generate_bom(None, 5.0, 100, "urban")
        ont_items = [i for i in bom["items"] if "ont" in i["name"].lower()]
        assert len(ont_items) == 1
        assert ont_items[0]["quantity"] == 100

    def test_olt_count_scales_with_subscribers(self):
        """More than 256 subscribers should require 2+ OLTs."""
        bom = generate_bom(None, 10.0, 600, "urban")
        olt_items = [i for i in bom["items"] if "olt" in i["name"].lower()]
        assert olt_items[0]["quantity"] >= 3  # ceil(600/256) = 3
