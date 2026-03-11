"""
ENLACE Public Router — Raio-X do Provedor & Public Map

Free, unauthenticated endpoints:
- /raio-x — search for an ISP by name and get a limited intelligence report
- /mapa  — blinded map of all real municipality data (no provider names or
            exact numbers) for the marketing site
"""

from __future__ import annotations

import logging
import math
import time
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

# ---------------------------------------------------------------------------
# In-memory cache for /mapa (same data for all visitors, refreshed hourly)
# ---------------------------------------------------------------------------
_mapa_cache: dict[str, Any] = {"data": None, "ts": 0.0}
_MAPA_TTL = 3600  # 1 hour


def _to_float(value: Any, decimals: int = 1) -> float | None:
    """Convert Decimal/numeric to rounded float, returning None for None."""
    if value is None:
        return None
    return round(float(value), decimals)


@router.get("/mapa")
async def mapa_brasil(
    db: AsyncSession = Depends(get_db),
):
    """
    Public blinded map of all municipality-level broadband data in Brazil.

    Returns lat/lng, rounded subscriber counts (nearest 100), provider count,
    HHI, and penetration for every municipality — without provider names or
    exact numbers.  Cached in-memory for 1 hour.
    """
    now = time.time()
    if _mapa_cache["data"] is not None and (now - _mapa_cache["ts"]) < _MAPA_TTL:
        return JSONResponse(_mapa_cache["data"])

    # ------------------------------------------------------------------
    # Single efficient query: municipality aggregates for the latest period
    # ------------------------------------------------------------------
    sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        market AS (
            SELECT
                bs.l2_id,
                SUM(bs.subscribers)                     AS total_subs,
                COUNT(DISTINCT bs.provider_id)          AS providers
            FROM broadband_subscribers bs, latest
            WHERE bs.year_month = latest.ym
            GROUP BY bs.l2_id
        ),
        hhi_calc AS (
            SELECT
                pv.l2_id,
                SUM(POWER(pv.share, 2))::int AS hhi
            FROM (
                SELECT
                    bs.l2_id,
                    100.0 * SUM(bs.subscribers) / NULLIF(m.total_subs, 0) AS share
                FROM broadband_subscribers bs
                JOIN latest ON bs.year_month = latest.ym
                JOIN market m ON m.l2_id = bs.l2_id
                GROUP BY bs.l2_id, bs.provider_id, m.total_subs
            ) pv
            GROUP BY pv.l2_id
        ),
        periods AS (
            SELECT array_agg(DISTINCT year_month ORDER BY year_month) AS yms
            FROM broadband_subscribers
        )
        SELECT
            ST_Y(a2.centroid)                                          AS lat,
            ST_X(a2.centroid)                                          AS lng,
            a1.abbrev                                                  AS state,
            a2.population                                              AS pop,
            COALESCE(m.total_subs, 0)                                  AS subs,
            COALESCE(m.providers, 0)                                   AS providers,
            COALESCE(h.hhi, 0)                                         AS hhi,
            CASE
                WHEN a2.population > 0 AND m.total_subs IS NOT NULL
                THEN ROUND(m.total_subs * 100.0 / (a2.population * 0.33), 1)
                ELSE 0
            END                                                        AS penetration,
            p.yms                                                      AS periods
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        CROSS JOIN periods p
        LEFT JOIN market m ON m.l2_id = a2.id
        LEFT JOIN hhi_calc h ON h.l2_id = a2.id
        WHERE a2.centroid IS NOT NULL
        ORDER BY a2.id
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    if not rows:
        return {"municipalities": [], "meta": {}}

    # Extract periods from the first row (same for all)
    periods_raw = rows[0].periods or []
    # Keep only a sample of periods (every 3rd month) to avoid huge arrays
    periods_list = [str(p) for p in periods_raw]

    municipalities = []
    total_subs = 0
    munis_with_data = 0

    for row in rows:
        subs_raw = int(row.subs or 0)
        # Blind: round to nearest 100
        subs_rounded = round(subs_raw / 100) * 100

        total_subs += subs_raw
        if subs_raw > 0:
            munis_with_data += 1

        municipalities.append({
            "lat": round(float(row.lat), 4),
            "lng": round(float(row.lng), 4),
            "uf": row.state.strip() if row.state else "",
            "pop": int(row.pop or 0),
            "subs": subs_rounded,
            "providers": int(row.providers),
            "hhi": int(row.hhi),
            "penetration": round(float(row.penetration), 1),
        })

    # Blind total: round to nearest 10_000
    total_subs_rounded = round(total_subs / 10_000) * 10_000

    avg_penetration = 0.0
    pen_values = [m["penetration"] for m in municipalities if m["penetration"] > 0]
    if pen_values:
        avg_penetration = round(sum(pen_values) / len(pen_values), 1)

    payload = {
        "municipalities": municipalities,
        "meta": {
            "total_municipalities": len(municipalities),
            "municipalities_with_data": munis_with_data,
            "total_subscribers": total_subs_rounded,
            "avg_penetration": avg_penetration,
            "periods_available": periods_list,
        },
    }

    _mapa_cache["data"] = payload
    _mapa_cache["ts"] = now

    return JSONResponse(payload)


