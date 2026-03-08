//! Coverage grid computation with Rayon parallelism.
//!
//! Computes signal strength over a geographic area for a given tower
//! configuration. Uses FSPL model for grid computation (terrain-aware
//! models are too slow for millions of grid points without real SRTM data).
//! In production, a coarse-to-fine strategy with ITM would be preferred.

use rayon::prelude::*;

use crate::common::{haversine_distance, AntennaPattern};
use crate::models::fspl::FsplModel;

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
    /// Received signal strength in dBm.
    pub signal_strength_dbm: f64,
    /// Path loss in dB.
    pub path_loss_db: f64,
}

/// Summary statistics for a coverage computation.
#[derive(Debug, Clone)]
pub struct CoverageStats {
    /// Total number of grid points computed.
    pub total_points: usize,
    /// Number of points above the minimum signal threshold.
    pub covered_points: usize,
    /// Coverage percentage (covered / total * 100).
    pub coverage_pct: f64,
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

    let points: Vec<CoveragePoint> = grid_coords
        .par_iter()
        .map(|&(lat, lon)| {
            let distance = haversine_distance(tower.latitude, tower.longitude, lat, lon);
            let distance_clamped = distance.max(1.0); // Avoid log(0)

            let path_loss = FsplModel::compute(tower.frequency_mhz, distance_clamped);
            let signal_strength = eirp - path_loss;

            CoveragePoint {
                latitude: lat,
                longitude: lon,
                signal_strength_dbm: signal_strength,
                path_loss_db: path_loss,
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
        }
    }

    #[test]
    fn test_coverage_basic() {
        let tower = test_tower();
        let area = CoverageArea {
            center_lat: tower.latitude,
            center_lon: tower.longitude,
            radius_m: 1000.0,
        };

        let result = compute_coverage(&tower, &area, 100.0, -100.0);

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

        let result = compute_coverage(&tower, &area, 500.0, -120.0);

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

        let result = compute_coverage(&tower, &area, 200.0, -100.0);

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

        let result = compute_coverage(&tower, &area, 100.0, -100.0);
        // May have 0 or 1 point
        assert!(result.stats.total_points <= 1);
    }
}
