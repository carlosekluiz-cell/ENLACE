# Dicionario de Dados — Enlace / Pulso Network

**Referencia tecnica das tabelas principais do banco de dados**

Versao 2.0 | Marco 2026

---

## Visao Geral do Banco

| Atributo | Valor |
|----------|-------|
| Engine | PostgreSQL 15+ com PostGIS 3.x |
| Database | `enlace` |
| User | `enlace` |
| Tamanho total (dados) | ~5.2 GB |
| Total de tabelas | 62 |
| Total de registros | 28M+ |
| Materialized views | 1 (`mv_market_summary`) |
| Spatial reference | SRID 4326 (WGS84) |

---

## Tabelas Geograficas

### admin_level_1 (Estados)

Unidades federativas do Brasil.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| code | VARCHAR | Codigo UF (ex: "SP", "MG") |
| name | VARCHAR | Nome completo do estado |
| abbrev | VARCHAR | Abreviacao (ex: "SP") — **NOTA: usar `abbrev`, NAO `abbreviation`** |
| country_code | VARCHAR | Codigo do pais ("BR") |
| geom | GEOMETRY | Geometria do estado (MultiPolygon) |

| Metrica | Valor |
|---------|-------|
| Registros | 27 |
| Atualizacao | Estatica |
| Pipeline | N/A (carga inicial) |

### admin_level_2 (Municipios)

Municipios do Brasil com geometrias PostGIS.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| code | VARCHAR | Codigo IBGE do municipio (7 digitos) |
| name | VARCHAR | Nome do municipio |
| l1_id | INTEGER FK | Referencia para admin_level_1 (estado) |
| country_code | VARCHAR | Codigo do pais ("BR") |
| population | INTEGER | Populacao estimada (IBGE 2024) |
| area_km2 | FLOAT | Area em km2 |
| geom | GEOMETRY | Geometria do municipio (MultiPolygon, SRID 4326) |
| centroid | GEOMETRY | Centroide do municipio (Point, SRID 4326) |

| Metrica | Valor |
|---------|-------|
| Registros | 5.572 |
| Atualizacao | Mensal |
| Pipeline | ibge_census |

---

## Tabelas de Provedores

### providers

Provedores de internet (ISPs) registrados na Anatel.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| name | VARCHAR | Nome do provedor — **NOTA: usar `name`, NAO `trade_name`** |
| national_id | VARCHAR | CNPJ do provedor — **NOTA: usar `national_id`, NAO `cnpj`** |
| country_code | VARCHAR | Codigo do pais ("BR") |

| Metrica | Valor |
|---------|-------|
| Registros | 13.534 |
| Atualizacao | Diaria |
| Pipeline | anatel_providers |

### provider_details

Detalhes empresariais da Receita Federal (enriquecimento CNPJ).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Referencia para providers |
| status | VARCHAR(50) | Status na Receita Federal (ATIVA, BAIXADA, etc.) |
| capital_social | NUMERIC | Capital social declarado (BRL) |
| founding_date | DATE | Data de fundacao |
| address_cep | VARCHAR(10) | CEP do endereco |
| address_city | VARCHAR(200) | Cidade do endereco |
| partner_count | INTEGER | Numero de socios |
| simples_nacional | BOOLEAN | Optante pelo Simples Nacional |
| cnae_primary | VARCHAR(20) | CNAE primario |
| updated_at | TIMESTAMP | Data da ultima atualizacao |

| Metrica | Valor |
|---------|-------|
| Registros | Incremental (ate 13.534) |
| Atualizacao | Semanal |
| Pipeline | cnpj_enrichment |
| Constraint | UNIQUE (provider_id) |

---

## Tabelas de Dados Telecom

### broadband_subscribers

Dados de assinantes de banda larga fixa por municipio, provedor e tecnologia.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Referencia para admin_level_2 — **NOTA: usar `l2_id`, NAO `municipality_id`** |
| provider_id | INTEGER FK | Referencia para providers |
| year_month | VARCHAR | Periodo no formato "YYYY-MM" — **NOTA: usar `year_month`, NAO `date`** |
| technology | VARCHAR | Tecnologia normalizada: fiber, cable, dsl, wireless, satellite, other |
| subscribers | INTEGER | Numero de assinantes — **NOTA: usar `subscribers`, NAO `subscriber_count`** |

