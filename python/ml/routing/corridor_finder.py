"""Infrastructure corridor identification for fiber deployment.

Identifies road segments that run alongside power lines or existing fiber
infrastructure.  These corridor segments receive cost bonuses in the
fiber routing algorithm because co-deployment with existing utilities
reduces construction costs (shared right-of-way, existing poles, etc.).
"""

import logging
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)

# Default buffer distances (meters)
DEFAULT_POWER_BUFFER_M = 50      # Road within 50m of a power line
DEFAULT_FIBER_BUFFER_M = 100     # Road within 100m of a known fiber provider


def find_power_corridors(
    municipality_id: int,
    buffer_m: float = DEFAULT_POWER_BUFFER_M,
    conn=None,
) -> set:
    """Find road segments that run alongside power lines.

    A road segment is considered a power corridor if any part of it lies
    within ``buffer_m`` meters of a power line geometry.  Such segments
    are preferred for aerial fiber deployment because existing utility
    poles can often be shared (postes compartilhados).

    Args:
        municipality_id: admin_level_2.id for centroid-based spatial lookup.
        buffer_m: Buffer distance in meters around power lines.
        conn: Optional psycopg2 connection.

    Returns:
        Set of road_segments.id values that qualify as power corridors.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return set()

    corridor_ids: set = set()

    try:
        with conn.cursor() as cur:
            # Get municipality centroid for spatial scope
            cur.execute(
                "SELECT ST_X(centroid), ST_Y(centroid) FROM admin_level_2 WHERE id = %s",
                (municipality_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                logger.warning(
                    "Municipality %d has no centroid; cannot find corridors",
                    municipality_id,
                )
                return corridor_ids

            center_lon, center_lat = row

            # Find road segments within 30 km of centroid that are also
            # within buffer_m of a power line
            cur.execute(
                """
                SELECT DISTINCT rs.id
                FROM road_segments rs
                JOIN power_lines pl
                    ON ST_DWithin(rs.geom::geography, pl.geom::geography, %s)
                WHERE ST_DWithin(
                    rs.geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    30000
                )
                """,
                (buffer_m, center_lon, center_lat),
            )
            rows = cur.fetchall()
            corridor_ids = {r[0] for r in rows}

        logger.info(
            "Found %d power corridor road segments for municipality %d "
            "(buffer=%dm)",
            len(corridor_ids),
            municipality_id,
            int(buffer_m),
        )

    except Exception as exc:
        logger.error("Error finding power corridors: %s", exc)
    finally:
        if own_conn:
            conn.close()

    return corridor_ids


def find_existing_fiber_corridors(
    municipality_id: int,
    conn=None,
) -> set:
    """Find road segments where fiber providers already operate.

    Uses broadband_subscribers data joined with base_stations as a proxy
    for existing fiber presence.  Road segments near municipalities with
    fiber subscribers are flagged as potential existing-fiber corridors,
    since fiber backhaul likely follows major roads in those areas.

    This is an approximation: ideally we would have actual fiber route
    geometries, but those are proprietary.  Instead we flag road segments
    near the centroid of municipalities that have fiber subscribers as
    corridors where co-location may be possible.

    Args:
        municipality_id: admin_level_2.id for spatial lookup.
        conn: Optional psycopg2 connection.

    Returns:
        Set of road_segments.id values near known fiber deployments.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return set()

    corridor_ids: set = set()

    try:
        with conn.cursor() as cur:
            # Get municipality centroid
            cur.execute(
                "SELECT ST_X(centroid), ST_Y(centroid) FROM admin_level_2 WHERE id = %s",
                (municipality_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                return corridor_ids

            center_lon, center_lat = row

            # Check if there are fiber subscribers in the municipality
            cur.execute(
                """
                SELECT COUNT(*)
                FROM broadband_subscribers bs
                WHERE bs.l2_id = %s
                  AND bs.technology = 'fiber'
                  AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
                  AND bs.subscribers > 0
                """,
                (municipality_id,),
            )
            fiber_row = cur.fetchone()
            has_fiber = fiber_row and fiber_row[0] and fiber_row[0] > 0

            if not has_fiber:
                logger.debug(
                    "No fiber subscribers in municipality %d; no fiber corridors",
                    municipality_id,
                )
                return corridor_ids

            # If fiber is present, flag major road segments (primary, secondary,
            # trunk) near the centroid as likely fiber corridors.
            # Fiber backhaul typically follows major roads.
            cur.execute(
                """
                SELECT rs.id
                FROM road_segments rs
                WHERE ST_DWithin(
                    rs.geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    15000
                )
                AND rs.highway_class IN (
                    'motorway', 'motorway_link',
                    'trunk', 'trunk_link',
                    'primary', 'primary_link',
                    'secondary', 'secondary_link'
                )
                """,
                (center_lon, center_lat),
            )
            rows = cur.fetchall()
            corridor_ids = {r[0] for r in rows}

        logger.info(
            "Found %d existing-fiber corridor segments for municipality %d",
            len(corridor_ids),
            municipality_id,
        )

    except Exception as exc:
        logger.error("Error finding fiber corridors: %s", exc)
    finally:
        if own_conn:
            conn.close()

    return corridor_ids


def find_all_corridors(
    municipality_id: int,
    power_buffer_m: float = DEFAULT_POWER_BUFFER_M,
    conn=None,
) -> dict:
    """Find both power and fiber corridors for a municipality.

    Convenience function that calls both find_power_corridors and
    find_existing_fiber_corridors with a shared connection.

    Args:
        municipality_id: admin_level_2.id.
        power_buffer_m: Buffer for power line proximity.
        conn: Optional psycopg2 connection.

    Returns:
        Dictionary with:
            power_corridor_ids: Set of road segment IDs near power lines.
            fiber_corridor_ids: Set of road segment IDs near existing fiber.
            total_corridor_segments: Count of unique corridor segments.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return {
                "power_corridor_ids": set(),
                "fiber_corridor_ids": set(),
                "total_corridor_segments": 0,
            }

    try:
        power_ids = find_power_corridors(municipality_id, power_buffer_m, conn)
        fiber_ids = find_existing_fiber_corridors(municipality_id, conn)

        all_ids = power_ids | fiber_ids

        return {
            "power_corridor_ids": power_ids,
            "fiber_corridor_ids": fiber_ids,
            "total_corridor_segments": len(all_ids),
        }
    finally:
        if own_conn:
            conn.close()
