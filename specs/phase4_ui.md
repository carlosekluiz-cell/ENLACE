# ENLACE — Phase 4: User Interface & Experience Specification
# Component 7 — Frontend, Maps, Reports, Multi-Tenant
# Read after all backend components are functional.

## OVERVIEW

Map-first interface built with React + TypeScript + Deck.gl (or Mapbox GL JS).
The primary interaction model: user sees a map, clicks on colored zones, gets intelligence.
Must work on desktop and tablet. Must be radically simple for non-technical ISP owners.
All text in Portuguese (with i18n architecture for future Spanish/English).

## TECHNOLOGY STACK

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.js          # Next.js 14 with App Router
├── tailwind.config.js
├── public/
│   ├── locales/
│   │   ├── pt-BR.json
│   │   └── es.json         # Future: Spanish
│   └── assets/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx         # Landing / login
│   │   ├── dashboard/
│   │   │   ├── page.tsx     # Main map dashboard
│   │   │   ├── expansion/
│   │   │   │   └── page.tsx # Expansion planning view
│   │   │   ├── design/
│   │   │   │   └── page.tsx # RF design view
│   │   │   ├── compliance/
│   │   │   │   └── page.tsx # Regulatory compliance view
│   │   │   ├── health/
│   │   │   │   └── page.tsx # Network health view
│   │   │   └── reports/
│   │   │       └── page.tsx # Report generation
│   │   └── api/             # Next.js API routes (proxy to backend)
│   ├── components/
│   │   ├── map/
│   │   │   ├── MapContainer.tsx        # Main map wrapper
│   │   │   ├── OpportunityLayer.tsx    # Color-coded opportunity zones
│   │   │   ├── CompetitorLayer.tsx     # Competitor coverage overlay
│   │   │   ├── CoverageLayer.tsx       # RF coverage footprint display
│   │   │   ├── RouteLayer.tsx          # Fiber route visualization
│   │   │   ├── BaseStationLayer.tsx    # Cell tower positions
│   │   │   ├── DrawingTools.tsx        # User draws area polygon
│   │   │   └── LayerControls.tsx       # Toggle layers on/off
│   │   ├── panels/
│   │   │   ├── OpportunityPanel.tsx    # Score details when area clicked
│   │   │   ├── FinancialPanel.tsx      # Financial projection charts
│   │   │   ├── CompetitorPanel.tsx     # Competitive analysis details
│   │   │   ├── DesignPanel.tsx         # RF design configuration & results
│   │   │   ├── CompliancePanel.tsx     # Regulatory status dashboard
│   │   │   └── HealthPanel.tsx         # Network health metrics
│   │   ├── charts/
│   │   │   ├── SubscriberProjection.tsx  # Logistic growth curve chart
│   │   │   ├── MarketSharePie.tsx        # Provider market share
│   │   │   ├── QualityTrend.tsx          # Quality metrics over time
│   │   │   └── RevenueProjection.tsx     # Financial projection bars
│   │   ├── common/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── ScoreGauge.tsx          # 0-100 score visualization
│   │   │   ├── CountdownTimer.tsx      # Regulatory deadline countdown
│   │   │   └── RiskBadge.tsx           # Red/yellow/green status badge
│   │   └── reports/
│   │       ├── ReportBuilder.tsx       # Configure and generate reports
│   │       └── PdfViewer.tsx           # Preview generated PDF
│   ├── hooks/
│   │   ├── useMapData.ts       # Fetch and cache map layer data
│   │   ├── useOpportunity.ts   # Opportunity scoring API calls
│   │   ├── useDesign.ts        # RF design job management
│   │   └── useAuth.ts          # Authentication state
│   ├── lib/
│   │   ├── api.ts              # API client (axios/fetch wrapper)
│   │   ├── mapUtils.ts         # Coordinate conversions, bbox calculations
│   │   ├── colorScales.ts      # Score-to-color mapping functions
│   │   └── formatters.ts       # Currency, number, date formatting (pt-BR)
│   └── types/
│       ├── api.ts              # API response type definitions
│       ├── map.ts              # Map layer data types
│       └── models.ts           # Domain model types
```

## MAP VISUALIZATION ARCHITECTURE

### Technology: Deck.gl with Mapbox base map

```typescript
/*
Deck.gl provides WebGL-accelerated rendering for large datasets.
Critical for rendering:
- 468,097 census tract polygons colored by opportunity score
- Thousands of base station points
- Coverage footprint rasters with 100,000+ grid points
- Fiber route polylines

Layer stack (bottom to top):
1. Mapbox base map (streets/satellite/terrain)
2. Administrative boundaries (states, municipalities) — GeoJsonLayer
3. Opportunity heat map (census tracts colored by score) — GeoJsonLayer or H3HexagonLayer
4. Competitor coverage areas — GeoJsonLayer with transparency
5. Base station markers — ScatterplotLayer or IconLayer
6. Proposed fiber route — PathLayer
7. RF coverage footprint — BitmapLayer (GeoTIFF rendered as image overlay)
8. User-drawn polygon for custom analysis — EditableGeoJsonLayer
*/
```

### Opportunity Layer (OpportunityLayer.tsx)

```typescript
/*
The first thing the user sees: a color-coded map of their operating area.

Data: opportunity_scores table → API → GeoJSON or H3 cells
Colors:
- Dark green (#1a9641): score 80-100 (excellent opportunity)
- Light green (#a6d96a): score 60-79 (good opportunity)
- Yellow (#ffffbf): score 40-59 (moderate)
- Orange (#fdae61): score 20-39 (poor)
- Red (#d7191c): score 0-19 (avoid — saturated or unfavorable)

Interaction:
- Hover: tooltip showing municipality name, score, key metric
- Click: opens OpportunityPanel with full analysis
- Zoom: at high zoom, show census tract level; at low zoom, aggregate to municipality

Performance:
- At national level: show only municipality centroids as colored circles
- At state level: show municipality polygons
- At municipality level: show census tract polygons or H3 hexagons
- Use Deck.gl's built-in LOD (level of detail) based on zoom
*/
```

### Coverage Layer (CoverageLayer.tsx)

```typescript
/*
Displays RF coverage footprints from the design engine.

Data: GeoTIFF raster from Rust engine → converted to PNG with georeferencing
Colors (signal strength):
- Dark green: > -70 dBm (excellent)
- Light green: -70 to -80 dBm (good)
- Yellow: -80 to -90 dBm (fair)
- Orange: -90 to -95 dBm (marginal)
- Red: -95 to -100 dBm (poor)
- Transparent: below -100 dBm (no coverage)

The GeoTIFF is converted server-side to a PNG with transparency,
plus a bounds file. Rendered using Deck.gl BitmapLayer.

Tower markers: shown as antenna icons with sector lines indicating azimuth.
Clicking a tower shows its individual coverage stats.
*/
```

## USER FLOWS

### Flow 1: "Where should I build?" (Primary)
```
1. User logs in → sees map centered on their state
2. Map shows opportunity heat map (green/yellow/red zones)
3. User clicks a green zone → OpportunityPanel opens
4. Panel shows: score breakdown, demographics, competition, subscriber estimate
5. User clicks "Analyze Financial Viability" → FinancialPanel shows IRR/payback
6. User clicks "Generate Route" → RouteLayer shows proposed fiber path
7. User clicks "Export Report" → PDF generated with maps, charts, financials
```

### Flow 2: "Design my private network" (Trópico customers)
```
1. User clicks "New Design" → DrawingTools activated
2. User draws polygon around their farm/mine/area on map
3. DesignPanel opens: user enters frequency, power, antenna height
4. User clicks "Optimize Coverage" → job submitted to Rust engine
5. Loading indicator while computation runs (1-5 minutes)
6. CoverageLayer shows result: tower positions + coverage footprint
7. Panel shows: tower count, coverage %, equipment list, CAPEX estimate
8. User can adjust parameters and re-run
9. User clicks "Export Design Package" → PDF with maps, link budgets, BOM
```

### Flow 3: "Am I compliant?" (Regulatory)
```
1. User navigates to Compliance tab
2. CompliancePanel shows dashboard with traffic-light indicators
3. Norma no. 4 section: countdown timer, estimated tax impact, readiness score
4. Licensing section: current status, approaching thresholds
5. Quality section: metrics vs Anatel standards
6. User clicks "View Action Items" → prioritized compliance checklist
7. User clicks "Generate Compliance Report" → PDF for management/board
```

## REPORT GENERATION

```python
"""
Reports are generated server-side as PDF using WeasyPrint or ReportLab.
Each report type has a template with embedded map screenshots and charts.

Report types:
1. Expansion Analysis Report
   - Cover page with platform branding
   - Executive summary (opportunity score, key findings)
   - Market analysis (demographics, competition, penetration)
   - Financial projection (subscriber curve, IRR, payback)
   - Route pre-design (map + equipment list + CAPEX)
   - Risk factors and recommendations
   Typical length: 8-12 pages
   
2. RF Design Report
   - Cover page
   - Design parameters (frequency, power, area)
   - Coverage map (full page, high resolution)
   - Tower specifications (coordinates, height, equipment)
   - Link budget calculations (backhaul)
   - Equipment bill of materials with costs
   - Power system design (if off-grid)
   Typical length: 10-15 pages
   
3. Compliance Status Report
   - Current compliance dashboard
   - Norma no. 4 impact analysis with financial projections
   - Licensing status and requirements
   - Quality metrics and benchmarks
   - Action plan with timelines
   Typical length: 6-8 pages

4. Rural Connectivity Feasibility Report
   - Community profile
   - Hybrid architecture design
   - Coverage map
   - Solar power system design
   - Cost estimate (CAPEX + OPEX)
   - Funding program eligibility
   - Implementation timeline
   Typical length: 12-18 pages

All reports in Portuguese. Professional formatting suitable for:
- Bank financing applications (BNDES, FUST financial agents)
- Investor presentations
- Government funding applications
- Board/management review
"""
```

## MULTI-TENANT ARCHITECTURE

```python
"""
Every ISP is a tenant. Data isolation is critical — ISP A must never see ISP B's analyses.

Authentication: JWT tokens with tenant_id claim
Authorization: Every API call checks tenant_id against the requested resource
Data isolation: 
  - Public data (Anatel, IBGE, terrain): shared across all tenants
  - User-generated data (saved analyses, custom areas, designs): tenant-isolated
  - Aggregated anonymized data (for model improvement): opt-in

Tenant model:
  Table: tenants
  - id, name, country_code, subscription_tier, created_at
  - primary_state (for default map center)
  - settings (JSONB — preferences, notification settings)

  Table: tenant_users
  - id, tenant_id, email, password_hash, role ('admin', 'engineer', 'viewer')
  
  Table: saved_analyses
  - id, tenant_id, analysis_type, parameters (JSONB), results (JSONB), created_at
  
  Table: saved_designs
  - id, tenant_id, design_type, area_geojson, result_data (JSONB), created_at

Rate limiting by tier:
  Free: 10 opportunity scores/day, no RF designs, no PDF reports
  ISP Standard: 100 scores/day, 5 designs/month, 10 reports/month
  ISP Professional: unlimited scores, 50 designs/month, unlimited reports
  Enterprise: unlimited everything + API access
"""
```

## COMPLETION CRITERIA

1. Map dashboard loads within 3 seconds showing opportunity heat map for any Brazilian state
2. Opportunity layer correctly colors zones and responds to click with score details
3. Coverage footprint renders correctly overlaid on map after RF design completes
4. Fiber route displays on map with correct path following roads
5. All 4 report types generate valid PDFs with embedded maps and charts
6. Multi-tenant isolation: logged-in user A cannot access user B's saved analyses
7. Works on Chrome, Firefox, Safari desktop and tablet (iPad)
8. All UI text in Portuguese with i18n framework ready for Spanish
9. Responsive layout: map takes full screen on desktop, panel slides in from right
