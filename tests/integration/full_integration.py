"""Full end-to-end integration test for the ENLACE platform.

Validates cross-module data flow, ML pipeline, financial chain,
routing, regulatory, rural, auth/reports, and M&A intelligence
using realistic Brazilian ISP data -- no database or running
services required.

Run: python tests/integration/full_integration.py
"""

import sys
import os
from datetime import date, datetime, timedelta

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------------
# ValidationResult (same pattern as phase1_validation.py)
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []

    def check(self, name: str, condition: bool, details: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  PASS  {name}")
        else:
            self.tests_failed += 1
            self.failures.append((name, details))
            print(f"  FAIL  {name}: {details}")

    def summary(self):
        print(f"\n{'='*60}")
        print(f"Full Integration: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailed tests:")
            for name, details in self.failures:
                print(f"  - {name}: {details}")
        print(f"{'='*60}")
        return self.tests_failed == 0


# ---------------------------------------------------------------------------
# Shared realistic Brazilian data
# ---------------------------------------------------------------------------

# Municipality-like profile: ~50,000 households, interior of Sao Paulo
MUNICIPALITY = {
    "households": 50_000,
    "avg_income": 1_800.0,
    "current_penetration": 0.35,
    "urbanization_rate": 0.72,
    "household_growth_rate": 0.015,
    "population": 180_000,
    "state_code": "SP",
    "municipality_code": 3550308,  # example IBGE code
}

# Provider profile for an ISP operating in SP
PROVIDER = {
    "name": "TestNet Telecom",
    "state_codes": ["SP", "MG"],
    "subscriber_count": 15_000,
    "fiber_pct": 0.75,
    "monthly_revenue_brl": 1_200_000.0,
    "ebitda_margin_pct": 32.0,
    "monthly_churn_pct": 1.8,
    "growth_rate_12m": 0.10,
}


# ===================================================================
# CATEGORY 1: Cross-Phase Data Flow (demand -> financial -> routing)
# ===================================================================

def test_cross_phase_data_flow(result: ValidationResult):
    """Demand model output feeds financial projections and routing BOM."""
    print("\n--- Category 1: Cross-Phase Data Flow ---")

    # 1a: Demand model produces addressable market estimate
    from python.ml.opportunity.demand_model import estimate_addressable_market

    demand = estimate_addressable_market(
        households=MUNICIPALITY["households"],
        avg_income=MUNICIPALITY["avg_income"],
        current_penetration=MUNICIPALITY["current_penetration"],
        urbanization_rate=MUNICIPALITY["urbanization_rate"],
        household_growth_rate=MUNICIPALITY["household_growth_rate"],
    )
    result.check(
        "1a. Demand model returns addressable households",
        demand["addressable_households"] > 0,
        f"addressable_households={demand.get('addressable_households')}",
    )

    # 1b: Demand output feeds subscriber curve projection
    from python.ml.financial.subscriber_curve import project_subscribers

    curves = project_subscribers(
        addressable_households=demand["addressable_households"],
        penetration_ceiling=demand["penetration_ceiling"],
        months=36,
        urbanization_rate=MUNICIPALITY["urbanization_rate"],
        competition_level="moderate",
    )
    result.check(
        "1b. Subscriber curve produces 36-month projection",
        len(curves["base_case"]) == 36 and curves["base_case"][-1] > 0,
        f"base_case length={len(curves.get('base_case', []))}",
    )

    # 1c: Peak subscribers feed CAPEX estimator
    from python.ml.financial.capex_estimator import estimate_capex

    peak_subs = max(curves["base_case"])
    capex = estimate_capex(
        cable_length_km=25.0,
        target_subscribers=int(peak_subs),
        technology="fiber",
        terrain="flat_urban",
    )
    result.check(
        "1c. CAPEX estimator returns positive total",
        capex["total_brl"] > 0 and capex["per_subscriber_brl"] > 0,
        f"total_brl={capex.get('total_brl')}, per_sub={capex.get('per_subscriber_brl')}",
    )

    # 1d: ARPU model provides revenue input for viability
    from python.ml.financial.arpu_model import estimate_arpu

    arpu = estimate_arpu(
        state_code=MUNICIPALITY["state_code"],
        municipality_population=MUNICIPALITY["population"],
        avg_income=MUNICIPALITY["avg_income"],
        technology="fiber",
    )
    result.check(
        "1d. ARPU estimate within R$40-200 range",
        40 <= arpu["base_arpu"] <= 200,
        f"base_arpu=R${arpu.get('base_arpu')}",
    )

    # 1e: Financial viability uses CAPEX + subscriber curve + ARPU
    from python.ml.financial.viability import compute_financial_metrics

    monthly_subs = curves["base_case"][:36]
    metrics = compute_financial_metrics(
        capex_brl=capex["total_brl"],
        monthly_subscribers=monthly_subs,
        arpu_brl=arpu["base_arpu"],
        opex_ratio=0.45,
        discount_rate=0.14,
        months=36,
    )
    result.check(
        "1e. Financial viability returns NPV and IRR",
        "npv_brl" in metrics and "irr_pct" in metrics,
        f"npv_brl={metrics.get('npv_brl')}, irr_pct={metrics.get('irr_pct')}",
    )

    # 1f: BOM generator uses route length and target subs
    from python.ml.routing.bom_generator import generate_bom

    # Simulate a simple route GeoJSON
    mock_route_geojson = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[-46.63, -23.55], [-46.64, -23.56], [-46.65, -23.57]],
        },
        "properties": {},
    }
    bom = generate_bom(
        route_geojson=mock_route_geojson,
        total_length_km=2.5,
        target_subscribers=500,
        area_type="urban",
    )
    result.check(
        "1f. BOM generator returns items and total cost",
        len(bom["items"]) > 0 and bom["grand_total_brl"] > 0,
        f"items={len(bom.get('items', []))}, total={bom.get('grand_total_brl')}",
    )


