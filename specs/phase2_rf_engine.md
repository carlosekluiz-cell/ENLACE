# ENLACE — Phase 2: Private Network Design (RF) Engine Specification
# Component 3 — Rust Computational Core
# This file is read by Claude Code before building the RF engine.

## OVERVIEW

This is the computationally intensive core of the platform, built entirely in Rust.
It implements RF propagation models, terrain analysis, Brazilian vegetation corrections,
tower placement optimization, and coverage map generation.

The starting point is the `rf-signals` open source repo (github.com/thebracket/rf-signals)
which provides Longley-Rice/ITM, HATA/COST-231, FSPL, and Fresnel calculations in pure Rust
with an SRTM HGT tile reader.

We extend this with:
1. Brazilian tropical vegetation correction layer
2. 3GPP TR 38.901 Rural Macrocell model for 5G
3. ITU-R P.1812 point-to-area model
4. ITU-R P.530 microwave backhaul link budget
5. Tower placement optimizer (greedy set-cover + simulated annealing)
6. Coverage map rasterizer (output GeoTIFF for frontend rendering)
7. gRPC service interface for Python API communication

## RUST WORKSPACE STRUCTURE

```
rust/
├── Cargo.toml              # Workspace definition
├── crates/
│   ├── enlace-terrain/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── srtm.rs          # SRTM HGT tile reader with LRU cache
│   │       ├── profile.rs       # Terrain profile extraction between two points
│   │       ├── landcover.rs     # Land cover classification lookup
│   │       ├── elevation.rs     # Point elevation query
│   │       └── cache.rs         # Memory-mapped tile cache management
│   │
│   ├── enlace-propagation/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── models/
│   │       │   ├── mod.rs
│   │       │   ├── itm.rs          # Longley-Rice Irregular Terrain Model
│   │       │   ├── hata.rs         # Extended Hata / COST-231
│   │       │   ├── fspl.rs         # Free-Space Path Loss
│   │       │   ├── tr38901.rs      # 3GPP TR 38.901 Rural Macrocell
│   │       │   ├── p1812.rs        # ITU-R P.1812-7
│   │       │   └── p530.rs         # ITU-R P.530 microwave link
│   │       ├── diffraction.rs      # Knife-edge diffraction (Epstein-Peterson, Deygout)
│   │       ├── fresnel.rs          # Fresnel zone calculations
│   │       ├── atmosphere.rs       # Atmospheric absorption, refractivity
│   │       ├── vegetation.rs       # Brazilian biome correction layer
│   │       ├── common.rs           # Shared types, Earth radius, unit conversions
│   │       └── coverage.rs         # Coverage footprint computation (grid evaluation)
│   │
│   ├── enlace-optimizer/
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── candidates.rs    # Generate candidate tower locations
│   │       ├── setcover.rs      # Greedy set-cover algorithm
│   │       ├── annealing.rs     # Simulated annealing refinement
│   │       ├── constraints.rs   # Tower height, spacing, access constraints
│   │       └── output.rs        # Design package generation
│   │
│   ├── enlace-service/
│   │   ├── Cargo.toml
│   │   ├── build.rs             # protobuf compilation
│   │   ├── proto/
│   │   │   └── rf_service.proto # gRPC service definition
│   │   └── src/
│   │       ├── main.rs          # gRPC server entry point
│   │       ├── handlers.rs      # Request handlers
│   │       └── config.rs        # Service configuration
│   │
│   └── enlace-raster/
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs
│           ├── geotiff.rs       # GeoTIFF writer for coverage maps
│           └── renderer.rs      # Signal strength to color mapping
```

## CRATE: enlace-terrain

### srtm.rs — SRTM Tile Reader

```rust
/// SRTM HGT tile reader with memory-mapped I/O and LRU cache.
/// Adapted from rf-signals repo's SRTM reader.
/// 
/// HGT format: 3601x3601 grid of big-endian i16 values (1 arc-second resolution)
/// Each tile covers 1°x1° area. Filename encodes SW corner: S23W044.hgt
/// 
/// Memory mapping: Each tile is ~25MB. With an LRU cache of 50 tiles,
/// memory usage is ~1.25 GB. Sufficient for any single design job.
/// Tiles used across the entire Brazil dataset: ~800 tiles = ~20 GB.
/// Only cache the actively needed tiles.

pub struct SrtmCache {
    tile_dir: PathBuf,        // MinIO mount or local directory
    cache: LruCache<String, MmapTile>,
    cache_size: usize,
}

pub struct MmapTile {
    mmap: Mmap,               // Memory-mapped file
    sw_lat: f64,              // Southwest corner latitude
    sw_lon: f64,              // Southwest corner longitude
    samples: usize,           // 3601 for 1-arc-second
}

impl SrtmCache {
    /// Get elevation at a specific lat/lon coordinate.
    /// Returns None if tile not found or point is over ocean (void = -32768).
    pub fn elevation(&mut self, lat: f64, lon: f64) -> Option<f64>;
    
    /// Extract terrain profile between two points.
    /// Samples at intervals of `step_m` meters along the great-circle path.
    /// Returns Vec<ProfilePoint> with distance_m and elevation_m.
    pub fn terrain_profile(&mut self, 
        lat1: f64, lon1: f64, 
        lat2: f64, lon2: f64, 
        step_m: f64
    ) -> Vec<ProfilePoint>;
}

pub struct ProfilePoint {
    pub distance_m: f64,
    pub elevation_m: f64,
    pub latitude: f64,
    pub longitude: f64,
}
```

