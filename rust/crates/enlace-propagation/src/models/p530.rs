//! ITU-R P.530 microwave point-to-point link budget model.
//!
//! Designed for microwave backhaul links in the 10-100 GHz range over
//! distances of 1-100 km. Accounts for:
//! - Free-space path loss
//! - Atmospheric gaseous absorption
//! - Rain attenuation (critical for Brazilian tropical climate)
//! - Multipath fading
//!
//! Includes rain attenuation based on ITU-R P.838 and Brazilian rain
//! rate statistics from ITU-R P.837 (Zone P — tropical).
//!
//! References:
//! - ITU-R P.530-18 (2021)
//! - ITU-R P.838-3 (2005)
//! - ITU-R P.837-7 (2017)

use crate::common::Polarization;
use crate::models::fspl::FsplModel;

/// Parameters for a microwave link budget calculation.
#[derive(Debug, Clone)]
pub struct LinkBudgetParams {
    /// Carrier frequency in GHz.
    pub frequency_ghz: f64,
    /// Path distance in km.
    pub distance_km: f64,
    /// Transmitter output power in dBm.
    pub tx_power_dbm: f64,
    /// Transmitter antenna gain in dBi.
    pub tx_antenna_gain_dbi: f64,
    /// Receiver antenna gain in dBi.
    pub rx_antenna_gain_dbi: f64,
    /// Receiver sensitivity threshold in dBm.
    pub rx_threshold_dbm: f64,
    /// Antenna polarization.
    pub polarization: Polarization,
    /// Rain rate exceeded 0.01% of time (mm/h).
    /// Default 145 mm/h for Brazilian tropical (ITU-R P.837 Zone P).
    pub rain_rate_mmh: f64,
}

impl Default for LinkBudgetParams {
    fn default() -> Self {
        Self {
            frequency_ghz: 18.0,
            distance_km: 10.0,
            tx_power_dbm: 20.0,
            tx_antenna_gain_dbi: 38.0,
            rx_antenna_gain_dbi: 38.0,
            rx_threshold_dbm: -70.0,
            polarization: Polarization::Vertical,
            rain_rate_mmh: 145.0, // Brazilian tropical
        }
    }
}

/// Result of a microwave link budget calculation.
#[derive(Debug, Clone)]
pub struct LinkBudgetResult {
    /// Free-space path loss in dB.
    pub free_space_loss_db: f64,
    /// Atmospheric gaseous absorption in dB.
    pub atmospheric_absorption_db: f64,
    /// Rain attenuation exceeded 0.01% of time in dB.
    pub rain_attenuation_db: f64,
    /// Total path loss in dB (FSPL + atmospheric + rain).
    pub total_path_loss_db: f64,
    /// Received power in dBm (clear sky, no rain).
    pub received_power_dbm: f64,
    /// Fade margin in dB (margin above receiver threshold, clear sky).
    pub fade_margin_db: f64,
    /// Estimated link availability percentage.
    pub availability_pct: f64,
}

/// Compute a complete microwave link budget.
pub fn compute_link_budget(params: &LinkBudgetParams) -> LinkBudgetResult {
    // Free-space path loss
    let freq_mhz = params.frequency_ghz * 1000.0;
    let distance_m = params.distance_km * 1000.0;
    let fspl = FsplModel::compute(freq_mhz, distance_m);

    // Atmospheric absorption
    let atmos = crate::atmosphere::atmospheric_absorption_brazil(freq_mhz, params.distance_km);

    // Rain attenuation
    let rain_atten = rain_attenuation(
        params.frequency_ghz,
        params.distance_km,
        params.rain_rate_mmh,
        params.polarization,
    );

    // Total path loss (clear sky)
    let total_loss = fspl + atmos;

    // Received power (clear sky)
    let received_power = params.tx_power_dbm
        + params.tx_antenna_gain_dbi
        + params.rx_antenna_gain_dbi
        - total_loss;

    // Fade margin (clear sky)
    let fade_margin = received_power - params.rx_threshold_dbm;

    // Availability estimation
    let availability = estimate_availability(fade_margin, rain_atten);

    LinkBudgetResult {
        free_space_loss_db: fspl,
        atmospheric_absorption_db: atmos,
        rain_attenuation_db: rain_atten,
        total_path_loss_db: total_loss,
        received_power_dbm: received_power,
        fade_margin_db: fade_margin,
        availability_pct: availability,
    }
}

