//! Candidate tower location generation.
//!
//! Generates potential tower placement positions using grid-based sampling
//! within a specified area. Candidates are scored by elevation to prefer
//! hilltop placements.

use serde::{Deserialize, Serialize};

/// Earth radius in meters (mean).
const EARTH_RADIUS_M: f64 = 6_371_000.0;

/// Meters per degree of latitude (approximately constant).
const METERS_PER_DEG_LAT: f64 = 111_320.0;

/// Type of candidate position (how it was generated).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CandidateType {
    /// Placed on a regular grid.
    Grid,
    /// Identified as a local hilltop.
    Hilltop,
    /// Near a power line corridor.
    PowerLine,
    /// Near a road intersection.
    RoadIntersection,
}

/// A candidate tower location.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TowerCandidate {
    /// Unique identifier.
    pub id: usize,
    /// Latitude in decimal degrees.
    pub latitude: f64,
    /// Longitude in decimal degrees.
    pub longitude: f64,
    /// Ground elevation in meters (from SRTM or 0 if unknown).
    pub elevation_m: f64,
    /// Preference score (hilltops get higher scores).
    pub score: f64,
    /// How this candidate was generated.
    pub candidate_type: CandidateType,
}

/// Generator for candidate tower positions.
pub struct CandidateGenerator {
    /// Spacing between grid candidates in meters.
    pub spacing_m: f64,
}

impl CandidateGenerator {
    /// Create a new candidate generator with the given grid spacing.
    pub fn new(spacing_m: f64) -> Self {
        Self {
            spacing_m: spacing_m.max(10.0),
        }
    }

    /// Generate grid-based candidates within a circular area.
    ///
    /// Places candidates on a regular grid at `spacing_m` intervals,
    /// filtering out any that fall outside the specified radius from
    /// the center point.
    ///
    /// # Parameters
    /// - `center_lat`: Center latitude in decimal degrees
    /// - `center_lon`: Center longitude in decimal degrees
    /// - `radius_m`: Radius of the candidate area in meters
    ///
    /// # Returns
    /// A vector of `TowerCandidate` positions within the circle.
    pub fn generate_grid_candidates(
        &self,
        center_lat: f64,
        center_lon: f64,
        radius_m: f64,
    ) -> Vec<TowerCandidate> {
        let lat_rad = center_lat.to_radians();
        let meters_per_deg_lon = METERS_PER_DEG_LAT * lat_rad.cos();

        let lat_range = radius_m / METERS_PER_DEG_LAT;
        let lon_range = radius_m / meters_per_deg_lon.max(1.0);

        let lat_step = self.spacing_m / METERS_PER_DEG_LAT;
        let lon_step = self.spacing_m / meters_per_deg_lon.max(1.0);

        let lat_min = center_lat - lat_range;
        let lat_max = center_lat + lat_range;
        let lon_min = center_lon - lon_range;
        let lon_max = center_lon + lon_range;

        let mut candidates = Vec::new();
        let mut id = 0;

        let mut lat = lat_min;
        while lat <= lat_max {
            let mut lon = lon_min;
            while lon <= lon_max {
                let dist = haversine_distance(center_lat, center_lon, lat, lon);
                if dist <= radius_m {
                    candidates.push(TowerCandidate {
                        id,
                        latitude: lat,
                        longitude: lon,
                        elevation_m: 0.0, // No SRTM data loaded; set to 0
                        score: 1.0,
                        candidate_type: CandidateType::Grid,
                    });
                    id += 1;
                }
                lon += lon_step;
            }
            lat += lat_step;
        }

        candidates
    }

    /// Score candidates by elevation, giving higher scores to hilltops.
    ///
    /// Candidates with higher elevation relative to the group average
    /// receive a bonus score. The score is normalized so the maximum is 1.0.
    pub fn score_by_elevation(candidates: &mut [TowerCandidate]) {
        if candidates.is_empty() {
            return;
        }

        let min_elev = candidates
            .iter()
            .map(|c| c.elevation_m)
            .fold(f64::INFINITY, f64::min);
        let max_elev = candidates
            .iter()
            .map(|c| c.elevation_m)
            .fold(f64::NEG_INFINITY, f64::max);

        let range = max_elev - min_elev;
        if range < 1.0 {
            // All at same elevation; set uniform score
            for c in candidates.iter_mut() {
                c.score = 1.0;
            }
            return;
        }

        for c in candidates.iter_mut() {
            // Normalize elevation to [0.1, 1.0] range
            // Higher elevation => higher score
            c.score = 0.1 + 0.9 * (c.elevation_m - min_elev) / range;
        }
    }
}

