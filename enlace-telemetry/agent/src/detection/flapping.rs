// SPDX-License-Identifier: Apache-2.0
// Flapping ONT Detector
//
// Detects ONTs that repeatedly cycle online/offline (flapping). A flapping
// ONT wastes OLT CPU, generates alarm storms, and can cascade-crash an
// entire PON port.
//
// Detection method:
//   1. Group readings by serial number, sort by timestamp
//   2. Count state transitions (Online->Offline or Offline->Online) per ONT
//   3. Calculate flap rate = transitions / time_span_hours
//   4. Classify severity: Sporadic (2-5/h), Moderate (5-15/h), Severe (>15/h)
//   5. Calculate cascade risk for severe flappers on busy ports (>20 ONTs)
//   6. Estimate root cause from signal patterns and down-cause metadata

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
            if curr.status == OntReadingStatus::Online {
                if let Some(rx) = curr.rx_power_dbm {
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
        if flap_count < 2 {
            continue;
        }

        let first_flap = transitions[0];
        let last_flap = transitions[transitions.len() - 1];
        let time_span = last_flap - first_flap;
        let time_span_hours = time_span.num_seconds() as f64 / 3600.0;

        // Avoid division by zero for transitions that happen within the same second
        let flap_rate = if time_span_hours > 0.0 {
            flap_count as f64 / time_span_hours
        } else {
            flap_count as f64
        };

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

        // One ONT cycles 22 times in 1 hour -> Severe
        let serial = "FLAPPER001";
        for i in 0..22 {
            let offset_mins = (i as i64) * 60 / 22; // spread over ~60 mins
            let ts = now - Duration::minutes(60) + Duration::minutes(offset_mins);
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

        // ONT cycles 3 times over 90 minutes -> Sporadic (3 / 1.5h = 2/h)
        let serial = "FLAPPER003";
        readings.push(make_reading(
            serial, port, now - Duration::minutes(120),
            OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(500), None,
        ));
        readings.push(make_reading(
            serial, port, now - Duration::minutes(100),
            OntReadingStatus::Offline, Some(-20.0), Some(2.5), Some(500), None,
        ));
        readings.push(make_reading(
            serial, port, now - Duration::minutes(60),
            OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(500), None,
        ));
        readings.push(make_reading(
            serial, port, now - Duration::minutes(10),
            OntReadingStatus::Offline, Some(-20.0), Some(2.5), Some(500), None,
        ));

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
            let ts = now - Duration::minutes(60) + Duration::minutes(i as i64 * 5);
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
            let ts = now - Duration::minutes(60) + Duration::minutes(i as i64 * 3);
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
