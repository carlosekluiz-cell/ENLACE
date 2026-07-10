//! Antenna pattern library for realistic RF link modeling.
//!
//! Provides full antenna radiation pattern support including MSI Planet
//! ASCII file parsing, pattern interpolation, beamwidth computation, and
//! link budget integration with directional antennas.
//!
//! # Pattern Format
//!
//! Antenna patterns are stored as 360-element arrays of relative gain values
//! in dB (0 dB = maximum gain direction). Horizontal and vertical planes are
//! handled independently and combined for 3D gain estimation.
//!
//! # MSI Planet Format
//!
//! The industry-standard `.msi` file contains metadata lines (`NAME`, `MAKE`,
//! `FREQUENCY`, `GAIN`) followed by `HORIZONTAL 360` and `VERTICAL 360`
//! sections, each with 360 float values (one per line, integer degree steps).

use std::collections::HashMap;
use std::io::{BufRead, BufReader};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// AntennaPatternData
// ---------------------------------------------------------------------------

/// Full antenna radiation pattern with horizontal and vertical plane data.
///
/// Each plane is represented as 360 values at integer degree steps, where
/// index 0 corresponds to boresight (0 degrees) and values are relative
/// gain in dB (0 = maximum gain direction, negative values elsewhere).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AntennaPatternData {
    /// Model name / identifier (e.g., "APXVALL14_C-A20").
    pub name: String,
    /// Manufacturer name (e.g., "CommScope").
    pub make: String,
    /// Design center frequency in MHz.
    pub frequency_mhz: f64,
    /// Peak gain in dBi.
    pub gain_dbi: f64,
    /// Horizontal plane pattern: 360 relative gain values in dB (0 = max).
    pub horizontal: Vec<f64>,
    /// Vertical plane pattern: 360 relative gain values in dB (0 = max).
    pub vertical: Vec<f64>,
}

impl AntennaPatternData {
    /// Interpolated relative gain at an arbitrary azimuth and elevation angle.
    ///
    /// Both angles are in degrees. The azimuth is measured clockwise from
    /// boresight (0 = forward), elevation is measured from horizontal.
    /// Values are normalized into 0..360 before interpolation.
    ///
    /// Returns the combined relative gain in dB (always <= 0).
    pub fn gain_at(&self, azimuth_deg: f64, elevation_deg: f64) -> f64 {
        let h_gain = interpolate_pattern(&self.horizontal, azimuth_deg);
        let v_gain = interpolate_pattern(&self.vertical, elevation_deg);
        h_gain + v_gain
    }

    /// Effective gain (in dBi) toward a target, accounting for antenna mounting.
    ///
    /// # Parameters
    /// - `antenna_azimuth`: compass bearing the antenna boresight points to (degrees).
    /// - `antenna_tilt`: mechanical/electrical downtilt of the antenna (degrees).
    /// - `target_azimuth`: compass bearing from antenna to target (degrees).
    /// - `target_elevation`: elevation angle from antenna to target (degrees).
    ///
    /// # Returns
    /// Absolute gain in dBi toward the target.
    pub fn effective_gain(
        &self,
        antenna_azimuth: f64,
        antenna_tilt: f64,
        target_azimuth: f64,
        target_elevation: f64,
    ) -> f64 {
        let relative_az = target_azimuth - antenna_azimuth;
        let relative_el = target_elevation - antenna_tilt;
        self.gain_dbi + self.gain_at(relative_az, relative_el)
    }

    /// Horizontal -3 dB beamwidth in degrees.
    ///
    /// Scans outward from boresight (0 degrees) in both directions until the
    /// relative gain drops below -3 dB. The total beamwidth is the sum of
    /// the left and right half-power angles.
    pub fn h_beamwidth(&self) -> f64 {
        beamwidth_from_pattern(&self.horizontal)
    }

    /// Vertical -3 dB beamwidth in degrees.
    pub fn v_beamwidth(&self) -> f64 {
        beamwidth_from_pattern(&self.vertical)
    }

