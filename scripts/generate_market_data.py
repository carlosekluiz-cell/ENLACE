#!/usr/bin/env python3
"""Generate static JSON market data files for SEO pages.

Queries PostgreSQL and outputs:
  site/src/data/market/index.json       — national summary + state overviews
  site/src/data/market/states/{uf}.json — per-state data with embedded municipalities

Also generates:
  site/public/sitemap-mercado.xml       — sitemap for all 5,597 market pages
"""

import json
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal

import psycopg2
import psycopg2.extras


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

DB_DSN = os.getenv("DATABASE_URL", "dbname=enlace user=enlace")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "src", "data", "market")
SITEMAP_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "public")
BASE_URL = "https://pulso.network"


def slugify(name: str) -> str:
    """Convert municipality name to URL slug."""
    s = unicodedata.normalize("NFD", name)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def blind_subs(n: int, level: str = "muni") -> int:
    """Blind subscriber counts: nearest 100 for municipalities, 10K for state/national."""
    if level == "muni":
        return round(n / 100) * 100
    return round(n / 10000) * 10000


def hhi_class(hhi: float) -> str:
    if hhi < 1500:
        return "competitivo"
    elif hhi < 2500:
        return "moderado"
    return "concentrado"


def ym_to_quarter(ym: str) -> str:
    """Convert '2023-01' to '2023-Q1'."""
    year = ym[:4]
    month = int(ym[5:7])
    q = (month - 1) // 3 + 1
    return f"{year}-Q{q}"


def generate_narrative(uf: str, state_name: str, data: dict) -> str:
    """Generate unique prose paragraph for each state from data."""
    subs = data["subscribers"]
    munis = data["municipalities"]
    fiber_pct = data["fiber_pct"]
    avg_hhi = data["avg_hhi"]
    monopoly_count = data.get("monopoly_count", 0)
    coverage_gap_count = data.get("coverage_gap_count", 0)
    avg_pen = data["avg_penetration"]

    # Growth info from timeseries
    ts = data.get("timeseries", [])
    if len(ts) >= 2:
        first_subs = ts[0]["subscribers"]
        last_subs = ts[-1]["subscribers"]
        growth_pct = round((last_subs - first_subs) / first_subs * 100, 1) if first_subs > 0 else 0
        first_fiber = ts[0].get("fiber_pct", 0)
        last_fiber = ts[-1].get("fiber_pct", 0)
    else:
        growth_pct = 0
        first_fiber = 0
        last_fiber = fiber_pct

    # Competition level
    if avg_hhi < 1500:
        comp_desc = "competitivo"
        comp_detail = "com baixa concentração de mercado"
    elif avg_hhi < 2500:
        comp_desc = "moderadamente concentrado"
        comp_detail = "com oportunidades para novos entrantes"
    else:
        comp_desc = "altamente concentrado"
        comp_detail = "onde poucos provedores dominam a base de assinantes"

    # Fiber transition
    if last_fiber >= 70:
        fiber_desc = f"com forte presença de fibra óptica ({fiber_pct:.0f}% dos acessos)"
    elif last_fiber >= 40:
        fiber_desc = f"em transição para fibra óptica, que já representa {fiber_pct:.0f}% dos acessos"
    else:
        fiber_desc = f"onde rádio e tecnologias legadas ainda predominam (fibra em {fiber_pct:.0f}%)"

    # Fiber evolution
    fiber_delta = last_fiber - first_fiber
    if fiber_delta > 15:
        fiber_evo = f"A migração para fibra acelerou: saiu de {first_fiber:.0f}% em 2023 para {last_fiber:.0f}% hoje, um avanço de {fiber_delta:.0f} pontos percentuais."
    elif fiber_delta > 5:
        fiber_evo = f"A adoção de fibra cresceu de {first_fiber:.0f}% para {last_fiber:.0f}% desde 2023."
    else:
        fiber_evo = f"A participação de fibra se manteve estável em torno de {last_fiber:.0f}%."

    # Growth
    if growth_pct > 20:
        growth_desc = f"O mercado cresceu {growth_pct:.0f}% nos últimos 3 anos, ritmo acima da média nacional."
    elif growth_pct > 5:
        growth_desc = f"O mercado registrou crescimento de {growth_pct:.0f}% desde 2023."
    elif growth_pct > 0:
        growth_desc = f"O crescimento foi modesto ({growth_pct:.0f}% desde 2023), sinalizando mercado maduro."
    else:
        growth_desc = "O número de assinantes ficou estável nos últimos 3 anos."

    # Coverage gaps
    if monopoly_count > 10:
        gap_desc = f" {monopoly_count} municípios ainda operam com apenas um provedor, representando oportunidades de expansão."
    elif monopoly_count > 0:
        gap_desc = f" {monopoly_count} município{'s' if monopoly_count > 1 else ''} opera{'m' if monopoly_count > 1 else ''} em regime de monopólio."
    else:
        gap_desc = ""

    # Complaints info
    complaints = data.get("complaints", [])
    if complaints:
        total_complaints = sum(c["count"] for c in complaints)
        avg_satisfaction = sum(c.get("avg_satisfaction", 0) for c in complaints) / len(complaints)
        if total_complaints > 10000:
            complaint_desc = f" O estado acumula {total_complaints:,.0f} reclamações de consumidores registradas.".replace(",", ".")
        elif total_complaints > 1000:
            complaint_desc = f" Foram registradas {total_complaints:,.0f} reclamações de consumidores.".replace(",", ".")
        else:
            complaint_desc = ""
    else:
        complaint_desc = ""

    # Penetration
    if avg_pen >= 80:
        pen_desc = f"A penetração média de {avg_pen:.0f}% indica alta maturidade digital"
    elif avg_pen >= 50:
        pen_desc = f"Com penetração média de {avg_pen:.0f}%, o estado apresenta cobertura moderada"
    else:
        pen_desc = f"A penetração média de {avg_pen:.0f}% revela espaço significativo para crescimento"

    subs_fmt = f"{subs / 1_000_000:.1f} milhões" if subs >= 1_000_000 else f"{subs / 1_000:.0f} mil"
    hhi_fmt = f"{avg_hhi:,.0f}".replace(",", ".")

    narrative = (
        f"{state_name} conta com {subs_fmt} de acessos de banda larga fixa distribuídos em "
        f"{munis} municípios, {fiber_desc}. O ambiente competitivo é {comp_desc}, "
        f"{comp_detail}, com HHI médio de {hhi_fmt}. "
        + growth_desc + " " + fiber_evo
        + f" {pen_desc}."
        + gap_desc
        + complaint_desc
    )

    return narrative.strip()