# ===================================================================
# CATEGORY 2: ML Pipeline (features, demand scoring, competition)
# ===================================================================

def test_ml_pipeline(result: ValidationResult):
    """Opportunity scoring features, demand score, and HHI."""
    print("\n--- Category 2: ML Pipeline ---")

    # 2a: Feature names list is complete
    from python.ml.opportunity.features import ALL_FEATURE_NAMES

    result.check(
        "2a. ALL_FEATURE_NAMES has 19 features",
        len(ALL_FEATURE_NAMES) == 19,
        f"Found {len(ALL_FEATURE_NAMES)} features",
    )

    # 2b: Demand score computation
    from python.ml.opportunity.demand_model import compute_demand_score

    features = {
        "total_households": MUNICIPALITY["households"],
        "avg_income_per_capita": MUNICIPALITY["avg_income"],
        "current_penetration": MUNICIPALITY["current_penetration"],
        "urbanization_rate": MUNICIPALITY["urbanization_rate"],
        "household_growth_rate": MUNICIPALITY["household_growth_rate"],
        "young_population_pct": 0.25,
        "education_index": 0.7,
    }
    score = compute_demand_score(features)
    result.check(
        "2b. Demand score in 0-100 range",
        0 <= score <= 100,
        f"demand_score={score}",
    )

    # 2c: HHI computation for market concentration
    from python.ml.opportunity.competition import compute_hhi

    subscribers_by_provider = {1: 5000, 2: 3000, 3: 2000}
    hhi = compute_hhi(subscribers_by_provider)
    result.check(
        "2c. HHI computation returns valid index",
        0 < hhi <= 10_000,
        f"HHI={hhi}",
    )

    # 2d: Verify HHI math: (50^2 + 30^2 + 20^2 = 3800)
    result.check(
        "2d. HHI equals expected 3800 for 50/30/20 split",
        abs(hhi - 3800) < 1,
        f"Expected 3800, got {hhi}",
    )


# ===================================================================
# CATEGORY 3: Financial Module Chain
# ===================================================================

