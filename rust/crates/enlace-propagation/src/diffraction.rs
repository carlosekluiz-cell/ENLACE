//! Knife-edge diffraction calculations.
//!
//! Implements the Fresnel-Kirchhoff diffraction parameter computation,
//! single knife-edge loss approximation, and the Deygout method for
//! multiple obstacle diffraction.

use crate::common::wavelength_m;

/// Compute the Fresnel-Kirchhoff diffraction parameter v.
///
/// v = h * sqrt(2 / (lambda * d1 * d2 / (d1 + d2)))
///
/// where:
/// - `h` = obstruction height above line-of-sight (meters, positive = above LOS)
/// - `d1` = distance from TX to obstruction (meters)
/// - `d2` = distance from obstruction to RX (meters)
/// - `freq_mhz` = carrier frequency in MHz
pub fn diffraction_parameter(h: f64, d1: f64, d2: f64, freq_mhz: f64) -> f64 {
    let lambda = wavelength_m(freq_mhz);
    let denom = lambda * d1 * d2 / (d1 + d2);
    if denom <= 0.0 {
        return 0.0;
    }
    h * (2.0 / denom).sqrt()
}

/// Knife-edge diffraction loss in dB (Lee approximation).
///
/// For v > -0.78:
///   J(v) = 6.02 + 9.11*v + 1.27*v^2
/// For v <= -0.78:
///   J(v) = 0 (no obstruction)
///
/// Returns non-negative loss in dB.
pub fn knife_edge_loss(v: f64) -> f64 {
    if v <= -0.78 {
        0.0
    } else {
        let loss = 6.02 + 9.11 * v + 1.27 * v * v;
        loss.max(0.0)
    }
}

/// Obstruction information for diffraction analysis.
#[derive(Debug, Clone)]
pub struct Obstruction {
    /// Distance from TX in meters.
    pub distance_m: f64,
    /// Height above the TX-RX line-of-sight in meters.
    pub height_above_los_m: f64,
    /// Elevation above sea level in meters.
    pub elevation_m: f64,
}

/// Compute total diffraction loss using the Deygout method for a terrain profile.
///
/// The terrain profile is given as a slice of (distance_m, elevation_m) tuples.
/// `tx_height_m` and `rx_height_m` are antenna heights above ground at the
/// respective ends of the profile.
///
/// # Algorithm
///
/// 1. Find the dominant obstacle (highest diffraction parameter v).
/// 2. Compute knife-edge loss for the dominant obstacle.
/// 3. Subdivide the path at the dominant obstacle.
/// 4. Recursively find secondary obstacles in each sub-path.
/// 5. Sum all individual knife-edge losses.
pub fn deygout_diffraction_loss(
    profile: &[(f64, f64)],
    tx_height_m: f64,
    rx_height_m: f64,
    freq_mhz: f64,
) -> f64 {
    if profile.len() < 3 {
        return 0.0;
    }

    let total_distance = profile.last().unwrap().0 - profile.first().unwrap().0;
    if total_distance <= 0.0 {
        return 0.0;
    }

    let tx_elev = profile.first().unwrap().1 + tx_height_m;
    let rx_elev = profile.last().unwrap().1 + rx_height_m;

    // Find the dominant obstacle (maximum v parameter)
    let mut max_v = f64::NEG_INFINITY;
    let mut dominant_idx = 0;

    for (i, &(dist, elev)) in profile.iter().enumerate().skip(1) {
        if i >= profile.len() - 1 {
            break;
        }

        let d1 = dist - profile.first().unwrap().0;
        let d2 = profile.last().unwrap().0 - dist;

        if d1 <= 0.0 || d2 <= 0.0 {
            continue;
        }

        // Line-of-sight elevation at this distance
        let fraction = d1 / total_distance;
        let los_elev = tx_elev + (rx_elev - tx_elev) * fraction;

        // Height above LOS
        let h = elev - los_elev;

        let v = diffraction_parameter(h, d1, d2, freq_mhz);
        if v > max_v {
            max_v = v;
            dominant_idx = i;
        }
    }

    if max_v <= -0.78 {
        // No significant obstruction
        return 0.0;
    }

    let mut total_loss = knife_edge_loss(max_v);

    // Recursively handle sub-paths (limited depth to avoid stack overflow)
    if profile.len() > 4 {
        // Left sub-path: TX to dominant obstacle
        if dominant_idx > 1 {
            let sub_profile = &profile[..=dominant_idx];
            let obs_height = profile[dominant_idx].1 - profile.first().unwrap().1;
            let sub_loss = deygout_sub_loss(sub_profile, tx_height_m, obs_height, freq_mhz, 2);
            total_loss += sub_loss;
        }

        // Right sub-path: dominant obstacle to RX
        if dominant_idx < profile.len() - 2 {
            let sub_profile = &profile[dominant_idx..];
            let obs_height = profile[dominant_idx].1 - profile[dominant_idx].1;
            let sub_loss = deygout_sub_loss(sub_profile, obs_height, rx_height_m, freq_mhz, 2);
            total_loss += sub_loss;
        }
    }

    total_loss
}

