"""Rural cost benchmarks -- typically 2-3x urban costs.

Based on BNDES and Abrint published data for rural deployments in Brazil.
Accounts for terrain difficulty, biome-specific logistics, and the
additional costs of operating in remote areas (transportation, fuel,
specialized labor, etc.).

Cost categories:
- Equipment: base station, tower, CPE, cabling
- Civil works: site preparation, tower foundation, trenching
- Logistics: transportation of equipment and personnel
- Installation: specialized labor
- Operating: maintenance, energy, monitoring

Sources:
    - BNDES rural telecom financing benchmarks
    - Abrint member cost surveys (anonymized)
    - Telebras deployment cost reports
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rural cost multipliers relative to urban baseline
# ---------------------------------------------------------------------------
RURAL_COST_MULTIPLIERS = {
    "flat_rural": 1.5,
    "hilly_rural": 2.0,
    "mountainous": 2.5,
    "amazon_riverine": 3.0,
    "island": 3.5,
}

# ---------------------------------------------------------------------------
# Technology base costs (BRL) — urban/peri-urban baseline
# ---------------------------------------------------------------------------
TECHNOLOGY_BASE_COSTS = {
    "wifi_mesh": {
        "capex_per_subscriber": 1_500,
        "opex_per_subscriber_monthly": 15,
        "base_site_cost": 8_000,
        "description": "WiFi mesh network with outdoor APs",
    },
    "4g_700mhz": {
        "capex_per_subscriber": 3_500,
        "opex_per_subscriber_monthly": 25,
        "base_site_cost": 260_000,  # eNodeB + tower
        "description": "4G/LTE 700 MHz rural deployment",
    },
    "4g_250mhz": {
        "capex_per_subscriber": 4_500,
        "opex_per_subscriber_monthly": 30,
        "base_site_cost": 340_000,  # eNodeB + taller tower
        "description": "4G/LTE 250 MHz wide-area rural deployment",
    },
    "tvws": {
        "capex_per_subscriber": 2_000,
        "opex_per_subscriber_monthly": 20,
        "base_site_cost": 25_000,
        "description": "TV White Spaces (TVWS) deployment",
    },
    "satellite_premises": {
        "capex_per_subscriber": 3_000,
        "opex_per_subscriber_monthly": 250,
        "base_site_cost": 0,  # No base station
        "description": "Satellite per-premises (Starlink/SGDC)",
    },
    "fiber_ftth": {
        "capex_per_subscriber": 2_500,
        "opex_per_subscriber_monthly": 10,
        "base_site_cost": 150_000,  # POP + OLT
        "description": "Fiber-to-the-home (rural FTTH)",
    },
}

# ---------------------------------------------------------------------------
# Logistics cost parameters
# ---------------------------------------------------------------------------
LOGISTICS_BASE_COST_BRL = 5_000  # Base logistics cost per deployment

LOGISTICS_DISTANCE_MULTIPLIERS = {
    # Distance from nearest city with telecom suppliers
    "close": {"max_km": 50, "multiplier": 1.0},
    "moderate": {"max_km": 200, "multiplier": 1.5},
    "remote": {"max_km": 500, "multiplier": 2.5},
    "very_remote": {"max_km": float("inf"), "multiplier": 4.0},
}

# Transport mode surcharges
TRANSPORT_SURCHARGES = {
    "road": 0,
    "boat": 5_000,
    "small_aircraft": 15_000,
    "helicopter": 50_000,
}

# ---------------------------------------------------------------------------
# OPEX components
# ---------------------------------------------------------------------------
OPEX_COMPONENTS = {
    "energy_grid_monthly_brl": 800,
    "energy_solar_monthly_brl": 200,  # Maintenance only (no energy bill)
    "monitoring_monthly_brl": 300,
    "maintenance_visit_brl": 2_000,
    "maintenance_visits_per_year": 4,
    "insurance_annual_pct_of_capex": 0.02,
}


@dataclass
class RuralCostEstimate:
    """Complete cost estimate for a rural telecom deployment.

    Attributes:
        total_capex_brl: Total one-time capital expenditure.
        total_monthly_opex_brl: Total monthly operating expenditure.
        breakdown: Detailed cost breakdown by category.
        terrain_multiplier: Applied terrain cost multiplier.
        logistics_surcharge_brl: Additional logistics cost.
        notes: Warnings, assumptions, and recommendations.
    """

    total_capex_brl: float
    total_monthly_opex_brl: float
    breakdown: dict
    terrain_multiplier: float
    logistics_surcharge_brl: float
    notes: list[str]


def _get_terrain_key(terrain: str) -> str:
    """Normalize terrain string to a valid multiplier key."""
    terrain_lower = terrain.lower().strip()

    # Direct match
    if terrain_lower in RURAL_COST_MULTIPLIERS:
        return terrain_lower

    # Fuzzy mapping
    mapping = {
        "flat": "flat_rural",
        "rural": "flat_rural",
        "hilly": "hilly_rural",
        "hills": "hilly_rural",
        "mountain": "mountainous",
        "mountains": "mountainous",
        "riverine": "amazon_riverine",
        "river": "amazon_riverine",
        "amazon": "amazon_riverine",
        "amazonia": "amazon_riverine",
        "island": "island",
        "islands": "island",
    }

    return mapping.get(terrain_lower, "flat_rural")


def _get_logistics_multiplier(nearest_road_km: float) -> float:
    """Determine logistics cost multiplier from distance to nearest road/city."""
    for _tier, params in sorted(
        LOGISTICS_DISTANCE_MULTIPLIERS.items(),
        key=lambda x: x[1]["max_km"],
    ):
        if nearest_road_km <= params["max_km"]:
            return params["multiplier"]
    return 4.0


def estimate_rural_cost(
    technology: str,
    area_km2: float,
    population: int,
    terrain: str = "flat_rural",
    grid_power: bool = False,
    nearest_road_km: float = 10.0,
) -> RuralCostEstimate:
    """Estimate total cost for a rural deployment.

    Calculates CAPEX and monthly OPEX for a given technology in a rural area,
    applying terrain multipliers, logistics surcharges, and power costs.

    Args:
        technology: Technology type (e.g. "4g_700mhz", "wifi_mesh").
        area_km2: Deployment coverage area in km^2.
        population: Target population.
        terrain: Terrain type for cost multiplier.
        grid_power: Whether grid power is available.
        nearest_road_km: Distance to nearest paved road in km.

    Returns:
        RuralCostEstimate with complete CAPEX and OPEX breakdown.
    """
    notes: list[str] = []

    # Validate inputs
    if population <= 0:
        logger.warning("Population <= 0. Returning zero cost estimate.")
        return RuralCostEstimate(
            total_capex_brl=0.0,
            total_monthly_opex_brl=0.0,
            breakdown={},
            terrain_multiplier=1.0,
            logistics_surcharge_brl=0.0,
            notes=["No population — no deployment cost."],
        )

    if area_km2 <= 0:
        logger.warning("Area <= 0. Defaulting to 1 km^2.")
        area_km2 = 1.0

    # Normalize technology key
    tech_key = technology.lower().strip()
    if tech_key not in TECHNOLOGY_BASE_COSTS:
        logger.warning(
            "Unknown technology '%s'. Defaulting to '4g_700mhz'.",
            technology,
        )
        tech_key = "4g_700mhz"
        notes.append(f"WARNING: Unknown technology '{technology}', defaulted to 4G 700MHz.")

    tech = TECHNOLOGY_BASE_COSTS[tech_key]

    # Terrain multiplier
    terrain_key = _get_terrain_key(terrain)
    terrain_mult = RURAL_COST_MULTIPLIERS.get(terrain_key, 1.5)

    # Logistics multiplier
    logistics_mult = _get_logistics_multiplier(nearest_road_km)

    # Estimate subscribers (~1 per household, ~3.5 people per household)
    estimated_subscribers = max(1, math.ceil(population / 3.5 * 0.50))

    # Number of sites needed (rough: 1 site per base coverage area)
    if tech_key in ("wifi_mesh",):
        site_coverage_km2 = 0.1  # WiFi has small range
    elif tech_key in ("4g_700mhz",):
        site_coverage_km2 = 25.0
    elif tech_key in ("4g_250mhz",):
        site_coverage_km2 = 200.0
    elif tech_key in ("tvws",):
        site_coverage_km2 = 100.0
    elif tech_key in ("satellite_premises",):
        site_coverage_km2 = float("inf")  # No base station
    else:
        site_coverage_km2 = 10.0

    num_sites = max(1, math.ceil(area_km2 / site_coverage_km2)) if site_coverage_km2 < float("inf") else 0

    # --- CAPEX calculation ---
    # Equipment cost
    site_cost = tech["base_site_cost"] * num_sites * terrain_mult
    subscriber_equipment_cost = tech["capex_per_subscriber"] * estimated_subscribers * terrain_mult

    # Civil works (30% of equipment for rural)
    civil_works = (site_cost + subscriber_equipment_cost) * 0.30

    # Logistics
    logistics_base = LOGISTICS_BASE_COST_BRL * logistics_mult * max(1, num_sites)
    # Transport surcharge
    if terrain_key == "island":
        transport_surcharge = TRANSPORT_SURCHARGES["boat"]
    elif terrain_key == "amazon_riverine":
        transport_surcharge = TRANSPORT_SURCHARGES["boat"]
    elif nearest_road_km > 200:
        transport_surcharge = TRANSPORT_SURCHARGES["small_aircraft"]
    else:
        transport_surcharge = TRANSPORT_SURCHARGES["road"]

    total_logistics = logistics_base + transport_surcharge

    # Power system CAPEX (if off-grid)
    if not grid_power:
        # Rough solar system cost: R$45,000-80,000 per site
        power_capex = 60_000 * max(1, num_sites)
        notes.append(
            "Off-grid solar power system included. See solar_power.py for detailed sizing."
        )
    else:
        power_capex = 15_000 * max(1, num_sites)  # Grid connection per site

    # Contingency (15%)
    subtotal_capex = site_cost + subscriber_equipment_cost + civil_works + total_logistics + power_capex
    contingency = subtotal_capex * 0.15

    total_capex = subtotal_capex + contingency

    # --- OPEX calculation ---
    # Energy
    if grid_power:
        energy_monthly = OPEX_COMPONENTS["energy_grid_monthly_brl"] * max(1, num_sites)
    else:
        energy_monthly = OPEX_COMPONENTS["energy_solar_monthly_brl"] * max(1, num_sites)

    # Monitoring
    monitoring_monthly = OPEX_COMPONENTS["monitoring_monthly_brl"]

    # Subscriber OPEX
    subscriber_opex = tech["opex_per_subscriber_monthly"] * estimated_subscribers

    # Maintenance (amortized monthly)
    maintenance_monthly = (
        OPEX_COMPONENTS["maintenance_visit_brl"]
        * OPEX_COMPONENTS["maintenance_visits_per_year"]
        * logistics_mult
        / 12.0
    )

    # Insurance (amortized monthly)
    insurance_monthly = total_capex * OPEX_COMPONENTS["insurance_annual_pct_of_capex"] / 12.0

    total_monthly_opex = (
        energy_monthly
        + monitoring_monthly
        + subscriber_opex
        + maintenance_monthly
        + insurance_monthly
    )

    # Build breakdown
    breakdown = {
        "capex": {
            "site_equipment": round(site_cost, 2),
            "subscriber_equipment": round(subscriber_equipment_cost, 2),
            "civil_works": round(civil_works, 2),
            "logistics": round(total_logistics, 2),
            "power_system": round(power_capex, 2),
            "contingency": round(contingency, 2),
        },
        "opex_monthly": {
            "energy": round(energy_monthly, 2),
            "monitoring": round(monitoring_monthly, 2),
            "subscriber_services": round(subscriber_opex, 2),
            "maintenance": round(maintenance_monthly, 2),
            "insurance": round(insurance_monthly, 2),
        },
        "parameters": {
            "technology": tech_key,
            "terrain": terrain_key,
            "terrain_multiplier": terrain_mult,
            "logistics_multiplier": logistics_mult,
            "estimated_subscribers": estimated_subscribers,
            "num_sites": num_sites,
            "area_km2": area_km2,
            "grid_power": grid_power,
        },
    }

    # Per-subscriber analysis
    per_sub_capex = total_capex / estimated_subscribers if estimated_subscribers > 0 else 0
    notes.append(
        f"Per-subscriber CAPEX: R${per_sub_capex:,.0f} "
        f"({terrain_key} terrain, {terrain_mult}x multiplier)."
    )

    if per_sub_capex > 8_000:
        notes.append(
            "HIGH COST WARNING: Per-subscriber CAPEX exceeds R$8,000. "
            "Consider government funding (FUST, BNDES ProConectividade)."
        )

    if terrain_mult >= 3.0:
        notes.append(
            f"EXTREME TERRAIN: {terrain_key} has a {terrain_mult}x cost multiplier. "
            "Budget for extended installation timelines and specialized logistics."
        )

    result = RuralCostEstimate(
        total_capex_brl=round(total_capex, 2),
        total_monthly_opex_brl=round(total_monthly_opex, 2),
        breakdown=breakdown,
        terrain_multiplier=terrain_mult,
        logistics_surcharge_brl=round(total_logistics, 2),
        notes=notes,
    )

    logger.info(
        "Rural cost estimate: %s, %s terrain (%.1fx), %d subs, %d sites — "
        "CAPEX R$%.0f, OPEX R$%.0f/mo",
        tech_key,
        terrain_key,
        terrain_mult,
        estimated_subscribers,
        num_sites,
        total_capex,
        total_monthly_opex,
    )

    return result
