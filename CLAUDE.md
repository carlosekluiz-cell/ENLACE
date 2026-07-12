# ENLACE — Claude operating notes

**Discipline: update this file (and README.md) at the end of every working
step.** Sessions die; this file is the survival state. Last update: 2026-07-11.

## What this repo is

Telecom intelligence platform for Brazilian/LatAm ISPs (Pulso/Enlace brand),
plus a UK FTTH pilot track. The flagship as of July 2026 is the **nationwide
RF propagation engine with a measured, field-calibrated accuracy benchmark**
— see `docs/propagation-methodology.md` (the single source of truth for the
model chain and its validated numbers).

## Current state (2026-07-10) — the propagation frontier

Everything below is **built, tested (497 pytest + 19/19 Playwright e2e,
Rust suites green) and UNCOMMITTED on branch `pilot-green-finishing-pass`**.

1. **Data layers, on-demand for any BR coordinate** (no bulk mirrors except
   land cover): SRTM GL1 (dtm), Copernicus GLO-30 (dsm), ANADEM v1 bare earth
   (ground) — all as .hgt tiles in `data/terrain/{dtm,dsm,ground}/`;
   MapBiomas C9 clutter (`data/terrain/landcover/*.lc`, 575 land tiles,
   ~7 GB); Google Open Buildings 2.5D point queries (manifest index cached in
   `data/terrain/buildings/`). Fetch logic: `python/api/services/terrain_tiles.py`,
   `buildings.py`.
2. **Engine** (`rust/crates/pulso-*`, binary `rust/target/release/pulso-rf-engine`):
   env-dispatched base loss (Hata/TR 38.901/FSPL floor), Deygout multi-edge
   terrain diffraction (P.526 knife edge — the old Lee quadratic exploded and
   was fixed), per-point sigma → P50/P90 coverage, 3 tile caches
   (SRTM/DSM/GROUND _TILE_DIR envs), `surface` + `environment` proto fields.
3. **API** (`python/api/routers/design.py`): profile with Fresnel
   `link_analysis` (+ Open Buildings rooftops via `buildings=true`),
   `/elevation` (all surfaces + clutter + building height), coverage with
   MapBiomas-inferred environment + P90 + `calibration_applied`, linkbudget
   with ITU-R P.837 regional rain (`mid_lat/mid_lon`) and P.2109 building
   entry loss (`rx_indoor`), terrain status/ensure, calibration endpoints.
4. **Calibration loop** (`python/api/services/calibration.py`):
   - `rf_measurements`: **3.88 M Anatel RNI/EMF measurements** ingested
     (`scripts/ingest_rni.py`; quirks: \r-only line endings, utf-8-sig BOM,
     decimal commas, "N/I" placeholders).
   - `anatel_stations`: **3.24 M carrier-sector licensing rows** (112 k
     stations) from
     `https://www.anatel.gov.br/dadosabertos/paineis_de_dados/outorga_e_licenciamento/estacoes_smp.zip`
     (updated daily; fetchable from this box — most other Anatel hosts are NOT).
   - `rf_residuals`: **1.72 M tier-1 residuals** (`scripts/benchmark_v1.sql`,
     near-station composite, field domain), env/clutter-classified via
     MapBiomas (`scripts/classify_residuals.py`).
   - `rf_correction_curves` + `rf_calibration_eval` (`scripts/fit_corrections.sql`):
     per-env a+b·log10(d); **held-out RMSE 25.8→7.0 dB urban, 7.6 suburban,
     8.3 rural** (n_test 343 k). `rf_band_offsets`: per-band from single-band
     stations (700 MHz +11.8 dB … 2500 +1.4); band-aware v2 = 8.02 dB on the
     single-band held-out subset.
   - Published artifact: https://claude.ai/code/artifact/3bf9cf26-1e7d-45bc-9b14-4d831c64cdcb
