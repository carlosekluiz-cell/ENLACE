"""Phase 3 Regulatory + Fault Intelligence Validation Tests.

Tests validate regulatory knowledge base, Norma no. 4 calculator,
ISP profile analyzer, fault intelligence modules, compliance API
endpoints, and cross-module integration.

Run: python tests/validation/phase3_validation.py
"""
import os
import sys

# Ensure the project root is on sys.path so imports resolve
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import psycopg2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "enlace"),
    "user": os.getenv("DB_USER", "enlace"),
    "password": os.getenv("DB_PASSWORD", "enlace_dev_2026"),
}


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
        print(f"Phase 3 Validation: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailed tests:")
            for name, details in self.failures:
                print(f"  - {name}: {details}")
        print(f"{'='*60}")
        return self.tests_failed == 0


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ===================================================================
# Category 1: Regulatory Knowledge Base (5 checks)
# ===================================================================

def test_1_regulatory_knowledge_base(result: ValidationResult):
    """Category 1: Regulatory Knowledge Base."""
    print("\nCategory 1: Regulatory Knowledge Base")

    from python.regulatory.knowledge_base.tax_rates import (
        ICMS_RATES_SCM,
        ALL_STATE_CODES,
    )

    # Check 1: ICMS rates complete — all 27 states have telecom ICMS rates
    all_27 = len(ALL_STATE_CODES) == 27
    all_have_telecom = all(
        "telecom" in ICMS_RATES_SCM[code] for code in ALL_STATE_CODES
    )
    result.check(
        "1. ICMS rates complete (27 states with telecom rates)",
        all_27 and all_have_telecom,
        f"states={len(ALL_STATE_CODES)}, all_have_telecom={all_have_telecom}",
    )

    # Check 2: ICMS rate validity — all rates between 0 and 1
    rates_valid = all(
        0 < ICMS_RATES_SCM[code]["telecom"] < 1
        for code in ALL_STATE_CODES
    )
    if not rates_valid:
        bad = [
            (code, ICMS_RATES_SCM[code]["telecom"])
            for code in ALL_STATE_CODES
            if not (0 < ICMS_RATES_SCM[code]["telecom"] < 1)
        ]
        result.check(
            "2. ICMS rate validity (all between 0 and 1)",
            False,
            f"Invalid rates: {bad}",
        )
    else:
        result.check(
            "2. ICMS rate validity (all between 0 and 1)",
            True,
        )

    # Check 3: Regulations populated — at least 5 regulations
    from python.regulatory.knowledge_base.regulations import REGULATIONS
    reg_count = len(REGULATIONS)
    result.check(
        "3. Regulations populated (>= 5)",
        reg_count >= 5,
        f"Found {reg_count} regulations",
    )

    # Check 4: Deadlines exist — at least 3 upcoming deadlines within 730 days
    from python.regulatory.knowledge_base.deadlines import get_upcoming_deadlines
    upcoming = get_upcoming_deadlines(within_days=730)
    result.check(
        "4. Upcoming deadlines (>= 3 within 730 days)",
        len(upcoming) >= 3,
        f"Found {len(upcoming)} upcoming deadlines",
    )

    # Check 5: State rates ordering — GO and PR (29%) > SP (25%) >= RS/SC (25%)
    go_rate = ICMS_RATES_SCM["GO"]["telecom"]
    pr_rate = ICMS_RATES_SCM["PR"]["telecom"]
    sp_rate = ICMS_RATES_SCM["SP"]["telecom"]
    rs_rate = ICMS_RATES_SCM["RS"]["telecom"]
    sc_rate = ICMS_RATES_SCM["SC"]["telecom"]

    ordering_ok = (
        go_rate > sp_rate
        and pr_rate > sp_rate
        and sp_rate >= rs_rate
        and sp_rate >= sc_rate
    )
    result.check(
        "5. State rates ordering (GO,PR > SP >= RS,SC)",
        ordering_ok,
        f"GO={go_rate}, PR={pr_rate}, SP={sp_rate}, RS={rs_rate}, SC={sc_rate}",
    )


# ===================================================================
# Category 2: Norma No. 4 Calculator (4 checks)
# ===================================================================

