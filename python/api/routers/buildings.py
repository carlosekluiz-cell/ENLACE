"""
ENLACE Building Footprints Router

Endpoints for building footprint statistics and polygon retrieval per municipality.
Source: Microsoft Global ML Building Footprints.
"""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/buildings", tags=["buildings"])


def _to_float(value: Any) -> float | None:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("/geo/{municipality_id}/buildings/stats")
async def building_stats(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Building footprint statistics for a municipality.

    Returns count, total area, average area, and density per km2.
    """
    sql = text("""
        SELECT
            COUNT(*) AS building_count,
            COALESCE(SUM(bf.area_m2), 0) AS total_area_m2,
            COALESCE(AVG(bf.area_m2), 0) AS avg_area_m2,
            CASE
                WHEN ST_Area(al2.geom::geography) > 0
                THEN COUNT(*)::float / (ST_Area(al2.geom::geography) / 1e6)
                ELSE 0
            END AS density_per_km2
        FROM admin_level_2 al2
        LEFT JOIN building_footprints bf ON bf.l2_id = al2.id
        WHERE al2.id = :municipality_id
        GROUP BY al2.id, al2.geom
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Municipality not found",
        )

    return {
        "municipality_id": municipality_id,
        "building_count": int(row.building_count),
        "total_area_m2": round(_to_float(row.total_area_m2), 2),
        "avg_area_m2": round(_to_float(row.avg_area_m2), 2),
        "density_per_km2": round(_to_float(row.density_per_km2), 2),
    }


@router.get("/geo/{municipality_id}/buildings")
async def building_polygons(
    municipality_id: int,
    bbox: str = Query(
        None,
        description="Bounding box as 'west,south,east,north' (lng,lat,lng,lat)",
    ),
    limit: int = Query(1000, ge=1, le=5000, description="Max buildings to return"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Building footprint polygons for a municipality, optionally filtered by bbox.

    Returns a GeoJSON FeatureCollection.
    """
    params: dict[str, Any] = {
        "municipality_id": municipality_id,
        "limit": limit,
    }

    bbox_filter = ""
    if bbox:
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
        bbox_filter = "AND ST_Intersects(bf.geom, ST_MakeEnvelope(:west, :south, :east, :north, 4326))"
        params.update({"west": west, "south": south, "east": east, "north": north})

    sql = text(f"""
        SELECT
            bf.id,
            bf.area_m2,
            bf.height_m,
            bf.source,
            ST_AsGeoJSON(bf.geom)::json AS geojson
        FROM building_footprints bf
        WHERE bf.l2_id = :municipality_id
          {bbox_filter}
        ORDER BY bf.area_m2 DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    features = []
    for row in rows:
        features.append({
            "type": "Feature",
            "geometry": row.geojson,
            "properties": {
                "id": row.id,
                "area_m2": round(_to_float(row.area_m2), 2) if row.area_m2 else None,
                "height_m": _to_float(row.height_m),
                "source": row.source,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "municipality_id": municipality_id,
            "count": len(features),
            "limit": limit,
            "bbox": bbox,
        },
    }
