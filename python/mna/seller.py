"""Seller preparation tool.

Helps ISP owners understand their company's value and prepare for sale.
Generates a comprehensive report with valuations, strengths/weaknesses,
value enhancement opportunities, and a preparation checklist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from python.mna.valuation import subscriber_multiple, revenue_multiple, dcf


@dataclass
class SellerReport:
    """Comprehensive seller preparation report."""

    provider_name: str
    subscriber_count: int
    estimated_value_range: tuple[float, float]
    valuation_methods: dict  # subscriber, revenue, dcf results
    strengths: list[str]
    weaknesses: list[str]
    value_enhancement_opportunities: list[dict]
    preparation_checklist: list[dict]
    estimated_timeline_months: int


def _identify_strengths(
    subscriber_count: int,
    fiber_pct: float,
    ebitda_margin_pct: float,
    growth_rate: float,
    state_codes: list[str],
) -> list[str]:
    """Identify ISP strengths relevant to potential acquirers."""
    strengths: list[str] = []

    if fiber_pct >= 0.80:
        strengths.append(
            f"High fiber penetration ({fiber_pct:.0%}) — premium technology base "
            "commands higher valuation multiples."
        )
    elif fiber_pct >= 0.60:
        strengths.append(
            f"Solid fiber base ({fiber_pct:.0%}) — majority-fiber network is attractive "
            "to acquirers seeking modern infrastructure."
        )

    if ebitda_margin_pct >= 35:
        strengths.append(
            f"Strong profitability (EBITDA margin {ebitda_margin_pct:.1f}%) — "
            "above industry average of 30%, indicating operational efficiency."
        )

    if growth_rate >= 0.10:
        strengths.append(
            f"Strong growth trajectory ({growth_rate:.0%} subscriber growth over 12 months) — "
            "demonstrates market demand and competitive positioning."
        )
    elif growth_rate >= 0.05:
        strengths.append(
            f"Healthy growth ({growth_rate:.0%} over 12 months) — indicates stable "
            "market position with room for expansion."
        )

    if subscriber_count >= 10_000:
        strengths.append(
            f"Scale advantage ({subscriber_count:,} subscribers) — larger base provides "
            "negotiating leverage and operational economies of scale."
        )

    premium_states = {"SP", "RJ", "PR", "SC", "DF"}
    if set(state_codes) & premium_states:
        strengths.append(
            "Presence in premium market(s) — Southeast/South regions have higher "
            "per-subscriber valuations and purchasing power."
        )

    if len(state_codes) >= 2:
        strengths.append(
            f"Multi-state presence ({', '.join(state_codes)}) — geographic diversification "
            "reduces concentration risk."
        )

    return strengths


def _identify_weaknesses(
    subscriber_count: int,
    fiber_pct: float,
    ebitda_margin_pct: float,
    growth_rate: float,
    net_debt_brl: float,
    monthly_revenue: float,
) -> list[str]:
    """Identify ISP weaknesses that may discount valuation."""
    weaknesses: list[str] = []

    if fiber_pct < 0.50:
        weaknesses.append(
            f"Low fiber penetration ({fiber_pct:.0%}) — legacy technology base (DSL/cable) "
            "reduces attractiveness and requires additional CAPEX post-acquisition."
        )

    if ebitda_margin_pct < 25:
        weaknesses.append(
            f"Below-average profitability (EBITDA margin {ebitda_margin_pct:.1f}%) — "
            "may indicate operational inefficiencies or pricing pressure."
        )

    if growth_rate < 0:
        weaknesses.append(
            f"Declining subscriber base ({growth_rate:.0%} over 12 months) — "
            "negative trend significantly discounts valuation."
        )
    elif growth_rate < 0.03:
        weaknesses.append(
            f"Stagnant growth ({growth_rate:.0%} over 12 months) — limited "
            "organic growth potential may concern acquirers."
        )

    if subscriber_count < 3_000:
        weaknesses.append(
            f"Small scale ({subscriber_count:,} subscribers) — may lack operational "
            "efficiencies and limit acquirer interest."
        )

    if net_debt_brl > 0:
        debt_to_revenue = net_debt_brl / (monthly_revenue * 12) if monthly_revenue > 0 else 0
        if debt_to_revenue > 2.0:
            weaknesses.append(
                f"High leverage (net debt {debt_to_revenue:.1f}x revenue) — "
                "excessive debt reduces equity value and may deter acquirers."
            )
        elif debt_to_revenue > 1.0:
            weaknesses.append(
                f"Moderate leverage (net debt {debt_to_revenue:.1f}x revenue) — "
                "debt burden will be factored into offer price."
            )

    return weaknesses


def _value_enhancement_opportunities(
    fiber_pct: float,
    ebitda_margin_pct: float,
    growth_rate: float,
    subscriber_count: int,
    state_codes: list[str],
) -> list[dict]:
    """Suggest actions to increase ISP value before sale."""
    opportunities: list[dict] = []

    if fiber_pct < 0.80:
        impact_pct = min(25, (0.80 - fiber_pct) * 40)
        opportunities.append(
            {
                "action": "Increase fiber penetration",
                "description": (
                    f"Migrate remaining {(1 - fiber_pct):.0%} non-fiber subscribers to FTTH. "
                    "Fiber subscribers command 2-3x higher valuation multiples."
                ),
                "estimated_value_impact_pct": round(impact_pct, 1),
                "timeline_months": 6 if fiber_pct >= 0.50 else 12,
                "difficulty": "medium",
            }
        )

    if ebitda_margin_pct < 30:
        improvement = min(10, 30 - ebitda_margin_pct)
        opportunities.append(
            {
                "action": "Improve EBITDA margins",
                "description": (
                    f"Optimize costs to raise EBITDA margin from {ebitda_margin_pct:.1f}% "
                    f"toward 30%+. Focus on NOC automation, vendor renegotiation, "
                    "and customer self-service tools."
                ),
                "estimated_value_impact_pct": round(improvement * 1.5, 1),
                "timeline_months": 6,
                "difficulty": "medium",
            }
        )

    if growth_rate < 0.08:
        opportunities.append(
            {
                "action": "Accelerate subscriber growth",
                "description": (
                    "Launch targeted marketing campaigns and competitive pricing in "
                    "underserved areas. Growing ISPs attract significantly higher multiples."
                ),
                "estimated_value_impact_pct": 10.0,
                "timeline_months": 6,
                "difficulty": "medium",
            }
        )

    if len(state_codes) == 1:
        opportunities.append(
            {
                "action": "Expand to adjacent municipality or state",
                "description": (
                    "Geographic diversification reduces single-market risk and "
                    "increases strategic attractiveness to acquirers."
                ),
                "estimated_value_impact_pct": 8.0,
                "timeline_months": 9,
                "difficulty": "high",
            }
        )

    if subscriber_count < 5_000:
        opportunities.append(
            {
                "action": "Build subscriber scale",
                "description": (
                    f"At {subscriber_count:,} subscribers, the ISP falls in the small tier. "
                    "Crossing 5,000 subscribers unlocks higher valuation multiples."
                ),
                "estimated_value_impact_pct": 12.0,
                "timeline_months": 12,
                "difficulty": "medium",
            }
        )

    # Always recommend this
    opportunities.append(
        {
            "action": "Clean up financials and documentation",
            "description": (
                "Ensure audited financial statements, clear contracts, and organized "
                "corporate documentation. Acquirers discount unclear records by 10-20%."
            ),
            "estimated_value_impact_pct": 5.0,
            "timeline_months": 3,
            "difficulty": "low",
        }
    )

    return opportunities


def _preparation_checklist() -> list[dict]:
    """Standard M&A preparation checklist for Brazilian ISPs."""
    return [
        {
            "category": "Financial",
            "item": "Prepare audited financial statements (last 3 years)",
            "priority": "critical",
            "typical_duration_weeks": 8,
        },
        {
            "category": "Financial",
            "item": "Document recurring revenue and ARPU trends",
            "priority": "critical",
            "typical_duration_weeks": 2,
        },
        {
            "category": "Financial",
            "item": "Prepare monthly management accounts and KPI dashboard",
            "priority": "high",
            "typical_duration_weeks": 3,
        },
        {
            "category": "Legal",
            "item": "Compile all Anatel licenses and authorizations",
            "priority": "critical",
            "typical_duration_weeks": 2,
        },
        {
            "category": "Legal",
            "item": "Review and organize all supplier contracts",
            "priority": "high",
            "typical_duration_weeks": 4,
        },
        {
            "category": "Legal",
            "item": "Verify compliance with Norma no. 4 (SCM regulation)",
            "priority": "high",
            "typical_duration_weeks": 3,
        },
        {
            "category": "Legal",
            "item": "Check for pending litigation or regulatory proceedings",
            "priority": "critical",
            "typical_duration_weeks": 2,
        },
        {
            "category": "Technology",
            "item": "Document network topology and infrastructure assets",
            "priority": "critical",
            "typical_duration_weeks": 4,
        },
        {
            "category": "Technology",
            "item": "Inventory all network equipment with age and condition",
            "priority": "high",
            "typical_duration_weeks": 3,
        },
        {
            "category": "Technology",
            "item": "Prepare fiber route documentation (GIS/KML files)",
            "priority": "high",
            "typical_duration_weeks": 4,
        },
        {
            "category": "Operations",
            "item": "Document subscriber churn rates and retention programs",
            "priority": "high",
            "typical_duration_weeks": 2,
        },
        {
            "category": "Operations",
            "item": "Prepare organizational chart and key personnel list",
            "priority": "medium",
            "typical_duration_weeks": 1,
        },
        {
            "category": "Operations",
            "item": "Document key customer contracts and SLAs",
            "priority": "medium",
            "typical_duration_weeks": 2,
        },
        {
            "category": "Tax",
            "item": "Verify tax compliance (ISS, ICMS, federal taxes)",
            "priority": "critical",
            "typical_duration_weeks": 4,
        },
        {
            "category": "Tax",
            "item": "Obtain tax clearance certificates (CND/CPEND)",
            "priority": "critical",
            "typical_duration_weeks": 6,
        },
    ]


def prepare_for_sale(
    provider_name: str,
    state_codes: list[str],
    subscriber_count: int,
    fiber_pct: float,
    monthly_revenue_brl: float,
    ebitda_margin_pct: float = 30.0,
    net_debt_brl: float = 0,
) -> SellerReport:
    """Generate comprehensive seller preparation report.

    Parameters
    ----------
    provider_name : str
        Name of the ISP.
    state_codes : list[str]
        Brazilian states where the ISP operates.
    subscriber_count : int
        Total active subscriber count.
    fiber_pct : float
        Fraction of subscribers on fiber (0.0-1.0).
    monthly_revenue_brl : float
        Gross monthly recurring revenue in BRL.
    ebitda_margin_pct : float
        EBITDA margin as percentage.
    net_debt_brl : float
        Net debt (debt minus cash).

    Returns
    -------
    SellerReport
    """
    primary_state = state_codes[0] if state_codes else "SP"

    # Estimate growth rate heuristic (in production, pulled from subscriber history)
    # Use a moderate default
    estimated_growth = 0.07

    # --- Run all three valuation methods ---
    val_sub = subscriber_multiple.calculate(
        total_subscribers=subscriber_count,
        fiber_pct=fiber_pct,
        monthly_churn_pct=2.0,  # default assumption
        growth_rate_12m=estimated_growth,
        state_code=primary_state,
    )

    val_rev = revenue_multiple.calculate(
        monthly_revenue_brl=monthly_revenue_brl,
        ebitda_margin_pct=ebitda_margin_pct,
        subscriber_count=subscriber_count,
        revenue_growth_12m=estimated_growth,
        fiber_pct=fiber_pct,
    )

    val_dcf_result = dcf.calculate(
        monthly_revenue_brl=monthly_revenue_brl,
        ebitda_margin_pct=ebitda_margin_pct,
        net_debt_brl=net_debt_brl,
    )

    # --- Combined valuation range ---
    all_lows = [
        val_sub.valuation_range[0],
        val_rev.valuation_range[0],
        val_dcf_result.equity_value_brl * 0.85,
    ]
    all_highs = [
        val_sub.valuation_range[1],
        val_rev.valuation_range[1],
        val_dcf_result.equity_value_brl * 1.15,
    ]
    combined_low = min(all_lows)
    combined_high = max(all_highs)

    valuation_methods = {
        "subscriber_multiple": {
            "adjusted_valuation_brl": val_sub.adjusted_valuation_brl,
            "range": val_sub.valuation_range,
            "fiber_multiple": val_sub.fiber_multiple,
            "other_multiple": val_sub.other_multiple,
            "confidence": val_sub.confidence,
        },
        "revenue_multiple": {
            "ev_revenue_brl": val_rev.ev_revenue_brl,
            "ev_ebitda_brl": val_rev.ev_ebitda_brl,
            "range": val_rev.valuation_range,
            "revenue_multiple": val_rev.revenue_multiple,
            "ebitda_multiple": val_rev.ebitda_multiple,
        },
        "dcf": {
            "enterprise_value_brl": val_dcf_result.enterprise_value_brl,
            "equity_value_brl": val_dcf_result.equity_value_brl,
            "wacc_pct": val_dcf_result.wacc_pct,
            "terminal_value_brl": val_dcf_result.terminal_value_brl,
        },
    }

    # --- Strengths and weaknesses ---
    strengths = _identify_strengths(
        subscriber_count=subscriber_count,
        fiber_pct=fiber_pct,
        ebitda_margin_pct=ebitda_margin_pct,
        growth_rate=estimated_growth,
        state_codes=state_codes,
    )

    weaknesses = _identify_weaknesses(
        subscriber_count=subscriber_count,
        fiber_pct=fiber_pct,
        ebitda_margin_pct=ebitda_margin_pct,
        growth_rate=estimated_growth,
        net_debt_brl=net_debt_brl,
        monthly_revenue=monthly_revenue_brl,
    )

    # --- Enhancement opportunities ---
    enhancements = _value_enhancement_opportunities(
        fiber_pct=fiber_pct,
        ebitda_margin_pct=ebitda_margin_pct,
        growth_rate=estimated_growth,
        subscriber_count=subscriber_count,
        state_codes=state_codes,
    )

    # --- Preparation checklist ---
    checklist = _preparation_checklist()

    # --- Estimated timeline ---
    # Base timeline: 4-6 months for mid-size ISP, longer for smaller or complex situations
    if subscriber_count >= 10_000:
        timeline = 4
    elif subscriber_count >= 5_000:
        timeline = 5
    else:
        timeline = 6
    if fiber_pct < 0.50:
        timeline += 2  # More prep needed for legacy networks
    if net_debt_brl > monthly_revenue_brl * 24:
        timeline += 1  # Debt restructuring may delay

    return SellerReport(
        provider_name=provider_name,
        subscriber_count=subscriber_count,
        estimated_value_range=(round(combined_low, 2), round(combined_high, 2)),
        valuation_methods=valuation_methods,
        strengths=strengths,
        weaknesses=weaknesses,
        value_enhancement_opportunities=enhancements,
        preparation_checklist=checklist,
        estimated_timeline_months=timeline,
    )
