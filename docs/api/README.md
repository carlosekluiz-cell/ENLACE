# API Reference — Enlace / Pulso Network

**Documentacao dos routers e endpoints REST da plataforma**

Versao 1.0 | Marco 2026

---

## Visao Geral

| Atributo | Valor |
|----------|-------|
| Base URL | `http://localhost:8010` |
| Versao da API | v1 |
| Autenticacao | JWT Bearer Token (header `Authorization: Bearer <token>`) |
| Rate Limiting | 60 req/min (geral), 10 req/min (auth) |
| Content-Type | `application/json` |
| CORS | Configuravel via environment |

---

## Autenticacao

Todos os endpoints (exceto login, register e health check) exigem autenticacao JWT.

### Obter Token

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@pulso.network",
  "password": "admin123"
}
```

Resposta:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "1",
  "email": "admin@pulso.network",
  "tenant_id": "default",
  "role": "admin",
  "full_name": "Admin"
}
```

---

## Routers

### 1. Auth — `/api/v1/auth`

Autenticacao, registro e gerenciamento de perfil.

| Metodo | Endpoint | Descricao | Auth |
|--------|----------|-----------|------|
| POST | `/api/v1/auth/login` | Login e obtencao de JWT token | Nao |
| POST | `/api/v1/auth/register` | Registro de novo usuario e tenant | Nao |
| GET | `/api/v1/auth/me` | Perfil do usuario autenticado | Sim |
| PUT | `/api/v1/auth/me` | Atualizar perfil (nome, email, preferencias) | Sim |
| PUT | `/api/v1/auth/me/password` | Alterar senha | Sim |

### 2. Geographic — `/api/v1/geo`

Busca de municipios, boundaries e consultas espaciais.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/geo/search` | Buscar municipios por nome | `q` (obrig.), `country`, `limit` |
| GET | `/api/v1/geo/{municipality_id}/boundary` | Boundary GeoJSON de um municipio | - |
| GET | `/api/v1/geo/within` | Municipios dentro de um raio | `lat`, `lng`, `radius_km`, `country` |

### 3. Market — `/api/v1/market`

Inteligencia de mercado: resumo, historico, concorrentes, heatmap.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/market/{municipality_id}/summary` | Resumo de mercado (mv_market_summary) | - |
| GET | `/api/v1/market/{municipality_id}/history` | Historico de assinantes (time series) | `months` (1-60) |
| GET | `/api/v1/market/{municipality_id}/competitors` | Breakdown de concorrentes + HHI | - |
| GET | `/api/v1/market/heatmap` | GeoJSON heatmap de municipios | `bbox` (obrig.), `metric`, `country` |
| GET | `/api/v1/market/{municipality_id}/quality-seals` | Selos de qualidade RQual/IQS | - |

Metricas de heatmap: `penetration`, `fiber_share`, `subscribers`

### 4. Opportunity — `/api/v1/opportunity`

Scoring de oportunidades, analise financeira, rota de fibra.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| POST | `/api/v1/opportunity/score` | Score de oportunidade para um municipio | Body: `country_code`, `area_type`, `area_id` |
| GET | `/api/v1/opportunity/top` | Top oportunidades ranked | `country`, `state`, `limit`, `min_score` |
| POST | `/api/v1/opportunity/financial` | Analise financeira (NPV, IRR, payback) | Body: `municipality_code`, `from_network_lat/lon`, `monthly_price_brl`, `technology` |
| POST | `/api/v1/opportunity/route` | Rota de fibra (Dijkstra + BOM) | Body: `from_lat/lon`, `to_lat/lon`, `prefer_corridors` |
| GET | `/api/v1/opportunity/base-stations` | Listar estacoes base | `country`, `technology`, `limit` |
| GET | `/api/v1/opportunity/{municipality_id}/competitors` | Analise competitiva | - |

### 5. Design — `/api/v1/design`

Projeto RF via Rust gRPC+TLS engine.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| POST | `/api/v1/design/coverage` | Cobertura RF (terreno SRTM 30m) | Body: `tower_lat/lon`, `tower_height_m`, `frequency_mhz`, `tx_power_dbm`, `antenna_gain_dbi`, `radius_m`, `grid_resolution_m` |
| POST | `/api/v1/design/optimize` | Otimizacao de posicionamento de torres | Body: `center_lat/lon`, `radius_m`, `coverage_target_pct`, `max_towers`, etc. |
| POST | `/api/v1/design/linkbudget` | Link budget microwave (ITU-R P.530) | Body: `frequency_ghz`, `distance_km`, `tx_power_dbm`, `antenna_gain_dbi`, `rain_rate_mmh` |
| GET | `/api/v1/design/profile` | Perfil de terreno entre dois pontos | `start_lat/lon`, `end_lat/lon`, `step_m` |

### 6. Compliance — `/api/v1/compliance`

