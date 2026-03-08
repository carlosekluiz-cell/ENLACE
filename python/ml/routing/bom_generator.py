"""Bill of Materials (BOM) generator from a fiber route.

Takes a computed fiber route (GeoJSON) and generates a detailed equipment
list with quantities, unit costs, and totals.  Cable types, splitter
spacing, and splice intervals are calibrated for Brazilian ISP deployments
based on Abrint industry data.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cable types and costs (BRL per meter)
# ---------------------------------------------------------------------------
CABLE_TYPES = {
    "drop": {
        "fiber_count": 2,
        "description": "Service drop cable (2-fiber, LSZH)",
        "cost_per_m": 2.50,
    },
    "distribution_12": {
        "fiber_count": 12,
        "description": "Distribution cable 12-fiber (rural/suburban feeder)",
        "cost_per_m": 5.00,
    },
    "distribution_48": {
        "fiber_count": 48,
        "description": "Distribution cable 48-fiber (urban feeder)",
        "cost_per_m": 12.00,
    },
    "backbone_144": {
        "fiber_count": 144,
        "description": "Backbone cable 144-fiber (trunk/ring)",
        "cost_per_m": 25.00,
    },
}

# ---------------------------------------------------------------------------
# Equipment unit costs (BRL)
# ---------------------------------------------------------------------------
EQUIPMENT_COSTS = {
    "splice_enclosure": {
        "description": "Fiber splice enclosure (IP68, 96-fiber capacity)",
        "unit_cost_brl": 1_000.0,
    },
    "splitter_cabinet_1x16": {
        "description": "Optical splitter cabinet 1:16 (outdoor, IP55)",
        "unit_cost_brl": 3_000.0,
    },
    "splitter_cabinet_1x32": {
        "description": "Optical splitter cabinet 1:32 (outdoor, IP55)",
        "unit_cost_brl": 4_500.0,
    },
    "ont": {
        "description": "ONT (Optical Network Terminal) GPON/XGS-PON",
        "unit_cost_brl": 350.0,
    },
    "olt_8port": {
        "description": "OLT 8-port GPON (256 ONT capacity)",
        "unit_cost_brl": 55_000.0,
    },
    "patch_panel": {
        "description": "Fiber patch panel 24-port (for POP/cabinet)",
        "unit_cost_brl": 800.0,
    },
    "power_supply_ups": {
        "description": "UPS / battery backup for cabinet (1kVA)",
        "unit_cost_brl": 2_500.0,
    },
}

# ---------------------------------------------------------------------------
# Spacing rules (km between items)
# ---------------------------------------------------------------------------
SPLICE_INTERVAL_KM = 2.0  # Splice enclosure every 2 km or at junctions

SPLITTER_SPACING = {
    "urban":    0.5,   # Every 500m in urban areas
    "suburban": 1.0,   # Every 1 km in suburban
    "rural":    2.0,   # Every 2 km in rural
}

# Service drop cable length per subscriber (meters)
DROP_CABLE_PER_SUB_M = 30.0

# OLT capacity (subscribers per OLT)
OLT_CAPACITY = 256


def _select_trunk_cable(area_type: str) -> dict:
    """Select the appropriate trunk/distribution cable type.

    Args:
        area_type: 'urban', 'suburban', or 'rural'.

    Returns:
        Cable type dict from CABLE_TYPES.
    """
    area = area_type.lower() if area_type else "urban"
    if area == "rural":
        return CABLE_TYPES["distribution_12"]
    elif area == "suburban":
        return CABLE_TYPES["distribution_48"]
    else:
        return CABLE_TYPES["distribution_48"]


def _count_junctions_from_geojson(route_geojson: Optional[dict]) -> int:
    """Estimate number of major junctions from the route GeoJSON.

    Major junctions are approximated by counting significant direction
    changes in the route coordinates.  A change of more than 45 degrees
    is considered a junction.

    Args:
        route_geojson: GeoJSON Feature with LineString geometry.

    Returns:
        Estimated number of junctions.
    """
    if not route_geojson:
        return 0

    geom = route_geojson.get("geometry", route_geojson)
    coords = geom.get("coordinates", [])

    if len(coords) < 3:
        return 0

    junctions = 0
    for i in range(1, len(coords) - 1):
        # Compute bearing change
        prev_lon, prev_lat = coords[i - 1][0], coords[i - 1][1]
        curr_lon, curr_lat = coords[i][0], coords[i][1]
        next_lon, next_lat = coords[i + 1][0], coords[i + 1][1]

        bearing_in = math.atan2(curr_lon - prev_lon, curr_lat - prev_lat)
        bearing_out = math.atan2(next_lon - curr_lon, next_lat - curr_lat)

        angle_diff = abs(math.degrees(bearing_out - bearing_in))
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        if angle_diff > 45:
            junctions += 1

    return junctions


def generate_bom(
    route_geojson: Optional[dict],
    total_length_km: float,
    target_subscribers: int,
    area_type: str = "urban",
) -> dict:
    """Generate a Bill of Materials for fiber deployment along a route.

    Args:
        route_geojson: GeoJSON Feature with LineString geometry of the route.
            May be None if only length-based estimation is needed.
        total_length_km: Total route length in kilometers.
        target_subscribers: Number of subscribers to provision for.
        area_type: Deployment area type — 'urban', 'suburban', or 'rural'.

    Returns:
        Dictionary with:
            items: List of BOM line items, each with:
                name, description, quantity, unit_cost_brl, total_cost_brl
            grand_total_brl: Sum of all line item totals
            summary: Human-readable summary string
    """
    if total_length_km <= 0 and target_subscribers <= 0:
        return {
            "items": [],
            "grand_total_brl": 0.0,
            "summary": "No route or subscribers specified",
        }

    area = area_type.lower() if area_type else "urban"
    if area not in SPLITTER_SPACING:
        area = "urban"

    items = []

    # --- 1. Trunk/distribution cable ---
    trunk_cable = _select_trunk_cable(area)
    trunk_length_m = total_length_km * 1000.0
    trunk_total = trunk_length_m * trunk_cable["cost_per_m"]
    items.append({
        "name": f"Distribution cable ({trunk_cable['fiber_count']}-fiber)",
        "description": trunk_cable["description"],
        "quantity": int(math.ceil(trunk_length_m)),
        "unit": "m",
        "unit_cost_brl": trunk_cable["cost_per_m"],
        "total_cost_brl": round(trunk_total, 2),
    })

    # --- 2. Backbone cable (if route > 5 km, add backbone segment) ---
    if total_length_km > 5.0:
        backbone = CABLE_TYPES["backbone_144"]
        # Backbone is typically 30-40% of the total route for longer builds
        backbone_length_m = trunk_length_m * 0.30
        backbone_total = backbone_length_m * backbone["cost_per_m"]
        items.append({
            "name": "Backbone cable (144-fiber)",
            "description": backbone["description"],
            "quantity": int(math.ceil(backbone_length_m)),
            "unit": "m",
            "unit_cost_brl": backbone["cost_per_m"],
            "total_cost_brl": round(backbone_total, 2),
        })

    # --- 3. Service drop cables ---
    drop = CABLE_TYPES["drop"]
    drop_length_m = target_subscribers * DROP_CABLE_PER_SUB_M
    drop_total = drop_length_m * drop["cost_per_m"]
    items.append({
        "name": "Service drop cable (2-fiber)",
        "description": drop["description"],
        "quantity": int(math.ceil(drop_length_m)),
        "unit": "m",
        "unit_cost_brl": drop["cost_per_m"],
        "total_cost_brl": round(drop_total, 2),
    })

    # --- 4. Splice enclosures ---
    junction_count = _count_junctions_from_geojson(route_geojson)
    interval_based = max(1, math.ceil(total_length_km / SPLICE_INTERVAL_KM))
    splice_count = max(interval_based, junction_count)
    # At least 1 at each end
    splice_count = max(2, splice_count)
    splice_unit = EQUIPMENT_COSTS["splice_enclosure"]
    items.append({
        "name": "Splice enclosure",
        "description": splice_unit["description"],
        "quantity": splice_count,
        "unit": "pcs",
        "unit_cost_brl": splice_unit["unit_cost_brl"],
        "total_cost_brl": round(splice_count * splice_unit["unit_cost_brl"], 2),
    })

    # --- 5. Splitter cabinets ---
    splitter_spacing_km = SPLITTER_SPACING[area]
    splitter_count = max(1, math.ceil(total_length_km / splitter_spacing_km))

    # Choose 1:16 for rural (fewer subs per splitter), 1:32 for urban
    if area == "rural":
        splitter_key = "splitter_cabinet_1x16"
    else:
        splitter_key = "splitter_cabinet_1x32"

    splitter_unit = EQUIPMENT_COSTS[splitter_key]
    items.append({
        "name": f"Splitter cabinet ({splitter_key.split('_')[-1]})",
        "description": splitter_unit["description"],
        "quantity": splitter_count,
        "unit": "pcs",
        "unit_cost_brl": splitter_unit["unit_cost_brl"],
        "total_cost_brl": round(splitter_count * splitter_unit["unit_cost_brl"], 2),
    })

    # --- 6. ONTs ---
    ont_unit = EQUIPMENT_COSTS["ont"]
    items.append({
        "name": "ONT (customer premise equipment)",
        "description": ont_unit["description"],
        "quantity": target_subscribers,
        "unit": "pcs",
        "unit_cost_brl": ont_unit["unit_cost_brl"],
        "total_cost_brl": round(target_subscribers * ont_unit["unit_cost_brl"], 2),
    })

    # --- 7. OLTs ---
    olt_count = max(1, math.ceil(target_subscribers / OLT_CAPACITY))
    olt_unit = EQUIPMENT_COSTS["olt_8port"]
    items.append({
        "name": "OLT (8-port GPON)",
        "description": olt_unit["description"],
        "quantity": olt_count,
        "unit": "pcs",
        "unit_cost_brl": olt_unit["unit_cost_brl"],
        "total_cost_brl": round(olt_count * olt_unit["unit_cost_brl"], 2),
    })

    # --- 8. Patch panels (1 per OLT + 1 per 4 splitter cabinets) ---
    patch_count = olt_count + max(1, math.ceil(splitter_count / 4))
    patch_unit = EQUIPMENT_COSTS["patch_panel"]
    items.append({
        "name": "Fiber patch panel (24-port)",
        "description": patch_unit["description"],
        "quantity": patch_count,
        "unit": "pcs",
        "unit_cost_brl": patch_unit["unit_cost_brl"],
        "total_cost_brl": round(patch_count * patch_unit["unit_cost_brl"], 2),
    })

    # --- 9. UPS / power supplies (1 per OLT location + 1 per 8 splitter cabinets) ---
    ups_count = olt_count + max(0, math.ceil(splitter_count / 8))
    ups_unit = EQUIPMENT_COSTS["power_supply_ups"]
    items.append({
        "name": "UPS / battery backup (1kVA)",
        "description": ups_unit["description"],
        "quantity": ups_count,
        "unit": "pcs",
        "unit_cost_brl": ups_unit["unit_cost_brl"],
        "total_cost_brl": round(ups_count * ups_unit["unit_cost_brl"], 2),
    })

    # --- Grand total ---
    grand_total = sum(item["total_cost_brl"] for item in items)

    summary = (
        f"BOM for {total_length_km:.1f} km {area} fiber deployment "
        f"serving {target_subscribers} subscribers: "
        f"{len(items)} line items, "
        f"R${grand_total:,.2f} total equipment cost"
    )

    logger.info(summary)

    return {
        "items": items,
        "grand_total_brl": round(grand_total, 2),
        "summary": summary,
    }
