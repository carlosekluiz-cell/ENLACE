"""Tests for network health modules.

Covers only pure-Python helper functions (no DB required):
- Weather risk level classification
- Precipitation, wind, temperature risk scoring
- Quality trend computation (OLS)
- Churn risk estimation
- Infrastructure age scoring
- Revenue risk scoring
- Maintenance action recommendation
- Timing determination
- Seasonal pattern generation
- State-to-region mapping
"""

from __future__ import annotations

from datetime import date

import pytest

from python.ml.health.weather_correlation import (
    get_risk_level,
    _score_precipitation_risk,
    _score_wind_risk,
    _score_temperature_risk,
    MonthlyWeatherMetrics,
)
from python.ml.health.quality_benchmark import (
    compute_trend,
    estimate_churn_risk,
)
from python.ml.health.maintenance_scorer import (
    compute_age_score,
    compute_revenue_risk,
    recommend_action,
    _determine_timing,
    MaintenancePriority,
)
from python.ml.health.seasonal_patterns import (
    generate_risk_pattern,
    get_region_from_state,
    REGION_MAP,
)


# ---------------------------------------------------------------------------
# Weather risk helpers
# ---------------------------------------------------------------------------


class TestGetRiskLevel:
    """Tests for get_risk_level."""

    def test_critical(self):
        assert get_risk_level(80) == "critical"
        assert get_risk_level(75) == "critical"

    def test_high(self):
        assert get_risk_level(60) == "high"
        assert get_risk_level(50) == "high"

    def test_moderate(self):
        assert get_risk_level(40) == "moderate"
        assert get_risk_level(25) == "moderate"

    def test_low(self):
        assert get_risk_level(10) == "low"
        assert get_risk_level(0) == "low"

    def test_boundary_values(self):
        assert get_risk_level(74.9) == "high"
        assert get_risk_level(24.9) == "low"


class TestPrecipitationRisk:
    """Tests for _score_precipitation_risk."""

    def _metrics(self, **kwargs):
        defaults = {
            "total_precipitation_mm": 0.0,
            "max_daily_precipitation_mm": 0.0,
            "max_wind_speed_ms": 0.0,
            "temperature_range": 0.0,
            "consecutive_rain_days": 0,
            "avg_humidity_pct": 0.0,
        }
        defaults.update(kwargs)
        return MonthlyWeatherMetrics(**defaults)

    def test_zero_rain_zero_score(self):
        score = _score_precipitation_risk(self._metrics())
        assert score == 0.0

    def test_heavy_monthly_rain(self):
        score = _score_precipitation_risk(
            self._metrics(total_precipitation_mm=600.0)
        )
        assert score >= 50

    def test_heavy_daily_event(self):
        score = _score_precipitation_risk(
            self._metrics(max_daily_precipitation_mm=80.0)
        )
        assert score >= 30

    def test_consecutive_rain_days(self):
        score = _score_precipitation_risk(
            self._metrics(consecutive_rain_days=8)
        )
        assert score >= 20

    def test_score_capped_at_100(self):
        score = _score_precipitation_risk(
            self._metrics(
                total_precipitation_mm=600,
                max_daily_precipitation_mm=100,
                consecutive_rain_days=10,
            )
        )
        assert score <= 100


class TestWindRisk:
    """Tests for _score_wind_risk."""

    def _metrics(self, wind_speed):
        return MonthlyWeatherMetrics(
            total_precipitation_mm=0,
            max_daily_precipitation_mm=0,
            max_wind_speed_ms=wind_speed,
            temperature_range=0,
            consecutive_rain_days=0,
            avg_humidity_pct=0,
        )

    def test_calm_winds(self):
        assert _score_wind_risk(self._metrics(3)) == 0.0

    def test_moderate_winds(self):
        assert _score_wind_risk(self._metrics(12)) == 30.0

    def test_high_winds(self):
        assert _score_wind_risk(self._metrics(20)) == 60.0

    def test_critical_winds(self):
        assert _score_wind_risk(self._metrics(30)) == 90.0


class TestTemperatureRisk:
    """Tests for _score_temperature_risk."""

    def _metrics(self, temp_range):
        return MonthlyWeatherMetrics(
            total_precipitation_mm=0,
            max_daily_precipitation_mm=0,
            max_wind_speed_ms=0,
            temperature_range=temp_range,
            consecutive_rain_days=0,
            avg_humidity_pct=0,
        )

    def test_stable_temps(self):
        assert _score_temperature_risk(self._metrics(5)) == 0.0

    def test_moderate_range(self):
        assert _score_temperature_risk(self._metrics(18)) == 25.0

    def test_high_range(self):
        assert _score_temperature_risk(self._metrics(25)) == 50.0

    def test_extreme_range(self):
        assert _score_temperature_risk(self._metrics(35)) == 80.0


# ---------------------------------------------------------------------------
# Quality benchmark helpers
# ---------------------------------------------------------------------------


