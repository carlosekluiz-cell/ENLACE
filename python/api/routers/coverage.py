"""
ENLACE Coverage Validation Router

Endpoints for cross-referencing tower data from multiple sources
(Anatel/OSM base_stations, OpenCelliD), identifying coverage gaps,
and computing validation confidence scores.
"""

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/coverage", tags=["coverage"])

# MNC -> operator name mapping for MCC 724 (Brazil)
MNC_OPERATOR_MAP = {
    2: "TIM",
    3: "TIM",
    4: "TIM",
    5: "Claro",
    6: "Vivo",
    10: "Vivo",
    11: "Vivo",
    23: "Vivo",
    31: "Oi",
    32: "Oi",
}


def _to_float(value: Any) -> float | None:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


# -----------------------------------------------------------------------
# GET /coverage/{municipality_id}/validation
# -----------------------------------------------------------------------

@router.get("/{municipality_id}/validation")
async def coverage_validation(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Coverage validation statistics for a municipality.

    Returns the latest cross-reference between Anatel/OSM base_stations
    and OpenCelliD towers, including match rate, coverage confidence,
    and estimated gap metrics.
    """
    sql = text("""
        SELECT
            cv.l2_id,
            al2.name AS municipality_name,
            al1.abbrev AS state_abbrev,
            cv.anatel_tower_count,
            cv.opencellid_tower_count,
            cv.osm_tower_count,
            cv.matched_count,
            cv.unmatched_opencellid,
            cv.coverage_confidence,
            cv.gap_area_km2,
            cv.gap_population,
            cv.computed_at
        FROM coverage_validation cv
        JOIN admin_level_2 al2 ON cv.l2_id = al2.id
        LEFT JOIN admin_level_1 al1 ON al2.l1_id = al1.id
        WHERE cv.l2_id = :municipality_id
        ORDER BY cv.computed_at DESC
        LIMIT 1
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No coverage validation found for municipality {municipality_id}. "
                   f"Trigger computation via POST /coverage/{municipality_id}/compute.",
        )

    match_rate = (
        round(row.matched_count / row.opencellid_tower_count * 100, 1)
        if row.opencellid_tower_count and row.opencellid_tower_count > 0
        else None
    )

    return {
        "municipality_id": row.l2_id,
        "municipality_name": row.municipality_name,
        "state_abbrev": row.state_abbrev,
        "anatel_tower_count": row.anatel_tower_count or 0,
        "opencellid_tower_count": row.opencellid_tower_count or 0,
        "osm_tower_count": row.osm_tower_count or 0,
        "matched_count": row.matched_count or 0,
        "unmatched_opencellid": row.unmatched_opencellid or 0,
        "match_rate_pct": match_rate,
        "coverage_confidence": _to_float(row.coverage_confidence),
        "gap_area_km2": _to_float(row.gap_area_km2),
        "gap_population": row.gap_population or 0,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }


# -----------------------------------------------------------------------
# GET /coverage/gaps
# -----------------------------------------------------------------------

