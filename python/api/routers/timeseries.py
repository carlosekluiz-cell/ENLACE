"""
ENLACE Time-Series Analytics Router

Endpoints for subscriber time-series data, growth metrics, forecasting,
backfill, national trends, and provider history.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.timeseries_service import (
    get_subscriber_timeseries,
    get_growth_metrics,
    backfill_timeseries,
)
from python.api.services.forecasting import forecast_subscribers

router = APIRouter(prefix="/api/v1/timeseries", tags=["timeseries"])


@router.get("/subscribers")
async def timeseries_subscribers(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    provider_id: Optional[int] = Query(None, description="Optional provider ID filter"),
    interval: str = Query(
        "month",
        description="Aggregation interval: 'month' or 'quarter'",
        pattern="^(month|quarter)$",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Subscriber time-series data aggregated by month or quarter.

    Returns chronologically ordered data points with total subscribers,
    fiber subscribers, provider count, and technology count for each period.
    """
    data = await get_subscriber_timeseries(
        db=db,
        municipality_id=municipality_id,
        provider_id=provider_id,
        interval=interval,
    )

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No subscriber data found for this municipality",
        )

    return {
        "municipality_id": municipality_id,
        "provider_id": provider_id,
        "interval": interval,
        "data_points": len(data),
        "series": data,
    }


