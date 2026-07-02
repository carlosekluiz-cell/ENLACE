"""
ENLACE FWA vs Fiber Calculator Service

Computes CAPEX, OPEX, and 5-year TCO comparison between Fixed Wireless Access
and Fiber-to-the-Home deployments using building_footprints, road_segments,
and opencellid_towers data.
"""

import logging
import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Cost constants (BRL, based on Brazilian market 2025)
FWA_TOWER_COST = 150_000  # per tower including equipment
FWA_CPE_COST = 800  # per subscriber CPE
FWA_BACKHAUL_COST_KM = 5_000  # microwave backhaul per km
FWA_MONTHLY_OPEX_PER_SUB = 15  # BRL/subscriber/month
FWA_TOWER_MONTHLY_OPEX = 3_000  # per tower maintenance
FWA_COVERAGE_RADIUS_KM = 5  # typical FWA coverage radius

FIBER_COST_PER_KM = 35_000  # trunk fiber per km
FIBER_DROP_COST = 1_200  # per subscriber drop
FIBER_OLT_COST = 80_000  # per OLT (serves ~128 subscribers)
FIBER_SPLITTER_COST = 2_500  # per splitter
FIBER_MONTHLY_OPEX_PER_SUB = 8  # BRL/subscriber/month
FIBER_ONT_COST = 350  # per subscriber ONT

# Revenue assumptions
ARPU_FWA = 79.90  # BRL/month
ARPU_FIBER = 99.90  # BRL/month


