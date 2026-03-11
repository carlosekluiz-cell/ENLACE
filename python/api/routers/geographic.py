"""
ENLACE Geographic Router

Endpoints for municipality search, boundary retrieval, and spatial queries.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.models.schemas import MunicipalityResponse

router = APIRouter(prefix="/api/v1/geo", tags=["geographic"])


@router.get("/search", response_model=list[MunicipalityResponse])
async def search_municipalities(
    q: str = Query(..., min_length=1, description="Search query"),
    country: str = Query("BR", description="Country code"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Search municipalities by name (case-insensitive, partial match).

    Results are ordered by relevance:
    1. Exact match
    2. Starts with query
    3. Contains query
    """
    sql = text("""
        SELECT
            a2.id,
            a2.code,
            a2.name,
            a1.abbrev AS state_abbrev,
            a2.country_code,
            a2.area_km2,
            ST_Y(a2.centroid) AS latitude,
            ST_X(a2.centroid) AS longitude
        FROM admin_level_2 a2
        LEFT JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE a2.country_code = :country
          AND unaccent(a2.name) ILIKE unaccent(:pattern)
        ORDER BY
            CASE
                WHEN LOWER(unaccent(a2.name)) = LOWER(unaccent(:q)) THEN 0
                WHEN LOWER(unaccent(a2.name)) LIKE LOWER(unaccent(:starts_with)) THEN 1
                ELSE 2
            END,
            a2.name
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "country": country,
            "pattern": f"%{q}%",
            "q": q,
            "starts_with": f"{q}%",
            "limit": limit,
        },
    )

    rows = result.fetchall()
    return [
        MunicipalityResponse(
            id=row.id,
            code=row.code,
            name=row.name,
            state_abbrev=row.state_abbrev,
            country_code=row.country_code,
            area_km2=row.area_km2,
            latitude=row.latitude,
            longitude=row.longitude,
        )
        for row in rows
    ]


@router.get("/{municipality_id}/boundary")
async def get_boundary(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Return GeoJSON boundary for a municipality.
    """
    sql = text("""
        SELECT
            a2.id,
            a2.code,
            a2.name,
            ST_AsGeoJSON(a2.geom)::json AS geometry
        FROM admin_level_2 a2
        WHERE a2.id = :municipality_id
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Municipality not found")

    if row.geometry is None:
        raise HTTPException(
            status_code=404,
            detail="No boundary geometry available for this municipality",
        )

    return {
        "type": "Feature",
        "properties": {
            "id": row.id,
            "code": row.code,
            "name": row.name,
        },
        "geometry": row.geometry,
    }


@router.get("/within", response_model=list[dict])
async def find_within_radius(
    lat: float = Query(..., description="Latitude of center point"),
    lng: float = Query(..., description="Longitude of center point"),
    radius_km: float = Query(50, ge=1, le=500, description="Search radius in km"),
    country: str = Query("BR", description="Country code"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Find municipalities within a radius of a given point.

    Uses PostGIS ST_DWithin with geography cast for accurate distance calculation.
    Returns municipalities with distance_km added.
    """
    sql = text("""
        SELECT
            a2.id,
            a2.code,
            a2.name,
            a1.abbrev AS state_abbrev,
            a2.country_code,
            a2.area_km2,
            ST_Y(a2.centroid) AS latitude,
            ST_X(a2.centroid) AS longitude,
            ST_Distance(
                a2.centroid::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            ) / 1000.0 AS distance_km
        FROM admin_level_2 a2
        LEFT JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE a2.country_code = :country
          AND a2.centroid IS NOT NULL
          AND ST_DWithin(
                a2.centroid::geography,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                :radius_m
          )
        ORDER BY distance_km
    """)

    result = await db.execute(
        sql,
        {
            "lat": lat,
            "lng": lng,
            "country": country,
            "radius_m": radius_km * 1000,
        },
    )

    rows = result.fetchall()
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "state_abbrev": row.state_abbrev,
            "country_code": row.country_code,
            "area_km2": row.area_km2,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "distance_km": round(row.distance_km, 2),
        }
        for row in rows
    ]
