"""
ENLACE FTTH Network Design Service

Pure-Python optical engineering for Fiber-to-the-Home network design.
Calculates optical budgets, splitter cascades, OLT sizing, building density
estimation, and generates itemized BOMs with Brazilian market pricing.
"""

import logging
import math
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optical constants
# ---------------------------------------------------------------------------

# Fiber attenuation (dB/km)
FIBER_ATTENUATION = {
    "1310nm": 0.35,
    "1490nm": 0.25,
    "1550nm": 0.22,
}

# Loss per event (dB)
SPLICE_LOSS_DB = 0.1
CONNECTOR_LOSS_DB = 0.5

# Splitter insertion loss (dB)
SPLITTER_LOSS = {
    2: 3.5,
    4: 7.0,
    8: 10.5,
    16: 13.5,
    32: 17.0,
    64: 20.5,
}

# PON technology specs
PON_SPECS = {
    "GPON": {
        "class": "C+",
        "budget_db": 33.0,
        "downstream_gbps": 2.488,
        "upstream_gbps": 1.244,
        "typical_splits": [32, 64],
        "max_distance_km": 20,
        "wavelength_down": "1490nm",
        "wavelength_up": "1310nm",
    },
    "XGS-PON": {
        "class": "N2",
        "budget_db": 34.0,
        "downstream_gbps": 9.953,
        "upstream_gbps": 9.953,
        "typical_splits": [16, 32],
        "max_distance_km": 20,
        "wavelength_down": "1550nm",
        "wavelength_up": "1310nm",
    },
}

# ---------------------------------------------------------------------------
# BOM cost constants (BRL, Brazilian market 2025)
# ---------------------------------------------------------------------------

FTTH_COSTS = {
    # OLT equipment
    "olt_chassis": 45_000.0,
    "gpon_board_8port": 12_000.0,
    "xgspon_board_8port": 22_000.0,
    # Splitters
    "splitter_1x2": 120.0,
    "splitter_1x4": 180.0,
    "splitter_1x8": 280.0,
    "splitter_1x16": 450.0,
    "splitter_1x32": 650.0,
    "splitter_1x64": 850.0,
    # Cabinets and enclosures
    "fdh_cabinet_small": 3_200.0,   # up to 256 fibers
    "fdh_cabinet_large": 4_500.0,   # up to 576 fibers
    "nap_box_8port": 250.0,
    "nap_box_16port": 350.0,
    # ONT
    "ont_gpon": 180.0,
    "ont_xgspon": 350.0,
    # Cable per km
    "trunk_cable_48core_per_km": 18_000.0,
    "trunk_cable_96core_per_km": 22_000.0,
    "distribution_cable_12core_per_km": 8_000.0,
    "drop_cable_2core_per_km": 2_500.0,
    # Civil works per km
    "civil_aerial_per_km": 6_000.0,
    "civil_underground_per_km": 35_000.0,
    "civil_mixed_per_km": 18_000.0,
    # Accessories
    "splice_closure_each": 800.0,
    "connector_each": 15.0,
}

SPLITTER_COST_MAP = {
    2: FTTH_COSTS["splitter_1x2"],
    4: FTTH_COSTS["splitter_1x4"],
    8: FTTH_COSTS["splitter_1x8"],
    16: FTTH_COSTS["splitter_1x16"],
    32: FTTH_COSTS["splitter_1x32"],
    64: FTTH_COSTS["splitter_1x64"],
}


# ---------------------------------------------------------------------------
# Optical budget calculation
# ---------------------------------------------------------------------------

