"""
ENLACE Intelligence Router

Aggregated intelligence endpoints: government contracts, FUST/FUNTTEL spending,
BNDES loans, regulatory acts, gazette mentions, and full municipality profiles.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/intelligence", tags=["intelligence"])


@router.get("/contracts")
async def government_contracts(
    state: Optional[str] = Query(None, description="Filter by state code (e.g. SP)"),
    keyword: Optional[str] = Query(None, description="Search in object description"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Government telecom contracts from PNCP."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("state_code = :state")
        params["state"] = state.upper()
    if keyword:
        where_parts.append("object_description ILIKE :keyword")
        params["keyword"] = f"%{keyword}%"

    where_sql = " AND ".join(where_parts)
    sql = text(f"""
        SELECT id, contracting_entity_name, winner_name, winner_cnpj,
               object_description, value_brl, state_code, published_date, sphere
        FROM government_contracts
        WHERE {where_sql}
        ORDER BY published_date DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "contracting_entity": r.contracting_entity_name,
            "winner": r.winner_name,
            "winner_cnpj": r.winner_cnpj,
            "description": r.object_description,
            "value_brl": float(r.value_brl) if r.value_brl else None,
            "state": r.state_code,
            "date": str(r.published_date) if r.published_date else None,
            "sphere": r.sphere,
        }
        for r in rows
    ]


@router.get("/fust")
async def fust_spending(
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """FUST/FUNTTEL spending from Portal da Transparência."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if year:
        where_parts.append("year = :year")
        params["year"] = year

    where_sql = " AND ".join(where_parts)
    sql = text(f"""
        SELECT year, month, org_name, org_code,
               SUM(value_committed_brl) AS total_committed,
               SUM(value_paid_brl) AS total_paid,
               COUNT(*) AS record_count
        FROM fust_spending
        WHERE {where_sql}
        GROUP BY year, month, org_name, org_code
        ORDER BY year DESC, month DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "year": r.year,
            "month": r.month,
            "org_name": r.org_name,
            "org_code": r.org_code,
            "total_committed_brl": float(r.total_committed) if r.total_committed else 0,
            "total_paid_brl": float(r.total_paid) if r.total_paid else 0,
            "record_count": r.record_count,
        }
        for r in rows
    ]


@router.get("/bndes")
async def bndes_loans(
    state: Optional[str] = Query(None, description="Filter by state"),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """BNDES telecom loans."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"limit": limit}

    if state:
        where_parts.append("""
            l2_id IN (SELECT a2.id FROM admin_level_2 a2
                      JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                      WHERE a1.abbrev = :state)
        """)
        params["state"] = state.upper()
    if provider_id:
        where_parts.append("provider_id = :provider_id")
        params["provider_id"] = provider_id

    where_sql = " AND ".join(where_parts)
    sql = text(f"""
        SELECT id, borrower_name, borrower_cnpj, sector,
               contract_value_brl, disbursed_brl, interest_rate,
               term_months, contract_date
        FROM bndes_loans
        WHERE {where_sql}
        ORDER BY contract_date DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "borrower": r.borrower_name,
            "cnpj": r.borrower_cnpj,
            "sector": r.sector,
            "contract_value_brl": float(r.contract_value_brl) if r.contract_value_brl else 0,
            "disbursed_brl": float(r.disbursed_brl) if r.disbursed_brl else 0,
            "interest_rate": float(r.interest_rate) if r.interest_rate else None,
            "term_months": r.term_months,
            "date": str(r.contract_date) if r.contract_date else None,
        }
        for r in rows
    ]


@router.get("/regulatory-feed")
async def regulatory_feed(
    days: int = Query(30, ge=1, le=365, description="Last N days"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Latest ANATEL regulatory acts from the DOU."""
    sql = text("""
        SELECT id, dou_section, published_date, act_type, title,
               content_summary, keywords, source_url
        FROM regulatory_acts
        WHERE published_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        ORDER BY published_date DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {"days": days, "limit": limit})
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "section": r.dou_section,
            "date": str(r.published_date) if r.published_date else None,
            "type": r.act_type,
            "title": r.title,
            "summary": r.content_summary,
            "keywords": r.keywords or [],
            "url": r.source_url,
        }
        for r in rows
    ]


