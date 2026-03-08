"""Competitive analysis functions for broadband market intelligence.

Provides HHI computation, threat detection, and competitive landscape
analysis for municipalities.
"""

import logging
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)


def compute_hhi(subscribers_by_provider: dict[int, int]) -> float:
    """Compute Herfindahl-Hirschman Index for market concentration.

    The HHI ranges from near 0 (perfect competition) to 10,000 (monopoly).
    U.S. DOJ guidelines:
        - < 1500: unconcentrated
        - 1500-2500: moderately concentrated
        - > 2500: highly concentrated

    Args:
        subscribers_by_provider: Mapping of provider_id to subscriber count.

    Returns:
        HHI value in range [0, 10000].
    """
    total = sum(subscribers_by_provider.values())
    if total == 0:
        return 0.0
    shares = [(s / total) ** 2 for s in subscribers_by_provider.values()]
    return sum(shares) * 10000


def get_market_concentration(municipality_id: int, conn=None) -> dict:
    """Get market concentration metrics for a municipality.

    Args:
        municipality_id: admin_level_2.id
        conn: Optional database connection.

    Returns:
        Dictionary with hhi_index, provider_count, leader_share, and details.
    """
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider_id, SUM(subscribers) AS total_subs
                FROM broadband_subscribers
                WHERE l2_id = %s
                  AND year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
                GROUP BY provider_id
                ORDER BY total_subs DESC
                """,
                (municipality_id,),
            )
            rows = cur.fetchall()

        if not rows:
            return {
                "hhi_index": 0.0,
                "provider_count": 0,
                "leader_share": 0.0,
                "leader_provider_id": None,
                "subscribers_by_provider": {},
            }

        subs_by_provider = {row[0]: row[1] for row in rows}
        total = sum(subs_by_provider.values())
        leader_id, leader_subs = rows[0]

        return {
            "hhi_index": compute_hhi(subs_by_provider),
            "provider_count": len(subs_by_provider),
            "leader_share": leader_subs / total if total > 0 else 0.0,
            "leader_provider_id": leader_id,
            "subscribers_by_provider": subs_by_provider,
        }
    finally:
        if own_conn:
            conn.close()


def detect_threats(municipality_id: int, conn=None) -> list[dict]:
    """Detect competitive threats for a municipality.

    Checks for:
    1. New entrants: providers appearing in the latest months that were absent before.
    2. Competitor growth spikes: providers growing > 10% in the last 3 months.
    3. Technology shifts: new fiber entrants in previously cable/DSL-only markets.

    Args:
        municipality_id: admin_level_2.id
        conn: Optional database connection.

    Returns:
        List of threat dictionaries with type, severity, and description.
    """
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(**DB_CONFIG)

    threats = []

    try:
        with conn.cursor() as cur:
            # 1. Check for new entrants (provider present in last 3 months
            #    but absent in the 3 months before that)
            cur.execute(
                """
                WITH months AS (
                    SELECT DISTINCT year_month
                    FROM broadband_subscribers
                    ORDER BY year_month DESC
                ),
                recent AS (
                    SELECT year_month FROM months LIMIT 3
                ),
                older AS (
                    SELECT year_month FROM months OFFSET 3 LIMIT 3
                ),
                recent_providers AS (
                    SELECT DISTINCT provider_id
                    FROM broadband_subscribers bs
                    JOIN recent r ON bs.year_month = r.year_month
                    WHERE bs.l2_id = %s
                ),
                older_providers AS (
                    SELECT DISTINCT provider_id
                    FROM broadband_subscribers bs
                    JOIN older o ON bs.year_month = o.year_month
                    WHERE bs.l2_id = %s
                )
                SELECT rp.provider_id, p.name
                FROM recent_providers rp
                LEFT JOIN older_providers op ON op.provider_id = rp.provider_id
                JOIN providers p ON p.id = rp.provider_id
                WHERE op.provider_id IS NULL
                """,
                (municipality_id, municipality_id),
            )
            new_entrants = cur.fetchall()
            for provider_id, provider_name in new_entrants:
                threats.append(
                    {
                        "type": "new_entrant",
                        "severity": "high",
                        "provider_id": provider_id,
                        "provider_name": provider_name,
                        "description": (
                            f"New provider '{provider_name}' entered the market"
                        ),
                    }
                )

            # 2. Check for competitor growth spikes (> 10% growth in 3 months)
            cur.execute(
                """
                WITH months AS (
                    SELECT DISTINCT year_month
                    FROM broadband_subscribers
                    ORDER BY year_month DESC
                ),
                latest_ym AS (SELECT year_month FROM months LIMIT 1),
                three_ago AS (SELECT year_month FROM months OFFSET 3 LIMIT 1),
                latest_subs AS (
                    SELECT provider_id, SUM(subscribers) AS subs
                    FROM broadband_subscribers bs, latest_ym ly
                    WHERE bs.year_month = ly.year_month AND bs.l2_id = %s
                    GROUP BY provider_id
                ),
                older_subs AS (
                    SELECT provider_id, SUM(subscribers) AS subs
                    FROM broadband_subscribers bs, three_ago ta
                    WHERE bs.year_month = ta.year_month AND bs.l2_id = %s
                    GROUP BY provider_id
                )
                SELECT
                    ls.provider_id,
                    p.name,
                    ls.subs AS current_subs,
                    os.subs AS older_subs,
                    (ls.subs - os.subs)::float / NULLIF(os.subs, 0) AS growth_rate
                FROM latest_subs ls
                JOIN older_subs os ON os.provider_id = ls.provider_id
                JOIN providers p ON p.id = ls.provider_id
                WHERE os.subs > 0
                  AND (ls.subs - os.subs)::float / os.subs > 0.10
                """,
                (municipality_id, municipality_id),
            )
            spikes = cur.fetchall()
            for provider_id, name, curr, older, rate in spikes:
                threats.append(
                    {
                        "type": "growth_spike",
                        "severity": "medium",
                        "provider_id": provider_id,
                        "provider_name": name,
                        "growth_rate": round(rate, 4),
                        "description": (
                            f"Provider '{name}' grew {rate:.1%} in 3 months"
                        ),
                    }
                )

            # 3. Technology shifts: new fiber presence where previously absent
            cur.execute(
                """
                WITH months AS (
                    SELECT DISTINCT year_month
                    FROM broadband_subscribers
                    ORDER BY year_month DESC
                ),
                latest_ym AS (SELECT year_month FROM months LIMIT 1),
                six_ago AS (SELECT year_month FROM months OFFSET 6 LIMIT 1),
                has_fiber_now AS (
                    SELECT BOOL_OR(technology = 'fiber') AS has_fiber
                    FROM broadband_subscribers bs, latest_ym ly
                    WHERE bs.year_month = ly.year_month AND bs.l2_id = %s
                ),
                had_fiber_before AS (
                    SELECT BOOL_OR(technology = 'fiber') AS had_fiber
                    FROM broadband_subscribers bs, six_ago sa
                    WHERE bs.year_month = sa.year_month AND bs.l2_id = %s
                )
                SELECT fn.has_fiber, fb.had_fiber
                FROM has_fiber_now fn, had_fiber_before fb
                """,
                (municipality_id, municipality_id),
            )
            row = cur.fetchone()
            if row and row[0] and not row[1]:
                threats.append(
                    {
                        "type": "technology_shift",
                        "severity": "high",
                        "description": "Fiber deployment detected where previously absent",
                    }
                )

    finally:
        if own_conn:
            conn.close()

    return threats


def compute_competitive_score(municipality_id: int, conn=None) -> float:
    """Compute a competition opportunity score (0-100).

    Higher score means less competition (more opportunity).
    Factors: HHI (inverted), provider count (fewer = more opportunity),
    absence of fiber (technology gap).

    Args:
        municipality_id: admin_level_2.id
        conn: Optional database connection.

    Returns:
        Score from 0 (hyper-competitive) to 100 (no competition).
    """
    market = get_market_concentration(municipality_id, conn)

    if market["provider_count"] == 0:
        # No providers at all — maximum opportunity
        return 95.0

    # Invert HHI: low HHI (competitive) = low score, high HHI (concentrated) = mixed
    # A monopoly (HHI=10000) is bad for entry, moderate concentration is best
    hhi = market["hhi_index"]
    if hhi > 5000:
        hhi_score = max(0, 100 - (hhi - 5000) / 50)  # Monopoly is hard to enter
    else:
        hhi_score = max(0, 100 - hhi / 50)  # Low concentration = competitive

    # Fewer providers = more room
    provider_score = max(0, 100 - market["provider_count"] * 15)

    # Leader dominance: very high share = vulnerable to disruption
    leader_score = min(100, market["leader_share"] * 120)

    return (hhi_score * 0.4 + provider_score * 0.3 + leader_score * 0.3)
