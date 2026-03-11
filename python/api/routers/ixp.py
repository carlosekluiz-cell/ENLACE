"""IX.br IXP Data Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/ixp", tags=["ixp"])


@router.get("/locations")
async def get_locations(
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List IX.br locations."""
    if state:
        sql = text("SELECT * FROM ixp_locations WHERE state = :state ORDER BY traffic_gbps DESC NULLS LAST")
        result = await db.execute(sql, {"state": state.upper()})
    else:
        sql = text("SELECT * FROM ixp_locations ORDER BY traffic_gbps DESC NULLS LAST")
        result = await db.execute(sql)
    rows = result.fetchall()
    return {"total": len(rows), "locations": [dict(r._mapping) for r in rows]}


@router.get("/traffic")
async def get_traffic(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get aggregate IXP traffic data."""
    sql = text("""
        SELECT ixp_code, MAX(peak_traffic_gbps) AS peak_gbps, AVG(avg_traffic_gbps) AS avg_gbps,
               COUNT(*) AS data_points
        FROM ixp_traffic_history
        GROUP BY ixp_code
        ORDER BY peak_gbps DESC NULLS LAST
        LIMIT :limit
    """)
    result = await db.execute(sql, {"limit": limit})
    rows = result.fetchall()
    return {"total": len(rows), "traffic": [dict(r._mapping) for r in rows]}


@router.get("/traffic/{code}")
async def get_traffic_history(
    code: str,
    limit: int = Query(365, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get traffic history for a specific IXP."""
    sql = text("SELECT * FROM ixp_traffic_history WHERE ixp_code = :code ORDER BY date DESC LIMIT :limit")
    result = await db.execute(sql, {"code": code.upper(), "limit": limit})
    rows = result.fetchall()
    return {"code": code, "total": len(rows), "history": [dict(r._mapping) for r in rows]}
