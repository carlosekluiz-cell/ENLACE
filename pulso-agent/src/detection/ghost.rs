// SPDX-License-Identifier: Apache-2.0
// Ghost Customer Detector
//
// Detects ONTs that are provisioned and online but never actually used.
// These represent revenue leakage: the ISP is paying for equipment and
// a port on the splitter, but the customer either never connected their
// router or has abandoned the service without cancelling.
//
// Detection criteria:
//   1. ONT consistently online (uptime > 90% of Online/Offline observations)
//   2. Rx power healthy (avg > -25 dBm) — rules out degraded/dead ONTs
//   3. Ethernet port shows no link: eth_speed always 0 or None
//      (no cable connected — the only usage signal available today)
//
// PHYSICS NOTE (why there is no Rx-variance check): GPON downstream is a
// CONTINUOUS broadcast — the OLT transmits at constant power to every ONT
// on the splitter regardless of who is passing traffic. An idle customer's
// ONT Rx power is exactly as stable as a busy customer's, so "flat Rx
// variance" carries zero information about usage and previously flagged
// perfectly healthy paying customers as revenue leakage. Usage detection
// for eth-linked ONTs requires traffic octet counters, which are not yet
// present in `OntReading`; until they are, those ONTs are honestly
// reported as insufficient-data instead of being guessed at.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{sane_rx, OntReading, OntReadingStatus};

/// A detected ghost customer — provisioned and online but never used.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostCustomer {
    pub ont_serial: String,
    pub port: String,
    pub distance_m: Option<u32>,
    pub rx_power_dbm: f64,
    pub eth_status: GhostEthStatus,
    pub days_online: f64,
    /// Assumed monthly revenue for this subscriber (= configured ARPU).
    /// An assumption echoed for context, not a measured value.
    pub estimated_monthly_revenue: f64,
}

/// Why the ghost ONT is considered unused.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum GhostEthStatus {
    /// Ethernet speed always 0 or None — no cable connected.
    NoLink,
}

impl std::fmt::Display for GhostEthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoLink => write!(f, "no_link"),
        }
    }
}

/// Full ghost-detection output, including the honest "cannot tell" bucket.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostDetection {
    /// ONTs confirmed unused (no ethernet link ever seen).
    pub ghosts: Vec<GhostCustomer>,
    /// ONT serials that are online and healthy with an ethernet link, whose
    /// actual usage CANNOT be determined: traffic octet counters are not
    /// available in the current data model, and GPON downstream Rx power
    /// carries no usage information (continuous broadcast). These are NOT
    /// ghosts — they are unknowns.
    pub insufficient_data_serials: Vec<String>,
}

/// Minimum uptime ratio for an ONT to be considered "consistently online".
const MIN_UPTIME_RATIO: f64 = 0.90;

/// Minimum average Rx power (dBm) for a healthy ONT.
const MIN_HEALTHY_RX_DBM: f64 = -25.0;

/// Detect ghost customers from ONT readings (confirmed no-link ghosts only).
///
/// Convenience wrapper around [`detect_ghost_customers_detailed`] that
/// returns just the confirmed ghosts. ONTs whose usage cannot be determined
/// (ethernet link present but no traffic counters available) are excluded —
/// they are reported in the detailed variant, never flagged as leakage.
pub fn detect_ghost_customers(readings: &[OntReading], arpu: f64) -> Vec<GhostCustomer> {
    detect_ghost_customers_detailed(readings, arpu).ghosts
}