def _classify_opportunity(opp: dict) -> dict:
    """Convert raw opportunity scores to classification teasers. Protects proprietary scoring."""
    if not opp or not opp.get("composite"):
        return {}
    composite = opp["composite"]
    if composite >= 70:
        level = "alto"
    elif composite >= 50:
        level = "moderado"
    elif composite >= 30:
        level = "baixo"
    else:
        level = "muito_baixo"
    return {
        "level": level,
        "demand_level": "alto" if opp.get("demand", 0) >= 60 else "moderado" if opp.get("demand", 0) >= 40 else "baixo",
        "competition_level": "alto" if opp.get("competition", 0) >= 60 else "moderado" if opp.get("competition", 0) >= 40 else "baixo",
        "infrastructure_level": "alto" if opp.get("infrastructure", 0) >= 60 else "moderado" if opp.get("infrastructure", 0) >= 40 else "baixo",
        "growth_level": "alto" if opp.get("growth", 0) >= 60 else "moderado" if opp.get("growth", 0) >= 40 else "baixo",
    }


def _classify_hhi_trend(trend: list) -> dict:
    """Convert raw HHI quarterly array to trend summary. Protects time-series data."""
    if not trend or len(trend) < 2:
        return {}
    first = trend[0]
    last = trend[-1]
    delta = last - first
    periods = len(trend)
    if delta < -200:
        direction = "caindo"
    elif delta > 200:
        direction = "subindo"
    else:
        direction = "estavel"
    return {
        "direction": direction,
        "current": last,
        "periods": periods,
    }


def generate_city_narrative(city_name: str, state_name: str, uf: str, data: dict) -> str:
    """Generate unique ~100-word prose paragraph for a municipality."""
    parts = []
    subs = data.get("subscribers", 0)
    isp_count = data.get("isp_count", 0)
    pen = data.get("penetration", 0)
    hhi = data.get("hhi", 0)
    fiber = data.get("fiber_pct", 0)
    growth = data.get("growth_pct", 0)

    subs_fmt = f"{subs:,.0f}".replace(",", ".") if subs < 10000 else f"{subs / 1000:.0f} mil"
    parts.append(
        f"{city_name} ({uf.upper()}) possui {subs_fmt} acessos de banda larga fixa "
        f"atendidos por {isp_count} provedor{'es' if isp_count != 1 else ''}, "
        f"com penetração de {pen}% dos domicílios."
    )

    if hhi < 1500:
        parts.append(f"O mercado local é competitivo (HHI {hhi}).")
    elif hhi < 2500:
        parts.append(f"A concentração de mercado é moderada (HHI {hhi}).")
    else:
        parts.append(f"O mercado é altamente concentrado (HHI {hhi}), com poucos provedores dominantes.")

    if fiber >= 70:
        parts.append(f"A fibra óptica predomina, com {fiber}% dos acessos.")
    elif fiber >= 40:
        parts.append(f"A migração para fibra avança — já representa {fiber}% dos acessos.")
    elif fiber > 0:
        parts.append(f"Tecnologias legadas ainda predominam; fibra responde por {fiber}% dos acessos.")

    if growth > 20:
        parts.append(f"O mercado cresceu expressivos {growth}% nos últimos 3 anos.")
    elif growth > 5:
        parts.append(f"Crescimento de {growth}% desde 2023 indica expansão contínua.")
    elif growth > 0:
        parts.append(f"Crescimento modesto ({growth}%) sinaliza maturidade.")

    schools = data.get("schools", {})
    sanitation = data.get("sanitation", {})
    opp = data.get("opportunity", {})

    infra_notes = []
    no_inet = schools.get("no_internet", 0)
    if no_inet > 0:
        infra_notes.append(f"{no_inet} escola{'s' if no_inet != 1 else ''} sem internet")
    water = sanitation.get("water_pct", 0)
    if 0 < water < 80:
        infra_notes.append(f"cobertura de água em {water:.0f}%")
    if infra_notes:
        parts.append(f"Desafios incluem {' e '.join(infra_notes)}.")

    opp_level = opp.get("level", "")
    if opp_level == "alto":
        parts.append("Score de oportunidade alto — forte potencial para investimento em telecom.")
    elif opp_level == "moderado":
        parts.append("Oportunidade moderada para expansão de banda larga.")

    planning = data.get("planning", {})
    if planning.get("digital_governance"):
        parts.append("O município possui governança digital.")

    return " ".join(parts)


