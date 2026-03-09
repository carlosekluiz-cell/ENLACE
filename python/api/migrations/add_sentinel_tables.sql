-- Migration: add_sentinel_tables
-- Description: Create tables for Sentinel-2 urban growth intelligence
-- Depends on: admin_level_2 table (Brazilian municipalities)
-- Database: PostgreSQL 16 + PostGIS 3.4

-- Sentinel-2 urban indices per municipality per year
CREATE TABLE IF NOT EXISTS sentinel_urban_indices (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER NOT NULL REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    -- Vegetation
    mean_ndvi FLOAT,
    ndvi_std FLOAT,
    -- Built-up
    mean_ndbi FLOAT,
    built_up_area_km2 FLOAT,
    built_up_pct FLOAT,
    -- Water
    mean_mndwi FLOAT,
    water_area_km2 FLOAT,
    -- Bare soil
    mean_bsi FLOAT,
    bare_soil_area_km2 FLOAT,
    -- Year-over-year change
    built_up_change_km2 FLOAT,
    built_up_change_pct FLOAT,
    ndvi_change_pct FLOAT,
    -- Metadata
    cloud_cover_pct FLOAT,
    scenes_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(l2_id, year)
);

CREATE INDEX idx_sentinel_indices_l2_year ON sentinel_urban_indices(l2_id, year);
CREATE INDEX idx_sentinel_indices_year ON sentinel_urban_indices(year);

-- Sentinel-2 composite tile metadata
CREATE TABLE IF NOT EXISTS sentinel_composites (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER NOT NULL REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    composite_type VARCHAR(20) NOT NULL,  -- 'true_color', 'false_color', 'ndvi'
    filepath VARCHAR(500) NOT NULL,       -- MinIO path
    bbox GEOMETRY(POLYGON, 4326),
    resolution_m FLOAT DEFAULT 10.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(l2_id, year, composite_type)
);

CREATE INDEX idx_sentinel_composites_l2_year ON sentinel_composites(l2_id, year);
CREATE INDEX idx_sentinel_composites_bbox ON sentinel_composites USING GIST(bbox);
