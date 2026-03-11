"""
ENLACE Speedtest Router

Endpoints for Ookla Speedtest open data: municipality stats, rankings,
tile-level heatmaps, and quarterly trend history.

Data source: Ookla Open Data (https://github.com/teamookla/ookla-open-data)
Tables: speedtest_tiles (tile-level), speedtest_municipality (aggregated)
"""

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/speedtest", tags=["speedtest"])


def _to_float(value: Any) -> float | None:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("/{municipality_id}")
async def speedtest_stats(
    municipality_id: int,
    quarter: Optional[str] = Query(
        None,
        description="Quarter in format 'YYYY-QN' (e.g. '2025-Q1'). Defaults to latest.",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Speedtest statistics for a municipality.

    Returns average download/upload speeds (Mbps), latency (ms),
    total tests, total devices, and percentile breakdowns for the
    specified or latest available quarter.
    """
    if quarter:
        sql = text("""
            SELECT
                sm.l2_id AS municipality_id,
                a2.name AS municipality_name,
                a1.abbrev AS state_abbrev,
                sm.quarter,
                sm.avg_download_mbps,
                sm.avg_upload_mbps,
                sm.avg_latency_ms,
                sm.total_tests,
                sm.total_devices,
                sm.p10_download_mbps,
                sm.p50_download_mbps,
                sm.p90_download_mbps
            FROM speedtest_municipality sm
            JOIN admin_level_2 a2 ON sm.l2_id = a2.id
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            WHERE sm.l2_id = :municipality_id
              AND sm.quarter = :quarter
        """)
        result = await db.execute(
            sql, {"municipality_id": municipality_id, "quarter": quarter}
        )
    else:
        sql = text("""
            SELECT
                sm.l2_id AS municipality_id,
                a2.name AS municipality_name,
                a1.abbrev AS state_abbrev,
                sm.quarter,
                sm.avg_download_mbps,
                sm.avg_upload_mbps,
                sm.avg_latency_ms,
                sm.total_tests,
                sm.total_devices,
                sm.p10_download_mbps,
                sm.p50_download_mbps,
                sm.p90_download_mbps
            FROM speedtest_municipality sm
            JOIN admin_level_2 a2 ON sm.l2_id = a2.id
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            WHERE sm.l2_id = :municipality_id
            ORDER BY sm.quarter DESC
            LIMIT 1
        """)
        result = await db.execute(sql, {"municipality_id": municipality_id})

    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="No speedtest data found for this municipality",
        )

    return {
        "municipality_id": row.municipality_id,
        "municipality_name": row.municipality_name,
        "state_abbrev": row.state_abbrev.strip() if row.state_abbrev else "",
        "quarter": row.quarter,
        "avg_download_mbps": _to_float(row.avg_download_mbps),
        "avg_upload_mbps": _to_float(row.avg_upload_mbps),
        "avg_latency_ms": _to_float(row.avg_latency_ms),
        "total_tests": int(row.total_tests or 0),
        "total_devices": int(row.total_devices or 0),
        "percentiles": {
            "p10_download_mbps": _to_float(row.p10_download_mbps),
            "p50_download_mbps": _to_float(row.p50_download_mbps),
            "p90_download_mbps": _to_float(row.p90_download_mbps),
        },
    }


@router.get("/ranking/")
async def speedtest_ranking(
    state: Optional[str] = Query(
        None,
        description="Filter by state abbreviation (e.g. 'SP', 'MG')",
    ),
    metric: str = Query(
        "download",
        description="Ranking metric: 'download', 'upload', or 'latency'",
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    quarter: Optional[str] = Query(
        None,
        description="Quarter in format 'YYYY-QN'. Defaults to latest.",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Municipality ranking by speedtest metric.

    Returns municipalities ranked by average download speed, upload speed,
    or latency for the specified or latest available quarter.
    """
    # Validate metric
    metric_map = {
        "download": ("avg_download_mbps", "DESC"),
        "upload": ("avg_upload_mbps", "DESC"),
        "latency": ("avg_latency_ms", "ASC"),  # Lower latency is better
    }
    if metric not in metric_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric. Choose from: {', '.join(metric_map.keys())}",
        )

    metric_col, sort_dir = metric_map[metric]

    # Use hardcoded SQL templates to avoid injection (metric_col from whitelist)
    _SQL_TEMPLATES = {
        "avg_download_mbps": {
            "DESC": {
                True: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND a1.abbrev = :state
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_download_mbps DESC
                    LIMIT :limit
                """),
                False: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_download_mbps DESC
                    LIMIT :limit
                """),
            },
        },
        "avg_upload_mbps": {
            "DESC": {
                True: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND a1.abbrev = :state
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_upload_mbps DESC
                    LIMIT :limit
                """),
                False: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_upload_mbps DESC
                    LIMIT :limit
                """),
            },
        },
        "avg_latency_ms": {
            "ASC": {
                True: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND a1.abbrev = :state
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_latency_ms ASC
                    LIMIT :limit
                """),
                False: text("""
                    SELECT
                        sm.l2_id AS municipality_id,
                        a2.name AS municipality_name,
                        a1.abbrev AS state_abbrev,
                        sm.quarter,
                        sm.avg_download_mbps,
                        sm.avg_upload_mbps,
                        sm.avg_latency_ms,
                        sm.total_tests,
                        sm.total_devices
                    FROM speedtest_municipality sm
                    JOIN admin_level_2 a2 ON sm.l2_id = a2.id
                    JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                    WHERE sm.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_municipality))
                      AND sm.total_tests >= 10
                    ORDER BY sm.avg_latency_ms ASC
                    LIMIT :limit
                """),
            },
        },
    }

    has_state = state is not None
    sql = _SQL_TEMPLATES[metric_col][sort_dir][has_state]

    params: dict[str, Any] = {"quarter": quarter, "limit": limit}
    if has_state:
        params["state"] = state.upper().strip()

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No speedtest ranking data found for the specified filters",
        )

    return {
        "quarter": rows[0].quarter if rows else None,
        "metric": metric,
        "count": len(rows),
        "ranking": [
            {
                "rank": idx + 1,
                "municipality_id": row.municipality_id,
                "municipality_name": row.municipality_name,
                "state_abbrev": row.state_abbrev.strip() if row.state_abbrev else "",
                "avg_download_mbps": _to_float(row.avg_download_mbps),
                "avg_upload_mbps": _to_float(row.avg_upload_mbps),
                "avg_latency_ms": _to_float(row.avg_latency_ms),
                "total_tests": int(row.total_tests or 0),
                "total_devices": int(row.total_devices or 0),
            }
            for idx, row in enumerate(rows)
        ],
    }


@router.get("/heatmap/")
async def speedtest_heatmap(
    bbox: str = Query(
        ...,
        description="Bounding box as 'west,south,east,north' (lng,lat,lng,lat)",
    ),
    quarter: Optional[str] = Query(
        None,
        description="Quarter in format 'YYYY-QN'. Defaults to latest.",
    ),
    limit: int = Query(5000, ge=1, le=50000, description="Maximum tiles to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Tile-level speedtest heatmap data within a bounding box.

    Returns a GeoJSON FeatureCollection with tile polygons and speed metrics,
    suitable for rendering as a choropleth heatmap layer. Download and upload
    speeds are converted from kbps to Mbps.
    """
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Expected 4 values")
        west, south, east, north = parts
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="bbox must be 4 comma-separated numbers: west,south,east,north",
        )

    sql = text("""
        SELECT
            st.quadkey,
            st.quarter,
            st.avg_d_kbps,
            st.avg_u_kbps,
            st.avg_lat_ms,
            st.tests,
            st.devices,
            ST_AsGeoJSON(st.geom) AS geojson
        FROM speedtest_tiles st
        WHERE st.quarter = COALESCE(:quarter, (SELECT MAX(quarter) FROM speedtest_tiles))
          AND st.geom IS NOT NULL
          AND ST_Intersects(
              st.geom,
              ST_MakeEnvelope(:west, :south, :east, :north, 4326)
          )
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "quarter": quarter,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "limit": limit,
        },
    )
    rows = result.fetchall()

    import json

    features = []
    for row in rows:
        try:
            geom = json.loads(row.geojson)
        except (json.JSONDecodeError, TypeError):
            continue

        # Convert kbps to Mbps for display
        avg_d_mbps = round(row.avg_d_kbps / 1000.0, 2) if row.avg_d_kbps else None
        avg_u_mbps = round(row.avg_u_kbps / 1000.0, 2) if row.avg_u_kbps else None

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "quadkey": row.quadkey,
                "quarter": row.quarter,
                "avg_download_mbps": avg_d_mbps,
                "avg_upload_mbps": avg_u_mbps,
                "avg_latency_ms": _to_float(row.avg_lat_ms),
                "tests": int(row.tests or 0),
                "devices": int(row.devices or 0),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "quarter": rows[0].quarter if rows else quarter,
            "tile_count": len(features),
            "bbox": [west, south, east, north],
        },
    }


@router.get("/history/{municipality_id}")
async def speedtest_history(
    municipality_id: int,
    limit: int = Query(12, ge=1, le=40, description="Maximum quarters to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Quarterly speedtest trend for a municipality.

    Returns time-series data of average download/upload speeds, latency,
    and test volumes across available quarters, ordered newest first.
    """
    sql = text("""
        SELECT
            sm.quarter,
            sm.avg_download_mbps,
            sm.avg_upload_mbps,
            sm.avg_latency_ms,
            sm.total_tests,
            sm.total_devices,
            sm.p10_download_mbps,
            sm.p50_download_mbps,
            sm.p90_download_mbps
        FROM speedtest_municipality sm
        WHERE sm.l2_id = :municipality_id
        ORDER BY sm.quarter DESC
        LIMIT :limit
    """)

    result = await db.execute(
        sql, {"municipality_id": municipality_id, "limit": limit}
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No speedtest history found for this municipality",
        )

    # Compute quarter-over-quarter change for download speed
    history = []
    for idx, row in enumerate(rows):
        entry = {
            "quarter": row.quarter,
            "avg_download_mbps": _to_float(row.avg_download_mbps),
            "avg_upload_mbps": _to_float(row.avg_upload_mbps),
            "avg_latency_ms": _to_float(row.avg_latency_ms),
            "total_tests": int(row.total_tests or 0),
            "total_devices": int(row.total_devices or 0),
            "percentiles": {
                "p10_download_mbps": _to_float(row.p10_download_mbps),
                "p50_download_mbps": _to_float(row.p50_download_mbps),
                "p90_download_mbps": _to_float(row.p90_download_mbps),
            },
            "download_change_pct": None,
        }

        # Calculate quarter-over-quarter change
        if idx < len(rows) - 1:
            prev = rows[idx + 1]
            if prev.avg_download_mbps and prev.avg_download_mbps > 0:
                change = (
                    (row.avg_download_mbps - prev.avg_download_mbps)
                    / prev.avg_download_mbps
                    * 100
                )
                entry["download_change_pct"] = round(float(change), 1)

        history.append(entry)

    return {
        "municipality_id": municipality_id,
        "quarters_available": len(history),
        "history": history,
    }
