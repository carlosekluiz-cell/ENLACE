//! Coverage grid computation with Rayon parallelism.
//!
//! Computes signal strength over a geographic area for a given tower
//! configuration. Base path loss is model-dispatched by frequency and
//! environment (Hata for 150-2000 MHz, 3GPP TR 38.901 RMa/UMa above,
//! FSPL floor everywhere), and an optional in-memory terrain grid adds
//! single-knife-edge diffraction loss along each tower->point ray.

use rayon::prelude::*;

use crate::common::{haversine_distance, AntennaPattern};
use crate::diffraction::deygout_diffraction_loss;
use crate::models::fspl::FsplModel;
use crate::models::hata::{CitySize, HataModel};
use crate::models::tr38901::{Tr38901RmaModel, Tr38901UmaModel};
use crate::models::{Environment, PathLossParams, PropagationModel};

/// Effective earth radius (k = 4/3) in meters, for curvature bulge.
const EFFECTIVE_EARTH_RADIUS_M: f64 = 4.0 / 3.0 * 6_371_000.0;

/// Tower/transmitter configuration.
#[derive(Debug, Clone)]
pub struct TowerConfig {
    /// Tower latitude in decimal degrees.
    pub latitude: f64,
    /// Tower longitude in decimal degrees.
    pub longitude: f64,
    /// Antenna height above ground in meters.
    pub antenna_height_m: f64,
    /// Carrier frequency in MHz.
    pub frequency_mhz: f64,
    /// Transmitter output power in dBm.
    pub tx_power_dbm: f64,
    /// Antenna gain in dBi.
    pub antenna_gain_dbi: f64,
    /// Antenna radiation pattern.
    pub antenna_pattern: AntennaPattern,
    /// Environment classification (drives base-loss model selection).
    pub environment: Environment,
    /// Optional sector antenna (None = omnidirectional).
    pub sector: Option<Sector>,
}

/// Sector antenna definition with a 3GPP TR 36.814-style pattern.
#[derive(Debug, Clone, Copy)]
pub struct Sector {
    /// Boresight azimuth in degrees (0 = north, clockwise).
    pub azimuth_deg: f64,
    /// Horizontal half-power beamwidth in degrees (e.g. 65, 90, 120).
    pub beamwidth_deg: f64,
    /// Mechanical downtilt in degrees (positive = down).
    pub downtilt_deg: f64,
}

impl Sector {
    /// Pattern attenuation (dB >= 0) toward a point at `bearing_deg` and
    /// `elev_angle_deg` (negative = below horizon) from the antenna.
    /// A(az) = min(12*(Δ/HPBW)^2, 25 dB); vertical HPBW fixed at 10°,
    /// A(el) = min(12*((θ+tilt)/10)^2, 20 dB) — standard 3GPP shapes.
    pub fn attenuation_db(&self, bearing_deg: f64, elev_angle_deg: f64) -> f64 {
        let mut d_az = (bearing_deg - self.azimuth_deg).abs() % 360.0;
        if d_az > 180.0 {
            d_az = 360.0 - d_az;
        }
        let a_h = (12.0 * (d_az / self.beamwidth_deg.max(1.0)).powi(2)).min(25.0);
        let d_el = elev_angle_deg + self.downtilt_deg; // 0 when aimed at point
        let a_v = (12.0 * (d_el / 10.0).powi(2)).min(20.0);
        (a_h + a_v).min(30.0)
    }
}

/// Initial bearing from (lat1,lon1) to (lat2,lon2), degrees clockwise from north.
fn bearing_deg(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (p1, p2) = (lat1.to_radians(), lat2.to_radians());
    let dl = (lon2 - lon1).to_radians();
    let y = dl.sin() * p2.cos();
    let x = p1.cos() * p2.sin() - p1.sin() * p2.cos() * dl.cos();
    (y.atan2(x).to_degrees() + 360.0) % 360.0
}

/// Regular lat/lon elevation raster held in memory for fast ray sampling.
///
/// Row 0 is the NORTH edge (`lat_max`); values are metres AMSL; NaN marks
/// cells with no data (treated as sea level).
#[derive(Debug, Clone)]
pub struct TerrainGrid {
    pub data: Vec<f32>,
    pub width: usize,
    pub height: usize,
    pub lat_max: f64,
    pub lon_min: f64,
    /// Degrees per row (positive).
    pub lat_step: f64,
    /// Degrees per column (positive).
    pub lon_step: f64,
}

