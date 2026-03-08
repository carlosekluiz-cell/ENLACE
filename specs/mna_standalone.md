# ENLACE M&A — Standalone M&A Intelligence Product Specification
# Separate codebase, shared data foundation, separate brand
# Can be built in parallel with Phase 2 once data foundation is solid.

## OVERVIEW

Two-sided intelligence platform for the Brazilian telecom M&A market.
Acquirers get continuous target identification and deal analysis.
Sellers get market-based valuation benchmarks and competitive positioning.
Investment banks and advisors get data infrastructure for deal sourcing.

CRITICAL: This product must be SEPARATE from the ISP operations platform
to avoid trust conflicts. An ISP using the operations platform must not
fear that their data is visible to potential acquirers.

## SEPARATE INFRASTRUCTURE

```
mna/
├── frontend/           # Separate React app with its own domain
├── api/                # Separate FastAPI backend
├── models/             # Valuation models, scoring algorithms
├── data/               # Reads from shared database (read-only views)
└── reports/            # M&A specific report templates
```

The M&A product connects to the SAME PostgreSQL database as the main platform
but through READ-ONLY views that expose only public Anatel/IBGE data.
It NEVER accesses tenant-specific data from the operations platform.

## DATA ARCHITECTURE

### Additional Tables (M&A specific)

```sql
-- M&A deal tracking (public deals from news/regulatory filings)
CREATE TABLE mna_deals (
    id SERIAL PRIMARY KEY,
    acquirer_name VARCHAR(300),
    target_name VARCHAR(300),
    target_provider_id INTEGER REFERENCES providers(id),
    deal_date DATE,
    deal_value_brl NUMERIC(15,2),
    subscribers_acquired INTEGER,
    municipalities_acquired INTEGER,
    value_per_subscriber NUMERIC(10,2),  -- computed
    revenue_multiple NUMERIC(6,2),       -- if disclosed
    source_url VARCHAR(500),
    source_type VARCHAR(50),  -- 'regulatory_filing', 'news', 'cade_approval'
    notes TEXT
);

-- ISP valuation estimates (computed, not user-provided)
CREATE TABLE mna_valuations (
    id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES providers(id),
    computed_at TIMESTAMPTZ NOT NULL,
    -- Subscriber-based metrics
    total_subscribers INTEGER,
    fiber_subscribers INTEGER,
    subscriber_growth_12m DOUBLE PRECISION,
    -- Market position
    municipalities_served INTEGER,
    avg_market_share DOUBLE PRECISION,
    hhi_weighted_avg DOUBLE PRECISION,  -- market concentration in service areas
    -- Technology assessment
    fiber_pct DOUBLE PRECISION,
    technology_score DOUBLE PRECISION,  -- 0-100 (higher = more fiber)
    -- Geographic assessment
    urbanization_score DOUBLE PRECISION,
    income_score DOUBLE PRECISION,
    growth_potential_score DOUBLE PRECISION,
    -- Regulatory risk
    norma4_exposure_score DOUBLE PRECISION,  -- 0-100 (higher = more risk)
    licensing_risk BOOLEAN,
    -- Valuation range
    estimated_value_low_brl NUMERIC(15,2),
    estimated_value_mid_brl NUMERIC(15,2),
    estimated_value_high_brl NUMERIC(15,2),
    valuation_method VARCHAR(50),  -- 'subscriber_multiple', 'revenue_multiple', 'dcf'
    comparable_deals JSONB,  -- list of similar deal references
    model_version VARCHAR(50)
);

-- Acquirer profiles (registered M&A platform users)
CREATE TABLE mna_acquirers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(300),
    contact_email VARCHAR(200),
    target_regions JSONB,  -- list of state codes of interest
    target_size_min INTEGER,  -- min subscriber count
    target_size_max INTEGER,  -- max subscriber count
    target_technology VARCHAR(50),  -- 'fiber', 'any'
    budget_brl NUMERIC(15,2),
    subscription_tier VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## VALUATION MODEL

```python
"""
mna_valuations are computed monthly after Anatel data refresh.

THREE VALUATION METHODS:

1. Subscriber Multiple Method:
   Based on historical deal data: what have acquirers paid per subscriber?
   
   value = total_subscribers × value_per_subscriber
   
   value_per_subscriber ranges (from published Brazilian telecom deals):
   - Fiber subscribers: R$1,200 — R$2,500 per sub
   - Cable/DSL subscribers: R$600 — R$1,200 per sub
   - Wireless subscribers: R$400 — R$800 per sub
   
   Adjustments:
   + Premium for high market share in served area (+10-20%)
   + Premium for high-growth market (+10-15%)
   + Premium for fiber-heavy technology mix (+15-25%)
   - Discount for high Norma no. 4 exposure (-10-20%)
   - Discount for declining subscriber trend (-15-25%)
   - Discount for concentrated service area (single municipality risk) (-10%)

2. Revenue Multiple Method:
   value = estimated_annual_revenue × revenue_multiple
   
   estimated_annual_revenue = subscribers × estimated_arpu × 12
   estimated_arpu from regional pricing analysis (Anatel data)
   
   Revenue multiples (from comparable deals):
   - Small ISP (<5,000 subs): 2.0 — 4.0x revenue
   - Mid ISP (5,000-20,000 subs): 3.0 — 6.0x revenue
   - Large ISP (>20,000 subs): 4.0 — 8.0x revenue

3. DCF (Discounted Cash Flow) Simplified:
   Project subscriber growth for 5 years using platform's growth model
   Apply regional ARPU estimates
   Assume EBITDA margin of 30-45% (published industry benchmarks)
   Discount at 15-20% (Brazil risk premium)
   Terminal value at 5x final year EBITDA
   
   This method is the least reliable without actual financial data
   but provides a cross-check against multiple-based methods.

OUTPUT:
   value_range = {
       "low": min(method_1_low, method_2_low, method_3_low),
       "mid": average(method_1_mid, method_2_mid, method_3_mid),
       "high": max(method_1_high, method_2_high, method_3_high)
   }
"""
```

## ACQUIRER DASHBOARD FEATURES

```python
"""
1. TARGET MAP:
   Interactive map showing every ISP in Brazil as a colored marker.
   Color = acquisition attractiveness score (0-100)
   Size = subscriber count
   Filters: by state, subscriber range, technology, score range
   Click: shows ISP profile with valuation estimate

2. DEAL FLOW PIPELINE:
   Kanban-style board: Identified → Under Analysis → Approached → In Negotiation → Closed
   Track multiple target ISPs through acquisition process
   
3. PORTFOLIO ANALYSIS:
   If acquirer has existing ISPs, show:
   - Combined footprint map
   - Overlap analysis with potential targets
   - Integration complexity score
   - "If you acquire X, your combined market share in State Y becomes Z%"

4. MARKET ALERTS:
   - ISP subscriber count stalled for 3+ months (potential distressed seller)
   - New regulatory pressure (Norma no. 4 exposure creates urgency)
   - Competitor acquisition (Brasil TecPar acquired ISP in your target region)
   - Quality degradation (ISP's quality metrics declining — management issues?)

5. COMPARABLE DEALS DATABASE:
   Searchable history of all tracked M&A deals in Brazilian telecom
   Filter by size, region, technology, date
   Per-deal metrics: subscribers acquired, price per subscriber, multiples
"""
```

## SELLER VALUATION TOOL FEATURES

```python
"""
Self-service tool for ISP owners to understand their market value.

1. AUTOMATED VALUATION:
   ISP enters their CNPJ or selects from provider list.
   Platform pulls all public data (Anatel subscribers, municipalities served, technology mix).
   Generates valuation range using all three methods.
   Shows comparable deals for similar ISPs.
   
2. COMPETITIVE POSITION REPORT:
   Where does this ISP stand in its service area?
   Market share by municipality
   Quality ranking vs competitors
   Growth rate vs competitors
   Technology advantage/disadvantage
   
3. PRE-SALE READINESS:
   Checklist of items acquirers typically evaluate:
   - Regulatory compliance status (from compliance engine)
   - Technology assessment (% fiber, network age proxy)
   - Market position strength
   - Geographic concentration risk
   - Customer base quality indicators
   
   Readiness score: 0-100
   "Your ISP scores 72 on acquisition readiness. Top improvement areas:
   - Increase fiber share from 60% to 80% (+8 points)
   - Resolve licensing threshold issue (+5 points)
   - Diversify to adjacent municipality (+5 points)"
"""
```

## API ENDPOINTS (Separate from main platform API)

```
# M&A API — runs on separate port/domain

