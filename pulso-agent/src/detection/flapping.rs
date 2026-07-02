// SPDX-License-Identifier: Apache-2.0
// Flapping ONT Detector
//
// Detects ONTs that repeatedly cycle online/offline (flapping). A flapping
// ONT wastes OLT CPU, generates alarm storms, and can cascade-crash an
// entire PON port.
//
// Detection method:
//   1. Group readings by serial number, sort by timestamp
//      (Unknown-status readings are polling gaps, not observations,
//       and are excluded before transition counting)
//   2. Count state transitions (Online->Offline or Offline->Online) per ONT
//   3. Statistical gates before ANY rating: at least 4 transitions observed
//      over an observation window of at least 1 hour. Two transitions five
//      minutes apart are a single reconnect, not a "24/hour flapper" —
//      extrapolating a rate from <1h of data is suppressed entirely.
//   4. Flap rate = transitions / observation_window_hours (the full span of
//      readings for the ONT, not just first-to-last flap, so a short burst
//      cannot masquerade as a sustained rate)
//   5. Classify severity: Sporadic (2-5/h), Moderate (5-15/h), Severe (>15/h)
//   6. Calculate cascade risk for severe flappers on busy ports (>20 ONTs)
//   7. Estimate root cause from signal patterns and down-cause metadata

use std::collections::HashMap;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// A detected flapping ONT with severity, cause, and cascade risk.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlappingOnt {
    pub ont_serial: String,
    pub port: String,
    pub flap_count: u32,
    pub flap_rate_per_hour: f64,
    pub severity: FlappingSeverity,
    pub first_flap: DateTime<Utc>,
    pub last_flap: DateTime<Utc>,
    pub cascade_risk: f64,
    pub probable_cause: FlappingCause,
    pub port_ont_count: u32,
}

/// Flapping severity classification based on flap rate per hour.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum FlappingSeverity {
    Sporadic,
    Moderate,
    Severe,
}

/// Estimated root cause of ONT flapping.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum FlappingCause {
    DirtyConnector,
    PowerInstability,
    HardwareFault,
    Unknown,
}

/// Minimum flap rate (per hour) to classify as Sporadic.
const FLAP_RATE_SPORADIC: f64 = 2.0;

/// Minimum flap rate (per hour) to classify as Moderate.
const FLAP_RATE_MODERATE: f64 = 5.0;

/// Minimum flap rate (per hour) to classify as Severe.
const FLAP_RATE_SEVERE: f64 = 15.0;

/// Minimum observation window (hours) before any flap rate may be quoted.
/// Rates extrapolated from shorter windows are statistically meaningless
/// (2 transitions 5 minutes apart would extrapolate to "24/hour").
const MIN_OBSERVATION_WINDOW_HOURS: f64 = 1.0;

/// Minimum number of state transitions before an ONT is considered a
/// flapper at all. Below this it is a normal reconnect.
const MIN_TRANSITIONS: u32 = 4;

/// Minimum number of ONTs on a port to consider cascade risk elevated.
const CASCADE_PORT_THRESHOLD: u32 = 20;

/// Marginal Rx power lower bound (dBm) — connectors in this range are suspect.
const MARGINAL_RX_LOW_DBM: f64 = -27.0;

/// Marginal Rx power upper bound (dBm).
const MARGINAL_RX_HIGH_DBM: f64 = -24.0;

/// Coefficient of variation threshold for detecting periodic (regular) flaps.
const PERIODIC_CV_THRESHOLD: f64 = 0.3;