impl TerrainGrid {
    /// Nearest-cell elevation; None outside the grid, 0.0 for NaN cells.
    pub fn elevation_at(&self, lat: f64, lon: f64) -> Option<f64> {
        let row = ((self.lat_max - lat) / self.lat_step).round();
        let col = ((lon - self.lon_min) / self.lon_step).round();
        if row < 0.0 || col < 0.0 {
            return None;
        }
        let (row, col) = (row as usize, col as usize);
        if row >= self.height || col >= self.width {
            return None;
        }
        let v = self.data[row * self.width + col];
        Some(if v.is_nan() { 0.0 } else { v as f64 })
    }
}

/// Base (unobstructed) path loss with model dispatch by frequency band and
/// environment. FSPL acts as the physical floor: no model may predict less
/// loss than free space (also guards Hata below its 1 km validity).
///
/// Returns `(median_loss_db, shadow_fading_sigma_db)` — the sigma is the
/// model's log-normal location variability, used for P90 coverage.
fn base_path_loss_db(
    freq_mhz: f64,
    distance_m: f64,
    tx_height_m: f64,
    rx_height_m: f64,
    environment: Environment,
) -> (f64, f64) {
    let fspl = FsplModel::compute(freq_mhz, distance_m);
    let params = PathLossParams {
        frequency_mhz: freq_mhz,
        distance_m,
        tx_height_m,
        rx_height_m,
        terrain_profile: None,
        environment,
    };
    let (model_loss, sigma) = if (150.0..=2000.0).contains(&freq_mhz) {
        let city = match environment {
            Environment::Urban => CitySize::Large,
            _ => CitySize::SmallMedium,
        };
        let r = HataModel::new(city).path_loss(&params);
        (r.loss_db, r.variability_db)
    } else if freq_mhz > 2000.0 {
        let r = match environment {
            Environment::Urban | Environment::Suburban => {
                Tr38901UmaModel::new().path_loss(&params)
            }
            _ => Tr38901RmaModel::new().path_loss(&params),
        };
        (r.loss_db, r.variability_db)
    } else {
        // Below all model ranges: FSPL median with a generic land-path
        // shadowing assumption (log-normal sigma ~5.5 dB).
        (fspl, 5.5)
    };
    (model_loss.max(fspl), sigma)
}

/// Terrain diffraction loss along the tower->receiver ray, using the
/// Deygout multiple-knife-edge method over a sampled profile.
///
/// Samples the terrain grid along the chord (linear lat/lon interpolation
/// is fine at coverage scales) and applies the k=4/3 effective-earth bulge
/// to interior points, so successive ridge lines (serra terrain) each
/// contribute — a single dominant edge underestimates multi-ridge paths.
#[allow(clippy::too_many_arguments)]
fn terrain_diffraction_db(
    grid: &TerrainGrid,
    tx_lat: f64,
    tx_lon: f64,
    tx_ground: f64,
    tx_height_m: f64,
    rx_lat: f64,
    rx_lon: f64,
    rx_ground: f64,
    rx_height_m: f64,
    distance_m: f64,
    freq_mhz: f64,
    sample_step_m: f64,
) -> f64 {
    if distance_m < 2.0 * sample_step_m {
        return 0.0;
    }
    // Cap samples: bounds both HTTP-free grid lookups and Deygout recursion.
    let n = ((distance_m / sample_step_m) as usize).clamp(2, 200);
    let mut profile: Vec<(f64, f64)> = Vec::with_capacity(n + 1);
    profile.push((0.0, tx_ground));
    for i in 1..n {
        let frac = i as f64 / n as f64;
        let lat = tx_lat + frac * (rx_lat - tx_lat);
        let lon = tx_lon + frac * (rx_lon - tx_lon);
        let elev = grid.elevation_at(lat, lon).unwrap_or(0.0);
        let d1 = frac * distance_m;
        let bulge = d1 * (distance_m - d1) / (2.0 * EFFECTIVE_EARTH_RADIUS_M);
        profile.push((d1, elev + bulge));
    }
    profile.push((distance_m, rx_ground));
    deygout_diffraction_loss(&profile, tx_height_m, rx_height_m, freq_mhz)
}

/// Definition of the coverage computation area.
#[derive(Debug, Clone)]
pub struct CoverageArea {
    /// Center latitude in decimal degrees.
    pub center_lat: f64,
    /// Center longitude in decimal degrees.
    pub center_lon: f64,
    /// Coverage radius in meters.
    pub radius_m: f64,
}

