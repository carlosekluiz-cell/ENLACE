//! # enlace-propagation
//!
//! RF propagation modeling for the ENLACE telecom intelligence platform.
//!
//! This crate provides a comprehensive set of propagation models, atmospheric
//! corrections, vegetation attenuation, and coverage computation tools designed
//! for the Brazilian telecommunications environment.
//!
//! ## Propagation Models
//!
//! Six models covering different frequency ranges and use cases:
//!
//! | Model | Frequency Range | Use Case |
//! |-------|----------------|----------|
//! | [`models::fspl`] | Any | Theoretical baseline |
//! | [`models::hata`] | 150-2000 MHz | Urban/suburban/rural macro-cells |
//! | [`models::itm`] | 20-40000 MHz | Terrain-aware long-distance paths |
//! | [`models::tr38901`] | 500-30000 MHz | 5G NR rural coverage planning |
//! | [`models::p1812`] | 30-6000 MHz | VHF/UHF point-to-area coverage |
//! | [`models::p530`] | 10-100 GHz | Microwave point-to-point links |
//!
//! ## Brazilian-Specific Features
//!
//! - **Vegetation correction** ([`vegetation`]): Per-biome attenuation for
//!   Amazonia, Mata Atlantica, Cerrado, Caatinga, Pampa, and Pantanal.
//! - **Tropical climate parameters**: Default atmospheric and rain rate
//!   values calibrated for Brazilian conditions.
//! - **Rain attenuation**: ITU-R P.838 coefficients with Zone P rain rates.
//!
//! ## Coverage Computation
//!
//! The [`coverage`] module provides parallel (Rayon) grid-based coverage
//! computation for rapid signal strength prediction across an area.
//!
//! ## Quick Start
//!
//! ```rust
//! use enlace_propagation::models::fspl::FsplModel;
//! use enlace_propagation::models::{PropagationModel, PathLossParams, Environment};
//!
//! let model = FsplModel::new();
//! let params = PathLossParams {
//!     frequency_mhz: 900.0,
//!     distance_m: 1000.0,
//!     tx_height_m: 30.0,
//!     rx_height_m: 1.5,
//!     terrain_profile: None,
//!     environment: Environment::Rural,
//! };
//!
//! let result = model.path_loss(&params);
//! println!("Path loss: {:.1} dB", result.loss_db);
//! ```

pub mod atmosphere;
pub mod common;
pub mod coverage;
pub mod diffraction;
pub mod fresnel;
pub mod models;
pub mod vegetation;

// Re-export key types for convenience
pub use common::{
    AntennaPattern, Climate, GeoPoint, Polarization, PropagationMode,
};
pub use coverage::{compute_coverage, CoverageArea, CoverageResult, CoverageStats, TowerConfig};
pub use models::{Environment, PathLossParams, PathLossResult, PropagationModel};
pub use vegetation::{BiomeCorrection, VegetationCorrector, VegetationCorrectionResult};
