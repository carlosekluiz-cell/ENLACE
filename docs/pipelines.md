# Catalogo de Pipelines — Enlace / Pulso Network

**38 pipelines de ingestao e computacao de dados**

Versao 2.0 | Marco 2026

---

## Visao Geral

| Frequencia | Quantidade | Horario (UTC) |
|------------|-----------|---------------|
| Diario | 7 | 02:00, 02:30, 03:00 |
| Semanal (Domingos) | 7 | 04:00, 04:30 |
| Mensal (dia 1) | 12 | 05:00, 06:00 |
| Computados (pos-ingestao) | 5 | Automatico apos telecom/geographic |
| On-demand | 7 | Manual / trigger |
| **Total** | **38** | |

---

## Pipelines Diarios — Telecom (02:00 UTC)

### 1. anatel_providers

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelProvidersPipeline` |
| **Fonte** | Anatel open data (dados.gov.br/CKAN) |
| **URL** | `dados.gov.br` — dataset "prestadoras-de-servicos-de-telecomunicacoes" |
| **Formato** | CSV (semicolon-delimited, ISO-8859-1) |
| **Tabela destino** | `providers` |
| **Registros** | 13.534 |
| **Frequencia** | Diario |
| **Validacao** | CNPJ unico, nome normalizado, country_code = 'BR' |

### 2. anatel_broadband

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelBroadbandPipeline` |
| **Fonte** | Anatel open data — "acessos---banda-larga-fixa" |
| **Formato** | CSV (semicolon-delimited, ISO-8859-1, milhoes de linhas) |
| **Tabela destino** | `broadband_subscribers` |
| **Registros** | 4.137.609 (37 meses, 2023-2026) |
| **Frequencia** | Diario (atualizacao mensal da Anatel, ~45 dias apos mes) |
| **Campos-chave** | year_month, provider_id (via CNPJ), l2_id (via Codigo IBGE), technology, subscribers |
| **Normalizacao** | Tecnologia mapeada (Fibra Optica -> fiber, Cabo Coaxial -> cable, etc.) |
| **Pos-processamento** | Trigger: refresh mv_market_summary + recompute opportunity_scores |
| **Validacao** | CNPJ match com providers, Codigo IBGE match com admin_level_2 |

### 3. anatel_base_stations

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelBaseStationsPipeline` |
| **Fonte** | OpenStreetMap (Overpass API) + atribuicao por market share |
| **Tabela destino** | `base_stations` |
| **Registros** | 37.727 |
| **Frequencia** | Diario |
| **Atribuicao** | Proprietaria: probabilistic operator attribution via market share municipal (CLARO 4.887, VIVO 3.560, OI 2.286, TIM 885 + regionais) |
| **Validacao** | Coordenadas dentro do Brasil, provider_id valido |

### 4. anatel_quality

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelQualityPipeline` |
| **Fonte** | Anatel SFF (Sistema de Fiscalizacao e Fomento) |
| **Tabela destino** | `quality_indicators` |
| **Registros** | 33.420 |
| **Frequencia** | Diario |
| **Metricas** | IDA score, download/upload speed compliance, latency, availability |
| **Validacao** | Score entre 0-10, porcentagens 0-100 |

---

## Pipelines Diarios — Intelligence (02:30 UTC)

### 5. pncp_contracts

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `PNCPContractsPipeline` |
| **Fonte** | Portal Nacional de Contratacoes Publicas (PNCP) |
| **URL** | `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` |
| **Formato** | REST JSON (paginado, 10 resultados/pagina) |
| **Tabela destino** | `government_contracts` |
| **Frequencia** | Diario |
| **Filtro** | Keywords telecom: telecomunicacao, fibra optica, banda larga, conectividade, etc. |
| **Modalidades** | Pregao Eletronico, Dispensa, Inexigibilidade, Concorrencia, Credenciamento |
| **Janela** | Ultimos 12 meses, chunks mensais |
| **Validacao** | Regex local de keywords telecom como filtro autoritativo |

### 6. dou_anatel

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `DOUAnatelPipeline` |
| **Fonte** | Diario Oficial da Uniao (DOU) — atos da Anatel |
| **Tabela destino** | `regulatory_acts` |
| **Frequencia** | Diario |
| **Conteudo** | Resolucoes, portarias, atos regulatorios da Anatel publicados no DOU |
| **Validacao** | Data de publicacao, tipo de ato, referencia normativa |

