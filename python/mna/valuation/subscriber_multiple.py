"""Subscriber multiple valuation.

VALUE = subscriber_count x per_subscriber_multiple

Multiples vary by:
- Technology (fiber subs worth more than DSL)
- Churn rate (lower churn = higher multiple)
- Region (Southeast > North)
- Growth trend (growing = premium, declining = discount)

Typical Brazilian ISP multiples (2024-2025 data):
- Fiber subscriber: R$1,500 - R$3,500 per sub
- Mixed (fiber + other): R$1,200 - R$2,800
- DSL/cable only: R$800 - R$1,500
- Wireless only: R$600 - R$1,200
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Regional multiplier adjustments (higher-income regions command premiums)
# ---------------------------------------------------------------------------
REGION_MULTIPLIERS: dict[str, float] = {
    # Southeast (premium markets)
    "SP": 1.15,
    "RJ": 1.10,
    "MG": 1.05,
    "ES": 1.05,
    # South
    "PR": 1.08,
    "SC": 1.10,
    "RS": 1.05,
    # Center-West
    "DF": 1.12,
    "GO": 1.00,
    "MT": 0.98,
    "MS": 0.98,
    # Northeast
    "BA": 0.95,
    "PE": 0.95,
    "CE": 0.93,
    "MA": 0.90,
    "PB": 0.92,
    "RN": 0.92,
    "AL": 0.90,
    "SE": 0.90,
    "PI": 0.88,
    # North
    "PA": 0.88,
    "AM": 0.85,
    "RO": 0.90,
    "AC": 0.85,
    "AP": 0.85,
    "RR": 0.85,
    "TO": 0.90,
}

# Base multiples per subscriber (BRL)
FIBER_MULTIPLE_BASE: float = 2_500.0
OTHER_MULTIPLE_BASE: float = 1_000.0


@dataclass
class SubscriberValuation:
    """Result of subscriber-multiple valuation."""

    total_subscribers: int
    fiber_subscribers: int
    other_subscribers: int
    fiber_multiple: float
    other_multiple: float
    base_valuation_brl: float
    adjustments: dict  # growth, churn, region, technology
    adjusted_valuation_brl: float
    valuation_range: tuple[float, float]  # low, high
    confidence: str  # low, medium, high


def _churn_adjustment(monthly_churn_pct: float) -> float:
    """Return a multiplier based on monthly churn rate.

    Lower churn => higher premium; higher churn => discount.
    Baseline assumption: 2.0% monthly churn is neutral (1.0x).
    """
    if monthly_churn_pct <= 1.0:
        return 1.15  # excellent retention
    if monthly_churn_pct <= 1.5:
        return 1.08
    if monthly_churn_pct <= 2.0:
        return 1.00  # baseline
    if monthly_churn_pct <= 3.0:
        return 0.90
    if monthly_churn_pct <= 4.0:
        return 0.80
    return 0.70  # very high churn


def _growth_adjustment(growth_rate_12m: float) -> float:
    """Return a multiplier based on 12-month subscriber growth.

    Positive growth earns a premium; decline earns a discount.
    """
    if growth_rate_12m >= 0.20:
        return 1.20  # rapid growth
    if growth_rate_12m >= 0.10:
        return 1.12
    if growth_rate_12m >= 0.05:
        return 1.05
    if growth_rate_12m >= 0.0:
        return 1.00  # flat
    if growth_rate_12m >= -0.05:
        return 0.92
    if growth_rate_12m >= -0.10:
        return 0.85
    return 0.75  # significant decline


def _technology_adjustment(fiber_pct: float) -> float:
    """Premium for fiber-heavy networks."""
    if fiber_pct >= 0.90:
        return 1.20
    if fiber_pct >= 0.70:
        return 1.10
    if fiber_pct >= 0.50:
        return 1.00
    if fiber_pct >= 0.30:
        return 0.92
    return 0.85


def _determine_confidence(
    total_subscribers: int,
    fiber_pct: float,
    monthly_churn_pct: float,
) -> str:
    """Heuristic confidence level for the valuation."""
    # More subscribers and more fiber data => higher confidence
    if total_subscribers >= 10_000 and fiber_pct >= 0.5:
        return "high"
    if total_subscribers >= 3_000:
        return "medium"
    return "low"


def calculate(
    total_subscribers: int,
    fiber_pct: float = 0.5,
    monthly_churn_pct: float = 2.0,
    growth_rate_12m: float = 0.05,
    state_code: str = "SP",
    technology_mix: dict | None = None,
) -> SubscriberValuation:
    """Calculate subscriber multiple valuation.

    Parameters
    ----------
    total_subscribers : int
        Total active subscriber count.
    fiber_pct : float
        Fraction of subscribers on fiber (0.0-1.0).
    monthly_churn_pct : float
        Monthly subscriber churn percentage (e.g. 2.0 for 2%).
    growth_rate_12m : float
        12-month subscriber growth rate (e.g. 0.05 for 5%).
    state_code : str
        Two-letter Brazilian state code (e.g. "SP", "MG").
    technology_mix : dict | None
        Optional detailed tech breakdown. Reserved for future use.

    Returns
    -------
    SubscriberValuation
    """
    fiber_pct = max(0.0, min(1.0, fiber_pct))
    fiber_subscribers = int(total_subscribers * fiber_pct)
    other_subscribers = total_subscribers - fiber_subscribers

    # --- Base multiples ---
    region_mult = REGION_MULTIPLIERS.get(state_code.upper(), 1.00)
    fiber_multiple = FIBER_MULTIPLE_BASE * region_mult
    other_multiple = OTHER_MULTIPLE_BASE * region_mult

    base_valuation = (fiber_subscribers * fiber_multiple) + (
        other_subscribers * other_multiple
    )

    # --- Adjustment factors ---
    churn_adj = _churn_adjustment(monthly_churn_pct)
    growth_adj = _growth_adjustment(growth_rate_12m)
    tech_adj = _technology_adjustment(fiber_pct)

    combined_adjustment = churn_adj * growth_adj * tech_adj

    adjustments = {
        "region": {"state": state_code.upper(), "multiplier": round(region_mult, 4)},
        "churn": {
            "monthly_pct": monthly_churn_pct,
            "multiplier": round(churn_adj, 4),
        },
        "growth": {
            "rate_12m": growth_rate_12m,
            "multiplier": round(growth_adj, 4),
        },
        "technology": {
            "fiber_pct": fiber_pct,
            "multiplier": round(tech_adj, 4),
        },
        "combined_multiplier": round(combined_adjustment, 4),
    }

    adjusted_valuation = base_valuation * combined_adjustment

    # --- Valuation range (+-20% for subscriber method) ---
    range_spread = 0.20
    val_low = adjusted_valuation * (1 - range_spread)
    val_high = adjusted_valuation * (1 + range_spread)

    confidence = _determine_confidence(total_subscribers, fiber_pct, monthly_churn_pct)

    return SubscriberValuation(
        total_subscribers=total_subscribers,
        fiber_subscribers=fiber_subscribers,
        other_subscribers=other_subscribers,
        fiber_multiple=round(fiber_multiple, 2),
        other_multiple=round(other_multiple, 2),
        base_valuation_brl=round(base_valuation, 2),
        adjustments=adjustments,
        adjusted_valuation_brl=round(adjusted_valuation, 2),
        valuation_range=(round(val_low, 2), round(val_high, 2)),
        confidence=confidence,
    )