async def compare_technologies(
    db: AsyncSession,
    l2_id: int,
    target_subscribers: Optional[int] = None,
    area_km2: Optional[float] = None,
) -> dict[str, Any]:
    """Compare FWA vs Fiber deployment costs for a municipality."""
    # Fetch municipality data
    sql = text("""
        SELECT a2.id, a2.name, a1.abbrev AS state, a2.population, a2.area_km2,
            (SELECT COUNT(*) FROM building_footprints bf WHERE bf.l2_id = a2.id) AS building_count,
            (SELECT COALESCE(SUM(bf.area_m2), 0) FROM building_footprints bf WHERE bf.l2_id = a2.id) AS total_building_area,
            (SELECT COUNT(*) FROM opencellid_towers ot WHERE ot.l2_id = a2.id) AS existing_towers,
            (SELECT COALESCE(SUM(rs.length_m), 0) / 1000.0 FROM road_segments rs
             JOIN admin_level_2 a22 ON ST_Intersects(a22.geom, rs.geom) WHERE a22.id = a2.id) AS road_km
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE a2.id = :l2_id
    """)

    result = await db.execute(sql, {"l2_id": l2_id})
    row = result.fetchone()

    if not row:
        return {"error": "municipality_not_found", "l2_id": l2_id}

    population = row.population or 0
    muni_area = area_km2 or (float(row.area_km2) if row.area_km2 else 100)
    subs = target_subscribers or max(int(population * 0.15 / 3.2), 100)  # 15% household penetration
    buildings = row.building_count or int(subs * 1.2)
    existing_towers = row.existing_towers or 0
    road_km = float(row.road_km) if row.road_km else muni_area * 0.5

    # ── FWA Calculation ──
    towers_needed = max(1, math.ceil(muni_area / (math.pi * FWA_COVERAGE_RADIUS_KM ** 2)))
    towers_new = max(0, towers_needed - existing_towers)
    backhaul_km = towers_new * 10  # avg 10km backhaul per tower

    fwa_capex = (
        towers_new * FWA_TOWER_COST
        + subs * FWA_CPE_COST
        + backhaul_km * FWA_BACKHAUL_COST_KM
    )
    fwa_monthly_opex = (
        subs * FWA_MONTHLY_OPEX_PER_SUB
        + towers_needed * FWA_TOWER_MONTHLY_OPEX
    )
    fwa_annual_opex = fwa_monthly_opex * 12
    fwa_5yr_tco = fwa_capex + fwa_annual_opex * 5

    fwa_monthly_revenue = subs * ARPU_FWA
    fwa_annual_revenue = fwa_monthly_revenue * 12
    fwa_net_monthly = fwa_monthly_revenue - fwa_monthly_opex
    fwa_payback_months = math.ceil(fwa_capex / fwa_net_monthly) if fwa_net_monthly > 0 else None

    # ── Fiber Calculation ──
    fiber_trunk_km = road_km * 0.3  # 30% of road network for fiber trunk
    olts_needed = max(1, math.ceil(subs / 128))
    splitters_needed = max(1, math.ceil(subs / 32))

    fiber_capex = (
        fiber_trunk_km * FIBER_COST_PER_KM
        + subs * FIBER_DROP_COST
        + subs * FIBER_ONT_COST
        + olts_needed * FIBER_OLT_COST
        + splitters_needed * FIBER_SPLITTER_COST
    )
    fiber_monthly_opex = subs * FIBER_MONTHLY_OPEX_PER_SUB
    fiber_annual_opex = fiber_monthly_opex * 12
    fiber_5yr_tco = fiber_capex + fiber_annual_opex * 5

    fiber_monthly_revenue = subs * ARPU_FIBER
    fiber_annual_revenue = fiber_monthly_revenue * 12
    fiber_net_monthly = fiber_monthly_revenue - fiber_monthly_opex
    fiber_payback_months = math.ceil(fiber_capex / fiber_net_monthly) if fiber_net_monthly > 0 else None

    # ── Recommendation ──
    if fwa_5yr_tco < fiber_5yr_tco * 0.7:
        recommendation = "FWA"
        reason = "FWA has significantly lower 5-year TCO for this municipality"
    elif fiber_5yr_tco < fwa_5yr_tco * 0.7:
        recommendation = "Fiber"
        reason = "Fiber has significantly lower 5-year TCO and higher ARPU potential"
    elif muni_area > 500 or population < 10000:
        recommendation = "FWA"
        reason = "Large/sparse area favors FWA economics"
    else:
        recommendation = "Fiber"
        reason = "Dense urban area favors fiber with higher ARPU and lower long-term OPEX"

    return {
        "municipality": {
            "l2_id": l2_id,
            "name": row.name,
            "state": row.state,
            "population": population,
            "area_km2": muni_area,
            "buildings": buildings,
            "existing_towers": existing_towers,
            "road_km": round(road_km, 1),
        },
        "target_subscribers": subs,
        "fwa": {
            "capex_brl": round(fwa_capex, 2),
            "monthly_opex_brl": round(fwa_monthly_opex, 2),
            "annual_opex_brl": round(fwa_annual_opex, 2),
            "tco_5yr_brl": round(fwa_5yr_tco, 2),
            "capex_per_sub": round(fwa_capex / max(subs, 1), 2),
            "towers_needed": towers_needed,
            "towers_new": towers_new,
            "monthly_revenue_brl": round(fwa_monthly_revenue, 2),
            "payback_months": fwa_payback_months,
            "arpu": ARPU_FWA,
        },
        "fiber": {
            "capex_brl": round(fiber_capex, 2),
            "monthly_opex_brl": round(fiber_monthly_opex, 2),
            "annual_opex_brl": round(fiber_annual_opex, 2),
            "tco_5yr_brl": round(fiber_5yr_tco, 2),
            "capex_per_sub": round(fiber_capex / max(subs, 1), 2),
            "fiber_trunk_km": round(fiber_trunk_km, 1),
            "olts_needed": olts_needed,
            "monthly_revenue_brl": round(fiber_monthly_revenue, 2),
            "payback_months": fiber_payback_months,
            "arpu": ARPU_FIBER,
        },
        "comparison": {
            "capex_savings_with_fwa_brl": round(fiber_capex - fwa_capex, 2),
            "tco_5yr_savings_with_fwa_brl": round(fiber_5yr_tco - fwa_5yr_tco, 2),
            "fiber_arpu_premium_pct": round((ARPU_FIBER - ARPU_FWA) / ARPU_FWA * 100, 1),
        },
        "recommendation": recommendation,
        "recommendation_reason": reason,
    }


def get_presets() -> list[dict[str, Any]]:
    """Return preset scenarios for the FWA vs Fiber calculator."""
    return [
        {"name": "Rural pequeno", "subscribers": 500, "area_km2": 200, "description": "Comunidade rural com baixa densidade"},
        {"name": "Cidade média", "subscribers": 5000, "area_km2": 50, "description": "Cidade de médio porte"},
        {"name": "Subúrbio", "subscribers": 15000, "area_km2": 30, "description": "Área suburbana densa"},
        {"name": "Centro urbano", "subscribers": 50000, "area_km2": 15, "description": "Centro urbano denso"},
    ]


# ---------------------------------------------------------------------------
# Ramp curve definitions
# ---------------------------------------------------------------------------

RAMP_CURVES = {
    "optimistic": {"target_pct": 0.70, "months_to_target": 12, "label": "Otimista"},
    "realistic": {"target_pct": 0.60, "months_to_target": 18, "label": "Realista"},
    "conservative": {"target_pct": 0.40, "months_to_target": 24, "label": "Conservador"},
}

DISCOUNT_RATE_ANNUAL = 0.12  # 12% annual discount rate


