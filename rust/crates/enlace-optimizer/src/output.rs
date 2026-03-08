//! Optimization result output and full pipeline orchestration.
//!
//! Provides the `optimize_tower_placement` entry point that ties together
//! candidate generation, greedy set-cover, and simulated annealing into
//! a single workflow, plus CAPEX estimation using BNDES/Abrint benchmarks.

use std::time::Instant;

use serde::{Deserialize, Serialize};
use tracing::info;

use crate::annealing::{AnnealingParams, AnnealingSolver};
use crate::candidates::CandidateGenerator;
use crate::setcover::{DemandPoint, SetCoverSolver};

/// Parameters for the optimization pipeline.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizationParams {
    /// Target coverage percentage (e.g., 95.0 for 95%).
    pub coverage_target_pct: f64,
    /// Minimum received signal strength in dBm.
    pub min_signal_dbm: f64,
    /// Maximum number of towers to deploy.
    pub max_towers: usize,
    /// Carrier frequency in MHz.
    pub frequency_mhz: f64,
    /// Transmitter power in dBm.
    pub tx_power_dbm: f64,
    /// Antenna gain in dBi.
    pub antenna_gain_dbi: f64,
    /// Antenna height above ground in meters.
    pub antenna_height_m: f64,
    /// Candidate grid spacing in meters.
    pub candidate_spacing_m: f64,
    /// Simulated annealing max iterations.
    pub annealing_iterations: usize,
    /// Simulated annealing initial temperature.
    pub annealing_initial_temp: f64,
    /// Simulated annealing cooling rate.
    pub annealing_cooling_rate: f64,
}

impl Default for OptimizationParams {
    fn default() -> Self {
        Self {
            coverage_target_pct: 95.0,
            min_signal_dbm: -95.0,
            max_towers: 20,
            frequency_mhz: 700.0,
            tx_power_dbm: 43.0,
            antenna_gain_dbi: 15.0,
            antenna_height_m: 30.0,
            candidate_spacing_m: 500.0,
            annealing_iterations: 10_000,
            annealing_initial_temp: 100.0,
            annealing_cooling_rate: 0.995,
        }
    }
}

/// A single tower placement in the final result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TowerPlacement {
    /// Unique tower identifier.
    pub id: usize,
    /// Latitude in decimal degrees.
    pub latitude: f64,
    /// Longitude in decimal degrees.
    pub longitude: f64,
    /// Ground elevation in meters.
    pub elevation_m: f64,
    /// Antenna height above ground in meters.
    pub antenna_height_m: f64,
    /// Estimated coverage area in km^2.
    pub coverage_area_km2: f64,
}

/// Complete optimization result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizationResult {
    /// Selected tower placements.
    pub towers: Vec<TowerPlacement>,
    /// Total coverage percentage achieved.
    pub total_coverage_pct: f64,
    /// Total covered area in km^2.
    pub covered_area_km2: f64,
    /// Estimated capital expenditure in BRL.
    pub estimated_capex_brl: f64,
    /// Computation time in seconds.
    pub computation_time_secs: f64,
}

