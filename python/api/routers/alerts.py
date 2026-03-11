"""
ENLACE Smart Alerts Router

CRUD for alert rules and alert events, plus manual rule evaluation.
All queries are scoped to the authenticated user's ``user_id``.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth, require_admin
from python.api.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic models
# ═══════════════════════════════════════════════════════════════════════════════


class AlertRuleCreate(BaseModel):
    """Request body to create a new alert rule."""

    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")
    rule_type: str = Field(
        ...,
        description="Rule type: subscriber_drop, competitor_entry, regulatory_deadline, quality_degradation, market_change",
    )
    conditions: dict[str, Any] = Field(
        ...,
        description="Conditions JSONB, e.g. {\"metric\": \"subscribers\", \"operator\": \"decrease_pct\", \"threshold\": 5, \"scope\": {\"state\": \"SP\"}}",
    )
    channels: Optional[dict[str, Any]] = Field(
        None,
        description="Notification channels, e.g. {\"email\": true, \"in_app\": true}",
    )
    cooldown_hours: int = Field(24, ge=0, le=8760, description="Minimum hours between re-triggers")
    is_active: bool = Field(True, description="Whether the rule is enabled")


class AlertRuleUpdate(BaseModel):
    """Request body to update an existing alert rule."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    rule_type: Optional[str] = None
    conditions: Optional[dict[str, Any]] = None
    channels: Optional[dict[str, Any]] = None
    cooldown_hours: Optional[int] = Field(None, ge=0, le=8760)
    is_active: Optional[bool] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_RULE_TYPES = {
    "subscriber_drop",
    "competitor_entry",
    "regulatory_deadline",
    "quality_degradation",
    "market_change",
}


def _validate_rule_type(rule_type: str) -> str:
    if rule_type not in _VALID_RULE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid rule_type '{rule_type}'. Must be one of: {', '.join(sorted(_VALID_RULE_TYPES))}",
        )
    return rule_type


def _row_to_rule(row) -> dict[str, Any]:
    """Convert a SQLAlchemy Row to a rule dict for JSON response."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "description": row.description,
        "rule_type": row.rule_type,
        "conditions": row.conditions,
        "is_active": row.is_active,
        "channels": row.channels,
        "cooldown_hours": row.cooldown_hours,
        "last_triggered_at": row.last_triggered_at.isoformat() if row.last_triggered_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _row_to_event(row) -> dict[str, Any]:
    """Convert a SQLAlchemy Row to an event dict for JSON response."""
    return {
        "id": row.id,
        "rule_id": row.rule_id,
        "user_id": row.user_id,
        "title": row.title,
        "message": row.message,
        "severity": row.severity,
        "data": row.data,
        "is_read": row.is_read,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Rule CRUD
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/rules")
async def list_rules(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    List the authenticated user's alert rules.

    Supports optional filtering by active status and rule type.
    """
    clauses = ["user_id = :user_id"]
    params: dict[str, Any] = {"user_id": user["user_id"]}

    if is_active is not None:
        clauses.append("is_active = :is_active")
        params["is_active"] = is_active

    if rule_type is not None:
        _validate_rule_type(rule_type)
        clauses.append("rule_type = :rule_type")
        params["rule_type"] = rule_type

    where = " AND ".join(clauses)

    result = await db.execute(
        text(f"""
            SELECT id, user_id, name, description, rule_type, conditions,
                   is_active, channels, cooldown_hours, last_triggered_at,
                   created_at, updated_at
            FROM alert_rules
            WHERE {where}
            ORDER BY created_at DESC
        """),
        params,
    )
    rows = result.fetchall()
    return [_row_to_rule(r) for r in rows]