def test_2_norma4_calculator(result: ValidationResult):
    """Category 2: Norma No. 4 Calculator."""
    print("\nCategory 2: Norma No. 4 Calculator")

    from python.regulatory.analyzer.norma4 import (
        calculate_impact,
        calculate_multi_state_impact,
    )

    # Check 6: SP example — R$267k revenue -> ~R$66,750/month additional ICMS
    try:
        impact = calculate_impact(
            state_code="SP",
            monthly_broadband_revenue_brl=267_000,
            subscriber_count=3000,
            current_classification="SVA",
        )
        expected = 267_000 * 0.25  # 25% ICMS
        tolerance = 1.0  # R$1 tolerance for rounding
        close_enough = abs(impact.additional_monthly_tax_brl - expected) < tolerance
        result.check(
            "6. SP example (R$267k -> ~R$66,750/month ICMS)",
            close_enough,
            f"Expected ~{expected:.2f}, got {impact.additional_monthly_tax_brl:.2f}",
        )
    except Exception as exc:
        result.check("6. SP example", False, str(exc))

    # Check 7: Restructuring options — at least 3 options returned with scores
    try:
        options = impact.restructuring_options
        has_enough = len(options) >= 3
        all_scored = all("score" in o for o in options)
        result.check(
            "7. Restructuring options (>= 3 with scores)",
            has_enough and all_scored,
            f"Found {len(options)} options, all_scored={all_scored}",
        )
    except Exception as exc:
        result.check("7. Restructuring options", False, str(exc))

    # Check 8: Multi-state — aggregate is sum of individual state impacts
    try:
        state_revenues = {"SP": 200_000, "RJ": 100_000}
        multi = calculate_multi_state_impact(
            state_revenues=state_revenues,
            subscriber_count=3000,
            current_classification="SVA",
        )

        # Compute individual totals
        sp_impact = calculate_impact("SP", 200_000, 2000, "SVA")
        rj_impact = calculate_impact("RJ", 100_000, 1000, "SVA")
        expected_total = sp_impact.additional_monthly_tax_brl + rj_impact.additional_monthly_tax_brl

        # Allow small tolerance for rounding in subscriber distribution
        close = abs(multi["total_monthly_tax_brl"] - expected_total) < 10
        result.check(
            "8. Multi-state aggregate (sum of individual impacts)",
            close,
            f"Multi-state total={multi['total_monthly_tax_brl']:.2f}, "
            f"sum of individuals={expected_total:.2f}",
        )
    except Exception as exc:
        result.check("8. Multi-state aggregate", False, str(exc))

    # Check 9: Edge case — 0 revenue returns 0 tax impact
    try:
        zero_impact = calculate_impact("SP", 0, 0, "SVA")
        result.check(
            "9. Edge case (0 revenue -> 0 tax impact)",
            zero_impact.additional_monthly_tax_brl == 0.0,
            f"Got {zero_impact.additional_monthly_tax_brl}",
        )
    except Exception as exc:
        result.check("9. Edge case (0 revenue)", False, str(exc))


# ===================================================================
# Category 3: ISP Profile Analyzer (3 checks)
# ===================================================================

def test_3_profile_analyzer(result: ValidationResult):
    """Category 3: ISP Profile Analyzer."""
    print("\nCategory 3: ISP Profile Analyzer")

    from python.regulatory.analyzer.profile import analyze_profile

    # Check 10: Profile returns checks — at least 5 compliance checks
    try:
        profile = analyze_profile(
            provider_name="Test ISP",
            state_codes=["SP"],
            subscriber_count=3000,
            services=["SCM", "broadband"],
            current_classification="SVA",
            monthly_revenue_brl=267_000,
        )
        check_count = len(profile.checks)
        result.check(
            "10. Profile returns checks (>= 5)",
            check_count >= 5,
            f"Found {check_count} compliance checks",
        )
    except Exception as exc:
        result.check("10. Profile returns checks", False, str(exc))

    # Check 11: Score range — overall_score is 0-100
    try:
        score_ok = 0 <= profile.overall_score <= 100
        result.check(
            "11. Overall score range (0-100)",
            score_ok,
            f"Score={profile.overall_score}",
        )
    except Exception as exc:
        result.check("11. Overall score range", False, str(exc))

    # Check 12: Small ISP at threshold — subscriber_count=4900 triggers licensing warning
    try:
        near_threshold = analyze_profile(
            provider_name="Small ISP Near Threshold",
            state_codes=["SP"],
            subscriber_count=4900,
            services=["SCM"],
            current_classification="SVA",
        )
        # Find the licensing check (res614)
        lic_checks = [c for c in near_threshold.checks if c.regulation_id == "res614"]
        has_lic_check = len(lic_checks) > 0
        if has_lic_check:
            lic_status = lic_checks[0].status
            lic_description = lic_checks[0].description
            # At 4900 subs (98% of 5000), should trigger approaching/at_risk warning
            is_warning = lic_status in ("at_risk", "non_compliant")
            result.check(
                "12. Near-threshold licensing warning (4900 subs)",
                is_warning,
                f"status={lic_status}, desc={lic_description[:100]}",
            )
        else:
            result.check("12. Near-threshold licensing warning", False, "No res614 check found")
    except Exception as exc:
        result.check("12. Near-threshold licensing warning", False, str(exc))


