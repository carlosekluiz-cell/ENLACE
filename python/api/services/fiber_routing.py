"""
Fiber Route Planning Service — pgRouting-based shortest-path fiber routing.

Uses PostgreSQL pgRouting extension to compute least-cost fiber routes on the
6.4M-segment OSM road network.  The road_segments table must have pgRouting
topology built (source/target columns populated via pgr_createTopology) and
the road_segments_vertices_pgr table must exist.

BOM (Bill of Materials) costs are based on Brazilian telecom market rates.
"""

import logging
import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BOM cost constants (Brazilian market, BRL)
# ---------------------------------------------------------------------------
BOM_COSTS = {
    "trunk_fiber_48core_per_km": 18_000.0,
    "distribution_fiber_12core_per_km": 8_000.0,
    "drop_cable_2core_per_km": 2_500.0,
    "splice_closure_each": 800.0,
    "splice_closure_interval_m": 2_000.0,
    "handhole_each": 1_200.0,
    "handhole_interval_m": 500.0,
    "olt_port_each": 3_500.0,
    "ont_each": 350.0,
}

# Highway classes that indicate trunk/backbone routes
TRUNK_CLASSES = {"motorway", "motorway_link", "trunk", "trunk_link"}
# Highway classes that indicate distribution routes
DISTRIBUTION_CLASSES = {"primary", "primary_link", "secondary", "secondary_link"}
# Everything else is drop/last-mile


# ---------------------------------------------------------------------------
# Topology check
# ---------------------------------------------------------------------------

