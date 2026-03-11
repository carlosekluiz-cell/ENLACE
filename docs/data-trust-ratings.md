# Classificacao de Confianca dos Dados — Enlace / Pulso Network

**Sistema de classificacao de proveniencia e confiabilidade das fontes de dados**

Versao 1.0 | Marco 2026

---

## Sistema de Classificacao

A plataforma Enlace classifica cada fonte de dados em quatro niveis de confianca, baseados na origem, metodologia de coleta e rastreabilidade:

| Nivel | Classificacao | Descricao | Criterios |
|-------|--------------|-----------|-----------|
| **A1** | Alta (Governamental) | Dados oficiais do governo brasileiro | Fonte governamental, metodologia publica, atualizacao regular, auditavel |
| **A2** | Alta (Cientifica) | Dados cientificos com metodologia peer-reviewed | Instituicao cientifica, resolucao conhecida, reproducivel |
| **A3** | Alta (Aberta) | Dados abertos colaborativos com validacao comunitaria | Comunidade ativa, validacao cruzada, licenca aberta |
| **B1** | Media (Computada) | Dados derivados por algoritmos proprietarios | Formula documentada, inputs de nivel A, atualizacao automatica |

---

## Fontes de Nivel A1 — Alta (Governamental)

### Anatel — Agencia Nacional de Telecomunicacoes

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Provedores SCM/SVA | `providers` | 13.534 | A1 | Cadastro obrigatorio na Anatel. CNPJs verificados. Atualizacao diaria via CKAN/dados.gov.br |
| Assinantes banda larga fixa | `broadband_subscribers` | 4.137.609 | A1 | Declaracao compulsoria mensal dos provedores (SICI). Dados por municipio, tecnologia, provedor. Atraso de ~45 dias |
| Qualidade IQS/RQual | `quality_indicators` | 33.420 | A1 | Medicoes realizadas pela propria Anatel via SFF. Metodologia publicada na Resolucao 717/2019 |
| Selos de qualidade | `quality_seals` | Variavel | A1 | Avaliacao semestral da Anatel baseada em medicoes automatizadas. Escala 0-100 |
| Licencas de espectro | `spectrum_licenses` | 47 | A1 | Registros oficiais de leiloes de frequencia conduzidos pela Anatel |
| Backhaul | `backhaul_presence` | Variavel | A1 | Dados de infraestrutura de backbone reportados pelos provedores a Anatel |
| Atos regulatorios (DOU) | `regulatory_acts` | Variavel | A1 | Publicacoes oficiais no Diario Oficial da Uniao — fonte primaria |

**Limitacoes conhecidas**:
- Assinantes: Provedores menores podem sub-reportar. Dados nao incluem assinantes de operadores moveis.
- Qualidade: Medicoes limitadas a provedores com mais de 50K assinantes em algumas metricas.

### IBGE — Instituto Brasileiro de Geografia e Estatistica

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Municipios (geometrias) | `admin_level_2` | 5.572 | A1 | Malha municipal oficial do Brasil. SRID 4326. Atualizada a cada Censo |
| Populacao estimada | `ibge_population` | 5.570 | A1 | Estimativas anuais por municipio (Diretoria de Pesquisas/IBGE). Metodologia AiBi |
| PIB municipal | `municipal_gdp` | Variavel | A1 | Contas Regionais do Brasil. Base IBGE/SIDRA |
| Projecoes populacionais | `population_projections` | Variavel | A1 | Projecao por componentes demograficas. Publicado pelo IBGE |
| POF (gastos familiares) | `household_expenditure` | Variavel | A1 | Pesquisa de Orcamentos Familiares. Amostra nacional com expansao |
| MUNIC (planejamento) | `municipal_planning` | Variavel | A1 | Pesquisa de Informacoes Basicas Municipais — questionario a prefeituras |
| CNEFE (enderecos) | `building_density` | Variavel | A1 | Cadastro Nacional de Enderecos para Fins Estatisticos. Base censitaria |

**Limitacoes conhecidas**:
- Censo: Ultimo completo em 2022. Estimativas intercensitarias podem divergir de contagens reais em municipios pequenos.
- MUNIC: Dependente de auto-declaracao das prefeituras. Frequencia variavel.

### INMET — Instituto Nacional de Meteorologia

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Estacoes meteorologicas | `weather_stations` | 671 | A1 | Rede oficial de estacoes automaticas e convencionais do INMET |
| Observacoes meteorologicas | `weather_observations` | 61.061 | A1* | Dados obtidos via Open-Meteo (API INMET retorna 403). Dados originais do INMET, servidos por intermediario |

**Nota**: A classificacao das observacoes e A1* porque, embora os dados originais sejam do INMET, a obtencao e via Open-Meteo (intermediario). A integridade dos dados e verificada por limites fisicos (temperatura -50 a +60C, vento 0-100 m/s, etc.).

