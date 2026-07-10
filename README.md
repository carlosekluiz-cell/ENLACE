# ENLACE

Telecom intelligence for ISPs in Brazil and Latin America — market
intelligence, network design, and a nationwide RF propagation engine with a
**measured, field-calibrated accuracy benchmark**.

## Highlight: the propagation engine (July 2026)

Click anywhere in Brazil and plan a link or a coverage footprint on real
data, fetched on demand:

| Layer | Source | Resolution |
|---|---|---|
| Terrain (3 surfaces) | SRTM GL1 · Copernicus GLO-30 DSM · ANADEM bare earth | 30 m |
| Land cover / clutter | MapBiomas Collection 9 | 30 m |
| Building heights | Google Open Buildings 2.5D | 0.5 m |

Models: Okumura-Hata, 3GPP TR 38.901, ITM, ITU-R P.1812/P.530/P.526 (Deygout
multi-edge)/P.837 regional rain/P.2109 building entry loss — dispatched by
frequency and MapBiomas-inferred environment, with P50/P90 uncertainty on
every coverage grid.

**Validated against 1.7 million Anatel field measurements** (2005–2025),
joined to the daily-refreshed SMP licensing registry. Held-out accuracy of
the calibrated model: **7.0 dB RMSE urban · 7.6 suburban · 8.3 rural**.
Full method, assumptions and reproduction recipe:
[`docs/propagation-methodology.md`](docs/propagation-methodology.md).

## Layout

```
rust/            RF engine (pulso-propagation, pulso-terrain, pulso-service…)
python/api/      FastAPI backend (design, calibration, intelligence routers)
python/pipeline/ data ingestion flows
frontend/        Next.js app (pt-BR) — /propagacao is the planner
scripts/         ingestion, benchmark & calibration scripts; start_stack.sh
docs/            methodology, whitepapers, specs
tests/           pytest suite (497 tests) + Playwright e2e script
```

## Quick start (dev box)

```bash
cargo build --release -p pulso-service   # once
bash scripts/start_stack.sh              # engine :50051 · API :8897 · app :3901
# tests
set -a; source .env; set +a
DEV_MODE=0 JWT_SECRET_KEY=test-secret python3 -m pytest tests/ --ignore=tests/integration
```

## Status & next steps

- **Done**: nationwide data layers · calibrated engine · 3.88 M measurements
  ingested · benchmark published · planner UI verified end-to-end (Playwright).
- **Next**: commit current work (all of the above is on
  `pilot-green-finishing-pass`, uncommitted) · engine-side application of the
  measured corrections (needs per-station EIRP) · fleet-as-sensor continuous
  calibration (starts with the first ISP pilot) · GPU ray tracing + ML
  surrogate for instant nationwide maps.

Operational detail and risks live in [`CLAUDE.md`](CLAUDE.md) — kept current
at every step.