| Metrica | Valor |
|---------|-------|
| Registros | 4.137.609 |
| Meses distintos | 37 (2023-2026) |
| Atualizacao | Diaria (dados mensais da Anatel, ~45 dias de atraso) |
| Pipeline | anatel_broadband |

### base_stations

Torres de telecomunicacoes com atribuicao de operadora.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| latitude | FLOAT | Latitude da torre |
| longitude | FLOAT | Longitude da torre |
| technology | VARCHAR | Tecnologia (3G, 4G, 5G) |
| frequency_mhz | FLOAT | Frequencia em MHz |
| provider_id | INTEGER FK | Operadora atribuida (probabilistic attribution) |
| country_code | VARCHAR | Codigo do pais |

| Metrica | Valor |
|---------|-------|
| Registros | 37.727 |
| Top operadoras | CLARO 4.887, VIVO 3.560, OI 2.286, TIM 885 |
| Atualizacao | Diaria |
| Pipeline | anatel_base_stations |
| Atribuicao | Proprietaria (market share municipal) |

### spectrum_licenses

Licencas de espectro de frequencia (dados de leilao Anatel).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Provedor detentor |
| frequency_band | VARCHAR | Banda de frequencia |
| bandwidth_mhz | FLOAT | Largura de banda (MHz) |
| region | VARCHAR | Regiao geografica |
| auction_date | DATE | Data do leilao |
| value_brl | NUMERIC | Valor pago (BRL) |

| Metrica | Valor |
|---------|-------|
| Registros | 47 |
| Atualizacao | Eventual |
| Pipeline | Carga manual |

---

## Tabelas de Infraestrutura

### road_segments

Segmentos rodoviarios do Brasil (grafo para roteamento de fibra).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| highway_class | VARCHAR | Classe da via — **NOTA: usar `highway_class`, NAO `road_type`** |
| geometry | GEOMETRY | Geometria do segmento (LineString, SRID 4326) |
| length_km | FLOAT | Comprimento em km |
| country_code | VARCHAR | Codigo do pais |
| source | INTEGER | Node de origem (pgRouting) |
| target | INTEGER | Node de destino (pgRouting) |
| cost | FLOAT | Custo de travessia (proporcional a length_km) |
| reverse_cost | FLOAT | Custo reverso (= cost para bidirecional) |

| Metrica | Valor |
|---------|-------|
| Registros | 6.457.585 |
| Extensao total | 3,73M km |
| Regioes | SE, Norte, Nordeste, Centro-Oeste, Sul (todas as 5) |
| Atualizacao | Mensal |
| Pipeline | osm_roads |
| **NOTA** | NAO possui colunas `lanes` ou `speed_limit_kmh` |

### power_lines

Linhas de transmissao eletrica (para co-locacao de fibra).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| geometry | GEOMETRY | Geometria do segmento (LineString) |
| voltage_kv | FLOAT | Voltagem em kV |
| length_km | FLOAT | Comprimento em km |
| country_code | VARCHAR | Codigo do pais |

| Metrica | Valor |
|---------|-------|
| Registros | 16.559 |
| Extensao total | 256K km |
| Atualizacao | Semanal |
| Pipeline | aneel_power |

### srtm_tiles

Metadata de tiles de terreno SRTM 30m (dados fisicos em disco).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| tile_name | VARCHAR | Nome do tile (ex: "S23W044") |
| filepath | VARCHAR | Caminho no disco (/tmp/srtm/...) |
| resolution_m | FLOAT | Resolucao em metros (30) |
| bbox | GEOMETRY | Bounding box do tile |

| Metrica | Valor |
|---------|-------|
| Registros (disco) | 1.681 tiles |
| Tamanho total | 40.6 GB |
| Cobertura | Todo o Brasil |
| Atualizacao | Mensal (verificacao de integridade) |
| Pipeline | srtm_terrain |

