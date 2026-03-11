# Calculadora de ROI — Enlace / Pulso Network

**Retorno sobre Investimento para Provedores de Internet Brasileiros**

Versao 1.0 | Marco 2026

---

## Metodologia

Cada caso de uso abaixo compara o custo da assinatura Enlace com o valor economico gerado (ou a perda evitada). O ROI e calculado como:

```
ROI = (Valor Gerado ou Perda Evitada) / (Custo Anual da Assinatura)
```

Os cenarios utilizam dados reais da plataforma (13.534 provedores, 5.572 municipios, 4,1M registros de assinantes) e premissas conservadoras baseadas no mercado brasileiro de ISPs.

---

## Caso 1: Expansao de ISP de Medio Porte

**Cenario**: Um ISP com 8.000 assinantes no interior de Sao Paulo planeja investir R$2.000.000 em expansao de fibra para um novo municipio.

### Sem Enlace (Decisao Tradicional)

| Etapa | Metodo | Custo/Risco |
|-------|--------|-------------|
| Pesquisa de mercado | Planilhas manuais, dados desatualizados da Anatel | 40h de trabalho (~R$8.000) |
| Analise competitiva | Ligacoes para conhecidos no mercado | Incompleta, 2-3 concorrentes identificados |
| Projeto de rede | Estimativa "de cabeca" baseada em Google Maps | Sem terreno real, sem BOM |
| Viabilidade financeira | Planilha Excel com premissas otimistas | Vies de confirmacao |
| **Risco**: Escolher municipio com HHI < 1500 (mercado ja saturado) | | **R$2.000.000 em CAPEX comprometido** |

### Com Enlace (Tier Provedor — R$1.500/mes)

| Etapa | Funcionalidade Enlace | Resultado |
|-------|----------------------|-----------|
| Identificar oportunidades | Ranking de 5.570 municipios por composite score | Top 50 municipios com score > 75 |
| Validar mercado | Market summary + competitors (HHI, shares, tendencia) | Confirmar HHI > 2500 = mercado concentrado = oportunidade |
| Projetar rota de fibra | Dijkstra sobre 6,4M segmentos + BOM | Rota otimizada de 23 km, R$1,8M com co-locacao de poste |
| Analise financeira | NPV, IRR, payback com 3 cenarios | IRR base = 28%, payback = 2,8 anos |
| **Resultado**: Evitar municipio saturado, escolher municipio adjacente com 40% menos concorrencia | | **R$2M de CAPEX protegido** |

### Calculo de ROI

| Metrica | Valor |
|---------|-------|
| Custo anual da assinatura (Provedor) | R$18.000 (12 x R$1.500) |
| Valor da perda evitada (CAPEX em municipio errado) | R$2.000.000 |
| **Multiplo de retorno** | **111x** |
| ROI conservador (evitar 10% do CAPEX mal alocado) | R$200.000 / R$18.000 = **11x** |
| ROI ultra-conservador (evitar 3% do CAPEX) | R$60.000 / R$18.000 = **3,3x** |

> **Conclusao**: Mesmo no cenario mais conservador (3% do CAPEX protegido), o ROI e de 3,3x. Em um cenario realista onde o ISP evita um investimento de R$2M em municipio saturado, o retorno e de 111x o custo anual da assinatura.

### Economia de Tempo

| Atividade | Sem Enlace | Com Enlace | Economia |
|-----------|-----------|-----------|----------|
| Pesquisa de mercado | 40h | 2h | 38h |
| Analise competitiva | 16h | 0,5h | 15,5h |
| Projeto de rede (rota) | 24h | 1h | 23h |
| Viabilidade financeira | 16h | 0,5h | 15,5h |
| **Total** | **96h** | **4h** | **92h (96% reducao)** |

---

## Caso 2: Conformidade Regulatoria

**Cenario**: Um ISP com 4.800 assinantes que esta proximo ao threshold de 5.000 da Anatel para exigencia de autorizacao SCM formal. Opera em 3 estados (SP, MG, PR) com receita mensal de R$480.000.

### Sem Enlace (Risco Regulatorio)

