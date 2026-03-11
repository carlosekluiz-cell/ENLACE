# Enlace / Pulso Network — Whitepaper

**Plataforma de Inteligencia Decisional para Telecomunicacoes no Brasil**

Versao 2.0 | Marco 2026

---

## Sumario Executivo

O Brasil abriga o quinto maior mercado de telecomunicacoes do mundo, com mais de 13.500 provedores de internet (ISPs) atendendo 5.572 municipios em um territorio continental de 8,5 milhoes de km2. Apesar de movimentar mais de R$250 bilhoes por ano em receitas de telecom, a grande maioria desses provedores opera com dados fragmentados, ferramentas manuais e decisoes baseadas em intuicao.

A plataforma Enlace/Pulso Network resolve esse problema com uma solucao integrada de inteligencia de mercado, planejamento de rede RF, conformidade regulatoria, avaliacao de M&A e monitoramento satelital. A plataforma consolida 28 milhoes de registros de 19+ fontes governamentais e cientificas, processados por 38 pipelines automatizados, com um motor de propagacao RF escrito em Rust de alto desempenho e analise de crescimento urbano via Sentinel-2.

Nenhum concorrente no mercado brasileiro oferece a combinacao de Inteligencia de Mercado + Projeto RF + Conformidade Regulatoria + M&A + Satelite em uma unica plataforma. Com 5 ondas de desenvolvimento, a plataforma expandiu de 9 modulos originais para 28 features completas, incluindo analise espacial avancada, inteligencia Starlink, scoring de provedores, peering/IX.br e analise cruzada multi-dimensional. O custo de reproducao independente da plataforma foi avaliado em R$16,4 milhoes (306 person-months de desenvolvimento).

---

## Oportunidade de Mercado

### O Mercado Brasileiro de Telecomunicacoes

| Indicador | Valor |
|-----------|-------|
| Receita anual do setor de telecom | ~R$250 bilhoes |
| ISPs registrados na Anatel | 13.534 |
| Municipios brasileiros | 5.572 |
| Assinantes de banda larga fixa (na base Enlace) | 4.137.609 registros (37 meses) |
| Torres de estacoes base mapeadas | 37.727 |
| Segmentos de rodovias (grafo rodoviario) | 6.457.585 (3,73M km) |

### Dor do Mercado

Os ISPs brasileiros enfrentam desafios criticos:

1. **Expansao as cegas**: Decisoes de CAPEX de R$1-5M baseadas em dados incompletos ou desatualizados. Um investimento mal direcionado pode comprometer a saude financeira de um ISP regional por anos.

2. **Complexidade regulatoria**: A transicao SVA-para-SCM (Norma no. 4), exigencias de qualidade RQual/IQS da Anatel, e prazos de licenciamento criam risco de multas de R$50K-500K para ISPs nao preparados.

3. **Consolidacao acelerada**: O mercado brasileiro de ISPs esta em plena onda de M&A, com provedores maiores adquirindo regionais. Tanto compradores quanto vendedores operam sem ferramentas adequadas de avaliacao.

4. **Conectividade rural**: 25+ milhoes de brasileiros em areas rurais ainda nao tem acesso adequado a internet, representando uma oportunidade massiva — mas que exige planejamento tecnico especializado (terreno, energia solar, travessias de rios).

5. **Fragmentacao de dados**: Dados da Anatel, IBGE, INMET, CNES, INEP, PNCP, BNDES e dezenas de outras fontes existem em silos, formatos incompativeis e com atualizacoes irregulares.

---

## Fosso Tecnologico (Technical Moat)

### Motor RF em Rust (9.000+ LOC)

O componente mais sofisticado da plataforma e o motor de propagacao RF, escrito inteiramente em Rust com comunicacao gRPC+TLS:

- **6 modelos de propagacao ITU-R**: FSPL, Hata, P.530, P.1812, ITM, TR38.901
- **Modelagem atmosferica**: P.676 (absorcao gasosa) + P.838 (atenuacao por chuva)
- **Difracao e vegetacao**: Perda por obstrucao topografica e cobertura vegetal
- **Terreno real SRTM 30m**: 1.681 tiles cobrindo todo o Brasil (40,6 GB)
- **Otimizacao de torres**: Simulated annealing com estimativa de CAPEX
- **Rota de fibra**: Dijkstra sobre 6,4M de segmentos rodoviarios com BOM