def _subscriber_ramp(month: int, target_subs: int, target_pct: float, months_to_target: int) -> int:
    """S-curve subscriber ramp: reaches target_pct of subscribers at months_to_target."""
    if month <= 0:
        return 0
    max_subs = int(target_subs * target_pct)
    # Logistic growth curve
    k = 6.0 / months_to_target  # steepness
    midpoint = months_to_target / 2
    ramp = max_subs / (1 + math.exp(-k * (month - midpoint)))
    return min(int(ramp), max_subs)


def _npv(cashflows: list[float], annual_rate: float) -> float:
    """Calculate NPV from monthly cashflows using monthly discount rate."""
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1
    total = 0.0
    for i, cf in enumerate(cashflows):
        total += cf / ((1 + monthly_rate) ** i)
    return total


def _irr(cashflows: list[float], max_iter: int = 200, tol: float = 1e-6) -> Optional[float]:
    """Calculate IRR using Newton's method on monthly cashflows. Returns annual rate."""
    # Initial guess
    r = 0.01  # monthly
    for _ in range(max_iter):
        npv_val = sum(cf / ((1 + r) ** i) for i, cf in enumerate(cashflows))
        dnpv = sum(-i * cf / ((1 + r) ** (i + 1)) for i, cf in enumerate(cashflows))
        if abs(dnpv) < 1e-12:
            break
        r_new = r - npv_val / dnpv
        if abs(r_new - r) < tol:
            r = r_new
            break
        r = r_new
    if r <= -1 or r > 10:
        return None
    return round(((1 + r) ** 12 - 1) * 100, 2)  # annualized %


async def get_market_context(db: AsyncSession, l2_id: int) -> dict[str, Any]:
    """Fetch competitive market context for a municipality.

    Returns HHI, competitor count, leader share, fiber %, and growth trend
    from broadband_subscribers and competitive_analysis tables.
    """
    sql = text("""
        WITH latest AS (
            SELECT year_month FROM broadband_subscribers
            WHERE l2_id = :l2_id
            ORDER BY year_month DESC LIMIT 1
        ),
        subs AS (
            SELECT bs.provider_id, p.name AS provider_name, SUM(bs.subscribers) AS subs,
                   SUM(CASE WHEN bs.technology IN ('Fibra Óptica', 'Fiber') THEN bs.subscribers ELSE 0 END) AS fiber_subs
            FROM broadband_subscribers bs
            JOIN providers p ON bs.provider_id = p.id
            WHERE bs.l2_id = :l2_id AND bs.year_month = (SELECT year_month FROM latest)
            GROUP BY bs.provider_id, p.name
        ),
        totals AS (
            SELECT SUM(subs) AS total, SUM(fiber_subs) AS total_fiber,
                   COUNT(*) AS providers
            FROM subs
        )
        SELECT t.total, t.total_fiber, t.providers,
               s.provider_name AS leader_name, s.subs AS leader_subs,
               ROUND(s.subs * 100.0 / NULLIF(t.total, 0), 1) AS leader_share,
               ROUND(t.total_fiber * 100.0 / NULLIF(t.total, 0), 1) AS fiber_pct,
               SUM(POWER(s2.subs * 100.0 / NULLIF(t.total, 0), 2)) AS hhi
        FROM totals t
        LEFT JOIN subs s ON s.subs = (SELECT MAX(subs) FROM subs)
        LEFT JOIN subs s2 ON TRUE
        GROUP BY t.total, t.total_fiber, t.providers, s.provider_name, s.subs
    """)
    result = await db.execute(sql, {"l2_id": l2_id})
    row = result.fetchone()

    if not row or not row.total:
        return {
            "total_subscribers": 0,
            "providers": 0,
            "hhi": 0,
            "leader_name": None,
            "leader_share_pct": 0,
            "fiber_pct": 0,
            "growth_trend": "unknown",
        }

    # Growth trend from last 6 months
    growth_sql = text("""
        SELECT year_month, SUM(subscribers) AS total
        FROM broadband_subscribers
        WHERE l2_id = :l2_id
        GROUP BY year_month
        ORDER BY year_month DESC LIMIT 6
    """)
    growth_result = await db.execute(growth_sql, {"l2_id": l2_id})
    growth_rows = growth_result.fetchall()

    trend = "stable"
    if len(growth_rows) >= 2:
        newest = growth_rows[0].total
        oldest = growth_rows[-1].total
        if oldest > 0:
            change_pct = (newest - oldest) / oldest * 100
            if change_pct > 5:
                trend = "growing"
            elif change_pct < -5:
                trend = "declining"

    return {
        "total_subscribers": int(row.total),
        "providers": int(row.providers),
        "hhi": round(float(row.hhi or 0), 0),
        "leader_name": row.leader_name,
        "leader_share_pct": float(row.leader_share or 0),
        "fiber_pct": float(row.fiber_pct or 0),
        "growth_trend": trend,
    }


