"""
ENLACE Investment Priority Service

Composite investment scoring using opportunity_scores, economic_indicators,
competitive_analysis, and broadband_subscribers. Plus anomaly detection
on quality_indicators time-series using pyod (IForest) with z-score fallback.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def investment_priority_ranking(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Composite investment priority score combining:
    - opportunity_scores.composite_score (30%)
    - population (20%)
    - GDP per capita (15%)
    - coverage gap severity (25%)
    - subscriber growth trend (10%)
    """
    where_parts = ["os2.composite_score IS NOT NULL"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH latest_ym AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        prev_ym AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
            WHERE year_month < (SELECT ym FROM latest_ym)
        ),
        current_subs AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers, latest_ym
            WHERE year_month = latest_ym.ym
            GROUP BY l2_id
        ),
        prev_subs AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers, prev_ym
            WHERE year_month = prev_ym.ym
            GROUP BY l2_id
        ),
        broadband_pen AS (
            SELECT l2_id,
                   SUM(subs) AS total_subs
            FROM current_subs
            GROUP BY l2_id
        ),
        stats AS (
            SELECT
                MAX(a2.population) AS max_pop,
                MAX(ei.pib_per_capita_brl) AS max_gdp,
                MAX(CASE WHEN a2.population > 0 THEN bp.total_subs::float / a2.population ELSE 0 END) AS max_pen
            FROM admin_level_2 a2
            LEFT JOIN economic_indicators ei ON ei.l2_id = a2.id
            LEFT JOIN broadband_pen bp ON bp.l2_id = a2.id
        )
        SELECT
            a2.id AS l2_id,
            a2.name AS municipality,
            a1.abbrev AS state,
            a2.population,
            os2.composite_score,
            os2.demand_score,
            os2.competition_score,
            ei.pib_per_capita_brl,
            ei.pib_municipal_brl,
            COALESCE(cs.subs, 0) AS current_subs,
            CASE WHEN COALESCE(ps.subs, 0) > 0
                 THEN ROUND(((COALESCE(cs.subs, 0) - ps.subs)::numeric / ps.subs * 100)::numeric, 2)
                 ELSE 0 END AS growth_pct,
            CASE WHEN a2.population > 0
                 THEN ROUND((COALESCE(bp.total_subs, 0)::numeric / a2.population * 100)::numeric, 2)
                 ELSE 0 END AS penetration_pct,
            -- Normalized sub-scores (0-100)
            ROUND((os2.composite_score)::numeric, 2) AS opp_score,
            CASE WHEN st.max_pop > 0 THEN ROUND((a2.population::numeric / st.max_pop * 100)::numeric, 2) ELSE 0 END AS pop_score,
            CASE WHEN st.max_gdp > 0 THEN ROUND((COALESCE(ei.pib_per_capita_brl, 0)::numeric / st.max_gdp * 100)::numeric, 2) ELSE 0 END AS gdp_score,
            CASE WHEN st.max_pen > 0 THEN ROUND(((1 - LEAST(COALESCE(bp.total_subs::numeric / NULLIF(a2.population, 0), 0) / st.max_pen, 1)) * 100)::numeric, 2) ELSE 100 END AS gap_score
        FROM opportunity_scores os2
        JOIN admin_level_2 a2 ON a2.code = os2.geographic_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        LEFT JOIN economic_indicators ei ON ei.l2_id = a2.id
        LEFT JOIN current_subs cs ON cs.l2_id = a2.id
        LEFT JOIN prev_subs ps ON ps.l2_id = a2.id
        LEFT JOIN broadband_pen bp ON bp.l2_id = a2.id
        CROSS JOIN stats st
        WHERE {where_sql}
        ORDER BY os2.composite_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    rankings = []
    for i, row in enumerate(rows, 1):
        opp = float(row.opp_score)
        pop = float(row.pop_score)
        gdp = float(row.gdp_score)
        gap = float(row.gap_score)
        growth = min(max(float(row.growth_pct), -50), 100)
        growth_norm = (growth + 50) / 150 * 100  # Normalize -50..100 to 0..100

        composite = round(opp * 0.30 + pop * 0.20 + gdp * 0.15 + gap * 0.25 + growth_norm * 0.10, 2)

        rankings.append({
            "rank": i,
            "l2_id": row.l2_id,
            "municipality": row.municipality,
            "state": row.state,
            "composite_score": composite,
            "sub_scores": {
                "opportunity": round(opp, 1),
                "population": round(pop, 1),
                "gdp": round(gdp, 1),
                "coverage_gap": round(gap, 1),
                "growth_trend": round(growth_norm, 1),
            },
            "population": row.population,
            "pib_per_capita_brl": float(row.pib_per_capita_brl) if row.pib_per_capita_brl else None,
            "current_subscribers": row.current_subs,
            "growth_pct": float(row.growth_pct),
            "penetration_pct": float(row.penetration_pct),
        })

    # Re-sort by composite
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(rankings, 1):
        r["rank"] = i

    return {
        "total_ranked": len(rankings),
        "weights": {
            "opportunity": 0.30,
            "population": 0.20,
            "gdp": 0.15,
            "coverage_gap": 0.25,
            "growth_trend": 0.10,
        },
        "rankings": rankings,
    }


