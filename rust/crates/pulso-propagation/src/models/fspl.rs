//! Free-Space Path Loss (FSPL) model.
//!
//! The most fundamental propagation model, representing signal attenuation
//! in an unobstructed vacuum. Serves as the baseline for all other models.
//!
//! Formula:
//!   FSPL(dB) = 20*log10(d_m) + 20*log10(f_hz) - 147.55
//!
//! Valid for any frequency and distance (theoretical).

use crate::common::{mhz_to_hz, PropagationMode};
use super::{PathLossParams, PathLossResult, PropagationModel};

/// Free-Space Path Loss model.
pub struct FsplModel;

impl FsplModel {
    /// Create a new FSPL model instance.
    pub fn new() -> Self {
        Self
    }

    /// Compute FSPL directly from frequency (MHz) and distance (m).
    ///
    /// FSPL(dB) = 20*log10(d_m) + 20*log10(f_hz) - 147.55
    pub fn compute(freq_mhz: f64, distance_m: f64) -> f64 {
        if distance_m <= 0.0 || freq_mhz <= 0.0 {
            return 0.0;
        }
        let freq_hz = mhz_to_hz(freq_mhz);
        20.0 * distance_m.log10() + 20.0 * freq_hz.log10() - 147.55
    }
}

impl Default for FsplModel {
    fn default() -> Self {
        Self::new()
    }
}

impl PropagationModel for FsplModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();

        if params.distance_m <= 0.0 {
            warnings.push("Distance must be positive".to_string());
            return PathLossResult {
                loss_db: 0.0,
                mode: PropagationMode::LineOfSight,
                variability_db: 0.0,
                warnings,
            };
        }

        let loss_db = FsplModel::compute(params.frequency_mhz, params.distance_m);

        PathLossResult {
            loss_db,
            mode: PropagationMode::LineOfSight,
            variability_db: 0.0, // FSPL is deterministic
            warnings,
        }
    }

    fn name(&self) -> &str {
        "Free-Space Path Loss (FSPL)"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (0.001, 1_000_000.0) // Essentially unlimited
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Environment;

    #[test]
    fn test_fspl_700mhz_1km() {
        // FSPL at 700 MHz, 1 km
        // 20*log10(1000) + 20*log10(700e6) - 147.55
        // = 60 + 176.9 - 147.55 = 89.35 dB
        let loss = FsplModel::compute(700.0, 1000.0);
        assert!(
            (loss - 89.35).abs() < 0.1,
            "FSPL at 700 MHz, 1 km: expected ~89.35 dB, got {} dB",
            loss
        );
    }

    #[test]
    fn test_fspl_900mhz_1km() {
        // 20*log10(1000) + 20*log10(900e6) - 147.55
        let loss = FsplModel::compute(900.0, 1000.0);
        // Expected: 60 + 179.08 - 147.55 ≈ 91.53 dB
        assert!(
            (loss - 91.5).abs() < 0.5,
            "FSPL at 900 MHz, 1 km: {} dB",
            loss
        );
    }

    #[test]
    fn test_fspl_inverse_square_law() {
        // Doubling distance adds 6 dB
        let loss_1km = FsplModel::compute(900.0, 1000.0);
        let loss_2km = FsplModel::compute(900.0, 2000.0);
        let diff = loss_2km - loss_1km;
        assert!(
            (diff - 6.02).abs() < 0.1,
            "Doubling distance should add ~6 dB: {} dB difference",
            diff
        );
    }

    #[test]
    fn test_fspl_zero_distance() {
        let loss = FsplModel::compute(900.0, 0.0);
        assert_eq!(loss, 0.0, "Zero distance should give zero loss");
    }

    #[test]
    fn test_fspl_via_trait() {
        let model = FsplModel::new();
        let params = PathLossParams {
            frequency_mhz: 700.0,
            distance_m: 1000.0,
            tx_height_m: 30.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Rural,
        };
        let result = model.path_loss(&params);
        assert!(
            (result.loss_db - 89.35).abs() < 0.1,
            "FSPL via trait: {} dB",
            result.loss_db
        );
        assert_eq!(result.mode, PropagationMode::LineOfSight);
    }
}
