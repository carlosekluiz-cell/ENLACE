# ENLACE — Phase 3: Network Health & Fault Intelligence Specification
# Component 5 — Predictive Maintenance & Quality Monitoring
# Read after Phase 1 data foundation is complete.

## OVERVIEW

Uses publicly available weather data (INMET), Anatel quality metrics, and
geographic/infrastructure data to predict fault risks, benchmark network quality,
and recommend proactive maintenance actions. Solvability: 55-60% with open data alone,
improving to 80%+ if ISP integrates their OZmap or network management data.

## MODULE STRUCTURE

```
python/ml/health/
├── __init__.py
├── weather_correlation.py   # Statistical model: weather → fault probability
├── quality_benchmark.py     # Per-municipality quality vs national averages
├── maintenance_scorer.py    # Proactive maintenance priority scoring
├── seasonal_patterns.py     # Seasonal fault pattern analysis
├── infrastructure_aging.py  # Infer infrastructure age from Anatel first-seen dates
└── integrations/
    ├── __init__.py
    └── ozmap_client.py      # Optional OZmap API integration
```

## WEATHER-FAULT CORRELATION MODEL

```python
"""
weather_correlation.py

HYPOTHESIS: Network faults correlate with weather events. Specifically:
- Heavy rainfall → aerial fiber damage, splice enclosure water ingress
- High winds → pole stress, cable sway, tree-on-line events
- Lightning → equipment damage, power surge
- Temperature extremes → cable expansion/contraction, equipment thermal failure

DATA SOURCES:
- INMET weather observations (hourly, ~600 stations across Brazil)
- Anatel quality indicators per municipality per month

MODEL:
For each municipality, compute monthly weather severity metrics:
- total_precipitation_mm: sum of hourly precipitation
- max_daily_precipitation_mm: worst single day
- max_wind_speed_ms: peak wind speed
- lightning_density: strikes per km² (if available from INMET)
- temperature_range: max - min temperature for the month
- consecutive_rain_days: longest streak of daily precipitation >10mm

Correlate with Anatel quality degradation:
- quality_delta = quality_this_month - quality_3month_rolling_average
- If quality_delta < -X (quality dropped), correlate with weather metrics

EXPECTED PATTERNS:
- October-March (rainy season in most of Brazil): higher fault rates
- Amazon region: year-round high precipitation correlation
- Northeast coast: wind-related faults more common
- South: winter temperature cycling affects buried infrastructure
- Lightning corridor (central Brazil, Minas-Goiás triangle): equipment damage spikes

OUTPUT:
- Per-municipality risk score (0-100) based on weather forecast for next 7 days
- Historical seasonal risk calendar: "Your area typically sees 35% more faults in January"
- Specific risk type: "wind risk HIGH next 48 hours" vs "precipitation risk MODERATE"
"""
```

## QUALITY BENCHMARKING

```python
"""
quality_benchmark.py

For each municipality where an ISP operates:
1. Extract Anatel quality metrics (IDA — Índice de Desempenho no Atendimento,
   download speed compliance, latency, availability)
2. Compare against:
   - National average for same technology type
   - State average
   - Same-size ISP average (peers)
3. Track trend: improving, stable, or degrading over last 12 months
4. Flag outliers: if quality metric is >2 standard deviations below peer average

VISUALIZATION:
- Dashboard showing each quality metric as gauge (red/yellow/green)
- Time series chart showing quality trends over last 12 months
- Peer comparison: "Your download speed compliance is at the 35th percentile
  among ISPs of similar size in your state"

CORRELATION WITH CHURN:
- Municipalities where quality degraded by >10% in 3 months show
  subscriber loss in subsequent quarters (observable from Anatel data)
- Alert: "Quality in Municipality X dropped 12% this quarter.
  Based on historical patterns, this correlates with 3-5% subscriber loss
  in the next quarter if not addressed."
"""
```

## PROACTIVE MAINTENANCE SCORING

```python
"""
maintenance_scorer.py

For each municipality where an ISP operates, compute maintenance priority:

FACTORS:
1. Weather risk (from weather_correlation): 0-100
2. Infrastructure age proxy:
   - First time ISP appeared in Anatel data for this municipality = approximate deployment date
   - Older deployments have higher failure rates
   - Score: 0 (new, <2 years) to 100 (old, >8 years)
3. Quality trend: declining quality = higher priority
4. Revenue at risk: subscriber count × ARPU = monthly revenue exposed
5. Competitive pressure: if competitor quality is improving while ISP's is declining,
   churn risk multiplied

COMPOSITE SCORE:
priority = 0.3 × weather_risk + 0.2 × age_score + 0.2 × quality_trend_score
         + 0.2 × revenue_risk_score + 0.1 × competitive_pressure_score

OUTPUT per municipality:
- Priority score: 0-100
- Recommended action: "Pre-position splice repair crew" / "Inspect aerial cable"
  / "Check equipment temperature thresholds" / "Schedule preventive maintenance window"
- Timing: "Before forecast rain event on Tuesday" / "Within next 30 days" / "Routine"
"""
```

## API ENDPOINTS

```
GET  /api/v1/health/weather-risk?municipality_id=X
     — Current and 7-day weather risk forecast

GET  /api/v1/health/quality/{municipality_id}
     — Quality metrics with benchmarks and trends

GET  /api/v1/health/quality/{municipality_id}/peers
     — Peer comparison for quality metrics

GET  /api/v1/health/maintenance/priorities?provider_id=X
     — Ranked list of municipalities by maintenance priority

GET  /api/v1/health/seasonal/{municipality_id}
     — Historical seasonal risk calendar

POST /api/v1/health/integrate/ozmap
     — Connect OZmap account for enhanced fault prediction
```

## COMPLETION CRITERIA

1. Weather-fault correlation model trained on at least 24 months of historical data
2. Quality benchmarking produces valid comparisons for all municipalities with Anatel data
3. Maintenance priority scores generated for test ISP's service area
4. Seasonal patterns correctly identify rainy season risk elevation
5. API endpoints respond with correctly computed metrics