---

## Tabelas Meteorologicas

### weather_stations

Estacoes meteorologicas do INMET.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| code | VARCHAR | Codigo INMET da estacao |
| name | VARCHAR | Nome da estacao |
| latitude | FLOAT | Latitude |
| longitude | FLOAT | Longitude |
| altitude_m | FLOAT | Altitude em metros |
| state_code | VARCHAR | UF |

| Metrica | Valor |
|---------|-------|
| Registros | 671 |
| Atualizacao | Diaria |
| Pipeline | inmet_weather |

### weather_observations

Observacoes meteorologicas (temperatura, chuva, vento).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| station_id | INTEGER FK | Referencia para weather_stations |
| observed_at | TIMESTAMP | Data/hora da observacao |
| temperature_c | FLOAT | Temperatura (Celsius) |
| precipitation_mm | FLOAT | Precipitacao (mm) |
| wind_speed_ms | FLOAT | Velocidade do vento (m/s) |
| humidity_pct | FLOAT | Umidade relativa (%) |
| pressure_hpa | FLOAT | Pressao atmosferica (hPa) |

| Metrica | Valor |
|---------|-------|
| Registros | 61.061 |
| Janela | 90 dias |
| Atualizacao | Diaria |
| Pipeline | inmet_weather |

---

## Tabelas Computadas

### opportunity_scores

Scores de oportunidade de expansao por municipio (derivados).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| geographic_id | VARCHAR | Codigo IBGE do municipio |
| computed_at | TIMESTAMP | Data/hora do calculo |
| composite_score | FLOAT | Score composto (0-100) |
| demand_score | FLOAT | Score de demanda (0-100) |
| competition_score | FLOAT | Score de concorrencia (0-100) |
| infrastructure_score | FLOAT | Score de infraestrutura (0-100) |
| growth_score | FLOAT | Score de crescimento (0-100) |
| features | JSONB | Detalhes adicionais (social_score, backhaul_boost, school_gap, etc.) |

| Metrica | Valor |
|---------|-------|
| Registros | 5.570 |
| Atualizacao | Automatica (pos-broadband/geographic update) |
| Formula | demand (25%) + competition (20%) + infrastructure (20%) + growth (15%) + social (20%) |
| Pipeline | _recompute_derived_data() |

### quality_indicators

Indicadores de qualidade de servico por provedor e municipio.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Referencia para providers |
| l2_id | INTEGER FK | Referencia para admin_level_2 |
| ida_score | FLOAT | Score IDA composto (0-10) |
| download_speed_pct | FLOAT | Compliance de velocidade download (%) |
| upload_speed_pct | FLOAT | Compliance de velocidade upload (%) |
| latency_pct | FLOAT | Compliance de latencia (%) |
| availability_pct | FLOAT | Disponibilidade (%) |

| Metrica | Valor |
|---------|-------|
| Registros | 33.420 |
| Atualizacao | Diaria |
| Pipeline | anatel_quality |

### competitive_analysis

Analise competitiva por municipio e mes.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| l2_id | INTEGER FK | Referencia para admin_level_2 |
| year_month | VARCHAR | Periodo "YYYY-MM" |
| computed_at | TIMESTAMP | Data/hora do calculo |
| hhi_index | FLOAT | Indice Herfindahl-Hirschman |
| leader_provider_id | INTEGER FK | Provedor lider (maior market share) |
| leader_market_share | FLOAT | Market share do lider (%) |
| provider_details | JSONB | Detalhes dos top 10 provedores |
| growth_trend | VARCHAR | Tendencia: growing, stable, declining, new |
| threat_level | VARCHAR | Nivel: monopoly, high_concentration, moderate, competitive |

| Metrica | Valor |
|---------|-------|
| Registros | ~5.570 |
| Atualizacao | Automatica (pos-broadband update) |
| Constraint | UNIQUE (l2_id, year_month) |
| Pipeline | _recompute_derived_data() |

