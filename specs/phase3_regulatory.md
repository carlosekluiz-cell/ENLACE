# ENLACE — Phase 3: Regulatory Compliance Engine Specification
# Component 4 — Legal Intelligence & Tax Impact Modeling
# Read after Phase 1 data foundation is complete.

## OVERVIEW

The Regulatory Compliance Engine monitors Brazil's telecom regulatory landscape,
analyzes each ISP's specific exposure, and generates actionable compliance roadmaps.
The most urgent use case: the Norma no. 4 SVA→SCM tax reclassification (deadline Jan 2027).

## MODULE STRUCTURE

```
python/regulatory/
├── __init__.py
├── knowledge_base/
│   ├── __init__.py
│   ├── regulations.py     # Structured regulatory database
│   ├── tax_rates.py       # ICMS rates by state for SCM vs SVA
│   ├── deadlines.py       # Regulatory deadline tracker
│   └── parser.py          # NLP parser for Anatel resolution documents
├── analyzer/
│   ├── __init__.py
│   ├── profile.py         # ISP profile analyzer — cross-reference against rules
│   ├── norma4.py          # Norma no. 4 specific impact calculator
│   ├── licensing.py       # Licensing requirement checker (sub-5000 threshold)
│   └── quality.py         # Quality standard compliance (Regulamento de Qualidade SCM)
├── monitor/
│   ├── __init__.py
│   ├── scanner.py         # Scrape Anatel website for new resolutions
│   ├── alerter.py         # Generate alerts when changes affect users
│   └── llm_analyzer.py    # LLM-based regulatory text analysis (API call to Claude)
└── reports/
    ├── __init__.py
    └── compliance_report.py  # Generate PDF compliance status report
```

## REGULATORY KNOWLEDGE BASE

### Tax Rate Database (tax_rates.py)

```python
"""
ICMS rates by Brazilian state for telecom services.
These are the rates that apply when broadband is classified as SCM (not SVA).

CRITICAL: Under SVA classification, broadband was EXEMPT from ICMS in most states.
Under SCM classification (Norma no. 4), ICMS applies at state-specific rates.

This is the core of the financial impact calculation.
"""

ICMS_RATES_SCM = {
    # State: { "standard_rate": float, "telecom_rate": float, "notes": str }
    "AC": {"standard": 0.19, "telecom": 0.25, "notes": "Acre"},
    "AL": {"standard": 0.19, "telecom": 0.25, "notes": "Alagoas"},
    "AM": {"standard": 0.20, "telecom": 0.25, "notes": "Amazonas"},
    "AP": {"standard": 0.18, "telecom": 0.25, "notes": "Amapá"},
    "BA": {"standard": 0.20.5, "telecom": 0.28, "notes": "Bahia — highest telecom ICMS"},
    "CE": {"standard": 0.20, "telecom": 0.28, "notes": "Ceará"},
    "DF": {"standard": 0.20, "telecom": 0.25, "notes": "Distrito Federal"},
    "ES": {"standard": 0.17, "telecom": 0.25, "notes": "Espírito Santo"},
    "GO": {"standard": 0.19, "telecom": 0.29, "notes": "Goiás"},
    "MA": {"standard": 0.22, "telecom": 0.27, "notes": "Maranhão"},
    "MG": {"standard": 0.18, "telecom": 0.25, "notes": "Minas Gerais"},
    "MS": {"standard": 0.17, "telecom": 0.27, "notes": "Mato Grosso do Sul"},
    "MT": {"standard": 0.17, "telecom": 0.25, "notes": "Mato Grosso"},
    "PA": {"standard": 0.19, "telecom": 0.25, "notes": "Pará"},
    "PB": {"standard": 0.20, "telecom": 0.28, "notes": "Paraíba"},
    "PE": {"standard": 0.20.5, "telecom": 0.28, "notes": "Pernambuco"},
    "PI": {"standard": 0.21, "telecom": 0.27, "notes": "Piauí"},
    "PR": {"standard": 0.19.5, "telecom": 0.29, "notes": "Paraná"},
    "RJ": {"standard": 0.22, "telecom": 0.25, "notes": "Rio de Janeiro"},
    "RN": {"standard": 0.20, "telecom": 0.28, "notes": "Rio Grande do Norte"},
    "RO": {"standard": 0.19.5, "telecom": 0.25, "notes": "Rondônia"},
    "RR": {"standard": 0.20, "telecom": 0.25, "notes": "Roraima"},
    "RS": {"standard": 0.17, "telecom": 0.25, "notes": "Rio Grande do Sul"},
    "SC": {"standard": 0.17, "telecom": 0.25, "notes": "Santa Catarina"},
    "SE": {"standard": 0.19, "telecom": 0.27, "notes": "Sergipe"},
    "SP": {"standard": 0.18, "telecom": 0.25, "notes": "São Paulo"},
    "TO": {"standard": 0.20, "telecom": 0.27, "notes": "Tocantins"},
}

# NOTE: These rates are approximate and must be validated against current state legislation.
# Some states have introduced reduced rates for small providers or transitional relief.
# The pipeline should scrape state treasury websites for current rates.
```

### Norma No. 4 Impact Calculator (norma4.py)