5. **Frontend**: `/propagacao` planner (deck.gl click-anywhere, DSM/DTM/SOLO
   toggle, buildings checkbox, P50/P90, calibration chip, equipment presets,
   address search, sector antennas, save/load projects, PDF/KMZ/GeoJSON export).
6. **PUBLIC as of 2026-07-11 (PROD-6)**: the planner is LIVE at
   `https://app.enlace.network` (login/register → /propagacao). nginx routes
   `/api/` → FastAPI :8897 (same-origin, no CORS), `/` → Next :3901,
   `/umami/` → agent analytics. Three systemd units (enabled, auto-restart):
   `enlace-rf-engine` (:50051), `enlace-rf-api` (:8897, **DEV_MODE=0** — real
   auth enforced, anonymous 401), `enlace-rf-app` (:3901). Unit sources
   versioned in `deploy/systemd/`. **19/19 Playwright e2e pass against the
   public URL** (`E2E_BASE=https://app.enlace.network python3
   scripts/e2e_propagacao_ui.py`).
   **Gotcha that bit twice**: systemd `EnvironmentFile` OVERRIDES `Environment=`
   lines regardless of order — `DEV_MODE` and `RF_ENGINE_TLS_CA` were therefore
   REMOVED from `.env` (start_stack.sh sets DEV_MODE=1 explicitly for dev).
   Marketing site pricing CTAs (Teste/WISP) now link to the app's login page.

## Runbook

- **Start everything**: `bash scripts/start_stack.sh` (engine :50051, API
  :8897, frontend :3901; logs in `logs/`). Never `pkill -f` long name
  patterns — it matches your own shell.
- **Public upload page** (nginx-exposed, token-gated):
  `https://api.enlace.network/calibration/upload-ui?token=$CALIBRATION_UPLOAD_TOKEN`
  (token in `.env`). nginx locations in `/etc/nginx/sites-enabled/enlace`
  (backup `.enlace.bak-calibration`). Accepts CSV/TXT/ZIP/ODT, multi-file;
  raw uploads persisted to `data/uploads/`.
- **Refit after new measurements**: run `scripts/benchmark_v1.sql` →
  `scripts/classify_residuals.py` → `scripts/fit_corrections.sql`
  (psql with `SET statement_timeout = 0`).
- **Tests**: `set -a; source .env; set +a; DEV_MODE=0 JWT_SECRET_KEY=test-secret
  python3 -m pytest tests/ --ignore=tests/integration` (DB creds in `.env`;
  the `enlace` role password was reset 2026-07-10 to match). E2E:
  `python3 scripts/e2e_propagacao_ui.py` (needs stack up; PIN 2707; test user
  e2e-test@enlace.dev / E2eTest!2026).
- **GDAL warning**: system `osgeo.gdal` is numpy-1.x built — use rasterio.
- **DB heavy ops**: default statement_timeout kills big index builds; use
  `SET statement_timeout = 0`.

## Risks / active watches

- **DISK (prod box 144.76.2.72, shared)**: hit 100% twice on 2026-07-10.
  An unrelated project (`/home/dev/gis`) downloads ~4.7 GB Sentinel-1
  scenes and can fill the disk, taking shared Postgres down. Emergency
  levers used (rerunnable): delete `data/terrain/landcover/` (7 GB,
  re-fetch with the prefetch snippet ~40 min — REQUIRED before running
  `scripts/classify_residuals.py`), truncate `/var/log/kern.log`. A
  session watchdog pauses tier-2 scoring below 4 GB. Check `df -h /`
  before any large job.
- **Disk crisis RESOLVED 2026-07-10 ~23:30**: sibling geodesia session
  freed its 13 GB scene zips after a coordination note in its BLOCKERS.md
  (the working channel between sessions on this box) → 24 G free. A 512 M
  Postgres ballast remains at `/home/dev/enlace/.pg-emergency-ballast`
  (delete only to give PG emergency headroom).