@router.get("/gazette-mentions")
async def gazette_mentions(
    state: Optional[str] = Query(None, description="Filter by state"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Municipal gazette telecom mentions from Querido Diário."""
    where_parts = ["published_date >= CURRENT_DATE - :days * INTERVAL '1 day'"]
    params: dict[str, Any] = {"days": days, "limit": limit}

    if state:
        where_parts.append("""
            l2_id IN (SELECT a2.id FROM admin_level_2 a2
                      JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                      WHERE a1.abbrev = :state)
        """)
        params["state"] = state.upper()

    where_sql = " AND ".join(where_parts)
    sql = text(f"""
        SELECT mgm.id, mgm.published_date, mgm.mention_type, mgm.excerpt,
               mgm.keywords, mgm.source_url, a2.name AS municipality_name
        FROM municipal_gazette_mentions mgm
        LEFT JOIN admin_level_2 a2 ON mgm.l2_id = a2.id
        WHERE {where_sql}
        ORDER BY mgm.published_date DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "date": str(r.published_date) if r.published_date else None,
            "municipality": r.municipality_name,
            "type": r.mention_type,
            "excerpt": r.excerpt,
            "keywords": r.keywords or [],
            "url": r.source_url,
        }
        for r in rows
    ]


@router.get("/gazette-alerts")
async def gazette_alerts(
    min_score: float = Query(70, ge=0, le=100, description="Minimum opportunity score"),
    days: int = Query(60, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Cross-reference gazette mentions with opportunity scores for actionable alerts.

    Returns gazette mentions in high-opportunity municipalities — these may indicate
    competitor deployments, government investment, or regulatory changes.
    """
    sql = text("""
        SELECT mgm.id, mgm.published_date, mgm.mention_type, mgm.excerpt,
               mgm.keywords, mgm.source_url,
               a2.name AS municipality_name,
               a1.abbrev AS state_abbrev,
               os.composite_score,
               os.demand_score,
               (CURRENT_DATE - mgm.published_date) AS days_ago
        FROM municipal_gazette_mentions mgm
        JOIN admin_level_2 a2 ON mgm.l2_id = a2.id
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        JOIN opportunity_scores os ON os.geographic_id = a2.code
        WHERE mgm.published_date >= CURRENT_DATE - :days * INTERVAL '1 day'
          AND os.composite_score >= :min_score
        ORDER BY os.composite_score DESC, mgm.published_date DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, {"days": days, "min_score": min_score, "limit": limit})
    rows = result.fetchall()

    return [
        {
            "id": r.id,
            "date": str(r.published_date) if r.published_date else None,
            "municipality": r.municipality_name,
            "state": r.state_abbrev,
            "type": r.mention_type,
            "excerpt": r.excerpt[:300] if r.excerpt else None,
            "keywords": r.keywords or [],
            "url": r.source_url,
            "opportunity_score": float(r.composite_score) if r.composite_score else 0,
            "demand_score": float(r.demand_score) if r.demand_score else None,
            "days_ago": int(r.days_ago) if r.days_ago else None,
        }
        for r in rows
    ]


@router.get("/{municipality_id}/fusion")
async def municipality_fusion(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Fused intelligence brief combining ALL domains for a municipality.

    Aggregates opportunity scores, infrastructure gaps, economic signals,
    regulatory climate, competition, and safety into one response.
    """
    fusion: dict[str, Any] = {"municipality_id": municipality_id}

    # Municipality basic info
    r = await db.execute(text("""
        SELECT a2.name, a1.abbrev AS state, a2.population
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE a2.id = :id
    """), {"id": municipality_id})
    info = r.fetchone()
    if not info:
        raise HTTPException(status_code=404, detail="Municipality not found")
    fusion["name"] = info.name
    fusion["state"] = info.state
    fusion["population"] = info.population

    # Opportunity score + sub-scores + features
    r = await db.execute(text("""
        SELECT os.composite_score, os.demand_score, os.competition_score,
               os.infrastructure_score, os.growth_score, os.features, os.confidence,
               RANK() OVER (ORDER BY os.composite_score DESC) AS rank
        FROM opportunity_scores os
        JOIN admin_level_2 a2 ON os.geographic_id = a2.code
        WHERE a2.id = :id
    """), {"id": municipality_id})
    os_row = r.fetchone()
    if os_row:
        features = os_row.features if isinstance(os_row.features, dict) else {}
        fusion["opportunity"] = {
            "score": float(os_row.composite_score) if os_row.composite_score else 0,
            "rank": int(os_row.rank),
            "sub_scores": {
                "demand": float(os_row.demand_score) if os_row.demand_score else 0,
                "competition": float(os_row.competition_score) if os_row.competition_score else 0,
                "infrastructure": float(os_row.infrastructure_score) if os_row.infrastructure_score else 0,
                "growth": float(os_row.growth_score) if os_row.growth_score else 0,
                "social": features.get("social_score"),
            },
            "details": features,
        }
    else:
        fusion["opportunity"] = None

    # Infrastructure gaps
    r = await db.execute(text("""
        SELECT has_fiber_backhaul, dominant_technology
        FROM backhaul_presence WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bh = r.fetchone()

    r = await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline, COUNT(*) AS total
        FROM schools WHERE l2_id = :id
    """), {"id": municipality_id})
    sc = r.fetchone()

    r = await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline, COUNT(*) AS total
        FROM health_facilities WHERE l2_id = :id
    """), {"id": municipality_id})
    hf = r.fetchone()

    r = await db.execute(text("""
        SELECT density_per_km2 FROM building_density
        WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bd = r.fetchone()

    fusion["infrastructure"] = {
        "backhaul": bh.dominant_technology if bh else "none",
        "has_fiber": bh.has_fiber_backhaul if bh else False,
        "schools_offline": sc.offline if sc else 0,
        "schools_total": sc.total if sc else 0,
        "health_offline": hf.offline if hf else 0,
        "health_total": hf.total if hf else 0,
        "building_density_km2": float(bd.density_per_km2) if bd and bd.density_per_km2 else None,
    }

    # Economic signals
    r = await db.execute(text("""
        SELECT formal_jobs_total, formal_jobs_telecom, net_hires, avg_salary_brl
        FROM employment_indicators WHERE l2_id = :id
        ORDER BY year DESC, month DESC LIMIT 1
    """), {"id": municipality_id})
    emp = r.fetchone()

    r = await db.execute(text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(value_brl), 0) AS total_value
        FROM government_contracts
        WHERE l2_id = :id AND published_date > CURRENT_DATE - INTERVAL '12 months'
    """), {"id": municipality_id})
    gc = r.fetchone()

    r = await db.execute(text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(contract_value_brl), 0) AS total_value
        FROM bndes_loans WHERE l2_id = :id
    """), {"id": municipality_id})
    bn = r.fetchone()

    fusion["economic"] = {
        "formal_jobs": emp.formal_jobs_total if emp else None,
        "telecom_jobs": emp.formal_jobs_telecom if emp else None,
        "net_hires": emp.net_hires if emp else None,
        "avg_salary_brl": float(emp.avg_salary_brl) if emp and emp.avg_salary_brl else None,
        "government_contracts_12m": gc.cnt if gc else 0,
        "contract_value_total_brl": float(gc.total_value) if gc else 0,
        "bndes_loans_active": bn.cnt if bn else 0,
        "bndes_total_brl": float(bn.total_value) if bn else 0,
    }

    # Regulatory climate
    r = await db.execute(text("""
        SELECT has_plano_diretor, has_building_code, has_zoning_law, has_digital_governance
        FROM municipal_planning WHERE l2_id = :id ORDER BY munic_year DESC LIMIT 1
    """), {"id": municipality_id})
    mp = r.fetchone()

    r = await db.execute(text("""
        SELECT COUNT(*) AS cnt,
               array_agg(DISTINCT mention_type) FILTER (WHERE mention_type IS NOT NULL) AS types
        FROM municipal_gazette_mentions
        WHERE l2_id = :id AND published_date > CURRENT_DATE - INTERVAL '6 months'
    """), {"id": municipality_id})
    gm = r.fetchone()

    # Determine regulatory risk
    reg_risk = "medium"
    if mp and mp.has_plano_diretor and mp.has_building_code:
        reg_risk = "low"
    elif not mp or not mp.has_plano_diretor:
        reg_risk = "high"

    fusion["regulatory"] = {
        "has_plano_diretor": mp.has_plano_diretor if mp else False,
        "has_building_code": mp.has_building_code if mp else False,
        "has_zoning_law": mp.has_zoning_law if mp else False,
        "has_digital_governance": mp.has_digital_governance if mp else False,
        "recent_gazette_mentions": gm.cnt if gm else 0,
        "mention_types": list(gm.types) if gm and gm.types else [],
        "regulatory_risk": reg_risk,
    }

    # Competition
    r = await db.execute(text("""
        SELECT hhi_index, leader_market_share, provider_details,
               growth_trend, threat_level
        FROM competitive_analysis WHERE l2_id = :id
        ORDER BY year_month DESC LIMIT 1
    """), {"id": municipality_id})
    ca = r.fetchone()

    r = await db.execute(text("""
        SELECT provider_count, fiber_share_pct
        FROM mv_market_summary WHERE l2_id = :id
    """), {"id": municipality_id})
    ms = r.fetchone()

    r = await db.execute(text("""
        SELECT AVG(overall_score) AS avg_score
        FROM quality_seals WHERE l2_id = :id
    """), {"id": municipality_id})
    qs = r.fetchone()

    fusion["competition"] = {
        "provider_count": ms.provider_count if ms else 0,
        "hhi": round(ca.hhi_index, 0) if ca and ca.hhi_index else None,
        "leader_market_share": round(ca.leader_market_share, 1) if ca and ca.leader_market_share else None,
        "growth_trend": ca.growth_trend if ca else None,
        "threat_level": ca.threat_level if ca else None,
        "avg_quality_score": round(float(qs.avg_score), 1) if qs and qs.avg_score else None,
        "fiber_share_pct": round(float(ms.fiber_share_pct), 1) if ms and ms.fiber_share_pct else None,
    }

    # Safety
    r = await db.execute(text("""
        SELECT risk_score, homicide_rate FROM safety_indicators
        WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    sf = r.fetchone()
    fusion["safety"] = {
        "risk_score": float(sf.risk_score) if sf and sf.risk_score else None,
        "homicide_rate": float(sf.homicide_rate) if sf and sf.homicide_rate else None,
    }

    # Generate recommendation
    score = fusion["opportunity"]["score"] if fusion["opportunity"] else 0
    infra = fusion["infrastructure"]
    econ = fusion["economic"]
    comp = fusion["competition"]

    signals = []
    if score >= 75:
        signals.append("High opportunity score")
    if infra.get("building_density_km2") and infra["building_density_km2"] > 500 and not infra["has_fiber"]:
        signals.append("Dense underserved area")
    if econ.get("government_contracts_12m", 0) > 0:
        signals.append("Government investment active")
    if comp.get("avg_quality_score") and comp["avg_quality_score"] < 50:
        signals.append("Weak incumbents")
    if reg_risk == "low":
        signals.append("Favorable regulatory environment")
    if infra.get("schools_offline", 0) > 5:
        signals.append("School connectivity gap")

    if len(signals) >= 4:
        priority = "HIGH PRIORITY"
    elif len(signals) >= 2:
        priority = "MEDIUM PRIORITY"
    else:
        priority = "LOW PRIORITY"

    fusion["recommendation"] = f"{priority} — {', '.join(signals)}" if signals else "Insufficient data for recommendation"

    return fusion