def calculate_optical_budget(
    fiber_km: float,
    splices: int,
    connectors: int,
    splitter_ratios: list[int],
    technology: str = "GPON",
) -> dict[str, Any]:
    """Calculate optical power budget and determine link viability.

    Args:
        fiber_km: Total fiber distance in kilometers.
        splices: Number of fusion splices in the path.
        connectors: Number of connectors (SC/APC etc.).
        splitter_ratios: List of splitter ratios in the path, e.g. [4, 8] for 1:4 + 1:8.
        technology: PON technology — "GPON" or "XGS-PON".

    Returns:
        Dict with loss breakdown, total loss, margin, max distance, and viability.
    """
    spec = PON_SPECS.get(technology, PON_SPECS["GPON"])
    budget_db = spec["budget_db"]
    wavelength = spec["wavelength_down"]
    attenuation_per_km = FIBER_ATTENUATION.get(wavelength, 0.25)

    fiber_loss = fiber_km * attenuation_per_km
    splice_loss = splices * SPLICE_LOSS_DB
    connector_loss = connectors * CONNECTOR_LOSS_DB

    splitter_loss = 0.0
    for ratio in splitter_ratios:
        splitter_loss += SPLITTER_LOSS.get(ratio, 0.0)

    total_loss = fiber_loss + splice_loss + connector_loss + splitter_loss
    margin = budget_db - total_loss
    viable = margin >= 3.0  # Minimum 3 dB margin recommended

    # Max distance with current splitter config and 3 dB safety margin
    remaining_for_fiber = budget_db - splice_loss - connector_loss - splitter_loss - 3.0
    max_distance_km = max(0, remaining_for_fiber / attenuation_per_km) if attenuation_per_km > 0 else 0

    total_split = 1
    for r in splitter_ratios:
        total_split *= r

    return {
        "technology": technology,
        "pon_class": spec["class"],
        "budget_db": budget_db,
        "wavelength": wavelength,
        "losses": {
            "fiber_db": round(fiber_loss, 2),
            "splice_db": round(splice_loss, 2),
            "connector_db": round(connector_loss, 2),
            "splitter_db": round(splitter_loss, 2),
        },
        "total_loss_db": round(total_loss, 2),
        "margin_db": round(margin, 2),
        "viable": viable,
        "max_distance_km": round(max_distance_km, 1),
        "total_split_ratio": total_split,
        "fiber_km": fiber_km,
        "splices": splices,
        "connectors": connectors,
        "splitter_ratios": splitter_ratios,
    }


# ---------------------------------------------------------------------------
# Splitter cascade design
# ---------------------------------------------------------------------------

def design_splitter_cascade(
    total_split: int,
    levels: int = 2,
) -> dict[str, Any]:
    """Design a multi-level splitter cascade to achieve a target split ratio.

    Args:
        total_split: Target total split ratio (e.g. 32, 64).
        levels: Number of cascade levels (1 or 2).

    Returns:
        Dict with cascade stages, total loss, and description.
    """
    if levels == 1:
        if total_split not in SPLITTER_LOSS:
            closest = min(SPLITTER_LOSS.keys(), key=lambda x: abs(x - total_split))
            total_split = closest
        return {
            "levels": 1,
            "stages": [
                {
                    "level": 1,
                    "location": "FDH",
                    "ratio": total_split,
                    "loss_db": SPLITTER_LOSS[total_split],
                    "unit_cost_brl": SPLITTER_COST_MAP[total_split],
                }
            ],
            "total_split": total_split,
            "total_loss_db": SPLITTER_LOSS[total_split],
            "description": f"Splitter único 1:{total_split} no FDH",
        }

    # 2-level cascade: find optimal factorization
    best = None
    for first in sorted(SPLITTER_LOSS.keys()):
        if total_split % first == 0:
            second = total_split // first
            if second in SPLITTER_LOSS:
                loss = SPLITTER_LOSS[first] + SPLITTER_LOSS[second]
                if best is None or loss < best["loss"]:
                    best = {"first": first, "second": second, "loss": loss}

    if best is None:
        # Fallback to single stage
        return design_splitter_cascade(total_split, levels=1)

    return {
        "levels": 2,
        "stages": [
            {
                "level": 1,
                "location": "FDH",
                "ratio": best["first"],
                "loss_db": SPLITTER_LOSS[best["first"]],
                "unit_cost_brl": SPLITTER_COST_MAP[best["first"]],
            },
            {
                "level": 2,
                "location": "NAP",
                "ratio": best["second"],
                "loss_db": SPLITTER_LOSS[best["second"]],
                "unit_cost_brl": SPLITTER_COST_MAP[best["second"]],
            },
        ],
        "total_split": total_split,
        "total_loss_db": round(best["loss"], 2),
        "description": f"1:{best['first']} no FDH + 1:{best['second']} no NAP = 1:{total_split}",
    }