@router.get("/gaps")
async def coverage_gaps(
    state: Optional[str] = Query(None, description="State abbreviation (e.g. SP, MG)"),
    min_population: int = Query(0, ge=0, description="Minimum gap_population threshold"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Municipalities with the largest coverage gaps.

    Returns municipalities ranked by gap_population descending, with optional
    filters for state and minimum population affected by coverage gaps.
    """
    where_parts = ["cv.gap_population >= :min_population"]
    params: dict[str, Any] = {"min_population": min_population, "limit": limit}

    if state:
        where_parts.append("al1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            cv.l2_id,
            al2.name AS municipality_name,
            al2.code AS municipality_code,
            al1.abbrev AS state_abbrev,
            al2.population,
            cv.anatel_tower_count,
            cv.opencellid_tower_count,
            cv.osm_tower_count,
            cv.matched_count,
            cv.unmatched_opencellid,
            cv.coverage_confidence,
            cv.gap_area_km2,
            cv.gap_population,
            cv.computed_at
        FROM coverage_validation cv
        JOIN admin_level_2 al2 ON cv.l2_id = al2.id
        LEFT JOIN admin_level_1 al1 ON al2.l1_id = al1.id
        WHERE {where_sql}
        ORDER BY cv.gap_population DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "municipality_id": row.l2_id,
            "municipality_name": row.municipality_name,
            "municipality_code": row.municipality_code.strip() if row.municipality_code else "",
            "state_abbrev": row.state_abbrev,
            "population": int(row.population) if row.population else None,
            "anatel_tower_count": row.anatel_tower_count or 0,
            "opencellid_tower_count": row.opencellid_tower_count or 0,
            "osm_tower_count": row.osm_tower_count or 0,
            "matched_count": row.matched_count or 0,
            "unmatched_opencellid": row.unmatched_opencellid or 0,
            "coverage_confidence": _to_float(row.coverage_confidence),
            "gap_area_km2": _to_float(row.gap_area_km2),
            "gap_population": row.gap_population or 0,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in rows
    ]


# -----------------------------------------------------------------------
# GET /coverage/{municipality_id}/towers
# -----------------------------------------------------------------------

@router.get("/{municipality_id}/towers")
async def coverage_towers(
    municipality_id: int,
    source: Optional[str] = Query(
        None, description="Filter by source: 'osm' (base_stations) or 'opencellid'"
    ),
    radio: Optional[str] = Query(None, description="Filter by radio type (e.g. LTE, UMTS, GSM)"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Combined tower data for a municipality from both base_stations (OSM/Anatel)
    and OpenCelliD sources.

    Returns a unified list with a 'source' field indicating the origin of each tower.
    """
    towers = []

    # Fetch from base_stations (OSM/Anatel) unless filtered to opencellid only
    if source is None or source == "osm":
        bs_sql = text("""
            SELECT
                bs.id,
                bs.latitude,
                bs.longitude,
                bs.technology,
                bs.frequency_mhz,
                p.name AS operator,
                'osm' AS source
            FROM base_stations bs
            LEFT JOIN providers p ON bs.provider_id = p.id
            WHERE EXISTS (
                SELECT 1 FROM admin_level_2 al2
                WHERE al2.id = :municipality_id
                  AND ST_Within(bs.geom, al2.geom)
            )
            ORDER BY bs.id
            LIMIT :limit
        """)
        bs_result = await db.execute(
            bs_sql, {"municipality_id": municipality_id, "limit": limit}
        )
        for row in bs_result.fetchall():
            towers.append({
                "id": row.id,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "technology": row.technology,
                "frequency_mhz": _to_float(row.frequency_mhz),
                "operator": row.operator,
                "radio": row.technology,
                "source": "osm",
                "matched": None,
            })

    # Fetch from OpenCelliD unless filtered to osm only
    if source is None or source == "opencellid":
        remaining = limit - len(towers)
        if remaining <= 0:
            remaining = limit

        oc_where_parts = ["oc.l2_id = :municipality_id"]
        oc_params: dict[str, Any] = {
            "municipality_id": municipality_id,
            "limit": remaining,
        }

        if radio:
            oc_where_parts.append("UPPER(oc.radio) = :radio")
            oc_params["radio"] = radio.upper()

        oc_where_sql = " AND ".join(oc_where_parts)

        oc_sql = text(f"""
            SELECT
                oc.id,
                oc.cell_id,
                oc.mnc,
                oc.lac,
                oc.radio,
                oc.latitude,
                oc.longitude,
                oc.range_m,
                oc.samples,
                oc.matched_base_station_id,
                'opencellid' AS source
            FROM opencellid_towers oc
            WHERE {oc_where_sql}
            ORDER BY oc.samples DESC
            LIMIT :limit
        """)
        oc_result = await db.execute(oc_sql, oc_params)
        for row in oc_result.fetchall():
            operator = MNC_OPERATOR_MAP.get(row.mnc, f"MNC-{row.mnc}")
            towers.append({
                "id": row.id,
                "cell_id": row.cell_id,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "technology": None,
                "frequency_mhz": None,
                "operator": operator,
                "radio": row.radio,
                "range_m": row.range_m,
                "samples": row.samples,
                "source": "opencellid",
                "matched": row.matched_base_station_id is not None,
            })

    if not towers:
        raise HTTPException(
            status_code=404,
            detail=f"No tower data found for municipality {municipality_id}",
        )

    return {
        "municipality_id": municipality_id,
        "total_count": len(towers),
        "towers": towers,
    }


# -----------------------------------------------------------------------
# POST /coverage/{municipality_id}/compute
# -----------------------------------------------------------------------

@router.post("/{municipality_id}/compute")
async def compute_coverage_validation(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Trigger coverage validation computation for a municipality.

    Cross-references tower data from base_stations (OSM/Anatel) and
    OpenCelliD, computes match rates, coverage confidence, and
    estimates gap area and population.
    """
    # Verify municipality exists
    check_sql = text("""
        SELECT id, name, area_km2, population
        FROM admin_level_2
        WHERE id = :municipality_id
    """)
    check_result = await db.execute(check_sql, {"municipality_id": municipality_id})
    municipality = check_result.fetchone()

    if not municipality:
        raise HTTPException(
            status_code=404,
            detail=f"Municipality {municipality_id} not found",
        )

    # Count OSM/Anatel base_stations in this municipality
    osm_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM base_stations bs
        WHERE EXISTS (
            SELECT 1 FROM admin_level_2 al2
            WHERE al2.id = :municipality_id
              AND ST_Within(bs.geom, al2.geom)
        )
    """)
    osm_result = await db.execute(osm_sql, {"municipality_id": municipality_id})
    osm_count = osm_result.scalar() or 0

    # Count OpenCelliD towers in this municipality
    oc_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM opencellid_towers
        WHERE l2_id = :municipality_id
    """)
    oc_result = await db.execute(oc_sql, {"municipality_id": municipality_id})
    oc_count = oc_result.scalar() or 0

    # Count matched OpenCelliD towers
    matched_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM opencellid_towers
        WHERE l2_id = :municipality_id
          AND matched_base_station_id IS NOT NULL
    """)
    matched_result = await db.execute(matched_sql, {"municipality_id": municipality_id})
    matched_count = matched_result.scalar() or 0

    unmatched_oc = oc_count - matched_count

    # Compute coverage confidence score (0-1)
    # Based on: data availability, match rate, and sample density
    total_towers = osm_count + oc_count
    if total_towers == 0:
        coverage_confidence = 0.0
    else:
        # Match rate contribution (higher = more confidence in data)
        match_rate = matched_count / oc_count if oc_count > 0 else 0.0

        # Source agreement contribution
        # If both sources have data, more confident
        source_factor = 1.0 if (osm_count > 0 and oc_count > 0) else 0.6

        # Density factor: more towers per area = more confidence
        area_km2 = float(municipality.area_km2) if municipality.area_km2 else 100.0
        density = total_towers / max(area_km2, 1.0)
        # Normalize: 0.1 tower/km2 = good coverage
        density_factor = min(density / 0.1, 1.0)

        coverage_confidence = round(
            0.4 * match_rate + 0.3 * source_factor + 0.3 * density_factor, 3
        )

    # Estimate gap area: municipality area minus estimated covered area
    # Each tower covers approximately pi * (range_m/1000)^2 km2
    # For unmatched OpenCelliD towers, assume they represent uncovered gaps
    gap_area_sql = text("""
        SELECT COALESCE(SUM(
            3.14159 * POWER(COALESCE(range_m, 1000) / 1000.0, 2)
        ), 0) AS covered_km2
        FROM opencellid_towers
        WHERE l2_id = :municipality_id
          AND matched_base_station_id IS NULL
    """)
    gap_area_result = await db.execute(gap_area_sql, {"municipality_id": municipality_id})
    unmatched_covered_km2 = float(gap_area_result.scalar() or 0)

    area_km2 = float(municipality.area_km2) if municipality.area_km2 else 0.0
    population = int(municipality.population) if municipality.population else 0

    # Gap area is the area these unmatched towers claim to cover
    # (areas that OpenCelliD sees but our base_stations don't)
    gap_area_km2 = min(unmatched_covered_km2, area_km2)

    # Estimate gap population proportionally
    gap_population = 0
    if area_km2 > 0 and population > 0:
        gap_population = int(population * gap_area_km2 / area_km2)

    # Anatel tower count = same as OSM for now (OSM data includes Anatel-attributed towers)
    anatel_tower_count = osm_count

    # Upsert into coverage_validation
    upsert_sql = text("""
        INSERT INTO coverage_validation
        (l2_id, anatel_tower_count, opencellid_tower_count, osm_tower_count,
         matched_count, unmatched_opencellid, coverage_confidence,
         gap_area_km2, gap_population, computed_at)
        VALUES
        (:l2_id, :anatel, :opencellid, :osm,
         :matched, :unmatched, :confidence,
         :gap_area, :gap_pop, NOW())
    """)

    await db.execute(upsert_sql, {
        "l2_id": municipality_id,
        "anatel": anatel_tower_count,
        "opencellid": oc_count,
        "osm": osm_count,
        "matched": matched_count,
        "unmatched": unmatched_oc,
        "confidence": coverage_confidence,
        "gap_area": round(gap_area_km2, 2),
        "gap_pop": gap_population,
    })

    return {
        "status": "computed",
        "municipality_id": municipality_id,
        "municipality_name": municipality.name,
        "anatel_tower_count": anatel_tower_count,
        "opencellid_tower_count": oc_count,
        "osm_tower_count": osm_count,
        "matched_count": matched_count,
        "unmatched_opencellid": unmatched_oc,
        "coverage_confidence": coverage_confidence,
        "gap_area_km2": round(gap_area_km2, 2),
        "gap_population": gap_population,
    }
