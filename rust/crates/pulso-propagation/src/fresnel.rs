//! Fresnel zone calculations.
//!
//! The Fresnel zone defines the ellipsoidal volume around the direct
//! line-of-sight path where most of the signal energy propagates.
//! Adequate clearance of the first Fresnel zone is critical for
//! achieving near-free-space propagation conditions.

use crate::common::wavelength_m;

/// Compute the first Fresnel zone radius at a given point along the path.
///
/// r1 = sqrt(lambda * d1 * d2 / (d1 + d2))
///
/// where:
/// - `d1` = distance from the point to TX (meters)
/// - `d2` = distance from the point to RX (meters)
/// - `freq_mhz` = carrier frequency in MHz
///
/// Returns the Fresnel zone radius in meters.
pub fn fresnel_zone_radius(d1: f64, d2: f64, freq_mhz: f64) -> f64 {
    let lambda = wavelength_m(freq_mhz);
    let total = d1 + d2;
    if total <= 0.0 {
        return 0.0;
    }
    (lambda * d1 * d2 / total).sqrt()
}

/// Compute the n-th Fresnel zone radius at a given point along the path.
///
/// rn = sqrt(n * lambda * d1 * d2 / (d1 + d2))
///
/// Returns the n-th Fresnel zone radius in meters.
pub fn fresnel_zone_radius_n(n: u32, d1: f64, d2: f64, freq_mhz: f64) -> f64 {
    fresnel_zone_radius(d1, d2, freq_mhz) * (n as f64).sqrt()
}

/// Compute Fresnel zone clearance ratio.
///
/// `clearance_ratio = actual_clearance / r1`
///
/// Rule of thumb: need clearance > 0.6 for effective LOS.
///
/// - `actual_clearance_m`: actual distance from obstacle to the LOS line (meters)
/// - `d1`: distance from TX to the obstacle point (meters)
/// - `d2`: distance from the obstacle point to RX (meters)
/// - `freq_mhz`: carrier frequency in MHz
///
/// Returns the clearance ratio (>1.0 = fully clear, 0.6 = minimum LOS).
pub fn fresnel_clearance_ratio(
    actual_clearance_m: f64,
    d1: f64,
    d2: f64,
    freq_mhz: f64,
) -> f64 {
    let r1 = fresnel_zone_radius(d1, d2, freq_mhz);
    if r1 <= 0.0 {
        return 0.0;
    }
    actual_clearance_m / r1
}

/// Determine if the path has adequate Fresnel clearance.
///
/// Returns `true` if the clearance ratio >= `min_ratio` at the given point.
/// The standard threshold is 0.6 (60% of the first Fresnel zone).
pub fn has_fresnel_clearance(
    actual_clearance_m: f64,
    d1: f64,
    d2: f64,
    freq_mhz: f64,
    min_ratio: f64,
) -> bool {
    fresnel_clearance_ratio(actual_clearance_m, d1, d2, freq_mhz) >= min_ratio
}

