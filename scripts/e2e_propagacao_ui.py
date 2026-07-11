"""End-to-end UI test for /propagacao: PIN gate -> real login -> link + coverage flows.

Prerequisites (run from repo root):
  1. RF engine:  SRTM_TILE_DIR=data/terrain/dtm DSM_TILE_DIR=data/terrain/dsm ./rust/target/release/pulso-rf-engine
  2. API:        TERRAIN_TILE_DIR=data/terrain CORS_ORIGINS='["http://127.0.0.1:3901"]' python3 -m uvicorn python.api.main:app --port 8897
  3. Frontend:   cd frontend && NEXT_PUBLIC_API_URL=http://127.0.0.1:8897 npm run build && PORT=3901 npm start
  4. Test user:  register e2e-test@enlace.dev / E2eTest!2026 via POST /api/v1/auth/register
Then: python3 scripts/e2e_propagacao_ui.py  (exits 0 when all checks pass)
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:3901")
SHOTS = "outputs"
EMAIL, PASSWORD = "e2e-test@enlace.dev", "E2eTest!2026"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    api_calls = []
    page.on("request", lambda r: api_calls.append(r.url) if "/api/v1/" in r.url else None)

    # 1. PIN gate
    page.goto(f"{BASE}/propagacao", wait_until="domcontentloaded")
    pin_input = page.locator('input[inputmode="numeric"]')
    expect(pin_input).to_be_visible(timeout=15000)
    check("pin_gate_shown", True)
    pin_input.fill("2707")
    page.get_by_role("button", name="Entrar").click()

    # 2. Redirect to /login, real login
    page.wait_for_url("**/login**", timeout=15000)
    check("redirected_to_login", True)
    page.locator('input[type="email"]').fill(EMAIL)
    page.locator('input[type="password"]').fill(PASSWORD)
    page.locator('form button[type="submit"], form button:not([type="button"])').first.click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
    check("login_succeeded", True, page.url)

    # 3. Propagacao page, deep-linked to São Paulo (cached tile)
    page.goto(f"{BASE}/propagacao?lat=-23.55&lon=-46.63&zoom=11", wait_until="domcontentloaded")
    expect(page.get_by_text("Propagação — Brasil inteiro")).to_be_visible(timeout=20000)
    check("planner_header", True)
    canvas = page.locator("#deckgl-overlay, canvas").first
    expect(canvas).to_be_visible(timeout=30000)
    page.wait_for_timeout(4000)  # let deck.gl + base map settle

    # 4. Enlace mode: click TX then RX (~14 km apart at zoom 11)
    box = canvas.bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.click(cx - 80, cy)
    page.wait_for_timeout(1500)
    expect(page.get_by_text("Elevação no ponto")).to_be_visible(timeout=20000)
    check("elevation_panel_after_tx", True)
    page.mouse.click(cx + 140, cy + 40)

    profile_hdr = page.get_by_text(re.compile(r"Perfil (DSM|DTM) — "))
    expect(profile_hdr).to_be_visible(timeout=90000)  # may download tiles
    check("profile_panel", True, profile_hdr.inner_text())
    los_badge = page.get_by_text(re.compile(r"LOS (livre|obstruído)"))
    expect(los_badge).to_be_visible(timeout=10000)
    check("los_badge", True, los_badge.inner_text())
    fres = page.get_by_text(re.compile(r"Fresnel"))
    check("fresnel_badge", fres.first.is_visible(), fres.first.inner_text())
    rx_txt = page.get_by_text(re.compile(r"Rx .*dBm .* margem"))
    check("link_budget_line", rx_txt.first.is_visible(), rx_txt.first.inner_text()[:80])
    body = page.inner_text("body")
    check("no_mock_terrain", "SIMULADO" not in body, "engine data is real")
    # chart svg rendered with legend series
    check("chart_rendered", page.locator("svg.recharts-surface").count() > 0)
    check("chart_terrain_series", "Terreno" in body and "Fresnel" in body)
    page.screenshot(path=f"{SHOTS}/e2e_1_enlace.png")

    # 5. DTM/DSM toggle triggers recompute
    page.get_by_role("button", name=re.compile(r"^dtm$", re.I)).click()
    expect(page.get_by_text(re.compile(r"Perfil DTM — "))).to_be_visible(timeout=60000)
    check("dtm_toggle", True)

    # 6. Coverage mode
    page.get_by_role("button", name="Cobertura", exact=True).click()
    page.wait_for_timeout(500)
    page.mouse.click(cx, cy)
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="Calcular cobertura").click()
    cov_hdr = page.get_by_text("Cobertura RF")
    expect(cov_hdr).to_be_visible(timeout=120000)
    check("coverage_panel", True)
    body = page.inner_text("body")
    m = re.search(r"(\d+)%\s*cobertura", body)
    check("coverage_pct_shown", bool(m), f"{m.group(1)}% cobertura" if m else "not found")
    check("coverage_area_km2", "km²" in body)
    check("no_mock_coverage", "SIMULADO" not in body, "real engine grid")
    page.screenshot(path=f"{SHOTS}/e2e_2_coverage.png")

    # 7. Hygiene
    real_calls = [u for u in api_calls if any(k in u for k in ("profile", "coverage", "elevation", "linkbudget", "terrain"))]
    check("api_calls_hit_backend", len(real_calls) >= 4, f"{len(real_calls)} design API calls")
    fatal = [e for e in console_errors if "favicon" not in e.lower() and "404" not in e]
    check("no_console_errors", len(fatal) == 0, "; ".join(fatal[:3])[:150])

    browser.close()

failed = [r for r in results if not r[1]]
print(f"\n{'='*50}\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
