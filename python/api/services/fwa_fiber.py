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
    fwa_payback_months = math.ceil(fwa_capex / max(fwa_monthly_revenue - fwa_monthly_opex, 1))

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
    fiber_payback_months = math.ceil(fiber_capex / max(fiber_monthly_revenue - fiber_monthly_opex, 1))

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