### 7. querido_diario

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `QueridoDiarioPipeline` |
| **Fonte** | Querido Diario (Open Knowledge Brasil) — gazetas municipais |
| **Tabela destino** | `gazette_mentions` |
| **Frequencia** | Diario |
| **Conteudo** | Mencoes a telecomunicacoes em diarios oficiais municipais |
| **Validacao** | Municipio match com admin_level_2, data de publicacao |

---

## Pipeline Diario — Clima (03:00 UTC)

### 8. inmet_weather

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `INMETWeatherPipeline` |
| **Fonte** | Open-Meteo (INMET API retorna 403) |
| **Tabelas destino** | `weather_stations` (671), `weather_observations` (61.061) |
| **Frequencia** | Diario |
| **Metricas** | Temperatura, precipitacao, vento, umidade, pressao |
| **Janela** | 90 dias de observacoes |
| **Validacao** | Coordenadas validas, valores dentro de limites fisicos |

---

## Pipelines Semanais — Economico (Domingos 04:00 UTC)

### 9. ibge_pib

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGEPIBPipeline` |
| **Fonte** | IBGE — Produto Interno Bruto municipal |
| **Tabela destino** | `municipal_gdp` |
| **Frequencia** | Semanal |
| **Validacao** | Codigo IBGE match, valores positivos |

### 10. ibge_projections

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGEProjectionsPipeline` |
| **Fonte** | IBGE — Projecoes populacionais |
| **Tabela destino** | `population_projections` |
| **Frequencia** | Semanal |
| **Validacao** | Ano futuro, populacao positiva |

### 11. ibge_pof

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGEPOFPipeline` |
| **Fonte** | IBGE — Pesquisa de Orcamentos Familiares |
| **Tabela destino** | `household_expenditure` |
| **Frequencia** | Semanal |
| **Conteudo** | Gastos com telecomunicacoes por faixa de renda e regiao |
| **Validacao** | Valores de despesa positivos |

### 12. anp_fuel

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `ANPFuelPipeline` |
| **Fonte** | ANP (Agencia Nacional do Petroleo) |
| **Tabela destino** | `fuel_prices` |
| **Frequencia** | Semanal |
| **Conteudo** | Precos de combustivel por municipio (proxy para custo de transporte/manutencao) |
| **Validacao** | Precos dentro de limites realistas |

### 13. aneel_power

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `ANEELPowerPipeline` |
| **Fonte** | ANEEL (Agencia Nacional de Energia Eletrica) + OSM |
| **Tabela destino** | `power_lines` |
| **Registros** | 16.559 segmentos (256K km) |
| **Frequencia** | Semanal |
| **Conteudo** | Linhas de transmissao para analise de co-locacao de fibra |
| **Validacao** | Geometria valida (LineString), voltagem |

### 14. snis_sanitation

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `SNISSanitationPipeline` |
| **Fonte** | SNIS (Sistema Nacional de Informacoes sobre Saneamento) |
| **Tabela destino** | `sanitation_indicators` |
| **Frequencia** | Semanal |
| **Conteudo** | Indicadores de infraestrutura basica (proxy para desenvolvimento municipal) |
| **Validacao** | Codigo IBGE match, indices entre 0-100 |

### 15. bndes_loans

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `BNDESLoansPipeline` |
| **Fonte** | BNDES Transparencia (portal de dados abertos) |
| **Tabela destino** | `bndes_loans` |
| **Frequencia** | Semanal |
| **Conteudo** | Emprestimos do BNDES para setor de telecomunicacoes |
| **Campos** | provider_id, contract_value_brl, disbursed_brl, contract_date, sector |
| **Validacao** | Valores monetarios positivos, match com providers |

---

## Pipelines Semanais — Enriquecimento (Domingos 04:30 UTC)

### 16. cnpj_enrichment

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `CNPJEnrichmentPipeline` |
| **Fonte** | ReceitaWS (Receita Federal via API) |
| **URL** | `receitaws.com.br/v1/cnpj/{cnpj}` |
| **Tabela destino** | `provider_details` |
| **Frequencia** | Semanal (incremental — so providers nao enriquecidos ou > 30 dias) |
| **Rate limit** | 3 req/min (21s entre requests) |
| **Campos** | status, capital_social, founding_date, partner_count, simples_nacional, cnae_primary |
| **Validacao** | CNPJ valido, resposta HTTP 200 |

### 17. anatel_rqual

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelRQUALPipeline` |
| **Fonte** | Anatel — Regulamento de Qualidade (RQual/IQS) |
| **Tabela destino** | `quality_seals` |
| **Frequencia** | Semanal |
| **Campos** | provider_id, l2_id, year_half, overall_score, availability_score, speed_score, latency_score, seal_level |
| **Validacao** | Scores entre 0-100, seal_level valido |

