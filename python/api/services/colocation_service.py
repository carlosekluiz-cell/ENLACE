"""
ENLACE Tower Co-Location Analysis Service

Computes co-location opportunity scores for base stations by analyzing
nearby towers, operator diversity, underserved population, coverage gaps,
and spectrum complementarity.  Results are stored in the
``tower_colocation_analysis`` table for efficient querying.

Scoring formula (0-100):
    colocation_score = 0.4 * underserved_pop_normalized
                     + 0.3 * competitor_density_score
                     + 0.2 * gap_coverage_score
                     + 0.1 * spectrum_complement_score

Savings estimate: R$ 150K-300K per shared tower (avoided duplicate CAPEX),
scaled by the number of nearby towers and provider diversity.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────────────────────────────
# Scoring weights
# ───────────────────────────────────────────────────────────────────────
WEIGHT_UNDERSERVED = 0.4
WEIGHT_DENSITY = 0.3
WEIGHT_GAP = 0.2
WEIGHT_SPECTRUM = 0.1

# Savings range per shared tower (BRL)
SAVINGS_MIN_BRL = 150_000.0
SAVINGS_MAX_BRL = 300_000.0

# Spatial thresholds
NEARBY_RADIUS_M = 500          # co-location candidate radius
UNDERSERVED_RADIUS_M = 5_000   # population catchment radius

# Normalization cap for underserved population
# Municipalities with >= this population within 5 km and low penetration
# receive a full 100 score on the underserved dimension.
UNDERSERVED_POP_CAP = 50_000


# ═══════════════════════════════════════════════════════════════════════
# Single tower analysis
# ═══════════════════════════════════════════════════════════════════════


async def compute_colocation(
    db: AsyncSession,
    base_station_id: int,
) -> Optional[dict[str, Any]]:
    """Compute co-location analysis for a single base station.

    Finds nearby towers within 500 m, evaluates provider diversity,
    estimates underserved population within 5 km, computes coverage gap
    and spectrum complement scores, and persists the result.

    Returns the analysis dict or ``None`` if the base station is not found.
    """
    # ── 1. Fetch target tower ────────────────────────────────────────
    bs_sql = text("""
        SELECT
            bs.id,
            bs.latitude,
            bs.longitude,
            bs.geom,
            bs.technology,
            bs.frequency_mhz,
            bs.provider_id,
            p.name AS provider_name
        FROM base_stations bs
        LEFT JOIN providers p ON p.id = bs.provider_id
        WHERE bs.id = :bs_id
    """)
    row = (await db.execute(bs_sql, {"bs_id": base_station_id})).fetchone()
    if row is None:
        return None

    provider_name = row.provider_name or "Unknown"

    # ── 2. Find municipality via spatial containment ─────────────────
    l2_sql = text("""
        SELECT a2.id AS l2_id, a2.name, a2.population,
               a1.abbrev AS state_abbrev
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE ST_Contains(a2.geom, (
            SELECT geom FROM base_stations WHERE id = :bs_id
        ))
        LIMIT 1
    """)
    l2_row = (await db.execute(l2_sql, {"bs_id": base_station_id})).fetchone()
    l2_id = l2_row.l2_id if l2_row else None

    # ── 3. Nearby towers within 500 m ────────────────────────────────
    nearby_sql = text("""
        SELECT
            nb.id,
            nb.technology,
            nb.frequency_mhz,
            nb.provider_id,
            p.name AS provider_name,
            ST_Distance(nb.geom::geography, src.geom::geography) AS distance_m
        FROM base_stations nb
        CROSS JOIN (SELECT geom FROM base_stations WHERE id = :bs_id) src
        LEFT JOIN providers p ON p.id = nb.provider_id
        WHERE nb.id != :bs_id
          AND ST_DWithin(nb.geom::geography, src.geom::geography, :radius_m)
        ORDER BY distance_m
    """)
    nearby_rows = (
        await db.execute(
            nearby_sql,
            {"bs_id": base_station_id, "radius_m": NEARBY_RADIUS_M},
        )
    ).fetchall()

    nearby_count = len(nearby_rows)

    # Build provider breakdown for nearby towers
    provider_set: dict[str, dict[str, Any]] = {}
    nearby_technologies: set[str] = set()
    nearby_frequencies: set[float] = set()

    for nr in nearby_rows:
        pname = nr.provider_name or "Unknown"
        nearby_technologies.add(nr.technology)
        if nr.frequency_mhz and nr.frequency_mhz > 0:
            nearby_frequencies.add(nr.frequency_mhz)
        if pname not in provider_set:
            provider_set[pname] = {
                "provider_name": pname,
                "tower_count": 0,
                "technologies": [],
            }
        provider_set[pname]["tower_count"] += 1
        if nr.technology not in provider_set[pname]["technologies"]:
            provider_set[pname]["technologies"].append(nr.technology)

    nearby_providers_json = list(provider_set.values())
    distinct_providers = len(provider_set)

    # ── 4. Underserved population within 5 km ────────────────────────
    # Sum population of municipalities whose centroid is within 5 km,
    # then discount by broadband penetration to estimate underserved.
    underserved_sql = text("""
        SELECT
            COALESCE(SUM(a2.population), 0) AS total_pop,
            COALESCE(SUM(
                GREATEST(0, a2.population - COALESCE(sub.total_subs, 0))
            ), 0) AS underserved_pop
        FROM admin_level_2 a2
        CROSS JOIN (SELECT geom FROM base_stations WHERE id = :bs_id) src
        LEFT JOIN LATERAL (
            SELECT SUM(bs2.subscribers) AS total_subs
            FROM broadband_subscribers bs2
            WHERE bs2.l2_id = a2.id
              AND bs2.year_month = (
                  SELECT MAX(year_month) FROM broadband_subscribers
              )
        ) sub ON true
        WHERE ST_DWithin(a2.centroid::geography, src.geom::geography, :radius_m)
          AND a2.centroid IS NOT NULL
    """)
    us_row = (
        await db.execute(
            underserved_sql,
            {"bs_id": base_station_id, "radius_m": UNDERSERVED_RADIUS_M},
        )
    ).fetchone()

    underserved_pop = int(us_row.underserved_pop) if us_row else 0

    # ── 5. Compute sub-scores (all 0-100) ────────────────────────────

    # 5a. Underserved population score
    underserved_normalized = min(underserved_pop / UNDERSERVED_POP_CAP, 1.0) * 100

    # 5b. Competitor density score — more distinct nearby providers = higher
    # sharing opportunity.  Capped at 5 providers for a full 100.
    competitor_density = min(distinct_providers / 5.0, 1.0) * 100

    # 5c. Coverage gap score — fewer nearby towers means bigger gap.
    # A lone tower (0 neighbours) gets 100; 10+ neighbours gets ~0.
    if nearby_count == 0:
        gap_coverage = 100.0
    else:
        gap_coverage = max(0.0, (1.0 - nearby_count / 10.0)) * 100

    # 5d. Spectrum complement — how many distinct frequency bands exist
    # across the tower and its neighbours.  More bands = better complement.
    own_freq = {row.frequency_mhz} if row.frequency_mhz and row.frequency_mhz > 0 else set()
    all_frequencies = own_freq | nearby_frequencies
    # Normalize: 4+ distinct bands = 100
    spectrum_complement = min(len(all_frequencies) / 4.0, 1.0) * 100

    # ── 6. Composite score ───────────────────────────────────────────
    colocation_score = (
        WEIGHT_UNDERSERVED * underserved_normalized
        + WEIGHT_DENSITY * competitor_density
        + WEIGHT_GAP * gap_coverage
        + WEIGHT_SPECTRUM * spectrum_complement
    )
    colocation_score = round(min(colocation_score, 100.0), 2)

    # ── 7. Estimated savings ─────────────────────────────────────────
    # Scale between SAVINGS_MIN and SAVINGS_MAX based on nearby tower count
    # and provider diversity.  More towers and providers = more sharing = more savings.
    sharing_factor = min((nearby_count * 0.3 + distinct_providers * 0.4), 1.0)
    estimated_savings = SAVINGS_MIN_BRL + sharing_factor * (SAVINGS_MAX_BRL - SAVINGS_MIN_BRL)
    estimated_savings = round(estimated_savings, 2)

    # ── 8. Persist into tower_colocation_analysis ──────────────────────
    # Delete any previous analysis for this tower, then insert fresh.
    await db.execute(
        text("DELETE FROM tower_colocation_analysis WHERE base_station_id = :bs_id"),
        {"bs_id": base_station_id},
    )

    insert_sql = text("""
        INSERT INTO tower_colocation_analysis (
            base_station_id, l2_id, provider_name,
            nearby_towers_500m, nearby_providers,
            underserved_pop_5km,
            competitor_density_score, gap_coverage_score,
            spectrum_complement_score, colocation_score,
            estimated_savings_brl, computed_at
        ) VALUES (
            :bs_id, :l2_id, :provider_name,
            :nearby_count, CAST(:nearby_providers AS jsonb),
            :underserved_pop,
            :competitor_density, :gap_coverage,
            :spectrum_complement, :colocation_score,
            :estimated_savings, :computed_at
        )
    """)

    computed_at = datetime.now(timezone.utc)
    await db.execute(
        insert_sql,
        {
            "bs_id": base_station_id,
            "l2_id": l2_id,
            "provider_name": provider_name,
            "nearby_count": nearby_count,
            "nearby_providers": json.dumps(nearby_providers_json),
            "underserved_pop": underserved_pop,
            "competitor_density": round(competitor_density, 2),
            "gap_coverage": round(gap_coverage, 2),
            "spectrum_complement": round(spectrum_complement, 2),
            "colocation_score": colocation_score,
            "estimated_savings": estimated_savings,
            "computed_at": computed_at,
        },
    )

    return {
        "base_station_id": base_station_id,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "technology": row.technology,
        "frequency_mhz": row.frequency_mhz,
        "provider_name": provider_name,
        "municipality_id": l2_id,
        "municipality_name": l2_row.name if l2_row else None,
        "state_abbrev": l2_row.state_abbrev if l2_row else None,
        "nearby_towers_500m": nearby_count,
        "nearby_providers": nearby_providers_json,
        "underserved_pop_5km": underserved_pop,
        "competitor_density_score": round(competitor_density, 2),
        "gap_coverage_score": round(gap_coverage, 2),
        "spectrum_complement_score": round(spectrum_complement, 2),
        "colocation_score": colocation_score,
        "estimated_savings_brl": estimated_savings,
        "computed_at": computed_at.isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════
# Municipality batch computation
# ═══════════════════════════════════════════════════════════════════════


async def compute_municipality_colocation(
    db: AsyncSession,
    municipality_id: int,
) -> dict[str, Any]:
    """Batch-compute co-location analysis for all towers in a municipality.

    Finds base stations whose geometry falls inside the municipality polygon,
    then computes co-location analysis for each one.

    Returns a summary dict with total towers processed, average score, and
    total estimated savings.
    """
    # Verify municipality exists
    muni_sql = text("""
        SELECT a2.id, a2.name, a1.abbrev AS state_abbrev
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE a2.id = :l2_id
    """)
    muni_row = (await db.execute(muni_sql, {"l2_id": municipality_id})).fetchone()
    if muni_row is None:
        return {"error": "municipality_not_found"}

    # Find all base stations in municipality via spatial containment
    towers_sql = text("""
        SELECT bs.id
        FROM base_stations bs
        JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
        WHERE a2.id = :l2_id
        ORDER BY bs.id
    """)
    tower_rows = (await db.execute(towers_sql, {"l2_id": municipality_id})).fetchall()

    if not tower_rows:
        return {
            "municipality_id": municipality_id,
            "municipality_name": muni_row.name,
            "state_abbrev": muni_row.state_abbrev,
            "towers_processed": 0,
            "avg_colocation_score": 0,
            "total_estimated_savings_brl": 0,
            "message": "No base stations found in this municipality",
        }

    total_score = 0.0
    total_savings = 0.0
    processed = 0
    errors = 0

    for tr in tower_rows:
        try:
            result = await compute_colocation(db, tr.id)
            if result:
                total_score += result["colocation_score"]
                total_savings += result["estimated_savings_brl"]
                processed += 1
        except Exception:
            logger.exception("Error computing colocation for tower %d", tr.id)
            errors += 1

    avg_score = round(total_score / processed, 2) if processed > 0 else 0

    return {
        "municipality_id": municipality_id,
        "municipality_name": muni_row.name,
        "state_abbrev": muni_row.state_abbrev,
        "towers_processed": processed,
        "towers_errored": errors,
        "avg_colocation_score": avg_score,
        "total_estimated_savings_brl": round(total_savings, 2),
    }
