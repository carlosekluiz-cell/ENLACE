//! ITU-R P.1812 point-to-area prediction model (simplified).
//!
//! This model is designed for VHF/UHF point-to-area coverage prediction
//! in the frequency range 30 MHz to 6 GHz. It accounts for:
//! - Free-space loss (baseline)
//! - Terrain diffraction (Deygout method)
//! - Clutter loss (urban/suburban/rural)
//! - Atmospheric absorption
//! - Location variability correction
//!
//! Reference: ITU-R P.1812-7 (2023).

use crate::common::PropagationMode;
use crate::diffraction::deygout_diffraction_loss;
use crate::models::fspl::FsplModel;
use super::{Environment, PathLossParams, PathLossResult, PropagationModel};

/// ITU-R P.1812 point-to-area coverage prediction model.
pub struct P1812Model {
    /// Time percentage for which the predicted loss is not exceeded (0.01-0.99).
    pub time_pct: f64,
    /// Location percentage for which the predicted signal level is exceeded (0.01-0.99).
    pub location_pct: f64,
}

impl P1812Model {
    /// Create a new P.1812 model.
    pub fn new(time_pct: f64, location_pct: f64) -> Self {
        Self {
            time_pct: time_pct.clamp(0.01, 0.99),
            location_pct: location_pct.clamp(0.01, 0.99),
        }
    }

    /// Create with 50% time and 50% location (median prediction).
    pub fn median() -> Self {
        Self::new(0.50, 0.50)
    }

    /// Clutter loss in dB based on environment type and frequency.
    ///
    /// Typical values from ITU-R P.1812 Table 4.
    fn clutter_loss(environment: Environment, freq_mhz: f64) -> f64 {
        let freq_factor = (freq_mhz / 1000.0).max(0.1).log10();

        match environment {
            Environment::Urban => {
                // Dense urban clutter: 15-25 dB
                18.0 + 5.0 * freq_factor
            }
            Environment::Suburban => {
                // Suburban clutter: 8-15 dB
                10.0 + 4.0 * freq_factor
            }
            Environment::Rural => {
                // Rural clutter: 0-5 dB (scattered trees/structures)
                2.0 + 2.0 * freq_factor.max(0.0)
            }
            Environment::OpenRural => {
                // Open area: essentially no clutter
                0.0
            }
        }
    }

    /// Location variability correction in dB.
    ///
    /// Uses a simplified approximation of the inverse normal distribution
    /// applied to the location percentage.
    fn location_variability_correction(location_pct: f64, environment: Environment) -> f64 {
        // Standard deviation of location variability
        let sigma_l = match environment {
            Environment::Urban => 7.0,
            Environment::Suburban => 6.0,
            Environment::Rural => 5.5,
            Environment::OpenRural => 4.0,
        };

        // Simplified inverse normal approximation
        // For location_pct > 0.5, we need a positive margin (more signal)
        let z = if (location_pct - 0.5).abs() < 0.01 {
            0.0
        } else if location_pct > 0.5 {
            // Approximation for upper tail
            let p = 1.0 - location_pct;
            let t = (-2.0 * p.ln()).sqrt();
            t - (2.515517 + 0.802853 * t + 0.010328 * t * t)
                / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t)
        } else {
            // Approximation for lower tail (negative z)
            let p = location_pct;
            let t = (-2.0 * p.ln()).sqrt();
            -(t - (2.515517 + 0.802853 * t + 0.010328 * t * t)
                / (1.0 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t))
        };

        z * sigma_l // Positive z for location_pct > 0.5 adds margin (more loss)
    }
}

impl Default for P1812Model {
    fn default() -> Self {
        Self::median()
    }
}

impl PropagationModel for P1812Model {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();

        // Validate frequency
        if params.frequency_mhz < 30.0 || params.frequency_mhz > 6000.0 {
            warnings.push(format!(
                "Frequency {} MHz outside P.1812 range (30-6000 MHz)",
                params.frequency_mhz
            ));
        }

        // Step 1: Free-space path loss (baseline)
        let fspl = FsplModel::compute(params.frequency_mhz, params.distance_m);

        // Step 2: Diffraction loss from terrain profile
        let diffraction_loss = if let Some(ref profile) = params.terrain_profile {
            deygout_diffraction_loss(
                profile,
                params.tx_height_m,
                params.rx_height_m,
                params.frequency_mhz,
            )
        } else {
            0.0
        };

        // Step 3: Clutter loss
        let clutter = Self::clutter_loss(params.environment, params.frequency_mhz);

        // Step 4: Atmospheric absorption (small for VHF/UHF)
        let distance_km = params.distance_m / 1000.0;
        let atmos = crate::atmosphere::atmospheric_absorption_brazil(
            params.frequency_mhz,
            distance_km,
        );

        // Step 5: Location variability correction
        let loc_var = Self::location_variability_correction(
            self.location_pct,
            params.environment,
        );

        // Determine propagation mode
        let mode = if diffraction_loss > 1.0 {
            PropagationMode::Diffraction
        } else {
            PropagationMode::LineOfSight
        };

        // Total loss
        let total_loss = fspl + diffraction_loss + clutter + atmos + loc_var;

        // Location variability (standard deviation)
        let variability_db = match params.environment {
            Environment::Urban => 7.0,
            Environment::Suburban => 6.0,
            Environment::Rural => 5.5,
            Environment::OpenRural => 4.0,
        };

        PathLossResult {
            loss_db: total_loss,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "ITU-R P.1812"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (30.0, 6000.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_p1812_urban_higher_than_rural() {
        let model = P1812Model::median();

        let urban = PathLossParams {
            frequency_mhz: 900.0,
            distance_m: 5000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let rural = PathLossParams {
            environment: Environment::OpenRural,
            ..urban.clone()
        };

        let urban_result = model.path_loss(&urban);
        let rural_result = model.path_loss(&rural);

        assert!(
            urban_result.loss_db > rural_result.loss_db,
            "Urban ({} dB) should have more loss than open rural ({} dB)",
            urban_result.loss_db,
            rural_result.loss_db
        );
    }

    #[test]
    fn test_p1812_clutter_values() {
        // Urban clutter at 900 MHz should be 15-25 dB
        let urban_clutter = P1812Model::clutter_loss(Environment::Urban, 900.0);
        assert!(
            urban_clutter > 10.0 && urban_clutter < 30.0,
            "Urban clutter at 900 MHz: {} dB",
            urban_clutter
        );

        // Open rural should be ~0
        let open_clutter = P1812Model::clutter_loss(Environment::OpenRural, 900.0);
        assert!(
            open_clutter < 1.0,
            "Open rural clutter: {} dB",
            open_clutter
        );
    }

    #[test]
    fn test_p1812_frequency_range() {
        let model = P1812Model::median();
        let (min, max) = model.frequency_range();
        assert_eq!(min, 30.0);
        assert_eq!(max, 6000.0);
    }

    #[test]
    fn test_p1812_location_variability() {
        // At 50% location, correction should be ~0
        let correction_50 =
            P1812Model::location_variability_correction(0.50, Environment::Urban);
        assert!(
            correction_50.abs() < 1.0,
            "50% location correction should be near 0: {} dB",
            correction_50
        );

        // At 90% location, correction should be positive (more loss margin)
        let correction_90 =
            P1812Model::location_variability_correction(0.90, Environment::Urban);
        assert!(
            correction_90 > 0.0,
            "90% location should add margin: {} dB",
            correction_90
        );
    }
}