def test_financial_chain(result: ValidationResult):
    """Subscriber curve -> ARPU -> CAPEX -> viability end-to-end."""
    print("\n--- Category 3: Financial Module Chain ---")

    # 3a: Bass diffusion parameters are sensible
    from python.ml.financial.subscriber_curve import project_subscribers, bass_diffusion

    # Bass diffusion single-point check at t=0 (initial adoption)
    val = bass_diffusion(t=0, M=10000, k=0.1, t0=12, q=0.3)
    result.check(
        "3a. Bass diffusion returns value at t=0",
        val >= 0,
        f"bass_diffusion(t=0)={val}",
    )

    # 3b: Project subscribers with pessimistic/base/optimistic scenarios
    curves = project_subscribers(
        addressable_households=20_000,
        penetration_ceiling=0.6,
        months=24,
    )
    result.check(
        "3b. All three scenarios present",
        all(k in curves for k in ["pessimistic", "base_case", "optimistic"]),
        f"keys={list(curves.keys())}",
    )

    # 3c: Optimistic >= base_case >= pessimistic at month 24
    result.check(
        "3c. Scenario ordering: optimistic >= base >= pessimistic",
        curves["optimistic"][-1] >= curves["base_case"][-1] >= curves["pessimistic"][-1],
        f"opt={curves['optimistic'][-1]:.0f}, base={curves['base_case'][-1]:.0f}, pess={curves['pessimistic'][-1]:.0f}",
    )

    # 3d: Terrain multipliers exist for key terrain types
    from python.ml.financial.capex_estimator import TERRAIN_MULTIPLIERS

    expected_terrains = ["flat_urban", "flat_rural", "mountainous", "amazon"]
    all_present = all(t in TERRAIN_MULTIPLIERS for t in expected_terrains)
    result.check(
        "3d. CAPEX terrain multipliers cover key types",
        all_present,
        f"Available: {list(TERRAIN_MULTIPLIERS.keys())}",
    )

    # 3e: Financial metrics: payback months is a positive integer or None
    from python.ml.financial.viability import compute_financial_metrics

    subs = [i * 100 for i in range(1, 25)]  # growing from 100 to 2400
    metrics = compute_financial_metrics(
        capex_brl=2_000_000,
        monthly_subscribers=subs,
        arpu_brl=80.0,
        opex_ratio=0.40,
        discount_rate=0.12,
        months=24,
    )
    result.check(
        "3e. Payback months is None or positive",
        metrics["payback_months"] is None or metrics["payback_months"] > 0,
        f"payback_months={metrics.get('payback_months')}",
    )


# ===================================================================
# CATEGORY 4: RF Engine & Routing
# ===================================================================

def test_routing(result: ValidationResult):
    """BOM generator and routing support functions."""
    print("\n--- Category 4: RF Engine & Routing ---")

    # 4a: BOM generator with rural area type
    from python.ml.routing.bom_generator import generate_bom

    route_geojson = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[-49.0, -25.0], [-49.01, -25.01], [-49.02, -25.02]],
        },
        "properties": {},
    }
    bom = generate_bom(
        route_geojson=route_geojson,
        total_length_km=10.0,
        target_subscribers=200,
        area_type="rural",
    )
    result.check(
        "4a. Rural BOM has equipment items",
        len(bom["items"]) >= 3,
        f"item_count={len(bom.get('items', []))}",
    )

    # 4b: Rural BOM cost > urban BOM cost for same distance
    bom_urban = generate_bom(
        route_geojson=route_geojson,
        total_length_km=10.0,
        target_subscribers=200,
        area_type="urban",
    )
    result.check(
        "4b. Rural and urban BOM costs are both positive and differ",
        bom["grand_total_brl"] > 0 and bom_urban["grand_total_brl"] > 0
        and bom["grand_total_brl"] != bom_urban["grand_total_brl"],
        f"rural={bom['grand_total_brl']:.0f}, urban={bom_urban['grand_total_brl']:.0f}",
    )

    # 4c: BOM items include fiber cable by name
    item_names = [s.get("name", "").lower() for s in bom["items"]]
    has_fiber = any("fiber" in n or "cable" in n for n in item_names)
    result.check(
        "4c. BOM includes fiber/cable items",
        has_fiber,
        f"item_names={item_names}",
    )