async def _check_topology(db: AsyncSession) -> bool:
    """Verify that pgRouting topology is built on road_segments.

    Returns True if the topology is ready (road_segments_vertices_pgr exists
    and source/target columns are populated).
    """
    # Check if vertices table exists
    result = await db.execute(text("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'road_segments_vertices_pgr'
        )
    """))
    vertices_exist = result.scalar()

    if not vertices_exist:
        return False

    # Check if source/target are populated
    result = await db.execute(text("""
        SELECT COUNT(*) FROM road_segments
        WHERE source IS NOT NULL AND source > 0
        LIMIT 1
    """))
    count = result.scalar()
    return count > 0


# ---------------------------------------------------------------------------
# Nearest vertex lookup
# ---------------------------------------------------------------------------

async def find_nearest_vertex(
    db: AsyncSession,
    lon: float,
    lat: float,
) -> Optional[dict[str, Any]]:
    """Find the nearest pgRouting vertex to a geographic point.

    Uses the road_segments_vertices_pgr table created by pgr_createTopology.
    Performs a KNN lookup using the PostGIS <-> distance operator for speed.

    Args:
        db: Async SQLAlchemy session.
        lon: Longitude (WGS84).
        lat: Latitude (WGS84).

    Returns:
        Dict with vertex id, lon, lat, and distance_m, or None if not found.
    """
    sql = text("""
        SELECT
            id,
            ST_X(the_geom) AS lon,
            ST_Y(the_geom) AS lat,
            ST_Distance(
                the_geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) AS distance_m
        FROM road_segments_vertices_pgr
        ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 1
    """)

    result = await db.execute(sql, {"lon": lon, "lat": lat})
    row = result.fetchone()

    if not row:
        return None

    return {
        "id": row.id,
        "lon": float(row.lon),
        "lat": float(row.lat),
        "distance_m": round(float(row.distance_m), 1),
    }


# ---------------------------------------------------------------------------
# Route computation
# ---------------------------------------------------------------------------

async def compute_route(
    db: AsyncSession,
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
) -> dict[str, Any]:
    """Compute the shortest fiber route between two points using pgr_dijkstra.

    Snaps start/end to nearest road vertices, runs Dijkstra on the pgRouting
    topology, and returns the route geometry as GeoJSON plus a full BOM.

    Args:
        db: Async SQLAlchemy session.
        start_lon, start_lat: Origin coordinates (WGS84).
        end_lon, end_lat: Destination coordinates (WGS84).

    Returns:
        Dict with route_geojson (FeatureCollection), total_distance_m,
        total_distance_km, bom, estimated_cost_brl, and status.

    Raises:
        ValueError: If topology is not built or vertices cannot be found.
    """
    # 1. Verify topology
    topology_ready = await _check_topology(db)
    if not topology_ready:
        raise ValueError(
            "pgRouting topology not built. Run: "
            "SELECT pgr_createTopology('road_segments', 0.0001, 'geom', 'id') "
            "to build the topology before using fiber route planning."
        )

    # 2. Find nearest vertices
    start_vertex = await find_nearest_vertex(db, start_lon, start_lat)
    end_vertex = await find_nearest_vertex(db, end_lon, end_lat)

    if start_vertex is None:
        raise ValueError(
            f"No road vertex found near start point ({start_lon}, {start_lat})"
        )
    if end_vertex is None:
        raise ValueError(
            f"No road vertex found near end point ({end_lon}, {end_lat})"
        )

    if start_vertex["id"] == end_vertex["id"]:
        return {
            "status": "success",
            "message": "Start and end snap to the same vertex",
            "route_geojson": {
                "type": "FeatureCollection",
                "features": [],
            },
            "total_distance_m": 0.0,
            "total_distance_km": 0.0,
            "bom": generate_bom(0.0, []),
            "estimated_cost_brl": 0.0,
            "start_vertex": start_vertex,
            "end_vertex": end_vertex,
        }

    # 3. Run pgr_dijkstra and join back to road_segments for geometry
    route_sql = text("""
        SELECT
            rs.id AS segment_id,
            rs.highway_class,
            rs.name AS road_name,
            rs.length_m,
            d.seq,
            d.cost AS edge_cost,
            ST_AsGeoJSON(rs.geom)::json AS geojson
        FROM pgr_dijkstra(
            'SELECT id, source, target, cost, reverse_cost FROM road_segments',
            :start_id,
            :end_id,
            directed := false
        ) AS d
        JOIN road_segments rs ON d.edge = rs.id
        WHERE d.edge != -1
        ORDER BY d.seq
    """)

    result = await db.execute(route_sql, {
        "start_id": start_vertex["id"],
        "end_id": end_vertex["id"],
    })
    rows = result.fetchall()

    if not rows:
        return {
            "status": "no_path",
            "message": (
                "No connected path found between the two points. "
                "The road network may be disconnected between these locations."
            ),
            "route_geojson": {"type": "FeatureCollection", "features": []},
            "total_distance_m": 0.0,
            "total_distance_km": 0.0,
            "bom": generate_bom(0.0, []),
            "estimated_cost_brl": 0.0,
            "start_vertex": start_vertex,
            "end_vertex": end_vertex,
        }

    # 4. Build GeoJSON FeatureCollection from route segments
    features = []
    total_distance_m = 0.0
    highway_classes = []

    for row in rows:
        length_m = float(row.length_m or row.edge_cost or 0)
        total_distance_m += length_m
        hwy_class = (row.highway_class or "unclassified").lower()
        highway_classes.append(hwy_class)

        features.append({
            "type": "Feature",
            "geometry": row.geojson,
            "properties": {
                "segment_id": row.segment_id,
                "highway_class": hwy_class,
                "road_name": row.road_name or "",
                "length_m": round(length_m, 1),
                "seq": row.seq,
            },
        })

    total_distance_km = total_distance_m / 1000.0
    bom = generate_bom(total_distance_m, highway_classes)

    route_geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    logger.info(
        "Fiber route computed via pgRouting: %.2f km, %d segments, R$%.0f",
        total_distance_km,
        len(features),
        bom["total_cost_brl"],
    )

    return {
        "status": "success",
        "route_geojson": route_geojson,
        "total_distance_m": round(total_distance_m, 1),
        "total_distance_km": round(total_distance_km, 3),
        "segment_count": len(features),
        "bom": bom,
        "estimated_cost_brl": bom["total_cost_brl"],
        "start_vertex": start_vertex,
        "end_vertex": end_vertex,
    }


# ---------------------------------------------------------------------------
# Corridor computation (route + buffer for right-of-way analysis)
# ---------------------------------------------------------------------------

async def compute_corridor(
    db: AsyncSession,
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float,
    buffer_m: float = 1000.0,
) -> dict[str, Any]:
    """Compute fiber route plus a buffer corridor polygon for ROW analysis.

    Runs the same Dijkstra routing as compute_route(), then creates a buffer
    polygon around the route for right-of-way / environmental analysis.

    Args:
        db: Async SQLAlchemy session.
        start_lon, start_lat: Origin coordinates (WGS84).
        end_lon, end_lat: Destination coordinates (WGS84).
        buffer_m: Buffer width in meters around the route (default 1000).

    Returns:
        Dict with route data (same as compute_route) plus corridor_geojson
        (GeoJSON Polygon/MultiPolygon of the buffered corridor).
    """
    # 1. Verify topology
    topology_ready = await _check_topology(db)
    if not topology_ready:
        raise ValueError(
            "pgRouting topology not built. Run: "
            "SELECT pgr_createTopology('road_segments', 0.0001, 'geom', 'id') "
            "to build the topology before using fiber route planning."
        )

    # 2. Find nearest vertices
    start_vertex = await find_nearest_vertex(db, start_lon, start_lat)
    end_vertex = await find_nearest_vertex(db, end_lon, end_lat)

    if start_vertex is None:
        raise ValueError(
            f"No road vertex found near start point ({start_lon}, {start_lat})"
        )
    if end_vertex is None:
        raise ValueError(
            f"No road vertex found near end point ({end_lon}, {end_lat})"
        )

    if start_vertex["id"] == end_vertex["id"]:
        return {
            "status": "success",
            "message": "Start and end snap to the same vertex",
            "route_geojson": {"type": "FeatureCollection", "features": []},
            "corridor_geojson": None,
            "total_distance_m": 0.0,
            "total_distance_km": 0.0,
            "buffer_m": buffer_m,
            "bom": generate_bom(0.0, []),
            "estimated_cost_brl": 0.0,
            "start_vertex": start_vertex,
            "end_vertex": end_vertex,
        }

    # 3. Run pgr_dijkstra, collect route geometry, and build corridor in one query
    corridor_sql = text("""
        WITH route AS (
            SELECT
                rs.id AS segment_id,
                rs.highway_class,
                rs.name AS road_name,
                rs.length_m,
                rs.geom,
                d.seq,
                d.cost AS edge_cost,
                ST_AsGeoJSON(rs.geom)::json AS geojson
            FROM pgr_dijkstra(
                'SELECT id, source, target, cost, reverse_cost FROM road_segments',
                :start_id,
                :end_id,
                directed := false
            ) AS d
            JOIN road_segments rs ON d.edge = rs.id
            WHERE d.edge != -1
            ORDER BY d.seq
        ),
        merged AS (
            SELECT ST_Union(geom) AS route_geom
            FROM route
        ),
        corridor AS (
            SELECT ST_AsGeoJSON(
                ST_Buffer(route_geom::geography, :buffer_m)::geometry
            )::json AS corridor_geojson
            FROM merged
        )
        SELECT
            r.segment_id,
            r.highway_class,
            r.road_name,
            r.length_m,
            r.seq,
            r.edge_cost,
            r.geojson,
            c.corridor_geojson
        FROM route r
        CROSS JOIN corridor c
        ORDER BY r.seq
    """)

    result = await db.execute(corridor_sql, {
        "start_id": start_vertex["id"],
        "end_id": end_vertex["id"],
        "buffer_m": buffer_m,
    })
    rows = result.fetchall()

    if not rows:
        return {
            "status": "no_path",
            "message": (
                "No connected path found between the two points. "
                "The road network may be disconnected between these locations."
            ),
            "route_geojson": {"type": "FeatureCollection", "features": []},
            "corridor_geojson": None,
            "total_distance_m": 0.0,
            "total_distance_km": 0.0,
            "buffer_m": buffer_m,
            "bom": generate_bom(0.0, []),
            "estimated_cost_brl": 0.0,
            "start_vertex": start_vertex,
            "end_vertex": end_vertex,
        }

    # 4. Build response
    features = []
    total_distance_m = 0.0
    highway_classes = []
    corridor_geojson = rows[0].corridor_geojson  # same for all rows

    for row in rows:
        length_m = float(row.length_m or row.edge_cost or 0)
        total_distance_m += length_m
        hwy_class = (row.highway_class or "unclassified").lower()
        highway_classes.append(hwy_class)

        features.append({
            "type": "Feature",
            "geometry": row.geojson,
            "properties": {
                "segment_id": row.segment_id,
                "highway_class": hwy_class,
                "road_name": row.road_name or "",
                "length_m": round(length_m, 1),
                "seq": row.seq,
            },
        })

    total_distance_km = total_distance_m / 1000.0
    bom = generate_bom(total_distance_m, highway_classes)

    route_geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Wrap corridor in a Feature
    corridor_feature = None
    if corridor_geojson:
        corridor_feature = {
            "type": "Feature",
            "geometry": corridor_geojson,
            "properties": {
                "buffer_m": buffer_m,
                "route_distance_km": round(total_distance_km, 3),
            },
        }

    logger.info(
        "Fiber corridor computed: %.2f km route, %dm buffer, %d segments",
        total_distance_km,
        buffer_m,
        len(features),
    )

    return {
        "status": "success",
        "route_geojson": route_geojson,
        "corridor_geojson": corridor_feature,
        "total_distance_m": round(total_distance_m, 1),
        "total_distance_km": round(total_distance_km, 3),
        "buffer_m": buffer_m,
        "segment_count": len(features),
        "bom": bom,
        "estimated_cost_brl": bom["total_cost_brl"],
        "start_vertex": start_vertex,
        "end_vertex": end_vertex,
    }


# ---------------------------------------------------------------------------
# Bill of Materials (BOM) generation
# ---------------------------------------------------------------------------

def generate_bom(
    total_distance_m: float,
    highway_classes: list[str],
) -> dict[str, Any]:
    """Generate a fiber deployment Bill of Materials based on route distance.

    Categorizes the route into trunk, distribution, and drop segments
    based on the highway_class of each segment, then calculates materials
    and costs.

    Args:
        total_distance_m: Total route distance in meters.
        highway_classes: List of highway_class values for each route segment
            (used to determine cable type proportions).

    Returns:
        Dict with itemized BOM, unit costs, quantities, and total cost.
    """
    if total_distance_m <= 0:
        return {
            "items": [],
            "total_cost_brl": 0.0,
            "total_distance_km": 0.0,
            "cable_breakdown": {
                "trunk_48core_km": 0.0,
                "distribution_12core_km": 0.0,
                "drop_2core_km": 0.0,
            },
        }

    total_km = total_distance_m / 1000.0

    # Classify route segments by cable type
    trunk_count = 0
    distribution_count = 0
    drop_count = 0

    for hwy in highway_classes:
        hwy_lower = hwy.lower() if hwy else "unclassified"
        if hwy_lower in TRUNK_CLASSES:
            trunk_count += 1
        elif hwy_lower in DISTRIBUTION_CLASSES:
            distribution_count += 1
        else:
            drop_count += 1

    total_segments = max(trunk_count + distribution_count + drop_count, 1)

    # Proportional distances
    trunk_km = total_km * (trunk_count / total_segments)
    distribution_km = total_km * (distribution_count / total_segments)
    drop_km = total_km * (drop_count / total_segments)

    # Calculate quantities
    splice_closures = max(1, math.ceil(
        total_distance_m / BOM_COSTS["splice_closure_interval_m"]
    ))
    handholes = max(1, math.ceil(
        total_distance_m / BOM_COSTS["handhole_interval_m"]
    ))

    # For OLT/ONT: 1 OLT at the head-end, ONT count scales with drop distance
    # Assume ~20 ONTs per km of drop cable (urban density)
    olt_ports = max(1, math.ceil(drop_km / 2.0))  # 1 port per 2km of drop
    ont_count = max(1, math.ceil(drop_km * 20))

    # Cost calculations
    trunk_cost = trunk_km * BOM_COSTS["trunk_fiber_48core_per_km"]
    distribution_cost = distribution_km * BOM_COSTS["distribution_fiber_12core_per_km"]
    drop_cost = drop_km * BOM_COSTS["drop_cable_2core_per_km"]
    splice_cost = splice_closures * BOM_COSTS["splice_closure_each"]
    handhole_cost = handholes * BOM_COSTS["handhole_each"]
    olt_cost = olt_ports * BOM_COSTS["olt_port_each"]
    ont_cost = ont_count * BOM_COSTS["ont_each"]

    total_cost = (
        trunk_cost + distribution_cost + drop_cost
        + splice_cost + handhole_cost
        + olt_cost + ont_cost
    )

    items = [
        {
            "item": "Trunk fiber cable (48-core)",
            "unit": "km",
            "quantity": round(trunk_km, 3),
            "unit_cost_brl": BOM_COSTS["trunk_fiber_48core_per_km"],
            "total_cost_brl": round(trunk_cost, 2),
        },
        {
            "item": "Distribution fiber cable (12-core)",
            "unit": "km",
            "quantity": round(distribution_km, 3),
            "unit_cost_brl": BOM_COSTS["distribution_fiber_12core_per_km"],
            "total_cost_brl": round(distribution_cost, 2),
        },
        {
            "item": "Drop cable (2-core)",
            "unit": "km",
            "quantity": round(drop_km, 3),
            "unit_cost_brl": BOM_COSTS["drop_cable_2core_per_km"],
            "total_cost_brl": round(drop_cost, 2),
        },
        {
            "item": "Splice closure",
            "unit": "each",
            "quantity": splice_closures,
            "unit_cost_brl": BOM_COSTS["splice_closure_each"],
            "total_cost_brl": round(splice_cost, 2),
            "note": f"1 every {BOM_COSTS['splice_closure_interval_m']:.0f}m",
        },
        {
            "item": "Handhole",
            "unit": "each",
            "quantity": handholes,
            "unit_cost_brl": BOM_COSTS["handhole_each"],
            "total_cost_brl": round(handhole_cost, 2),
            "note": f"1 every {BOM_COSTS['handhole_interval_m']:.0f}m",
        },
        {
            "item": "OLT port",
            "unit": "each",
            "quantity": olt_ports,
            "unit_cost_brl": BOM_COSTS["olt_port_each"],
            "total_cost_brl": round(olt_cost, 2),
        },
        {
            "item": "ONT",
            "unit": "each",
            "quantity": ont_count,
            "unit_cost_brl": BOM_COSTS["ont_each"],
            "total_cost_brl": round(ont_cost, 2),
        },
    ]

    return {
        "items": items,
        "total_cost_brl": round(total_cost, 2),
        "total_distance_km": round(total_km, 3),
        "cable_breakdown": {
            "trunk_48core_km": round(trunk_km, 3),
            "distribution_12core_km": round(distribution_km, 3),
            "drop_2core_km": round(drop_km, 3),
        },
    }
