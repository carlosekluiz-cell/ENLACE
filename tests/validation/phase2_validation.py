"""Phase 2 ML + RF Engine Validation Tests.

Tests validate ML opportunity scoring, financial viability models,
fiber routing, API endpoints, Rust RF engine, and integration sanity.

Run: python tests/validation/phase2_validation.py
"""
import json
import os
import subprocess
import sys
import time

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
        print(f"Phase 2 Validation: {self.tests_passed}/{self.tests_run} passed")
        if self.failures:
            print(f"\nFailed tests:")
            for name, details in self.failures:
                print(f"  - {name}: {details}")
        print(f"{'='*60}")
        return self.tests_failed == 0


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ═══════════════════════════════════════════════════════════════════════
# Category 1: ML Opportunity Scoring (5 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_1_ml_opportunity_scoring(result: ValidationResult):
    """Category 1: ML Opportunity Scoring."""
    print("\nCategory 1: ML Opportunity Scoring")
    conn = get_conn()
    cur = conn.cursor()

    # Check 1: Scores exist in opportunity_scores table
    cur.execute("SELECT COUNT(*) FROM opportunity_scores")
    score_count = cur.fetchone()[0]
    result.check(
        "1. Scores exist in opportunity_scores",
        score_count > 0,
        f"Found {score_count} rows (expected > 0)",
    )

    # Check 2: All composite_score values are between 0 and 100
    cur.execute("""
        SELECT COUNT(*) FROM opportunity_scores
        WHERE composite_score < 0 OR composite_score > 100
    """)
    out_of_range = cur.fetchone()[0]
    result.check(
        "2. Score range 0-100",
        out_of_range == 0,
        f"{out_of_range} scores out of range",
    )

    # Check 3: SHAP explanations — top_factors JSON is non-empty
    # top_factors is stored inside the 'features' JSONB column
    cur.execute("""
        SELECT COUNT(*) FROM opportunity_scores
        WHERE features IS NOT NULL
          AND features->'top_factors' IS NOT NULL
          AND jsonb_array_length(features->'top_factors') > 0
    """)
    has_shap = cur.fetchone()[0]
    result.check(
        "3. SHAP explanations (top_factors) non-empty",
        has_shap > 0,
        f"{has_shap}/{score_count} have top_factors",
    )

    # Check 4: Sub-score consistency — all sub-scores between 0-100
    cur.execute("""
        SELECT COUNT(*) FROM opportunity_scores
        WHERE demand_score < 0 OR demand_score > 100
           OR competition_score < 0 OR competition_score > 100
           OR infrastructure_score < 0 OR infrastructure_score > 100
           OR growth_score < 0 OR growth_score > 100
    """)
    bad_sub = cur.fetchone()[0]
    result.check(
        "4. Sub-scores all 0-100",
        bad_sub == 0,
        f"{bad_sub} rows with sub-scores out of range",
    )

    # Check 5: Score ordering sanity — municipalities with high income
    # AND no fiber competitor should score higher on average than those
    # with low income and high competition (spot check via features JSON)
    cur.execute("""
        SELECT composite_score
        FROM opportunity_scores
        WHERE features IS NOT NULL
          AND (features->>'avg_income')::float > 2000
          AND (features->>'fiber_penetration')::float < 0.1
        ORDER BY composite_score DESC
        LIMIT 5
    """)
    high_opp_scores = [r[0] for r in cur.fetchall()]

    cur.execute("""
        SELECT composite_score
        FROM opportunity_scores
        WHERE features IS NOT NULL
          AND (features->>'avg_income')::float < 1000
          AND (features->>'provider_count')::float >= 3
        ORDER BY composite_score ASC
        LIMIT 5
    """)
    low_opp_scores = [r[0] for r in cur.fetchall()]

    if high_opp_scores and low_opp_scores:
        avg_high = sum(high_opp_scores) / len(high_opp_scores)
        avg_low = sum(low_opp_scores) / len(low_opp_scores)
        result.check(
            "5. Score ordering sanity (high-opp > low-opp)",
            avg_high > avg_low,
            f"High-opportunity avg={avg_high:.1f}, Low-opportunity avg={avg_low:.1f}",
        )
    else:
        # If data doesn't support this exact split, just verify scores
        # have non-trivial variance (not all the same)
        cur.execute("SELECT MIN(composite_score), MAX(composite_score) FROM opportunity_scores")
        mn, mx = cur.fetchone()
        result.check(
            "5. Score ordering sanity (score variance exists)",
            mx - mn > 5,
            f"Score range: {mn:.1f} - {mx:.1f}",
        )

    cur.close()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Category 2: Financial Viability (5 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_2_financial_viability(result: ValidationResult):
    """Category 2: Financial Viability."""
    print("\nCategory 2: Financial Viability")

    # Check 6: Bass diffusion curve
    try:
        from python.ml.financial.subscriber_curve import project_subscribers

        proj = project_subscribers(
            addressable_households=5000,
            penetration_ceiling=0.6,
            months=36,
            urbanization_rate=0.7,
            competition_level="moderate",
        )

        has_keys = all(k in proj for k in ("pessimistic", "base_case", "optimistic"))
        all_int = all(
            isinstance(v, int)
            for curve in (proj.get("pessimistic", []), proj.get("base_case", []), proj.get("optimistic", []))
            for v in curve
        )
        # Check monotonicity at the end: pessimistic[-1] < base_case[-1] < optimistic[-1]
        p_end = proj["pessimistic"][-1]
        b_end = proj["base_case"][-1]
        o_end = proj["optimistic"][-1]
        ordering_ok = p_end <= b_end <= o_end

        result.check(
            "6. Bass diffusion curve (keys, types, ordering)",
            has_keys and all_int and ordering_ok,
            f"keys={has_keys}, int={all_int}, ordering: p={p_end} <= b={b_end} <= o={o_end}",
        )
    except Exception as exc:
        result.check("6. Bass diffusion curve", False, str(exc))

    # Check 7: CAPEX estimator
    try:
        from python.ml.financial.capex_estimator import estimate_capex

        capex_flat = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
            area_type="urban",
        )
        capex_mount = estimate_capex(
            cable_length_km=10.0,
            target_subscribers=500,
            area_type="urban",
            terrain="mountainous",
        )

        bd = capex_flat["breakdown"]
        total_from_bd = sum(bd.values())
        total_match = abs(total_from_bd - capex_flat["total_brl"]) < 1.0
        terrain_higher = capex_mount["total_brl"] > capex_flat["total_brl"]

        result.check(
            "7. CAPEX estimator (breakdown sums, terrain multiplier)",
            total_match and terrain_higher,
            f"sum_match={total_match} (breakdown={total_from_bd:.0f} vs total={capex_flat['total_brl']:.0f}), "
            f"terrain_higher={terrain_higher} (flat={capex_flat['total_brl']:.0f} vs mount={capex_mount['total_brl']:.0f})",
        )
    except Exception as exc:
        result.check("7. CAPEX estimator", False, str(exc))

    # Check 8: ARPU model
    try:
        from python.ml.financial.arpu_model import estimate_arpu

        arpu_fiber = estimate_arpu(
            state_code="SP",
            municipality_population=100000,
            avg_income=2000.0,
            technology="fiber",
            provider_count=2,
        )
        arpu_dsl = estimate_arpu(
            state_code="SP",
            municipality_population=100000,
            avg_income=2000.0,
            technology="dsl",
            provider_count=2,
        )

        ordering_ok = arpu_fiber["min_arpu"] <= arpu_fiber["base_arpu"] <= arpu_fiber["max_arpu"]
        fiber_gt_dsl = arpu_fiber["base_arpu"] > arpu_dsl["base_arpu"]

        result.check(
            "8. ARPU model (ordering, fiber > DSL)",
            ordering_ok and fiber_gt_dsl,
            f"ordering={ordering_ok} ({arpu_fiber['min_arpu']:.2f} <= {arpu_fiber['base_arpu']:.2f} <= {arpu_fiber['max_arpu']:.2f}), "
            f"fiber_gt_dsl={fiber_gt_dsl} (fiber={arpu_fiber['base_arpu']:.2f} vs dsl={arpu_dsl['base_arpu']:.2f})",
        )
    except Exception as exc:
        result.check("8. ARPU model", False, str(exc))

    # Check 9: Financial metrics
    try:
        from python.ml.financial.viability import compute_financial_metrics

        # Use a reasonable scenario
        subs_curve = list(range(0, 360, 10))  # grows from 0 to 350 over 36 months
        metrics = compute_financial_metrics(
            capex_brl=500_000,
            monthly_subscribers=subs_curve,
            arpu_brl=100.0,
        )

        has_npv = "npv_brl" in metrics
        has_irr = "irr_pct" in metrics
        has_payback = "payback_months" in metrics
        payback_ok = metrics["payback_months"] is None or metrics["payback_months"] > 0

        result.check(
            "9. Financial metrics (NPV/IRR/payback computed)",
            has_npv and has_irr and has_payback and payback_ok,
            f"npv={metrics.get('npv_brl')}, irr={metrics.get('irr_pct')}, "
            f"payback={metrics.get('payback_months')}",
        )
    except Exception as exc:
        result.check("9. Financial metrics", False, str(exc))

    # Check 10: IRR reasonableness for profitable scenario
    try:
        from python.ml.financial.viability import compute_financial_metrics

        # High subs, low CAPEX: should be very profitable
        high_subs = [i * 50 for i in range(36)]  # up to 1750
        metrics_profit = compute_financial_metrics(
            capex_brl=100_000,
            monthly_subscribers=high_subs,
            arpu_brl=120.0,
        )

        irr_positive = (
            metrics_profit["irr_pct"] is not None and metrics_profit["irr_pct"] > 0
        )
        result.check(
            "10. IRR positive for profitable scenario",
            irr_positive,
            f"IRR={metrics_profit.get('irr_pct')}%",
        )
    except Exception as exc:
        result.check("10. IRR positive for profitable scenario", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════
# Category 3: Routing (4 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_3_routing(result: ValidationResult):
    """Category 3: Routing."""
    print("\nCategory 3: Routing")

    # Check 11: Road graph builds (at least an empty graph)
    try:
        from python.ml.routing.fiber_route import build_road_graph
        import networkx as nx

        conn = get_conn()
        cur = conn.cursor()
        # Get a municipality id that has data
        cur.execute("SELECT id FROM admin_level_2 WHERE centroid IS NOT NULL LIMIT 1")
        row = cur.fetchone()
        cur.close()

        if row:
            muni_id = row[0]
            G = build_road_graph(municipality_id=muni_id, buffer_km=5.0, conn=conn)
            is_graph = isinstance(G, nx.Graph)
            result.check(
                "11. Road graph builds (returns nx.Graph)",
                is_graph,
                f"type={type(G).__name__}, nodes={G.number_of_nodes()}, edges={G.number_of_edges()}",
            )
        else:
            result.check("11. Road graph builds", False, "No municipality with centroid found")
        conn.close()
    except Exception as exc:
        result.check("11. Road graph builds", False, str(exc))

    # Check 12: BOM generator
    try:
        from python.ml.routing.bom_generator import generate_bom

        bom = generate_bom(
            route_geojson=None,
            total_length_km=5.0,
            target_subscribers=200,
            area_type="urban",
        )
        has_items = len(bom.get("items", [])) > 0
        has_grand_total = bom.get("grand_total_brl", 0) > 0

        # Check that each item has required fields
        items_valid = all(
            "quantity" in item and "total_cost_brl" in item
            for item in bom.get("items", [])
        )

        result.check(
            "12. BOM generator (items, costs, grand_total > 0)",
            has_items and has_grand_total and items_valid,
            f"items={len(bom.get('items', []))}, grand_total=R${bom.get('grand_total_brl', 0):,.2f}",
        )
    except Exception as exc:
        result.check("12. BOM generator", False, str(exc))

    # Check 13: Corridor finder functions exist and are callable
    try:
        from python.ml.routing.corridor_finder import (
            find_power_corridors,
            find_existing_fiber_corridors,
        )

        power_callable = callable(find_power_corridors)
        fiber_callable = callable(find_existing_fiber_corridors)

        result.check(
            "13. Corridor finder functions are callable",
            power_callable and fiber_callable,
            f"power={power_callable}, fiber={fiber_callable}",
        )
    except Exception as exc:
        result.check("13. Corridor finder functions are callable", False, str(exc))

    # Check 14: Route GeoJSON format
    try:
        from python.ml.routing.fiber_route import compute_fiber_route
        import networkx as nx

        # Build a small synthetic graph to test GeoJSON output
        G = nx.Graph()
        node_a = (-23.55, -46.63)
        node_b = (-23.56, -46.64)
        node_c = (-23.57, -46.65)
        G.add_node(node_a, lat=-23.55, lon=-46.63)
        G.add_node(node_b, lat=-23.56, lon=-46.64)
        G.add_node(node_c, lat=-23.57, lon=-46.65)
        G.add_edge(node_a, node_b, weight=100, length_m=1200, road_class="secondary", segment_id=1, cost_brl=24000)
        G.add_edge(node_b, node_c, weight=100, length_m=1300, road_class="secondary", segment_id=2, cost_brl=26000)

        route = compute_fiber_route(G, -23.55, -46.63, -23.57, -46.65)

        if route.get("status") == "success" and route.get("route_geojson"):
            geojson = route["route_geojson"]
            geom = geojson.get("geometry", {})
            is_linestring = geom.get("type") == "LineString"
            has_coords = len(geom.get("coordinates", [])) > 0
            result.check(
                "14. Route GeoJSON format (LineString + coordinates)",
                is_linestring and has_coords,
                f"type={geom.get('type')}, coords={len(geom.get('coordinates', []))}",
            )
        else:
            result.check(
                "14. Route GeoJSON format",
                False,
                f"Route status: {route.get('status')}, msg: {route.get('message', 'N/A')}",
            )
    except Exception as exc:
        result.check("14. Route GeoJSON format", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════
# Category 4: API Endpoints (5 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_4_api_endpoints(result: ValidationResult):
    """Category 4: API Endpoints."""
    print("\nCategory 4: API Endpoints")

    # We'll test by importing the app and using httpx TestClient,
    # falling back to verifying router imports if httpx is not available.
    app = None
    client = None
    use_client = False

    try:
        from python.api.main import app as fastapi_app
        app = fastapi_app
    except Exception as exc:
        result.check("API app import", False, f"Could not import FastAPI app: {exc}")
        # Fill remaining checks with failures
        for i in range(15, 20):
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
        # httpx not available; test with plain import checks
        use_client = False

    if use_client:
        loop = asyncio.new_event_loop()

        # Check 15: GET /api/v1/opportunity/top
        try:
            resp = loop.run_until_complete(_get("/api/v1/opportunity/top?country=BR&limit=5&min_score=0"))
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else None
            is_list = isinstance(body, list) if body is not None else False
            result.check(
                "15. GET /api/v1/opportunity/top returns list",
                is_ok and is_list,
                f"status={resp.status_code}, type={type(body).__name__}, len={len(body) if is_list else 'N/A'}",
            )
        except Exception as exc:
            result.check("15. GET /api/v1/opportunity/top", False, str(exc))

        # Check 16: POST /api/v1/opportunity/financial
        try:
            # Use a known municipality code from the DB
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT code, ST_Y(centroid), ST_X(centroid) FROM admin_level_2 WHERE centroid IS NOT NULL LIMIT 1")
            muni = cur.fetchone()
            cur.close()
            conn.close()

            if muni:
                payload = {
                    "municipality_code": muni[0].strip(),
                    "from_network_lat": float(muni[1]),
                    "from_network_lon": float(muni[2]),
                    "monthly_price_brl": 99.90,
                    "technology": "fiber",
                }
                resp = loop.run_until_complete(_post("/api/v1/opportunity/financial", payload))
                if resp.status_code == 200:
                    body = resp.json()
                    has_keys = all(
                        k in body
                        for k in ("subscriber_projection", "capex_estimate", "financial_metrics")
                    )
                    result.check(
                        "16. POST /financial schema (3 keys)",
                        has_keys,
                        f"keys={list(body.keys())}",
                    )
                else:
                    result.check(
                        "16. POST /financial schema",
                        False,
                        f"status={resp.status_code}, body={resp.text[:200]}",
                    )
            else:
                result.check("16. POST /financial schema", False, "No municipality found in DB")
        except Exception as exc:
            result.check("16. POST /financial schema", False, str(exc))

        # Check 17: GET /api/v1/design/profile
        try:
            resp = loop.run_until_complete(
                _get("/api/v1/design/profile?start_lat=-23.55&start_lon=-46.63&end_lat=-23.60&end_lon=-46.70&step_m=100")
            )
            if resp.status_code == 200:
                body = resp.json()
                has_points = "points" in body
                result.check(
                    "17. GET /design/profile returns points",
                    has_points,
                    f"keys={list(body.keys())}, points={len(body.get('points', []))}",
                )
            else:
                result.check("17. GET /design/profile", False, f"status={resp.status_code}")
        except Exception as exc:
            result.check("17. GET /design/profile", False, str(exc))

        # Check 18: POST /api/v1/design/coverage
        try:
            payload = {
                "tower_lat": -23.55,
                "tower_lon": -46.63,
                "tower_height_m": 30,
                "frequency_mhz": 700,
                "tx_power_dbm": 43,
                "antenna_gain_dbi": 15,
                "radius_m": 5000,
                "grid_resolution_m": 100,
            }
            resp = loop.run_until_complete(_post("/api/v1/design/coverage", payload))
            if resp.status_code == 200:
                body = resp.json()
                has_stats = "stats" in body
                result.check(
                    "18. POST /design/coverage returns stats",
                    has_stats,
                    f"keys={list(body.keys())}",
                )
            else:
                result.check("18. POST /design/coverage", False, f"status={resp.status_code}")
        except Exception as exc:
            result.check("18. POST /design/coverage", False, str(exc))

        # Check 19: GET /health
        try:
            resp = loop.run_until_complete(_get("/health"))
            is_ok = resp.status_code == 200
            body = resp.json() if is_ok else {}
            is_healthy = body.get("status") == "healthy"
            result.check(
                "19. GET /health returns healthy",
                is_ok and is_healthy,
                f"status={resp.status_code}, body_status={body.get('status')}",
            )
        except Exception as exc:
            result.check("19. GET /health", False, str(exc))

        loop.close()
    else:
        # Fallback: just verify routers import correctly
        try:
            from python.api.routers import opportunity, design, health
            result.check("15. Opportunity router imports", True)
            result.check("16. Financial endpoint router imports", True)
            result.check("17. Design router imports", True)
            result.check("18. Design coverage router imports", True)
            result.check("19. Health router imports", True)
        except Exception as exc:
            for i in range(15, 20):
                result.check(f"{i}. Router import", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════
# Category 5: Rust RF Engine (5 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_5_rust_rf_engine(result: ValidationResult):
    """Category 5: Rust RF Engine."""
    print("\nCategory 5: Rust RF Engine")

    rust_dir = os.path.join(PROJECT_ROOT, "rust")

    # Check 20: Workspace builds
    try:
        proc = subprocess.run(
            ["cargo", "build"],
            cwd=rust_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        result.check(
            "20. cargo build succeeds",
            proc.returncode == 0,
            f"exit={proc.returncode}, stderr={proc.stderr[-300:]}" if proc.returncode != 0 else "",
        )
    except subprocess.TimeoutExpired:
        result.check("20. cargo build succeeds", False, "Build timed out (300s)")
    except FileNotFoundError:
        result.check("20. cargo build succeeds", False, "cargo not found on PATH")
    except Exception as exc:
        result.check("20. cargo build succeeds", False, str(exc))

    # Check 21: All tests pass
    test_output = ""
    try:
        proc = subprocess.run(
            ["cargo", "test"],
            cwd=rust_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        test_output = proc.stdout + proc.stderr
        result.check(
            "21. cargo test passes",
            proc.returncode == 0,
            f"exit={proc.returncode}, output_tail={test_output[-300:]}" if proc.returncode != 0 else "",
        )
    except subprocess.TimeoutExpired:
        result.check("21. cargo test passes", False, "Tests timed out (300s)")
    except FileNotFoundError:
        result.check("21. cargo test passes", False, "cargo not found on PATH")
    except Exception as exc:
        result.check("21. cargo test passes", False, str(exc))

    # Check 22: FSPL tests passing
    fspl_pass = "test_fspl" in test_output or "fspl" in test_output.lower()
    # Look for "test result: ok" which indicates tests passed
    tests_ok = "test result: ok" in test_output
    result.check(
        "22. FSPL accuracy tests present and passing",
        fspl_pass and tests_ok,
        f"fspl_mentioned={fspl_pass}, tests_ok={tests_ok}",
    )

    # Check 23: Vegetation correction tests
    veg_pass = "vegetation" in test_output.lower() or "itu_r_veg" in test_output.lower()
    result.check(
        "23. Vegetation correction tests present and passing",
        veg_pass and tests_ok,
        f"veg_mentioned={veg_pass}, tests_ok={tests_ok}",
    )

    # Check 24: Binary exists
    binary_path = os.path.join(rust_dir, "target", "debug", "enlace-rf-engine")
    binary_exists = os.path.isfile(binary_path)
    result.check(
        "24. enlace-rf-engine binary exists",
        binary_exists,
        f"path={binary_path}",
    )


# ═══════════════════════════════════════════════════════════════════════
# Category 6: Integration Sanity (3 checks)
# ═══════════════════════════════════════════════════════════════════════


def test_6_integration_sanity(result: ValidationResult):
    """Category 6: Integration Sanity."""
    print("\nCategory 6: Integration Sanity")

    # Check 25: Model imports
    import_errors = []
    try:
        from python.ml.opportunity import scorer
        assert hasattr(scorer, "OpportunityScorer")
    except Exception as exc:
        import_errors.append(f"scorer: {exc}")

    try:
        from python.ml.financial import viability
        assert hasattr(viability, "compute_financial_metrics")
    except Exception as exc:
        import_errors.append(f"viability: {exc}")

    try:
        from python.ml.routing import fiber_route
        assert hasattr(fiber_route, "build_road_graph")
    except Exception as exc:
        import_errors.append(f"fiber_route: {exc}")

    result.check(
        "25. ML module imports (scorer, viability, fiber_route)",
        len(import_errors) == 0,
        "; ".join(import_errors),
    )

    # Check 26: RF client import
    try:
        from python.api.services.rf_client import RfEngineClient

        is_class = isinstance(RfEngineClient, type)
        result.check(
            "26. RfEngineClient class exists",
            is_class,
            f"type={type(RfEngineClient).__name__}",
        )
    except Exception as exc:
        result.check("26. RfEngineClient class exists", False, str(exc))

    # Check 27: End-to-end ML pipeline — scored municipalities match DB
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Get top scored municipalities from DB
        cur.execute("""
            SELECT geographic_id, composite_score
            FROM opportunity_scores
            ORDER BY composite_score DESC
            LIMIT 5
        """)
        top_scored = cur.fetchall()
        has_scores = len(top_scored) > 0

        if has_scores:
            # Verify these municipality codes actually exist in admin_level_2
            codes = [r[0].strip() for r in top_scored]
            placeholders = ",".join(["%s"] * len(codes))
            cur.execute(
                f"SELECT COUNT(*) FROM admin_level_2 WHERE code IN ({placeholders})",
                codes,
            )
            match_count = cur.fetchone()[0]
            all_match = match_count == len(codes)
        else:
            all_match = False

        result.check(
            "27. End-to-end ML pipeline (scored munis match DB)",
            has_scores and all_match,
            f"top_scored={len(top_scored)}, matching_munis={match_count if has_scores else 0}",
        )

        cur.close()
        conn.close()
    except Exception as exc:
        result.check("27. End-to-end ML pipeline", False, str(exc))


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("ENLACE Phase 2: ML + RF Engine Validation")
    print("=" * 60)

    result = ValidationResult()

    test_1_ml_opportunity_scoring(result)
    test_2_financial_viability(result)
    test_3_routing(result)
    test_4_api_endpoints(result)
    test_5_rust_rf_engine(result)
    test_6_integration_sanity(result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