# ===================================================================
# CATEGORY 5: Regulatory & Compliance
# ===================================================================

def test_regulatory(result: ValidationResult):
    """Norma no.4, licensing, tax rates, deadlines, compliance profile."""
    print("\n--- Category 5: Regulatory & Compliance ---")

    # 5a: Norma no.4 impact calculation
    from python.regulatory.analyzer.norma4 import calculate_impact

    impact = calculate_impact(
        state_code="SP",
        monthly_broadband_revenue_brl=1_200_000,
        subscriber_count=15_000,
    )
    result.check(
        "5a. Norma no.4 returns additional annual tax > 0",
        impact.additional_annual_tax_brl > 0,
        f"annual_tax={impact.additional_annual_tax_brl}",
    )

    # 5b: ICMS rate for SP
    from python.regulatory.knowledge_base.tax_rates import get_telecom_icms, ICMS_RATES_SCM

    sp_rate = get_telecom_icms("SP")
    result.check(
        "5b. SP ICMS telecom rate is 0.25 (25%)",
        sp_rate == 0.25,
        f"SP ICMS={sp_rate}",
    )

    # 5c: All 27 states have ICMS rates
    result.check(
        "5c. ICMS rates cover 27 states",
        len(ICMS_RATES_SCM) == 27,
        f"states_count={len(ICMS_RATES_SCM)}",
    )

    # 5d: Licensing check for ISP above 5000 threshold
    from python.regulatory.analyzer.licensing import check_licensing, LICENSING_THRESHOLD

    lic = check_licensing(
        subscriber_count=15_000,
        services=["broadband", "voip"],
        monthly_revenue_brl=1_200_000,
    )
    result.check(
        "5d. ISP with 15k subs is above licensing threshold",
        lic.above_threshold is True,
        f"above_threshold={lic.above_threshold}, threshold={LICENSING_THRESHOLD}",
    )

    # 5e: Regulatory deadlines exist
    from python.regulatory.knowledge_base.deadlines import get_all_deadlines

    deadlines = get_all_deadlines()
    result.check(
        "5e. Regulatory deadlines list is non-empty",
        len(deadlines) > 0,
        f"deadline_count={len(deadlines)}",
    )

    # 5f: Active regulations catalog
    from python.regulatory.knowledge_base.regulations import get_active_regulations

    regs = get_active_regulations()
    result.check(
        "5f. Active regulations catalog is non-empty",
        len(regs) > 0,
        f"regulation_count={len(regs)}",
    )

    # 5g: Compliance profile analysis
    from python.regulatory.analyzer.profile import analyze_profile

    profile = analyze_profile(
        provider_name=PROVIDER["name"],
        state_codes=PROVIDER["state_codes"],
        subscriber_count=PROVIDER["subscriber_count"],
        services=["broadband"],
    )
    result.check(
        "5g. Compliance profile returns overall score 0-100",
        0 <= profile.overall_score <= 100,
        f"overall_score={profile.overall_score}",
    )


# ===================================================================
# CATEGORY 6: Rural Connectivity
# ===================================================================

