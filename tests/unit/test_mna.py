"""Tests for M&A (Mergers & Acquisitions) modules.

Covers:
- Subscriber multiple valuation
- Revenue multiple valuation
- DCF valuation
- Acquirer target evaluation
- Seller preparation report
"""

from __future__ import annotations

import pytest

from python.mna.valuation.subscriber_multiple import calculate as sub_calc
from python.mna.valuation.revenue_multiple import calculate as rev_calc
from python.mna.valuation.dcf import calculate as dcf_calc
from python.mna.acquirer import evaluate_targets, compute_synergies
from python.mna.seller import prepare_for_sale


# ---------------------------------------------------------------------------
# Subscriber multiple valuation
# ---------------------------------------------------------------------------


class TestSubscriberMultiple:
    """Tests for subscriber_multiple.calculate."""

    def test_returns_valuation_object(self):
        result = sub_calc(total_subscribers=10_000)
        assert hasattr(result, "adjusted_valuation_brl")
        assert hasattr(result, "valuation_range")
        assert hasattr(result, "confidence")

    def test_valuation_positive(self):
        result = sub_calc(total_subscribers=5_000)
        assert result.adjusted_valuation_brl > 0

    def test_more_subs_higher_value(self):
        small = sub_calc(total_subscribers=2_000)
        large = sub_calc(total_subscribers=20_000)
        assert large.adjusted_valuation_brl > small.adjusted_valuation_brl

    def test_higher_fiber_higher_value(self):
        low_fiber = sub_calc(total_subscribers=10_000, fiber_pct=0.20)
        high_fiber = sub_calc(total_subscribers=10_000, fiber_pct=0.90)
        assert high_fiber.adjusted_valuation_brl > low_fiber.adjusted_valuation_brl

    def test_high_churn_discounts_value(self):
        low_churn = sub_calc(total_subscribers=10_000, monthly_churn_pct=1.0)
        high_churn = sub_calc(total_subscribers=10_000, monthly_churn_pct=4.0)
        assert low_churn.adjusted_valuation_brl > high_churn.adjusted_valuation_brl

    def test_sp_premium(self):
        """Sao Paulo state should have a region premium."""
        sp = sub_calc(total_subscribers=10_000, state_code="SP")
        other = sub_calc(total_subscribers=10_000, state_code="PA")
        assert sp.adjusted_valuation_brl >= other.adjusted_valuation_brl

    def test_valuation_range_is_tuple(self):
        result = sub_calc(total_subscribers=10_000)
        assert isinstance(result.valuation_range, tuple)
        assert len(result.valuation_range) == 2
        assert result.valuation_range[0] < result.valuation_range[1]

    def test_growth_rate_premium(self):
        """Higher growth should increase valuation."""
        slow = sub_calc(total_subscribers=10_000, growth_rate_12m=0.01)
        fast = sub_calc(total_subscribers=10_000, growth_rate_12m=0.20)
        assert fast.adjusted_valuation_brl >= slow.adjusted_valuation_brl


# ---------------------------------------------------------------------------
# Revenue multiple valuation
# ---------------------------------------------------------------------------


class TestRevenueMultiple:
    """Tests for revenue_multiple.calculate."""

    def test_returns_revenue_valuation(self):
        result = rev_calc(monthly_revenue_brl=500_000)
        assert hasattr(result, "ev_revenue_brl")
        assert hasattr(result, "ev_ebitda_brl")
        assert hasattr(result, "revenue_multiple")

    def test_ev_positive(self):
        result = rev_calc(monthly_revenue_brl=500_000)
        assert result.ev_revenue_brl > 0
        assert result.ev_ebitda_brl > 0

    def test_higher_revenue_higher_ev(self):
        small = rev_calc(monthly_revenue_brl=100_000)
        large = rev_calc(monthly_revenue_brl=1_000_000)
        assert large.ev_revenue_brl > small.ev_revenue_brl

    def test_higher_margin_higher_multiple(self):
        low_margin = rev_calc(monthly_revenue_brl=500_000, ebitda_margin_pct=20.0)
        high_margin = rev_calc(monthly_revenue_brl=500_000, ebitda_margin_pct=40.0)
        assert high_margin.revenue_multiple >= low_margin.revenue_multiple

    def test_fiber_premium(self):
        low_fiber = rev_calc(monthly_revenue_brl=500_000, fiber_pct=0.20)
        high_fiber = rev_calc(monthly_revenue_brl=500_000, fiber_pct=0.90)
        assert high_fiber.revenue_multiple > low_fiber.revenue_multiple

    def test_valuation_range(self):
        result = rev_calc(monthly_revenue_brl=500_000)
        low, high = result.valuation_range
        assert low < high


# ---------------------------------------------------------------------------
# DCF valuation
# ---------------------------------------------------------------------------


