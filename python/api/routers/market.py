"""
ENLACE Market Intelligence Router

Endpoints for market summary, subscriber history, competitor analysis, and heatmap.
"""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.models.schemas import MarketSummary, CompetitorResponse, ProviderBreakdown

router = APIRouter(prefix="/api/v1/market", tags=["market"])


def _to_float(value: Any) -> float | None:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("/{municipality_id}/summary", response_model=MarketSummary)
async def market_summary(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Market summary for a municipality from the mv_market_summary materialized view.
    """
    sql = text("""
        SELECT
            l2_id AS municipality_id,
            municipality_code AS code,
            municipality_name AS name,
            state_abbrev,
            year_month,
            total_subscribers,
            fiber_subscribers,
            provider_count,
            total_households,
            total_population,
            broadband_penetration_pct,
            fiber_share_pct
        FROM mv_market_summary
        WHERE l2_id = :municipality_id
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Market summary not found for this municipality")

    return MarketSummary(
        municipality_id=row.municipality_id,
        code=row.code.strip() if row.code else "",
        name=row.name,
        state_abbrev=row.state_abbrev,
        year_month=row.year_month.strip() if row.year_month else "",
        total_subscribers=int(row.total_subscribers or 0),
        fiber_subscribers=int(row.fiber_subscribers or 0),
        provider_count=int(row.provider_count or 0),
        total_households=int(row.total_households) if row.total_households else None,
        total_population=int(row.total_population) if row.total_population else None,
        broadband_penetration_pct=_to_float(row.broadband_penetration_pct),
        fiber_share_pct=_to_float(row.fiber_share_pct),
    )


@router.get("/{municipality_id}/history")
async def market_history(
    municipality_id: int,
    months: int = Query(12, ge=1, le=60, description="Number of months of history"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Time series subscriber data for a municipality, aggregated by year_month.
    """
    sql = text("""
        SELECT
            bs.year_month,
            SUM(bs.subscribers) AS total_subscribers,
            SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subscribers,
            COUNT(DISTINCT bs.provider_id) AS provider_count
        FROM broadband_subscribers bs
        WHERE bs.l2_id = :municipality_id
        GROUP BY bs.year_month
        ORDER BY bs.year_month DESC
        LIMIT :months
    """)

    result = await db.execute(
        sql, {"municipality_id": municipality_id, "months": months}
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No subscriber history found for this municipality",
        )

    return [
        {
            "year_month": row.year_month.strip() if row.year_month else "",
            "total_subscribers": int(row.total_subscribers or 0),
            "fiber_subscribers": int(row.fiber_subscribers or 0),
            "provider_count": int(row.provider_count or 0),
        }
        for row in rows
    ]


@router.get("/{municipality_id}/competitors", response_model=CompetitorResponse)
async def market_competitors(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Provider-level competitive breakdown for a municipality.

    Queries the competitive_analysis table for the latest year_month,
    and enriches with provider details from broadband_subscribers.
    """
    # Get latest competitive analysis record
    ca_sql = text("""
        SELECT
            ca.hhi_index,
            ca.provider_details,
            ca.growth_trend,
            ca.threat_level,
            ca.year_month
        FROM competitive_analysis ca
        WHERE ca.l2_id = :municipality_id
        ORDER BY ca.year_month DESC
        LIMIT 1
    """)

    ca_result = await db.execute(ca_sql, {"municipality_id": municipality_id})
    ca_row = ca_result.fetchone()

    if not ca_row:
        raise HTTPException(
            status_code=404,
            detail="No competitive analysis found for this municipality",
        )

    # Build provider breakdown from provider_details JSON
    providers: list[ProviderBreakdown] = []
    provider_details = ca_row.provider_details or []

    if provider_details:
        # Get provider names for the IDs in provider_details
        provider_ids = [p["provider_id"] for p in provider_details if "provider_id" in p]

        if provider_ids:
            names_sql = text("""
                SELECT id, name FROM providers WHERE id = ANY(:ids)
            """)
            names_result = await db.execute(names_sql, {"ids": provider_ids})
            name_map = {row.id: row.name for row in names_result.fetchall()}

            # Get technology info from broadband_subscribers for latest month
            tech_sql = text("""
                SELECT
                    provider_id,
                    technology,
                    SUM(subscribers) AS subs
                FROM broadband_subscribers
                WHERE l2_id = :municipality_id
                  AND year_month = :year_month
                  AND provider_id = ANY(:ids)
                GROUP BY provider_id, technology
                ORDER BY provider_id, subs DESC
            """)
            tech_result = await db.execute(
                tech_sql,
                {
                    "municipality_id": municipality_id,
                    "year_month": ca_row.year_month,
                    "ids": provider_ids,
                },
            )
            tech_rows = tech_result.fetchall()

            # Map provider_id -> dominant technology
            tech_map: dict[int, str] = {}
            for tr in tech_rows:
                if tr.provider_id not in tech_map:
                    tech_map[tr.provider_id] = tr.technology

            for pd in provider_details:
                pid = pd.get("provider_id")
                providers.append(
                    ProviderBreakdown(
                        provider_id=pid,
                        name=name_map.get(pid, f"Provider {pid}"),
                        subscribers=pd.get("subscribers", 0),
                        share_pct=round(pd.get("market_share", 0) * 100, 2),
                        technology=tech_map.get(pid),
                        growth_3m=None,
                    )
                )

    # Build threats list
    threats: list[dict[str, Any]] = []
    if ca_row.threat_level:
        threats.append(
            {
                "level": ca_row.threat_level,
                "trend": ca_row.growth_trend,
                "description": f"Market concentration (HHI: {ca_row.hhi_index:.0f}) "
                f"with {ca_row.threat_level} threat level",
            }
        )

    return CompetitorResponse(
        hhi_index=ca_row.hhi_index or 0.0,
        providers=providers,
        threats=threats,
    )


@router.get("/heatmap")
async def market_heatmap(
    bbox: str = Query(
        ...,
        description="Bounding box as 'west,south,east,north' (lng,lat,lng,lat)",
    ),
    metric: str = Query("penetration", description="Metric: penetration, fiber_share, subscribers"),
    country: str = Query("BR", description="Country code"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    GeoJSON heatmap of municipality centroids with metric values.

    Queries mv_market_summary with ST_MakeEnvelope for bounding box filtering.
    Returns a GeoJSON FeatureCollection.
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

    # Map metric name to column
    metric_column_map = {
        "penetration": "broadband_penetration_pct",
        "fiber_share": "fiber_share_pct",
        "subscribers": "total_subscribers",
    }
    if metric not in metric_column_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric. Choose from: {', '.join(metric_column_map.keys())}",
        )

    metric_col = metric_column_map[metric]

    # metric_col is from a hardcoded whitelist above — safe to interpolate.
    # Using string formatting only for the validated column name; all user
    # values go through SQLAlchemy's :param binding.
    _SQL_TEMPLATES = {
        "broadband_penetration_pct": text("""
            SELECT l2_id, municipality_code, municipality_name, state_abbrev,
                   ST_Y(centroid) AS lat, ST_X(centroid) AS lng,
                   broadband_penetration_pct AS metric_value,
                   total_subscribers, provider_count
            FROM mv_market_summary
            WHERE country_code = :country AND centroid IS NOT NULL
              AND ST_Within(centroid, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            ORDER BY broadband_penetration_pct DESC
        """),
        "fiber_share_pct": text("""
            SELECT l2_id, municipality_code, municipality_name, state_abbrev,
                   ST_Y(centroid) AS lat, ST_X(centroid) AS lng,
                   fiber_share_pct AS metric_value,
                   total_subscribers, provider_count
            FROM mv_market_summary
            WHERE country_code = :country AND centroid IS NOT NULL
              AND ST_Within(centroid, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            ORDER BY fiber_share_pct DESC
        """),
        "total_subscribers": text("""
            SELECT l2_id, municipality_code, municipality_name, state_abbrev,
                   ST_Y(centroid) AS lat, ST_X(centroid) AS lng,
                   total_subscribers AS metric_value,
                   total_subscribers, provider_count
            FROM mv_market_summary
            WHERE country_code = :country AND centroid IS NOT NULL
              AND ST_Within(centroid, ST_MakeEnvelope(:west, :south, :east, :north, 4326))
            ORDER BY total_subscribers DESC
        """),
    }
    sql = _SQL_TEMPLATES[metric_col]

    result = await db.execute(
        sql,
        {
            "country": country,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
    )
    rows = result.fetchall()

    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row.lng, row.lat],
                },
                "properties": {
                    "municipality_id": row.l2_id,
                    "code": row.municipality_code.strip() if row.municipality_code else "",
                    "name": row.municipality_name,
                    "state_abbrev": row.state_abbrev,
                    "metric": metric,
                    "value": _to_float(row.metric_value),
                    "total_subscribers": int(row.total_subscribers or 0),
                    "provider_count": int(row.provider_count or 0),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }
