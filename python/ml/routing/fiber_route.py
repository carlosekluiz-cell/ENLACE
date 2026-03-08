"""Dijkstra shortest-path fiber routing on OSM road network.

Builds a weighted graph from PostGIS road_segments and computes the
least-cost fiber route between two geographic points.  Edge weights
account for distance, road classification, terrain difficulty, and
proximity to existing infrastructure corridors (power lines, fiber).
"""

import logging
import math
from typing import Optional

import networkx as nx
import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Road class cost factors (lower = preferred for fiber deployment)
# ---------------------------------------------------------------------------
ROAD_CLASS_FACTORS = {
    "motorway":       0.8,
    "motorway_link":  0.85,
    "trunk":          0.85,
    "trunk_link":     0.9,
    "primary":        0.9,
    "primary_link":   0.95,
    "secondary":      1.0,
    "secondary_link": 1.05,
    "tertiary":       1.1,
    "tertiary_link":  1.15,
    "residential":    1.2,
    "unclassified":   1.3,
    "service":        1.4,
    "living_street":  1.3,
    "track":          2.0,
    "path":           3.0,
}

# Base cost per meter for aerial fiber deployment (BRL)
BASE_COST_PER_M = 20.0  # ~R$20k/km midpoint for urban aerial

# Corridor bonuses: multiplier applied when road segment is near infrastructure
POWER_LINE_CORRIDOR_BONUS = 0.7   # 30% cost reduction near power lines
FIBER_CORRIDOR_BONUS = 0.5        # 50% cost reduction near existing fiber

# Default terrain factor for flat urban environments
DEFAULT_TERRAIN_FACTOR = 1.0