# ---------------------------------------------------------------------------
# OLT sizing
# ---------------------------------------------------------------------------

def size_olt(
    subscribers: int,
    technology: str = "GPON",
    split_ratio: int = 32,
) -> dict[str, Any]:
    """Size OLT equipment for target subscriber count.

    Args:
        subscribers: Target number of ONTs/subscribers.
        technology: "GPON" or "XGS-PON".
        split_ratio: Splitter ratio per PON port (e.g. 32).

    Returns:
        Dict with port count, line cards, chassis, and bandwidth calculations.
    """
    spec = PON_SPECS.get(technology, PON_SPECS["GPON"])
    ports_per_board = 8

    pon_ports_needed = max(1, math.ceil(subscribers / split_ratio))
    boards_needed = max(1, math.ceil(pon_ports_needed / ports_per_board))
    # Typical chassis holds 8-16 boards
    chassis_needed = max(1, math.ceil(boards_needed / 14))

    total_bandwidth_down = pon_ports_needed * spec["downstream_gbps"]
    total_bandwidth_up = pon_ports_needed * spec["upstream_gbps"]
    bw_per_sub_down = (total_bandwidth_down * 1000) / max(subscribers, 1)  # Mbps
    bw_per_sub_up = (total_bandwidth_up * 1000) / max(subscribers, 1)

    board_cost = FTTH_COSTS["xgspon_board_8port"] if technology == "XGS-PON" else FTTH_COSTS["gpon_board_8port"]
    total_olt_cost = chassis_needed * FTTH_COSTS["olt_chassis"] + boards_needed * board_cost

    return {
        "technology": technology,
        "subscribers": subscribers,
        "split_ratio": split_ratio,
        "pon_ports": pon_ports_needed,
        "boards": boards_needed,
        "ports_per_board": ports_per_board,
        "chassis": chassis_needed,
        "total_bandwidth_down_gbps": round(total_bandwidth_down, 1),
        "total_bandwidth_up_gbps": round(total_bandwidth_up, 1),
        "bandwidth_per_sub_down_mbps": round(bw_per_sub_down, 1),
        "bandwidth_per_sub_up_mbps": round(bw_per_sub_up, 1),
        "olt_cost_brl": round(total_olt_cost, 2),
    }


# ---------------------------------------------------------------------------
# Building density estimation
# ---------------------------------------------------------------------------