# ===================================================================
# Category 4: Fault Intelligence (5 checks)
# ===================================================================

def test_4_fault_intelligence(result: ValidationResult):
    """Category 4: Fault Intelligence."""
    print("\nCategory 4: Fault Intelligence")

    # Check 13: Weather risk returns valid — risk_score 0-100
    try:
        from python.ml.health.weather_correlation import compute_weather_risk

        risk = compute_weather_risk(municipality_id=1)
        score_ok = 0 <= risk.overall_risk_score <= 100
        has_fields = (
            hasattr(risk, "precipitation_risk")
            and hasattr(risk, "wind_risk")
            and hasattr(risk, "temperature_risk")
        )
        result.check(
            "13. Weather risk valid (score 0-100, has risk fields)",
            score_ok and has_fields,
            f"score={risk.overall_risk_score}, precip={risk.precipitation_risk}, "
            f"wind={risk.wind_risk}, temp={risk.temperature_risk}",
        )
    except Exception as exc:
        result.check("13. Weather risk valid", False, str(exc))

    # Check 14: Quality benchmark callable and returns valid structure
    try:
        from python.ml.health.quality_benchmark import benchmark_quality

        is_callable = callable(benchmark_quality)
        # Call with a provider that may not exist — should return empty list gracefully
        benchmarks = benchmark_quality(provider_id=1, municipality_id=1)
        is_list = isinstance(benchmarks, list)
        result.check(
            "14. Quality benchmark (callable, returns list)",
            is_callable and is_list,
            f"callable={is_callable}, returns_list={is_list}, len={len(benchmarks)}",
        )
    except Exception as exc:
        result.check("14. Quality benchmark", False, str(exc))

    # Check 15: Maintenance priorities returns list
    try:
        from python.ml.health.maintenance_scorer import compute_maintenance_priorities

        is_callable = callable(compute_maintenance_priorities)
        priorities = compute_maintenance_priorities(provider_id=1)
        is_list = isinstance(priorities, list)
        result.check(
            "15. Maintenance priorities (callable, returns list)",
            is_callable and is_list,
            f"callable={is_callable}, returns_list={is_list}, len={len(priorities)}",
        )
    except Exception as exc:
        result.check("15. Maintenance priorities", False, str(exc))

    # Check 16: Seasonal calendar returns 12 months
    try:
        from python.ml.health.seasonal_patterns import generate_seasonal_calendar

        cal = generate_seasonal_calendar(municipality_id=1)
        has_12 = len(cal.months) == 12
        all_scored = all(
            0 <= m.risk_score <= 100 for m in cal.months
        )
        result.check(
            "16. Seasonal calendar (12 months, scores 0-100)",
            has_12 and all_scored,
            f"months={len(cal.months)}, all_scored={all_scored}",
        )
    except Exception as exc:
        result.check("16. Seasonal calendar", False, str(exc))

    # Check 17: Region mapping — all 27 states map to valid regions
    try:
        from python.ml.health.seasonal_patterns import REGION_MAP, get_region_from_state

        valid_regions = {"north", "northeast", "southeast", "south", "central-west"}
        has_27 = len(REGION_MAP) == 27
        all_valid = all(
            get_region_from_state(code) in valid_regions
            for code in REGION_MAP.keys()
        )
        result.check(
            "17. Region mapping (27 states, all valid regions)",
            has_27 and all_valid,
            f"states_mapped={len(REGION_MAP)}, all_valid_regions={all_valid}",
        )
    except Exception as exc:
        result.check("17. Region mapping", False, str(exc))