/// Run the full optimization pipeline.
///
/// Steps:
/// 1. Generate candidate tower positions on a grid
/// 2. Generate demand points as a dense grid within the area
/// 3. Run greedy set-cover for initial solution
/// 4. Refine with simulated annealing
/// 5. Compute final placement metrics and CAPEX
///
/// # Parameters
/// - `center_lat`: Center latitude of the coverage area
/// - `center_lon`: Center longitude of the coverage area
/// - `radius_m`: Radius of the coverage area in meters
/// - `params`: Optimization parameters
///
/// # Returns
/// An `OptimizationResult` with final tower placements and metrics.
pub fn optimize_tower_placement(
    center_lat: f64,
    center_lon: f64,
    radius_m: f64,
    params: &OptimizationParams,
) -> OptimizationResult {
    let start = Instant::now();

    info!(
        center_lat,
        center_lon,
        radius_m,
        "Starting tower placement optimization"
    );

    // Step 1: Generate candidate positions
    let generator = CandidateGenerator::new(params.candidate_spacing_m);
    let candidates = generator.generate_grid_candidates(center_lat, center_lon, radius_m);

    info!(num_candidates = candidates.len(), "Generated candidates");

    // Step 2: Generate demand points (uniform grid at half candidate spacing)
    let demand_spacing = params.candidate_spacing_m / 2.0;
    let demand_gen = CandidateGenerator::new(demand_spacing);
    let demand_candidates = demand_gen.generate_grid_candidates(center_lat, center_lon, radius_m);
    let demand_points: Vec<DemandPoint> = demand_candidates
        .iter()
        .map(|c| DemandPoint {
            latitude: c.latitude,
            longitude: c.longitude,
            weight: 1.0,
        })
        .collect();

    info!(num_demand_points = demand_points.len(), "Generated demand points");

    if candidates.is_empty() || demand_points.is_empty() {
        return OptimizationResult {
            towers: Vec::new(),
            total_coverage_pct: 0.0,
            covered_area_km2: 0.0,
            estimated_capex_brl: 0.0,
            computation_time_secs: start.elapsed().as_secs_f64(),
        };
    }

    // Step 3: Greedy set-cover
    let solver = SetCoverSolver::new(
        params.coverage_target_pct,
        params.min_signal_dbm,
        params.max_towers,
    );
    let initial_solution = solver.solve(
        &candidates,
        &demand_points,
        params.frequency_mhz,
        params.tx_power_dbm,
        params.antenna_gain_dbi,
        params.antenna_height_m,
    );

    info!(
        num_towers = initial_solution.selected_towers.len(),
        coverage_pct = initial_solution.coverage_pct,
        "Initial greedy solution"
    );

    // Step 4: Simulated annealing refinement
    let annealing_params = AnnealingParams {
        max_iterations: params.annealing_iterations,
        initial_temperature: params.annealing_initial_temp,
        cooling_rate: params.annealing_cooling_rate,
        perturbation_radius: 3,
    };
    let annealer = AnnealingSolver::new(annealing_params);
    let refined = annealer.refine(
        &initial_solution,
        &candidates,
        &demand_points,
        params.frequency_mhz,
        params.tx_power_dbm,
        params.antenna_gain_dbi,
        params.antenna_height_m,
        params.min_signal_dbm,
        params.coverage_target_pct,
    );

    info!(
        num_towers = refined.selected_towers.len(),
        coverage_pct = refined.coverage_pct,
        "Refined solution after annealing"
    );

    // Step 5: Build final placements
    let total_area_km2 = std::f64::consts::PI * (radius_m / 1000.0).powi(2);
    let covered_area_km2 = total_area_km2 * refined.coverage_pct / 100.0;
    let per_tower_area = if !refined.selected_towers.is_empty() {
        covered_area_km2 / refined.selected_towers.len() as f64
    } else {
        0.0
    };

    let towers: Vec<TowerPlacement> = refined
        .selected_towers
        .iter()
        .enumerate()
        .map(|(i, &idx)| {
            let c = &candidates[idx];
            TowerPlacement {
                id: i,
                latitude: c.latitude,
                longitude: c.longitude,
                elevation_m: c.elevation_m,
                antenna_height_m: params.antenna_height_m,
                coverage_area_km2: per_tower_area,
            }
        })
        .collect();

    let estimated_capex_brl = estimate_capex(&towers);
    let computation_time_secs = start.elapsed().as_secs_f64();

    info!(
        num_towers = towers.len(),
        total_coverage_pct = refined.coverage_pct,
        covered_area_km2,
        estimated_capex_brl,
        computation_time_secs,
        "Optimization complete"
    );

    OptimizationResult {
        towers,
        total_coverage_pct: refined.coverage_pct,
        covered_area_km2,
        estimated_capex_brl,
        computation_time_secs,
    }
}