async def estimate_building_density(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float,
    l2_id: Optional[int] = None,
) -> dict[str, Any]:
    """Estimate building/household density near a point.

    Uses building_footprints if available, falls back to admin_level_2 population stats.

    Args:
        db: Async SQLAlchemy session.
        lat, lon: Center point coordinates.
        radius_km: Search radius in km.
        l2_id: Optional municipality ID for direct lookup.

    Returns:
        Dict with estimated buildings, households, density, and data source.
    """
    area_km2 = math.pi * radius_km ** 2

    # Try building_footprints first
    bf_sql = text("""
        SELECT COUNT(*) AS building_count,
               COALESCE(SUM(area_m2), 0) AS total_area_m2
        FROM building_footprints
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius_m
        )
    """)
    result = await db.execute(bf_sql, {"lon": lon, "lat": lat, "radius_m": radius_km * 1000})
    row = result.fetchone()
    buildings = row.building_count if row else 0

    if buildings > 0:
        avg_building_area = float(row.total_area_m2) / buildings if buildings > 0 else 150
        # Estimate households: residential buildings avg 1-4 units
        households = int(buildings * 1.5) if avg_building_area < 300 else int(buildings * 3)
        return {
            "source": "building_footprints",
            "buildings": buildings,
            "households": households,
            "area_km2": round(area_km2, 2),
            "building_density_km2": round(buildings / area_km2, 1),
            "household_density_km2": round(households / area_km2, 1),
        }

    # Fallback: admin_level_2 population stats
    if l2_id:
        muni_sql = text("""
            SELECT population, area_km2
            FROM admin_level_2 WHERE id = :l2_id
        """)
    else:
        muni_sql = text("""
            SELECT population, area_km2
            FROM admin_level_2
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                :radius_m
            )
            ORDER BY ST_Distance(
                geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            LIMIT 1
        """)

    params: dict[str, Any] = {"lon": lon, "lat": lat, "radius_m": radius_km * 1000}
    if l2_id:
        params = {"l2_id": l2_id}
    result = await db.execute(muni_sql, params)
    muni = result.fetchone()

    if muni and muni.population:
        pop = muni.population
        muni_area = float(muni.area_km2) if muni.area_km2 else 100
        # Scale population to the search radius area
        pop_in_area = int(pop * min(area_km2 / muni_area, 1.0))
        households = max(1, int(pop_in_area / 3.2))  # avg 3.2 people per household
        buildings = max(1, int(households * 0.7))  # ~70% single-unit
        return {
            "source": "population_estimate",
            "buildings": buildings,
            "households": households,
            "area_km2": round(area_km2, 2),
            "building_density_km2": round(buildings / area_km2, 1),
            "household_density_km2": round(households / area_km2, 1),
            "municipality_population": pop,
        }

    return {
        "source": "default",
        "buildings": 0,
        "households": 0,
        "area_km2": round(area_km2, 2),
        "building_density_km2": 0,
        "household_density_km2": 0,
    }


# ---------------------------------------------------------------------------
# FTTH network design orchestrator
# ---------------------------------------------------------------------------

async def design_ftth_network(
    db: AsyncSession,
    lat: float,
    lon: float,
    radius_km: float,
    subscribers: int,
    technology: str = "GPON",
    split_ratio: int = 32,
    cascade_levels: int = 2,
    deployment_type: str = "aerial",
    l2_id: Optional[int] = None,
) -> dict[str, Any]:
    """Full FTTH network design combining all sub-calculations.

    Args:
        db: Async SQLAlchemy session.
        lat, lon: Central OLT location.
        radius_km: Service area radius.
        subscribers: Target subscriber count.
        technology: "GPON" or "XGS-PON".
        split_ratio: Target split ratio (16, 32, 64).
        cascade_levels: 1 or 2 level splitter cascade.
        deployment_type: "aerial", "underground", or "mixed".
        l2_id: Optional municipality ID.

    Returns:
        Complete FTTH design with optical budget, cascade, OLT, coverage, and BOM.
    """
    # 1. Building density
    density = await estimate_building_density(db, lat, lon, radius_km, l2_id)

    # 2. Splitter cascade
    cascade = design_splitter_cascade(split_ratio, cascade_levels)

    # 3. OLT sizing
    olt = size_olt(subscribers, technology, split_ratio)

    # 4. Network geometry estimates
    # Trunk: OLT to FDH (avg 40% of radius)
    trunk_km = radius_km * 0.4
    # Distribution: FDH to NAPs (avg 30% of radius)
    distribution_km = radius_km * 0.3 * math.ceil(subscribers / 256)
    # Drop: NAP to subscriber (avg 100m each)
    drop_total_km = subscribers * 0.1 / 1000 * radius_km  # scale with area

    avg_fiber_km = trunk_km + (distribution_km / max(olt["pon_ports"], 1))
    splices_per_path = max(2, int(avg_fiber_km / 2))  # ~1 splice per 2km
    connectors_per_path = 4  # OLT, FDH in, FDH out, ONT

    # 5. Optical budget for worst-case path
    splitter_ratios = [s["ratio"] for s in cascade["stages"]]
    optical = calculate_optical_budget(
        fiber_km=avg_fiber_km + radius_km * 0.3,  # add drop distance
        splices=splices_per_path,
        connectors=connectors_per_path,
        splitter_ratios=splitter_ratios,
        technology=technology,
    )

    # 6. BOM
    bom = generate_ftth_bom(
        subscribers=subscribers,
        technology=technology,
        split_ratio=split_ratio,
        cascade=cascade,
        olt=olt,
        trunk_km=trunk_km,
        distribution_km=distribution_km,
        drop_total_km=drop_total_km,
        deployment_type=deployment_type,
    )

    return {
        "optical_budget": optical,
        "splitter_cascade": cascade,
        "olt_sizing": olt,
        "coverage": density,
        "bom": bom,
        "summary": {
            "technology": technology,
            "subscribers": subscribers,
            "split_ratio": split_ratio,
            "deployment_type": deployment_type,
            "total_capex_brl": bom["total_cost_brl"],
            "capex_per_subscriber_brl": round(bom["total_cost_brl"] / max(subscribers, 1), 2),
            "optical_margin_db": optical["margin_db"],
            "optical_viable": optical["viable"],
            "max_reach_km": optical["max_distance_km"],
            "trunk_km": round(trunk_km, 2),
            "distribution_km": round(distribution_km, 2),
            "drop_km": round(drop_total_km, 2),
        },
    }