class TestDCFValuation:
    """Tests for dcf.calculate."""

    def test_returns_dcf_valuation(self):
        result = dcf_calc(monthly_revenue_brl=500_000)
        assert hasattr(result, "enterprise_value_brl")
        assert hasattr(result, "equity_value_brl")
        assert hasattr(result, "projected_cashflows")

    def test_five_year_projections(self):
        result = dcf_calc(monthly_revenue_brl=500_000)
        assert len(result.projected_cashflows) == 5

    def test_enterprise_value_positive(self):
        result = dcf_calc(monthly_revenue_brl=500_000)
        assert result.enterprise_value_brl > 0

    def test_equity_equals_ev_minus_debt(self):
        result = dcf_calc(monthly_revenue_brl=500_000, net_debt_brl=1_000_000)
        assert result.equity_value_brl == pytest.approx(
            max(0, result.enterprise_value_brl - 1_000_000), rel=1e-3,
        )

    def test_zero_debt_equity_equals_ev(self):
        result = dcf_calc(monthly_revenue_brl=500_000, net_debt_brl=0)
        assert result.equity_value_brl == pytest.approx(
            result.enterprise_value_brl, rel=1e-3,
        )

    def test_higher_wacc_lower_value(self):
        low_wacc = dcf_calc(monthly_revenue_brl=500_000, wacc_pct=10.0)
        high_wacc = dcf_calc(monthly_revenue_brl=500_000, wacc_pct=20.0)
        assert low_wacc.enterprise_value_brl > high_wacc.enterprise_value_brl

    def test_sensitivity_table_present(self):
        result = dcf_calc(monthly_revenue_brl=500_000)
        assert "wacc_values" in result.sensitivity_table
        assert "growth_values" in result.sensitivity_table
        assert "enterprise_values" in result.sensitivity_table

    def test_terminal_value_positive(self):
        result = dcf_calc(monthly_revenue_brl=500_000)
        assert result.terminal_value_brl > 0


# ---------------------------------------------------------------------------
# Acquirer target evaluation
# ---------------------------------------------------------------------------


class TestEvaluateTargets:
    """Tests for acquirer.evaluate_targets."""

    def test_returns_list(self):
        targets = evaluate_targets(
            acquirer_states=["SP"],
            acquirer_subscribers=10_000,
        )
        assert isinstance(targets, list)

    def test_targets_sorted_by_score(self):
        targets = evaluate_targets(
            acquirer_states=["SP"],
            acquirer_subscribers=10_000,
        )
        scores = [t.overall_score for t in targets]
        assert scores == sorted(scores, reverse=True)

    def test_filters_by_subscriber_range(self):
        targets = evaluate_targets(
            acquirer_states=["SP"],
            acquirer_subscribers=10_000,
            min_target_subs=10_000,
            max_target_subs=25_000,
        )
        for t in targets:
            assert 10_000 <= t.subscriber_count <= 25_000

    def test_has_expected_fields(self):
        targets = evaluate_targets(
            acquirer_states=["SP"],
            acquirer_subscribers=10_000,
        )
        if targets:
            t = targets[0]
            assert hasattr(t, "provider_name")
            assert hasattr(t, "overall_score")
            assert hasattr(t, "strategic_score")
            assert hasattr(t, "financial_score")
            assert hasattr(t, "integration_risk")


class TestComputeSynergies:
    """Tests for compute_synergies."""

    def test_returns_dict(self):
        result = compute_synergies(
            acquirer_profile={"subscriber_count": 15_000, "states": ["SP"]},
            target_profile={
                "subscriber_count": 5_000,
                "states": ["SP"],
                "monthly_revenue_brl": 400_000,
            },
        )
        assert isinstance(result, dict)
        assert "annual_synergy_brl" in result

    def test_synergy_positive(self):
        result = compute_synergies(
            acquirer_profile={"subscriber_count": 10_000, "states": ["SP"]},
            target_profile={
                "subscriber_count": 8_000,
                "states": ["RJ"],
                "monthly_revenue_brl": 600_000,
            },
        )
        assert result["annual_synergy_brl"] > 0

    def test_geographic_overlap_increases_synergy(self):
        overlap = compute_synergies(
            acquirer_profile={"subscriber_count": 10_000, "states": ["SP"]},
            target_profile={
                "subscriber_count": 5_000,
                "states": ["SP"],
                "monthly_revenue_brl": 400_000,
            },
        )
        no_overlap = compute_synergies(
            acquirer_profile={"subscriber_count": 10_000, "states": ["SP"]},
            target_profile={
                "subscriber_count": 5_000,
                "states": ["BA"],
                "monthly_revenue_brl": 400_000,
            },
        )
        assert overlap["annual_synergy_brl"] > no_overlap["annual_synergy_brl"]


# ---------------------------------------------------------------------------
# Seller preparation
# ---------------------------------------------------------------------------


class TestSellerReport:
    """Tests for seller.prepare_for_sale."""

    def test_returns_seller_report(self):
        report = prepare_for_sale(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            fiber_pct=0.75,
            monthly_revenue_brl=640_000,
        )
        assert hasattr(report, "estimated_value_range")
        assert hasattr(report, "strengths")
        assert hasattr(report, "weaknesses")

    def test_value_range_is_tuple(self):
        report = prepare_for_sale(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            fiber_pct=0.75,
            monthly_revenue_brl=640_000,
        )
        assert isinstance(report.estimated_value_range, tuple)
        assert len(report.estimated_value_range) == 2
        assert report.estimated_value_range[0] < report.estimated_value_range[1]

    def test_has_preparation_checklist(self):
        report = prepare_for_sale(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            fiber_pct=0.75,
            monthly_revenue_brl=640_000,
        )
        assert isinstance(report.preparation_checklist, list)
        assert len(report.preparation_checklist) >= 1

    def test_timeline_reasonable(self):
        report = prepare_for_sale(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            fiber_pct=0.75,
            monthly_revenue_brl=640_000,
        )
        assert 3 <= report.estimated_timeline_months <= 12

    def test_valuation_methods_dict(self):
        report = prepare_for_sale(
            provider_name="TestNet",
            state_codes=["SP"],
            subscriber_count=8_000,
            fiber_pct=0.75,
            monthly_revenue_brl=640_000,
        )
        assert "subscriber_multiple" in report.valuation_methods
        assert "revenue_multiple" in report.valuation_methods
        assert "dcf" in report.valuation_methods