### profile.rs — Terrain Profile Extraction

```rust
/// Extract a terrain profile between two geographic points.
/// 
/// Algorithm:
/// 1. Compute great-circle distance between points
/// 2. Generate intermediate points at `step_m` intervals along the great-circle path
/// 3. For each intermediate point, query SRTM elevation
/// 4. Apply Earth curvature correction: 
///    earth_bulge_m = distance_m² / (2 * k * earth_radius_m)
///    where k = effective Earth radius factor (default 4/3 for standard atmosphere)
/// 5. Return profile as Vec<ProfilePoint>
///
/// The k-factor can be adjusted for Brazilian tropical conditions:
/// - Standard atmosphere: k = 4/3 (1.333)
/// - Tropical moist conditions: k can vary 1.2 to 2.0
/// - Sub-refractive (worst case): k = 2/3
/// Use INMET radiosonde data to determine regional k-factor if available.

pub fn extract_profile(
    cache: &mut SrtmCache,
    start: GeoPoint,
    end: GeoPoint,
    step_m: f64,
    k_factor: f64,
) -> TerrainProfile;

pub struct TerrainProfile {
    pub points: Vec<ProfilePoint>,
    pub distance_m: f64,
    pub max_elevation_m: f64,
    pub min_elevation_m: f64,
    pub num_obstructions: usize,  // Points above line-of-sight
}
```

## CRATE: enlace-propagation

### models/itm.rs — Longley-Rice Irregular Terrain Model

```rust
/// Longley-Rice ITM implementation.
/// Ported from rf-signals repo which ported from Cloud-RF Signal Server.
/// 
/// Input parameters:
/// - Terrain profile between TX and RX
/// - Frequency (MHz)
/// - TX/RX antenna heights above ground (m)
/// - Polarization (horizontal/vertical)
/// - Surface refractivity (N-units) — use 360 for Brazilian tropical default
/// - Ground conductivity (S/m) — varies by Brazilian soil type
/// - Ground dielectric constant — varies by Brazilian soil type
/// - Climate type (1=equatorial, 2=continental subtropical, etc.)
///   Brazil: use 1 (equatorial) for Amazon, 2 (continental subtropical) for South/Southeast
/// - Statistical parameters: time variability, location variability, situation variability
///
/// Output:
/// - Path loss (dB)
/// - Mode of propagation (line-of-sight, diffraction, troposcatter)
/// - Variability

/// Brazilian soil type RF parameters (from Embrapa characterization + RF literature):
/// | Soil Type       | Region        | Conductivity (S/m) | Dielectric Const |
/// |-----------------|---------------|--------------------|------------------|
/// | Laterite (red)  | Amazon, MG    | 0.01 - 0.03        | 10 - 15          |
/// | Sandy           | NE coast      | 0.001 - 0.01       | 3 - 10           |
/// | Clay (terra roxa)| SP, PR, cerrado| 0.02 - 0.05      | 15 - 25          |
/// | Alluvial        | River valleys | 0.01 - 0.03        | 10 - 20          |

pub fn itm_path_loss(
    profile: &TerrainProfile,
    params: &ItmParams,
) -> ItmResult;

pub struct ItmParams {
    pub frequency_mhz: f64,
    pub tx_height_m: f64,
    pub rx_height_m: f64,
    pub polarization: Polarization,
    pub surface_refractivity: f64,  // Default: 360 for Brazil tropical
    pub ground_conductivity: f64,   // S/m, varies by soil type
    pub ground_dielectric: f64,     // Relative permittivity
    pub climate: Climate,
    pub time_pct: f64,              // Time variability (0.5 = 50%)
    pub location_pct: f64,          // Location variability
    pub situation_pct: f64,         // Situation variability
}

pub struct ItmResult {
    pub path_loss_db: f64,
    pub mode: PropagationMode,
    pub variability_db: f64,
    pub warnings: Vec<String>,
}
```

