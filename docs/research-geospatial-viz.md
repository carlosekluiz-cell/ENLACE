# Geospatial, Visualization & Data Platform Research

**Date:** 2026-03-11
**Current Stack:** Next.js 14, Deck.gl, Mapbox GL JS, FastAPI, PostgreSQL+PostGIS, WeasyPrint
**Purpose:** Evaluate cutting-edge open-source tools to supercharge the Enlace telecom intelligence platform

---

## Table of Contents

1. [Advanced Geospatial Visualization](#1-advanced-geospatial-visualization)
2. [Spatial Analytics Engines](#2-spatial-analytics-engines)
3. [Real-time Data & Streaming](#3-real-time-data--streaming)
4. [Report & Analytics Platforms](#4-report--analytics-platforms)
5. [Bonus: Map Tile Infrastructure](#5-bonus-map-tile-infrastructure)
6. [Priority Recommendations](#6-priority-recommendations)

---

## 1. Advanced Geospatial Visualization

### 1.1 Kepler.gl

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/keplergl/kepler.gl |
| **Website** | https://kepler.gl |
| **Stars** | ~11.6k |
| **License** | MIT |
| **Latest** | v3.2.5 (Dec 2025) |
| **Maintained by** | Foursquare (formerly Uber Vis) |

**What it is:** A powerful, data-agnostic geospatial analysis tool for large-scale datasets. Built on top of deck.gl and MapLibre GL. Renders millions of points with on-the-fly spatial aggregation.

**Key features (v3.0+):**
- Apache Arrow / GeoArrow support for dramatic loading performance gains
- Default base map switched from Mapbox to MapLibre (fully open source)
- Full TypeScript codebase
- Built-in layer types: arc, hexbin, heatmap, grid, point, polygon, trip, S2, H3
- GPU-accelerated filtering and aggregation
- Export to image, data, or map config JSON

**Value for Enlace:**
- Drop-in replacement/complement for current deck.gl map layers
- H3 hexagonal visualization layer (native) -- perfect for coverage analysis
- Trip layer for visualizing backhaul routes and fiber paths
- Heatmap/hexbin for subscriber density and signal strength
- No-code exploration mode for internal analysts

**Integration complexity:** MEDIUM
- Kepler.gl v3 is built ON TOP of deck.gl (same rendering engine we use)
- Available as React component: `@kepler.gl/components`
- Can embed in Next.js pages alongside existing deck.gl layers
- Shares MapLibre GL for base maps (aligns with MapLibre migration path)
- State management uses Redux -- may need adapter for existing state

**Effort:** 2-3 weeks to integrate as an exploration/analysis tool within the platform. Could power an "Advanced Analysis" mode.

---

### 1.2 CesiumJS

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/CesiumGS/cesium |
| **Website** | https://cesium.com/platform/cesiumjs |
| **Stars** | ~13.7k |
| **License** | Apache-2.0 |
| **Latest** | Active development (2025) |

**What it is:** The industry-standard JavaScript library for 3D globes and maps. WebGL-powered, cross-platform, tuned for dynamic data visualization on a true 3D globe.

**Key features (2025):**
- WebGPU renderer branch landing for 2-4x performance uplift
- Gaussian splat support for photorealistic scene rendering
- Draping imagery on 3D Tiles
- Quantized-mesh terrain streaming (Cesium World Terrain)
- 3D Tiles, glTF, KML, GeoJSON, CZML support
- Time-dynamic visualization

**Value for Enlace:**
- 3D terrain-aware RF coverage visualization (overlay propagation results on real terrain)
- Tower placement visualization with line-of-sight analysis in 3D
- Satellite imagery draping over 3D terrain
- Impressive demo/sales tool for showing coverage across Brazil's varied topography
- Could visualize SRTM terrain data (already have 1,681 tiles / 40.6 GB)

**Integration complexity:** HIGH
- Completely different rendering paradigm from deck.gl (globe vs. flat map)
- Would need to be a separate view/mode, not a drop-in replacement
- Cesium Ion (cloud service) is paid for terrain hosting; can self-host with open data
- SRTM data needs conversion to quantized-mesh format for Cesium streaming
- Heavy library (~3MB gzipped)

**Effort:** 4-6 weeks for a dedicated 3D coverage visualization view. Best as a "3D Mode" toggle.

---

### 1.3 MapLibre GL JS

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/maplibre/maplibre-gl-js |
| **Website** | https://maplibre.org |
| **Stars** | ~9.9k |
| **License** | BSD-3-Clause |
| **Latest** | v5.19.0 (Feb 2026) |

**What it is:** Community-driven open-source fork of Mapbox GL JS (pre-proprietary license). GPU-accelerated vector tile rendering with full API compatibility.

**Key features:**
- Near API-compatible with Mapbox GL JS (drop-in replacement for most use cases)
- No usage-based pricing or API key requirements
- Active community (MapTiler, Microsoft, Elastic, AWS backing)
- 3D terrain support
- Globe view
- Steady growth trend since mid-2024

**Value for Enlace:**
- Eliminate Mapbox GL JS licensing costs and API key dependency
- Kepler.gl v3 already uses MapLibre as default (alignment)
- deck.gl has first-class MapLibre integration
- Can use free tile sources: OpenFreeMap, Protomaps, MapTiler free tier
- Same developer experience, zero vendor lock-in

**Integration complexity:** LOW
- Near drop-in replacement for Mapbox GL JS
- Change import from `mapbox-gl` to `maplibre-gl`
- Update style URLs to point to non-Mapbox tile sources
- deck.gl `MapView` supports MapLibre natively

**Effort:** 1-2 weeks including tile source migration and testing. HIGH PRIORITY -- immediate cost savings.

---

### 1.4 Deck.gl v9.x (Current Stack Upgrade)

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/visgl/deck.gl |
| **Website** | https://deck.gl |
| **Stars** | ~13.8k |
| **License** | MIT |
| **Latest** | v9.2 (2025) |

**What it is:** The WebGL2/WebGPU-powered visualization framework we already use. v9.x brings significant upgrades.

**Key features (v9.1-9.2):**
- WebGPU preview support (v9.2)
- GPU aggregation restored and refactored (HexagonLayer, GridLayer)
- Built-in Widgets (zoom, fullscreen, compass controls)
- Category Filtering in DataFilterExtension (GPU-powered)
- A5Layer for A5 geospatial indexing
- PostProcessEffect improvements
- Full TypeScript support
- Uniform buffers (WebGPU-ready shader migration)

**Value for Enlace:**
- GPU-accelerated hexagonal aggregation for subscriber data (4M+ records)
- WebGPU path gives 2-4x rendering performance on modern browsers
- Built-in widgets reduce custom UI code
- Category filtering for provider-level data slicing on GPU

**Integration complexity:** LOW-MEDIUM
- Already using deck.gl -- this is an upgrade path
- Check breaking changes in upgrade guide
- WebGPU is opt-in preview, not required

**Effort:** 1-2 weeks to upgrade to v9.2 and leverage new features.

---

### 1.5 Globe.GL / React-Globe.GL

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/vasturiano/globe.gl |
| **React** | https://github.com/vasturiano/react-globe.gl |
| **Stars** | ~2.4k (globe.gl), ~1k (react-globe.gl) |
| **License** | MIT |

**What it is:** Lightweight 3D globe data visualization using ThreeJS/WebGL. Supports arcs, polygons, heatmaps, hex bins, and custom 3D objects on a spherical projection.

**Value for Enlace:**
- Beautiful hero visualization for marketing site or dashboard landing page
- Show Brazil-wide coverage as 3D globe with arc connections
- Much lighter than CesiumJS for simple globe visualizations
- Great for executive presentations

**Integration complexity:** LOW
- React component, drop into any page
- No complex setup or tile management
- Not suitable for detailed analytical work (decorative/overview use)

**Effort:** 1-2 days for a hero visualization component.

---

## 2. Spatial Analytics Engines

### 2.1 Uber H3 (Hexagonal Hierarchical Spatial Index)

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/uber/h3 |
| **Website** | https://h3geo.org |
| **Stars** | ~6k (core), ~1k (h3-js), ~933 (h3-py) |
| **License** | Apache-2.0 |
| **Bindings** | C, Python, JavaScript, Rust, Java, Go |
| **PostGIS extension** | h3-pg (https://github.com/zachasme/h3-pg) |

**What it is:** A hierarchical hexagonal geospatial indexing system with 16 resolution levels. Each finer resolution has cells with 1/7th the area. Hexagons have uniform adjacency (unlike square grids) making them ideal for spatial analysis.

**Key features:**
- 16 resolution levels (0 = continental, 15 = ~1m^2)
- Uniform neighbor distance (unlike square grids with diagonal distortion)
- Fast lat/lng to cell conversion
- Cell-to-cell distance and path algorithms
- Compact representation (64-bit integer per cell)
- PostGIS extension (h3-pg) available on AWS RDS

**Value for Enlace (CRITICAL FOR TELECOM):**
- **Coverage aggregation**: Aggregate signal strength, subscriber density, and tower coverage into uniform hex cells
- **Resolution 7** (~5.16 km^2): Municipal-level market analysis
- **Resolution 9** (~0.105 km^2): Neighborhood-level coverage planning
- **Resolution 10** (~0.015 km^2): Street-level RF coverage mapping
- Index 4M+ broadband subscriber records by hex cell for instant spatial queries
- Pre-compute opportunity scores per hex cell
- Native deck.gl H3HexagonLayer for visualization
- Native kepler.gl H3 layer support
- Replace current municipality-based analysis with continuous hexagonal analysis

**Integration complexity:** MEDIUM
- h3-py: `pip install h3` -- use in Python pipelines
- h3-pg: PostgreSQL extension, works alongside PostGIS
- h3-js: client-side hex operations in Next.js
- Requires data re-indexing: add H3 cell columns to broadband_subscribers, base_stations, opportunity_scores tables
- Build materialized views aggregated by H3 cell at multiple resolutions

**Effort:** 3-4 weeks for full integration (schema changes, pipeline updates, API endpoints, frontend layers). HIGH VALUE.

---

### 2.2 DuckDB Spatial

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/duckdb/duckdb-spatial |
| **Website** | https://duckdb.org/docs/extensions/spatial |
| **Stars** | ~30k+ (DuckDB core) |
| **License** | MIT |
| **Latest** | v1.3.0+ with SPATIAL_JOIN operator (2025) |

**What it is:** In-process analytical SQL database with a spatial extension. Called "the most important geospatial software of the last decade" (2025). Columnar storage, vectorized execution, zero-copy integration with Python.

**Key features (2025):**
- Dedicated SPATIAL_JOIN operator (v1.3.0) for scalable geospatial joins
- GEOMETRY type with full Simple Features support
- GDAL-based file I/O (GeoJSON, Shapefile, GeoParquet, PostGIS)
- Reads directly from PostGIS databases
- 300+ spatial functions
- Zero-copy pandas/Arrow integration

**Value for Enlace:**
- Accelerate heavy spatial analytics that currently run in PostGIS
- Ad-hoc analysis without loading data into PostgreSQL first
- GeoParquet export/import for data exchange
- Could power report generation with fast analytical queries
- Ideal for pipeline batch processing (read from PostGIS, compute, write back)

**Integration complexity:** LOW-MEDIUM
- `pip install duckdb` -- use alongside existing PostGIS
- Can connect directly to PostgreSQL via postgres_scanner extension
- Use for analytical workloads, keep PostGIS for transactional/serving
- Python API is just SQL strings -- minimal learning curve

**Effort:** 1-2 weeks to integrate into Python analytics pipelines.

---

### 2.3 Apache Sedona

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/apache/sedona |
| **Website** | https://sedona.apache.org |
| **Stars** | ~2k |
| **License** | Apache-2.0 |
| **Latest** | Active development; SedonaDB released 2025 |

**What it is:** Cluster computing system for large-scale spatial data processing. Extends Apache Spark, Flink, and Snowflake with spatial SQL. SedonaDB (2025) is a new single-node analytical engine treating spatial data as first-class.

**Key features:**
- 300+ spatial functions
- Distributed spatial joins (Spark/Flink)
- Raster AND vector analysis
- GeoParquet, GeoJSON, Shapefile, OSM PBF support
- SedonaDB: single-node spatial-first analytical database

**Value for Enlace:**
- Heavy-duty spatial processing at scale (when PostGIS isn't enough)
- Process massive road network datasets (6.4M segments)
- Batch raster analysis of SRTM tiles

**Integration complexity:** HIGH
- Requires Spark/Flink cluster (or SedonaDB standalone)
- Different paradigm from current PostGIS-centric architecture
- Overkill for current data volumes (PostGIS handles 5K municipalities fine)
- More relevant if data grows 10-100x

**Effort:** 4-6 weeks. NOT RECOMMENDED at current scale -- PostGIS + DuckDB cover our needs.

---

### 2.4 Turf.js

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/Turfjs/turf |
| **Website** | https://turfjs.org |
| **Stars** | ~9.3k |
| **License** | MIT |
| **Latest** | v7.3.4 (Feb 2026) |

**What it is:** Modular geospatial engine for JavaScript/TypeScript. Provides spatial operations (buffer, measure, interpolation, classification) that run entirely in the browser or Node.js.

**Key features:**
- Modular: import only what you need (`@turf/buffer`, `@turf/distance`, etc.)
- Works with GeoJSON natively
- Buffer, intersect, union, dissolve, voronoi, tin, interpolate
- Point-in-polygon, nearest point, line intersect
- Measurement: distance, area, bearing, midpoint
- Web Worker compatible for non-blocking computation
- TypeScript definitions

**Value for Enlace:**
- Client-side coverage area calculations (no server round-trip)
- Buffer zones around towers for quick coverage estimation
- Point-in-polygon for checking if locations fall within coverage areas
- Voronoi diagrams for service area partitioning
- Distance calculations for nearest-tower analysis
- Reduce API calls for simple spatial operations

**Integration complexity:** LOW
- `npm install @turf/turf` (or individual modules)
- Works directly with GeoJSON (our API already returns GeoJSON)
- Pure JavaScript, no native dependencies
- Already compatible with deck.gl and MapLibre data formats

**Effort:** 1 week to integrate key modules. Add incrementally as needed.

---

### 2.5 PostGIS Advanced Functions (Already Available)

| Feature | Function | Use Case |
|---------|----------|----------|
| K-Means Clustering | `ST_ClusterKMeans` | Cluster towers, identify coverage gaps |
| DBSCAN Clustering | `ST_ClusterDBSCAN` | Density-based subscriber clustering |
| Weighted K-Means | `ST_ClusterKMeans` with M-coordinate | Population-weighted coverage zones |
| Voronoi | `ST_VoronoiPolygons` | Service area partitioning |
| Concave Hull | `ST_ConcaveHull` | Coverage boundary estimation |
| Raster Analysis | `ST_MapAlgebra` | SRTM terrain analysis in-database |
| Nearest Neighbor | `ST_DWithin` + KNN `<->` | Nearest tower to any point |
| Network Analysis | pgRouting extension | Fiber route optimization |

**Value for Enlace:** These functions are ALREADY AVAILABLE in our PostGIS installation. Zero additional infrastructure.

**Effort:** 1-2 weeks to build SQL functions and expose via API endpoints. HIGHEST ROI.

---

### 2.6 GeoMesa

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/locationtech/geomesa |
| **Website** | https://geomesa.org |
| **Stars** | ~1.5k |
| **License** | Apache-2.0 |
| **Latest** | v5.4.0 (Oct 2025) |

**What it is:** Suite for large-scale geospatial querying on distributed systems (HBase, Cassandra, Kafka, Accumulo, Redis). Spatio-temporal indexing with GeoServer integration.

**Value for Enlace:** Real-time geospatial streaming via Kafka integration. Relevant if we add real-time network monitoring.

**Integration complexity:** HIGH -- Requires HBase/Cassandra infrastructure. JVM-based. Overkill for current needs.

**Effort:** NOT RECOMMENDED at current scale.

---

## 3. Real-time Data & Streaming

### 3.1 TimescaleDB

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/timescale/timescaledb |
| **Website** | https://timescale.com |
| **Stars** | ~18k+ |
| **License** | Apache-2.0 (core), Timescale License (enterprise features) |
| **Latest** | v2.24.0 (Dec 2025) |

**What it is:** Time-series database built as a PostgreSQL extension. Automatic partitioning (hypertables), columnar compression (up to 95%), continuous aggregates, and 200+ native SQL functions.

**Key features:**
- Hypertables: automatic time-based partitioning
- Continuous aggregates: pre-computed rollups that update incrementally
- Columnar compression: 95% storage reduction
- Data retention policies
- S3 tiering for cold data
- Full SQL compatibility (it IS PostgreSQL)
- Works alongside PostGIS in the same database

**Value for Enlace (HIGH):**
- **Broadband subscriber time-series**: 4.1M records across 37 months -- perfect hypertable candidate
- **Continuous aggregates**: Pre-compute monthly/quarterly subscriber growth by municipality
- **Weather observations**: 61K records, time-indexed -- natural fit
- **Network quality metrics**: Time-series quality indicators (33K records)
- **Compression**: Reduce storage for historical broadband data by 90%+
- **Retention policies**: Auto-archive data older than N months to S3
- Works IN our existing PostgreSQL -- no separate database needed

**Integration complexity:** LOW
- Install as PostgreSQL extension (`CREATE EXTENSION timescaledb;`)
- Convert existing tables to hypertables with one command
- All existing SQL queries continue to work
- Continuous aggregates replace manual materialized view refreshes
- No application code changes needed for basic adoption

**Effort:** 1-2 weeks to install, convert key tables, set up continuous aggregates. VERY HIGH ROI.

---

### 3.2 Apache Kafka (Geospatial Streaming)

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/apache/kafka |
| **Website** | https://kafka.apache.org |
| **Stars** | ~29k+ |
| **License** | Apache-2.0 |

**What it is:** Distributed event streaming platform for high-performance data pipelines and streaming analytics.

**Geospatial integration options:**
- GeoMesa Kafka connector for spatio-temporal stream processing
- Kafka Streams with geohashing for spatial queries
- GeoFlink for real-time spatial stream processing

**Value for Enlace:**
- Real-time ingestion of network telemetry (future)
- Stream processing of weather impact on network quality
- Event-driven pipeline triggers (new data -> recompute scores)
- Pub/sub for real-time dashboard updates (replace current SSE)

**Integration complexity:** HIGH
- Requires Kafka cluster (ZooKeeper or KRaft)
- Significant infrastructure overhead
- Current APScheduler + SSE approach works for batch use case
- Kafka is justified when we need sub-second event processing

**Effort:** 4-6 weeks minimum. NOT RECOMMENDED now -- current SSE + cron approach is sufficient. Revisit when adding real-time network monitoring.

---

## 4. Report & Analytics Platforms

### 4.1 Apache Superset

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/apache/superset |
| **Website** | https://superset.apache.org |
| **Stars** | ~70.9k |
| **License** | Apache-2.0 |

**What it is:** Modern data exploration and visualization platform. 40+ visualization types, SQL IDE, embedded analytics SDK, row-level security.

**Key features:**
- 40+ pre-installed visualization types (including maps)
- SQL Lab: in-browser SQL IDE
- Embedded SDK: iframe-based dashboard embedding with guest tokens
- Row-level security: multi-tenant data access control
- REST API for programmatic dashboard management
- SSO/OAuth/LDAP authentication
- Connects directly to PostgreSQL/PostGIS
- Dashboard versioning and CI/CD support
- Deck.gl integration for geospatial visualizations

**Value for Enlace:**
- Embeddable dashboards for client-facing analytics
- Self-service analytics for internal team (no code needed)
- Direct PostgreSQL connection -- query existing data without ETL
- Replace some custom dashboard pages with Superset dashboards
- Row-level security maps well to multi-tenant ISP model
- Deck.gl integration means geospatial viz works out of the box

**Integration complexity:** MEDIUM
- Runs as separate service (Python/Flask app, ~1GB memory)
- Embedded SDK is an iframe -- straightforward Next.js integration
- Auth bridge needed: JWT guest token generation from our FastAPI
- Requires Redis + metadata database (can use existing PostgreSQL)
- Initial dashboard setup takes time but is no-code after that

**Effort:** 3-4 weeks for deployment + embedding + initial dashboards. STRONG CANDIDATE for client-facing analytics.

---

### 4.2 Metabase

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/metabase/metabase |
| **Website** | https://metabase.com |
| **Stars** | ~44.3k |
| **License** | AGPL-3.0 (OSS), Commercial license (Pro/Enterprise) |

**What it is:** User-friendly BI and embedded analytics tool. Known for its intuitive question-building interface.

**Key features:**
- Natural-language question interface
- Embeddable charts and dashboards (SDK)
- Custom styling for white-labeling
- Direct PostgreSQL connection
- Alerts and subscriptions
- API for automation

**Value for Enlace:**
- More user-friendly than Superset for non-technical users
- Embedding SDK allows deeper integration than iframe
- Good for quick client-facing reports
- AI-powered question answering

**Integration complexity:** MEDIUM
- Java application (~2GB memory footprint)
- AGPL license requires open-sourcing embedding app OR purchasing Pro license
- Premium Embedding license needed to remove "Powered by Metabase" branding
- Embedded SDK more sophisticated than Superset's iframe approach

**Caveats:**
- AGPL license is restrictive for SaaS products
- Pro license ($500/month) needed for premium embedding
- Less geospatial-native than Superset (no deck.gl integration)

**Effort:** 2-3 weeks for basic integration. License cost is the main concern.

---

### 4.3 Evidence.dev

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/evidence-dev/evidence |
| **Website** | https://evidence.dev |
| **Stars** | ~5.6k |
| **License** | MIT |

**What it is:** Code-first BI framework. Build data products (reports, dashboards, decision tools) using only SQL + Markdown. Renders as a static website.

**Key features:**
- SQL queries embedded in Markdown files
- Pre-built chart components (bar, line, area, scatter, map, sankey, funnel)
- Git-versioned reports (BI as code)
- Direct PostgreSQL connection
- Parameterized pages (dynamic filtering)
- Built-in AI agent for writing Evidence markdown
- SOC 2 compliant enterprise edition
- Deploys as static site or SSR

**Value for Enlace:**
- **Automated report generation**: Replace WeasyPrint PDF pipeline with interactive web reports
- Code-versioned reports: track changes to regulatory compliance reports in Git
- Parameterized municipality reports: one template, 5,570 variations
- SQL-first: team already writes SQL for PostGIS queries
- Could power client-facing "Market Intelligence Reports"
- Interactive versions of currently static PDF reports
- Lightweight alternative to full Superset deployment

**Integration complexity:** LOW
- `npx degit evidence-dev/template my-reports`
- Configure PostgreSQL connection
- Write SQL + Markdown files
- Deploy as static site alongside main app
- No heavy runtime dependencies

**Effort:** 2-3 weeks for initial report templates. EXCELLENT fit for replacing/supplementing WeasyPrint reports.

---

### 4.4 Rill Data

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/rilldata/rill |
| **Website** | https://rilldata.com |
| **Stars** | ~2.5k |
| **License** | Apache-2.0 |
| **Latest** | v0.77 (Dec 2025) |

**What it is:** BI-as-code tool for transforming datasets into opinionated dashboards using SQL. Embedded DuckDB/ClickHouse for millisecond query response.

**Key features:**
- Embedded in-memory database (DuckDB) -- data and compute co-located
- Sub-100ms dashboard interactions
- SQL-only workflow
- AI-powered dashboard generation (one-click from data source)
- MCP (Model Context Protocol) integration for AI assistants
- Metrics layer abstraction

**Value for Enlace:**
- Blazing-fast exploratory dashboards for internal analysis
- DuckDB backend can query S3 data directly
- Good for prototyping dashboards before building custom ones
- AI-generated dashboards from existing PostGIS data

**Integration complexity:** LOW-MEDIUM
- Go binary, runs locally or as service
- Reads from PostgreSQL, S3, GCS, local files
- Embeddable but less mature than Superset/Metabase
- Best as internal analytics tool, not client-facing

**Effort:** 1-2 weeks for internal analytics. Good complement, not a replacement.

---

### 4.5 Streamlit

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/streamlit/streamlit |
| **Website** | https://streamlit.io |
| **Stars** | ~40k+ |
| **License** | Apache-2.0 |
| **Latest** | v1.53.x (Jan 2026) |

**What it is:** Python framework for building interactive data apps. Uses PyDeck (Python deck.gl bindings) for map visualizations.

**Key features:**
- Pure Python -- no frontend code needed
- `st.map()` for basic maps, `st.pydeck_chart()` for advanced
- `st.plotly_chart()` for interactive charts
- File upload, forms, caching, session state
- Handles thousands of data points efficiently
- Deploy on Streamlit Cloud or self-host

**Value for Enlace:**
- Rapid prototyping of analysis tools
- Internal tools for data team (coverage analysis, opportunity scoring)
- Interactive parameter tuning for RF models
- Quick "what-if" scenario builders
- Bridge between Python analytics and visual output

**Integration complexity:** LOW
- `pip install streamlit`
- Pure Python, uses existing data access code
- Can share PostgreSQL connection with FastAPI
- Self-contained apps, run alongside main platform
- Not embeddable in Next.js (separate app)

**Effort:** 1-2 days per internal tool. EXCELLENT for rapid prototyping and internal analysis.

---

## 5. Bonus: Map Tile Infrastructure

### 5.1 Protomaps / PMTiles

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/protomaps/PMTiles |
| **Website** | https://protomaps.com |
| **Stars** | ~2.6k |
| **License** | BSD-3-Clause |

**What it is:** Single-file archive format for map tiles. Serves vector/raster tiles from static storage (S3, CDN) using HTTP range requests. No tile server needed.

**Key features:**
- Single .pmtiles file contains entire tileset
- HTTP range requests -- works from any static file host
- 70%+ deduplication for global vector basemaps
- OpenStreetMap basemap tilesets available
- Works with MapLibre GL JS natively
- Zero maintenance, zero server costs

**Value for Enlace:**
- Eliminate Mapbox tile hosting dependency entirely
- Host basemap as single file on S3 or CDN
- Pair with MapLibre GL JS for fully open-source map stack
- Brazil-specific tileset could be <2 GB
- Zero ongoing tile serving costs

**Integration complexity:** LOW
- Download Brazil PMTiles from Protomaps
- Host on S3 or serve from nginx
- Configure MapLibre GL JS to use pmtiles protocol
- `pmtiles` npm package for client-side tile loading

**Effort:** 1 week including tile generation and testing. Combined with MapLibre migration = fully open-source map stack.

---

### 5.2 OpenFreeMap

| Attribute | Detail |
|-----------|--------|
| **URL** | https://github.com/hyperknot/openfreemap |
| **Website** | https://openfreemap.org |
| **Stars** | ~2k+ |
| **License** | MIT (code), ODbL (data) |

**What it is:** Free, open-source map hosting using OpenStreetMap data. Public instance with no limits, no API keys, no registration. Self-hosting with a single command.

**Value for Enlace:** Free basemap tile source during development/testing. Self-hostable for production. Alternative to Protomaps if you want a running tile server.

**Integration complexity:** VERY LOW -- just change tile URL in MapLibre config.

---

## 6. Priority Recommendations

### Tier 1: Do Now (Weeks 1-4, Highest ROI)

| Tool | Why | Effort | Impact |
|------|-----|--------|--------|
| **MapLibre GL JS** | Drop-in Mapbox replacement, eliminate vendor costs | 1-2 weeks | Cost savings, zero vendor lock-in |
| **Protomaps/PMTiles** | Self-hosted basemap tiles, zero ongoing costs | 1 week | Eliminate tile hosting costs |
| **TimescaleDB** | PostgreSQL extension, hypertables for time-series data | 1-2 weeks | 10x faster time-series queries, 90% compression |
| **PostGIS Advanced** | Already installed, just need to use ST_ClusterKMeans etc. | 1-2 weeks | Spatial clustering, coverage gap analysis |
| **Turf.js** | Client-side spatial ops, reduce API calls | 1 week | Faster UX, offline-capable spatial analysis |
| **Deck.gl v9.2 upgrade** | GPU aggregation, widgets, WebGPU preview | 1-2 weeks | Better performance, modern features |

**Combined Tier 1 effort: 6-10 weeks. Transforms the platform foundation.**

### Tier 2: Next Quarter (Weeks 5-12, Strategic Value)

| Tool | Why | Effort | Impact |
|------|-----|--------|--------|
| **H3 Hexagonal Indexing** | Revolutionize spatial analysis with uniform hex grid | 3-4 weeks | Telecom-grade coverage analysis |
| **Evidence.dev** | Code-first reports to replace/complement WeasyPrint | 2-3 weeks | Interactive reports, Git-versioned |
| **Kepler.gl** | Advanced analysis mode for power users | 2-3 weeks | Self-service geospatial exploration |
| **DuckDB Spatial** | Accelerate batch analytics in Python pipelines | 1-2 weeks | Faster pipeline processing |

**Combined Tier 2 effort: 8-12 weeks. Adds analytical superpowers.**

### Tier 3: Future / Conditional

| Tool | Why | When |
|------|-----|------|
| **CesiumJS** | 3D terrain coverage visualization | When selling to enterprise clients needing "wow" demos |
| **Apache Superset** | Embeddable dashboards for multi-tenant SaaS | When launching client-facing portal |
| **Streamlit** | Internal analysis tools | Ongoing, as-needed for specific analyses |
| **Globe.GL** | Marketing hero visualization | When redesigning marketing site |
| **Apache Sedona** | Distributed spatial processing | If data grows 100x+ |
| **Apache Kafka** | Real-time event streaming | When adding live network telemetry |

---

## Architecture Vision: Fully Open-Source Geospatial Stack

```
Current Stack                          Target Stack
============                          ============
Mapbox GL JS ----migrate-to----->    MapLibre GL JS (BSD-3)
Mapbox Tiles ----migrate-to----->    Protomaps/PMTiles (BSD-3)
deck.gl v8   ----upgrade-to----->    deck.gl v9.2 (MIT)
WeasyPrint   ----complement----->    Evidence.dev (MIT) + WeasyPrint
PostGIS      ----enhance-with--->    PostGIS + TimescaleDB + h3-pg
Manual SQL   ----augment-with--->    DuckDB Spatial for analytics
Municipality ----evolve-to------>    H3 Hexagonal Grid (Apache-2.0)
SSE/Polling  ----keep-for-now--->    SSE (Kafka when scale demands)
```

**Result: Zero vendor lock-in, zero usage-based pricing, full open-source stack.**

---

## Sources

- [kepler.gl GitHub](https://github.com/keplergl/kepler.gl)
- [kepler.gl 3.0 Announcement](https://openjsf.org/blog/whats-new-in-the-keplergl-30-application)
- [CesiumJS GitHub](https://github.com/CesiumGS/cesium)
- [CesiumJS Platform](https://cesium.com/platform/cesiumjs/)
- [MapLibre GL JS GitHub](https://github.com/maplibre/maplibre-gl-js)
- [MapLibre Website](https://maplibre.org/)
- [deck.gl GitHub](https://github.com/visgl/deck.gl)
- [deck.gl What's New](https://deck.gl/docs/whats-new)
- [deck.gl WebGPU](https://deck.gl/docs/developer-guide/webgpu)
- [Globe.GL GitHub](https://github.com/vasturiano/globe.gl)
- [H3 GitHub](https://github.com/uber/h3)
- [H3 Website](https://h3geo.org/)
- [h3-pg PostgreSQL Extension](https://github.com/zachasme/h3-pg)
- [DuckDB Spatial](https://github.com/duckdb/duckdb-spatial)
- [DuckDB 30K Stars](https://duckdb.org/2025/06/06/github-30k-stars)
- [DuckDB Most Important Geospatial Software](https://www.dbreunig.com/2025/05/03/duckdb-is-the-most-impactful-geospatial-software-in-a-decade.html)
- [Apache Sedona](https://sedona.apache.org/latest/)
- [SedonaDB vs DuckDB vs PostGIS](https://forrest.nyc/sedonadb-vs-duckdb-vs-postgis-which-spatial-sql-engine-is-fastest/)
- [Turf.js GitHub](https://github.com/Turfjs/turf)
- [Turf.js Website](https://turfjs.org/)
- [PostGIS ST_ClusterKMeans](https://postgis.net/docs/ST_ClusterKMeans.html)
- [PostGIS Clustering Examples](https://mapscaping.com/examples-of-spatial-clustering-with-postgis/)
- [GeoMesa GitHub](https://github.com/locationtech/geomesa)
- [TimescaleDB GitHub](https://github.com/timescale/timescaledb)
- [TimescaleDB Website](https://www.timescale.com/)
- [Apache Kafka](https://kafka.apache.org/)
- [GeoMesa Kafka Streaming](https://www.ga-intelligence.com/using-kafka-geomesa-visualize-streaming-data)
- [Apache Superset GitHub](https://github.com/apache/superset)
- [Superset Embedded SDK](https://github.com/apache/superset/blob/master/superset-embedded-sdk/README.md)
- [Superset with FastAPI and React](https://medium.com/@sameerhussain230/building-secure-role-based-embedded-dashboards-with-apache-superset-fastapi-and-react-3798ed7f8651)
- [Metabase GitHub](https://github.com/metabase/metabase)
- [Metabase Website](https://www.metabase.com/)
- [Evidence.dev GitHub](https://github.com/evidence-dev/evidence)
- [Evidence.dev Website](https://evidence.dev/)
- [Rill Data GitHub](https://github.com/rilldata/rill)
- [Rill Data Website](https://www.rilldata.com)
- [Streamlit GitHub](https://github.com/streamlit/streamlit)
- [Lonboard (Python deck.gl)](https://github.com/developmentseed/lonboard)
- [Protomaps / PMTiles GitHub](https://github.com/protomaps/PMTiles)
- [Protomaps Website](https://protomaps.com/)
- [OpenFreeMap GitHub](https://github.com/hyperknot/openfreemap)
- [OpenFreeMap Website](https://openfreemap.org/)
- [Felt Platform](https://felt.com/)
- [CARTO Spatial Analytics 2026](https://carto.com/blog/spatial-analytics-in-2026-whats-changing)