Conformidade regulatoria brasileira.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/compliance/status` | Dashboard de conformidade | `provider_name`, `state`, `subscribers`, `services`, `classification`, `revenue_monthly` |
| GET | `/api/v1/compliance/norma4/impact` | Impacto Norma no. 4 (estado unico) | `state`, `subscribers`, `revenue_monthly`, `classification` |
| POST | `/api/v1/compliance/norma4/multi-state` | Impacto multi-estado (blended ICMS) | Body: `states[]`, `subscriber_count`, `current_classification` |
| GET | `/api/v1/compliance/licensing/check` | Check de threshold de licenciamento | `subscribers`, `services`, `revenue_monthly` |
| GET | `/api/v1/compliance/quality/check` | Verificacao de qualidade vs. thresholds | `provider_id`, `download_speed_pct`, `upload_speed_pct`, `latency_pct`, `availability_pct`, `ida_score`, `subscribers` |
| GET | `/api/v1/compliance/deadlines` | Deadlines regulatorios | `days_ahead` (1-3650) |
| GET | `/api/v1/compliance/regulations` | Listar regulamentacoes ativas | - |
| GET | `/api/v1/compliance/regulations/{id}` | Detalhe de uma regulamentacao | - |

### 7. Network Health — `/api/v1/health`

Inteligencia de falhas: clima, qualidade, manutencao, sazonalidade.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/health/weather-risk` | Risco climatico atual + previsao 7 dias | `municipality_id` |
| GET | `/api/v1/health/quality/{municipality_id}` | Benchmark de qualidade vs. pares | `provider_id` |
| GET | `/api/v1/health/quality/{municipality_id}/peers` | Comparacao com todos os provedores do municipio | `provider_id` |
| GET | `/api/v1/health/maintenance/priorities` | Prioridades de manutencao rankeadas | `provider_id` |
| GET | `/api/v1/health/seasonal/{municipality_id}` | Calendario sazonal de riscos (12 meses) | - |

### 8. Rural — `/api/v1/rural`

Conectividade rural: design hibrido, solar, funding, travessia de rio.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| POST | `/api/v1/rural/design` | Design de rede hibrida | Body: `community_lat/lon`, `population`, `area_km2`, `grid_power`, `terrain_type`, `biome` |
| GET | `/api/v1/rural/solar` | Dimensionamento de sistema solar | `lat`, `lon`, `power_watts`, `autonomy_days`, `battery_type` |
| POST | `/api/v1/rural/funding/match` | Match de programas de financiamento | Body: `municipality_code`, `municipality_population`, `state_code`, `technology`, `capex_brl` |
| GET | `/api/v1/rural/funding/programs` | Listar programas de financiamento | - |
| POST | `/api/v1/rural/community/profile` | Perfil de demanda comunitaria | Body: `population`, `avg_income_brl`, `has_school`, `has_health_unit`, `agricultural` |
| POST | `/api/v1/rural/crossing` | Design de travessia de rio | Body: `width_m`, `depth_m`, `current_speed_ms` |

Programas de financiamento tracked: FUST, Norte Conectado, New PAC, 5G Obligations, WiFi Brasil, BNDES ProConectividade.

### 9. M&A Intelligence — `/api/v1/mna`

Inteligencia para fusoes e aquisicoes de ISPs.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| POST | `/api/v1/mna/valuation` | Calculo de valuation (3 metodos) | Body: `subscriber_count`, `fiber_pct`, `monthly_revenue_brl`, `ebitda_margin_pct`, `state_code`, etc. |
| POST | `/api/v1/mna/targets` | Descoberta de targets de aquisicao | Body: `acquirer_states[]`, `acquirer_subscribers`, `min_subs`, `max_subs` |
| POST | `/api/v1/mna/seller/prepare` | Relatorio de preparacao para venda | Body: `provider_name`, `state_codes[]`, `subscriber_count`, etc. |
| GET | `/api/v1/mna/market` | Overview do mercado M&A por estado | `state` (UF code) |
| GET | `/api/v1/mna/provider/{provider_id}/details` | Detalhes CNPJ + BNDES do provedor | - |

Metodos de valuation:
1. **Subscriber Multiple**: Multiplo por assinante com ajuste por fibra, churn, crescimento, estado
2. **Revenue Multiple**: EV/Revenue e EV/EBITDA com multiplos de mercado
3. **DCF**: Fluxo de caixa descontado com WACC e valor terminal

### 10. Satellite — `/api/v1/satellite`

