//! Greedy weighted set-cover algorithm for initial tower placement.
//!
//! Pre-computes coverage for each candidate tower using simplified FSPL,
//! then greedily selects candidates that cover the most uncovered demand
//! points. The resulting solution is typically within 1.5x of optimal.

use crate::candidates::{haversine_distance, TowerCandidate};
use enlace_propagation::models::fspl::FsplModel;
use serde::{Deserialize, Serialize};

/// A point representing demand (population or households needing coverage).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DemandPoint {
    /// Latitude in decimal degrees.
    pub latitude: f64,
    /// Longitude in decimal degrees.
    pub longitude: f64,
    /// Weight representing relative demand (e.g., population density).
    pub weight: f64,
}

/// Result of the set-cover optimization.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoverageSolution {
    /// Indices of selected towers in the candidates array.
    pub selected_towers: Vec<usize>,
    /// Overall coverage percentage achieved.
    pub coverage_pct: f64,
    /// Total weighted demand covered.
    pub covered_demand: f64,
    /// Total weighted demand in the area.
    pub total_demand: f64,
}

/// Greedy set-cover solver for tower placement.
pub struct SetCoverSolver {
    /// Target coverage percentage (e.g., 95.0 for 95%).
    pub coverage_target_pct: f64,
    /// Minimum received signal strength in dBm for "covered".
    pub min_signal_dbm: f64,
    /// Maximum number of towers to place.
    pub max_towers: usize,
}

impl SetCoverSolver {
    /// Create a new solver with the given parameters.
    pub fn new(target_pct: f64, min_signal_dbm: f64, max_towers: usize) -> Self {
        Self {
            coverage_target_pct: target_pct,
            min_signal_dbm,
            max_towers,
        }
    }