Crates Rust:
| Crate | LOC | Funcao |
|-------|-----|--------|
| enlace-propagation | 3.511 | Modelos de propagacao RF |
| enlace-optimizer | 1.786 | Otimizacao de cobertura |
| enlace-terrain | 981 | Processamento de terreno SRTM |
| enlace-raster | 779 | Geracao de rasters de cobertura |
| enlace-service | 600+ | Servico gRPC+TLS |
| enlace-tiles | 347 | Gerador de tiles XYZ |

### Inteligencia Satelital (Sentinel-2)

Pipeline de sensoriamento remoto com Google Earth Engine:
- 4 indices espectrais: NDVI, NDBI, MNDWI, BSI
- Deteccao de crescimento urbano ano-a-ano (2016-2026)
- Compositos Cloud-Optimized GeoTIFF por municipio
- Correlacao com projecoes populacionais do IBGE

### 38 Pipelines de Dados

| Frequencia | Pipelines | Exemplos |
|------------|-----------|----------|
| Diario | 7 | Anatel telecom, INMET clima, PNCP contratos, DOU regulatorio, Querido Diario |
| Semanal | 7 | IBGE economico, ANP combustiveis, ANEEL energia, BNDES emprestimos, CNPJ enriquecimento |
| Mensal | 12 | IBGE censo, SRTM terreno, MapBiomas, OSM rodovias, DATASUS saude, INEP escolas |
| On-demand | 7 | MS Buildings, OpenCelliD, Ookla Speedtest, H3 Grid, Pulso Score, PeeringDB, IX.br |
| Computados | 5 | Opportunity scores, quality indicators, competitive analysis, market summary refresh |

### Base de Dados Real

28+ milhoes de registros de producao, incluindo:
- 4.137.609 registros de assinantes de banda larga (37 meses)
- 6.457.585 segmentos rodoviarios (todas as 5 regioes)
- 37.727 estacoes base com atribuicao de operadora
- 13.534 provedores ISP
- 33.420 indicadores de qualidade computados
- 5.570 scores de oportunidade por municipio
- 34.000+ redes de peering (PeeringDB)
- 13.534 provedores com Pulso Score
- 200K+ tiles de speedtest (Ookla)
- 100K+ celulas H3 com analise
- 47+ holdings de espectro

---

## Proveniencia e Confianca dos Dados

Toda fonte de dados e classificada por confiabilidade:

| Classificacao | Tipo | Fontes |
|---------------|------|--------|
| **Alta (Governamental)** | Dados oficiais do governo federal | Anatel, IBGE, INMET, DATASUS/CNES, INEP, PNCP, Portal da Transparencia |
| **Alta (Cientifica)** | Dados cientificos com metodologia publica | SRTM/NASA, Sentinel-2/ESA, MapBiomas |
| **Alta (Aberta)** | Dados colaborativos com validacao | OpenStreetMap (OSM), Open-Meteo |
| **Media (Computada)** | Derivados por algoritmos proprietarios | Opportunity scores, quality indicators, competitive analysis, base station attribution |

Cada pipeline inclui validacao automatica de integridade, contagem de registros e deteccao de anomalias.

---

## Analise Competitiva

| Capacidade | Enlace/Pulso | Teleco.com.br | Anatel SFF | McKinsey Telecom | Ookla/Speedtest |
|------------|:---:|:---:|:---:|:---:|:---:|
| Inteligencia de mercado por municipio | X | Parcial | Parcial | Sob demanda | - |
| Projeto RF com terreno real | X | - | - | - | - |
| Conformidade regulatoria (Norma 4) | X | Parcial | - | Sob demanda | - |
| Avaliacao M&A de ISPs | X | - | - | Sob demanda | - |
| Inteligencia satelital | X | - | - | - | - |
| Planejamento rural (solar, rio) | X | - | - | - | - |
| Roteamento de fibra (6,4M segmentos) | X | - | - | - | - |
| Base de dados integrada (28M+) | X | - | - | - | - |
| Pipelines automatizados (38) | X | - | - | - | - |
| Motor Rust de alto desempenho | X | - | - | - | - |
| Analise espacial e clustering | X | - | - | - | - |
| Inteligencia anti-Starlink | X | - | - | - | - |
| Scoring de provedor (Pulso Score) | X | - | - | - | - |
| Peering / IX.br intelligence | X | - | - | - | - |

