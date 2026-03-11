"""
ENLACE 5G Coverage Obligation Tracker Service

Tracks 5G auction obligations for CLARO, VIVO, TIM, WINITY.
Obligations: fiber_backhaul_530, 4g_7430, 5g_all_seats, highways_4g, 5g_non_seats.
"""

import logging
from datetime import date
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 5G auction obligation deadlines (Brazilian 5G auction Nov 2021)
OBLIGATIONS = [
    {
        "id": "fiber_backhaul_530",
        "description": "Levar fibra óptica de backhaul a 530 sedes de municípios sem atendimento",
        "deadline": date(2028, 12, 31),
        "operators": ["CLARO", "VIVO", "TIM"],
        "target_municipalities": 530,
    },
    {
        "id": "4g_7430",
        "description": "Cobertura 4G em 7.430 localidades sem internet móvel",
        "deadline": date(2028, 6, 30),
        "operators": ["CLARO", "VIVO", "TIM"],
        "target_municipalities": 7430,
    },
    {
        "id": "5g_all_seats",
        "description": "5G standalone em todas as sedes de municípios",
        "deadline": date(2029, 12, 31),
        "operators": ["CLARO", "VIVO", "TIM"],
        "target_municipalities": 5570,
    },
    {
        "id": "highways_4g",
        "description": "Cobertura 4G em rodovias federais prioritárias",
        "deadline": date(2028, 12, 31),
        "operators": ["CLARO", "VIVO", "TIM"],
        "target_km": 62000,
    },
    {
        "id": "5g_non_seats",
        "description": "5G em localidades com mais de 30 mil habitantes (fora sedes)",
        "deadline": date(2030, 6, 30),
        "operators": ["CLARO", "VIVO", "TIM", "WINITY"],
        "target_municipalities": 900,
    },
]


async def get_obligations(
    db: AsyncSession,
    provider_name: Optional[str] = None,
) -> dict[str, Any]:
    """Get all 5G obligations with progress estimates."""
    today = date.today()
    results = []

    for obl in OBLIGATIONS:
        if provider_name and provider_name.upper() not in obl["operators"]:
            continue

        days_remaining = (obl["deadline"] - today).days
        total_days = (obl["deadline"] - date(2021, 11, 5)).days
        elapsed_pct = max(0, min(100, (total_days - days_remaining) / max(total_days, 1) * 100))

        # Estimate progress from base_stations data
        progress_sql = text("""
            SELECT COUNT(DISTINCT a2.id) AS covered_municipalities
            FROM base_stations bs
            JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
            WHERE bs.technology IN ('LTE', 'NR')
        """)
        prog_row = (await db.execute(progress_sql)).fetchone()
        covered = prog_row.covered_municipalities if prog_row else 0

        target = obl.get("target_municipalities", obl.get("target_km", 0))
        progress_pct = min(100, covered / max(target, 1) * 100)

        status = "on_track" if progress_pct >= elapsed_pct * 0.8 else "at_risk" if progress_pct >= elapsed_pct * 0.5 else "behind"

        results.append({
            "obligation_id": obl["id"],
            "description": obl["description"],
            "deadline": obl["deadline"].isoformat(),
            "days_remaining": days_remaining,
            "operators": obl["operators"],
            "target": target,
            "estimated_progress": covered,
            "progress_pct": round(progress_pct, 1),
            "elapsed_pct": round(elapsed_pct, 1),
            "status": status,
        })

    return {
        "provider_filter": provider_name,
        "total_obligations": len(results),
        "obligations": results,
    }


async def gap_analysis(
    db: AsyncSession,
    provider_name: Optional[str] = None,
) -> dict[str, Any]:
    """Analyze gaps in 5G coverage obligation fulfillment."""
    # Find municipalities without 5G/LTE coverage
    sql = text("""
        WITH covered AS (
            SELECT DISTINCT a2.id
            FROM base_stations bs
            JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
            WHERE bs.technology IN ('LTE', 'NR')
        )
        SELECT
            a1.abbrev AS state,
            COUNT(a2.id) AS total_municipalities,
            COUNT(c.id) AS covered_municipalities,
            COUNT(a2.id) - COUNT(c.id) AS uncovered_municipalities,
            SUM(CASE WHEN c.id IS NULL THEN a2.population ELSE 0 END) AS uncovered_population
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN covered c ON c.id = a2.id
        GROUP BY a1.abbrev
        ORDER BY uncovered_municipalities DESC
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    gaps = []
    for row in rows:
        gaps.append({
            "state": row.state,
            "total_municipalities": row.total_municipalities,
            "covered": row.covered_municipalities,
            "uncovered": row.uncovered_municipalities,
            "coverage_pct": round(row.covered_municipalities / max(row.total_municipalities, 1) * 100, 1),
            "uncovered_population": int(row.uncovered_population or 0),
        })

    return {
        "provider_filter": provider_name,
        "total_states": len(gaps),
        "total_uncovered": sum(g["uncovered"] for g in gaps),
        "total_uncovered_population": sum(g["uncovered_population"] for g in gaps),
        "states": gaps,
    }
