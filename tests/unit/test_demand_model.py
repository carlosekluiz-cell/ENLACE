"""Tests for broadband demand estimation model.

Covers:
- Addressable market estimation with various input scenarios
- Affordability gating and penetration ceiling logic
- Edge cases: zero households, zero income, full penetration
- Demand score computation
"""

from __future__ import annotations

import pytest

from python.ml.opportunity.demand_model import (
    estimate_addressable_market,
    compute_demand_score,
)
from python.ml.config import MIN_BROADBAND_PRICE_BRL, AFFORDABILITY_INCOME_RATIO


class TestEstimateAddressableMarket:
    """Tests for estimate_addressable_market."""

    def test_returns_dict_with_expected_keys(self, sample_municipality):
        result = estimate_addressable_market(
            households=sample_municipality["households"],
            avg_income=sample_municipality["avg_income_brl"],
            current_penetration=sample_municipality["current_penetration"],
            urbanization_rate=sample_municipality["urbanization_rate"],
        )
        assert isinstance(result, dict)
        expected_keys = {
            "addressable_households",
            "penetration_ceiling",
            "untapped_demand",
            "monthly_revenue_potential_brl",
            "demand_score",
        }
        assert expected_keys.issubset(result.keys())

    def test_positive_addressable_households(self, sample_municipality):
        result = estimate_addressable_market(
            households=sample_municipality["households"],
            avg_income=sample_municipality["avg_income_brl"],
            current_penetration=sample_municipality["current_penetration"],
        )
        assert result["addressable_households"] > 0

    def test_penetration_ceiling_capped(self):
        """Penetration ceiling should not exceed 0.85 (configurable max)."""
        result = estimate_addressable_market(
            households=10_000,
            avg_income=10_000.0,
            current_penetration=0.0,
            urbanization_rate=1.0,
        )
        assert result["penetration_ceiling"] <= 0.85

    def test_zero_households_returns_zeros(self):
        """Zero or negative households should give zero output."""
        result = estimate_addressable_market(
            households=0,
            avg_income=3_000.0,
            current_penetration=0.0,
        )
        assert result["addressable_households"] == 0
        assert result["untapped_demand"] == 0

    def test_zero_income_gives_low_demand(self):
        """Very low income should result in minimal addressable market."""
        result = estimate_addressable_market(
            households=10_000,
            avg_income=0.0,
            current_penetration=0.0,
        )
        # With zero income the affordability fraction falls to 0.05 (fallback),
        # so addressable_households will be small but nonzero.
        assert result["addressable_households"] < 1_000
        assert result["demand_score"] < 20

    def test_full_penetration_gives_zero_untapped(self):
        """When penetration equals ceiling, untapped demand should be near zero."""
        result = estimate_addressable_market(
            households=10_000,
            avg_income=5_000.0,
            current_penetration=0.85,
        )
        assert result["untapped_demand"] <= 0

    def test_high_urbanization_increases_ceiling(self):
        """Higher urbanization should lead to higher penetration potential."""
        urban = estimate_addressable_market(
            households=10_000,
            avg_income=3_000.0,
            current_penetration=0.3,
            urbanization_rate=0.95,
        )
        rural = estimate_addressable_market(
            households=10_000,
            avg_income=3_000.0,
            current_penetration=0.3,
            urbanization_rate=0.20,
        )
        assert urban["penetration_ceiling"] >= rural["penetration_ceiling"]

    def test_revenue_potential_positive(self, sample_municipality):
        result = estimate_addressable_market(
            households=sample_municipality["households"],
            avg_income=sample_municipality["avg_income_brl"],
            current_penetration=sample_municipality["current_penetration"],
        )
        assert result["monthly_revenue_potential_brl"] >= 0

    def test_demand_score_range(self, sample_municipality):
        result = estimate_addressable_market(
            households=sample_municipality["households"],
            avg_income=sample_municipality["avg_income_brl"],
            current_penetration=sample_municipality["current_penetration"],
        )
        assert 0 <= result["demand_score"] <= 100

    def test_low_penetration_high_demand(self):
        """Low penetration with good income should show high demand."""
        result = estimate_addressable_market(
            households=20_000,
            avg_income=4_000.0,
            current_penetration=0.10,
            urbanization_rate=0.80,
        )
        assert result["untapped_demand"] > 0
        assert result["demand_score"] > 0


class TestComputeDemandScore:
    """Tests for compute_demand_score."""

    def test_returns_float(self):
        features = {
            "total_households": 10_000,
            "avg_income_per_capita": 3_000.0,
            "current_penetration": 0.40,
            "urbanization_rate": 0.75,
        }
        score = compute_demand_score(features)
        assert isinstance(score, float)

    def test_score_in_valid_range(self):
        features = {
            "total_households": 15_000,
            "avg_income_per_capita": 3_500.0,
            "current_penetration": 0.30,
            "urbanization_rate": 0.80,
        }
        score = compute_demand_score(features)
        assert 0 <= score <= 100

    def test_high_opportunity_area(self):
        """Large underserved urban area should score highly."""
        features = {
            "total_households": 50_000,
            "avg_income_per_capita": 5_000.0,
            "current_penetration": 0.15,
            "urbanization_rate": 0.90,
        }
        score = compute_demand_score(features)
        assert score > 30  # should be at least moderate

    def test_saturated_market_low_score(self):
        """Fully saturated market should score low."""
        features = {
            "total_households": 5_000,
            "avg_income_per_capita": 3_000.0,
            "current_penetration": 0.80,
            "urbanization_rate": 0.70,
        }
        score = compute_demand_score(features)
        assert score < 50
