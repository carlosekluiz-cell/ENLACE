# ENLACE — Phase 2: Expansion Planning Engine Specification
# Component 2 — Market Intelligence & Financial Viability
# This file is read by Claude Code after Phase 1 data foundation is complete.

## OVERVIEW

The Expansion Planning Engine answers: "Where should I build next?"
It combines demographic data (IBGE), telecom market data (Anatel), geographic data (OSM/SRTM),
and infrastructure data (ANEEL) to score every geographic unit in Brazil for expansion potential,
identify competitive threats, model financial viability, and generate preliminary fiber routes.

## PREREQUISITES

- Phase 1 complete: all data tables populated, materialized views working
- Python ML environment: scikit-learn, xgboost, pandas, geopandas, shapely
- PostGIS queries returning data correctly

## PYTHON MODULE STRUCTURE

```
python/ml/
├── __init__.py
├── opportunity/
│   ├── __init__.py
│   ├── scorer.py           # Composite opportunity scoring
│   ├── demand_model.py     # Subscriber demand estimation
│   ├── competition.py      # Competitive analysis & threat detection
│   ├── features.py         # Feature engineering from raw data
│   └── training.py         # Model training pipeline
├── financial/
│   ├── __init__.py
│   ├── viability.py        # ROI, payback, NPV calculations
│   ├── capex_estimator.py  # Infrastructure cost estimation
│   ├── subscriber_curve.py # Logistic growth subscriber uptake model
│   └── arpu_model.py       # Regional ARPU estimation
├── routing/
│   ├── __init__.py
│   ├── fiber_route.py      # Dijkstra shortest path on OSM road network
│   ├── corridor_finder.py  # Identify power line / road corridors
│   └── bom_generator.py    # Bill of materials from route
└── config.py               # Model hyperparameters, cost benchmarks
```

## SUB-COMPONENT: OPPORTUNITY SCORING

### Feature Engineering (features.py)

For each geographic unit (municipality or H3 cell at resolution 8), compute:

```python
"""
DEMAND FEATURES (from IBGE census + PNAD):
- total_households: int — number of households in the area
- avg_income_per_capita: float — average monthly income per person (R$)
- pct_above_broadband_threshold: float — % households with income > 1.5x cheapest broadband plan
  (Current threshold: ~R$1,500/month household income for R$79/month broadband affordability)
- population_density: float — people per km²
- urbanization_rate: float — % of area classified as urban
- education_index: float — weighted average of education levels (higher = more internet demand)
- young_population_pct: float — % population aged 15-44 (highest broadband adoption)
- household_growth_rate: float — annual % change in households (from census comparison or projection)

MARKET FEATURES (from Anatel):
- current_penetration: float — broadband subscribers / total households (0.0 to 1.0+)
- fiber_penetration: float — fiber subscribers / total households
- technology_gap: bool — True if no fiber provider present (only DSL/wireless/cable)
- provider_count: int — number of active broadband providers
- hhi_index: float — Herfindahl-Hirschman Index (0 = fragmented, 10000 = monopoly)
- leader_share: float — market share of largest provider
- subscriber_growth_3m: float — 3-month subscriber growth rate (latest Anatel data)
- subscriber_growth_12m: float — 12-month subscriber growth rate
- nearest_fiber_provider_km: float — distance to nearest municipality with fiber coverage

INFRASTRUCTURE FEATURES (from OSM, ANEEL, SRTM):
- road_density_km_per_km2: float — paved road length per area (proxy for deployment ease)
- power_line_coverage: bool — power distribution lines present (pole-sharing opportunity)
- avg_terrain_slope: float — average terrain gradient (steeper = harder deployment)
- max_elevation_diff: float — elevation range within area (affects wireless coverage)
- distance_to_existing_network_km: float — distance from ISP's current service edge

COMPETITIVE THREAT FEATURES (from Anatel time series):
- adjacent_competitor_count: int — providers in neighboring municipalities
- adjacent_competitor_growth: float — fastest-growing competitor in adjacent areas
- competitor_expansion_signal: bool — True if any adjacent competitor grew >20% in 3 months
"""
```

### Opportunity Scoring Model (scorer.py)

