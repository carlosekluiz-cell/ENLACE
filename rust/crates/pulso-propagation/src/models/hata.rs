//! Extended Hata / COST-231 propagation model.
//!
//! The Okumura-Hata model is an empirical model widely used for macro-cell
//! coverage prediction in urban, suburban, and rural environments. The
//! COST-231 extension adds support for frequencies up to 2000 MHz.
//!
//! Valid ranges:
//! - Frequency: 150-2000 MHz
//! - Distance: 1-20 km
//! - Base station height: 30-200 m
//! - Mobile height: 1-10 m
//!
//! References:
//! - M. Hata, "Empirical Formula for Propagation Loss in Land Mobile
//!   Radio Services," IEEE Trans. VT, 1980.
//! - COST-231 Final Report, "Digital Mobile Radio Towards Future Generation
//!   Systems," 1999.

use crate::common::PropagationMode;
use super::{Environment, PathLossParams, PathLossResult, PropagationModel};

/// City size classification for the Hata model.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CitySize {
    /// Small or medium city.
    SmallMedium,
    /// Large city (metropolitan center).
    Large,
}

/// Extended Hata / COST-231 propagation model.
pub struct HataModel {
    /// City size classification (affects mobile antenna correction).
    pub city_size: CitySize,
}

impl HataModel {
    /// Create a new Hata model with the given city size.
    pub fn new(city_size: CitySize) -> Self {
        Self { city_size }
    }

    /// Create a Hata model for small/medium cities (default for Brazil).
    pub fn small_medium_city() -> Self {
        Self::new(CitySize::SmallMedium)
    }

    /// Create a Hata model for large/metropolitan cities.
    pub fn large_city() -> Self {
        Self::new(CitySize::Large)
    }

    /// Mobile antenna height correction factor a(h_m).
    fn mobile_correction(&self, freq_mhz: f64, h_m: f64) -> f64 {
        match self.city_size {
            CitySize::SmallMedium => {
                // Small/medium city
                (1.1 * freq_mhz.log10() - 0.7) * h_m - (1.56 * freq_mhz.log10() - 0.8)
            }
            CitySize::Large => {
                if freq_mhz <= 300.0 {
                    // Large city, f <= 300 MHz
                    8.29 * (1.54 * h_m).log10().powi(2) - 1.1
                } else {
                    // Large city, f > 300 MHz
                    3.2 * (11.75 * h_m).log10().powi(2) - 4.97
                }
            }
        }
    }

    /// Compute urban path loss using the Okumura-Hata formula.
    ///
    /// For frequencies 150-1500 MHz (original Hata):
    ///   L = 69.55 + 26.16*log10(f) - 13.82*log10(h_b) - a(h_m)
    ///       + (44.9 - 6.55*log10(h_b))*log10(d_km)
    ///
    /// For frequencies 1500-2000 MHz (COST-231 extension):
    ///   L = 46.3 + 33.9*log10(f) - 13.82*log10(h_b) - a(h_m)
    ///       + (44.9 - 6.55*log10(h_b))*log10(d_km) + C_m
    fn urban_loss(&self, freq_mhz: f64, h_b: f64, h_m: f64, distance_km: f64) -> f64 {
        let a_hm = self.mobile_correction(freq_mhz, h_m);

        if freq_mhz <= 1500.0 {
            // Original Okumura-Hata
            69.55
                + 26.16 * freq_mhz.log10()
                - 13.82 * h_b.log10()
                - a_hm
                + (44.9 - 6.55 * h_b.log10()) * distance_km.log10()
        } else {
            // COST-231 extension
            let c_m = match self.city_size {
                CitySize::SmallMedium => 0.0,
                CitySize::Large => 3.0,
            };
            46.3
                + 33.9 * freq_mhz.log10()
                - 13.82 * h_b.log10()
                - a_hm
                + (44.9 - 6.55 * h_b.log10()) * distance_km.log10()
                + c_m
        }
    }

    /// Compute suburban correction.
    ///
    /// L_sub = L_urban - 2*(log10(f/28))^2 - 5.4
    fn suburban_correction(freq_mhz: f64) -> f64 {
        2.0 * (freq_mhz / 28.0).log10().powi(2) + 5.4
    }

    /// Compute open rural correction.
    ///
    /// L_rural = L_urban - 4.78*(log10(f))^2 + 18.33*log10(f) - 40.94
    fn rural_correction(freq_mhz: f64) -> f64 {
        4.78 * freq_mhz.log10().powi(2) - 18.33 * freq_mhz.log10() + 40.94
    }
}

impl Default for HataModel {
    fn default() -> Self {
        Self::small_medium_city()
    }
}

