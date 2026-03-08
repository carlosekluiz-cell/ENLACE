//! Tower placement constraints and validation.
//!
//! Enforces minimum spacing between towers and provides height
//! recommendations based on surrounding terrain.

use crate::candidates::{haversine_distance, TowerCandidate};

/// Minimum spacing between towers in meters.
pub const MIN_TOWER_SPACING_M: f64 = 200.0;

/// Minimum tower height in meters.
pub const MIN_TOWER_HEIGHT_M: f64 = 10.0;

/// Maximum tower height in meters.
pub const MAX_TOWER_HEIGHT_M: f64 = 100.0;

/// Validate minimum spacing between all pairs of selected towers.
///
/// Returns a list of warning messages for any tower pairs that are
/// closer than the specified minimum spacing.
///
/// # Parameters
/// - `towers`: Tower candidates to validate
/// - `min_spacing_m`: Minimum allowed spacing in meters
///
/// # Returns
/// A vector of warning strings (empty if all constraints pass).
pub fn validate_spacing(towers: &[TowerCandidate], min_spacing_m: f64) -> Vec<String> {
    let mut warnings = Vec::new();

    for i in 0..towers.len() {
        for j in (i + 1)..towers.len() {
            let dist = haversine_distance(
                towers[i].latitude,
                towers[i].longitude,
                towers[j].latitude,
                towers[j].longitude,
            );
            if dist < min_spacing_m {
                warnings.push(format!(
                    "Towers {} and {} are too close: {:.0} m (minimum: {:.0} m)",
                    towers[i].id, towers[j].id, dist, min_spacing_m
                ));
            }
        }
    }

    warnings
}

/// Recommend antenna height based on ground elevation and surrounding terrain.
///
/// If the tower is below the surrounding average, a taller mast is recommended.
/// If the tower is well above the surroundings, a shorter mast suffices.
///
/// # Parameters
/// - `ground_elevation_m`: Elevation at the tower site in meters
/// - `surrounding_avg_elevation`: Average elevation of surrounding terrain in meters
///
/// # Returns
/// Recommended antenna height in meters, clamped to [MIN_TOWER_HEIGHT_M, MAX_TOWER_HEIGHT_M].
pub fn recommend_height(ground_elevation_m: f64, surrounding_avg_elevation: f64) -> f64 {
    let delta = surrounding_avg_elevation - ground_elevation_m;

    // Base height is 30m; adjust for terrain difference
    let recommended = if delta > 0.0 {
        // Tower is in a valley/low spot: need taller mast
        30.0 + delta * 0.5
    } else {
        // Tower is on a hill: can use shorter mast
        (30.0 + delta * 0.3).max(MIN_TOWER_HEIGHT_M)
    };

    recommended.clamp(MIN_TOWER_HEIGHT_M, MAX_TOWER_HEIGHT_M)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::candidates::CandidateType;

    fn make_tower(id: usize, lat: f64, lon: f64) -> TowerCandidate {
        TowerCandidate {
            id,
            latitude: lat,
            longitude: lon,
            elevation_m: 0.0,
            score: 1.0,
            candidate_type: CandidateType::Grid,
        }
    }

    #[test]
    fn test_validate_spacing_pass() {
        // Two towers ~11 km apart (well above minimum)
        let towers = vec![
            make_tower(0, -23.55, -46.63),
            make_tower(1, -23.65, -46.73),
        ];

        let warnings = validate_spacing(&towers, MIN_TOWER_SPACING_M);
        assert!(
            warnings.is_empty(),
            "Should have no warnings for well-spaced towers: {:?}",
            warnings
        );
    }

    #[test]
    fn test_validate_spacing_fail() {
        // Two towers very close together (~11 m apart)
        let towers = vec![
            make_tower(0, -23.550000, -46.630000),
            make_tower(1, -23.550100, -46.630100),
        ];

        let warnings = validate_spacing(&towers, MIN_TOWER_SPACING_M);
        assert!(
            !warnings.is_empty(),
            "Should warn about closely-spaced towers"
        );
        assert!(
            warnings[0].contains("too close"),
            "Warning should mention 'too close'"
        );
    }

    #[test]
    fn test_validate_spacing_empty() {
        let warnings = validate_spacing(&[], MIN_TOWER_SPACING_M);
        assert!(warnings.is_empty());
    }

    #[test]
    fn test_validate_spacing_single_tower() {
        let towers = vec![make_tower(0, -23.55, -46.63)];
        let warnings = validate_spacing(&towers, MIN_TOWER_SPACING_M);
        assert!(warnings.is_empty());
    }

    #[test]
    fn test_recommend_height_valley() {
        // Tower is 50m below surrounding terrain
        let height = recommend_height(100.0, 150.0);
        // Should recommend taller than base 30m
        assert!(
            height > 30.0,
            "Valley site should get taller mast: {} m",
            height
        );
        assert!(height <= MAX_TOWER_HEIGHT_M);
        assert!(height >= MIN_TOWER_HEIGHT_M);
    }

    #[test]
    fn test_recommend_height_hilltop() {
        // Tower is 100m above surrounding terrain
        let height = recommend_height(500.0, 400.0);
        // Should recommend shorter than base 30m
        assert!(
            height < 30.0,
            "Hilltop site should get shorter mast: {} m",
            height
        );
        assert!(height >= MIN_TOWER_HEIGHT_M);
    }

    #[test]
    fn test_recommend_height_flat() {
        // Tower at same elevation as surroundings
        let height = recommend_height(200.0, 200.0);
        assert!(
            (height - 30.0).abs() < 0.1,
            "Flat terrain should use base height 30m: {} m",
            height
        );
    }

    #[test]
    fn test_recommend_height_clamped() {
        // Extreme valley: very deep
        let height = recommend_height(0.0, 500.0);
        assert!(
            height <= MAX_TOWER_HEIGHT_M,
            "Height should be clamped to max: {} m",
            height
        );

        // Extreme hilltop
        let height2 = recommend_height(1000.0, 0.0);
        assert!(
            height2 >= MIN_TOWER_HEIGHT_M,
            "Height should be clamped to min: {} m",
            height2
        );
    }
}