### DATASUS/CNES — Ministerio da Saude

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Estabelecimentos de saude | `health_facilities` | Variavel | A1 | Cadastro Nacional de Estabelecimentos de Saude. Registro obrigatorio para estabelecimentos SUS |

**Limitacoes conhecidas**: Campo `has_internet` pode nao estar atualizado para todos os estabelecimentos.

### INEP — Instituto Nacional de Estudos e Pesquisas Educacionais

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Escolas (Censo Escolar) | `schools` | Variavel | A1 | Censo Escolar anual. Participacao obrigatoria de todas as escolas publicas e privadas |

### PNCP — Portal Nacional de Contratacoes Publicas

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Contratos governamentais | `government_contracts` | Variavel | A1 | Registro obrigatorio de contratacoes publicas (Lei 14.133/2021). Filtro local por keywords telecom |

**Limitacoes conhecidas**: Filtro por keywords pode excluir contratos relevantes com descricoes atipicas, ou incluir falsos positivos. Mitigacao: regex local autoritativo apos busca no servidor.

### Portal da Transparencia / BNDES

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Gastos FUST/FUNTTEL | `fust_spending` | Variavel | A1 | Dados de execucao orcamentaria do Governo Federal |
| Emprestimos BNDES | `bndes_loans` | Variavel | A1 | Portal de Transparencia do BNDES. Dados de contratos e desembolsos |

### CAGED — Ministerio do Trabalho

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Indicadores de emprego | `employment_indicators` | Variavel | A1 | Cadastro Geral de Empregados e Desempregados. Registro obrigatorio |

### SNIS — Ministerio das Cidades

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Indicadores de saneamento | `sanitation_indicators` | Variavel | A1 | Sistema Nacional de Informacoes sobre Saneamento. Auto-declaracao dos prestadores |

### ANP — Agencia Nacional do Petroleo

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Precos de combustivel | `fuel_prices` | Variavel | A1 | Levantamento de Precos semanal da ANP. Amostragem em postos |

### IPEA/FBSP — Atlas da Violencia

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Indicadores de seguranca | `safety_indicators` | Variavel | A1 | Atlas da Violencia (IPEA + Forum Brasileiro de Seguranca Publica). Base: registros de obito do SIM/DATASUS |

### Querido Diario — Open Knowledge Brasil

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Gazetas municipais | `gazette_mentions` | Variavel | A1 | Diarios oficiais municipais coletados e indexados pelo projeto Querido Diario (OKBr) |

---

## Fontes de Nivel A2 — Alta (Cientifica)

### SRTM — NASA/USGS

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Terreno 30m | `srtm_tiles` + disco | 1.681 tiles / 40.6 GB | A2 | Shuttle Radar Topography Mission (NASA, 2000). Resolucao 30m (1 arc-second). Validado por altimetria |

**Metodologia de validacao**: Elevacoes verificadas contra pontos conhecidos — Manaus 36-86m, Curitiba 905-945m, Salvador 9-71m, Sao Paulo 726-852m.

**Limitacoes conhecidas**: Dados de 2000. Mudancas topograficas significativas (mineracao, aterros) nao estao refletidas. Precisao vertical: +/-16m (especificacao), tipicamente +/-6m.

### Sentinel-2 — ESA/Copernicus

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Indices urbanos | `sentinel_urban_indices` | 87+ | A2 | Sentinel-2 MSI via Google Earth Engine. Resolucao 10m. Compositos anuais (2016-2026) |
| Compositos | `sentinel_composites` | Variavel | A2 | Cloud-Optimized GeoTIFF. Mediana anual com mascara de nuvens |

**Metodologia de indices**:
- NDVI (Normalized Difference Vegetation Index): (B8 - B4) / (B8 + B4)
- NDBI (Normalized Difference Built-up Index): (B11 - B8) / (B11 + B8)
- MNDWI (Modified Normalized Difference Water Index): (B3 - B11) / (B3 + B11)
- BSI (Bare Soil Index): ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))

**Limitacoes conhecidas**: Cobertura de nuvens reduz qualidade em regioes com alta nebulosidade (Norte do Brasil). Threshold de nuvens: 20%.

### MapBiomas

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Cobertura do solo | `land_cover` | Variavel | A2 | Classificacao supervisionada por Random Forest sobre Landsat. Acuracia geral > 85%. Projeto colaborativo multi-institucional |

---

## Fontes de Nivel A3 — Alta (Aberta)

### OpenStreetMap (OSM)

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Segmentos rodoviarios | `road_segments` | 6.457.585 | A3 | Geofabrik extracts de todas as 5 regioes do Brasil. Validacao cruzada com dados oficiais DNIT |
| Torres de telecomunicacao | `base_stations` (posicao) | 37.727 | A3 | Overpass API com query `man_made=mast/tower + communication=*`. Validacao por coordenadas |
| Linhas de energia | `power_lines` | 16.559 | A3 | Overpass API com query `power=line`. Validacao por voltagem e geometria |

