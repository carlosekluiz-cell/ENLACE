"""Revenue multiple (EV/Revenue) valuation.

VALUE = annual_revenue x revenue_multiple

Typical multiples for Brazilian ISPs:
- Small ISP (<5k subs): 1.5-3.0x revenue
- Medium ISP (5k-50k subs): 2.0-4.0x revenue
- Large ISP (>50k subs): 3.0-6.0x revenue
- With high fiber %: +0.5-1.0x premium
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Revenue multiple tiers by subscriber count
# ---------------------------------------------------------------------------
# (max_subs, base_revenue_multiple, base_ebitda_multiple)
MULTIPLE_TIERS: list[tuple[int, float, float]] = [
    (2_000, 2.0, 5.0),
    (5_000, 2.5, 5.5),
    (10_000, 3.0, 6.0),
    (20_000, 3.5, 6.5),
    (50_000, 4.0, 7.0),
    (100_000, 4.5, 7.5),
    (999_999_999, 5.0, 8.0),
]


@dataclass
class RevenueValuation:
    """Result of revenue-multiple valuation."""

    annual_revenue_brl: float
    ebitda_brl: float
    ebitda_margin_pct: float
    revenue_multiple: float
    ebitda_multiple: float
    ev_revenue_brl: float
    ev_ebitda_brl: float
    adjustments: dict
    valuation_range: tuple[float, float]


def _base_multiples(subscriber_count: int) -> tuple[float, float]:
    """Look up base revenue and EBITDA multiples by subscriber tier."""
    for max_subs, rev_mult, ebitda_mult in MULTIPLE_TIERS:
        if subscriber_count <= max_subs:
            return rev_mult, ebitda_mult
    # fallback (should not reach here)
    return MULTIPLE_TIERS[-1][1], MULTIPLE_TIERS[-1][2]


def _fiber_premium(fiber_pct: float) -> float:
    """Additional multiple premium for high fiber penetration."""
    if fiber_pct >= 0.90:
        return 1.0
    if fiber_pct >= 0.70:
        return 0.7
    if fiber_pct >= 0.50:
        return 0.4
    if fiber_pct >= 0.30:
        return 0.1
    return 0.0


def _growth_premium(revenue_growth_12m: float) -> float:
    """Multiple premium/discount based on revenue growth."""
    if revenue_growth_12m >= 0.25:
        return 0.8
    if revenue_growth_12m >= 0.15:
        return 0.5
    if revenue_growth_12m >= 0.08:
        return 0.2
    if revenue_growth_12m >= 0.0:
        return 0.0
    if revenue_growth_12m >= -0.05:
        return -0.3
    return -0.5


def _margin_adjustment(ebitda_margin_pct: float) -> float:
    """Multiplier adjustment based on profitability.

    Baseline assumption: 30% EBITDA margin is neutral.
    """
    if ebitda_margin_pct >= 40.0:
        return 1.12
    if ebitda_margin_pct >= 35.0:
        return 1.06
    if ebitda_margin_pct >= 30.0:
        return 1.00
    if ebitda_margin_pct >= 25.0:
        return 0.95
    if ebitda_margin_pct >= 20.0:
        return 0.90
    return 0.82


def calculate(
    monthly_revenue_brl: float,
    ebitda_margin_pct: float = 30.0,
    subscriber_count: int = 5_000,
    revenue_growth_12m: float = 0.10,
    fiber_pct: float = 0.5,
) -> RevenueValuation:
    """Calculate revenue multiple valuation.

    Parameters
    ----------
    monthly_revenue_brl : float
        Gross monthly recurring revenue in BRL.
    ebitda_margin_pct : float
        EBITDA margin as percentage (e.g. 30.0 for 30%).
    subscriber_count : int
        Total active subscriber count (used to select multiple tier).
    revenue_growth_12m : float
        12-month revenue growth rate (e.g. 0.10 for 10%).
    fiber_pct : float
        Fraction of subscribers on fiber (0.0-1.0).

    Returns
    -------
    RevenueValuation
    """
    annual_revenue = monthly_revenue_brl * 12
    ebitda = annual_revenue * (ebitda_margin_pct / 100.0)

    # Base multiples from subscriber tier
    base_rev_mult, base_ebitda_mult = _base_multiples(subscriber_count)

    # Adjustments
    fiber_prem = _fiber_premium(fiber_pct)
    growth_prem = _growth_premium(revenue_growth_12m)
    margin_adj = _margin_adjustment(ebitda_margin_pct)

    # Apply additive premiums first, then margin multiplier
    adjusted_rev_mult = (base_rev_mult + fiber_prem + growth_prem) * margin_adj
    adjusted_ebitda_mult = (base_ebitda_mult + fiber_prem + growth_prem) * margin_adj

    # Ensure multiples stay in reasonable range
    adjusted_rev_mult = max(1.0, adjusted_rev_mult)
    adjusted_ebitda_mult = max(3.0, adjusted_ebitda_mult)

    ev_revenue = annual_revenue * adjusted_rev_mult
    ev_ebitda = ebitda * adjusted_ebitda_mult

    # Blended enterprise value (average of both methods)
    blended_ev = (ev_revenue + ev_ebitda) / 2

    adjustments = {
        "base_revenue_multiple": round(base_rev_mult, 2),
        "base_ebitda_multiple": round(base_ebitda_mult, 2),
        "fiber_premium": round(fiber_prem, 2),
        "growth_premium": round(growth_prem, 2),
        "margin_adjustment": round(margin_adj, 4),
        "subscriber_tier": _tier_label(subscriber_count),
    }

    # Range: EV/Revenue as low, EV/EBITDA as high (or whichever is larger)
    val_low = min(ev_revenue, ev_ebitda) * 0.85
    val_high = max(ev_revenue, ev_ebitda) * 1.15

    return RevenueValuation(
        annual_revenue_brl=round(annual_revenue, 2),
        ebitda_brl=round(ebitda, 2),
        ebitda_margin_pct=round(ebitda_margin_pct, 2),
        revenue_multiple=round(adjusted_rev_mult, 2),
        ebitda_multiple=round(adjusted_ebitda_mult, 2),
        ev_revenue_brl=round(ev_revenue, 2),
        ev_ebitda_brl=round(ev_ebitda, 2),
        adjustments=adjustments,
        valuation_range=(round(val_low, 2), round(val_high, 2)),
    )


def _tier_label(subscriber_count: int) -> str:
    """Human-readable tier label."""
    if subscriber_count < 5_000:
        return "small"
    if subscriber_count < 50_000:
        return "medium"
    return "large"