class TestComputeTrend:
    """Tests for compute_trend."""

    def test_improving_trend(self):
        values = [50, 55, 60, 65, 70, 75, 80]
        direction, pct = compute_trend(values)
        assert direction == "improving"
        assert pct > 0

    def test_degrading_trend(self):
        values = [80, 75, 70, 65, 60, 55, 50]
        direction, pct = compute_trend(values)
        assert direction == "degrading"
        assert pct < 0

    def test_stable_trend(self):
        values = [50, 50, 50, 50, 50]
        direction, pct = compute_trend(values)
        assert direction == "stable"
        assert pct == pytest.approx(0.0, abs=3.1)

    def test_single_value_stable(self):
        direction, pct = compute_trend([50])
        assert direction == "stable"
        assert pct == 0.0

    def test_empty_stable(self):
        direction, pct = compute_trend([])
        assert direction == "stable"


class TestEstimateChurnRisk:
    """Tests for estimate_churn_risk."""

    def test_high_risk(self):
        assert estimate_churn_risk(-15) == "high"

    def test_moderate_risk(self):
        assert estimate_churn_risk(-7) == "moderate"

    def test_low_risk(self):
        assert estimate_churn_risk(0) == "low"
        assert estimate_churn_risk(5) == "low"


# ---------------------------------------------------------------------------
# Maintenance scorer helpers
# ---------------------------------------------------------------------------


class TestComputeAgeScore:
    """Tests for compute_age_score."""

    def test_none_returns_50(self):
        assert compute_age_score(None) == 50.0

    def test_new_infrastructure(self):
        """Less than 2 years old -> low score."""
        first_seen = date(2025, 1, 1)
        current = date(2026, 1, 1)  # 1 year old
        score = compute_age_score(first_seen, current)
        assert score < 25

    def test_old_infrastructure(self):
        """More than 8 years old -> 100."""
        first_seen = date(2015, 1, 1)
        current = date(2026, 1, 1)  # 11 years old
        score = compute_age_score(first_seen, current)
        assert score == 100.0

    def test_mid_age_interpolation(self):
        """5 years old should be between 25 and 100."""
        first_seen = date(2021, 3, 1)
        current = date(2026, 3, 1)
        score = compute_age_score(first_seen, current)
        assert 25 < score < 100


class TestComputeRevenueRisk:
    """Tests for compute_revenue_risk."""

    def test_zero_subscribers(self):
        assert compute_revenue_risk(0) == 0.0

    def test_positive_subscribers(self):
        score = compute_revenue_risk(1_000)
        assert score > 0

    def test_large_revenue_caps_at_100(self):
        """Very high subscriber count should cap at 100."""
        score = compute_revenue_risk(100_000, arpu_brl=100)
        assert score <= 100.0

    def test_more_subs_higher_score(self):
        small = compute_revenue_risk(100)
        large = compute_revenue_risk(10_000)
        assert large > small


class TestDetermineTiming:
    """Tests for _determine_timing."""

    def test_immediate(self):
        assert _determine_timing(85) == "immediate"

    def test_within_7_days(self):
        assert _determine_timing(65) == "within_7_days"

    def test_within_30_days(self):
        assert _determine_timing(45) == "within_30_days"

    def test_routine(self):
        assert _determine_timing(20) == "routine"


class TestRecommendAction:
    """Tests for recommend_action."""

    def test_returns_string(self):
        priority = MaintenancePriority(
            municipality_id=1,
            municipality_name="Test",
            priority_score=75,
            weather_risk_score=90,
            infrastructure_age_score=50,
            quality_trend_score=40,
            revenue_risk_score=60,
            competitive_pressure_score=30,
            recommended_action="",
            timing="immediate",
        )
        result = recommend_action(priority)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Seasonal patterns
# ---------------------------------------------------------------------------


class TestGenerateRiskPattern:
    """Tests for generate_risk_pattern."""

    def test_returns_12_months(self):
        pattern = generate_risk_pattern("southeast")
        assert len(pattern) == 12

    def test_months_numbered_1_to_12(self):
        pattern = generate_risk_pattern("north")
        months = [r.month for r in pattern]
        assert months == list(range(1, 13))

    def test_scores_in_range(self):
        for region in ("north", "northeast", "southeast", "south", "central-west"):
            pattern = generate_risk_pattern(region)
            for r in pattern:
                assert 0 <= r.risk_score <= 100

    def test_unknown_region_falls_back(self):
        """Unknown region should fall back to southeast defaults."""
        pattern = generate_risk_pattern("nonexistent")
        se_pattern = generate_risk_pattern("southeast")
        assert len(pattern) == 12
        # Should match southeast pattern
        for a, b in zip(pattern, se_pattern):
            assert a.risk_score == b.risk_score


class TestGetRegionFromState:
    """Tests for get_region_from_state."""

    def test_sp_is_southeast(self):
        assert get_region_from_state("SP") == "southeast"

    def test_am_is_north(self):
        assert get_region_from_state("AM") == "north"

    def test_ba_is_northeast(self):
        assert get_region_from_state("BA") == "northeast"

    def test_rs_is_south(self):
        assert get_region_from_state("RS") == "south"

    def test_df_is_central_west(self):
        assert get_region_from_state("DF") == "central-west"

    def test_unknown_defaults_to_southeast(self):
        assert get_region_from_state("XX") == "southeast"

    def test_all_27_states_mapped(self):
        assert len(REGION_MAP) == 27

    def test_case_insensitive(self):
        assert get_region_from_state("sp") == "southeast"
        assert get_region_from_state("Sp") == "southeast"
