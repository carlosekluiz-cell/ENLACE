"""Multi-tenant management for ENLACE platform.

Each ISP organization is a tenant.  Public data (Anatel, IBGE) is shared
across all tenants.  Tenant-specific data (custom analyses, saved reports,
settings, and user accounts) is isolated by ``tenant_id``.

Tenants are stored in the PostgreSQL ``tenants`` table.  The table is
auto-created on first access if it does not exist.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import psycopg2
import psycopg2.extras

from python.api.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Tenant:
    """Represents an ISP organization (tenant).

    Attributes:
        id: Unique tenant identifier.
        name: Organization display name.
        country_code: ISO 3166-1 alpha-2 country code.
        primary_state: Primary state of operation (two-letter UF code).
        plan: Subscription plan tier.
        rate_limit: Maximum API requests per minute.
        created_at: Tenant creation timestamp.
    """

    id: str
    name: str
    country_code: str = "BR"
    primary_state: str | None = None
    plan: str = "free"  # "free", "pro", "enterprise"
    rate_limit: int = 60  # requests per minute
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Plan rate limits
# ---------------------------------------------------------------------------
PLAN_RATE_LIMITS = {
    "free": 30,
    "starter": 60,
    "provedor": 120,
    "pro": 120,  # legacy alias
    "profissional": 300,
    "enterprise": 600,
}

# Full plan config with credit allocations
PLAN_CONFIG = {
    "free": {"monthly_credits": 0, "rpm": 30},
    "starter": {"monthly_credits": 3, "rpm": 60},
    "provedor": {"monthly_credits": 10, "rpm": 120},
    "profissional": {"monthly_credits": 50, "rpm": 300},
    "enterprise": {"monthly_credits": -1, "rpm": 600},  # -1 = unlimited
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_connection():
    """Get a psycopg2 connection using app settings."""
    settings = Settings()
    return psycopg2.connect(settings.database_sync_url)


def _ensure_table():
    """Create the tenants table if it does not exist."""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            country_code VARCHAR(10) NOT NULL DEFAULT 'BR',
            primary_state VARCHAR(10),
            plan VARCHAR(50) NOT NULL DEFAULT 'free',
            rate_limit INTEGER NOT NULL DEFAULT 60,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    # Ensure default tenant exists
    cur.execute("""
        INSERT INTO tenants (id, name, country_code, plan, rate_limit)
        VALUES ('default', 'ENLACE Development', 'BR', 'enterprise', 600)
        ON CONFLICT (id) DO NOTHING
    """)
    conn.commit()
    cur.close()
    conn.close()


_table_ensured = False


def _ensure_table_once():
    global _table_ensured
    if not _table_ensured:
        try:
            _ensure_table()
            _table_ensured = True
        except Exception as e:
            logger.warning("Could not ensure tenants table: %s", e)


def _row_to_tenant(row: dict) -> Tenant:
    """Convert a database row dict to a Tenant dataclass."""
    return Tenant(
        id=row["id"],
        name=row["name"],
        country_code=row.get("country_code", "BR"),
        primary_state=row.get("primary_state"),
        plan=row.get("plan", "free"),
        rate_limit=row.get("rate_limit", 60),
        created_at=str(row.get("created_at", "")),
    )


# ---------------------------------------------------------------------------
# Public API (same interface as before)
# ---------------------------------------------------------------------------

def get_tenant(tenant_id: str) -> Tenant | None:
    """Get a tenant by ID.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        Tenant instance, or None if not found.
    """
    _ensure_table_once()
    try:
        conn = _get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row is None:
            logger.debug("Tenant not found: %s", tenant_id)
            return None
        return _row_to_tenant(row)
    except Exception as e:
        logger.warning("Error fetching tenant %s: %s", tenant_id, e)
        # Fallback for default tenant during startup
        if tenant_id == "default":
            return Tenant(
                id="default",
                name="ENLACE Development",
                plan="enterprise",
                rate_limit=600,
            )
        return None


def create_tenant(
    name: str,
    country_code: str = "BR",
    primary_state: str | None = None,
    plan: str = "free",
) -> Tenant:
    """Create a new tenant.

    Args:
        name: Organization display name.
        country_code: ISO country code (default: BR).
        primary_state: Primary state of operation.
        plan: Subscription plan (free, pro, enterprise).

    Returns:
        Newly created Tenant.

    Raises:
        ValueError: If the plan is invalid.
    """
    if plan not in PLAN_RATE_LIMITS:
        raise ValueError(
            f"Invalid plan '{plan}'. Must be one of: {list(PLAN_RATE_LIMITS.keys())}"
        )

    _ensure_table_once()

    tenant_id = str(uuid.uuid4())[:8]
    rate_limit = PLAN_RATE_LIMITS[plan]

    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tenants (id, name, country_code, primary_state, plan, rate_limit)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (tenant_id, name, country_code, primary_state, plan, rate_limit))
    conn.commit()
    cur.close()
    conn.close()

    tenant = Tenant(
        id=tenant_id,
        name=name,
        country_code=country_code,
        primary_state=primary_state,
        plan=plan,
        rate_limit=rate_limit,
    )

    logger.info(
        "Created tenant: id=%s, name=%s, plan=%s, rate_limit=%d",
        tenant_id, name, plan, rate_limit,
    )

    return tenant


def list_tenants() -> list[Tenant]:
    """List all tenants.

    Returns:
        List of all Tenant instances.
    """
    _ensure_table_once()
    try:
        conn = _get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM tenants ORDER BY created_at")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [_row_to_tenant(r) for r in rows]
    except Exception as e:
        logger.warning("Error listing tenants: %s", e)
        return []


def delete_tenant(tenant_id: str) -> bool:
    """Delete a tenant by ID.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        True if the tenant was deleted, False if not found.
    """
    if tenant_id == "default":
        logger.warning("Cannot delete the default tenant.")
        return False

    _ensure_table_once()
    try:
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            logger.info("Deleted tenant: %s", tenant_id)
        return deleted
    except Exception as e:
        logger.warning("Error deleting tenant %s: %s", tenant_id, e)
        return False