@router.get("/{municipality_id}/funding-eligibility")
async def funding_eligibility(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Funding program eligibility based on infrastructure gaps and demographics.

    Matches municipality characteristics against federal funding program criteria.
    """
    programs: list[dict[str, Any]] = []

    # Get municipality data
    r = await db.execute(text("""
        SELECT a2.name, a1.abbrev AS state, a1.name AS region_name,
               a2.population
        FROM admin_level_2 a2
        JOIN admin_level_1 a1 ON a2.l1_id = a1.id
        WHERE a2.id = :id
    """), {"id": municipality_id})
    info = r.fetchone()
    if not info:
        raise HTTPException(status_code=404, detail="Municipality not found")

    population = info.population or 0
    state = info.state

    # Schools offline
    r = await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline, COUNT(*) AS total
        FROM schools WHERE l2_id = :id
    """), {"id": municipality_id})
    sc = r.fetchone()
    schools_offline = sc.offline if sc else 0

    # Health facilities offline
    r = await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE NOT has_internet) AS offline
        FROM health_facilities WHERE l2_id = :id
    """), {"id": municipality_id})
    hf = r.fetchone()
    health_offline = hf.offline if hf else 0

    # Backhaul
    r = await db.execute(text("""
        SELECT has_fiber_backhaul FROM backhaul_presence
        WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bh = r.fetchone()
    has_fiber = bh.has_fiber_backhaul if bh else False

    # BNDES history
    r = await db.execute(text("""
        SELECT COUNT(*) AS cnt FROM bndes_loans WHERE l2_id = :id
    """), {"id": municipality_id})
    bn = r.fetchone()
    has_bndes_history = (bn.cnt if bn else 0) > 0

    # WiFi Brasil / GESAC — schools without internet
    if schools_offline >= 5:
        programs.append({
            "program": "WiFi Brasil / GESAC",
            "description": "Conectividade para escolas públicas sem internet",
            "eligible": True,
            "reason": f"{schools_offline} escolas sem internet no município",
            "estimated_value_brl": schools_offline * 15000,
            "requirements": ["Escola pública", "Sem conectividade", "Cadastro no MEC"],
        })

    # FUST backbone — no fiber backhaul
    if not has_fiber:
        programs.append({
            "program": "FUST - Backbone",
            "description": "Financiamento para infraestrutura de backbone fibra óptica",
            "eligible": True,
            "reason": "Município sem backhaul de fibra óptica",
            "estimated_value_brl": 500000,
            "requirements": ["Operadora autorizada SCM", "Projeto técnico", "Contrapartida financeira"],
        })

    # Norte Conectado / PAC — small municipalities
    if population < 30000:
        programs.append({
            "program": "Norte Conectado / PAC Digital",
            "description": "Programa para municípios com menos de 30 mil habitantes",
            "eligible": True,
            "reason": f"População de {population:,} (< 30.000)",
            "estimated_value_brl": 200000,
            "requirements": ["População < 30.000", "Projeto de conectividade", "Adesão municipal"],
        })

    # Telessaúde — health facilities offline
    if health_offline >= 3:
        programs.append({
            "program": "Telessaúde / RUTE",
            "description": "Conectividade para unidades de saúde do SUS",
            "eligible": True,
            "reason": f"{health_offline} unidades de saúde sem internet",
            "estimated_value_brl": health_offline * 10000,
            "requirements": ["Unidade SUS", "Sem conectividade", "Cadastro no CNES"],
        })

    # BNDES credit line
    programs.append({
        "program": "BNDES Telecom",
        "description": "Linha de crédito para investimentos em telecomunicações",
        "eligible": True,
        "reason": "Linha de crédito disponível para operadoras" + (" (histórico de crédito existente)" if has_bndes_history else ""),
        "estimated_value_brl": None,
        "requirements": ["CNPJ ativo", "Certidões negativas", "Projeto de investimento"],
        "has_credit_history": has_bndes_history,
    })

    return {
        "municipality_id": municipality_id,
        "municipality_name": info.name,
        "state": state,
        "population": population,
        "programs": programs,
        "total_eligible": len([p for p in programs if p["eligible"]]),
        "total_estimated_brl": sum(p.get("estimated_value_brl") or 0 for p in programs),
    }


