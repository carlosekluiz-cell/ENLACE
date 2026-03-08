"""Norma no. 4 SVA-to-SCM tax impact calculator.

Calculates the financial impact of broadband reclassification from SVA
(Servico de Valor Adicionado) to SCM (Servico de Comunicacao Multimidia)
for a given ISP, including:

    - Additional ICMS tax burden per state
    - Annual and monthly cost projections
    - Restructuring options with scored recommendations
    - Readiness assessment and countdown to deadline

The core calculation:
    Under SVA, broadband revenue was exempt from ICMS in most states.
    Under SCM (Norma no. 4), ICMS at the state telecom rate applies to
    gross broadband revenue.  For an ISP in Sao Paulo with R$267k
    monthly revenue, that is 25% x R$267,000 = R$66,750/month or
    R$801,000/year in additional taxation.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from python.regulatory.knowledge_base.deadlines import days_until
from python.regulatory.knowledge_base.tax_rates import (
    ICMS_RATES_SCM,
    get_telecom_icms,
    compute_blended_rate,
)

logger = logging.getLogger(__name__)

# The Norma no. 4 final compliance deadline
NORMA4_DEADLINE = date(2027, 1, 1)

# Typical ARPU (Average Revenue Per User) for Brazilian broadband
DEFAULT_ARPU_BRL = 89.0

# Churn sensitivity: estimated % subscriber loss per 1% price increase
CHURN_SENSITIVITY = 0.015  # 1.5% churn per 1% price increase

# Readiness scoring weights
_READINESS_WEIGHTS = {
    "days_factor": 0.30,        # More time = higher score
    "classification_factor": 0.25,  # Already SCM = big boost
    "size_factor": 0.20,       # Smaller ISPs adapt faster
    "revenue_factor": 0.25,    # Lower tax burden = easier transition
}


@dataclass
class Norma4Impact:
    """Result of a Norma no. 4 impact calculation.

    Attributes:
        state_code: Brazilian UF code where the ISP operates.
        icms_rate: Telecom ICMS rate for the state.
        monthly_revenue_brl: ISP's monthly broadband revenue.
        additional_monthly_tax_brl: New monthly ICMS tax amount.
        additional_annual_tax_brl: Annualized ICMS tax amount.
        pct_of_revenue: Tax as a percentage of revenue.
        subscriber_count: Number of broadband subscribers.
        arpu_brl: Average Revenue Per User (monthly).
        restructuring_options: Scored restructuring strategies.
        recommended_action: The top recommended strategy.
        days_until_deadline: Days remaining to NORMA4_DEADLINE.
        readiness_score: Overall readiness score (0-100).
    """
    state_code: str
    icms_rate: float
    monthly_revenue_brl: float
    additional_monthly_tax_brl: float
    additional_annual_tax_brl: float
    pct_of_revenue: float
    subscriber_count: int
    arpu_brl: float
    restructuring_options: list[dict] = field(default_factory=list)
    recommended_action: str = ""
    days_until_deadline: int = 0
    readiness_score: float = 0.0


def calculate_impact(
    state_code: str,
    monthly_broadband_revenue_brl: float,
    subscriber_count: int,
    current_classification: str = "SVA",
    arpu_brl: Optional[float] = None,
) -> Norma4Impact:
    """Calculate the Norma no. 4 tax impact for an ISP.

    Args:
        state_code: Two-letter UF code (e.g. 'SP', 'GO', 'BA').
        monthly_broadband_revenue_brl: Total monthly broadband revenue in BRL.
        subscriber_count: Number of active broadband subscribers.
        current_classification: Current service classification ('SVA' or 'SCM').
        arpu_brl: Override average revenue per user. If None, computed from
            revenue / subscribers.

    Returns:
        Norma4Impact with all calculated fields populated.

    Raises:
        ValueError: If state_code is invalid or revenue/subscribers are negative.

    Example:
        >>> impact = calculate_impact("SP", 267_000, 3000)
        >>> impact.additional_monthly_tax_brl  # 25% of R$267k = R$66,750
        66750.0
    """
    # Input validation
    code = state_code.strip().upper()
    if code not in ICMS_RATES_SCM:
        raise ValueError(
            f"Unknown state code '{state_code}'. Must be a valid Brazilian UF."
        )
    if monthly_broadband_revenue_brl < 0:
        raise ValueError("Monthly revenue cannot be negative.")
    if subscriber_count < 0:
        raise ValueError("Subscriber count cannot be negative.")

    # Handle zero-revenue / zero-subscriber edge cases
    if monthly_broadband_revenue_brl == 0 or subscriber_count == 0:
        logger.warning(
            "Zero revenue or subscribers for %s — returning zero impact", code
        )
        return Norma4Impact(
            state_code=code,
            icms_rate=get_telecom_icms(code),
            monthly_revenue_brl=0.0,
            additional_monthly_tax_brl=0.0,
            additional_annual_tax_brl=0.0,
            pct_of_revenue=0.0,
            subscriber_count=0,
            arpu_brl=0.0,
            restructuring_options=[],
            recommended_action="No action needed — zero revenue",
            days_until_deadline=days_until(NORMA4_DEADLINE),
            readiness_score=100.0,
        )

    # Core calculation
    icms_rate = get_telecom_icms(code)

    if current_classification.upper() == "SCM":
        # Already classified as SCM — ICMS already applies
        additional_monthly = 0.0
        logger.info(
            "ISP in %s already classified as SCM; no additional ICMS impact",
            code,
        )
    else:
        # SVA -> SCM transition: full ICMS rate is the new burden
        additional_monthly = monthly_broadband_revenue_brl * icms_rate

    additional_annual = additional_monthly * 12
    pct_of_revenue = (
        (additional_monthly / monthly_broadband_revenue_brl) * 100
        if monthly_broadband_revenue_brl > 0
        else 0.0
    )

    # Compute or use provided ARPU
    computed_arpu = arpu_brl
    if computed_arpu is None:
        computed_arpu = (
            monthly_broadband_revenue_brl / subscriber_count
            if subscriber_count > 0
            else DEFAULT_ARPU_BRL
        )

    remaining_days = days_until(NORMA4_DEADLINE)

    impact = Norma4Impact(
        state_code=code,
        icms_rate=icms_rate,
        monthly_revenue_brl=monthly_broadband_revenue_brl,
        additional_monthly_tax_brl=round(additional_monthly, 2),
        additional_annual_tax_brl=round(additional_annual, 2),
        pct_of_revenue=round(pct_of_revenue, 2),
        subscriber_count=subscriber_count,
        arpu_brl=round(computed_arpu, 2),
        days_until_deadline=remaining_days,
    )

    # Score restructuring options
    impact.restructuring_options = score_restructuring_options(impact)

    # Pick recommended action: the option with the highest score
    if impact.restructuring_options:
        best = max(impact.restructuring_options, key=lambda o: o["score"])
        impact.recommended_action = best["strategy"]
    else:
        impact.recommended_action = "Review options with financial advisor"

    # Compute readiness
    impact.readiness_score = _compute_readiness_score(
        impact, current_classification
    )

    logger.info(
        "Norma4 impact for %s: R$%.2f/month additional ICMS (%.1f%% of revenue), "
        "readiness=%.1f, recommended=%s",
        code,
        impact.additional_monthly_tax_brl,
        impact.pct_of_revenue,
        impact.readiness_score,
        impact.recommended_action,
    )
    return impact


def calculate_multi_state_impact(
    state_revenues: dict[str, float],
    subscriber_count: int,
    current_classification: str = "SVA",
) -> dict:
    """Calculate combined Norma no. 4 impact across multiple states.

    Args:
        state_revenues: Dict mapping state code to monthly revenue in BRL.
        subscriber_count: Total subscriber count across all states.
        current_classification: Current classification ('SVA' or 'SCM').

    Returns:
        Dictionary with per-state impacts and aggregate totals.
    """
    per_state = {}
    total_monthly_tax = 0.0
    total_revenue = 0.0

    for code, revenue in state_revenues.items():
        # Approximate subscriber distribution proportional to revenue
        total_rev_sum = sum(state_revenues.values())
        if total_rev_sum > 0:
            state_subs = int(subscriber_count * (revenue / total_rev_sum))
        else:
            state_subs = 0

        impact = calculate_impact(
            code, revenue, state_subs, current_classification
        )
        per_state[code] = impact
        total_monthly_tax += impact.additional_monthly_tax_brl
        total_revenue += revenue

    blended_rate = compute_blended_rate(state_revenues)

    result = {
        "per_state": per_state,
        "total_monthly_tax_brl": round(total_monthly_tax, 2),
        "total_annual_tax_brl": round(total_monthly_tax * 12, 2),
        "total_monthly_revenue_brl": round(total_revenue, 2),
        "blended_icms_rate": blended_rate,
        "effective_pct_of_revenue": (
            round((total_monthly_tax / total_revenue) * 100, 2)
            if total_revenue > 0
            else 0.0
        ),
        "days_until_deadline": days_until(NORMA4_DEADLINE),
    }

    logger.info(
        "Multi-state Norma4 impact: %d states, R$%.2f/month total ICMS",
        len(state_revenues),
        total_monthly_tax,
    )
    return result


def score_restructuring_options(impact: Norma4Impact) -> list[dict]:
    """Score restructuring options for handling the ICMS tax impact.

    Evaluates four strategies:
        a) Absorb cost — reduce margin, no price increase
        b) Pass to customer — raise prices, accept some churn
        c) Corporate restructure — separate infra from service entity
        d) Negotiate state relief — seek transition tax incentives

    Args:
        impact: The calculated Norma4Impact for the ISP.

    Returns:
        List of dicts, each with:
            - strategy: Strategy name
            - description: What the strategy entails
            - score: Suitability score (0-100, higher = better fit)
            - pros: List of advantages
            - cons: List of disadvantages
            - estimated_monthly_savings_brl: Estimated tax savings
            - implementation_months: Estimated time to implement
    """
    options = []

    monthly_tax = impact.additional_monthly_tax_brl
    revenue = impact.monthly_revenue_brl
    subs = impact.subscriber_count
    rate = impact.icms_rate

    # If there is no additional tax (already SCM), all options score high
    if monthly_tax <= 0:
        return [{
            "strategy": "No restructuring needed",
            "description": "ISP is already classified as SCM; no additional ICMS burden.",
            "score": 100.0,
            "pros": ["No action required"],
            "cons": [],
            "estimated_monthly_savings_brl": 0.0,
            "implementation_months": 0,
        }]

    # --- Option A: Absorb cost ---
    # Feasibility depends on current margin
    # Assume typical ISP gross margin of ~40%
    estimated_margin_pct = 0.40
    margin_brl = revenue * estimated_margin_pct
    absorb_pct_of_margin = (monthly_tax / margin_brl * 100) if margin_brl > 0 else 100
    # If tax eats > 50% of margin, score drops sharply
    absorb_score = max(0, 100 - absorb_pct_of_margin * 1.5)

    options.append({
        "strategy": "Absorver o custo (absorb cost)",
        "description": (
            f"Absorb the R${monthly_tax:,.2f}/month ICMS tax internally, "
            f"reducing gross margin by approximately {absorb_pct_of_margin:.1f}%. "
            f"No price change for customers."
        ),
        "score": round(max(0, min(100, absorb_score)), 1),
        "pros": [
            "No customer impact — zero churn risk",
            "Simple to implement (no contract changes)",
            "Competitive advantage if competitors raise prices",
        ],
        "cons": [
            f"Reduces gross margin by ~{absorb_pct_of_margin:.1f}%",
            "Not sustainable long-term if margins are thin",
            "May require cost cuts elsewhere in the business",
        ],
        "estimated_monthly_savings_brl": 0.0,
        "implementation_months": 1,
    })

    # --- Option B: Pass to customer ---
    # Raise ARPU by the tax amount per subscriber
    tax_per_sub = monthly_tax / subs if subs > 0 else 0
    price_increase_pct = (tax_per_sub / impact.arpu_brl * 100) if impact.arpu_brl > 0 else 0
    estimated_churn_pct = price_increase_pct * CHURN_SENSITIVITY * 100
    estimated_lost_subs = int(subs * estimated_churn_pct / 100)
    # Net revenue after churn
    remaining_subs = max(0, subs - estimated_lost_subs)
    new_arpu = impact.arpu_brl + tax_per_sub
    new_revenue = remaining_subs * new_arpu
    revenue_change = new_revenue - revenue

    # Score: good if price increase is small, bad if > 20%
    passthrough_score = max(0, 100 - price_increase_pct * 3)

    options.append({
        "strategy": "Repassar ao cliente (pass to customer)",
        "description": (
            f"Increase customer prices by R${tax_per_sub:,.2f}/month "
            f"(+{price_increase_pct:.1f}%). Estimated churn: "
            f"{estimated_churn_pct:.1f}% ({estimated_lost_subs:,} subscribers)."
        ),
        "score": round(max(0, min(100, passthrough_score)), 1),
        "pros": [
            "Fully offsets ICMS cost",
            "Preserves margin percentages",
            "Industry-wide price increase expected (competitive equilibrium)",
        ],
        "cons": [
            f"Estimated {estimated_churn_pct:.1f}% subscriber churn",
            f"~{estimated_lost_subs:,} lost subscribers",
            "Customer dissatisfaction and Anatel complaints risk",
            "Competitors who absorb costs gain market share",
        ],
        "estimated_monthly_savings_brl": round(monthly_tax, 2),
        "implementation_months": 2,
    })

    # --- Option C: Corporate restructure ---
    # Separate infrastructure (SCM) from value-added services (SVA)
    # Can reduce the taxable base by separating non-communication revenue
    # Typically saves 30-40% of the ICMS burden through legitimate structuring
    restructure_savings_pct = 0.35
    restructure_savings = monthly_tax * restructure_savings_pct
    # Score: good for larger ISPs (cost of restructuring is fixed)
    restructure_base_score = 60
    if subs >= 5000:
        restructure_base_score += 20
    if subs >= 10000:
        restructure_base_score += 10
    if subs < 1000:
        restructure_base_score -= 30  # Too small to justify the overhead

    options.append({
        "strategy": "Reestruturação societária (corporate restructure)",
        "description": (
            "Separate the infrastructure company (SCM licensee) from the "
            "value-added services entity (SVA). The SVA entity provides "
            "content, support, and application services not subject to ICMS. "
            f"Estimated savings: R${restructure_savings:,.2f}/month "
            f"(~{restructure_savings_pct:.0%} of ICMS burden)."
        ),
        "score": round(max(0, min(100, restructure_base_score)), 1),
        "pros": [
            f"~{restructure_savings_pct:.0%} reduction in ICMS burden",
            "Legally established mechanism (used by major telcos)",
            "Creates clearer business unit separation",
            "SVA entity can offer exempt services",
        ],
        "cons": [
            "Significant legal and accounting costs (R$50k-200k setup)",
            "Increased administrative complexity (two CNPJ entities)",
            "Tax authority scrutiny risk (simulação / abuso de forma)",
            "Takes 6-12 months to implement properly",
            "Not suitable for very small ISPs (< 1,000 subscribers)",
        ],
        "estimated_monthly_savings_brl": round(restructure_savings, 2),
        "implementation_months": 9,
    })

    # --- Option D: Negotiate state relief ---
    # Some states offer transition incentives or reduced rates for small ISPs
    # Effectiveness varies widely by state
    state_has_incentives = impact.state_code in ("SP", "MG", "PR", "SC", "RS", "GO")
    negotiate_savings_pct = 0.15 if state_has_incentives else 0.05
    negotiate_savings = monthly_tax * negotiate_savings_pct
    negotiate_score = 40
    if state_has_incentives:
        negotiate_score += 25
    if subs < 5000:
        negotiate_score += 10  # Small ISPs get more sympathy

    options.append({
        "strategy": "Negociar incentivo estadual (negotiate state relief)",
        "description": (
            "Negotiate with the state tax authority (SEFAZ) for transition "
            "incentives, reduced rates, or phase-in periods. Some states offer "
            "programs for small ISPs or companies bringing connectivity to "
            "underserved areas. "
            f"{'State has known incentive programs.' if state_has_incentives else 'No known incentive programs in this state.'}"
        ),
        "score": round(max(0, min(100, negotiate_score)), 1),
        "pros": [
            "Can reduce effective ICMS rate by 5-20%",
            "Some states offer multi-year phase-in periods",
            "ISPs serving underserved areas may qualify for special programs",
            "Industry association (Abrint) lobbying support available",
        ],
        "cons": [
            "Uncertain outcome — depends on state politics",
            "Time-consuming negotiation process (3-6 months)",
            "May require commitments (coverage expansion, employment)",
            "Incentives may expire, creating future exposure",
        ],
        "estimated_monthly_savings_brl": round(negotiate_savings, 2),
        "implementation_months": 5,
    })

    # Sort by score descending
    options.sort(key=lambda o: o["score"], reverse=True)

    logger.debug(
        "Scored %d restructuring options. Best: %s (%.1f)",
        len(options),
        options[0]["strategy"],
        options[0]["score"],
    )
    return options


def _compute_readiness_score(
    impact: Norma4Impact,
    current_classification: str,
) -> float:
    """Compute an overall readiness score (0-100) for Norma no. 4 compliance.

    Higher score = better prepared for the transition.

    Factors:
        - Time remaining until deadline (more time = higher score)
        - Current classification (already SCM = much higher score)
        - ISP size (smaller ISPs adapt faster)
        - Revenue exposure (lower tax burden relative to revenue = easier)

    Args:
        impact: The calculated Norma4Impact.
        current_classification: 'SVA' or 'SCM'.

    Returns:
        Readiness score from 0 to 100.
    """
    # --- Days factor: more time = higher readiness ---
    remaining = impact.days_until_deadline
    if remaining <= 0:
        days_score = 0.0  # Deadline has passed
    elif remaining >= 730:
        days_score = 100.0  # > 2 years: plenty of time
    elif remaining >= 365:
        days_score = 50.0 + (remaining - 365) / 365 * 50
    elif remaining >= 180:
        days_score = 20.0 + (remaining - 180) / 185 * 30
    else:
        days_score = max(0, remaining / 180 * 20)

    # --- Classification factor ---
    if current_classification.upper() == "SCM":
        classification_score = 100.0  # Already compliant
    else:
        classification_score = 10.0  # SVA: significant work ahead

    # --- Size factor: smaller ISPs adapt faster ---
    subs = impact.subscriber_count
    if subs <= 1000:
        size_score = 80.0
    elif subs <= 5000:
        size_score = 60.0
    elif subs <= 20000:
        size_score = 40.0
    else:
        size_score = 20.0  # Large ISPs have more complex transitions

    # --- Revenue exposure factor ---
    pct = impact.pct_of_revenue
    if pct <= 0:
        revenue_score = 100.0
    elif pct <= 15:
        revenue_score = 80.0
    elif pct <= 25:
        revenue_score = 50.0
    else:
        revenue_score = max(0, 30 - (pct - 25))

    # Weighted combination
    readiness = (
        days_score * _READINESS_WEIGHTS["days_factor"]
        + classification_score * _READINESS_WEIGHTS["classification_factor"]
        + size_score * _READINESS_WEIGHTS["size_factor"]
        + revenue_score * _READINESS_WEIGHTS["revenue_factor"]
    )

    return round(max(0.0, min(100.0, readiness)), 1)


def estimate_price_increase(
    state_code: str,
    current_arpu_brl: float,
    passthrough_pct: float = 1.0,
) -> dict:
    """Estimate the customer price increase needed to offset ICMS.

    Args:
        state_code: Two-letter UF code.
        current_arpu_brl: Current average revenue per user in BRL.
        passthrough_pct: Fraction of the tax to pass through (0.0 to 1.0).

    Returns:
        Dictionary with pricing projections.
    """
    if current_arpu_brl <= 0:
        return {
            "current_arpu_brl": 0.0,
            "new_arpu_brl": 0.0,
            "increase_brl": 0.0,
            "increase_pct": 0.0,
            "estimated_churn_pct": 0.0,
        }

    rate = get_telecom_icms(state_code)
    tax_per_sub = current_arpu_brl * rate
    passthrough_amount = tax_per_sub * passthrough_pct
    new_arpu = current_arpu_brl + passthrough_amount
    increase_pct = (passthrough_amount / current_arpu_brl) * 100
    estimated_churn = increase_pct * CHURN_SENSITIVITY * 100

    return {
        "state_code": state_code,
        "icms_rate": rate,
        "current_arpu_brl": round(current_arpu_brl, 2),
        "new_arpu_brl": round(new_arpu, 2),
        "increase_brl": round(passthrough_amount, 2),
        "increase_pct": round(increase_pct, 2),
        "estimated_churn_pct": round(estimated_churn, 2),
        "passthrough_pct": passthrough_pct,
    }
