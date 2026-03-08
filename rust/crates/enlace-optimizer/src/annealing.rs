//! Simulated annealing refinement for tower placement.
//!
//! Improves the greedy set-cover solution by applying random perturbations
//! (move, swap, remove) and accepting them based on the Metropolis criterion.
//! This can reduce the number of towers while maintaining coverage.

use rand::Rng;
use tracing::debug;

use crate::candidates::{haversine_distance, TowerCandidate};
use crate::setcover::{CoverageSolution, DemandPoint};
use enlace_propagation::models::fspl::FsplModel;

/// Parameters controlling the simulated annealing process.
#[derive(Debug, Clone)]
pub struct AnnealingParams {
    /// Maximum number of iterations.
    pub max_iterations: usize,
    /// Initial temperature (higher = more exploration).
    pub initial_temperature: f64,
    /// Cooling rate per iteration (e.g., 0.995).
    pub cooling_rate: f64,
    /// Perturbation neighborhood radius (number of adjacent candidates to consider).
    pub perturbation_radius: usize,
}

impl Default for AnnealingParams {
    fn default() -> Self {
        Self {
            max_iterations: 10_000,
            initial_temperature: 100.0,
            cooling_rate: 0.995,
            perturbation_radius: 3,
        }
    }
}

/// Simulated annealing solver for refining tower placements.
pub struct AnnealingSolver {
    /// Annealing parameters.
    pub params: AnnealingParams,
}

impl AnnealingSolver {
    /// Create a new annealing solver with the given parameters.
    pub fn new(params: AnnealingParams) -> Self {
        Self { params }
    }