# ===================================================================
# Category 5: API Endpoints (5 checks)
# ===================================================================

def test_5_api_endpoints(result: ValidationResult):
    """Category 5: API Endpoints."""
    print("\nCategory 5: API Endpoints")

    app = None
    client = None
    use_client = False

    try:
        from python.api.main import app as fastapi_app
        app = fastapi_app
    except Exception as exc:
        result.check("API app import", False, f"Could not import FastAPI app: {exc}")
        for i in range(18, 23):
            result.check(f"{i}. API endpoint", False, "App import failed")
        return

    try:
        from httpx import ASGITransport, AsyncClient
        import asyncio

        transport = ASGITransport(app=app)

        async def _get(url):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                return await ac.get(url)

        async def _post(url, json_data=None):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                return await ac.post(url, json=json_data)

        use_client = True
    except ImportError:
        use_client = False

    if use_client:
        loop = asyncio.new_event_loop()

        # Check 18: Compliance status endpoint
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/compliance/status?provider_name=TestISP&state=SP&subscribers=3000&services=SCM&classification=SVA&revenue_monthly=267000")
            )
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else {}
            has_checks = "checks" in body
            has_score = "overall_score" in body
            result.check(
                "18. Compliance status endpoint",
                is_ok and has_checks and has_score,
                f"status={resp.status_code}, has_checks={has_checks}, has_score={has_score}",
            )
        except Exception as exc:
            result.check("18. Compliance status endpoint", False, str(exc))

        # Check 19: Norma4 impact endpoint
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/compliance/norma4/impact?state=SP&subscribers=3000&revenue_monthly=267000&classification=SVA")
            )
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else {}
            has_icms = "additional_monthly_tax_brl" in body
            result.check(
                "19. Norma4 impact endpoint",
                is_ok and has_icms,
                f"status={resp.status_code}, has_icms={has_icms}",
            )
        except Exception as exc:
            result.check("19. Norma4 impact endpoint", False, str(exc))

        # Check 20: Licensing check endpoint
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/compliance/licensing/check?subscribers=6000&services=SCM")
            )
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else {}
            has_threshold = "above_threshold" in body
            result.check(
                "20. Licensing check endpoint",
                is_ok and has_threshold,
                f"status={resp.status_code}, has_threshold={has_threshold}",
            )
        except Exception as exc:
            result.check("20. Licensing check endpoint", False, str(exc))

        # Check 21: Regulations list endpoint
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/compliance/regulations")
            )
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else []
            is_list = isinstance(body, list)
            has_regs = len(body) >= 5 if is_list else False
            result.check(
                "21. Regulations list endpoint",
                is_ok and is_list and has_regs,
                f"status={resp.status_code}, count={len(body) if is_list else 'N/A'}",
            )
        except Exception as exc:
            result.check("21. Regulations list endpoint", False, str(exc))

        # Check 22: Deadlines endpoint
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/compliance/deadlines?days_ahead=730")
            )
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else []
            is_list = isinstance(body, list)
            has_deadlines = len(body) >= 3 if is_list else False
            result.check(
                "22. Deadlines endpoint",
                is_ok and is_list and has_deadlines,
                f"status={resp.status_code}, count={len(body) if is_list else 'N/A'}",
            )
        except Exception as exc:
            result.check("22. Deadlines endpoint", False, str(exc))

        loop.close()
    else:
        # Fallback: verify router imports
        try:
            from python.api.routers import compliance, network_health
            result.check("18. Compliance router imports", True)
            result.check("19. Norma4 endpoint router imports", True)
            result.check("20. Licensing endpoint router imports", True)
            result.check("21. Regulations endpoint router imports", True)
            result.check("22. Deadlines endpoint router imports", True)
        except Exception as exc:
            for i in range(18, 23):
                result.check(f"{i}. Router import", False, str(exc))


# ===================================================================
# Category 6: Integration (3 checks)
# ===================================================================

