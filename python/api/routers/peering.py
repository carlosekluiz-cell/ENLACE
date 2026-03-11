"""PeeringDB Network Data Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/peering", tags=["peering"])


@router.get("/networks")
async def get_networks(
    country: str = Query("BR"),
    info_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List peering networks from PeeringDB data."""
    where_parts = ["country = :country"]
    params = {"country": country.upper(), "limit": limit}
    if info_type:
        where_parts.append("info_type = :info_type")
        params["info_type"] = info_type
    where_sql = " AND ".join(where_parts)
    sql = text(f"SELECT * FROM peering_networks WHERE {where_sql} ORDER BY info_prefixes4 DESC NULLS LAST LIMIT :limit")
    result = await db.execute(sql, params)
    rows = result.fetchall()
    return {
        "country": country,
        "total": len(rows),
        "networks": [dict(r._mapping) for r in rows],
    }


@router.get("/ixps")
async def get_ixps(
    country: str = Query("BR"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """List IXPs from PeeringDB data."""
    sql = text("SELECT * FROM peering_ixps WHERE country = :country ORDER BY participants_count DESC NULLS LAST LIMIT :limit")
    result = await db.execute(sql, {"country": country.upper(), "limit": limit})
    rows = result.fetchall()
    return {"country": country, "total": len(rows), "ixps": [dict(r._mapping) for r in rows]}


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get peering statistics summary."""
    net_sql = text("SELECT COUNT(*) AS cnt, SUM(info_prefixes4) AS total_prefixes4 FROM peering_networks WHERE country = 'BR'")
    ixp_sql = text("SELECT COUNT(*) AS cnt, SUM(participants_count) AS total_participants FROM peering_ixps WHERE country = 'BR'")
    net_row = (await db.execute(net_sql)).fetchone()
    ixp_row = (await db.execute(ixp_sql)).fetchone()
    return {
        "networks": {"count": net_row.cnt if net_row else 0, "total_prefixes4": int(net_row.total_prefixes4 or 0) if net_row else 0},
        "ixps": {"count": ixp_row.cnt if ixp_row else 0, "total_participants": int(ixp_row.total_participants or 0) if ixp_row else 0},
    }
