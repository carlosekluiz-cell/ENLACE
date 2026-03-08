"""Market intelligence service — bridges async API with sync ML modules.

Wraps synchronous ML module calls (which use psycopg2 directly) so they
can be invoked safely from async FastAPI endpoints via a thread-pool
executor.  Also provides direct async database helpers for queries that
use the async SQLAlchemy session.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Thread pool for running sync ML code in async context.
# Sized to 4 workers — these are IO-heavy (DB queries inside the ML
# modules use psycopg2 sync), so a small pool prevents overloading
# the database with too many concurrent sync connections.
_executor = ThreadPoolExecutor(max_workers=4)


# ═══════════════════════════════════════════════════════════════════════
# Opportunity Scoring (DB look-up)
# ═══════════════════════════════════════════════════════════════════════


async def score_area(
    db: AsyncSession,
    country_code: str,
    area_type: str,
    area_id: str,
) -> Optional[dict[str, Any]]:
    """Look up pre-computed opportunity score from the database.

    Queries ``opportunity_scores`` joined with ``admin_level_2``,
    ``admin_level_1``, and ``census_demographics`` to return a rich
    score payload.

    Args:
        db: Async SQLAlchemy session.
        country_code: ISO country code (e.g. 'BR').
        area_type: Geographic level — currently only 'municipality'.
        area_id: The ``admin_level_2.code`` (IBGE municipality code).

    Returns:
        Score dictionary or ``None`` if no matching record is found.
    """
    sql = text("""
        SELECT
            os.composite_score,
            os.confidence,
            os.demand_score,
            os.competition_score,
            os.infrastructure_score,
            os.growth_score,
            os.top_factors,
            os.scored_at,
            os.model_version,
            a2.id   AS l2_id,
            a2.code AS municipality_code,
            a2.name AS municipality_name,
            a1.abbrev AS state_abbrev,
            a2.area_km2,
            cd_agg.total_households,
            cd_agg.total_population
        FROM opportunity_scores os
        JOIN admin_level_2 a2 ON a2.id = os.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        LEFT JOIN LATERAL (
            SELECT
                SUM(cd.total_households) AS total_households,
                SUM(cd.total_population) AS total_population
            FROM census_tracts ct
            JOIN census_demographics cd ON cd.tract_id = ct.id
            WHERE ct.l2_id = a2.id
        ) cd_agg ON TRUE
        WHERE a2.code = :area_id
          AND a2.country_code = :country_code
        ORDER BY os.scored_at DESC
        LIMIT 1
    """)

    result = await db.execute(
        sql,
        {"area_id": area_id, "country_code": country_code},
    )
    row = result.fetchone()

    if not row:
        return None

    return {
        "composite_score": float(row.composite_score),
        "confidence": float(row.confidence),
        "sub_scores": {
            "demand": float(row.demand_score),
            "competition": float(row.competition_score),
            "infrastructure": float(row.infrastructure_score),
            "growth": float(row.growth_score),
        },
        "top_factors": row.top_factors if row.top_factors else [],
        "market_summary": {
            "municipality_id": row.l2_id,
            "municipality_code": row.municipality_code.strip() if row.municipality_code else "",
            "municipality_name": row.municipality_name,
            "state_abbrev": row.state_abbrev,
            "area_km2": float(row.area_km2) if row.area_km2 else None,
            "total_households": int(row.total_households) if row.total_households else None,
            "total_population": int(row.total_population) if row.total_population else None,
            "model_version": row.model_version,
            "scored_at": row.scored_at.isoformat() if row.scored_at else None,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# Top Opportunities (DB look-up)
# ═══════════════════════════════════════════════════════════════════════


async def get_top_opportunities(
    db: AsyncSession,
    country: str = "BR",
    state: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get top-scoring municipalities by opportunity score.

    Joins ``opportunity_scores`` with ``admin_level_2``,
    ``admin_level_1``, and aggregated ``census_demographics`` for a
    complete picture.

    Args:
        db: Async SQLAlchemy session.
        country: ISO country code filter.
        state: Optional state abbreviation filter (e.g. 'SP').
        min_score: Minimum composite score threshold.
        limit: Maximum number of results to return.

    Returns:
        List of opportunity summary dictionaries, ordered by score
        descending.
    """
    # Build the WHERE clause dynamically based on optional filters
    where_clauses = [
        "a2.country_code = :country",
        "os.composite_score >= :min_score",
    ]
    params: dict[str, Any] = {
        "country": country,
        "min_score": min_score,
        "limit": limit,
    }

    if state:
        where_clauses.append("a1.abbrev = :state")
        params["state"] = state

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT DISTINCT ON (a2.id)
            a2.id   AS l2_id,
            a2.code AS municipality_code,
            a2.name AS municipality_name,
            a1.abbrev AS state_abbrev,
            os.composite_score,
            os.confidence,
            os.demand_score,
            os.competition_score,
            os.infrastructure_score,
            os.growth_score,
            a2.area_km2,
            cd_agg.total_households,
            cd_agg.total_population
        FROM opportunity_scores os
        JOIN admin_level_2 a2 ON a2.id = os.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        LEFT JOIN LATERAL (
            SELECT
                SUM(cd.total_households) AS total_households,
                SUM(cd.total_population) AS total_population
            FROM census_tracts ct
            JOIN census_demographics cd ON cd.tract_id = ct.id
            WHERE ct.l2_id = a2.id
        ) cd_agg ON TRUE
        WHERE {where_sql}
        ORDER BY a2.id, os.scored_at DESC
    """)

    # Wrap in a subquery so we can ORDER BY composite_score and LIMIT
    outer_sql = text(f"""
        SELECT *
        FROM (
            SELECT DISTINCT ON (a2.id)
                a2.id   AS l2_id,
                a2.code AS municipality_code,
                a2.name AS municipality_name,
                a1.abbrev AS state_abbrev,
                os.composite_score,
                os.confidence,
                os.demand_score,
                os.competition_score,
                os.infrastructure_score,
                os.growth_score,
                a2.area_km2,
                cd_agg.total_households,
                cd_agg.total_population
            FROM opportunity_scores os
            JOIN admin_level_2 a2 ON a2.id = os.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            LEFT JOIN LATERAL (
                SELECT
                    SUM(cd.total_households) AS total_households,
                    SUM(cd.total_population) AS total_population
                FROM census_tracts ct
                JOIN census_demographics cd ON cd.tract_id = ct.id
                WHERE ct.l2_id = a2.id
            ) cd_agg ON TRUE
            WHERE {where_sql}
            ORDER BY a2.id, os.scored_at DESC
        ) ranked
        ORDER BY ranked.composite_score DESC
        LIMIT :limit
    """)

    result = await db.execute(outer_sql, params)
    rows = result.fetchall()

    return [
        {
            "municipality_id": row.l2_id,
            "municipality_code": row.municipality_code.strip() if row.municipality_code else "",
            "name": row.municipality_name,
            "state_abbrev": row.state_abbrev,
            "score": float(row.composite_score),
            "confidence": float(row.confidence),
            "sub_scores": {
                "demand": float(row.demand_score),
                "competition": float(row.competition_score),
                "infrastructure": float(row.infrastructure_score),
                "growth": float(row.growth_score),
            },
            "area_km2": float(row.area_km2) if row.area_km2 else None,
            "households": int(row.total_households) if row.total_households else None,
            "population": int(row.total_population) if row.total_population else None,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# Financial Analysis (sync ML → thread pool)
# ═══════════════════════════════════════════════════════════════════════


def _sync_financial(
    municipality_code: str,
    from_lat: float,
    from_lon: float,
    price: float,
    technology: str,
) -> dict[str, Any]:
    """Synchronous wrapper that calls the ML financial viability module.

    This function runs inside the thread-pool executor and must not use
    any async constructs.
    """
    from python.ml.financial.viability import run_full_analysis

    return run_full_analysis(
        municipality_code=municipality_code,
        from_lat=from_lat,
        from_lon=from_lon,
        monthly_price_brl=price,
        technology=technology,
    )


async def run_financial_analysis(
    municipality_code: str,
    from_lat: float,
    from_lon: float,
    price: float,
    technology: str,
) -> dict[str, Any]:
    """Run financial viability analysis in the thread pool.

    Offloads the synchronous ``run_full_analysis`` call (which opens its
    own psycopg2 connection internally) to a background thread so it
    does not block the async event loop.

    Args:
        municipality_code: IBGE municipality code.
        from_lat: Latitude of proposed POP / starting point.
        from_lon: Longitude of proposed POP / starting point.
        price: Planned monthly subscription price in BRL.
        technology: Access technology ('fiber', 'fwa', 'dsl').

    Returns:
        Complete financial analysis dictionary from the ML module.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _sync_financial,
        municipality_code,
        from_lat,
        from_lon,
        price,
        technology,
    )


