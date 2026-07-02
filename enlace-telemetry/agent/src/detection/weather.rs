// SPDX-License-Identifier: Apache-2.0
// Weather-Correlated Degradation Detector
//
// Detects patterns in ONT signal degradation that correlate with weather
// conditions, even without direct weather data. By analyzing groups of
// ONTs at similar distances on the same PON port, we can identify:
//
//   1. NIGHTTIME CONDENSATION — Rx power worse at night than day, indicating
//      moisture ingress into a splice enclosure or aerial cable joint.
//
//   2. PERIODIC RAIN INGRESS — Coordinated degradation episodes lasting
//      2-8 hours then full recovery, matching rainfall patterns.
//
//   3. THERMAL EXPANSION — Higher Rx variance during afternoon heat vs
//      stable nighttime readings, indicating aerial cable thermal stress.
//
// All patterns require 3+ ONTs at similar distance (within 100m) on the
// same port to confirm it's an infrastructure issue, not a single ONT fault.

use std::collections::HashMap;
use chrono::{DateTime, Timelike, Utc};
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// A detected weather-correlated degradation pattern.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherCorrelation {
    pub ont_serials: Vec<String>,
    pub port: String,
    pub distance_range: (u32, u32),
    pub pattern: WeatherPattern,
    pub correlation_strength: f64,
    pub description: String,
}

/// Type of weather-correlated degradation pattern.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum WeatherPattern {
    /// Rx power consistently worse at night (22:00-06:00) than day (10:00-18:00).
    NighttimeCondensation,
    /// Coordinated degradation episodes lasting 2-8 hours then recovery.
    PeriodicRainIngress,
    /// Higher Rx variance during afternoon heat vs stable nighttime readings.
    ThermalExpansion,
}

impl std::fmt::Display for WeatherPattern {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NighttimeCondensation => write!(f, "nighttime_condensation"),
            Self::PeriodicRainIngress => write!(f, "periodic_rain_ingress"),
            Self::ThermalExpansion => write!(f, "thermal_expansion"),
        }
    }
}

/// Minimum number of ONTs in a distance group to flag a weather pattern.
const MIN_GROUP_SIZE: usize = 3;

/// Maximum distance difference (meters) to group ONTs together.
const DISTANCE_GROUP_TOLERANCE: u32 = 100;

/// Minimum day/night Rx power difference (dBm) to flag condensation.
const MIN_CONDENSATION_DELTA_DBM: f64 = 0.15;

/// Minimum degradation (dBm) from baseline to flag a rain episode.
const MIN_RAIN_DEGRADATION_DBM: f64 = 0.3;

/// Maximum recovery tolerance (dBm) — must recover to within this of baseline.
const RAIN_RECOVERY_TOLERANCE_DBM: f64 = 0.1;

/// Minimum number of rain episodes to flag the pattern.
const MIN_RAIN_EPISODES: usize = 2;

/// Minimum afternoon/night stdev ratio to flag thermal expansion.
const MIN_THERMAL_STDEV_RATIO: f64 = 2.0;

/// A group of ONTs at similar distance on the same port.
struct DistanceGroup {
    serials: Vec<String>,
    port: String,
    min_distance: u32,
    max_distance: u32,
}

