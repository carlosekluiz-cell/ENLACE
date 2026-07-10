# Enlace Propagation Engine — Methodology

*Version 1.0 — July 2026. This document describes exactly what the engine
computes, from which data, with which models, and what is and is not yet
validated. It is written to be published: every claim here is reproducible
from open data and the accuracy section reports only measured results.*

## 1. Scope

Nationwide RF propagation prediction for Brazil: point-to-point link
analysis (microwave/FWA) and area coverage (macro/small cell), for any
coordinate within the national territory, with no pre-provisioning — all
geodata is fetched on demand from open sources.

## 2. Data layers (all open, all on-demand)

| Layer | Source | Resolution | Role |
|---|---|---|---|
| DTM | SRTM GL1 (NASA, via OpenTopography S3) | 30 m | Legacy terrain; C-band radar partially includes canopy |
| DSM | Copernicus GLO-30 (ESA, AWS Open Data) | 30 m | Surface incl. vegetation/buildings (smeared at 30 m) |
| Bare earth | ANADEM v1 (UFRGS/IPH, via OpenTopography) | 30 m | ML-corrected true ground: vegetation/building bias removed |
| Land cover | MapBiomas Collection 9 (2023) | 30 m | Clutter class per profile point; environment inference |
| Buildings | Google Open Buildings 2.5D Temporal (2023) | 0.5 m | Per-building heights at urban points (rooftop diffraction) |

Elevation tiles are converted to a common 1-arc-second grid (SRTM `.hgt`
convention). Land cover and building data are read as windowed HTTP range
requests against the providers' cloud-optimized GeoTIFFs — nothing is
bulk-mirrored. Ocean/no-data tiles are cached as markers.

Measured example of why three elevation surfaces matter (Amazônia,
2.95°S 60.20°W): SRTM 53 m, DSM 56 m, ANADEM bare earth 40 m — a 16 m
canopy bias that corrupts any link budget planned on SRTM alone.

## 3. Propagation models

Base path loss is dispatched by frequency and environment, with free-space
loss as a hard physical floor:

- **150–2000 MHz**: Okumura-Hata / COST-231, city size from land cover
  (urban → large city).
- **> 2000 MHz**: 3GPP TR 38.901 UMa (urban/suburban) or RMa (rural).
- **< 150 MHz**: FSPL with a generic 5.5 dB shadowing assumption.
- **Point-to-point**: ITM/Longley-Rice, ITU-R P.1812, and P.530 link
  budgets (rain per P.838, gaseous absorption per P.676) are available via
  the same engine. Rain rate R0.01 is resolved from the ITU-R P.837-7
  spatial grid at the path midpoint (Manaus ~98 mm/h, São Paulo ~63)
  rather than a single national default.

Environment (urban/suburban/rural/open) is inferred from MapBiomas pixels
around the transmitter (≥35% urban → urban; ≥10% → suburban), overridable
per request.

**Terrain interaction.** Coverage rays sample an in-memory DTM raster and
apply Deygout multiple-knife-edge diffraction (dominant obstacle plus
recursive sub-path edges), each edge per ITU-R P.526-15 §4.1
(J(v) = 6.9 + 20·log₁₀(√((v−0.1)²+1) + v − 0.1)); the effective-earth
curvature bulge uses k = 4/3. Link profiles compute first-Fresnel-zone
clearance point by point; the standard 60% clearance criterion drives the
pass/fail verdict. With building data enabled, interior profile points in
urban land cover obstruct at terrain + measured building height
(endpoints exempt — antennas clear their own structure).

Measured example (São Paulo, 2.5 km, 5.8 GHz, 25 m/12 m antennas): the
path is Fresnel-clear by 6.4× over bare earth and **blocked** (worst
clearance −43×) against Open Buildings rooftops.

## 4. Uncertainty

Every model reports its log-normal shadow-fading sigma (Hata/P.1812 per
environment; TR 38.901 spec values 4 dB LOS / 8 dB NLOS). Coverage results
carry, per grid:

- `coverage_pct` — median (P50) prediction, and
- `coverage_pct_p90` — fraction of locations where P50 − 1.282σ still
  clears the threshold (90% location confidence).

Predictions are presented as distributions, not point estimates. A
prediction without a confidence statement is marketing, not engineering.

## 5. Calibration protocol (fleet-as-sensor)

The engine maintains a measurement store (`rf_measurements`) accepting
geolocated received-power samples from: ISP CPE telemetry, Anatel EMF
conformity campaigns (E-field converted via S = E²/377, Aeff = λ²/4π),
SIMET probes, and drive tests. Each measurement with known transmitter
parameters is scored against the engine's prediction; the residual is
stored with the environment, clutter class, and model used.

