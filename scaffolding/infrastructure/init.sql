-- ENLACE Database Initialization
-- Run automatically by Docker on first startup

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- NOTE: TimescaleDB requires separate installation
-- If available: CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ═══ Geographic Entities ═══

CREATE TABLE countries (
    code CHAR(2) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    name_local VARCHAR(100) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    language_code VARCHAR(10) NOT NULL,
    regulator_name VARCHAR(200),
    regulator_url VARCHAR(500),
    national_crs INTEGER,
    timezone VARCHAR(50),
    bounding_box BOX2D,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO countries VALUES
('BR', 'Brazil', 'Brasil', 'BRL', 'pt-BR', 'Anatel', 'https://www.anatel.gov.br', 4674, 'America/Sao_Paulo',
 ST_MakeBox2D(ST_Point(-73.99, -33.77), ST_Point(-28.83, 5.27)));

CREATE TABLE admin_level_1 (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    code VARCHAR(10) NOT NULL,
    name VARCHAR(200) NOT NULL,
    abbrev VARCHAR(10),
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    UNIQUE(country_code, code)
);
CREATE INDEX idx_al1_geom ON admin_level_1 USING GIST(geom);
CREATE INDEX idx_al1_country ON admin_level_1(country_code);

CREATE TABLE admin_level_2 (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    l1_id INTEGER REFERENCES admin_level_1(id),
    code VARCHAR(20) NOT NULL,
    name VARCHAR(200) NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    centroid GEOMETRY(POINT, 4326),
    UNIQUE(country_code, code)
);
CREATE INDEX idx_al2_geom ON admin_level_2 USING GIST(geom);
CREATE INDEX idx_al2_l1 ON admin_level_2(l1_id);
CREATE INDEX idx_al2_country ON admin_level_2(country_code);

CREATE TABLE census_tracts (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    l2_id INTEGER REFERENCES admin_level_2(id),
    code VARCHAR(20) NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    area_km2 DOUBLE PRECISION,
    centroid GEOMETRY(POINT, 4326),
    situation VARCHAR(10),
    tract_type VARCHAR(50),
    UNIQUE(country_code, code)
);
CREATE INDEX idx_ct_geom ON census_tracts USING GIST(geom);
CREATE INDEX idx_ct_l2 ON census_tracts(l2_id);
CREATE INDEX idx_ct_country ON census_tracts(country_code);

-- ═══ Demographics ═══

CREATE TABLE census_demographics (
    id SERIAL PRIMARY KEY,
    tract_id INTEGER REFERENCES census_tracts(id),
    census_year INTEGER NOT NULL,
    total_population INTEGER,
    total_households INTEGER,
    occupied_households INTEGER,
    avg_residents_per_household NUMERIC(4,2),
    income_data JSONB,
    education_data JSONB,
    housing_data JSONB,
    UNIQUE(tract_id, census_year)
);
CREATE INDEX idx_cd_tract ON census_demographics(tract_id);

CREATE TABLE population_projections (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    projected_population INTEGER,
    growth_rate NUMERIC(6,4),
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
    source VARCHAR(100),
    UNIQUE(l2_id, year)
);

-- ═══ Telecom Market ═══

CREATE TABLE providers (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    name VARCHAR(300) NOT NULL,
    name_normalized VARCHAR(300) NOT NULL,
    national_id VARCHAR(30),
    classification VARCHAR(20),
    services JSONB,
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
    year_month CHAR(7) NOT NULL,
    technology VARCHAR(20) NOT NULL,
    subscribers INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bs_provider ON broadband_subscribers(provider_id);
CREATE INDEX idx_bs_l2 ON broadband_subscribers(l2_id);
CREATE INDEX idx_bs_yearmonth ON broadband_subscribers(year_month);
CREATE INDEX idx_bs_l2_ym ON broadband_subscribers(l2_id, year_month);

CREATE TABLE base_stations (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    provider_id INTEGER REFERENCES providers(id),
    station_id VARCHAR(50),
    geom GEOMETRY(POINT, 4326) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    technology VARCHAR(10) NOT NULL,
    frequency_mhz DOUBLE PRECISION,
    bandwidth_mhz DOUBLE PRECISION,
    antenna_height_m DOUBLE PRECISION,
    azimuth_degrees DOUBLE PRECISION,
    mechanical_tilt DOUBLE PRECISION,
    power_watts DOUBLE PRECISION,
    authorization_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bst_geom ON base_stations USING GIST(geom);
CREATE INDEX idx_bst_provider ON base_stations(provider_id);
CREATE INDEX idx_bst_tech ON base_stations(technology);
CREATE INDEX idx_bst_country ON base_stations(country_code);

CREATE TABLE spectrum_licenses (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    provider_id INTEGER REFERENCES providers(id),
    frequency_start_mhz DOUBLE PRECISION NOT NULL,
    frequency_end_mhz DOUBLE PRECISION NOT NULL,
    bandwidth_mhz DOUBLE PRECISION,
    geographic_area VARCHAR(200),
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
    value DOUBLE PRECISION NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_qi_l2_ym ON quality_indicators(l2_id, year_month);

-- ═══ Terrain & Environment ═══

CREATE TABLE terrain_tiles (
    id SERIAL PRIMARY KEY,
    tile_name VARCHAR(50) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    bbox GEOMETRY(POLYGON, 4326) NOT NULL,
    resolution_m DOUBLE PRECISION NOT NULL,
    source VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT,
    loaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tt_bbox ON terrain_tiles USING GIST(bbox);

CREATE TABLE land_cover (
    id BIGSERIAL PRIMARY KEY,
    h3_index VARCHAR(20) NOT NULL,
    cover_type VARCHAR(50) NOT NULL,
    biome VARCHAR(50),
    cover_pct DOUBLE PRECISION,
    year INTEGER NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_lc_h3 ON land_cover(h3_index);
CREATE INDEX idx_lc_biome ON land_cover(biome);

CREATE TABLE biome_rf_corrections (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    biome_type VARCHAR(50) NOT NULL,
    frequency_min_mhz DOUBLE PRECISION NOT NULL,
    frequency_max_mhz DOUBLE PRECISION NOT NULL,
    additional_loss_db_min DOUBLE PRECISION NOT NULL,
    additional_loss_db_max DOUBLE PRECISION NOT NULL,
    additional_loss_db_mean DOUBLE PRECISION,
    additional_loss_db_stddev DOUBLE PRECISION,
    measurement_distance_range VARCHAR(50),
    source_paper VARCHAR(500) NOT NULL,
    source_institution VARCHAR(200),
    source_year INTEGER,
    confidence VARCHAR(20),
    notes TEXT
);

-- Pre-populate Brazilian corrections from published research
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
 'Estimated from vegetation density analysis - needs field validation',
 'Platform estimate', 2026, 'low'),
('BR', 'amazonia_urban', 5800, 5800, 10.0, 25.0, 17.0,
 'Comparison of propagation models at 5.8 GHz in Amazon Region cities (SciELO) - 12 cities in Pará',
 'UFPA Pará', 2011, 'high'),
('BR', 'vegetation_mmwave', 36600, 36600, 15.0, 40.0, 27.0,
 'Polarimetric Vegetation Propagation Measurements at 36.6 GHz (IEEE) - UFMG campus',
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
    station_type VARCHAR(50),
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

-- ═══ Infrastructure Corridors ═══

CREATE TABLE road_segments (
    id BIGSERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    osm_id BIGINT,
    highway_class VARCHAR(30),
    name VARCHAR(300),
    surface_type VARCHAR(30),
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
    line_type VARCHAR(30),
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_pl_geom ON power_lines USING GIST(geom);

CREATE TABLE railways (
    id SERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    operator_name VARCHAR(200),
    gauge_mm INTEGER,
    status VARCHAR(20),
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    source VARCHAR(100)
);
CREATE INDEX idx_rw_geom ON railways USING GIST(geom);

-- ═══ Computed Metrics ═══

CREATE TABLE opportunity_scores (
    id BIGSERIAL PRIMARY KEY,
    country_code CHAR(2) REFERENCES countries(code),
    geographic_type VARCHAR(20) NOT NULL,
    geographic_id VARCHAR(30) NOT NULL,
    centroid GEOMETRY(POINT, 4326),
    computed_at TIMESTAMPTZ NOT NULL,
    demand_score DOUBLE PRECISION,
    competition_score DOUBLE PRECISION,
    infrastructure_score DOUBLE PRECISION,
    growth_score DOUBLE PRECISION,
    composite_score DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    features JSONB,
    model_version VARCHAR(50)
);
CREATE INDEX idx_os_geom ON opportunity_scores USING GIST(centroid);
CREATE INDEX idx_os_composite ON opportunity_scores(composite_score DESC);

CREATE TABLE competitive_analysis (
    id BIGSERIAL PRIMARY KEY,
    l2_id INTEGER REFERENCES admin_level_2(id),
    year_month CHAR(7) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    hhi_index DOUBLE PRECISION,
    leader_provider_id INTEGER REFERENCES providers(id),
    leader_market_share DOUBLE PRECISION,
    provider_details JSONB,
    growth_trend VARCHAR(20),
    threat_level VARCHAR(20),
    UNIQUE(l2_id, year_month)
);

-- ═══ Pipeline Tracking ═══

CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    pipeline_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,  -- 'running', 'success', 'failed'
    rows_processed INTEGER,
    rows_inserted INTEGER,
    rows_updated INTEGER,
    error_message TEXT,
    metadata JSONB
);

-- Log successful initialization
INSERT INTO pipeline_runs (pipeline_name, started_at, completed_at, status, metadata)
VALUES ('schema_init', NOW(), NOW(), 'success', '{"version": "1.0", "country": "BR"}');
