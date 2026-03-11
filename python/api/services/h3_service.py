"""H3 hexagonal grid service for spatial analytics.

Provides functions to query, compute, and aggregate H3 hexagonal cells
for municipalities. Uses the PostgreSQL h3 extension (h3_postgis 4.1.3)
for spatial operations and falls back to the Python h3 library (4.4.2)
for polyfill when needed.

Key operations:
  - Query pre-computed H3 cells within a bounding box
  - Compute H3 grid for a municipality by polyfilling its geometry
  - Aggregate subscriber and tower data per hexagon
"""

import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Valid metrics that can be used for cell queries
VALID_METRICS = {
    "subscribers",
    "tower_count",
    "building_count",
    "building_area_m2",
    "population_estimate",
    "penetration_pct",
    "growth_pct_12m",
    "avg_download_mbps",
}

# Valid H3 resolutions for telecom analysis (5 = ~252 km2, 7 = ~5.16 km2, 9 = ~0.105 km2)
VALID_RESOLUTIONS = range(4, 11)


def _to_float(value: Any) -> Optional[float]:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


async def get_h3_cells(
    db: AsyncSession,
    bbox: str,
    resolution: int = 7,
    metric: str = "subscribers",
) -> dict[str, Any]:
    """Query H3 cells within a bounding box at a given resolution.

    Returns a GeoJSON FeatureCollection with H3 cell polygons and the
    requested metric value per cell.

    Args:
        db: Async SQLAlchemy session.
        bbox: Bounding box as 'west,south,east,north' (lng,lat,lng,lat).
        resolution: H3 resolution (4-10). Default 7.
        metric: Metric column to include. Default 'subscribers'.

    Returns:
        GeoJSON FeatureCollection with H3 cell polygons.

    Raises:
        ValueError: If bbox format is invalid, metric is unknown, or
            resolution is out of range.
    """
    # Parse bbox
    try:
        parts = [float(x.strip()) for x in bbox.split(",")]
        if len(parts) != 4:
            raise ValueError("Expected 4 values")
        west, south, east, north = parts
    except (ValueError, TypeError):
        raise ValueError(
            "bbox must be 4 comma-separated numbers: west,south,east,north"
        )

    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(f"Resolution must be between 4 and 10, got {resolution}")

    if metric not in VALID_METRICS:
        raise ValueError(
            f"Invalid metric '{metric}'. Choose from: {', '.join(sorted(VALID_METRICS))}"
        )

    # Use a per-metric SQL template to avoid dynamic column interpolation.
    # Each metric column is hardcoded in its own query variant.
    _SQL_BY_METRIC = {
        "subscribers": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.subscribers AS metric_value,
                hc.tower_count,
                hc.population_estimate,
                hc.penetration_pct,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.subscribers DESC NULLS LAST
            LIMIT 5000
        """),
        "tower_count": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.tower_count AS metric_value,
                hc.subscribers,
                hc.population_estimate,
                hc.penetration_pct,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.tower_count DESC NULLS LAST
            LIMIT 5000
        """),
        "building_count": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.building_count AS metric_value,
                hc.subscribers,
                hc.population_estimate,
                hc.penetration_pct,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.building_count DESC NULLS LAST
            LIMIT 5000
        """),
        "building_area_m2": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.building_area_m2 AS metric_value,
                hc.subscribers,
                hc.population_estimate,
                hc.penetration_pct,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.building_area_m2 DESC NULLS LAST
            LIMIT 5000
        """),
        "population_estimate": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.population_estimate AS metric_value,
                hc.subscribers,
                hc.tower_count,
                hc.penetration_pct,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.population_estimate DESC NULLS LAST
            LIMIT 5000
        """),
        "penetration_pct": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.penetration_pct AS metric_value,
                hc.subscribers,
                hc.tower_count,
                hc.population_estimate,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.penetration_pct DESC NULLS LAST
            LIMIT 5000
        """),
        "growth_pct_12m": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.growth_pct_12m AS metric_value,
                hc.subscribers,
                hc.tower_count,
                hc.population_estimate,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.growth_pct_12m DESC NULLS LAST
            LIMIT 5000
        """),
        "avg_download_mbps": text("""
            SELECT
                hc.h3_index,
                hc.resolution,
                hc.l2_id,
                hc.avg_download_mbps AS metric_value,
                hc.subscribers,
                hc.tower_count,
                hc.population_estimate,
                ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
            FROM h3_cells hc
            WHERE hc.resolution = :resolution
              AND h3_cell_to_boundary_geometry(hc.h3_index::h3index) &&
                  ST_MakeEnvelope(:west, :south, :east, :north, 4326)
            ORDER BY hc.avg_download_mbps DESC NULLS LAST
            LIMIT 5000
        """),
    }

    sql = _SQL_BY_METRIC[metric]

    result = await db.execute(
        sql,
        {
            "resolution": resolution,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
    )
    rows = result.fetchall()

    import json

    features = []
    for row in rows:
        geometry = json.loads(row.geojson)
        properties: dict[str, Any] = {
            "h3_index": row.h3_index,
            "resolution": row.resolution,
            "l2_id": row.l2_id,
            "metric": metric,
            "value": _to_float(row.metric_value),
        }
        # Add context fields when available
        for attr in ("subscribers", "tower_count", "population_estimate", "penetration_pct"):
            val = getattr(row, attr, None)
            if val is not None and attr != metric:
                properties[attr] = _to_float(val) if isinstance(val, (Decimal, float)) else int(val)

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "resolution": resolution,
            "metric": metric,
            "cell_count": len(features),
        },
    }


async def compute_municipality_h3(
    db: AsyncSession,
    municipality_id: int,
    resolution: int = 7,
) -> dict[str, Any]:
    """Compute H3 grid for a municipality by polyfilling its geometry.

    Uses the PostgreSQL h3_polygon_to_cells function to generate H3 cells
    that cover the municipality boundary. Then aggregates broadband
    subscriber and base station data per hexagonal cell.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id.
        resolution: H3 resolution (4-10). Default 7.

    Returns:
        Summary dict with cell count, aggregated stats, and the
        municipality name.

    Raises:
        ValueError: If resolution is out of range or municipality not found.
    """
    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(f"Resolution must be between 4 and 10, got {resolution}")

    # Verify municipality exists and has geometry
    mun_sql = text("""
        SELECT a2.id, a2.code, a2.name, a2.population,
               a1.abbrev AS state_abbrev,
               ST_GeometryType(a2.geom) AS geom_type
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE a2.id = :municipality_id
    """)
    mun_result = await db.execute(mun_sql, {"municipality_id": municipality_id})
    mun_row = mun_result.fetchone()

    if not mun_row:
        raise ValueError(f"Municipality with id={municipality_id} not found")

    if not mun_row.geom_type:
        raise ValueError(
            f"Municipality '{mun_row.name}' (id={municipality_id}) has no geometry"
        )

    # Step 1: Generate H3 cells covering the municipality using PostgreSQL
    # h3_polygon_to_cells works with simple geometries; for MultiPolygon we
    # need to ST_Dump first to iterate individual polygons.
    polyfill_sql = text("""
        INSERT INTO h3_cells (h3_index, resolution, l2_id, computed_at)
        SELECT DISTINCT
            cell::text,
            :resolution,
            :municipality_id,
            NOW()
        FROM admin_level_2 a2,
             LATERAL ST_Dump(a2.geom) AS dump,
             LATERAL h3_polygon_to_cells(dump.geom, :resolution) AS cell
        WHERE a2.id = :municipality_id
        ON CONFLICT (h3_index, resolution) DO UPDATE
        SET l2_id = :municipality_id,
            computed_at = NOW()
        RETURNING h3_index
    """)
    polyfill_result = await db.execute(
        polyfill_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )
    cell_indices = [row.h3_index for row in polyfill_result.fetchall()]
    cell_count = len(cell_indices)

    if cell_count == 0:
        return {
            "municipality_id": municipality_id,
            "municipality_name": mun_row.name,
            "state_abbrev": mun_row.state_abbrev,
            "resolution": resolution,
            "cell_count": 0,
            "message": "No H3 cells generated — geometry may be too small for this resolution",
        }

    # Step 2: Aggregate subscriber counts per H3 cell.
    # Subscribers are stored at municipality level (l2_id), so we distribute
    # them evenly across cells within that municipality as an estimate.
    subs_sql = text("""
        UPDATE h3_cells hc
        SET subscribers = sub_data.per_cell_subs
        FROM (
            SELECT
                hc2.id AS cell_id,
                COALESCE(
                    (SELECT SUM(bs.subscribers)
                     FROM broadband_subscribers bs
                     WHERE bs.l2_id = :municipality_id
                       AND bs.year_month = (
                           SELECT MAX(bs2.year_month)
                           FROM broadband_subscribers bs2
                           WHERE bs2.l2_id = :municipality_id
                       )
                    ) / NULLIF(
                        (SELECT COUNT(*) FROM h3_cells
                         WHERE l2_id = :municipality_id AND resolution = :resolution),
                        0
                    ),
                    0
                ) AS per_cell_subs
            FROM h3_cells hc2
            WHERE hc2.l2_id = :municipality_id
              AND hc2.resolution = :resolution
        ) sub_data
        WHERE hc.id = sub_data.cell_id
    """)
    await db.execute(
        subs_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )

    # Step 3: Count towers per H3 cell using the PostgreSQL h3 extension.
    # For each base station, compute its H3 cell index and count per cell.
    towers_sql = text("""
        UPDATE h3_cells hc
        SET tower_count = tower_data.cnt
        FROM (
            SELECT
                h3_lat_lng_to_cell(
                    ST_MakePoint(bs.longitude, bs.latitude)::point,
                    :resolution
                )::text AS cell_index,
                COUNT(*) AS cnt
            FROM base_stations bs
            JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
            WHERE a2.id = :municipality_id
            GROUP BY cell_index
        ) tower_data
        WHERE hc.h3_index = tower_data.cell_index
          AND hc.resolution = :resolution
    """)
    await db.execute(
        towers_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )

    # Step 4: Distribute population estimate across cells.
    pop_sql = text("""
        UPDATE h3_cells hc
        SET population_estimate = pop_data.per_cell_pop
        FROM (
            SELECT
                hc2.id AS cell_id,
                COALESCE(
                    (SELECT a2.population
                     FROM admin_level_2 a2
                     WHERE a2.id = :municipality_id
                    ) / NULLIF(
                        (SELECT COUNT(*) FROM h3_cells
                         WHERE l2_id = :municipality_id AND resolution = :resolution),
                        0
                    ),
                    0
                ) AS per_cell_pop
            FROM h3_cells hc2
            WHERE hc2.l2_id = :municipality_id
              AND hc2.resolution = :resolution
        ) pop_data
        WHERE hc.id = pop_data.cell_id
    """)
    await db.execute(
        pop_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )

    # Step 5: Compute penetration percentage per cell.
    pen_sql = text("""
        UPDATE h3_cells hc
        SET penetration_pct = CASE
            WHEN hc.population_estimate > 0 AND hc.subscribers > 0
            THEN ROUND((hc.subscribers::numeric / hc.population_estimate * 100), 2)
            ELSE 0
        END
        WHERE hc.l2_id = :municipality_id
          AND hc.resolution = :resolution
    """)
    await db.execute(
        pen_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )

    # Flush to ensure all updates are visible
    await db.flush()

    # Step 6: Gather summary statistics
    summary_sql = text("""
        SELECT
            COUNT(*) AS cell_count,
            SUM(hc.subscribers) AS total_subscribers,
            SUM(hc.tower_count) AS total_towers,
            SUM(hc.population_estimate) AS total_population,
            AVG(hc.penetration_pct) AS avg_penetration,
            COUNT(*) FILTER (WHERE hc.tower_count > 0) AS cells_with_towers,
            COUNT(*) FILTER (WHERE hc.subscribers > 0) AS cells_with_subs
        FROM h3_cells hc
        WHERE hc.l2_id = :municipality_id
          AND hc.resolution = :resolution
    """)
    summary_result = await db.execute(
        summary_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )
    summary = summary_result.fetchone()

    return {
        "municipality_id": municipality_id,
        "municipality_code": mun_row.code.strip() if mun_row.code else "",
        "municipality_name": mun_row.name,
        "state_abbrev": mun_row.state_abbrev,
        "resolution": resolution,
        "cell_count": summary.cell_count,
        "total_subscribers": int(summary.total_subscribers or 0),
        "total_towers": int(summary.total_towers or 0),
        "total_population": int(summary.total_population or 0),
        "avg_penetration_pct": _to_float(summary.avg_penetration),
        "cells_with_towers": int(summary.cells_with_towers or 0),
        "cells_with_subscribers": int(summary.cells_with_subs or 0),
        "coverage_ratio": round(
            (summary.cells_with_towers or 0) / summary.cell_count * 100, 2
        ) if summary.cell_count > 0 else 0,
    }


async def get_municipality_h3_analysis(
    db: AsyncSession,
    municipality_id: int,
    resolution: int = 7,
) -> dict[str, Any]:
    """Retrieve pre-computed H3 analysis for a municipality.

    Returns the H3 cells as a GeoJSON FeatureCollection along with
    aggregate statistics. Does NOT trigger computation — use
    ``compute_municipality_h3`` for that.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id.
        resolution: H3 resolution (4-10). Default 7.

    Returns:
        Dict with 'geojson' (FeatureCollection) and 'summary' stats.

    Raises:
        ValueError: If municipality not found or no cells computed.
    """
    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(f"Resolution must be between 4 and 10, got {resolution}")

    # Verify municipality
    mun_sql = text("""
        SELECT a2.id, a2.code, a2.name, a1.abbrev AS state_abbrev
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE a2.id = :municipality_id
    """)
    mun_result = await db.execute(mun_sql, {"municipality_id": municipality_id})
    mun_row = mun_result.fetchone()

    if not mun_row:
        raise ValueError(f"Municipality with id={municipality_id} not found")

    # Fetch all H3 cells for this municipality
    cells_sql = text("""
        SELECT
            hc.h3_index,
            hc.resolution,
            hc.subscribers,
            hc.tower_count,
            hc.building_count,
            hc.building_area_m2,
            hc.population_estimate,
            hc.penetration_pct,
            hc.growth_pct_12m,
            hc.avg_download_mbps,
            hc.computed_at,
            ST_AsGeoJSON(h3_cell_to_boundary_geometry(hc.h3_index::h3index)) AS geojson
        FROM h3_cells hc
        WHERE hc.l2_id = :municipality_id
          AND hc.resolution = :resolution
        ORDER BY hc.subscribers DESC NULLS LAST
    """)
    cells_result = await db.execute(
        cells_sql,
        {"municipality_id": municipality_id, "resolution": resolution},
    )
    rows = cells_result.fetchall()

    if not rows:
        raise ValueError(
            f"No H3 cells found for municipality '{mun_row.name}' "
            f"at resolution {resolution}. Trigger computation first via POST."
        )

    import json

    features = []
    total_subs = 0
    total_towers = 0
    total_pop = 0
    cells_with_towers = 0

    for row in rows:
        geometry = json.loads(row.geojson)
        subs = int(row.subscribers or 0)
        towers = int(row.tower_count or 0)
        pop = int(row.population_estimate or 0)

        total_subs += subs
        total_towers += towers
        total_pop += pop
        if towers > 0:
            cells_with_towers += 1

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "h3_index": row.h3_index,
                "subscribers": subs,
                "tower_count": towers,
                "building_count": int(row.building_count or 0),
                "building_area_m2": _to_float(row.building_area_m2),
                "population_estimate": pop,
                "penetration_pct": _to_float(row.penetration_pct),
                "growth_pct_12m": _to_float(row.growth_pct_12m),
                "avg_download_mbps": _to_float(row.avg_download_mbps),
                "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            },
        })

    cell_count = len(features)

    return {
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
        "summary": {
            "municipality_id": municipality_id,
            "municipality_code": mun_row.code.strip() if mun_row.code else "",
            "municipality_name": mun_row.name,
            "state_abbrev": mun_row.state_abbrev,
            "resolution": resolution,
            "cell_count": cell_count,
            "total_subscribers": total_subs,
            "total_towers": total_towers,
            "total_population": total_pop,
            "cells_with_towers": cells_with_towers,
            "coverage_ratio": round(
                cells_with_towers / cell_count * 100, 2
            ) if cell_count > 0 else 0,
        },
    }