# ---------------------------------------------------------------------------
# BOM generation
# ---------------------------------------------------------------------------

def generate_ftth_bom(
    subscribers: int,
    technology: str,
    split_ratio: int,
    cascade: dict[str, Any],
    olt: dict[str, Any],
    trunk_km: float,
    distribution_km: float,
    drop_total_km: float,
    deployment_type: str = "aerial",
) -> dict[str, Any]:
    """Generate itemized BOM for an FTTH deployment.

    Returns:
        Dict with categorized line items, subtotals, and grand total.
    """
    items: list[dict[str, Any]] = []

    # -- OLT Equipment --
    items.append({
        "category": "Equipamento OLT",
        "item": "Chassis OLT",
        "unit": "un",
        "quantity": olt["chassis"],
        "unit_cost_brl": FTTH_COSTS["olt_chassis"],
        "total_cost_brl": round(olt["chassis"] * FTTH_COSTS["olt_chassis"], 2),
    })
    board_key = "xgspon_board_8port" if technology == "XGS-PON" else "gpon_board_8port"
    items.append({
        "category": "Equipamento OLT",
        "item": f"Placa {'XGS-PON' if technology == 'XGS-PON' else 'GPON'} 8 portas",
        "unit": "un",
        "quantity": olt["boards"],
        "unit_cost_brl": FTTH_COSTS[board_key],
        "total_cost_brl": round(olt["boards"] * FTTH_COSTS[board_key], 2),
    })

    # -- ONTs --
    ont_key = "ont_xgspon" if technology == "XGS-PON" else "ont_gpon"
    items.append({
        "category": "Equipamento CPE",
        "item": f"ONT {'XGS-PON' if technology == 'XGS-PON' else 'GPON'}",
        "unit": "un",
        "quantity": subscribers,
        "unit_cost_brl": FTTH_COSTS[ont_key],
        "total_cost_brl": round(subscribers * FTTH_COSTS[ont_key], 2),
    })

    # -- Splitters --
    for stage in cascade["stages"]:
        ratio = stage["ratio"]
        # Number of splitters depends on stage level
        if stage["level"] == 1:
            qty = olt["pon_ports"]
        else:
            qty = math.ceil(subscribers / ratio)
        cost_key = f"splitter_1x{ratio}"
        unit_cost = FTTH_COSTS.get(cost_key, SPLITTER_COST_MAP.get(ratio, 300))
        items.append({
            "category": "Splitters",
            "item": f"Splitter 1:{ratio} ({stage['location']})",
            "unit": "un",
            "quantity": qty,
            "unit_cost_brl": unit_cost,
            "total_cost_brl": round(qty * unit_cost, 2),
        })

    # -- Cabinets --
    fdh_count = max(1, math.ceil(subscribers / 256))
    fdh_cost = FTTH_COSTS["fdh_cabinet_large"] if subscribers > 256 else FTTH_COSTS["fdh_cabinet_small"]
    items.append({
        "category": "Gabinetes",
        "item": "Armário FDH",
        "unit": "un",
        "quantity": fdh_count,
        "unit_cost_brl": fdh_cost,
        "total_cost_brl": round(fdh_count * fdh_cost, 2),
    })

    nap_count = math.ceil(subscribers / 8)
    nap_cost = FTTH_COSTS["nap_box_8port"]
    items.append({
        "category": "Gabinetes",
        "item": "Caixa NAP 8 portas",
        "unit": "un",
        "quantity": nap_count,
        "unit_cost_brl": nap_cost,
        "total_cost_brl": round(nap_count * nap_cost, 2),
    })

    # -- Cables --
    core_count = 48 if subscribers <= 1000 else 96
    trunk_cost_key = f"trunk_cable_{core_count}core_per_km"
    trunk_unit = FTTH_COSTS.get(trunk_cost_key, FTTH_COSTS["trunk_cable_48core_per_km"])
    items.append({
        "category": "Cabos",
        "item": f"Cabo tronco {core_count} fibras",
        "unit": "km",
        "quantity": round(trunk_km, 2),
        "unit_cost_brl": trunk_unit,
        "total_cost_brl": round(trunk_km * trunk_unit, 2),
    })
    items.append({
        "category": "Cabos",
        "item": "Cabo distribuição 12 fibras",
        "unit": "km",
        "quantity": round(distribution_km, 2),
        "unit_cost_brl": FTTH_COSTS["distribution_cable_12core_per_km"],
        "total_cost_brl": round(distribution_km * FTTH_COSTS["distribution_cable_12core_per_km"], 2),
    })
    items.append({
        "category": "Cabos",
        "item": "Cabo drop 2 fibras",
        "unit": "km",
        "quantity": round(drop_total_km, 2),
        "unit_cost_brl": FTTH_COSTS["drop_cable_2core_per_km"],
        "total_cost_brl": round(drop_total_km * FTTH_COSTS["drop_cable_2core_per_km"], 2),
    })

    # -- Civil works --
    total_cable_km = trunk_km + distribution_km + drop_total_km
    civil_key = f"civil_{deployment_type}_per_km"
    civil_cost = FTTH_COSTS.get(civil_key, FTTH_COSTS["civil_aerial_per_km"])
    items.append({
        "category": "Obra civil",
        "item": f"Obra civil ({deployment_type})",
        "unit": "km",
        "quantity": round(total_cable_km, 2),
        "unit_cost_brl": civil_cost,
        "total_cost_brl": round(total_cable_km * civil_cost, 2),
    })

    # -- Accessories --
    splice_count = max(2, int(total_cable_km / 2) * 2)
    items.append({
        "category": "Acessórios",
        "item": "Caixa de emenda",
        "unit": "un",
        "quantity": splice_count,
        "unit_cost_brl": FTTH_COSTS["splice_closure_each"],
        "total_cost_brl": round(splice_count * FTTH_COSTS["splice_closure_each"], 2),
    })

    connector_count = subscribers * 2 + olt["pon_ports"] * 2
    items.append({
        "category": "Acessórios",
        "item": "Conector SC/APC",
        "unit": "un",
        "quantity": connector_count,
        "unit_cost_brl": FTTH_COSTS["connector_each"],
        "total_cost_brl": round(connector_count * FTTH_COSTS["connector_each"], 2),
    })

    # Calculate subtotals by category
    categories: dict[str, float] = {}
    for item in items:
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + item["total_cost_brl"]

    total = sum(item["total_cost_brl"] for item in items)

    return {
        "items": items,
        "subtotals": {k: round(v, 2) for k, v in categories.items()},
        "total_cost_brl": round(total, 2),
    }