- **Tier-2 proximity scoring** (`scripts/benchmark_v2_proximity.py`,
  `logs/tier2.log`): RUNNING (resumed 23:30 from 120 k / 2.08 M; ~50-80
  rows/s ≈ overnight). Resumable — rerun the script and it continues.
  **Landcover prefetch DEFERRED** — running it concurrently with the
  geodesia session's SNAP processing (multi-GB transient temps) spiked the
  disk to 0 at 2026-07-10 23:59 (PG survived; ballast + cleanup recovered
  22 G). Rule: only run the 7 GB landcover prefetch when the sibling
  pipeline is quiet AND >12 G free, ideally with a free-space guard in the
  loop. After tier-2 scoring completes: prefetch landcover, run
  classify_residuals with WHERE extended to model='composite_v2_prox',
  fit tier-2 curves, update methodology doc + validation artifact.
- **pkill -f is a footgun on this box**: patterns match your own shell and
  Monitor scripts (exit 144). Use `pgrep -f 'name[_]part'` bracket trick
  or kill by port (`fuser -k PORT/tcp`).
- **`/home/dev/ENLACE/data/uk` (60 GB) is LIVE production data** (user
  confirmed 2026-07-11) — serves the UK pilot (pulso-uk-api reads it).
  Never delete, move, or compress it.
- Disk reclaim done 2026-07-11: docker build cache (12.6 G) + unused
  images (2.7 G) pruned → 30 G free. Next candidates if needed: 24 unused
  docker volumes (74 G "reclaimable" but volumes hold data — inspect names
  with `sudo docker volume ls -f dangling=true` and prune only clearly-dead
  ones, with user).
- Core propagation work **committed (d17ea4f) and pushed** to
  origin/pilot-green-finishing-pass on 2026-07-10 as disk-crisis protection.
  Remaining untracked files (PDFs, screenshots, data/, other subprojects)
  intentionally not committed.
- Tier-2 scoring PAUSED at ~120k/2.08M (disk contention with the
  geodesia/worldtwin session's Sentinel downloads — `worldtwin-sentinel`
  poller still active). Resume `scripts/benchmark_v2_proximity.py` when
  `df -h /` shows >8G free.
- passlib was replaced by `python/api/auth/passwords.py` (bcrypt 5
  incompatibility broke all login) — don't reintroduce passlib.

## Next steps (in order of value)

1. **PRODUCTIZATION SPRINT COMPLETE (2026-07-11)** — PROD-1..7 all shipped.
   PROD-7 prospectuses: `scripts/prospectus.py` generates 9 per-client PDFs
   (pt-BR, only verified numbers) → `outputs/prospectus/` AND published at
   `https://enlace.network/prospectos/enlace-prospecto-{01..09}-*.pdf`
   (site `public/prospectos/`; rebuild site to update).
   **Whitepaper (2026-07-12, designed edition)**: `scripts/whitepaper_html.py`
   (HTML -> Chromium PDF via Playwright; Fraunces/Inter/IBM Plex Mono in
   `assets/fonts/`, petrol cover, 6 SVG diagrams, 12 hand-paginated pages),
   LIVE at `enlace.network/whitepaper/enlace-rf-whitepaper.pdf` (linked from
   /validation). Numbers from rf_calibration_eval/rf_band_offsets. The old
   reportlab generator was removed; regenerate + copy to site public/ +
   rebuild site to update.
2. **Payment integration LAST** (user directive): pricing published at
   https://enlace.network/pricing; activation by contact until then. This is
   the only remaining productization item and starts only on user's go.
3. **Engine-side correction application**: gated on disentangling per-band
   EIRP practice from propagation — needs real station powers (technical
   Mosaico export, not URL-accessible) or pilot fleet telemetry.
4. **Phase 3 fleet-as-sensor**: pulso-agent CPE telemetry → continuous
   calibration. Gated on a signed pilot.
5. **Phase 4**: GPU ray tracing over Open Buildings; ML surrogate for
   instant nationwide maps. Weeks-scale.
