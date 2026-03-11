"""
ENLACE Pulso Score Router

Endpoints for ISP health scoring: individual provider scores, rankings,
tier distribution, and on-demand score computation.
"""

import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.pulso_score import (
    compute_provider_score,
    get_distribution,
    get_provider_score,
    get_ranking,
    save_provider_score,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/score", tags=["pulso-score"])


@router.get("/provider/{provider_id}")
async def provider_score(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Full Pulso Score breakdown for a provider.

    Returns the latest computed score with all sub-scores, tier, rank,
    and score delta from previous computation.
    """
    score = await get_provider_score(db, provider_id)

    if not score:
        raise HTTPException(
            status_code=404,
            detail=f"No Pulso Score found for provider {provider_id}. "
                   "Use POST /score/compute/{provider_id} to compute it.",
        )

    return score


@router.get("/ranking")
async def provider_ranking(
    state: str = Query(None, description="Filter by state abbreviation (e.g. SP, RJ)"),
    tier: str = Query(None, description="Filter by tier (S, A, B, C, D)"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Provider ranking by Pulso Score.

    Returns providers ordered by composite score, with optional state and
    tier filters. Each entry includes all sub-scores and the score delta.
    """
    if tier and tier.upper() not in ("S", "A", "B", "C", "D"):
        raise HTTPException(
            status_code=400,
            detail="Invalid tier. Must be one of: S, A, B, C, D",
        )

    results = await get_ranking(db, state=state, tier=tier, limit=limit)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No scored providers found. Run the Pulso Score pipeline first.",
        )

    return results


@router.get("/distribution")
async def tier_distribution(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Tier distribution statistics.

    Returns the count and percentage of providers in each tier (S/A/B/C/D),
    along with average, min, and max scores per tier.
    """
    dist = await get_distribution(db)

    if dist["total_providers_scored"] == 0:
        raise HTTPException(
            status_code=404,
            detail="No providers have been scored yet. Run the Pulso Score pipeline.",
        )

    return dist


@router.post("/compute/{provider_id}")
async def compute_score(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Trigger Pulso Score computation for a single provider.

    Computes all seven sub-scores from live database data, saves the result,
    and returns the full score breakdown.
    """
    score_data = await compute_provider_score(db, provider_id)

    if "error" in score_data:
        raise HTTPException(status_code=404, detail=score_data["error"])

    # Persist the computed score
    row_id = await save_provider_score(db, score_data)
    score_data["id"] = row_id

    logger.info(
        "Pulso Score computed for provider %d: %.2f (tier %s)",
        provider_id,
        score_data["score"],
        score_data["tier"],
    )

    return score_data