| Risco | Probabilidade | Impacto |
|-------|--------------|---------|
| Multa por operar sem autorizacao (acima de 5.000 subs) | Alta (crescimento natural) | R$50.000 - R$100.000 |
| Impacto ICMS nao planejado (Norma no. 4, transicao SVA->SCM) | Certo ao cruzar threshold | R$57.600/ano adicional (12% ICMS medio sobre R$480K) |
| Multa por nao cumprimento de RQual/IQS | Media | R$20.000 - R$50.000 |
| Perda de deadline regulatorio | Media | R$30.000 + custos advocaticios |
| **Exposicao total anual** | | **R$100.000 - R$260.000** |

### Com Enlace (Tier Provedor — R$1.500/mes)

| Funcionalidade | Acao Preventiva | Valor |
|---------------|----------------|-------|
| Licensing check (threshold 5K) | Alerta 6 meses antes de cruzar, tempo para obter autorizacao | Evita multa de R$50K-100K |
| Norma no. 4 multi-estado | Calcula ICMS blended para SP+MG+PR, sugere reestruturacao | Economia de R$12K/ano com otimizacao de estrutura |
| Quality check vs. thresholds | Identifica metricas abaixo do minimo antes da auditoria | Evita multa de R$20K-50K |
| Calendario de deadlines | Alerta de prazos com urgencia categorizada | Evita perda de prazo e custos advocaticios |
| Dashboard de compliance | Score geral + action items priorizados | Reducao de 80% no tempo de preparacao |

### Calculo de ROI

| Metrica | Valor |
|---------|-------|
| Custo anual da assinatura (Provedor) | R$18.000 |
| Multa evitada (cenario base: uma multa media) | R$100.000 |
| **Multiplo de retorno** | **5,5x** |
| Economia adicional (otimizacao ICMS) | R$12.000/ano |
| Economia de tempo (compliance manual vs. automatico) | 120h/ano = ~R$24.000 |
| **ROI total (multa + ICMS + tempo)** | R$136.000 / R$18.000 = **7,5x** |

> **Conclusao**: Evitar uma unica multa regulatoria ja paga 5,5x a assinatura anual. Com a economia de ICMS e tempo, o ROI sobe para 7,5x.

### Detalhamento do Impacto Norma no. 4

| Estado | Receita Mensal | ICMS SCM | Impacto Mensal | Impacto Anual |
|--------|---------------|----------|---------------|---------------|
| SP (18%) | R$200.000 | 18% | R$36.000 | R$432.000 |
| MG (18%) | R$180.000 | 18% | R$32.400 | R$388.800 |
| PR (18%) | R$100.000 | 18% | R$18.000 | R$216.000 |
| **Total** | **R$480.000** | | **R$86.400** | **R$1.036.800** |

Com a funcionalidade de multi-state impact, o Enlace sugere opcoes de reestruturacao (cisao, holding, consorcio) que podem reduzir o impacto total em 10-15%.

---

## Caso 3: Avaliacao de Targets para M&A

**Cenario**: Um ISP grande (50.000 assinantes, SP) busca adquirir ISPs regionais para expandir footprint. Quer avaliar targets em SP, MG e PR com 1.000-50.000 assinantes.

### Sem Enlace (Due Diligence Tradicional)

| Atividade | Custo | Tempo |
|-----------|-------|-------|
| Contratacao de consultoria para 1 target | R$80.000 - R$150.000 | 30-60 dias |
| Levantamento de dados de mercado (por target) | R$15.000 | 10 dias |
| Avaliacao financeira (por target) | R$25.000 | 15 dias |
| Due diligence tecnica (por target) | R$30.000 | 15 dias |
| **Total para 1 target** | **R$150.000 - R$220.000** | **2-3 meses** |
| **Para avaliar 10 targets** | **R$1.500.000 - R$2.200.000** | **6-12 meses** |

### Com Enlace (Tier Profissional — R$5.000/mes)

