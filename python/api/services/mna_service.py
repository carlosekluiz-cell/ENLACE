"""
ENLACE M&A Intelligence Service

Advanced M&A analytics: comparable transaction analysis, synergy modeling,
due diligence checklists, and integration timeline estimation.  All queries
use the async SQLAlchemy session and real Anatel/IBGE data.
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brazilian ISP market constants (based on real transaction data 2022-2025)
# ---------------------------------------------------------------------------

# EV/subscriber multiples by fiber penetration tier
_FIBER_TIER_MULTIPLES = {
    "high":   {"low": 2_200, "mid": 2_800, "high": 3_500},   # >=70% fiber
    "medium": {"low": 1_500, "mid": 2_000, "high": 2_500},   # 30-69% fiber
    "low":    {"low":   800, "mid": 1_200, "high": 1_600},   # <30% fiber
}

# Regional premium factors (South/Southeast command higher multiples)
_REGION_PREMIUMS: dict[str, float] = {
    "SP": 1.20, "RJ": 1.10, "MG": 1.08, "PR": 1.12, "SC": 1.15,
    "RS": 1.10, "ES": 1.05, "DF": 1.15,
    "GO": 1.00, "MT": 0.95, "MS": 0.95,
    "BA": 0.90, "PE": 0.90, "CE": 0.88,
}

# Estimated monthly ARPU by technology mix
_ARPU_FIBER = 95.0   # R$/month
_ARPU_OTHER = 65.0   # R$/month (cable/DSL/FWA)

# Synergy assumptions
_COST_SYNERGY_PCT = 0.15          # 15% opex overlap elimination
_REVENUE_SYNERGY_PCT = 0.05       # 5% ARPU uplift from cross-sell
_INFRA_SHARING_DISCOUNT = 0.10    # 10% capex savings from shared infra
_CHURN_REDUCTION_PCT = 0.02       # 2pp churn improvement post-integration


# ═══════════════════════════════════════════════════════════════════════════════
# Comparable Transaction Analysis
# ═══════════════════════════════════════════════════════════════════════════════


async def comparable_analysis(
    db: AsyncSession,
    provider_id: int,
    subscriber_range: Optional[tuple[int, int]] = None,
    fiber_range: Optional[tuple[float, float]] = None,
    states: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Find ISPs comparable to the target and compute transaction multiples.

    Queries ``broadband_subscribers`` for the latest month to find providers
    with similar subscriber count, fiber penetration, and geographic presence.
    Computes implied EV/subscriber and EV/revenue multiples for each comp.

    Args:
        db: Async SQLAlchemy session.
        provider_id: The target provider's ``providers.id``.
        subscriber_range: Optional (min, max) subscriber filter.
        fiber_range: Optional (min_pct, max_pct) fiber penetration filter.
        states: Optional list of state abbreviations to restrict comps.

    Returns:
        Dictionary with target profile, comparable ISPs, and implied multiples.
    """
    # ---- Step 1: build the target profile ----
    target_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        target_agg AS (
            SELECT
                bs.provider_id,
                p.name AS provider_name,
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subs,
                array_agg(DISTINCT l1.abbrev) AS state_codes
            FROM broadband_subscribers bs
            JOIN providers p ON bs.provider_id = p.id
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            JOIN admin_level_1 l1 ON a2.l1_id = l1.id
            CROSS JOIN latest
            WHERE bs.provider_id = :pid
              AND bs.year_month = latest.ym
            GROUP BY bs.provider_id, p.name
        )
        SELECT * FROM target_agg
    """)

    result = await db.execute(target_sql, {"pid": provider_id})
    target_row = result.fetchone()

    if not target_row or not target_row.total_subs:
        return {
            "error": "Provider not found or has no subscriber data",
            "provider_id": provider_id,
        }

    target_subs = int(target_row.total_subs)
    target_fiber_pct = round(
        int(target_row.fiber_subs) / max(target_subs, 1) * 100, 1
    )
    target_states = list(target_row.state_codes) if target_row.state_codes else []

    # Determine default comparable ranges (0.25x to 4x subscriber count)
    if subscriber_range:
        sub_lo, sub_hi = subscriber_range
    else:
        sub_lo = max(100, int(target_subs * 0.25))
        sub_hi = int(target_subs * 4.0)

    # ---- Step 2: find comparable ISPs ----
    where_parts = [
        "bs.provider_id != :pid",
        "bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)",
    ]
    params: dict[str, Any] = {"pid": provider_id}

    if states:
        where_parts.append("l1.abbrev = ANY(:states)")
        params["states"] = [s.upper() for s in states]
    elif target_states:
        # Default: same states as target
        where_parts.append("l1.abbrev = ANY(:states)")
        params["states"] = target_states

    where_sql = " AND ".join(where_parts)

    comps_sql = text(f"""
        WITH comp_agg AS (
            SELECT
                bs.provider_id,
                p.name AS provider_name,
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subs,
                array_agg(DISTINCT l1.abbrev) AS state_codes,
                COUNT(DISTINCT a2.id) AS municipality_count
            FROM broadband_subscribers bs
            JOIN providers p ON bs.provider_id = p.id
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            JOIN admin_level_1 l1 ON a2.l1_id = l1.id
            WHERE {where_sql}
            GROUP BY bs.provider_id, p.name
            HAVING SUM(bs.subscribers) BETWEEN :sub_lo AND :sub_hi
        )
        SELECT * FROM comp_agg
        ORDER BY total_subs DESC
        LIMIT 20
    """)

    params["sub_lo"] = sub_lo
    params["sub_hi"] = sub_hi

    result = await db.execute(comps_sql, params)
    comp_rows = result.fetchall()

    # ---- Step 3: compute multiples for each comp ----
    comparables: list[dict[str, Any]] = []

    for row in comp_rows:
        subs = int(row.total_subs)
        fiber_pct = round(int(row.fiber_subs) / max(subs, 1) * 100, 1)

        # Apply fiber range filter if specified
        if fiber_range:
            if fiber_pct < fiber_range[0] or fiber_pct > fiber_range[1]:
                continue

        # Estimate monthly revenue
        fiber_s = int(row.fiber_subs)
        other_s = subs - fiber_s
        est_monthly_revenue = (fiber_s * _ARPU_FIBER) + (other_s * _ARPU_OTHER)
        est_annual_revenue = est_monthly_revenue * 12

        # Determine fiber tier
        if fiber_pct >= 70:
            tier = "high"
        elif fiber_pct >= 30:
            tier = "medium"
        else:
            tier = "low"

        multiples = _FIBER_TIER_MULTIPLES[tier]

        # Regional premium based on primary state
        comp_states = list(row.state_codes) if row.state_codes else []
        primary_state = comp_states[0] if comp_states else "SP"
        premium = _REGION_PREMIUMS.get(primary_state, 0.95)

        ev_per_sub = round(multiples["mid"] * premium, 0)
        implied_ev = round(subs * ev_per_sub, 2)
        ev_revenue = round(implied_ev / max(est_annual_revenue, 1), 2)

        comparables.append({
            "provider_id": row.provider_id,
            "provider_name": row.provider_name,
            "subscribers": subs,
            "fiber_pct": fiber_pct,
            "state_codes": comp_states,
            "municipality_count": row.municipality_count,
            "estimated_annual_revenue_brl": round(est_annual_revenue, 2),
            "implied_ev_brl": implied_ev,
            "ev_per_subscriber": ev_per_sub,
            "ev_revenue_multiple": ev_revenue,
            "fiber_tier": tier,
            "regional_premium": premium,
        })

    # ---- Step 4: aggregate market multiples ----
    if comparables:
        ev_per_sub_values = [c["ev_per_subscriber"] for c in comparables]
        ev_rev_values = [c["ev_revenue_multiple"] for c in comparables]

        market_multiples = {
            "ev_per_subscriber": {
                "min": min(ev_per_sub_values),
                "median": round(sorted(ev_per_sub_values)[len(ev_per_sub_values) // 2], 0),
                "max": max(ev_per_sub_values),
                "mean": round(sum(ev_per_sub_values) / len(ev_per_sub_values), 0),
            },
            "ev_revenue": {
                "min": min(ev_rev_values),
                "median": round(sorted(ev_rev_values)[len(ev_rev_values) // 2], 2),
                "max": max(ev_rev_values),
                "mean": round(sum(ev_rev_values) / len(ev_rev_values), 2),
            },
        }

        # Apply median multiple to the target
        target_fiber_s = int(target_row.fiber_subs)
        target_other_s = target_subs - target_fiber_s
        target_monthly_rev = (target_fiber_s * _ARPU_FIBER) + (target_other_s * _ARPU_OTHER)
        target_annual_rev = target_monthly_rev * 12

        target_implied_ev = round(
            target_subs * market_multiples["ev_per_subscriber"]["median"], 2
        )
    else:
        market_multiples = None
        target_annual_rev = 0
        target_implied_ev = 0

    return {
        "target": {
            "provider_id": provider_id,
            "provider_name": target_row.provider_name,
            "subscribers": target_subs,
            "fiber_pct": target_fiber_pct,
            "state_codes": target_states,
            "estimated_annual_revenue_brl": round(target_annual_rev, 2),
            "implied_ev_brl": target_implied_ev,
        },
        "comparables": comparables,
        "comparable_count": len(comparables),
        "market_multiples": market_multiples,
        "filters_applied": {
            "subscriber_range": [sub_lo, sub_hi],
            "fiber_range": list(fiber_range) if fiber_range else None,
            "states": states or target_states,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Synergy Model
# ═══════════════════════════════════════════════════════════════════════════════


async def synergy_model(
    db: AsyncSession,
    acquirer_id: int,
    target_id: int,
) -> dict[str, Any]:
    """Estimate revenue, cost, and market synergies for an acquisition.

    Analyses geographic overlap, subscriber mix, and infrastructure
    complementarity between acquirer and target.

    Args:
        db: Async SQLAlchemy session.
        acquirer_id: The acquiring provider's ``providers.id``.
        target_id: The target provider's ``providers.id``.

    Returns:
        Dictionary with synergy breakdown and combined entity projections.
    """
    # ---- Fetch both provider profiles ----
    profile_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        provider_agg AS (
            SELECT
                bs.provider_id,
                p.name AS provider_name,
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subs,
                array_agg(DISTINCT l1.abbrev) AS state_codes,
                array_agg(DISTINCT a2.id) AS municipality_ids,
                COUNT(DISTINCT a2.id) AS municipality_count
            FROM broadband_subscribers bs
            JOIN providers p ON bs.provider_id = p.id
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            JOIN admin_level_1 l1 ON a2.l1_id = l1.id
            CROSS JOIN latest
            WHERE bs.provider_id = :pid
              AND bs.year_month = latest.ym
            GROUP BY bs.provider_id, p.name
        )
        SELECT * FROM provider_agg
    """)

    acq_result = await db.execute(profile_sql, {"pid": acquirer_id})
    acq = acq_result.fetchone()

    tgt_result = await db.execute(profile_sql, {"pid": target_id})
    tgt = tgt_result.fetchone()

    if not acq or not acq.total_subs:
        return {"error": "Acquirer provider not found or has no subscriber data"}
    if not tgt or not tgt.total_subs:
        return {"error": "Target provider not found or has no subscriber data"}

    acq_subs = int(acq.total_subs)
    tgt_subs = int(tgt.total_subs)
    acq_fiber_pct = round(int(acq.fiber_subs) / max(acq_subs, 1) * 100, 1)
    tgt_fiber_pct = round(int(tgt.fiber_subs) / max(tgt_subs, 1) * 100, 1)

    acq_munis = set(acq.municipality_ids) if acq.municipality_ids else set()
    tgt_munis = set(tgt.municipality_ids) if tgt.municipality_ids else set()
    overlap_munis = acq_munis & tgt_munis
    new_munis = tgt_munis - acq_munis

    # ---- Revenue estimates ----
    acq_fiber_s = int(acq.fiber_subs)
    tgt_fiber_s = int(tgt.fiber_subs)
    acq_monthly_rev = (acq_fiber_s * _ARPU_FIBER) + ((acq_subs - acq_fiber_s) * _ARPU_OTHER)
    tgt_monthly_rev = (tgt_fiber_s * _ARPU_FIBER) + ((tgt_subs - tgt_fiber_s) * _ARPU_OTHER)
    combined_monthly_rev = acq_monthly_rev + tgt_monthly_rev

    # ---- Revenue synergies ----
    # 1. ARPU uplift from cross-selling (premium plans, bundles)
    arpu_uplift = round(tgt_monthly_rev * _REVENUE_SYNERGY_PCT * 12, 2)

    # 2. Churn reduction (stronger brand, better coverage)
    avg_monthly_churn_brl = tgt_monthly_rev * 0.03  # assume 3% monthly churn
    churn_savings = round(avg_monthly_churn_brl * _CHURN_REDUCTION_PCT / 0.03 * 12, 2)

    # 3. Market expansion revenue (new municipalities)
    # Estimate new addressable market in non-overlapping municipalities
    if new_munis:
        expansion_rev_sql = text("""
            SELECT COALESCE(SUM(a2.population), 0) AS total_pop
            FROM admin_level_2 a2
            WHERE a2.id = ANY(:muni_ids)
        """)
        exp_result = await db.execute(expansion_rev_sql, {"muni_ids": list(new_munis)})
        exp_row = exp_result.fetchone()
        new_pop = int(exp_row.total_pop) if exp_row and exp_row.total_pop else 0
        # Conservative: 5% household penetration in new markets, 3.2 people/household
        new_households = new_pop / 3.2
        new_subs_potential = int(new_households * 0.05)
        expansion_revenue = round(new_subs_potential * _ARPU_FIBER * 12, 2)
    else:
        new_pop = 0
        new_subs_potential = 0
        expansion_revenue = 0.0

    total_revenue_synergy = round(arpu_uplift + churn_savings + expansion_revenue, 2)

    # ---- Cost synergies ----
    # 1. Operating cost overlap elimination (shared NOC, billing, support)
    combined_opex = combined_monthly_rev * 0.65 * 12  # assume 65% opex ratio
    opex_savings = round(combined_opex * _COST_SYNERGY_PCT, 2)

    # 2. Infrastructure sharing (shared backbone, towers, POPs)
    overlap_ratio = len(overlap_munis) / max(len(tgt_munis), 1)
    infra_savings = round(
        tgt_monthly_rev * 12 * 0.20 * _INFRA_SHARING_DISCOUNT * (1 + overlap_ratio), 2
    )

    # 3. Vendor consolidation and scale discounts
    scale_factor = math.log10(max(acq_subs + tgt_subs, 10)) / math.log10(max(acq_subs, 10))
    vendor_savings = round(combined_monthly_rev * 12 * 0.02 * (scale_factor - 1), 2)

    total_cost_synergy = round(opex_savings + infra_savings + max(vendor_savings, 0), 2)

    # ---- Market synergies ----
    acq_states = set(acq.state_codes) if acq.state_codes else set()
    tgt_states = set(tgt.state_codes) if tgt.state_codes else set()
    new_states = tgt_states - acq_states
    combined_states = acq_states | tgt_states

    geographic_fill_in = {
        "acquirer_states": sorted(acq_states),
        "target_states": sorted(tgt_states),
        "new_states_gained": sorted(new_states),
        "combined_states": sorted(combined_states),
        "overlap_municipalities": len(overlap_munis),
        "new_municipalities": len(new_munis),
        "total_municipalities": len(acq_munis | tgt_munis),
        "geographic_overlap_pct": round(
            len(overlap_munis) / max(len(tgt_munis), 1) * 100, 1
        ),
    }

    # Combined market position
    combined_subs = acq_subs + tgt_subs
    combined_fiber_pct = round(
        (acq_fiber_s + tgt_fiber_s) / max(combined_subs, 1) * 100, 1
    )

    # ---- Total synergy value (NPV over 5 years, 12% discount) ----
    annual_synergy = total_revenue_synergy + total_cost_synergy
    discount_rate = 0.12
    npv_synergies = round(
        sum(annual_synergy / (1 + discount_rate) ** yr for yr in range(1, 6)), 2
    )

    return {
        "acquirer": {
            "provider_id": acquirer_id,
            "name": acq.provider_name,
            "subscribers": acq_subs,
            "fiber_pct": acq_fiber_pct,
            "states": sorted(acq_states),
            "municipality_count": acq.municipality_count,
            "estimated_monthly_revenue_brl": round(acq_monthly_rev, 2),
        },
        "target": {
            "provider_id": target_id,
            "name": tgt.provider_name,
            "subscribers": tgt_subs,
            "fiber_pct": tgt_fiber_pct,
            "states": sorted(tgt_states),
            "municipality_count": tgt.municipality_count,
            "estimated_monthly_revenue_brl": round(tgt_monthly_rev, 2),
        },
        "combined_entity": {
            "subscribers": combined_subs,
            "fiber_pct": combined_fiber_pct,
            "states": sorted(combined_states),
            "total_municipalities": len(acq_munis | tgt_munis),
            "estimated_monthly_revenue_brl": round(combined_monthly_rev, 2),
            "estimated_annual_revenue_brl": round(combined_monthly_rev * 12, 2),
        },
        "revenue_synergies": {
            "arpu_uplift_annual_brl": arpu_uplift,
            "churn_reduction_annual_brl": churn_savings,
            "market_expansion_annual_brl": expansion_revenue,
            "new_addressable_population": new_pop,
            "new_subscriber_potential": new_subs_potential,
            "total_annual_brl": total_revenue_synergy,
        },
        "cost_synergies": {
            "opex_overlap_annual_brl": opex_savings,
            "infrastructure_sharing_annual_brl": infra_savings,
            "vendor_consolidation_annual_brl": max(vendor_savings, 0),
            "total_annual_brl": total_cost_synergy,
        },
        "geographic_fill_in": geographic_fill_in,
        "total_annual_synergy_brl": round(annual_synergy, 2),
        "npv_5yr_synergies_brl": npv_synergies,
        "synergy_as_pct_of_target_revenue": round(
            annual_synergy / max(tgt_monthly_rev * 12, 1) * 100, 1
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Due Diligence Checklist
# ═══════════════════════════════════════════════════════════════════════════════


async def due_diligence_checklist(
    db: AsyncSession,
    target_id: int,
) -> dict[str, Any]:
    """Generate a due diligence checklist for a target ISP acquisition.

    Assesses regulatory compliance, subscriber quality, infrastructure
    health, financial position, and competitive standing using real data.

    Args:
        db: Async SQLAlchemy session.
        target_id: The target provider's ``providers.id``.

    Returns:
        Dictionary with categorized checklist items and risk assessments.
    """
    # ---- Provider basic info ----
    provider_sql = text("""
        SELECT p.id, p.name, p.national_id,
               pd.status, pd.capital_social, pd.founding_date,
               pd.partner_count, pd.simples_nacional, pd.cnae_primary
        FROM providers p
        LEFT JOIN provider_details pd ON p.id = pd.provider_id
        WHERE p.id = :pid
    """)
    result = await db.execute(provider_sql, {"pid": target_id})
    provider = result.fetchone()

    if not provider:
        return {"error": "Provider not found", "provider_id": target_id}

    checklist: list[dict[str, Any]] = []
    risk_flags: list[str] = []

    # ---- 1. REGULATORY COMPLIANCE ----
    category = "regulatory_compliance"

    # Company registration status
    if provider.status:
        is_active = provider.status.lower() in ("ativa", "active")
        checklist.append({
            "category": category,
            "item": "Company registration status (Receita Federal)",
            "status": "pass" if is_active else "fail",
            "detail": f"Status: {provider.status}",
            "priority": "critical",
        })
        if not is_active:
            risk_flags.append("Company registration not active")
    else:
        checklist.append({
            "category": category,
            "item": "Company registration status (Receita Federal)",
            "status": "pending",
            "detail": "CNPJ enrichment data not available — manual verification required",
            "priority": "critical",
        })

    # Spectrum licenses
    spectrum_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM spectrum_licenses WHERE provider_id = :pid
    """)
    spec_result = await db.execute(spectrum_sql, {"pid": target_id})
    spec_row = spec_result.fetchone()
    has_spectrum = (spec_row.cnt if spec_row else 0) > 0

    checklist.append({
        "category": category,
        "item": "Spectrum / SCM authorization",
        "status": "pass" if has_spectrum else "info",
        "detail": f"{spec_row.cnt} spectrum license(s) on record" if has_spectrum
                  else "No spectrum licenses found — verify SCM authorization with Anatel",
        "priority": "critical",
    })

    # Quality seal assessment
    quality_sql = text("""
        SELECT AVG(overall_score) AS avg_score,
               COUNT(*) AS seal_count,
               MIN(overall_score) AS min_score
        FROM quality_seals WHERE provider_id = :pid
    """)
    qs_result = await db.execute(quality_sql, {"pid": target_id})
    qs_row = qs_result.fetchone()
    avg_quality = float(qs_row.avg_score) if qs_row and qs_row.avg_score else None

    if avg_quality is not None:
        quality_status = "pass" if avg_quality >= 50 else "warning"
        checklist.append({
            "category": category,
            "item": "Anatel quality seal compliance",
            "status": quality_status,
            "detail": f"Average quality score: {avg_quality:.1f}/100 across {qs_row.seal_count} municipality(ies)",
            "priority": "high",
        })
        if avg_quality < 40:
            risk_flags.append(f"Low quality seal score ({avg_quality:.1f}/100)")
    else:
        checklist.append({
            "category": category,
            "item": "Anatel quality seal compliance",
            "status": "pending",
            "detail": "No quality seal data on record",
            "priority": "high",
        })

    # ---- 2. SUBSCRIBER QUALITY ----
    category = "subscriber_quality"

    # Subscriber base and trend
    subs_sql = text("""
        WITH monthly AS (
            SELECT
                bs.year_month,
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subs
            FROM broadband_subscribers bs
            WHERE bs.provider_id = :pid
            GROUP BY bs.year_month
            ORDER BY bs.year_month DESC
            LIMIT 12
        )
        SELECT * FROM monthly ORDER BY year_month ASC
    """)
    subs_result = await db.execute(subs_sql, {"pid": target_id})
    subs_rows = subs_result.fetchall()

    if subs_rows and len(subs_rows) >= 2:
        latest_subs = int(subs_rows[-1].total_subs)
        earliest_subs = int(subs_rows[0].total_subs)
        fiber_latest = int(subs_rows[-1].fiber_subs)
        fiber_pct = round(fiber_latest / max(latest_subs, 1) * 100, 1)

        months_span = len(subs_rows)
        if earliest_subs > 0:
            growth_pct = round((latest_subs - earliest_subs) / earliest_subs * 100, 1)
        else:
            growth_pct = 0.0

        growth_status = "pass" if growth_pct >= 0 else "warning"
        checklist.append({
            "category": category,
            "item": "Subscriber base size and trend",
            "status": growth_status,
            "detail": (
                f"{latest_subs:,} subscribers (latest month), "
                f"{growth_pct:+.1f}% growth over {months_span} months"
            ),
            "priority": "critical",
        })
        if growth_pct < -5:
            risk_flags.append(f"Subscriber base declining ({growth_pct:.1f}% over {months_span}mo)")

        # Fiber penetration
        fiber_status = "pass" if fiber_pct >= 50 else ("warning" if fiber_pct >= 20 else "fail")
        checklist.append({
            "category": category,
            "item": "Fiber penetration ratio",
            "status": fiber_status,
            "detail": f"{fiber_pct}% fiber ({fiber_latest:,} of {latest_subs:,} subscribers)",
            "priority": "high",
        })
        if fiber_pct < 20:
            risk_flags.append(f"Very low fiber penetration ({fiber_pct}%)")

        # Technology mix
        tech_sql = text("""
            SELECT bs.technology, SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs
            WHERE bs.provider_id = :pid
              AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid)
            GROUP BY bs.technology
            ORDER BY subs DESC
        """)
        tech_result = await db.execute(tech_sql, {"pid": target_id})
        tech_rows = tech_result.fetchall()
        tech_mix = {r.technology: int(r.subs) for r in tech_rows}

        checklist.append({
            "category": category,
            "item": "Technology mix diversity",
            "status": "info",
            "detail": ", ".join(f"{k}: {v:,}" for k, v in tech_mix.items()),
            "priority": "medium",
        })

        # Geographic concentration
        geo_sql = text("""
            SELECT COUNT(DISTINCT a2.id) AS muni_count,
                   COUNT(DISTINCT l1.abbrev) AS state_count
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            JOIN admin_level_1 l1 ON a2.l1_id = l1.id
            WHERE bs.provider_id = :pid
              AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid)
        """)
        geo_result = await db.execute(geo_sql, {"pid": target_id})
        geo_row = geo_result.fetchone()

        muni_count = geo_row.muni_count if geo_row else 0
        state_count = geo_row.state_count if geo_row else 0
        geo_status = "pass" if muni_count > 5 else ("warning" if muni_count > 1 else "fail")
        checklist.append({
            "category": category,
            "item": "Geographic diversification",
            "status": geo_status,
            "detail": f"Present in {muni_count} municipality(ies) across {state_count} state(s)",
            "priority": "medium",
        })
        if muni_count == 1:
            risk_flags.append("Single-municipality concentration risk")
    else:
        checklist.append({
            "category": category,
            "item": "Subscriber base size and trend",
            "status": "pending",
            "detail": "Insufficient subscriber history for trend analysis",
            "priority": "critical",
        })

    # ---- 3. INFRASTRUCTURE ASSESSMENT ----
    category = "infrastructure"

    # Base station presence
    tower_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM base_stations WHERE provider_id = :pid
    """)
    tower_result = await db.execute(tower_sql, {"pid": target_id})
    tower_row = tower_result.fetchone()
    tower_count = tower_row.cnt if tower_row else 0

    checklist.append({
        "category": category,
        "item": "Base station / tower infrastructure",
        "status": "pass" if tower_count > 0 else "info",
        "detail": f"{tower_count} base station(s) attributed to provider",
        "priority": "high",
    })

    # Government contracts (indicates infrastructure investment)
    contracts_sql = text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(gc.value_brl), 0) AS total_value
        FROM government_contracts gc
        JOIN providers p ON gc.winner_cnpj = p.national_id
        WHERE p.id = :pid
    """)
    gc_result = await db.execute(contracts_sql, {"pid": target_id})
    gc_row = gc_result.fetchone()

    checklist.append({
        "category": category,
        "item": "Government contracts won",
        "status": "info",
        "detail": (
            f"{gc_row.cnt} contract(s), total R$ {float(gc_row.total_value):,.2f}"
            if gc_row and gc_row.cnt > 0
            else "No government contracts on record"
        ),
        "priority": "medium",
    })

    # ---- 4. FINANCIAL HEALTH ----
    category = "financial_health"

    # BNDES loans
    bndes_sql = text("""
        SELECT COUNT(*) AS cnt,
               COALESCE(SUM(contract_value_brl), 0) AS total_contracted,
               COALESCE(SUM(disbursed_brl), 0) AS total_disbursed
        FROM bndes_loans WHERE provider_id = :pid
    """)
    bn_result = await db.execute(bndes_sql, {"pid": target_id})
    bn_row = bn_result.fetchone()

    has_bndes = (bn_row.cnt if bn_row else 0) > 0
    checklist.append({
        "category": category,
        "item": "BNDES debt obligations",
        "status": "warning" if has_bndes else "pass",
        "detail": (
            f"{bn_row.cnt} loan(s): R$ {float(bn_row.total_contracted):,.2f} contracted, "
            f"R$ {float(bn_row.total_disbursed):,.2f} disbursed"
            if has_bndes
            else "No BNDES loans on record"
        ),
        "priority": "high",
    })
    if has_bndes:
        risk_flags.append(
            f"Outstanding BNDES debt: R$ {float(bn_row.total_contracted):,.2f}"
        )

    # Capital social
    if provider.capital_social:
        capital = float(provider.capital_social)
        checklist.append({
            "category": category,
            "item": "Registered capital (capital social)",
            "status": "info",
            "detail": f"R$ {capital:,.2f}",
            "priority": "medium",
        })
    else:
        checklist.append({
            "category": category,
            "item": "Registered capital (capital social)",
            "status": "pending",
            "detail": "Capital social not available — manual verification required",
            "priority": "medium",
        })

    # Founding date / company age
    if provider.founding_date:
        age_years = (date.today() - provider.founding_date).days / 365.25
        age_status = "pass" if age_years >= 5 else ("warning" if age_years >= 2 else "fail")
        checklist.append({
            "category": category,
            "item": "Company age and track record",
            "status": age_status,
            "detail": f"Founded {provider.founding_date}, operating for {age_years:.1f} years",
            "priority": "medium",
        })
        if age_years < 2:
            risk_flags.append(f"Company is only {age_years:.1f} years old")
    else:
        checklist.append({
            "category": category,
            "item": "Company age and track record",
            "status": "pending",
            "detail": "Founding date not available",
            "priority": "medium",
        })

    # ---- 5. COMPETITIVE POSITION ----
    category = "competitive_position"

    # Market share in operating municipalities
    market_sql = text("""
        WITH provider_munis AS (
            SELECT DISTINCT bs.l2_id
            FROM broadband_subscribers bs
            WHERE bs.provider_id = :pid
              AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid)
        ),
        muni_totals AS (
            SELECT
                bs.l2_id,
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN bs.provider_id = :pid THEN bs.subscribers ELSE 0 END) AS provider_subs
            FROM broadband_subscribers bs
            JOIN provider_munis pm ON bs.l2_id = pm.l2_id
            WHERE bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid)
            GROUP BY bs.l2_id
        )
        SELECT
            AVG(CASE WHEN total_subs > 0 THEN provider_subs::float / total_subs ELSE 0 END) AS avg_share,
            MAX(CASE WHEN total_subs > 0 THEN provider_subs::float / total_subs ELSE 0 END) AS max_share,
            COUNT(*) AS muni_count
        FROM muni_totals
    """)
    mkt_result = await db.execute(market_sql, {"pid": target_id})
    mkt_row = mkt_result.fetchone()

    if mkt_row and mkt_row.avg_share is not None:
        avg_share = round(float(mkt_row.avg_share) * 100, 1)
        max_share = round(float(mkt_row.max_share) * 100, 1)
        share_status = "pass" if avg_share >= 10 else "warning"
        checklist.append({
            "category": category,
            "item": "Average market share in operating areas",
            "status": share_status,
            "detail": f"Average: {avg_share}%, Peak: {max_share}% across {mkt_row.muni_count} municipality(ies)",
            "priority": "high",
        })
    else:
        checklist.append({
            "category": category,
            "item": "Average market share in operating areas",
            "status": "pending",
            "detail": "Market share data not computable",
            "priority": "high",
        })

    # ---- Summary ----
    total_items = len(checklist)
    passed = sum(1 for c in checklist if c["status"] == "pass")
    warnings = sum(1 for c in checklist if c["status"] == "warning")
    failed = sum(1 for c in checklist if c["status"] == "fail")
    pending = sum(1 for c in checklist if c["status"] == "pending")

    if failed > 0 or len(risk_flags) >= 3:
        overall_risk = "high"
    elif warnings > 2 or len(risk_flags) >= 2:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    return {
        "provider_id": target_id,
        "provider_name": provider.name,
        "national_id": provider.national_id,
        "checklist": checklist,
        "summary": {
            "total_items": total_items,
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "pending": pending,
            "overall_risk": overall_risk,
        },
        "risk_flags": risk_flags,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Timeline
# ═══════════════════════════════════════════════════════════════════════════════


async def integration_timeline(
    acquirer_subs: int,
    target_subs: int,
) -> dict[str, Any]:
    """Estimate post-acquisition integration phases and timeline.

    Uses subscriber scale to determine complexity and phase durations.
    This is a computation-only function that does not require DB access.

    Args:
        acquirer_subs: Acquirer's total subscriber count.
        target_subs: Target's total subscriber count.

    Returns:
        Dictionary with integration phases, milestones, and risk factors.
    """
    combined = acquirer_subs + target_subs
    ratio = target_subs / max(acquirer_subs, 1)

    # Complexity tiers determine base durations
    if combined > 500_000 or ratio > 0.5:
        complexity = "high"
        base_months = 24
    elif combined > 100_000 or ratio > 0.25:
        complexity = "medium"
        base_months = 18
    else:
        complexity = "low"
        base_months = 12

    phases = []

    # Phase 1: Regulatory approval
    regulatory_months = 3 if combined < 200_000 else (6 if combined < 1_000_000 else 9)
    phases.append({
        "phase": 1,
        "name": "Regulatory Approval (Anatel / CADE)",
        "duration_months": regulatory_months,
        "start_month": 0,
        "end_month": regulatory_months,
        "key_activities": [
            "File merger notification with CADE (if applicable)",
            "Submit Anatel authorization transfer request",
            "Prepare competition impact assessment",
            "Engage legal counsel for regulatory filings",
        ],
        "risks": [
            "CADE review may require remedies if combined market share exceeds 20% in any municipality",
            "Anatel processing delays (typical 60-120 days)",
        ],
        "estimated_cost_pct": 2,
    })

    # Phase 2: Day-1 integration (legal close to initial ops)
    day1_months = 2 if complexity == "low" else (3 if complexity == "medium" else 4)
    phases.append({
        "phase": 2,
        "name": "Day-1 Integration & Transition",
        "duration_months": day1_months,
        "start_month": regulatory_months,
        "end_month": regulatory_months + day1_months,
        "key_activities": [
            "Legal entity consolidation",
            "Management team alignment and key-person retention",
            "Customer communication and brand transition plan",
            "Financial systems integration kickoff",
            "IT security and access unification",
        ],
        "risks": [
            "Key employee attrition during transition",
            "Customer confusion leading to elevated churn",
        ],
        "estimated_cost_pct": 5,
    })

    # Phase 3: Network integration
    network_months = 4 if complexity == "low" else (6 if complexity == "medium" else 9)
    p3_start = regulatory_months + day1_months
    phases.append({
        "phase": 3,
        "name": "Network & Infrastructure Integration",
        "duration_months": network_months,
        "start_month": p3_start,
        "end_month": p3_start + network_months,
        "key_activities": [
            "NOC consolidation and monitoring unification",
            "IP address space and AS number planning",
            "Backbone interconnection and traffic optimization",
            "OSS/BSS system migration or integration",
            "Redundancy and failover improvements",
        ],
        "risks": [
            "Service disruptions during network migration",
            "Incompatible equipment vendors requiring replacement",
            "Fiber splicing and last-mile re-provisioning delays",
        ],
        "estimated_cost_pct": 15,
    })

    # Phase 4: Commercial integration
    commercial_months = 3 if complexity == "low" else (4 if complexity == "medium" else 6)
    p4_start = p3_start + 2  # overlaps with phase 3
    phases.append({
        "phase": 4,
        "name": "Commercial & Customer Integration",
        "duration_months": commercial_months,
        "start_month": p4_start,
        "end_month": p4_start + commercial_months,
        "key_activities": [
            "Billing system migration / unification",
            "Product catalog harmonization and upsell campaigns",
            "Customer support team integration",
            "Brand consolidation (if applicable)",
            "Contract renegotiation with shared vendors",
        ],
        "risks": [
            "Billing migration errors causing revenue leakage",
            "Customer churn during plan migration",
        ],
        "estimated_cost_pct": 8,
    })

    # Phase 5: Optimization and synergy capture
    opt_months = 6 if complexity == "low" else (9 if complexity == "medium" else 12)
    p5_start = p3_start + network_months
    phases.append({
        "phase": 5,
        "name": "Optimization & Synergy Capture",
        "duration_months": opt_months,
        "start_month": p5_start,
        "end_month": p5_start + opt_months,
        "key_activities": [
            "Headcount rationalization and org restructuring",
            "Infrastructure decommissioning (duplicate POPs, links)",
            "Cross-sell and upsell execution in new markets",
            "Performance benchmarking against synergy targets",
            "Continuous improvement and feedback loops",
        ],
        "risks": [
            "Synergy targets not fully realized",
            "Cultural integration challenges",
        ],
        "estimated_cost_pct": 5,
    })

    total_months = max(p["end_month"] for p in phases)

    # Integration cost estimate (percentage of target annual revenue)
    total_cost_pct = sum(p["estimated_cost_pct"] for p in phases)

    # Key milestones
    milestones = [
        {"month": 0, "milestone": "Transaction signing"},
        {"month": regulatory_months, "milestone": "Regulatory approval / legal close"},
        {"month": regulatory_months + 1, "milestone": "Day-1 operational control"},
        {"month": regulatory_months + day1_months, "milestone": "Day-1 integration complete"},
        {"month": p3_start + (network_months // 2), "milestone": "NOC consolidation complete"},
        {"month": p3_start + network_months, "milestone": "Network integration complete"},
        {"month": p4_start + commercial_months, "milestone": "Commercial integration complete"},
        {"month": total_months, "milestone": "Full integration complete"},
    ]

    return {
        "acquirer_subscribers": acquirer_subs,
        "target_subscribers": target_subs,
        "combined_subscribers": combined,
        "size_ratio": round(ratio, 2),
        "complexity": complexity,
        "total_duration_months": total_months,
        "phases": phases,
        "milestones": milestones,
        "integration_cost_pct_of_target_revenue": total_cost_pct,
        "risk_factors": [
            "Key employee retention during extended integration period",
            "Customer churn spike in months 3-6 post-close",
            "Regulatory conditions or remedies imposed by CADE",
            "Technology stack incompatibility increasing migration costs",
            "Market conditions changing during integration window",
        ],
        "success_factors": [
            "Dedicated integration management office (IMO)",
            "Clear communication plan for customers and employees",
            "Phased migration approach minimizing service disruption",
            "Retention bonuses for key technical and commercial staff",
            "Regular synergy tracking and reporting cadence",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Spectrum Asset Valuation
# ═══════════════════════════════════════════════════════════════════════════════

# BRL per MHz-pop pricing by band
_SPECTRUM_PRICING: dict[str, float] = {
    "700":   0.80,
    "850":   0.60,
    "1800":  0.40,
    "2100":  0.35,
    "2600":  0.25,
    "3500":  0.50,
    "26000": 0.05,
}
_SPECTRUM_DEFAULT_PRICE = 0.30


def _band_name_from_freq(freq_mhz: float) -> str:
    """Map a frequency in MHz to a canonical band name."""
    if 694 <= freq_mhz <= 756:
        return "700 MHz"
    if 824 <= freq_mhz <= 894:
        return "850 MHz"
    if 1710 <= freq_mhz <= 1880:
        return "1800 MHz"
    if 1920 <= freq_mhz <= 2170:
        return "2100 MHz"
    if 2500 <= freq_mhz <= 2690:
        return "2600 MHz"
    if 3300 <= freq_mhz <= 3700:
        return "3500 MHz (5G)"
    if 24250 <= freq_mhz <= 27500:
        return "26 GHz (mmWave)"
    return f"{freq_mhz:.0f} MHz"


def _price_key_from_freq(freq_mhz: float) -> str:
    """Return the pricing dict key for a given frequency."""
    if 694 <= freq_mhz <= 756:
        return "700"
    if 824 <= freq_mhz <= 894:
        return "850"
    if 1710 <= freq_mhz <= 1880:
        return "1800"
    if 1920 <= freq_mhz <= 2170:
        return "2100"
    if 2500 <= freq_mhz <= 2690:
        return "2600"
    if 3300 <= freq_mhz <= 3700:
        return "3500"
    if 24250 <= freq_mhz <= 27500:
        return "26000"
    return ""


async def get_spectrum_holdings(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Return spectrum holdings for a provider.

    Queries the ``spectrum_holdings`` table first.  If no rows exist,
    synthesizes approximate holdings from ``base_stations`` grouped by
    frequency band.

    Args:
        db: Async SQLAlchemy session.
        provider_id: The provider's ``providers.id``.

    Returns:
        Dictionary with provider info and holdings list.
    """
    # ---- Provider name ----
    name_sql = text("SELECT id, name FROM providers WHERE id = :pid")
    name_result = await db.execute(name_sql, {"pid": provider_id})
    provider_row = name_result.fetchone()
    if not provider_row:
        return {"error": "Provider not found", "provider_id": provider_id}

    # ---- Try spectrum_holdings table first ----
    holdings_sql = text("""
        SELECT
            id, frequency_mhz, bandwidth_mhz, band_name,
            license_expiry, coverage_area_km2, population_covered,
            license_type
        FROM spectrum_holdings
        WHERE provider_id = :pid
        ORDER BY frequency_mhz
    """)
    result = await db.execute(holdings_sql, {"pid": provider_id})
    rows = result.fetchall()

    if rows:
        holdings = [
            {
                "id": r.id,
                "frequency_mhz": r.frequency_mhz,
                "bandwidth_mhz": r.bandwidth_mhz,
                "band_name": r.band_name or _band_name_from_freq(r.frequency_mhz),
                "license_expiry": str(r.license_expiry) if r.license_expiry else None,
                "coverage_area_km2": r.coverage_area_km2,
                "population_covered": int(r.population_covered) if r.population_covered else None,
                "license_type": r.license_type,
                "source": "spectrum_holdings",
            }
            for r in rows
        ]
    else:
        # ---- Synthesize from base_stations ----
        synth_sql = text("""
            SELECT
                bs.frequency_mhz,
                bs.technology,
                COUNT(*) AS station_count,
                AVG(bs.bandwidth_mhz) AS avg_bw
            FROM base_stations bs
            WHERE bs.provider_id = :pid
              AND bs.frequency_mhz IS NOT NULL
            GROUP BY bs.frequency_mhz, bs.technology
            ORDER BY bs.frequency_mhz
        """)
        synth_result = await db.execute(synth_sql, {"pid": provider_id})
        synth_rows = synth_result.fetchall()

        # Get provider population footprint for estimation
        pop_sql = text("""
            SELECT COALESCE(SUM(a2.population), 0) AS total_pop
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            WHERE bs.provider_id = :pid
              AND bs.year_month = (
                  SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid
              )
        """)
        pop_result = await db.execute(pop_sql, {"pid": provider_id})
        pop_row = pop_result.fetchone()
        est_pop = int(pop_row.total_pop) if pop_row and pop_row.total_pop else 100_000

        holdings = []
        for r in synth_rows:
            freq = float(r.frequency_mhz)
            bw = float(r.avg_bw) if r.avg_bw else 10.0
            holdings.append({
                "id": None,
                "frequency_mhz": freq,
                "bandwidth_mhz": round(bw, 1),
                "band_name": _band_name_from_freq(freq),
                "license_expiry": None,
                "coverage_area_km2": None,
                "population_covered": est_pop,
                "license_type": f"synthesized from {r.station_count} base station(s)",
                "technology": r.technology,
                "station_count": r.station_count,
                "source": "base_stations_synthesized",
            })

    return {
        "provider_id": provider_id,
        "provider_name": provider_row.name,
        "holdings": holdings,
        "holdings_count": len(holdings),
    }


