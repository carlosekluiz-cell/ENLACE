//! Shared types and constants for RF propagation calculations.
//!
//! Provides fundamental physical constants, unit conversion helpers,
//! and common enumerations used throughout the propagation models.

use serde::{Deserialize, Serialize};

/// Earth radius in meters (mean).
pub const EARTH_RADIUS_M: f64 = 6_371_000.0;

/// Speed of light in m/s.
pub const SPEED_OF_LIGHT: f64 = 299_792_458.0;

/// Pi constant.
pub const PI: f64 = std::f64::consts::PI;

/// Antenna polarization.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Polarization {
    Horizontal,
    Vertical,
}

/// Climate classification for propagation modeling.
///
/// These zones correspond to typical Brazilian climatic regions
/// and affect atmospheric refractivity and ducting parameters.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Climate {
    /// Amazon region — hot, humid, high refractivity.
    Equatorial,
    /// South/Southeast Brazil — warm, moderate humidity.
    ContinentalSubtropical,
    /// Coastal areas — oceanic influence.
    Maritime,
    /// Semi-arid Northeast — dry, low refractivity.
    Desert,
    /// Southern Brazil — cooler, temperate.
    ContinentalTemperate,
}

/// Propagation mode determined by path analysis.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PropagationMode {
    /// Clear line-of-sight path.
    LineOfSight,
    /// Signal diffracts over terrain obstacles.
    Diffraction,
    /// Signal scatters in the troposphere (long paths).
    Troposcatter,
    /// Combined/mixed propagation mechanisms.
    Combined,
}

/// Antenna radiation pattern type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AntennaPattern {
    /// Radiates equally in all horizontal directions.
    Omnidirectional,
    /// Directional pattern covering a sector (e.g., 120 degrees).
    Sectoral,
}

/// A geographic point specified by latitude and longitude in degrees.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct GeoPoint {
    /// Latitude in decimal degrees (positive = North).
    pub lat: f64,
    /// Longitude in decimal degrees (positive = East).
    pub lon: f64,
}

impl GeoPoint {
    /// Create a new geographic point.
    pub fn new(lat: f64, lon: f64) -> Self {
        Self { lat, lon }
    }
}

// ---------------------------------------------------------------------------
// Unit conversion helpers
// ---------------------------------------------------------------------------

/// Convert decibels to linear ratio.
pub fn db_to_linear(db: f64) -> f64 {
    10.0_f64.powf(db / 10.0)
}

/// Convert linear ratio to decibels.
pub fn linear_to_db(linear: f64) -> f64 {
    10.0 * linear.log10()
}

/// Convert dBm to watts.
pub fn dbm_to_watts(dbm: f64) -> f64 {
    10.0_f64.powf((dbm - 30.0) / 10.0)
}

/// Convert watts to dBm.
pub fn watts_to_dbm(w: f64) -> f64 {
    10.0 * w.log10() + 30.0
}

/// Convert MHz to Hz.
pub fn mhz_to_hz(mhz: f64) -> f64 {
    mhz * 1e6
}

/// Compute wavelength in meters from frequency in MHz.
pub fn wavelength_m(freq_mhz: f64) -> f64 {
    SPEED_OF_LIGHT / mhz_to_hz(freq_mhz)
}

/// Haversine distance between two geographic points in meters.
pub fn haversine_distance(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let lat1_rad = lat1.to_radians();
    let lat2_rad = lat2.to_radians();
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();

    let a = (dlat / 2.0).sin().powi(2)
        + lat1_rad.cos() * lat2_rad.cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();

    EARTH_RADIUS_M * c
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_db_conversions() {
        assert!((db_to_linear(0.0) - 1.0).abs() < 1e-10);
        assert!((db_to_linear(10.0) - 10.0).abs() < 1e-10);
        assert!((db_to_linear(20.0) - 100.0).abs() < 1e-8);
        assert!((linear_to_db(1.0) - 0.0).abs() < 1e-10);
        assert!((linear_to_db(10.0) - 10.0).abs() < 1e-10);
    }

    #[test]
    fn test_dbm_watt_conversions() {
        // 0 dBm = 1 mW = 0.001 W
        assert!((dbm_to_watts(0.0) - 0.001).abs() < 1e-10);
        // 30 dBm = 1 W
        assert!((dbm_to_watts(30.0) - 1.0).abs() < 1e-10);
        // 40 dBm = 10 W
        assert!((dbm_to_watts(40.0) - 10.0).abs() < 1e-8);
        // roundtrip
        assert!((watts_to_dbm(dbm_to_watts(37.0)) - 37.0).abs() < 1e-10);
    }

    #[test]
    fn test_wavelength() {
        // 300 MHz -> 1 m
        assert!((wavelength_m(300.0) - 1.0).abs() < 0.01);
        // 900 MHz -> ~0.333 m
        assert!((wavelength_m(900.0) - 0.333).abs() < 0.01);
    }

    #[test]
    fn test_haversine() {
        // 1 degree longitude at equator ~ 111.32 km
        let dist = haversine_distance(0.0, 0.0, 0.0, 1.0);
        assert!(
            (dist - 111_320.0).abs() < 500.0,
            "Equator 1-degree: {} m",
            dist
        );
    }
}
