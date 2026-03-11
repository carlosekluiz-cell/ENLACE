"""
ENLACE M&A Enhanced Router

Additional M&A intelligence endpoints: comparable transaction analysis,
synergy modeling, due diligence checklists, and integration timeline
estimation.  Uses the same ``/api/v1/mna`` prefix as the base M&A router
so all M&A functionality is grouped under a single path.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import mna_service


router = APIRouter(prefix="/api/v1/mna", tags=["mna"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic request / response models
# ═══════════════════════════════════════════════════════════════════════════════


class ComparableAnalysisRequest(BaseModel):
    provider_id: int = Field(..., description="Target provider ID")
    subscriber_range: Optional[list[int]] = Field(
        None,
        min_length=2,
        max_length=2,
        description="[min, max] subscriber count filter for comparables",
    )
    fiber_range: Optional[list[float]] = Field(
        None,
        min_length=2,
        max_length=2,
        description="[min_pct, max_pct] fiber penetration filter (0-100)",
    )
    states: Optional[list[str]] = Field(
        None,
        description="State abbreviation(s) to restrict comparable search (e.g. ['SP','MG'])",
    )


class SynergyModelRequest(BaseModel):
    acquirer_id: int = Field(..., description="Acquiring provider ID")
    target_id: int = Field(..., description="Target provider ID")


class DueDiligenceRequest(BaseModel):
    target_provider_name: str = Field(
        ...,
        min_length=1,
        description="Target provider name (used to look up by name if ID unknown)",
    )
    state_codes: Optional[list[str]] = Field(
        None,
        description="State code(s) to narrow provider lookup",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /comparable-analysis — Comparable transaction analysis
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/comparable-analysis")
async def comparable_analysis(
    request: ComparableAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Find comparable ISPs and compute implied transaction multiples.

    Identifies ISPs of similar size, fiber mix, and geographic presence to
    derive market-based valuation multiples (EV/subscriber, EV/revenue).
    """
    sub_range = None
    if request.subscriber_range and len(request.subscriber_range) == 2:
        sub_range = (request.subscriber_range[0], request.subscriber_range[1])

    fiber_range = None
    if request.fiber_range and len(request.fiber_range) == 2:
        fiber_range = (request.fiber_range[0], request.fiber_range[1])

    result = await mna_service.comparable_analysis(
        db=db,
        provider_id=request.provider_id,
        subscriber_range=sub_range,
        fiber_range=fiber_range,
        states=request.states,
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /synergy-model — Synergy estimation between acquirer and target
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/synergy-model")
async def synergy_model(
    request: SynergyModelRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Estimate revenue, cost, and market synergies for a proposed acquisition.

    Analyses geographic overlap, subscriber complementarity, and
    infrastructure sharing potential to project annual synergy value
    and 5-year NPV.
    """
    result = await mna_service.synergy_model(
        db=db,
        acquirer_id=request.acquirer_id,
        target_id=request.target_id,
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /due-diligence — Due diligence checklist generation
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/due-diligence")
async def due_diligence(
    request: DueDiligenceRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Generate a comprehensive due diligence checklist for an acquisition target.

    Assesses regulatory compliance, subscriber quality, infrastructure
    health, financial position, and competitive standing from real data.
    Accepts a provider name (with optional state filter) and resolves it
    to a provider ID before running the analysis.
    """
    from sqlalchemy import text

    # Resolve provider by name (case-insensitive, optional state filter)
    where_parts = ["LOWER(p.name) = LOWER(:name)"]
    params: dict[str, Any] = {"name": request.target_provider_name.strip()}

    if request.state_codes:
        where_parts.append("""
            p.id IN (
                SELECT DISTINCT bs.provider_id
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON bs.l2_id = a2.id
                JOIN admin_level_1 l1 ON a2.l1_id = l1.id
                WHERE l1.abbrev = ANY(:states)
            )
        """)
        params["states"] = [s.upper() for s in request.state_codes]

    where_sql = " AND ".join(where_parts)
    lookup_sql = text(f"""
        SELECT p.id, p.name
        FROM providers p
        WHERE {where_sql}
        LIMIT 1
    """)

    result = await db.execute(lookup_sql, params)
    row = result.fetchone()

    if not row:
        # Try fuzzy match (ILIKE with %name%)
        params["name_like"] = f"%{request.target_provider_name.strip()}%"
        fuzzy_parts = ["p.name ILIKE :name_like"]
        if request.state_codes:
            fuzzy_parts.append(where_parts[1])  # reuse state filter
        fuzzy_sql = text(f"""
            SELECT p.id, p.name
            FROM providers p
            WHERE {' AND '.join(fuzzy_parts)}
            ORDER BY LENGTH(p.name) ASC
            LIMIT 5
        """)
        fuzzy_result = await db.execute(fuzzy_sql, params)
        fuzzy_rows = fuzzy_result.fetchall()

        if not fuzzy_rows:
            return {
                "error": "Provider not found",
                "searched_name": request.target_provider_name,
                "state_filter": request.state_codes,
                "suggestion": "Try a partial name or check the providers table",
            }

        if len(fuzzy_rows) == 1:
            row = fuzzy_rows[0]
        else:
            return {
                "error": "Multiple providers match — please refine your search",
                "matches": [
                    {"provider_id": r.id, "name": r.name} for r in fuzzy_rows
                ],
            }

    dd_result = await mna_service.due_diligence_checklist(
        db=db,
        target_id=row.id,
    )

    return dd_result


# ═══════════════════════════════════════════════════════════════════════════════
# GET /integration-timeline — Integration timeline estimation
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/integration-timeline")
async def integration_timeline(
    acquirer_subs: int = Query(..., ge=1, description="Acquirer subscriber count"),
    target_subs: int = Query(..., ge=1, description="Target subscriber count"),
    user: dict = Depends(require_auth),
):
    """Estimate post-acquisition integration phases and timeline.

    Returns a phased integration plan with durations, milestones,
    key activities, risks, and success factors based on the relative
    size of the acquirer and target.
    """
    result = await mna_service.integration_timeline(
        acquirer_subs=acquirer_subs,
        target_subs=target_subs,
    )

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GET /spectrum/{provider_id} — Spectrum holdings
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/spectrum/{provider_id}")
async def spectrum_holdings(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get spectrum holdings for a provider."""
    result = await mna_service.get_spectrum_holdings(db=db, provider_id=provider_id)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GET /spectrum/valuation/{provider_id} — Spectrum asset valuation
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/spectrum/valuation/{provider_id}")
async def spectrum_valuation(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Value spectrum assets for a provider."""
    result = await mna_service.value_spectrum(db=db, provider_id=provider_id)
    return result