### 18. transparencia_fust

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `TransparenciaFUSTPipeline` |
| **Fonte** | Portal da Transparencia — FUST/FUNTTEL |
| **Tabela destino** | `fust_spending` |
| **Frequencia** | Semanal |
| **Conteudo** | Gastos do FUST (Fundo de Universalizacao dos Servicos de Telecomunicacoes) |
| **Validacao** | Valores monetarios, datas validas |

---

## Pipelines Mensais — Geografico (dia 1, 05:00 UTC)

### 19. ibge_census

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGECensusPipeline` |
| **Fonte** | IBGE — Censo Demografico e estimativas populacionais |
| **Tabela destino** | `admin_level_2` (atualizacao de population), `ibge_population` |
| **Registros** | 5.570 (ibge_population), 5.572 (admin_level_2) |
| **Frequencia** | Mensal |
| **Validacao** | Codigo IBGE match, populacao positiva |

### 20. srtm_terrain

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `SRTMTerrainPipeline` |
| **Fonte** | SRTM 30m (NASA/USGS via AWS S3) |
| **Tabela destino** | `srtm_tiles` (metadata) + disco (`/tmp/srtm`) |
| **Registros** | 1.681 tiles / 40.6 GB |
| **Frequencia** | Mensal (verificacao de integridade) |
| **Cobertura** | Todo o Brasil |
| **Validacao** | Checksum SHA256, resolucao 30m, cobertura completa |

### 21. mapbiomas_landcover

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `MapBiomasLandCoverPipeline` |
| **Fonte** | MapBiomas (cobertura e uso do solo) |
| **Tabela destino** | `land_cover` |
| **Frequencia** | Mensal |
| **Conteudo** | Classificacao de cobertura do solo por municipio (vegetacao, area construida, agua) |
| **Uso** | Modelagem de atenuacao por vegetacao no motor RF |
| **Validacao** | Porcentagens somam 100%, classes validas |

### 22. osm_roads

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `OSMRoadsPipeline` |
| **Fonte** | OpenStreetMap (Geofabrik) — todas as 5 regioes do Brasil |
| **Tabela destino** | `road_segments` |
| **Registros** | 6.457.585 (3,73M km) |
| **Frequencia** | Mensal |
| **Campos** | highway_class, geometry (LineString), length_km |
| **Uso** | Grafo para Dijkstra (roteamento de fibra) |
| **Validacao** | Geometria valida, highway_class dentro do enum |

### 23. anatel_backhaul

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AnatelBackhaulPipeline` |
| **Fonte** | Anatel — dados de backhaul (fibra backbone) |
| **Tabela destino** | `backhaul_presence` |
| **Frequencia** | Mensal |
| **Campos** | l2_id, has_fiber_backhaul, year |
| **Uso** | Score de oportunidade: municipio sem backhaul = +30 infrastructure_score |
| **Validacao** | Boolean has_fiber_backhaul, l2_id match |

### 24. datasus_health

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `DATASUSHealthPipeline` |
| **Fonte** | CNES (Cadastro Nacional de Estabelecimentos de Saude) via S3 |
| **URL** | `s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos.zip` |
| **Tabela destino** | `health_facilities` |
| **Frequencia** | Mensal |
| **Campos** | nome, cnes_code, l2_id, lat, lon, bed_count, facility_type, has_internet |
| **Uso** | Anchor institutions: facilities sem internet = oportunidade de connectivity |
| **Validacao** | Coordenadas dentro do Brasil, CNES code unico |