# ═══════════════════════════════════════════════════════════════════════
# Fiber Route Computation (sync ML → thread pool)
# ═══════════════════════════════════════════════════════════════════════


def _sync_compute_route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    prefer_corridors: bool,
) -> dict[str, Any]:
    """Synchronous wrapper that calls the ML routing modules.

    Builds a road graph around the midpoint of source and destination,
    optionally finds infrastructure corridors, then computes the
    least-cost fiber route and generates a BOM.
    """
    import psycopg2

    from python.ml.config import DB_CONFIG
    from python.ml.routing.bom_generator import generate_bom
    from python.ml.routing.corridor_finder import find_all_corridors
    from python.ml.routing.fiber_route import build_road_graph, compute_fiber_route

    # We need a municipality_id to scope the road graph. Find the
    # nearest municipality to the midpoint of source and destination.
    mid_lat = (from_lat + to_lat) / 2.0
    mid_lon = (from_lon + to_lon) / 2.0

    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        logger.error("Database connection failed for routing: %s", exc)
        return {
            "status": "error",
            "message": "Database connection failed",
        }

    try:
        with conn.cursor() as cur:
            # Find the nearest municipality to the midpoint
            cur.execute(
                """
                SELECT id, code, name
                FROM admin_level_2
                WHERE centroid IS NOT NULL
                ORDER BY centroid::geography <-> ST_SetSRID(
                    ST_MakePoint(%s, %s), 4326
                )::geography
                LIMIT 1
                """,
                (mid_lon, mid_lat),
            )
            muni_row = cur.fetchone()
            if not muni_row:
                return {
                    "status": "error",
                    "message": "No municipality found near the route endpoints",
                }

            municipality_id = muni_row[0]

        # Determine buffer size based on route length
        from python.ml.routing.fiber_route import _haversine_m

        direct_dist_km = _haversine_m(from_lat, from_lon, to_lat, to_lon) / 1000.0
        buffer_km = max(10.0, direct_dist_km * 1.5)

        # Find corridors if requested
        power_ids: set = set()
        fiber_ids: set = set()
        if prefer_corridors:
            corridors = find_all_corridors(municipality_id, conn=conn)
            power_ids = corridors["power_corridor_ids"]
            fiber_ids = corridors["fiber_corridor_ids"]

        # Build road graph
        graph = build_road_graph(
            municipality_id=municipality_id,
            buffer_km=buffer_km,
            conn=conn,
            power_corridor_ids=power_ids,
            fiber_corridor_ids=fiber_ids,
        )

        # Compute route
        route_result = compute_fiber_route(
            graph=graph,
            source_lat=from_lat,
            source_lon=from_lon,
            dest_lat=to_lat,
            dest_lon=to_lon,
            prefer_corridors=prefer_corridors,
        )

        # Generate BOM if route was found
        bom: dict[str, Any] = {"items": [], "grand_total_brl": 0.0, "summary": ""}
        if route_result.get("status") == "success" and route_result.get("total_length_km", 0) > 0:
            # Estimate target subscribers from premises passed
            target_subs = max(1, route_result.get("premises_passed", 0))
            bom = generate_bom(
                route_geojson=route_result.get("route_geojson"),
                total_length_km=route_result["total_length_km"],
                target_subscribers=target_subs,
                area_type="urban",  # Default; could be refined with more context
            )

        return {
            "status": route_result.get("status", "error"),
            "route": route_result.get("route_geojson"),
            "total_length_km": route_result.get("total_length_km", 0.0),
            "estimated_cost_brl": route_result.get("estimated_cost_brl", 0.0),
            "premises_passed": route_result.get("premises_passed", 0),
            "bom": bom,
            "municipality": {
                "id": muni_row[0],
                "code": muni_row[1],
                "name": muni_row[2],
            },
            "message": route_result.get("message"),
        }

    except Exception as exc:
        logger.error("Error computing fiber route: %s", exc)
        return {
            "status": "error",
            "message": f"Route computation failed: {exc}",
        }
    finally:
        conn.close()