| Funcionalidade | Resultado | Tempo |
|---------------|-----------|-------|
| Target discovery (POST /mna/targets) | Lista de 50+ targets rankeados por overall_score | 30 segundos |
| 3 metodos de valuation por target | Subscriber multiple + revenue multiple + DCF | 5 segundos/target |
| Enriquecimento CNPJ (capital social, socio, CNAE) | Dados da Receita Federal em tempo real | Automatico |
| Contratos governamentais ganhos | Match CNPJ vs. PNCP | Automatico |
| Emprestimos BNDES | Historico de financiamento por provedor | Automatico |
| Selos de qualidade RQual | Score de qualidade por provedor | Automatico |
| Market overview por estado | Total ISPs, subscribers, fiber_pct, top providers | 2 segundos |
| **Total para 10 targets** | **Avaliacao completa de 10 targets** | **1 hora** |

### Calculo de ROI

| Metrica | Valor |
|---------|-------|
| Custo anual da assinatura (Profissional) | R$60.000 (12 x R$5.000) |
| Custo de due diligence manual para 10 targets | R$1.500.000 |
| Custo equivalente com Enlace (1 hora de analista) | ~R$500 + R$60.000 assinatura |
| **Economia direta** | **R$1.439.500** |
| **Multiplo de retorno** | **24x** |

> **Conclusao**: Com o custo de 1 due diligence manual tradicional (R$150K-220K), o Enlace permite avaliar mais de 10 targets automaticamente. O ROI e de 24x quando comparado com a alternativa de consultoria.

### Valor Adicional: Qualidade da Decisao

| Aspecto | Due Diligence Manual | Enlace |
|---------|---------------------|--------|
| Targets avaliados | 1-3 (limitado por orcamento) | 50+ (automatico) |
| Dados de mercado | Snapshot pontual | Atualizados mensalmente |
| Cobertura geografica | Estado unico | Nacional (27 UFs) |
| Avaliacao financeira | 1 metodo | 3 metodos (subscriber, revenue, DCF) |
| Enriquecimento CNPJ | Manual, 5 dias | Automatico, tempo real |
| Contratos governamentais | Nao incluido | Integrado (PNCP) |
| Financiamento BNDES | Nao incluido | Integrado |
| **Risco de perder o melhor target** | **Alto** | **Minimo** |

---

## Resumo Comparativo dos 3 Casos

| Caso de Uso | Tier | Custo Anual | Valor Gerado/Protegido | ROI |
|-------------|------|------------|----------------------|-----|
| Expansao (evitar CAPEX ruim) | Provedor | R$18.000 | R$60K - R$2M | 3,3x - 111x |
| Conformidade regulatoria | Provedor | R$18.000 | R$100K - R$136K | 5,5x - 7,5x |
| M&A target evaluation | Profissional | R$60.000 | R$1.440K | 24x |

### Payback Period

| Tier | Custo Mensal | Payback (cenario conservador) |
|------|-------------|-------------------------------|
| Provedor | R$1.500 | < 1 mes (evitando 1 erro de R$60K) |
| Profissional | R$5.000 | < 1 mes (substituindo 1 consultoria de R$150K) |
| Empresa | Customizado | Depende do escopo, tipicamente < 3 meses |

---

## Premissas e Limitacoes

1. **Premissa de CAPEX**: O valor medio de investimento em expansao de fibra para ISPs de medio porte no Brasil e de R$1-3M, baseado em dados do setor (Abrint, TelComp).

2. **Premissa de multas**: Valores de multa baseados na Resolucao Anatel no. 589/2012 e no Regulamento de Fiscalizacao (multas variam de R$1.500 a R$50M dependendo da gravidade).

3. **Premissa de due diligence**: Custos de consultoria baseados em tarifas de mercado para assessoria M&A no setor de telecomunicacoes brasileiro (Deloitte, PwC, KPMG, EY).

4. **Cenarios conservadores**: Todos os calculos de "ROI ultra-conservador" utilizam o pior cenario plausivel. Os ROIs reais tendem a ser significativamente maiores.

5. **Dados reais**: Todas as referencias a dados da plataforma (13.534 provedores, 5.572 municipios, 4,1M registros) sao verificados contra a base de producao.