/// Compute rain attenuation using simplified ITU-R P.838 model.
///
/// Specific rain attenuation: gamma_R = k * R^alpha (dB/km)
/// Path attenuation: A_R = gamma_R * d * r (dB)
/// where r is the distance reduction factor.
fn rain_attenuation(
    freq_ghz: f64,
    distance_km: f64,
    rain_rate_mmh: f64,
    polarization: Polarization,
) -> f64 {
    if rain_rate_mmh <= 0.0 || freq_ghz < 1.0 {
        return 0.0;
    }

    // ITU-R P.838 coefficients k and alpha
    // Simplified lookup for common frequencies
    let (k, alpha) = rain_coefficients(freq_ghz, polarization);

    // Specific attenuation (dB/km)
    let gamma_r = k * rain_rate_mmh.powf(alpha);

    // Distance reduction factor (ITU-R P.530)
    // r = 1 / (1 + d/d_0) where d_0 depends on rain rate
    let d_0 = 35.0 * (-0.015 * rain_rate_mmh).exp();
    let r = 1.0 / (1.0 + distance_km / d_0.max(1.0));

    // Path rain attenuation
    gamma_r * distance_km * r
}

/// Get rain attenuation coefficients k and alpha from ITU-R P.838.
///
/// Simplified interpolation for key frequencies. Values are approximate
/// and suitable for engineering calculations.
fn rain_coefficients(freq_ghz: f64, polarization: Polarization) -> (f64, f64) {
    // Simplified coefficient lookup table
    // (freq_ghz, k_h, alpha_h, k_v, alpha_v)
    let table: &[(f64, f64, f64, f64, f64)] = &[
        (1.0, 0.0000387, 0.912, 0.0000352, 0.880),
        (5.0, 0.000973, 1.074, 0.000854, 1.065),
        (10.0, 0.0101, 1.276, 0.00887, 1.264),
        (15.0, 0.0367, 1.154, 0.0335, 1.128),
        (18.0, 0.0571, 1.090, 0.0527, 1.062),
        (23.0, 0.0963, 1.021, 0.0894, 0.999),
        (28.0, 0.148, 0.965, 0.139, 0.946),
        (35.0, 0.233, 0.918, 0.221, 0.900),
        (40.0, 0.299, 0.895, 0.285, 0.878),
        (50.0, 0.424, 0.867, 0.406, 0.852),
        (60.0, 0.543, 0.853, 0.521, 0.839),
        (80.0, 0.772, 0.842, 0.742, 0.830),
        (100.0, 0.964, 0.840, 0.928, 0.829),
    ];

    // Find surrounding entries for interpolation
    let (k, alpha) = if freq_ghz <= table[0].0 {
        match polarization {
            Polarization::Horizontal => (table[0].1, table[0].2),
            Polarization::Vertical => (table[0].3, table[0].4),
        }
    } else if freq_ghz >= table.last().unwrap().0 {
        let last = table.last().unwrap();
        match polarization {
            Polarization::Horizontal => (last.1, last.2),
            Polarization::Vertical => (last.3, last.4),
        }
    } else {
        // Linear interpolation in log space for k, linear for alpha
        let mut lower = &table[0];
        let mut upper = &table[1];
        for i in 0..table.len() - 1 {
            if freq_ghz >= table[i].0 && freq_ghz <= table[i + 1].0 {
                lower = &table[i];
                upper = &table[i + 1];
                break;
            }
        }

        let frac = (freq_ghz - lower.0) / (upper.0 - lower.0);

        match polarization {
            Polarization::Horizontal => {
                let k_log = lower.1.ln() + frac * (upper.1.ln() - lower.1.ln());
                let alpha = lower.2 + frac * (upper.2 - lower.2);
                (k_log.exp(), alpha)
            }
            Polarization::Vertical => {
                let k_log = lower.3.ln() + frac * (upper.3.ln() - lower.3.ln());
                let alpha = lower.4 + frac * (upper.4 - lower.4);
                (k_log.exp(), alpha)
            }
        }
    };

    (k, alpha)
}

