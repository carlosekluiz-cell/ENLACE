"""
ENLACE Starlink Threat Index Service

Computes a weighted threat score for each municipality indicating vulnerability
to Starlink competition. Factors: provider density, broadband penetration,
household income, and distance to nearest fiber infrastructure.

Weights: density 30%, penetration 25%, income 20%, fiber distance 25%
Tiers: Critical (>=80), High (60-79), Moderate (40-59), Low (20-39), Minimal (<20)
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

WEIGHT_DENSITY = 0.30
WEIGHT_PENETRATION = 0.25
WEIGHT_INCOME = 0.20
WEIGHT_FIBER = 0.25

TIER_MAP = [
    (80, "Critical"),
    (60, "High"),
    (40, "Moderate"),
    (20, "Low"),
    (0, "Minimal"),
]


def _score_to_tier(score: float) -> str:
    for threshold, tier in TIER_MAP:
        if score >= threshold:
            return tier
    return "Minimal"


async def compute_threat_index(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Compute Starlink threat index for municipalities."""
    where_parts = ["a2.population > 0"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH latest_ym AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        muni_data AS (
            SELECT
                a2.id AS l2_id,
                a2.name AS municipality,
                a1.abbrev AS state,
                a2.population,
                a2.area_km2,
                COALESCE(SUM(bs.subscribers), 0) AS total_subscribers,
                COUNT(DISTINCT bs.provider_id) AS provider_count,
                COALESCE(SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END), 0) AS fiber_subscribers
            FROM admin_level_2 a2
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            LEFT JOIN broadband_subscribers bs ON bs.l2_id = a2.id
                AND bs.year_month = (SELECT ym FROM latest_ym)
            WHERE {where_sql}
            GROUP BY a2.id, a2.name, a1.abbrev, a2.population, a2.area_km2
        )
        SELECT *,
            CASE WHEN population > 0 THEN total_subscribers::float / (population / 3.2) * 100 ELSE 0 END AS penetration_pct,
            CASE WHEN total_subscribers > 0 THEN fiber_subscribers::float / total_subscribers * 100 ELSE 0 END AS fiber_pct,
            CASE WHEN area_km2 > 0 THEN population::float / area_km2 ELSE 0 END AS density
        FROM muni_data
        ORDER BY population DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    municipalities = []
    for row in rows:
        penetration = float(row.penetration_pct) if row.penetration_pct else 0
        fiber_pct = float(row.fiber_pct) if row.fiber_pct else 0
        density = float(row.density) if row.density else 0
        provider_count = int(row.provider_count)

        # Low density = HIGH vulnerability to Starlink (rural areas)
        density_score = max(0, min(100, 100 - min(density / 50, 1) * 100))

        # Low penetration = HIGH vulnerability
        penetration_score = max(0, min(100, 100 - min(penetration / 80, 1) * 100))

        # Low income proxy: fewer providers and lower population = higher vulnerability
        income_score = max(0, min(100, 100 - min(provider_count / 5, 1) * 100))

        # Low fiber = HIGH vulnerability
        fiber_score = max(0, min(100, 100 - min(fiber_pct / 60, 1) * 100))

        threat = round(
            WEIGHT_DENSITY * density_score
            + WEIGHT_PENETRATION * penetration_score
            + WEIGHT_INCOME * income_score
            + WEIGHT_FIBER * fiber_score,
            2,
        )
        threat = min(100, max(0, threat))

        municipalities.append({
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "population": row.population,
            "area_km2": float(row.area_km2) if row.area_km2 else None,
            "total_subscribers": row.total_subscribers,
            "provider_count": provider_count,
            "penetration_pct": round(penetration, 2),
            "fiber_pct": round(fiber_pct, 2),
            "threat_score": threat,
            "tier": _score_to_tier(threat),
            "sub_scores": {
                "density": round(density_score, 2),
                "penetration": round(penetration_score, 2),
                "income_proxy": round(income_score, 2),
                "fiber_distance": round(fiber_score, 2),
            },
        })

    municipalities.sort(key=lambda x: x["threat_score"], reverse=True)

    # Summary
    tier_counts = {}
    for m in municipalities:
        tier_counts[m["tier"]] = tier_counts.get(m["tier"], 0) + 1

    return {
        "state_filter": state,
        "total_municipalities": len(municipalities),
        "tier_distribution": tier_counts,
        "avg_threat_score": round(sum(m["threat_score"] for m in municipalities) / max(len(municipalities), 1), 2),
        "municipalities": municipalities,
    }