/// A single computed coverage point.
#[derive(Debug, Clone)]
pub struct CoveragePoint {
    /// Point latitude.
    pub latitude: f64,
    /// Point longitude.
    pub longitude: f64,
    /// Received signal strength in dBm (P50 / median prediction).
    pub signal_strength_dbm: f64,
    /// Path loss in dB.
    pub path_loss_db: f64,
    /// Log-normal shadow-fading sigma for this point in dB.
    pub sigma_db: f64,
}

/// Summary statistics for a coverage computation.
#[derive(Debug, Clone)]
pub struct CoverageStats {
    /// Total number of grid points computed.
    pub total_points: usize,
    /// Number of points above the minimum signal threshold.
    pub covered_points: usize,
    /// Coverage percentage (covered / total * 100), at the P50 prediction.
    pub coverage_pct: f64,
    /// Coverage percentage with 90% location confidence: covered only if
    /// P50 signal - 1.282*sigma still clears the threshold.
    pub coverage_pct_p90: f64,
    /// Mean shadow-fading sigma across the grid in dB.
    pub sigma_db: f64,
    /// Total area of the computation grid in km^2.
    pub area_km2: f64,
    /// Covered area in km^2.
    pub covered_area_km2: f64,
    /// Average signal strength across all points in dBm.
    pub avg_signal_dbm: f64,
    /// Minimum signal strength in dBm.
    pub min_signal_dbm: f64,
    /// Maximum signal strength in dBm.
    pub max_signal_dbm: f64,
}

/// Complete coverage computation result.
#[derive(Debug, Clone)]
pub struct CoverageResult {
    /// All computed grid points.
    pub points: Vec<CoveragePoint>,
    /// Summary statistics.
    pub stats: CoverageStats,
    /// Grid resolution in meters.
    pub grid_resolution_m: f64,
}

