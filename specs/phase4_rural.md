# ENLACE — Phase 4: Rural Connectivity Planner Specification
# Component 6 — Amazon & Remote Area Hybrid Network Design
# Read after Phases 1-3 are complete.

## OVERVIEW

Specialized module for designing connectivity solutions for rural and remote
communities, particularly in the Amazon, Nordeste interior, and other underserved
regions. Combines expansion planning (Comp 2) with RF design (Comp 3) under
extreme constraints: no grid power, limited backhaul, difficult terrain, and
hybrid technology architectures.

This module also matches deployments to government funding programs (FUST,
Norte Conectado, New PAC) and generates funding application materials.

## MODULE STRUCTURE

```
python/rural/
├── __init__.py
├── hybrid_designer.py      # Multi-technology network architecture design
├── satellite_backhaul.py   # Satellite link budget and service selection
├── solar_power.py          # Off-grid solar + battery sizing
├── community_profiler.py   # Rural community connectivity demand estimation
├── funding_matcher.py      # Match deployments to government programs
├── cost_model_rural.py     # Rural-specific cost benchmarks (2-3x urban)
└── river_crossing.py       # Amazon river crossing design (submarine cable / wireless)
```

## HYBRID ARCHITECTURE DESIGNER

```python
"""
hybrid_designer.py

Rural deployments almost never use a single technology. The designer selects
the optimal combination based on constraints.

TECHNOLOGY OPTIONS:
1. Satellite backhaul (VSAT, Starlink, HughesNet, Telebras SGDC)
   - Pros: Available anywhere, fast deployment
   - Cons: High latency (500-700ms GEO, 30-50ms LEO), bandwidth caps, ongoing cost
   - Best for: Very remote, <500 users, no terrestrial backhaul path

2. Microwave backhaul
   - Pros: High bandwidth (100Mbps-1Gbps), low latency, moderate cost
   - Cons: Requires line-of-sight, towers at both ends, licensed spectrum
   - Best for: 10-50km links between communities with suitable terrain

3. Fiber backbone (where available)
   - Pros: Highest bandwidth, lowest latency, lowest operating cost
   - Cons: Highest CAPEX, slow deployment, physical vulnerability (Amazon)
   - Best for: Along existing infrastructure corridors (roads, rivers, power lines)

4. 4G/LTE fixed wireless access (last mile)
   - Pros: Wide coverage per tower (5-15km at 700MHz), serves many users
   - Cons: Shared bandwidth, requires licensed spectrum, tower infrastructure
   - Best for: Dispersed communities with 200-5000 users in tower coverage area
   - Trópico's primary solution: 250MHz and 700MHz private LTE

5. WiFi mesh (last mile)
   - Pros: Cheap equipment, unlicensed spectrum, easy to deploy
   - Cons: Short range (100-300m), interference-prone, limited capacity
   - Best for: Concentrated settlements, community centers, schools

6. TV White Space (last mile)
   - Pros: Good propagation in VHF/UHF bands, longer range than WiFi
   - Cons: Regulatory complexity, limited equipment availability
   - Best for: Rural areas with unused TV spectrum

DECISION LOGIC:
Input: community location, population, area, nearest infrastructure point,
       power availability, budget, terrain type

1. Backhaul selection:
   - If fiber backbone within 20km and road/river corridor exists → fiber
   - If line-of-sight path exists to nearest connected point within 50km → microwave
   - If no terrestrial option → satellite (prefer LEO if available)

2. Last mile selection:
   - If community area < 1km² and population < 500 → WiFi mesh
   - If community spread over 1-10km² → 4G/LTE at 700MHz (1-2 towers)
   - If community spread over 10-50km² → 4G/LTE at 250MHz (wider coverage)
   - If very dispersed (farm-by-farm) → satellite per-premises

3. Power selection:
   - If grid power available → grid (with UPS backup)
   - If no grid → solar + battery
   - If both available → grid primary + solar backup

OUTPUT:
- Network architecture diagram (which technologies where)
- Equipment list per site
- Backhaul link budget
- Coverage footprint (from RF engine)
- Power system design (from solar_power module)
- Total CAPEX and monthly OPEX
- Funding eligibility assessment
"""
```

## SOLAR POWER SIZING

