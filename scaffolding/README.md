# ENLACE — AI-Powered Telecom Decision Intelligence Platform

## For Claude Code: Read This First

This project is built by reading specification files in `specs/` sequentially.
Each spec file contains complete implementation details for one phase.

### Execution Order

1. Start infrastructure: `cd infrastructure && docker compose up -d`
2. Read and implement: `specs/phase1_data_foundation.md`
3. Run validation: `python tests/validation/phase1_validation.py`
4. Read and implement: `specs/phase2_expansion_planning.md`
5. Read and implement: `specs/phase2_rf_engine.md`
6. Run validation: `python tests/validation/phase2_validation.py`
7. Read and implement: `specs/phase3_regulatory.md`
8. Read and implement: `specs/phase3_fault_intelligence.md`
9. Read and implement: `specs/phase4_rural.md`
10. Read and implement: `specs/phase4_ui.md`
11. Read and implement: `specs/mna_standalone.md`
12. Run full integration: `python tests/integration/full_integration.py`

### Project Structure

```
enlace/
├── specs/                          # Layer 2: Component specifications
│   ├── phase1_data_foundation.md   # Database + data pipelines + multi-country
│   ├── phase2_expansion_planning.md # Market opportunity + competitive intelligence
│   ├── phase2_rf_engine.md         # Rust RF propagation + tower optimization
│   ├── phase3_regulatory.md        # Compliance engine
│   ├── phase3_fault_intelligence.md # Network health
│   ├── phase4_rural.md             # Rural connectivity planner
│   ├── phase4_ui.md                # Frontend + reports
│   └── mna_standalone.md           # M&A Intelligence product
│
├── rust/                           # Rust workspace (RF engine)
│   ├── Cargo.toml
│   └── crates/
│       ├── enlace-terrain/         # SRTM reading, terrain profiles
│       ├── enlace-propagation/     # RF propagation models + vegetation corrections
│       ├── enlace-optimizer/       # Tower placement optimization
│       ├── enlace-raster/          # GeoTIFF coverage map output
│       └── enlace-service/         # gRPC server
│
├── python/                         # Python services
│   ├── pipeline/                   # Data ingestion (Prefect flows)
│   ├── api/                        # FastAPI backend
│   ├── ml/                         # ML models (opportunity scoring, demand prediction)
│   └── regulatory/                 # Regulatory compliance engine
│
├── frontend/                       # React/TypeScript + Deck.gl
│   └── src/
│       ├── components/
│       ├── maps/                   # Map visualization layers
│       └── reports/                # PDF report generation
│
├── infrastructure/                 # Docker, CI/CD, deployment
│   ├── docker-compose.yml
│   ├── init.sql                    # Database schema
│   └── ...
│
├── data/                           # Data download scripts, sample data
│   └── scripts/
│
├── tests/                          # All tests
│   ├── unit/
│   ├── integration/
│   └── validation/                 # Real-data validation against published research
│
├── docs/                           # Documentation
├── .env.template                   # Environment configuration
└── README.md                       # This file
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| RF Engine | Rust 2021 edition |
| Data Pipeline | Python 3.11+ / Prefect |
| Backend API | Python FastAPI + gRPC |
| Frontend | TypeScript / React / Deck.gl |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Cache | Redis 7 |
| Object Storage | MinIO |
| Containers | Docker Compose |

### Key Open Source Dependencies

| Repo | Use |
|------|-----|
| github.com/thebracket/rf-signals | Rust RF propagation algorithms (Longley-Rice, HATA) |
| github.com/georust | Rust geospatial libraries |
| github.com/uber/h3 | Hexagonal spatial indexing |
| deck.gl | WebGL map visualization |
| basedosdados.org | Pre-cleaned Brazilian government datasets |

### Data Sources (Brazil)

| Source | Data | Update |
|--------|------|--------|
| Anatel | Subscribers, base stations, spectrum, quality | Monthly |
| IBGE | Census demographics, income, boundaries | Decennial + annual |
| SRTM/NASA | Terrain elevation (30m resolution) | Static |
| MapBiomas | Land use/cover classification | Annual |
| OpenStreetMap | Road network, buildings | Continuous |
| INMET | Weather observations and forecasts | Hourly |
| ANEEL | Power grid corridors | Periodic |