@router.post("/rules", status_code=201)
async def create_rule(
    body: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Create a new alert rule for the authenticated user.

    The rule starts evaluating immediately if ``is_active`` is true.
    """
    _validate_rule_type(body.rule_type)
    now = datetime.now(timezone.utc)

    import json

    result = await db.execute(
        text("""
            INSERT INTO alert_rules
                (user_id, name, description, rule_type, conditions, is_active,
                 channels, cooldown_hours, created_at, updated_at)
            VALUES
                (:user_id, :name, :description, :rule_type, :conditions::jsonb,
                 :is_active, :channels::jsonb, :cooldown_hours, :now, :now)
            RETURNING id, user_id, name, description, rule_type, conditions,
                      is_active, channels, cooldown_hours, last_triggered_at,
                      created_at, updated_at
        """),
        {
            "user_id": user["user_id"],
            "name": body.name,
            "description": body.description,
            "rule_type": body.rule_type,
            "conditions": json.dumps(body.conditions),
            "is_active": body.is_active,
            "channels": json.dumps(body.channels) if body.channels else None,
            "cooldown_hours": body.cooldown_hours,
            "now": now,
        },
    )
    row = result.fetchone()
    logger.info("Alert rule %d created by user %s", row.id, user["user_id"])
    return _row_to_rule(row)


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Update an existing alert rule. Only the fields provided are changed.

    The rule must belong to the authenticated user.
    """
    import json

    # Verify ownership
    existing = await db.execute(
        text("SELECT id FROM alert_rules WHERE id = :id AND user_id = :user_id"),
        {"id": rule_id, "user_id": user["user_id"]},
    )
    if existing.fetchone() is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    # Build SET clause dynamically from provided fields
    updates: list[str] = []
    params: dict[str, Any] = {"id": rule_id, "user_id": user["user_id"]}

    if body.name is not None:
        updates.append("name = :name")
        params["name"] = body.name

    if body.description is not None:
        updates.append("description = :description")
        params["description"] = body.description

    if body.rule_type is not None:
        _validate_rule_type(body.rule_type)
        updates.append("rule_type = :rule_type")
        params["rule_type"] = body.rule_type

    if body.conditions is not None:
        updates.append("conditions = :conditions::jsonb")
        params["conditions"] = json.dumps(body.conditions)

    if body.channels is not None:
        updates.append("channels = :channels::jsonb")
        params["channels"] = json.dumps(body.channels)

    if body.cooldown_hours is not None:
        updates.append("cooldown_hours = :cooldown_hours")
        params["cooldown_hours"] = body.cooldown_hours

    if body.is_active is not None:
        updates.append("is_active = :is_active")
        params["is_active"] = body.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    now = datetime.now(timezone.utc)
    updates.append("updated_at = :updated_at")
    params["updated_at"] = now

    set_clause = ", ".join(updates)

    result = await db.execute(
        text(f"""
            UPDATE alert_rules
            SET {set_clause}
            WHERE id = :id AND user_id = :user_id
            RETURNING id, user_id, name, description, rule_type, conditions,
                      is_active, channels, cooldown_hours, last_triggered_at,
                      created_at, updated_at
        """),
        params,
    )
    row = result.fetchone()
    logger.info("Alert rule %d updated by user %s", rule_id, user["user_id"])
    return _row_to_rule(row)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Delete an alert rule and all its associated events.

    The rule must belong to the authenticated user.
    """
    # Verify ownership
    existing = await db.execute(
        text("SELECT id FROM alert_rules WHERE id = :id AND user_id = :user_id"),
        {"id": rule_id, "user_id": user["user_id"]},
    )
    if existing.fetchone() is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    # Delete associated events first (FK constraint)
    await db.execute(
        text("DELETE FROM alert_events WHERE rule_id = :rule_id"),
        {"rule_id": rule_id},
    )

    await db.execute(
        text("DELETE FROM alert_rules WHERE id = :id AND user_id = :user_id"),
        {"id": rule_id, "user_id": user["user_id"]},
    )

    logger.info("Alert rule %d deleted by user %s", rule_id, user["user_id"])
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Events
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/events")
async def list_events(
    unread: Optional[bool] = Query(None, description="Filter to unread events only"),
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    rule_type: Optional[str] = Query(None, description="Filter by originating rule type"),
    limit: int = Query(50, ge=1, le=500, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    List alert events for the authenticated user.

    Supports filtering by read status, severity, and rule type.
    Results are ordered newest-first.
    """
    clauses = ["ae.user_id = :user_id"]
    params: dict[str, Any] = {
        "user_id": user["user_id"],
        "limit": limit,
        "offset": offset,
    }

    if unread is True:
        clauses.append("ae.is_read = false")
    elif unread is False:
        clauses.append("ae.is_read = true")

    if severity is not None:
        clauses.append("ae.severity = :severity")
        params["severity"] = severity

    if rule_type is not None:
        _validate_rule_type(rule_type)
        clauses.append("ar.rule_type = :rule_type")
        params["rule_type"] = rule_type

    where = " AND ".join(clauses)

    # Join with alert_rules to get rule_type for filtering
    result = await db.execute(
        text(f"""
            SELECT ae.id, ae.rule_id, ae.user_id, ae.title, ae.message,
                   ae.severity, ae.data, ae.is_read, ae.acknowledged_at,
                   ae.created_at
            FROM alert_events ae
            LEFT JOIN alert_rules ar ON ar.id = ae.rule_id
            WHERE {where}
            ORDER BY ae.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )
    rows = result.fetchall()
    return [_row_to_event(r) for r in rows]


@router.get("/events/count")
async def event_count(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Get unread alert event count for the authenticated user.

    Intended for the notification bell badge in the frontend.
    """
    result = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM alert_events
            WHERE user_id = :user_id AND is_read = false
        """),
        {"user_id": user["user_id"]},
    )
    row = result.fetchone()
    return {"unread_count": row.cnt if row else 0}


@router.post("/events/{event_id}/acknowledge")
async def acknowledge_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Mark an alert event as read / acknowledged.

    Sets ``is_read = true`` and records the acknowledgement timestamp.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        text("""
            UPDATE alert_events
            SET is_read = true, acknowledged_at = :now
            WHERE id = :id AND user_id = :user_id
            RETURNING id, rule_id, user_id, title, message, severity, data,
                      is_read, acknowledged_at, created_at
        """),
        {"id": event_id, "user_id": user["user_id"], "now": now},
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Alert event not found")

    logger.info("Alert event %d acknowledged by user %s", event_id, user["user_id"])
    return _row_to_event(row)


# ═══════════════════════════════════════════════════════════════════════════════
# Manual evaluation (admin only)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/evaluate")
async def evaluate(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    """
    Manually trigger evaluation of all active alert rules.

    Requires admin role. Evaluates every active rule across all users,
    respecting cooldown windows. Returns a summary of how many rules
    were evaluated and how many fired.
    """
    from python.api.services.alert_engine import evaluate_rules

    summary = await evaluate_rules(db)
    logger.info(
        "Manual alert evaluation by admin %s: %s",
        user["user_id"],
        summary,
    )
    return summary
