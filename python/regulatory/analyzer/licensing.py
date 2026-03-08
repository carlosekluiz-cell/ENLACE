"""Licensing threshold checker for Brazilian ISPs.

Under SCM regulations (Resolution 614/2013), ISPs are classified by
subscriber count:

    - Below 5,000 subscribers:  Comunicação Prévia (simplified notification)
        - Minimal paperwork, no formal licensing fee
        - Can be done online via Anatel's Mosaico system

    - 5,000 subscribers and above:  Autorização de SCM (formal authorization)
        - Requires formal application to Anatel
        - Technical and financial qualification requirements
        - Annual licensing fee (TFI) based on revenue
        - Periodic renewal obligations
        - Enhanced reporting requirements

The 5,000-subscriber threshold is critical for ISP planning because
crossing it triggers significant compliance and cost obligations.

Sources:
    - Resolution 614/2013 (Regulamento do SCM)
    - Anatel procedural guidelines for SCM authorization
    - Abrint licensing cost estimates
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Licensing thresholds and costs
# ---------------------------------------------------------------------------
LICENSING_THRESHOLD = 5000

# Distance from threshold at which warnings are generated
WARNING_ZONE_PCT = 0.80  # Warn at 80% of threshold (4,000 subs)

# Estimated costs for obtaining Autorização de SCM (BRL)
AUTHORIZATION_COSTS = {
    "application_fee": 9_000,
    "legal_advisory": 15_000,
    "technical_documentation": 10_000,
    "accounting_certification": 5_000,
    "total_estimated_range": {"low": 30_000, "high": 60_000},
}

# Annual Tax on Supervision (TFI - Taxa de Fiscalização de Instalação)
# and TFF (Taxa de Fiscalização de Funcionamento)
# TFF is 33% of the TFI, paid annually
ANNUAL_TFF_BASE = 9_000  # Base TFF for smallest authorized providers
ANNUAL_TFF_REVENUE_FACTOR = 0.005  # 0.5% of gross telecom revenue as TFF cap

# Requirements by tier
REQUIREMENTS_BELOW_THRESHOLD = [
    "File Comunicação Prévia via Anatel Mosaico system",
    "Maintain updated registration data (CNPJ, address, technical contact)",
    "Comply with consumer protection rules (Res. 632)",
    "Submit quality reports if requested by Anatel",
]

REQUIREMENTS_ABOVE_THRESHOLD = [
    "Obtain Autorização de SCM from Anatel",
    "Demonstrate technical qualification (network documentation, topology)",
    "Demonstrate financial qualification (financial statements, tax compliance)",
    "Pay Taxa de Fiscalização de Instalação (TFI)",
    "Pay annual Taxa de Fiscalização de Funcionamento (TFF)",
    "Submit annual financial and technical reports to Anatel",
    "Comply with quality standards (Res. 717) with quarterly reporting",
    "Maintain 24/7 customer support channels",
    "Implement number portability procedures (if applicable)",
    "Participate in Anatel consumer satisfaction surveys",
    "Maintain updated records in STEL and Mosaico systems",
]


@dataclass
class LicensingStatus:
    """Result of a licensing threshold check.

    Attributes:
        subscriber_count: Current number of subscribers.
        threshold: The licensing threshold (5,000).
        above_threshold: Whether the ISP is above the threshold.
        pct_of_threshold: Current subscribers as % of threshold.
        requirements: List of applicable regulatory requirements.
        estimated_licensing_cost_brl: Estimated one-time cost if above threshold.
        estimated_annual_cost_brl: Estimated annual recurring cost if above threshold.
        urgency: 'immediate' (above), 'approaching' (>=80%), or 'safe' (below).
        subscribers_until_threshold: How many more subs until threshold.
        recommendation: Action recommendation for the ISP.
    """
    subscriber_count: int
    threshold: int
    above_threshold: bool
    pct_of_threshold: float
    requirements: list[str] = field(default_factory=list)
    estimated_licensing_cost_brl: float = 0.0
    estimated_annual_cost_brl: float = 0.0
    urgency: str = "safe"
    subscribers_until_threshold: int = 0
    recommendation: str = ""


def check_licensing(
    subscriber_count: int,
    services: Optional[list[str]] = None,
    monthly_revenue_brl: Optional[float] = None,
) -> LicensingStatus:
    """Check if an ISP needs enhanced licensing based on subscriber count.

    Args:
        subscriber_count: Current number of active subscribers.
        services: List of service types offered (e.g. ['SCM', 'broadband']).
            Used to determine if SCM licensing rules apply.
        monthly_revenue_brl: Optional monthly revenue in BRL, used to
            estimate annual TFF cost more accurately.

    Returns:
        LicensingStatus with all licensing details.

    Raises:
        ValueError: If subscriber_count is negative.
    """
    if subscriber_count < 0:
        raise ValueError("Subscriber count cannot be negative.")

    # Check if SCM licensing applies
    scm_applicable = True
    if services:
        scm_services = {"SCM", "scm", "broadband", "fixed_internet"}
        scm_applicable = bool(set(s.lower() for s in services) & {s.lower() for s in scm_services})

    if not scm_applicable:
        logger.info(
            "Services %s do not include SCM — licensing check not applicable",
            services,
        )
        return LicensingStatus(
            subscriber_count=subscriber_count,
            threshold=LICENSING_THRESHOLD,
            above_threshold=False,
            pct_of_threshold=0.0,
            requirements=["SCM licensing not applicable for provided services"],
            urgency="safe",
            subscribers_until_threshold=LICENSING_THRESHOLD,
            recommendation="SCM licensing rules do not apply to your services.",
        )

    pct = (subscriber_count / LICENSING_THRESHOLD) * 100 if LICENSING_THRESHOLD > 0 else 0
    above = subscriber_count >= LICENSING_THRESHOLD
    subs_remaining = max(0, LICENSING_THRESHOLD - subscriber_count)

    # Determine urgency
    if above:
        urgency = "immediate"
    elif pct >= WARNING_ZONE_PCT * 100:
        urgency = "approaching"
    else:
        urgency = "safe"

    # Requirements
    if above:
        requirements = list(REQUIREMENTS_ABOVE_THRESHOLD)
    else:
        requirements = list(REQUIREMENTS_BELOW_THRESHOLD)

    # Cost estimation
    if above:
        licensing_cost_low = AUTHORIZATION_COSTS["total_estimated_range"]["low"]
        licensing_cost_high = AUTHORIZATION_COSTS["total_estimated_range"]["high"]
        licensing_cost = (licensing_cost_low + licensing_cost_high) / 2

        # Annual TFF
        if monthly_revenue_brl and monthly_revenue_brl > 0:
            annual_revenue = monthly_revenue_brl * 12
            tff = min(
                annual_revenue * ANNUAL_TFF_REVENUE_FACTOR,
                max(ANNUAL_TFF_BASE, annual_revenue * ANNUAL_TFF_REVENUE_FACTOR),
            )
            tff = max(ANNUAL_TFF_BASE, tff)
        else:
            tff = ANNUAL_TFF_BASE

        annual_cost = tff
    else:
        licensing_cost = 0.0
        annual_cost = 0.0

    # Recommendation
    if above:
        recommendation = (
            f"IMMEDIATE ACTION: Your {subscriber_count:,} subscribers exceed "
            f"the {LICENSING_THRESHOLD:,} threshold. You must obtain an "
            f"Autorização de SCM from Anatel. Estimated one-time cost: "
            f"R${licensing_cost:,.0f}. Begin the application process immediately."
        )
    elif urgency == "approaching":
        recommendation = (
            f"WARNING: You are at {pct:.0f}% of the {LICENSING_THRESHOLD:,} "
            f"threshold ({subs_remaining:,} subscribers remaining). Begin "
            f"preparing Autorização documentation now to avoid delays when "
            f"you cross the threshold. Budget R${AUTHORIZATION_COSTS['total_estimated_range']['low']:,}-"
            f"R${AUTHORIZATION_COSTS['total_estimated_range']['high']:,} for licensing."
        )
    else:
        recommendation = (
            f"No immediate action needed. You are at {pct:.0f}% of the "
            f"{LICENSING_THRESHOLD:,} threshold with {subs_remaining:,} "
            f"subscribers of headroom. Monitor growth rate and plan ahead."
        )

    status = LicensingStatus(
        subscriber_count=subscriber_count,
        threshold=LICENSING_THRESHOLD,
        above_threshold=above,
        pct_of_threshold=round(pct, 1),
        requirements=requirements,
        estimated_licensing_cost_brl=round(licensing_cost, 2),
        estimated_annual_cost_brl=round(annual_cost, 2),
        urgency=urgency,
        subscribers_until_threshold=subs_remaining,
        recommendation=recommendation,
    )

    logger.info(
        "Licensing check: %d subs (%.0f%% of %d threshold) — %s",
        subscriber_count,
        pct,
        LICENSING_THRESHOLD,
        urgency,
    )
    return status


def estimate_time_to_threshold(
    current_subscribers: int,
    monthly_growth_rate: float,
) -> Optional[int]:
    """Estimate months until the ISP crosses the licensing threshold.

    Args:
        current_subscribers: Current subscriber count.
        monthly_growth_rate: Monthly subscriber growth rate as a decimal
            (e.g. 0.03 for 3% monthly growth).

    Returns:
        Estimated months until threshold is reached, or None if growth
        rate is zero/negative or already above threshold.
    """
    if current_subscribers >= LICENSING_THRESHOLD:
        return 0

    if monthly_growth_rate <= 0:
        return None

    months = 0
    projected = float(current_subscribers)
    # Cap at 120 months (10 years) to avoid infinite loops
    while projected < LICENSING_THRESHOLD and months < 120:
        projected *= (1 + monthly_growth_rate)
        months += 1

    if months >= 120:
        return None

    logger.info(
        "Estimated %d months to reach %d subscribers (from %d at %.1f%% monthly growth)",
        months,
        LICENSING_THRESHOLD,
        current_subscribers,
        monthly_growth_rate * 100,
    )
    return months


def get_licensing_cost_breakdown(monthly_revenue_brl: float = 0.0) -> dict:
    """Get a detailed breakdown of licensing costs.

    Args:
        monthly_revenue_brl: Monthly revenue in BRL for TFF calculation.

    Returns:
        Dictionary with one-time and recurring cost breakdowns.
    """
    annual_revenue = monthly_revenue_brl * 12 if monthly_revenue_brl > 0 else 0

    if annual_revenue > 0:
        tff = max(ANNUAL_TFF_BASE, annual_revenue * ANNUAL_TFF_REVENUE_FACTOR)
    else:
        tff = ANNUAL_TFF_BASE

    return {
        "one_time_costs": {
            "application_fee": AUTHORIZATION_COSTS["application_fee"],
            "legal_advisory": AUTHORIZATION_COSTS["legal_advisory"],
            "technical_documentation": AUTHORIZATION_COSTS["technical_documentation"],
            "accounting_certification": AUTHORIZATION_COSTS["accounting_certification"],
            "total_estimated": {
                "low": AUTHORIZATION_COSTS["total_estimated_range"]["low"],
                "high": AUTHORIZATION_COSTS["total_estimated_range"]["high"],
            },
        },
        "annual_recurring_costs": {
            "tff_base": ANNUAL_TFF_BASE,
            "tff_estimated": round(tff, 2),
            "tff_note": (
                "TFF is the greater of the base amount (R$9,000) or "
                "0.5% of annual gross telecom revenue."
            ),
        },
        "notes": [
            "Costs are estimates based on Abrint member surveys and Anatel published fees.",
            "Legal and accounting costs vary significantly by region and provider.",
            "Anatel may waive or reduce fees for ISPs in underserved areas.",
        ],
    }