/// Haversine distance between two geographic points in meters.
pub(crate) fn haversine_distance(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let lat1_rad = lat1.to_radians();
    let lat2_rad = lat2.to_radians();
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();

    let a = (dlat / 2.0).sin().powi(2)
        + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();

    EARTH_RADIUS_M * c
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_grid_candidates_count() {
        let gen = CandidateGenerator::new(500.0);
        let candidates = gen.generate_grid_candidates(-23.55, -46.63, 2000.0);

        // For a 2km radius circle with 500m spacing:
        // Diameter = 4km, so ~8x8 = 64 grid points, but circle clips to ~50
        assert!(
            candidates.len() > 10,
            "Should have many candidates: {}",
            candidates.len()
        );
        assert!(
            candidates.len() < 200,
            "Should not have too many candidates: {}",
            candidates.len()
        );
    }

    #[test]
    fn test_candidates_within_radius() {
        let gen = CandidateGenerator::new(500.0);
        let center_lat = -23.55;
        let center_lon = -46.63;
        let radius_m = 2000.0;
        let candidates = gen.generate_grid_candidates(center_lat, center_lon, radius_m);

        for c in &candidates {
            let dist = haversine_distance(center_lat, center_lon, c.latitude, c.longitude);
            assert!(
                dist <= radius_m + 1.0,
                "Candidate {} at distance {} m exceeds radius {} m",
                c.id,
                dist,
                radius_m
            );
        }
    }

    #[test]
    fn test_candidates_have_unique_ids() {
        let gen = CandidateGenerator::new(500.0);
        let candidates = gen.generate_grid_candidates(-23.55, -46.63, 2000.0);

        let mut ids: Vec<usize> = candidates.iter().map(|c| c.id).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), candidates.len(), "All IDs should be unique");
    }

    #[test]
    fn test_score_by_elevation() {
        let mut candidates = vec![
            TowerCandidate {
                id: 0,
                latitude: -23.55,
                longitude: -46.63,
                elevation_m: 100.0,
                score: 0.0,
                candidate_type: CandidateType::Grid,
            },
            TowerCandidate {
                id: 1,
                latitude: -23.56,
                longitude: -46.64,
                elevation_m: 500.0,
                score: 0.0,
                candidate_type: CandidateType::Grid,
            },
            TowerCandidate {
                id: 2,
                latitude: -23.57,
                longitude: -46.65,
                elevation_m: 300.0,
                score: 0.0,
                candidate_type: CandidateType::Grid,
            },
        ];

        CandidateGenerator::score_by_elevation(&mut candidates);

        // Highest elevation should have highest score
        assert!(
            candidates[1].score > candidates[0].score,
            "500m candidate should score higher than 100m"
        );
        assert!(
            candidates[1].score > candidates[2].score,
            "500m candidate should score higher than 300m"
        );
        assert!(
            candidates[2].score > candidates[0].score,
            "300m candidate should score higher than 100m"
        );

        // Highest should be 1.0
        assert!(
            (candidates[1].score - 1.0).abs() < 1e-6,
            "Max elevation should have score 1.0, got {}",
            candidates[1].score
        );
        // Lowest should be 0.1
        assert!(
            (candidates[0].score - 0.1).abs() < 1e-6,
            "Min elevation should have score 0.1, got {}",
            candidates[0].score
        );
    }

    #[test]
    fn test_haversine_distance_basic() {
        // 1 degree latitude ≈ 111.32 km
        let dist = haversine_distance(0.0, 0.0, 1.0, 0.0);
        assert!(
            (dist - 111_320.0).abs() < 500.0,
            "1 degree latitude should be ~111 km, got {} m",
            dist
        );
    }

    #[test]
    fn test_small_radius_few_candidates() {
        // Use spacing smaller than radius so we definitely get some candidates
        let gen = CandidateGenerator::new(100.0);
        let candidates = gen.generate_grid_candidates(-23.55, -46.63, 300.0);
        // Small radius: should get a handful of candidates
        assert!(
            candidates.len() <= 50,
            "Small radius should yield few candidates: {}",
            candidates.len()
        );
        assert!(
            !candidates.is_empty(),
            "Should have at least one candidate"
        );
    }
}