async def value_spectrum(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Value spectrum assets for a provider using BRL/MHz-pop pricing.

    Fetches holdings via :func:`get_spectrum_holdings`, then applies
    band-specific pricing with license remaining-life depreciation.

    Args:
        db: Async SQLAlchemy session.
        provider_id: The provider's ``providers.id``.

    Returns:
        Dictionary with per-holding valuations and totals.
    """
    holdings_data = await get_spectrum_holdings(db=db, provider_id=provider_id)

    if "error" in holdings_data:
        return holdings_data

    today = date.today()
    default_license_years = 15  # typical Anatel license term
    valued_holdings: list[dict[str, Any]] = []
    total_value = 0.0
    total_bw = 0.0

    for h in holdings_data["holdings"]:
        freq = h["frequency_mhz"]
        bw = h["bandwidth_mhz"] or 10.0
        pop = h["population_covered"] or 100_000

        # Look up price per MHz-pop
        key = _price_key_from_freq(freq)
        price_per_mhz_pop = _SPECTRUM_PRICING.get(key, _SPECTRUM_DEFAULT_PRICE)

        # Gross value = price * bandwidth * population
        gross_value = price_per_mhz_pop * bw * pop

        # Apply license remaining life discount (linear depreciation)
        if h["license_expiry"]:
            try:
                expiry = date.fromisoformat(h["license_expiry"])
                remaining_days = (expiry - today).days
                remaining_years = max(remaining_days / 365.25, 0)
                life_factor = min(remaining_years / default_license_years, 1.0)
            except (ValueError, TypeError):
                life_factor = 0.7  # default 70% if parse fails
        else:
            # No expiry known — assume 70% remaining life
            life_factor = 0.7

        net_value = round(gross_value * life_factor, 2)
        total_value += net_value
        total_bw += bw

        valued_holdings.append({
            **h,
            "price_per_mhz_pop": price_per_mhz_pop,
            "gross_value_brl": round(gross_value, 2),
            "life_factor": round(life_factor, 3),
            "net_value_brl": net_value,
        })

    return {
        "provider_id": provider_id,
        "provider_name": holdings_data["provider_name"],
        "holdings": valued_holdings,
        "total_spectrum_value_brl": round(total_value, 2),
        "total_bandwidth_mhz": round(total_bw, 1),
        "bands_count": len(valued_holdings),
    }
