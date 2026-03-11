# Arquitetura do Sistema — Enlace / Pulso Network

Versao 2.0 | Marco 2026

---

## Diagrama de Arquitetura

```
                                   +--------------------+
                                   |   Navegador Web    |
                                   |   (Usuario ISP)    |
                                   +--------+-----------+
                                            |
                                            | HTTPS (porta 4100)
                                            v
                               +------------------------+
                               |    Frontend Next.js    |
                               |   (React / TypeScript) |
                               |   Deck.gl / Mapbox GL  |
                               |     30 paginas         |
                               +--------+---------------+
                                        |
                                        | REST / SSE (porta 8010)
                                        v
                  +---------------------------------------------+
                  |           Backend FastAPI (Python)           |
                  |                                             |
                  |  +---------------------------------------+  |
                  |  |       37 routers | 157 endpoints       |  |
                  |  +---------------------------------------+  |
                  |                                             |
                  |  Middleware: CORS, Security Headers,        |
                  |  Rate Limiter (60/min), Request Logging     |
                  +------+------------------+---+----+----------+
                         |                  |   |    |
             +-----------+      +-----------+   |    +----------+
             |                  |               |               |
             v                  v               v               v
   +---------+------+  +-------+--------+  +---+---+   +------+-------+
   | PostgreSQL +   |  |  Rust RF Engine |  | GEE   |   | ReceitaWS /  |
   | PostGIS        |  |  (gRPC + TLS)  |  | API   |   | APIs Externas|
   |                |  |  porta 50051   |  |       |   |              |
   | 62 tabelas     |  |  3.8 MB binary |  | Earth |   | PNCP, DOU,   |
   | 5.2 GB dados   |  |               |  | Engine|   | Anatel, IBGE |
   | 28M+ records   |  | +-----------+ |  +-------+   +--------------+
   |                |  | | enlace-   | |
   | mv_market_     |  | | propag.   | |
   |   summary      |  | +-----------+ |
   | (mat. view)    |  | | enlace-   | |
   |                |  | | optimizer | |
   +-------+--------+  | +-----------+ |
           ^            | | enlace-   | |
           |            | | terrain   | |
           |            | +-----------+ |
           |            | | enlace-   | |
           |            | | raster    | |
           |            | +-----------+ |
           |            | | enlace-   | |
           |            | | service   | |
           |            | +-----------+ |
           |            +-------+-------+
           |                    |
           |                    v
           |            +-------+-------+
           |            |  SRTM Tiles   |
           |            |  1,681 files  |
           |            |  40.6 GB      |
           |            |  /tmp/srtm    |
           |            +---------------+
           |
    +------+-------+
    |  Scheduler    |
    |  (APScheduler)|
    |               |
    | 38 pipelines  |
    | Diario 02:00  |
    | Semanal Dom   |
    | Mensal 1o dia |
    +---------------+
```

---

## Componentes do Sistema

### 1. Frontend — Next.js 14

| Aspecto | Detalhe |
|---------|---------|
| **Framework** | Next.js 14 (React 18, TypeScript) |
| **Porta** | 4100 (production build) |
| **Paginas** | 30 paginas interativas |
| **Visualizacao** | Deck.gl (3D), Mapbox GL JS, recharts |
| **Autenticacao** | JWT tokens (cookie + header) |
| **Comunicacao** | REST API (fetch) + SSE (EventSource) |
| **Responsividade** | Mobile-first, Tailwind CSS |

Navegacao (6 secoes agrupadas):

**Inteligencia de Mercado:**
- Mapa, Expansao, Concorrencia, Research, Velocidade, Hex Grid, Analise Espacial, Indice Starlink

**Infraestrutura:**
- Projeto RF, Satelite, Fibra, Cobertura, FWA vs Fibra, Backhaul, Risco Climatico, Peering, IX.br

**Conformidade:**
- Conformidade, Obrigacoes 5G

**M&A & Financas:**
- M&A, Pulso Score, Credito ISP