    /// Front-to-back ratio in dB.
    ///
    /// Defined as the difference between the boresight gain (0 dB by
    /// convention) and the gain at 180 degrees in the horizontal plane.
    pub fn front_to_back_db(&self) -> f64 {
        let back_gain = interpolate_pattern(&self.horizontal, 180.0);
        -back_gain // back_gain is negative, so F/B is positive
    }

    /// Convert antenna gain from dBd (relative to dipole) to dBi (relative
    /// to isotropic radiator).
    ///
    /// A half-wave dipole has 2.15 dBi gain, so dBi = dBd + 2.15.
    pub fn dbd_to_dbi(dbd: f64) -> f64 {
        dbd + 2.15
    }
}

// ---------------------------------------------------------------------------
// MSI file parser
// ---------------------------------------------------------------------------

/// Parse an antenna pattern from MSI Planet ASCII format.
///
/// The format consists of metadata header lines followed by horizontal and
/// vertical pattern data sections:
///
/// ```text
/// NAME MyAntenna
/// MAKE CommScope
/// FREQUENCY 1800
/// GAIN 18.0
/// HORIZONTAL 360
/// 0.0
/// -0.1
/// ...  (360 values)
/// VERTICAL 360
/// 0.0
/// -0.2
/// ...  (360 values)
/// ```
///
/// Lines not matching known keywords are ignored.
pub fn from_msi(reader: impl std::io::Read) -> Result<AntennaPatternData> {
    let buf = BufReader::new(reader);

    let mut name = String::new();
    let mut make = String::new();
    let mut frequency_mhz: f64 = 0.0;
    let mut gain_dbi: f64 = 0.0;
    let mut horizontal: Vec<f64> = Vec::new();
    let mut vertical: Vec<f64> = Vec::new();

    #[derive(PartialEq)]
    enum Section {
        Header,
        Horizontal,
        Vertical,
    }

    let mut section = Section::Header;
    let mut remaining = 0_usize;

    for line_result in buf.lines() {
        let line = line_result.context("reading MSI line")?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        // Check for section headers regardless of current state
        if trimmed.starts_with("HORIZONTAL") {
            let count = parse_section_count(trimmed, "HORIZONTAL")?;
            remaining = count;
            section = Section::Horizontal;
            continue;
        }
        if trimmed.starts_with("VERTICAL") {
            let count = parse_section_count(trimmed, "VERTICAL")?;
            remaining = count;
            section = Section::Vertical;
            continue;
        }

        match section {
            Section::Header => {
                if let Some(val) = trimmed.strip_prefix("NAME") {
                    name = val.trim().to_string();
                } else if let Some(val) = trimmed.strip_prefix("MAKE") {
                    make = val.trim().to_string();
                } else if let Some(val) = trimmed.strip_prefix("FREQUENCY") {
                    frequency_mhz = val
                        .trim()
                        .parse::<f64>()
                        .context("parsing FREQUENCY value")?;
                } else if let Some(val) = trimmed.strip_prefix("GAIN") {
                    gain_dbi = val
                        .trim()
                        .parse::<f64>()
                        .context("parsing GAIN value")?;
                }
                // Ignore unknown header lines
            }
            Section::Horizontal => {
                if remaining > 0 {
                    let val: f64 = trimmed
                        .parse()
                        .with_context(|| format!("parsing horizontal value: '{}'", trimmed))?;
                    horizontal.push(val);
                    remaining -= 1;
                    if remaining == 0 {
                        section = Section::Header;
                    }
                }
            }
            Section::Vertical => {
                if remaining > 0 {
                    let val: f64 = trimmed
                        .parse()
                        .with_context(|| format!("parsing vertical value: '{}'", trimmed))?;
                    vertical.push(val);
                    remaining -= 1;
                    if remaining == 0 {
                        section = Section::Header;
                    }
                }
            }
        }
    }

    anyhow::ensure!(
        horizontal.len() == 360,
        "expected 360 horizontal values, got {}",
        horizontal.len()
    );
    anyhow::ensure!(
        vertical.len() == 360,
        "expected 360 vertical values, got {}",
        vertical.len()
    );

    Ok(AntennaPatternData {
        name,
        make,
        frequency_mhz,
        gain_dbi,
        horizontal,
        vertical,
    })
}