/// Analyze Fresnel zone clearance along an entire terrain profile.
///
/// `profile`: slice of (distance_m, elevation_m) tuples.
/// `tx_height_m`: antenna height above ground at TX.
/// `rx_height_m`: antenna height above ground at RX.
/// `freq_mhz`: carrier frequency in MHz.
///
/// Returns the minimum Fresnel clearance ratio along the path.
/// A value >= 0.6 indicates adequate LOS clearance.
pub fn min_fresnel_clearance(
    profile: &[(f64, f64)],
    tx_height_m: f64,
    rx_height_m: f64,
    freq_mhz: f64,
) -> f64 {
    if profile.len() < 3 {
        return f64::INFINITY;
    }

    let total_distance = profile.last().unwrap().0 - profile.first().unwrap().0;
    if total_distance <= 0.0 {
        return f64::INFINITY;
    }

    let tx_elev = profile.first().unwrap().1 + tx_height_m;
    let rx_elev = profile.last().unwrap().1 + rx_height_m;

    let mut min_ratio = f64::INFINITY;

    for &(dist, elev) in profile.iter().skip(1) {
        let d1 = dist - profile.first().unwrap().0;
        let d2 = profile.last().unwrap().0 - dist;

        if d1 <= 0.0 || d2 <= 0.0 {
            continue;
        }

        // LOS elevation at this point
        let fraction = d1 / total_distance;
        let los_elev = tx_elev + (rx_elev - tx_elev) * fraction;

        // Clearance = LOS elevation - terrain elevation
        let clearance = los_elev - elev;
        let ratio = fresnel_clearance_ratio(clearance, d1, d2, freq_mhz);

        if ratio < min_ratio {
            min_ratio = ratio;
        }
    }

    min_ratio
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fresnel_zone_radius_900mhz() {
        // 900 MHz, midpoint of 10 km path -> d1 = d2 = 5000 m
        // lambda = 0.333 m
        // r1 = sqrt(0.333 * 5000 * 5000 / 10000) = sqrt(833.25) ≈ 28.87 m
        let r1 = fresnel_zone_radius(5000.0, 5000.0, 900.0);
        assert!(
            (r1 - 28.87).abs() < 0.5,
            "Fresnel zone radius at 900 MHz, 10km: {} m",
            r1
        );
    }

    #[test]
    fn test_fresnel_zone_radius_2100mhz() {
        // 2100 MHz, midpoint of 10 km
        // lambda = 299792458 / 2.1e9 ≈ 0.1428 m
        // r1 = sqrt(0.1428 * 5000 * 5000 / 10000) ≈ 18.89 m
        let r1 = fresnel_zone_radius(5000.0, 5000.0, 2100.0);
        assert!(
            (r1 - 18.89).abs() < 0.5,
            "Fresnel zone radius at 2100 MHz, 10km: {} m",
            r1
        );
    }

    #[test]
    fn test_fresnel_zone_radius_at_endpoints() {
        // At the endpoints (d1=0 or d2=0), the Fresnel zone radius should be 0
        let r1_start = fresnel_zone_radius(0.0, 10000.0, 900.0);
        assert!(r1_start < 0.01, "Fresnel radius at start: {}", r1_start);
    }

    #[test]
    fn test_nth_fresnel_zone() {
        let r1 = fresnel_zone_radius(5000.0, 5000.0, 900.0);
        let r2 = fresnel_zone_radius_n(2, 5000.0, 5000.0, 900.0);
        assert!(
            (r2 - r1 * 2.0_f64.sqrt()).abs() < 0.01,
            "2nd Fresnel zone should be sqrt(2) * r1"
        );
    }

    #[test]
    fn test_clearance_ratio() {
        let r1 = fresnel_zone_radius(5000.0, 5000.0, 900.0);
        let ratio = fresnel_clearance_ratio(r1, 5000.0, 5000.0, 900.0);
        assert!(
            (ratio - 1.0).abs() < 0.01,
            "Clearance = r1 should give ratio 1.0: {}",
            ratio
        );

        let ratio_60 = fresnel_clearance_ratio(0.6 * r1, 5000.0, 5000.0, 900.0);
        assert!(
            (ratio_60 - 0.6).abs() < 0.01,
            "Clearance = 0.6*r1 should give ratio 0.6: {}",
            ratio_60
        );
    }

    #[test]
    fn test_min_fresnel_clearance_flat() {
        // Flat terrain with antennas on top
        let profile: Vec<(f64, f64)> = (0..101)
            .map(|i| (i as f64 * 100.0, 0.0))
            .collect();
        let min_ratio = min_fresnel_clearance(&profile, 50.0, 50.0, 900.0);
        assert!(
            min_ratio > 0.6,
            "Flat terrain with 50m antennas should clear Fresnel: {}",
            min_ratio
        );
    }
}
