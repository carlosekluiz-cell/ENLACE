"""
PeeringDB API Enrichment Pipeline

Fetches network and IXP data from PeeringDB's free REST API (no auth required).
Stores results in peering_networks and peering_ixps tables.

API docs: https://www.peeringdb.com/apidocs/
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.database import get_db_session

logger = logging.getLogger(__name__)

PEERINGDB_API = "https://www.peeringdb.com/api"


async def fetch_networks(country: str = "BR") -> list[dict[str, Any]]:
    """Fetch networks from PeeringDB API filtered by country."""
    url = f"{PEERINGDB_API}/net?country={country}&depth=0"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", [])


async def fetch_ixps(country: str = "BR") -> list[dict[str, Any]]:
    """Fetch IXPs from PeeringDB API filtered by country."""
    url = f"{PEERINGDB_API}/ix?country={country}&depth=0"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    return data.get("data", [])


async def ingest_networks(db: AsyncSession, networks: list[dict]) -> int:
    """Upsert network records into peering_networks table."""
    count = 0
    for net in networks:
        asn = net.get("asn")
        if not asn:
            continue
        sql = text("""
            INSERT INTO peering_networks (asn, name, aka, irr_as_set, info_type,
                info_prefixes4, info_prefixes6, policy_general, policy_url,
                website, info_traffic, info_scope, country, updated_at)
            VALUES (:asn, :name, :aka, :irr_as_set, :info_type,
                :info_prefixes4, :info_prefixes6, :policy_general, :policy_url,
                :website, :info_traffic, :info_scope, :country, :updated_at)
            ON CONFLICT (asn) DO UPDATE SET
                name = EXCLUDED.name,
                aka = EXCLUDED.aka,
                info_prefixes4 = EXCLUDED.info_prefixes4,
                info_prefixes6 = EXCLUDED.info_prefixes6,
                policy_general = EXCLUDED.policy_general,
                info_traffic = EXCLUDED.info_traffic,
                updated_at = EXCLUDED.updated_at
        """)
        await db.execute(sql, {
            "asn": asn,
            "name": net.get("name", ""),
            "aka": net.get("aka"),
            "irr_as_set": net.get("irr_as_set"),
            "info_type": net.get("info_type"),
            "info_prefixes4": net.get("info_prefixes4"),
            "info_prefixes6": net.get("info_prefixes6"),
            "policy_general": net.get("policy_general"),
            "policy_url": net.get("policy_url"),
            "website": net.get("website"),
            "info_traffic": net.get("info_traffic"),
            "info_scope": net.get("info_scope"),
            "country": net.get("country", "BR"),
            "updated_at": datetime.now(timezone.utc),
        })
        count += 1

    await db.commit()
    return count


async def ingest_ixps(db: AsyncSession, ixps: list[dict]) -> int:
    """Upsert IXP records into peering_ixps table."""
    count = 0
    for ix in ixps:
        pdb_id = ix.get("id")
        if not pdb_id:
            continue
        sql = text("""
            INSERT INTO peering_ixps (peeringdb_id, name, name_long, city, country,
                region_continent, participants_count, website, updated_at)
            VALUES (:pdb_id, :name, :name_long, :city, :country,
                :region_continent, :participants, :website, :updated_at)
            ON CONFLICT (peeringdb_id) DO UPDATE SET
                name = EXCLUDED.name,
                participants_count = EXCLUDED.participants_count,
                updated_at = EXCLUDED.updated_at
        """)
        await db.execute(sql, {
            "pdb_id": pdb_id,
            "name": ix.get("name", ""),
            "name_long": ix.get("name_long"),
            "city": ix.get("city"),
            "country": ix.get("country", "BR"),
            "region_continent": ix.get("region_continent"),
            "participants": ix.get("net_count", 0),
            "website": ix.get("website"),
            "updated_at": datetime.now(timezone.utc),
        })
        count += 1

    await db.commit()
    return count


async def run_pipeline() -> dict[str, Any]:
    """Main pipeline entry point."""
    logger.info("Starting PeeringDB pipeline")

    networks = await fetch_networks()
    ixps = await fetch_ixps()

    logger.info("Fetched %d networks and %d IXPs from PeeringDB", len(networks), len(ixps))

    async for db in get_db_session():
        net_count = await ingest_networks(db, networks)
        ixp_count = await ingest_ixps(db, ixps)

    logger.info("PeeringDB pipeline complete: %d networks, %d IXPs", net_count, ixp_count)

    return {
        "status": "success",
        "networks_ingested": net_count,
        "ixps_ingested": ixp_count,
    }
