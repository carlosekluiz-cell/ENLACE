"""
ENLACE Backhaul Utilization Model Service

Models backhaul utilization from subscriber_timeseries and opencellid_towers,
with forecasting via numpy polyfit (pattern from forecasting.py).
"""

import logging
import math
from typing import Any, Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Backhaul capacity assumptions
CAPACITY_PER_TOWER_GBPS = {
    "NR": 10.0,     # 5G
    "LTE": 1.0,     # 4G
    "UMTS": 0.384,  # 3G
    "GSM": 0.05,    # 2G
}
DEFAULT_CAPACITY_GBPS = 1.0

# Traffic per subscriber (Mbps average during busy hour)
TRAFFIC_PER_SUB_MBPS = 2.5


async def get_utilization(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Compute backhaul utilization estimates per municipality."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("a1.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        WITH latest_ym AS (SELECT MAX(year_month) AS ym FROM broadband_subscribers),
        muni_data AS (
            SELECT
                a2.id AS l2_id, a2.name, a1.abbrev AS state,
                a2.population,
                COALESCE(SUM(bs.subscribers), 0) AS subscribers,
                (SELECT COUNT(*) FROM base_stations bst
                 JOIN admin_level_2 a22 ON ST_Contains(a22.geom, bst.geom)
                 WHERE a22.id = a2.id) AS tower_count
            FROM admin_level_2 a2
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            LEFT JOIN broadband_subscribers bs ON bs.l2_id = a2.id
                AND bs.year_month = (SELECT ym FROM latest_ym)
            WHERE {where_sql}
            GROUP BY a2.id, a2.name, a1.abbrev, a2.population
            HAVING COALESCE(SUM(bs.subscribers), 0) > 0
        )
        SELECT * FROM muni_data
        ORDER BY subscribers DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    municipalities = []
    for row in rows:
        subs = row.subscribers
        towers = row.tower_count or 1
        total_capacity_gbps = towers * DEFAULT_CAPACITY_GBPS
        demand_gbps = subs * TRAFFIC_PER_SUB_MBPS / 1000
        utilization_pct = min(100, demand_gbps / max(total_capacity_gbps, 0.001) * 100)

        risk = "critical" if utilization_pct > 85 else "warning" if utilization_pct > 70 else "ok"

        municipalities.append({
            "l2_id": row.l2_id,
            "name": row.name,
            "state": row.state,
            "subscribers": subs,
            "tower_count": towers,
            "estimated_capacity_gbps": round(total_capacity_gbps, 2),
            "estimated_demand_gbps": round(demand_gbps, 3),
            "utilization_pct": round(utilization_pct, 1),
            "risk_level": risk,
        })

    municipalities.sort(key=lambda x: x["utilization_pct"], reverse=True)

    return {
        "state_filter": state,
        "total": len(municipalities),
        "critical_count": sum(1 for m in municipalities if m["risk_level"] == "critical"),
        "warning_count": sum(1 for m in municipalities if m["risk_level"] == "warning"),
        "municipalities": municipalities,
    }


async def forecast_utilization(
    db: AsyncSession,
    l2_id: int,
    months_ahead: int = 12,
) -> dict[str, Any]:
    """Forecast backhaul utilization using subscriber growth trends."""
    sql = text("""
        SELECT year_month, SUM(subscribers) AS total
        FROM broadband_subscribers
        WHERE l2_id = :l2_id
        GROUP BY year_month
        ORDER BY year_month ASC
    """)
    result = await db.execute(sql, {"l2_id": l2_id})
    rows = result.fetchall()

    if len(rows) < 3:
        return {"l2_id": l2_id, "status": "insufficient_data", "data_points": len(rows)}

    months = [r.year_month.strip() for r in rows]
    totals = [int(r.total) for r in rows]

    # Tower count
    tower_sql = text("""
        SELECT COUNT(*) AS cnt FROM base_stations bs
        JOIN admin_level_2 a2 ON ST_Contains(a2.geom, bs.geom)
        WHERE a2.id = :l2_id
    """)
    tower_row = (await db.execute(tower_sql, {"l2_id": l2_id})).fetchone()
    tower_count = tower_row.cnt if tower_row else 1
    capacity_gbps = max(tower_count, 1) * DEFAULT_CAPACITY_GBPS

    n = len(totals)
    x = np.arange(n, dtype=np.float64)
    y = np.array(totals, dtype=np.float64)

    coeffs = np.polyfit(x, y, 1)
    residuals = y - np.polyval(coeffs, x)
    std = float(np.std(residuals))

    historical = []
    for i in range(n):
        demand = totals[i] * TRAFFIC_PER_SUB_MBPS / 1000
        util = min(100, demand / max(capacity_gbps, 0.001) * 100)
        historical.append({
            "year_month": months[i],
            "subscribers": totals[i],
            "demand_gbps": round(demand, 3),
            "utilization_pct": round(util, 1),
        })

    forecast = []
    last_ym = months[-1]
    for i in range(1, months_ahead + 1):
        future_x = float(n - 1 + i)
        predicted_subs = max(0, float(np.polyval(coeffs, future_x)))
        demand = predicted_subs * TRAFFIC_PER_SUB_MBPS / 1000
        util = min(100, demand / max(capacity_gbps, 0.001) * 100)

        parts = last_ym.split("-")
        total_m = int(parts[0]) * 12 + int(parts[1]) - 1 + i
        ym = f"{total_m // 12:04d}-{total_m % 12 + 1:02d}"

        forecast.append({
            "year_month": ym,
            "predicted_subscribers": round(predicted_subs),
            "demand_gbps": round(demand, 3),
            "utilization_pct": round(util, 1),
            "congestion_risk": util > 85,
        })

    congestion_month = None
    for f in forecast:
        if f["utilization_pct"] > 85:
            congestion_month = f["year_month"]
            break

    return {
        "l2_id": l2_id,
        "tower_count": tower_count,
        "capacity_gbps": round(capacity_gbps, 2),
        "current_utilization_pct": historical[-1]["utilization_pct"] if historical else 0,
        "historical": historical,
        "forecast": forecast,
        "congestion_month": congestion_month,
        "growth_per_month": round(float(coeffs[0]), 1),
    }


async def congestion_risk(
    db: AsyncSession,
    months_horizon: int = 12,
    state: Optional[str] = None,
) -> dict[str, Any]:
    """Find municipalities at risk of backhaul congestion."""
    util_data = await get_utilization(db, state=state, limit=200)
    at_risk = [m for m in util_data["municipalities"] if m["utilization_pct"] > 60]

    return {
        "horizon_months": months_horizon,
        "state_filter": state,
        "at_risk_count": len(at_risk),
        "municipalities": at_risk[:50],
    }