impl PropagationModel for HataModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq = params.frequency_mhz;
        let distance_km = params.distance_m / 1000.0;
        let h_b = params.tx_height_m;
        let h_m = params.rx_height_m;

        // Validate frequency range
        if freq < 150.0 || freq > 2000.0 {
            warnings.push(format!(
                "Frequency {} MHz outside Hata valid range (150-2000 MHz)",
                freq
            ));
        }

        // Validate distance range
        if distance_km < 1.0 || distance_km > 20.0 {
            warnings.push(format!(
                "Distance {} km outside Hata valid range (1-20 km)",
                distance_km
            ));
        }

        // Validate heights
        if h_b < 30.0 || h_b > 200.0 {
            warnings.push(format!(
                "Base station height {} m outside typical range (30-200 m)",
                h_b
            ));
        }
        if h_m < 1.0 || h_m > 10.0 {
            warnings.push(format!(
                "Mobile height {} m outside typical range (1-10 m)",
                h_m
            ));
        }

        // Clamp parameters to avoid numerical issues
        let h_b_clamped = h_b.max(1.0);
        let h_m_clamped = h_m.max(1.0);
        let dist_clamped = distance_km.max(0.1);
        let freq_clamped = freq.max(1.0);

        // Compute urban loss
        let urban_loss = self.urban_loss(freq_clamped, h_b_clamped, h_m_clamped, dist_clamped);

        // Apply environment correction
        let loss_db = match params.environment {
            Environment::Urban => urban_loss,
            Environment::Suburban => urban_loss - Self::suburban_correction(freq_clamped),
            Environment::Rural | Environment::OpenRural => {
                urban_loss - Self::rural_correction(freq_clamped)
            }
        };

        // Location variability (typical values)
        let variability_db = match params.environment {
            Environment::Urban => 8.0,
            Environment::Suburban => 7.0,
            Environment::Rural | Environment::OpenRural => 6.0,
        };

        PathLossResult {
            loss_db,
            mode: PropagationMode::Combined,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "Extended Hata / COST-231"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (150.0, 2000.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hata_urban_900mhz() {
        let model = HataModel::small_medium_city();
        let params = PathLossParams {
            frequency_mhz: 900.0,
            distance_m: 5000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        // Expected: around 140-150 dB for urban at 5 km
        assert!(
            result.loss_db > 120.0 && result.loss_db < 170.0,
            "Hata urban 900 MHz, 5 km: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_hata_suburban_less_than_urban() {
        let model = HataModel::small_medium_city();

        let urban_params = PathLossParams {
            frequency_mhz: 900.0,
            distance_m: 5000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let suburban_params = PathLossParams {
            environment: Environment::Suburban,
            ..urban_params.clone()
        };

        let urban = model.path_loss(&urban_params);
        let suburban = model.path_loss(&suburban_params);

        assert!(
            suburban.loss_db < urban.loss_db,
            "Suburban ({} dB) should be less than urban ({} dB)",
            suburban.loss_db,
            urban.loss_db
        );
    }

    #[test]
    fn test_hata_rural_less_than_suburban() {
        let model = HataModel::small_medium_city();

        let suburban_params = PathLossParams {
            frequency_mhz: 900.0,
            distance_m: 5000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Suburban,
        };
        let rural_params = PathLossParams {
            environment: Environment::Rural,
            ..suburban_params.clone()
        };

        let suburban = model.path_loss(&suburban_params);
        let rural = model.path_loss(&rural_params);

        assert!(
            rural.loss_db < suburban.loss_db,
            "Rural ({} dB) should be less than suburban ({} dB)",
            rural.loss_db,
            suburban.loss_db
        );
    }

    #[test]
    fn test_hata_cost231_extension() {
        let model = HataModel::small_medium_city();

        // Test at 1800 MHz (COST-231 range)
        let params = PathLossParams {
            frequency_mhz: 1800.0,
            distance_m: 5000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert!(
            result.loss_db > 130.0 && result.loss_db < 180.0,
            "COST-231 at 1800 MHz: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_hata_distance_increases_loss() {
        let model = HataModel::small_medium_city();

        let near = PathLossParams {
            frequency_mhz: 900.0,
            distance_m: 1000.0,
            tx_height_m: 50.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let far = PathLossParams {
            distance_m: 10000.0,
            ..near.clone()
        };

        let near_result = model.path_loss(&near);
        let far_result = model.path_loss(&far);

        assert!(
            far_result.loss_db > near_result.loss_db,
            "Farther distance ({} dB) should have more loss than near ({} dB)",
            far_result.loss_db,
            near_result.loss_db
        );
    }

    #[test]
    fn test_hata_warnings_out_of_range() {
        let model = HataModel::small_medium_city();

        let params = PathLossParams {
            frequency_mhz: 100.0, // below 150 MHz
            distance_m: 500.0,    // below 1 km
            tx_height_m: 10.0,    // below 30 m
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };

        let result = model.path_loss(&params);
        assert!(
            !result.warnings.is_empty(),
            "Should produce warnings for out-of-range parameters"
        );
    }
}