```python
"""
MODEL: XGBoost Gradient Boosted Trees
TARGET: Binary classification — did a new ISP successfully enter this municipality?
  Success = subscriber growth > 20% in first 18 months after entry
  Failure = growth < 5% in first 18 months

TRAINING DATA: 
  Anatel historical data 2018-2023 (pre-Phase 2 period)
  Identify municipalities where new providers appeared (first_seen_date in providers table)
  Label as success/failure based on subsequent subscriber trajectory
  
  Expected training set size: ~2,000-5,000 municipality-entry events

FEATURES: All features from features.py computed at the time of entry (using historical data)

OUTPUT: 
  - composite_score: 0-100 (probability of successful entry * 100)
  - confidence: 0-1 (model confidence, lower for sparse data areas)
  - sub_scores: {demand: 0-100, competition: 0-100, infrastructure: 0-100, growth: 0-100}
  - top_factors: list of top 3 features driving the score (SHAP values)

MODEL TRAINING PIPELINE:
1. Extract historical entry events from Anatel time series
2. Compute features at each municipality for the month before entry
3. Label success/failure based on 18-month subscriber trajectory
4. Train XGBoost with 5-fold cross-validation
5. Compute SHAP values for interpretability
6. Save model artifact with version tag
7. Backtest: run trained model on held-out 2024 data, verify >70% AUC

SCORING PIPELINE (production):
1. Monthly: after Anatel data refresh, recompute features for all municipalities
2. Score all municipalities with trained model
3. Store in opportunity_scores table
4. Refresh API caches

IMPORTANT: The model must be INTERPRETABLE. ISP owners need to understand WHY
a score is high or low. SHAP values provide per-feature explanations.
"This area scores 82 because: high income households (30 pts), no fiber competitor (25 pts),
growing population (15 pts), close to your network (12 pts)."
"""
```

### Competitive Intelligence (competition.py)

```python
"""
COMPETITIVE ANALYSIS PER MUNICIPALITY:

1. Market Concentration (HHI):
   HHI = Σ (market_share_i)² × 10000
   where market_share_i = subscribers_i / total_subscribers
   
   Interpretation:
   - HHI < 1500: Competitive market (many small players)
   - 1500-2500: Moderately concentrated
   - > 2500: Highly concentrated (near monopoly)

2. Provider Growth Tracking:
   For each provider in each municipality, compute:
   - 3-month growth rate: (subs_current - subs_3m_ago) / subs_3m_ago
   - 12-month growth rate: same logic
   - Trend: 'accelerating', 'steady', 'decelerating', 'declining'
   
3. Expansion Pattern Detection:
   For each provider, look at their geographic footprint over time:
   - Which municipalities did they enter in the last 12 months?
   - What is their expansion direction? (geographic clustering of new entries)
   - Predict next likely expansion municipalities using spatial autocorrelation
   
   Method: For provider P, find municipalities adjacent to P's current footprint
   where P is NOT present. Rank by: demographic similarity to P's existing markets,
   distance to P's nearest existing presence, market attractiveness score.
   
4. Technology Threat Assessment:
   Flag municipalities where:
   - Only DSL/wireless exists but demographics support fiber (technology gap)
   - A fiber provider entered an adjacent municipality (fiber expansion front)
   - 5G base stations appeared (potential FWA competition for fixed broadband)
   
5. Competitor Alert System:
   Generate alerts when:
   - New provider appears in a municipality where the ISP operates (new entrant)
   - Existing competitor's growth rate exceeds 30% in 3 months (aggressive expansion)
   - Competitor deploys fiber in a municipality where ISP has only wireless (tech upgrade threat)
"""
```

## SUB-COMPONENT: FINANCIAL VIABILITY

### Subscriber Uptake Model (subscriber_curve.py)

```python
"""
MODEL: Modified logistic growth curve (Bass diffusion model variant)

S(t) = M × [1 - e^(-k×(t-t0))] / [1 + q×e^(-k×(t-t0))]

Where:
  S(t) = cumulative subscribers at month t
  M = market ceiling (addressable households × maximum penetration rate)
  k = growth rate parameter (how fast adoption occurs)
  t0 = inflection point (month of fastest growth)
  q = imitation coefficient (word-of-mouth effect)

PARAMETER CALIBRATION:
  Use Anatel historical data for municipalities where ISPs entered 2018-2023.
  For each entry event:
  - M calibrated from: addressable_households × regional_penetration_ceiling
    (penetration ceiling varies: 60-80% in high-income urban, 30-50% in rural/low-income)
  - k calibrated from: observed growth rate in similar municipalities
  - t0 calibrated from: median time to inflection in similar markets
  
  "Similar" = within same income bracket + population density + competition level cluster

OUTPUT:
  Monthly subscriber projection for 36 months, with:
  - Pessimistic (25th percentile of historical curves)
  - Base case (median)
  - Optimistic (75th percentile)
"""
```

### CAPEX Estimator (capex_estimator.py)

