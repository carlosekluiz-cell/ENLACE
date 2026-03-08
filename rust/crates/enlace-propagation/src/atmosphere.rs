//! Atmospheric absorption calculations.
//!
//! Simplified model based on ITU-R P.676 for atmospheric gaseous attenuation.
//! Accounts for oxygen and water vapor absorption as a function of frequency,
//! tailored for typical Brazilian tropical atmospheric conditions.

/// Compute atmospheric absorption in dB for a given frequency and path distance.
///
/// This is a simplified model suitable for engineering estimates:
/// - Below 10 GHz: essentially negligible (< 0.01 dB/km).
/// - 10-100 GHz: significant, dominated by oxygen (60 GHz peak) and
///   water vapor (22 GHz, 183 GHz peaks).
///
/// The model uses a lookup/interpolation approach with key frequencies.
///
/// # Parameters
/// - `freq_mhz`: frequency in MHz
/// - `distance_km`: path length in km
/// - `temperature_c`: ambient temperature in Celsius (default 25.0 for Brazil)
/// - `humidity_pct`: relative humidity percentage (default 70.0 for tropical)
///
/// # Returns
/// Total atmospheric absorption in dB.
pub fn atmospheric_absorption(
    freq_mhz: f64,
    distance_km: f64,
    temperature_c: f64,
    humidity_pct: f64,
) -> f64 {
    let specific_attenuation = specific_attenuation_db_per_km(freq_mhz, temperature_c, humidity_pct);
    specific_attenuation * distance_km
}

/// Compute atmospheric absorption with default Brazilian tropical parameters.
///
/// Uses temperature = 25 C and humidity = 70%.
pub fn atmospheric_absorption_brazil(freq_mhz: f64, distance_km: f64) -> f64 {
    atmospheric_absorption(freq_mhz, distance_km, 25.0, 70.0)
}

/// Compute specific attenuation in dB/km.
///
/// Simplified model based on ITU-R P.676-13 reference data for
/// standard atmosphere. The model interpolates between known
/// attenuation values at key frequencies.
fn specific_attenuation_db_per_km(freq_mhz: f64, temperature_c: f64, humidity_pct: f64) -> f64 {
    let freq_ghz = freq_mhz / 1000.0;

    // Temperature/humidity correction factor (simplified)
    // Higher humidity = more water vapor absorption
    // Higher temperature = slightly different line shapes
    let humidity_factor = humidity_pct / 50.0; // normalized to 50% reference
    let temp_factor = 1.0 + (temperature_c - 15.0) * 0.002; // small correction

    // Oxygen absorption (frequency-dependent)
    let oxygen = oxygen_specific_attenuation(freq_ghz);

    // Water vapor absorption (frequency-dependent, scaled by humidity)
    let water_vapor = water_vapor_specific_attenuation(freq_ghz) * humidity_factor;

    (oxygen + water_vapor) * temp_factor
}

/// Oxygen-specific attenuation in dB/km.
///
/// Key features:
/// - Complex of absorption lines around 60 GHz (~15 dB/km peak)
/// - Single line at 118.75 GHz
/// - Very low below 10 GHz
fn oxygen_specific_attenuation(freq_ghz: f64) -> f64 {
    if freq_ghz < 1.0 {
        // Sub-1 GHz: negligible
        0.0001 * freq_ghz
    } else if freq_ghz < 10.0 {
        // 1-10 GHz: very small, roughly linear increase
        0.001 + 0.0005 * (freq_ghz - 1.0)
    } else if freq_ghz < 50.0 {
        // 10-50 GHz: gradual increase approaching 60 GHz complex
        0.005 + 0.002 * (freq_ghz - 10.0)
    } else if freq_ghz < 70.0 {
        // 50-70 GHz: oxygen absorption complex (60 GHz peak)
        // Simplified Gaussian-like peak centered at 60 GHz
        let delta = (freq_ghz - 60.0) / 5.0;
        15.0 * (-delta * delta / 2.0).exp()
    } else if freq_ghz < 100.0 {
        // 70-100 GHz: decreasing after the peak
        0.1 + 0.05 * (100.0 - freq_ghz) / 30.0
    } else {
        // Above 100 GHz: moderate
        0.1
    }
}

/// Water-vapor-specific attenuation in dB/km (at 50% humidity reference).
///
/// Key features:
/// - Absorption line at 22.235 GHz (~0.2 dB/km at sea level)
/// - Stronger line at 183.31 GHz
fn water_vapor_specific_attenuation(freq_ghz: f64) -> f64 {
    if freq_ghz < 5.0 {
        // Below 5 GHz: negligible
        0.0001 * freq_ghz
    } else if freq_ghz < 35.0 {
        // 5-35 GHz: includes 22.235 GHz absorption peak
        let delta = (freq_ghz - 22.235) / 3.0;
        let peak_22 = 0.2 * (-delta * delta / 2.0).exp();
        0.001 + peak_22
    } else if freq_ghz < 100.0 {
        // 35-100 GHz: moderate water vapor contribution
        0.01 + 0.001 * (freq_ghz - 35.0)
    } else {
        // Above 100 GHz
        0.08
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_low_frequency_negligible() {
        // At 900 MHz over 10 km, absorption should be tiny
        let loss = atmospheric_absorption_brazil(900.0, 10.0);
        assert!(
            loss < 0.1,
            "900 MHz over 10 km should have negligible absorption: {} dB",
            loss
        );
    }

    #[test]
    fn test_microwave_moderate() {
        // At 18 GHz over 10 km, should see some absorption
        let loss = atmospheric_absorption_brazil(18_000.0, 10.0);
        assert!(
            loss > 0.1,
            "18 GHz over 10 km should have measurable absorption: {} dB",
            loss
        );
    }

    #[test]
    fn test_60ghz_peak() {
        // At 60 GHz, oxygen absorption peaks at ~15 dB/km
        let loss = atmospheric_absorption_brazil(60_000.0, 1.0);
        assert!(
            loss > 5.0,
            "60 GHz over 1 km should have high absorption: {} dB",
            loss
        );
    }

    #[test]
    fn test_zero_distance() {
        let loss = atmospheric_absorption_brazil(18_000.0, 0.0);
        assert!(
            loss.abs() < 1e-10,
            "Zero distance should give zero absorption"
        );
    }

    #[test]
    fn test_humidity_effect() {
        let dry = atmospheric_absorption(18_000.0, 10.0, 25.0, 30.0);
        let wet = atmospheric_absorption(18_000.0, 10.0, 25.0, 90.0);
        assert!(
            wet > dry,
            "Higher humidity should give more absorption: dry={}, wet={}",
            dry,
            wet
        );
    }
}
