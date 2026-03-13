"""
Paywall middleware — feature gating and credit requirement dependencies.

Use `require_credits(report_type)` as a FastAPI dependency on protected
endpoints that consume report credits.
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.report_credits import check_credits, PLAN_CONFIG

logger = logging.getLogger(__name__)

# Feature → minimum plan mapping
FEATURE_MATRIX: dict[str, str] = {
    "raio-x-intel": "starter",
    "raio-x-full": "starter",
    "gazette-detail": "starter",
    "regulatory-detail": "starter",
    "bndes-detail": "starter",
    "spectrum-detail": "starter",
    "historical-data": "starter",
    "export-pdf": "provedor",
    "export-excel": "provedor",
    "api-access": "profissional",
    "custom-data": "enterprise",
}

# Plan hierarchy for comparison
PLAN_HIERARCHY = ["free", "starter", "provedor", "profissional", "enterprise"]


def _plan_rank(plan: str) -> int:
    """Return numeric rank for plan comparison."""
    try:
        return PLAN_HIERARCHY.index(plan)
    except ValueError:
        return 0


def require_plan(minimum_plan: str) -> Callable:
    """FastAPI dependency that checks if the user's tenant has at least the given plan."""
    async def _check(user: dict = Depends(require_auth)):
        user_plan = user.get("plan", "free")
        if _plan_rank(user_plan) < _plan_rank(minimum_plan):
            raise HTTPException(
                status_code=403,
                detail=f"Este recurso requer o plano '{minimum_plan}' ou superior. Seu plano atual: '{user_plan}'.",
            )
        return user
    return _check


def require_credits(report_type: str) -> Callable:
    """
    FastAPI dependency that checks if the user has credits available
    for the given report type. Does NOT spend the credit — call
    spend_credit() explicitly after generating the report.
    """
    minimum_plan = FEATURE_MATRIX.get(report_type, "starter")

    async def _check(
        user: dict = Depends(require_auth),
        db: AsyncSession = Depends(get_db),
    ):
        # Check plan
        user_plan = user.get("plan", "free")
        if _plan_rank(user_plan) < _plan_rank(minimum_plan):
            raise HTTPException(
                status_code=403,
                detail=f"Este recurso requer o plano '{minimum_plan}' ou superior.",
            )

        # Check credits
        tenant_id = user.get("tenant_id", "default")
        available = await check_credits(db, tenant_id)
        if available == 0:
            raise HTTPException(
                status_code=402,
                detail="Créditos insuficientes. Adquira mais créditos ou faça upgrade do plano.",
            )

        return user
    return _check