/// Recursive helper for Deygout sub-path analysis.
fn deygout_sub_loss(
    profile: &[(f64, f64)],
    start_height: f64,
    end_height: f64,
    freq_mhz: f64,
    max_depth: usize,
) -> f64 {
    if profile.len() < 3 || max_depth == 0 {
        return 0.0;
    }

    let total_distance = profile.last().unwrap().0 - profile.first().unwrap().0;
    if total_distance <= 0.0 {
        return 0.0;
    }

    let start_elev = profile.first().unwrap().1 + start_height;
    let end_elev = profile.last().unwrap().1 + end_height;

    let mut max_v = f64::NEG_INFINITY;

    for (i, &(dist, elev)) in profile.iter().enumerate().skip(1) {
        if i >= profile.len() - 1 {
            break;
        }

        let d1 = dist - profile.first().unwrap().0;
        let d2 = profile.last().unwrap().0 - dist;
        if d1 <= 0.0 || d2 <= 0.0 {
            continue;
        }

        let fraction = d1 / total_distance;
        let los_elev = start_elev + (end_elev - start_elev) * fraction;
        let h = elev - los_elev;
        let v = diffraction_parameter(h, d1, d2, freq_mhz);
        if v > max_v {
            max_v = v;
        }
    }

    if max_v <= -0.78 {
        return 0.0;
    }

    knife_edge_loss(max_v)
}

/// Find all obstructions in a terrain profile relative to TX-RX line-of-sight.
pub fn find_obstructions(
    profile: &[(f64, f64)],
    tx_height_m: f64,
    rx_height_m: f64,
) -> Vec<Obstruction> {
    if profile.len() < 3 {
        return Vec::new();
    }

    let total_distance = profile.last().unwrap().0 - profile.first().unwrap().0;
    if total_distance <= 0.0 {
        return Vec::new();
    }

    let tx_elev = profile.first().unwrap().1 + tx_height_m;
    let rx_elev = profile.last().unwrap().1 + rx_height_m;

    let mut obstructions = Vec::new();

    for &(dist, elev) in profile.iter().skip(1) {
        let d_from_tx = dist - profile.first().unwrap().0;
        let fraction = d_from_tx / total_distance;
        let los_elev = tx_elev + (rx_elev - tx_elev) * fraction;

        if elev > los_elev {
            obstructions.push(Obstruction {
                distance_m: dist,
                height_above_los_m: elev - los_elev,
                elevation_m: elev,
            });
        }
    }

    obstructions
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_knife_edge_no_obstruction() {
        // v <= -0.78 means no loss
        assert_eq!(knife_edge_loss(-1.0), 0.0);
        assert_eq!(knife_edge_loss(-0.78), 0.0);
    }

    #[test]
    fn test_knife_edge_grazing() {
        // v = 0 means grazing incidence -> ~6 dB
        let loss = knife_edge_loss(0.0);
        assert!((loss - 6.02).abs() < 0.01, "Grazing loss: {} dB", loss);
    }

    #[test]
    fn test_knife_edge_full_obstruction() {
        // v = 1 -> 6.02 + 9.11 + 1.27 = 16.4 dB
        let loss = knife_edge_loss(1.0);
        assert!((loss - 16.4).abs() < 0.1, "v=1 loss: {} dB", loss);
    }

    #[test]
    fn test_diffraction_parameter() {
        // 900 MHz, 50m above LOS, 5km from TX, 5km from RX
        let v = diffraction_parameter(50.0, 5000.0, 5000.0, 900.0);
        assert!(v > 0.0, "Should be positive for obstruction above LOS");
        // Expect v to be in a reasonable range (typically 0-10 for telecom)
        assert!(v < 20.0, "v = {} seems too large", v);
    }

    #[test]
    fn test_deygout_flat_terrain() {
        // Flat terrain with no obstructions
        let profile: Vec<(f64, f64)> = (0..100)
            .map(|i| (i as f64 * 100.0, 0.0))
            .collect();

        let loss = deygout_diffraction_loss(&profile, 30.0, 10.0, 900.0);
        assert!(
            loss < 0.01,
            "Flat terrain should have no diffraction loss: {} dB",
            loss
        );
    }

    #[test]
    fn test_deygout_single_obstacle() {
        // Terrain with a single obstacle in the middle
        let mut profile: Vec<(f64, f64)> = (0..100)
            .map(|i| (i as f64 * 100.0, 0.0))
            .collect();
        // Put a hill at the midpoint
        profile[50] = (5000.0, 100.0);

        let loss = deygout_diffraction_loss(&profile, 30.0, 10.0, 900.0);
        assert!(loss > 0.0, "Should have diffraction loss: {} dB", loss);
    }
}