async def get_threat_detail(
    db: AsyncSession,
    l2_id: int,
) -> dict[str, Any]:
    """Get detailed Starlink threat analysis for a single municipality."""
    sql = text("""
        WITH latest_ym AS (SELECT MAX(year_month) AS ym FROM broadband_subscribers)
        SELECT
            a2.id AS l2_id, a2.name AS municipality, a1.abbrev AS state,
            a2.population, a2.area_km2,
            COALESCE(SUM(bs.subscribers), 0) AS total_subscribers,
            COUNT(DISTINCT bs.provider_id) AS provider_count,
            COALESCE(SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END), 0) AS fiber_subscribers,
            (SELECT COUNT(*) FROM base_stations bst
             JOIN admin_level_2 a22 ON ST_Contains(a22.geom, bst.geom) WHERE a22.id = :l2_id) AS tower_count
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN broadband_subscribers bs ON bs.l2_id = a2.id
            AND bs.year_month = (SELECT ym FROM latest_ym)
        WHERE a2.id = :l2_id
        GROUP BY a2.id, a2.name, a1.abbrev, a2.population, a2.area_km2
    """)

    result = await db.execute(sql, {"l2_id": l2_id})
    row = result.fetchone()

    if not row:
        return {"error": "municipality_not_found", "l2_id": l2_id}

    pop = row.population or 0
    penetration = float(row.total_subscribers) / (pop / 3.2) * 100 if pop > 0 else 0
    fiber_pct = float(row.fiber_subscribers) / max(row.total_subscribers, 1) * 100
    density = pop / float(row.area_km2) if row.area_km2 and row.area_km2 > 0 else 0

    density_score = max(0, min(100, 100 - min(density / 50, 1) * 100))
    penetration_score = max(0, min(100, 100 - min(penetration / 80, 1) * 100))
    income_score = max(0, min(100, 100 - min(row.provider_count / 5, 1) * 100))
    fiber_score = max(0, min(100, 100 - min(fiber_pct / 60, 1) * 100))

    threat = round(
        WEIGHT_DENSITY * density_score + WEIGHT_PENETRATION * penetration_score
        + WEIGHT_INCOME * income_score + WEIGHT_FIBER * fiber_score, 2
    )

    recommendations = []
    if fiber_pct < 30:
        recommendations.append("Expand fiber infrastructure to reduce satellite appeal")
    if penetration < 40:
        recommendations.append("Launch aggressive pricing/marketing to increase penetration")
    if row.provider_count < 3:
        recommendations.append("Low competition — opportunity for first-mover fiber deployment")
    if density < 20:
        recommendations.append("Low density area — consider FWA as cost-effective alternative to fiber")

    return {
        "l2_id": l2_id,
        "municipality": row.municipality,
        "state": row.state,
        "population": pop,
        "area_km2": float(row.area_km2) if row.area_km2 else None,
        "total_subscribers": row.total_subscribers,
        "provider_count": row.provider_count,
        "tower_count": row.tower_count,
        "penetration_pct": round(penetration, 2),
        "fiber_pct": round(fiber_pct, 2),
        "threat_score": threat,
        "tier": _score_to_tier(threat),
        "sub_scores": {
            "density": round(density_score, 2),
            "penetration": round(penetration_score, 2),
            "income_proxy": round(income_score, 2),
            "fiber_distance": round(fiber_score, 2),
        },
        "recommendations": recommendations,
    }


async def threat_summary(db: AsyncSession) -> dict[str, Any]:
    """National summary of Starlink threat distribution."""
    sql = text("""
        WITH latest_ym AS (SELECT MAX(year_month) AS ym FROM broadband_subscribers),
        state_data AS (
            SELECT
                a1.abbrev AS state,
                COUNT(DISTINCT a2.id) AS municipalities,
                SUM(a2.population) AS population,
                COALESCE(SUM(bs.subscribers), 0) AS subscribers,
                COUNT(DISTINCT bs.provider_id) AS providers
            FROM admin_level_1 a1
            JOIN admin_level_2 a2 ON a2.l1_id = a1.id
            LEFT JOIN broadband_subscribers bs ON bs.l2_id = a2.id
                AND bs.year_month = (SELECT ym FROM latest_ym)
            GROUP BY a1.abbrev
        )
        SELECT *,
            CASE WHEN population > 0 THEN subscribers::float / (population / 3.2) * 100 ELSE 0 END AS penetration_pct
        FROM state_data
        ORDER BY penetration_pct ASC
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    states = []
    for row in rows:
        pen = float(row.penetration_pct) if row.penetration_pct else 0
        threat_level = "Critical" if pen < 20 else "High" if pen < 40 else "Moderate" if pen < 60 else "Low"
        states.append({
            "state": row.state,
            "municipalities": row.municipalities,
            "population": row.population,
            "subscribers": row.subscribers,
            "providers": row.providers,
            "penetration_pct": round(pen, 2),
            "threat_level": threat_level,
        })

    return {
        "total_states": len(states),
        "states": states,
    }
