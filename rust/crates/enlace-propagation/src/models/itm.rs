//! Longley-Rice Irregular Terrain Model (ITM) — simplified implementation.
//!
//! The ITM is a general-purpose radio propagation model that predicts
//! median signal strength as a function of terrain, distance, frequency,
//! and other parameters. It operates in three modes:
//!
//! - **Line-of-Sight (LOS)**: Clear path with Fresnel zone clearance.
//! - **Diffraction**: Signal bends over terrain obstacles.
//! - **Troposcatter**: Signal scatters in the troposphere (long paths).
//!
//! This implementation uses terrain profiles from `enlace-terrain` and
//! applies a simplified but functional version of the ITM suitable for
//! engineering coverage estimates.

use crate::common::{Climate, Polarization, PropagationMode};
use crate::diffraction::deygout_diffraction_loss;
use crate::fresnel::min_fresnel_clearance;
use crate::models::fspl::FsplModel;

/// Parameters for the ITM calculation.
#[derive(Debug, Clone)]
pub struct ItmParams {
    /// Carrier frequency in MHz.
    pub frequency_mhz: f64,
    /// Transmitter antenna height above ground in meters.
    pub tx_height_m: f64,
    /// Receiver antenna height above ground in meters.
    pub rx_height_m: f64,
    /// Antenna polarization.
    pub polarization: Polarization,
    /// Surface refractivity in N-units (default 360 for tropical Brazil).
    pub surface_refractivity: f64,
    /// Ground conductivity in S/m.
    pub ground_conductivity: f64,
    /// Ground relative dielectric constant.
    pub ground_dielectric: f64,
    /// Climate zone.
    pub climate: Climate,
    /// Time percentage (0.01 to 0.99).
    pub time_pct: f64,
    /// Location percentage (0.01 to 0.99).
    pub location_pct: f64,
    /// Situation percentage (0.01 to 0.99).
    pub situation_pct: f64,
}

impl Default for ItmParams {
    /// Default parameters for Brazilian tropical conditions.
    fn default() -> Self {
        Self {
            frequency_mhz: 900.0,
            tx_height_m: 30.0,
            rx_height_m: 1.5,
            polarization: Polarization::Vertical,
            surface_refractivity: 360.0,  // Tropical Brazil
            ground_conductivity: 0.005,   // Average ground
            ground_dielectric: 15.0,      // Average ground
            climate: Climate::Equatorial,
            time_pct: 0.50,
            location_pct: 0.50,
            situation_pct: 0.50,
        }
    }
}

/// Result of an ITM calculation.
#[derive(Debug, Clone)]
pub struct ItmResult {
    /// Total path loss in dB.
    pub path_loss_db: f64,
    /// Determined propagation mode.
    pub mode: PropagationMode,
    /// Variability in dB (standard deviation).
    pub variability_db: f64,
    /// Warnings or notes about the calculation.
    pub warnings: Vec<String>,
}