/// Estimate CAPEX for tower deployments in BRL.
///
/// Based on BNDES/Abrint benchmarks for Brazilian telecom infrastructure:
/// - Base tower cost: R$ 150,000 (structure, foundation, site prep)
/// - Radio equipment: R$ 80,000 (radio units, antennas, cables)
/// - Backhaul: R$ 50,000 (fiber or microwave link)
/// - Site acquisition: R$ 20,000 (licensing, environmental permits)
/// - Height premium: R$ 1,000 per meter above 30m
///
/// Total per tower ≈ R$ 300,000 + height premium.
pub fn estimate_capex(towers: &[TowerPlacement]) -> f64 {
    let base_cost = 300_000.0; // BRL per tower

    towers
        .iter()
        .map(|t| {
            let height_premium = if t.antenna_height_m > 30.0 {
                (t.antenna_height_m - 30.0) * 1_000.0
            } else {
                0.0
            };
            base_cost + height_premium
        })
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_params() {
        let params = OptimizationParams::default();
        assert!((params.coverage_target_pct - 95.0).abs() < f64::EPSILON);
        assert!((params.min_signal_dbm - (-95.0)).abs() < f64::EPSILON);
        assert_eq!(params.max_towers, 20);
        assert!((params.frequency_mhz - 700.0).abs() < f64::EPSILON);
        assert!((params.tx_power_dbm - 43.0).abs() < f64::EPSILON);
        assert!((params.antenna_gain_dbi - 15.0).abs() < f64::EPSILON);
        assert!((params.antenna_height_m - 30.0).abs() < f64::EPSILON);
        assert!((params.candidate_spacing_m - 500.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_estimate_capex_single_tower() {
        let towers = vec![TowerPlacement {
            id: 0,
            latitude: -23.55,
            longitude: -46.63,
            elevation_m: 800.0,
            antenna_height_m: 30.0,
            coverage_area_km2: 10.0,
        }];

        let capex = estimate_capex(&towers);
        assert!(
            (capex - 300_000.0).abs() < f64::EPSILON,
            "Single 30m tower should cost R$ 300,000: R$ {}",
            capex
        );
    }

    #[test]
    fn test_estimate_capex_tall_tower() {
        let towers = vec![TowerPlacement {
            id: 0,
            latitude: -23.55,
            longitude: -46.63,
            elevation_m: 100.0,
            antenna_height_m: 50.0,
            coverage_area_km2: 15.0,
        }];

        let capex = estimate_capex(&towers);
        // 300,000 + (50 - 30) * 1000 = 320,000
        assert!(
            (capex - 320_000.0).abs() < f64::EPSILON,
            "50m tower should cost R$ 320,000: R$ {}",
            capex
        );
    }

    #[test]
    fn test_estimate_capex_multiple_towers() {
        let towers = vec![
            TowerPlacement {
                id: 0,
                latitude: -23.55,
                longitude: -46.63,
                elevation_m: 800.0,
                antenna_height_m: 30.0,
                coverage_area_km2: 10.0,
            },
            TowerPlacement {
                id: 1,
                latitude: -23.60,
                longitude: -46.68,
                elevation_m: 600.0,
                antenna_height_m: 45.0,
                coverage_area_km2: 12.0,
            },
        ];

        let capex = estimate_capex(&towers);
        // 300,000 + 300,000 + (45-30)*1000 = 615,000
        assert!(
            (capex - 615_000.0).abs() < f64::EPSILON,
            "Two towers should cost R$ 615,000: R$ {}",
            capex
        );
    }

    #[test]
    fn test_estimate_capex_empty() {
        let capex = estimate_capex(&[]);
        assert!(
            (capex - 0.0).abs() < f64::EPSILON,
            "No towers should cost R$ 0: R$ {}",
            capex
        );
    }

    #[test]
    fn test_estimate_capex_reasonable_range() {
        // 5 towers at 30m each
        let towers: Vec<TowerPlacement> = (0..5)
            .map(|i| TowerPlacement {
                id: i,
                latitude: -23.55,
                longitude: -46.63,
                elevation_m: 800.0,
                antenna_height_m: 30.0,
                coverage_area_km2: 8.0,
            })
            .collect();

        let capex = estimate_capex(&towers);
        // Should be 5 * 300,000 = 1,500,000
        assert!(
            capex >= 1_000_000.0 && capex <= 5_000_000.0,
            "CAPEX for 5 towers should be R$ 1-5M: R$ {}",
            capex
        );
    }

    #[test]
    fn test_optimize_tower_placement_basic() {
        // Small area with tight parameters for fast execution
        let params = OptimizationParams {
            coverage_target_pct: 80.0,
            min_signal_dbm: -100.0,
            max_towers: 5,
            frequency_mhz: 700.0,
            tx_power_dbm: 43.0,
            antenna_gain_dbi: 15.0,
            antenna_height_m: 30.0,
            candidate_spacing_m: 500.0,
            annealing_iterations: 100,
            annealing_initial_temp: 50.0,
            annealing_cooling_rate: 0.95,
        };

        let result = optimize_tower_placement(-23.55, -46.63, 2000.0, &params);

        assert!(
            !result.towers.is_empty(),
            "Should place at least one tower"
        );
        assert!(
            result.total_coverage_pct > 0.0,
            "Should achieve some coverage: {}%",
            result.total_coverage_pct
        );
        assert!(
            result.covered_area_km2 > 0.0,
            "Should cover some area: {} km^2",
            result.covered_area_km2
        );
        assert!(
            result.estimated_capex_brl > 0.0,
            "Should have positive CAPEX: R$ {}",
            result.estimated_capex_brl
        );
        assert!(
            result.computation_time_secs >= 0.0,
            "Computation time should be non-negative"
        );
    }

    #[test]
    fn test_optimize_tower_placement_full_pipeline() {
        let params = OptimizationParams {
            coverage_target_pct: 90.0,
            min_signal_dbm: -95.0,
            max_towers: 10,
            frequency_mhz: 700.0,
            tx_power_dbm: 43.0,
            antenna_gain_dbi: 15.0,
            antenna_height_m: 30.0,
            candidate_spacing_m: 1000.0,
            annealing_iterations: 200,
            annealing_initial_temp: 50.0,
            annealing_cooling_rate: 0.95,
        };

        let result = optimize_tower_placement(-23.55, -46.63, 5000.0, &params);

        // Verify result structure
        assert!(result.towers.len() <= params.max_towers);
        for tower in &result.towers {
            assert!(tower.latitude != 0.0 || tower.longitude != 0.0);
            assert!(tower.antenna_height_m > 0.0);
        }
    }
}