# Target discovery
GET  /api/v1/mna/targets?state=SP&min_subs=1000&max_subs=10000&min_score=60
GET  /api/v1/mna/targets/{provider_id}
GET  /api/v1/mna/targets/{provider_id}/valuation

# Portfolio analysis
POST /api/v1/mna/portfolio/analyze
     Body: { "existing_providers": [id1, id2], "target_provider": id3 }

# Comparable deals
GET  /api/v1/mna/deals?state=SP&min_date=2023-01-01&technology=fiber
GET  /api/v1/mna/deals/statistics  — aggregate deal metrics

# Seller self-service
GET  /api/v1/mna/valuation?provider_id=X  — or by CNPJ
GET  /api/v1/mna/valuation/{provider_id}/comparables
GET  /api/v1/mna/valuation/{provider_id}/readiness

# Market intelligence
GET  /api/v1/mna/market/consolidation-index?state=SP  — consolidation pace
GET  /api/v1/mna/market/alerts?acquirer_id=X

# Reports
POST /api/v1/mna/reports/target-profile  — generate target analysis PDF
POST /api/v1/mna/reports/valuation       — generate valuation report PDF
POST /api/v1/mna/reports/portfolio       — generate portfolio analysis PDF
```

## COMPLETION CRITERIA

1. Valuation model produces reasonable estimates for 100 test ISPs
   (cross-reference against known deal values where available)
2. Target map displays all 10,000+ ISPs with correct scoring
3. Comparable deals database populated with at least 50 historical deals
4. Acquirer dashboard filters and alerts work correctly
5. Seller valuation tool produces report within 30 seconds
6. Portfolio overlap analysis correctly identifies geographic intersections
7. All reports generate valid PDFs
8. Complete data isolation from operations platform (no tenant data leakage)
