//! 3GPP TR 38.901 Rural Macrocell (RMa) path loss model.
//!
//! This model is designed for 5G NR coverage planning in rural areas.
//! It provides both LOS and NLOS path loss predictions for frequencies
//! from 0.5 to 30 GHz and distances from 10 m to 10 km.
//!
//! Reference: 3GPP TR 38.901 V17.0.0 (2022-03), Table 7.4.1-1.

use crate::common::{PropagationMode, SPEED_OF_LIGHT};
use super::{Environment, PathLossParams, PathLossResult, PropagationModel};

/// 3GPP TR 38.901 Rural Macrocell (RMa) model.
pub struct Tr38901RmaModel {
    /// Average building height in meters (default 5 m for rural).
    pub avg_building_height_m: f64,
    /// Average street width in meters (default 20 m for rural).
    pub avg_street_width_m: f64,
}

impl Tr38901RmaModel {
    /// Create a new TR 38.901 RMa model with default parameters.
    pub fn new() -> Self {
        Self {
            avg_building_height_m: 5.0,
            avg_street_width_m: 20.0,
        }
    }

    /// Create with custom building/street parameters.
    pub fn with_params(avg_building_height_m: f64, avg_street_width_m: f64) -> Self {
        Self {
            avg_building_height_m,
            avg_street_width_m,
        }
    }

    /// Compute LOS path loss.
    ///
    /// For d_2D < d_BP:
    ///   PL1 = 20*log10(40*pi*d_3D*f_c/3) + min(0.03*h^1.72, 10)*log10(d_3D)
    ///         - min(0.044*h^1.72, 14.77) + 0.002*log10(h)*d_3D
    ///
    /// For d_2D >= d_BP:
    ///   PL2 = PL1(d_BP) + 40*log10(d_3D/d_BP)
    fn los_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h = self.avg_building_height_m;

        // Breakpoint distance
        let d_bp = 2.0 * std::f64::consts::PI * h_bs * h_ut * freq_ghz * 1e9 / SPEED_OF_LIGHT;

        let term1 = 20.0 * (40.0 * std::f64::consts::PI * d_3d * freq_ghz / 3.0)
            .max(1.0)
            .log10();
        let term2 = (0.03 * h.powf(1.72)).min(10.0) * d_3d.max(1.0).log10();
        let term3 = (0.044 * h.powf(1.72)).min(14.77);
        let term4 = 0.002 * h.max(0.01).log10() * d_3d;

        let pl1 = term1 + term2 - term3 + term4;

        if d_2d < d_bp {
            pl1
        } else {
            // Beyond breakpoint
            let d_3d_bp = (d_bp * d_bp + (h_bs - h_ut).powi(2)).sqrt();
            let pl1_bp = {
                let t1 = 20.0
                    * (40.0 * std::f64::consts::PI * d_3d_bp * freq_ghz / 3.0)
                        .max(1.0)
                        .log10();
                let t2 = (0.03 * h.powf(1.72)).min(10.0) * d_3d_bp.max(1.0).log10();
                let t3 = (0.044 * h.powf(1.72)).min(14.77);
                let t4 = 0.002 * h.max(0.01).log10() * d_3d_bp;
                t1 + t2 - t3 + t4
            };
            pl1_bp + 40.0 * (d_3d / d_3d_bp).max(1.0).log10()
        }
    }

    /// Compute NLOS path loss.
    ///
    /// PL_NLOS = max(PL_LOS, PL'_NLOS)
    /// PL'_NLOS = 161.04 - 7.1*log10(W) + 7.5*log10(h)
    ///            - (24.37 - 3.7*(h/h_BS)^2)*log10(h_BS)
    ///            + (43.42 - 3.1*log10(h_BS))*(log10(d_3D) - 3)
    ///            + 20*log10(f_c) - (3.2*(log10(11.75*h_UT))^2 - 4.97)
    fn nlos_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h = self.avg_building_height_m;
        let w = self.avg_street_width_m;

        let pl_los = self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut);

        let pl_nlos_prime = 161.04
            - 7.1 * w.max(1.0).log10()
            + 7.5 * h.max(1.0).log10()
            - (24.37 - 3.7 * (h / h_bs.max(1.0)).powi(2)) * h_bs.max(1.0).log10()
            + (43.42 - 3.1 * h_bs.max(1.0).log10()) * (d_3d.max(1.0).log10() - 3.0)
            + 20.0 * freq_ghz.max(0.001).log10()
            - (3.2 * (11.75 * h_ut.max(0.1)).log10().powi(2) - 4.97);

        pl_los.max(pl_nlos_prime)
    }
}

