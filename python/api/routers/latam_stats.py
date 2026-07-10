"""LATAM Platform Stats Router — platform-wide metrics for the /latam dashboard."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/latam", tags=["latam"])


# Tables we want to count (table_name, human-readable label)
_COUNTABLE_TABLES: list[tuple[str, str]] = [
    ("admin_level_2", "Municípios"),
    ("providers", "Provedores"),
    ("broadband_subscribers", "Registros de Assinantes"),
    ("base_stations", "Torres / ERBs"),
    ("quality_indicators", "Indicadores de Qualidade"),
    ("competitive_analysis", "Análises Competitivas"),
    ("census_tracts", "Setores Censitários"),
    ("economic_indicators", "Indicadores Econômicos"),
    ("spectrum_licenses", "Licenças de Espectro"),
]


async def _safe_count(db: AsyncSession, table: str) -> int:
    """Return row count for a table, or 0 if the table doesn't exist."""
    try:
        result = await db.execute(text(f'SELECT count(*) FROM "{table}"'))  # noqa: S608
        return result.scalar() or 0
    except Exception:
        logger.debug("Table %s not found or inaccessible", table)
        return 0


async def _country_breakdown(db: AsyncSession) -> list[dict[str, Any]]:
    """Return municipality and provider counts grouped by country_code."""
    try:
        result = await db.execute(text("""
            SELECT
                c.code AS country_code,
                COALESCE(l2.cnt, 0) AS municipalities,
                COALESCE(p.cnt, 0)  AS providers
            FROM countries c
            LEFT JOIN (
                SELECT country_code, count(*) AS cnt
                FROM admin_level_2
                GROUP BY country_code
            ) l2 ON l2.country_code = c.code
            LEFT JOIN (
                SELECT country_code, count(*) AS cnt
                FROM providers
                GROUP BY country_code
            ) p ON p.country_code = c.code
            ORDER BY COALESCE(l2.cnt, 0) DESC
        """))
        return [
            {
                "country_code": row.country_code,
                "municipalities": row.municipalities,
                "providers": row.providers,
            }
            for row in result.fetchall()
        ]
    except Exception:
        logger.debug("country_breakdown query failed", exc_info=True)
        return []


@router.get("/platform-stats")
async def platform_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
) -> dict[str, Any]:
    """Return platform-wide table counts and per-country breakdown.

    Used by the /latam dashboard for dynamic metrics.
    """
    tables = []
    for table_name, label in _COUNTABLE_TABLES:
        count = await _safe_count(db, table_name)
        tables.append({"table": table_name, "count": count, "label": label})

    by_country = await _country_breakdown(db)

    total_records = sum(t["count"] for t in tables)

    return {
        "tables": tables,
        "by_country": by_country,
        "total_records": total_records,
    }
