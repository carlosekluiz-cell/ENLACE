"""
ENLACE Social Gaps Service

Analyzes connectivity gaps for schools (180K) and health facilities (574K)
by cross-referencing with base station proximity and broadband coverage.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def school_connectivity_gaps(
    db: AsyncSession,
    state: Optional[str] = None,
    max_distance_km: float = 10.0,
    limit: int = 50,
) -> dict[str, Any]:
    """Analyze school connectivity gaps using broadband coverage data."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    # Summary stats by state
    stats_sql = text(f"""
        SELECT
            COUNT(*) AS total_schools,
            COUNT(*) FILTER (WHERE s.has_internet = true) AS with_internet,
            COUNT(*) FILTER (WHERE s.rural = true) AS rural_schools,
            COALESCE(SUM(s.student_count), 0) AS total_students,
            COUNT(DISTINCT a1.abbrev) AS states_covered
        FROM schools s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
    """)

    stats_result = await db.execute(stats_sql, params)
    stats = stats_result.fetchone()

    # Schools without internet in municipalities with low broadband coverage
    gaps_sql = text(f"""
        WITH muni_coverage AS (
            SELECT l2_id, SUM(subscribers) AS total_subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        )
        SELECT
            s.id,
            s.name AS school_name,
            s.has_internet,
            s.student_count,
            s.rural,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            COALESCE(mc.total_subs, 0) AS muni_subscribers,
            CASE WHEN a2.population > 0
                 THEN ROUND((COALESCE(mc.total_subs, 0)::numeric / a2.population * 100), 1)
                 ELSE 0 END AS muni_penetration_pct
        FROM schools s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN muni_coverage mc ON mc.l2_id = a2.id
        WHERE {where_sql}
            AND s.has_internet = false
        ORDER BY s.student_count DESC NULLS LAST
        LIMIT :limit
    """)

    gaps_result = await db.execute(gaps_sql, params)
    gap_rows = gaps_result.fetchall()

    # By-state breakdown
    state_sql = text(f"""
        SELECT
            a1.abbrev AS state,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE s.has_internet = true) AS connected,
            COUNT(*) FILTER (WHERE s.rural = true) AS rural
        FROM schools s
        JOIN admin_level_2 a2 ON a2.id = s.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
        GROUP BY a1.abbrev
        ORDER BY COUNT(*) DESC
    """)

    state_result = await db.execute(state_sql, params)
    state_rows = state_result.fetchall()

    gap_schools = []
    for row in gap_rows:
        gap_schools.append({
            "id": row.id,
            "school_name": row.school_name,
            "municipality": row.municipality,
            "state": row.state,
            "has_internet": row.has_internet,
            "student_count": row.student_count,
            "rural": row.rural,
            "muni_penetration_pct": float(row.muni_penetration_pct),
        })

    by_state = []
    for row in state_rows:
        by_state.append({
            "state": row.state,
            "total": row.total,
            "connected": row.connected,
            "connected_pct": round(row.connected / row.total * 100, 1) if row.total > 0 else 0,
            "rural": row.rural,
        })

    total = stats.total_schools if stats else 0
    return {
        "summary": {
            "total_schools": total,
            "with_internet": stats.with_internet if stats else 0,
            "internet_pct": round(stats.with_internet / total * 100, 1) if total > 0 else 0,
            "total_students": stats.total_students if stats else 0,
            "rural_schools": stats.rural_schools if stats else 0,
        },
        "by_state": by_state,
        "gap_schools": gap_schools,
    }


async def health_facility_gaps(
    db: AsyncSession,
    state: Optional[str] = None,
    max_distance_km: float = 10.0,
    limit: int = 50,
) -> dict[str, Any]:
    """Analyze health facility connectivity gaps using broadband coverage."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    stats_sql = text(f"""
        SELECT
            COUNT(*) AS total_facilities,
            COUNT(*) FILTER (WHERE hf.has_internet = true) AS with_internet,
            COALESCE(SUM(hf.bed_count), 0) AS total_beds
        FROM health_facilities hf
        JOIN admin_level_2 a2 ON a2.id = hf.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
    """)

    stats_result = await db.execute(stats_sql, params)
    stats = stats_result.fetchone()

    # Unconnected facilities prioritized by bed count
    gaps_sql = text(f"""
        WITH muni_coverage AS (
            SELECT l2_id, SUM(subscribers) AS total_subs
            FROM broadband_subscribers
            WHERE year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY l2_id
        )
        SELECT
            hf.id,
            hf.name AS facility_name,
            hf.has_internet,
            hf.bed_count,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            COALESCE(mc.total_subs, 0) AS muni_subscribers,
            CASE WHEN a2.population > 0
                 THEN ROUND((COALESCE(mc.total_subs, 0)::numeric / a2.population * 100), 1)
                 ELSE 0 END AS muni_penetration_pct
        FROM health_facilities hf
        JOIN admin_level_2 a2 ON a2.id = hf.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN muni_coverage mc ON mc.l2_id = a2.id
        WHERE {where_sql}
            AND hf.has_internet = false
        ORDER BY hf.bed_count DESC NULLS LAST
        LIMIT :limit
    """)

    gaps_result = await db.execute(gaps_sql, params)
    gap_rows = gaps_result.fetchall()

    # By-state breakdown
    state_sql = text(f"""
        SELECT
            a1.abbrev AS state,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE hf.has_internet = true) AS connected,
            COALESCE(SUM(hf.bed_count), 0) AS beds
        FROM health_facilities hf
        JOIN admin_level_2 a2 ON a2.id = hf.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
        GROUP BY a1.abbrev
        ORDER BY COUNT(*) DESC
    """)

    state_result = await db.execute(state_sql, params)
    state_rows = state_result.fetchall()

    gap_facilities = []
    for row in gap_rows:
        gap_facilities.append({
            "id": row.id,
            "facility_name": row.facility_name,
            "municipality": row.municipality,
            "state": row.state,
            "has_internet": row.has_internet,
            "bed_count": row.bed_count,
            "muni_penetration_pct": float(row.muni_penetration_pct),
        })

    by_state = []
    for row in state_rows:
        by_state.append({
            "state": row.state,
            "total": row.total,
            "connected": row.connected,
            "connected_pct": round(row.connected / row.total * 100, 1) if row.total > 0 else 0,
            "beds": row.beds,
        })

    total = stats.total_facilities if stats else 0
    return {
        "summary": {
            "total_facilities": total,
            "with_internet": stats.with_internet if stats else 0,
            "internet_pct": round(stats.with_internet / total * 100, 1) if total > 0 else 0,
            "total_beds": stats.total_beds if stats else 0,
        },
        "by_state": by_state,
        "gap_facilities": gap_facilities,
    }
