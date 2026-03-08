"""Tests for rural connectivity modules.

Covers:
- Hybrid network design (backhaul + last mile selection)
- Solar power system sizing
- Community demand profiling
- Funding program matching
- River crossing solutions
- Rural cost model
"""

from __future__ import annotations

import pytest

from python.rural.hybrid_designer import (
    design_hybrid_network,
    select_backhaul,
    select_last_mile,
    CommunityProfile,
)
from python.rural.solar_power import size_solar_system
from python.rural.community_profiler import profile_community
from python.rural.funding_matcher import (
    match_funding,
    get_all_programs,
    LEGAL_AMAZON_STATES,
)
from python.rural.river_crossing import design_crossing
from python.rural.cost_model_rural import estimate_rural_cost


# ---------------------------------------------------------------------------
# Helper to build a CommunityProfile for hybrid designer tests
# ---------------------------------------------------------------------------


def _make_profile(**overrides) -> CommunityProfile:
    """Create a CommunityProfile with sensible defaults.

    CommunityProfile fields: latitude, longitude, population, area_km2,
    grid_power, nearest_fiber_km, nearest_road_km, terrain_type, biome.
    """
    defaults = {
        "latitude": -15.0,
        "longitude": -47.0,
        "population": 800,
        "area_km2": 25.0,
        "grid_power": True,
        "nearest_fiber_km": 15.0,
        "nearest_road_km": 10.0,
        "terrain_type": "flat_rural",
        "biome": "cerrado",
    }
    defaults.update(overrides)
    return CommunityProfile(**defaults)


# ---------------------------------------------------------------------------
# Hybrid network design
# ---------------------------------------------------------------------------


class TestHybridNetworkDesign:
    """Tests for design_hybrid_network."""

    def test_returns_hybrid_design(self):
        profile = _make_profile()
        design = design_hybrid_network(profile)
        assert hasattr(design, "backhaul_technology")
        assert hasattr(design, "last_mile_technology")
        assert hasattr(design, "power_solution")

    def test_close_fiber_gets_fiber_backhaul(self):
        """Community near existing fiber with road access should get fiber backhaul.

        Fiber backhaul requires nearest_fiber_km <= 20 AND nearest_road_km <= 5.
        """
        profile = _make_profile(nearest_fiber_km=2.0, nearest_road_km=3.0)
        design = design_hybrid_network(profile)
        assert "fiber" in design.backhaul_technology.lower()

    def test_remote_community_gets_satellite_or_microwave(self):
        """Very remote communities should get satellite or microwave backhaul."""
        profile = _make_profile(
            nearest_fiber_km=100.0,
            nearest_road_km=50.0,
            terrain_type="amazon_riverine",
            biome="amazonia",
            grid_power=False,
        )
        design = design_hybrid_network(profile)
        assert "satellite" in design.backhaul_technology.lower() or "microwave" in design.backhaul_technology.lower()


class TestSelectBackhaul:
    """Tests for select_backhaul."""

    def test_returns_tuple(self):
        profile = _make_profile()
        result = select_backhaul(profile)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_fiber_backhaul_when_close(self):
        """Fiber requires both close fiber backbone AND road corridor (<=5km)."""
        profile = _make_profile(nearest_fiber_km=2.0, nearest_road_km=3.0)
        tech, details = select_backhaul(profile)
        assert "fiber" in tech.lower()

    def test_returns_known_backhaul_technology(self):
        profile = _make_profile(nearest_fiber_km=15.0, terrain_type="flat_rural")
        tech, details = select_backhaul(profile)
        known = {"fiber", "microwave", "satellite_leo", "satellite_geo"}
        assert tech.lower() in known


class TestSelectLastMile:
    """Tests for select_last_mile."""

    def test_returns_tuple(self):
        profile = _make_profile()
        result = select_last_mile(profile)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_known_technology(self):
        profile = _make_profile()
        tech, details = select_last_mile(profile)
        assert any(k in tech.lower() for k in ("wifi", "4g", "tvws", "satellite", "fiber"))


# ---------------------------------------------------------------------------
# Solar power sizing
# ---------------------------------------------------------------------------


class TestSolarPower:
    """Tests for size_solar_system."""

    def test_returns_solar_design(self):
        design = size_solar_system(
            latitude=-2.5,
            longitude=-44.3,
            power_consumption_watts=500,
        )
        assert hasattr(design, "panel_array_kwp")
        assert hasattr(design, "battery_kwh")
        assert hasattr(design, "estimated_capex_brl")

    def test_panel_count_positive(self):
        design = size_solar_system(
            latitude=-15.0,
            longitude=-47.0,
            power_consumption_watts=300,
        )
        assert design.panel_count >= 1

    def test_more_power_needs_more_panels(self):
        small = size_solar_system(
            latitude=-10.0,
            longitude=-50.0,
            power_consumption_watts=200,
        )
        large = size_solar_system(
            latitude=-10.0,
            longitude=-50.0,
            power_consumption_watts=1_000,
        )
        assert large.panel_count >= small.panel_count

    def test_higher_autonomy_more_battery(self):
        """More autonomy days should require larger battery bank."""
        short = size_solar_system(
            latitude=-15.0,
            longitude=-47.0,
            power_consumption_watts=500,
            autonomy_days=1,
        )
        long = size_solar_system(
            latitude=-15.0,
            longitude=-47.0,
            power_consumption_watts=500,
            autonomy_days=5,
        )
        assert long.battery_kwh >= short.battery_kwh

    def test_capex_positive(self):
        design = size_solar_system(
            latitude=-23.5,
            longitude=-46.6,
            power_consumption_watts=400,
        )
        assert design.estimated_capex_brl > 0


