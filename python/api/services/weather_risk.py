"""
ENLACE Weather-Infrastructure Risk Correlation Service

Correlates weather_observations with base_stations via ST_DWithin.
Weighted risk: wind 30%, precipitation 25%, temp 15%, lightning 15%, exposure 15%.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WEIGHT_WIND = 0.30
WEIGHT_PRECIP = 0.25
WEIGHT_TEMP = 0.15
WEIGHT_LIGHTNING = 0.15
WEIGHT_EXPOSURE = 0.15


async def compute_weather_risk(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Compute weather risk scores for municipalities with towers."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH muni_weather AS (
            SELECT
                a2.id AS l2_id, a2.name, a1.abbrev AS state,
                AVG(wo.wind_speed_ms) AS avg_wind,
                MAX(wo.wind_speed_ms) AS max_wind,
                AVG(wo.precipitation_mm) AS avg_precip,
                MAX(wo.precipitation_mm) AS max_precip,
                AVG(wo.temperature_c) AS avg_temp,
                MIN(wo.temperature_c) AS min_temp,
                MAX(wo.temperature_c) AS max_temp,
                COUNT(wo.id) AS observation_count,
                (SELECT COUNT(*) FROM base_stations bst
                 JOIN admin_level_2 a22 ON ST_Contains(a22.geom, bst.geom)
                 WHERE a22.id = a2.id) AS tower_count
            FROM admin_level_2 a2
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            LEFT JOIN weather_observations wo ON wo.l2_id = a2.id
            WHERE {where_sql}
            GROUP BY a2.id, a2.name, a1.abbrev
            HAVING COUNT(wo.id) > 0
        )
        SELECT * FROM muni_weather
        ORDER BY tower_count DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    municipalities = []
    for row in rows:
        avg_wind = float(row.avg_wind or 0)
        max_wind = float(row.max_wind or 0)
        avg_precip = float(row.avg_precip or 0)
        max_precip = float(row.max_precip or 0)
        avg_temp = float(row.avg_temp or 0)
        min_temp = float(row.min_temp or 0)
        max_temp = float(row.max_temp or 0)
        towers = row.tower_count or 0

        # Wind risk: >15 m/s = 100, <3 m/s = 0
        wind_score = min(100, max(0, (max_wind - 3) / 12 * 100))

        # Precipitation risk: >100mm/day = 100
        precip_score = min(100, max(0, max_precip / 100 * 100))

        # Temperature risk: extreme heat (>40) or cold (<0)
        temp_score = min(100, max(0, max(max_temp - 35, 0) * 20 + max(0 - min_temp, 0) * 20))

        # Lightning risk proxy: high precip + high temp variance
        lightning_score = min(100, (avg_precip / 10 + abs(max_temp - min_temp)) * 3)

        # Exposure: more towers = more infrastructure at risk
        exposure_score = min(100, towers / 50 * 100)

        risk = round(
            WEIGHT_WIND * wind_score + WEIGHT_PRECIP * precip_score
            + WEIGHT_TEMP * temp_score + WEIGHT_LIGHTNING * lightning_score
            + WEIGHT_EXPOSURE * exposure_score, 2
        )

        tier = "critical" if risk >= 70 else "high" if risk >= 50 else "moderate" if risk >= 30 else "low"

        municipalities.append({
            "l2_id": row.l2_id,
            "name": row.name,
            "state": row.state,
            "tower_count": towers,
            "observation_count": row.observation_count,
            "risk_score": risk,
            "risk_tier": tier,
            "weather": {
                "avg_wind_ms": round(avg_wind, 1),
                "max_wind_ms": round(max_wind, 1),
                "avg_precip_mm": round(avg_precip, 1),
                "max_precip_mm": round(max_precip, 1),
                "avg_temp_c": round(avg_temp, 1),
                "min_temp_c": round(min_temp, 1),
                "max_temp_c": round(max_temp, 1),
            },
            "sub_scores": {
                "wind": round(wind_score, 1),
                "precipitation": round(precip_score, 1),
                "temperature": round(temp_score, 1),
                "lightning": round(lightning_score, 1),
                "exposure": round(exposure_score, 1),
            },
        })

    municipalities.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "state_filter": state,
        "total": len(municipalities),
        "critical_count": sum(1 for m in municipalities if m["risk_tier"] == "critical"),
        "high_count": sum(1 for m in municipalities if m["risk_tier"] == "high"),
        "municipalities": municipalities,
    }


async def get_risk_detail(
    db: AsyncSession,
    l2_id: int,
) -> dict[str, Any]:
    """Get detailed weather risk for a single municipality."""
    result = await compute_weather_risk(db, limit=5000)
    for m in result["municipalities"]:
        if m["l2_id"] == l2_id:
            return m
    return {"error": "municipality_not_found", "l2_id": l2_id}


async def seasonal_risk(
    db: AsyncSession,
    state: Optional[str] = None,
) -> dict[str, Any]:
    """Compute seasonal weather risk patterns."""
    where_parts = ["wo.observed_at IS NOT NULL"]
    params: dict[str, Any] = {}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            EXTRACT(MONTH FROM wo.observed_at)::int AS month,
            AVG(wo.wind_speed_ms) AS avg_wind,
            AVG(wo.precipitation_mm) AS avg_precip,
            AVG(wo.temperature_c) AS avg_temp,
            MAX(wo.wind_speed_ms) AS max_wind,
            MAX(wo.precipitation_mm) AS max_precip,
            COUNT(*) AS observations
        FROM weather_observations wo
        JOIN admin_level_2 a2 ON wo.l2_id = a2.id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
        GROUP BY EXTRACT(MONTH FROM wo.observed_at)
        ORDER BY month
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    month_names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    months = []
    for row in rows:
        m = int(row.month)
        wind = float(row.avg_wind or 0)
        precip = float(row.avg_precip or 0)
        risk = min(100, wind * 5 + precip * 0.5)
        months.append({
            "month": m,
            "month_name": month_names[m - 1] if 1 <= m <= 12 else str(m),
            "avg_wind_ms": round(wind, 1),
            "avg_precip_mm": round(precip, 1),
            "avg_temp_c": round(float(row.avg_temp or 0), 1),
            "max_wind_ms": round(float(row.max_wind or 0), 1),
            "max_precip_mm": round(float(row.max_precip or 0), 1),
            "risk_score": round(risk, 1),
            "observations": row.observations,
        })

    return {
        "state_filter": state,
        "months": months,
        "highest_risk_month": max(months, key=lambda x: x["risk_score"])["month_name"] if months else None,
        "lowest_risk_month": min(months, key=lambda x: x["risk_score"])["month_name"] if months else None,
    }
