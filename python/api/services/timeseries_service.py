"""
ENLACE Time-Series Analytics Service

Provides subscriber time-series aggregation, growth metric computation,
and backfill logic for the subscriber_timeseries table.

All queries use raw SQL via SQLAlchemy text() — no ORM models.
Column references follow the real schema:
  - broadband_subscribers: l2_id, provider_id, technology, subscribers, year_month
  - subscriber_timeseries: l2_id, provider_id, year_month, subscribers,
    fiber_subscribers, mom_growth_pct, yoy_growth_pct, churn_estimate_pct,
    arpu_estimate_brl, computed_at
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> Optional[float]:
    """Convert Decimal or other numeric types to float."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


# ═══════════════════════════════════════════════════════════════════════════════
# Subscriber Time-Series Aggregation
# ═══════════════════════════════════════════════════════════════════════════════


async def get_subscriber_timeseries(
    db: AsyncSession,
    municipality_id: int,
    provider_id: Optional[int] = None,
    interval: str = "month",
) -> list[dict[str, Any]]:
    """Aggregate broadband_subscribers by time interval.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id (l2_id in broadband_subscribers).
        provider_id: Optional filter for a specific provider.
        interval: Aggregation interval — 'month' or 'quarter'.

    Returns:
        List of time-series data points ordered chronologically.
    """
    # Build the time bucket expression based on interval
    if interval == "quarter":
        # Convert year_month '2025-01' -> date, then truncate to quarter
        time_bucket = (
            "TO_CHAR(DATE_TRUNC('quarter', TO_DATE(bs.year_month, 'YYYY-MM')), 'YYYY-\"Q\"Q')"
        )
        order_expr = "DATE_TRUNC('quarter', TO_DATE(bs.year_month, 'YYYY-MM'))"
    else:
        # Default: monthly — just use year_month directly
        time_bucket = "TRIM(bs.year_month)"
        order_expr = "TRIM(bs.year_month)"

    where_clauses = ["bs.l2_id = :municipality_id"]
    params: dict[str, Any] = {"municipality_id": municipality_id}

    if provider_id is not None:
        where_clauses.append("bs.provider_id = :provider_id")
        params["provider_id"] = provider_id

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            {time_bucket} AS period,
            SUM(bs.subscribers) AS total_subscribers,
            SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END)
                AS fiber_subscribers,
            COUNT(DISTINCT bs.provider_id) AS provider_count,
            COUNT(DISTINCT bs.technology) AS technology_count
        FROM broadband_subscribers bs
        WHERE {where_sql}
        GROUP BY {time_bucket}, {order_expr}
        ORDER BY {order_expr} ASC
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "period": row.period.strip() if isinstance(row.period, str) else row.period,
            "total_subscribers": int(row.total_subscribers or 0),
            "fiber_subscribers": int(row.fiber_subscribers or 0),
            "provider_count": int(row.provider_count or 0),
            "technology_count": int(row.technology_count or 0),
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Growth Metrics (MoM, YoY, CAGR)
# ═══════════════════════════════════════════════════════════════════════════════