**Rural & Social:**
- Rural, Saude

**Dados & AI:**
- Relatorios, Consulta SQL, Alertas, Analise Cruzada

### 2. Backend — Python FastAPI

| Aspecto | Detalhe |
|---------|---------|
| **Framework** | FastAPI (async, Python 3.11+) |
| **Porta** | 8010 |
| **Routers** | 37 routers, 157 endpoints |
| **Autenticacao** | JWT (bcrypt hash, token com sub/email/tenant/role) |
| **Rate Limiting** | 60 req/min geral, 10 req/min auth |
| **Logging** | Structured JSON, correlation IDs por request |
| **Security Headers** | HSTS, X-Frame-Options, CSP, XSS Protection |
| **CORS** | Configuravel por environment |
| **ORM** | SQLAlchemy 2.0 (async) |

Routers:

**Foundation (15):**

| Router | Prefixo | Descricao |
|--------|---------|-----------|
| auth | `/api/v1/auth` | Login, registro, perfil, troca de senha |
| market | `/api/v1/market` | Market summary, historico, concorrentes, heatmap, selos de qualidade |
| opportunity | `/api/v1/opportunity` | Scoring, top opportunities, analise financeira, rota de fibra, base stations |
| design | `/api/v1/design` | Cobertura RF, otimizacao, link budget, perfil de terreno |
| compliance | `/api/v1/compliance` | Dashboard, Norma 4, licenciamento, qualidade, deadlines, regulamentos |
| network_health | `/api/v1/health` | Risco climatico, benchmark de qualidade, manutencao, calendario sazonal |
| rural | `/api/v1/rural` | Design hibrido, solar, funding, perfil comunitario, travessia de rio |
| mna | `/api/v1/mna` | Valuation, targets, seller prepare, market overview, detalhes do provedor |
| satellite | `/api/v1/satellite` | Indices, crescimento, ranking, compositos, computacao on-demand |
| intelligence | `/api/v1/intelligence` | Contratos governamentais, FUST, BNDES, DOU, gazetas, perfil municipal |
| geographic | `/api/v1/geo` | Busca de municipios, boundaries GeoJSON, busca por raio |
| reports | `/api/v1/reports` | Geracao de relatorios (PDF, CSV, XLSX) |
| events | `/api/v1/events` | Server-Sent Events (SSE) para atualizacoes em tempo real |
| admin | `/api/v1/admin` | Administracao de tenants e usuarios |
| health | `/health` | Health check do sistema |

**Wave 1 (11):**

| Router | Prefixo | Descricao |
|--------|---------|-----------|
| buildings | `/api/v1/buildings` | Footprints de edificios, contagem por municipio |
| fiber | `/api/v1/fiber` | Roteamento de fibra, custos, segmentos |
| h3 | `/api/v1/h3` | Celulas H3, agregacao hexagonal |
| timeseries | `/api/v1/timeseries` | Series temporais de assinantes, tendencias |
| speedtest | `/api/v1/speedtest` | Tiles de velocidade, ranking municipal |
| coverage | `/api/v1/coverage` | Validacao de cobertura, obrigacoes |
| colocation | `/api/v1/colocation` | Analise de colocalizacao de torres |
| alerts | `/api/v1/alerts` | Regras de alerta, eventos, notificacoes |
| mna_enhanced | `/api/v1/mna-enhanced` | Comparaveis, sinergias, due diligence, espectro |
| pulso_score | `/api/v1/pulso-score` | Score composto de provedores |
| credit | `/api/v1/credit` | Score de credito de ISPs |

**Wave 2 (9):**