- The **benchmark** (bias, σ, RMSE — overall and per environment/clutter/
  model) is only reported once ≥100 residuals exist.
- **Corrections** (per-environment bias applied back onto predictions) are
  only activated for groups with ≥30 samples, and every corrected response
  is labelled `calibration_applied`.

This loop compounds: each deployed CPE improves the model for everyone.

## 6. Current validation status — Benchmark v1 (July 2026)

First measured benchmark, computed from **1,715,227 Anatel RNI
measurements (2005–2025)** attributed to licensed stations by station
number and scored against a near-station composite prediction
(free-space power-density sum over the station's carrier bands — the
engine's own short-range behavior — with documented typical-EIRP per
band and a 1-of-3-sectors-facing heuristic; the registry omits
per-station power):

| Slice | n | bias (dB) | σ (dB) |
|---|---|---|---|
| Overall | 1,715,227 | −23.7 | 10.3 |
| 0–500 m | 1,661,203 | −24.4 | 9.7 |
| 500–1000 m | 29,968 | −6.7 | 7.7 |
| 1000–1500 m | 14,645 | −2.1 | 7.5 |
| 1500–2000 m | 9,411 | **+0.9** | **7.4** |
| 2005–2009 | 3,978 | −28.3 | 12.3 |
| 2020–2024 | 419,465 | −22.3 | 9.7 |
| Urban (MapBiomas) | 1,287,804 | −23.8 | 10.1 |
| Rural | 176,675 | −22.8 | 11.7 |
| Forest clutter | 37,193 | −22.6 | 12.3 |
| Water clutter | 2,049 | **−19.1** | 12.2 |

**Interpretation.** The large near-tower bias is the vertical antenna
pattern: probes under the tower sit below the downtilted main beam, so an
isotropic free-space composite over-predicts — the bias decays
monotonically with distance and vanishes (+0.9 dB) at 1.5–2 km where the
main lobe reaches ground level. σ of 7.4–10.3 dB matches the literature
band for uncalibrated empirical models. Clutter structure is physically
coherent: water/wetland paths lose ~4 dB less than land, forest spreads
widest. Environment/clutter classification (MapBiomas at each point)
covers 88% of residuals; the remainder fall in no-data cells. All
findings are structural and therefore learnable — the Phase-2 correction
model adds an elevation-angle/beam term and per-band decomposition.

**Calibrated model v1 (held-out evaluation).** Fitting a per-environment
log-distance correction (residual ≈ a + b·log₁₀ d; slope 17.6–19.2
dB/decade, consistent with sector vertical-pattern elevation angle) on an
80% training split and evaluating on the untouched 20%:

| Environment | n (held-out) | RMSE uncorrected | RMSE calibrated |
|---|---|---|---|
| Urban | 257,446 | 25.8 dB | **7.0 dB** |
| Suburban | 13,625 | 26.1 dB | **7.6 dB** |
| Rural | 35,621 | 25.6 dB | **8.3 dB** |

The calibrated near-station field model is therefore accurate to 7–8 dB
(1σ) out-of-sample.

**Per-band decomposition (v2).** Measurements at single-band stations
isolate frequency behavior. After the distance/environment correction,
low bands out-perform the composite assumption (700 MHz +11.8 dB,
900 +11.3, 850 +6.5) and high bands sit near it (2500 +1.4, 1800 +3.0,
2100 +8.1) — directionally consistent with frequency-dependent clutter
absorption, though entangled with per-band EIRP practice (low-band
coverage layers typically run closer to licensed maxima). Adding these
offsets (fitted on the training split) improves the single-band held-out
subset from 9.97 to **8.02 dB RMSE** (n = 6,980). Corrections remain in
the field domain; engine-side application is gated on disentangling the
EIRP term.

**Caveats.** Measured values are broadband total-field spot measurements
(coarser than per-carrier drive-test bins); EIRP is assumed at typical
licensed levels, so absolute bias conflates antenna pattern with power
assumptions; environment/clutter classification of measurement points is
in progress (MapBiomas). Field-domain composite residuals are kept
separate from path-loss-domain corrections — the coverage correction
table only activates on domain-matched, environment-classified groups.

Every number above is reproducible: data sources are public (Anatel RNI
measurements + SMP licensing registry), and the scoring SQL ships in
`scripts/benchmark_v1.sql`.

## 7. Known limitations

- Vegetation attenuation applies biome-level corrections, not per-point
  canopy depth (per-point vegetation is on the roadmap; the DSM surface
  already captures canopy as an obstruction geometrically).
- Open Buildings heights are ML estimates from satellite imagery (2023
  snapshot); new construction since then is absent.
- Building entry loss (ITU-R P.2109-2, traditional/thermally-efficient
  classes) is applied for indoor terminals on link budgets; coverage grids
  remain outdoor-only.