---

## Tabelas Satelitais

### sentinel_urban_indices

Indices de crescimento urbano derivados do Sentinel-2.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Referencia para admin_level_2 |
| year | INTEGER | Ano do composito |
| mean_ndvi | FLOAT | NDVI medio (vegetacao) |
| ndvi_std | FLOAT | Desvio padrao NDVI |
| mean_ndbi | FLOAT | NDBI medio (area construida) |
| built_up_area_km2 | FLOAT | Area construida (km2) |
| built_up_pct | FLOAT | Porcentagem de area construida |
| mean_mndwi | FLOAT | MNDWI medio (agua) |
| water_area_km2 | FLOAT | Area de agua (km2) |
| mean_bsi | FLOAT | BSI medio (solo exposto) |
| bare_soil_area_km2 | FLOAT | Area de solo exposto (km2) |
| built_up_change_km2 | FLOAT | Mudanca de area construida (km2 vs. ano anterior) |
| built_up_change_pct | FLOAT | Mudanca de area construida (% vs. ano anterior) |
| ndvi_change_pct | FLOAT | Mudanca de NDVI (% vs. ano anterior) |
| scenes_used | INTEGER | Numero de cenas Sentinel-2 utilizadas |
| created_at | TIMESTAMP | Data de computacao |

| Metrica | Valor |
|---------|-------|
| Registros | 87+ |
| Cobertura temporal | 2016-2026 |
| Atualizacao | Mensal |
| Pipeline | sentinel_growth |
| Constraint | UNIQUE (l2_id, year) |

---

## Tabelas Adicionais (Sprint 14)

| Tabela | Registros | Pipeline | Descricao |
|--------|-----------|----------|-----------|
| `ibge_population` | 5.570 | ibge_census | Populacao IBGE 2024 por municipio |
| `quality_seals` | Variavel | anatel_rqual | Selos de qualidade RQual/IQS |
| `government_contracts` | Variavel | pncp_contracts | Contratos publicos de telecom |
| `regulatory_acts` | Variavel | dou_anatel | Atos regulatorios do DOU |
| `gazette_mentions` | Variavel | querido_diario | Mencoes em gazetas municipais |
| `bndes_loans` | Variavel | bndes_loans | Emprestimos BNDES telecom |
| `fust_spending` | Variavel | transparencia_fust | Gastos FUST/FUNTTEL |
| `backhaul_presence` | Variavel | anatel_backhaul | Presenca de backhaul por municipio |
| `health_facilities` | Variavel | datasus_health | Estabelecimentos de saude CNES |
| `schools` | Variavel | inep_schools | Escolas do Censo Escolar |
| `municipal_planning` | Variavel | ibge_munic | Planejamento municipal (MUNIC) |
| `building_density` | Variavel | ibge_cnefe | Densidade de edificacoes (CNEFE) |
| `employment_indicators` | Variavel | caged_employment | Indicadores de emprego (CAGED) |
| `safety_indicators` | Variavel | atlas_violencia | Indicadores de seguranca |
| `fuel_prices` | Variavel | anp_fuel | Precos de combustivel |
| `sanitation_indicators` | Variavel | snis_sanitation | Indicadores de saneamento |
| `household_expenditure` | Variavel | ibge_pof | Gastos familiares (POF) |
| `land_cover` | Variavel | mapbiomas_landcover | Cobertura do solo (MapBiomas) |
| `population_projections` | Variavel | ibge_projections | Projecoes populacionais |
| `municipal_gdp` | Variavel | ibge_pib | PIB municipal |
| `sentinel_composites` | Variavel | sentinel_growth | Compositos Sentinel-2 (metadata) |

---

## Tabelas Wave 1 (Migracao 0003)

### building_footprints

Footprints de edificacoes (Microsoft Buildings).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Referencia para admin_level_2 |
| geometry | GEOMETRY | Footprint do edificio (Polygon) |
| area_m2 | FLOAT | Area do footprint em m2 |
| confidence | FLOAT | Confianca do ML (0-1) |
| created_at | TIMESTAMP | Data de importacao |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel (on-demand) |
| Atualizacao | On-demand |
| Pipeline | ms_buildings |