| Router | Prefixo | Descricao |
|--------|---------|-----------|
| spatial_analytics | `/api/v1/spatial` | Analise espacial avancada, clusters, autocorrelacao |
| starlink_threat | `/api/v1/starlink` | Indice de ameaca Starlink por municipio |
| fwa_fiber | `/api/v1/fwa-fiber` | Comparacao FWA vs fibra, break-even |
| backhaul | `/api/v1/backhaul` | Modelagem de backhaul, custos, capacidade |
| weather_risk | `/api/v1/weather-risk` | Risco climatico para infraestrutura |
| compliance_rgst | `/api/v1/compliance-rgst` | Conformidade RGST 777 |
| obligations | `/api/v1/obligations` | Obrigacoes de cobertura 5G |
| peering | `/api/v1/peering` | Redes de peering, IXPs proximos |
| ixp | `/api/v1/ixp` | Localizacoes IX.br, trafego historico |

**Wave 3 (1):**

| Router | Prefixo | Descricao |
|--------|---------|-----------|
| cross_analytics | `/api/v1/analytics` | HHI, gaps de cobertura, correlacoes, investimento, anomalias |

**Research (1):**

| Router | Prefixo | Descricao |
|--------|---------|-----------|
| research | `/api/v1/research` | Pesquisas de mercado, tendencias, relatorios de pesquisa |

### Servicos (23)

| Servico | Funcao |
|---------|--------|
| market_intelligence | Inteligencia de mercado, concorrentes, heatmaps |
| rf_client | Cliente gRPC para o motor RF Rust |
| fiber_routing | Roteamento otimizado de fibra optica |
| h3_service | Operacoes com celulas hexagonais H3 |
| timeseries_service | Series temporais e previsoes |
| forecasting | Previsao com regressao polinomial (numpy polyfit) |
| colocation_service | Analise de colocalizacao de torres |
| alert_engine | Motor de alertas e notificacoes |
| mna_service | Valuation, comparaveis, sinergias, due diligence, espectro |
| pulso_score | Score composto de saude do provedor |
| credit_scoring | Score de credito para ISPs |
| cross_analytics | HHI, gaps de cobertura, sobreposicao, densidade de torres |
| social_gaps | Conectividade de escolas e postos de saude |
| investment_priority | Score composto de prioridade de investimento + anomalias (pyod) |
| spatial_analytics | Analise espacial, clusters, autocorrelacao |
| starlink_threat | Modelagem de ameaca Starlink |
| fwa_fiber | Comparacao FWA vs fibra optica |
| backhaul_model | Modelagem de backhaul e capacidade |
| weather_risk | Risco climatico para infraestrutura telecom |
| compliance_checker | Verificacao de conformidade regulatoria |
| coverage_obligations | Obrigacoes de cobertura 5G |
| proto | Definicoes gRPC (Protocol Buffers) |

### 3. Motor RF — Rust (gRPC + TLS)

| Aspecto | Detalhe |
|---------|---------|
| **Linguagem** | Rust (edition 2021) |
| **Comunicacao** | gRPC com TLS mutuo (tonic 0.12) |
| **Porta** | 50051 |
| **Binary** | 3.8 MB (release build) |
| **LOC** | 9.000+ linhas de codigo |
| **Testes** | 22 unit tests passing |
| **Paralelismo** | rayon (parallel iterators) |
| **Matematica** | nalgebra, num-traits |
| **Geoespacial** | geo 0.28, proj 0.27, h3o 0.6 |
| **I/O** | memmap2 (memory-mapped SRTM tiles) |

Crates do workspace:

| Crate | LOC | Funcao |
|-------|-----|--------|
| **enlace-propagation** | 3.511 | FSPL, Hata, P.530, P.1812, ITM, TR38.901, P.676, P.838, difracao, vegetacao |
| **enlace-optimizer** | 1.786 | Set-cover + simulated annealing, estimativa CAPEX |
| **enlace-terrain** | 981 | Leitura SRTM, perfil de elevacao, deteccao de obstrucao |
| **enlace-raster** | 779 | Grid de cobertura, interpolacao de sinal |
| **enlace-service** | 600+ | Servidor gRPC+TLS, handlers de request, proto definitions |
| **enlace-tiles** | 347 | Cloud-Optimized GeoTIFF para XYZ tiles |