/// Extract the element count from a section header like "HORIZONTAL 360".
fn parse_section_count(line: &str, keyword: &str) -> Result<usize> {
    let rest = line
        .strip_prefix(keyword)
        .unwrap_or("")
        .trim();
    let count: usize = rest
        .parse()
        .with_context(|| format!("parsing {} count from '{}'", keyword, line))?;
    Ok(count)
}

// ---------------------------------------------------------------------------
// Pattern interpolation helpers
// ---------------------------------------------------------------------------

/// Linearly interpolate a 360-element pattern at an arbitrary angle.
///
/// The angle is normalized to the 0..360 range. Values between integer
/// degrees are linearly interpolated from the two nearest entries.
fn interpolate_pattern(pattern: &[f64], angle_deg: f64) -> f64 {
    if pattern.is_empty() {
        return 0.0;
    }
    let len = pattern.len() as f64;
    // Normalize to [0, 360)
    let mut a = angle_deg % 360.0;
    if a < 0.0 {
        a += 360.0;
    }

    let idx_f = a * (len / 360.0);
    let idx_lo = (idx_f.floor() as usize) % pattern.len();
    let idx_hi = (idx_lo + 1) % pattern.len();
    let frac = idx_f - idx_f.floor();

    pattern[idx_lo] * (1.0 - frac) + pattern[idx_hi] * frac
}

/// Compute the -3 dB beamwidth from a 360-element pattern.
///
/// Scans outward from 0 degrees (boresight) in both the positive and
/// negative direction until the relative gain falls below -3 dB.
fn beamwidth_from_pattern(pattern: &[f64]) -> f64 {
    if pattern.is_empty() {
        return 360.0;
    }
    let threshold = -3.0;
    let mut left = 0.0_f64;
    let mut right = 0.0_f64;

    // Scan right (increasing angle)
    for deg in 1..=180 {
        let val = interpolate_pattern(pattern, deg as f64);
        if val < threshold {
            // Interpolate between deg-1 and deg for more precision
            let prev = interpolate_pattern(pattern, (deg - 1) as f64);
            if (val - prev).abs() > 1e-12 {
                let frac = (threshold - prev) / (val - prev);
                right = (deg - 1) as f64 + frac;
            } else {
                right = deg as f64;
            }
            break;
        }
        if deg == 180 {
            right = 180.0;
        }
    }

    // Scan left (decreasing angle, i.e., 359, 358, ...)
    for deg in 1..=180 {
        let val = interpolate_pattern(pattern, 360.0 - deg as f64);
        if val < threshold {
            let prev = interpolate_pattern(pattern, 360.0 - (deg - 1) as f64);
            if (val - prev).abs() > 1e-12 {
                let frac = (threshold - prev) / (val - prev);
                left = (deg - 1) as f64 + frac;
            } else {
                left = deg as f64;
            }
            break;
        }
        if deg == 180 {
            left = 180.0;
        }
    }

    left + right
}

// ---------------------------------------------------------------------------
// AntennaDatabase
// ---------------------------------------------------------------------------

/// In-memory database of antenna radiation patterns.
///
/// Patterns are keyed by a normalized string: `"{make}/{name}/{freq_mhz}"`
/// in lowercase. The database supports loading entire directories of `.msi`
/// files and both exact and fuzzy lookups.
pub struct AntennaDatabase {
    patterns: HashMap<String, AntennaPatternData>,
}

impl AntennaDatabase {
    /// Create an empty antenna database.
    pub fn new() -> Self {
        Self {
            patterns: HashMap::new(),
        }
    }

    /// Insert a pattern into the database, keyed by make/name/frequency.
    pub fn insert(&mut self, pattern: AntennaPatternData) {
        let key = make_key(&pattern.make, &pattern.name, pattern.frequency_mhz);
        self.patterns.insert(key, pattern);
    }

