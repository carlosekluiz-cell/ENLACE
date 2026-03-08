"""Tests for financial modelling modules.

Covers:
- Bass diffusion subscriber curve
- Subscriber projection (pessimistic / base / optimistic)
- ARPU estimation (without DB, by providing provider_count)
- CAPEX estimation and terrain multipliers
- Financial viability (NPV, IRR, payback)
"""

from __future__ import annotations

import pytest

from python.ml.financial.subscriber_curve import (
    bass_diffusion,
    project_subscribers,
)
from python.ml.financial.arpu_model import estimate_arpu
from python.ml.financial.capex_estimator import (
    estimate_capex,
    get_terrain_multiplier,
)
from python.ml.financial.viability import compute_financial_metrics


# ---------------------------------------------------------------------------
# Bass diffusion model
# ---------------------------------------------------------------------------


class TestBassDiffusion:
    """Tests for bass_diffusion function."""

    def test_returns_float(self):
        result = bass_diffusion(t=12, M=10_000, k=0.5, t0=6, q=0.3)
        assert isinstance(result, float)

    def test_early_period_low_adoption(self):
        """At t=0, adoption should be near zero."""
        result = bass_diffusion(t=0, M=10_000, k=0.5, t0=12, q=0.3)
        assert result < 1_000

    def test_saturation_at_long_time(self):
        """At very large t, should approach M (market size)."""
        result = bass_diffusion(t=100, M=10_000, k=0.5, t0=12, q=0.3)
        assert result > 9_000  # should be close to M

    def test_s_curve_shape(self):
        """Values should increase over time: early < mid < late."""
        early = bass_diffusion(t=1, M=10_000, k=0.5, t0=12, q=0.3)
        mid = bass_diffusion(t=18, M=10_000, k=0.5, t0=12, q=0.3)
        late = bass_diffusion(t=36, M=10_000, k=0.5, t0=12, q=0.3)
        assert early <= mid <= late
        assert late > early  # ensure some growth happened

    def test_monotonically_increasing(self):
        """Adoption should never decrease over time."""
        prev = 0
        for t in range(0, 48):
            val = bass_diffusion(t=t, M=10_000, k=0.5, t0=12, q=0.3)
            assert val >= prev
            prev = val


# ---------------------------------------------------------------------------
# Subscriber projection
# ---------------------------------------------------------------------------


class TestProjectSubscribers:
    """Tests for project_subscribers."""

    def test_returns_dict_with_scenarios(self):
        result = project_subscribers(
            addressable_households=10_000,
            penetration_ceiling=0.60,
            months=36,
        )
        assert isinstance(result, dict)
        assert "pessimistic" in result
        assert "base_case" in result
        assert "optimistic" in result

    def test_base_case_curve_length(self):
        result = project_subscribers(
            addressable_households=10_000,
            penetration_ceiling=0.60,
            months=24,
        )
        # Each scenario value is a list of subscriber counts directly
        assert len(result["base_case"]) == 24

    def test_optimistic_higher_than_pessimistic(self):
        result = project_subscribers(
            addressable_households=10_000,
            penetration_ceiling=0.60,
            months=36,
        )
        opt_final = result["optimistic"][-1]
        pes_final = result["pessimistic"][-1]
        assert opt_final >= pes_final

    def test_subscribers_non_negative(self):
        result = project_subscribers(
            addressable_households=5_000,
            penetration_ceiling=0.50,
            months=36,
        )
        for scenario in ["pessimistic", "base_case", "optimistic"]:
            for val in result[scenario]:
                assert val >= 0

    def test_competition_level_affects_growth(self):
        """Competition level influences Bass diffusion q parameter.

        The q (imitation) coefficient differs by competition level, affecting
        the S-curve shape.  Low competition uses higher q (stronger word-of-mouth)
        which changes the ramp-up trajectory.  At saturation all scenarios
        converge to the same M, so we verify that the parameter sets actually
        differ and both eventually converge.
        """
        low_comp = project_subscribers(
            addressable_households=10_000,
            penetration_ceiling=0.60,
            competition_level="low",
            months=120,
        )
        high_comp = project_subscribers(
            addressable_households=10_000,
            penetration_ceiling=0.60,
            competition_level="high",
            months=120,
        )
        # Both should converge to the same market ceiling at saturation
        low_final = low_comp["base_case"][-1]
        high_final = high_comp["base_case"][-1]
        assert low_final == high_final  # same M at saturation

        # The q parameters should differ between competition levels
        low_q = low_comp["parameters"]["base_case"]["q"]
        high_q = high_comp["parameters"]["base_case"]["q"]
        assert low_q > high_q  # low competition -> higher word-of-mouth


# ---------------------------------------------------------------------------
# ARPU model
# ---------------------------------------------------------------------------