Variaveis de ambiente:
- `SRTM_TILE_DIR` — Diretorio com tiles SRTM (`/tmp/srtm`)
- `TLS_CERT` — Certificado TLS do servidor
- `TLS_KEY` — Chave privada TLS
- `RF_ENGINE_TLS_CA` — Certificado CA para o cliente Python

### 4. Banco de Dados — PostgreSQL + PostGIS

| Aspecto | Detalhe |
|---------|---------|
| **Engine** | PostgreSQL 15+ com PostGIS 3.x |
| **Database/User** | `enlace` / `enlace` |
| **Tamanho** | ~5.2 GB (dados) + 40.6 GB (SRTM tiles em disco) |
| **Tabelas** | 62 tabelas |
| **Registros** | 28M+ |
| **Materialized View** | `mv_market_summary` (refresh apos mudancas em broadband) |
| **Spatial** | SRID 4326 (WGS84), ST_DWithin, ST_MakeEnvelope, ST_AsGeoJSON |

### 5. Pipeline Scheduler — APScheduler

| Aspecto | Detalhe |
|---------|---------|
| **Framework** | APScheduler (BlockingScheduler) |
| **Execucao** | `python -m python.pipeline.scheduler` |
| **Modo unico** | `--once` (roda tudo uma vez e sai) |
| **Total de pipelines** | 38 (31 scheduled + 7 on-demand) |

Agenda (31 scheduled):

| Horario (UTC) | Frequencia | Grupo | Pipelines |
|---------------|-----------|-------|-----------|
| 02:00 | Diario | Telecom | Anatel providers, broadband, base stations, quality |
| 02:30 | Diario | Intelligence | PNCP contracts, DOU regulatory, Querido Diario gazettes |
| 03:00 | Diario | Clima | INMET/Open-Meteo weather |
| 04:00 Dom | Semanal | Economico | IBGE PIB, projections, POF, ANP fuel, ANEEL power, SNIS, BNDES |
| 04:30 Dom | Semanal | Enriquecimento | CNPJ enrichment, RQUAL quality seals, FUST spending |
| 05:00 dia 1 | Mensal | Geografico | IBGE census, SRTM, MapBiomas, OSM roads, backhaul, health, schools, MUNIC, CNEFE, CAGED, Atlas Violencia |
| 06:00 dia 1 | Mensal | Satelite | Sentinel-2 urban growth |

On-demand (7):

| Pipeline | Descricao |
|----------|-----------|
| ms_buildings | Microsoft Building Footprints |
| opencellid | Torres OpenCellID |
| ookla_speedtest | Speedtest tiles (Ookla) |
| h3_grid | Grid hexagonal H3 |
| pulso_score | Score composto de provedores |
| peeringdb | Redes de peering (PeeringDB) |
| ixbr | Pontos de troca de trafego IX.br |

Pos-processamento automatico:
- Refresh de `mv_market_summary`
- Recompute de `opportunity_scores` (formula com 8 fatores)
- Recompute de `competitive_analysis` (HHI, tendencia, threat level)

---

## Fluxo de Dados

```
Fontes Externas          Pipelines               Banco de Dados         API/Frontend
+-------------+      +---------------+       +-----------------+     +-------------+
| Anatel      +----->| anatel_broad. +------>| broadband_subs  +---->| /market/*   |
| IBGE        +----->| ibge_census   +------>| admin_level_2   +---->| /geo/*      |
| INMET       +----->| inmet_weather +------>| weather_obs     +---->| /health/*   |
| OSM         +----->| osm_roads     +------>| road_segments   +---->| /opportunity|
| SRTM/NASA   +----->| srtm_terrain  +------>| srtm_tiles      +---->| /design/*   |
| PNCP        +----->| pncp_contracts+------>| gov_contracts   +---->| /intell.*   |
| ReceitaWS   +----->| cnpj_enrichm. +------>| provider_details+---->| /mna/*      |
| GEE/Sentinel+----->| sentinel_grow.+------>| sentinel_urban  +---->| /satellite/*|
+-------------+      +-------+-------+       +--------+--------+     +------+------+
                              |                        |                      |
                              v                        v                      v
                     +--------+--------+      +--------+--------+     +------+------+
                     | Recompute       |      | mv_market_      |     | Relatorios  |
                     | opportunity_    |      |    summary       |     | PDF/CSV/    |
                     | scores + CA     |      | (materialized)  |     | XLSX        |
                     +-----------------+      +-----------------+     +-------------+
```