### vegetation.rs — Brazilian Biome Correction Layer

```rust
/// Brazilian-specific vegetation correction layer.
/// Applied AFTER base propagation model calculation.
/// 
/// Architecture:
/// 1. For the signal path between TX and RX, sample land cover at intervals
/// 2. For each segment that passes through vegetation, look up the biome correction
/// 3. Apply distance-weighted correction:
///    total_correction = Σ (segment_correction_db * segment_length / total_path_length)
///
/// Correction factors are loaded from the biome_rf_corrections database table
/// and cached in memory at service startup.
///
/// CRITICAL: This is what makes the platform's predictions more accurate
/// than any international tool for Brazilian deployments.

pub struct VegetationCorrector {
    corrections: Vec<BiomeCorrection>,  // Loaded from DB at startup
}

pub struct BiomeCorrection {
    pub biome_type: String,
    pub freq_min_mhz: f64,
    pub freq_max_mhz: f64,
    pub loss_db_min: f64,
    pub loss_db_max: f64,
    pub loss_db_mean: f64,
    pub loss_db_stddev: f64,
}

impl VegetationCorrector {
    /// Query land cover along a path and compute total vegetation correction.
    /// 
    /// `land_cover_fn` is a closure that returns the land cover type 
    /// for a given (lat, lon) — typically backed by a PostGIS query
    /// or a cached raster lookup.
    pub fn compute_correction<F>(
        &self,
        profile: &TerrainProfile,
        frequency_mhz: f64,
        land_cover_fn: F,
    ) -> VegetationCorrectionResult
    where
        F: Fn(f64, f64) -> Option<LandCoverInfo>;
}

pub struct LandCoverInfo {
    pub cover_type: String,  // 'forest', 'savanna', etc.
    pub biome: String,       // 'amazonia', 'cerrado', etc.
    pub density_pct: f64,    // Vegetation coverage percentage
}

pub struct VegetationCorrectionResult {
    pub total_correction_db: f64,
    pub segments: Vec<PathSegmentCorrection>,
    pub confidence: f64,
}

pub struct PathSegmentCorrection {
    pub start_distance_m: f64,
    pub end_distance_m: f64,
    pub biome: String,
    pub correction_db: f64,
}
```

### coverage.rs — Coverage Footprint Computation

```rust
/// Compute signal strength at every grid point within a coverage area.
/// This is the most computationally intensive function in the platform.
///
/// For a single tower covering 20km radius at 30m resolution:
/// - Grid points: π * (20000/30)² ≈ 1.4 million points
/// - Each point requires: terrain profile extraction + propagation model + vegetation correction
/// - Total: ~1.4 million propagation calculations
///
/// Optimization strategies:
/// 1. Parallel computation using Rayon (one thread per grid row)
/// 2. SRTM tile caching (most queries hit same few tiles)
/// 3. Early termination: skip points beyond maximum range for the frequency
/// 4. Coarse-to-fine: compute on 90m grid first, then refine areas near threshold
/// 5. Pre-compute terrain profiles for radial lines, interpolate between

pub fn compute_coverage(
    tower: &TowerConfig,
    area: &CoverageArea,
    propagation_model: &dyn PropagationModel,
    vegetation_corrector: &VegetationCorrector,
    terrain_cache: &mut SrtmCache,
    grid_resolution_m: f64,
) -> CoverageResult;

pub struct TowerConfig {
    pub latitude: f64,
    pub longitude: f64,
    pub antenna_height_m: f64,
    pub frequency_mhz: f64,
    pub tx_power_dbm: f64,
    pub antenna_gain_dbi: f64,
    pub antenna_pattern: AntennaPattern,  // Omnidirectional or sectoral
    pub num_sectors: u8,
    pub sector_azimuths: Vec<f64>,
    pub mechanical_tilt_deg: f64,
}

pub struct CoverageArea {
    pub center_lat: f64,
    pub center_lon: f64,
    pub radius_m: f64,
    // OR polygon boundary:
    pub boundary: Option<Vec<GeoPoint>>,
}

pub struct CoverageResult {
    pub grid: Vec<Vec<CoveragePoint>>,
    pub grid_resolution_m: f64,
    pub bbox: BoundingBox,
    pub coverage_stats: CoverageStats,
}

pub struct CoveragePoint {
    pub latitude: f64,
    pub longitude: f64,
    pub signal_strength_dbm: f64,
    pub path_loss_db: f64,
    pub vegetation_correction_db: f64,
    pub propagation_mode: PropagationMode,
}

pub struct CoverageStats {
    pub total_points: usize,
    pub covered_points: usize,  // Above minimum threshold
    pub coverage_pct: f64,
    pub area_km2: f64,
    pub covered_area_km2: f64,
    pub avg_signal_dbm: f64,
    pub min_signal_dbm: f64,
    pub max_signal_dbm: f64,
}
```