/// Detect weather-correlated degradation patterns from ONT readings.
///
/// Groups ONTs by port and similar distance, then checks each group for
/// nighttime condensation, periodic rain ingress, and thermal expansion
/// patterns. Only flags patterns affecting 3+ ONTs to confirm infrastructure
/// issues rather than single-ONT faults.
pub fn detect_weather_correlation(readings: &[OntReading]) -> Vec<WeatherCorrelation> {
    let groups = build_distance_groups(readings);
    let mut results = Vec::new();

    // Group readings by serial for quick lookup
    let mut by_serial: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial
            .entry(r.serial_number.clone())
            .or_default()
            .push(r);
    }

    // Sort each serial's readings by timestamp
    for readings_vec in by_serial.values_mut() {
        readings_vec.sort_by_key(|r| r.timestamp);
    }

    for group in &groups {
        // Check for nighttime condensation
        if let Some(correlation) = check_condensation(group, &by_serial) {
            results.push(correlation);
        }

        // Check for periodic rain ingress
        if let Some(correlation) = check_rain_ingress(group, &by_serial) {
            results.push(correlation);
        }

        // Check for thermal expansion
        if let Some(correlation) = check_thermal_expansion(group, &by_serial) {
            results.push(correlation);
        }
    }

    // Sort by correlation strength descending
    results.sort_by(|a, b| {
        b.correlation_strength
            .partial_cmp(&a.correlation_strength)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Build groups of ONTs at similar distance on the same port.
fn build_distance_groups(readings: &[OntReading]) -> Vec<DistanceGroup> {
    // Collect (port, serial, distance) tuples
    let mut ont_distances: HashMap<(String, String), Vec<u32>> = HashMap::new();
    for r in readings {
        if let Some(dist) = r.distance_meters {
            ont_distances
                .entry((r.pon_port.clone(), r.serial_number.clone()))
                .or_default()
                .push(dist);
        }
    }

    // Average distance per ONT per port
    let mut port_onts: HashMap<String, Vec<(String, u32)>> = HashMap::new();
    for ((port, serial), distances) in &ont_distances {
        let avg_dist = (distances.iter().sum::<u32>() as f64 / distances.len() as f64) as u32;
        port_onts
            .entry(port.clone())
            .or_default()
            .push((serial.clone(), avg_dist));
    }

    let mut groups = Vec::new();

    for (port, mut onts) in port_onts {
        onts.sort_by_key(|(_, d)| *d);

        // Greedy grouping: cluster ONTs within DISTANCE_GROUP_TOLERANCE of each other
        let mut i = 0;
        while i < onts.len() {
            let base_dist = onts[i].1;
            let mut group_serials = vec![onts[i].0.clone()];
            let mut max_dist = base_dist;
            let mut j = i + 1;

            while j < onts.len() && onts[j].1 - base_dist <= DISTANCE_GROUP_TOLERANCE {
                group_serials.push(onts[j].0.clone());
                max_dist = onts[j].1;
                j += 1;
            }

            if group_serials.len() >= MIN_GROUP_SIZE {
                groups.push(DistanceGroup {
                    serials: group_serials,
                    port: port.clone(),
                    min_distance: base_dist,
                    max_distance: max_dist,
                });
            }

            i = j.max(i + 1);
        }
    }

    groups
}

/// Check for nighttime condensation pattern.
/// Night (22:00-06:00) Rx consistently worse than day (10:00-18:00).
fn check_condensation(
    group: &DistanceGroup,
    by_serial: &HashMap<String, Vec<&OntReading>>,
) -> Option<WeatherCorrelation> {
    let mut flagged_count = 0;
    let mut total_delta = 0.0;

    for serial in &group.serials {
        let readings = match by_serial.get(serial) {
            Some(r) => r,
            None => continue,
        };

        // Separate readings into night (22:00-06:00) and day (10:00-18:00)
        let night_rx: Vec<f64> = readings
            .iter()
            .filter(|r| {
                let h = r.timestamp.hour();
                r.status == OntReadingStatus::Online && (h >= 22 || h < 6)
            })
            .filter_map(|r| r.rx_power_dbm)
            .collect();

        let day_rx: Vec<f64> = readings
            .iter()
            .filter(|r| {
                let h = r.timestamp.hour();
                r.status == OntReadingStatus::Online && h >= 10 && h < 18
            })
            .filter_map(|r| r.rx_power_dbm)
            .collect();

        if night_rx.is_empty() || day_rx.is_empty() {
            continue;
        }

        let night_avg = night_rx.iter().sum::<f64>() / night_rx.len() as f64;
        let day_avg = day_rx.iter().sum::<f64>() / day_rx.len() as f64;

        // Night avg should be worse (more negative) than day avg
        let delta = day_avg - night_avg; // positive if night is worse
        if delta > MIN_CONDENSATION_DELTA_DBM {
            flagged_count += 1;
            total_delta += delta;
        }
    }

    // Need majority of ONTs to show the pattern
    if flagged_count < MIN_GROUP_SIZE || flagged_count * 2 < group.serials.len() {
        return None;
    }

    let avg_delta = total_delta / flagged_count as f64;

    Some(WeatherCorrelation {
        ont_serials: group.serials.clone(),
        port: group.port.clone(),
        distance_range: (group.min_distance, group.max_distance),
        pattern: WeatherPattern::NighttimeCondensation,
        correlation_strength: avg_delta,
        description: format!(
            "Nighttime condensation: {} ONTs at {}–{}m show avg {:.2} dBm worse Rx at night (22:00–06:00) \
             vs day (10:00–18:00), suggesting moisture ingress in splice enclosure or cable joint",
            flagged_count, group.min_distance, group.max_distance, avg_delta
        ),
    })
}

/// Check for periodic rain ingress pattern.
/// All ONTs in group degrade > 0.3 dBm for 2-8 hours then recover.
fn check_rain_ingress(
    group: &DistanceGroup,
    by_serial: &HashMap<String, Vec<&OntReading>>,
) -> Option<WeatherCorrelation> {
    // For each ONT, compute baseline Rx (average of all online readings)
    let mut baselines: HashMap<&str, f64> = HashMap::new();
    for serial in &group.serials {
        if let Some(readings) = by_serial.get(serial) {
            let rx_vals: Vec<f64> = readings
                .iter()
                .filter(|r| r.status == OntReadingStatus::Online)
                .filter_map(|r| r.rx_power_dbm)
                .collect();
            if !rx_vals.is_empty() {
                baselines.insert(serial, rx_vals.iter().sum::<f64>() / rx_vals.len() as f64);
            }
        }
    }

    if baselines.len() < MIN_GROUP_SIZE {
        return None;
    }

    // Collect all unique timestamps from all ONTs in the group
    let mut all_timestamps: Vec<DateTime<Utc>> = Vec::new();
    for serial in &group.serials {
        if let Some(readings) = by_serial.get(serial) {
            for r in readings.iter() {
                if r.status == OntReadingStatus::Online {
                    all_timestamps.push(r.timestamp);
                }
            }
        }
    }
    all_timestamps.sort();
    all_timestamps.dedup();

    // Find degradation episodes: timestamps where ALL ONTs degrade > threshold
    let mut degraded_windows: Vec<DateTime<Utc>> = Vec::new();
    for ts in &all_timestamps {
        let mut all_degraded = true;
        for serial in &group.serials {
            let baseline = match baselines.get(serial.as_str()) {
                Some(b) => *b,
                None => {
                    all_degraded = false;
                    break;
                }
            };
            if let Some(readings) = by_serial.get(serial) {
                // Find closest reading to this timestamp
                let closest_rx = readings
                    .iter()
                    .filter(|r| {
                        r.status == OntReadingStatus::Online
                            && (r.timestamp - *ts).num_seconds().abs() < 1800
                    })
                    .filter_map(|r| r.rx_power_dbm)
                    .next();

                match closest_rx {
                    Some(rx) if baseline - rx > MIN_RAIN_DEGRADATION_DBM => {}
                    _ => {
                        all_degraded = false;
                        break;
                    }
                }
            } else {
                all_degraded = false;
                break;
            }
        }
        if all_degraded {
            degraded_windows.push(*ts);
        }
    }

    // Cluster degraded timestamps into episodes (gap > 1 hour = new episode)
    let mut episodes: Vec<(DateTime<Utc>, DateTime<Utc>)> = Vec::new();
    let mut ep_start: Option<DateTime<Utc>> = None;
    let mut ep_last: Option<DateTime<Utc>> = None;

    for ts in &degraded_windows {
        match (ep_start, ep_last) {
            (Some(start), Some(last)) => {
                if (*ts - last).num_seconds() > 3600 {
                    // End previous episode, start new one
                    episodes.push((start, last));
                    ep_start = Some(*ts);
                }
                ep_last = Some(*ts);
            }
            _ => {
                ep_start = Some(*ts);
                ep_last = Some(*ts);
            }
        }
    }
    if let (Some(start), Some(last)) = (ep_start, ep_last) {
        episodes.push((start, last));
    }

    // Filter episodes: must last 2-8 hours
    let valid_episodes: Vec<&(DateTime<Utc>, DateTime<Utc>)> = episodes
        .iter()
        .filter(|(start, end)| {
            let hours = (*end - *start).num_seconds() as f64 / 3600.0;
            hours >= 2.0 && hours <= 8.0
        })
        .collect();

    if valid_episodes.len() < MIN_RAIN_EPISODES {
        // Also count short episodes from single-point degradation clusters
        if episodes.len() < MIN_RAIN_EPISODES {
            return None;
        }
    }

    let episode_count = valid_episodes.len().max(episodes.len());
    // Correlation: episodes per week (normalized by data window)
    let data_days = if all_timestamps.len() >= 2 {
        let span = (*all_timestamps.last().unwrap() - *all_timestamps.first().unwrap())
            .num_seconds() as f64
            / 86400.0;
        span.max(1.0)
    } else {
        1.0
    };
    let weekly_rate = episode_count as f64 / data_days * 7.0;

    Some(WeatherCorrelation {
        ont_serials: group.serials.clone(),
        port: group.port.clone(),
        distance_range: (group.min_distance, group.max_distance),
        pattern: WeatherPattern::PeriodicRainIngress,
        correlation_strength: weekly_rate.min(1.0),
        description: format!(
            "Periodic rain ingress: {} episodes detected across {} ONTs at {}–{}m, \
             rate {:.1}/week — check cable joints and splice enclosures for water seals",
            episode_count, group.serials.len(), group.min_distance, group.max_distance, weekly_rate
        ),
    })
}

/// Check for thermal expansion pattern.
/// Afternoon (11:00-15:00) Rx stdev > 2x night (00:00-06:00) stdev.
fn check_thermal_expansion(
    group: &DistanceGroup,
    by_serial: &HashMap<String, Vec<&OntReading>>,
) -> Option<WeatherCorrelation> {
    let mut flagged_count = 0;
    let mut total_ratio = 0.0;

    for serial in &group.serials {
        let readings = match by_serial.get(serial) {
            Some(r) => r,
            None => continue,
        };

        // Afternoon readings (11:00-15:00)
        let afternoon_rx: Vec<f64> = readings
            .iter()
            .filter(|r| {
                let h = r.timestamp.hour();
                r.status == OntReadingStatus::Online && h >= 11 && h < 15
            })
            .filter_map(|r| r.rx_power_dbm)
            .collect();

        // Night readings (00:00-06:00)
        let night_rx: Vec<f64> = readings
            .iter()
            .filter(|r| {
                let h = r.timestamp.hour();
                r.status == OntReadingStatus::Online && h < 6
            })
            .filter_map(|r| r.rx_power_dbm)
            .collect();

        if afternoon_rx.len() < 2 || night_rx.len() < 2 {
            continue;
        }

        let afternoon_stdev = stdev(&afternoon_rx);
        let night_stdev = stdev(&night_rx);

        if night_stdev < 1e-9 {
            // Night is perfectly stable; any afternoon variation counts
            if afternoon_stdev > 0.01 {
                flagged_count += 1;
                total_ratio += 10.0; // large ratio
            }
            continue;
        }

        let ratio = afternoon_stdev / night_stdev;
        if ratio > MIN_THERMAL_STDEV_RATIO {
            flagged_count += 1;
            total_ratio += ratio;
        }
    }

    // Need majority of ONTs
    if flagged_count < MIN_GROUP_SIZE || flagged_count * 2 < group.serials.len() {
        return None;
    }

    let avg_ratio = total_ratio / flagged_count as f64;
    let correlation = (avg_ratio / MIN_THERMAL_STDEV_RATIO).min(1.0);

    Some(WeatherCorrelation {
        ont_serials: group.serials.clone(),
        port: group.port.clone(),
        distance_range: (group.min_distance, group.max_distance),
        pattern: WeatherPattern::ThermalExpansion,
        correlation_strength: correlation,
        description: format!(
            "Thermal expansion: {} ONTs at {}–{}m show {:.1}x higher Rx variance during \
             afternoon (11:00–15:00) vs night (00:00–06:00), suggesting aerial cable thermal stress",
            flagged_count, group.min_distance, group.max_distance, avg_ratio
        ),
    })
}

/// Calculate standard deviation of a slice of f64 values.
fn stdev(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let n = values.len() as f64;
    let mean = values.iter().sum::<f64>() / n;
    let variance = values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / n;
    variance.sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: DateTime<Utc>,
        rx: Option<f64>,
        distance: Option<u32>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: None,
            status: OntReadingStatus::Online,
            distance_meters: distance,
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
        }
    }

    #[test]
    fn test_weather_nighttime_condensation() {
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 4 ONTs at ~500m, over 7 days with readings every 4 hours
        for day in 0..7 {
            for hour_idx in 0..6 {
                let hour = hour_idx * 4; // 0, 4, 8, 12, 16, 20
                let ts = Utc.with_ymd_and_hms(2026, 3, 10 + day, hour, 0, 0).unwrap();
                let is_night = hour >= 22 || hour < 6;

                for ont_idx in 0..4 {
                    let serial = format!("ONT{:03}", ont_idx);
                    let distance = 500 + ont_idx * 20; // 500-560m
                    // Night readings are 0.3 dBm worse
                    let rx = if is_night { -20.3 } else { -20.0 };
                    readings.push(make_reading(&serial, port, ts, Some(rx), Some(distance)));
                }
            }
        }

        let correlations = detect_weather_correlation(&readings);
        let condensation = correlations
            .iter()
            .find(|c| c.pattern == WeatherPattern::NighttimeCondensation);
        assert!(
            condensation.is_some(),
            "Should detect nighttime condensation pattern: {:?}",
            correlations
        );
        assert!(condensation.unwrap().correlation_strength >= MIN_CONDENSATION_DELTA_DBM);
    }

    #[test]
    fn test_weather_periodic_rain() {
        let port = "0/2/0";
        let mut readings = Vec::new();

        // 4 ONTs at ~800m with baseline readings
        let serials: Vec<String> = (0..4).map(|i| format!("RAIN{:03}", i)).collect();

        // Baseline readings across 14 days, every 2 hours
        for day in 0..14 {
            for hour in (0..24).step_by(2) {
                let ts = Utc.with_ymd_and_hms(2026, 3, 1 + day, hour, 0, 0).unwrap();
                for (i, serial) in serials.iter().enumerate() {
                    let distance = 800 + i as u32 * 10;
                    readings.push(make_reading(serial, port, ts, Some(-20.0), Some(distance)));
                }
            }
        }

        // Rain episode 1: day 3, hours 14-18 (4 hours), all ONTs degrade 0.5 dBm
        for hour in 14..=18 {
            let ts = Utc.with_ymd_and_hms(2026, 3, 4, hour, 0, 0).unwrap();
            for (i, serial) in serials.iter().enumerate() {
                let distance = 800 + i as u32 * 10;
                readings.push(make_reading(serial, port, ts, Some(-20.5), Some(distance)));
            }
        }

        // Rain episode 2: day 8, hours 10-14 (4 hours), all ONTs degrade 0.5 dBm
        for hour in 10..=14 {
            let ts = Utc.with_ymd_and_hms(2026, 3, 9, hour, 0, 0).unwrap();
            for (i, serial) in serials.iter().enumerate() {
                let distance = 800 + i as u32 * 10;
                readings.push(make_reading(serial, port, ts, Some(-20.5), Some(distance)));
            }
        }

        let correlations = detect_weather_correlation(&readings);
        let rain = correlations
            .iter()
            .find(|c| c.pattern == WeatherPattern::PeriodicRainIngress);
        assert!(
            rain.is_some(),
            "Should detect periodic rain ingress pattern: {:?}",
            correlations
        );
    }

    #[test]
    fn test_weather_thermal_expansion() {
        let port = "0/3/0";
        let mut readings = Vec::new();

        // 4 ONTs at ~1200m over 7 days
        for day in 0..7 {
            for hour in (0..24).step_by(2) {
                let ts = Utc.with_ymd_and_hms(2026, 3, 10 + day, hour, 0, 0).unwrap();
                let is_afternoon = hour >= 11 && hour < 15;

                for ont_idx in 0..4 {
                    let serial = format!("THERM{:03}", ont_idx);
                    let distance = 1200 + ont_idx * 15;
                    // Afternoon: high variance (-19.5 to -20.5)
                    // Night: stable (-20.0)
                    let rx = if is_afternoon {
                        -20.0 + ((day as f64 + ont_idx as f64) * 0.3).sin() * 0.5
                    } else {
                        -20.0
                    };
                    readings.push(make_reading(&serial, port, ts, Some(rx), Some(distance)));
                }
            }
        }

        let correlations = detect_weather_correlation(&readings);
        let thermal = correlations
            .iter()
            .find(|c| c.pattern == WeatherPattern::ThermalExpansion);
        assert!(
            thermal.is_some(),
            "Should detect thermal expansion pattern: {:?}",
            correlations
        );
    }

    #[test]
    fn test_weather_no_pattern_normal() {
        let port = "0/4/0";
        let mut readings = Vec::new();

        // 4 ONTs with perfectly stable signal at all times
        for day in 0..7 {
            for hour in (0..24).step_by(4) {
                let ts = Utc.with_ymd_and_hms(2026, 3, 10 + day, hour, 0, 0).unwrap();
                for ont_idx in 0..4 {
                    let serial = format!("NORM{:03}", ont_idx);
                    let distance = 600 + ont_idx * 20;
                    readings.push(make_reading(&serial, port, ts, Some(-20.0), Some(distance)));
                }
            }
        }

        let correlations = detect_weather_correlation(&readings);
        assert!(
            correlations.is_empty(),
            "Stable network should produce no weather correlations: {:?}",
            correlations
        );
    }

    #[test]
    fn test_weather_requires_group_of_3() {
        let port = "0/5/0";
        let mut readings = Vec::new();

        // Only 2 ONTs — not enough for a weather group
        for day in 0..7 {
            for hour in (0..24).step_by(4) {
                let ts = Utc.with_ymd_and_hms(2026, 3, 10 + day, hour, 0, 0).unwrap();
                let is_night = hour >= 22 || hour < 6;
                for ont_idx in 0..2 {
                    let serial = format!("PAIR{:03}", ont_idx);
                    let distance = 700 + ont_idx * 10;
                    let rx = if is_night { -20.4 } else { -20.0 };
                    readings.push(make_reading(&serial, port, ts, Some(rx), Some(distance)));
                }
            }
        }

        let correlations = detect_weather_correlation(&readings);
        assert!(
            correlations.is_empty(),
            "Should require 3+ ONTs in a distance group: {:?}",
            correlations
        );
    }
}
