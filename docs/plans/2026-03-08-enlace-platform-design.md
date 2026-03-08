# ENLACE Platform — Execution Design

## Architecture Summary

Production AI-powered telecom decision intelligence platform for Brazil.
5 phases, 50+ modules, Python/Rust/TypeScript stack.

## Execution Strategy: Phase-Sequential, Module-Parallel

Each phase: Infrastructure → Core Logic → API → Validation → Commit

## Technology Choices

| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL 16 + PostGIS 3.4 (Docker) |
| Cache | Redis 7 (Docker) |
| Object Storage | MinIO (Docker) |
| Python | 3.11+, FastAPI, SQLAlchemy, XGBoost, GeoPandas |
| Rust | 2021 edition, tonic gRPC, rayon parallelism |
| Frontend | Next.js 14, React, TypeScript, Deck.gl, Tailwind |
| PDF Reports | WeasyPrint |
| Pipeline | Lightweight async (Prefect-compatible structure) |

## Data Strategy

Pipeline code targets real APIs (Anatel, IBGE, SRTM, OSM, INMET).
Realistic synthetic seed data for all tables for validation.
~100 municipalities, 20 providers, demographics, terrain data seeded.

## Phase Dependencies

```
Phase 1 (Data) → Phase 2 (ML + RF) → Phase 3 (Regulatory + Health)
                                    → Phase 4 (Rural + UI)
                  M&A (parallel after Phase 1)
```

## Key Design Decisions

1. Multi-country from day one: every table has country_code
2. Tenant isolation: public data shared, user data isolated by tenant_id
3. gRPC bridge: Rust RF engine ↔ Python API via protobuf
4. Map-first UI: Deck.gl WebGL layers for 400k+ polygons
5. Interpretable ML: SHAP values for all scoring models
6. Brazilian vegetation corrections: published research-backed RF adjustments