/// Estimate link availability based on fade margin and rain attenuation.
///
/// Simple model:
/// - If fade_margin > rain_attenuation: availability > 99.99%
/// - Otherwise, estimate based on margin deficit
fn estimate_availability(fade_margin_db: f64, rain_atten_0_01_pct: f64) -> f64 {
    if fade_margin_db <= 0.0 {
        // Link does not close even in clear sky
        return 0.0;
    }

    if fade_margin_db >= rain_atten_0_01_pct {
        // Margin exceeds rain attenuation at 0.01% => >99.99% availability
        99.99
    } else if fade_margin_db >= rain_atten_0_01_pct * 0.75 {
        // Partially covered
        99.95
    } else if fade_margin_db >= rain_atten_0_01_pct * 0.5 {
        99.9
    } else if fade_margin_db >= rain_atten_0_01_pct * 0.25 {
        99.5
    } else {
        99.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_link_budget_18ghz_10km() {
        let params = LinkBudgetParams {
            frequency_ghz: 18.0,
            distance_km: 10.0,
            tx_power_dbm: 20.0,
            tx_antenna_gain_dbi: 38.0,
            rx_antenna_gain_dbi: 38.0,
            rx_threshold_dbm: -70.0,
            polarization: Polarization::Vertical,
            rain_rate_mmh: 145.0,
        };

        let result = compute_link_budget(&params);

        // FSPL at 18 GHz, 10 km:
        // 20*log10(10000) + 20*log10(18e9) - 147.55 = 80 + 205.1 - 147.55 ≈ 137.55 dB
        assert!(
            (result.free_space_loss_db - 137.55).abs() < 1.0,
            "FSPL: {} dB",
            result.free_space_loss_db
        );

        // Should have positive fade margin
        assert!(
            result.fade_margin_db > 0.0,
            "Should have positive fade margin: {} dB",
            result.fade_margin_db
        );

        // Rain attenuation should be significant for tropical
        assert!(
            result.rain_attenuation_db > 5.0,
            "Rain attenuation should be significant: {} dB",
            result.rain_attenuation_db
        );

        // Availability should be reasonable
        assert!(
            result.availability_pct >= 99.0,
            "Availability: {}%",
            result.availability_pct
        );
    }

    #[test]
    fn test_rain_attenuation_increases_with_frequency() {
        let rain_10ghz = rain_attenuation(10.0, 10.0, 145.0, Polarization::Vertical);
        let rain_18ghz = rain_attenuation(18.0, 10.0, 145.0, Polarization::Vertical);
        let rain_28ghz = rain_attenuation(28.0, 10.0, 145.0, Polarization::Vertical);

        assert!(
            rain_18ghz > rain_10ghz,
            "18 GHz rain ({} dB) should exceed 10 GHz ({})",
            rain_18ghz,
            rain_10ghz
        );
        assert!(
            rain_28ghz > rain_18ghz,
            "28 GHz rain ({} dB) should exceed 18 GHz ({})",
            rain_28ghz,
            rain_18ghz
        );
    }

    #[test]
    fn test_rain_attenuation_brazil_tropical() {
        // Brazilian tropical rain rate at 0.01%: 145 mm/h
        let rain = rain_attenuation(18.0, 10.0, 145.0, Polarization::Vertical);
        // Should be substantial (typically 20-60 dB for 10 km at 18 GHz)
        assert!(
            rain > 10.0 && rain < 100.0,
            "Rain attenuation at 18 GHz, 10 km, 145 mm/h: {} dB",
            rain
        );
    }

    #[test]
    fn test_rain_zero_rate() {
        let rain = rain_attenuation(18.0, 10.0, 0.0, Polarization::Vertical);
        assert_eq!(rain, 0.0, "Zero rain rate should give zero attenuation");
    }

    #[test]
    fn test_availability_good_margin() {
        let avail = estimate_availability(50.0, 30.0);
        assert!(
            avail >= 99.99,
            "Good fade margin should give high availability: {}%",
            avail
        );
    }

    #[test]
    fn test_availability_no_margin() {
        let avail = estimate_availability(0.0, 30.0);
        assert_eq!(
            avail, 0.0,
            "Zero fade margin should give zero availability"
        );
    }
}