/// Compute coverage grid for a given tower configuration.
///
/// Generates a grid of points within `area.radius_m` of the tower,
/// computes FSPL-based path loss for each point in parallel using Rayon,
/// and returns signal strength predictions with summary statistics.
///
/// # Parameters
/// - `tower`: transmitter configuration
/// - `area`: coverage computation area
/// - `grid_resolution_m`: spacing between grid points in meters
/// - `min_signal_dbm`: minimum signal threshold for "covered" classification
///
/// # Returns
/// A `CoverageResult` with all grid points and statistics.
pub fn compute_coverage(
    tower: &TowerConfig,
    area: &CoverageArea,
    grid_resolution_m: f64,
    min_signal_dbm: f64,
    terrain: Option<&TerrainGrid>,
) -> CoverageResult {
    let resolution = grid_resolution_m.max(1.0);

    // Convert radius to approximate degree offsets
    // At the equator, 1 degree ≈ 111,320 m
    // Adjust for latitude
    let lat_rad = area.center_lat.to_radians();
    let meters_per_deg_lat = 111_320.0;
    let meters_per_deg_lon = 111_320.0 * lat_rad.cos();

    let lat_range = area.radius_m / meters_per_deg_lat;
    let lon_range = area.radius_m / meters_per_deg_lon.max(1.0);

    let lat_step = resolution / meters_per_deg_lat;
    let lon_step = resolution / meters_per_deg_lon.max(1.0);

    // Generate grid points
    let mut grid_coords: Vec<(f64, f64)> = Vec::new();

    let lat_min = area.center_lat - lat_range;
    let lat_max = area.center_lat + lat_range;
    let lon_min = area.center_lon - lon_range;
    let lon_max = area.center_lon + lon_range;

    let mut lat = lat_min;
    while lat <= lat_max {
        let mut lon = lon_min;
        while lon <= lon_max {
            // Check if within radius
            let dist = haversine_distance(area.center_lat, area.center_lon, lat, lon);
            if dist <= area.radius_m {
                grid_coords.push((lat, lon));
            }
            lon += lon_step;
        }
        lat += lat_step;
    }

    // Compute coverage for each point in parallel
    let eirp = tower.tx_power_dbm + tower.antenna_gain_dbi;
    let rx_height_m = 1.5;
    let tx_ground = terrain
        .and_then(|g| g.elevation_at(tower.latitude, tower.longitude))
        .unwrap_or(0.0);
    let tx_amsl_for_sector = tx_ground + tower.antenna_height_m;
    // Keep the per-ray terrain walk bounded (<=400 samples) on large areas.
    let ray_step_m = resolution.max(area.radius_m / 200.0).max(30.0);

    let points: Vec<CoveragePoint> = grid_coords
        .par_iter()
        .map(|&(lat, lon)| {
            let distance = haversine_distance(tower.latitude, tower.longitude, lat, lon);
            let distance_clamped = distance.max(1.0); // Avoid log(0)

            let (mut path_loss, sigma_db) = base_path_loss_db(
                tower.frequency_mhz,
                distance_clamped,
                tower.antenna_height_m,
                rx_height_m,
                tower.environment,
            );
            if let Some(grid) = terrain {
                if let Some(rx_ground) = grid.elevation_at(lat, lon) {
                    path_loss += terrain_diffraction_db(
                        grid,
                        tower.latitude,
                        tower.longitude,
                        tx_ground,
                        tower.antenna_height_m,
                        lat,
                        lon,
                        rx_ground,
                        rx_height_m,
                        distance_clamped,
                        tower.frequency_mhz,
                        ray_step_m,
                    );
                }
            }
            // Sector pattern: attenuate off-boresight directions.
            let mut pattern_db = 0.0;
            if let Some(sec) = &tower.sector {
                let brg = bearing_deg(tower.latitude, tower.longitude, lat, lon);
                let rx_g = terrain
                    .and_then(|g| g.elevation_at(lat, lon))
                    .unwrap_or(tx_ground);
                let dh = (rx_g + rx_height_m) - tx_amsl_for_sector;
                let elev_angle = dh.atan2(distance_clamped).to_degrees();
                pattern_db = sec.attenuation_db(brg, elev_angle);
            }
            let signal_strength = eirp - path_loss - pattern_db;

            CoveragePoint {
                latitude: lat,
                longitude: lon,
                signal_strength_dbm: signal_strength,
                path_loss_db: path_loss + pattern_db,
                sigma_db,
            }
        })
        .collect();

    // Compute statistics
    let total_points = points.len();

    if total_points == 0 {
        return CoverageResult {
            points: Vec::new(),
            stats: CoverageStats {
                total_points: 0,
                covered_points: 0,
                coverage_pct: 0.0,
                coverage_pct_p90: 0.0,
                sigma_db: 0.0,
                area_km2: 0.0,
                covered_area_km2: 0.0,
                avg_signal_dbm: 0.0,
                min_signal_dbm: 0.0,
                max_signal_dbm: 0.0,
            },
            grid_resolution_m: resolution,
        };
    }

    let covered_points = points
        .iter()
        .filter(|p| p.signal_strength_dbm >= min_signal_dbm)
        .count();

    let coverage_pct = 100.0 * covered_points as f64 / total_points as f64;

    // P90 location confidence: z(0.90) = 1.282 of log-normal shadow fading.
    let covered_p90 = points
        .iter()
        .filter(|p| p.signal_strength_dbm - 1.282 * p.sigma_db >= min_signal_dbm)
        .count();
    let coverage_pct_p90 = 100.0 * covered_p90 as f64 / total_points as f64;
    let sigma_avg = points.iter().map(|p| p.sigma_db).sum::<f64>() / total_points as f64;

    let total_area_km2 = std::f64::consts::PI * (area.radius_m / 1000.0).powi(2);
    let covered_area_km2 = total_area_km2 * coverage_pct / 100.0;

    let signal_sum: f64 = points.iter().map(|p| p.signal_strength_dbm).sum();
    let avg_signal = signal_sum / total_points as f64;

    let min_signal = points
        .iter()
        .map(|p| p.signal_strength_dbm)
        .fold(f64::INFINITY, f64::min);
    let max_signal = points
        .iter()
        .map(|p| p.signal_strength_dbm)
        .fold(f64::NEG_INFINITY, f64::max);

    let stats = CoverageStats {
        total_points,
        covered_points,
        coverage_pct,
        coverage_pct_p90,
        sigma_db: sigma_avg,
        area_km2: total_area_km2,
        covered_area_km2,
        avg_signal_dbm: avg_signal,
        min_signal_dbm: min_signal,
        max_signal_dbm: max_signal,
    };

    CoverageResult {
        points,
        stats,
        grid_resolution_m: resolution,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_tower() -> TowerConfig {
        TowerConfig {
            latitude: -23.55,
            longitude: -46.63,
            antenna_height_m: 30.0,
            frequency_mhz: 900.0,
            tx_power_dbm: 43.0, // 20 W
            antenna_gain_dbi: 15.0,
            antenna_pattern: AntennaPattern::Omnidirectional,
            environment: Environment::Rural,
            sector: None,
        }
    }

    #[test]
    fn test_sector_pattern_attenuation() {
        let s = Sector { azimuth_deg: 0.0, beamwidth_deg: 90.0, downtilt_deg: 3.0 };
        // Boresight, aimed elevation: ~0 dB
        assert!(s.attenuation_db(0.0, -3.0) < 0.2);
        // 45° off a 90° HPBW: 12*(0.5)^2 = 3 dB horizontal
        assert!((s.attenuation_db(45.0, -3.0) - 3.0).abs() < 0.2);
        // Behind the antenna: capped
        assert!(s.attenuation_db(180.0, -3.0) >= 25.0 - 0.01);
        // Wraparound: 350° is 10° off boresight 0°
        assert!(s.attenuation_db(350.0, -3.0) < 0.5);
    }

    #[test]
    fn test_coverage_basic() {
        let tower = test_tower();
        let area = CoverageArea {
            center_lat: tower.latitude,
            center_lon: tower.longitude,
            radius_m: 1000.0,
        };

        let result = compute_coverage(&tower, &area, 100.0, -100.0, None);

        assert!(
            result.stats.total_points > 0,
            "Should have grid points: {}",
            result.stats.total_points
        );
        assert!(
            result.stats.total_points < 10000,
            "Should not have too many points for 1km radius at 100m resolution: {}",
            result.stats.total_points
        );
    }

    #[test]
    fn test_coverage_signal_decreases_with_distance() {
        let tower = test_tower();
        let area = CoverageArea {
            center_lat: tower.latitude,
            center_lon: tower.longitude,
            radius_m: 5000.0,
        };

        let result = compute_coverage(&tower, &area, 500.0, -120.0, None);

        // Find points near and far from tower
        let near_points: Vec<&CoveragePoint> = result
            .points
            .iter()
            .filter(|p| {
                haversine_distance(tower.latitude, tower.longitude, p.latitude, p.longitude) < 500.0
            })
            .collect();

        let far_points: Vec<&CoveragePoint> = result
            .points
            .iter()
            .filter(|p| {
                haversine_distance(tower.latitude, tower.longitude, p.latitude, p.longitude)
                    > 4000.0
            })
            .collect();

        if !near_points.is_empty() && !far_points.is_empty() {
            let avg_near: f64 =
                near_points.iter().map(|p| p.signal_strength_dbm).sum::<f64>()
                    / near_points.len() as f64;
            let avg_far: f64 =
                far_points.iter().map(|p| p.signal_strength_dbm).sum::<f64>()
                    / far_points.len() as f64;

            assert!(
                avg_near > avg_far,
                "Near signal ({} dBm) should be stronger than far ({} dBm)",
                avg_near,
                avg_far
            );
        }
    }

    #[test]
    fn test_coverage_stats() {
        let tower = test_tower();
        let area = CoverageArea {
            center_lat: tower.latitude,
            center_lon: tower.longitude,
            radius_m: 2000.0,
        };

        let result = compute_coverage(&tower, &area, 200.0, -100.0, None);

        // With FSPL at 900 MHz and 43 dBm + 15 dBi EIRP = 58 dBm:
        // At 2 km: FSPL ≈ 97.5 dB, so signal ≈ -39.5 dBm
        // All points should be above -100 dBm threshold
        assert!(
            result.stats.coverage_pct > 50.0,
            "Coverage should be substantial: {}%",
            result.stats.coverage_pct
        );

        assert!(
            result.stats.max_signal_dbm > result.stats.min_signal_dbm,
            "Max ({}) should exceed min ({})",
            result.stats.max_signal_dbm,
            result.stats.min_signal_dbm
        );

        assert!(
            result.stats.area_km2 > 0.0,
            "Area should be positive: {} km^2",
            result.stats.area_km2
        );
    }

    #[test]
    fn test_coverage_empty_radius() {
        let tower = test_tower();
        let area = CoverageArea {
            center_lat: tower.latitude,
            center_lon: tower.longitude,
            radius_m: 0.0,
        };

        let result = compute_coverage(&tower, &area, 100.0, -100.0, None);
        // May have 0 or 1 point
        assert!(result.stats.total_points <= 1);
    }
}
