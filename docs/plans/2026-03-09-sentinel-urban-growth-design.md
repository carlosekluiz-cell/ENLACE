# Sentinel-2 Urban Growth Intelligence

**Date:** 2026-03-09
**Status:** Approved

## Problem

IBGE census data (population, households) is updated infrequently and lags reality. We need ground-truth validation of urban growth using satellite imagery to:
- Detect built-up area expansion at 10m resolution
- Compare satellite-derived growth vs IBGE census claims
- Rank municipalities by actual physical growth, not just reported population
- Show users actual RGB satellite imagery of target areas

## Solution

Integrate Sentinel-2 satellite data into the platform using a three-stage hybrid architecture:
- **Google Earth Engine (GEE)** for planetary-scale raster computation
- **Rust CLI** for fast XYZ tile generation from composites
- **Python pipeline** for orchestration (existing BasePipeline pattern)

## Architecture

### Data Flow

```
Sentinel-2 L2A (ESA Copernicus)
        |
        v
Google Earth Engine
  - Filter by municipality bbox + year + cloud cover
  - Compute annual median composites
  - Calculate indices: NDVI, NDBI, MNDWI, BSI
  - Classify built-up pixels
  - Reduce to municipality-level stats
  - Export: CSV (stats) + COG (composites) → GCS
        |
        v
Python Pipeline (SentinelGrowthPipeline)
  - Monitor GEE task completion
  - Download CSV stats → INSERT sentinel_urban_indices
  - Download COGs → upload to MinIO
  - Compute year-over-year change metrics
        |
        v
Rust CLI (enlace-tiles)
  - Read COG from MinIO
  - Generate XYZ tile pyramid (zoom 10-16)
  - Output PNG tiles → MinIO tiles bucket
        |
        v
PostgreSQL + MinIO
  - sentinel_urban_indices: annual metrics per municipality
  - sentinel_composites: COG/tile metadata
  - MinIO: tiles/{municipality_code}/{year}/{z}/{x}/{y}.png
        |
        v
Frontend (Next.js + deck.gl)
  - Satellite RGB overlay on map
  - Year timeline slider (2016-2026)
  - Growth charts (satellite vs IBGE)
  - Municipality ranking by satellite growth
```

### Satellite Indices

Computed from Sentinel-2 bands (10-20m resolution):

| Index | Formula | Purpose |
|-------|---------|---------|
| NDVI  | (B8 - B4) / (B8 + B4) | Vegetation density. Low NDVI = urbanized |
| NDBI  | (B11 - B8) / (B11 + B8) | Built-up intensity. High NDBI = buildings |
| MNDWI | (B3 - B11) / (B3 + B11) | Water bodies. Track flooding/reservoirs |
| BSI   | ((B11+B4) - (B8+B2)) / ((B11+B4) + (B8+B2)) | Bare soil. Leading indicator of construction |

### Database Schema

```sql
CREATE TABLE sentinel_urban_indices (
  id SERIAL PRIMARY KEY,
  l2_id INT REFERENCES admin_level_2(id),
  year INT NOT NULL,
  mean_ndvi FLOAT,
  ndvi_std FLOAT,
  mean_ndbi FLOAT,
  built_up_area_km2 FLOAT,
  built_up_pct FLOAT,
  mean_mndwi FLOAT,
  water_area_km2 FLOAT,
  mean_bsi FLOAT,
  bare_soil_area_km2 FLOAT,
  built_up_change_km2 FLOAT,
  built_up_change_pct FLOAT,
  ndvi_change_pct FLOAT,
  cloud_cover_pct FLOAT,
  scenes_used INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(l2_id, year)
);

CREATE TABLE sentinel_composites (
  id SERIAL PRIMARY KEY,
  l2_id INT REFERENCES admin_level_2(id),
  year INT NOT NULL,
  composite_type VARCHAR(20),
  filepath VARCHAR(500),
  bbox GEOMETRY(POLYGON, 4326),
  resolution_m FLOAT DEFAULT 10.0,
  UNIQUE(l2_id, year, composite_type)
);

CREATE INDEX idx_sentinel_indices_l2_year ON sentinel_urban_indices(l2_id, year);
CREATE INDEX idx_sentinel_composites_l2_year ON sentinel_composites(l2_id, year);
CREATE INDEX idx_sentinel_composites_bbox ON sentinel_composites USING GIST(bbox);
```

### API Endpoints

```
GET  /api/v1/satellite/{municipality_code}/indices?from_year=2016&to_year=2026
GET  /api/v1/satellite/{municipality_code}/growth
GET  /api/v1/satellite/{municipality_code}/tiles/{year}/{z}/{x}/{y}.png
GET  /api/v1/satellite/ranking?state=SP&metric=built_up_change_pct&years=3
GET  /api/v1/satellite/{municipality_code}/composite/{year}
```

### GEE Compute Strategy

- Process all ~5,570 municipalities across 10 years (2016-2026)
- Batch municipalities in groups of ~100 (GEE concurrent task limit)
- Priority: high-opportunity-score municipalities processed first
- Cloud masking: use SCL band (Scene Classification Layer) to exclude clouds/shadows
- Compositing: annual median reduces noise and cloud contamination
- Monthly re-runs only process the current year

### Rust CLI (enlace-tiles)

```
enlace-tiles --input <cog_path> --output <tile_dir> \
             --zoom 10-16 --format png --quality 85
```

- Reads Cloud-Optimized GeoTIFF (COG) composites
- Generates standard XYZ tile pyramid
- Uses `gdal` crate for raster I/O, `image` crate for PNG encoding
- Outputs to MinIO via S3-compatible upload

### Frontend Components

1. **Satellite layer toggle** on MapView (XYZ TileLayer in deck.gl)
2. **Year timeline slider** (2016-2026, animatable)
3. **Growth comparison chart** (satellite built-up vs IBGE population, dual-axis)
4. **Satellite vs IBGE comparison card** (discrepancy highlighting)
5. **Growth ranking table** (sortable by satellite metrics)
6. **Integration with Opportunities page** (satellite_growth_score in composite)

### Scheduling

- Monthly 1st at 06:00 UTC (after geographic pipelines at 05:00)
- One-time backfill job for 2016-2025 historical data
- Monthly runs only process current year

### Dependencies

- `earthengine-api` (Python GEE client)
- `google-cloud-storage` (download exports from GCS)
- Rust: `gdal`, `image`, `clap`, `aws-sdk-s3` (MinIO)
- GEE service account with Earth Engine API access

## Success Criteria

- All ~5,570 municipalities have annual urban indices for 2016-2026
- Users can view RGB satellite imagery overlaid on the map for any municipality/year
- Growth comparison charts clearly show satellite vs IBGE trends
- Satellite growth ranking identifies municipalities with fastest physical expansion
- Processing completes within 24 hours for full Brazil backfill