---

## Seguranca

### Autenticacao e Autorizacao

| Camada | Implementacao |
|--------|--------------|
| **Autenticacao** | JWT tokens com bcrypt password hashing |
| **Token payload** | sub (user_id), email, tenant_id, role, full_name |
| **Multi-tenant** | Tenant isolation via tenant_id no JWT |
| **Roles** | admin, viewer (extensivel) |
| **Dev mode** | Auto-create user no primeiro login (desabilitavel) |

### Comunicacao

| Canal | Seguranca |
|-------|-----------|
| Frontend <-> Backend | HTTPS |
| Backend <-> RF Engine | gRPC com TLS mutuo (ca-cert.pem, server-cert.pem, server-key.pem) |
| Backend <-> PostgreSQL | Connection string com credenciais |
| Backend <-> APIs externas | HTTPS |

### Middleware de Seguranca

| Middleware | Funcao |
|-----------|--------|
| CORS | Origins configuraveis, credentials habilitadas |
| Security Headers | HSTS, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, CSP |
| Rate Limiter | 60 req/min geral, 10 req/min para auth endpoints |
| Request Logging | Correlation IDs, structured JSON logging |
| Global Exception Handler | Previne vazamento de stack traces |

### Certificados TLS

Localizacao: `/home/dev/enlace/certs/`
- `ca-cert.pem` — Certificado da CA
- `server-cert.pem` — Certificado do servidor (RF Engine)
- `server-key.pem` — Chave privada do servidor

---

## Deploy

### Servicos

| Servico | Porta | Comando de Inicio |
|---------|-------|-------------------|
| Frontend (Next.js) | 4100 | `npm run start` (production build) |
| Backend (FastAPI) | 8010 | `uvicorn python.api.main:app --port 8010` |
| RF Engine (Rust) | 50051 | `./rust/target/release/enlace-rf-engine` |
| Scheduler | N/A | `python -m python.pipeline.scheduler` |
| PostgreSQL | 5432 | Servico do sistema |

### Requisitos de Sistema

| Recurso | Minimo | Recomendado |
|---------|--------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Disco | 60 GB | 100+ GB (SRTM tiles = 40.6 GB) |
| Python | 3.11+ | 3.12 |
| Rust | 1.75+ | Latest stable |
| PostgreSQL | 15 | 16 |
| PostGIS | 3.3+ | 3.4 |
| Node.js | 18+ | 20 |

### Variaveis de Ambiente Principais

| Variavel | Descricao | Exemplo |
|----------|-----------|---------|
| `DATABASE_URL` | Connection string PostgreSQL | `postgresql://enlace:...@localhost/enlace` |
| `SRTM_TILE_DIR` | Diretorio de tiles SRTM | `/tmp/srtm` |
| `TLS_CERT` | Certificado TLS (RF Engine) | `/home/dev/enlace/certs/server-cert.pem` |
| `TLS_KEY` | Chave TLS (RF Engine) | `/home/dev/enlace/certs/server-key.pem` |
| `RF_ENGINE_TLS_CA` | CA cert para cliente gRPC | `/home/dev/enlace/certs/ca-cert.pem` |
| `DEV_MODE` | Habilita auto-create de usuarios | `1` |
| `CORS_ORIGINS` | Origins permitidas para CORS | `http://localhost:4100` |
| `JWT_SECRET` | Segredo para assinatura JWT | (gerado) |