def main():
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # 1. Get latest and earliest periods
    cur.execute("SELECT MAX(year_month) AS latest, MIN(year_month) AS earliest FROM broadband_subscribers")
    period_row = cur.fetchone()
    latest_ym = period_row["latest"]
    earliest_ym = period_row["earliest"]
    print(f"Period range: {earliest_ym} to {latest_ym}")

    # 2. Core broadband data per municipality
    cur.execute("""
        SELECT
            a2.id AS l2_id, a2.name, a2.code, a2.population, a2.households,
            a1.abbrev AS uf, a1.name AS state_name,
            COALESCE(ST_Y(a2.centroid), 0) AS lat,
            COALESCE(ST_X(a2.centroid), 0) AS lng,
            SUM(bs.subscribers) AS total_subs,
            COUNT(DISTINCT bs.provider_id) AS isp_count,
            SUM(CASE WHEN bs.technology IN ('fiber','ftth','fttb') THEN bs.subscribers ELSE 0 END) AS fiber_subs,
            SUM(CASE WHEN bs.technology IN ('fwa') THEN bs.subscribers ELSE 0 END) AS fwa_subs,
            SUM(CASE WHEN bs.technology LIKE '%%dsl%%' OR bs.technology IN ('adsl1','adsl2','hdsl') THEN bs.subscribers ELSE 0 END) AS dsl_subs,
            SUM(CASE WHEN bs.technology IN ('cable','cable modem') THEN bs.subscribers ELSE 0 END) AS cable_subs,
            SUM(CASE WHEN bs.technology IN ('ethernet','dwdm','fr','atm') THEN bs.subscribers ELSE 0 END) AS other_fixed_subs,
            SUM(CASE WHEN bs.technology NOT IN ('fiber','ftth','fttb','fwa','cable','cable modem','ethernet','dwdm','fr','atm')
                      AND bs.technology NOT LIKE '%%dsl%%'
                      AND bs.technology NOT IN ('adsl1','adsl2','hdsl')
                 THEN bs.subscribers ELSE 0 END) AS radio_subs
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.year_month = %s AND bs.subscribers > 0
        GROUP BY a2.id, a2.name, a2.code, a2.population, a2.households,
                 a1.abbrev, a1.name, a2.centroid
    """, (latest_ym,))
    rows = cur.fetchall()
    print(f"Municipalities with data: {len(rows)}")

    # 3. HHI per municipality (need provider-level shares)
    cur.execute("""
        SELECT l2_id, provider_id, SUM(subscribers) AS subs
        FROM broadband_subscribers
        WHERE year_month = %s AND subscribers > 0
        GROUP BY l2_id, provider_id
    """, (latest_ym,))
    provider_subs = defaultdict(list)
    for r in cur.fetchall():
        provider_subs[r["l2_id"]].append(r["subs"])

    hhi_map = {}
    for l2_id, subs_list in provider_subs.items():
        total = sum(subs_list)
        if total > 0:
            hhi_map[l2_id] = sum((s / total * 100) ** 2 for s in subs_list)

    # 4. Quality seals per municipality
    cur.execute("""
        SELECT l2_id, seal_level, COUNT(*) AS cnt
        FROM quality_seals
        WHERE year_half = (SELECT MAX(year_half) FROM quality_seals)
        GROUP BY l2_id, seal_level
    """)
    quality_map = defaultdict(lambda: {"ouro": 0, "prata": 0, "bronze": 0, "sem_selo": 0})
    for r in cur.fetchall():
        level = r["seal_level"]
        if level in quality_map[r["l2_id"]]:
            quality_map[r["l2_id"]][level] = r["cnt"]

    # 5. Tax debt ISPs per municipality
    cur.execute("""
        SELECT bs.l2_id, COUNT(DISTINCT ptd.provider_id) AS cnt
        FROM provider_tax_debts ptd
        JOIN broadband_subscribers bs ON bs.provider_id = ptd.provider_id
        WHERE bs.year_month = %s AND bs.subscribers > 0
        GROUP BY bs.l2_id
    """, (latest_ym,))
    tax_debt_map = {}
    for r in cur.fetchall():
        tax_debt_map[r["l2_id"]] = r["cnt"]

    # 6. Consumer complaints per municipality
    cur.execute("""
        SELECT bs.l2_id, COUNT(*) AS cnt
        FROM consumer_complaints cc
        JOIN broadband_subscribers bs ON bs.provider_id = cc.provider_id
        WHERE bs.year_month = %s AND bs.subscribers > 0
        GROUP BY bs.l2_id
    """, (latest_ym,))
    complaints_map = {}
    for r in cur.fetchall():
        complaints_map[r["l2_id"]] = r["cnt"]

    # ═══════════════════════════════════════════════════════════════
    # NEW: 7. Quarterly timeseries per state (subs, fiber_pct, ISP count)
    # ═══════════════════════════════════════════════════════════════
    print("Querying quarterly timeseries...")
    cur.execute("""
        SELECT
            a1.abbrev AS uf,
            bs.year_month,
            SUM(bs.subscribers) AS total_subs,
            SUM(CASE WHEN bs.technology IN ('fiber','ftth','fttb') THEN bs.subscribers ELSE 0 END) AS fiber_subs,
            COUNT(DISTINCT bs.provider_id) AS isp_count
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.subscribers > 0
        GROUP BY a1.abbrev, bs.year_month
        ORDER BY a1.abbrev, bs.year_month
    """)
    # Group by state then aggregate by quarter (take last month of each quarter)
    state_monthly = defaultdict(list)
    for r in cur.fetchall():
        state_monthly[r["uf"].lower()].append(r)

    state_timeseries = {}
    for uf, months in state_monthly.items():
        quarterly = defaultdict(lambda: {"subs": 0, "fiber": 0, "isps": 0, "ym": ""})
        for m in months:
            q = ym_to_quarter(m["year_month"])
            # Keep latest month's data per quarter (overwrite)
            quarterly[q] = {
                "subs": m["total_subs"],
                "fiber": m["fiber_subs"],
                "isps": m["isp_count"],
                "ym": m["year_month"],
            }
        ts = []
        for q in sorted(quarterly.keys()):
            d = quarterly[q]
            ts.append({
                "quarter": q,
                "subscribers": blind_subs(d["subs"], "state"),
                "fiber_pct": round(d["fiber"] / d["subs"] * 100, 1) if d["subs"] > 0 else 0,
                "isp_count": d["isps"],
            })
        state_timeseries[uf] = ts
    print(f"  Timeseries for {len(state_timeseries)} states, avg {sum(len(v) for v in state_timeseries.values()) // max(len(state_timeseries), 1)} quarters each")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 8. Tech evolution per state (earliest vs latest quarter)
    # ═══════════════════════════════════════════════════════════════
    print("Querying tech evolution...")
    cur.execute("""
        SELECT
            a1.abbrev AS uf,
            bs.year_month,
            SUM(CASE WHEN bs.technology IN ('fiber','ftth','fttb') THEN bs.subscribers ELSE 0 END) AS fiber,
            SUM(CASE WHEN bs.technology NOT IN ('fiber','ftth','fttb','fwa','cable','cable modem','ethernet','dwdm','fr','atm')
                      AND bs.technology NOT LIKE '%%dsl%%'
                      AND bs.technology NOT IN ('adsl1','adsl2','hdsl')
                 THEN bs.subscribers ELSE 0 END) AS radio,
            SUM(CASE WHEN bs.technology IN ('cable','cable modem') THEN bs.subscribers ELSE 0 END) AS cable,
            SUM(CASE WHEN bs.technology LIKE '%%dsl%%' OR bs.technology IN ('adsl1','adsl2','hdsl') THEN bs.subscribers ELSE 0 END) AS dsl,
            SUM(bs.subscribers) AS total
        FROM broadband_subscribers bs
        JOIN admin_level_2 a2 ON a2.id = bs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE bs.year_month IN (%s, %s) AND bs.subscribers > 0
        GROUP BY a1.abbrev, bs.year_month
    """, (earliest_ym, latest_ym))

    state_tech_evo = defaultdict(dict)
    for r in cur.fetchall():
        uf = r["uf"].lower()
        total = r["total"] or 1
        period_key = "before" if r["year_month"] == earliest_ym else "after"
        state_tech_evo[uf][period_key] = {
            "period": r["year_month"],
            "fiber_pct": round(r["fiber"] / total * 100, 1),
            "radio_pct": round(r["radio"] / total * 100, 1),
            "cable_pct": round(r["cable"] / total * 100, 1),
            "dsl_pct": round(r["dsl"] / total * 100, 1),
        }
    print(f"  Tech evolution for {len(state_tech_evo)} states")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 9. Municipality growth (earliest vs latest)
    # ═══════════════════════════════════════════════════════════════
    print("Querying municipality growth...")
    cur.execute("""
        SELECT l2_id, year_month, SUM(subscribers) AS subs
        FROM broadband_subscribers
        WHERE year_month IN (%s, %s) AND subscribers > 0
        GROUP BY l2_id, year_month
    """, (earliest_ym, latest_ym))

    muni_periods = defaultdict(dict)
    for r in cur.fetchall():
        muni_periods[r["l2_id"]][r["year_month"]] = r["subs"]

    muni_growth = {}
    for l2_id, periods in muni_periods.items():
        early = periods.get(earliest_ym, 0)
        late = periods.get(latest_ym, 0)
        if early > 0:
            muni_growth[l2_id] = round((late - early) / early * 100, 1)
        elif late > 0:
            muni_growth[l2_id] = 999.9  # new market
        else:
            muni_growth[l2_id] = 0
    print(f"  Growth data for {len(muni_growth)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 10. Consumer complaints per state (quarterly)
    # ═══════════════════════════════════════════════════════════════
    print("Querying complaints by state...")
    cur.execute("""
        SELECT
            UPPER(cc.state) AS uf,
            CONCAT(EXTRACT(YEAR FROM cc.complaint_date)::int, '-Q',
                   CEIL(EXTRACT(MONTH FROM cc.complaint_date) / 3.0)::int) AS quarter,
            COUNT(*) AS cnt,
            AVG(cc.response_days) FILTER (WHERE cc.response_days IS NOT NULL AND cc.response_days < 365) AS avg_response,
            AVG(cc.satisfaction_rating) FILTER (WHERE cc.satisfaction_rating IS NOT NULL) AS avg_satisfaction
        FROM consumer_complaints cc
        WHERE cc.state IS NOT NULL AND cc.complaint_date IS NOT NULL
        GROUP BY UPPER(cc.state), quarter
        ORDER BY UPPER(cc.state), quarter
    """)
    state_complaints = defaultdict(list)
    for r in cur.fetchall():
        uf = r["uf"].lower() if r["uf"] else None
        if uf:
            state_complaints[uf].append({
                "quarter": r["quarter"],
                "count": r["cnt"],
                "avg_response_days": round(r["avg_response"], 1) if r["avg_response"] else None,
                "avg_satisfaction": round(r["avg_satisfaction"], 1) if r["avg_satisfaction"] else None,
            })
    print(f"  Complaints for {len(state_complaints)} states")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 11. Employment per state (yearly telecom jobs + avg salary)
    # ═══════════════════════════════════════════════════════════════
    print("Querying employment by state...")
    cur.execute("""
        SELECT
            a1.abbrev AS uf,
            ei.year,
            SUM(ei.formal_jobs_telecom) AS telecom_jobs,
            AVG(ei.avg_salary_brl) FILTER (WHERE ei.avg_salary_brl > 0 AND ei.avg_salary_brl < 100000) AS avg_salary
        FROM employment_indicators ei
        JOIN admin_level_2 a2 ON a2.id = ei.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE ei.formal_jobs_telecom > 0
        GROUP BY a1.abbrev, ei.year
        ORDER BY a1.abbrev, ei.year
    """)
    state_employment = defaultdict(list)
    for r in cur.fetchall():
        uf = r["uf"].lower()
        state_employment[uf].append({
            "year": r["year"],
            "telecom_jobs": r["telecom_jobs"],
            "avg_salary_brl": round(r["avg_salary"]) if r["avg_salary"] else None,
        })
    print(f"  Employment for {len(state_employment)} states")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 12. Economy per state (PIB, per-capita, latest year)
    # ═══════════════════════════════════════════════════════════════
    print("Querying economy by state...")
    cur.execute("""
        SELECT
            a1.abbrev AS uf,
            SUM((ec.sector_breakdown->'anp_fuel_breakdown'->>'proxy_pib')::numeric) AS proxy_pib,
            ec.year
        FROM economic_indicators ec
        JOIN admin_level_2 a2 ON a2.id = ec.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE ec.year = (SELECT MAX(year) FROM economic_indicators)
          AND ec.sector_breakdown->'anp_fuel_breakdown'->>'proxy_pib' IS NOT NULL
        GROUP BY a1.abbrev, ec.year
    """)
    state_economy = {}
    for r in cur.fetchall():
        uf = r["uf"].lower()
        proxy = float(r["proxy_pib"]) if r["proxy_pib"] else 0
        state_economy[uf] = {
            "year": r["year"],
            "proxy_pib": round(proxy),
        }
    print(f"  Economy for {len(state_economy)} states")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 13. Opportunity scores per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying opportunity scores...")
    cur.execute("""
        SELECT a2.id AS l2_id,
               os.demand_score, os.competition_score,
               os.infrastructure_score, os.growth_score, os.composite_score
        FROM opportunity_scores os
        JOIN admin_level_2 a2 ON a2.code = os.geographic_id
    """)
    opp_map = {}
    for r in cur.fetchall():
        opp_map[r["l2_id"]] = {
            "demand": round(float(r["demand_score"]), 1) if r["demand_score"] else 0,
            "competition": round(float(r["competition_score"]), 1) if r["competition_score"] else 0,
            "infrastructure": round(float(r["infrastructure_score"]), 1) if r["infrastructure_score"] else 0,
            "growth": round(float(r["growth_score"]), 1) if r["growth_score"] else 0,
            "composite": round(float(r["composite_score"]), 1) if r["composite_score"] else 0,
        }
    print(f"  Opportunity scores for {len(opp_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 14. Schools per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying schools...")
    cur.execute("""
        SELECT l2_id,
               COUNT(*) AS total,
               SUM(CASE WHEN NOT has_internet THEN 1 ELSE 0 END) AS no_internet,
               SUM(COALESCE(student_count, 0)) AS students
        FROM schools
        WHERE year = (SELECT MAX(year) FROM schools)
        GROUP BY l2_id
    """)
    schools_map = {}
    for r in cur.fetchall():
        schools_map[r["l2_id"]] = {
            "total": r["total"],
            "no_internet": r["no_internet"],
            "students": r["students"],
        }
    print(f"  Schools for {len(schools_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 15. Health facilities per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying health facilities...")
    cur.execute("""
        SELECT l2_id,
               COUNT(*) AS facilities,
               SUM(COALESCE(bed_count, 0)) AS beds
        FROM health_facilities
        GROUP BY l2_id
    """)
    health_map = {}
    for r in cur.fetchall():
        health_map[r["l2_id"]] = {
            "facilities": r["facilities"],
            "beds": r["beds"],
        }
    print(f"  Health facilities for {len(health_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 16. Safety indicators per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying safety indicators...")
    cur.execute("""
        SELECT l2_id, homicide_rate, risk_score
        FROM safety_indicators
        WHERE year = (SELECT MAX(year) FROM safety_indicators)
    """)
    safety_map = {}
    for r in cur.fetchall():
        safety_map[r["l2_id"]] = {
            "homicide_rate": round(float(r["homicide_rate"]), 1) if r["homicide_rate"] else 0,
            "risk_score": round(float(r["risk_score"]), 1) if r["risk_score"] else 0,
        }
    print(f"  Safety for {len(safety_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 17. Sanitation indicators per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying sanitation...")
    cur.execute("""
        SELECT l2_id, water_coverage_pct, sewage_coverage_pct, water_losses_pct
        FROM sanitation_indicators
        WHERE year = (SELECT MAX(year) FROM sanitation_indicators)
    """)
    sanitation_map = {}
    for r in cur.fetchall():
        sanitation_map[r["l2_id"]] = {
            "water_pct": round(float(r["water_coverage_pct"]), 1) if r["water_coverage_pct"] else 0,
            "sewage_pct": round(float(r["sewage_coverage_pct"]), 1) if r["sewage_coverage_pct"] else 0,
            "water_loss_pct": round(float(r["water_losses_pct"]), 1) if r["water_losses_pct"] else 0,
        }
    print(f"  Sanitation for {len(sanitation_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 18. Economy per municipality (PIB per capita, formal employment)
    # ═══════════════════════════════════════════════════════════════
    print("Querying municipal economy...")
    cur.execute("""
        SELECT l2_id, pib_per_capita_brl, formal_employment
        FROM economic_indicators
        WHERE year = (SELECT MAX(year) FROM economic_indicators)
    """)
    muni_economy_map = {}
    for r in cur.fetchall():
        muni_economy_map[r["l2_id"]] = {
            "pib_per_capita": round(float(r["pib_per_capita_brl"])) if r["pib_per_capita_brl"] else 0,
            "formal_employment": r["formal_employment"] or 0,
        }
    print(f"  Municipal economy for {len(muni_economy_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 19. Building density per municipality
    # ═══════════════════════════════════════════════════════════════
    print("Querying building density...")
    cur.execute("""
        SELECT l2_id, total_addresses, residential_addresses,
               density_per_km2,
               CASE WHEN total_addresses > 0
                    THEN rural_addresses::float / total_addresses * 100
                    ELSE 0 END AS rural_pct
        FROM building_density
    """)
    density_map = {}
    for r in cur.fetchall():
        density_map[r["l2_id"]] = {
            "addresses": r["total_addresses"] or 0,
            "residential": r["residential_addresses"] or 0,
            "per_km2": round(float(r["density_per_km2"]), 1) if r["density_per_km2"] else 0,
            "rural_pct": round(float(r["rural_pct"]), 1) if r["rural_pct"] else 0,
        }
    print(f"  Building density for {len(density_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 20. Telecom employment per municipality (latest year/month)
    # ═══════════════════════════════════════════════════════════════
    print("Querying municipal telecom employment...")
    cur.execute("""
        SELECT l2_id, formal_jobs_telecom, avg_salary_brl
        FROM employment_indicators
        WHERE year = (SELECT MAX(year) FROM employment_indicators)
          AND month = (SELECT MAX(month) FROM employment_indicators
                       WHERE year = (SELECT MAX(year) FROM employment_indicators))
    """)
    muni_employment_map = {}
    for r in cur.fetchall():
        muni_employment_map[r["l2_id"]] = {
            "telecom_jobs": r["formal_jobs_telecom"] or 0,
            "telecom_salary": round(float(r["avg_salary_brl"])) if r["avg_salary_brl"] else 0,
        }
    print(f"  Municipal employment for {len(muni_employment_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 21. Municipal planning
    # ═══════════════════════════════════════════════════════════════
    print("Querying municipal planning...")
    cur.execute("""
        SELECT l2_id, has_plano_diretor, has_zoning_law,
               has_building_code, has_digital_governance
        FROM municipal_planning
        WHERE munic_year = (SELECT MAX(munic_year) FROM municipal_planning)
    """)
    planning_map = {}
    for r in cur.fetchall():
        planning_map[r["l2_id"]] = {
            "plano_diretor": bool(r["has_plano_diretor"]),
            "zoning": bool(r["has_zoning_law"]),
            "building_code": bool(r["has_building_code"]),
            "digital_governance": bool(r["has_digital_governance"]),
        }
    print(f"  Municipal planning for {len(planning_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 22. Top ouro providers per municipality (for city pages)
    # ═══════════════════════════════════════════════════════════════
    print("Querying top ouro providers...")
    cur.execute("""
        SELECT qs.l2_id, p.name AS provider_name,
               qs.overall_score, qs.speed_score,
               qs.availability_score, qs.latency_score
        FROM quality_seals qs
        JOIN providers p ON p.id = qs.provider_id
        WHERE qs.year_half = (SELECT MAX(year_half) FROM quality_seals)
          AND qs.seal_level = 'ouro'
        ORDER BY qs.l2_id, qs.overall_score DESC
    """)
    ouro_providers_map = defaultdict(list)
    for r in cur.fetchall():
        if len(ouro_providers_map[r["l2_id"]]) < 5:
            ouro_providers_map[r["l2_id"]].append({
                "name": r["provider_name"],
                "score": round(float(r["overall_score"]), 1) if r["overall_score"] else 0,
                "speed": round(float(r["speed_score"]), 1) if r["speed_score"] else 0,
                "availability": round(float(r["availability_score"]), 1) if r["availability_score"] else 0,
                "latency": round(float(r["latency_score"]), 1) if r["latency_score"] else 0,
            })
    print(f"  Ouro providers for {len(ouro_providers_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 23. HHI trend per municipality (quarterly from competitive_analysis)
    # ═══════════════════════════════════════════════════════════════
    print("Querying HHI trends...")
    cur.execute("""
        SELECT l2_id, year_month, hhi_index
        FROM competitive_analysis
        ORDER BY l2_id, year_month
    """)
    hhi_trend_raw = defaultdict(list)
    for r in cur.fetchall():
        hhi_trend_raw[r["l2_id"]].append({
            "ym": r["year_month"],
            "hhi": round(float(r["hhi_index"])) if r["hhi_index"] else 0,
        })
    # Aggregate to quarterly (last 12 quarters)
    hhi_trend_map = {}
    for l2_id, entries in hhi_trend_raw.items():
        quarterly = {}
        for e in entries:
            q = ym_to_quarter(e["ym"])
            quarterly[q] = e["hhi"]  # keep latest month per quarter
        # Last 12 quarters
        sorted_qs = sorted(quarterly.keys())[-12:]
        hhi_trend_map[l2_id] = [quarterly[q] for q in sorted_qs]
    print(f"  HHI trends for {len(hhi_trend_map)} municipalities")

    # ═══════════════════════════════════════════════════════════════
    # NEW: 24. ALL quality seal providers per municipality (for /qualidade page)
    # ═══════════════════════════════════════════════════════════════
    print("Querying all quality providers for search page...")
    cur.execute("""
        SELECT qs.l2_id, a1.abbrev AS uf, a2.name AS city_name, a2.code AS city_code,
               p.name AS provider_name, qs.seal_level,
               qs.overall_score, qs.speed_score,
               qs.availability_score, qs.latency_score
        FROM quality_seals qs
        JOIN providers p ON p.id = qs.provider_id
        JOIN admin_level_2 a2 ON a2.id = qs.l2_id
        JOIN admin_level_1 a1 ON a1.id = a2.l1_id
        WHERE qs.year_half = (SELECT MAX(year_half) FROM quality_seals)
        ORDER BY a1.abbrev, a2.name, qs.overall_score DESC
    """)
    quality_by_state = defaultdict(lambda: defaultdict(list))
    for r in cur.fetchall():
        uf = r["uf"].lower()
        city_code = r["city_code"]
        quality_by_state[uf][city_code].append({
            "name": r["provider_name"],
            "seal": r["seal_level"],
            "score": round(float(r["overall_score"]), 1) if r["overall_score"] else 0,
            "speed": round(float(r["speed_score"]), 1) if r["speed_score"] else 0,
            "avail": round(float(r["availability_score"]), 1) if r["availability_score"] else 0,
            "latency": round(float(r["latency_score"]), 1) if r["latency_score"] else 0,
        })
    print(f"  Quality providers for {len(quality_by_state)} states")

    cur.close()
    conn.close()

    # Build municipality data grouped by state
    states = defaultdict(lambda: {
        "cities": [], "total_subs": 0, "isp_ids": set(),
        "fiber_subs": 0, "radio_subs": 0, "cable_subs": 0, "dsl_subs": 0,
        "fwa_subs": 0, "other_subs": 0,
        "quality": {"ouro": 0, "prata": 0, "bronze": 0, "sem_selo": 0},
        "uf": "", "state_name": "", "hhi_sum": 0.0, "hhi_count": 0,
        "penetration_sum": 0.0, "penetration_count": 0,
    })

    for row in rows:
        uf = row["uf"].lower()
        l2_id = row["l2_id"]
        total = row["total_subs"] or 0
        households = row["households"] or 0
        population = row["population"] or 0
        isp_count = row["isp_count"] or 0
        hhi = hhi_map.get(l2_id, 0)
        penetration = (total / households * 100) if households > 0 else 0

        fiber = row["fiber_subs"] or 0
        radio = row["radio_subs"] or 0
        cable = row["cable_subs"] or 0
        dsl = row["dsl_subs"] or 0
        fwa = row["fwa_subs"] or 0
        other = row["other_fixed_subs"] or 0

        q = quality_map.get(l2_id, {"ouro": 0, "prata": 0, "bronze": 0, "sem_selo": 0})

        city = {
            "name": row["name"],
            "slug": slugify(row["name"]),
            "code": row["code"],
            "population": population,
            "households": households,
            "subscribers": blind_subs(total, "muni"),
            "isp_count": isp_count,
            "penetration": round(penetration, 1),
            "hhi": round(hhi),
            "hhi_class": hhi_class(hhi),
            "fiber_pct": round(fiber / total * 100, 1) if total > 0 else 0,
            "radio_pct": round(radio / total * 100, 1) if total > 0 else 0,
            "cable_pct": round(cable / total * 100, 1) if total > 0 else 0,
            "dsl_pct": round(dsl / total * 100, 1) if total > 0 else 0,
            "fwa_pct": round(fwa / total * 100, 1) if total > 0 else 0,
            "quality": q,
            "teasers": {
                "tax_debt_isps": tax_debt_map.get(l2_id, 0),
                "complaints": complaints_map.get(l2_id, 0),
                "ouro_isps": q["ouro"],
            },
            "growth_pct": muni_growth.get(l2_id, 0),
            "opportunity": _classify_opportunity(opp_map.get(l2_id, {})),
            "schools": schools_map.get(l2_id, {}),
            "health": health_map.get(l2_id, {}),
            "safety": safety_map.get(l2_id, {}),
            "sanitation": sanitation_map.get(l2_id, {}),
            "economy": muni_economy_map.get(l2_id, {}),
            "density": density_map.get(l2_id, {}),
            "employment": muni_employment_map.get(l2_id, {}),
            "planning": planning_map.get(l2_id, {}),
            "top_providers": ouro_providers_map.get(l2_id, []),
            "hhi_trend": _classify_hhi_trend(hhi_trend_map.get(l2_id, [])),
        }

        st = states[uf]
        st["cities"].append(city)
        st["total_subs"] += total
        st["fiber_subs"] += fiber
        st["radio_subs"] += radio
        st["cable_subs"] += cable
        st["dsl_subs"] += dsl
        st["fwa_subs"] += fwa
        st["other_subs"] += other
        st["uf"] = row["uf"]
        st["state_name"] = row["state_name"]
        for k in ("ouro", "prata", "bronze", "sem_selo"):
            st["quality"][k] += q[k]
        if hhi > 0:
            st["hhi_sum"] += hhi
            st["hhi_count"] += 1
        if penetration > 0:
            st["penetration_sum"] += penetration
            st["penetration_count"] += 1

    # Handle duplicate slugs within same state
    for uf, st in states.items():
        slug_counts = defaultdict(list)
        for city in st["cities"]:
            slug_counts[city["slug"]].append(city)
        for slug, cities in slug_counts.items():
            if len(cities) > 1:
                for city in cities:
                    city["slug"] = f"{slug}-{city['code']}"

    # Sort cities by subscribers descending
    for st in states.values():
        st["cities"].sort(key=lambda c: c["subscribers"], reverse=True)

    # Build state summaries for index.json
    national_subs = 0
    national_isps = set()
    total_munis = 0
    state_summaries = []

    for uf in sorted(states.keys()):
        st = states[uf]
        total = st["total_subs"]
        national_subs += total
        total_munis += len(st["cities"])

        state_isp_count = sum(c["isp_count"] for c in st["cities"])  # approximate

        avg_hhi = st["hhi_sum"] / st["hhi_count"] if st["hhi_count"] > 0 else 0
        avg_pen = st["penetration_sum"] / st["penetration_count"] if st["penetration_count"] > 0 else 0

        fiber_pct = round(st["fiber_subs"] / total * 100, 1) if total > 0 else 0
        radio_pct = round(st["radio_subs"] / total * 100, 1) if total > 0 else 0
        cable_pct = round(st["cable_subs"] / total * 100, 1) if total > 0 else 0

        monopoly_count = sum(1 for c in st["cities"] if c["isp_count"] <= 1)
        coverage_gap_count = sum(1 for c in st["cities"] if c["isp_count"] <= 2)

        summary = {
            "uf": st["uf"],
            "name": st["state_name"],
            "subscribers": blind_subs(total, "state"),
            "municipalities": len(st["cities"]),
            "avg_hhi": round(avg_hhi),
            "avg_penetration": round(avg_pen, 1),
            "fiber_pct": fiber_pct,
            "radio_pct": radio_pct,
            "cable_pct": cable_pct,
            "quality": st["quality"],
            "monopoly_count": monopoly_count,
            "coverage_gap_count": coverage_gap_count,
        }
        state_summaries.append(summary)

    # National summary
    national = {
        "subscribers": blind_subs(national_subs, "state"),
        "municipalities": total_munis,
        "states": state_summaries,
        "period": latest_ym,
        "generated": date.today().isoformat(),
    }

    # Write index.json
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "states"), exist_ok=True)

    with open(os.path.join(OUT_DIR, "index.json"), "w") as f:
        json.dump(national, f, ensure_ascii=False, separators=(",", ":"), cls=DecimalEncoder)
    print(f"Wrote index.json ({len(state_summaries)} states)")

    # Write per-state files
    for uf in sorted(states.keys()):
        st = states[uf]
        total = st["total_subs"]
        avg_hhi = st["hhi_sum"] / st["hhi_count"] if st["hhi_count"] > 0 else 0
        avg_pen = st["penetration_sum"] / st["penetration_count"] if st["penetration_count"] > 0 else 0

        ts = state_timeseries.get(uf, [])
        tech_evo = state_tech_evo.get(uf, {})
        complaints = state_complaints.get(uf, [])
        employment = state_employment.get(uf, [])
        economy = state_economy.get(uf, {})

        state_data = {
            "uf": st["uf"],
            "name": st["state_name"],
            "subscribers": blind_subs(total, "state"),
            "municipalities": len(st["cities"]),
            "avg_hhi": round(avg_hhi),
            "avg_penetration": round(avg_pen, 1),
            "fiber_pct": round(st["fiber_subs"] / total * 100, 1) if total > 0 else 0,
            "radio_pct": round(st["radio_subs"] / total * 100, 1) if total > 0 else 0,
            "cable_pct": round(st["cable_subs"] / total * 100, 1) if total > 0 else 0,
            "quality": st["quality"],
            "monopoly_count": sum(1 for c in st["cities"] if c["isp_count"] <= 1),
            "coverage_gap_count": sum(1 for c in st["cities"] if c["isp_count"] <= 2),
            "timeseries": ts,
            "tech_evolution": tech_evo,
            "complaints": complaints,
            "employment": employment,
            "economy": economy,
            "cities": st["cities"],
            "period": latest_ym,
        }

        # State-level aggregates from city data
        cities_with_schools = [c for c in st["cities"] if c.get("schools")]
        schools_no_internet_total = sum(c["schools"].get("no_internet", 0) for c in cities_with_schools)
        cities_with_sanitation = [c for c in st["cities"] if c.get("sanitation") and c["sanitation"].get("water_pct", 0) > 0]
        avg_water = round(sum(c["sanitation"]["water_pct"] for c in cities_with_sanitation) / max(len(cities_with_sanitation), 1), 1)
        avg_sewage = round(sum(c["sanitation"].get("sewage_pct", 0) for c in cities_with_sanitation) / max(len(cities_with_sanitation), 1), 1)
        digital_gov_count = sum(1 for c in st["cities"] if c.get("planning", {}).get("digital_governance"))
        # Top 10 opportunity municipalities (use raw opp_map for ranking, emit level only)
        opp_level_rank = {"alto": 3, "moderado": 2, "baixo": 1, "muito_baixo": 0}
        cities_with_opp = [c for c in st["cities"] if c.get("opportunity", {}).get("level")]
        top10_opp = sorted(cities_with_opp,
                           key=lambda c: opp_level_rank.get(c["opportunity"]["level"], 0),
                           reverse=True)[:10]

        state_data["aggregates"] = {
            "schools_no_internet": schools_no_internet_total,
            "avg_water_pct": avg_water,
            "avg_sewage_pct": avg_sewage,
            "digital_governance_count": digital_gov_count,
            "top_opportunities": [
                {"name": c["name"], "slug": c["slug"], "level": c["opportunity"]["level"],
                 "subscribers": c["subscribers"], "isp_count": c["isp_count"]}
                for c in top10_opp
            ],
        }

        # Generate city narratives
        for city in st["cities"]:
            city["narrative"] = generate_city_narrative(
                city["name"], st["state_name"], uf, city
            )

        # Generate state narrative
        narrative = generate_narrative(uf, st["state_name"], state_data)
        state_data["insights"] = {"narrative": narrative}

        with open(os.path.join(OUT_DIR, "states", f"{uf}.json"), "w") as f:
            json.dump(state_data, f, ensure_ascii=False, separators=(",", ":"), cls=DecimalEncoder)

    print(f"Wrote {len(states)} state files")

    # ═══════════════════════════════════════════════════════════════
    # Write quality/{uf}.json files for consumer search page
    # ═══════════════════════════════════════════════════════════════
    quality_dir = os.path.join(OUT_DIR, "quality")
    quality_public_dir = os.path.join(SITEMAP_DIR, "data", "quality")
    os.makedirs(quality_dir, exist_ok=True)
    os.makedirs(quality_public_dir, exist_ok=True)
    # Build a slug lookup from all states
    code_to_slug = {}
    code_to_name = {}
    for uf_key, st in states.items():
        for city in st["cities"]:
            code_to_slug[city["code"]] = city["slug"]
            code_to_name[city["code"]] = city["name"]

    for uf_key in sorted(quality_by_state.keys()):
        cities_quality = []
        for city_code, providers in quality_by_state[uf_key].items():
            slug = code_to_slug.get(city_code, "")
            name = code_to_name.get(city_code, "")
            if slug and name:
                cities_quality.append({
                    "code": city_code,
                    "name": name,
                    "slug": slug,
                    "providers": providers,
                })
        cities_quality.sort(key=lambda c: c["name"])
        quality_json = json.dumps(cities_quality, ensure_ascii=False, separators=(",", ":"), cls=DecimalEncoder)
        with open(os.path.join(quality_dir, f"{uf_key}.json"), "w") as f:
            f.write(quality_json)
        with open(os.path.join(quality_public_dir, f"{uf_key}.json"), "w") as f:
            f.write(quality_json)
    print(f"Wrote {len(quality_by_state)} quality files")

    # Generate sitemap
    os.makedirs(SITEMAP_DIR, exist_ok=True)
    today = date.today().isoformat()
    urls = []
    urls.append(f'  <url><loc>{BASE_URL}/mercado</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>')

    for st_summary in state_summaries:
        uf_lower = st_summary["uf"].lower()
        urls.append(f'  <url><loc>{BASE_URL}/mercado/{uf_lower}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>')

    for uf in sorted(states.keys()):
        for city in states[uf]["cities"]:
            urls.append(f'  <url><loc>{BASE_URL}/mercado/{uf}/{city["slug"]}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>')

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_xml += "\n".join(urls)
    sitemap_xml += "\n</urlset>\n"

    with open(os.path.join(SITEMAP_DIR, "sitemap-mercado.xml"), "w") as f:
        f.write(sitemap_xml)
    print(f"Wrote sitemap-mercado.xml ({len(urls)} URLs)")

    # Generate core sitemap (non-mercado pages)
    core_pages = [
        ("/", "daily", "1.0"),
        ("/produto", "weekly", "0.9"),
        ("/dados", "weekly", "0.8"),
        ("/precos", "weekly", "0.9"),
        ("/sobre", "monthly", "0.7"),
        ("/raio-x", "weekly", "0.8"),
        ("/mapa-brasil", "weekly", "0.8"),
        ("/contato", "monthly", "0.6"),
        ("/blog", "weekly", "0.8"),
        ("/recursos", "monthly", "0.7"),
        ("/recursos/whitepaper", "monthly", "0.6"),
        ("/recursos/roi", "monthly", "0.6"),
        ("/recursos/funcionalidades", "monthly", "0.6"),
        ("/recursos/dados-confianca", "monthly", "0.6"),
        ("/mercado", "weekly", "0.9"),
        ("/qualidade", "weekly", "0.8"),
        ("/termos", "yearly", "0.3"),
        ("/privacidade", "yearly", "0.3"),
    ]

    # Add blog post slugs
    blog_slugs = [
        "crescimento-banda-larga-interior-2026",
        "top-50-municipios-oportunidade-isps-2026",
        "concentracao-mercado-hhi-caindo",
        "fibra-vs-radio-evolucao-tecnologica",
        "outorga-anatel-2026-provedores",
        "fust-2026-conectividade-rural",
        "consolidacao-isp-aquisicoes",
        "internet-rural-municipios-30-mil",
        "inteligencia-ma-dados-abertos",
        "custo-fibra-optica-km-brasil",
        "como-montar-provedor-de-internet-2026",
        "ranking-provedores-internet-brasil-2026",
        "banda-larga-brasil-panorama-2026",
    ]
    for slug in blog_slugs:
        core_pages.append((f"/blog/{slug}", "monthly", "0.6"))

    core_urls = []
    for path, freq, priority in core_pages:
        core_urls.append(f'  <url><loc>{BASE_URL}{path}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{priority}</priority></url>')

    core_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    core_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    core_xml += "\n".join(core_urls)
    core_xml += "\n</urlset>\n"

    with open(os.path.join(SITEMAP_DIR, "sitemap-core.xml"), "w") as f:
        f.write(core_xml)
    print(f"Wrote sitemap-core.xml ({len(core_urls)} URLs)")

    # Generate sitemap index
    sitemap_index = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_index += '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_index += f'  <sitemap><loc>{BASE_URL}/sitemap-core.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
    sitemap_index += f'  <sitemap><loc>{BASE_URL}/sitemap-mercado.xml</loc><lastmod>{today}</lastmod></sitemap>\n'
    sitemap_index += '</sitemapindex>\n'

    with open(os.path.join(SITEMAP_DIR, "sitemap.xml"), "w") as f:
        f.write(sitemap_index)
    print("Wrote sitemap.xml (index)")

    print(f"\nTotal: {total_munis} municipalities + 27 states + 1 national = {total_munis + 28} pages")


if __name__ == "__main__":
    main()