async def compute_route(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    prefer_corridors: bool = True,
) -> dict[str, Any]:
    """Compute fiber route in the thread pool.

    Offloads the synchronous road-graph construction, Dijkstra routing,
    and BOM generation to a background thread.

    Args:
        from_lat: Source latitude (POP location).
        from_lon: Source longitude.
        to_lat: Destination latitude.
        to_lon: Destination longitude.
        prefer_corridors: Whether to apply infrastructure corridor
            bonuses when computing the route.

    Returns:
        Route result dictionary with GeoJSON, cost, and BOM.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _sync_compute_route,
        from_lat,
        from_lon,
        to_lat,
        to_lon,
        prefer_corridors,
    )


# ═══════════════════════════════════════════════════════════════════════
# Competitor Analysis (DB look-up)
# ═══════════════════════════════════════════════════════════════════════


async def get_competitors(
    db: AsyncSession,
    municipality_id: int,
) -> Optional[dict[str, Any]]:
    """Get competitive landscape for a municipality.

    Queries ``competitive_analysis`` for the latest month and enriches
    provider details with names from the ``providers`` table and
    technology info from ``broadband_subscribers``.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: ``admin_level_2.id``.

    Returns:
        Competitor data dictionary, or ``None`` if no data found.
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
        return None

    # Build provider breakdown from provider_details JSON
    providers: list[dict[str, Any]] = []
    provider_details = ca_row.provider_details or []

    if provider_details:
        provider_ids = [
            p["provider_id"] for p in provider_details if "provider_id" in p
        ]

        if provider_ids:
            # Fetch provider names
            names_sql = text("""
                SELECT id, name FROM providers WHERE id = ANY(:ids)
            """)
            names_result = await db.execute(names_sql, {"ids": provider_ids})
            name_map = {row.id: row.name for row in names_result.fetchall()}

            # Fetch dominant technology per provider
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
                providers.append({
                    "provider_id": pid,
                    "name": name_map.get(pid, f"Provider {pid}"),
                    "subscribers": pd.get("subscribers", 0),
                    "share_pct": round(pd.get("market_share", 0) * 100, 2),
                    "technology": tech_map.get(pid),
                    "growth_3m": None,
                })

    # Build threats list
    threats: list[dict[str, Any]] = []
    if ca_row.threat_level:
        threats.append({
            "level": ca_row.threat_level,
            "trend": ca_row.growth_trend,
            "description": (
                f"Market concentration (HHI: {ca_row.hhi_index:.0f}) "
                f"with {ca_row.threat_level} threat level"
            ),
        })

    return {
        "hhi_index": float(ca_row.hhi_index) if ca_row.hhi_index else 0.0,
        "providers": providers,
        "threats": threats,
    }