async def viability_analysis(
    db: AsyncSession,
    l2_id: int,
    technology: str,
    subscribers: int,
    arpu: float,
    capex_override: Optional[float] = None,
) -> dict[str, Any]:
    """Economic viability analysis with 3 scenarios, NPV, IRR, and payback.

    Args:
        db: Async database session.
        l2_id: Municipality ID.
        technology: "FTTH", "FWA", or "Hibrido".
        subscribers: Target subscriber count.
        arpu: Average Revenue Per User (BRL/month).
        capex_override: Optional manual CAPEX (otherwise estimated).

    Returns:
        Dict with CAPEX breakdown, OPEX, 3 scenario analyses, market context,
        and recommendation.
    """
    # Estimate CAPEX
    if capex_override:
        total_capex = capex_override
    else:
        if technology == "FWA":
            total_capex = subscribers * (FWA_CPE_COST + 200)  # CPE + tower share
        elif technology == "Hibrido":
            total_capex = subscribers * 2_200  # blend
        else:  # FTTH
            total_capex = subscribers * 2_800  # typical FTTH CAPEX/sub

    # OPEX per subscriber per month
    if technology == "FWA":
        opex_per_sub = FWA_MONTHLY_OPEX_PER_SUB
    elif technology == "Hibrido":
        opex_per_sub = 12
    else:
        opex_per_sub = FIBER_MONTHLY_OPEX_PER_SUB

    # Market context
    market = await get_market_context(db, l2_id)

    # Run 3 scenarios over 60 months
    scenarios = {}
    for scenario_key, curve in RAMP_CURVES.items():
        cashflows = [-total_capex]
        monthly_data = []
        payback_month = None
        cumulative = -total_capex

        for month in range(1, 61):
            active_subs = _subscriber_ramp(month, subscribers, curve["target_pct"], curve["months_to_target"])
            revenue = active_subs * arpu
            opex = active_subs * opex_per_sub
            net = revenue - opex
            cumulative += net
            cashflows.append(net)

            monthly_data.append({
                "month": month,
                "subscribers": active_subs,
                "revenue_brl": round(revenue, 2),
                "opex_brl": round(opex, 2),
                "net_brl": round(net, 2),
                "cumulative_brl": round(cumulative, 2),
            })

            if payback_month is None and cumulative >= 0:
                payback_month = month

        npv_val = _npv(cashflows, DISCOUNT_RATE_ANNUAL)
        irr_val = _irr(cashflows)

        scenarios[scenario_key] = {
            "label": curve["label"],
            "target_pct": curve["target_pct"],
            "months_to_target": curve["months_to_target"],
            "max_subscribers": int(subscribers * curve["target_pct"]),
            "payback_months": payback_month,
            "npv_brl": round(npv_val, 2),
            "irr_pct": irr_val,
            "monthly_revenue_at_target_brl": round(int(subscribers * curve["target_pct"]) * arpu, 2),
            "monthly_opex_at_target_brl": round(int(subscribers * curve["target_pct"]) * opex_per_sub, 2),
            "cashflow": monthly_data,
        }

    # Recommendation based on realistic scenario
    realistic = scenarios["realistic"]
    if realistic["payback_months"] is not None and realistic["payback_months"] <= 24:
        recommendation = "viable"
        recommendation_label = "Viável"
        recommendation_reason = f"Payback em {realistic['payback_months']} meses no cenário realista"
    elif realistic["payback_months"] is not None and realistic["payback_months"] <= 48:
        recommendation = "marginal"
        recommendation_label = "Marginal"
        recommendation_reason = f"Payback em {realistic['payback_months']} meses — requer análise detalhada"
    else:
        recommendation = "not_viable"
        recommendation_label = "Inviável"
        recommendation_reason = "Payback superior a 48 meses ou NPV negativo"

    if realistic["npv_brl"] < 0:
        recommendation = "not_viable"
        recommendation_label = "Inviável"
        recommendation_reason = f"NPV negativo (R$ {realistic['npv_brl']:,.0f})"

    return {
        "technology": technology,
        "subscribers": subscribers,
        "arpu_brl": arpu,
        "capex": {
            "total_brl": round(total_capex, 2),
            "per_subscriber_brl": round(total_capex / max(subscribers, 1), 2),
        },
        "opex_per_subscriber_brl": opex_per_sub,
        "scenarios": scenarios,
        "market_context": market,
        "recommendation": {
            "status": recommendation,
            "label": recommendation_label,
            "reason": recommendation_reason,
        },
        "discount_rate_annual_pct": DISCOUNT_RATE_ANNUAL * 100,
    }