```python
"""
solar_power.py

For off-grid sites, design the solar power system.

INPUT:
- Site latitude/longitude (determines solar irradiance)
- Equipment power consumption profile (watts per hour, 24-hour cycle)
- Required autonomy (days without sun the system must sustain — typically 3-5 for Amazon)
- Battery technology (lead-acid vs lithium — affects depth of discharge)

DATA SOURCE:
- INPE LABREN solar irradiance atlas (labren.ccst.inpe.br)
  Provides: daily average solar irradiance in kWh/m²/day per month
  Resolution: municipal level or finer

CALCULATION:
1. Daily energy requirement = Σ(equipment_watts × hours_per_day) / 1000 (kWh)
   Include DC-AC inverter losses (15%), cable losses (5%), charge controller losses (5%)
   
2. Adjusted daily energy = daily_requirement × 1.25 (safety margin)

3. Peak solar hours = daily_irradiance_kwh_m2 / 1.0 (reference irradiance)
   Use WORST MONTH value for the location (system must work year-round)
   Amazon: worst month typically Dec-Feb (rainy season) — 3.0-4.0 peak hours
   Nordeste: worst month typically Jun-Jul — 4.5-5.5 peak hours
   South: worst month Jun-Jul — 3.0-4.0 peak hours

4. Panel array size = adjusted_daily_energy / peak_solar_hours / panel_efficiency
   Panel efficiency: 0.85 (derating for temperature, soiling, aging)

5. Battery bank size = daily_requirement × autonomy_days / depth_of_discharge
   Lead-acid DoD: 50% (don't discharge below 50%)
   Lithium DoD: 80%

6. Charge controller size = panel_array_watts × 1.25

EXAMPLE — Typical rural 4G tower site:
- Radio unit: 150W continuous
- Backhaul: 30W
- Router/switch: 20W
- Cooling fan: 30W (daytime only)
- Total: ~230W average, ~250W peak
- Daily energy: 230W × 24h = 5.52 kWh
- Amazon (worst month 3.5 peak hours): panel array = 5.52 × 1.25 / 3.5 / 0.85 = 2.32 kWp
- Battery (3 days autonomy, lithium): 5.52 × 3 / 0.8 = 20.7 kWh

OUTPUT:
- Panel array: quantity and wattage of panels
- Battery bank: capacity in kWh, number of batteries
- Charge controller: specification
- Inverter: specification
- Estimated CAPEX for power system
- Estimated lifespan and replacement schedule
"""
```

## GOVERNMENT FUNDING MATCHER

```python
"""
funding_matcher.py

Match proposed rural deployments against active government funding programs.

PROGRAMS TO TRACK:
1. FUST (Fundo de Universalização dos Serviços de Telecomunicações)
   - Source: gov.br/mcom/fust
   - Eligibility: municipalities < 30,000 inhabitants, underserved areas
   - Funding: credit lines through BNDES and other financial agents
   - Application: feasibility study + business plan required

2. Norte Conectado
   - Source: gov.br/mcom/norte-conectado
   - Focus: Amazon region fiber backbone
   - Eligibility: communities along Norte Conectado routes
   - Funding: public investment for backbone, private for last mile

3. New PAC — Connectivity
   - Source: gov.br/planalto/novo-pac
   - Includes: 4G to 6,800 villages, 5G to all 5,565 municipalities
   - Eligibility: communities in program target list
   - Funding: public-private partnership

4. 5G Auction Obligations
   - Source: Anatel 5G license conditions
   - Operators must cover rural communities by specific deadlines
   - Opportunity: partner with obligation-holding operator

5. State-level programs (varies by state)
   - Some states have their own connectivity funds
   - E.g., Ceará's Cinturão Digital

MATCHING LOGIC:
For each proposed deployment:
1. Check municipality population (< 30,000 for FUST)
2. Check geographic location (Amazon for Norte Conectado)
3. Check if community is on New PAC target list
4. Check if 5G obligation operator has unfulfilled commitments in area
5. Identify all applicable programs
6. For each program, generate eligibility assessment and required documentation list

OUTPUT:
- List of applicable funding programs with eligibility confidence
- Required documentation checklist per program
- Pre-formatted feasibility summary (can be used in funding applications)
- Estimated funding amount available
- Application timeline and contacts
"""
```

## API ENDPOINTS

```
POST /api/v1/rural/design
     Body: { "community_lat": -2.5, "community_lon": -56.0, 
             "population": 1200, "area_km2": 5, "grid_power": false }
     — Generate complete hybrid network design

GET  /api/v1/rural/solar?lat=-2.5&lon=-56.0&power_watts=250&autonomy_days=3
     — Solar power system sizing

POST /api/v1/rural/funding/match
     Body: { "municipality_code": "1505064", "technology": "4g_lte", "capex_brl": 500000 }
     — Match deployment to funding programs

GET  /api/v1/rural/funding/programs?country=BR
     — List all active funding programs

POST /api/v1/rural/report
     — Generate complete rural connectivity feasibility report PDF
```

## COMPLETION CRITERIA

1. Hybrid designer correctly selects technology mix for 5 test scenarios
   (Amazon riverside, Nordeste interior, cerrado farm, mountain community, island)
2. Solar power sizing matches manual calculations within ±10%
3. Funding matcher correctly identifies applicable programs for test municipalities
4. River crossing module handles Amazon river width variations
5. Cost model produces estimates within BNDES published rural benchmark ranges
6. Feasibility report PDF is professional quality suitable for funding applications