Inteligencia satelital via Sentinel-2/Google Earth Engine.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/satellite/{code}/indices` | Indices anuais (NDVI, NDBI, MNDWI, BSI) | `from_year`, `to_year` |
| GET | `/api/v1/satellite/{code}/growth` | Crescimento satelital vs. IBGE | - |
| GET | `/api/v1/satellite/ranking` | Ranking de municipios por crescimento | `state`, `metric`, `years`, `limit` |
| GET | `/api/v1/satellite/{code}/composite/{year}` | Metadata de compositos | - |
| POST | `/api/v1/satellite/{code}/compute` | Computacao on-demand (GEE) | - |

Metricas de ranking: `built_up_change_pct`, `built_up_change_km2`, `built_up_area_km2`, `built_up_pct`, `mean_ndvi`, `mean_ndbi`, `mean_mndwi`, `mean_bsi`, `ndvi_change_pct`

### 11. Intelligence — `/api/v1/intelligence`

Inteligencia agregada: contratos, FUST, BNDES, DOU, gazetas.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/intelligence/contracts` | Contratos governamentais de telecom | `state`, `keyword`, `limit` |
| GET | `/api/v1/intelligence/fust` | Gastos FUST/FUNTTEL | `year`, `state` |
| GET | `/api/v1/intelligence/bndes` | Emprestimos BNDES telecom | `state`, `limit` |
| GET | `/api/v1/intelligence/regulatory` | Atos regulatorios (DOU) | `keyword`, `limit` |
| GET | `/api/v1/intelligence/gazette` | Mencoes em gazetas municipais | `municipality_code`, `keyword`, `limit` |
| GET | `/api/v1/intelligence/municipality/{code}/profile` | Perfil completo do municipio | - |

### 12. Reports — `/api/v1/reports`

Geracao de relatorios em PDF, CSV e XLSX.

| Metodo | Endpoint | Descricao | Formato |
|--------|----------|-----------|---------|
| POST | `/api/v1/reports/market` | Relatorio de analise de mercado | `format=pdf\|csv\|xlsx` |
| POST | `/api/v1/reports/expansion` | Relatorio de oportunidade de expansao | `format=pdf\|csv\|xlsx` |
| POST | `/api/v1/reports/compliance` | Relatorio de conformidade regulatoria | `format=pdf\|csv\|xlsx` |
| POST | `/api/v1/reports/rural` | Relatorio de viabilidade rural | `format=pdf\|csv\|xlsx` |

### 13. Events — `/api/v1/events`

Server-Sent Events para atualizacoes em tempo real.

| Metodo | Endpoint | Descricao | Parametros |
|--------|----------|-----------|-----------|
| GET | `/api/v1/events/stream` | Stream SSE de eventos | `types` (comma-separated: pipeline_status, data_updated, notification) |

### 14. Admin — `/api/v1/admin`

Administracao de tenants e usuarios (requer role=admin).

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/admin/tenants` | Listar tenants |
| GET | `/api/v1/admin/users` | Listar usuarios |

### 15. Health Check

| Metodo | Endpoint | Descricao | Auth |
|--------|----------|-----------|------|
| GET | `/health` | Health check do sistema | Nao |

---

## Codigos de Resposta

| Codigo | Significado |
|--------|-------------|
| 200 | Sucesso |
| 400 | Parametros invalidos |
| 401 | Nao autenticado (JWT ausente ou invalido) |
| 403 | Nao autorizado (conta desativada) |
| 404 | Recurso nao encontrado |
| 422 | Entidade nao processavel (ex: rota sem caminho) |
| 429 | Rate limit excedido |
| 500 | Erro interno do servidor |

---

## Exemplos de Uso

### Buscar municipio e obter market summary

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8010/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@pulso.network","password":"admin123"}' \
  | jq -r .access_token)

# 2. Buscar municipio
curl -s http://localhost:8010/api/v1/geo/search?q=Manaus \
  -H "Authorization: Bearer $TOKEN" | jq '.[0]'

# 3. Market summary (usando o id retornado)
curl -s http://localhost:8010/api/v1/market/130260/summary \
  -H "Authorization: Bearer $TOKEN" | jq .

# 4. Concorrentes
curl -s http://localhost:8010/api/v1/market/130260/competitors \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Computar cobertura RF

```bash
curl -s -X POST http://localhost:8010/api/v1/design/coverage \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tower_lat": -3.1190,
    "tower_lon": -60.0217,
    "tower_height_m": 30,
    "frequency_mhz": 700,
    "tx_power_dbm": 43,
    "antenna_gain_dbi": 15,
    "radius_m": 5000,
    "grid_resolution_m": 30
  }' | jq .
```

### Top oportunidades de expansao em SP

```bash
curl -s "http://localhost:8010/api/v1/opportunity/top?state=SP&min_score=70&limit=20" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Valuation M&A

```bash
curl -s -X POST http://localhost:8010/api/v1/mna/valuation \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subscriber_count": 5000,
    "fiber_pct": 60,
    "monthly_revenue_brl": 500000,
    "ebitda_margin_pct": 30,
    "state_code": "SP"
  }' | jq .
```
