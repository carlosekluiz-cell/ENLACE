"""Multi-tenant management for ENLACE platform.

Each ISP organization is a tenant.  Public data (Anatel, IBGE) is shared
across all tenants.  Tenant-specific data (custom analyses, saved reports,
settings, and user accounts) is isolated by ``tenant_id``.

Tenant storage is currently in-memory for development.  In production
this would be backed by the PostgreSQL database.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

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
    "pro": 120,
    "enterprise": 600,
}


# ---------------------------------------------------------------------------
# In-memory tenant store (development)
# ---------------------------------------------------------------------------
_TENANTS: dict[str, Tenant] = {
    "default": Tenant(
        id="default",
        name="ENLACE Development",
        country_code="BR",
        primary_state=None,
        plan="enterprise",
        rate_limit=600,
    ),
}


def get_tenant(tenant_id: str) -> Tenant | None:
    """Get a tenant by ID.

    Args:
        tenant_id: Tenant identifier.

    Returns:
        Tenant instance, or None if not found.
    """
    tenant = _TENANTS.get(tenant_id)
    if tenant is None:
        logger.debug(f"Tenant not found: {tenant_id}")
    return tenant


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

    tenant_id = str(uuid.uuid4())[:8]
    rate_limit = PLAN_RATE_LIMITS[plan]

    tenant = Tenant(
        id=tenant_id,
        name=name,
        country_code=country_code,
        primary_state=primary_state,
        plan=plan,
        rate_limit=rate_limit,
    )

    _TENANTS[tenant_id] = tenant

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
    return list(_TENANTS.values())


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

    if tenant_id in _TENANTS:
        del _TENANTS[tenant_id]
        logger.info("Deleted tenant: %s", tenant_id)
        return True

    return False
