# Enlace/Pulso Network: Disruptive Innovation Research

**Date**: 2026-03-11
**Scope**: Data moat expansion and user engagement features for a Brazilian telecom intelligence platform
**Current baseline**: 31 pipelines, 12M+ records, 5,570 municipalities, Rust RF engine, M&A valuation, regulatory compliance, satellite imagery, rural connectivity

---

## Part 1: DATA MOAT -- New Data Sources and Analytics

### 1.1 Real-Time Network Quality Monitoring (Crowdsourced Speed Tests + BGP/AS Path Analysis)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 8-10 weeks |

**What it is**: Ingest crowdsourced speed test results (from M-Lab NDT, RIPE Atlas probes, and/or a custom lightweight speed test SDK embedded in ISP customer portals) plus BGP routing data (AS path length, route stability, prefix hijack detection) to build a real-time network quality layer across Brazil. Correlate with the existing Anatel RQUAL quality seals already in the platform.

**Why it matters**: The platform already has static quality seals from Anatel (33,420 records). Real-time quality data would let ISPs see *today's* network performance, not last semester's regulatory snapshot. BGP path analysis reveals upstream transit quality -- critical for ISPs choosing between transit providers or evaluating peering strategies.

**Accelerators**:
- [M-Lab NDT](https://www.measurementlab.net/) -- Open data, REST API, all speed test results are public domain. Brazil has M-Lab servers.
- [RIPE Atlas](https://atlas.ripe.net/) -- 12,000+ probes globally, REST API, free tier for measurements. ~200 probes in Brazil.
- [BGPStream (CAIDA)](https://bgpstream.caida.org/) -- Open-source framework for live and historical BGP data from RouteViews + RIPE RIS.
- [BGPKIT](https://bgpkit.com/) -- Open-source toolkit indexing 70+ BGP collectors with ASN/prefix filtering.
- [pyasn](https://pypi.org/project/pyasn/) -- Fast IP-to-ASN lookup from MRT/RIB archives.

**Implementation approach**: New pipeline `mlab_speedtest.py` pulling from M-Lab BigQuery public dataset (daily). BGP pipeline using pybgpstream to track Brazilian ASNs. New `network_quality_realtime` table with H3 hex index for sub-municipal granularity. Frontend: overlay heatmap on existing MapView component.

---

### 1.2 Social Media Sentiment Analysis for ISP Reputation

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 5-6 weeks |

**What it is**: Monitor Twitter/X, Reclame Aqui (Brazil's dominant consumer complaint platform), and Google Reviews for mentions of ISPs. Use Portuguese-language NLP to classify sentiment, detect service outage complaints, and track reputation trends per provider per municipality.

**Why it matters**: ISPs making M&A decisions (the platform already has 3-method valuation) need to understand target reputation. ISPs monitoring competitors need to know when a rival's customers are unhappy. Sentiment data enriches the existing `competitive_analysis` and `quality_seals` tables.

**Accelerators**:
- [BERTimbau](https://huggingface.co/neuralmind/bert-base-portuguese-cased) -- Pre-trained BERT for Brazilian Portuguese on HuggingFace. State-of-the-art for PT-BR sentiment.
- [TweetNLP](https://github.com/cardiffnlp/tweetnlp) -- Twitter-specialized NLP with sentiment, hate speech, and offensive language detection.
- [Reclame Aqui](https://www.reclameaqui.com.br/) -- Brazil's largest consumer complaint platform. Public pages can be scraped (no official API, but structured HTML).
- [snscrape](https://github.com/JustAnotherArchivist/snscrape) -- Open-source social media scraper for Twitter/X, Reddit, etc.

**Implementation approach**: New pipeline `isp_sentiment.py` scraping Reclame Aqui ISP pages daily + Twitter mentions. BERTimbau model fine-tuned on telecom complaint corpus. New `isp_sentiment` table (provider_id, source, sentiment_score, mention_count, date). Enriches M&A `/valuation` and `/targets` endpoints.

---

### 1.3 H3 Hexagonal Grid Analytics for Sub-Municipal Granularity

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 4-5 weeks |

**What it is**: Index all geospatial data (subscribers, base stations, buildings, speed tests, coverage) into Uber's H3 hexagonal grid at resolution 7 (~5.16 km2) and resolution 9 (~0.105 km2). Enable sub-municipal analysis -- neighborhoods, districts, rural vs urban pockets within a single municipality.

**Why it matters**: The platform currently operates at municipality level (admin_level_2). Brazil's municipalities vary enormously in size (Sao Paulo municipality = 1,521 km2 with 12M people; Altamira = 159,533 km2 with 115K people). H3 hexagons provide uniform spatial units for fair comparison and precise targeting. This is a *structural* moat -- once data is H3-indexed, every analytics feature gets sub-municipal precision for free.

**Accelerators**:
- [h3-py](https://github.com/uber/h3-py) -- Official Python bindings. `pip install h3`. Convert lat/lon to hex cell in microseconds.
- [h3-pg](https://github.com/zachasme/h3-pg) -- PostgreSQL extension for H3. Enables `SELECT h3_lat_lng_to_cell(point, 7)` directly in SQL.
- PostGIS + H3 integration -- H3 cells can be converted to PostGIS polygons for spatial joins with existing municipality geometries.

**Implementation approach**: Add `h3_index_r7` and `h3_index_r9` columns to `base_stations`, `broadband_subscribers`, `building_density`. Create materialized view `mv_h3_summary` aggregating subscribers, providers, penetration per hex. Extend `/market/heatmap` endpoint to support `granularity=h3` parameter. Frontend: render hex grid on map using deck.gl H3HexagonLayer.

---

### 1.4 FTTH/GPON PON Splitting Analytics

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 4-5 weeks |

**What it is**: Model GPON/XGS-PON optical distribution network (ODN) designs with split-ratio optimization (1:8, 1:16, 1:32, 1:64), OLT port capacity planning, and optical power budget calculations. Integrate with the existing fiber route pre-design (`/opportunity/route`) and financial analysis (`/opportunity/financial`) endpoints.

**Why it matters**: The platform already computes fiber routes with BOM (Bill of Materials) via Dijkstra on 6.4M road segments. Adding PON splitting analytics turns a route estimate into a complete FTTH design -- OLT placement, splitter cabinet locations, drop cable counts, and optical loss budgets. This is the natural extension of the existing fiber planning feature.

**Accelerators**:
- [QGIS + GNI Plugin](https://ksavinetworkinventory.com/ftth-design-software-free/) -- Open-source FTTH network planning based on QGIS with GPON algorithms.
- [ftth_planner](https://github.com/ChrisMolanus/ftth_planner) -- Open-source Python tool for FTTH planning given postcodes.
- ITU-T G.984 (GPON) and G.9807 (XGS-PON) standards define optical budgets (Class B+ = 28 dB, Class C+ = 32 dB).

**Implementation approach**: New module `python/design/pon_designer.py` that takes a fiber route GeoJSON + building density data and outputs: OLT placement, splitter locations, split ratios per segment, optical power budget, and BOM with splitters/cabinets/drop cables. Extend `/opportunity/route` response to include `pon_design` section. Frontend: visualize ODN tree on map.

---

### 1.5 Dark Fiber Inventory and Lit Building Database

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 8-10 weeks |

**What it is**: Build a database of fiber-optic infrastructure: backbone routes (from Anatel licensing data + OSM), lit buildings (buildings with active fiber connections inferred from subscriber data + building density), and dark fiber availability (from public infrastructure sharing registrations). Cross-reference with the existing 6.4M road segments and 16,559 power line records.

**Why it matters**: Knowing where fiber already exists is the single most valuable dataset for ISP expansion planning. It reduces CAPEX by 40-60% when you can lease existing fiber instead of building new. The platform already has road segments and power lines -- adding fiber routes creates a complete infrastructure map.

**Accelerators**:
- [Kuwaiba](https://www.kuwaiba.org/) -- Open-source network inventory management platform with fiber modeling.
- Anatel MOSAICO database -- Public spectrum and infrastructure licensing data.
- IBGE CNEFE data (already in platform) -- Address-level building enumeration can proxy lit/unlit status.
- OSM `telecom=*` tags -- OpenStreetMap has some fiber route data for Brazil.

**Implementation approach**: New pipeline `fiber_inventory.py` combining: (1) Anatel infrastructure sharing registry (SNOA), (2) OSM telecom tags, (3) inference from broadband subscriber density vs building density to estimate lit buildings. New tables: `fiber_routes`, `lit_buildings`. Extend `/opportunity/route` to show existing fiber for co-location.

---

### 1.6 Backhaul Capacity Utilization Data

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | Medium |
| **Competitive Moat** | High |
| **MVP Effort** | 6-8 weeks |

**What it is**: Model backhaul capacity utilization by combining: subscriber counts per municipality (already have 4.1M records), average bandwidth per subscriber (from M-Lab data), backhaul technology (already have `backhaul_presence` table), and theoretical capacity per technology (satellite ~50 Mbps, radio ~1 Gbps, fiber ~100 Gbps).

**Why it matters**: The platform already tracks backhaul presence (fiber/radio/satellite) per municipality. Adding utilization modeling identifies bottleneck municipalities -- where subscriber growth will hit a backhaul wall. Critical for ISPs planning capacity upgrades and for the financial viability analysis.

**Accelerators**:
- Existing data: `backhaul_presence` + `broadband_subscribers` + `base_stations` tables provide the inputs.
- M-Lab average throughput data provides per-municipality bandwidth consumption estimates.
- ITU-R capacity models (already implemented in Rust RF engine for link budget calculations).

**Implementation approach**: New computed column `backhaul_utilization_pct` in a `mv_backhaul_capacity` materialized view. Logic: (total_subscribers * avg_bandwidth_mbps) / technology_capacity_mbps. Threshold alerts: >70% = yellow, >90% = red. Integrate into opportunity scoring pipeline to penalize areas with saturated backhaul.

---

### 1.7 Cell Tower Co-Location Database

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Low |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 2-3 weeks |

**What it is**: Analyze existing base station data (37,727 towers) to identify co-location opportunities -- towers where multiple operators share infrastructure, and towers with available capacity for new tenants. Use proximity clustering to group towers within 50m radius as same physical site.

**Why it matters**: Co-location reduces tower CAPEX by 50-70%. The platform already has 37,727 attributed base stations. Clustering them by physical location and identifying single-tenant towers creates an instant co-location opportunity database. This enriches the tower optimization endpoint.

**Accelerators**:
- Existing data: `base_stations` table with lat/lon and provider attribution.
- [scikit-learn DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html) -- Density-based clustering for tower proximity grouping.
- PostGIS `ST_ClusterDBSCAN` -- Native spatial clustering in PostgreSQL.

**Implementation approach**: SQL materialized view using `ST_ClusterDBSCAN(geom, eps := 0.0005, minpoints := 1)` on `base_stations`. Result: `tower_sites` table with site_id, tower_count, operators list, available_capacity flag. Extend `/opportunity/base-stations` endpoint with `?colocation=true` filter. Integrate into `/design/optimize` to prefer co-location sites.

---

### 1.8 Street-Level Infrastructure Mapping (Poles, Ducts, Manholes)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | Medium |
| **Competitive Moat** | High |
| **MVP Effort** | 10-12 weeks |

**What it is**: Build a database of street-level infrastructure: utility poles (from power company data + OSM), underground ducts (from municipal GIS + ANEEL data), and manholes. This is the physical layer that determines where fiber can actually be deployed.

**Why it matters**: The existing fiber route algorithm runs on road segments but does not know whether poles or ducts exist along those roads. Adding infrastructure data turns approximate routes into constructible designs. This dramatically improves CAPEX accuracy.

**Accelerators**:
- OSM `power=pole`, `man_made=manhole`, `utility=*` tags -- Partial coverage in Brazilian cities.
- [ANEEL power grid data](https://dadosabertos.aneel.gov.br/) -- The platform already has `aneel_power` pipeline. ANEEL's SIGEL database includes transmission line and distribution pole locations.
- Municipal GIS portals -- GeoSampa (Sao Paulo), Data.Rio (Rio de Janeiro) have pole/duct data.

**Implementation approach**: Extend `osm_roads.py` pipeline to also pull `power=pole` and `man_made=manhole` features. New pipeline for ANEEL SIGEL pole data. New `infrastructure_points` table (type, lat, lon, owner, capacity). Extend fiber route BOM to use actual pole counts instead of estimates.

---

### 1.9 Mobile Coverage from Crowdsourced Apps (OpenSignal-Style)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 10-12 weeks |

**What it is**: Aggregate crowdsourced mobile signal measurements from open databases (OpenCellID, beaconDB, Mozilla Location Services) and/or build a lightweight measurement SDK for ISPs to embed in their customer apps. Map real-world 3G/4G/5G coverage vs theoretical coverage from the Rust RF engine.

**Why it matters**: The Rust RF engine computes theoretical coverage from SRTM terrain + propagation models. Comparing theoretical vs actual coverage identifies model calibration errors, interference zones, and coverage holes. Essential for ISPs validating tower placement decisions.

**Accelerators**:
- [OpenCellID](https://opencellid.org/) -- Open database of cell tower locations with signal measurements. Free API.
- [beaconDB](https://beacondb.net/) -- Open-source alternative to OpenSignal. Community-contributed data.
- [Mozilla Location Services (MLS)](https://location.services.mozilla.com/) -- Crowdsourced cell tower + WiFi location database (note: winding down, but data dumps available).

**Implementation approach**: New pipeline `opencellid_coverage.py` pulling from OpenCellID API. Cross-reference with existing `base_stations` table. New `measured_coverage` table with signal_dbm, technology, provider, H3 hex index. Frontend: toggle layer showing theoretical vs measured coverage.

---

### 1.10 Power Grid Reliability Correlated with Telecom Uptime

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | High |
| **MVP Effort** | 4-5 weeks |

**What it is**: Ingest ANEEL DEC/FEC indicators (Brazilian equivalents of SAIDI/SAIFI -- average outage duration and frequency per distribution company) and correlate with telecom infrastructure. Municipalities with unreliable power need UPS/battery/solar for telecom sites -- this affects CAPEX and OPEX.

**Why it matters**: The platform already has the `aneel_power` pipeline. Adding reliability metrics creates a power risk layer that directly impacts: (1) rural hybrid design solar sizing (already have `solar_power.py`), (2) tower optimization CAPEX (backup power costs), (3) financial viability analysis (OPEX for generators/batteries).

**Accelerators**:
- [ANEEL Open Data](https://dadosabertos.aneel.gov.br/) -- DEC/FEC indicators per distribution company, per municipality. CSV downloads available.
- Existing `aneel_power.py` pipeline can be extended to pull reliability data.
- Correlation with existing `weather_observations` for weather-related outage analysis.

**Implementation approach**: Extend `aneel_power.py` to pull DEC/FEC data from ANEEL open data portal. New table `power_reliability` (l2_id, distributor, dec_hours, fec_count, year). Add `power_reliability_score` to opportunity scoring features. Integrate into rural hybrid design for backup power sizing.

---

### 1.11 Real Estate Development Data as Demand Predictors

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 5-6 weeks |

**What it is**: Track new construction permits, real estate developments, and urbanization trends as leading indicators of future broadband demand. When a 500-unit condominium is approved, that is 500 future subscribers in 18-24 months.

**Why it matters**: The platform currently uses IBGE population projections and building density for demand estimation. Real estate development data is a *leading* indicator that arrives 1-2 years before subscribers materialize. This is the difference between reactive and predictive expansion planning.

**Accelerators**:
- IBGE SIDRA -- Construction permit data (Pesquisa Anual da Industria da Construcao).
- Municipal IPTU records -- Property registration changes indicate new construction (GeoSampa API for Sao Paulo, Data.Rio for Rio).
- [geobr](https://ipeagit.github.io/geobr/) -- R/Python package for official Brazilian spatial data including urban areas and census tracts.
- Existing `ibge_cnefe.py` pipeline (address enumeration) can be run annually to detect building count changes.

**Implementation approach**: New pipeline `construction_permits.py` pulling from IBGE SIDRA Table 1291 (construction permits by municipality). New table `construction_activity` (l2_id, permits_residential, permits_commercial, units_approved, year). Add as feature to opportunity scoring: `construction_growth_score`. Integrate into subscriber projection model in financial analysis.

---

### 1.12 Credit/Financial Health Data for ISP Risk Scoring

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 4-5 weeks |

**What it is**: Integrate with Brazilian credit bureaus (Serasa Experian, Boa Vista, SPC Brasil) to assess ISP financial health for M&A targets and competitive analysis. Use Receita Federal CNPJ data (already in platform via `cnpj_enrichment.py`) plus financial indicators to build risk scores.

**Why it matters**: The M&A module already does 3-method valuation. Adding financial health/risk scoring makes target evaluation dramatically more reliable. An ISP with R$50M in subscribers but R$30M in debt and falling credit scores is a very different acquisition target.

**Accelerators**:
- [Serasa Experian Developer Portal](https://developer.serasaexperian.com.br/apis) -- Commercial API for CNPJ credit scores, payment history, and restrictions.
- Existing `cnpj_enrichment.py` pipeline -- Already pulls capital social, founding date, partner count from Receita Federal. Extend with credit data.
- [Receita Federal CNPJ Open Data](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj) -- Free quarterly dumps with status, capital, CNAE codes.

**Implementation approach**: Extend `cnpj_enrichment.py` to compute a financial health score from: capital social, founding age, Simples Nacional status, CNAE alignment, partner count. For premium tier: integrate Serasa API for credit scores (commercial API, ~R$2-5 per query). New `provider_risk_score` table. Enrich M&A `/targets` and `/valuation` responses.

---

## Part 1 Summary Table

| # | Data Source | Complexity | Revenue | Moat | Weeks | Key Accelerator |
|---|------------|------------|---------|------|-------|-----------------|
| 1.1 | Real-time network quality | High | High | High | 8-10 | M-Lab NDT + BGPStream |
| 1.2 | Social media sentiment | Medium | Medium | Medium | 5-6 | BERTimbau + Reclame Aqui |
| 1.3 | H3 hexagonal grid | Medium | High | High | 4-5 | h3-py + h3-pg |
| 1.4 | FTTH/GPON PON analytics | Medium | Medium | Medium | 4-5 | QGIS GNI + ITU-T G.984 |
| 1.5 | Dark fiber inventory | High | High | High | 8-10 | Kuwaiba + Anatel SNOA |
| 1.6 | Backhaul utilization | High | Medium | High | 6-8 | M-Lab + existing data |
| 1.7 | Tower co-location | Low | Medium | Medium | 2-3 | PostGIS ST_ClusterDBSCAN |
| 1.8 | Street-level infrastructure | High | Medium | High | 10-12 | OSM + ANEEL SIGEL |
| 1.9 | Crowdsourced mobile coverage | High | Medium | Medium | 10-12 | OpenCellID + beaconDB |
| 1.10 | Power grid reliability | Medium | Medium | High | 4-5 | ANEEL DEC/FEC open data |
| 1.11 | Real estate development | Medium | High | High | 5-6 | IBGE SIDRA + CNEFE delta |
| 1.12 | ISP credit/risk scoring | Medium | High | High | 4-5 | Serasa API + CNPJ data |

**Recommended priority order** (highest impact-to-effort ratio first):
1. **1.7 Tower co-location** -- 2-3 weeks, immediate value from existing data
2. **1.3 H3 hexagonal grid** -- 4-5 weeks, structural upgrade that amplifies every other feature
3. **1.12 ISP credit/risk scoring** -- 4-5 weeks, directly enriches existing M&A module
4. **1.10 Power grid reliability** -- 4-5 weeks, extends existing ANEEL pipeline
5. **1.11 Real estate development** -- 5-6 weeks, leading demand indicator
6. **1.1 Real-time network quality** -- 8-10 weeks, highest moat of all features

---

## Part 2: USER ENGAGEMENT -- Features for Daily Platform Usage

### 2.1 AI Chatbot/Copilot for Natural Language Queries

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 6-8 weeks |

**What it is**: Natural language interface that converts Portuguese queries into SQL against the platform's PostgreSQL database. Examples: "Quais municipios em Minas com HHI acima de 2500?", "Mostra os 10 ISPs com mais crescimento no Parana", "Qual o custo estimado para fibra de Curitiba a Londrina?".

**Why it matters**: The platform has 30+ tables with rich data but accessing it requires navigating multiple pages. A chatbot puts every data point one sentence away. This is the highest-leverage engagement feature because it makes ALL existing data more accessible.

**Accelerators**:
- [Vanna.AI](https://vanna.ai/) -- Open-source text-to-SQL framework. Supports PostgreSQL. Fine-tunable on schema.
- [WrenAI](https://github.com/Canner/WrenAI) -- Open-source GenBI engine with text-to-SQL, text-to-chart. PostgreSQL support. 5K+ GitHub stars.
- [DBHub](https://dbhub.ai/) -- Universal database MCP server for text-to-SQL. 100K+ downloads.
- [QueryWeaver](https://sequel.sh/) -- Graph-powered text-to-SQL with semantic layer. PostgreSQL support.
- Claude/GPT API -- For natural language understanding and response generation.

**Implementation approach**: Deploy WrenAI or Vanna.AI with the platform's schema. Create a semantic layer mapping table/column names to Portuguese business terms (e.g., `broadband_subscribers.subscribers` = "assinantes de banda larga"). New endpoint `POST /api/v1/copilot/query` that accepts Portuguese text, generates SQL, executes safely (read-only), and returns formatted results. Frontend: chat panel component in sidebar. Safety: query timeout (5s), row limit (1000), no DDL/DML.

---

### 2.2 Custom Alerting System

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | High |
| **Competitive Moat** | Medium |
| **MVP Effort** | 4-5 weeks |

**What it is**: User-configurable alerts triggered by data changes. Categories: (1) Competitive -- "competitor entered my market", "new ISP registered in my state"; (2) Regulatory -- "ANATEL deadline in 30 days", "new DOU regulatory act"; (3) Market -- "subscriber count changed >10% in municipality X", "opportunity score crossed 80 threshold"; (4) Financial -- "BNDES loan program announced", "government contract published in my area".

**Why it matters**: The platform already has SSE streaming (`/api/v1/events/stream`) and gazette alerts (`/intelligence/gazette-alerts`). A structured alerting system with user-defined rules turns a tool users visit weekly into one they rely on daily. This is the single most important engagement driver.

**Accelerators**:
- Existing `event_bus.py` SSE infrastructure -- Already supports `pipeline_status`, `data_updated`, `notification` event types.
- Existing `regulatory_acts` and `municipal_gazette_mentions` tables -- Already populated by DOU and Querido Diario pipelines.
- [APScheduler](https://apscheduler.readthedocs.io/) -- Already used in `scheduler.py` for pipeline scheduling. Can trigger alert evaluation jobs.
- PostgreSQL `LISTEN/NOTIFY` -- For real-time alert triggering on data changes.

**Implementation approach**: New tables: `alert_rules` (user_id, alert_type, conditions JSON, channels, active) and `alert_history` (rule_id, triggered_at, payload). New module `python/api/services/alert_engine.py` that runs every 15 minutes via APScheduler, evaluating rules against latest data. Channels: in-app (SSE), email (SMTP/SendGrid), WhatsApp (Twilio). Frontend: "Alertas" page with rule builder UI. Extend existing `/events/stream` to push alert notifications.

---

### 2.3 Collaborative Workspaces for ISP Teams

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 5-6 weeks |

**What it is**: Shared analysis workspaces where ISP team members can: save map views with annotations, pin municipalities to a shared watchlist, leave comments on opportunity scores, and share financial analysis results with colleagues.

**Why it matters**: The platform currently has single-user JWT auth. Adding collaboration features means multiple people at the same ISP use the platform, increasing stickiness and seat-based pricing potential. Annotations create institutional knowledge that makes the platform harder to leave.

**Accelerators**:
- Existing JWT auth in `python/api/auth/` -- Extend with organization/team model.
- PostgreSQL JSONB -- Flexible storage for annotations, comments, saved views.
- [Tiptap](https://tiptap.dev/) -- Open-source rich text editor for annotation/comment content.
- [Y.js](https://yjs.dev/) -- Open-source CRDT framework for real-time collaboration.

**Implementation approach**: New tables: `organizations` (org_id, name), `org_memberships` (user_id, org_id, role), `workspaces` (org_id, name, settings), `annotations` (workspace_id, user_id, type, geometry, content, target_entity). Extend auth to support org-scoped permissions. Frontend: share button on every analysis view, annotation layer on map, comment threads on municipality profiles.

---

### 2.4 What-If Scenario Modeling (Interactive Tower Placement)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | High |
| **Competitive Moat** | High |
| **MVP Effort** | 5-7 weeks |

**What it is**: Interactive map mode where users drag-and-drop tower locations and instantly see coverage predictions update. Supports: (1) adding/removing towers, (2) changing tower height/power/frequency, (3) comparing scenarios side-by-side, (4) saving scenarios with cost estimates.

**Why it matters**: The Rust RF engine already computes real coverage from SRTM terrain data (`/design/coverage` endpoint, 349K grid points). Making this interactive creates a "telecom SimCity" experience that engineers will use daily. The existing `/design/optimize` endpoint can suggest placements, but planners want to manually adjust and see results.

**Accelerators**:
- Existing Rust RF engine -- Already handles coverage computation in ~2 seconds for 10km radius at 30m resolution.
- Existing `/design/coverage` endpoint -- Returns grid points with signal strength.
- [deck.gl](https://deck.gl/) -- High-performance WebGL map layers for rendering coverage grids.
- [Turf.js](https://turfjs.org/) -- Client-side geospatial analysis for quick bounding-box checks before server calls.
- WebSocket connection -- For streaming coverage results as they compute (the gRPC call takes 1-3 seconds).

**Implementation approach**: New frontend component `ScenarioEditor.tsx` with: draggable tower markers, parameter sidebar (height, power, frequency), coverage overlay that auto-updates on marker dragend. Backend: new endpoint `POST /api/v1/design/scenario` that accepts multiple tower configs and returns combined coverage. New table `scenarios` (user_id, name, towers JSON, coverage_summary, cost_estimate). Frontend: scenario comparison panel showing two coverage maps side-by-side.

---

### 2.5 ISP Community Features (Anonymous Benchmarking + Forum)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | High |
| **MVP Effort** | 6-8 weeks |

**What it is**: Anonymous benchmarking where ISPs can see how their metrics compare to peers without revealing identity. Categories: ARPU, churn rate, fiber penetration, CAPEX per subscriber, subscriber growth rate. Plus a moderated forum for ISP operators to discuss regulatory changes, equipment vendors, and deployment strategies.

**Why it matters**: Creates network effects -- the more ISPs that join, the more valuable benchmarks become. This is how platforms like Glassdoor and AngelList became sticky. Anonymous benchmarking addresses ISPs' fear of exposing competitive data while delivering the peer comparison they desperately want.

**Accelerators**:
- [Discourse](https://www.discourse.org/) -- Open-source forum platform. Self-hosted. REST API for integration.
- Differential privacy libraries -- [Google's dp library](https://github.com/google/differential-privacy) for anonymizing benchmark data.
- Existing Anatel data can seed initial benchmarks (public data, no anonymization needed).

**Implementation approach**: New tables: `benchmark_submissions` (org_id, metric_type, value, period -- encrypted), `benchmark_aggregates` (metric_type, percentile_25/50/75, segment, period). ISPs submit anonymized metrics; system computes percentile rankings. Forum: embed Discourse or build lightweight forum with `forum_threads`, `forum_posts` tables. Frontend: "Comunidade" section with benchmark dashboards and discussion threads.

---

### 2.6 Gamification of Expansion Planning

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Low |
| **Revenue Impact** | Low |
| **Competitive Moat** | Low |
| **MVP Effort** | 2-3 weeks |

**What it is**: Achievement tracking and progress metrics for ISP expansion activities. Badges: "First Coverage Analysis", "10 Municipalities Analyzed", "Financial Model Guru", "RF Engineer Level 3". Leaderboards: optional, org-internal ranking by analyses completed.

**Why it matters**: Increases feature discovery and adoption. Users who earn a "Coverage Analysis" badge have used the Rust RF engine, which they might not have found otherwise. Low effort to implement but marginal revenue impact -- this is a retention feature, not a revenue driver.

**Accelerators**:
- [Python-gamification](https://github.com/mattupham/django-gamification) -- Django gamification framework (concepts transferable to FastAPI).
- Simple implementation: `achievements` table + trigger logic in API middleware.

**Implementation approach**: New tables: `user_achievements` (user_id, achievement_id, unlocked_at), `achievement_definitions` (id, name, description, icon, criteria_json). Middleware that tracks API endpoint usage and awards achievements. Frontend: achievement panel in user profile, toast notifications on unlock. ~15 achievement definitions covering all major features.

---

### 2.7 CRM Integration (Customer Data Overlay)

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | High |
| **Competitive Moat** | Medium |
| **MVP Effort** | 8-10 weeks |

**What it is**: Bidirectional integration with ISP billing/CRM systems (IXC Soft, MK Solutions, SGP, HubSoft -- the dominant Brazilian ISP management platforms). Import: subscriber locations, service plans, churn data. Export: opportunity scores, coverage analysis results, financial models.

**Why it matters**: This is the ultimate engagement driver -- when the ISP's own customer data is inside the platform, it becomes indispensable. Overlaying real subscriber locations on coverage maps, opportunity scores, and competitor analysis creates insights neither system provides alone.

**Accelerators**:
- [IXC Soft API](https://wiki.ixcsoft.com.br/) -- REST API for subscriber management. Most popular Brazilian ISP billing platform.
- [MK Solutions API](https://www.mksolutions.com.br/) -- ERP/CRM for ISPs with API access.
- Generic CSV/XLSX import as fallback for ISPs without API-capable CRM.

**Implementation approach**: New module `python/api/integrations/` with adapters for IXC Soft, MK Solutions, and generic CSV. New tables: `crm_connections` (org_id, provider_type, credentials_encrypted, sync_status), `crm_subscribers` (org_id, plan, lat, lon, status, synced_at). Sync runs hourly. Frontend: "Integracoes" settings page + subscriber overlay on map. Privacy: subscriber data is org-scoped, never shared.

---

### 2.8 Mobile App for Field Technicians

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | High |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Medium |
| **MVP Effort** | 10-14 weeks |

**What it is**: Lightweight mobile app (React Native or Flutter) for field technicians doing site surveys. Features: GPS-tagged photos of tower sites, signal measurement recording, terrain notes, offline map tiles, and site survey checklist. Data syncs back to main platform.

**Why it matters**: Field teams are a separate user persona from the analysts using the web platform. Capturing site survey data in-platform closes the loop between planning (web) and execution (field). However, this is a large investment for a niche user group.

**Accelerators**:
- [React Native](https://reactnative.dev/) -- Share code with Next.js web app (same React ecosystem).
- [Expo](https://expo.dev/) -- Simplified React Native development with OTA updates.
- [MapLibre Native](https://maplibre.org/) -- Open-source mobile map SDK with offline tile support.
- Existing API endpoints -- Mobile app consumes the same FastAPI backend.

**Implementation approach**: React Native app with: offline-first architecture (SQLite local DB), map view with downloaded tile regions, camera for site photos (geotagged), signal strength measurement via Android TelephonyManager API, checklist for site surveys. New backend endpoint `POST /api/v1/surveys` for data upload. MVP: Android only (dominant in Brazil's ISP field workforce).

---

### 2.9 Dashboard Customization and Saved Views

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Medium |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Low |
| **MVP Effort** | 4-5 weeks |

**What it is**: Let users configure their dashboard: choose which metrics to display, set default map view (state, region, or custom bbox), pin favorite municipalities, and save filter combinations. Each user gets a personalized home screen.

**Why it matters**: The current frontend has fixed page layouts (expansao, concorrencia, saude, etc.). Customizable dashboards let users build their own workflow, increasing daily usage. This is table-stakes for enterprise SaaS but currently missing.

**Accelerators**:
- [react-grid-layout](https://github.com/react-grid-layout/react-grid-layout) -- Draggable/resizable grid layout for dashboard widgets.
- [recharts](https://recharts.org/) -- Already likely in use for charts. Supports configurable chart types.
- PostgreSQL JSONB -- Store dashboard configs as JSON per user.

**Implementation approach**: New table: `user_dashboards` (user_id, name, layout_json, is_default). Layout JSON defines widget positions, types (map, chart, table, metric card), and data source configs. New endpoint `GET/PUT /api/v1/user/dashboard`. Frontend: drag-and-drop dashboard editor with widget palette. ~10 widget types covering existing data: subscriber trend, opportunity ranking, competitor map, quality scorecard, alert feed, etc.

---

### 2.10 Scheduled Report Generation and Email Delivery

| Dimension | Rating |
|-----------|--------|
| **Implementation Complexity** | Low |
| **Revenue Impact** | Medium |
| **Competitive Moat** | Low |
| **MVP Effort** | 3-4 weeks |

**What it is**: Schedule the existing PDF reports (market analysis, expansion opportunity, compliance, rural feasibility) to be generated and emailed weekly or monthly. Users configure: report type, parameters (municipality, state), frequency, recipients.

**Why it matters**: The platform already generates 4 types of PDF reports via `python/reports/generator.py` with WeasyPrint. Adding scheduling means stakeholders who do not log into the platform still receive intelligence -- expanding the user base from analysts to executives. This is low-effort, high-value because the hard part (report generation) is already built.

**Accelerators**:
- Existing `reports/generator.py` -- Already generates 4 PDF report types from live PostgreSQL data.
- Existing APScheduler in `scheduler.py` -- Can schedule report generation jobs.
- [SendGrid](https://sendgrid.com/) or [Amazon SES](https://aws.amazon.com/ses/) -- For email delivery. Free tier covers initial needs.
- [python-emails](https://github.com/lavr/python-emails) -- Lightweight email sending library.

**Implementation approach**: New table: `scheduled_reports` (user_id, report_type, params_json, frequency, recipients, last_run, next_run). Extend `scheduler.py` to check for due reports every hour. On trigger: call existing `generator.py`, attach PDF to email, send via SendGrid/SES. Frontend: "Agendar" button on report generation page with frequency picker and recipient list. Notification via existing SSE when report is ready.

---

## Part 2 Summary Table

| # | Feature | Complexity | Revenue | Moat | Weeks | Key Accelerator |
|---|---------|------------|---------|------|-------|-----------------|
| 2.1 | AI Chatbot/Copilot | High | High | High | 6-8 | WrenAI / Vanna.AI |
| 2.2 | Custom alerting | Medium | High | Medium | 4-5 | Existing SSE + APScheduler |
| 2.3 | Collaborative workspaces | Medium | Medium | Medium | 5-6 | Y.js + org model |
| 2.4 | What-if scenario modeling | Medium | High | High | 5-7 | Existing Rust RF engine |
| 2.5 | ISP community/benchmarking | Medium | Medium | High | 6-8 | Discourse + differential privacy |
| 2.6 | Gamification | Low | Low | Low | 2-3 | Achievement table + middleware |
| 2.7 | CRM integration | High | High | Medium | 8-10 | IXC Soft / MK Solutions API |
| 2.8 | Mobile field app | High | Medium | Medium | 10-14 | React Native + Expo |
| 2.9 | Dashboard customization | Medium | Medium | Low | 4-5 | react-grid-layout |
| 2.10 | Scheduled reports | Low | Medium | Low | 3-4 | Existing generator.py + SendGrid |

**Recommended priority order** (highest impact-to-effort ratio first):
1. **2.10 Scheduled reports** -- 3-4 weeks, leverages existing report generator, expands audience to executives
2. **2.2 Custom alerting** -- 4-5 weeks, leverages existing SSE + pipelines, highest daily engagement driver
3. **2.4 What-if scenario modeling** -- 5-7 weeks, leverages existing Rust RF engine, showcase feature
4. **2.1 AI Chatbot/Copilot** -- 6-8 weeks, highest long-term engagement but needs careful schema mapping
5. **2.9 Dashboard customization** -- 4-5 weeks, table-stakes for enterprise SaaS
6. **2.7 CRM integration** -- 8-10 weeks, highest lock-in but requires ISP partnership for testing

---

## Combined Roadmap Recommendation

### Phase 1: Quick Wins (Weeks 1-5)
- **1.7 Tower co-location database** (2-3 weeks) -- Pure SQL on existing data
- **2.10 Scheduled report delivery** (3-4 weeks) -- Extend existing generator
- **2.6 Gamification** (2-3 weeks) -- Simple engagement layer

### Phase 2: Structural Upgrades (Weeks 4-10)
- **1.3 H3 hexagonal grid** (4-5 weeks) -- Amplifies every other feature
- **2.2 Custom alerting system** (4-5 weeks) -- Daily engagement driver
- **1.12 ISP credit/risk scoring** (4-5 weeks) -- Enriches M&A module
- **1.10 Power grid reliability** (4-5 weeks) -- Extends existing ANEEL pipeline

### Phase 3: Differentiation Features (Weeks 8-16)
- **2.4 What-if scenario modeling** (5-7 weeks) -- Showcase for sales demos
- **1.11 Real estate development data** (5-6 weeks) -- Predictive demand layer
- **1.2 Social media sentiment** (5-6 weeks) -- Reputation intelligence
- **2.1 AI Chatbot/Copilot** (6-8 weeks) -- Accessibility revolution

### Phase 4: Deep Moats (Weeks 14-26)
- **1.1 Real-time network quality** (8-10 weeks) -- Hardest to replicate
- **1.5 Dark fiber inventory** (8-10 weeks) -- Highest-value infrastructure data
- **2.7 CRM integration** (8-10 weeks) -- Customer lock-in
- **1.4 FTTH/GPON PON analytics** (4-5 weeks) -- Complete fiber design story

### Deferred
- **1.8 Street-level infrastructure** (10-12 weeks) -- High value but slow data acquisition
- **1.9 Crowdsourced mobile coverage** (10-12 weeks) -- Requires user base for data collection
- **2.8 Mobile field app** (10-14 weeks) -- Large investment, niche user group
- **1.6 Backhaul utilization** (6-8 weeks) -- Depends on M-Lab data quality for Brazil

---

## Total Investment Summary

| Phase | Features | Estimated Weeks | Parallel Team Capacity |
|-------|----------|-----------------|----------------------|
| Phase 1 | 3 features | 3-5 weeks | 1-2 developers |
| Phase 2 | 4 features | 4-5 weeks | 2-3 developers |
| Phase 3 | 4 features | 5-8 weeks | 2-3 developers |
| Phase 4 | 4 features | 8-10 weeks | 2-3 developers |
| **Total** | **15 features** | **~20-28 weeks** | **2-3 developers** |

With a team of 2-3 developers working in parallel, the full roadmap spans approximately 6-7 months, delivering incremental value at each phase.