/// Detect flapping ONTs from a time-series of ONT readings across all ports.
///
/// Groups readings by serial number, counts state transitions, calculates
/// flap rate, classifies severity, estimates root cause, and scores cascade
/// risk based on port density.
pub fn detect_flapping(readings: &[OntReading]) -> Vec<FlappingOnt> {
    if readings.is_empty() {
        return Vec::new();
    }

    // Group readings by serial number
    let mut by_serial: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial
            .entry(&r.serial_number)
            .or_default()
            .push(r);
    }

    // Count unique ONTs per port for cascade risk calculation
    let mut port_ont_counts: HashMap<&str, Vec<&str>> = HashMap::new();
    for r in readings {
        port_ont_counts
            .entry(&r.pon_port)
            .or_default()
            .push(&r.serial_number);
    }
    let port_ont_counts: HashMap<&str, u32> = port_ont_counts
        .into_iter()
        .map(|(port, serials)| {
            let mut s: Vec<&str> = serials;
            s.sort();
            s.dedup();
            (port, s.len() as u32)
        })
        .collect();

    let mut results = Vec::new();

    for (serial, mut serial_readings) in by_serial {
        // Unknown-status readings are polling gaps, not observations —
        // they must not create phantom transitions (Online -> Unknown ->
        // Online would otherwise count as two flaps).
        serial_readings.retain(|r| r.status != OntReadingStatus::Unknown);
        serial_readings.sort_by_key(|r| r.timestamp);

        if serial_readings.len() < 2 {
            continue;
        }

        // Find state transitions and collect transition timestamps
        let mut transitions: Vec<DateTime<Utc>> = Vec::new();
        let mut online_rx_values: Vec<f64> = Vec::new();
        let mut has_power_down_cause = false;

        for window in serial_readings.windows(2) {
            let prev = window[0];
            let curr = window[1];

            let is_transition = prev.status != curr.status;
            if is_transition {
                transitions.push(curr.timestamp);
            }

            // Collect Rx power during online periods for cause analysis
            // (sentinels / implausible values excluded)
            if curr.status == OntReadingStatus::Online {
                if let Some(rx) = super::sane_rx(curr) {
                    online_rx_values.push(rx);
                }
            }

            // Check for power-related down causes
            if curr.status == OntReadingStatus::Offline {
                if let Some(ref cause) = curr.last_down_cause {
                    if cause.to_lowercase().contains("power") {
                        has_power_down_cause = true;
                    }
                }
            }
        }

        let flap_count = transitions.len() as u32;
        if flap_count < MIN_TRANSITIONS {
            // A couple of transitions is a normal reconnect, not flapping.
            continue;
        }

        // Observation window: the full span of readings for this ONT, NOT
        // first-to-last flap. A burst of flaps inside a long stable window
        // yields the true average rate; more importantly, a rate cannot be
        // extrapolated from a window shorter than MIN_OBSERVATION_WINDOW_HOURS
        // — such ONTs are suppressed rather than rated as low-confidence noise.
        let obs_start = serial_readings.first().unwrap().timestamp;
        let obs_end = serial_readings.last().unwrap().timestamp;
        let window_hours = (obs_end - obs_start).num_seconds() as f64 / 3600.0;
        if window_hours < MIN_OBSERVATION_WINDOW_HOURS {
            continue;
        }

        let first_flap = transitions[0];
        let last_flap = transitions[transitions.len() - 1];
        let flap_rate = flap_count as f64 / window_hours;

        // Classify severity
        let severity = if flap_rate >= FLAP_RATE_SEVERE {
            FlappingSeverity::Severe
        } else if flap_rate >= FLAP_RATE_MODERATE {
            FlappingSeverity::Moderate
        } else if flap_rate >= FLAP_RATE_SPORADIC {
            FlappingSeverity::Sporadic
        } else {
            // Below threshold — normal reconnects, skip
            continue;
        };

        // Determine port for this ONT (use most common port in readings)
        let port = serial_readings
            .last()
            .map(|r| r.pon_port.clone())
            .unwrap_or_default();

        let ont_count = port_ont_counts
            .get(port.as_str())
            .copied()
            .unwrap_or(1);

        // Calculate cascade risk: severe flappers on busy ports get higher risk
        let cascade_risk = {
            let severity_factor = match severity {
                FlappingSeverity::Severe => 0.7,
                FlappingSeverity::Moderate => 0.3,
                FlappingSeverity::Sporadic => 0.1,
            };
            let density_factor = if ont_count > CASCADE_PORT_THRESHOLD {
                0.3 * (ont_count as f64 / CASCADE_PORT_THRESHOLD as f64).min(2.0)
            } else {
                0.1
            };
            (severity_factor + density_factor).min(1.0)
        };

        // Estimate root cause
        let probable_cause = estimate_cause(
            &online_rx_values,
            has_power_down_cause,
            &transitions,
        );

        results.push(FlappingOnt {
            ont_serial: serial.to_string(),
            port,
            flap_count,
            flap_rate_per_hour: flap_rate,
            severity,
            first_flap,
            last_flap,
            cascade_risk,
            probable_cause,
            port_ont_count: ont_count,
        });
    }

    // Sort by flap rate descending (worst offenders first)
    results.sort_by(|a, b| {
        b.flap_rate_per_hour
            .partial_cmp(&a.flap_rate_per_hour)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Estimate the root cause of flapping from signal data and transition patterns.
///
/// Priority order:
///   1. Marginal Rx power (-24 to -27 dBm) during online periods -> dirty connector
///   2. Down cause contains "power" -> power instability
///   3. Regular transition intervals (low coefficient of variation) -> hardware fault
///   4. Otherwise -> unknown
fn estimate_cause(
    online_rx_values: &[f64],
    has_power_down_cause: bool,
    transitions: &[DateTime<Utc>],
) -> FlappingCause {
    // Check for marginal Rx power (dirty connector)
    if !online_rx_values.is_empty() {
        let avg_rx = online_rx_values.iter().sum::<f64>() / online_rx_values.len() as f64;
        if avg_rx >= MARGINAL_RX_LOW_DBM && avg_rx <= MARGINAL_RX_HIGH_DBM {
            return FlappingCause::DirtyConnector;
        }
    }

    // Check for power instability
    if has_power_down_cause {
        return FlappingCause::PowerInstability;
    }

    // Check for periodic (hardware fault) — regular intervals between transitions
    if transitions.len() >= 3 {
        let intervals: Vec<f64> = transitions
            .windows(2)
            .map(|w| (w[1] - w[0]).num_seconds() as f64)
            .collect();

        let mean = intervals.iter().sum::<f64>() / intervals.len() as f64;
        if mean > 0.0 {
            let variance = intervals
                .iter()
                .map(|x| (x - mean).powi(2))
                .sum::<f64>()
                / intervals.len() as f64;
            let cv = variance.sqrt() / mean;
            if cv < PERIODIC_CV_THRESHOLD {
                return FlappingCause::HardwareFault;
            }
        }
    }

    FlappingCause::Unknown
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
        tx: Option<f64>,
        distance: Option<u32>,
        down_cause: Option<&str>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: tx,
            status,
            distance_meters: distance,
            eth_speed_mbps: None,
            last_down_cause: down_cause.map(|s| s.into()),
            ..Default::default()
        }
    }

    #[test]
    fn test_no_flapping_stable_network() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 10 ONTs, all stable online throughout
        for i in 0..10 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now - Duration::hours(2),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &serial, port, now - Duration::hours(1),
                OntReadingStatus::Online, Some(-20.1), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Online, Some(-19.9), Some(2.5), Some(1000), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert!(flappers.is_empty(), "Stable network should produce no flapping detections");
    }

    #[test]
    fn test_flapping_severe() {
        let now = Utc::now();
        let port = "0/2/0";
        let mut readings = Vec::new();

        // One ONT cycles 22 times in ~63 minutes -> Severe
        let serial = "FLAPPER001";
        for i in 0..22 {
            let offset_mins = (i as i64) * 3; // spread over 63 mins (>= 1h window)
            let ts = now - Duration::minutes(63) + Duration::minutes(offset_mins);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Offline
            };
            readings.push(make_reading(
                serial, port, ts, status,
                Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        // Some stable ONTs on the same port
        for i in 0..5 {
            let s = format!("STABLE{:03}", i);
            readings.push(make_reading(
                &s, port, now - Duration::hours(1),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &s, port, now,
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert_eq!(flappers.len(), 1);
        assert_eq!(flappers[0].ont_serial, "FLAPPER001");
        assert_eq!(flappers[0].severity, FlappingSeverity::Severe);
        assert!(
            flappers[0].flap_rate_per_hour >= FLAP_RATE_SEVERE,
            "Flap rate {} should be >= {}",
            flappers[0].flap_rate_per_hour,
            FLAP_RATE_SEVERE,
        );
    }

    #[test]
    fn test_flapping_moderate() {
        let now = Utc::now();
        let port = "0/3/0";
        let mut readings = Vec::new();

        // ONT cycles 8 times in 1 hour -> Moderate (8 transitions / 1h = 8/h)
        let serial = "FLAPPER002";
        for i in 0..9 {
            let ts = now - Duration::minutes(60) + Duration::minutes(i as i64 * 60 / 8);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Offline
            };
            readings.push(make_reading(
                serial, port, ts, status,
                Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert_eq!(flappers.len(), 1);
        assert_eq!(flappers[0].ont_serial, "FLAPPER002");
        assert_eq!(flappers[0].severity, FlappingSeverity::Moderate);
    }

    #[test]
    fn test_flapping_sporadic() {
        let now = Utc::now();
        let port = "0/4/0";
        let mut readings = Vec::new();

        // ONT makes 4 transitions over a 2-hour window -> Sporadic (4 / 2h = 2/h)
        let serial = "FLAPPER003";
        for (mins, status) in [
            (120_i64, OntReadingStatus::Online),
            (100, OntReadingStatus::Offline),
            (80, OntReadingStatus::Online),
            (40, OntReadingStatus::Offline),
            (0, OntReadingStatus::Online),
        ] {
            readings.push(make_reading(
                serial, port, now - Duration::minutes(mins),
                status, Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert_eq!(flappers.len(), 1);
        assert_eq!(flappers[0].ont_serial, "FLAPPER003");
        assert_eq!(flappers[0].severity, FlappingSeverity::Sporadic);
    }

    #[test]
    fn test_flapping_dirty_connector_cause() {
        let now = Utc::now();
        let port = "0/5/0";
        let mut readings = Vec::new();

        // ONT flapping with marginal Rx power (-25.5 dBm) -> DirtyConnector
        let serial = "DIRTY001";
        for i in 0..12 {
            let ts = now - Duration::minutes(66) + Duration::minutes(i as i64 * 6);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Offline
            };
            let rx = if status == OntReadingStatus::Online {
                Some(-25.5) // Marginal range: -24 to -27 dBm
            } else {
                None
            };
            readings.push(make_reading(
                serial, port, ts, status,
                rx, Some(2.5), Some(800), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert_eq!(flappers.len(), 1);
        assert_eq!(flappers[0].probable_cause, FlappingCause::DirtyConnector);
    }

    #[test]
    fn test_flapping_single_reconnect_not_a_flapper() {
        let now = Utc::now();
        let port = "0/7/0";
        // Two transitions 5 minutes apart: previously extrapolated to a
        // "Severe 24/h flapper". Must produce NO detection — below both the
        // minimum transition count and the minimum observation window.
        let readings = vec![
            make_reading(
                "RECONNECT01", port, now - Duration::minutes(10),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(500), None,
            ),
            make_reading(
                "RECONNECT01", port, now - Duration::minutes(5),
                OntReadingStatus::Offline, None, None, Some(500), None,
            ),
            make_reading(
                "RECONNECT01", port, now,
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(500), None,
            ),
        ];

        let flappers = detect_flapping(&readings);
        assert!(
            flappers.is_empty(),
            "2 transitions 5 min apart must not be rated a flapper: {:?}",
            flappers
        );
    }

    #[test]
    fn test_flapping_short_window_suppressed() {
        let now = Utc::now();
        let port = "0/8/0";
        // Plenty of transitions but all within 30 minutes: rate extrapolation
        // from <1h of observation is suppressed, not labeled Severe.
        let mut readings = Vec::new();
        for i in 0..10 {
            let ts = now - Duration::minutes(30) + Duration::minutes(i * 3);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Offline
            };
            readings.push(make_reading(
                "BURST01", port, ts, status,
                Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert!(
            flappers.is_empty(),
            "sub-1h observation window must be suppressed: {:?}",
            flappers
        );
    }

    #[test]
    fn test_flapping_unknown_status_no_phantom_transitions() {
        let now = Utc::now();
        let port = "0/9/0";
        // Online readings interleaved with Unknown (polling gaps) over 2h:
        // must not fabricate transitions.
        let mut readings = Vec::new();
        for i in 0..8 {
            let ts = now - Duration::hours(2) + Duration::minutes(i * 15);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Unknown
            };
            readings.push(make_reading(
                "UNKNOWN01", port, ts, status,
                Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert!(
            flappers.is_empty(),
            "Unknown-status polling gaps must not create flap transitions: {:?}",
            flappers
        );
    }

    #[test]
    fn test_flapping_cascade_risk() {
        let now = Utc::now();
        let port = "0/6/0";
        let mut readings = Vec::new();

        // 30 stable ONTs on the same port (busy port)
        for i in 0..30 {
            let s = format!("STABLE{:03}", i);
            readings.push(make_reading(
                &s, port, now - Duration::hours(1),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &s, port, now,
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        // One severe flapper on the same busy port
        let serial = "FLAPPER_CASCADE";
        for i in 0..20 {
            let ts = now - Duration::minutes(76) + Duration::minutes(i as i64 * 4);
            let status = if i % 2 == 0 {
                OntReadingStatus::Online
            } else {
                OntReadingStatus::Offline
            };
            readings.push(make_reading(
                serial, port, ts, status,
                Some(-20.0), Some(2.5), Some(500), None,
            ));
        }

        let flappers = detect_flapping(&readings);
        assert_eq!(flappers.len(), 1);
        assert_eq!(flappers[0].ont_serial, "FLAPPER_CASCADE");
        assert!(
            flappers[0].cascade_risk > 0.7,
            "Severe flapper on busy port (31 ONTs) should have high cascade risk, got {}",
            flappers[0].cascade_risk,
        );
        assert_eq!(flappers[0].port_ont_count, 31); // 30 stable + 1 flapper
    }
}
