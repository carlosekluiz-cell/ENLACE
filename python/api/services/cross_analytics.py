"""
ENLACE Cross-Reference Analytics Service

Cross-references 11.7M+ records across 45+ tables for competitive intelligence,
coverage gap analysis, provider overlap, tower density, and correlations.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def hhi_competition_index(
    db: AsyncSession,
    state: Optional[str] = None,
    year_month: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Read precomputed HHI from competitive_analysis, classify concentration."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("""
            ca.l2_id IN (
                SELECT a2.id FROM admin_level_2 a2
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    if year_month:
        where_parts.append("ca.year_month = :year_month")
        params["year_month"] = year_month
    else:
        where_parts.append(
            "ca.year_month = (SELECT MAX(year_month) FROM competitive_analysis)"
        )

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            ca.l2_id,
            a2.name AS municipality_name,
            a1.abbrev AS state,
            ca.hhi_index,
            ca.threat_level,
            p.name AS leader_name,
            a2.population
        FROM competitive_analysis ca
        JOIN admin_level_2 a2 ON a2.id = ca.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN providers p ON p.id = ca.leader_provider_id
        WHERE {where_sql}
        ORDER BY ca.hhi_index DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    # Distribution buckets
    competitive = moderate = concentrated = dominant = 0
    municipalities = []
    for row in rows:
        hhi = float(row.hhi_index) if row.hhi_index else 0
        if hhi < 1500:
            competitive += 1
            classification = "competitive"
        elif hhi < 2500:
            moderate += 1
            classification = "moderate"
        elif hhi < 5000:
            concentrated += 1
            classification = "concentrated"
        else:
            dominant += 1
            classification = "dominant"

        municipalities.append({
            "l2_id": row.l2_id,
            "municipality": row.municipality_name,
            "state": row.state,
            "hhi_index": round(hhi, 1),
            "classification": classification,
            "threat_level": row.threat_level,
            "leader": row.leader_name,
            "population": row.population,
        })

    return {
        "total_municipalities": len(municipalities),
        "distribution": {
            "competitive": competitive,
            "moderate": moderate,
            "concentrated": concentrated,
            "dominant": dominant,
        },
        "municipalities": municipalities,
    }


async def coverage_gap_analysis(
    db: AsyncSession,
    state: Optional[str] = None,
    min_population: int = 10000,
    max_towers_per_1000: float = 1.0,
    limit: int = 50,
) -> dict[str, Any]:
    """Find underserved municipalities: high population but few towers."""
    where_parts = ["a2.population >= :min_pop"]
    params: dict[str, Any] = {
        "min_pop": min_population,
        "max_tpk": max_towers_per_1000,
        "limit": limit,
    }

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH sub_counts AS (
            SELECT l2_id, SUM(subscribers) AS total_subs,
                   COUNT(DISTINCT provider_id) AS provider_count
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        )
        SELECT
            a2.id AS l2_id,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            a2.area_km2,
            COALESCE(sc.provider_count, 0) AS providers,
            COALESCE(sc.total_subs, 0) AS subscribers,
            CASE WHEN a2.population > 0
                 THEN ROUND((COALESCE(sc.total_subs, 0)::numeric / a2.population * 100)::numeric, 2)
                 ELSE 0 END AS broadband_penetration_pct
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN sub_counts sc ON sc.l2_id = a2.id
        WHERE {where_sql}
            AND CASE WHEN a2.population > 0
                     THEN (COALESCE(sc.total_subs, 0)::numeric / a2.population * 100)
                     ELSE 0 END <= :max_tpk * 10
        ORDER BY a2.population DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    gaps = []
    for row in rows:
        gaps.append({
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "population": row.population,
            "area_km2": float(row.area_km2) if row.area_km2 else None,
            "providers": row.providers,
            "subscribers": row.subscribers,
            "broadband_penetration_pct": float(row.broadband_penetration_pct),
        })

    return {
        "total_gaps": len(gaps),
        "filters": {"state": state, "min_population": min_population, "max_towers_per_1000": max_towers_per_1000},
        "gaps": gaps,
    }


async def provider_overlap(
    db: AsyncSession,
    provider_id_a: int,
    provider_id_b: int,
) -> dict[str, Any]:
    """Find municipalities where both providers operate and compare shares."""
    sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        subs_a AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers, latest
            WHERE provider_id = :pa AND year_month = latest.ym
            GROUP BY l2_id
        ),
        subs_b AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers, latest
            WHERE provider_id = :pb AND year_month = latest.ym
            GROUP BY l2_id
        ),
        overlap AS (
            SELECT
                sa.l2_id,
                a2.name AS municipality,
                a1.abbrev AS state,
                sa.subs AS subs_a,
                sb.subs AS subs_b,
                (sa.subs + sb.subs) AS combined
            FROM subs_a sa
            JOIN subs_b sb ON sa.l2_id = sb.l2_id
            JOIN admin_level_2 a2 ON a2.id = sa.l2_id
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        )
        SELECT * FROM overlap ORDER BY combined DESC
    """)

    result = await db.execute(sql, {"pa": provider_id_a, "pb": provider_id_b})
    rows = result.fetchall()

    # Get provider names
    names_sql = text("SELECT id, name FROM providers WHERE id IN (:pa, :pb)")
    names = {r.id: r.name for r in (await db.execute(names_sql, {"pa": provider_id_a, "pb": provider_id_b})).fetchall()}

    municipalities = []
    total_subs_a = total_subs_b = 0
    for row in rows:
        total_subs_a += row.subs_a
        total_subs_b += row.subs_b
        combined = row.subs_a + row.subs_b
        municipalities.append({
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "subs_a": row.subs_a,
            "subs_b": row.subs_b,
            "share_a_pct": round(row.subs_a / combined * 100, 1) if combined > 0 else 0,
            "share_b_pct": round(row.subs_b / combined * 100, 1) if combined > 0 else 0,
        })

    return {
        "provider_a": {"id": provider_id_a, "name": names.get(provider_id_a)},
        "provider_b": {"id": provider_id_b, "name": names.get(provider_id_b)},
        "overlap_count": len(municipalities),
        "total_shared_subs_a": total_subs_a,
        "total_shared_subs_b": total_subs_b,
        "municipalities": municipalities,
    }


async def tower_density_analysis(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Rank municipalities by tower density (lowest = most underserved)."""
    where_parts = ["a2.population > 0"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH sub_counts AS (
            SELECT l2_id, SUM(subscribers) AS total_subs,
                   COUNT(DISTINCT provider_id) AS provider_count
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        )
        SELECT
            a2.id AS l2_id,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            a2.area_km2,
            COALESCE(sc.provider_count, 0) AS providers,
            COALESCE(sc.total_subs, 0) AS subscribers,
            ROUND((COALESCE(sc.total_subs, 0)::numeric / a2.population * 100)::numeric, 2) AS penetration_pct,
            CASE WHEN a2.area_km2 > 0
                 THEN ROUND((COALESCE(sc.total_subs, 0)::numeric / a2.area_km2)::numeric, 2)
                 ELSE 0 END AS subs_per_km2
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN sub_counts sc ON sc.l2_id = a2.id
        WHERE {where_sql}
        ORDER BY penetration_pct ASC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    rankings = []
    for i, row in enumerate(rows, 1):
        rankings.append({
            "rank": i,
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "population": row.population,
            "area_km2": float(row.area_km2) if row.area_km2 else None,
            "providers": row.providers,
            "subscribers": row.subscribers,
            "penetration_pct": float(row.penetration_pct),
            "subs_per_km2": float(row.subs_per_km2),
        })

    return {
        "total_ranked": len(rankings),
        "state_filter": state,
        "rankings": rankings,
    }


async def weather_quality_correlation(
    db: AsyncSession,
    state: Optional[str] = None,
    months: int = 12,
) -> dict[str, Any]:
    """Correlate weather (precipitation) with quality indicators per state."""
    where_parts = ["wo.observed_at >= NOW() - make_interval(months => :months)"]
    params: dict[str, Any] = {"months": months}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH weather_monthly AS (
            SELECT
                ws.station_code,
                DATE_TRUNC('month', wo.observed_at) AS month,
                AVG(wo.precipitation_mm) AS avg_precip
            FROM weather_observations wo
            JOIN weather_stations ws ON ws.id = wo.station_id
            WHERE wo.observed_at >= NOW() - make_interval(months => :months)
                AND wo.precipitation_mm IS NOT NULL
            GROUP BY ws.station_code, DATE_TRUNC('month', wo.observed_at)
        ),
        weather_agg AS (
            SELECT
                TO_CHAR(month, 'YYYY-MM') AS month_str,
                AVG(avg_precip) AS avg_precip
            FROM weather_monthly
            GROUP BY TO_CHAR(month, 'YYYY-MM')
        ),
        quality_monthly AS (
            SELECT
                a1.abbrev AS state,
                qi.year_month AS month_str,
                AVG(qi.value) AS avg_quality
            FROM quality_indicators qi
            JOIN admin_level_2 a2 ON a2.id = qi.l2_id
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            WHERE qi.metric_type = 'download_speed'
            {"AND a1.abbrev = :state" if state else ""}
            GROUP BY a1.abbrev, qi.year_month
        )
        SELECT
            qm.state,
            COUNT(*) AS data_points,
            AVG(wa.avg_precip) AS mean_precip,
            AVG(qm.avg_quality) AS mean_quality,
            CORR(wa.avg_precip, qm.avg_quality) AS correlation
        FROM quality_monthly qm
        JOIN weather_agg wa ON wa.month_str = qm.month_str
        GROUP BY qm.state
        HAVING COUNT(*) >= 3
        ORDER BY CORR(wa.avg_precip, qm.avg_quality) ASC NULLS LAST
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    correlations = []
    for row in rows:
        correlations.append({
            "state": row.state,
            "data_points": row.data_points,
            "mean_precipitation_mm": round(float(row.mean_precip), 2) if row.mean_precip else None,
            "mean_quality": round(float(row.mean_quality), 2) if row.mean_quality else None,
            "correlation": round(float(row.correlation), 4) if row.correlation else None,
        })

    return {
        "months_analyzed": months,
        "states_with_data": len(correlations),
        "correlations": correlations,
    }


async def employment_broadband_correlation(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Correlate formal employment with broadband penetration."""
    where_parts = ["ei.formal_jobs_total > 0", "a2.population > 0"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH latest_subs AS (
            SELECT l2_id, SUM(subscribers) AS total_subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        )
        SELECT
            a2.id AS l2_id,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            ei.formal_jobs_total,
            ei.avg_salary_brl,
            COALESCE(ls.total_subs, 0) AS subscribers,
            ROUND((COALESCE(ls.total_subs, 0)::numeric / a2.population * 100), 2) AS penetration_pct
        FROM employment_indicators ei
        JOIN admin_level_2 a2 ON a2.id = ei.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN latest_subs ls ON ls.l2_id = a2.id
        WHERE {where_sql}
        ORDER BY ei.formal_jobs_total DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    data_points = []
    jobs_list = []
    penetration_list = []
    for row in rows:
        pen = float(row.penetration_pct) if row.penetration_pct else 0
        data_points.append({
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "population": row.population,
            "formal_jobs": row.formal_jobs_total,
            "avg_salary_brl": float(row.avg_salary_brl) if row.avg_salary_brl else None,
            "subscribers": row.subscribers,
            "penetration_pct": pen,
        })
        jobs_list.append(float(row.formal_jobs_total))
        penetration_list.append(pen)

    # Simple Pearson correlation using numpy
    correlation = None
    if len(jobs_list) >= 3:
        try:
            import numpy as np
            if np.std(jobs_list) > 0 and np.std(penetration_list) > 0:
                correlation = round(float(np.corrcoef(jobs_list, penetration_list)[0, 1]), 4)
        except ImportError:
            pass

    return {
        "total_municipalities": len(data_points),
        "correlation_jobs_penetration": correlation,
        "data_points": data_points,
    }
