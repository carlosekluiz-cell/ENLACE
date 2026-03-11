"""
ENLACE Tower Co-Location Analysis Router

Endpoints for identifying and analyzing tower sharing opportunities
across Brazil's 37K+ base stations.  Helps operators reduce CAPEX
through infrastructure sharing by scoring co-location potential based
on proximity, operator diversity, underserved population, coverage
gaps, and spectrum complementarity.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.colocation_service import (
    compute_colocation,
    compute_municipality_colocation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/colocation", tags=["colocation"])


# ═══════════════════════════════════════════════════════════════════════
# GET /opportunities — Top co-location opportunities
# ═══════════════════════════════════════════════════════════════════════


@router.get("/opportunities")
async def colocation_opportunities(
    state: Optional[str] = Query(
        None, description="State abbreviation filter (e.g. SP, MG, RJ)"
    ),
    min_score: float = Query(
        50.0, ge=0.0, le=100.0, description="Minimum colocation score threshold"
    ),
    limit: int = Query(100, ge=1, le=5000, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> list[dict[str, Any]]:
    """
    Return top tower co-location opportunities ranked by score.

    Reads pre-computed results from ``tower_colocation_analysis`` joined
    with base station and municipality data.  Supports filtering by
    state and minimum score threshold.
    """
    where_parts = ["tca.colocation_score >= :min_score"]
    params: dict[str, Any] = {"min_score": min_score, "limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            tca.id,
            tca.base_station_id,
            bs.latitude,
            bs.longitude,
            bs.technology,
            bs.frequency_mhz,
            tca.provider_name,
            tca.l2_id AS municipality_id,
            a2.name AS municipality_name,
            a1.abbrev AS state_abbrev,
            tca.nearby_towers_500m,
            tca.nearby_providers,
            tca.underserved_pop_5km,
            tca.competitor_density_score,
            tca.gap_coverage_score,
            tca.spectrum_complement_score,
            tca.colocation_score,
            tca.estimated_savings_brl,
            tca.computed_at
        FROM tower_colocation_analysis tca
        JOIN base_stations bs ON bs.id = tca.base_station_id
        LEFT JOIN admin_level_2 a2 ON a2.id = tca.l2_id
        LEFT JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE {where_sql}
        ORDER BY tca.colocation_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "base_station_id": row.base_station_id,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "technology": row.technology,
            "frequency_mhz": row.frequency_mhz,
            "provider_name": row.provider_name,
            "municipality_id": row.municipality_id,
            "municipality_name": row.municipality_name,
            "state_abbrev": row.state_abbrev,
            "nearby_towers_500m": row.nearby_towers_500m,
            "nearby_providers": row.nearby_providers,
            "underserved_pop_5km": row.underserved_pop_5km,
            "competitor_density_score": row.competitor_density_score,
            "gap_coverage_score": row.gap_coverage_score,
            "spectrum_complement_score": row.spectrum_complement_score,
            "colocation_score": row.colocation_score,
            "estimated_savings_brl": row.estimated_savings_brl,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# GET /{base_station_id}/analysis — Single tower analysis
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{base_station_id}/analysis")
async def colocation_analysis(
    base_station_id: int,
    recompute: bool = Query(
        False, description="Force recomputation instead of returning cached result"
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict[str, Any]:
    """
    Detailed co-location analysis for a single base station.

    Returns cached results by default.  Pass ``recompute=true`` to trigger
    a fresh computation that considers current nearby towers, population,
    and broadband subscriber data.
    """
    if not recompute:
        # Try to return cached result first
        cached_sql = text("""
            SELECT
                tca.base_station_id,
                bs.latitude,
                bs.longitude,
                bs.technology,
                bs.frequency_mhz,
                tca.provider_name,
                tca.l2_id AS municipality_id,
                a2.name AS municipality_name,
                a1.abbrev AS state_abbrev,
                tca.nearby_towers_500m,
                tca.nearby_providers,
                tca.underserved_pop_5km,
                tca.competitor_density_score,
                tca.gap_coverage_score,
                tca.spectrum_complement_score,
                tca.colocation_score,
                tca.estimated_savings_brl,
                tca.computed_at
            FROM tower_colocation_analysis tca
            JOIN base_stations bs ON bs.id = tca.base_station_id
            LEFT JOIN admin_level_2 a2 ON a2.id = tca.l2_id
            LEFT JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE tca.base_station_id = :bs_id
        """)
        cached = (
            await db.execute(cached_sql, {"bs_id": base_station_id})
        ).fetchone()

        if cached:
            return {
                "base_station_id": cached.base_station_id,
                "latitude": cached.latitude,
                "longitude": cached.longitude,
                "technology": cached.technology,
                "frequency_mhz": cached.frequency_mhz,
                "provider_name": cached.provider_name,
                "municipality_id": cached.municipality_id,
                "municipality_name": cached.municipality_name,
                "state_abbrev": cached.state_abbrev,
                "nearby_towers_500m": cached.nearby_towers_500m,
                "nearby_providers": cached.nearby_providers,
                "underserved_pop_5km": cached.underserved_pop_5km,
                "competitor_density_score": cached.competitor_density_score,
                "gap_coverage_score": cached.gap_coverage_score,
                "spectrum_complement_score": cached.spectrum_complement_score,
                "colocation_score": cached.colocation_score,
                "estimated_savings_brl": cached.estimated_savings_brl,
                "computed_at": (
                    cached.computed_at.isoformat() if cached.computed_at else None
                ),
                "cached": True,
            }

    # Compute fresh analysis
    result = await compute_colocation(db, base_station_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Base station {base_station_id} not found",
        )

    result["cached"] = False
    return result


# ═══════════════════════════════════════════════════════════════════════
# POST /compute/{municipality_id} — Trigger batch computation
# ═══════════════════════════════════════════════════════════════════════


@router.post("/compute/{municipality_id}")
async def trigger_computation(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict[str, Any]:
    """
    Trigger co-location analysis computation for all base stations in a
    municipality.

    This is a potentially long-running operation for municipalities with
    many towers.  Returns a summary with the number of towers processed,
    average co-location score, and total estimated savings.
    """
    result = await compute_municipality_colocation(db, municipality_id)

    if result.get("error") == "municipality_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Municipality {municipality_id} not found",
        )

    return result


# ═══════════════════════════════════════════════════════════════════════
# GET /summary — Aggregate co-location stats by state
# ═══════════════════════════════════════════════════════════════════════


@router.get("/summary")
async def colocation_summary(
    state: Optional[str] = Query(
        None, description="State abbreviation filter (e.g. SP, MG)"
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict[str, Any]:
    """
    Aggregate co-location statistics, optionally filtered by state.

    Returns total towers analyzed, total/average scores, estimated savings
    potential, and per-state breakdown.
    """
    # Global aggregates (with optional state filter)
    where_clause = ""
    params: dict[str, Any] = {}

    if state:
        where_clause = "WHERE a1.abbrev = :state"
        params["state"] = state.upper()

    agg_sql = text(f"""
        SELECT
            COUNT(*) AS total_analyzed,
            ROUND(AVG(tca.colocation_score)::numeric, 2) AS avg_score,
            MAX(tca.colocation_score) AS max_score,
            MIN(tca.colocation_score) AS min_score,
            ROUND(SUM(tca.estimated_savings_brl)::numeric, 2) AS total_savings_brl,
            COUNT(*) FILTER (WHERE tca.colocation_score >= 70) AS high_opportunity,
            COUNT(*) FILTER (WHERE tca.colocation_score >= 50 AND tca.colocation_score < 70) AS medium_opportunity,
            COUNT(*) FILTER (WHERE tca.colocation_score < 50) AS low_opportunity
        FROM tower_colocation_analysis tca
        LEFT JOIN admin_level_2 a2 ON a2.id = tca.l2_id
        LEFT JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        {where_clause}
    """)

    agg_row = (await db.execute(agg_sql, params)).fetchone()

    # Per-state breakdown
    state_where = ""
    if state:
        state_where = "WHERE a1.abbrev = :state"

    state_sql = text(f"""
        SELECT
            a1.abbrev AS state_abbrev,
            COUNT(*) AS towers_analyzed,
            ROUND(AVG(tca.colocation_score)::numeric, 2) AS avg_score,
            ROUND(SUM(tca.estimated_savings_brl)::numeric, 2) AS total_savings_brl,
            COUNT(*) FILTER (WHERE tca.colocation_score >= 70) AS high_opportunity
        FROM tower_colocation_analysis tca
        LEFT JOIN admin_level_2 a2 ON a2.id = tca.l2_id
        LEFT JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        {state_where}
        GROUP BY a1.abbrev
        ORDER BY avg_score DESC
    """)

    state_rows = (await db.execute(state_sql, params)).fetchall()

    return {
        "total_analyzed": agg_row.total_analyzed if agg_row else 0,
        "avg_colocation_score": float(agg_row.avg_score) if agg_row and agg_row.avg_score else 0,
        "max_colocation_score": agg_row.max_score if agg_row else 0,
        "min_colocation_score": agg_row.min_score if agg_row else 0,
        "total_estimated_savings_brl": float(agg_row.total_savings_brl) if agg_row and agg_row.total_savings_brl else 0,
        "opportunity_breakdown": {
            "high": agg_row.high_opportunity if agg_row else 0,
            "medium": agg_row.medium_opportunity if agg_row else 0,
            "low": agg_row.low_opportunity if agg_row else 0,
        },
        "by_state": [
            {
                "state_abbrev": sr.state_abbrev,
                "towers_analyzed": sr.towers_analyzed,
                "avg_score": float(sr.avg_score) if sr.avg_score else 0,
                "total_savings_brl": float(sr.total_savings_brl) if sr.total_savings_brl else 0,
                "high_opportunity": sr.high_opportunity,
            }
            for sr in state_rows
        ],
    }