@router.get("/{municipality_id}/profile")
async def municipality_profile(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Full enrichment profile aggregating ALL new data for a municipality."""
    profile: dict[str, Any] = {"municipality_id": municipality_id}

    # Backhaul status
    r = await db.execute(text("""
        SELECT has_fiber_backhaul, has_radio_backhaul, has_satellite_backhaul,
               dominant_technology, provider_count
        FROM backhaul_presence WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bh = r.fetchone()
    profile["backhaul"] = {
        "has_fiber": bh.has_fiber_backhaul,
        "has_radio": bh.has_radio_backhaul,
        "has_satellite": bh.has_satellite_backhaul,
        "dominant": bh.dominant_technology,
        "providers": bh.provider_count,
    } if bh else None

    # School connectivity gaps
    r = await db.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE has_internet = false) AS without_internet,
               SUM(student_count) FILTER (WHERE has_internet = false) AS students_offline,
               COUNT(*) FILTER (WHERE rural = true) AS rural_schools
        FROM schools WHERE l2_id = :id
    """), {"id": municipality_id})
    sc = r.fetchone()
    profile["schools"] = {
        "total": sc.total,
        "without_internet": sc.without_internet,
        "students_offline": int(sc.students_offline or 0),
        "rural_schools": sc.rural_schools,
    } if sc and sc.total > 0 else None

    # Health facilities
    r = await db.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE has_internet = false) AS without_internet,
               SUM(bed_count) AS total_beds,
               COUNT(*) FILTER (WHERE sus_contract = true) AS sus_facilities
        FROM health_facilities WHERE l2_id = :id
    """), {"id": municipality_id})
    hf = r.fetchone()
    profile["health_facilities"] = {
        "total": hf.total,
        "without_internet": hf.without_internet,
        "total_beds": int(hf.total_beds or 0),
        "sus_facilities": hf.sus_facilities,
    } if hf and hf.total > 0 else None

    # Employment indicators
    r = await db.execute(text("""
        SELECT formal_jobs_total, formal_jobs_telecom, avg_salary_brl, net_hires
        FROM employment_indicators WHERE l2_id = :id
        ORDER BY year DESC, month DESC LIMIT 1
    """), {"id": municipality_id})
    emp = r.fetchone()
    profile["employment"] = {
        "formal_jobs": emp.formal_jobs_total,
        "telecom_jobs": emp.formal_jobs_telecom,
        "avg_salary_brl": float(emp.avg_salary_brl) if emp.avg_salary_brl else None,
        "net_hires": emp.net_hires,
    } if emp else None

    # Safety
    r = await db.execute(text("""
        SELECT homicide_rate, risk_score FROM safety_indicators
        WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    sf = r.fetchone()
    profile["safety"] = {
        "homicide_rate": float(sf.homicide_rate) if sf.homicide_rate else None,
        "risk_score": float(sf.risk_score) if sf.risk_score else None,
    } if sf else None

    # Quality seals for incumbents
    r = await db.execute(text("""
        SELECT p.name, qs.overall_score, qs.seal_level
        FROM quality_seals qs
        JOIN providers p ON qs.provider_id = p.id
        WHERE qs.l2_id = :id
        ORDER BY qs.overall_score DESC LIMIT 10
    """), {"id": municipality_id})
    profile["quality_seals"] = [
        {"provider": row.name, "score": float(row.overall_score) if row.overall_score else None,
         "seal": row.seal_level}
        for row in r.fetchall()
    ]

    # Planning status
    r = await db.execute(text("""
        SELECT has_plano_diretor, has_zoning_law, has_building_code, has_digital_governance
        FROM municipal_planning WHERE l2_id = :id ORDER BY munic_year DESC LIMIT 1
    """), {"id": municipality_id})
    mp = r.fetchone()
    profile["planning"] = {
        "plano_diretor": mp.has_plano_diretor,
        "zoning_law": mp.has_zoning_law,
        "building_code": mp.has_building_code,
        "digital_governance": mp.has_digital_governance,
    } if mp else None

    # Building density
    r = await db.execute(text("""
        SELECT total_addresses, residential_addresses, density_per_km2,
               urban_addresses, rural_addresses
        FROM building_density WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bd = r.fetchone()
    profile["building_density"] = {
        "total": bd.total_addresses,
        "residential": bd.residential_addresses,
        "density_km2": float(bd.density_per_km2) if bd.density_per_km2 else None,
        "urban": bd.urban_addresses,
        "rural": bd.rural_addresses,
    } if bd else None

    # Recent government contracts won by local ISPs
    r = await db.execute(text("""
        SELECT winner_name, object_description, value_brl, published_date
        FROM government_contracts WHERE l2_id = :id
        ORDER BY published_date DESC LIMIT 5
    """), {"id": municipality_id})
    profile["recent_contracts"] = [
        {"winner": row.winner_name, "description": row.object_description,
         "value_brl": float(row.value_brl) if row.value_brl else None,
         "date": str(row.published_date) if row.published_date else None}
        for row in r.fetchall()
    ]

    # Recent gazette mentions
    r = await db.execute(text("""
        SELECT published_date, mention_type, excerpt
        FROM municipal_gazette_mentions WHERE l2_id = :id
        ORDER BY published_date DESC LIMIT 5
    """), {"id": municipality_id})
    profile["gazette_mentions"] = [
        {"date": str(row.published_date) if row.published_date else None,
         "type": row.mention_type, "excerpt": row.excerpt[:200]}
        for row in r.fetchall()
    ]

    return profile


@router.get("/{municipality_id}/infrastructure-gaps")
async def infrastructure_gaps(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Infrastructure gap analysis: backhaul + school + health facility gaps."""
    gaps: dict[str, Any] = {"municipality_id": municipality_id}

    # Backhaul
    r = await db.execute(text("""
        SELECT has_fiber_backhaul, has_radio_backhaul, dominant_technology
        FROM backhaul_presence WHERE l2_id = :id ORDER BY year DESC LIMIT 1
    """), {"id": municipality_id})
    bh = r.fetchone()
    gaps["backhaul"] = {
        "has_fiber": bh.has_fiber_backhaul if bh else False,
        "has_radio": bh.has_radio_backhaul if bh else False,
        "dominant": bh.dominant_technology if bh else "none",
        "gap_severity": "critical" if (not bh or not bh.has_fiber_backhaul) else "none",
    }

    # Schools without internet
    r = await db.execute(text("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE NOT has_internet) AS offline
        FROM schools WHERE l2_id = :id
    """), {"id": municipality_id})
    sc = r.fetchone()
    gaps["schools"] = {
        "total": sc.total if sc else 0,
        "without_internet": sc.offline if sc else 0,
        "gap_pct": round((sc.offline / max(sc.total, 1)) * 100, 1) if sc else 0,
    }

    # Health facilities without internet
    r = await db.execute(text("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE NOT has_internet) AS offline
        FROM health_facilities WHERE l2_id = :id
    """), {"id": municipality_id})
    hf = r.fetchone()
    gaps["health_facilities"] = {
        "total": hf.total if hf else 0,
        "without_internet": hf.offline if hf else 0,
        "gap_pct": round((hf.offline / max(hf.total, 1)) * 100, 1) if hf else 0,
    }

    return gaps