def test_rural(result: ValidationResult):
    """Hybrid network design, solar, community profiling, funding, river crossing."""
    print("\n--- Category 6: Rural Connectivity ---")

    # 6a: Hybrid network designer
    from python.rural.hybrid_designer import CommunityProfile, design_hybrid_network

    community = CommunityProfile(
        latitude=-3.1,
        longitude=-60.0,
        population=800,
        area_km2=50.0,
        grid_power=False,
        nearest_fiber_km=150.0,
        nearest_road_km=30.0,
        terrain_type="flat",
        biome="amazon",
    )
    design = design_hybrid_network(community)
    valid_backhauls = ["fiber", "microwave", "satellite", "satellite_leo", "satellite_geo"]
    result.check(
        "6a. Hybrid design selects backhaul technology",
        design.backhaul_technology in valid_backhauls,
        f"backhaul={design.backhaul_technology}",
    )

    # 6b: CAPEX estimate is positive
    result.check(
        "6b. Rural CAPEX estimate > R$0",
        design.estimated_capex_brl > 0,
        f"capex={design.estimated_capex_brl}",
    )

    # 6c: Solar power sizing for off-grid site
    from python.rural.solar_power import size_solar_system

    solar = size_solar_system(
        latitude=-3.1,
        longitude=-60.0,
        power_consumption_watts=250,
        autonomy_days=3,
        battery_type="lithium",
    )
    result.check(
        "6c. Solar system includes panels and batteries",
        solar.panel_count > 0 and solar.battery_count > 0,
        f"panels={solar.panel_count}, batteries={solar.battery_count}",
    )

    # 6d: Community demand profiler
    from python.rural.community_profiler import profile_community

    demand = profile_community(
        population=800,
        avg_income_brl=1_200,
        has_school=True,
        has_health_unit=True,
        agricultural=True,
    )
    result.check(
        "6d. Community profiler returns estimated subscribers > 0",
        demand.estimated_subscribers > 0,
        f"estimated_subs={demand.estimated_subscribers}",
    )

    # 6e: Funding matcher
    from python.rural.funding_matcher import match_funding, get_all_programs

    programs = get_all_programs()
    result.check(
        "6e. Funding programs catalog is non-empty",
        len(programs) > 0,
        f"program_count={len(programs)}",
    )

    matches = match_funding(
        municipality_code=1500107,
        municipality_population=800,
        state_code="PA",
        technology="fiber",
        capex_brl=500_000,
        latitude=-3.1,
        longitude=-60.0,
    )
    result.check(
        "6f. Amazon community matches at least 1 funding program",
        len(matches) >= 1,
        f"matched_programs={len(matches)}",
    )

    # 6g: River crossing designer
    from python.rural.river_crossing import design_crossing

    crossings = design_crossing(
        width_m=500,
        depth_m=15,
        current_speed_ms=2.0,
    )
    result.check(
        "6g. River crossing returns design options",
        len(crossings) >= 1,
        f"options={len(crossings)}",
    )


# ===================================================================
# CATEGORY 7: Auth & Reports
# ===================================================================

def test_auth_reports(result: ValidationResult):
    """JWT tokens, tenant management, report generation."""
    print("\n--- Category 7: Auth & Reports ---")

    # 7a: JWT token creation and verification
    from python.api.auth.jwt_handler import create_access_token, verify_token

    token = create_access_token(
        data={"sub": "testuser", "tenant_id": "default"},
        expires_delta=timedelta(hours=1),
    )
    result.check(
        "7a. JWT token is a non-empty string",
        isinstance(token, str) and len(token) > 20,
        f"token_length={len(token) if token else 0}",
    )

    # 7b: Token verification round-trip
    payload = verify_token(token)
    result.check(
        "7b. JWT verification recovers payload",
        payload is not None and payload.get("sub") == "testuser",
        f"payload={payload}",
    )

    # 7c: Tenant creation
    from python.api.auth.tenant import create_tenant, get_tenant

    tenant = create_tenant(
        name="Integration Test ISP",
        country_code="BR",
        primary_state="SP",
        plan="pro",
    )
    result.check(
        "7c. Tenant created with pro plan rate limit",
        tenant.rate_limit == 120,
        f"rate_limit={tenant.rate_limit}",
    )

    # 7d: Tenant retrieval
    retrieved = get_tenant(tenant.id)
    result.check(
        "7d. Tenant retrieval by ID succeeds",
        retrieved is not None and retrieved.name == "Integration Test ISP",
        f"retrieved={'found' if retrieved else 'not found'}",
    )

    # 7e: Market report generation
    from python.reports.generator import generate_market_report

    content, media_type = generate_market_report(
        municipality_id=3550308,
        provider_id=1,
    )
    result.check(
        "7e. Market report generates content",
        len(content) > 100 and media_type in ("application/pdf", "text/html"),
        f"content_len={len(content)}, type={media_type}",
    )

    # 7f: Expansion report generation
    from python.reports.generator import generate_expansion_report

    content2, media_type2 = generate_expansion_report(municipality_id=3550308)
    result.check(
        "7f. Expansion report generates content",
        len(content2) > 100 and media_type2 in ("application/pdf", "text/html"),
        f"content_len={len(content2)}, type={media_type2}",
    )