impl Default for Tr38901RmaModel {
    fn default() -> Self {
        Self::new()
    }
}

impl PropagationModel for Tr38901RmaModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq_ghz = params.frequency_mhz / 1000.0;
        let h_bs = params.tx_height_m;
        let h_ut = params.rx_height_m;

        // Validate frequency
        if freq_ghz < 0.5 || freq_ghz > 30.0 {
            warnings.push(format!(
                "Frequency {} GHz outside TR 38.901 RMa range (0.5-30 GHz)",
                freq_ghz
            ));
        }

        // Validate distance
        if params.distance_m < 10.0 || params.distance_m > 10_000.0 {
            warnings.push(format!(
                "Distance {} m outside TR 38.901 RMa range (10-10000 m)",
                params.distance_m
            ));
        }

        // 2D and 3D distances
        let d_2d = params.distance_m;
        let d_3d = (d_2d * d_2d + (h_bs - h_ut).powi(2)).sqrt();

        // Determine LOS probability based on environment
        let is_los = match params.environment {
            Environment::OpenRural => true, // Open rural is always LOS
            Environment::Rural => d_2d < 1000.0, // Simplified LOS probability
            Environment::Suburban => d_2d < 500.0,
            Environment::Urban => d_2d < 200.0,
        };

        let (loss_db, mode) = if is_los {
            (
                self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::LineOfSight,
            )
        } else {
            (
                self.nlos_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::Diffraction,
            )
        };

        // Shadow fading standard deviation
        let variability_db = if is_los { 4.0 } else { 8.0 };

        PathLossResult {
            loss_db,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "3GPP TR 38.901 Rural Macrocell (RMa)"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (500.0, 30_000.0) // 0.5 - 30 GHz
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tr38901_los_700mhz() {
        let model = Tr38901RmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 700.0,
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let result = model.path_loss(&params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);
        assert!(
            result.loss_db > 60.0 && result.loss_db < 140.0,
            "TR 38.901 LOS at 700 MHz, 1 km: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_tr38901_nlos_higher_loss() {
        let model = Tr38901RmaModel::new();

        let los_params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let nlos_params = PathLossParams {
            environment: Environment::Urban,
            ..los_params.clone()
        };

        let los_result = model.path_loss(&los_params);
        let nlos_result = model.path_loss(&nlos_params);

        assert!(
            nlos_result.loss_db >= los_result.loss_db,
            "NLOS ({} dB) should be >= LOS ({} dB)",
            nlos_result.loss_db,
            los_result.loss_db
        );
    }

    #[test]
    fn test_tr38901_distance_increases_loss() {
        let model = Tr38901RmaModel::new();

        let near = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 100.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let far = PathLossParams {
            distance_m: 5000.0,
            ..near.clone()
        };

        let near_result = model.path_loss(&near);
        let far_result = model.path_loss(&far);

        assert!(
            far_result.loss_db > near_result.loss_db,
            "Farther ({} dB) should have more loss than near ({} dB)",
            far_result.loss_db,
            near_result.loss_db
        );
    }

    #[test]
    fn test_tr38901_frequency_warning() {
        let model = Tr38901RmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 50_000.0, // 50 GHz, above 30 GHz limit
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Rural,
        };
        let result = model.path_loss(&params);
        assert!(!result.warnings.is_empty());
    }
}
