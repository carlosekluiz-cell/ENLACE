"""
ENLACE RGST 777/2025 Compliance Checker Service

Checks provider compliance against RGST 777/2025 obligations:
authorization, quality reporting, RF compliance, subscriber thresholds.
"""

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_rgst777(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Run RGST 777/2025 compliance checklist for a provider."""
    # Verify provider exists
    prov_sql = text("SELECT id, name, status, services FROM providers WHERE id = :pid")
    result = await db.execute(prov_sql, {"pid": provider_id})
    provider = result.fetchone()

    if not provider:
        return {"error": "Provider not found", "provider_id": provider_id}

    checks = []

    # 1. Authorization check: provider must have active status
    is_active = provider.status and provider.status.lower() in ("ativa", "active")
    checks.append({
        "category": "authorization",
        "obligation": "Autorização SCM/STFC ativa",
        "status": "pass" if is_active else "fail",
        "detail": f"Status: {provider.status or 'desconhecido'}",
        "evidence_source": "providers.status",
    })

    # 2. Quality reporting: check if quality indicators exist
    qi_sql = text("""
        SELECT COUNT(*) AS cnt FROM quality_indicators WHERE provider_id = :pid
    """)
    qi_row = (await db.execute(qi_sql, {"pid": provider_id})).fetchone()
    has_quality = qi_row and qi_row.cnt > 0
    checks.append({
        "category": "quality_reporting",
        "obligation": "Indicadores de qualidade reportados",
        "status": "pass" if has_quality else "warning",
        "detail": f"{qi_row.cnt} indicadores encontrados" if has_quality else "Nenhum indicador de qualidade encontrado",
        "evidence_source": "quality_indicators",
    })

    # 3. Spectrum license compliance
    spec_sql = text("""
        SELECT COUNT(*) AS cnt FROM spectrum_licenses WHERE provider_id = :pid
    """)
    spec_row = (await db.execute(spec_sql, {"pid": provider_id})).fetchone()
    has_spectrum = spec_row and spec_row.cnt > 0
    checks.append({
        "category": "rf_compliance",
        "obligation": "Licenças de espectro válidas",
        "status": "pass" if has_spectrum else "warning",
        "detail": f"{spec_row.cnt} licença(s) de espectro" if has_spectrum else "Sem licenças de espectro no registro",
        "evidence_source": "spectrum_licenses",
    })

    # 4. Subscriber threshold check (SCM >= 5000 requires full compliance)
    subs_sql = text("""
        SELECT COALESCE(SUM(subscribers), 0) AS total
        FROM broadband_subscribers
        WHERE provider_id = :pid
          AND year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid)
    """)
    subs_row = (await db.execute(subs_sql, {"pid": provider_id})).fetchone()
    total_subs = int(subs_row.total) if subs_row else 0

    if total_subs >= 5000:
        threshold_status = "warning"
        threshold_detail = f"{total_subs:,} assinantes — requer conformidade total RGST 777"
    else:
        threshold_status = "pass"
        threshold_detail = f"{total_subs:,} assinantes — abaixo do limiar de conformidade total"

    checks.append({
        "category": "subscriber_threshold",
        "obligation": "Limiar de assinantes para conformidade total",
        "status": threshold_status,
        "detail": threshold_detail,
        "evidence_source": "broadband_subscribers",
    })

    # 5. Base station registration
    bs_sql = text("SELECT COUNT(*) AS cnt FROM base_stations WHERE provider_id = :pid")
    bs_row = (await db.execute(bs_sql, {"pid": provider_id})).fetchone()
    has_stations = bs_row and bs_row.cnt > 0
    checks.append({
        "category": "rf_compliance",
        "obligation": "Estações base registradas na Anatel",
        "status": "pass" if has_stations else "warning",
        "detail": f"{bs_row.cnt} estações base registradas" if has_stations else "Sem estações base registradas",
        "evidence_source": "base_stations",
    })

    # Summary
    passed = sum(1 for c in checks if c["status"] == "pass")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    failed = sum(1 for c in checks if c["status"] == "fail")

    overall = "compliant" if failed == 0 and warnings == 0 else "partial" if failed == 0 else "non_compliant"

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "regulation": "RGST 777/2025",
        "overall_status": overall,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
        },
        "total_subscribers": total_subs,
    }


async def rgst777_overview(
    db: AsyncSession,
    state: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Overview of RGST 777 compliance across providers."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("""
            p.id IN (
                SELECT DISTINCT bs.provider_id FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON bs.l2_id = a2.id
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)

    sql = text(f"""
        SELECT p.id, p.name, p.status,
            COALESCE((SELECT SUM(subscribers) FROM broadband_subscribers bs
                WHERE bs.provider_id = p.id
                AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)), 0) AS total_subs
        FROM providers p
        WHERE {where_sql}
        ORDER BY total_subs DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    providers = []
    for row in rows:
        is_active = row.status and row.status.lower() in ("ativa", "active")
        requires_full = int(row.total_subs) >= 5000
        providers.append({
            "provider_id": row.id,
            "provider_name": row.name,
            "status": row.status,
            "is_active": is_active,
            "total_subscribers": int(row.total_subs),
            "requires_full_compliance": requires_full,
            "compliance_estimate": "compliant" if is_active and not requires_full else "review_needed",
        })

    return {
        "regulation": "RGST 777/2025",
        "state_filter": state,
        "total_providers": len(providers),
        "providers": providers,
    }
