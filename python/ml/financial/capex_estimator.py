"""Infrastructure CAPEX estimation with Brazilian telecom benchmarks.

Cost constants are derived from BNDES (Brazilian Development Bank) financing
data and Abrint (Brazilian ISP Association) industry reports.  All values
are in BRL (Brazilian Reais).
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fiber deployment cost per km (BRL)
# ---------------------------------------------------------------------------
FIBER_COST_PER_KM = {
    "aerial": {
        "urban":    {"low": 15_000, "high": 25_000},
        "suburban": {"low": 12_000, "high": 20_000},
        "rural":    {"low": 20_000, "high": 35_000},
    },
    "underground": {
        "urban":    {"low": 60_000, "high": 120_000},
        "suburban": {"low": 45_000, "high": 80_000},
        "rural":    {"low": 30_000, "high": 60_000},
    },
}

# ---------------------------------------------------------------------------
# Equipment costs (BRL)
# ---------------------------------------------------------------------------
EQUIPMENT = {
    "olt": {
        "small":  {"cost": 30_000, "capacity": 128},   # GPON OLT, 4-port
        "medium": {"cost": 55_000, "capacity": 256},   # GPON OLT, 8-port
        "large":  {"cost": 80_000, "capacity": 512},   # XGS-PON OLT, 16-port
    },
    "ont_per_unit": {"low": 200, "mid": 350, "high": 500},
    "splitter_cabinet": {"low": 2_000, "high": 5_000},   # 1:16 or 1:32
    "splice_enclosure": {"low": 500, "high": 1_500},
}

# ---------------------------------------------------------------------------
# POP (Point of Presence) costs (BRL)
# ---------------------------------------------------------------------------
POP_COST = {
    "small":  {"low": 50_000,  "high": 150_000, "max_subs": 2_000},
    "medium": {"low": 150_000, "high": 400_000, "max_subs": 10_000},
    "large":  {"low": 400_000, "high": 800_000, "max_subs": 50_000},
}

# ---------------------------------------------------------------------------
# Terrain multipliers
# ---------------------------------------------------------------------------
TERRAIN_MULTIPLIERS = {
    "flat_urban":    1.0,
    "flat_rural":    1.1,
    "hilly":         1.2,
    "mountainous":   1.5,
    "amazon":        2.0,
    "remote":        2.5,
    "amazon_remote": 3.0,
}

# Biome-specific multipliers (override terrain when biome is known)
BIOME_MULTIPLIERS = {
    "amazonia":       2.5,
    "cerrado":        1.2,
    "mata_atlantica": 1.3,
    "caatinga":       1.4,
    "pampa":          1.1,
    "pantanal":       2.0,
}

# Contingency factor
CONTINGENCY_FACTOR = 0.15

# Labor is typically 30-40% of material costs in Brazil
LABOR_RATIO = 0.35


def get_terrain_multiplier(
    avg_slope: float = 0.0,
    max_elevation_diff: float = 0.0,
    biome: Optional[str] = None,
) -> float:
    """Compute a terrain difficulty multiplier for cost estimation.

    Args:
        avg_slope: Average terrain slope in degrees.
        max_elevation_diff: Maximum elevation difference in meters along
            the route.
        biome: Brazilian biome name (e.g. 'amazonia', 'cerrado').

    Returns:
        Multiplier >= 1.0 to apply to base construction costs.
    """
    # Start with biome-based multiplier if available
    if biome and biome.lower() in BIOME_MULTIPLIERS:
        base_mult = BIOME_MULTIPLIERS[biome.lower()]
    else:
        base_mult = 1.0

    # Slope-based adjustment
    if avg_slope <= 3.0:
        slope_mult = 1.0
    elif avg_slope <= 8.0:
        slope_mult = 1.1 + (avg_slope - 3.0) * 0.02
    elif avg_slope <= 15.0:
        slope_mult = 1.2 + (avg_slope - 8.0) * 0.04
    else:
        slope_mult = 1.5 + (avg_slope - 15.0) * 0.05

    # Elevation difference adjustment
    if max_elevation_diff <= 100:
        elev_mult = 1.0
    elif max_elevation_diff <= 500:
        elev_mult = 1.0 + (max_elevation_diff - 100) * 0.0005
    else:
        elev_mult = 1.2 + (max_elevation_diff - 500) * 0.0003

    # Combined: take the maximum of biome-based and terrain-based,
    # then apply elevation on top
    terrain_mult = max(base_mult, slope_mult) * elev_mult
    terrain_mult = round(max(1.0, terrain_mult), 3)

    logger.debug(
        "Terrain multiplier: slope=%.1f, elev_diff=%.0f, biome=%s -> %.3f",
        avg_slope,
        max_elevation_diff,
        biome,
        terrain_mult,
    )
    return terrain_mult


def _select_olt(target_subscribers: int) -> tuple:
    """Select appropriate OLT size and compute quantity needed.

    Returns:
        (unit_cost, quantity, capacity_each)
    """
    if target_subscribers <= 128:
        tier = "small"
    elif target_subscribers <= 512:
        tier = "medium"
    else:
        tier = "large"

    olt = EQUIPMENT["olt"][tier]
    quantity = max(1, math.ceil(target_subscribers / olt["capacity"]))
    return olt["cost"], quantity, olt["capacity"]


def _select_pop(target_subscribers: int) -> tuple:
    """Select POP size and return cost range midpoint.

    Returns:
        (pop_cost, pop_tier_name)
    """
    if target_subscribers <= POP_COST["small"]["max_subs"]:
        tier = "small"
    elif target_subscribers <= POP_COST["medium"]["max_subs"]:
        tier = "medium"
    else:
        tier = "large"

    cost_mid = (POP_COST[tier]["low"] + POP_COST[tier]["high"]) / 2
    return cost_mid, tier


def estimate_capex(
    cable_length_km: float,
    target_subscribers: int,
    technology: str = "fiber",
    terrain: str = "flat_urban",
    area_type: str = "urban",
    deployment_method: str = "aerial",
    biome: Optional[str] = None,
    avg_slope: float = 0.0,
    max_elevation_diff: float = 0.0,
) -> dict:
    """Estimate total CAPEX for fiber network deployment.

    Args:
        cable_length_km: Total cable route length in kilometers.
        target_subscribers: Number of subscribers to serve at full build.
        technology: Access technology ('fiber', 'fwa', 'dsl').
        terrain: Terrain category key from TERRAIN_MULTIPLIERS.
        area_type: 'urban', 'suburban', or 'rural'.
        deployment_method: 'aerial' or 'underground'.
        biome: Optional Brazilian biome name.
        avg_slope: Average terrain slope in degrees.
        max_elevation_diff: Maximum elevation difference in meters.

    Returns:
        Dictionary with:
            total_brl: Grand total estimated CAPEX.
            breakdown: Dict with cable, equipment, pop, labor, contingency.
            per_subscriber_brl: CAPEX per subscriber (total / target).
            terrain_multiplier: Applied terrain multiplier.
    """
    if cable_length_km <= 0 or target_subscribers <= 0:
        return {
            "total_brl": 0,
            "breakdown": {
                "cable": 0,
                "equipment": 0,
                "pop": 0,
                "labor": 0,
                "contingency": 0,
            },
            "per_subscriber_brl": 0,
            "terrain_multiplier": 1.0,
        }

    # --- Terrain multiplier ---
    if terrain in TERRAIN_MULTIPLIERS:
        t_mult = TERRAIN_MULTIPLIERS[terrain]
    else:
        t_mult = 1.0

    # Override with computed terrain multiplier if slope/elevation data provided
    if avg_slope > 0 or max_elevation_diff > 0 or biome:
        t_mult = max(t_mult, get_terrain_multiplier(avg_slope, max_elevation_diff, biome))

    # --- Cable cost ---
    deploy = deployment_method.lower() if deployment_method else "aerial"
    if deploy not in FIBER_COST_PER_KM:
        deploy = "aerial"

    area = area_type.lower() if area_type else "urban"
    if area not in FIBER_COST_PER_KM[deploy]:
        area = "urban"

    cable_range = FIBER_COST_PER_KM[deploy][area]
    cable_cost_per_km = (cable_range["low"] + cable_range["high"]) / 2
    cable_cost = cable_length_km * cable_cost_per_km * t_mult

    # --- Equipment costs ---
    # OLT
    olt_unit_cost, olt_qty, olt_capacity = _select_olt(target_subscribers)
    olt_cost = olt_unit_cost * olt_qty

    # ONTs
    ont_unit_cost = EQUIPMENT["ont_per_unit"]["mid"]
    ont_cost = ont_unit_cost * target_subscribers

    # Splitter cabinets: spacing depends on area type
    if area == "urban":
        splitter_spacing_km = 0.5
    elif area == "suburban":
        splitter_spacing_km = 1.0
    else:
        splitter_spacing_km = 2.0
    splitter_count = max(1, math.ceil(cable_length_km / splitter_spacing_km))
    splitter_unit = (EQUIPMENT["splitter_cabinet"]["low"] + EQUIPMENT["splitter_cabinet"]["high"]) / 2
    splitter_cost = splitter_count * splitter_unit

    # Splice enclosures: every 2 km
    splice_count = max(1, math.ceil(cable_length_km / 2.0))
    splice_unit = (EQUIPMENT["splice_enclosure"]["low"] + EQUIPMENT["splice_enclosure"]["high"]) / 2
    splice_cost = splice_count * splice_unit

    equipment_cost = olt_cost + ont_cost + splitter_cost + splice_cost

    # --- POP cost ---
    pop_cost, pop_tier = _select_pop(target_subscribers)

    # --- Labor ---
    material_subtotal = cable_cost + equipment_cost + pop_cost
    labor_cost = material_subtotal * LABOR_RATIO

    # --- Contingency ---
    subtotal = material_subtotal + labor_cost
    contingency = subtotal * CONTINGENCY_FACTOR

    # --- Grand total ---
    total = subtotal + contingency

    per_sub = total / target_subscribers if target_subscribers > 0 else 0

    logger.info(
        "CAPEX estimate: %.1f km, %d subs, %s/%s, terrain=%.2fx -> R$%.0f "
        "(R$%.0f/sub)",
        cable_length_km,
        target_subscribers,
        deploy,
        area,
        t_mult,
        total,
        per_sub,
    )

    return {
        "total_brl": round(total, 2),
        "breakdown": {
            "cable": round(cable_cost, 2),
            "equipment": round(equipment_cost, 2),
            "pop": round(pop_cost, 2),
            "labor": round(labor_cost, 2),
            "contingency": round(contingency, 2),
        },
        "per_subscriber_brl": round(per_sub, 2),
        "terrain_multiplier": t_mult,
        "details": {
            "deployment_method": deploy,
            "area_type": area,
            "cable_cost_per_km": round(cable_cost_per_km * t_mult, 2),
            "olt_count": olt_qty,
            "olt_capacity_each": olt_capacity,
            "ont_count": target_subscribers,
            "splitter_count": splitter_count,
            "splice_count": splice_count,
            "pop_tier": pop_tier,
        },
    }
