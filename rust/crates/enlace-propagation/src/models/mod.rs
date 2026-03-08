//! RF propagation models for the ENLACE platform.
//!
//! This module provides six propagation models covering different frequency
//! ranges, distances, and use cases relevant to Brazilian telecommunications:
//!
//! - [`fspl`]: Free-Space Path Loss — theoretical baseline
//! - [`hata`]: Extended Hata / COST-231 — urban/suburban/rural VHF/UHF
//! - [`itm`]: Longley-Rice Irregular Terrain Model — terrain-aware long paths
//! - [`tr38901`]: 3GPP TR 38.901 Rural Macrocell — 5G NR planning
//! - [`p1812`]: ITU-R P.1812 — VHF/UHF point-to-area coverage
//! - [`p530`]: ITU-R P.530 — microwave point-to-point link budget

pub mod fspl;
pub mod hata;
pub mod itm;
pub mod p1812;
pub mod p530;
pub mod tr38901;

use crate::common::PropagationMode;

/// Common trait for all propagation models.
pub trait PropagationModel {
    /// Compute path loss for the given parameters.
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult;

    /// Human-readable model name.
    fn name(&self) -> &str;

    /// Valid frequency range (min_mhz, max_mhz).
    fn frequency_range(&self) -> (f64, f64);
}

/// Input parameters for propagation model calculations.
#[derive(Debug, Clone)]
pub struct PathLossParams {
    /// Carrier frequency in MHz.
    pub frequency_mhz: f64,
    /// Distance between TX and RX in meters.
    pub distance_m: f64,
    /// Transmitter antenna height above ground in meters.
    pub tx_height_m: f64,
    /// Receiver antenna height above ground in meters.
    pub rx_height_m: f64,
    /// Optional terrain profile as (distance_m, elevation_m) pairs.
    pub terrain_profile: Option<Vec<(f64, f64)>>,
    /// Environment type classification.
    pub environment: Environment,
}

/// Environment classification for propagation models.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Environment {
    /// Dense urban area with tall buildings.
    Urban,
    /// Suburban residential area.
    Suburban,
    /// Rural area with sparse structures.
    Rural,
    /// Open rural area (farmland, plains).
    OpenRural,
}

/// Result of a path loss calculation.
#[derive(Debug, Clone)]
pub struct PathLossResult {
    /// Total path loss in dB.
    pub loss_db: f64,
    /// Determined propagation mode.
    pub mode: PropagationMode,
    /// Standard deviation of path loss (location variability) in dB.
    pub variability_db: f64,
    /// Any warnings (e.g., parameters outside valid range).
    pub warnings: Vec<String>,
}