@router.get("/growth")
async def timeseries_growth(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Growth metrics for a municipality: MoM, YoY, CAGR, 3-month, 6-month.

    Computes growth rates from the full broadband_subscribers history.
    Includes both total and fiber-specific growth rates.
    """
    metrics = await get_growth_metrics(db=db, municipality_id=municipality_id)

    if metrics["data_points"] == 0:
        raise HTTPException(
            status_code=404,
            detail="No subscriber data found for this municipality",
        )

    return metrics


@router.get("/forecast")
async def timeseries_forecast(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    months_ahead: int = Query(
        12, ge=1, le=60, description="Number of months to forecast (1-60)"
    ),
    model: str = Query(
        "auto",
        description="Forecasting model: 'linear', 'exponential', or 'auto'",
        pattern="^(linear|exponential|auto)$",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Subscriber forecast using trend extrapolation.

    Fits linear and/or exponential models to historical data and projects
    forward. Returns historical fitted values, forecast points with 95%
    confidence intervals, and model diagnostics (R-squared, slope, etc.).

    When model='auto', the service selects whichever model has a better
    R-squared fit (with a small bias toward linear for stability).
    """
    result = await forecast_subscribers(
        db=db,
        municipality_id=municipality_id,
        months_ahead=months_ahead,
        model=model,
    )

    if result["status"] == "insufficient_data":
        raise HTTPException(
            status_code=422,
            detail=result["message"],
        )

    return result


@router.post("/backfill/{municipality_id}")
async def timeseries_backfill(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Trigger backfill computation for subscriber_timeseries.

    Computes and stores per-provider monthly aggregates with derived
    metrics (MoM growth, YoY growth, churn estimate, ARPU estimate)
    in the subscriber_timeseries table. Existing rows for the given
    municipality are replaced.
    """
    result = await backfill_timeseries(db=db, municipality_id=municipality_id)

    if result["rows_inserted"] == 0:
        raise HTTPException(
            status_code=404,
            detail=result.get("message", "No data to backfill"),
        )

    return result


@router.get("/national")
async def national_trends(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    National broadband evolution: total subscribers, fiber %, provider count,
    technology breakdown per period across all of Brazil.
    """
    sql = text("""
        SELECT
            bs.year_month AS period,
            SUM(bs.subscribers) AS total_subs,
            COUNT(DISTINCT bs.provider_id) AS active_providers,
            COUNT(DISTINCT bs.l2_id) AS active_municipalities,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBER%'
                     OR UPPER(bs.technology) LIKE '%FTTH%'
                     OR UPPER(bs.technology) LIKE '%GPON%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS fiber_pct,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%RADIO%'
                     OR UPPER(bs.technology) LIKE '%FWA%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS radio_pct,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%DSL%'
                     OR UPPER(bs.technology) LIKE '%ADSL%'
                     OR UPPER(bs.technology) LIKE '%XDSL%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS dsl_pct,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%COAX%'
                     OR UPPER(bs.technology) LIKE '%HFC%'
                     OR UPPER(bs.technology) LIKE '%CABLE%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS cable_pct
        FROM broadband_subscribers bs
        GROUP BY bs.year_month
        ORDER BY bs.year_month
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    return {
        "data_points": len(rows),
        "series": [
            {
                "period": str(row.period),
                "total_subscribers": int(row.total_subs),
                "active_providers": int(row.active_providers),
                "active_municipalities": int(row.active_municipalities),
                "fiber_pct": round(float(row.fiber_pct or 0), 1),
                "radio_pct": round(float(row.radio_pct or 0), 1),
                "dsl_pct": round(float(row.dsl_pct or 0), 1),
                "cable_pct": round(float(row.cable_pct or 0), 1),
            }
            for row in rows
        ],
    }


@router.get("/provider/{provider_id}")
async def provider_history(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Full historical time series for a specific provider.
    Includes subscriber count, fiber %, municipality count, and market share.
    """
    sql = text("""
        WITH provider_data AS (
            SELECT
                bs.year_month AS period,
                SUM(bs.subscribers) AS subs,
                COUNT(DISTINCT bs.l2_id) AS municipalities,
                SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBER%'
                         OR UPPER(bs.technology) LIKE '%FTTH%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS fiber_pct
            FROM broadband_subscribers bs
            WHERE bs.provider_id = :pid
            GROUP BY bs.year_month
        ),
        national AS (
            SELECT year_month, SUM(subscribers) AS total
            FROM broadband_subscribers
            GROUP BY year_month
        )
        SELECT
            pd.period,
            pd.subs AS subscribers,
            pd.municipalities,
            pd.fiber_pct,
            ROUND(pd.subs * 100.0 / NULLIF(n.total, 0), 2) AS national_share
        FROM provider_data pd
        JOIN national n ON n.year_month = pd.period
        ORDER BY pd.period
    """)

    result = await db.execute(sql, {"pid": provider_id})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No data for this provider")

    # Provider name
    name_result = await db.execute(
        text("SELECT name FROM providers WHERE id = :pid"), {"pid": provider_id}
    )
    name_row = name_result.fetchone()

    return {
        "provider_id": provider_id,
        "name": name_row.name.strip() if name_row else str(provider_id),
        "data_points": len(rows),
        "series": [
            {
                "period": str(row.period),
                "subscribers": int(row.subscribers),
                "municipalities": int(row.municipalities),
                "fiber_pct": round(float(row.fiber_pct or 0), 1),
                "national_share": round(float(row.national_share or 0), 2),
            }
            for row in rows
        ],
    }


@router.get("/employment")
async def employment_trends(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Employment indicator trends for a municipality over 5 years (2021-2025).
    Returns telecom employment, services employment, average salary.
    """
    sql = text("""
        SELECT year, month, formal_jobs_telecom, formal_jobs_services,
               formal_jobs_total, avg_salary_brl, net_hires
        FROM employment_indicators
        WHERE l2_id = :muni_id
        ORDER BY year, month
    """)
    result = await db.execute(sql, {"muni_id": municipality_id})
    rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No employment data for this municipality")

    return {
        "municipality_id": municipality_id,
        "data_points": len(rows),
        "series": [
            {
                "period": f"{row.year}-{row.month:02d}",
                "formal_jobs_telecom": int(row.formal_jobs_telecom or 0),
                "formal_jobs_services": int(row.formal_jobs_services or 0),
                "formal_jobs_total": int(row.formal_jobs_total or 0),
                "avg_salary_brl": round(float(row.avg_salary_brl), 2) if row.avg_salary_brl else None,
                "net_hires": int(row.net_hires or 0),
            }
            for row in rows
        ],
    }


@router.get("/gazette")
async def gazette_search(
    municipality_id: Optional[int] = Query(None, description="Municipality ID filter"),
    q: Optional[str] = Query(None, min_length=2, description="Search term for gazette excerpts"),
    mention_type: Optional[str] = Query(None, description="Filter by mention type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Searchable gazette timeline — 60K+ records from municipal official gazettes.
    Filter by municipality, keyword, mention type.
    """
    conditions = []
    params: dict = {"lim": limit, "off": offset}

    if municipality_id:
        conditions.append("g.l2_id = :muni_id")
        params["muni_id"] = municipality_id
    if q:
        conditions.append("g.excerpt ILIKE '%' || :q || '%'")
        params["q"] = q
    if mention_type:
        conditions.append("g.mention_type = :mtype")
        params["mtype"] = mention_type

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    count_sql = text(f"SELECT COUNT(*) AS cnt FROM municipal_gazette_mentions g {where}")
    result = await db.execute(count_sql, params)
    total = result.fetchone().cnt

    sql = text(f"""
        SELECT g.id, g.published_date, g.gazette_id, g.excerpt,
               g.mention_type, g.keywords,
               a2.name AS municipality_name, a1.abbrev AS state
        FROM municipal_gazette_mentions g
        LEFT JOIN admin_level_2 a2 ON a2.id = g.l2_id
        LEFT JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        {where}
        ORDER BY g.published_date DESC
        LIMIT :lim OFFSET :off
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    # Get mention type counts
    type_sql = text(f"""
        SELECT g.mention_type, COUNT(*) AS cnt
        FROM municipal_gazette_mentions g {where}
        GROUP BY g.mention_type ORDER BY cnt DESC
    """)
    result = await db.execute(type_sql, params)
    type_counts = {r.mention_type: int(r.cnt) for r in result.fetchall()}

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "mention_types": type_counts,
        "results": [
            {
                "id": row.id,
                "published_date": str(row.published_date) if row.published_date else None,
                "gazette_id": row.gazette_id,
                "excerpt": (row.excerpt[:300] + "...") if row.excerpt and len(row.excerpt) > 300 else row.excerpt,
                "mention_type": row.mention_type,
                "keywords": list(row.keywords) if row.keywords else [],
                "municipality": row.municipality_name.strip() if row.municipality_name else None,
                "state": row.state.strip() if row.state else None,
            }
            for row in rows
        ],
    }


@router.get("/fiber-race")
async def fiber_race(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Fiber adoption race by state over time.
    Returns fiber % per state per period for animated timeline charts.
    """
    sql = text("""
        SELECT
            a1.abbrev AS state,
            bs.year_month AS period,
            SUM(CASE WHEN UPPER(bs.technology) LIKE '%FIBER%'
                     OR UPPER(bs.technology) LIKE '%FTTH%'
                THEN bs.subscribers ELSE 0 END) * 100.0
                / NULLIF(SUM(bs.subscribers), 0) AS fiber_pct,
            SUM(bs.subscribers) AS total_subs
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        GROUP BY a1.abbrev, bs.year_month
        ORDER BY a1.abbrev, bs.year_month
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    # Group by state
    states: dict[str, list] = {}
    for row in rows:
        state = row.state.strip()
        if state not in states:
            states[state] = []
        states[state].append({
            "period": str(row.period),
            "fiber_pct": round(float(row.fiber_pct or 0), 1),
            "total_subs": int(row.total_subs),
        })

    return {
        "states": len(states),
        "data": states,
    }