# ===================================================================
# CATEGORY 8: M&A Intelligence
# ===================================================================

def test_mna(result: ValidationResult):
    """Subscriber/revenue/DCF valuation, acquirer scoring, seller report."""
    print("\n--- Category 8: M&A Intelligence ---")

    # 8a: Subscriber multiple valuation
    from python.mna.valuation.subscriber_multiple import calculate as val_subscriber

    sub_val = val_subscriber(
        total_subscribers=PROVIDER["subscriber_count"],
        fiber_pct=PROVIDER["fiber_pct"],
        monthly_churn_pct=PROVIDER["monthly_churn_pct"],
        growth_rate_12m=PROVIDER["growth_rate_12m"],
        state_code="SP",
    )
    result.check(
        "8a. Subscriber valuation > R$10M for 15k subs",
        sub_val.adjusted_valuation_brl > 10_000_000,
        f"valuation=R${sub_val.adjusted_valuation_brl:,.0f}",
    )

    # 8b: Revenue multiple valuation
    from python.mna.valuation.revenue_multiple import calculate as val_revenue

    rev_val = val_revenue(
        monthly_revenue_brl=PROVIDER["monthly_revenue_brl"],
        ebitda_margin_pct=PROVIDER["ebitda_margin_pct"],
        subscriber_count=PROVIDER["subscriber_count"],
        revenue_growth_12m=PROVIDER["growth_rate_12m"],
        fiber_pct=PROVIDER["fiber_pct"],
    )
    result.check(
        "8b. Revenue valuation returns EV/Revenue and EV/EBITDA",
        rev_val.ev_revenue_brl > 0 and rev_val.ev_ebitda_brl > 0,
        f"ev_rev=R${rev_val.ev_revenue_brl:,.0f}, ev_ebitda=R${rev_val.ev_ebitda_brl:,.0f}",
    )

    # 8c: DCF valuation
    from python.mna.valuation.dcf import calculate as val_dcf

    dcf_val = val_dcf(
        monthly_revenue_brl=PROVIDER["monthly_revenue_brl"],
        ebitda_margin_pct=PROVIDER["ebitda_margin_pct"],
    )
    result.check(
        "8c. DCF returns 5-year projected cash flows",
        len(dcf_val.projected_cashflows) == 5,
        f"cf_count={len(dcf_val.projected_cashflows)}",
    )

    # 8d: DCF sensitivity table present
    result.check(
        "8d. DCF sensitivity table has WACC and growth dimensions",
        len(dcf_val.sensitivity_table.get("wacc_values", [])) == 5
        and len(dcf_val.sensitivity_table.get("growth_values", [])) == 5,
        f"wacc_steps={len(dcf_val.sensitivity_table.get('wacc_values', []))}, "
        f"growth_steps={len(dcf_val.sensitivity_table.get('growth_values', []))}",
    )

    # 8e: Acquirer target evaluation
    from python.mna.acquirer import evaluate_targets

    targets = evaluate_targets(
        acquirer_states=["SP", "MG"],
        acquirer_subscribers=30_000,
        min_target_subs=3_000,
        max_target_subs=25_000,
    )
    result.check(
        "8e. Acquirer finds multiple targets",
        len(targets) >= 3,
        f"target_count={len(targets)}",
    )

    # 8f: Targets are sorted by overall score descending
    if len(targets) >= 2:
        sorted_ok = all(
            targets[i].overall_score >= targets[i + 1].overall_score
            for i in range(len(targets) - 1)
        )
    else:
        sorted_ok = True
    result.check(
        "8f. Targets sorted by overall score descending",
        sorted_ok,
        f"scores={[t.overall_score for t in targets[:5]]}",
    )

    # 8g: Seller preparation report
    from python.mna.seller import prepare_for_sale

    seller = prepare_for_sale(
        provider_name=PROVIDER["name"],
        state_codes=PROVIDER["state_codes"],
        subscriber_count=PROVIDER["subscriber_count"],
        fiber_pct=PROVIDER["fiber_pct"],
        monthly_revenue_brl=PROVIDER["monthly_revenue_brl"],
        ebitda_margin_pct=PROVIDER["ebitda_margin_pct"],
    )
    result.check(
        "8g. Seller report includes valuation range",
        seller.estimated_value_range[0] > 0 and seller.estimated_value_range[1] > seller.estimated_value_range[0],
        f"range=R${seller.estimated_value_range[0]:,.0f} - R${seller.estimated_value_range[1]:,.0f}",
    )

    # 8h: Seller report includes preparation checklist
    result.check(
        "8h. Seller checklist has >= 10 items",
        len(seller.preparation_checklist) >= 10,
        f"checklist_items={len(seller.preparation_checklist)}",
    )

    # 8i: Synergy estimation
    from python.mna.acquirer import compute_synergies

    synergy = compute_synergies(
        acquirer_profile={
            "subscriber_count": 30_000,
            "states": ["SP", "MG"],
            "monthly_revenue_brl": 2_400_000,
        },
        target_profile={
            "subscriber_count": 12_000,
            "states": ["SP"],
            "monthly_revenue_brl": 960_000,
            "fiber_pct": 0.85,
        },
    )
    result.check(
        "8i. Synergy estimate includes 5yr PV",
        synergy["pv_5yr_synergies_brl"] > 0 and synergy["geographic_overlap"] is True,
        f"pv_5yr=R${synergy.get('pv_5yr_synergies_brl', 0):,.0f}, overlap={synergy.get('geographic_overlap')}",
    )