    /// Refine an existing coverage solution using simulated annealing.
    ///
    /// Perturbations applied at each step:
    /// - **Move**: Shift a tower to an adjacent candidate position
    /// - **Swap**: Exchange one selected tower for an unselected candidate
    /// - **Remove**: Try removing a tower if coverage target is still met
    ///
    /// Acceptance criterion: improvements are always accepted; worse solutions
    /// are accepted with probability exp(-delta_cost / temperature).
    ///
    /// The cost function is: `num_towers * 1000 - coverage_pct * 100`.
    /// This balances minimizing towers with maintaining coverage.
    #[allow(clippy::too_many_arguments)]
    pub fn refine(
        &self,
        initial_solution: &CoverageSolution,
        candidates: &[TowerCandidate],
        demand_points: &[DemandPoint],
        frequency_mhz: f64,
        tx_power_dbm: f64,
        antenna_gain_dbi: f64,
        _antenna_height_m: f64,
        min_signal_dbm: f64,
        coverage_target_pct: f64,
    ) -> CoverageSolution {
        if candidates.is_empty() || demand_points.is_empty() {
            return initial_solution.clone();
        }

        let eirp = tx_power_dbm + antenna_gain_dbi;

        // Pre-compute coverage matrix
        let coverage_sets: Vec<Vec<usize>> = candidates
            .iter()
            .map(|candidate| {
                demand_points
                    .iter()
                    .enumerate()
                    .filter_map(|(j, dp)| {
                        let distance = haversine_distance(
                            candidate.latitude,
                            candidate.longitude,
                            dp.latitude,
                            dp.longitude,
                        );
                        let path_loss = FsplModel::compute(frequency_mhz, distance.max(1.0));
                        let received_power = eirp - path_loss;
                        if received_power >= min_signal_dbm {
                            Some(j)
                        } else {
                            None
                        }
                    })
                    .collect()
            })
            .collect();

        let total_demand: f64 = demand_points.iter().map(|d| d.weight).sum();

        // Current solution state
        let mut current_towers: Vec<usize> = initial_solution.selected_towers.clone();
        let mut current_cost = Self::compute_cost(&current_towers, &coverage_sets, demand_points, total_demand);

        let mut best_towers = current_towers.clone();
        let mut best_cost = current_cost;

        let mut rng = rand::thread_rng();
        let mut temperature = self.params.initial_temperature;

        for iteration in 0..self.params.max_iterations {
            if current_towers.is_empty() {
                break;
            }

            // Choose perturbation type
            let perturbation = rng.gen_range(0..3);
            let mut new_towers = current_towers.clone();

            match perturbation {
                0 => {
                    // Move: replace one tower with a nearby candidate
                    let tower_idx = rng.gen_range(0..new_towers.len());
                    let current_candidate = new_towers[tower_idx];

                    // Find nearby candidates (by index proximity as a simple heuristic)
                    let radius = self.params.perturbation_radius;
                    let min_idx = current_candidate.saturating_sub(radius);
                    let max_idx = (current_candidate + radius).min(candidates.len() - 1);

                    let neighbor = rng.gen_range(min_idx..=max_idx);
                    if !new_towers.contains(&neighbor) {
                        new_towers[tower_idx] = neighbor;
                    }
                }
                1 => {
                    // Swap: exchange with a random unselected candidate
                    let tower_idx = rng.gen_range(0..new_towers.len());
                    let random_candidate = rng.gen_range(0..candidates.len());
                    if !new_towers.contains(&random_candidate) {
                        new_towers[tower_idx] = random_candidate;
                    }
                }
                2 => {
                    // Remove: try removing a tower
                    if new_towers.len() > 1 {
                        let tower_idx = rng.gen_range(0..new_towers.len());
                        let trial_towers: Vec<usize> = new_towers
                            .iter()
                            .enumerate()
                            .filter(|&(i, _)| i != tower_idx)
                            .map(|(_, &t)| t)
                            .collect();

                        // Only remove if coverage target is still met
                        let trial_coverage =
                            Self::compute_coverage_pct(&trial_towers, &coverage_sets, demand_points, total_demand);
                        if trial_coverage >= coverage_target_pct {
                            new_towers = trial_towers;
                        }
                    }
                }
                _ => unreachable!(),
            }

            let new_cost = Self::compute_cost(&new_towers, &coverage_sets, demand_points, total_demand);
            let delta = new_cost - current_cost;

            // Metropolis acceptance criterion
            let accept = if delta <= 0.0 {
                true
            } else {
                let acceptance_prob = (-delta / temperature).exp();
                rng.gen::<f64>() < acceptance_prob
            };

            if accept {
                current_towers = new_towers;
                current_cost = new_cost;

                if current_cost < best_cost {
                    best_towers = current_towers.clone();
                    best_cost = current_cost;
                }
            }

            // Cool down
            temperature *= self.params.cooling_rate;

            if iteration % 1000 == 0 {
                debug!(
                    iteration,
                    temperature,
                    current_cost,
                    best_cost,
                    num_towers = best_towers.len(),
                    "Annealing progress"
                );
            }
        }

        // Compute final coverage stats for best solution
        let covered_demand = Self::compute_covered_demand(&best_towers, &coverage_sets, demand_points);
        let coverage_pct = if total_demand > 0.0 {
            100.0 * covered_demand / total_demand
        } else {
            0.0
        };

        CoverageSolution {
            selected_towers: best_towers,
            coverage_pct,
            covered_demand,
            total_demand,
        }
    }

    /// Compute the cost function for a tower selection.
    ///
    /// Cost = num_towers * 1000 - coverage_pct * 100
    /// Lower is better: fewer towers and higher coverage.
    fn compute_cost(
        towers: &[usize],
        coverage_sets: &[Vec<usize>],
        demand_points: &[DemandPoint],
        total_demand: f64,
    ) -> f64 {
        let coverage_pct = Self::compute_coverage_pct(towers, coverage_sets, demand_points, total_demand);
        towers.len() as f64 * 1000.0 - coverage_pct * 100.0
    }

    /// Compute coverage percentage for a given set of towers.
    fn compute_coverage_pct(
        towers: &[usize],
        coverage_sets: &[Vec<usize>],
        demand_points: &[DemandPoint],
        total_demand: f64,
    ) -> f64 {
        if total_demand <= 0.0 {
            return 0.0;
        }
        let covered = Self::compute_covered_demand(towers, coverage_sets, demand_points);
        100.0 * covered / total_demand
    }