/// Detect ghost customers, separating confirmed ghosts from ONTs with
/// insufficient data.
///
/// Groups readings by serial number and checks each ONT for:
///   - High uptime (> 90% of Online/Offline observations Online;
///     Unknown-status readings are not observations and are excluded)
///   - Healthy Rx power (average > -25 dBm)
///   - No ethernet link ever observed -> confirmed ghost (NoLink)
///   - Ethernet link observed -> insufficient data (usage unknowable
///     without traffic octet counters)
pub fn detect_ghost_customers_detailed(readings: &[OntReading], arpu: f64) -> GhostDetection {
    let mut by_serial: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial
            .entry(r.serial_number.clone())
            .or_default()
            .push(r);
    }

    let mut ghosts = Vec::new();
    let mut insufficient_data_serials = Vec::new();

    for (serial, mut ont_readings) in by_serial {
        ont_readings.sort_by_key(|r| r.timestamp);

        if ont_readings.len() < 3 {
            continue;
        }

        // 1. Check uptime > 90% of definite (Online/Offline) observations.
        //    Unknown-status readings are polling gaps, not evidence.
        let online_count = ont_readings
            .iter()
            .filter(|r| r.status == OntReadingStatus::Online)
            .count();
        let observed_count = ont_readings
            .iter()
            .filter(|r| r.status != OntReadingStatus::Unknown)
            .count();
        if observed_count < 3 {
            continue;
        }
        let uptime_ratio = online_count as f64 / observed_count as f64;
        if uptime_ratio < MIN_UPTIME_RATIO {
            continue;
        }

        // 2. Check Rx power healthy (avg > -25 dBm, sentinels excluded)
        let rx_values: Vec<f64> = ont_readings.iter().filter_map(|r| sane_rx(r)).collect();
        if rx_values.is_empty() {
            continue;
        }
        let rx_avg = rx_values.iter().sum::<f64>() / rx_values.len() as f64;
        if rx_avg <= MIN_HEALTHY_RX_DBM {
            continue;
        }

        // 3. Check ethernet status
        let has_any_eth = ont_readings.iter().any(|r| {
            r.eth_speed_mbps.map_or(false, |s| s > 0)
        });

        if has_any_eth {
            // Link is up, but without traffic octet counters we cannot know
            // whether the customer actually uses the service. GPON downstream
            // Rx does not vary with traffic, so there is no optical proxy.
            // Report honestly as insufficient data — never as leakage.
            insufficient_data_serials.push(serial);
            continue;
        }

        // 4. Calculate days online from first to last reading
        let first_ts = ont_readings.first().unwrap().timestamp;
        let last_ts = ont_readings.last().unwrap().timestamp;
        let days_online = (last_ts - first_ts).num_seconds() as f64 / 86400.0;

        // Get distance from any reading that has it
        let distance_m = ont_readings.iter().find_map(|r| r.distance_meters);

        // Get port from first reading
        let port = ont_readings[0].pon_port.clone();

        ghosts.push(GhostCustomer {
            ont_serial: serial,
            port,
            distance_m,
            rx_power_dbm: rx_avg,
            eth_status: GhostEthStatus::NoLink,
            days_online,
            estimated_monthly_revenue: arpu,
        });
    }

    // Sort by estimated revenue descending (all same ARPU, so by days_online)
    ghosts.sort_by(|a, b| {
        b.days_online
            .partial_cmp(&a.days_online)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    insufficient_data_serials.sort();

    GhostDetection {
        ghosts,
        insufficient_data_serials,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{DateTime, Duration, Utc};

    fn make_reading(
        serial: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
        eth_speed: Option<u32>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            rx_power_dbm: rx,
            tx_power_dbm: None,
            status,
            distance_meters: Some(500),
            eth_speed_mbps: eth_speed,
            last_down_cause: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_ghost_no_ethernet_link() {
        let now = Utc::now();
        // ONT online with good signal but eth_speed always None
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "GHOST01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0),
                    None, // no ethernet link
                )
            })
            .collect();

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert_eq!(ghosts.len(), 1);
        assert_eq!(ghosts[0].ont_serial, "GHOST01");
        assert_eq!(ghosts[0].eth_status, GhostEthStatus::NoLink);
        assert!((ghosts[0].estimated_monthly_revenue - 89.90).abs() < 0.01);
    }

    #[test]
    fn test_ghost_flat_signal_with_link_is_insufficient_data() {
        let now = Utc::now();
        // ONT online with eth link and perfectly flat Rx power. GPON downstream
        // is continuous broadcast, so a flat Rx says NOTHING about usage —
        // this must be reported as insufficient data, never as a ghost.
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "STABLE02",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0), // perfectly flat — irrelevant to usage
                    Some(1000),  // ethernet link present
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "Flat Rx with eth link must NOT be flagged as ghost: {:?}",
            detection.ghosts
        );
        assert_eq!(
            detection.insufficient_data_serials,
            vec!["STABLE02".to_string()],
            "eth-linked ONT without traffic counters is insufficient data"
        );
    }

    #[test]
    fn test_ghost_varying_signal_with_link_also_insufficient_data() {
        let now = Utc::now();
        // Varying Rx with eth link: equally unknowable (Rx variance is
        // thermal/quantization noise, not traffic).
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                let rx = -20.0 + (i as f64 * 0.1) - 0.5; // varying signal
                make_reading(
                    "ACTIVE01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(rx),
                    Some(1000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "eth-linked customer should never be flagged as ghost"
        );
        assert_eq!(detection.insufficient_data_serials, vec!["ACTIVE01".to_string()]);
    }

    #[test]
    fn test_ghost_excludes_degraded_signal() {
        let now = Utc::now();
        // ONT online but with degraded signal (avg < -25 dBm) — not a ghost, just broken
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "DEGRADED01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-27.0), // degraded signal
                    None,
                )
            })
            .collect();

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert!(
            ghosts.is_empty(),
            "ONT with degraded signal (< -25 dBm) should not be flagged as ghost"
        );
    }

    #[test]
    fn test_ghost_unknown_status_excluded_from_uptime() {
        let now = Utc::now();
        // 5 Online + 5 Unknown readings: uptime over definite observations is
        // 100%, so the Unknown polling gaps must not disqualify the ONT.
        let mut readings: Vec<OntReading> = (0..5)
            .map(|i| {
                make_reading(
                    "GHOST_UNK",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0),
                    None,
                )
            })
            .collect();
        for i in 5..10 {
            readings.push(make_reading(
                "GHOST_UNK",
                now - Duration::days(10 - i),
                OntReadingStatus::Unknown,
                None,
                None,
            ));
        }

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert_eq!(ghosts.len(), 1, "Unknown readings must not count as downtime");
    }
}