    /// Load all `.msi` files from a directory. Returns the number of
    /// patterns successfully loaded.
    pub fn load_dir(&mut self, path: &std::path::Path) -> Result<usize> {
        let mut count = 0usize;
        let entries = std::fs::read_dir(path)
            .with_context(|| format!("reading antenna directory: {}", path.display()))?;

        for entry in entries {
            let entry = entry?;
            let file_path = entry.path();
            if file_path
                .extension()
                .map_or(false, |ext| ext.eq_ignore_ascii_case("msi"))
            {
                let file = std::fs::File::open(&file_path)
                    .with_context(|| format!("opening {}", file_path.display()))?;
                match from_msi(file) {
                    Ok(pattern) => {
                        self.insert(pattern);
                        count += 1;
                    }
                    Err(e) => {
                        tracing::warn!(
                            "skipping {}: {}",
                            file_path.display(),
                            e
                        );
                    }
                }
            }
        }
        Ok(count)
    }

    /// Find a pattern by make, model name, and frequency.
    ///
    /// Tries exact key match first, then falls back to a fuzzy search:
    /// case-insensitive substring match on make and model, with frequency
    /// within 10% of the target.
    pub fn find(&self, make: &str, model: &str, freq_mhz: f64) -> Option<&AntennaPatternData> {
        // Exact match
        let key = make_key(make, model, freq_mhz);
        if let Some(p) = self.patterns.get(&key) {
            return Some(p);
        }

        // Fuzzy match
        let make_lower = make.to_lowercase();
        let model_lower = model.to_lowercase();
        let freq_lo = freq_mhz * 0.9;
        let freq_hi = freq_mhz * 1.1;

        self.patterns.values().find(|p| {
            let p_make = p.make.to_lowercase();
            let p_name = p.name.to_lowercase();
            p_make.contains(&make_lower)
                && p_name.contains(&model_lower)
                && p.frequency_mhz >= freq_lo
                && p.frequency_mhz <= freq_hi
        })
    }

    /// Create a synthetic omnidirectional antenna pattern.
    ///
    /// All 360 horizontal and vertical values are 0 dB (uniform radiation).
    pub fn omnidirectional(gain_dbi: f64) -> AntennaPatternData {
        AntennaPatternData {
            name: "Omnidirectional".to_string(),
            make: "Synthetic".to_string(),
            frequency_mhz: 0.0,
            gain_dbi,
            horizontal: vec![0.0; 360],
            vertical: vec![0.0; 360],
        }
    }

    /// Create a synthetic 120-degree sector antenna pattern.
    ///
    /// Horizontal pattern:
    /// - Linear rolloff from 0 dB at boresight to -3 dB at +/-60 deg
    /// - Steeper rolloff from -3 dB at +/-60 deg to -20 dB at +/-120 deg
    /// - -20 dB from +/-120 deg through 180 deg (back lobe)
    ///
    /// This produces a -3 dB beamwidth of 120 degrees, matching the
    /// industry-standard definition of a 120-degree sector antenna.
    ///
    /// Vertical pattern: uniform 0 dB.
    pub fn sectoral_120(gain_dbi: f64) -> AntennaPatternData {
        let mut horizontal = vec![0.0_f64; 360];

        for deg in 0..360 {
            // Map to [-180, 180) relative to boresight
            let angle = if deg <= 180 { deg as f64 } else { deg as f64 - 360.0 };
            let abs_angle = angle.abs();

            horizontal[deg] = if abs_angle <= 60.0 {
                // Linear rolloff: 0 dB at 0 deg -> -3 dB at 60 deg
                -3.0 * abs_angle / 60.0
            } else if abs_angle <= 120.0 {
                // Steeper rolloff: -3 dB at 60 deg -> -20 dB at 120 deg
                -3.0 - 17.0 * (abs_angle - 60.0) / 60.0
            } else {
                -20.0
            };
        }

        AntennaPatternData {
            name: "Sectoral120".to_string(),
            make: "Synthetic".to_string(),
            frequency_mhz: 0.0,
            gain_dbi,
            horizontal,
            vertical: vec![0.0; 360],
        }
    }
}