```python
"""
COST BENCHMARKS (from BNDES studies, Abrint reports, published industry data):

FIBER DEPLOYMENT:
  Aerial fiber (on existing poles):
  - Urban: R$15,000 - R$25,000 per km (includes cable, splices, labor)
  - Suburban: R$12,000 - R$20,000 per km
  - Rural: R$20,000 - R$35,000 per km (longer spans, harder access)
  
  Underground fiber (new duct):
  - Urban: R$60,000 - R$120,000 per km (trenching is expensive)
  - Only used where aerial is prohibited by municipal regulations
  
  Submarine/river crossing:
  - R$80,000 - R$200,000 per crossing (highly variable)

EQUIPMENT:
  OLT (Optical Line Terminal): R$30,000 - R$80,000 per unit (serves 128-512 ONTs)
  ONT (customer premises): R$200 - R$500 per unit
  Splitter cabinet (1:16 or 1:32): R$2,000 - R$5,000 installed
  Splice enclosure: R$500 - R$1,500 installed

POP (Point of Presence):
  Small POP (serves <2,000 subs): R$50,000 - R$150,000
  Medium POP (2,000-10,000 subs): R$150,000 - R$400,000
  Includes: rack, UPS, AC, OLT, switch, router, monitoring

PRIVATE NETWORK (4G/5G):
  Tower + radio unit (single sector): R$150,000 - R$300,000
  Tower + radio unit (3 sectors): R$250,000 - R$500,000
  Solar power system (off-grid): R$30,000 - R$80,000
  Microwave backhaul link: R$50,000 - R$120,000 per hop
  
TERRAIN DIFFICULTY MULTIPLIER:
  Flat urban: 1.0x
  Hilly suburban: 1.2x
  Mountainous: 1.5x
  Amazon/remote: 2.0-3.0x (logistics, river crossings, off-grid power)

CAPEX CALCULATION:
  total_capex = (cable_length_km × per_km_cost × terrain_multiplier)
              + (num_splitters × splitter_cost)
              + (num_splice_enclosures × enclosure_cost)
              + (pop_cost)
              + (num_onts × ont_cost)  -- initial batch
              + (contingency_pct × subtotal)  -- typically 15-20%
"""
```

## SUB-COMPONENT: FIBER ROUTE PRE-DESIGN

### Route Algorithm (fiber_route.py)

```python
"""
ALGORITHM: Modified Dijkstra on OSM road network graph

1. BUILD GRAPH:
   Load road_segments from PostGIS for the area of interest
   Nodes: road intersections (from OSM)
   Edges: road segments with weighted cost:
     cost = distance_m × base_cost_per_m × terrain_factor × road_class_factor
   
   Road class factors:
   - motorway/trunk: 0.8 (good infrastructure, but may have access restrictions)
   - primary: 0.9
   - secondary: 1.0 (baseline)
   - tertiary: 1.1
   - residential: 1.2
   - track/unpaved: 2.0 (expensive, avoid if possible)
   
   Terrain factor:
   - Computed from SRTM: average elevation change per km along segment
   - Flat (<2%): 1.0
   - Moderate (2-5%): 1.2
   - Steep (5-10%): 1.5
   - Very steep (>10%): 2.0
   
   Corridor bonus:
   - If segment runs parallel to a power line (from ANEEL data, within 50m): 0.7x
     (pole-sharing dramatically reduces cost)
   - If segment runs along an existing fiber corridor: 0.5x

2. FIND PATH:
   Source: ISP's existing network edge (nearest POP or splice point)
   Destination: centroid of target expansion area
   Algorithm: Dijkstra shortest path with the weighted cost function
   
3. GENERATE DESIGN:
   Along the computed path:
   - Place splice enclosures every 2 km or at major route junctions
   - Place splitter cabinets at intervals based on premises density:
     Urban (>100 premises/km²): every 500m
     Suburban (20-100): every 1km
     Rural (<20): every 2km
   - Calculate total cable length (path length + 10% for service drops and routing margins)
   - Determine cable type: 12-fiber for rural feeders, 48-fiber for urban trunks, 
     144-fiber for backbone segments
   
4. OUTPUT:
   - GeoJSON route polyline
   - Equipment list (splice enclosures, splitter cabinets, cable quantities by type)
   - Estimated CAPEX using capex_estimator
   - Estimated premises passed (buildings within 100m of route, from OSM)
   - Cost per premises passed (total capex / premises)
"""
```

## API ENDPOINTS (additions to Phase 1 API)

