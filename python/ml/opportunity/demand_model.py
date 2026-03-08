"""Subscriber demand estimation for broadband market sizing.

Estimates the addressable market for broadband services in a municipality
by combining household counts, income-based affordability analysis, and
current penetration rates.
"""

import logging

from python.ml.config import MIN_BROADBAND_PRICE_BRL, AFFORDABILITY_INCOME_RATIO

logger = logging.getLogger(__name__)


def estimate_addressable_market(
    households: int,
    avg_income: float,
    current_penetration: float,
    urbanization_rate: float = 0.6,
    household_growth_rate: float = 0.01,
) -> dict:
    """Estimate addressable market for broadband in a municipality.

    Uses an affordability-adjusted ceiling approach:
    1. Compute the fraction of households that can afford broadband
       based on income distribution relative to the minimum price.
    2. Apply an urbanization adjustment (rural areas have lower adoption).
    3. Compute untapped demand as the gap between the ceiling and current
       penetration.

    Args:
        households: Total number of households in the municipality.
        avg_income: Average per-capita income in BRL.
        current_penetration: Current broadband penetration rate (0-1).
        urbanization_rate: Fraction of population in urban areas (0-1).
        household_growth_rate: Annual household growth rate.

    Returns:
        Dictionary with:
            - addressable_households: Number of households that could subscribe.
            - penetration_ceiling: Maximum achievable penetration (0-1).
            - untapped_demand: Number of unserved addressable households.
            - monthly_revenue_potential_brl: Estimated monthly revenue from
              untapped demand at minimum broadband price.
            - demand_score: Score from 0-100 representing opportunity.
    """
    if households <= 0:
        return {
            "addressable_households": 0,
            "penetration_ceiling": 0.0,
            "untapped_demand": 0,
            "monthly_revenue_potential_brl": 0.0,
            "demand_score": 0.0,
        }

    # Affordability threshold: monthly income must be at least
    # AFFORDABILITY_INCOME_RATIO * MIN_BROADBAND_PRICE
    affordability_threshold = MIN_BROADBAND_PRICE_BRL * AFFORDABILITY_INCOME_RATIO

    # Estimate fraction of households that can afford broadband
    # Using a sigmoid-like curve centered on the threshold
    # avg_income is per capita; multiply by ~2.5 for household income estimate
    estimated_household_income = avg_income * 2.5

    if estimated_household_income <= 0:
        affordability_fraction = 0.05
    else:
        # Ratio of household income to threshold
        ratio = estimated_household_income / affordability_threshold
        # Sigmoid: maps ratio to [0, 1] with inflection at ratio=1
        import math

        affordability_fraction = 1.0 / (1.0 + math.exp(-3.0 * (ratio - 1.0)))

    # Urbanization adjustment: rural areas have ~60% of urban adoption potential
    urban_multiplier = 0.4 + 0.6 * urbanization_rate

    # Technology-aware ceiling: broadband penetration rarely exceeds ~85%
    max_ceiling = 0.85

    # Compute penetration ceiling
    penetration_ceiling = min(max_ceiling, affordability_fraction * urban_multiplier)

    # Addressable households
    addressable_households = int(households * penetration_ceiling)

    # Currently served households
    currently_served = int(households * min(current_penetration, 1.0))

    # Untapped demand
    untapped_demand = max(0, addressable_households - currently_served)

    # Revenue potential
    monthly_revenue = untapped_demand * MIN_BROADBAND_PRICE_BRL

    # Demand score: combination of untapped demand size and growth
    # Normalize to 0-100 scale
    demand_intensity = untapped_demand / max(households, 1)
    growth_bonus = min(0.2, household_growth_rate * 10)  # Up to 20% bonus for growth

    # Score: weighted combination of demand gap and absolute size
    size_factor = min(1.0, untapped_demand / 50000)  # Caps at 50k households
    demand_score = min(
        100.0,
        (demand_intensity * 60 + size_factor * 25 + growth_bonus * 100 * 0.15) * 100
        / 100,
    )
    demand_score = max(0.0, demand_score)

    return {
        "addressable_households": addressable_households,
        "penetration_ceiling": round(penetration_ceiling, 4),
        "untapped_demand": untapped_demand,
        "monthly_revenue_potential_brl": round(monthly_revenue, 2),
        "demand_score": round(demand_score, 2),
    }


def compute_demand_score(features: dict) -> float:
    """Compute demand sub-score from feature dictionary.

    This is the simplified scoring function used by the main scorer
    for computing the demand component of the composite score.

    Args:
        features: Dictionary with demand-related feature values.

    Returns:
        Demand score from 0 to 100.
    """
    result = estimate_addressable_market(
        households=int(features.get("total_households", 0)),
        avg_income=float(features.get("avg_income_per_capita", 1500)),
        current_penetration=float(features.get("current_penetration", 0)),
        urbanization_rate=float(features.get("urbanization_rate", 0.6)),
        household_growth_rate=float(features.get("household_growth_rate", 0.01)),
    )
    return result["demand_score"]