impl Default for AntennaDatabase {
    fn default() -> Self {
        Self::new()
    }
}

/// Build the normalized HashMap key for an antenna pattern.
fn make_key(make: &str, name: &str, freq_mhz: f64) -> String {
    format!("{}/{}/{}", make, name, freq_mhz).to_lowercase()
}

// ---------------------------------------------------------------------------
// Link budget integration
// ---------------------------------------------------------------------------

/// Compute received power using full antenna pattern data.
///
/// This function accounts for the directional gain of both the transmitter
/// and receiver antennas at the specific angles involved in the link.
///
/// # Formula
///
/// ```text
/// rx_power = tx_power + tx_effective_gain + rx_effective_gain - path_loss
/// ```
///
/// The receiver sees the reverse azimuth (offset by 180 degrees) and the
/// negated elevation relative to the transmitter direction.
///
/// # Parameters
/// - `tx_power_dbm`: transmitter output power in dBm.
/// - `tx_pattern`: transmitter antenna pattern.
/// - `tx_azimuth`: compass bearing of the TX antenna boresight (degrees).
/// - `tx_tilt`: mechanical/electrical tilt of the TX antenna (degrees).
/// - `rx_pattern`: receiver antenna pattern.
/// - `rx_azimuth`: compass bearing of the RX antenna boresight (degrees).
/// - `rx_tilt`: mechanical/electrical tilt of the RX antenna (degrees).
/// - `target_azimuth_from_tx`: compass bearing from TX toward RX (degrees).
/// - `target_elevation_from_tx`: elevation angle from TX toward RX (degrees).
/// - `path_loss_db`: total propagation path loss in dB (positive value).
///
/// # Returns
/// Received signal power in dBm.
pub fn link_budget_with_antenna(
    tx_power_dbm: f64,
    tx_pattern: &AntennaPatternData,
    tx_azimuth: f64,
    tx_tilt: f64,
    rx_pattern: &AntennaPatternData,
    rx_azimuth: f64,
    rx_tilt: f64,
    target_azimuth_from_tx: f64,
    target_elevation_from_tx: f64,
    path_loss_db: f64,
) -> f64 {
    let tx_gain = tx_pattern.effective_gain(
        tx_azimuth,
        tx_tilt,
        target_azimuth_from_tx,
        target_elevation_from_tx,
    );

    // RX sees the reverse direction
    let reverse_azimuth = target_azimuth_from_tx + 180.0;
    let reverse_elevation = -target_elevation_from_tx;

    let rx_gain = rx_pattern.effective_gain(rx_azimuth, rx_tilt, reverse_azimuth, reverse_elevation);

    tx_power_dbm + tx_gain + rx_gain - path_loss_db
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Minimal valid MSI file for testing the parser.
    const SAMPLE_MSI: &str = "\
NAME TestSector
MAKE TestMfg
FREQUENCY 1800
GAIN 17.5
HORIZONTAL 360
0.0
-0.1
-0.4
-0.9
-1.6
-2.5
-3.6
-4.9
-6.4
-8.1
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-8.1
-6.4
-4.9
-3.6
-2.5
-1.6
-0.9
-0.4
-0.1
VERTICAL 360
0.0
-0.1
-0.4
-0.9
-1.6
-2.5
-3.6
-4.9
-6.4
-8.1
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-20.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-10.0
-8.1
-6.4
-4.9
-3.6
-2.5
-1.6
-0.9
-0.4
-0.1
";

    #[test]
    fn test_parse_msi() {
        let pattern = from_msi(SAMPLE_MSI.as_bytes()).expect("parse MSI");
        assert_eq!(pattern.name, "TestSector");
        assert_eq!(pattern.make, "TestMfg");
        assert!((pattern.frequency_mhz - 1800.0).abs() < 1e-6);
        assert!((pattern.gain_dbi - 17.5).abs() < 1e-6);
        assert_eq!(pattern.horizontal.len(), 360);
        assert_eq!(pattern.vertical.len(), 360);
        // Boresight should be 0 dB
        assert!((pattern.horizontal[0] - 0.0).abs() < 1e-6);
    }

    #[test]
    fn test_gain_at_boresight() {
        let pattern = from_msi(SAMPLE_MSI.as_bytes()).unwrap();
        let gain = pattern.gain_at(0.0, 0.0);
        assert!(
            gain.abs() < 1e-6,
            "boresight relative gain should be 0 dB, got {}",
            gain
        );
    }

    #[test]
    fn test_gain_at_180_nonzero() {
        let pattern = from_msi(SAMPLE_MSI.as_bytes()).unwrap();
        let gain = pattern.gain_at(180.0, 0.0);
        assert!(
            gain < -1.0,
            "gain at 180 deg should be significantly negative for directional pattern, got {}",
            gain
        );
    }

    #[test]
    fn test_sectoral_120_beamwidth() {
        let sector = AntennaDatabase::sectoral_120(15.0);
        let bw = sector.h_beamwidth();
        assert!(
            (bw - 120.0).abs() < 5.0,
            "120-deg sector H beamwidth should be ~120 deg, got {}",
            bw
        );
    }

    #[test]
    fn test_omnidirectional_uniform() {
        let omni = AntennaDatabase::omnidirectional(6.0);
        for deg in 0..360 {
            let gain = omni.gain_at(deg as f64, 0.0);
            assert!(
                gain.abs() < 1e-6,
                "omni gain at {} deg should be 0 dB, got {}",
                deg,
                gain
            );
        }
    }

    #[test]
    fn test_front_to_back_ratio() {
        let sector = AntennaDatabase::sectoral_120(15.0);
        let ftb = sector.front_to_back_db();
        assert!(
            ftb > 0.0,
            "front-to-back ratio should be positive for directional antenna, got {}",
            ftb
        );
        // For the 120-deg synthetic sector, back lobe is -20 dB
        assert!(
            (ftb - 20.0).abs() < 1.0,
            "expected F/B ~20 dB, got {}",
            ftb
        );
    }

    #[test]
    fn test_link_budget_with_antenna() {
        let omni = AntennaDatabase::omnidirectional(0.0);
        let sector = AntennaDatabase::sectoral_120(15.0);

        let path_loss = 100.0;
        let tx_power = 30.0; // 30 dBm = 1 W

        // With omni (0 dBi) on both ends: rx = 30 + 0 + 0 - 100 = -70 dBm
        let rx_omni = link_budget_with_antenna(
            tx_power, &omni, 0.0, 0.0, &omni, 180.0, 0.0, 0.0, 0.0, path_loss,
        );
        assert!(
            (rx_omni - (-70.0)).abs() < 0.1,
            "omni link budget: expected -70 dBm, got {}",
            rx_omni
        );

        // With sector TX on boresight + omni RX: rx = 30 + 15 + 0 - 100 = -55 dBm
        let rx_sector = link_budget_with_antenna(
            tx_power, &sector, 0.0, 0.0, &omni, 180.0, 0.0, 0.0, 0.0, path_loss,
        );
        assert!(
            (rx_sector - (-55.0)).abs() < 0.1,
            "sector link budget: expected -55 dBm, got {}",
            rx_sector
        );

        // The difference should be the TX antenna gain
        assert!(
            ((rx_sector - rx_omni) - 15.0).abs() < 0.1,
            "gain difference should be 15 dB, got {}",
            rx_sector - rx_omni
        );
    }

    #[test]
    fn test_dbd_to_dbi() {
        let dbi = AntennaPatternData::dbd_to_dbi(0.0);
        assert!(
            (dbi - 2.15).abs() < 1e-10,
            "0 dBd should equal 2.15 dBi, got {}",
            dbi
        );
    }
}