### speedtest_tiles

Tiles de velocidade Ookla Speedtest.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| quadkey | VARCHAR | Quadkey do tile (zoom 16) |
| avg_d_kbps | INTEGER | Download medio (kbps) |
| avg_u_kbps | INTEGER | Upload medio (kbps) |
| avg_lat_ms | INTEGER | Latencia media (ms) |
| tests | INTEGER | Numero de testes |
| devices | INTEGER | Dispositivos unicos |
| quarter | VARCHAR | Trimestre (YYYY-Q#) |
| geometry | GEOMETRY | Geometria do tile |

| Metrica | Valor |
|---------|-------|
| Registros | 200K+ |
| Atualizacao | On-demand |
| Pipeline | ookla_speedtest |

### speedtest_municipality

Agregacao de speedtest por municipio.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Referencia para admin_level_2 |
| avg_download_mbps | FLOAT | Download medio (Mbps) |
| avg_upload_mbps | FLOAT | Upload medio (Mbps) |
| avg_latency_ms | FLOAT | Latencia media (ms) |
| total_tests | INTEGER | Total de testes |
| quarter | VARCHAR | Trimestre |

| Metrica | Valor |
|---------|-------|
| Registros | ~5.572 por quarter |
| Atualizacao | On-demand |
| Pipeline | ookla_speedtest |

### opencellid_towers

Torres de celular (OpenCelliD).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| cell_id | BIGINT | ID da celula |
| mcc | INTEGER | Mobile Country Code |
| mnc | INTEGER | Mobile Network Code |
| lac | INTEGER | Location Area Code |
| radio | VARCHAR | Tipo (GSM, UMTS, LTE, NR) |
| latitude | FLOAT | Latitude |
| longitude | FLOAT | Longitude |
| range_m | INTEGER | Alcance estimado (m) |
| created_at | TIMESTAMP | Data de importacao |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | On-demand |
| Pipeline | opencellid |

### coverage_validation

Validacao de cobertura (ERBs vs assinantes).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Municipio |
| provider_id | INTEGER FK | Provedor |
| claimed_coverage | BOOLEAN | Cobertura declarada |
| has_subscribers | BOOLEAN | Tem assinantes ativos |
| has_base_station | BOOLEAN | Tem ERB no municipio |
| validation_status | VARCHAR | Status (validated, gap, overclaim) |
| computed_at | TIMESTAMP | Data do calculo |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | Computado |
| Pipeline | coverage validation |

### tower_colocation_analysis

Analise de co-locacao de torres com linhas de energia.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| tower_id | INTEGER FK | Referencia para base_stations |
| nearest_power_line_id | INTEGER FK | Linha de energia mais proxima |
| distance_m | FLOAT | Distancia em metros |
| colocation_feasible | BOOLEAN | Viabilidade de co-locacao |
| computed_at | TIMESTAMP | Data do calculo |

| Metrica | Valor |
|---------|-------|
| Registros | 4 (proof of concept) |
| Atualizacao | On-demand |
| Pipeline | colocation_service |

### h3_cells

Celulas hexagonais H3.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| h3_index | VARCHAR | Indice H3 (resolucao 7) |
| resolution | INTEGER | Resolucao H3 (5-9) |
| l2_id | INTEGER FK | Municipio |
| population_estimate | INTEGER | Populacao estimada |
| subscriber_count | INTEGER | Assinantes estimados |
| geometry | GEOMETRY | Geometria hexagonal |

| Metrica | Valor |
|---------|-------|
| Registros | 100K+ |
| Atualizacao | On-demand |
| Pipeline | h3_grid |

### subscriber_timeseries

Series temporais de assinantes para forecasting.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| l2_id | INTEGER FK | Municipio |
| provider_id | INTEGER FK | Provedor |
| year_month | VARCHAR | Periodo "YYYY-MM" |
| subscribers | INTEGER | Assinantes |
| technology | VARCHAR | Tecnologia |
| trend | VARCHAR | Tendencia (growing, stable, declining) |

| Metrica | Valor |
|---------|-------|
| Registros | Derivado de broadband_subscribers |
| Atualizacao | Computado |
| Pipeline | timeseries_service |

### alert_rules

Regras de alerta configuradas por usuario.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| tenant_id | INTEGER FK | Tenant |
| name | VARCHAR | Nome da regra |
| metric | VARCHAR | Metrica monitorada |
| condition | VARCHAR | Condicao (gt, lt, eq, change_pct) |
| threshold | FLOAT | Limiar |
| enabled | BOOLEAN | Ativa/inativa |
| created_at | TIMESTAMP | Data de criacao |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel (por tenant) |
| Atualizacao | User-driven |
| Pipeline | alert_engine |

### alert_events

Eventos de alerta disparados.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| rule_id | INTEGER FK | Regra que disparou |
| triggered_at | TIMESTAMP | Data/hora do disparo |
| current_value | FLOAT | Valor atual |
| message | TEXT | Mensagem do alerta |
| acknowledged | BOOLEAN | Reconhecido pelo usuario |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | Event-driven |
| Pipeline | alert_engine |

### pulso_scores

Scores de saude do provedor Pulso.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Provedor |
| overall_score | FLOAT | Score geral (0-100) |
| growth_score | FLOAT | Crescimento |
| quality_score | FLOAT | Qualidade |
| coverage_score | FLOAT | Cobertura |
| financial_score | FLOAT | Financeiro |
| computed_at | TIMESTAMP | Data do calculo |

| Metrica | Valor |
|---------|-------|
| Registros | 13.534 |
| Atualizacao | On-demand |
| Pipeline | pulso_score |

### isp_credit_scores

Ratings de credito de ISPs.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Provedor |
| rating | VARCHAR | Rating (AAA a D) |
| score | FLOAT | Score numerico (0-100) |
| financial_factor | FLOAT | Fator financeiro |
| operational_factor | FLOAT | Fator operacional |
| market_factor | FLOAT | Fator de mercado |
| computed_at | TIMESTAMP | Data do calculo |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel (on-demand) |
| Atualizacao | On-demand |
| Pipeline | credit_scoring |
| Exemplos | CLARO BBB/61.0, ABNET BB/51.4 |

---

## Tabelas Wave 2 (Migracao 0004)

### spectrum_holdings

Holdings de espectro por operadora.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Operadora |
| band_mhz | VARCHAR | Banda de frequencia |
| bandwidth_mhz | FLOAT | Largura de banda |
| region | VARCHAR | Regiao |
| license_type | VARCHAR | Tipo de licenca |
| expiry_date | DATE | Data de expiracao |
| estimated_value_brl | NUMERIC | Valor estimado |

| Metrica | Valor |
|---------|-------|
| Registros | 47+ |
| Atualizacao | Eventual |
| Pipeline | Carga manual / mna_enhanced |

### rgst777_compliance

Compliance com RGST 777 por provedor.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Provedor |
| obligation | VARCHAR | Obrigacao especifica |
| status | VARCHAR | Status (compliant, non_compliant, partial) |
| deadline | DATE | Prazo |
| evidence | TEXT | Evidencia documentada |
| checked_at | TIMESTAMP | Data da verificacao |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | Computado |
| Pipeline | compliance_checker |

### coverage_obligations_5g

Obrigacoes de cobertura 5G dos leiloes.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| provider_id | INTEGER FK | Operadora |
| obligation_type | VARCHAR | Tipo (coverage, backhaul, rede_privativa) |
| target_municipalities | INTEGER | Municipios-alvo |
| deadline | DATE | Prazo |
| progress_pct | FLOAT | Progresso (%) |
| source_auction | VARCHAR | Leilao de origem |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | Computado |
| Pipeline | coverage_obligations |

### peering_networks

Redes de peering (PeeringDB).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| asn | INTEGER | Autonomous System Number |
| name | VARCHAR | Nome da rede |
| info_type | VARCHAR | Tipo (NSP, Content, Enterprise, etc.) |
| info_traffic | VARCHAR | Volume de trafego |
| policy_general | VARCHAR | Politica de peering (open, selective, restrictive) |
| website | VARCHAR | Website |
| created_at | TIMESTAMP | Data de importacao |

| Metrica | Valor |
|---------|-------|
| Registros | 34.000+ |
| Atualizacao | On-demand |
| Pipeline | peeringdb |

### peering_ixps

Participacao em IXPs (PeeringDB).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| network_id | INTEGER FK | Rede |
| ixp_id | INTEGER FK | IXP |
| speed_mbps | INTEGER | Velocidade da porta |
| is_rs_peer | BOOLEAN | Peering via route server |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | On-demand |
| Pipeline | peeringdb |

### ixp_locations

Localizacoes de IXPs no Brasil (IX.br).

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| name | VARCHAR | Nome do PIX |
| city | VARCHAR | Cidade |
| state | VARCHAR | Estado |
| latitude | FLOAT | Latitude |
| longitude | FLOAT | Longitude |
| participants | INTEGER | Numero de participantes |
| aggregate_traffic_gbps | FLOAT | Trafego agregado (Gbps) |

| Metrica | Valor |
|---------|-------|
| Registros | 37+ |
| Atualizacao | On-demand |
| Pipeline | ixbr |

### ixp_traffic_history

Historico de trafego de IXPs.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | SERIAL PK | Identificador interno |
| ixp_id | INTEGER FK | IXP |
| date | DATE | Data |
| peak_traffic_gbps | FLOAT | Pico de trafego (Gbps) |
| avg_traffic_gbps | FLOAT | Media de trafego (Gbps) |

| Metrica | Valor |
|---------|-------|
| Registros | Variavel |
| Atualizacao | On-demand |
| Pipeline | ixbr |

---

## Materialized View

### mv_market_summary

Agregacao principal de dados de mercado, atualizada apos cada ingestao de broadband.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| l2_id | INTEGER | ID do municipio |
| municipality_code | VARCHAR | Codigo IBGE |
| municipality_name | VARCHAR | Nome do municipio |
| state_abbrev | VARCHAR | UF |
| country_code | VARCHAR | "BR" |
| year_month | VARCHAR | Ultimo periodo disponivel |
| total_subscribers | BIGINT | Total de assinantes |
| fiber_subscribers | BIGINT | Assinantes de fibra |
| provider_count | INTEGER | Numero de provedores |
| total_households | INTEGER | Total de domicilios |
| total_population | INTEGER | Populacao total |
| broadband_penetration_pct | NUMERIC | Penetracao de banda larga (%) |
| fiber_share_pct | NUMERIC | Participacao de fibra (%) |
| centroid | GEOMETRY | Centroide do municipio (Point) |

| Metrica | Valor |
|---------|-------|
| Refresh | `REFRESH MATERIALIZED VIEW CONCURRENTLY` |
| Trigger | Automatico apos pipeline anatel_broadband |

---

## Notas Importantes sobre Schema

1. **`admin_level_1.abbrev`** — Usar `abbrev`, NAO `abbreviation`
2. **`providers.national_id`** — Usar `national_id`, NAO `cnpj`
3. **`providers.name`** — Usar `name`, NAO `trade_name`
4. **`broadband_subscribers.l2_id`** — Usar `l2_id`, NAO `municipality_id`
5. **`broadband_subscribers.subscribers`** — Usar `subscribers`, NAO `subscriber_count`
6. **`broadband_subscribers.year_month`** — Usar `year_month`, NAO `date`
7. **`road_segments.highway_class`** — Usar `highway_class`, NAO `road_type`
8. **`road_segments`** — NAO possui colunas `lanes` ou `speed_limit_kmh`
9. **`road_segments`** — Colunas pgRouting adicionadas: `source`, `target`, `cost`, `reverse_cost`
10. **`opportunity_scores.geographic_id`** — Codigo IBGE, join via `admin_level_2.code`