## CRATE: enlace-optimizer

### Tower Placement Optimization

```rust
/// Find minimum number of towers and optimal placement to achieve
/// coverage target over a defined area.
///
/// Algorithm:
/// Phase 1 — Candidate Generation:
///   1. Generate candidates along OSM roads within/near area (spacing: 500m)
///   2. Generate candidates at SRTM local elevation maxima (hilltops)
///   3. Generate candidates at power line tower positions (from ANEEL data)
///   4. Filter: remove candidates in water bodies, environmental restrictions, flood zones
///   5. For each candidate, pre-compute coverage footprint
///
/// Phase 2 — Greedy Set-Cover:
///   1. Select candidate with largest uncovered area coverage
///   2. Mark its coverage area as covered
///   3. Repeat until coverage target met or max towers reached
///   4. This gives an initial solution (typically within 1.5x of optimal)
///
/// Phase 3 — Simulated Annealing Refinement:
///   1. Start with greedy solution
///   2. Perturbations: move a tower to adjacent candidate, swap two towers, remove a tower
///   3. Accept if coverage target still met with fewer towers
///   4. Accept worse solutions with probability exp(-delta/temperature)
///   5. Cool temperature over iterations
///   6. Typically improves greedy solution by 10-20% (1-2 fewer towers)
///
/// Phase 4 — Output Generation:
///   1. For each selected tower: GPS coordinates, height recommendation, coverage footprint
///   2. Inter-tower backhaul design (microwave link budget using P.530)
///   3. Frequency plan (avoid co-channel interference between adjacent sectors)
///   4. Equipment bill of materials
///   5. CAPEX estimate from published benchmarks

pub fn optimize_tower_placement(
    area: &CoverageArea,
    params: &OptimizationParams,
    terrain_cache: &mut SrtmCache,
    road_network: &RoadNetwork,
    power_network: &PowerNetwork,
    propagation_model: &dyn PropagationModel,
    vegetation_corrector: &VegetationCorrector,
) -> OptimizationResult;

pub struct OptimizationParams {
    pub coverage_target_pct: f64,      // e.g., 95.0
    pub min_signal_dbm: f64,           // e.g., -95.0
    pub max_towers: usize,             // Budget constraint
    pub frequency_mhz: f64,
    pub tx_power_dbm: f64,
    pub antenna_gain_dbi: f64,
    pub antenna_height_m: f64,
    pub candidate_spacing_m: f64,      // Default: 500m along roads
    pub annealing_iterations: usize,   // Default: 10000
    pub annealing_initial_temp: f64,   // Default: 100.0
    pub annealing_cooling_rate: f64,   // Default: 0.995
}

pub struct OptimizationResult {
    pub towers: Vec<TowerPlacement>,
    pub total_coverage_pct: f64,
    pub covered_area_km2: f64,
    pub estimated_capex_brl: f64,
    pub backhaul_links: Vec<BackhaulLink>,
    pub equipment_bom: Vec<BomItem>,
    pub computation_time_secs: f64,
}

pub struct TowerPlacement {
    pub id: usize,
    pub latitude: f64,
    pub longitude: f64,
    pub elevation_m: f64,           // Ground elevation from SRTM
    pub antenna_height_m: f64,
    pub coverage_footprint: Vec<CoveragePoint>,
    pub coverage_area_km2: f64,
    pub unique_coverage_km2: f64,   // Not covered by other towers
}

pub struct BackhaulLink {
    pub from_tower_id: usize,
    pub to_tower_id: usize,
    pub distance_km: f64,
    pub frequency_ghz: f64,
    pub path_loss_db: f64,
    pub rain_attenuation_db: f64,   // From ITU-R P.530 for Brazilian rain rates
    pub fade_margin_db: f64,
    pub availability_pct: f64,
}
```

## gRPC SERVICE DEFINITION

