"""
Research documents API — serves markdown research files for the /research UI.
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/research", tags=["research"])

DOCS_DIR = Path(__file__).resolve().parents[3] / "docs"

# Ordered list of research documents with metadata
RESEARCH_DOCS = [
    {
        "id": "master-synthesis",
        "file": "research-master-synthesis.md",
        "title": "Master Innovation Synthesis",
        "description": "Ranked synthesis of 250+ innovations across 15 research agents",
        "icon": "star",
        "tier": "overview",
    },
    {
        "id": "competitive-landscape",
        "file": "research-competitive-landscape.md",
        "title": "Competitive Landscape",
        "description": "38 competitors profiled, 6 high-threat, 18-24 month window",
        "icon": "target",
        "tier": "strategy",
    },
    {
        "id": "business-models",
        "file": "research-business-models.md",
        "title": "Business Models & GTM",
        "description": "Pricing, go-to-market, case studies (Veeva/Toast/Procore/ServiceTitan)",
        "icon": "briefcase",
        "tier": "strategy",
    },
    {
        "id": "monetization-partnerships",
        "file": "research-monetization-partnerships.md",
        "title": "Monetization & Partnerships",
        "description": "27 partners, API licensing, R$35-77M Year 5 projection",
        "icon": "handshake",
        "tier": "strategy",
    },
    {
        "id": "international-expansion",
        "file": "research-international-expansion.md",
        "title": "International Expansion",
        "description": "25+ markets, $429-655M TAM, Colombia #1 target",
        "icon": "globe",
        "tier": "strategy",
    },
    {
        "id": "revenue-markets",
        "file": "research-revenue-markets.md",
        "title": "Revenue & New Markets",
        "description": "22 initiatives, R$10.6M Y2 ARR potential",
        "icon": "trending-up",
        "tier": "product",
    },
    {
        "id": "data-engagement",
        "file": "research-data-engagement.md",
        "title": "Data Moat & Engagement",
        "description": "22 innovations for data depth and user stickiness",
        "icon": "database",
        "tier": "product",
    },
    {
        "id": "regulatory-financial",
        "file": "research-regulatory-financial.md",
        "title": "Regulatory & Financial",
        "description": "26 innovations, R$1.8-7.5B TAM, CBS/IBS tax reform",
        "icon": "shield",
        "tier": "product",
    },
    {
        "id": "ai-telecom-disruptors",
        "file": "research-ai-telecom-disruptors.md",
        "title": "AI Telecom Disruptors",
        "description": "18 AI startups, $50.21B market, Portuguese unserved",
        "icon": "brain",
        "tier": "technology",
    },
    {
        "id": "ml-repos",
        "file": "research-ml-repos.md",
        "title": "ML & CNN Repositories",
        "description": "27 repos + 7 meta-resources for telecom ML",
        "icon": "cpu",
        "tier": "technology",
    },
    {
        "id": "llm-ai-agents",
        "file": "research-llm-ai-agents.md",
        "title": "LLM & AI Agents",
        "description": "20+ tools including Vanna.ai, Claude Agent SDK, WhatsApp bot",
        "icon": "message-square",
        "tier": "technology",
    },
    {
        "id": "telecom-tools",
        "file": "research-telecom-tools.md",
        "title": "Open-Source Telecom Tools",
        "description": "28 tools: pgRouting, OpenCelliD, Ookla, NetBox, GNPy",
        "icon": "wrench",
        "tier": "technology",
    },
    {
        "id": "geospatial-viz",
        "file": "research-geospatial-viz.md",
        "title": "Geospatial & Visualization",
        "description": "20+ tools: MapLibre, kepler.gl, H3, CesiumJS, DuckDB Spatial",
        "icon": "map",
        "tier": "technology",
    },
    {
        "id": "tech-paradigms",
        "file": "research-tech-paradigms.md",
        "title": "Technology Paradigms",
        "description": "25 paradigm shifts: 5G FWA, Starlink, private 5G, Open RAN",
        "icon": "zap",
        "tier": "technology",
    },
    {
        "id": "standards-protocols",
        "file": "research-standards-protocols.md",
        "title": "Standards & Protocols",
        "description": "30 standards: RGST 777/2025, NFCom, Wi-Fi 7, Open RAN, IX.br",
        "icon": "book-open",
        "tier": "technology",
    },
]


@router.get("/")
async def list_research_docs():
    """List all available research documents with metadata."""
    result = []
    for doc in RESEARCH_DOCS:
        filepath = DOCS_DIR / doc["file"]
        exists = filepath.exists()
        size = filepath.stat().st_size if exists else 0
        result.append({**doc, "available": exists, "size_bytes": size})
    return {"documents": result}


@router.get("/{doc_id}")
async def get_research_doc(doc_id: str):
    """Get a specific research document's markdown content."""
    doc_meta = next((d for d in RESEARCH_DOCS if d["id"] == doc_id), None)
    if not doc_meta:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    filepath = DOCS_DIR / doc_meta["file"]
    if not filepath.exists():
        raise HTTPException(
            status_code=404, detail=f"Document file not yet available"
        )

    content = filepath.read_text(encoding="utf-8")
    return {
        **doc_meta,
        "content": content,
        "size_bytes": len(content.encode("utf-8")),
    }
