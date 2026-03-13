"""
Report credit management service.

Handles credit checking, spending, and monthly refills for the
freemium/paywall monetization model.
"""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Credit allocations per plan tier
PLAN_CONFIG = {
    "free": {"monthly_credits": 0, "rpm": 30},
    "starter": {"monthly_credits": 3, "rpm": 60},
    "provedor": {"monthly_credits": 10, "rpm": 120},
    "profissional": {"monthly_credits": 50, "rpm": 300},
    "enterprise": {"monthly_credits": -1, "rpm": 600},  # -1 = unlimited
}


async def check_credits(db: AsyncSession, tenant_id: str) -> int:
    """Return available credits for a tenant. -1 means unlimited."""
    result = await db.execute(
        text("SELECT credits_total - credits_used AS available, plan_monthly_credits FROM report_credits WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        return 0
    # Unlimited plan
    if row.plan_monthly_credits == -1:
        return -1
    return max(0, row.available)


async def spend_credit(
    db: AsyncSession,
    tenant_id: str,
    user_id: int | None,
    report_type: str,
    entity_id: int | None = None,
) -> bool:
    """
    Spend 1 credit for a report unlock.
    Returns True if successful, False if insufficient credits.
    """
    available = await check_credits(db, tenant_id)
    if available == 0:
        return False

    # Deduct credit (skip for unlimited)
    if available != -1:
        await db.execute(
            text("UPDATE report_credits SET credits_used = credits_used + 1 WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )

    # Record purchase
    await db.execute(
        text("""
            INSERT INTO report_purchases (tenant_id, user_id, report_type, provider_id, credits_spent)
            VALUES (:tid, :uid, :rtype, :eid, 1)
        """),
        {"tid": tenant_id, "uid": user_id, "rtype": report_type, "eid": entity_id},
    )

    await db.commit()
    logger.info("Credit spent: tenant=%s user=%s type=%s entity=%s", tenant_id, user_id, report_type, entity_id)
    return True


async def refill_monthly(db: AsyncSession, tenant_id: str) -> int:
    """
    Auto-refill monthly credits based on plan.
    Returns new credit total, or -1 for errors.
    """
    result = await db.execute(
        text("SELECT plan_monthly_credits, last_refill_date FROM report_credits WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        return -1

    today = date.today()
    # Only refill if last refill was in a previous month
    if row.last_refill_date and row.last_refill_date.month == today.month and row.last_refill_date.year == today.year:
        return 0  # Already refilled this month

    new_total = row.plan_monthly_credits
    if new_total == -1:
        return -1  # Unlimited, no refill needed

    await db.execute(
        text("""
            UPDATE report_credits
            SET credits_total = :total, credits_used = 0, last_refill_date = :today
            WHERE tenant_id = :tid
        """),
        {"total": new_total, "today": today, "tid": tenant_id},
    )
    await db.commit()
    logger.info("Monthly refill: tenant=%s credits=%d", tenant_id, new_total)
    return new_total


async def ensure_credits_row(db: AsyncSession, tenant_id: str, plan: str = "free") -> None:
    """Ensure a report_credits row exists for the tenant."""
    result = await db.execute(
        text("SELECT id FROM report_credits WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    if result.fetchone():
        return

    config = PLAN_CONFIG.get(plan, PLAN_CONFIG["free"])
    monthly = config["monthly_credits"]

    await db.execute(
        text("""
            INSERT INTO report_credits (tenant_id, credits_total, credits_used, plan_monthly_credits, last_refill_date)
            VALUES (:tid, :total, 0, :monthly, :today)
        """),
        {"tid": tenant_id, "total": monthly, "monthly": monthly, "today": date.today()},
    )
    await db.commit()
