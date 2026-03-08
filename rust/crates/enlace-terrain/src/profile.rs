//! Terrain profile extraction between two geographic points.
//!
//! Computes elevation profiles along great-circle paths, including
//! Earth curvature correction and obstruction analysis. These profiles
//! are essential inputs for RF propagation models.

use serde::{Deserialize, Serialize};

use crate::cache::TileCache;

/// Earth radius in meters.
pub const EARTH_RADIUS_M: f64 = 6_371_000.0;

/// Default k-factor for standard atmosphere (4/3).
pub const DEFAULT_K_FACTOR: f64 = 4.0 / 3.0;

/// A geographic point specified by latitude and longitude in degrees.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct GeoPoint {
    /// Latitude in decimal degrees (positive = North).
    pub lat: f64,
    /// Longitude in decimal degrees (positive = East).
    pub lon: f64,
}

impl GeoPoint {
    /// Create a new geographic point.
    pub fn new(lat: f64, lon: f64) -> Self {
        Self { lat, lon }
    }
}

/// A point along a terrain profile.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProfilePoint {
    /// Distance from the start of the profile in meters.
    pub distance_m: f64,
    /// Elevation above mean sea level in meters.
    pub elevation_m: f64,
    /// Latitude of this point in decimal degrees.
    pub latitude: f64,
    /// Longitude of this point in decimal degrees.
    pub longitude: f64,
}

/// Complete terrain profile between two points.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TerrainProfile {
    /// Ordered list of points along the profile.
    pub points: Vec<ProfilePoint>,
    /// Total great-circle distance between start and end in meters.
    pub distance_m: f64,
    /// Maximum terrain elevation along the profile in meters.
    pub max_elevation_m: f64,
    /// Minimum terrain elevation along the profile in meters.
    pub min_elevation_m: f64,
    /// Number of points where terrain exceeds the line-of-sight between endpoints.
    /// This is computed assuming both TX and RX are at the terrain elevation
    /// (i.e., antenna heights of 0). Use with caution; for actual link analysis,
    /// antenna heights should be added to the endpoint elevations.
    pub num_obstructions: usize,
}

/// Extract a terrain profile between two geographic points.
///
/// # Algorithm
///
/// 1. Compute great-circle distance between start and end.
/// 2. Generate intermediate points at `step_m` intervals along the great-circle path.
/// 3. Query elevation for each intermediate point from the tile cache.
/// 4. Apply Earth curvature correction: `earth_bulge_m = d1 * d2 / (2 * k * R)`
///    where `d1` = distance from start, `d2` = distance from end, `k` = effective
///    Earth radius factor, `R` = Earth radius.
/// 5. Count obstructions (points above the straight line between start and end
///    terrain elevations).
///
/// # Parameters
///
/// - `cache`: Mutable reference to the tile cache for elevation queries.
/// - `start`: Starting geographic point.
/// - `end`: Ending geographic point.
/// - `step_m`: Distance in meters between profile sample points.
/// - `k_factor`: Effective Earth radius factor (default 4/3 for standard atmosphere).
///
/// # Returns
///
/// A `TerrainProfile` containing all sample points and summary statistics.
pub fn extract_profile(
    cache: &mut TileCache,
    start: GeoPoint,
    end: GeoPoint,
    step_m: f64,
    k_factor: f64,
) -> TerrainProfile {
    let total_distance = haversine_distance(start.lat, start.lon, end.lat, end.lon);

    if total_distance < 1.0 || step_m <= 0.0 {
        // Degenerate case: start and end are at the same point
        let elev = cache.elevation(start.lat, start.lon).unwrap_or(0.0);
        return TerrainProfile {
            points: vec![ProfilePoint {
                distance_m: 0.0,
                elevation_m: elev,
                latitude: start.lat,
                longitude: start.lon,
            }],
            distance_m: total_distance,
            max_elevation_m: elev,
            min_elevation_m: elev,
            num_obstructions: 0,
        };
    }

    // Generate sample points along the great-circle path
    let num_steps = (total_distance / step_m).ceil() as usize;
    let _actual_step = total_distance / num_steps as f64;

    let mut points = Vec::with_capacity(num_steps + 1);
    let mut max_elev = f64::NEG_INFINITY;
    let mut min_elev = f64::INFINITY;

    for i in 0..=num_steps {
        let fraction = i as f64 / num_steps as f64;
        let distance_m = fraction * total_distance;

        let (lat, lon) = intermediate_point(start.lat, start.lon, end.lat, end.lon, fraction);

        // Query elevation from cache
        let raw_elev = cache.elevation(lat, lon).unwrap_or(0.0);

        // Apply Earth curvature correction
        // Earth bulge: the apparent rise of the Earth's surface between two points.
        // d1 = distance from start, d2 = distance from end
        let d1 = distance_m;
        let d2 = total_distance - distance_m;
        let earth_bulge = d1 * d2 / (2.0 * k_factor * EARTH_RADIUS_M);

        // The effective elevation includes Earth curvature
        let elevation_m = raw_elev + earth_bulge;

        if elevation_m > max_elev {
            max_elev = elevation_m;
        }
        if elevation_m < min_elev {
            min_elev = elevation_m;
        }

        points.push(ProfilePoint {
            distance_m,
            elevation_m,
            latitude: lat,
            longitude: lon,
        });
    }

    // Handle edge case where no points were generated
    if points.is_empty() {
        return TerrainProfile {
            points,
            distance_m: total_distance,
            max_elevation_m: 0.0,
            min_elevation_m: 0.0,
            num_obstructions: 0,
        };
    }

    // Count obstructions: points where terrain exceeds the line-of-sight
    // between the first and last point elevations
    let start_elev = points.first().map(|p| p.elevation_m).unwrap_or(0.0);
    let end_elev = points.last().map(|p| p.elevation_m).unwrap_or(0.0);

    let num_obstructions = points
        .iter()
        .skip(1) // skip start point
        .filter(|p| {
            if total_distance == 0.0 {
                return false;
            }
            // Line-of-sight elevation at this distance
            let los_elev =
                start_elev + (end_elev - start_elev) * (p.distance_m / total_distance);
            p.elevation_m > los_elev
        })
        .count();

    // Clamp min/max if no valid elevations
    if max_elev == f64::NEG_INFINITY {
        max_elev = 0.0;
    }
    if min_elev == f64::INFINITY {
        min_elev = 0.0;
    }

    TerrainProfile {
        points,
        distance_m: total_distance,
        max_elevation_m: max_elev,
        min_elevation_m: min_elev,
        num_obstructions,
    }
}

