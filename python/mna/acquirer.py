"""Acquirer dashboard for evaluating ISP acquisition targets.

Scores potential targets based on:
- Strategic fit (geography, technology, market overlap)
- Financial attractiveness (price, margins, growth)
- Integration risk (technology compatibility, customer overlap)
- Synergy potential (cost savings, revenue uplift)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from python.mna.valuation import subscriber_multiple, revenue_multiple, dcf


# ---------------------------------------------------------------------------
# Simulated ISP universe for target discovery
# ---------------------------------------------------------------------------
# In production this would query the read-only database views.
# For now we provide a representative sample for development/testing.

_SAMPLE_TARGETS: list[dict] = [
    {
        "provider_id": 1001,
        "provider_name": "FibraNet Telecom",
        "state_codes": ["SP"],
        "subscriber_count": 12_000,
        "fiber_pct": 0.85,
        "monthly_revenue_brl": 960_000,
        "ebitda_margin_pct": 35.0,
        "growth_rate_12m": 0.12,
        "monthly_churn_pct": 1.5,
    },
    {
        "provider_id": 1002,
        "provider_name": "ConectaMais Internet",
        "state_codes": ["MG"],
        "subscriber_count": 8_500,
        "fiber_pct": 0.65,
        "monthly_revenue_brl": 595_000,
        "ebitda_margin_pct": 30.0,
        "growth_rate_12m": 0.08,
        "monthly_churn_pct": 2.0,
    },
    {
        "provider_id": 1003,
        "provider_name": "Velocidade Internet",
        "state_codes": ["PR", "SC"],
        "subscriber_count": 22_000,
        "fiber_pct": 0.72,
        "monthly_revenue_brl": 1_760_000,
        "ebitda_margin_pct": 32.0,
        "growth_rate_12m": 0.10,
        "monthly_churn_pct": 1.8,
    },
    {
        "provider_id": 1004,
        "provider_name": "Norte Online LTDA",
        "state_codes": ["PA", "AM"],
        "subscriber_count": 5_200,
        "fiber_pct": 0.40,
        "monthly_revenue_brl": 312_000,
        "ebitda_margin_pct": 25.0,
        "growth_rate_12m": 0.15,
        "monthly_churn_pct": 3.0,
    },
    {
        "provider_id": 1005,
        "provider_name": "LinkBR Servicos",
        "state_codes": ["RJ"],
        "subscriber_count": 3_800,
        "fiber_pct": 0.55,
        "monthly_revenue_brl": 266_000,
        "ebitda_margin_pct": 28.0,
        "growth_rate_12m": 0.03,
        "monthly_churn_pct": 2.5,
    },
    {
        "provider_id": 1006,
        "provider_name": "SertaoNet Comunicacoes",
        "state_codes": ["BA", "PE"],
        "subscriber_count": 15_000,
        "fiber_pct": 0.50,
        "monthly_revenue_brl": 975_000,
        "ebitda_margin_pct": 27.0,
        "growth_rate_12m": 0.18,
        "monthly_churn_pct": 2.2,
    },
    {
        "provider_id": 1007,
        "provider_name": "CentroOeste Fibra",
        "state_codes": ["GO", "DF"],
        "subscriber_count": 9_200,
        "fiber_pct": 0.78,
        "monthly_revenue_brl": 736_000,
        "ebitda_margin_pct": 33.0,
        "growth_rate_12m": 0.09,
        "monthly_churn_pct": 1.7,
    },
    {
        "provider_id": 1008,
        "provider_name": "RS Telecom Sul",
        "state_codes": ["RS"],
        "subscriber_count": 6_800,
        "fiber_pct": 0.60,
        "monthly_revenue_brl": 476_000,
        "ebitda_margin_pct": 29.0,
        "growth_rate_12m": 0.04,
        "monthly_churn_pct": 2.3,
    },
    {
        "provider_id": 1009,
        "provider_name": "Planalto Digital",
        "state_codes": ["MT", "MS"],
        "subscriber_count": 4_100,
        "fiber_pct": 0.45,
        "monthly_revenue_brl": 246_000,
        "ebitda_margin_pct": 26.0,
        "growth_rate_12m": 0.06,
        "monthly_churn_pct": 2.8,
    },
    {
        "provider_id": 1010,
        "provider_name": "Mega Fibra ES",
        "state_codes": ["ES"],
        "subscriber_count": 11_500,
        "fiber_pct": 0.88,
        "monthly_revenue_brl": 920_000,
        "ebitda_margin_pct": 36.0,
        "growth_rate_12m": 0.14,
        "monthly_churn_pct": 1.4,
    },
]


@dataclass
class AcquisitionTarget:
    """Scored acquisition target."""

    provider_id: int
    provider_name: str
    state_codes: list[str]
    subscriber_count: int
    fiber_pct: float
    estimated_revenue_brl: float
    valuation_subscriber: float
    valuation_revenue: float
    valuation_dcf: float
    strategic_score: float  # 0-100
    financial_score: float  # 0-100
    integration_risk: str  # low, medium, high
    synergy_estimate_brl: float
    overall_score: float  # 0-100


def _strategic_score(
    target_states: list[str],
    acquirer_states: list[str],
    fiber_pct: float,
    subscriber_count: int,
    growth_rate: float,
) -> float:
    """Score strategic fit (0-100).

    Factors:
    - Geographic adjacency/overlap with acquirer
    - Technology quality (fiber percentage)
    - Scale contribution
    - Growth momentum
    """
    score = 0.0

    # Geographic fit: adjacent or overlapping states score higher
    overlap = set(target_states) & set(acquirer_states)
    if overlap:
        score += 25  # Same-state overlap is very strategic
    else:
        # Check adjacency (simplified)
        score += 10  # Adjacent states get some credit

    # Technology quality
    score += min(30, fiber_pct * 35)

    # Scale contribution (more subs = more impactful)
    if subscriber_count >= 20_000:
        score += 25
    elif subscriber_count >= 10_000:
        score += 20
    elif subscriber_count >= 5_000:
        score += 15
    else:
        score += 10

    # Growth momentum
    if growth_rate >= 0.15:
        score += 20
    elif growth_rate >= 0.10:
        score += 15
    elif growth_rate >= 0.05:
        score += 10
    else:
        score += 5

    return min(100, score)


def _financial_score(
    ebitda_margin_pct: float,
    growth_rate: float,
    monthly_churn_pct: float,
    fiber_pct: float,
) -> float:
    """Score financial attractiveness (0-100).

    Higher margins, growth, retention, and fiber = better score.
    """
    score = 0.0

    # EBITDA margin (max 30 points)
    if ebitda_margin_pct >= 35:
        score += 30
    elif ebitda_margin_pct >= 30:
        score += 25
    elif ebitda_margin_pct >= 25:
        score += 18
    else:
        score += 10

    # Revenue growth (max 25 points)
    if growth_rate >= 0.15:
        score += 25
    elif growth_rate >= 0.10:
        score += 20
    elif growth_rate >= 0.05:
        score += 12
    else:
        score += 5

    # Churn (max 25 points, lower = better)
    if monthly_churn_pct <= 1.5:
        score += 25
    elif monthly_churn_pct <= 2.0:
        score += 20
    elif monthly_churn_pct <= 2.5:
        score += 12
    else:
        score += 5

    # Fiber (max 20 points)
    score += min(20, fiber_pct * 22)

    return min(100, score)


def _integration_risk(
    target_states: list[str],
    acquirer_states: list[str],
    fiber_pct: float,
    subscriber_count: int,
) -> str:
    """Assess integration risk level.

    Lower risk if geographically close, fiber-heavy, and not too large.
    """
    risk_score = 0

    # Geographic distance/overlap
    overlap = set(target_states) & set(acquirer_states)
    if not overlap:
        risk_score += 2
    if len(target_states) > 2:
        risk_score += 1

    # Technology risk (legacy tech harder to integrate)
    if fiber_pct < 0.4:
        risk_score += 2
    elif fiber_pct < 0.6:
        risk_score += 1

    # Scale risk (very large targets harder to integrate)
    if subscriber_count > 30_000:
        risk_score += 2
    elif subscriber_count > 15_000:
        risk_score += 1

    if risk_score >= 4:
        return "high"
    if risk_score >= 2:
        return "medium"
    return "low"


def _estimate_synergies(
    acquirer_subscribers: int,
    target_subscribers: int,
    target_monthly_revenue: float,
    geographic_overlap: bool,
) -> float:
    """Estimate annual synergy value in BRL.

    Synergies from:
    - Opex reduction (shared NOC, billing, support): 5-10% of target revenue
    - Purchasing power (better equipment pricing): 2-5% of combined capex
    - Revenue uplift (cross-sell, reduced churn): 3-5% of target revenue
    """
    annual_revenue = target_monthly_revenue * 12

    # Opex savings (higher if geographic overlap)
    opex_savings_pct = 0.08 if geographic_overlap else 0.05
    opex_synergy = annual_revenue * opex_savings_pct

    # Purchasing leverage scales with combined size
    combined_subs = acquirer_subscribers + target_subscribers
    if combined_subs > 50_000:
        purchase_synergy = annual_revenue * 0.04
    elif combined_subs > 20_000:
        purchase_synergy = annual_revenue * 0.03
    else:
        purchase_synergy = annual_revenue * 0.02

    # Revenue uplift
    revenue_synergy = annual_revenue * 0.04

    return opex_synergy + purchase_synergy + revenue_synergy


def evaluate_targets(
    acquirer_states: list[str],
    acquirer_subscribers: int,
    min_target_subs: int = 1_000,
    max_target_subs: int = 50_000,
) -> list[AcquisitionTarget]:
    """Find and evaluate potential acquisition targets.

    Parameters
    ----------
    acquirer_states : list[str]
        States where the acquirer currently operates.
    acquirer_subscribers : int
        Acquirer's current subscriber count.
    min_target_subs : int
        Minimum target subscriber count filter.
    max_target_subs : int
        Maximum target subscriber count filter.

    Returns
    -------
    list[AcquisitionTarget]
        Targets sorted by overall score (descending).
    """
    targets: list[AcquisitionTarget] = []

    for isp in _SAMPLE_TARGETS:
        subs = isp["subscriber_count"]
        if subs < min_target_subs or subs > max_target_subs:
            continue

        # Run all three valuation methods
        val_sub = subscriber_multiple.calculate(
            total_subscribers=subs,
            fiber_pct=isp["fiber_pct"],
            monthly_churn_pct=isp["monthly_churn_pct"],
            growth_rate_12m=isp["growth_rate_12m"],
            state_code=isp["state_codes"][0],
        )

        val_rev = revenue_multiple.calculate(
            monthly_revenue_brl=isp["monthly_revenue_brl"],
            ebitda_margin_pct=isp["ebitda_margin_pct"],
            subscriber_count=subs,
            revenue_growth_12m=isp["growth_rate_12m"],
            fiber_pct=isp["fiber_pct"],
        )

        val_dcf = dcf.calculate(
            monthly_revenue_brl=isp["monthly_revenue_brl"],
            ebitda_margin_pct=isp["ebitda_margin_pct"],
        )

        # Compute scores
        strat_score = _strategic_score(
            target_states=isp["state_codes"],
            acquirer_states=acquirer_states,
            fiber_pct=isp["fiber_pct"],
            subscriber_count=subs,
            growth_rate=isp["growth_rate_12m"],
        )

        fin_score = _financial_score(
            ebitda_margin_pct=isp["ebitda_margin_pct"],
            growth_rate=isp["growth_rate_12m"],
            monthly_churn_pct=isp["monthly_churn_pct"],
            fiber_pct=isp["fiber_pct"],
        )

        risk = _integration_risk(
            target_states=isp["state_codes"],
            acquirer_states=acquirer_states,
            fiber_pct=isp["fiber_pct"],
            subscriber_count=subs,
        )

        geographic_overlap = bool(set(isp["state_codes"]) & set(acquirer_states))
        synergy = _estimate_synergies(
            acquirer_subscribers=acquirer_subscribers,
            target_subscribers=subs,
            target_monthly_revenue=isp["monthly_revenue_brl"],
            geographic_overlap=geographic_overlap,
        )

        # Overall score: weighted average
        risk_penalty = {"low": 0, "medium": -5, "high": -12}[risk]
        overall = (strat_score * 0.40) + (fin_score * 0.45) + (15 + risk_penalty) * 1.0
        overall = max(0, min(100, overall))

        targets.append(
            AcquisitionTarget(
                provider_id=isp["provider_id"],
                provider_name=isp["provider_name"],
                state_codes=isp["state_codes"],
                subscriber_count=subs,
                fiber_pct=isp["fiber_pct"],
                estimated_revenue_brl=isp["monthly_revenue_brl"] * 12,
                valuation_subscriber=val_sub.adjusted_valuation_brl,
                valuation_revenue=(val_rev.ev_revenue_brl + val_rev.ev_ebitda_brl) / 2,
                valuation_dcf=val_dcf.equity_value_brl,
                strategic_score=round(strat_score, 1),
                financial_score=round(fin_score, 1),
                integration_risk=risk,
                synergy_estimate_brl=round(synergy, 2),
                overall_score=round(overall, 1),
            )
        )

    # Sort by overall score descending
    targets.sort(key=lambda t: t.overall_score, reverse=True)
    return targets


def compute_synergies(acquirer_profile: dict, target_profile: dict) -> dict:
    """Estimate synergy value from combining two ISPs.

    Parameters
    ----------
    acquirer_profile : dict
        Keys: subscriber_count, states, monthly_revenue_brl
    target_profile : dict
        Keys: subscriber_count, states, monthly_revenue_brl, fiber_pct

    Returns
    -------
    dict
        Synergy breakdown with total, opex_savings, purchasing, revenue_uplift.
    """
    acquirer_subs = acquirer_profile.get("subscriber_count", 10_000)
    target_subs = target_profile.get("subscriber_count", 5_000)
    target_revenue = target_profile.get("monthly_revenue_brl", 400_000)
    annual_target_revenue = target_revenue * 12

    acq_states = set(acquirer_profile.get("states", []))
    tgt_states = set(target_profile.get("states", []))
    geographic_overlap = bool(acq_states & tgt_states)

    # Opex savings
    opex_pct = 0.08 if geographic_overlap else 0.05
    opex_savings = annual_target_revenue * opex_pct

    # Purchasing leverage
    combined = acquirer_subs + target_subs
    if combined > 50_000:
        purchase_pct = 0.04
    elif combined > 20_000:
        purchase_pct = 0.03
    else:
        purchase_pct = 0.02
    purchasing_savings = annual_target_revenue * purchase_pct

    # Revenue uplift (cross-sell, churn reduction)
    revenue_uplift = annual_target_revenue * 0.04

    total = opex_savings + purchasing_savings + revenue_uplift

    # Present value of synergies over 5 years (discounted at 14%)
    wacc = 0.14
    pv_synergies = sum(total / ((1 + wacc) ** yr) for yr in range(1, 6))

    return {
        "annual_synergy_brl": round(total, 2),
        "opex_savings_brl": round(opex_savings, 2),
        "purchasing_savings_brl": round(purchasing_savings, 2),
        "revenue_uplift_brl": round(revenue_uplift, 2),
        "pv_5yr_synergies_brl": round(pv_synergies, 2),
        "geographic_overlap": geographic_overlap,
        "combined_subscribers": combined,
    }
