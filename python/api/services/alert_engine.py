"""
ENLACE Smart Alerts Engine

Evaluates user-defined alert rules against live database state and creates
alert events when conditions are met.  Supports the following rule types:

- **subscriber_drop**: fires when total subscribers in a scoped area drop
  by more than a threshold percentage between the two most recent months.
- **competitor_entry**: fires when new providers appear in monitored
  municipalities compared to a lookback window.
- **regulatory_deadline**: fires when upcoming regulatory deadlines fall
  within a configurable ``days_ahead`` window.
- **quality_degradation**: fires when quality indicator scores fall below
  a minimum threshold for monitored municipalities.
- **market_change**: fires when broadband penetration or fiber share
  changes by more than a threshold percentage month-over-month.

Each rule respects a ``cooldown_hours`` setting so the same rule does not
fire repeatedly in a short window.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _severity_from_pct(change_pct: float) -> str:
    """Map a percentage change magnitude to a severity level."""
    abs_pct = abs(change_pct)
    if abs_pct >= 20:
        return "critical"
    if abs_pct >= 10:
        return "high"
    if abs_pct >= 5:
        return "medium"
    return "low"


async def _is_within_cooldown(
    db: AsyncSession, rule_id: int, cooldown_hours: int
) -> bool:
    """Return True if the rule was triggered within its cooldown window."""
    if cooldown_hours <= 0:
        return False

    cutoff = _now_utc() - timedelta(hours=cooldown_hours)
    result = await db.execute(
        text("""
            SELECT 1 FROM alert_events
            WHERE rule_id = :rule_id AND created_at > :cutoff
            LIMIT 1
        """),
        {"rule_id": rule_id, "cutoff": cutoff},
    )
    return result.fetchone() is not None


async def _create_event(
    db: AsyncSession,
    rule_id: int,
    user_id: Any,
    title: str,
    message: str,
    severity: str,
    data: dict,
) -> int:
    """Insert a new alert_events row and update the rule's last_triggered_at.

    Returns the new event id.
    """
    now = _now_utc()
    result = await db.execute(
        text("""
            INSERT INTO alert_events (rule_id, user_id, title, message, severity, data, is_read, created_at)
            VALUES (:rule_id, :user_id, :title, :message, :severity, :data::jsonb, false, :now)
            RETURNING id
        """),
        {
            "rule_id": rule_id,
            "user_id": user_id,
            "title": title,
            "message": message,
            "severity": severity,
            "data": __import__("json").dumps(data),
            "now": now,
        },
    )
    event_id = result.scalar_one()

    await db.execute(
        text("UPDATE alert_rules SET last_triggered_at = :now WHERE id = :rule_id"),
        {"now": now, "rule_id": rule_id},
    )

    logger.info(
        "Alert event %d created for rule %d [%s]: %s",
        event_id, rule_id, severity, title,
    )
    return event_id


def _scope_where(conditions: dict, params: dict, prefix: str = "") -> str:
    """Build optional WHERE clause fragments from rule conditions scope.

    Supports scope keys: state, municipality_id, municipality_ids.
    Mutates *params* in place to add bind values.
    Returns a SQL fragment (may be empty string).
    """
    scope = conditions.get("scope", {})
    clauses: list[str] = []

    if "state" in scope:
        key = f"{prefix}scope_state"
        params[key] = scope["state"]
        clauses.append(f"a1.abbrev = :{key}")

    if "municipality_id" in scope:
        key = f"{prefix}scope_muni"
        params[key] = scope["municipality_id"]
        clauses.append(f"bs.l2_id = :{key}")

    if "municipality_ids" in scope:
        key = f"{prefix}scope_munis"
        params[key] = scope["municipality_ids"]
        clauses.append(f"bs.l2_id = ANY(:{key})")

    if clauses:
        return " AND " + " AND ".join(clauses)
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Rule-type checkers
# ═══════════════════════════════════════════════════════════════════════════════


async def check_subscriber_drop(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Compare the latest vs. previous month total subscribers.

    Fires if the percentage drop exceeds ``conditions.threshold`` (default 5%).
    Returns the event id if fired, else None.
    """
    conditions = rule["conditions"] or {}
    threshold = float(conditions.get("threshold", 5))

    params: dict[str, Any] = {}
    scope_sql = _scope_where(conditions, params)

    # Aggregate subscribers for the two most recent months, optionally scoped
    sql = text(f"""
        WITH monthly AS (
            SELECT bs.year_month, SUM(bs.subscribers) AS total
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE 1=1 {scope_sql}
            GROUP BY bs.year_month
            ORDER BY bs.year_month DESC
            LIMIT 2
        )
        SELECT year_month, total FROM monthly ORDER BY year_month DESC
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if len(rows) < 2:
        return None

    latest_month, latest_total = rows[0].year_month.strip(), int(rows[0].total)
    prev_month, prev_total = rows[1].year_month.strip(), int(rows[1].total)

    if prev_total == 0:
        return None

    change_pct = ((latest_total - prev_total) / prev_total) * 100

    if change_pct < -threshold:
        drop_pct = abs(change_pct)
        scope_label = _scope_label(conditions)
        return await _create_event(
            db,
            rule_id=rule["id"],
            user_id=rule["user_id"],
            title=f"Queda de assinantes: {drop_pct:.1f}%{scope_label}",
            message=(
                f"Assinantes caíram de {prev_total:,} ({prev_month}) para "
                f"{latest_total:,} ({latest_month}), uma queda de {drop_pct:.1f}%."
            ),
            severity=_severity_from_pct(change_pct),
            data={
                "rule_type": "subscriber_drop",
                "latest_month": latest_month,
                "previous_month": prev_month,
                "latest_total": latest_total,
                "previous_total": prev_total,
                "change_pct": round(change_pct, 2),
                "threshold_pct": threshold,
                "scope": conditions.get("scope", {}),
            },
        )

    return None


async def check_competitor_entry(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Detect new providers in monitored municipalities.

    Compares the set of providers in the latest month against those present
    in the previous month.  Fires if any new provider appears.
    Returns the event id if fired, else None.
    """
    conditions = rule["conditions"] or {}
    scope = conditions.get("scope", {})

    # Determine municipality scope
    muni_ids: Optional[list[int]] = None
    if "municipality_id" in scope:
        muni_ids = [scope["municipality_id"]]
    elif "municipality_ids" in scope:
        muni_ids = scope["municipality_ids"]

    scope_clause = ""
    params: dict[str, Any] = {}
    if muni_ids:
        params["muni_ids"] = muni_ids
        scope_clause = "AND bs.l2_id = ANY(:muni_ids)"

    if "state" in scope:
        params["scope_state"] = scope["state"]
        scope_clause += " AND a1.abbrev = :scope_state"

    sql = text(f"""
        WITH months AS (
            SELECT DISTINCT year_month
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE 1=1 {scope_clause}
            ORDER BY year_month DESC
            LIMIT 2
        ),
        latest_providers AS (
            SELECT DISTINCT bs.provider_id
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE bs.year_month = (SELECT year_month FROM months LIMIT 1)
              {scope_clause}
        ),
        prev_providers AS (
            SELECT DISTINCT bs.provider_id
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON a2.id = bs.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE bs.year_month = (SELECT year_month FROM months OFFSET 1 LIMIT 1)
              {scope_clause}
        )
        SELECT lp.provider_id, p.name
        FROM latest_providers lp
        JOIN providers p ON p.id = lp.provider_id
        WHERE lp.provider_id NOT IN (SELECT provider_id FROM prev_providers)
    """)

    result = await db.execute(sql, params)
    new_providers = result.fetchall()

    if not new_providers:
        return None

    names = [row.name for row in new_providers]
    scope_label = _scope_label(conditions)
    return await _create_event(
        db,
        rule_id=rule["id"],
        user_id=rule["user_id"],
        title=f"{len(new_providers)} novo(s) concorrente(s) detectado(s){scope_label}",
        message=(
            f"Novos provedores identificados: {', '.join(names)}."
        ),
        severity="high" if len(new_providers) >= 3 else "medium",
        data={
            "rule_type": "competitor_entry",
            "new_providers": [
                {"id": row.provider_id, "name": row.name}
                for row in new_providers
            ],
            "scope": conditions.get("scope", {}),
        },
    )


async def check_regulatory_deadline(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Check for upcoming regulatory deadlines within the rule's window.

    Uses the in-memory deadline knowledge base rather than a DB table.
    Fires if any deadline falls within ``conditions.days_ahead`` days.
    Returns the event id if fired, else None.
    """
    from python.regulatory.knowledge_base.deadlines import (
        get_upcoming_deadlines,
        format_deadline_summary,
    )

    conditions = rule["conditions"] or {}
    days_ahead = int(conditions.get("days_ahead", 30))

    upcoming = get_upcoming_deadlines(within_days=days_ahead)

    if not upcoming:
        return None

    # Build summary of the most urgent deadlines
    urgent = [d for d in upcoming if d.urgency in ("critical", "overdue")]
    if not urgent:
        urgent = upcoming[:3]

    summaries = [format_deadline_summary(d) for d in urgent[:5]]

    return await _create_event(
        db,
        rule_id=rule["id"],
        user_id=rule["user_id"],
        title=f"{len(upcoming)} prazo(s) regulatório(s) nos próximos {days_ahead} dias",
        message="\n".join(summaries),
        severity="critical" if any(d.urgency in ("critical", "overdue") for d in upcoming) else "medium",
        data={
            "rule_type": "regulatory_deadline",
            "days_ahead": days_ahead,
            "deadlines": [
                {
                    "regulation_id": d.regulation_id,
                    "name": d.name,
                    "deadline_date": d.deadline_date.isoformat(),
                    "urgency": d.urgency,
                    "days_remaining": d.days_remaining,
                }
                for d in upcoming
            ],
        },
    )


async def check_quality_degradation(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Detect quality score drops below a minimum threshold.

    Checks the quality_indicators table for the most recent period and
    fires if any monitored metric falls below ``conditions.min_score``.
    Returns the event id if fired, else None.
    """
    conditions = rule["conditions"] or {}
    min_score = float(conditions.get("min_score", 6.0))
    metric = conditions.get("metric", "overall_score")
    scope = conditions.get("scope", {})

    scope_clause = ""
    params: dict[str, Any] = {"min_score": min_score}

    if "state" in scope:
        params["scope_state"] = scope["state"]
        scope_clause += " AND a1.abbrev = :scope_state"

    if "municipality_id" in scope:
        params["scope_muni"] = scope["municipality_id"]
        scope_clause += " AND qi.l2_id = :scope_muni"

    # quality_indicators has: l2_id, provider_id, year_half, overall_score,
    # availability_score, speed_score, latency_score
    # Use overall_score by default
    score_col_map = {
        "overall_score": "qi.overall_score",
        "availability_score": "qi.availability_score",
        "speed_score": "qi.speed_score",
        "latency_score": "qi.latency_score",
    }
    score_col = score_col_map.get(metric, "qi.overall_score")

    sql = text(f"""
        SELECT qi.l2_id, a2.name AS municipality_name, p.name AS provider_name,
               {score_col} AS score, qi.year_half
        FROM quality_indicators qi
        JOIN admin_level_2 a2 ON a2.id = qi.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        JOIN providers p ON p.id = qi.provider_id
        WHERE qi.year_half = (SELECT MAX(year_half) FROM quality_indicators)
          AND {score_col} < :min_score
          {scope_clause}
        ORDER BY {score_col} ASC
        LIMIT 20
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return None

    scope_label = _scope_label(conditions)
    worst = rows[0]
    return await _create_event(
        db,
        rule_id=rule["id"],
        user_id=rule["user_id"],
        title=f"Degradação de qualidade detectada{scope_label}: {len(rows)} caso(s)",
        message=(
            f"Pior caso: {worst.provider_name} em {worst.municipality_name} "
            f"com {metric} = {float(worst.score):.1f} (mínimo: {min_score})."
        ),
        severity="critical" if float(worst.score) < min_score * 0.7 else "high",
        data={
            "rule_type": "quality_degradation",
            "metric": metric,
            "min_score": min_score,
            "violations": [
                {
                    "municipality_id": row.l2_id,
                    "municipality_name": row.municipality_name,
                    "provider_name": row.provider_name,
                    "score": float(row.score),
                    "year_half": row.year_half,
                }
                for row in rows
            ],
            "scope": scope,
        },
    )


async def check_market_change(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Detect significant changes in market metrics (penetration, fiber share).

    Compares the latest vs. previous month's aggregated metrics from
    mv_market_summary and fires if the change exceeds the threshold.
    Returns the event id if fired, else None.
    """
    conditions = rule["conditions"] or {}
    metric = conditions.get("metric", "broadband_penetration_pct")
    threshold = float(conditions.get("threshold", 5))
    operator = conditions.get("operator", "change_pct")
    scope = conditions.get("scope", {})

    metric_map = {
        "penetration": "broadband_penetration_pct",
        "broadband_penetration_pct": "broadband_penetration_pct",
        "fiber_share": "fiber_share_pct",
        "fiber_share_pct": "fiber_share_pct",
        "subscribers": "total_subscribers",
        "total_subscribers": "total_subscribers",
    }
    db_col = metric_map.get(metric, "broadband_penetration_pct")

    scope_clause = ""
    params: dict[str, Any] = {}

    if "state" in scope:
        params["scope_state"] = scope["state"]
        scope_clause += " AND state_abbrev = :scope_state"

    if "municipality_id" in scope:
        params["scope_muni"] = scope["municipality_id"]
        scope_clause += " AND l2_id = :scope_muni"

    # Get two most recent year_months of aggregated data
    sql = text(f"""
        WITH months AS (
            SELECT DISTINCT year_month
            FROM mv_market_summary
            WHERE 1=1 {scope_clause}
            ORDER BY year_month DESC
            LIMIT 2
        ),
        latest AS (
            SELECT AVG({db_col}) AS avg_val
            FROM mv_market_summary
            WHERE year_month = (SELECT year_month FROM months LIMIT 1)
              {scope_clause}
        ),
        prev AS (
            SELECT AVG({db_col}) AS avg_val
            FROM mv_market_summary
            WHERE year_month = (SELECT year_month FROM months OFFSET 1 LIMIT 1)
              {scope_clause}
        )
        SELECT latest.avg_val AS latest_val, prev.avg_val AS prev_val
        FROM latest, prev
    """)

    result = await db.execute(sql, params)
    row = result.fetchone()

    if not row or row.latest_val is None or row.prev_val is None:
        return None

    latest_val = float(row.latest_val)
    prev_val = float(row.prev_val)

    if prev_val == 0:
        return None

    change_pct = ((latest_val - prev_val) / prev_val) * 100

    should_fire = False
    if operator == "decrease_pct" and change_pct < -threshold:
        should_fire = True
    elif operator == "increase_pct" and change_pct > threshold:
        should_fire = True
    elif operator == "change_pct" and abs(change_pct) > threshold:
        should_fire = True

    if not should_fire:
        return None

    direction = "aumento" if change_pct > 0 else "queda"
    scope_label = _scope_label(conditions)

    return await _create_event(
        db,
        rule_id=rule["id"],
        user_id=rule["user_id"],
        title=f"Mudança de mercado: {direction} de {abs(change_pct):.1f}% em {metric}{scope_label}",
        message=(
            f"Métrica '{metric}' mudou de {prev_val:.2f} para {latest_val:.2f} "
            f"({change_pct:+.1f}%), ultrapassando o limiar de {threshold}%."
        ),
        severity=_severity_from_pct(change_pct),
        data={
            "rule_type": "market_change",
            "metric": metric,
            "operator": operator,
            "threshold_pct": threshold,
            "latest_value": round(latest_val, 4),
            "previous_value": round(prev_val, 4),
            "change_pct": round(change_pct, 2),
            "scope": scope,
        },
    )


def _scope_label(conditions: dict) -> str:
    """Build a human-readable scope suffix for alert titles."""
    scope = conditions.get("scope", {})
    parts: list[str] = []
    if "state" in scope:
        parts.append(scope["state"])
    if "municipality_id" in scope:
        parts.append(f"muni:{scope['municipality_id']}")
    if parts:
        return f" ({', '.join(parts)})"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Rule dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_RULE_HANDLERS = {
    "subscriber_drop": check_subscriber_drop,
    "competitor_entry": check_competitor_entry,
    "regulatory_deadline": check_regulatory_deadline,
    "quality_degradation": check_quality_degradation,
    "market_change": check_market_change,
}


async def evaluate_single_rule(
    db: AsyncSession,
    rule: dict,
) -> Optional[int]:
    """Evaluate a single rule and create an event if triggered.

    Checks cooldown before running the handler. Returns the event id
    if an alert was created, else None.
    """
    rule_id = rule["id"]
    cooldown = rule.get("cooldown_hours", 24)

    if await _is_within_cooldown(db, rule_id, cooldown):
        logger.debug("Rule %d is within cooldown (%dh), skipping", rule_id, cooldown)
        return None

    handler = _RULE_HANDLERS.get(rule["rule_type"])
    if handler is None:
        logger.warning("Unknown rule_type '%s' for rule %d", rule["rule_type"], rule_id)
        return None

    try:
        return await handler(db, rule)
    except Exception:
        logger.exception("Error evaluating rule %d (%s)", rule_id, rule["rule_type"])
        return None


async def evaluate_rules(
    db: AsyncSession,
    user_id: Optional[Any] = None,
) -> dict[str, Any]:
    """Evaluate all active rules (optionally filtered to a single user).

    Returns a summary dict with counts of evaluated / triggered rules.
    """
    where = "WHERE is_active = true"
    params: dict[str, Any] = {}
    if user_id is not None:
        where += " AND user_id = :user_id"
        params["user_id"] = user_id

    result = await db.execute(
        text(f"""
            SELECT id, user_id, name, rule_type, conditions, cooldown_hours,
                   last_triggered_at
            FROM alert_rules
            {where}
            ORDER BY id
        """),
        params,
    )
    rows = result.fetchall()

    evaluated = 0
    triggered = 0
    errors = 0
    events_created: list[int] = []

    for row in rows:
        rule = {
            "id": row.id,
            "user_id": row.user_id,
            "name": row.name,
            "rule_type": row.rule_type,
            "conditions": row.conditions,
            "cooldown_hours": row.cooldown_hours or 24,
            "last_triggered_at": row.last_triggered_at,
        }
        evaluated += 1
        try:
            event_id = await evaluate_single_rule(db, rule)
            if event_id is not None:
                triggered += 1
                events_created.append(event_id)
        except Exception:
            errors += 1
            logger.exception("Failed to evaluate rule %d", row.id)

    logger.info(
        "Rule evaluation complete: %d evaluated, %d triggered, %d errors",
        evaluated, triggered, errors,
    )

    return {
        "evaluated": evaluated,
        "triggered": triggered,
        "errors": errors,
        "events_created": events_created,
    }