**Limitacoes conhecidas**: OSM depende de contribuicoes voluntarias. Areas rurais remotas podem ter cobertura incompleta. Mitigacao: complemento com dados Geofabrik (extracts completos).

### Open-Meteo

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Observacoes meteorologicas | `weather_observations` | 61.061 | A3 | Agregador de dados meteorologicos de fontes oficiais (INMET, NOAA, DWD). API aberta sem autenticacao |

---

## Fontes de Nivel B1 — Media (Computada)

### Algoritmos Proprietarios da Plataforma

| Dataset | Tabela | Registros | Confianca | Metodologia |
|---------|--------|-----------|-----------|-------------|
| Scores de oportunidade | `opportunity_scores` | 5.570 | B1 | Formula proprietaria: demand (25%) + competition (20%) + infrastructure (20%) + growth (15%) + social (20%). 8 fatores de enriquecimento. Inputs: A1 (Anatel, IBGE, INEP, CNES, CAGED, Atlas Violencia, CNEFE, MUNIC) |
| Analise competitiva | `competitive_analysis` | ~5.570 | B1 | HHI computado a partir de market shares reais (broadband_subscribers). Thresholds padrao (DOJ/FTC): > 2500 = alta concentracao |
| Atribuicao de operadora | `base_stations` (provider_id) | 37.727 | B1 | Atribuicao probabilistica baseada em market share municipal. Inputs: A1 (Anatel broadband) + A3 (OSM positions) |
| Indicadores de qualidade | `quality_indicators` | 33.420 | B1 | Derivados de dados A1 (Anatel SFF) com normalizacao e agregacao proprietaria |

**Metodologia de scoring de oportunidade**:

```
composite = demand * 0.25 + competition * 0.20 + infrastructure * 0.20
          + growth * 0.15 + social * 0.20

Fatores de enriquecimento:
  - Backhaul ausente: infrastructure += 30
  - Escolas sem internet: demand += (offline_pct * 0.2), social += (offline_pct * 0.3)
  - Saude sem internet: social += (offline_pct * 0.2)
  - Emprego positivo: growth += 20
  - Qualidade incumbente baixa: competition += 15
  - Area segura: social += (100 - risk) * 0.2
  - Densidade alta + demanda alta: demand += 15
  - Plano diretor + codigo obras: infrastructure += 10
  - Contratos gov. recentes: growth += 10
```

**Limitacoes conhecidas**: Scores sao tao bons quanto os dados de entrada. Municipios com dados incompletos em alguma dimensao recebem valores default (50.0), o que pode sub- ou super-estimar a oportunidade.

---

## Resumo da Classificacao por Tabela

| Tabela | Nivel | Fonte Primaria |
|--------|-------|----------------|
| providers | A1 | Anatel |
| broadband_subscribers | A1 | Anatel |
| quality_indicators | B1 | Anatel (derivado) |
| quality_seals | A1 | Anatel RQual |
| spectrum_licenses | A1 | Anatel |
| base_stations (posicao) | A3 | OSM |
| base_stations (operadora) | B1 | Proprietario |
| admin_level_1 | A1 | IBGE |
| admin_level_2 | A1 | IBGE |
| ibge_population | A1 | IBGE |
| road_segments | A3 | OSM/Geofabrik |
| power_lines | A3 | OSM |
| srtm_tiles | A2 | NASA/USGS |
| weather_stations | A1 | INMET |
| weather_observations | A1* | INMET via Open-Meteo |
| sentinel_urban_indices | A2 | ESA/Sentinel-2 |
| opportunity_scores | B1 | Proprietario |
| competitive_analysis | B1 | Proprietario |
| government_contracts | A1 | PNCP |
| health_facilities | A1 | DATASUS/CNES |
| schools | A1 | INEP |
| bndes_loans | A1 | BNDES |
| fust_spending | A1 | Transparencia |
| employment_indicators | A1 | CAGED |
| safety_indicators | A1 | IPEA/FBSP |
| municipal_planning | A1 | IBGE MUNIC |
| building_density | A1 | IBGE CNEFE |
| land_cover | A2 | MapBiomas |
| fuel_prices | A1 | ANP |
| sanitation_indicators | A1 | SNIS |

---

## Processo de Validacao

Cada pipeline executa as seguintes validacoes automaticas:

1. **Contagem de registros**: Compara com a ultima ingestao. Alertas se variacao > 20%.
2. **Integridade referencial**: Foreign keys verificadas (l2_id, provider_id).
3. **Limites fisicos**: Coordenadas dentro do Brasil (-34 a +5 lat, -74 a -35 lon). Temperaturas -50 a +60C. Scores 0-100.
4. **Duplicatas**: Deteccao e tratamento de registros duplicados via UPSERT (ON CONFLICT DO UPDATE).
5. **Freshness**: Alertas se a fonte nao atualizar dentro do prazo esperado (diario, semanal, mensal).