async def get_growth_metrics(
    db: AsyncSession,
    municipality_id: int,
) -> dict[str, Any]:
    """Compute MoM, YoY, and CAGR growth metrics for a municipality.

    Uses broadband_subscribers aggregated by month. Growth rates are
    computed from the most recent month compared to prior periods.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id.

    Returns:
        Dictionary with mom, yoy, cagr, and supporting data.
    """
    sql = text("""
        SELECT
            TRIM(bs.year_month) AS year_month,
            SUM(bs.subscribers) AS total_subscribers,
            SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END)
                AS fiber_subscribers
        FROM broadband_subscribers bs
        WHERE bs.l2_id = :municipality_id
        GROUP BY TRIM(bs.year_month)
        ORDER BY TRIM(bs.year_month) ASC
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    rows = result.fetchall()

    if not rows:
        return {
            "municipality_id": municipality_id,
            "data_points": 0,
            "mom_growth_pct": None,
            "yoy_growth_pct": None,
            "cagr_pct": None,
            "fiber_mom_growth_pct": None,
            "fiber_yoy_growth_pct": None,
            "latest_month": None,
            "earliest_month": None,
            "latest_subscribers": None,
        }

    # Build ordered lists
    months = [r.year_month.strip() if isinstance(r.year_month, str) else r.year_month for r in rows]
    totals = [int(r.total_subscribers or 0) for r in rows]
    fibers = [int(r.fiber_subscribers or 0) for r in rows]

    latest_total = totals[-1]
    latest_fiber = fibers[-1]

    # MoM: compare last month with the one before it
    mom_growth = None
    if len(totals) >= 2 and totals[-2] > 0:
        mom_growth = round(((totals[-1] - totals[-2]) / totals[-2]) * 100, 2)

    fiber_mom_growth = None
    if len(fibers) >= 2 and fibers[-2] > 0:
        fiber_mom_growth = round(((fibers[-1] - fibers[-2]) / fibers[-2]) * 100, 2)

    # YoY: compare last month with 12 months ago
    yoy_growth = None
    fiber_yoy_growth = None
    if len(totals) >= 13:
        if totals[-13] > 0:
            yoy_growth = round(((totals[-1] - totals[-13]) / totals[-13]) * 100, 2)
        if fibers[-13] > 0:
            fiber_yoy_growth = round(((fibers[-1] - fibers[-13]) / fibers[-13]) * 100, 2)

    # CAGR: compound annual growth rate over the full time span
    cagr = None
    n_months = len(totals)
    if n_months >= 2 and totals[0] > 0 and totals[-1] > 0:
        years = n_months / 12.0
        if years > 0:
            cagr = round(((totals[-1] / totals[0]) ** (1.0 / years) - 1) * 100, 2)

    # 3-month and 6-month growth
    growth_3m = None
    if len(totals) >= 4 and totals[-4] > 0:
        growth_3m = round(((totals[-1] - totals[-4]) / totals[-4]) * 100, 2)

    growth_6m = None
    if len(totals) >= 7 and totals[-7] > 0:
        growth_6m = round(((totals[-1] - totals[-7]) / totals[-7]) * 100, 2)

    return {
        "municipality_id": municipality_id,
        "data_points": n_months,
        "latest_month": months[-1],
        "earliest_month": months[0],
        "latest_subscribers": latest_total,
        "latest_fiber_subscribers": latest_fiber,
        "mom_growth_pct": mom_growth,
        "yoy_growth_pct": yoy_growth,
        "cagr_pct": cagr,
        "growth_3m_pct": growth_3m,
        "growth_6m_pct": growth_6m,
        "fiber_mom_growth_pct": fiber_mom_growth,
        "fiber_yoy_growth_pct": fiber_yoy_growth,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Backfill subscriber_timeseries
# ═══════════════════════════════════════════════════════════════════════════════


async def backfill_timeseries(
    db: AsyncSession,
    municipality_id: int,
) -> dict[str, Any]:
    """Compute and store time-series aggregates in subscriber_timeseries.

    For each (l2_id, provider_id, year_month) combination, computes:
      - total subscribers
      - fiber subscribers
      - MoM growth %
      - YoY growth %
      - churn estimate % (based on negative MoM movements)
      - ARPU estimate (placeholder at R$80 for fiber, R$50 for DSL/cable)

    Existing rows for this municipality are deleted before inserting.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id to backfill.

    Returns:
        Summary with row count inserted and time range.
    """
    # Step 1: Get all monthly aggregates per provider
    agg_sql = text("""
        SELECT
            bs.l2_id,
            bs.provider_id,
            TRIM(bs.year_month) AS year_month,
            SUM(bs.subscribers) AS subscribers,
            SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END)
                AS fiber_subscribers
        FROM broadband_subscribers bs
        WHERE bs.l2_id = :municipality_id
        GROUP BY bs.l2_id, bs.provider_id, TRIM(bs.year_month)
        ORDER BY bs.provider_id, TRIM(bs.year_month)
    """)

    result = await db.execute(agg_sql, {"municipality_id": municipality_id})
    rows = result.fetchall()

    if not rows:
        return {
            "municipality_id": municipality_id,
            "rows_inserted": 0,
            "message": "No broadband data found for this municipality",
        }

    # Step 2: Organize by provider for growth calculations
    provider_data: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        pid = row.provider_id
        if pid not in provider_data:
            provider_data[pid] = []
        provider_data[pid].append({
            "l2_id": row.l2_id,
            "provider_id": pid,
            "year_month": row.year_month.strip() if isinstance(row.year_month, str) else row.year_month,
            "subscribers": int(row.subscribers or 0),
            "fiber_subscribers": int(row.fiber_subscribers or 0),
        })

    # Step 3: Compute growth metrics for each provider time-series
    now = datetime.now(timezone.utc)
    records_to_insert: list[dict[str, Any]] = []

    for pid, series in provider_data.items():
        # Build lookup by year_month for this provider
        by_month: dict[str, dict[str, Any]] = {r["year_month"]: r for r in series}
        sorted_months = sorted(by_month.keys())

        for i, ym in enumerate(sorted_months):
            rec = by_month[ym]
            subs = rec["subscribers"]
            fiber_subs = rec["fiber_subscribers"]

            # MoM growth
            mom_growth = None
            if i > 0:
                prev = by_month[sorted_months[i - 1]]["subscribers"]
                if prev > 0:
                    mom_growth = round(((subs - prev) / prev) * 100, 4)

            # YoY growth — find the month 12 positions back
            yoy_growth = None
            if i >= 12:
                prev_year = by_month[sorted_months[i - 12]]["subscribers"]
                if prev_year > 0:
                    yoy_growth = round(((subs - prev_year) / prev_year) * 100, 4)

            # Churn estimate: negative MoM as proxy for churn
            churn_estimate = None
            if mom_growth is not None and mom_growth < 0:
                churn_estimate = round(abs(mom_growth), 4)
            elif mom_growth is not None:
                churn_estimate = 0.0

            # ARPU estimate: fiber-heavy providers tend to have higher ARPU
            fiber_ratio = fiber_subs / subs if subs > 0 else 0.0
            arpu_estimate = round(50.0 + (fiber_ratio * 30.0), 2)  # R$50-80 range

            records_to_insert.append({
                "l2_id": municipality_id,
                "provider_id": pid,
                "year_month": ym,
                "subscribers": subs,
                "fiber_subscribers": fiber_subs,
                "mom_growth_pct": mom_growth,
                "yoy_growth_pct": yoy_growth,
                "churn_estimate_pct": churn_estimate,
                "arpu_estimate_brl": arpu_estimate,
                "computed_at": now,
            })

    # Step 4: Delete existing rows for this municipality
    delete_sql = text("""
        DELETE FROM subscriber_timeseries WHERE l2_id = :municipality_id
    """)
    await db.execute(delete_sql, {"municipality_id": municipality_id})

    # Step 5: Insert all computed records
    if records_to_insert:
        insert_sql = text("""
            INSERT INTO subscriber_timeseries
                (l2_id, provider_id, year_month, subscribers, fiber_subscribers,
                 mom_growth_pct, yoy_growth_pct, churn_estimate_pct,
                 arpu_estimate_brl, computed_at)
            VALUES
                (:l2_id, :provider_id, :year_month, :subscribers, :fiber_subscribers,
                 :mom_growth_pct, :yoy_growth_pct, :churn_estimate_pct,
                 :arpu_estimate_brl, :computed_at)
        """)
        for rec in records_to_insert:
            await db.execute(insert_sql, rec)

    # Gather summary
    all_months = sorted({r["year_month"] for r in records_to_insert})

    return {
        "municipality_id": municipality_id,
        "rows_inserted": len(records_to_insert),
        "providers_processed": len(provider_data),
        "earliest_month": all_months[0] if all_months else None,
        "latest_month": all_months[-1] if all_months else None,
        "computed_at": now.isoformat(),
    }
