"""
ENLACE Satellite Urban Growth Router

Endpoints for querying Sentinel-2 derived urban growth indices,
on-demand computation of satellite metrics for any municipality,
cross-referencing satellite data with IBGE census projections,
ranking municipalities by growth metrics, and retrieving composite
metadata.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/satellite", tags=["satellite"])


# ═══════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/indices — Annual satellite indices time series
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/indices")
async def satellite_indices(
    municipality_code: str,
    from_year: int = Query(2016, ge=2016, le=2030, description="Start year (inclusive)"),
    to_year: int = Query(2026, ge=2016, le=2030, description="End year (inclusive)"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Annual satellite indices time series for a municipality.

    Returns per-year NDVI, NDBI, MNDWI, BSI metrics along with
    built-up area and change statistics derived from Sentinel-2
    composites.
    """
    if from_year > to_year:
        raise HTTPException(
            status_code=400,
            detail=f"from_year ({from_year}) must be <= to_year ({to_year})",
        )

    sql = sa_text("""
        SELECT s.year, s.mean_ndvi, s.ndvi_std, s.mean_ndbi,
               s.built_up_area_km2, s.built_up_pct,
               s.mean_mndwi, s.water_area_km2,
               s.mean_bsi, s.bare_soil_area_km2,
               s.built_up_change_km2, s.built_up_change_pct,
               s.ndvi_change_pct, s.scenes_used
        FROM sentinel_urban_indices s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        WHERE a2.code = :code
          AND s.year BETWEEN :from_year AND :to_year
        ORDER BY s.year
    """)

    result = await db.execute(sql, {
        "code": municipality_code,
        "from_year": from_year,
        "to_year": to_year,
    })
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No satellite indices found for municipality {municipality_code} "
                f"between {from_year} and {to_year}"
            ),
        )

    return [
        {
            "year": row.year,
            "mean_ndvi": row.mean_ndvi,
            "ndvi_std": row.ndvi_std,
            "mean_ndbi": row.mean_ndbi,
            "built_up_area_km2": row.built_up_area_km2,
            "built_up_pct": row.built_up_pct,
            "mean_mndwi": row.mean_mndwi,
            "water_area_km2": row.water_area_km2,
            "mean_bsi": row.mean_bsi,
            "bare_soil_area_km2": row.bare_soil_area_km2,
            "built_up_change_km2": row.built_up_change_km2,
            "built_up_change_pct": row.built_up_change_pct,
            "ndvi_change_pct": row.ndvi_change_pct,
            "scenes_used": row.scenes_used,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/growth — Satellite vs. IBGE census comparison
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/growth")
async def satellite_growth(
    municipality_code: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Compare satellite-detected urban growth with IBGE census population.

    Returns satellite growth metrics, IBGE population projections,
    and a correlation summary combining both data sources.
    """
    # Fetch satellite growth data
    sat_sql = sa_text("""
        SELECT s.year, s.built_up_area_km2, s.built_up_pct,
               s.built_up_change_pct, s.mean_ndvi
        FROM sentinel_urban_indices s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        WHERE a2.code = :code
        ORDER BY s.year
    """)

    sat_result = await db.execute(sat_sql, {"code": municipality_code})
    sat_rows = sat_result.fetchall()

    if not sat_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No satellite data found for municipality {municipality_code}",
        )

    satellite_growth_list = [
        {
            "year": row.year,
            "built_up_area_km2": row.built_up_area_km2,
            "built_up_pct": row.built_up_pct,
            "built_up_change_pct": row.built_up_change_pct,
            "mean_ndvi": row.mean_ndvi,
        }
        for row in sat_rows
    ]

    # Fetch IBGE population projections (table may not exist)
    ibge_growth_list: list[dict[str, Any]] = []
    try:
        ibge_sql = sa_text("""
            SELECT pp.year, pp.projected_population AS population
            FROM population_projections pp
            JOIN admin_level_2 a2 ON a2.id = pp.l2_id
            WHERE a2.code = :code
            ORDER BY pp.year
        """)
        ibge_result = await db.execute(ibge_sql, {"code": municipality_code})
        ibge_rows = ibge_result.fetchall()
        ibge_growth_list = [
            {"year": row.year, "population": row.population}
            for row in ibge_rows
        ]
    except Exception:
        # population_projections table may not exist yet; return empty list
        ibge_growth_list = []

    # Build correlation summary from municipality metadata + satellite averages
    summary_sql = sa_text("""
        SELECT a2.population, a2.area_km2
        FROM admin_level_2 a2
        WHERE a2.code = :code
    """)
    summary_result = await db.execute(summary_sql, {"code": municipality_code})
    summary_row = summary_result.fetchone()

    # Compute average annual built-up change from satellite data
    change_values = [
        r["built_up_change_pct"]
        for r in satellite_growth_list
        if r["built_up_change_pct"] is not None
    ]
    avg_change = (
        round(sum(change_values) / len(change_values), 4)
        if change_values
        else None
    )

    correlation_summary: dict[str, Any] = {
        "avg_annual_built_up_change_pct": avg_change,
        "ibge_population": summary_row.population if summary_row else None,
        "area_km2": summary_row.area_km2 if summary_row else None,
    }

    return {
        "satellite_growth": satellite_growth_list,
        "ibge_growth": ibge_growth_list,
        "correlation_summary": correlation_summary,
    }


# ═══════════════════════════════════════════════════════════════════════
# GET /ranking — Rank municipalities by satellite-detected urban growth
# ═══════════════════════════════════════════════════════════════════════


@router.get("/ranking")
async def satellite_ranking(
    state: Optional[str] = Query(None, description="State abbreviation filter (e.g. SP, MG)"),
    metric: str = Query(
        "built_up_change_pct",
        description="Metric to rank by",
    ),
    years: int = Query(3, ge=1, le=10, description="Number of recent years to average"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Rank municipalities by satellite-detected urban growth.

    Groups by municipality, averages the selected metric over the most
    recent N years, and orders by the average descending. Optionally
    filters by state abbreviation.
    """
    # Whitelist allowed metrics to prevent SQL injection
    allowed_metrics = {
        "built_up_change_pct",
        "built_up_change_km2",
        "built_up_area_km2",
        "built_up_pct",
        "mean_ndvi",
        "mean_ndbi",
        "mean_mndwi",
        "mean_bsi",
        "ndvi_change_pct",
    }

    if metric not in allowed_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric}'. Allowed: {sorted(allowed_metrics)}",
        )

    where_parts = []
    params: dict[str, Any] = {"years": years, "limit": limit}

    if state:
        where_parts.append("a1.code = :state")
        params["state"] = state.upper()

    where_clause = f"AND {' AND '.join(where_parts)}" if where_parts else ""

    sql = sa_text(f"""
        WITH recent_years AS (
            SELECT DISTINCT s.year
            FROM sentinel_urban_indices s
            ORDER BY s.year DESC
            LIMIT :years
        )
        SELECT a2.code AS municipality_code,
               a2.name AS municipality_name,
               a1.code AS state_code,
               a2.population,
               a2.area_km2,
               AVG(s.{metric}) AS avg_metric,
               COUNT(s.year) AS data_points
        FROM sentinel_urban_indices s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE s.year IN (SELECT year FROM recent_years)
              {where_clause}
        GROUP BY a2.code, a2.name, a1.code, a2.population, a2.area_km2
        ORDER BY avg_metric DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return []

    return [
        {
            "municipality_code": row.municipality_code,
            "municipality_name": row.municipality_name,
            "state_code": row.state_code,
            "population": row.population,
            "area_km2": row.area_km2,
            "avg_metric": round(float(row.avg_metric), 6) if row.avg_metric is not None else None,
            "metric": metric,
            "years_averaged": row.data_points,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/composite/{year} — Composite metadata
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/composite/{year}")
async def satellite_composite(
    municipality_code: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Get metadata for available satellite composites for a municipality and year.

    Returns a list of composite types (e.g. true_color, ndvi, ndbi) with
    filepath, resolution, and a tile URL template for rendering on maps.
    """
    sql = sa_text("""
        SELECT sc.composite_type, sc.filepath, sc.resolution_m,
               sc.bbox_north, sc.bbox_south, sc.bbox_east, sc.bbox_west,
               sc.file_size_mb, sc.created_at
        FROM sentinel_composites sc
        JOIN admin_level_2 a2 ON a2.id = sc.l2_id
        WHERE a2.code = :code
          AND sc.year = :year
        ORDER BY sc.composite_type
    """)

    result = await db.execute(sql, {"code": municipality_code, "year": year})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No satellite composites found for municipality "
                f"{municipality_code} in {year}"
            ),
        )

    return [
        {
            "composite_type": row.composite_type,
            "filepath": row.filepath,
            "resolution_m": row.resolution_m,
            "bbox": {
                "north": row.bbox_north,
                "south": row.bbox_south,
                "east": row.bbox_east,
                "west": row.bbox_west,
            } if all(
                v is not None
                for v in [row.bbox_north, row.bbox_south, row.bbox_east, row.bbox_west]
            ) else None,
            "file_size_mb": row.file_size_mb,
            "created_at": str(row.created_at) if row.created_at else None,
            "tile_url": f"/api/v1/tiles/{municipality_code}/{year}/{row.composite_type}/{{z}}/{{x}}/{{y}}.png",
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# POST /{municipality_code}/compute — On-demand satellite analysis
# ═══════════════════════════════════════════════════════════════════════

# In-memory set tracking which municipalities are currently being computed
_computing: set[str] = set()

START_YEAR = 2016


def _compute_municipality_sync(
    municipality_code: str,
    name: str,
    l2_id: int,
    geojson_str: str,
    area_km2: float,
    db_url: str,
) -> list[dict]:
    """Run GEE computation for a municipality across all years (blocking).

    Called from a thread pool to avoid blocking the async event loop.
    Returns the list of computed year rows.
    """
    import psycopg2
    from psycopg2.extras import execute_values

    try:
        import ee
        from python.pipeline.gee.sentinel_compute import (
            _adaptive_scale,
            _build_annual_composite,
            _reduce_to_stats,
            initialize_gee,
        )
    except ImportError as exc:
        raise RuntimeError(
            "earthengine-api is required for on-demand satellite analysis"
        ) from exc

    initialize_gee()

    geojson = json.loads(geojson_str) if geojson_str else None
    current_year = datetime.utcnow().year
    years = list(range(START_YEAR, current_year + 1))
    bbox_placeholder = [0, 0, 0, 0]  # Not used when geojson is provided

    results: list[dict] = []

    for year in years:
        try:
            composite = _build_annual_composite(
                bbox_placeholder, year, geojson=geojson
            )
            stats = _reduce_to_stats(
                composite, bbox_placeholder, municipality_code, year,
                geojson=geojson, area_km2=area_km2,
            )
            props = stats.getInfo()["properties"]

            results.append({
                "year": year,
                "ndvi_mean": props.get("ndvi_mean"),
                "ndbi_mean": props.get("ndbi_mean"),
                "mndwi_mean": props.get("mndwi_mean"),
                "bsi_mean": props.get("bsi_mean"),
                "built_up_area_km2": props.get("builtup_area_km2"),
                "built_up_pct": props.get("builtup_pct"),
            })
            logger.info(
                "Computed %s/%d: NDVI=%.3f built=%.1f%%",
                municipality_code, year,
                props.get("ndvi_mean") or 0,
                props.get("builtup_pct") or 0,
            )
        except Exception:
            logger.exception(
                "Failed to compute %s/%d", municipality_code, year
            )

    if not results:
        return results

    # Compute year-over-year changes
    results.sort(key=lambda r: r["year"])
    for i, row in enumerate(results):
        if i == 0:
            row["built_up_change_km2"] = None
            row["built_up_change_pct"] = None
            row["ndvi_change_pct"] = None
        else:
            prev = results[i - 1]
            pa = prev.get("built_up_area_km2")
            ca = row.get("built_up_area_km2")
            pn = prev.get("ndvi_mean")
            cn = row.get("ndvi_mean")

            row["built_up_change_km2"] = (
                (ca - pa) if ca is not None and pa is not None else None
            )
            row["built_up_change_pct"] = (
                ((ca - pa) / pa * 100) if ca and pa and pa > 0 else None
            )
            row["ndvi_change_pct"] = (
                ((cn - pn) / abs(pn) * 100) if cn is not None and pn and pn != 0 else None
            )

    # Persist to database
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    try:
        values = [
            (
                l2_id, r["year"],
                r.get("ndvi_mean"), None,  # ndvi_std
                r.get("ndbi_mean"),
                r.get("built_up_area_km2"), r.get("built_up_pct"),
                r.get("mndwi_mean"), None,  # water_area_km2
                r.get("bsi_mean"), None,  # bare_soil_area_km2
                r.get("built_up_change_km2"), r.get("built_up_change_pct"),
                r.get("ndvi_change_pct"),
            )
            for r in results
        ]
        execute_values(
            cur,
            """
            INSERT INTO sentinel_urban_indices (
                l2_id, year, mean_ndvi, ndvi_std, mean_ndbi,
                built_up_area_km2, built_up_pct,
                mean_mndwi, water_area_km2,
                mean_bsi, bare_soil_area_km2,
                built_up_change_km2, built_up_change_pct, ndvi_change_pct
            ) VALUES %s
            ON CONFLICT (l2_id, year) DO UPDATE SET
                mean_ndvi = EXCLUDED.mean_ndvi,
                mean_ndbi = EXCLUDED.mean_ndbi,
                built_up_area_km2 = EXCLUDED.built_up_area_km2,
                built_up_pct = EXCLUDED.built_up_pct,
                mean_mndwi = EXCLUDED.mean_mndwi,
                mean_bsi = EXCLUDED.mean_bsi,
                built_up_change_km2 = EXCLUDED.built_up_change_km2,
                built_up_change_pct = EXCLUDED.built_up_change_pct,
                ndvi_change_pct = EXCLUDED.ndvi_change_pct,
                created_at = NOW()
            """,
            values,
            template="(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        )
        conn.commit()
        logger.info(
            "Cached %d years for %s (%s)", len(results), name, municipality_code
        )
    finally:
        cur.close()
        conn.close()

    return results


@router.post("/{municipality_code}/compute")
async def compute_satellite_analysis(
    municipality_code: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute 10-year satellite growth analysis for a municipality on demand.

    - Returns cached data instantly if already computed.
    - If not cached, runs GEE computation (~30s per year, ~5 min total).
    - Results are persisted so subsequent requests are instant.
    """
    # 1) Check cache
    cached_sql = sa_text("""
        SELECT s.year, s.mean_ndvi, s.mean_ndbi, s.mean_mndwi, s.mean_bsi,
               s.built_up_area_km2, s.built_up_pct,
               s.built_up_change_km2, s.built_up_change_pct, s.ndvi_change_pct
        FROM sentinel_urban_indices s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        WHERE a2.code = :code
        ORDER BY s.year
    """)
    result = await db.execute(cached_sql, {"code": municipality_code})
    cached = result.fetchall()

    if cached and len(cached) >= 3:
        return {
            "status": "cached",
            "municipality_code": municipality_code,
            "years_computed": len(cached),
            "data": [
                {
                    "year": r.year,
                    "ndvi_mean": r.mean_ndvi,
                    "ndbi_mean": r.mean_ndbi,
                    "mndwi_mean": r.mean_mndwi,
                    "bsi_mean": r.mean_bsi,
                    "built_up_area_km2": r.built_up_area_km2,
                    "built_up_pct": r.built_up_pct,
                    "built_up_change_km2": r.built_up_change_km2,
                    "built_up_change_pct": r.built_up_change_pct,
                    "ndvi_change_pct": r.ndvi_change_pct,
                }
                for r in cached
            ],
        }

    # 2) Check if already computing
    if municipality_code in _computing:
        return {
            "status": "computing",
            "municipality_code": municipality_code,
            "message": "Análise satelital em andamento. Tente novamente em alguns minutos.",
        }

    # 3) Fetch municipality geometry
    geo_sql = sa_text("""
        SELECT a2.id, a2.name, a2.area_km2,
               ST_AsGeoJSON(ST_Simplify(a2.geom, 0.01)) AS geojson
        FROM admin_level_2 a2
        WHERE a2.code = :code AND a2.geom IS NOT NULL
    """)
    geo_result = await db.execute(geo_sql, {"code": municipality_code})
    geo_row = geo_result.fetchone()

    if not geo_row:
        raise HTTPException(
            status_code=404,
            detail=f"Municipality {municipality_code} not found or has no geometry",
        )

    # 4) Build sync DB URL for the thread
    from python.api.config import settings
    db_url = settings.database_sync_url

    # 5) Run computation in thread pool
    _computing.add(municipality_code)
    try:
        data = await asyncio.to_thread(
            _compute_municipality_sync,
            municipality_code,
            geo_row.name,
            geo_row.id,
            geo_row.geojson,
            float(geo_row.area_km2 or 0),
            db_url,
        )
    finally:
        _computing.discard(municipality_code)

    if not data:
        raise HTTPException(
            status_code=500,
            detail="Satellite computation failed. Check GEE credentials.",
        )

    return {
        "status": "computed",
        "municipality_code": municipality_code,
        "years_computed": len(data),
        "data": data,
    }