class TestEstimateArpu:
    """Tests for estimate_arpu (without DB, provider_count provided)."""

    def test_returns_dict(self):
        result = estimate_arpu(
            state_code="SP",
            municipality_population=50_000,
            avg_income=3_200.0,
            technology="fiber",
            provider_count=5,
        )
        assert isinstance(result, dict)

    def test_expected_keys(self):
        result = estimate_arpu(
            state_code="SP",
            municipality_population=50_000,
            avg_income=3_200.0,
            provider_count=3,
        )
        assert "base_arpu" in result
        assert "min_arpu" in result
        assert "max_arpu" in result

    def test_arpu_positive(self):
        result = estimate_arpu(
            state_code="MG",
            municipality_population=30_000,
            avg_income=2_500.0,
            provider_count=4,
        )
        assert result["base_arpu"] > 0
        assert result["min_arpu"] > 0
        assert result["max_arpu"] > 0

    def test_fiber_higher_than_dsl(self):
        fiber = estimate_arpu(
            state_code="SP",
            municipality_population=50_000,
            avg_income=3_000.0,
            technology="fiber",
            provider_count=3,
        )
        dsl = estimate_arpu(
            state_code="SP",
            municipality_population=50_000,
            avg_income=3_000.0,
            technology="dsl",
            provider_count=3,
        )
        assert fiber["base_arpu"] >= dsl["base_arpu"]

    def test_min_less_than_max(self):
        result = estimate_arpu(
            state_code="RJ",
            municipality_population=100_000,
            avg_income=4_000.0,
            provider_count=5,
        )
        assert result["min_arpu"] <= result["base_arpu"] <= result["max_arpu"]


# ---------------------------------------------------------------------------
# CAPEX estimator
# ---------------------------------------------------------------------------


class TestEstimateCapex:
    """Tests for estimate_capex."""

    def test_returns_dict(self):
        result = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
        )
        assert isinstance(result, dict)

    def test_expected_keys(self):
        result = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
        )
        assert "total_brl" in result
        assert "per_subscriber_brl" in result

    def test_total_positive(self):
        result = estimate_capex(
            cable_length_km=5.0,
            target_subscribers=200,
        )
        assert result["total_brl"] > 0
        assert result["per_subscriber_brl"] > 0

    def test_longer_route_costs_more(self):
        short = estimate_capex(cable_length_km=5.0, target_subscribers=500)
        long = estimate_capex(cable_length_km=20.0, target_subscribers=500)
        assert long["total_brl"] > short["total_brl"]

    def test_more_subs_costs_more(self):
        few = estimate_capex(cable_length_km=10.0, target_subscribers=100)
        many = estimate_capex(cable_length_km=10.0, target_subscribers=1_000)
        assert many["total_brl"] > few["total_brl"]

    def test_mountainous_terrain_more_expensive(self):
        flat = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
            terrain="flat_urban",
        )
        mountain = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
            terrain="mountainous",
        )
        assert mountain["total_brl"] > flat["total_brl"]


class TestGetTerrainMultiplier:
    """Tests for get_terrain_multiplier."""

    def test_flat_returns_one(self):
        result = get_terrain_multiplier(avg_slope=0.0, max_elevation_diff=0.0)
        assert result == pytest.approx(1.0, rel=0.1)

    def test_steep_slope_higher(self):
        flat = get_terrain_multiplier(avg_slope=0.0)
        steep = get_terrain_multiplier(avg_slope=30.0)
        assert steep > flat

    def test_amazon_biome_premium(self):
        result = get_terrain_multiplier(biome="amazonia")
        assert result > 1.0


# ---------------------------------------------------------------------------
# Financial viability (NPV, IRR, payback)
# ---------------------------------------------------------------------------


class TestComputeFinancialMetrics:
    """Tests for compute_financial_metrics."""

    def test_returns_dict(self):
        subs = [100 + i * 20 for i in range(36)]
        result = compute_financial_metrics(
            capex_brl=500_000.0,
            monthly_subscribers=subs,
            arpu_brl=80.0,
            opex_ratio=0.45,
            discount_rate=0.12,
            months=36,
        )
        assert isinstance(result, dict)

    def test_expected_keys(self):
        subs = [200 + i * 15 for i in range(24)]
        result = compute_financial_metrics(
            capex_brl=300_000.0,
            monthly_subscribers=subs,
            arpu_brl=90.0,
            opex_ratio=0.40,
            discount_rate=0.12,
            months=24,
        )
        assert "npv_brl" in result
        assert "irr_pct" in result
        assert "payback_months" in result

    def test_profitable_project_positive_npv(self):
        """A clearly profitable project should have positive NPV."""
        subs = [500 + i * 50 for i in range(36)]
        result = compute_financial_metrics(
            capex_brl=200_000.0,
            monthly_subscribers=subs,
            arpu_brl=100.0,
            opex_ratio=0.40,
            discount_rate=0.12,
            months=36,
        )
        assert result["npv_brl"] > 0

    def test_unprofitable_project_negative_npv(self):
        """Massive capex with tiny subscriber base should have negative NPV."""
        subs = [10] * 36
        result = compute_financial_metrics(
            capex_brl=5_000_000.0,
            monthly_subscribers=subs,
            arpu_brl=50.0,
            opex_ratio=0.50,
            discount_rate=0.12,
            months=36,
        )
        assert result["npv_brl"] < 0

    def test_payback_months_is_int_or_none(self):
        subs = [100 + i * 30 for i in range(36)]
        result = compute_financial_metrics(
            capex_brl=400_000.0,
            monthly_subscribers=subs,
            arpu_brl=85.0,
            opex_ratio=0.45,
            discount_rate=0.12,
            months=36,
        )
        assert result["payback_months"] is None or isinstance(result["payback_months"], (int, float))
