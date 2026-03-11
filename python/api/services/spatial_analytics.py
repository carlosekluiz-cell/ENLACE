"""
ENLACE Spatial Analytics Service

PostGIS advanced spatial analytics: ST_ClusterKMeans for tower clustering,
ST_VoronoiPolygons for coverage areas, ST_ConcaveHull for network footprints.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def cluster_towers(
    db: AsyncSession,
    num_clusters: int = 10,
    state: Optional[str] = None,
    technology: Optional[str] = None,
) -> dict[str, Any]:
    """Cluster base stations using ST_ClusterKMeans."""
    where_parts = ["bs.geom IS NOT NULL"]
    params: dict[str, Any] = {"num_clusters": num_clusters}

    if state:
        where_parts.append("""
            bs.id IN (
                SELECT bst.id FROM base_stations bst
                JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bst.geom)
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    if technology:
        where_parts.append("bs.technology = :tech")
        params["tech"] = technology

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH clustered AS (
            SELECT
                bs.id,
                bs.latitude,
                bs.longitude,
                bs.technology,
                bs.frequency_mhz,
                bs.provider_id,
                p.name AS provider_name,
                ST_ClusterKMeans(bs.geom, :num_clusters) OVER () AS cluster_id
            FROM base_stations bs
            LEFT JOIN providers p ON p.id = bs.provider_id
            WHERE {where_sql}
        )
        SELECT
            cluster_id,
            COUNT(*) AS tower_count,
            AVG(latitude) AS center_lat,
            AVG(longitude) AS center_lon,
            array_agg(DISTINCT technology) AS technologies,
            array_agg(DISTINCT provider_name) AS providers,
            MIN(latitude) AS min_lat, MAX(latitude) AS max_lat,
            MIN(longitude) AS min_lon, MAX(longitude) AS max_lon
        FROM clustered
        GROUP BY cluster_id
        ORDER BY tower_count DESC
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    clusters = []
    for row in rows:
        clusters.append({
            "cluster_id": row.cluster_id,
            "tower_count": row.tower_count,
            "center": {"lat": round(float(row.center_lat), 6), "lon": round(float(row.center_lon), 6)},
            "technologies": [t for t in (row.technologies or []) if t],
            "providers": [p for p in (row.providers or []) if p],
            "bounds": {
                "min_lat": float(row.min_lat), "max_lat": float(row.max_lat),
                "min_lon": float(row.min_lon), "max_lon": float(row.max_lon),
            },
        })

    return {
        "num_clusters": num_clusters,
        "state_filter": state,
        "technology_filter": technology,
        "total_towers": sum(c["tower_count"] for c in clusters),
        "clusters": clusters,
    }


async def voronoi_coverage(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Generate Voronoi polygons from base station positions for coverage areas."""
    where_parts = ["bs.geom IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("""
            bs.id IN (
                SELECT bst.id FROM base_stations bst
                JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bst.geom)
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH tower_points AS (
            SELECT bs.id, bs.geom, bs.provider_id, p.name AS provider_name, bs.technology
            FROM base_stations bs
            LEFT JOIN providers p ON p.id = bs.provider_id
            WHERE {where_sql}
            LIMIT :limit
        ),
        collected AS (
            SELECT ST_Collect(geom) AS geom_collection FROM tower_points
        ),
        voronoi AS (
            SELECT (ST_Dump(ST_VoronoiPolygons(geom_collection))).geom AS voronoi_geom
            FROM collected
        )
        SELECT
            tp.id AS tower_id,
            tp.provider_name,
            tp.technology,
            ST_AsGeoJSON(v.voronoi_geom)::json AS geojson,
            ST_Area(v.voronoi_geom::geography) / 1e6 AS area_km2,
            ST_Y(ST_Centroid(v.voronoi_geom)) AS centroid_lat,
            ST_X(ST_Centroid(v.voronoi_geom)) AS centroid_lon
        FROM voronoi v
        JOIN tower_points tp ON ST_Contains(v.voronoi_geom, tp.geom)
        ORDER BY area_km2 DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "properties": {
                "tower_id": row.tower_id,
                "provider_name": row.provider_name,
                "technology": row.technology,
                "area_km2": round(float(row.area_km2), 2) if row.area_km2 else None,
            },
            "geometry": row.geojson,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "total_features": len(features),
    }


async def provider_footprint(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Compute concave hull footprint for a provider's network coverage."""
    sql = text("""
        WITH provider_towers AS (
            SELECT bs.geom
            FROM base_stations bs
            WHERE bs.provider_id = :pid AND bs.geom IS NOT NULL
        )
        SELECT
            COUNT(*) AS tower_count,
            ST_AsGeoJSON(
                ST_ConcaveHull(ST_Collect(geom), 0.8)
            )::json AS footprint_geojson,
            ST_Area(
                ST_ConcaveHull(ST_Collect(geom), 0.8)::geography
            ) / 1e6 AS area_km2,
            ST_Y(ST_Centroid(ST_Collect(geom))) AS center_lat,
            ST_X(ST_Centroid(ST_Collect(geom))) AS center_lon
        FROM provider_towers
    """)

    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row or not row.tower_count or row.tower_count < 3:
        # Fallback: provider name lookup
        name_sql = text("SELECT name FROM providers WHERE id = :pid")
        name_row = (await db.execute(name_sql, {"pid": provider_id})).fetchone()
        return {
            "provider_id": provider_id,
            "provider_name": name_row.name if name_row else None,
            "error": "insufficient_towers",
            "message": f"Provider has {row.tower_count if row else 0} towers — need at least 3 for footprint",
        }

    name_sql = text("SELECT name FROM providers WHERE id = :pid")
    name_row = (await db.execute(name_sql, {"pid": provider_id})).fetchone()

    return {
        "provider_id": provider_id,
        "provider_name": name_row.name if name_row else None,
        "tower_count": row.tower_count,
        "area_km2": round(float(row.area_km2), 2) if row.area_km2 else None,
        "center": {"lat": round(float(row.center_lat), 6), "lon": round(float(row.center_lon), 6)},
        "footprint": {
            "type": "Feature",
            "properties": {"provider_id": provider_id, "area_km2": round(float(row.area_km2), 2) if row.area_km2 else None},
            "geometry": row.footprint_geojson,
        },
    }