### 25. inep_schools

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `INEPSchoolsPipeline` |
| **Fonte** | INEP — Censo Escolar |
| **Tabela destino** | `schools` |
| **Frequencia** | Mensal |
| **Campos** | nome, l2_id, lat, lon, has_internet, student_count |
| **Uso** | Score de oportunidade: escolas sem internet boost demand_score e social_score |
| **Validacao** | Codigo INEP unico, l2_id match |

### 26. ibge_munic

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGEMUNICPipeline` |
| **Fonte** | IBGE — Pesquisa de Informacoes Basicas Municipais (MUNIC) |
| **Tabela destino** | `municipal_planning` |
| **Frequencia** | Mensal |
| **Campos** | l2_id, has_plano_diretor, has_building_code, munic_year |
| **Uso** | Score: municipio com plano diretor e codigo de obras = +10 infrastructure_score |
| **Validacao** | Boolean fields, year valido |

### 27. ibge_cnefe

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IBGECNEFEPipeline` |
| **Fonte** | IBGE — Cadastro Nacional de Enderecos para Fins Estatisticos |
| **Tabela destino** | `building_density` |
| **Frequencia** | Mensal |
| **Campos** | l2_id, density_per_km2, residential_addresses, year |
| **Uso** | Score: densidade > 500/km2 com alta demanda = +15 demand_score |
| **Validacao** | Densidade positiva, l2_id match |

### 28. caged_employment

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `CAGEDEmploymentPipeline` |
| **Fonte** | CAGED (Cadastro Geral de Empregados e Desempregados) |
| **Tabela destino** | `employment_indicators` |
| **Frequencia** | Mensal |
| **Campos** | l2_id, net_hires, year, month |
| **Uso** | Score: net_hires > 0 = +20 growth_score (economia crescendo) |
| **Validacao** | l2_id match, year/month validos |

### 29. atlas_violencia

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `AtlasViolenciaPipeline` |
| **Fonte** | Atlas da Violencia (IPEA/FBSP) |
| **Tabela destino** | `safety_indicators` |
| **Frequencia** | Mensal |
| **Campos** | l2_id, risk_score, year |
| **Uso** | Score: area segura (100 - risk_score) * 0.2 -> social_score |
| **Validacao** | risk_score entre 0-100, l2_id match |

---

## Pipeline Mensal — Satelite (dia 1, 06:00 UTC)

### 30. sentinel_growth

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `SentinelGrowthPipeline` |
| **Fonte** | Google Earth Engine — Sentinel-2 |
| **Tabelas destino** | `sentinel_urban_indices`, `sentinel_composites` |
| **Frequencia** | Mensal |
| **Indices** | NDVI, NDBI, MNDWI, BSI |
| **Cobertura** | 2016-2026 (10 anos por municipio) |
| **Dependencia** | earthengine-api (import optional) |
| **Validacao** | Indices dentro de limites fisicos (-1 a +1), area km2 positiva |

---

## Pipelines Computados (Pos-Ingestao)

Estes nao sao pipelines standalone — sao executados automaticamente pela funcao `_recompute_derived_data()` apos pipelines de telecom e geographic.

### 31a. opportunity_scores (recompute)

| Aspecto | Detalhe |
|---------|---------|
| **Tabela destino** | `opportunity_scores` |
| **Registros** | 5.570 |
| **Trigger** | Apos broadband update (diario) ou geographic update (mensal) |
| **Formula** | demand (25%) + competition (20%) + infrastructure (20%) + growth (15%) + social (20%) |
| **8 fatores de enriquecimento** | backhaul, schools, health, employment, quality seals, safety, building density, municipal planning |

### 31b. competitive_analysis (recompute)

| Aspecto | Detalhe |
|---------|---------|
| **Tabela destino** | `competitive_analysis` |
| **Trigger** | Apos broadband update |
| **Campos** | l2_id, year_month, hhi_index, leader_provider_id, leader_market_share, provider_details (JSON), growth_trend, threat_level |
| **HHI thresholds** | > 5000 = monopoly, > 2500 = high_concentration, > 1500 = moderate, < 1500 = competitive |

### 31c. market_summary_refresh

| Aspecto | Detalhe |
|---------|---------|
| **Destino** | `mv_market_summary` (REFRESH MATERIALIZED VIEW CONCURRENTLY) |
| **Trigger** | Apos broadband update |
| **Conteudo** | Agregacao de broadband_subscribers + admin_level_2 + providers + ibge_population |

