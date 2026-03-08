"""Tests for regulatory compliance modules.

Covers:
- ICMS tax rate lookup (all 27 states)
- Norma no. 4 impact calculation and restructuring options
- Licensing threshold checks
- Compliance profile analysis
- Regulation knowledge base
- Deadline tracking
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from python.regulatory.knowledge_base.tax_rates import (
    ICMS_RATES_SCM,
    get_telecom_icms,
    get_all_rates,
    compute_blended_rate,
)
from python.regulatory.analyzer.norma4 import (
    calculate_impact,
    score_restructuring_options,
    NORMA4_DEADLINE,
)
from python.regulatory.analyzer.licensing import (
    check_licensing,
    LICENSING_THRESHOLD,
)
from python.regulatory.analyzer.profile import analyze_profile
from python.regulatory.knowledge_base.regulations import (
    REGULATIONS,
    get_regulation,
    get_regulations_by_size,
)
from python.regulatory.knowledge_base.deadlines import (
    days_until,
    get_urgency,
    get_all_deadlines,
    get_upcoming_deadlines,
)


# ---------------------------------------------------------------------------
# ICMS tax rates
# ---------------------------------------------------------------------------


class TestICMSTaxRates:
    """Tests for ICMS telecom tax rates."""

    def test_all_27_states_present(self):
        """Brazil has 26 states + DF = 27 entries."""
        assert len(ICMS_RATES_SCM) == 27

    def test_sp_rate(self):
        assert get_telecom_icms("SP") == 0.25

    def test_unknown_state_raises(self):
        """Unknown state code should raise ValueError."""
        with pytest.raises(ValueError):
            get_telecom_icms("XX")

    def test_rates_are_reasonable(self):
        """All telecom rates should be between 5% and 40%."""
        for state, rate_info in ICMS_RATES_SCM.items():
            telecom_rate = rate_info["telecom"]
            assert 0.05 <= telecom_rate <= 0.40, f"Rate for {state} is {telecom_rate}"

    def test_get_all_rates(self):
        all_rates = get_all_rates()
        assert isinstance(all_rates, dict)
        assert len(all_rates) == 27

    def test_blended_rate(self):
        """Blended rate across multiple states."""
        revenues = {"SP": 500_000, "RJ": 300_000, "MG": 200_000}
        rate = compute_blended_rate(revenues)
        assert isinstance(rate, float)
        assert 0.0 < rate < 1.0


# ---------------------------------------------------------------------------
# Norma no. 4 impact
# ---------------------------------------------------------------------------


class TestNorma4Impact:
    """Tests for calculate_impact and score_restructuring_options."""

    def test_returns_impact_object(self):
        impact = calculate_impact(
            state_code="SP",
            monthly_broadband_revenue_brl=500_000,
            subscriber_count=8_000,
        )
        assert hasattr(impact, "additional_annual_tax_brl")
        assert hasattr(impact, "readiness_score")

    def test_sva_classification_has_increase(self):
        """SVA operators face tax increase on migration to SCM."""
        impact = calculate_impact(
            state_code="SP",
            monthly_broadband_revenue_brl=500_000,
            subscriber_count=8_000,
            current_classification="SVA",
        )
        assert impact.additional_annual_tax_brl > 0

    def test_scm_classification_no_increase(self):
        """Already-SCM operators should have zero increase."""
        impact = calculate_impact(
            state_code="SP",
            monthly_broadband_revenue_brl=500_000,
            subscriber_count=8_000,
            current_classification="SCM",
        )
        assert impact.additional_annual_tax_brl == 0

    def test_readiness_score_range(self):
        impact = calculate_impact(
            state_code="MG",
            monthly_broadband_revenue_brl=300_000,
            subscriber_count=5_000,
        )
        assert 0 <= impact.readiness_score <= 100

    def test_restructuring_options(self):
        impact = calculate_impact(
            state_code="SP",
            monthly_broadband_revenue_brl=500_000,
            subscriber_count=8_000,
        )
        options = score_restructuring_options(impact)
        assert isinstance(options, list)
        assert len(options) >= 1
        for opt in options:
            assert "strategy" in opt or "name" in opt or "description" in opt

    def test_deadline_is_future_date(self):
        """NORMA4_DEADLINE should be 2027-01-01."""
        assert NORMA4_DEADLINE == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# Licensing thresholds
# ---------------------------------------------------------------------------


class TestLicensing:
    """Tests for check_licensing."""

    def test_threshold_is_5000(self):
        assert LICENSING_THRESHOLD == 5_000

    def test_below_threshold_not_above(self):
        """Below 5000 should not be above threshold."""
        status = check_licensing(subscriber_count=3_000)
        assert status.above_threshold is False

    def test_above_threshold(self):
        """Above 5000 should be above threshold."""
        status = check_licensing(subscriber_count=6_000)
        assert status.above_threshold is True

    def test_at_threshold_is_above(self):
        """At exactly 5000 should be at or above threshold."""
        status = check_licensing(subscriber_count=5_000)
        assert status.above_threshold is True

    def test_warning_zone(self):
        """Near threshold (80% = 4000) should have moderate urgency or warning."""
        status = check_licensing(subscriber_count=4_200)
        # Should show some awareness of approaching threshold
        assert status.pct_of_threshold >= 80.0

    def test_small_provider_safe(self):
        """Small provider well below threshold should have safe urgency."""
        status = check_licensing(subscriber_count=1_000)
        assert status.urgency == "safe"

    def test_returns_licensing_status(self):
        """LicensingStatus should have standard fields."""
        status = check_licensing(subscriber_count=3_000)
        assert hasattr(status, "subscriber_count")
        assert hasattr(status, "above_threshold")
        assert hasattr(status, "urgency")
        assert hasattr(status, "requirements")

    def test_has_requirements_list(self):
        status = check_licensing(subscriber_count=6_000)
        assert isinstance(status.requirements, list)
        assert len(status.requirements) >= 1


# ---------------------------------------------------------------------------
# Compliance profile
# ---------------------------------------------------------------------------


class TestComplianceProfile:
    """Tests for analyze_profile."""

    def test_returns_profile(self):
        profile = analyze_profile(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            services=["internet"],
        )
        assert hasattr(profile, "overall_score")
        assert hasattr(profile, "checks")

    def test_overall_score_range(self):
        profile = analyze_profile(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            services=["internet"],
        )
        assert 0 <= profile.overall_score <= 100

    def test_has_checks_list(self):
        profile = analyze_profile(
            provider_name="TestNet",
            state_codes=["SP", "RJ"],
            subscriber_count=12_000,
            services=["internet", "voip"],
        )
        assert isinstance(profile.checks, list)
        assert len(profile.checks) >= 1

    def test_critical_issues_count(self):
        profile = analyze_profile(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            services=["internet"],
        )
        assert isinstance(profile.critical_issues, int)
        assert profile.critical_issues >= 0


# ---------------------------------------------------------------------------
# Regulation knowledge base
# ---------------------------------------------------------------------------


class TestRegulations:
    """Tests for the regulation knowledge base."""

    def test_regulations_list_not_empty(self):
        assert len(REGULATIONS) >= 1

    def test_get_regulation_by_id(self):
        reg = get_regulation("norma4")
        assert reg is not None
        assert reg.id == "norma4"

    def test_get_nonexistent_regulation(self):
        reg = get_regulation("nonexistent_regulation_xyz")
        assert reg is None

    def test_regulations_have_required_fields(self):
        for reg in REGULATIONS:
            assert hasattr(reg, "id")
            assert hasattr(reg, "name")
            assert hasattr(reg, "description")

    def test_get_regulations_by_size(self):
        small = get_regulations_by_size(2_000)
        large = get_regulations_by_size(60_000)
        # Larger providers should have equal or more regulations
        assert len(large) >= len(small)


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


class TestDeadlines:
    """Tests for deadline tracking."""

    def test_days_until_future_date(self):
        future = date.today() + timedelta(days=100)
        result = days_until(future)
        assert 99 <= result <= 101

    def test_days_until_past_date(self):
        past = date.today() - timedelta(days=30)
        result = days_until(past)
        assert result < 0

    def test_get_urgency_categories(self):
        """Urgency should be one of the expected labels."""
        far_future = date.today() + timedelta(days=365)
        urgency = get_urgency(far_future)
        valid_levels = {"low", "medium", "high", "critical", "overdue", "safe",
                        "approaching", "warning"}
        assert urgency in valid_levels

    def test_overdue_urgency(self):
        """Past deadlines should be 'overdue'."""
        past = date.today() - timedelta(days=30)
        assert get_urgency(past) == "overdue"

    def test_get_all_deadlines(self):
        deadlines = get_all_deadlines()
        assert isinstance(deadlines, list)
        assert len(deadlines) >= 1

    def test_upcoming_deadlines(self):
        upcoming = get_upcoming_deadlines(within_days=365 * 5)
        assert isinstance(upcoming, list)