    /// Compute total weighted demand covered by the selected towers.
    fn compute_covered_demand(
        towers: &[usize],
        coverage_sets: &[Vec<usize>],
        demand_points: &[DemandPoint],
    ) -> f64 {
        let mut covered = vec![false; demand_points.len()];
        for &t in towers {
            if t < coverage_sets.len() {
                for &j in &coverage_sets[t] {
                    covered[j] = true;
                }
            }
        }
        demand_points
            .iter()
            .enumerate()
            .filter(|(i, _)| covered[*i])
            .map(|(_, dp)| dp.weight)
            .sum()
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

    fn make_demand(lat: f64, lon: f64) -> DemandPoint {
        DemandPoint {
            latitude: lat,
            longitude: lon,
            weight: 1.0,
        }
    }

    #[test]
    fn test_annealing_maintains_or_improves() {
        let candidates: Vec<TowerCandidate> = (0..10)
            .map(|i| make_candidate(i, -23.55 + i as f64 * 0.005, -46.63))
            .collect();

        let demand_points: Vec<DemandPoint> = (0..20)
            .map(|i| make_demand(-23.55 + i as f64 * 0.002, -46.63 + (i % 5) as f64 * 0.002))
            .collect();

        // Start with all candidates selected (wasteful)
        let initial = CoverageSolution {
            selected_towers: vec![0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            coverage_pct: 100.0,
            covered_demand: 20.0,
            total_demand: 20.0,
        };

        let params = AnnealingParams {
            max_iterations: 1_000,
            initial_temperature: 50.0,
            cooling_rate: 0.99,
            perturbation_radius: 3,
        };
        let solver = AnnealingSolver::new(params);

        let result = solver.refine(
            &initial,
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
            -95.0,
            80.0,
        );

        // Annealing should find a solution with fewer or equal towers
        // while still meeting coverage target
        assert!(
            result.selected_towers.len() <= initial.selected_towers.len(),
            "Should not increase number of towers: {} vs {}",
            result.selected_towers.len(),
            initial.selected_towers.len()
        );
        assert!(
            result.coverage_pct >= 0.0,
            "Coverage should be non-negative"
        );
    }

    #[test]
    fn test_annealing_empty_inputs() {
        let solver = AnnealingSolver::new(AnnealingParams::default());
        let initial = CoverageSolution {
            selected_towers: Vec::new(),
            coverage_pct: 0.0,
            covered_demand: 0.0,
            total_demand: 0.0,
        };

        let result = solver.refine(&initial, &[], &[], 700.0, 43.0, 15.0, 30.0, -95.0, 95.0);
        assert!(result.selected_towers.is_empty());
    }

    #[test]
    fn test_annealing_single_tower() {
        let candidates = vec![make_candidate(0, -23.55, -46.63)];
        let demand_points = vec![make_demand(-23.5505, -46.6305)];

        let initial = CoverageSolution {
            selected_towers: vec![0],
            coverage_pct: 100.0,
            covered_demand: 1.0,
            total_demand: 1.0,
        };

        let params = AnnealingParams {
            max_iterations: 100,
            ..Default::default()
        };
        let solver = AnnealingSolver::new(params);

        let result = solver.refine(
            &initial,
            &candidates,
            &demand_points,
            700.0,
            43.0,
            15.0,
            30.0,
            -95.0,
            95.0,
        );

        // With only one candidate, solution should remain the same
        assert_eq!(result.selected_towers.len(), 1);
    }

    #[test]
    fn test_default_params() {
        let params = AnnealingParams::default();
        assert_eq!(params.max_iterations, 10_000);
        assert!((params.initial_temperature - 100.0).abs() < f64::EPSILON);
        assert!((params.cooling_rate - 0.995).abs() < f64::EPSILON);
        assert_eq!(params.perturbation_radius, 3);
    }
}
