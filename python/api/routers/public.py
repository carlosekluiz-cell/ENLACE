"""
ENLACE Public Router — Raio-X do Provedor & Public Map

Free, unauthenticated endpoints:
- /raio-x — search for an ISP by name and get a limited intelligence report
- /raio-x/historico — 37-month subscriber time series for a provider
- /mapa  — blinded map of all real municipality data (no provider names or
            exact numbers) for the marketing site
- /mapa/historico — historical municipality data across all periods
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
# Provider group mapping — corporate entities that belong to the same group
# ---------------------------------------------------------------------------
PROVIDER_GROUPS: dict[str, list[int]] = {
    "CLARO": [3, 1771],        # CLARO S.A. + CLARO NXT TELECOMUNICACOES
    "VIVO": [5],               # TELEFONICA BRASIL S.A.
    "OI": [2],                 # Oi S.A.
    "TIM": [14],               # TIM S A
}

# Reverse lookup: provider_id → group name
_PROVIDER_TO_GROUP: dict[int, str] = {}
for _group_name, _ids in PROVIDER_GROUPS.items():
    for _pid in _ids:
        _PROVIDER_TO_GROUP[_pid] = _group_name


def _match_group(search_term: str) -> tuple[str, list[int]] | None:
    """Check if search term matches a provider group name."""
    term = search_term.strip().upper()
    for group_name, ids in PROVIDER_GROUPS.items():
        if term == group_name or group_name.startswith(term):
            if len(ids) > 1:
                return group_name, ids
    return None

# ---------------------------------------------------------------------------
# In-memory cache for /mapa (same data for all visitors, refreshed hourly)
# ---------------------------------------------------------------------------
_mapa_cache: dict[str, Any] = {"data": None, "ts": 0.0}
_mapa_hist_cache: dict[str, Any] = {"data": None, "ts": 0.0}
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
    # Step 0: Check if search term matches a provider group
    # ---------------------------------------------------------------
    group_match = _match_group(q)
    is_group = False
    group_ids: list[int] = []

    if group_match:
        group_name, group_ids = group_match
        is_group = True
        provider_name = f"Grupo {group_name}"
        provider_id = group_ids[0]  # primary entity

    # ---------------------------------------------------------------
    # Step 1: Find matching providers (only ACTIVE ones with subscribers)
    # ---------------------------------------------------------------
    if not is_group:
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

        # Check if any match belongs to a group with multiple entities
        if len(matches) >= 1:
            first_id = matches[0].id
            if first_id in _PROVIDER_TO_GROUP:
                gname = _PROVIDER_TO_GROUP[first_id]
                gids = PROVIDER_GROUPS[gname]
                if len(gids) > 1:
                    # Auto-group: show combined result
                    is_group = True
                    group_ids = gids
                    group_name = gname
                    provider_name = f"Grupo {gname}"
                    provider_id = gids[0]

        if not is_group:
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

    # Build provider ID filter for SQL
    pid_list = group_ids if is_group else [provider_id]
    pid_tuple = tuple(pid_list)

    # ---------------------------------------------------------------
    # Step 2: Municipality breakdown with market share and HHI
    # ---------------------------------------------------------------
    municipality_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym
            FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
        ),
        provider_subs AS (
            SELECT
                bs.l2_id,
                SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs, latest
            WHERE bs.provider_id = ANY(:pids)
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

    result = await db.execute(municipality_sql, {"pids": list(pid_tuple)})
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
            WHERE provider_id = ANY(:pids)
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
            WHERE bs.provider_id = ANY(:pids)
              AND bs.year_month = latest.ym
        ),
        prev_totals AS (
            SELECT SUM(bs.subscribers) AS total_subs
            FROM broadband_subscribers bs, previous
            WHERE bs.provider_id = ANY(:pids)
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

    result = await db.execute(totals_sql, {"pids": list(pid_tuple)})
    totals_row = result.fetchone()

    total_subscribers = int(totals_row.total_subs or 0) if totals_row else 0
    fiber_pct = _to_float(totals_row.fiber_pct) if totals_row else None
    growth_pct = _to_float(totals_row.growth_pct) if totals_row else None

    # ---------------------------------------------------------------
    # Step 4: Pulso Score (use primary entity)
    # ---------------------------------------------------------------
    pulso_sql = text("""
        SELECT score, tier
        FROM pulso_scores
        WHERE provider_id = ANY(:pids)
        ORDER BY score DESC, computed_at DESC
        LIMIT 1
    """)

    result = await db.execute(pulso_sql, {"pids": list(pid_tuple)})
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
            WHERE provider_id = ANY(:pids)
        )
        SELECT COUNT(DISTINCT bs.l2_id) AS cnt
        FROM broadband_subscribers bs, latest
        WHERE bs.provider_id = ANY(:pids)
          AND bs.year_month = latest.ym
    """)
    result = await db.execute(count_sql, {"pids": list(pid_tuple)})
    count_row = result.fetchone()
    total_municipalities = int(count_row.cnt) if count_row else total_municipalities

    # Build entity list for groups
    entity_names: list[dict] | None = None
    if is_group:
        ent_sql = text("""
            SELECT p.id, p.name FROM providers p WHERE p.id = ANY(:pids) ORDER BY p.id
        """)
        result = await db.execute(ent_sql, {"pids": list(pid_tuple)})
        entity_names = [{"id": r.id, "name": r.name.strip()} for r in result.fetchall()]

    response: dict[str, Any] = {
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

    if is_group and entity_names:
        response["provider"]["is_group"] = True
        response["provider"]["entities"] = entity_names
        response["provider"]["entity_count"] = len(entity_names)

    return response


@router.get("/raio-x/historico")
async def raio_x_historico(
    provider_id: int = Query(..., description="Provider ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    37-month subscriber time series for a provider (or provider group).
    Returns monthly subscriber count and fiber percentage.
    """
    # Check if this provider belongs to a group
    pid_list = [provider_id]
    group_name = None
    if provider_id in _PROVIDER_TO_GROUP:
        gname = _PROVIDER_TO_GROUP[provider_id]
        gids = PROVIDER_GROUPS[gname]
        if len(gids) > 1:
            pid_list = gids
            group_name = gname

    sql = text("""
        SELECT
            bs.year_month AS period,
            SUM(bs.subscribers) AS subscribers,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBER%'
                     OR UPPER(bs.technology) LIKE '%FTTH%'
                     OR UPPER(bs.technology) LIKE '%GPON%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS fiber_pct
        FROM broadband_subscribers bs
        WHERE bs.provider_id = ANY(:pids)
        GROUP BY bs.year_month
        ORDER BY bs.year_month
    """)

    result = await db.execute(sql, {"pids": pid_list})
    rows = result.fetchall()

    # Provider name
    name_sql = text("SELECT name FROM providers WHERE id = :pid")
    name_result = await db.execute(name_sql, {"pid": provider_id})
    name_row = name_result.fetchone()
    name = name_row.name.strip() if name_row else str(provider_id)
    if group_name:
        name = f"Grupo {group_name}"

    history = [
        {
            "period": str(row.period),
            "subscribers": int(row.subscribers),
            "fiber_pct": round(float(row.fiber_pct), 1) if row.fiber_pct else 0.0,
        }
        for row in rows
    ]

    # Also include per-municipality history for top 5 municipalities
    muni_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
        ),
        top_munis AS (
            SELECT bs.l2_id, SUM(bs.subscribers) AS subs
            FROM broadband_subscribers bs, latest
            WHERE bs.provider_id = ANY(:pids) AND bs.year_month = latest.ym
            GROUP BY bs.l2_id
            ORDER BY subs DESC
            LIMIT 5
        )
        SELECT
            bs.l2_id,
            a2.name AS municipality_name,
            a1.abbrev AS state,
            bs.year_month AS period,
            SUM(bs.subscribers) AS provider_subs,
            mt.total AS market_total,
            ROUND(100.0 * SUM(bs.subscribers) / NULLIF(mt.total, 0), 1) AS share_pct
        FROM broadband_subscribers bs
        JOIN top_munis tm ON tm.l2_id = bs.l2_id
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN LATERAL (
            SELECT SUM(b2.subscribers) AS total
            FROM broadband_subscribers b2
            WHERE b2.l2_id = bs.l2_id AND b2.year_month = bs.year_month
        ) mt ON true
        WHERE bs.provider_id = ANY(:pids)
        GROUP BY bs.l2_id, a2.name, a1.abbrev, bs.year_month, mt.total
        ORDER BY bs.l2_id, bs.year_month
    """)

    muni_result = await db.execute(muni_sql, {"pids": pid_list})
    muni_rows = muni_result.fetchall()

    # Group by municipality
    muni_histories: dict[int, dict] = {}
    for row in muni_rows:
        l2_id = row.l2_id
        if l2_id not in muni_histories:
            muni_histories[l2_id] = {
                "municipality": row.municipality_name.strip(),
                "state": row.state.strip(),
                "history": [],
            }
        muni_histories[l2_id]["history"].append({
            "period": str(row.period),
            "subscribers": int(row.provider_subs),
            "share_pct": float(row.share_pct) if row.share_pct else 0.0,
        })

    return {
        "provider_id": provider_id,
        "name": name,
        "history": history,
        "municipality_histories": list(muni_histories.values()),
    }


@router.get("/raio-x/posicao")
async def raio_x_posicao(
    provider_id: int = Query(..., description="Provider ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Competitive position report for a provider — FREE teaser.

    Returns national rank, market share, municipality/state count,
    technology breakdown, 12-month growth, and employment snapshot.
    Supports entity grouping (Claro, Vivo, etc.).
    """
    # Resolve group
    pid_list = [provider_id]
    if provider_id in _PROVIDER_TO_GROUP:
        gname = _PROVIDER_TO_GROUP[provider_id]
        gids = PROVIDER_GROUPS[gname]
        if len(gids) > 1:
            pid_list = gids

    # National rank + share
    rank_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        provider_totals AS (
            SELECT provider_id, SUM(subscribers) AS total
            FROM broadband_subscribers
            WHERE year_month = (SELECT ym FROM latest)
            GROUP BY provider_id
        ),
        ranked AS (
            SELECT provider_id, total,
                   RANK() OVER (ORDER BY total DESC) AS national_rank,
                   total * 100.0 / SUM(total) OVER () AS national_share
            FROM provider_totals
        )
        SELECT national_rank, national_share, total
        FROM ranked WHERE provider_id = ANY(:pids)
        ORDER BY total DESC
        LIMIT 1
    """)
    result = await db.execute(rank_sql, {"pids": pid_list})
    rank_row = result.fetchone()

    # If group, sum their totals for rank
    if len(pid_list) > 1:
        group_rank_sql = text("""
            WITH latest AS (
                SELECT MAX(year_month) AS ym FROM broadband_subscribers
            ),
            provider_totals AS (
                SELECT provider_id, SUM(subscribers) AS total
                FROM broadband_subscribers
                WHERE year_month = (SELECT ym FROM latest)
                GROUP BY provider_id
            ),
            group_totals AS (
                SELECT SUM(total) AS total FROM provider_totals
                WHERE provider_id = ANY(:pids)
            ),
            national AS (
                SELECT SUM(total) AS grand_total FROM provider_totals
            ),
            all_entities AS (
                SELECT provider_id, total FROM provider_totals
                UNION ALL
                SELECT -1 AS provider_id, (SELECT total FROM group_totals) AS total
            ),
            ranked AS (
                SELECT provider_id, total,
                       RANK() OVER (ORDER BY total DESC) AS rk
                FROM all_entities
            )
            SELECT rk AS national_rank,
                   gt.total * 100.0 / n.grand_total AS national_share,
                   gt.total
            FROM group_totals gt, national n,
                 (SELECT rk FROM ranked WHERE provider_id = -1) r
        """)
        result = await db.execute(group_rank_sql, {"pids": pid_list})
        rank_row = result.fetchone()

    national_rank = int(rank_row.national_rank) if rank_row else None
    national_share = _to_float(rank_row.national_share, 2) if rank_row else None
    total_subscribers = int(rank_row.total) if rank_row else 0

    # Municipality count, state count, tech breakdown
    geo_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
        )
        SELECT
            COUNT(DISTINCT bs.l2_id) AS municipalities,
            COUNT(DISTINCT a1.id) AS states,
            SUM(bs.subscribers) AS total_subs,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBER%'
                     OR UPPER(bs.technology) LIKE '%FTTH%'
                     OR UPPER(bs.technology) LIKE '%GPON%'
                     OR UPPER(bs.technology) LIKE '%FTTB%'
                THEN bs.subscribers ELSE 0 END) AS fiber_subs,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%RADIO%'
                     OR UPPER(bs.technology) LIKE '%FWA%'
                THEN bs.subscribers ELSE 0 END) AS radio_subs
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.provider_id = ANY(:pids) AND bs.year_month = (SELECT ym FROM latest)
    """)
    result = await db.execute(geo_sql, {"pids": pid_list})
    geo = result.fetchone()

    municipalities = int(geo.municipalities) if geo else 0
    states = int(geo.states) if geo else 0
    total = int(geo.total_subs) if geo and geo.total_subs else 1
    fiber_pct = round(float(geo.fiber_subs or 0) * 100.0 / total, 1) if geo else 0
    radio_pct = round(float(geo.radio_subs or 0) * 100.0 / total, 1) if geo else 0

    # 12-month growth
    growth_sql = text("""
        WITH periods AS (
            SELECT DISTINCT year_month FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
            ORDER BY year_month DESC
        ),
        latest AS (SELECT year_month FROM periods LIMIT 1),
        twelve_ago AS (SELECT year_month FROM periods OFFSET 11 LIMIT 1),
        t_now AS (
            SELECT SUM(subscribers) AS s FROM broadband_subscribers
            WHERE provider_id = ANY(:pids) AND year_month = (SELECT year_month FROM latest)
        ),
        t_then AS (
            SELECT SUM(subscribers) AS s FROM broadband_subscribers
            WHERE provider_id = ANY(:pids) AND year_month = (SELECT year_month FROM twelve_ago)
        )
        SELECT ROUND(100.0 * (n.s - t.s) / NULLIF(t.s, 0), 1) AS growth
        FROM t_now n, t_then t
    """)
    result = await db.execute(growth_sql, {"pids": pid_list})
    growth_row = result.fetchone()
    growth_12m = _to_float(growth_row.growth, 1) if growth_row and growth_row.growth else None

    # Employment snapshot
    emp_sql = text("""
        SELECT
            SUM(formal_jobs_telecom) AS total_employees,
            AVG(avg_salary_brl) AS avg_salary,
            COUNT(DISTINCT year) AS years_available
        FROM employment_indicators
        WHERE l2_id IN (
            SELECT DISTINCT l2_id FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
        )
        AND year = (SELECT MAX(year) FROM employment_indicators)
    """)
    result = await db.execute(emp_sql, {"pids": pid_list})
    emp = result.fetchone()

    employment = None
    if emp and emp.total_employees:
        employment = {
            "total_employees": int(emp.total_employees),
            "avg_salary_brl": round(float(emp.avg_salary), 2) if emp.avg_salary else None,
            "years_available": int(emp.years_available) if emp.years_available else 0,
        }

    return {
        "provider_id": provider_id,
        "national_rank": national_rank,
        "national_share_pct": national_share,
        "total_subscribers": total_subscribers,
        "municipalities": municipalities,
        "states": states,
        "fiber_pct": fiber_pct,
        "radio_pct": radio_pct,
        "growth_12m_pct": growth_12m,
        "employment": employment,
    }


@router.get("/raio-x/intel")
async def raio_x_intel(
    provider_id: int = Query(..., description="Provider ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Intelligence summary for a provider — FREE counts, details LOCKED.

    Aggregates gazette mentions, regulatory acts, BNDES loans, spectrum
    licenses, and competitive data. Returns counts and teasers (free),
    with full details locked behind paywall.
    """
    # Resolve group
    pid_list = [provider_id]
    if provider_id in _PROVIDER_TO_GROUP:
        gname = _PROVIDER_TO_GROUP[provider_id]
        gids = PROVIDER_GROUPS[gname]
        if len(gids) > 1:
            pid_list = gids

    # Get provider's municipalities for gazette lookup
    muni_sql = text("""
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
            WHERE provider_id = ANY(:pids)
        )
        SELECT DISTINCT l2_id FROM broadband_subscribers
        WHERE provider_id = ANY(:pids)
          AND year_month = (SELECT ym FROM latest)
    """)
    result = await db.execute(muni_sql, {"pids": pid_list})
    muni_ids = [r.l2_id for r in result.fetchall()]

    # Provider name for gazette search
    name_sql = text("SELECT name FROM providers WHERE id = :pid")
    result = await db.execute(name_sql, {"pid": provider_id})
    name_row = result.fetchone()
    provider_name = name_row.name.strip() if name_row else ""

    # 1. Gazette mentions — search by provider name in excerpt
    gazette_data = {"total_mentions": 0, "by_type": {}, "latest_date": None, "locked": True}
    if provider_name:
        gazette_sql = text("""
            SELECT mention_type, COUNT(*) AS cnt,
                   MAX(published_date) AS latest
            FROM municipal_gazette_mentions
            WHERE excerpt ILIKE :pattern
               OR excerpt ILIKE :pattern2
            GROUP BY mention_type
        """)
        # Search by provider name, also try first word
        first_word = provider_name.split()[0] if provider_name else ""
        result = await db.execute(gazette_sql, {
            "pattern": f"%{provider_name}%",
            "pattern2": f"%{first_word}%",
        })
        gazette_rows = result.fetchall()
        total = 0
        by_type = {}
        latest_date = None
        for row in gazette_rows:
            cnt = int(row.cnt)
            total += cnt
            mtype = row.mention_type or "outros"
            by_type[mtype] = by_type.get(mtype, 0) + cnt
            if row.latest and (latest_date is None or row.latest > latest_date):
                latest_date = row.latest
        gazette_data = {
            "total_mentions": total,
            "by_type": by_type,
            "latest_date": str(latest_date) if latest_date else None,
            "locked": True,
        }

    # Also try gazette in provider's municipalities (broader search)
    if gazette_data["total_mentions"] == 0 and muni_ids:
        gazette_muni_sql = text("""
            SELECT mention_type, COUNT(*) AS cnt,
                   MAX(published_date) AS latest
            FROM municipal_gazette_mentions
            WHERE l2_id = ANY(:muni_ids)
              AND (mention_type IN ('telecomunicacao', 'fibra', 'banda_larga', 'conectividade'))
            GROUP BY mention_type
        """)
        result = await db.execute(gazette_muni_sql, {"muni_ids": muni_ids[:50]})
        gazette_rows = result.fetchall()
        total = 0
        by_type = {}
        latest_date = None
        for row in gazette_rows:
            cnt = int(row.cnt)
            total += cnt
            mtype = row.mention_type or "outros"
            by_type[mtype] = by_type.get(mtype, 0) + cnt
            if row.latest and (latest_date is None or row.latest > latest_date):
                latest_date = row.latest
        gazette_data = {
            "total_mentions": total,
            "by_type": by_type,
            "latest_date": str(latest_date) if latest_date else None,
            "locked": True,
        }

    # 2. Regulatory acts — search by provider name in title/content
    reg_data = {"relevant_acts": 0, "latest_act_title": None, "locked": True}
    reg_sql = text("""
        SELECT title, published_date
        FROM regulatory_acts
        WHERE title ILIKE :pattern
           OR content_summary ILIKE :pattern
           OR :pid_str = ANY(affects_providers)
        ORDER BY published_date DESC
        LIMIT 10
    """)
    result = await db.execute(reg_sql, {
        "pattern": f"%{provider_name.split()[0] if provider_name else ''}%",
        "pid_str": str(provider_id),
    })
    reg_rows = result.fetchall()
    if not reg_rows:
        # Fallback: get latest regulatory acts for telecom sector
        reg_fallback_sql = text("""
            SELECT title, published_date
            FROM regulatory_acts
            WHERE keywords && ARRAY['telecomunicacao', 'banda_larga', 'fibra', 'internet']::text[]
               OR title ILIKE '%telecom%'
               OR title ILIKE '%banda larga%'
            ORDER BY published_date DESC
            LIMIT 5
        """)
        result = await db.execute(reg_fallback_sql)
        reg_rows = result.fetchall()

    reg_data = {
        "relevant_acts": len(reg_rows),
        "latest_act_title": reg_rows[0].title[:100] if reg_rows else None,
        "locked": True,
    }

    # 3. BNDES loans
    bndes_data = {"loans_count": 0, "total_value_brl": 0, "locked": True}
    bndes_sql = text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(contract_value_brl), 0) AS total_val
        FROM bndes_loans
        WHERE provider_id = ANY(:pids)
           OR borrower_name ILIKE :pattern
    """)
    result = await db.execute(bndes_sql, {
        "pids": pid_list,
        "pattern": f"%{provider_name.split()[0] if provider_name else ''}%",
    })
    bndes_row = result.fetchone()
    if bndes_row:
        bndes_data = {
            "loans_count": int(bndes_row.cnt),
            "total_value_brl": float(bndes_row.total_val),
            "locked": True,
        }

    # 4. Spectrum licenses
    spectrum_data = {"licenses_count": 0, "locked": True}
    spectrum_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM spectrum_licenses
        WHERE provider_id = ANY(:pids)
    """)
    result = await db.execute(spectrum_sql, {"pids": pid_list})
    spectrum_row = result.fetchone()
    if spectrum_row:
        spectrum_data = {
            "licenses_count": int(spectrum_row.cnt),
            "locked": True,
        }

    # 5. Competition snapshot (free teaser)
    comp_data = {
        "national_rank": None,
        "national_share_pct": None,
        "top_5_markets_locked": True,
    }
    # Reuse rank computation
    rank_sql2 = text("""
        WITH latest AS (SELECT MAX(year_month) AS ym FROM broadband_subscribers),
        totals AS (
            SELECT provider_id, SUM(subscribers) AS total
            FROM broadband_subscribers
            WHERE year_month = (SELECT ym FROM latest)
            GROUP BY provider_id
        ),
        ranked AS (
            SELECT provider_id, total,
                   RANK() OVER (ORDER BY total DESC) AS rk,
                   total * 100.0 / SUM(total) OVER () AS share
            FROM totals
        )
        SELECT rk, share FROM ranked WHERE provider_id = ANY(:pids)
        ORDER BY total DESC LIMIT 1
    """)
    result = await db.execute(rank_sql2, {"pids": pid_list})
    comp_row = result.fetchone()
    if comp_row:
        comp_data["national_rank"] = int(comp_row.rk)
        comp_data["national_share_pct"] = _to_float(comp_row.share, 2)

    return {
        "provider_id": provider_id,
        "gazette": gazette_data,
        "regulatory": reg_data,
        "bndes": bndes_data,
        "spectrum": spectrum_data,
        "competition": comp_data,
    }