```protobuf
// proto/rf_service.proto
syntax = "proto3";
package enlace.rf;

service RfEngine {
    // Single point path loss calculation
    rpc CalculatePathLoss(PathLossRequest) returns (PathLossResponse);
    
    // Coverage footprint for a single tower
    rpc ComputeCoverage(CoverageRequest) returns (CoverageResponse);
    
    // Tower placement optimization (long-running)
    rpc OptimizeTowers(OptimizeRequest) returns (stream OptimizeProgress);
    
    // Point-to-point microwave link budget
    rpc LinkBudget(LinkBudgetRequest) returns (LinkBudgetResponse);
    
    // Terrain profile extraction
    rpc TerrainProfile(ProfileRequest) returns (ProfileResponse);
    
    // Health check
    rpc Health(HealthRequest) returns (HealthResponse);
}

message PathLossRequest {
    double tx_lat = 1;
    double tx_lon = 2;
    double tx_height_m = 3;
    double rx_lat = 4;
    double rx_lon = 5;
    double rx_height_m = 6;
    double frequency_mhz = 7;
    string model = 8;  // "itm", "hata", "tr38901", "p1812"
    bool apply_vegetation = 9;
    string country_code = 10;
}

message CoverageRequest {
    double tower_lat = 1;
    double tower_lon = 2;
    double tower_height_m = 3;
    double frequency_mhz = 4;
    double tx_power_dbm = 5;
    double antenna_gain_dbi = 6;
    double radius_m = 7;
    double grid_resolution_m = 8;
    double min_signal_dbm = 9;
    bool apply_vegetation = 10;
    string country_code = 11;
    // Optional: polygon boundary instead of radius
    repeated GeoPoint boundary = 12;
}

message OptimizeRequest {
    repeated GeoPoint area_boundary = 1;
    double coverage_target_pct = 2;
    double min_signal_dbm = 3;
    uint32 max_towers = 4;
    double frequency_mhz = 5;
    double tx_power_dbm = 6;
    double antenna_gain_dbi = 7;
    double antenna_height_m = 8;
    bool apply_vegetation = 9;
    string country_code = 10;
}

message GeoPoint {
    double latitude = 1;
    double longitude = 2;
}
```

## VALIDATION TESTS — Phase 2 RF Engine

```rust
// tests/validation/rf_validation.rs

/// Test 1: Free-space path loss
/// At 700 MHz, 1 km distance:
/// FSPL = 20*log10(1000) + 20*log10(700e6) + 20*log10(4π/c)
/// Expected: approximately 87.3 dB
/// Tolerance: ±0.1 dB

/// Test 2: Flat terrain (no obstructions)
/// ITM with flat terrain profile should approximate FSPL + ground reflection
/// Expected: within 3 dB of FSPL for distances < 1 km LOS

/// Test 3: Known Brazilian measurement — UFPA Amazon cities
/// Paper: "Path loss model for densely arboreous cities in Amazon Region" (IEEE)
/// Measurement: Belém, 900 MHz, base station at 30m, mobile at 1.5m
/// Published results: path loss at 1 km ≈ 135-145 dB (with vegetation)
/// Platform prediction: should be within ±8 dB of published measurements

/// Test 4: Known Brazilian measurement — PUC-Rio
/// Paper: "Empirical Model for Propagation Loss Through Tropical Woodland" (IEEE)
/// Measurement: Rio de Janeiro park, 900-1800 MHz
/// Published: vegetation excess loss at 100m depth ≈ 10-20 dB at 900 MHz
/// Platform vegetation correction for mata_atlantica at 900 MHz: 8-15 dB
/// Should overlap with published range

/// Test 5: Coverage computation performance
/// Area: 20 km radius, 30m grid resolution
/// Expected computation time: < 5 minutes on 8-core machine
/// Coverage map should be reasonable: ~60-80% coverage in mixed terrain

/// Test 6: Tower optimization convergence
/// Area: 10,000 hectares flat farmland at 700 MHz
/// Expected: 3-6 towers for 95% coverage
/// Greedy solution should be within 2x of this
/// Simulated annealing should improve by at least 10%

/// Test 7: Backhaul link budget
/// ITU-R P.530 at 18 GHz, 10 km link, Brazilian tropical rain zone
/// Published rain rate for Brazil Region P (tropical): 145 mm/h (0.01%)
/// Expected rain attenuation: approximately 30-50 dB for 10 km
/// System availability should be calculable
```

## COMPLETION CRITERIA

Phase 2 RF Engine is complete when:
1. All propagation models implemented and unit-tested
2. Brazilian vegetation corrections applied and validated against published papers
3. Coverage footprint computation works for arbitrary tower locations
4. Tower placement optimizer produces reasonable designs for test scenarios
5. gRPC service responds to all defined RPCs
6. Performance: coverage computation for 20km radius < 5 minutes
7. Validation: predictions within ±8 dB of published Brazilian measurements
8. GeoTIFF coverage maps render correctly in the frontend map layer