**Nenhum concorrente cobre simultaneamente RF + Mercado + Regulatorio + M&A + Satelite.**

A McKinsey e a Deloitte oferecem relatorios sob demanda a custos de R$500K-2M por projeto. Teleco.com.br fornece estatisticas agregadas sem granularidade municipal. O SFF da Anatel e limitado a consultas basicas de dados publicos.

---

## Resumo da Avaliacao de PI

A avaliacao independente (metodologia COCOMO II, padrao IVS 210) resultou em:

| Metrica | Valor |
|---------|-------|
| Linhas de codigo (total) | 86.627 |
| Arquivos | 340+ |
| Esforco de desenvolvimento | 306 person-months |
| Tamanho da equipe estimada | 14 profissionais |
| Prazo de reproducao | 22-28 meses |
| **Custo de reproducao (Cost Approach)** | **R$16.400.000** |
| **Valor justo (Fair Value)** | **R$16,4M** |

Componentes do custo:
- Mao de obra: R$8.996.400 (306 PM x R$29.400/mes medio ponderado)
- Infraestrutura: R$680.000
- Aquisicao de dados: R$520.000
- Expertise de dominio: R$780.000
- Overhead e contingencia: R$5.423.600

---

## Estrategia Go-to-Market

### Modelo de Precificacao por Tiers

| Tier | Preco | Publico-Alvo | Modulos |
|------|-------|-------------|---------|
| **Gratuito** | R$0/mes | ISPs exploradores, avaliacao | Market Intelligence (basico), mapa de oportunidades (somente leitura) |
| **Provedor** | R$1.500/mes | ISPs pequenos/medios (1K-10K assinantes) | Market, Expansion, Competition, Compliance, Network Health |
| **Profissional** | R$5.000/mes | ISPs medios/grandes (10K-100K assinantes) | Tudo do Provedor + RF Design, Rural, M&A, Satellite, API access |
| **Empresa** | Sob consulta | Operadoras, fundos de investimento, consultorias | Tudo + API ilimitada, white-label, integracao customizada, SLA dedicado |

### Estrategia de Adocao

1. **Fase 1 — Adocao** (Meses 1-6): Tier gratuito para gerar base de usuarios entre os 13.534 ISPs. Meta: 500 cadastros.
2. **Fase 2 — Conversao** (Meses 6-12): Conversao para tiers pagos atraves de demonstracao de valor (primeiro relatorio de oportunidade gratuito). Meta: 50 assinantes Provedor, 10 Profissional.
3. **Fase 3 — Escala** (Meses 12-24): Expansao para consultorias de telecom, fundos de investimento (tier Empresa), e parcerias com associacoes setoriais (Abrint, TelComp).

### Receita Projetada (Cenario Base)

| Metrica | Ano 1 | Ano 2 | Ano 3 |
|---------|-------|-------|-------|
| Assinantes Provedor | 50 | 150 | 400 |
| Assinantes Profissional | 10 | 40 | 100 |
| Contratos Empresa | 2 | 5 | 10 |
| **ARR (Receita Anual Recorrente)** | **R$1,8M** | **R$6,6M** | **R$16,8M** |

### Mercado Enderecavel

Com 13.534 ISPs no Brasil, e um TAM de R$5.000/mes medio, o mercado enderecavel total e de aproximadamente R$810M/ano. Mesmo com 1% de penetracao no Ano 3, a plataforma geraria R$8,1M ARR.

---

## Conclusao

A plataforma Enlace/Pulso Network representa uma oportunidade unica no mercado brasileiro de telecomunicacoes:

1. **Unicidade**: Nenhuma solucao existente integra inteligencia de mercado, projeto RF, conformidade, M&A e satelite.
2. **Base de dados robusta**: 28M+ registros reais de producao, atualizados por 38 pipelines automatizados.
3. **Tecnologia proprietaria**: Motor RF em Rust com 9.000+ LOC, validado contra terreno real SRTM de todo o Brasil.
4. **Mercado massivo**: 13.534 ISPs operando em um mercado de R$250B+/ano, em plena onda de consolidacao.
5. **Barreira de entrada**: R$16,4M e 22-28 meses para reproduzir, segundo avaliacao independente.

A plataforma esta pronta para producao, com backend, frontend, motor RF e pipelines totalmente funcionais. O proximo passo e a aquisicao de clientes.

---

*Enlace Platform | pulso.network | Marco 2026*