@router.get("/raio-x")
async def raio_x_provedor(
    q: str = Query(..., min_length=2, description="Provider name search term"),
    db: AsyncSession = Depends(get_db),
):
    """
    Raio-X do Provedor — free ISP intelligence report.

    Searches providers by name (ILIKE) and returns subscriber totals,
    municipality-level breakdown with market share and HHI, growth rate,
    fiber percentage, and Pulso Score.

    If multiple providers match, returns a list of suggestions.
    If no match, returns an error message.
    """
    # ---------------------------------------------------------------
    # Step 1: Find matching providers (only ACTIVE ones with subscribers)
    # ---------------------------------------------------------------
    search_sql = text("""
        SELECT p.id, p.name, COALESCE(sub_totals.total_subscribers, 0) AS total_subscribers
        FROM providers p
        INNER JOIN (
            SELECT provider_id, SUM(subscribers) AS total_subscribers
            FROM broadband_subscribers
            WHERE subscribers > 0
            GROUP BY provider_id
        ) sub_totals ON sub_totals.provider_id = p.id
        WHERE p.name ILIKE :pattern
        ORDER BY sub_totals.total_subscribers DESC
        LIMIT 10
    """)
    result = await db.execute(search_sql, {"pattern": f"%{q}%"})
    matches = result.fetchall()

    if not matches:
        return {"error": "Provedor não encontrado", "query": q}

    if len(matches) > 1:
        # Check if there's an exact match (case-insensitive)
        exact = [m for m in matches if m.name.strip().upper() == q.strip().upper()]
        if len(exact) == 1:
            matches = exact
        else:
            return {
                "matches": [
                    {
                        "id": m.id,
                        "name": m.name.strip(),
                        "total_subscribers": int(m.total_subscribers),
                    }
                    for m in matches
                ],
                "message": "Múltiplos provedores encontrados. Selecione um.",
            }

    provider_id = matches[0].id
    provider_name = matches[0].name.strip()

    # ---------------------------------------------------------------
    # Step 2: Municipality breakdown with market share and HHI
    # ---------------------------------------------------------------
    # This query:
    #  - Finds the latest year_month for this provider
    #  - Gets subscriber counts per municipality
    #  - Computes total market subscribers per municipality
    #  - Computes market share %
    #  - Computes HHI per municipality
    #  - Returns top 10 by subscriber count
    municipality_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym
            FROM broadband_subscribers
            WHERE provider_id = :pid
        ),
        provider_subs AS (
            SELECT
                bs.l2_id,
                SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs, latest
            WHERE bs.provider_id = :pid
              AND bs.year_month = latest.ym
            GROUP BY bs.l2_id
        ),
        market_totals AS (
            SELECT
                bs.l2_id,
                SUM(bs.subscribers) AS total_subs
            FROM broadband_subscribers bs, latest
            WHERE bs.year_month = latest.ym
              AND bs.l2_id IN (SELECT l2_id FROM provider_subs)
            GROUP BY bs.l2_id
        ),
        market_hhi AS (
            SELECT
                bs.l2_id,
                SUM(
                    POWER(
                        100.0 * bs.subscribers / NULLIF(mt.total_subs, 0),
                        2
                    )
                )::int AS hhi
            FROM (
                SELECT l2_id, provider_id, SUM(subscribers) AS subscribers
                FROM broadband_subscribers, latest
                WHERE year_month = latest.ym
                  AND l2_id IN (SELECT l2_id FROM provider_subs)
                GROUP BY l2_id, provider_id
            ) bs
            JOIN market_totals mt ON mt.l2_id = bs.l2_id
            GROUP BY bs.l2_id
        )
        SELECT
            a2.name AS municipality_name,
            a1.abbrev AS state,
            ps.subs AS subscribers,
            mt.total_subs AS total_market_subs,
            ROUND(100.0 * ps.subs / NULLIF(mt.total_subs, 0), 1) AS market_share_pct,
            mh.hhi
        FROM provider_subs ps
        JOIN admin_level_2 a2 ON a2.id = ps.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        JOIN market_totals mt ON mt.l2_id = ps.l2_id
        LEFT JOIN market_hhi mh ON mh.l2_id = ps.l2_id
        ORDER BY ps.subs DESC
        LIMIT 10
    """)

    result = await db.execute(municipality_sql, {"pid": provider_id})
    muni_rows = result.fetchall()

    municipalities = []
    for row in muni_rows:
        municipalities.append({
            "name": row.municipality_name.strip() if row.municipality_name else "",
            "state": row.state.strip() if row.state else "",
            "subscribers": int(row.subscribers or 0),
            "market_share_pct": _to_float(row.market_share_pct),
            "hhi": int(row.hhi) if row.hhi else None,
            "total_market_subs": int(row.total_market_subs or 0),
        })

    # ---------------------------------------------------------------
    # Step 3: Provider totals, growth rate, fiber percentage
    # ---------------------------------------------------------------
    totals_sql = text("""
        WITH periods AS (
            SELECT DISTINCT year_month
            FROM broadband_subscribers
            WHERE provider_id = :pid
            ORDER BY year_month DESC
            LIMIT 2
        ),
        latest AS (
            SELECT MAX(year_month) AS ym FROM periods
        ),
        previous AS (
            SELECT MIN(year_month) AS ym FROM periods
        ),
        current_totals AS (
            SELECT
                SUM(bs.subscribers) AS total_subs,
                SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBRA%'
                         OR UPPER(bs.technology) LIKE '%FIBER%'
                         OR UPPER(bs.technology) LIKE '%FTTH%'
                         OR UPPER(bs.technology) LIKE '%GPON%'
                    THEN bs.subscribers ELSE 0 END) AS fiber_subs
            FROM broadband_subscribers bs, latest
            WHERE bs.provider_id = :pid
              AND bs.year_month = latest.ym
        ),
        prev_totals AS (
            SELECT SUM(bs.subscribers) AS total_subs
            FROM broadband_subscribers bs, previous
            WHERE bs.provider_id = :pid
              AND bs.year_month = previous.ym
        )
        SELECT
            ct.total_subs,
            ct.fiber_subs,
            ROUND(100.0 * ct.fiber_subs / NULLIF(ct.total_subs, 0), 1) AS fiber_pct,
            ROUND(
                100.0 * (ct.total_subs - pt.total_subs)
                / NULLIF(pt.total_subs, 0),
                1
            ) AS growth_pct
        FROM current_totals ct, prev_totals pt
    """)

    result = await db.execute(totals_sql, {"pid": provider_id})
    totals_row = result.fetchone()

    total_subscribers = int(totals_row.total_subs or 0) if totals_row else 0
    fiber_pct = _to_float(totals_row.fiber_pct) if totals_row else None
    growth_pct = _to_float(totals_row.growth_pct) if totals_row else None

    # ---------------------------------------------------------------
    # Step 4: Pulso Score
    # ---------------------------------------------------------------
    pulso_sql = text("""
        SELECT score, tier
        FROM pulso_scores
        WHERE provider_id = :pid
        ORDER BY computed_at DESC
        LIMIT 1
    """)

    result = await db.execute(pulso_sql, {"pid": provider_id})
    pulso_row = result.fetchone()

    pulso_score = _to_float(pulso_row.score) if pulso_row else None
    pulso_tier = pulso_row.tier.strip() if pulso_row and pulso_row.tier else None

    # ---------------------------------------------------------------
    # Step 5: Build insights
    # ---------------------------------------------------------------
    total_municipalities = len(municipalities)

    strongest_market = None
    weakest_market = None
    avg_hhi = None

    if municipalities:
        strongest = municipalities[0]  # already sorted by subs DESC
        strongest_market = f"{strongest['name']}, {strongest['state']}"

        weakest = municipalities[-1]
        weakest_market = f"{weakest['name']}, {weakest['state']}"

        hhi_values = [m["hhi"] for m in municipalities if m["hhi"] is not None]
        if hhi_values:
            avg_hhi = round(sum(hhi_values) / len(hhi_values))

    # Also get the full municipality count (beyond top 10)
    count_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym
            FROM broadband_subscribers
            WHERE provider_id = :pid
        )
        SELECT COUNT(DISTINCT bs.l2_id) AS cnt
        FROM broadband_subscribers bs, latest
        WHERE bs.provider_id = :pid
          AND bs.year_month = latest.ym
    """)
    result = await db.execute(count_sql, {"pid": provider_id})
    count_row = result.fetchone()
    total_municipalities = int(count_row.cnt) if count_row else total_municipalities

    return {
        "provider": {
            "id": provider_id,
            "name": provider_name,
            "total_subscribers": total_subscribers,
            "pulso_score": pulso_score,
            "pulso_tier": pulso_tier,
            "growth_pct": growth_pct,
            "fiber_pct": fiber_pct,
        },
        "municipalities": municipalities,
        "insights": {
            "total_municipalities": total_municipalities,
            "strongest_market": strongest_market,
            "weakest_market": weakest_market,
            "avg_hhi": avg_hhi,
        },
    }