```python
# Expansion Planning endpoints

# Score a specific area
POST /api/v1/opportunity/score
Body: {
    "country_code": "BR",
    "area_type": "municipality",  # or "h3_cell", "custom_polygon"
    "area_id": "3509502",         # IBGE municipality code (Campinas)
    # OR for custom polygon:
    "polygon": [[lat,lon], [lat,lon], ...]
}
Response: {
    "composite_score": 78,
    "confidence": 0.85,
    "sub_scores": {"demand": 82, "competition": 71, "infrastructure": 85, "growth": 74},
    "top_factors": [
        {"feature": "pct_above_broadband_threshold", "impact": +18, "value": 0.72},
        {"feature": "technology_gap", "impact": +15, "value": true},
        {"feature": "subscriber_growth_12m", "impact": +12, "value": 0.08}
    ],
    "market_summary": {
        "total_households": 12450,
        "broadband_penetration": 0.62,
        "fiber_penetration": 0.15,
        "provider_count": 4,
        "hhi_index": 2100
    }
}

# Get top expansion opportunities
GET /api/v1/opportunity/top?country=BR&state=SP&limit=50&min_score=60
Response: {
    "opportunities": [
        {"municipality_code": "...", "name": "...", "score": 92, "households": 8500, ...},
        ...
    ]
}

# Financial viability analysis
POST /api/v1/opportunity/financial
Body: {
    "municipality_code": "3509502",
    "from_network_lat": -22.90,
    "from_network_lon": -47.06,
    "monthly_price_brl": 89.90,
    "technology": "fiber"
}
Response: {
    "subscriber_projection": {
        "pessimistic": {"month_12": 180, "month_24": 320, "month_36": 410},
        "base_case": {"month_12": 280, "month_24": 520, "month_36": 680},
        "optimistic": {"month_12": 400, "month_24": 720, "month_36": 900}
    },
    "capex_estimate": {
        "total_brl": 850000,
        "breakdown": {"cable": 420000, "equipment": 180000, "pop": 120000, "labor": 80000, "contingency": 50000},
        "per_premises_passed": 95
    },
    "financial_metrics": {
        "pessimistic": {"irr_pct": 8.5, "payback_months": 32, "npv_brl": -120000},
        "base_case": {"irr_pct": 22.0, "payback_months": 18, "npv_brl": 450000},
        "optimistic": {"irr_pct": 38.0, "payback_months": 12, "npv_brl": 980000}
    }
}

# Fiber route pre-design
POST /api/v1/opportunity/route
Body: {
    "from_lat": -22.90, "from_lon": -47.06,
    "to_lat": -22.95, "to_lon": -47.10,
    "prefer_corridors": true
}
Response: {
    "route_geojson": { ... },
    "total_length_km": 8.5,
    "terrain_difficulty": "moderate",
    "corridor_overlap_pct": 45,  # % of route along power line corridors
    "equipment": {
        "cable_48f_km": 8.5,
        "splice_enclosures": 5,
        "splitter_cabinets": 12
    },
    "premises_passed": 2800,
    "capex_estimate_brl": 680000
}

# Competitive intelligence
GET /api/v1/market/{municipality_id}/competitors
Response: {
    "hhi_index": 2100,
    "providers": [
        {"name": "ISP Local", "subscribers": 3200, "share_pct": 42, "technology": "fiber", "growth_3m": 0.05},
        {"name": "Vivo", "subscribers": 2800, "share_pct": 37, "technology": "fiber", "growth_3m": -0.01},
        ...
    ],
    "threats": [
        {"type": "new_entrant_adjacent", "provider": "Brisanet", "municipality": "Adjacent City", "distance_km": 12}
    ]
}
```

## VALIDATION TESTS

```python
# tests/validation/phase2_expansion_validation.py

"""
Test 1: Backtesting opportunity scores
- Train model on 2018-2022 data
- Score all municipalities using 2022 features
- Compare top 100 recommended municipalities against actual 2023-2025 ISP entry success
- Target: >70% of actual high-growth entries should appear in top 100 recommendations

Test 2: Financial model calibration
- Select 10 known ISP expansions from 2020-2022 with publicly available cost/subscriber data
- Run financial model on pre-expansion conditions
- Compare predicted subscriber count at month 18 vs actual Anatel data
- Target: predictions within ±30% of actual for 7 out of 10 cases

Test 3: Route generation validity
- Generate routes for 5 known fiber deployments (where actual route is visible on OSM/Google Earth)
- Compare generated route length vs actual deployment length
- Target: within ±25% length for urban, ±40% for rural (rural has more variation)

Test 4: Competitive intelligence accuracy
- Verify HHI calculations against manual computation for 10 municipalities
- Verify provider growth rates against raw Anatel CSV data
- Verify expansion pattern detection flags at least 3 known expansion events from 2024

Test 5: Feature engineering correctness
- For 5 municipalities, manually verify each feature value against source data
- broadband_penetration should match Anatel subscribers / IBGE households
- avg_income should match IBGE census data for the municipality's tracts
- provider_count should match distinct providers in Anatel data
"""
```

## COMPLETION CRITERIA

Phase 2 Expansion Planning is complete when:
1. Feature engineering computes all features for all Brazilian municipalities
2. XGBoost model trained with AUC > 0.70 on held-out test set
3. Opportunity scores populated for all 5,570 municipalities
4. Financial viability model produces reasonable projections (validated against known cases)
5. Fiber route generation produces valid routes on OSM network
6. All API endpoints respond correctly with appropriate error handling
7. Backtesting shows >70% alignment with actual market outcomes
