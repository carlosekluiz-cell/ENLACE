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
# GET /due-diligence-dossier — Comprehensive provider due diligence dossier
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/due-diligence-dossier")
async def due_diligence_dossier(
    provider_id: int = Query(..., ge=1, description="Provider ID to investigate"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Build a comprehensive due diligence dossier for a provider.

    Aggregates data from provider_tax_debts, ownership_graph,
    provider_sanctions, consumer_complaints, and provider_details into
    a single risk-assessed report suitable for M&A evaluation.
    """
    from sqlalchemy import text
    from collections import defaultdict
    from datetime import date

    # ------------------------------------------------------------------
    # 1. Basic provider info
    # ------------------------------------------------------------------
    provider_row = (await db.execute(text("""
        SELECT p.id, p.name, p.national_id
        FROM providers p
        WHERE p.id = :pid
    """), {"pid": provider_id})).fetchone()

    if not provider_row:
        return {"error": "Provider not found", "provider_id": provider_id}

    provider_section: dict[str, Any] = {
        "id": provider_row.id,
        "name": provider_row.name,
        "national_id": provider_row.national_id,
    }

    # ------------------------------------------------------------------
    # 2. Subscriber context
    # ------------------------------------------------------------------
    sub_rows = (await db.execute(text("""
        SELECT
            COALESCE(SUM(bs.subscribers), 0)      AS total_subs,
            COUNT(DISTINCT bs.l2_id)               AS municipality_count,
            ARRAY_AGG(DISTINCT l1.abbrev)          AS states
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON bs.l2_id = a2.id
        JOIN admin_level_1 l1 ON a2.l1_id = l1.id
        WHERE bs.provider_id = :pid
          AND bs.year_month = (
              SELECT MAX(year_month) FROM broadband_subscribers
              WHERE provider_id = :pid
          )
    """), {"pid": provider_id})).fetchone()

    subscribers_section: dict[str, Any] = {
        "total": int(sub_rows.total_subs) if sub_rows and sub_rows.total_subs else 0,
        "municipalities": int(sub_rows.municipality_count) if sub_rows else 0,
        "states": sorted(sub_rows.states) if sub_rows and sub_rows.states and sub_rows.states[0] is not None else [],
    }

    # ------------------------------------------------------------------
    # 3. Registration (provider_details)
    # ------------------------------------------------------------------
    detail_row = (await db.execute(text("""
        SELECT
            legal_name, trade_name, legal_nature, capital_social,
            founding_date, partner_count, address_city, address_state,
            cnae_primary, status
        FROM provider_details
        WHERE provider_id = :pid
        ORDER BY created_at DESC
        LIMIT 1
    """), {"pid": provider_id})).fetchone()

    registration_section: dict[str, Any] = {}
    if detail_row:
        registration_section = {
            "legal_name": detail_row.legal_name,
            "trade_name": detail_row.trade_name,
            "legal_nature": detail_row.legal_nature,
            "capital_social": float(detail_row.capital_social) if detail_row.capital_social else None,
            "founding_date": detail_row.founding_date,
            "status": detail_row.status,
            "partner_count": detail_row.partner_count,
            "address_city": detail_row.address_city,
            "address_state": detail_row.address_state,
            "cnae_primary": detail_row.cnae_primary,
        }
    else:
        registration_section = {
            "legal_name": None, "trade_name": None, "legal_nature": None,
            "capital_social": None, "founding_date": None, "status": None,
            "partner_count": None, "address_city": None, "address_state": None,
            "cnae_primary": None,
        }

    # ------------------------------------------------------------------
    # 4. Tax debts (provider_tax_debts)
    # ------------------------------------------------------------------
    debt_rows = (await db.execute(text("""
        SELECT
            debt_type,
            COUNT(*)                              AS cnt,
            COALESCE(SUM(total_consolidated), 0)  AS total_amount,
            COUNT(*) FILTER (WHERE has_legal_action) AS legal_action_count
        FROM provider_tax_debts
        WHERE provider_id = :pid
        GROUP BY debt_type
    """), {"pid": provider_id})).fetchall()

    total_debt_brl = 0.0
    total_debt_count = 0
    total_legal_action = 0
    by_type: dict[str, Any] = {}
    for r in debt_rows:
        amount = float(r.total_amount)
        total_debt_brl += amount
        total_debt_count += r.cnt
        total_legal_action += r.legal_action_count
        by_type[r.debt_type] = {
            "count": r.cnt,
            "total_brl": round(amount, 2),
        }

    tax_debts_section: dict[str, Any] = {
        "total_brl": round(total_debt_brl, 2),
        "count": total_debt_count,
        "by_type": by_type,
        "with_legal_action": total_legal_action,
    }

    # ------------------------------------------------------------------
    # 5. Ownership graph (ownership_graph)
    # ------------------------------------------------------------------
    partner_rows = (await db.execute(text("""
        SELECT DISTINCT
            partner_name, partner_document, partner_type, partner_role
        FROM ownership_graph
        WHERE provider_id = :pid
        ORDER BY partner_name
    """), {"pid": provider_id})).fetchall()

    partners_list = [
        {
            "name": r.partner_name,
            "document": r.partner_document,
            "type": r.partner_type,
            "role": r.partner_role,
        }
        for r in partner_rows
    ]

    related_rows = (await db.execute(text("""
        SELECT DISTINCT
            related_cnpj_root, related_company_name, related_company_type
        FROM ownership_graph
        WHERE provider_id = :pid
          AND related_cnpj_root IS NOT NULL
        ORDER BY related_company_name
    """), {"pid": provider_id})).fetchall()

    related_companies = [
        {
            "cnpj_root": r.related_cnpj_root,
            "name": r.related_company_name,
            "type": r.related_company_type,
        }
        for r in related_rows
    ]

    # Count how many related companies are also ISPs (exist in providers)
    related_isp_count = 0
    if related_companies:
        related_isp_row = (await db.execute(text("""
            SELECT COUNT(DISTINCT og.related_cnpj_root) AS cnt
            FROM ownership_graph og
            JOIN providers p ON LEFT(p.national_id, 8) = og.related_cnpj_root
            WHERE og.provider_id = :pid
              AND og.related_cnpj_root IS NOT NULL
        """), {"pid": provider_id})).fetchone()
        related_isp_count = related_isp_row.cnt if related_isp_row else 0

    ownership_section: dict[str, Any] = {
        "partners": partners_list,
        "related_companies": related_companies,
        "related_isps": related_isp_count,
    }

    # ------------------------------------------------------------------
    # 6. Sanctions (provider_sanctions)
    # ------------------------------------------------------------------
    sanction_rows = (await db.execute(text("""
        SELECT
            list_type, sanction_type, sanctioning_authority,
            process_number, start_date, end_date
        FROM provider_sanctions
        WHERE provider_id = :pid
        ORDER BY start_date DESC
    """), {"pid": provider_id})).fetchall()

    today = date.today()
    active_sanctions = []
    expired_sanctions = []
    for r in sanction_rows:
        entry = {
            "list_type": r.list_type,
            "sanction_type": r.sanction_type,
            "sanctioning_authority": r.sanctioning_authority,
            "process_number": r.process_number,
            "start_date": r.start_date.isoformat() if r.start_date else None,
            "end_date": r.end_date.isoformat() if r.end_date else None,
        }
        if r.end_date and r.end_date < today:
            expired_sanctions.append(entry)
        else:
            active_sanctions.append(entry)

    sanctions_section: dict[str, Any] = {
        "active": active_sanctions,
        "expired": expired_sanctions,
        "has_active": len(active_sanctions) > 0,
    }

    # ------------------------------------------------------------------
    # 7. Consumer complaints (consumer_complaints)
    # ------------------------------------------------------------------
    complaint_agg = (await db.execute(text("""
        SELECT
            COUNT(*)                            AS total,
            AVG(satisfaction_rating)             AS avg_satisfaction,
            category,
            COUNT(*) FILTER (WHERE category IS NOT NULL) AS cat_count
        FROM consumer_complaints
        WHERE provider_id = :pid
        GROUP BY category
    """), {"pid": provider_id})).fetchall()

    total_complaints = 0
    all_satisfaction_values: list[float] = []
    by_category: dict[str, int] = {}
    for r in complaint_agg:
        total_complaints += r.total
        if r.avg_satisfaction is not None:
            all_satisfaction_values.extend([float(r.avg_satisfaction)] * r.total)
        if r.category:
            by_category[r.category] = r.total

    avg_satisfaction: float | None = None
    if all_satisfaction_values:
        avg_satisfaction = round(sum(all_satisfaction_values) / len(all_satisfaction_values), 2)

    # Monthly trend (last 12 months)
    trend_rows = (await db.execute(text("""
        SELECT
            TO_CHAR(complaint_date, 'YYYY-MM') AS month,
            COUNT(*)                            AS count,
            AVG(satisfaction_rating)             AS avg_sat
        FROM consumer_complaints
        WHERE provider_id = :pid
          AND complaint_date >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY TO_CHAR(complaint_date, 'YYYY-MM')
        ORDER BY month
    """), {"pid": provider_id})).fetchall()

    monthly_trend = [
        {
            "month": r.month,
            "count": r.count,
            "avg_satisfaction": round(float(r.avg_sat), 2) if r.avg_sat else None,
        }
        for r in trend_rows
    ]

    complaints_section: dict[str, Any] = {
        "total": total_complaints,
        "avg_satisfaction": avg_satisfaction,
        "by_category": by_category,
        "monthly_trend": monthly_trend,
    }

    # ------------------------------------------------------------------
    # 8. Risk summary
    # ------------------------------------------------------------------
    flags: list[str] = []

    if total_debt_brl > 1_000_000:
        flags.append(f"Tax debt > R$1M (R${total_debt_brl:,.2f})")
    elif total_debt_brl > 100_000:
        flags.append(f"Tax debt > R$100K (R${total_debt_brl:,.2f})")

    if total_legal_action > 0:
        flags.append(f"{total_legal_action} debt(s) with legal action")

    if active_sanctions:
        flags.append(f"{len(active_sanctions)} active sanction(s)")

    if avg_satisfaction is not None and avg_satisfaction < 2.5:
        flags.append(f"Low consumer satisfaction ({avg_satisfaction}/5)")

    if total_complaints > 100:
        flags.append(f"High complaint volume ({total_complaints})")

    registration_status = registration_section.get("status", "")
    if registration_status and registration_status.upper() not in ("ATIVA", ""):
        flags.append(f"Company status: {registration_status}")

    # Determine risk level
    if len(flags) >= 3 or any("active sanction" in f for f in flags) or total_debt_brl > 1_000_000:
        risk_level = "high"
    elif len(flags) >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    risk_summary: dict[str, Any] = {
        "level": risk_level,
        "flags": flags,
    }

    # ------------------------------------------------------------------
    # Assemble full dossier
    # ------------------------------------------------------------------
    return {
        "provider": provider_section,
        "subscribers": subscribers_section,
        "registration": registration_section,
        "tax_debts": tax_debts_section,
        "ownership": ownership_section,
        "sanctions": sanctions_section,
        "complaints": complaints_section,
        "risk_summary": risk_summary,
    }


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