---

## Pipelines On-Demand (7)

Pipelines executados manualmente ou por trigger, nao agendados.

### 32. ms_buildings

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `MSBuildingsPipeline` |
| **Fonte** | Microsoft Building Footprints |
| **Tabela destino** | `building_footprints` |
| **Frequencia** | On-demand |
| **Conteudo** | Footprints de edificacoes detectados por ML |
| **Uso** | Estimativa de densidade habitacional para scoring |

### 33. opencellid

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `OpenCelliDPipeline` |
| **Fonte** | OpenCelliD (community cell tower database) |
| **Tabela destino** | `opencellid_towers` |
| **Frequencia** | On-demand |
| **Conteudo** | Torres de celular com localizacao e tipo de radio |
| **Uso** | Validacao cruzada com base_stations da Anatel |

### 34. ookla_speedtest

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `OoklaSpeedtestPipeline` |
| **Fonte** | Ookla Open Data (tiles de speedtest) |
| **Tabelas destino** | `speedtest_tiles`, `speedtest_municipality` |
| **Frequencia** | On-demand (trimestral) |
| **Conteudo** | Medicoes de velocidade agregadas em tiles e por municipio |
| **Registros** | 200K+ tiles |

### 35. h3_grid

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `H3GridPipeline` |
| **Fonte** | Computado (H3 sobre admin_level_2 + broadband) |
| **Tabela destino** | `h3_cells` |
| **Frequencia** | On-demand |
| **Conteudo** | Grade hexagonal H3 com estimativas de populacao e assinantes |
| **Registros** | 100K+ celulas |

### 36. pulso_score

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `PulsoScorePipeline` |
| **Fonte** | Computado (multi-fator sobre dados Enlace) |
| **Tabela destino** | `pulso_scores` |
| **Frequencia** | On-demand |
| **Conteudo** | Score de saude do provedor (crescimento, qualidade, cobertura, financeiro) |
| **Registros** | 13.534 |

### 37. peeringdb

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `PeeringDBPipeline` |
| **Fonte** | PeeringDB (API REST) |
| **Tabelas destino** | `peering_networks`, `peering_ixps` |
| **Frequencia** | On-demand |
| **Conteudo** | Redes de peering, politicas e participacao em IXPs |
| **Registros** | 34.000+ redes |

### 38. ixbr

| Aspecto | Detalhe |
|---------|---------|
| **Classe** | `IXBRPipeline` |
| **Fonte** | IX.br (NIC.br) |
| **Tabelas destino** | `ixp_locations`, `ixp_traffic_history` |
| **Frequencia** | On-demand |
| **Conteudo** | Pontos de troca de trafego no Brasil, historico de trafego |
| **Registros** | 37+ IXPs |

---

## Resumo de Registros

| Pipeline | Tabela Destino | Registros |
|----------|---------------|-----------|
| anatel_providers | providers | 13.534 |
| anatel_broadband | broadband_subscribers | 4.137.609 |
| anatel_base_stations | base_stations | 37.727 |
| anatel_quality | quality_indicators | 33.420 |
| ibge_census | ibge_population / admin_level_2 | 5.570 / 5.572 |
| osm_roads | road_segments | 6.457.585 |
| aneel_power | power_lines | 16.559 |
| inmet_weather | weather_stations / weather_observations | 671 / 61.061 |
| srtm_terrain | srtm_tiles (disco) | 1.681 |
| opportunity_scores | opportunity_scores | 5.570 |
| competitive_analysis | competitive_analysis | ~5.570 |
| sentinel_growth | sentinel_urban_indices | 87+ |
| spectrum_licenses | spectrum_licenses | 47 |
| ms_buildings | building_footprints | Variavel |
| opencellid | opencellid_towers | Variavel |
| ookla_speedtest | speedtest_tiles / speedtest_municipality | 200K+ |
| h3_grid | h3_cells | 100K+ |
| pulso_score | pulso_scores | 13.534 |
| peeringdb | peering_networks / peering_ixps | 34.000+ |
| ixbr | ixp_locations / ixp_traffic_history | 37+ |
| **Total** | | **~28M+** |
