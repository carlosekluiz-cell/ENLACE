"""Hybrid network architecture designer for rural/remote areas.

Selects optimal combination of backhaul + last mile + power technologies
based on community characteristics and constraints.

TECHNOLOGY OPTIONS:
- Backhaul: fiber, microwave, satellite (GEO/LEO)
- Last mile: 4G/LTE (700MHz/250MHz), WiFi mesh, TVWS, satellite per-premises
- Power: grid, solar+battery, grid+solar hybrid

Decision logic follows BNDES rural deployment guidelines and Abrint best
practices for small ISPs in underserved areas.
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Equipment cost benchmarks (BRL) — based on BNDES / Abrint data
# ---------------------------------------------------------------------------
BACKHAUL_EQUIPMENT = {
    "fiber": {
        "cost_per_km_brl": 27_500,  # aerial, rural average
        "installation_per_km_brl": 8_000,
        "terminal_equipment_brl": 35_000,  # OLT/media converter
    },
    "microwave": {
        "radio_pair_brl": 45_000,  # licensed pair, 1 Gbps
        "tower_per_unit_brl": 80_000,  # 30m guyed tower
        "installation_brl": 25_000,
    },
    "satellite_geo": {
        "terminal_brl": 15_000,
        "monthly_service_brl": 0,  # Telebras SGDC is free for eligible
        "installation_brl": 5_000,
    },
    "satellite_leo": {
        "terminal_brl": 2_800,
        "monthly_service_brl": 250,
        "installation_brl": 1_500,
    },
}

LAST_MILE_EQUIPMENT = {
    "wifi_mesh": {
        "ap_unit_brl": 1_200,
        "cpe_unit_brl": 350,
        "coverage_radius_m": 150,
        "max_users_per_ap": 30,
    },
    "4g_700mhz": {
        "enodeb_brl": 180_000,
        "tower_brl": 80_000,
        "cpe_unit_brl": 600,
        "coverage_radius_km": 5.0,
        "max_users": 200,
    },
    "4g_250mhz": {
        "enodeb_brl": 220_000,
        "tower_brl": 120_000,
        "cpe_unit_brl": 800,
        "coverage_radius_km": 15.0,
        "max_users": 150,
    },
    "tvws": {
        "base_station_brl": 25_000,
        "cpe_unit_brl": 500,
        "coverage_radius_km": 10.0,
        "max_users": 100,
    },
    "satellite_premises": {
        "terminal_per_premises_brl": 2_800,
        "monthly_per_premises_brl": 250,
    },
}

POWER_EQUIPMENT = {
    "grid": {
        "connection_cost_brl": 15_000,
        "monthly_energy_brl": 800,
        "ups_brl": 8_000,
    },
    "solar_battery": {
        "base_system_brl": 45_000,  # 1 kW system base
        "per_kw_brl": 12_000,
        "battery_per_kwh_brl": 2_500,
        "monthly_maintenance_brl": 200,
    },
    "grid_solar_hybrid": {
        "grid_connection_brl": 15_000,
        "solar_supplement_brl": 25_000,
        "monthly_energy_brl": 400,
        "monthly_maintenance_brl": 150,
    },
}

# Terrain-specific adjustments for coverage radius
TERRAIN_COVERAGE_FACTOR = {
    "flat": 1.0,
    "hilly": 0.7,
    "mountainous": 0.5,
    "riverine": 0.8,
    "island": 0.6,
}

# Biome-specific logistics surcharge (%)
BIOME_LOGISTICS_SURCHARGE = {
    "amazonia": 0.40,
    "cerrado": 0.10,
    "caatinga": 0.15,
    "mata_atlantica": 0.10,
    "pampa": 0.05,
    "pantanal": 0.30,
}


@dataclass
class CommunityProfile:
    """Describes a rural community for network design purposes.

    Attributes:
        latitude: Community center latitude (decimal degrees).
        longitude: Community center longitude (decimal degrees).
        population: Total population.
        area_km2: Approximate area of the community footprint.
        grid_power: Whether grid electricity is available.
        nearest_fiber_km: Distance to nearest fiber backbone in km.
        nearest_road_km: Distance to nearest paved road in km.
        terrain_type: Terrain classification.
        biome: Brazilian biome where the community is located.
    """

    latitude: float
    longitude: float
    population: int
    area_km2: float
    grid_power: bool
    nearest_fiber_km: float = 100.0
    nearest_road_km: float = 10.0
    terrain_type: str = "flat"  # flat, hilly, mountainous, riverine, island
    biome: str = "cerrado"  # amazonia, cerrado, caatinga, mata_atlantica, pampa, pantanal


@dataclass
class HybridDesign:
    """Complete hybrid network design for a rural community.

    Attributes:
        backhaul_technology: Selected backhaul type.
        backhaul_details: Parameters and rationale for backhaul selection.
        last_mile_technology: Selected last mile type.
        last_mile_details: Parameters and rationale for last mile selection.
        power_solution: Selected power source.
        power_details: Parameters and rationale for power selection.
        equipment_list: Itemized list of equipment with quantities and costs.
        estimated_capex_brl: Total estimated capital expenditure (BRL).
        estimated_monthly_opex_brl: Estimated monthly operating cost (BRL).
        coverage_estimate_km2: Estimated coverage area in km^2.
        max_subscribers: Maximum number of subscribers supported.
        design_notes: Additional notes, warnings, or recommendations.
    """

    backhaul_technology: str
    backhaul_details: dict
    last_mile_technology: str
    last_mile_details: dict
    power_solution: str
    power_details: dict
    equipment_list: list[dict]
    estimated_capex_brl: float
    estimated_monthly_opex_brl: float
    coverage_estimate_km2: float
    max_subscribers: int
    design_notes: list[str]


def _get_region_from_coords(latitude: float, longitude: float) -> str:
    """Infer Brazilian region from latitude/longitude for irradiance lookup.

    Uses simplified bounding boxes. This is approximate and intended for
    irradiance and logistics estimation, not for regulatory purposes.
    """
    if latitude > -5.0:
        return "north"
    if latitude > -10.0 and longitude > -42.0:
        return "northeast"
    if latitude > -15.0 and longitude < -42.0:
        return "central-west"
    if latitude > -22.0:
        return "southeast"
    return "south"


def select_backhaul(profile: CommunityProfile) -> tuple[str, dict]:
    """Select backhaul technology and estimate parameters.

    Decision logic:
    - Fiber if nearest fiber is < 20 km and there is a road corridor
    - Microwave if line-of-sight possible (< 50 km, not riverine without towers)
    - Satellite LEO if latency-sensitive and budget allows
    - Satellite GEO as fallback (Telebras SGDC for eligible communities)

    Args:
        profile: Community characteristics.

    Returns:
        Tuple of (technology_name, details_dict).
    """
    details: dict = {}

    # Fiber is optimal when close to existing backbone and road access exists
    fiber_viable = (
        profile.nearest_fiber_km <= 20.0
        and profile.nearest_road_km <= 5.0
        and profile.terrain_type not in ("island", "riverine")
    )

    if fiber_viable:
        cost_per_km = BACKHAUL_EQUIPMENT["fiber"]["cost_per_km_brl"]
        install_per_km = BACKHAUL_EQUIPMENT["fiber"]["installation_per_km_brl"]
        terminal = BACKHAUL_EQUIPMENT["fiber"]["terminal_equipment_brl"]
        total_km = profile.nearest_fiber_km
        surcharge = BIOME_LOGISTICS_SURCHARGE.get(profile.biome, 0.10)

        total_cost = (cost_per_km + install_per_km) * total_km + terminal
        total_cost *= (1.0 + surcharge)

        details = {
            "distance_km": total_km,
            "cost_per_km_brl": cost_per_km,
            "terminal_cost_brl": terminal,
            "total_estimated_cost_brl": round(total_cost, 2),
            "capacity_mbps": 1000,
            "latency_ms": 2.0,
            "rationale": (
                f"Fiber backhaul selected: {total_km:.1f} km to nearest backbone "
                f"along road corridor. High capacity, low latency."
            ),
        }
        logger.info(
            "Backhaul: fiber selected — %.1f km, estimated R$%.0f",
            total_km,
            total_cost,
        )
        return "fiber", details

    # Microwave is viable for moderate distances with line-of-sight
    mw_max_distance = 50.0
    terrain_factor = TERRAIN_COVERAGE_FACTOR.get(profile.terrain_type, 0.7)
    effective_mw_range = mw_max_distance * terrain_factor

    mw_viable = (
        profile.nearest_fiber_km <= effective_mw_range
        and profile.terrain_type not in ("island",)
    )

    if mw_viable:
        radio = BACKHAUL_EQUIPMENT["microwave"]["radio_pair_brl"]
        tower = BACKHAUL_EQUIPMENT["microwave"]["tower_per_unit_brl"]
        install = BACKHAUL_EQUIPMENT["microwave"]["installation_brl"]
        # Need one tower at each end if no existing tower
        num_towers = 2 if profile.terrain_type in ("flat", "riverine") else 1
        # Additional repeater tower for distances > 30 km
        hops = max(1, math.ceil(profile.nearest_fiber_km / 30.0))
        num_radios = hops
        num_towers_total = num_towers + max(0, hops - 1)

        total_cost = (radio * num_radios) + (tower * num_towers_total) + (install * hops)
        surcharge = BIOME_LOGISTICS_SURCHARGE.get(profile.biome, 0.10)
        total_cost *= (1.0 + surcharge)

        details = {
            "distance_km": profile.nearest_fiber_km,
            "hops": hops,
            "towers_required": num_towers_total,
            "total_estimated_cost_brl": round(total_cost, 2),
            "capacity_mbps": 500 if hops == 1 else 250,
            "latency_ms": 5.0 * hops,
            "rationale": (
                f"Microwave backhaul selected: {profile.nearest_fiber_km:.1f} km, "
                f"{hops} hop(s), {num_towers_total} tower(s). "
                f"Good capacity with moderate latency."
            ),
        }
        logger.info(
            "Backhaul: microwave selected — %.1f km, %d hop(s), estimated R$%.0f",
            profile.nearest_fiber_km,
            hops,
            total_cost,
        )
        return "microwave", details

    # Satellite — prefer LEO (Starlink) for latency, GEO (Telebras) for cost
    # Use LEO if population > 100 (justifies ongoing cost) or if riverine/island
    if profile.population > 100 or profile.terrain_type in ("riverine", "island"):
        terminal = BACKHAUL_EQUIPMENT["satellite_leo"]["terminal_brl"]
        install = BACKHAUL_EQUIPMENT["satellite_leo"]["installation_brl"]
        monthly = BACKHAUL_EQUIPMENT["satellite_leo"]["monthly_service_brl"]
        total_cost = terminal + install

        details = {
            "provider": "Starlink (LEO)",
            "total_estimated_cost_brl": round(total_cost, 2),
            "monthly_service_brl": monthly,
            "capacity_mbps": 100,
            "latency_ms": 35.0,
            "rationale": (
                "LEO satellite backhaul selected: no fiber/microwave viable. "
                "Low latency (~35 ms), good for interactive applications."
            ),
        }
        logger.info(
            "Backhaul: satellite LEO selected — estimated R$%.0f + R$%.0f/mo",
            total_cost,
            monthly,
        )
        return "satellite_leo", details

    # GEO satellite as lowest-cost fallback
    terminal = BACKHAUL_EQUIPMENT["satellite_geo"]["terminal_brl"]
    install = BACKHAUL_EQUIPMENT["satellite_geo"]["installation_brl"]
    monthly = BACKHAUL_EQUIPMENT["satellite_geo"]["monthly_service_brl"]
    total_cost = terminal + install

    details = {
        "provider": "Telebras SGDC (GEO)",
        "total_estimated_cost_brl": round(total_cost, 2),
        "monthly_service_brl": monthly,
        "capacity_mbps": 10,
        "latency_ms": 600.0,
        "rationale": (
            "GEO satellite backhaul selected (Telebras SGDC): lowest cost option. "
            "High latency (~600 ms) limits real-time applications."
        ),
    }
    logger.info(
        "Backhaul: satellite GEO selected — estimated R$%.0f, free service (SGDC)",
        total_cost,
    )
    return "satellite_geo", details


def select_last_mile(profile: CommunityProfile) -> tuple[str, dict]:
    """Select last mile technology based on area and population.

    Decision logic:
    - WiFi mesh: area < 1 km^2 and population < 500 (concentrated village)
    - 4G/LTE 700 MHz: area 1-10 km^2 (standard rural coverage)
    - 4G/LTE 250 MHz: area 10-50 km^2 (wide-area rural)
    - TVWS: area > 50 km^2 or very sparse population
    - Satellite per-premises: island or extreme remote (< 50 people scattered)

    Args:
        profile: Community characteristics.

    Returns:
        Tuple of (technology_name, details_dict).
    """
    terrain_factor = TERRAIN_COVERAGE_FACTOR.get(profile.terrain_type, 0.7)

    # Handle edge case: zero or negative population
    if profile.population <= 0:
        logger.warning("Community has population <= 0; returning minimal design.")
        return "satellite_premises", {
            "subscribers": 0,
            "total_estimated_cost_brl": 0,
            "monthly_cost_brl": 0,
            "coverage_km2": 0,
            "rationale": "No population — no last mile deployment needed.",
        }

    # Island or extreme remote with tiny population: satellite per premises
    if (
        profile.terrain_type == "island"
        or (profile.population < 50 and profile.area_km2 > 10)
    ):
        subs = max(1, profile.population // 4)  # ~1 terminal per household
        eq = LAST_MILE_EQUIPMENT["satellite_premises"]
        capex = eq["terminal_per_premises_brl"] * subs
        monthly = eq["monthly_per_premises_brl"] * subs

        return "satellite_premises", {
            "subscribers": subs,
            "terminals": subs,
            "total_estimated_cost_brl": round(capex, 2),
            "monthly_cost_brl": round(monthly, 2),
            "coverage_km2": profile.area_km2,
            "rationale": (
                f"Satellite per-premises selected: {profile.terrain_type} terrain, "
                f"{profile.population} people. Each household gets a terminal."
            ),
        }

    # WiFi mesh: compact villages
    if profile.area_km2 < 1.0 and profile.population < 500:
        eq = LAST_MILE_EQUIPMENT["wifi_mesh"]
        # Calculate number of APs needed
        coverage_per_ap_km2 = math.pi * (eq["coverage_radius_m"] / 1000) ** 2 * terrain_factor
        num_aps = max(1, math.ceil(profile.area_km2 / coverage_per_ap_km2))
        subs = min(profile.population // 4, num_aps * eq["max_users_per_ap"])
        subs = max(1, subs)
        num_cpes = subs

        capex = (eq["ap_unit_brl"] * num_aps) + (eq["cpe_unit_brl"] * num_cpes)
        coverage = min(profile.area_km2, coverage_per_ap_km2 * num_aps)

        return "wifi_mesh", {
            "access_points": num_aps,
            "cpes": num_cpes,
            "subscribers": subs,
            "total_estimated_cost_brl": round(capex, 2),
            "monthly_cost_brl": 0,  # No per-unit monthly for WiFi
            "coverage_km2": round(coverage, 3),
            "rationale": (
                f"WiFi mesh selected: compact village ({profile.area_km2:.2f} km^2, "
                f"{profile.population} people). {num_aps} AP(s), up to {subs} subscribers."
            ),
        }

    # 4G/LTE 700 MHz: standard rural areas
    if profile.area_km2 <= 10.0:
        eq = LAST_MILE_EQUIPMENT["4g_700mhz"]
        effective_radius = eq["coverage_radius_km"] * terrain_factor
        coverage_per_site = math.pi * effective_radius ** 2
        num_sites = max(1, math.ceil(profile.area_km2 / coverage_per_site))
        subs = min(profile.population // 4, num_sites * eq["max_users"])
        subs = max(1, subs)
        num_cpes = subs

        capex = num_sites * (eq["enodeb_brl"] + eq["tower_brl"]) + (eq["cpe_unit_brl"] * num_cpes)
        coverage = min(profile.area_km2, coverage_per_site * num_sites)

        return "4g_700mhz", {
            "sites": num_sites,
            "cpes": num_cpes,
            "subscribers": subs,
            "effective_radius_km": round(effective_radius, 2),
            "total_estimated_cost_brl": round(capex, 2),
            "monthly_cost_brl": 0,
            "coverage_km2": round(coverage, 2),
            "rationale": (
                f"4G/LTE 700 MHz selected: {profile.area_km2:.1f} km^2 coverage area. "
                f"{num_sites} site(s), effective radius {effective_radius:.1f} km."
            ),
        }

    # 4G/LTE 250 MHz: wide-area rural
    if profile.area_km2 <= 50.0:
        eq = LAST_MILE_EQUIPMENT["4g_250mhz"]
        effective_radius = eq["coverage_radius_km"] * terrain_factor
        coverage_per_site = math.pi * effective_radius ** 2
        num_sites = max(1, math.ceil(profile.area_km2 / coverage_per_site))
        subs = min(profile.population // 4, num_sites * eq["max_users"])
        subs = max(1, subs)
        num_cpes = subs

        capex = num_sites * (eq["enodeb_brl"] + eq["tower_brl"]) + (eq["cpe_unit_brl"] * num_cpes)
        coverage = min(profile.area_km2, coverage_per_site * num_sites)

        return "4g_250mhz", {
            "sites": num_sites,
            "cpes": num_cpes,
            "subscribers": subs,
            "effective_radius_km": round(effective_radius, 2),
            "total_estimated_cost_brl": round(capex, 2),
            "monthly_cost_brl": 0,
            "coverage_km2": round(coverage, 2),
            "rationale": (
                f"4G/LTE 250 MHz selected: wide-area {profile.area_km2:.1f} km^2. "
                f"{num_sites} site(s), effective radius {effective_radius:.1f} km."
            ),
        }

    # TVWS: very large / sparse areas
    eq = LAST_MILE_EQUIPMENT["tvws"]
    effective_radius = eq["coverage_radius_km"] * terrain_factor
    coverage_per_site = math.pi * effective_radius ** 2
    num_sites = max(1, math.ceil(profile.area_km2 / coverage_per_site))
    subs = min(profile.population // 4, num_sites * eq["max_users"])
    subs = max(1, subs)
    num_cpes = subs

    capex = (eq["base_station_brl"] * num_sites) + (eq["cpe_unit_brl"] * num_cpes)
    coverage = min(profile.area_km2, coverage_per_site * num_sites)

    return "tvws", {
        "sites": num_sites,
        "cpes": num_cpes,
        "subscribers": subs,
        "effective_radius_km": round(effective_radius, 2),
        "total_estimated_cost_brl": round(capex, 2),
        "monthly_cost_brl": 0,
        "coverage_km2": round(coverage, 2),
        "rationale": (
            f"TVWS selected: very large area ({profile.area_km2:.1f} km^2). "
            f"{num_sites} base station(s), effective radius {effective_radius:.1f} km."
        ),
    }


def select_power(profile: CommunityProfile) -> tuple[str, dict]:
    """Select power solution.

    Decision logic:
    - Grid: if grid_power is True
    - Grid + solar hybrid: if grid power but unreliable (remote areas)
    - Solar + battery: if no grid power

    Args:
        profile: Community characteristics.

    Returns:
        Tuple of (technology_name, details_dict).
    """
    if profile.grid_power:
        # In remote biomes, grid may be unreliable — recommend hybrid
        unreliable_biomes = {"amazonia", "pantanal"}
        if profile.biome in unreliable_biomes or profile.nearest_road_km > 20.0:
            eq = POWER_EQUIPMENT["grid_solar_hybrid"]
            capex = eq["grid_connection_brl"] + eq["solar_supplement_brl"]
            monthly = eq["monthly_energy_brl"] + eq["monthly_maintenance_brl"]

            return "grid_solar_hybrid", {
                "total_estimated_cost_brl": round(capex, 2),
                "monthly_cost_brl": round(monthly, 2),
                "rationale": (
                    "Grid + solar hybrid selected: grid available but potentially "
                    "unreliable in this region. Solar provides backup power."
                ),
            }

        eq = POWER_EQUIPMENT["grid"]
        capex = eq["connection_cost_brl"] + eq["ups_brl"]
        monthly = eq["monthly_energy_brl"]

        return "grid", {
            "total_estimated_cost_brl": round(capex, 2),
            "monthly_cost_brl": round(monthly, 2),
            "rationale": "Grid power selected: reliable grid electricity available.",
        }

    # Off-grid: solar + battery
    eq = POWER_EQUIPMENT["solar_battery"]
    # Estimate power consumption based on last mile tech (rough average: 500 W)
    estimated_power_kw = 0.5
    capex = eq["base_system_brl"] + (eq["per_kw_brl"] * estimated_power_kw)
    # 3 days autonomy, 10 kWh per day estimate
    battery_kwh = estimated_power_kw * 24 * 3 / 0.8  # 80% DoD
    battery_cost = battery_kwh * eq["battery_per_kwh_brl"]
    capex += battery_cost
    monthly = eq["monthly_maintenance_brl"]

    return "solar_battery", {
        "estimated_power_kw": estimated_power_kw,
        "battery_kwh": round(battery_kwh, 1),
        "total_estimated_cost_brl": round(capex, 2),
        "monthly_cost_brl": round(monthly, 2),
        "rationale": (
            "Solar + battery selected: no grid power available. "
            f"Sized for {estimated_power_kw} kW load with 3 days autonomy."
        ),
    }


def estimate_equipment(
    backhaul: str,
    last_mile: str,
    power: str,
    profile: CommunityProfile,
    backhaul_details: dict,
    last_mile_details: dict,
    power_details: dict,
) -> list[dict]:
    """Generate itemized equipment list with costs.

    Args:
        backhaul: Backhaul technology name.
        last_mile: Last mile technology name.
        power: Power solution name.
        profile: Community characteristics.
        backhaul_details: Details from select_backhaul.
        last_mile_details: Details from select_last_mile.
        power_details: Details from select_power.

    Returns:
        List of equipment items with name, quantity, unit_cost, and total_cost.
    """
    equipment: list[dict] = []

    # --- Backhaul equipment ---
    if backhaul == "fiber":
        distance = backhaul_details.get("distance_km", 0)
        equipment.append({
            "category": "backhaul",
            "item": "Fiber optic cable (rural aerial)",
            "quantity": math.ceil(distance),
            "unit": "km",
            "unit_cost_brl": BACKHAUL_EQUIPMENT["fiber"]["cost_per_km_brl"],
            "total_cost_brl": round(distance * BACKHAUL_EQUIPMENT["fiber"]["cost_per_km_brl"], 2),
        })
        equipment.append({
            "category": "backhaul",
            "item": "Fiber installation labor",
            "quantity": math.ceil(distance),
            "unit": "km",
            "unit_cost_brl": BACKHAUL_EQUIPMENT["fiber"]["installation_per_km_brl"],
            "total_cost_brl": round(distance * BACKHAUL_EQUIPMENT["fiber"]["installation_per_km_brl"], 2),
        })
        equipment.append({
            "category": "backhaul",
            "item": "Terminal equipment (OLT/media converter)",
            "quantity": 1,
            "unit": "unit",
            "unit_cost_brl": BACKHAUL_EQUIPMENT["fiber"]["terminal_equipment_brl"],
            "total_cost_brl": BACKHAUL_EQUIPMENT["fiber"]["terminal_equipment_brl"],
        })

    elif backhaul == "microwave":
        hops = backhaul_details.get("hops", 1)
        towers = backhaul_details.get("towers_required", 2)
        equipment.append({
            "category": "backhaul",
            "item": "Microwave radio pair (licensed, 1 Gbps)",
            "quantity": hops,
            "unit": "pair",
            "unit_cost_brl": BACKHAUL_EQUIPMENT["microwave"]["radio_pair_brl"],
            "total_cost_brl": hops * BACKHAUL_EQUIPMENT["microwave"]["radio_pair_brl"],
        })
        equipment.append({
            "category": "backhaul",
            "item": "Guyed tower (30m)",
            "quantity": towers,
            "unit": "unit",
            "unit_cost_brl": BACKHAUL_EQUIPMENT["microwave"]["tower_per_unit_brl"],
            "total_cost_brl": towers * BACKHAUL_EQUIPMENT["microwave"]["tower_per_unit_brl"],
        })

    elif backhaul in ("satellite_leo", "satellite_geo"):
        key = backhaul
        equipment.append({
            "category": "backhaul",
            "item": f"Satellite terminal ({backhaul_details.get('provider', backhaul)})",
            "quantity": 1,
            "unit": "unit",
            "unit_cost_brl": BACKHAUL_EQUIPMENT[key]["terminal_brl"],
            "total_cost_brl": BACKHAUL_EQUIPMENT[key]["terminal_brl"],
        })

    # --- Last mile equipment ---
    if last_mile == "wifi_mesh":
        aps = last_mile_details.get("access_points", 1)
        cpes = last_mile_details.get("cpes", 1)
        eq = LAST_MILE_EQUIPMENT["wifi_mesh"]
        equipment.append({
            "category": "last_mile",
            "item": "WiFi mesh access point (outdoor)",
            "quantity": aps,
            "unit": "unit",
            "unit_cost_brl": eq["ap_unit_brl"],
            "total_cost_brl": aps * eq["ap_unit_brl"],
        })
        equipment.append({
            "category": "last_mile",
            "item": "WiFi CPE (client device)",
            "quantity": cpes,
            "unit": "unit",
            "unit_cost_brl": eq["cpe_unit_brl"],
            "total_cost_brl": cpes * eq["cpe_unit_brl"],
        })

    elif last_mile in ("4g_700mhz", "4g_250mhz"):
        sites = last_mile_details.get("sites", 1)
        cpes = last_mile_details.get("cpes", 1)
        eq = LAST_MILE_EQUIPMENT[last_mile]
        equipment.append({
            "category": "last_mile",
            "item": f"eNodeB ({last_mile.replace('_', ' ').upper()})",
            "quantity": sites,
            "unit": "unit",
            "unit_cost_brl": eq["enodeb_brl"],
            "total_cost_brl": sites * eq["enodeb_brl"],
        })
        equipment.append({
            "category": "last_mile",
            "item": f"Tower ({last_mile})",
            "quantity": sites,
            "unit": "unit",
            "unit_cost_brl": eq["tower_brl"],
            "total_cost_brl": sites * eq["tower_brl"],
        })
        equipment.append({
            "category": "last_mile",
            "item": "LTE CPE (subscriber unit)",
            "quantity": cpes,
            "unit": "unit",
            "unit_cost_brl": eq["cpe_unit_brl"],
            "total_cost_brl": cpes * eq["cpe_unit_brl"],
        })

    elif last_mile == "tvws":
        sites = last_mile_details.get("sites", 1)
        cpes = last_mile_details.get("cpes", 1)
        eq = LAST_MILE_EQUIPMENT["tvws"]
        equipment.append({
            "category": "last_mile",
            "item": "TVWS base station",
            "quantity": sites,
            "unit": "unit",
            "unit_cost_brl": eq["base_station_brl"],
            "total_cost_brl": sites * eq["base_station_brl"],
        })
        equipment.append({
            "category": "last_mile",
            "item": "TVWS CPE",
            "quantity": cpes,
            "unit": "unit",
            "unit_cost_brl": eq["cpe_unit_brl"],
            "total_cost_brl": cpes * eq["cpe_unit_brl"],
        })

    elif last_mile == "satellite_premises":
        terminals = last_mile_details.get("terminals", 1)
        eq = LAST_MILE_EQUIPMENT["satellite_premises"]
        equipment.append({
            "category": "last_mile",
            "item": "Satellite terminal (per-premises)",
            "quantity": terminals,
            "unit": "unit",
            "unit_cost_brl": eq["terminal_per_premises_brl"],
            "total_cost_brl": terminals * eq["terminal_per_premises_brl"],
        })

    # --- Power equipment ---
    equipment.append({
        "category": "power",
        "item": f"Power system ({power})",
        "quantity": 1,
        "unit": "system",
        "unit_cost_brl": power_details.get("total_estimated_cost_brl", 0),
        "total_cost_brl": power_details.get("total_estimated_cost_brl", 0),
    })

    return equipment


def design_hybrid_network(profile: CommunityProfile) -> HybridDesign:
    """Design optimal hybrid network for a rural community.

    Orchestrates backhaul, last mile, and power selection, then produces
    a complete design with equipment list, cost estimates, and notes.

    Args:
        profile: Community characteristics.

    Returns:
        Complete HybridDesign with all technology selections, equipment,
        and cost estimates.

    Raises:
        ValueError: If profile has invalid data (e.g. negative population).
    """
    if profile.population < 0:
        raise ValueError("Population cannot be negative.")
    if profile.area_km2 < 0:
        raise ValueError("Area cannot be negative.")

    logger.info(
        "Designing hybrid network for community at (%.4f, %.4f): "
        "pop=%d, area=%.1f km^2, terrain=%s, biome=%s",
        profile.latitude,
        profile.longitude,
        profile.population,
        profile.area_km2,
        profile.terrain_type,
        profile.biome,
    )

    notes: list[str] = []

    # Handle edge case: zero population
    if profile.population == 0:
        notes.append("WARNING: Community has zero population. Returning minimal design.")
        return HybridDesign(
            backhaul_technology="none",
            backhaul_details={"rationale": "No population, no backhaul needed."},
            last_mile_technology="none",
            last_mile_details={"rationale": "No population, no last mile needed."},
            power_solution="none",
            power_details={"rationale": "No population, no power needed."},
            equipment_list=[],
            estimated_capex_brl=0.0,
            estimated_monthly_opex_brl=0.0,
            coverage_estimate_km2=0.0,
            max_subscribers=0,
            design_notes=notes,
        )

    # Step 1: Select backhaul
    backhaul_tech, backhaul_details = select_backhaul(profile)

    # Step 2: Select last mile
    last_mile_tech, last_mile_details = select_last_mile(profile)

    # Step 3: Select power
    power_tech, power_details = select_power(profile)

    # Step 4: Generate equipment list
    equipment = estimate_equipment(
        backhaul_tech,
        last_mile_tech,
        power_tech,
        profile,
        backhaul_details,
        last_mile_details,
        power_details,
    )

    # Step 5: Calculate totals
    total_capex = sum(item["total_cost_brl"] for item in equipment)
    # Apply logistics surcharge
    surcharge_rate = BIOME_LOGISTICS_SURCHARGE.get(profile.biome, 0.10)
    logistics_surcharge = total_capex * surcharge_rate
    total_capex += logistics_surcharge

    # Monthly OPEX
    monthly_opex = (
        backhaul_details.get("monthly_service_brl", 0)
        + last_mile_details.get("monthly_cost_brl", 0)
        + power_details.get("monthly_cost_brl", 0)
    )

    coverage = last_mile_details.get("coverage_km2", profile.area_km2)
    max_subs = last_mile_details.get("subscribers", profile.population // 4)

    # Step 6: Add design notes
    if profile.biome == "amazonia":
        notes.append(
            "AMAZON: Consider river crossing requirements. Logistics costs "
            "are 40% above baseline. Rainy season (Dec-May) limits installation."
        )
    if profile.terrain_type == "riverine":
        notes.append(
            "RIVERINE: Community is along a river. Consider boat-based "
            "maintenance access and flood-resistant equipment mounting."
        )
    if not profile.grid_power:
        notes.append(
            "OFF-GRID: No grid power. Solar system requires periodic maintenance "
            "and battery replacement every 5-10 years (lithium) or 2-4 years (lead-acid)."
        )
    if backhaul_tech.startswith("satellite"):
        notes.append(
            "SATELLITE BACKHAUL: Shared bandwidth. Monitor usage and consider "
            "traffic shaping policies. Check Telebras SGDC eligibility for free service."
        )
    if profile.nearest_road_km > 20:
        notes.append(
            f"REMOTE ACCESS: Nearest road is {profile.nearest_road_km:.0f} km away. "
            "Installation and maintenance will require specialized logistics "
            "(boat, helicopter, or extended overland travel)."
        )

    # Per-subscriber cost check
    if max_subs > 0:
        per_sub_capex = total_capex / max_subs
        if per_sub_capex > 10_000:
            notes.append(
                f"HIGH COST: CAPEX per subscriber is R${per_sub_capex:,.0f}. "
                "Consider government funding programs (FUST, Norte Conectado, New PAC)."
            )

    design = HybridDesign(
        backhaul_technology=backhaul_tech,
        backhaul_details=backhaul_details,
        last_mile_technology=last_mile_tech,
        last_mile_details=last_mile_details,
        power_solution=power_tech,
        power_details=power_details,
        equipment_list=equipment,
        estimated_capex_brl=round(total_capex, 2),
        estimated_monthly_opex_brl=round(monthly_opex, 2),
        coverage_estimate_km2=round(coverage, 2),
        max_subscribers=max_subs,
        design_notes=notes,
    )

    logger.info(
        "Hybrid design complete: backhaul=%s, last_mile=%s, power=%s, "
        "CAPEX=R$%.0f, OPEX=R$%.0f/mo, %d max subs",
        backhaul_tech,
        last_mile_tech,
        power_tech,
        total_capex,
        monthly_opex,
        max_subs,
    )

    return design