    /// Solve the set cover problem.
    ///
    /// For each candidate tower, computes which demand points it covers
    /// using FSPL. Then greedily selects candidates that cover the most
    /// uncovered weighted demand points until the coverage target is met
    /// or the tower limit is reached.
    ///
    /// # Parameters
    /// - `candidates`: Potential tower locations
    /// - `demand_points`: Points needing coverage
    /// - `frequency_mhz`: Carrier frequency in MHz
    /// - `tx_power_dbm`: Transmitter power in dBm
    /// - `antenna_gain_dbi`: Antenna gain in dBi
    /// - `antenna_height_m`: Antenna height above ground in meters
    ///
    /// # Returns
    /// A `CoverageSolution` with selected tower indices and coverage stats.
    pub fn solve(
        &self,
        candidates: &[TowerCandidate],
        demand_points: &[DemandPoint],
        frequency_mhz: f64,
        tx_power_dbm: f64,
        antenna_gain_dbi: f64,
        _antenna_height_m: f64,
    ) -> CoverageSolution {
        if candidates.is_empty() || demand_points.is_empty() {
            return CoverageSolution {
                selected_towers: Vec::new(),
                coverage_pct: 0.0,
                covered_demand: 0.0,
                total_demand: demand_points.iter().map(|d| d.weight).sum(),
            };
        }

        let total_demand: f64 = demand_points.iter().map(|d| d.weight).sum();
        let eirp = tx_power_dbm + antenna_gain_dbi;

        // Pre-compute coverage matrix: coverage_sets[i] = set of demand point indices covered by candidate i
        let coverage_sets: Vec<Vec<usize>> = candidates
            .iter()
            .map(|candidate| {
                demand_points
                    .iter()
                    .enumerate()
                    .filter_map(|(j, dp)| {
                        let distance =
                            haversine_distance(candidate.latitude, candidate.longitude, dp.latitude, dp.longitude);
                        let distance_clamped = distance.max(1.0);
                        let path_loss = FsplModel::compute(frequency_mhz, distance_clamped);
                        let received_power = eirp - path_loss;
                        if received_power >= self.min_signal_dbm {
                            Some(j)
                        } else {
                            None
                        }
                    })
                    .collect()
            })
            .collect();

        // Greedy set cover
        let mut selected_towers: Vec<usize> = Vec::new();
        let mut covered: Vec<bool> = vec![false; demand_points.len()];
        let mut covered_demand = 0.0;
        let mut used_candidates: Vec<bool> = vec![false; candidates.len()];

        while selected_towers.len() < self.max_towers {
            let current_pct = if total_demand > 0.0 {
                100.0 * covered_demand / total_demand
            } else {
                0.0
            };

            if current_pct >= self.coverage_target_pct {
                break;
            }

            // Find candidate covering the most uncovered weighted demand
            let mut best_candidate: Option<usize> = None;
            let mut best_marginal_demand = 0.0;

            for (i, cover_set) in coverage_sets.iter().enumerate() {
                if used_candidates[i] {
                    continue;
                }

                let marginal_demand: f64 = cover_set
                    .iter()
                    .filter(|&&j| !covered[j])
                    .map(|&j| demand_points[j].weight)
                    .sum();

                if marginal_demand > best_marginal_demand {
                    best_marginal_demand = marginal_demand;
                    best_candidate = Some(i);
                }
            }

            match best_candidate {
                Some(idx) => {
                    selected_towers.push(idx);
                    used_candidates[idx] = true;

                    // Mark newly covered demand points
                    for &j in &coverage_sets[idx] {
                        if !covered[j] {
                            covered[j] = true;
                            covered_demand += demand_points[j].weight;
                        }
                    }
                }
                None => break, // No candidate can cover any more points
            }
        }

        let coverage_pct = if total_demand > 0.0 {
            100.0 * covered_demand / total_demand
        } else {
            0.0
        };

        CoverageSolution {
            selected_towers,
            coverage_pct,
            covered_demand,
            total_demand,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::candidates::CandidateType;

    fn make_candidate(id: usize, lat: f64, lon: f64) -> TowerCandidate {
        TowerCandidate {
            id,
            latitude: lat,
            longitude: lon,
            elevation_m: 0.0,
            score: 1.0,
            candidate_type: CandidateType::Grid,
        }
    }

    fn make_demand(lat: f64, lon: f64, weight: f64) -> DemandPoint {
        DemandPoint {
            latitude: lat,
            longitude: lon,
            weight,
        }
    }

    #[test]
    fn test_setcover_basic_convergence() {
        // Create a candidate at the center and demand points around it
        let candidates = vec![
            make_candidate(0, -23.55, -46.63),
            make_candidate(1, -23.56, -46.64),
        ];

        // Demand points very close to candidate 0
        let demand_points: Vec<DemandPoint> = (0..10)
            .map(|i| {
                let offset = i as f64 * 0.001;
                make_demand(-23.55 + offset * 0.1, -46.63 + offset * 0.1, 1.0)
            })
            .collect();

        let solver = SetCoverSolver::new(50.0, -110.0, 5);
        let solution = solver.solve(
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
        );

        assert!(
            !solution.selected_towers.is_empty(),
            "Should select at least one tower"
        );
        assert!(
            solution.coverage_pct > 0.0,
            "Should achieve some coverage: {}%",
            solution.coverage_pct
        );
    }

    #[test]
    fn test_setcover_covers_nearby_points() {
        // One candidate, all demand points within 500m
        let candidates = vec![make_candidate(0, -23.55, -46.63)];

        let demand_points = vec![
            make_demand(-23.5505, -46.6305, 1.0),
            make_demand(-23.5495, -46.6295, 1.0),
            make_demand(-23.5510, -46.6300, 1.0),
        ];

        // With high power and gain at 700 MHz, 500m gives ~80 dB FSPL
        // EIRP = 43 + 15 = 58 dBm, so received ~ -22 dBm. Easily above -95 dBm.
        let solver = SetCoverSolver::new(95.0, -95.0, 5);
        let solution = solver.solve(
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
        );

        assert_eq!(solution.selected_towers.len(), 1);
        assert!(
            (solution.coverage_pct - 100.0).abs() < 0.1,
            "All nearby points should be covered: {}%",
            solution.coverage_pct
        );
    }

    #[test]
    fn test_setcover_empty_inputs() {
        let solver = SetCoverSolver::new(95.0, -95.0, 5);

        let sol1 = solver.solve(&[], &[], 700.0, 43.0, 15.0, 30.0);
        assert!(sol1.selected_towers.is_empty());
        assert_eq!(sol1.coverage_pct, 0.0);

        let sol2 = solver.solve(
            &[make_candidate(0, -23.55, -46.63)],
            &[],
            700.0,
            43.0,
            15.0,
            30.0,
        );
        assert!(sol2.selected_towers.is_empty());
    }

    #[test]
    fn test_setcover_respects_max_towers() {
        let candidates: Vec<TowerCandidate> = (0..20)
            .map(|i| make_candidate(i, -23.55 + i as f64 * 0.05, -46.63))
            .collect();

        let demand_points: Vec<DemandPoint> = (0..100)
            .map(|i| make_demand(-23.55 + i as f64 * 0.01, -46.63 + (i % 10) as f64 * 0.01, 1.0))
            .collect();

        let solver = SetCoverSolver::new(99.0, -95.0, 3);
        let solution = solver.solve(
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
        );

        assert!(
            solution.selected_towers.len() <= 3,
            "Should not exceed max_towers: {}",
            solution.selected_towers.len()
        );
    }

    #[test]
    fn test_setcover_weighted_demand() {
        // Two clusters, one with higher weight
        let candidates = vec![
            make_candidate(0, -23.55, -46.63),   // near high-weight cluster
            make_candidate(1, -23.60, -46.68),   // near low-weight cluster
        ];

        let demand_points = vec![
            make_demand(-23.5505, -46.6305, 100.0),  // high weight near candidate 0
            make_demand(-23.6005, -46.6805, 1.0),    // low weight near candidate 1
        ];

        let solver = SetCoverSolver::new(50.0, -95.0, 1);
        let solution = solver.solve(
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
        );

        // Should pick candidate 0 first (covers higher weighted demand)
        assert_eq!(solution.selected_towers.len(), 1);
        assert_eq!(
            solution.selected_towers[0], 0,
            "Should pick the candidate near the high-weight demand"
        );
    }
}