# Approximate premises per km of road in different area types
PREMISES_PER_KM = {
    "motorway":    0,
    "trunk":       5,
    "primary":     15,
    "secondary":   25,
    "tertiary":    35,
    "residential": 50,
    "track":       5,
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in meters between two WGS84 points."""
    R = 6_371_000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    )
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def build_road_graph(
    municipality_id: int,
    buffer_km: float = 10.0,
    conn=None,
    power_corridor_ids: Optional[set] = None,
    fiber_corridor_ids: Optional[set] = None,
) -> nx.Graph:
    """Build a NetworkX graph from road_segments near a municipality centroid.

    Each road segment becomes one or more edges.  Node coordinates are the
    start/end points of each segment (snapped to a grid to merge nearby
    intersections).

    Args:
        municipality_id: admin_level_2.id for centroid lookup.
        buffer_km: Radius in km around the centroid to include roads.
        conn: Optional psycopg2 connection.
        power_corridor_ids: Set of road_segment IDs near power lines
            (from corridor_finder).
        fiber_corridor_ids: Set of road_segment IDs near existing fiber
            (from corridor_finder).

    Returns:
        NetworkX Graph with weighted edges.  Node keys are (lat, lon) tuples
        rounded to ~11 m precision.  Edge attributes include:
            weight, length_m, road_class, segment_id, cost_brl.
    """
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)

    G = nx.Graph()
    power_ids = power_corridor_ids or set()
    fiber_ids = fiber_corridor_ids or set()

    try:
        with conn.cursor() as cur:
            # Get municipality centroid
            cur.execute(
                "SELECT ST_X(centroid), ST_Y(centroid) FROM admin_level_2 WHERE id = %s",
                (municipality_id,),
            )
            row = cur.fetchone()
            if not row or row[0] is None:
                logger.warning(
                    "Municipality %d has no centroid; returning empty graph",
                    municipality_id,
                )
                return G

            center_lon, center_lat = row

            # Fetch road segments within buffer distance
            buffer_m = buffer_km * 1000.0
            cur.execute(
                """
                SELECT
                    rs.id,
                    rs.highway_class,
                    rs.length_m,
                    ST_Y(ST_StartPoint(rs.geom)) AS start_lat,
                    ST_X(ST_StartPoint(rs.geom)) AS start_lon,
                    ST_Y(ST_EndPoint(rs.geom))   AS end_lat,
                    ST_X(ST_EndPoint(rs.geom))   AS end_lon
                FROM road_segments rs
                WHERE ST_DWithin(
                    rs.geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                )
                """,
                (center_lon, center_lat, buffer_m),
            )
            segments = cur.fetchall()

        if not segments:
            logger.warning(
                "No road segments found within %.0f km of municipality %d",
                buffer_km,
                municipality_id,
            )
            return G

        logger.info(
            "Building road graph: %d segments within %.0f km of municipality %d",
            len(segments),
            buffer_km,
            municipality_id,
        )

        # Snap coordinates to ~11 m grid (4 decimal places)
        def snap(coord: float) -> float:
            return round(coord, 4)

        for seg_id, highway_class, length_m, s_lat, s_lon, e_lat, e_lon in segments:
            if s_lat is None or e_lat is None:
                continue

            node_a = (snap(s_lat), snap(s_lon))
            node_b = (snap(e_lat), snap(e_lon))

            if node_a == node_b:
                continue  # Degenerate segment

            # Use stored length or compute from coordinates
            if length_m and length_m > 0:
                dist_m = length_m
            else:
                dist_m = _haversine_m(s_lat, s_lon, e_lat, e_lon)

            if dist_m <= 0:
                continue

            # Road class factor
            road_class = (highway_class or "unclassified").lower()
            road_factor = ROAD_CLASS_FACTORS.get(road_class, 1.5)

            # Terrain factor (flat urban default; real terrain data would
            # come from elevation queries)
            terrain_factor = DEFAULT_TERRAIN_FACTOR

            # Corridor bonuses
            corridor_mult = 1.0
            if seg_id in fiber_ids:
                corridor_mult = FIBER_CORRIDOR_BONUS
            elif seg_id in power_ids:
                corridor_mult = POWER_LINE_CORRIDOR_BONUS

            # Edge cost = distance × base_cost × road_factor × terrain × corridor
            cost = dist_m * BASE_COST_PER_M * road_factor * terrain_factor * corridor_mult

            # Add nodes with coordinate attributes
            G.add_node(node_a, lat=node_a[0], lon=node_a[1])
            G.add_node(node_b, lat=node_b[0], lon=node_b[1])

            # If parallel edge already exists, keep the cheaper one
            if G.has_edge(node_a, node_b):
                existing_cost = G[node_a][node_b].get("weight", float("inf"))
                if cost >= existing_cost:
                    continue

            G.add_edge(
                node_a,
                node_b,
                weight=cost,
                length_m=dist_m,
                road_class=road_class,
                segment_id=seg_id,
                cost_brl=cost,
            )

        logger.info(
            "Road graph built: %d nodes, %d edges",
            G.number_of_nodes(),
            G.number_of_edges(),
        )

    except Exception as exc:
        logger.error("Error building road graph: %s", exc)
    finally:
        if own_conn:
            conn.close()

    return G


def _find_nearest_node(G: nx.Graph, lat: float, lon: float) -> Optional[tuple]:
    """Find the graph node nearest to (lat, lon) using Euclidean distance.

    Args:
        G: The road network graph.
        lat: Target latitude.
        lon: Target longitude.

    Returns:
        Node key (lat, lon) tuple, or None if graph is empty.
    """
    if G.number_of_nodes() == 0:
        return None

    best_node = None
    best_dist = float("inf")

    for node in G.nodes:
        n_lat, n_lon = node
        dist = _haversine_m(lat, lon, n_lat, n_lon)
        if dist < best_dist:
            best_dist = dist
            best_node = node

    logger.debug(
        "Nearest node to (%.4f, %.4f): (%.4f, %.4f) at %.0f m",
        lat,
        lon,
        best_node[0],
        best_node[1],
        best_dist,
    )
    return best_node


def compute_fiber_route(
    graph: nx.Graph,
    source_lat: float,
    source_lon: float,
    dest_lat: float,
    dest_lon: float,
    prefer_corridors: bool = True,
) -> dict:
    """Compute least-cost fiber route using Dijkstra's algorithm.

    Args:
        graph: Road network graph from build_road_graph().
        source_lat: Source point latitude (POP location).
        source_lon: Source point longitude.
        dest_lat: Destination point latitude.
        dest_lon: Destination point longitude.
        prefer_corridors: Whether corridor bonuses were applied (info only).

    Returns:
        Dictionary with:
            route_geojson: GeoJSON LineString of the route
            total_length_km: Total route length in kilometers
            estimated_cost_brl: Estimated deployment cost in BRL
            premises_passed: Estimated number of premises along the route
            node_count: Number of waypoints
            status: 'success', 'no_path', or 'error'
    """
    empty_result = {
        "route_geojson": None,
        "total_length_km": 0.0,
        "estimated_cost_brl": 0.0,
        "premises_passed": 0,
        "node_count": 0,
        "status": "error",
    }

    if graph.number_of_nodes() == 0:
        logger.warning("Cannot route on empty graph")
        empty_result["status"] = "error"
        empty_result["message"] = "Road graph is empty"
        return empty_result

    # Find nearest nodes to source and destination
    src_node = _find_nearest_node(graph, source_lat, source_lon)
    dst_node = _find_nearest_node(graph, dest_lat, dest_lon)

    if src_node is None or dst_node is None:
        empty_result["message"] = "Could not find nearest road nodes"
        return empty_result

    if src_node == dst_node:
        # Source and destination map to the same node
        geojson = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[src_node[1], src_node[0]]],
            },
            "properties": {
                "total_length_km": 0.0,
                "estimated_cost_brl": 0.0,
            },
        }
        return {
            "route_geojson": geojson,
            "total_length_km": 0.0,
            "estimated_cost_brl": 0.0,
            "premises_passed": 0,
            "node_count": 1,
            "status": "success",
        }

    # Run Dijkstra
    try:
        path = nx.dijkstra_path(graph, src_node, dst_node, weight="weight")
    except nx.NetworkXNoPath:
        logger.warning(
            "No path found between (%.4f,%.4f) and (%.4f,%.4f)",
            source_lat,
            source_lon,
            dest_lat,
            dest_lon,
        )
        empty_result["status"] = "no_path"
        empty_result["message"] = "No connected path between source and destination"
        return empty_result
    except Exception as exc:
        logger.error("Dijkstra error: %s", exc)
        empty_result["message"] = str(exc)
        return empty_result

    # Aggregate route metrics
    coordinates = []
    total_length_m = 0.0
    total_cost = 0.0
    total_premises = 0

    for i, node in enumerate(path):
        lat, lon = node
        coordinates.append([lon, lat])  # GeoJSON uses [lon, lat]

        if i > 0:
            prev = path[i - 1]
            edge_data = graph[prev][node]
            total_length_m += edge_data.get("length_m", 0)
            total_cost += edge_data.get("cost_brl", 0)

            road_class = edge_data.get("road_class", "residential")
            edge_km = edge_data.get("length_m", 0) / 1000.0
            # Look up base road class for premises estimate
            for rc_prefix, prem_per_km in PREMISES_PER_KM.items():
                if road_class.startswith(rc_prefix):
                    total_premises += int(edge_km * prem_per_km)
                    break
            else:
                total_premises += int(edge_km * 20)  # default

    total_length_km = total_length_m / 1000.0

    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "properties": {
            "total_length_km": round(total_length_km, 3),
            "estimated_cost_brl": round(total_cost, 2),
            "premises_passed": total_premises,
        },
    }

    logger.info(
        "Fiber route computed: %.2f km, %d nodes, R$%,.0f, ~%d premises",
        total_length_km,
        len(path),
        total_cost,
        total_premises,
    )

    return {
        "route_geojson": geojson,
        "total_length_km": round(total_length_km, 3),
        "estimated_cost_brl": round(total_cost, 2),
        "premises_passed": total_premises,
        "node_count": len(path),
        "status": "success",
    }