async def anomaly_detection(
    db: AsyncSession,
    state: Optional[str] = None,
    lookback_months: int = 6,
    limit: int = 50,
) -> dict[str, Any]:
    """Detect quality anomalies using pyod IForest (fallback: z-score)."""
    where_parts = ["qi.year_month >= TO_CHAR(NOW() - make_interval(months => :lookback), 'YYYY-MM')"]
    params: dict[str, Any] = {"lookback": lookback_months, "limit": limit}

    if state:
        where_parts.append("""
            qi.l2_id IN (
                SELECT a2.id FROM admin_level_2 a2
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT
            qi.l2_id,
            a2.name AS municipality,
            a1.abbrev AS state,
            qi.metric_type,
            qi.year_month,
            qi.value
        FROM quality_indicators qi
        JOIN admin_level_2 a2 ON a2.id = qi.l2_id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE {where_sql}
        ORDER BY qi.l2_id, qi.metric_type, qi.year_month
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return {"total_anomalies": 0, "method": "none", "anomalies": []}

    import numpy as np

    # Group by (l2_id, metric_type)
    groups: dict[tuple, list] = {}
    row_map: dict[tuple, list] = {}
    for row in rows:
        key = (row.l2_id, row.metric_type)
        if key not in groups:
            groups[key] = []
            row_map[key] = []
        if row.value is not None:
            groups[key].append(float(row.value))
            row_map[key].append(row)

    anomalies = []
    method = "zscore"

    # Try pyod first
    try:
        from pyod.models.iforest import IForest
        method = "iforest"

        for key, values in groups.items():
            if len(values) < 4:
                continue
            arr = np.array(values).reshape(-1, 1)
            clf = IForest(contamination=0.1, random_state=42, n_estimators=50)
            clf.fit(arr)
            labels = clf.labels_  # 0=normal, 1=anomaly
            scores = clf.decision_scores_

            for i, label in enumerate(labels):
                if label == 1:
                    r = row_map[key][i]
                    anomalies.append({
                        "l2_id": r.l2_id,
                        "municipality": r.municipality,
                        "state": r.state,
                        "metric_type": r.metric_type,
                        "year_month": r.year_month,
                        "value": float(r.value),
                        "anomaly_score": round(float(scores[i]), 3),
                        "severity": "high" if scores[i] > 0.5 else "medium",
                    })
    except (ImportError, Exception) as e:
        logger.warning("pyod unavailable or failed (%s), using z-score fallback", e)
        method = "zscore"

        for key, values in groups.items():
            if len(values) < 4:
                continue
            mean = np.mean(values)
            std = np.std(values)
            if std == 0:
                continue

            for i, val in enumerate(values):
                z = abs(val - mean) / std
                if z > 2.0:
                    r = row_map[key][i]
                    anomalies.append({
                        "l2_id": r.l2_id,
                        "municipality": r.municipality,
                        "state": r.state,
                        "metric_type": r.metric_type,
                        "year_month": r.year_month,
                        "value": float(r.value),
                        "anomaly_score": round(float(z), 3),
                        "severity": "high" if z > 3.0 else "medium",
                    })

    # Sort by severity then score
    anomalies.sort(key=lambda x: (-1 if x["severity"] == "high" else 0, -x["anomaly_score"]))

    return {
        "total_anomalies": len(anomalies),
        "method": method,
        "lookback_months": lookback_months,
        "anomalies": anomalies[:limit],
    }