/// Compute path loss using the simplified ITM model.
///
/// # Parameters
/// - `profile`: terrain profile as (distance_m, elevation_m) pairs
/// - `params`: ITM calculation parameters
///
/// # Algorithm
/// 1. Compute Fresnel zone clearance at each terrain point
/// 2. Classify propagation mode based on clearance:
///    - Clearance >= 0.6: LOS (FSPL + minor corrections)
///    - Clearance 0.0-0.6: Partial diffraction
///    - Clearance < 0.0: Full diffraction (Deygout method)
/// 3. For troposcatter (>100 km): simplified troposcatter formula
/// 4. Apply atmospheric and climate corrections
pub fn itm_path_loss(profile: &[(f64, f64)], params: &ItmParams) -> ItmResult {
    let mut warnings = Vec::new();

    if profile.len() < 2 {
        return ItmResult {
            path_loss_db: 0.0,
            mode: PropagationMode::LineOfSight,
            variability_db: 0.0,
            warnings: vec!["Profile too short for ITM analysis".to_string()],
        };
    }

    let total_distance = profile.last().unwrap().0 - profile.first().unwrap().0;
    if total_distance <= 0.0 {
        return ItmResult {
            path_loss_db: 0.0,
            mode: PropagationMode::LineOfSight,
            variability_db: 0.0,
            warnings: vec!["Zero or negative path distance".to_string()],
        };
    }

    let distance_km = total_distance / 1000.0;

    // Step 1: Compute Fresnel zone clearance
    let clearance_ratio = min_fresnel_clearance(
        profile,
        params.tx_height_m,
        params.rx_height_m,
        params.frequency_mhz,
    );

    // Step 2: Compute free-space path loss (baseline)
    let fspl = FsplModel::compute(params.frequency_mhz, total_distance);

    // Step 3: Determine mode and compute additional losses
    let (mode, additional_loss) = if distance_km > 100.0 {
        // Troposcatter regime for very long paths
        let tropo_loss = troposcatter_loss(
            params.frequency_mhz,
            total_distance,
            params.tx_height_m,
            params.rx_height_m,
            params.surface_refractivity,
        );
        (PropagationMode::Troposcatter, tropo_loss)
    } else if clearance_ratio >= 0.6 {
        // Line-of-sight: FSPL + minor corrections
        let ground_reflection_loss = ground_reflection_correction(
            params.frequency_mhz,
            total_distance,
            params.tx_height_m,
            params.rx_height_m,
            params.ground_conductivity,
        );
        (PropagationMode::LineOfSight, ground_reflection_loss)
    } else {
        // Diffraction mode
        let diff_loss = deygout_diffraction_loss(
            profile,
            params.tx_height_m,
            params.rx_height_m,
            params.frequency_mhz,
        );
        (PropagationMode::Diffraction, diff_loss)
    };

    // Step 4: Atmospheric absorption correction
    let atmos_loss = crate::atmosphere::atmospheric_absorption_brazil(
        params.frequency_mhz,
        distance_km,
    );

    // Step 5: Climate correction
    let climate_correction = climate_variability_correction(params.climate);

    // Step 6: Variability based on percentages
    let variability = compute_variability(
        params.time_pct,
        params.location_pct,
        params.situation_pct,
        &mode,
    );

    // Frequency validation
    if params.frequency_mhz < 20.0 || params.frequency_mhz > 40_000.0 {
        warnings.push(format!(
            "Frequency {} MHz may be outside ITM reliable range (20-40000 MHz)",
            params.frequency_mhz
        ));
    }

    let total_loss = fspl + additional_loss + atmos_loss + climate_correction;

    ItmResult {
        path_loss_db: total_loss,
        mode,
        variability_db: variability,
        warnings,
    }
}

/// Simplified troposcatter loss.
///
/// For paths exceeding ~100 km, tropospheric scatter becomes the dominant
/// propagation mechanism. Loss increases rapidly with distance.
fn troposcatter_loss(
    freq_mhz: f64,
    distance_m: f64,
    tx_height_m: f64,
    rx_height_m: f64,
    surface_refractivity: f64,
) -> f64 {
    let distance_km = distance_m / 1000.0;
    let freq_ghz = freq_mhz / 1000.0;

    // Simplified troposcatter formula based on NBS Tech Note 101
    // Additional loss beyond FSPL:
    // L_tropo ≈ 30*log10(f_ghz) + 30*log10(d_km) + N_correction - height_gain
    let freq_term = 30.0 * freq_ghz.max(0.001).log10();
    let dist_term = 30.0 * distance_km.max(1.0).log10();

    // Refractivity correction (higher N = better troposcatter)
    let n_correction = -0.1 * (surface_refractivity - 301.0);

    // Height gain (taller antennas improve troposcatter coupling)
    let height_gain = 5.0 * (tx_height_m * rx_height_m).max(1.0).log10();

    let loss = freq_term + dist_term + n_correction - height_gain;
    loss.max(0.0)
}

/// Ground reflection correction for LOS paths.
///
/// Accounts for multipath interference from ground-reflected signal.
/// Simplified model based on two-ray approximation.
fn ground_reflection_correction(
    _freq_mhz: f64,
    distance_m: f64,
    _tx_height_m: f64,
    _rx_height_m: f64,
    ground_conductivity: f64,
) -> f64 {
    // Two-ray model correction: at certain distances, ground reflection
    // can cause constructive or destructive interference.
    // Breakpoint distance: d_bp = 4 * h_tx * h_rx / lambda
    // Beyond the breakpoint, loss follows 40*log10(d) instead of 20*log10(d).
    // We use a simplified average correction.

    let distance_km = distance_m / 1000.0;

    // Conductivity-based ground loss (higher conductivity = more reflection)
    let conductivity_factor = (ground_conductivity / 0.005).min(2.0).max(0.5);

    // Average ground reflection adds 2-6 dB depending on conditions
    let correction = 2.0 * conductivity_factor * (distance_km / 10.0).min(1.0);

    correction.max(0.0)
}

