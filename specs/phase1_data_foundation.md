# ENLACE — Phase 1: Data Foundation Specification
# Component 1 + Component 8 (Multi-Country Architecture)
# This file is read by Claude Code before building the data layer.

## OVERVIEW

Build the complete data ingestion, storage, and serving layer for all open data sources.
Everything else in the platform depends on this component being correct and complete.

The multi-country abstraction (Component 8) is built INTO this phase, not after it.
Every table, every pipeline, every API endpoint includes country_code from day one.

## PREREQUISITES

Before starting this spec:
1. PostgreSQL 16 with PostGIS 3.4 must be running (via Docker)
2. Redis 7 must be running (via Docker)  
3. MinIO must be running (via Docker)
4. Python 3.11+ with virtual environment
5. Rust toolchain installed via rustup

## DATABASE SETUP

### Step 1: Create PostgreSQL with PostGIS

```sql
-- Run via psql or migration script
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for text search
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- for range queries

-- TimescaleDB for time-series data (Anatel monthly metrics)
-- Install via: CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Step 2: Core Schema — Geographic Entities

```sql
-- Countries (Multi-country foundation)
CREATE TABLE countries (
    code CHAR(2) PRIMARY KEY,  -- ISO 3166-1 alpha-2
    name VARCHAR(100) NOT NULL,
    name_local VARCHAR(100) NOT NULL,  -- name in local language
    currency_code CHAR(3) NOT NULL,  -- ISO 4217
    language_code VARCHAR(10) NOT NULL,  -- BCP 47
    regulator_name VARCHAR(200),
    regulator_url VARCHAR(500),
    national_crs INTEGER,  -- EPSG code (Brazil: 4674 SIRGAS 2000)
    timezone VARCHAR(50),
    bounding_box BOX2D,  -- geographic extent for validation
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO countries VALUES 
('BR', 'Brazil', 'Brasil', 'BRL', 'pt-BR', 'Anatel', 'https://www.anatel.gov.br', 4674, 'America/Sao_Paulo', 
 ST_MakeBox2D(ST_Point(-73.99, -33.77), ST_Point(-28.83, 5.27)));

-- Administrative Level 1 (States/Provinces)
CREATE TABLE admin_level_1 (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    code VARCHAR(10) NOT NULL,  -- Brazil: UF code (e.g., '35' for SP)
    name VARCHAR(200) NOT NULL,
    abbrev VARCHAR(10),  -- Brazil: 'SP', 'RJ', 'MG'
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    UNIQUE(country_code, code)
);
CREATE INDEX idx_al1_geom ON admin_level_1 USING GIST(geom);
CREATE INDEX idx_al1_country ON admin_level_1(country_code);

-- Administrative Level 2 (Municipalities)
CREATE TABLE admin_level_2 (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    l1_id INTEGER REFERENCES admin_level_1(id),
    code VARCHAR(20) NOT NULL,  -- Brazil: IBGE municipality code (7 digits)
    name VARCHAR(200) NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    centroid GEOMETRY(POINT, 4326),
    UNIQUE(country_code, code)
);
CREATE INDEX idx_al2_geom ON admin_level_2 USING GIST(geom);
CREATE INDEX idx_al2_l1 ON admin_level_2(l1_id);
CREATE INDEX idx_al2_country ON admin_level_2(country_code);

-- Census Tracts (Setores Censitários)
CREATE TABLE census_tracts (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    l2_id INTEGER REFERENCES admin_level_2(id),
    code VARCHAR(20) NOT NULL,  -- Brazil: 15-digit setor code
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    centroid GEOMETRY(POINT, 4326),
    situation VARCHAR(10),  -- 'urban' or 'rural'
    tract_type VARCHAR(50),  -- operational type from IBGE
    UNIQUE(country_code, code)
);
CREATE INDEX idx_ct_geom ON census_tracts USING GIST(geom);
CREATE INDEX idx_ct_l2 ON census_tracts(l2_id);
CREATE INDEX idx_ct_country ON census_tracts(country_code);
```

### Step 3: Demographic Entities

```sql
CREATE TABLE census_demographics (
    id SERIAL PRIMARY KEY,
    tract_id INTEGER REFERENCES census_tracts(id),
    census_year INTEGER NOT NULL,
    total_population INTEGER,
    total_households INTEGER,
    occupied_households INTEGER,
    avg_residents_per_household NUMERIC(4,2),
    -- Income brackets (Brazil Censo 2022 categories)
    income_data JSONB,
    -- Structure: {
    --   "avg_per_capita_brl": 1850.00,
    --   "median_per_capita_brl": 1200.00,
    --   "brackets": {
    --     "below_half_min_wage": 120,
    --     "half_to_one_min_wage": 200,
    --     "one_to_two_min_wage": 350,
    --     "two_to_five_min_wage": 180,
    --     "five_to_ten_min_wage": 40,
    --     "above_ten_min_wage": 10
    --   }
    -- }
    education_data JSONB,
    -- Structure: { "no_education": N, "elementary": N, "high_school": N, "university": N }
    housing_data JSONB,
    -- Structure: { "owned": N, "rented": N, "water_supply": N, "sewage": N, "electricity": N }
    UNIQUE(tract_id, census_year)
);
CREATE INDEX idx_cd_tract ON census_demographics(tract_id);

CREATE TABLE population_projections (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    projected_population INTEGER,
    growth_rate NUMERIC(6,4),  -- annual growth rate
    source VARCHAR(100),
    UNIQUE(l2_id, year)
);

CREATE TABLE economic_indicators (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    pib_municipal_brl NUMERIC(15,2),
    pib_per_capita_brl NUMERIC(10,2),
    formal_employment INTEGER,
    sector_breakdown JSONB,
    -- Structure: { "agriculture": N, "industry": N, "services": N, "public_admin": N }
    source VARCHAR(100),
    UNIQUE(l2_id, year)
);
```

### Step 4: Telecom Market Entities

```sql
CREATE TABLE providers (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    name VARCHAR(300) NOT NULL,
    name_normalized VARCHAR(300) NOT NULL,  -- lowercase, no accents, trimmed
    national_id VARCHAR(30),  -- Brazil: CNPJ
    classification VARCHAR(20),  -- 'PPP', 'PMP', 'PGP' (Brazil Anatel categories)
    services JSONB,  -- ['SCM', 'SMP', 'STFC', 'SeAC']
    status VARCHAR(20) DEFAULT 'active',
    first_seen_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_prov_country ON providers(country_code);
CREATE INDEX idx_prov_name ON providers USING GIN(name_normalized gin_trgm_ops);

CREATE TABLE broadband_subscribers (
    id BIGSERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES providers(id),
    l2_id INTEGER REFERENCES admin_level_2(id),
    year_month CHAR(7) NOT NULL,  -- '2025-06'
    technology VARCHAR(20) NOT NULL,  -- 'fiber', 'cable', 'dsl', 'wireless', 'satellite', 'other'
    subscribers INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bs_provider ON broadband_subscribers(provider_id);
CREATE INDEX idx_bs_l2 ON broadband_subscribers(l2_id);
CREATE INDEX idx_bs_yearmonth ON broadband_subscribers(year_month);
CREATE INDEX idx_bs_l2_ym ON broadband_subscribers(l2_id, year_month);
-- Convert to TimescaleDB hypertable for efficient time-series queries:
-- SELECT create_hypertable('broadband_subscribers', 'year_month');

CREATE TABLE base_stations (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    provider_id INTEGER REFERENCES providers(id),
    station_id VARCHAR(50),  -- Anatel STEL station number
    geom GEOMETRY(POINT, 4326) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    technology VARCHAR(10) NOT NULL,  -- '2G', '3G', '4G', '5G'
    frequency_mhz DOUBLE PRECISION,
    bandwidth_mhz DOUBLE PRECISION,
    antenna_height_m DOUBLE PRECISION,
    azimuth_degrees DOUBLE PRECISION,
    mechanical_tilt DOUBLE PRECISION,
    power_watts DOUBLE PRECISION,
    authorization_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    raw_data JSONB,  -- store full original record for reference
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bs_geom ON base_stations USING GIST(geom);
CREATE INDEX idx_bs_provider ON base_stations(provider_id);
CREATE INDEX idx_bs_tech ON base_stations(technology);
CREATE INDEX idx_bs_freq ON base_stations(frequency_mhz);
CREATE INDEX idx_bs_country ON base_stations(country_code);

CREATE TABLE spectrum_licenses (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    provider_id INTEGER REFERENCES providers(id),
    frequency_start_mhz DOUBLE PRECISION NOT NULL,
    frequency_end_mhz DOUBLE PRECISION NOT NULL,
    bandwidth_mhz DOUBLE PRECISION,
    geographic_area VARCHAR(200),  -- description or polygon
    geographic_geom GEOMETRY(MULTIPOLYGON, 4326),
    license_type VARCHAR(50),
    grant_date DATE,
    expiry_date DATE,
    conditions JSONB,
    source VARCHAR(200)
);

CREATE TABLE quality_indicators (
    id BIGSERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    provider_id INTEGER REFERENCES providers(id),
    year_month CHAR(7) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    -- Types: 'download_speed_mbps', 'upload_speed_mbps', 'latency_ms', 
    -- 'availability_pct', 'complaint_rate', 'ida_score'
    value DOUBLE PRECISION NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_qi_l2_ym ON quality_indicators(l2_id, year_month);
```

### Step 5: Terrain and Environmental Entities

```sql
CREATE TABLE terrain_tiles (
    id SERIAL PRIMARY KEY,
    tile_name VARCHAR(50) NOT NULL,  -- e.g., 'S23W044.hgt'
    filepath VARCHAR(500) NOT NULL,  -- path in MinIO object storage
    bbox GEOMETRY(POLYGON, 4326) NOT NULL,
    resolution_m DOUBLE PRECISION NOT NULL,  -- 30 for 1-arc-sec SRTM
    source VARCHAR(50) NOT NULL,  -- 'SRTM', 'ALOS', 'ASTER'
    file_size_bytes BIGINT,
    loaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tt_bbox ON terrain_tiles USING GIST(bbox);

CREATE TABLE land_cover (
    id BIGSERIAL PRIMARY KEY,
    h3_index VARCHAR(20) NOT NULL,  -- H3 hexagonal cell index at resolution 8
    cover_type VARCHAR(50) NOT NULL,
    -- Types from MapBiomas: 'forest', 'savanna', 'mangrove', 'plantation',
    -- 'wetland', 'grassland', 'agriculture', 'pasture', 'urban', 'mining',
    -- 'water', 'bare_soil', 'other'
    biome VARCHAR(50),  -- 'amazonia', 'cerrado', 'mata_atlantica', 'caatinga', 'pampa', 'pantanal'
    cover_pct DOUBLE PRECISION,  -- % of cell covered by this type
    year INTEGER NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_lc_h3 ON land_cover(h3_index);
CREATE INDEX idx_lc_biome ON land_cover(biome);

CREATE TABLE biome_rf_corrections (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    biome_type VARCHAR(50) NOT NULL,  -- matches land_cover.biome or cover_type
    frequency_min_mhz DOUBLE PRECISION NOT NULL,
    frequency_max_mhz DOUBLE PRECISION NOT NULL,
    additional_loss_db_min DOUBLE PRECISION NOT NULL,
    additional_loss_db_max DOUBLE PRECISION NOT NULL,
    additional_loss_db_mean DOUBLE PRECISION,
    additional_loss_db_stddev DOUBLE PRECISION,
    measurement_distance_range VARCHAR(50),  -- e.g., '100m-2km'
    source_paper VARCHAR(500) NOT NULL,
    source_institution VARCHAR(200),
    source_year INTEGER,
    confidence VARCHAR(20),  -- 'high', 'medium', 'low'
    notes TEXT
);

-- Pre-populate with known Brazilian corrections
INSERT INTO biome_rf_corrections (country_code, biome_type, frequency_min_mhz, frequency_max_mhz, 
    additional_loss_db_min, additional_loss_db_max, additional_loss_db_mean, source_paper, source_institution, source_year, confidence) VALUES
('BR', 'cerrado', 700, 800, 4.0, 8.0, 6.0, 
 'Propagation Model for Path Loss Through Vegetated Environments at 700-800 MHz Band (SciELO JMOEA)', 
 'Brazilian researchers', 2019, 'high'),
('BR', 'mata_atlantica', 900, 1800, 8.0, 15.0, 11.5,
 'An Empirical Model for Propagation Loss Through Tropical Woodland in Urban Areas at UHF (IEEE)',
 'PUC-Rio / CETUC', 2010, 'high'),
('BR', 'amazonia', 900, 1800, 15.0, 30.0, 22.0,
 'Path loss model for densely arboreous cities in Amazon Region (IEEE)',
 'UFPA Pará', 2005, 'high'),
('BR', 'caatinga', 700, 1800, 2.0, 5.0, 3.5,
 'Estimated from vegetation density analysis — needs field validation',
 'Platform estimate', 2026, 'low'),
('BR', 'amazonia_urban', 5800, 5800, 10.0, 25.0, 17.0,
 'Comparison of propagation models at 5.8 GHz in Amazon Region cities (SciELO) — 12 cities in Pará',
 'UFPA Pará', 2011, 'high'),
('BR', 'vegetation_general', 36600, 36600, 15.0, 40.0, 27.0,
 'Polarimetric Vegetation Propagation Measurements at 36.6 GHz (IEEE) — UFMG campus',
 'UFMG', 2024, 'medium');

CREATE TABLE weather_stations (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    station_code VARCHAR(20) NOT NULL,
    name VARCHAR(200),
    geom GEOMETRY(POINT, 4326) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation_m DOUBLE PRECISION,
    station_type VARCHAR(50),  -- 'automatic', 'conventional'
    active BOOLEAN DEFAULT TRUE,
    UNIQUE(country_code, station_code)
);
CREATE INDEX idx_ws_geom ON weather_stations USING GIST(geom);

CREATE TABLE weather_observations (
    station_id INTEGER REFERENCES weather_stations(id),
    observed_at TIMESTAMPTZ NOT NULL,
    precipitation_mm DOUBLE PRECISION,
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    wind_speed_ms DOUBLE PRECISION,
    wind_direction_deg DOUBLE PRECISION,
    pressure_hpa DOUBLE PRECISION,
    solar_radiation_wm2 DOUBLE PRECISION,
    PRIMARY KEY (station_id, observed_at)
);
-- Convert to TimescaleDB hypertable:
-- SELECT create_hypertable('weather_observations', 'observed_at');
```

### Step 6: Infrastructure Corridor Entities

```sql
CREATE TABLE road_segments (
    id BIGSERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    osm_id BIGINT,
    highway_class VARCHAR(30),  -- 'motorway', 'primary', 'secondary', 'tertiary', 'residential', 'track'
    name VARCHAR(300),
    surface_type VARCHAR(30),  -- 'paved', 'unpaved', 'gravel', 'dirt'
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_m DOUBLE PRECISION
);
CREATE INDEX idx_rs_geom ON road_segments USING GIST(geom);
CREATE INDEX idx_rs_class ON road_segments(highway_class);

CREATE TABLE power_lines (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    voltage_kv DOUBLE PRECISION,
    operator_name VARCHAR(200),
    line_type VARCHAR(30),  -- 'transmission', 'distribution'
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_pl_geom ON power_lines USING GIST(geom);

CREATE TABLE railways (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    operator_name VARCHAR(200),
    gauge_mm INTEGER,
    status VARCHAR(20),  -- 'active', 'inactive', 'planned'
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_rw_geom ON railways USING GIST(geom);
```

### Step 7: Materialized Views for Common Queries

```sql
-- Market summary per municipality — the most frequently queried view
CREATE MATERIALIZED VIEW mv_market_summary AS
SELECT 
    al2.id AS l2_id,
    al2.country_code,
    al2.code AS municipality_code,
    al2.name AS municipality_name,
    al1.abbrev AS state_abbrev,
    al2.centroid,
    -- Latest subscriber data
    latest.year_month,
    latest.total_subscribers,
    latest.fiber_subscribers,
    latest.provider_count,
    -- Demographics
    cd.total_households,
    cd.total_population,
    (cd.income_data->>'avg_per_capita_brl')::NUMERIC AS avg_income,
    -- Computed metrics
    CASE WHEN cd.total_households > 0 
         THEN ROUND(latest.total_subscribers::NUMERIC / cd.total_households * 100, 1)
         ELSE 0 END AS broadband_penetration_pct,
    CASE WHEN latest.total_subscribers > 0
         THEN ROUND(latest.fiber_subscribers::NUMERIC / latest.total_subscribers * 100, 1)
         ELSE 0 END AS fiber_share_pct
FROM admin_level_2 al2
JOIN admin_level_1 al1 ON al2.l1_id = al1.id
LEFT JOIN census_demographics cd ON cd.tract_id IS NULL  -- aggregate level TBD
LEFT JOIN LATERAL (
    SELECT 
        bs.year_month,
        SUM(bs.subscribers) AS total_subscribers,
        SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) AS fiber_subscribers,
        COUNT(DISTINCT bs.provider_id) AS provider_count
    FROM broadband_subscribers bs
    WHERE bs.l2_id = al2.id
    AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers WHERE l2_id = al2.id)
    GROUP BY bs.year_month
) latest ON TRUE
WHERE al2.country_code = 'BR';

CREATE UNIQUE INDEX idx_mvms_l2 ON mv_market_summary(l2_id);
CREATE INDEX idx_mvms_geom ON mv_market_summary USING GIST(centroid);

-- Refresh command (run after each Anatel data update):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_market_summary;
```

### Step 8: Computed Metrics Tables

```sql
-- Opportunity scores per geographic unit (populated by ML pipeline)
CREATE TABLE opportunity_scores (
    id BIGSERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    geographic_type VARCHAR(20) NOT NULL,  -- 'census_tract', 'h3_cell', 'municipality'
    geographic_id VARCHAR(30) NOT NULL,  -- tract code, h3 index, or municipality code
    centroid GEOMETRY(POINT, 4326),
    computed_at TIMESTAMPTZ NOT NULL,
    -- Score components (all 0-100)
    demand_score DOUBLE PRECISION,
    competition_score DOUBLE PRECISION,
    infrastructure_score DOUBLE PRECISION,
    growth_score DOUBLE PRECISION,
    composite_score DOUBLE PRECISION,
    confidence DOUBLE PRECISION,  -- 0-1
    -- Input features preserved for explainability
    features JSONB,
    model_version VARCHAR(50)
);
CREATE INDEX idx_os_geom ON opportunity_scores USING GIST(centroid);
CREATE INDEX idx_os_composite ON opportunity_scores(composite_score DESC);
CREATE INDEX idx_os_country_type ON opportunity_scores(country_code, geographic_type);

-- Competitive analysis per municipality
CREATE TABLE competitive_analysis (
    id BIGSERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    year_month CHAR(7) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    hhi_index DOUBLE PRECISION,  -- Herfindahl-Hirschman Index (market concentration)
    leader_provider_id INTEGER REFERENCES providers(id),
    leader_market_share DOUBLE PRECISION,
    provider_details JSONB,
    -- Structure: [{"provider_id": N, "name": "X", "subscribers": N, "share_pct": N, "technology": "fiber", "growth_3m": 0.05}]
    growth_trend VARCHAR(20),  -- 'growing', 'stable', 'declining'
    threat_level VARCHAR(20),  -- 'low', 'medium', 'high'
    UNIQUE(l2_id, year_month)
);
```

## DATA INGESTION PIPELINES

### Pipeline Architecture

Use Prefect 2.x for orchestration. Each data source has its own flow.
All flows are idempotent and store raw downloads before transformation.

### Python Pipeline Structure

```
python/pipeline/
├── __init__.py
├── config.py          # Data source URLs, schedules, credentials
├── base.py            # Base pipeline class with download/validate/transform/load
├── flows/
│   ├── __init__.py
│   ├── anatel_broadband.py    # Monthly broadband subscriber data
│   ├── anatel_base_stations.py # ERB/base station registry
│   ├── anatel_quality.py       # Quality indicators
│   ├── anatel_providers.py     # Provider registry
│   ├── ibge_census.py          # Census demographics + boundaries
│   ├── ibge_pib.py             # Municipal GDP
│   ├── ibge_projections.py     # Population projections
│   ├── srtm_terrain.py         # SRTM elevation tile download
│   ├── mapbiomas_landcover.py  # Land use classification
│   ├── osm_roads.py            # OpenStreetMap road network
│   ├── aneel_power.py          # Power grid corridors
│   ├── inmet_weather.py        # Meteorological observations
│   └── ookla_speedtest.py      # Speedtest open data
├── transformers/
│   ├── __init__.py
│   ├── provider_normalizer.py  # Normalize ISP names (Vivo S.A. = Telefonica Brasil)
│   ├── geocoder.py             # Assign geographic codes to records
│   ├── h3_indexer.py           # Assign H3 hexagonal cells
│   └── validator.py            # Schema validation, bounds checking
└── loaders/
    ├── __init__.py
    ├── postgres_loader.py      # Upsert to PostgreSQL
    ├── minio_loader.py         # Upload raster files to MinIO
    └── refresh_views.py        # Refresh materialized views after load
```

### Critical Pipeline: Anatel Broadband Subscribers

```python
# python/pipeline/flows/anatel_broadband.py
# This is the highest-priority pipeline. Most analyses depend on it.

"""
Source: Anatel open data portal
URL: https://dados.gov.br/dados/conjuntos-dados/acessos-banda-larga-fixa
Format: CSV (semicolon-delimited, ISO-8859-1 encoding)
Update: Monthly (published ~45 days after month end)
Key columns: Ano, Mês, Grupo Econômico, Empresa, CNPJ, UF, Município, Código IBGE, 
             Tecnologia, Meio de Acesso, Acessos

Pipeline steps:
1. Check for new monthly file on portal
2. Download CSV
3. Convert encoding from ISO-8859-1 to UTF-8
4. Parse with pandas, validate schema
5. Normalize provider names (critical — many variations exist)
6. Map municipality codes to admin_level_2 IDs
7. Classify technology: 'Fibra Óptica' -> 'fiber', 'Cabo Coaxial/HFC' -> 'cable', etc.
8. Upsert into broadband_subscribers table
9. Recompute competitive_analysis for affected municipalities
10. Refresh mv_market_summary materialized view
11. Log pipeline run with row counts and any validation warnings
"""
```

### Critical Pipeline: IBGE Census Setores Censitários

```python
# python/pipeline/flows/ibge_census.py
# Heavy initial load — 468,097 setores with geometry + demographics

"""
Sources:
- Malha de Setores Censitários: 
  https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais/26565-malhas-de-setores-censitarios-divisoes-intramunicipais.html
  Format: Shapefile or GeoPackage, per UF
  
- Agregados por Setores Censitários:
  https://www.ibge.gov.br/estatisticas/sociais/saude/22827-censo-demografico-2022.html
  Format: CSV (multiple files — basico, domicilios, pessoas, renda)

Pipeline steps:
1. Download malha files for all 27 UFs (shapefile or gpkg)
2. Download agregados CSV files (basico, caracteristicas_domicilios, pessoas_renda)
3. Load boundaries into census_tracts table using ogr2ogr or geopandas
4. Parse demographic CSVs, join to tracts via 15-digit setor code
5. Compute derived metrics:
   - broadband_affordability_index: % households with income > 1.5x minimum broadband price
   - urbanization_density: population / area for urban tracts
   - growth_potential: weighted composite of income, education, young population %
6. Load into census_demographics table
7. Assign H3 indexes to each tract centroid (resolution 7, 8, 9)
8. Validate: total population per municipality should match IBGE published totals (+/- 1%)
"""
```

### Critical Pipeline: SRTM Terrain Tiles

```python
# python/pipeline/flows/srtm_terrain.py
# Large initial download (~25 GB), then static

"""
Source: NASA SRTM 1-arc-second (30m resolution)
URL: https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL1.003/2000.02.11/
     (requires NASA Earthdata login — free registration)
Alternative: https://dwtkns.com/srtm30m/ (direct download, no login)
Format: HGT (raw binary, 3601x3601 16-bit signed integers per tile)

Brazil coverage: approximately S01W035 to S34W074 = ~800 tiles
Some tiles over ocean or outside Brazil can be skipped.

Pipeline steps:
1. Generate list of required tiles based on Brazil's bounding box
2. Download each .hgt file (each ~25 MB)
3. Store in MinIO under bucket 'terrain/srtm/{tile_name}.hgt'
4. Register in terrain_tiles table with bounding box geometry
5. Validate: spot-check known elevations (e.g., Pico da Neblina = 2,993m)
6. Build spatial index for tile lookup by coordinate

The Rust RF engine reads these tiles directly via memory-mapped I/O.
The Python pipeline only handles download and registration.
"""
```

### Critical Pipeline: OpenStreetMap Roads

```python
# python/pipeline/flows/osm_roads.py

"""
Source: Geofabrik daily extracts
URL: https://download.geofabrik.de/south-america/brazil-latest.osm.pbf
Format: Protocol Buffer Binary Format (.pbf)
Tool: osm2pgsql or osmium + ogr2ogr

Pipeline steps:
1. Download brazil-latest.osm.pbf (~1.5 GB)
2. Extract road network using osm2pgsql with custom style:
   - highway = motorway, trunk, primary, secondary, tertiary, residential, track
   - Include: name, surface, lanes, maxspeed
3. Load into road_segments table
4. Compute segment lengths in meters
5. Classify surface type: 'asphalt' -> 'paved', 'unpaved'/'gravel'/'dirt' -> 'unpaved'
6. Build spatial index
7. Also extract: building footprints (for demand estimation), power=line (for corridor detection)
"""
```

## API LAYER

### FastAPI Application Structure

```
python/api/
├── __init__.py
├── main.py              # FastAPI app setup, CORS, middleware
├── config.py            # Environment-based configuration
├── database.py          # SQLAlchemy + PostGIS session management
├── auth.py              # JWT authentication, multi-tenant isolation
├── routers/
│   ├── __init__.py
│   ├── geographic.py    # /api/v1/geo/* — municipality search, boundary queries
│   ├── market.py        # /api/v1/market/* — subscriber data, competitive analysis
│   ├── opportunity.py   # /api/v1/opportunity/* — expansion scores, recommendations
│   ├── design.py        # /api/v1/design/* — RF design requests, coverage maps
│   ├── compliance.py    # /api/v1/compliance/* — regulatory status, tax impact
│   ├── health.py        # /api/v1/health/* — network quality, fault intelligence
│   └── reports.py       # /api/v1/reports/* — PDF generation, export
├── models/
│   ├── __init__.py
│   ├── schemas.py       # Pydantic models for request/response validation
│   └── orm.py           # SQLAlchemy ORM models
├── services/
│   ├── __init__.py
│   ├── spatial.py       # PostGIS query helpers
│   ├── market_intelligence.py  # Subscriber analysis, market share calculation
│   ├── rf_client.py     # gRPC client to Rust RF engine
│   └── report_generator.py    # PDF report generation
└── middleware/
    ├── __init__.py
    ├── tenant.py        # Extract tenant from JWT, enforce data isolation
    └── rate_limit.py    # Tier-based rate limiting
```

### Key API Endpoints

```
# Geographic
GET  /api/v1/geo/search?q=Campinas&country=BR  — Search municipalities
GET  /api/v1/geo/{municipality_id}/boundary     — Get GeoJSON boundary
GET  /api/v1/geo/within?lat=-23.5&lng=-46.6&radius_km=50  — Find municipalities in radius

# Market Intelligence
GET  /api/v1/market/{municipality_id}/summary    — Subscribers, providers, penetration
GET  /api/v1/market/{municipality_id}/history     — Time series subscriber data
GET  /api/v1/market/{municipality_id}/competitors — Provider-level breakdown
GET  /api/v1/market/heatmap?bbox=-48,-24,-43,-20&metric=penetration — GeoJSON heatmap

# Expansion Planning
POST /api/v1/opportunity/score     — Score a geographic area for expansion
GET  /api/v1/opportunity/top?state=SP&limit=50  — Top expansion opportunities
POST /api/v1/opportunity/route     — Generate preliminary fiber route
POST /api/v1/opportunity/financial — Financial viability projection

# RF Design (proxies to Rust engine via gRPC)
POST /api/v1/design/coverage       — Compute coverage footprint for a tower location
POST /api/v1/design/optimize       — Find optimal tower placement for an area
POST /api/v1/design/linkbudget     — Point-to-point link budget calculation
GET  /api/v1/design/{job_id}/status — Check status of long-running design job
GET  /api/v1/design/{job_id}/result — Download completed design

# Compliance
GET  /api/v1/compliance/status?provider_id=X  — Current compliance status
GET  /api/v1/compliance/norma4/impact?state=SP&subscribers=4500 — Tax impact estimate
GET  /api/v1/compliance/deadlines  — Upcoming regulatory deadlines

# Reports
POST /api/v1/reports/expansion     — Generate expansion analysis PDF
POST /api/v1/reports/design        — Generate RF design report PDF
POST /api/v1/reports/compliance    — Generate compliance status PDF
```

## VALIDATION TESTS — Phase 1

After completing the data foundation, run these validations:

```python
# tests/validation/phase1_validation.py

"""
Test 1: Geographic data integrity
- admin_level_1 for Brazil should have exactly 27 records (26 states + DF)
- admin_level_2 for Brazil should have approximately 5,570 records
- census_tracts for Brazil should have approximately 468,097 records
- Every tract should be within its parent municipality boundary (ST_Within)
- No tract geometries should overlap (ST_Intersects with area > 1% threshold)

Test 2: Demographic data completeness
- Every census tract should have a demographics record for census_year 2022
- No negative population or household counts
- Sum of tract populations per municipality should be within 2% of IBGE published municipal total
- Income data JSONB should have all required bracket fields

Test 3: Anatel subscriber data
- Latest year_month should be within 3 months of current date (data freshness)
- Sum of subscribers by state should approximately match Anatel published state totals
- No municipality should have more subscribers than households (penetration > 100% is a data error)
- Provider names should be normalized (no duplicates like 'VIVO' and 'VIVO S.A.')

Test 4: Spatial query performance
- Query: "Find all census tracts within 10km of coordinates (-23.55, -46.63) where avg_income > 3000"
  Should complete in < 2 seconds on a properly indexed database
- Query: "Count providers and total subscribers for all municipalities in São Paulo state"
  Should complete in < 5 seconds

Test 5: SRTM terrain data
- Elevation at Pico da Neblina (0.7833°N, 66.0°W) should read approximately 2,993m
- Elevation at sea level coastal point should read approximately 0-5m
- All tiles within Brazil's bounding box should be registered
- No NULL elevation values within land area (ocean tiles are expected to have voids)

Test 6: Multi-country architecture
- Inserting a Colombia country record and a test municipality should not affect any Brazil queries
- All queries should accept country_code parameter and filter correctly
- Adding a new country module configuration should not require schema changes
"""
```

## COMPLETION CRITERIA

Phase 1 is complete when:
1. All database tables created and indexed
2. All data pipelines implemented and have run at least once successfully
3. All Phase 1 validation tests pass
4. mv_market_summary materialized view returns data for all Brazilian municipalities
5. API endpoints for geographic search and market summary respond correctly
6. A second country (Colombia stub with minimal test data) can be added without code changes
7. Documentation: data dictionary for all tables, pipeline run instructions, API endpoint docs
