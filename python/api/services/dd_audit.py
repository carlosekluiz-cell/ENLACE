"""Due Diligence audit logging service.

Every access to fiscal / ownership data via the DD endpoints is recorded for
LGPD compliance and audit trail purposes.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_dd_access(
    db: AsyncSession,
    *,
    user: dict,
    target_provider_id: int,
    target_cnpj: Optional[str] = None,
    purpose: Optional[str] = None,
    nda_accepted: bool = False,
    sections: Optional[list[str]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> int:
    """Insert an audit row and return the generated audit ID."""
    result = await db.execute(
        text("""
            INSERT INTO due_diligence_audit_log
                (buyer_user_id, buyer_email, buyer_tenant_id,
                 target_provider_id, target_cnpj, purpose,
                 nda_accepted, data_sections_accessed,
                 ip_address, user_agent)
            VALUES
                (:uid, :email, :tid,
                 :pid, :cnpj, :purpose,
                 :nda, :sections,
                 :ip, :ua)
            RETURNING id
        """),
        {
            "uid": user.get("user_id", "unknown"),
            "email": user.get("email", ""),
            "tid": user.get("tenant_id", "default"),
            "pid": target_provider_id,
            "cnpj": target_cnpj,
            "purpose": purpose,
            "nda": nda_accepted,
            "sections": sections or [],
            "ip": ip_address,
            "ua": user_agent,
        },
    )
    row = result.fetchone()
    audit_id = row[0] if row else 0
    await db.commit()
    logger.info(
        "DD audit #%d: user=%s target=%d sections=%s",
        audit_id,
        user.get("email"),
        target_provider_id,
        sections,
    )
    return audit_id
