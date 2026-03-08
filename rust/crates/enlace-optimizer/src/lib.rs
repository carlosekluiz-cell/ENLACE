//! # enlace-optimizer
//!
//! Tower placement optimization for the ENLACE telecom intelligence platform.
//!
//! This crate provides a complete optimization pipeline for determining
//! optimal tower locations to maximize coverage while minimizing cost:
//!
//! 1. **Candidate generation** ([`candidates`]): Grid-based candidate tower
//!    positions scored by elevation.
//! 2. **Set cover** ([`setcover`]): Greedy weighted set-cover algorithm for
//!    initial tower selection (typically within 1.5x of optimal).
//! 3. **Simulated annealing** ([`annealing`]): Metropolis-based refinement
//!    that reduces tower count while maintaining coverage targets.
//! 4. **Constraints** ([`constraints`]): Tower spacing validation and height
//!    recommendations based on terrain.
//! 5. **Output** ([`output`]): Full pipeline orchestration and CAPEX estimation
//!    using BNDES/Abrint benchmarks.
//!
//! ## Quick Start
//!
//! ```rust
//! use enlace_optimizer::output::{optimize_tower_placement, OptimizationParams};
//!
//! let params = OptimizationParams {
//!     coverage_target_pct: 90.0,
//!     max_towers: 10,
//!     candidate_spacing_m: 1000.0,
//!     annealing_iterations: 500,
//!     ..Default::default()
//! };
//!
//! let result = optimize_tower_placement(-23.55, -46.63, 5000.0, &params);
//! println!("Placed {} towers, coverage: {:.1}%", result.towers.len(), result.total_coverage_pct);
//! println!("Estimated CAPEX: R$ {:.0}", result.estimated_capex_brl);
//! ```

pub mod annealing;
pub mod candidates;
pub mod constraints;
pub mod output;
pub mod setcover;

// Re-export key types for convenience
pub use annealing::{AnnealingParams, AnnealingSolver};
pub use candidates::{CandidateGenerator, CandidateType, TowerCandidate};
pub use constraints::{
    recommend_height, validate_spacing, MAX_TOWER_HEIGHT_M, MIN_TOWER_HEIGHT_M,
    MIN_TOWER_SPACING_M,
};
pub use output::{
    estimate_capex, optimize_tower_placement, OptimizationParams, OptimizationResult,
    TowerPlacement,
};
pub use setcover::{CoverageSolution, DemandPoint, SetCoverSolver};