/// Climate variability correction in dB.
///
/// Different climate zones produce different atmospheric conditions
/// that affect long-term signal variability.
fn climate_variability_correction(climate: Climate) -> f64 {
    match climate {
        Climate::Equatorial => 2.0,              // Tropical, high humidity
        Climate::ContinentalSubtropical => 1.0,  // Moderate
        Climate::Maritime => 1.5,                // Oceanic, moderate
        Climate::Desert => 0.5,                  // Dry, stable
        Climate::ContinentalTemperate => 0.8,    // Cool, moderate
    }
}

/// Compute location/time/situation variability.
fn compute_variability(
    time_pct: f64,
    location_pct: f64,
    _situation_pct: f64,
    mode: &PropagationMode,
) -> f64 {
    // Base variability depends on propagation mode
    let base_var = match mode {
        PropagationMode::LineOfSight => 4.0,
        PropagationMode::Diffraction => 8.0,
        PropagationMode::Troposcatter => 12.0,
        PropagationMode::Combined => 6.0,
    };

    // Adjust for the requested reliability percentages
    // Using simplified inverse normal approximation
    let time_factor = if time_pct > 0.5 {
        1.0 + 2.0 * (time_pct - 0.5)
    } else {
        1.0 - 2.0 * (0.5 - time_pct)
    };

    let location_factor = if location_pct > 0.5 {
        1.0 + 1.5 * (location_pct - 0.5)
    } else {
        1.0 - 1.5 * (0.5 - location_pct)
    };

    base_var * time_factor.max(0.5) * location_factor.max(0.5)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_itm_flat_los() {
        // Flat terrain with tall antennas for clear Fresnel zone
        // At 900 MHz over 1 km, Fresnel radius at midpoint ≈ 9.1 m
        // With 50m TX and 50m RX, clearance at midpoint = 50m >> 9.1m
        let profile: Vec<(f64, f64)> = (0..100)
            .map(|i| (i as f64 * 10.0, 0.0))
            .collect();

        let params = ItmParams {
            frequency_mhz: 900.0,
            tx_height_m: 50.0,
            rx_height_m: 50.0,
            ..ItmParams::default()
        };

        let result = itm_path_loss(&profile, &params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);

        // Should be close to FSPL + minor corrections
        let fspl = FsplModel::compute(900.0, 990.0);
        assert!(
            (result.path_loss_db - fspl).abs() < 15.0,
            "ITM LOS should be near FSPL: ITM={} vs FSPL={}",
            result.path_loss_db,
            fspl
        );
    }

    #[test]
    fn test_itm_obstructed_diffraction() {
        // Terrain with a large hill in the middle
        let mut profile: Vec<(f64, f64)> = (0..100)
            .map(|i| (i as f64 * 100.0, 0.0))
            .collect();
        // Add a 200m hill at the midpoint
        for i in 45..55 {
            profile[i] = (i as f64 * 100.0, 200.0);
        }

        let params = ItmParams {
            frequency_mhz: 900.0,
            tx_height_m: 30.0,
            rx_height_m: 1.5,
            ..ItmParams::default()
        };

        let result = itm_path_loss(&profile, &params);
        assert_eq!(
            result.mode,
            PropagationMode::Diffraction,
            "Should detect diffraction mode"
        );

        // Diffraction loss should be higher than FSPL
        let fspl = FsplModel::compute(900.0, 9900.0);
        assert!(
            result.path_loss_db > fspl,
            "Diffraction loss ({}) should exceed FSPL ({})",
            result.path_loss_db,
            fspl
        );
    }

    #[test]
    fn test_itm_default_params() {
        let params = ItmParams::default();
        assert_eq!(params.frequency_mhz, 900.0);
        assert_eq!(params.surface_refractivity, 360.0);
        assert_eq!(params.climate, Climate::Equatorial);
    }

    #[test]
    fn test_itm_short_profile() {
        let profile = vec![(0.0, 0.0)];
        let params = ItmParams::default();
        let result = itm_path_loss(&profile, &params);
        assert!(!result.warnings.is_empty());
    }
}