def test_6_integration(result: ValidationResult):
    """Category 6: Integration."""
    print("\nCategory 6: Integration")

    # Check 23: All regulatory modules import
    import_errors = []
    try:
        from python.regulatory.knowledge_base import tax_rates
        assert hasattr(tax_rates, "ICMS_RATES_SCM")
    except Exception as exc:
        import_errors.append(f"tax_rates: {exc}")

    try:
        from python.regulatory.knowledge_base import regulations
        assert hasattr(regulations, "REGULATIONS")
    except Exception as exc:
        import_errors.append(f"regulations: {exc}")

    try:
        from python.regulatory.knowledge_base import deadlines
        assert hasattr(deadlines, "get_upcoming_deadlines")
    except Exception as exc:
        import_errors.append(f"deadlines: {exc}")

    try:
        from python.regulatory.analyzer import norma4
        assert hasattr(norma4, "calculate_impact")
    except Exception as exc:
        import_errors.append(f"norma4: {exc}")

    try:
        from python.regulatory.analyzer import profile
        assert hasattr(profile, "analyze_profile")
    except Exception as exc:
        import_errors.append(f"profile: {exc}")

    try:
        from python.regulatory.analyzer import licensing
        assert hasattr(licensing, "check_licensing")
    except Exception as exc:
        import_errors.append(f"licensing: {exc}")

    result.check(
        "23. All regulatory modules import (knowledge_base + analyzer)",
        len(import_errors) == 0,
        "; ".join(import_errors),
    )

    # Check 24: All health modules import
    health_errors = []
    try:
        from python.ml.health import weather_correlation
        assert hasattr(weather_correlation, "compute_weather_risk")
    except Exception as exc:
        health_errors.append(f"weather_correlation: {exc}")

    try:
        from python.ml.health import quality_benchmark
        assert hasattr(quality_benchmark, "benchmark_quality")
    except Exception as exc:
        health_errors.append(f"quality_benchmark: {exc}")

    try:
        from python.ml.health import maintenance_scorer
        assert hasattr(maintenance_scorer, "compute_maintenance_priorities")
    except Exception as exc:
        health_errors.append(f"maintenance_scorer: {exc}")

    try:
        from python.ml.health import seasonal_patterns
        assert hasattr(seasonal_patterns, "generate_seasonal_calendar")
    except Exception as exc:
        health_errors.append(f"seasonal_patterns: {exc}")

    result.check(
        "24. All health modules import (weather, quality, maintenance, seasonal)",
        len(health_errors) == 0,
        "; ".join(health_errors),
    )

    # Check 25: Cross-module — profile analyzer uses tax_rates and licensing internally
    try:
        from python.regulatory.analyzer.profile import analyze_profile
        from python.regulatory.knowledge_base.tax_rates import ICMS_RATES_SCM
        from python.regulatory.analyzer.licensing import LICENSING_THRESHOLD

        # Verify the profile analyzer calls through to Norma4 (which uses tax_rates)
        # and licensing (which uses LICENSING_THRESHOLD)
        profile = analyze_profile(
            provider_name="Cross-Module Test ISP",
            state_codes=["SP"],
            subscriber_count=6000,
            services=["SCM"],
            current_classification="SVA",
            monthly_revenue_brl=500_000,
        )

        # Should have norma4 check (uses tax_rates internally)
        has_norma4 = any(c.regulation_id == "norma4" for c in profile.checks)
        # Should have licensing check (uses LICENSING_THRESHOLD internally)
        has_licensing = any(c.regulation_id == "res614" for c in profile.checks)
        # Licensing check should flag above_threshold since 6000 > 5000
        lic_check = [c for c in profile.checks if c.regulation_id == "res614"]
        lic_flagged = lic_check[0].status in ("at_risk", "non_compliant") if lic_check else False

        result.check(
            "25. Cross-module (profile uses tax_rates + licensing)",
            has_norma4 and has_licensing and lic_flagged,
            f"has_norma4={has_norma4}, has_licensing={has_licensing}, lic_flagged={lic_flagged}",
        )
    except Exception as exc:
        result.check("25. Cross-module integration", False, str(exc))


# ===================================================================
# Main
# ===================================================================

def main():
    print("=" * 60)
    print("ENLACE Phase 3: Regulatory + Fault Intelligence Validation")
    print("=" * 60)

    result = ValidationResult()

    test_1_regulatory_knowledge_base(result)
    test_2_norma4_calculator(result)
    test_3_profile_analyzer(result)
    test_4_fault_intelligence(result)
    test_5_api_endpoints(result)
    test_6_integration(result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