@router.get("/mapa/historico")
async def mapa_historico(
    db: AsyncSession = Depends(get_db),
):
    """
    Historical municipality data across all 37 periods.
    Returns aggregated subscriber counts, provider counts, HHI, and penetration
    for every municipality at every available time period.
    Cached in-memory for 1 hour. Response ~3-5MB, served with gzip.
    """
    now = time.time()
    if _mapa_hist_cache["data"] is not None and (now - _mapa_hist_cache["ts"]) < _MAPA_TTL:
        return JSONResponse(_mapa_hist_cache["data"])

    sql = text("""
        WITH periods AS (
            SELECT array_agg(DISTINCT year_month ORDER BY year_month) AS yms
            FROM broadband_subscribers
        ),
        muni_periods AS (
            SELECT
                bs.l2_id,
                bs.year_month,
                SUM(bs.subscribers) AS total_subs,
                COUNT(DISTINCT bs.provider_id) AS providers
            FROM broadband_subscribers bs
            GROUP BY bs.l2_id, bs.year_month
        ),
        hhi_per_period AS (
            SELECT
                pv.l2_id,
                pv.year_month,
                SUM(POWER(pv.share, 2))::int AS hhi
            FROM (
                SELECT
                    bs.l2_id,
                    bs.year_month,
                    100.0 * SUM(bs.subscribers) / NULLIF(mp.total_subs, 0) AS share
                FROM broadband_subscribers bs
                JOIN muni_periods mp ON mp.l2_id = bs.l2_id AND mp.year_month = bs.year_month
                GROUP BY bs.l2_id, bs.year_month, bs.provider_id, mp.total_subs
            ) pv
            GROUP BY pv.l2_id, pv.year_month
        )
        SELECT
            a2.id AS l2_id,
            ST_Y(a2.centroid) AS lat,
            ST_X(a2.centroid) AS lng,
            a1.abbrev AS state,
            a2.population AS pop,
            mp.year_month,
            COALESCE(mp.total_subs, 0) AS subs,
            COALESCE(mp.providers, 0) AS providers,
            COALESCE(h.hhi, 0) AS hhi,
            CASE
                WHEN a2.population > 0 AND mp.total_subs IS NOT NULL
                THEN ROUND(mp.total_subs * 100.0 / (a2.population * 0.33), 1)
                ELSE 0
            END AS penetration,
            p.yms AS periods
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        CROSS JOIN periods p
        JOIN muni_periods mp ON mp.l2_id = a2.id
        LEFT JOIN hhi_per_period h ON h.l2_id = a2.id AND h.year_month = mp.year_month
        WHERE a2.centroid IS NOT NULL
        ORDER BY a2.id, mp.year_month
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    if not rows:
        return {"periods": [], "municipalities": []}

    # Extract period list from first row
    periods_list = [str(p) for p in (rows[0].periods or [])]

    # Build municipality dict keyed by l2_id
    munis: dict[int, dict] = {}
    for row in rows:
        l2_id = row.l2_id
        if l2_id not in munis:
            munis[l2_id] = {
                "lat": round(float(row.lat), 4),
                "lng": round(float(row.lng), 4),
                "uf": row.state.strip() if row.state else "",
                "pop": int(row.pop or 0),
                "history": [],
            }
        subs_raw = int(row.subs or 0)
        munis[l2_id]["history"].append({
            "s": round(subs_raw / 100) * 100,  # blind to nearest 100
            "p": int(row.providers),
            "h": int(row.hhi),
            "n": round(float(row.penetration), 1),
        })

    # Compute per-period national stats
    period_stats = []
    for pi, period in enumerate(periods_list):
        total_subs = 0
        pen_sum = 0.0
        pen_count = 0
        fiber_munis = 0  # munis with any subs
        for mdata in munis.values():
            if pi < len(mdata["history"]):
                h = mdata["history"][pi]
                total_subs += h["s"]
                if h["n"] > 0:
                    pen_sum += h["n"]
                    pen_count += 1
                if h["s"] > 0:
                    fiber_munis += 1
        period_stats.append({
            "period": period,
            "total_subs": round(total_subs / 10_000) * 10_000,
            "avg_penetration": round(pen_sum / pen_count, 1) if pen_count else 0,
            "municipalities_with_data": fiber_munis,
        })

    payload = {
        "periods": periods_list,
        "period_stats": period_stats,
        "municipalities": list(munis.values()),
    }

    _mapa_hist_cache["data"] = payload
    _mapa_hist_cache["ts"] = now

    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Raio-X: Quality Seals (Anatel quality rating)
# ---------------------------------------------------------------------------

@router.get("/raio-x/qualidade")
async def raio_x_qualidade(
    provider_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Anatel quality seals (ouro/prata/bronze) for a provider across municipalities."""
    group_name = _PROVIDER_TO_GROUP.get(provider_id)
    if group_name:
        pids = PROVIDER_GROUPS[group_name]
    else:
        pids = [provider_id]

    sql = text("""
        SELECT qs.year_half, qs.seal_level,
               ROUND(AVG(qs.overall_score)::numeric, 1) AS avg_overall,
               ROUND(AVG(qs.availability_score)::numeric, 1) AS avg_availability,
               ROUND(AVG(qs.speed_score)::numeric, 1) AS avg_speed,
               ROUND(AVG(qs.latency_score)::numeric, 1) AS avg_latency,
               COUNT(*) AS municipality_count
        FROM quality_seals qs
        WHERE qs.provider_id = ANY(:pids)
        GROUP BY qs.year_half, qs.seal_level
        ORDER BY qs.year_half DESC, qs.seal_level
    """)
    res = await db.execute(sql, {"pids": pids})
    rows = res.fetchall()

    # Summary: latest period breakdown
    periods: dict[str, list] = {}
    for r in rows:
        p = r.year_half
        if p not in periods:
            periods[p] = []
        periods[p].append({
            "seal_level": r.seal_level,
            "avg_overall": float(r.avg_overall) if r.avg_overall else 0,
            "avg_availability": float(r.avg_availability) if r.avg_availability else 0,
            "avg_speed": float(r.avg_speed) if r.avg_speed else 0,
            "avg_latency": float(r.avg_latency) if r.avg_latency else 0,
            "municipality_count": r.municipality_count,
        })

    # Overall totals
    total_sql = text("""
        SELECT seal_level, COUNT(*) as cnt
        FROM quality_seals
        WHERE provider_id = ANY(:pids)
          AND year_half = (SELECT MAX(year_half) FROM quality_seals WHERE provider_id = ANY(:pids))
        GROUP BY seal_level ORDER BY cnt DESC
    """)
    totals_res = await db.execute(total_sql, {"pids": pids})
    seal_summary = {r.seal_level: r.cnt for r in totals_res.fetchall()}

    return {
        "provider_id": provider_id,
        "seal_summary": seal_summary,
        "total_evaluated": sum(seal_summary.values()),
        "by_period": periods,
    }


# ---------------------------------------------------------------------------
# Raio-X: Government Contracts
# ---------------------------------------------------------------------------

@router.get("/raio-x/contratos")
async def raio_x_contratos(
    provider_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Government telecom contracts won by or related to a provider."""
    # Get provider name for text matching
    name_res = await db.execute(
        text("SELECT name FROM providers WHERE id = :pid"), {"pid": provider_id}
    )
    name_row = name_res.fetchone()
    pname = name_row.name.strip() if name_row else ""
    first_word = pname.split()[0] if pname else ""

    # Count + summary (free teaser)
    count_sql = text("""
        SELECT COUNT(*) as total,
               COALESCE(SUM(value_brl), 0) as total_value,
               MIN(published_date) as earliest,
               MAX(published_date) as latest
        FROM government_contracts
        WHERE winner_name ILIKE :pattern
           OR winner_cnpj IN (
               SELECT national_id FROM providers WHERE id = :pid
           )
    """)
    res = await db.execute(count_sql, {"pattern": f"%{first_word}%", "pid": provider_id})
    summary = res.fetchone()

    # By sphere breakdown
    sphere_sql = text("""
        SELECT sphere, COUNT(*) as cnt, COALESCE(SUM(value_brl), 0) as total
        FROM government_contracts
        WHERE winner_name ILIKE :pattern
           OR winner_cnpj IN (SELECT national_id FROM providers WHERE id = :pid)
        GROUP BY sphere ORDER BY total DESC
    """)
    sphere_res = await db.execute(sphere_sql, {"pattern": f"%{first_word}%", "pid": provider_id})

    # By state
    state_sql = text("""
        SELECT state_code, COUNT(*) as cnt
        FROM government_contracts
        WHERE (winner_name ILIKE :pattern
           OR winner_cnpj IN (SELECT national_id FROM providers WHERE id = :pid))
           AND state_code IS NOT NULL
        GROUP BY state_code ORDER BY cnt DESC LIMIT 10
    """)
    state_res = await db.execute(state_sql, {"pattern": f"%{first_word}%", "pid": provider_id})

    return {
        "provider_id": provider_id,
        "total_contracts": summary.total if summary else 0,
        "total_value_brl": float(summary.total_value) if summary and summary.total_value else 0,
        "earliest_date": str(summary.earliest) if summary and summary.earliest else None,
        "latest_date": str(summary.latest) if summary and summary.latest else None,
        "by_sphere": [
            {"sphere": r.sphere, "count": r.cnt, "total_brl": float(r.total)}
            for r in sphere_res.fetchall()
        ],
        "by_state": [
            {"state": r.state_code, "count": r.cnt}
            for r in state_res.fetchall()
        ],
        "locked": True,
    }


# ---------------------------------------------------------------------------
# Raio-X: Municipality Intelligence Profile
# ---------------------------------------------------------------------------

@router.get("/raio-x/municipio-perfil")
async def raio_x_municipio_perfil(
    municipality_id: int = Query(None),
    municipality_code: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Comprehensive municipality profile combining safety, sanitation, building density, planning, backhaul, economic data."""
    if not municipality_id and not municipality_code:
        return {"error": "Provide municipality_id or municipality_code"}

    # Resolve to internal l2_id (admin_level_2.id)
    lid = None
    if municipality_code:
        r = await db.execute(
            text("SELECT id FROM admin_level_2 WHERE code = :code"),
            {"code": municipality_code},
        )
        row = r.fetchone()
        if row:
            lid = row.id
    elif municipality_id:
        # municipality_id could be IBGE code (7 digits) or internal id
        if municipality_id > 100000:
            r = await db.execute(
                text("SELECT id FROM admin_level_2 WHERE code = :code"),
                {"code": str(municipality_id)},
            )
            row = r.fetchone()
            if row:
                lid = row.id
        else:
            lid = municipality_id

    if not lid:
        return {"error": "Municipality not found"}

    profile: dict[str, Any] = {"municipality_id": municipality_id if municipality_id else lid}

    # Safety indicators
    safety = await db.execute(
        text("SELECT year, homicide_rate, violent_crime_rate, theft_rate, risk_score FROM safety_indicators WHERE l2_id = :lid ORDER BY year DESC LIMIT 1"),
        {"lid": lid},
    )
    sr = safety.fetchone()
    if sr:
        profile["safety"] = {
            "year": sr.year,
            "homicide_rate": float(sr.homicide_rate) if sr.homicide_rate else None,
            "violent_crime_rate": float(sr.violent_crime_rate) if sr.violent_crime_rate else None,
            "theft_rate": float(sr.theft_rate) if sr.theft_rate else None,
            "risk_score": float(sr.risk_score) if sr.risk_score else None,
        }

    # Building density
    bld = await db.execute(
        text("SELECT year, total_addresses, residential_addresses, commercial_addresses, density_per_km2, urban_addresses, rural_addresses FROM building_density WHERE l2_id = :lid ORDER BY year DESC LIMIT 1"),
        {"lid": lid},
    )
    br = bld.fetchone()
    if br:
        profile["building_density"] = {
            "year": br.year,
            "total_addresses": br.total_addresses,
            "residential": br.residential_addresses,
            "commercial": br.commercial_addresses,
            "density_per_km2": float(br.density_per_km2) if br.density_per_km2 else None,
            "urban_pct": round(br.urban_addresses * 100 / br.total_addresses, 1) if br.total_addresses else 0,
        }

    # Sanitation
    san = await db.execute(
        text("SELECT year, water_coverage_pct, sewage_coverage_pct, water_losses_pct FROM sanitation_indicators WHERE l2_id = :lid ORDER BY year DESC LIMIT 1"),
        {"lid": lid},
    )
    snr = san.fetchone()
    if snr:
        profile["sanitation"] = {
            "year": snr.year,
            "water_coverage_pct": float(snr.water_coverage_pct) if snr.water_coverage_pct else None,
            "sewage_coverage_pct": float(snr.sewage_coverage_pct) if snr.sewage_coverage_pct else None,
            "water_losses_pct": float(snr.water_losses_pct) if snr.water_losses_pct else None,
        }

    # Municipal planning
    plan = await db.execute(
        text("SELECT munic_year, has_plano_diretor, has_zoning_law, has_building_code, has_digital_governance FROM municipal_planning WHERE l2_id = :lid ORDER BY munic_year DESC LIMIT 1"),
        {"lid": lid},
    )
    pr = plan.fetchone()
    if pr:
        profile["planning"] = {
            "year": pr.munic_year,
            "has_plano_diretor": pr.has_plano_diretor,
            "has_zoning_law": pr.has_zoning_law,
            "has_building_code": pr.has_building_code,
            "has_digital_governance": pr.has_digital_governance,
        }

    # Backhaul presence
    bh = await db.execute(
        text("SELECT year, has_fiber_backhaul, has_radio_backhaul, has_satellite_backhaul, dominant_technology, provider_count FROM backhaul_presence WHERE l2_id = :lid ORDER BY year DESC LIMIT 1"),
        {"lid": lid},
    )
    bhr = bh.fetchone()
    if bhr:
        profile["backhaul"] = {
            "year": bhr.year,
            "has_fiber_backhaul": bhr.has_fiber_backhaul,
            "has_radio_backhaul": bhr.has_radio_backhaul,
            "has_satellite_backhaul": bhr.has_satellite_backhaul,
            "dominant_technology": bhr.dominant_technology,
            "provider_count": bhr.provider_count,
        }

    # Economic indicators
    eco = await db.execute(
        text("SELECT year, pib_municipal_brl, pib_per_capita_brl, formal_employment FROM economic_indicators WHERE l2_id = :lid ORDER BY year DESC LIMIT 1"),
        {"lid": lid},
    )
    er = eco.fetchone()
    if er:
        profile["economic"] = {
            "year": er.year,
            "pib_municipal_brl": float(er.pib_municipal_brl) if er.pib_municipal_brl else None,
            "pib_per_capita_brl": float(er.pib_per_capita_brl) if er.pib_per_capita_brl else None,
            "formal_employment": er.formal_employment,
        }

    # Population projections
    pop = await db.execute(
        text("SELECT year, projected_population, growth_rate FROM population_projections WHERE l2_id = :lid ORDER BY year DESC LIMIT 3"),
        {"lid": lid},
    )
    pop_rows = pop.fetchall()
    if pop_rows:
        profile["population_projections"] = [
            {
                "year": r.year,
                "projected_population": r.projected_population,
                "growth_rate": float(r.growth_rate) if r.growth_rate else None,
            }
            for r in pop_rows
        ]

    return profile


# ---------------------------------------------------------------------------
# Raio-X: Competitive Dynamics (market share over time)
# ---------------------------------------------------------------------------

@router.get("/raio-x/dinamica")
async def raio_x_dinamica(
    provider_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Competitive dynamics: how a provider's market position changed over time.

    Data comes from competitive_analysis table where provider_details is a JSONB
    array of {provider_id, subscribers, market_share} per municipality per period.
    """
    group_name = _PROVIDER_TO_GROUP.get(provider_id)
    if group_name:
        pids = PROVIDER_GROUPS[group_name]
    else:
        pids = [provider_id]

    # Extract this provider's data from JSONB provider_details across all periods
    pids_str = ",".join(str(p) for p in pids)
    sql = text(f"""
        SELECT ca.year_month,
               COUNT(DISTINCT ca.l2_id) AS municipalities,
               SUM((pd->>'subscribers')::bigint) AS total_subs,
               AVG((pd->>'market_share')::float) AS avg_share,
               SUM(CASE WHEN ca.leader_provider_id = ANY(:pids) THEN 1 ELSE 0 END) AS markets_as_leader
        FROM competitive_analysis ca,
             jsonb_array_elements(ca.provider_details::jsonb) pd
        WHERE (pd->>'provider_id')::int = ANY(:pids)
        GROUP BY ca.year_month
        ORDER BY ca.year_month
    """)
    res = await db.execute(sql, {"pids": pids})
    rows = res.fetchall()

    if not rows:
        return {"provider_id": provider_id, "periods": [], "summary": {}}

    periods = [
        {
            "period": r.year_month,
            "total_subscribers": int(r.total_subs) if r.total_subs else 0,
            "municipalities": r.municipalities,
            "avg_market_share": round(float(r.avg_share) * 100, 2) if r.avg_share else 0,
            "markets_as_leader": r.markets_as_leader,
        }
        for r in rows
    ]

    # Growth summary
    if len(periods) >= 2:
        latest = periods[-1]
        earliest = periods[0]
        sub_growth = (
            (latest["total_subscribers"] - earliest["total_subscribers"])
            / earliest["total_subscribers"] * 100
            if earliest["total_subscribers"] > 0 else 0
        )
        muni_growth = latest["municipalities"] - earliest["municipalities"]
    else:
        sub_growth = 0
        muni_growth = 0

    return {
        "provider_id": provider_id,
        "periods": periods,
        "summary": {
            "subscriber_growth_pct": round(sub_growth, 1),
            "municipality_change": muni_growth,
            "total_periods": len(periods),
        },
    }


# ---------------------------------------------------------------------------
# Raio-X: FUST/FUNTTEL Government Fund Spending
# ---------------------------------------------------------------------------

@router.get("/raio-x/fust")
async def raio_x_fust(
    db: AsyncSession = Depends(get_db),
):
    """FUST/FUNTTEL government fund spending summary (industry-wide, not per-provider)."""
    sql = text("""
        SELECT year, SUM(value_committed_brl) as committed,
               SUM(value_paid_brl) as paid, COUNT(*) as records
        FROM fust_spending
        GROUP BY year ORDER BY year DESC
    """)
    res = await db.execute(sql)
    rows = res.fetchall()

    by_year = [
        {
            "year": r.year,
            "committed_brl": float(r.committed) if r.committed else 0,
            "paid_brl": float(r.paid) if r.paid else 0,
            "records": r.records,
        }
        for r in rows
    ]

    total_committed = sum(y["committed_brl"] for y in by_year)
    total_paid = sum(y["paid_brl"] for y in by_year)

    return {
        "total_committed_brl": total_committed,
        "total_paid_brl": total_paid,
        "by_year": by_year,
        "years_available": len(by_year),
    }


# ---------------------------------------------------------------------------
# Waitlist
# ---------------------------------------------------------------------------

from pydantic import BaseModel, EmailStr


class WaitlistRequest(BaseModel):
    email: str
    name: str | None = None
    company: str | None = None
    role: str | None = None


@router.post("/waitlist")
async def join_waitlist(req: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    """Add an email to the pre-launch waitlist."""
    email = req.email.strip().lower()
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"detail": "E-mail inválido."})
    try:
        await db.execute(
            text("""
                INSERT INTO waitlist (email, name, company, role)
                VALUES (:email, :name, :company, :role)
                ON CONFLICT (email) DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, waitlist.name),
                    company = COALESCE(EXCLUDED.company, waitlist.company),
                    role = COALESCE(EXCLUDED.role, waitlist.role)
            """),
            {"email": email, "name": req.name, "company": req.company, "role": req.role},
        )
        await db.commit()
    except Exception:
        logger.exception("Waitlist insert failed")
        return JSONResponse(status_code=500, content={"detail": "Erro interno."})
    # Get position
    result = await db.execute(text("SELECT COUNT(*) FROM waitlist WHERE id <= (SELECT id FROM waitlist WHERE email = :email)"), {"email": email})
    position = result.scalar() or 0
    return {"ok": True, "position": position}
