"""
Pulso MCP Server — Inteligência Telecom para LLMs.

Exposes Pulso's top API endpoints as MCP tools so AI agents
can query Brazilian ISP market intelligence, compliance status,
rural connectivity design, and M&A valuations.

Run:
    pip install "mcp[cli]"
    python -m python.mcp_server

Or via stdio transport for Claude Code:
    python python/mcp_server.py
"""
import json
import logging
import os
import sys

import httpx

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = os.getenv("PULSO_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("PULSO_API_TOKEN", "")

mcp = FastMCP(
    "Pulso - Inteligência Telecom",
    json_response=True,
)

# ---------------------------------------------------------------------------
# Internal HTTP helper
# ---------------------------------------------------------------------------

def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if API_TOKEN:
        h["Authorization"] = f"Bearer {API_TOKEN}"
    return h


def _get(path: str, params: dict | None = None) -> dict:
    """GET request to Pulso API."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{API_BASE}{path}", params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: dict) -> dict:
    """POST request to Pulso API."""
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{API_BASE}{path}", json=body, headers=_headers())
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tools — Oportunidades de expansão
# ---------------------------------------------------------------------------

@mcp.tool()
def top_expansion_opportunities(
    limit: int = 10,
    state: str | None = None,
) -> str:
    """Lista os municípios com maior score de oportunidade de expansão para ISPs.

    Retorna municípios ranqueados por score composto (demanda, competição,
    infraestrutura, crescimento). Use para identificar onde expandir.

    Args:
        limit: Número de municípios a retornar (padrão 10, max 50)
        state: Filtrar por UF (ex: "SP", "MG"). Opcional.
    """
    params = {"limit": str(min(limit, 50))}
    if state:
        params["state"] = state.upper()
    data = _get("/api/v1/opportunity/top", params=params)
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def municipality_score(municipality_code: str) -> str:
    """Score de oportunidade detalhado para um município específico.

    Retorna sub-scores de demanda, competição, infraestrutura e crescimento
    junto com dados demográficos.

    Args:
        municipality_code: Código IBGE de 7 dígitos do município (ex: "2304400")
    """
    data = _get(f"/api/v1/opportunity/score/{municipality_code}")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — Inteligência de mercado
# ---------------------------------------------------------------------------

@mcp.tool()
def market_summary(municipality_id: int) -> str:
    """Resumo de mercado de banda larga de um município.

    Retorna total de assinantes, percentual de fibra, penetração,
    número de provedores e velocidade mediana.

    Args:
        municipality_id: ID interno do município no Pulso
    """
    data = _get(f"/api/v1/market/{municipality_id}/summary")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def market_competitors(municipality_id: int) -> str:
    """Análise competitiva de um município — provedores, market share, HHI.

    Args:
        municipality_id: ID interno do município no Pulso
    """
    data = _get(f"/api/v1/market/{municipality_id}/competitors")
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — Conformidade regulatória
# ---------------------------------------------------------------------------

@mcp.tool()
def compliance_status(
    provider_name: str,
    state: str,
    subscribers: int,
) -> str:
    """Verifica o status de conformidade regulatória de um provedor.

    Retorna checks obrigatórios (Anatel, FUST, SCM, etc.), prazos,
    custos estimados e ações necessárias.

    Args:
        provider_name: Nome do provedor (ex: "Minha Fibra Telecom")
        state: UF do provedor (ex: "SP")
        subscribers: Número atual de assinantes
    """
    data = _get("/api/v1/compliance/status", params={
        "provider_name": provider_name,
        "state": state,
        "subscribers": str(subscribers),
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def compliance_deadlines(days_ahead: int = 90) -> str:
    """Lista prazos regulatórios próximos (Anatel, FUST, FUNTTEL, etc.).

    Args:
        days_ahead: Número de dias à frente para buscar prazos (padrão 90)
    """
    data = _get("/api/v1/compliance/deadlines", params={"days_ahead": str(days_ahead)})
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def norma4_tax_impact(state: str, subscribers: int, revenue_monthly: float) -> str:
    """Calcula o impacto tributário da Norma 4 (ICMS sobre telecom) para um provedor.

    Retorna alíquota ICMS, impacto mensal/anual, percentual da receita,
    e opções de reestruturação com economia estimada.

    Args:
        state: UF (ex: "SP")
        subscribers: Número de assinantes
        revenue_monthly: Receita mensal em BRL
    """
    data = _get("/api/v1/compliance/norma4/impact", params={
        "state": state,
        "subscribers": str(subscribers),
        "revenue_monthly": str(revenue_monthly),
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — Conectividade rural
# ---------------------------------------------------------------------------

@mcp.tool()
def rural_design(
    latitude: float,
    longitude: float,
    population: int,
    area_km2: float,
    has_grid_power: bool = True,
    community_name: str = "",
) -> str:
    """Projeto completo de conectividade para comunidade rural.

    Gera design de backhaul (satélite/rádio), última milha (TVWS/WiFi),
    solução de energia, lista de equipamentos, CAPEX e OPEX estimados.

    Args:
        latitude: Latitude da comunidade
        longitude: Longitude da comunidade
        population: População estimada
        area_km2: Área em km²
        has_grid_power: Se tem energia elétrica da rede
        community_name: Nome da comunidade (opcional)
    """
    data = _post("/api/v1/rural/design", {
        "community_lat": latitude,
        "community_lon": longitude,
        "population": population,
        "area_km2": area_km2,
        "has_grid_power": has_grid_power,
        "community_name": community_name,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def rural_funding_programs() -> str:
    """Lista programas de financiamento para conectividade rural.

    Retorna FUST, BNDES, Fundo Amazônia e outros programas com
    critérios de elegibilidade, valores máximos e prazos.
    """
    data = _get("/api/v1/rural/funding/programs")
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def rural_funding_match(
    latitude: float,
    longitude: float,
    population: int,
    subscribers: int,
) -> str:
    """Encontra programas de financiamento compatíveis com uma comunidade.

    Args:
        latitude: Latitude
        longitude: Longitude
        population: População
        subscribers: Assinantes atuais na área
    """
    data = _post("/api/v1/rural/funding/match", {
        "latitude": latitude,
        "longitude": longitude,
        "population": population,
        "subscribers": subscribers,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — M&A Intelligence
# ---------------------------------------------------------------------------

@mcp.tool()
def mna_valuation(
    subscriber_count: int,
    fiber_pct: float,
    monthly_revenue_brl: float,
    ebitda_margin_pct: float,
    state_code: str,
    monthly_churn_pct: float = 2.0,
    growth_rate_12m: float = 5.0,
    net_debt_brl: float = 0,
) -> str:
    """Valuation completo de um ISP usando 3 metodologias.

    Retorna faixa de valor (baixo/médio/alto) usando múltiplos de
    assinante, múltiplos de receita e DCF (fluxo de caixa descontado).

    Args:
        subscriber_count: Total de assinantes
        fiber_pct: Percentual de fibra (0-100)
        monthly_revenue_brl: Receita mensal em BRL
        ebitda_margin_pct: Margem EBITDA (0-100)
        state_code: UF (ex: "SP")
        monthly_churn_pct: Churn mensal (padrão 2%)
        growth_rate_12m: Crescimento 12 meses (padrão 5%)
        net_debt_brl: Dívida líquida em BRL (padrão 0)
    """
    data = _post("/api/v1/mna/valuation", {
        "subscriber_count": subscriber_count,
        "fiber_pct": fiber_pct,
        "monthly_revenue_brl": monthly_revenue_brl,
        "ebitda_margin_pct": ebitda_margin_pct,
        "state_code": state_code,
        "monthly_churn_pct": monthly_churn_pct,
        "growth_rate_12m": growth_rate_12m,
        "net_debt_brl": net_debt_brl,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def mna_find_targets(
    acquirer_states: list[str],
    acquirer_subscribers: int,
    min_subs: int = 1000,
    max_subs: int = 50000,
) -> str:
    """Identifica alvos de aquisição compatíveis com o perfil do comprador.

    Retorna provedores ranqueados por score estratégico, financeiro,
    risco de integração e sinergias estimadas.

    Args:
        acquirer_states: UFs de atuação do comprador (ex: ["SP", "MG"])
        acquirer_subscribers: Assinantes atuais do comprador
        min_subs: Mínimo de assinantes do alvo
        max_subs: Máximo de assinantes do alvo
    """
    data = _post("/api/v1/mna/targets", {
        "acquirer_states": acquirer_states,
        "acquirer_subscribers": acquirer_subscribers,
        "min_subs": min_subs,
        "max_subs": max_subs,
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def mna_market_overview(state: str) -> str:
    """Panorama do mercado de M&A de ISPs em um estado.

    Retorna total de ISPs, assinantes, valuation médio por assinante,
    percentual de fibra e transações recentes.

    Args:
        state: UF (ex: "SP")
    """
    data = _get(f"/api/v1/mna/market", params={"state": state})
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — Saúde da rede
# ---------------------------------------------------------------------------

@mcp.tool()
def network_weather_risk(municipality_id: int) -> str:
    """Risco climático atual para infraestrutura de rede em um município.

    Retorna score de risco geral, risco de precipitação, vento e
    temperatura com detalhes da estação meteorológica mais próxima.

    Args:
        municipality_id: ID do município no Pulso
    """
    data = _get("/api/v1/health/weather-risk", params={"municipality_id": str(municipality_id)})
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def network_maintenance_priorities(provider_id: int) -> str:
    """Municípios ranqueados por prioridade de manutenção preventiva.

    Retorna scores de risco climático, idade da infraestrutura,
    tendência de qualidade, receita em risco e pressão competitiva.

    Args:
        provider_id: ID do provedor no Pulso
    """
    data = _get("/api/v1/health/maintenance/priorities", params={"provider_id": str(provider_id)})
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tools — Projeto RF
# ---------------------------------------------------------------------------

@mcp.tool()
def rf_coverage_simulation(
    tower_lat: float,
    tower_lon: float,
    tower_height_m: float = 30,
    frequency_mhz: float = 700,
    tx_power_dbm: float = 43,
    antenna_gain_dbi: float = 15,
    radius_m: float = 5000,
) -> str:
    """Simulação de cobertura RF de uma torre.

    Retorna percentual de cobertura, área coberta, sinal médio/mín/máx
    e grid de pontos com intensidade de sinal.

    Args:
        tower_lat: Latitude da torre
        tower_lon: Longitude da torre
        tower_height_m: Altura da torre em metros (padrão 30)
        frequency_mhz: Frequência em MHz (padrão 700)
        tx_power_dbm: Potência de transmissão em dBm (padrão 43)
        antenna_gain_dbi: Ganho da antena em dBi (padrão 15)
        radius_m: Raio de simulação em metros (padrão 5000)
    """
    data = _post("/api/v1/design/coverage", {
        "tower_lat": tower_lat,
        "tower_lon": tower_lon,
        "tower_height_m": tower_height_m,
        "frequency_mhz": frequency_mhz,
        "tx_power_dbm": tx_power_dbm,
        "antenna_gain_dbi": antenna_gain_dbi,
        "radius_m": radius_m,
        "grid_resolution_m": 50,
        "apply_vegetation": True,
        "country_code": "BR",
    })
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