```python
"""
Norma no. 4 reclassifies fixed broadband from SVA (Serviço de Valor Adicionado)
to SCM (Serviço de Comunicação Multimídia).

Impact per ISP:
1. ICMS tax now applies to broadband revenue (was exempt under SVA)
2. Additional regulatory obligations (quality reporting, consumer protection)
3. Licensing requirements for ISPs with <5,000 subscribers

CALCULATOR INPUT:
- ISP state (determines ICMS rate)
- Monthly broadband revenue (R$)
- Number of subscribers
- Current classification (SVA or already SCM)

CALCULATOR OUTPUT:
- Additional monthly tax burden (R$)
- Additional annual tax burden (R$)
- % increase in cost structure
- Restructuring options:
  a) Absorb cost (reduce margin)
  b) Pass to customer (price increase — with churn risk estimate)
  c) Corporate restructure (separate infrastructure from service entity)
  d) Negotiate state-level relief (some states offering transition incentives)
- Recommended action based on ISP size and state

EXAMPLE:
ISP in São Paulo, 3,000 subscribers, R$89/month average, R$267,000 monthly revenue
ICMS at 25% on broadband: R$66,750/month additional tax
Annual impact: R$801,000
% of revenue: 25%
This would likely make the ISP unprofitable without restructuring.

RESTRUCTURING OPTIONS SCORING:
Each option scored on: ease of implementation, tax savings, legal risk, time to implement
"""
```

### ISP Profile Analyzer (profile.py)

```python
"""
Cross-references an ISP's characteristics against all applicable regulations.

INPUT (from Anatel provider data + user-provided):
- Provider name / CNPJ
- State(s) of operation
- Subscriber count (from Anatel data or user input)
- Services offered (SCM, SMP, STFC, SeAC)
- Current classification
- Revenue (user input — not in open data)

CHECKS:
1. Licensing status:
   - Is the provider licensed for all services they appear to offer?
   - Are they approaching the 5,000 subscriber threshold requiring new licensing?
   - License expiry dates and renewal requirements

2. Norma no. 4 exposure:
   - What is their current SVA/SCM classification?
   - What is the estimated tax impact of reclassification?
   - Days until January 2027 deadline
   - Readiness score (0-100) based on whether they've taken preparatory steps

3. Quality compliance:
   - Do they meet Anatel's quality standards for their size category?
   - From quality_indicators table: are their metrics above minimum thresholds?
   - Risk of Anatel enforcement action

4. Consumer protection:
   - LGPD compliance requirements
   - Customer contract requirements
   - Complaint rate benchmarking (from Anatel quality data)

OUTPUT:
- Compliance dashboard with red/yellow/green status per category
- Specific action items with priority and deadline
- Estimated cost of non-compliance (fines, lost revenue from enforcement)
- Countdown timers for approaching deadlines
"""
```

## REGULATORY CHANGE MONITOR

```python
"""
monitor/scanner.py

Periodically scan Anatel's website for new publications:
- https://www.anatel.gov.br/legislacao/resolucoes — new resolutions
- https://www.anatel.gov.br/dados/destaques — regulatory news
- https://informacoes.anatel.gov.br/legislacao/consultas-publicas — open consultations

For each new publication:
1. Download document (PDF or HTML)
2. Extract text content
3. Send to LLM (Claude API) with prompt:
   "Analyze this Anatel regulatory document. Identify:
   - Which types of telecom providers are affected
   - What new obligations or changes are introduced
   - Effective dates and transition periods
   - Financial impact categories (taxes, fees, fines, investment requirements)
   Respond in structured JSON format."
4. Cross-reference affected provider types against platform users
5. Generate targeted alerts for affected ISPs

monitor/alerter.py

Alert types:
- URGENT: New regulation directly affects the ISP's current operations
- WARNING: Proposed regulation (public consultation) that may affect them
- INFO: Industry news relevant to their market segment

Delivery: In-platform notification + email digest
"""
```

## API ENDPOINTS

```
GET  /api/v1/compliance/status?provider_id=X
     — Full compliance dashboard for a provider

GET  /api/v1/compliance/norma4/impact?state=SP&subscribers=4500&revenue_monthly=400000
     — Norma no. 4 tax impact calculation

GET  /api/v1/compliance/licensing/check?subscribers=4800&services=SCM
     — Licensing threshold check

GET  /api/v1/compliance/deadlines?country=BR
     — All upcoming regulatory deadlines

GET  /api/v1/compliance/quality/benchmark?municipality_id=X&provider_id=Y
     — Quality metrics vs thresholds

POST /api/v1/compliance/monitor/subscribe
     — Subscribe to regulatory change alerts

GET  /api/v1/compliance/alerts?provider_id=X
     — Recent regulatory alerts for this provider
```

## COMPLETION CRITERIA

1. ICMS tax rates populated for all 27 Brazilian states
2. Norma no. 4 impact calculator produces correct tax estimates (validated against 5 manual calculations)
3. ISP profile analyzer correctly flags known compliance issues for test ISPs
4. Regulatory scanner successfully parses at least 3 recent Anatel resolutions
5. Alert generation produces relevant notifications for test scenarios
6. All API endpoints respond with correct data
