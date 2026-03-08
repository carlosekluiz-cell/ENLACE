"""Rural community demand profiling.

Estimates connectivity demand for underserved communities based on
population, economics, and existing infrastructure. Uses Brazilian-specific
parameters for willingness-to-pay, use case identification, and subscriber
adoption modeling.

The demand model draws on:
- IBGE census and income data patterns
- NIC.br (CGI.br) internet usage surveys for rural Brazil
- Abrint small ISP subscriber adoption benchmarks
- Telebras community connectivity reports

Sources:
    - IBGE PNAD Continua — internet access module
    - CGI.br TIC Domicilios survey
    - Abrint member data (anonymized benchmarks)
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Adoption model parameters
# ---------------------------------------------------------------------------
# Base internet adoption rate for rural Brazil (IBGE 2023: ~76% urban, ~52% rural)
BASE_RURAL_ADOPTION_RATE = 0.52

# Income elasticity: higher income -> higher adoption
# For each R$100 above minimum wage, adoption increases by 1.5%
INCOME_ELASTICITY_PER_100BRL = 0.015

# Facility-driven demand multipliers
FACILITY_DEMAND_MULTIPLIER = {
    "school": 1.10,          # School increases community awareness
    "health_unit": 1.08,     # Telemedicine demand driver
    "agricultural_coop": 1.05,  # AgTech adoption
}

# Use case bandwidth requirements (Mbps per concurrent user)
USE_CASE_BANDWIDTH = {
    "education": {"per_user_mbps": 1.5, "concurrent_pct": 0.15},
    "health": {"per_user_mbps": 3.0, "concurrent_pct": 0.05},
    "agriculture": {"per_user_mbps": 0.5, "concurrent_pct": 0.10},
    "commerce": {"per_user_mbps": 1.0, "concurrent_pct": 0.08},
    "general": {"per_user_mbps": 2.0, "concurrent_pct": 0.10},
}

# Willingness to pay model
# Based on NIC.br surveys: rural users spend ~2-4% of income on connectivity
WTP_INCOME_RATIO_LOW = 0.02
WTP_INCOME_RATIO_HIGH = 0.04
WTP_INCOME_RATIO_MID = 0.03

# Minimum wage reference (2024)
MINIMUM_WAGE_BRL = 1_412

# Average household size in rural Brazil
AVG_HOUSEHOLD_SIZE = 3.5


@dataclass
class CommunityDemand:
    """Estimated connectivity demand for a rural community.

    Attributes:
        estimated_subscribers: Number of expected internet subscribers.
        estimated_bandwidth_mbps: Aggregate bandwidth needed in Mbps.
        primary_use_cases: Main use cases driving demand.
        revenue_potential_monthly_brl: Estimated monthly revenue from subscribers.
        willingness_to_pay_brl: Average monthly WTP per household in BRL.
        demand_confidence: Confidence level of the estimate.
    """

    estimated_subscribers: int
    estimated_bandwidth_mbps: float
    primary_use_cases: list[str]
    revenue_potential_monthly_brl: float
    willingness_to_pay_brl: float
    demand_confidence: str  # low, medium, high


def profile_community(
    population: int,
    avg_income_brl: float = 1_200,
    has_school: bool = True,
    has_health_unit: bool = True,
    agricultural: bool = True,
) -> CommunityDemand:
    """Estimate connectivity demand for a rural community.

    Uses a multi-factor model to estimate:
    - Number of subscribers (household-based adoption)
    - Aggregate bandwidth requirement
    - Primary use cases
    - Revenue potential
    - Willingness to pay

    Args:
        population: Total population of the community.
        avg_income_brl: Average monthly household income in BRL.
            Defaults to R$1,200 (approximately 0.85x minimum wage).
        has_school: Whether the community has a school.
        has_health_unit: Whether the community has a health unit/post.
        agricultural: Whether the community is primarily agricultural.

    Returns:
        CommunityDemand with all demand estimates.
    """
    # Handle edge cases
    if population <= 0:
        logger.warning("Community has population <= 0. Returning zero demand.")
        return CommunityDemand(
            estimated_subscribers=0,
            estimated_bandwidth_mbps=0.0,
            primary_use_cases=[],
            revenue_potential_monthly_brl=0.0,
            willingness_to_pay_brl=0.0,
            demand_confidence="low",
        )

    if avg_income_brl <= 0:
        logger.warning("Average income <= 0. Defaulting to minimum wage.")
        avg_income_brl = MINIMUM_WAGE_BRL

    # Step 1: Calculate number of households
    num_households = max(1, math.ceil(population / AVG_HOUSEHOLD_SIZE))

    # Step 2: Estimate adoption rate
    adoption_rate = BASE_RURAL_ADOPTION_RATE

    # Income adjustment
    income_delta = avg_income_brl - MINIMUM_WAGE_BRL
    income_adjustment = (income_delta / 100.0) * INCOME_ELASTICITY_PER_100BRL
    adoption_rate += income_adjustment

    # Facility-driven adjustments
    if has_school:
        adoption_rate *= FACILITY_DEMAND_MULTIPLIER["school"]
    if has_health_unit:
        adoption_rate *= FACILITY_DEMAND_MULTIPLIER["health_unit"]
    if agricultural:
        adoption_rate *= FACILITY_DEMAND_MULTIPLIER["agricultural_coop"]

    # Clamp adoption rate to valid range
    adoption_rate = max(0.10, min(0.90, adoption_rate))

    # Step 3: Estimate subscriber count
    estimated_subscribers = max(1, round(num_households * adoption_rate))

    # Step 4: Identify primary use cases and calculate bandwidth
    use_cases: list[str] = ["general"]
    total_bandwidth = 0.0

    if has_school:
        use_cases.append("education")
    if has_health_unit:
        use_cases.append("health")
    if agricultural:
        use_cases.append("agriculture")
    if population > 200:
        use_cases.append("commerce")

    for uc in use_cases:
        params = USE_CASE_BANDWIDTH.get(uc, USE_CASE_BANDWIDTH["general"])
        concurrent_users = estimated_subscribers * params["concurrent_pct"]
        uc_bandwidth = concurrent_users * params["per_user_mbps"]
        total_bandwidth += uc_bandwidth

    # Minimum viable bandwidth: 10 Mbps
    total_bandwidth = max(10.0, total_bandwidth)

    # Step 5: Calculate willingness to pay
    wtp_per_household = avg_income_brl * WTP_INCOME_RATIO_MID
    # Floor at R$30/mo (bare minimum for basic service)
    wtp_per_household = max(30.0, wtp_per_household)
    # Cap at R$150/mo (realistic rural ceiling)
    wtp_per_household = min(150.0, wtp_per_household)

    # Step 6: Estimate revenue potential
    revenue_monthly = estimated_subscribers * wtp_per_household

    # Step 7: Determine confidence level
    if population >= 500 and avg_income_brl >= MINIMUM_WAGE_BRL:
        confidence = "high"
    elif population >= 100:
        confidence = "medium"
    else:
        confidence = "low"

    demand = CommunityDemand(
        estimated_subscribers=estimated_subscribers,
        estimated_bandwidth_mbps=round(total_bandwidth, 2),
        primary_use_cases=use_cases,
        revenue_potential_monthly_brl=round(revenue_monthly, 2),
        willingness_to_pay_brl=round(wtp_per_household, 2),
        demand_confidence=confidence,
    )

    logger.info(
        "Community demand profile: pop=%d, households=%d, adoption=%.0f%%, "
        "subs=%d, bandwidth=%.1f Mbps, WTP=R$%.0f/mo, revenue=R$%,.0f/mo (%s confidence)",
        population,
        num_households,
        adoption_rate * 100,
        estimated_subscribers,
        total_bandwidth,
        wtp_per_household,
        revenue_monthly,
        confidence,
    )

    return demand