/// Calculate the great-circle distance between two points using the Haversine formula.
///
/// # Parameters
///
/// - `lat1`, `lon1`: First point in decimal degrees.
/// - `lat2`, `lon2`: Second point in decimal degrees.
///
/// # Returns
///
/// Distance in meters.
pub fn haversine_distance(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let lat1_rad = lat1.to_radians();
    let lat2_rad = lat2.to_radians();
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();

    let a = (dlat / 2.0).sin().powi(2)
        + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();

    EARTH_RADIUS_M * c
}

/// Calculate an intermediate point along the great-circle path between two points.
///
/// # Parameters
///
/// - `lat1`, `lon1`: Start point in decimal degrees.
/// - `lat2`, `lon2`: End point in decimal degrees.
/// - `fraction`: Fraction along the path (0.0 = start, 1.0 = end).
///
/// # Returns
///
/// Tuple of (latitude, longitude) in decimal degrees.
pub fn intermediate_point(
    lat1: f64,
    lon1: f64,
    lat2: f64,
    lon2: f64,
    fraction: f64,
) -> (f64, f64) {
    let lat1_rad = lat1.to_radians();
    let lon1_rad = lon1.to_radians();
    let lat2_rad = lat2.to_radians();
    let lon2_rad = lon2.to_radians();

    let dlat = lat2_rad - lat1_rad;
    let dlon = lon2_rad - lon1_rad;

    let a = (dlat / 2.0).sin().powi(2)
        + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2.0).sin().powi(2);
    let delta = 2.0 * a.sqrt().asin();

    // Handle zero distance
    if delta.abs() < 1e-12 {
        return (lat1, lon1);
    }

    let a_coeff = ((1.0 - fraction) * delta).sin() / delta.sin();
    let b_coeff = (fraction * delta).sin() / delta.sin();

    let x = a_coeff * lat1_rad.cos() * lon1_rad.cos() + b_coeff * lat2_rad.cos() * lon2_rad.cos();
    let y = a_coeff * lat1_rad.cos() * lon1_rad.sin() + b_coeff * lat2_rad.cos() * lon2_rad.sin();
    let z = a_coeff * lat1_rad.sin() + b_coeff * lat2_rad.sin();

    let lat = z.atan2((x * x + y * y).sqrt()).to_degrees();
    let lon = y.atan2(x).to_degrees();

    (lat, lon)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_haversine_known_values() {
        // London (51.5074, -0.1278) to Paris (48.8566, 2.3522)
        // Known distance: ~343.5 km
        let dist = haversine_distance(51.5074, -0.1278, 48.8566, 2.3522);
        assert!(
            (dist - 343_560.0).abs() < 1000.0,
            "London-Paris distance: {} m",
            dist
        );
    }

    #[test]
    fn test_haversine_same_point() {
        let dist = haversine_distance(45.0, 10.0, 45.0, 10.0);
        assert!(dist < 1.0, "Same point distance should be ~0: {}", dist);
    }

    #[test]
    fn test_haversine_equator() {
        // 1 degree of longitude at equator ~ 111.32 km
        let dist = haversine_distance(0.0, 0.0, 0.0, 1.0);
        assert!(
            (dist - 111_320.0).abs() < 500.0,
            "Equator 1-degree: {} m",
            dist
        );
    }

    #[test]
    fn test_haversine_brazil() {
        // Sao Paulo (-23.5505, -46.6333) to Rio (-22.9068, -43.1729)
        // Known distance: ~357 km
        let dist = haversine_distance(-23.5505, -46.6333, -22.9068, -43.1729);
        assert!(
            (dist - 357_000.0).abs() < 5000.0,
            "SP-Rio distance: {} m",
            dist
        );
    }

    #[test]
    fn test_intermediate_point_endpoints() {
        let (lat, lon) = intermediate_point(45.0, 10.0, 50.0, 20.0, 0.0);
        assert!((lat - 45.0).abs() < 1e-10);
        assert!((lon - 10.0).abs() < 1e-10);

        let (lat, lon) = intermediate_point(45.0, 10.0, 50.0, 20.0, 1.0);
        assert!((lat - 50.0).abs() < 1e-10);
        assert!((lon - 20.0).abs() < 1e-10);
    }

    #[test]
    fn test_intermediate_point_midpoint() {
        // Midpoint between (0, 0) and (0, 2) should be near (0, 1)
        let (lat, lon) = intermediate_point(0.0, 0.0, 0.0, 2.0, 0.5);
        assert!((lat - 0.0).abs() < 0.01, "Midpoint lat: {}", lat);
        assert!((lon - 1.0).abs() < 0.01, "Midpoint lon: {}", lon);
    }

    #[test]
    fn test_extract_profile_no_tiles() {
        // Without real tiles, elevations will be 0.0
        let mut cache = TileCache::new("/nonexistent", 5);
        let start = GeoPoint::new(-23.55, -46.63);
        let end = GeoPoint::new(-22.90, -43.17);

        let profile = extract_profile(&mut cache, start, end, 1000.0, DEFAULT_K_FACTOR);

        assert!(profile.distance_m > 300_000.0);
        assert!(profile.distance_m < 400_000.0);
        assert!(!profile.points.is_empty());
        assert!((profile.points[0].latitude - start.lat).abs() < 0.01);
        assert!(
            (profile.points.last().unwrap().latitude - end.lat).abs() < 0.01
        );
    }

    #[test]
    fn test_extract_profile_degenerate() {
        let mut cache = TileCache::new("/nonexistent", 5);
        let point = GeoPoint::new(-23.55, -46.63);

        let profile = extract_profile(&mut cache, point, point, 100.0, DEFAULT_K_FACTOR);

        assert_eq!(profile.points.len(), 1);
        assert!(profile.distance_m < 1.0);
    }

    #[test]
    fn test_profile_distances_monotonic() {
        let mut cache = TileCache::new("/nonexistent", 5);
        let start = GeoPoint::new(0.0, 0.0);
        let end = GeoPoint::new(1.0, 1.0);

        let profile = extract_profile(&mut cache, start, end, 5000.0, DEFAULT_K_FACTOR);

        for i in 1..profile.points.len() {
            assert!(
                profile.points[i].distance_m >= profile.points[i - 1].distance_m,
                "Distance not monotonic at index {}",
                i
            );
        }
    }

    #[test]
    fn test_earth_bulge() {
        // At the midpoint of a 100 km link, Earth bulge is:
        // d1 * d2 / (2 * k * R) = 50000 * 50000 / (2 * 1.333 * 6371000) ≈ 147.15 m
        let k = DEFAULT_K_FACTOR;
        let r = EARTH_RADIUS_M;
        let d1 = 50_000.0;
        let d2 = 50_000.0;
        let bulge = d1 * d2 / (2.0 * k * r);
        assert!(
            (bulge - 147.15).abs() < 1.0,
            "Earth bulge for 100 km link: expected ~147.15 m, got {} m",
            bulge
        );

        // For a short 1 km link, bulge should be tiny (~0.015 m)
        let d1_short = 500.0;
        let d2_short = 500.0;
        let bulge_short = d1_short * d2_short / (2.0 * k * r);
        assert!(
            bulge_short < 0.1,
            "Earth bulge for 1 km link should be tiny: {} m",
            bulge_short
        );
    }
}