# ---------------------------------------------------------------------------
# Community profiler
# ---------------------------------------------------------------------------


class TestCommunityProfiler:
    """Tests for profile_community."""

    def test_returns_community_demand(self):
        demand = profile_community(population=800)
        assert hasattr(demand, "estimated_subscribers")
        assert hasattr(demand, "revenue_potential_monthly_brl")

    def test_subscribers_less_than_population(self):
        demand = profile_community(population=500)
        assert demand.estimated_subscribers <= 500

    def test_subscribers_positive(self):
        demand = profile_community(population=1_000)
        assert demand.estimated_subscribers > 0

    def test_school_increases_bandwidth(self):
        """Communities with schools should have higher bandwidth needs."""
        with_school = profile_community(population=500, has_school=True)
        no_school = profile_community(population=500, has_school=False)
        assert with_school.estimated_bandwidth_mbps >= no_school.estimated_bandwidth_mbps

    def test_revenue_potential_positive(self):
        demand = profile_community(population=800, avg_income_brl=1_500)
        assert demand.revenue_potential_monthly_brl > 0


# ---------------------------------------------------------------------------
# Funding matcher
# ---------------------------------------------------------------------------


class TestFundingMatcher:
    """Tests for match_funding and get_all_programs."""

    def test_get_all_programs(self):
        programs = get_all_programs()
        assert isinstance(programs, list)
        assert len(programs) >= 1

    def test_program_has_name(self):
        programs = get_all_programs()
        for p in programs:
            assert hasattr(p, "name")

    def test_amazon_state_matches_norte_conectado(self):
        """A municipality in the Legal Amazon should match Norte Conectado."""
        matches = match_funding(
            municipality_code="1500800",
            municipality_population=5_000,
            state_code="PA",
            technology="fiber",
            capex_brl=2_000_000,
        )
        # FundingMatch.program is a FundingProgram object with a .name field
        program_names = [m.program.name for m in matches]
        assert any("norte" in n.lower() for n in program_names)

    def test_legal_amazon_states(self):
        expected = {"AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"}
        assert LEGAL_AMAZON_STATES == expected

    def test_match_returns_list(self):
        matches = match_funding(
            municipality_code="3550308",
            municipality_population=50_000,
            state_code="SP",
            technology="fiber",
            capex_brl=1_000_000,
        )
        assert isinstance(matches, list)


# ---------------------------------------------------------------------------
# River crossing
# ---------------------------------------------------------------------------


class TestRiverCrossing:
    """Tests for design_crossing."""

    def test_narrow_river_includes_aerial(self):
        """Narrow river (<400m) should include aerial option."""
        crossings = design_crossing(width_m=200)
        tech_list = [c.crossing_type for c in crossings]
        assert any("aerial" in t.lower() for t in tech_list)

    def test_wide_river_includes_submarine_or_microwave(self):
        """Very wide river (>800m) should include submarine or microwave."""
        crossings = design_crossing(width_m=1_500)
        tech_list = [c.crossing_type for c in crossings]
        assert any("submarine" in t.lower() or "microwave" in t.lower() for t in tech_list)

    def test_results_sorted_by_cost(self):
        crossings = design_crossing(width_m=300)
        costs = [c.estimated_cost_brl for c in crossings]
        assert costs == sorted(costs)

    def test_returns_list(self):
        result = design_crossing(width_m=500)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_very_wide_river_microwave(self):
        """Extremely wide crossings should include microwave."""
        crossings = design_crossing(width_m=10_000)
        tech_list = [c.crossing_type for c in crossings]
        assert any("microwave" in t.lower() for t in tech_list)


# ---------------------------------------------------------------------------
# Rural cost model
# ---------------------------------------------------------------------------


class TestRuralCostModel:
    """Tests for estimate_rural_cost."""

    def test_returns_cost_estimate(self):
        result = estimate_rural_cost(
            technology="fiber",
            area_km2=25.0,
            population=800,
        )
        assert hasattr(result, "total_capex_brl")

    def test_total_positive(self):
        result = estimate_rural_cost(
            technology="fiber",
            area_km2=10.0,
            population=500,
        )
        assert result.total_capex_brl > 0

    def test_amazon_more_expensive(self):
        flat = estimate_rural_cost(
            technology="fiber",
            area_km2=25.0,
            population=800,
            terrain="flat_rural",
        )
        amazon = estimate_rural_cost(
            technology="fiber",
            area_km2=25.0,
            population=800,
            terrain="amazon_riverine",
        )
        assert amazon.total_capex_brl > flat.total_capex_brl

    def test_no_grid_power_increases_cost(self):
        with_grid = estimate_rural_cost(
            technology="fiber",
            area_km2=25.0,
            population=800,
            grid_power=True,
        )
        no_grid = estimate_rural_cost(
            technology="fiber",
            area_km2=25.0,
            population=800,
            grid_power=False,
        )
        assert no_grid.total_capex_brl >= with_grid.total_capex_brl