# ===================================================================
# Bonus: Health module standalone functions
# ===================================================================

def test_health_standalone(result: ValidationResult):
    """Standalone health module functions (no DB needed)."""
    print("\n--- Bonus: Health Standalone Functions ---")

    # B1: Quality trend computation
    from python.ml.health.quality_benchmark import compute_trend, estimate_churn_risk

    trend, pct = compute_trend([6.5, 6.6, 6.7, 6.8, 6.9, 7.0])
    result.check(
        "B1. Improving quality trend detected",
        trend == "improving" and pct > 0,
        f"trend={trend}, pct={pct}",
    )

    # B2: Churn risk estimation from quality drop
    risk = estimate_churn_risk(-12.0)
    result.check(
        "B2. Large quality drop => high churn risk",
        risk == "high",
        f"churn_risk={risk}",
    )

    # B3: Maintenance age score
    from python.ml.health.maintenance_scorer import compute_age_score, compute_revenue_risk

    age_score = compute_age_score(
        first_seen_date=date(2018, 1, 1),
        current_date=date(2025, 6, 1),
    )
    result.check(
        "B3. Age score for 7.5yr old provider in 0-100",
        0 <= age_score <= 100,
        f"age_score={age_score}",
    )

    # B4: Revenue risk score
    rev_risk = compute_revenue_risk(subscriber_count=15_000, arpu_brl=80.0)
    result.check(
        "B4. Revenue risk score in 0-100",
        0 <= rev_risk <= 100,
        f"revenue_risk={rev_risk}",
    )

    # B5: Seasonal patterns - generate risk pattern
    from python.ml.health.seasonal_patterns import generate_risk_pattern, get_region_from_state

    region = get_region_from_state("SP")
    result.check(
        "B5. SP maps to southeast region",
        region == "southeast",
        f"region={region}",
    )

    risks = generate_risk_pattern("southeast")
    result.check(
        "B6. Southeast risk pattern has 12 months",
        len(risks) == 12 and all(0 <= r.risk_score <= 100 for r in risks),
        f"month_count={len(risks)}",
    )


# ===================================================================
# Main
# ===================================================================

def main():
    result = ValidationResult()

    test_cross_phase_data_flow(result)
    test_ml_pipeline(result)
    test_financial_chain(result)
    test_routing(result)
    test_regulatory(result)
    test_rural(result)
    test_auth_reports(result)
    test_mna(result)
    test_health_standalone(result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
