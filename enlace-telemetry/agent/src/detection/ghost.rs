// SPDX-License-Identifier: Apache-2.0
// Ghost Customer Detector
//
// Detects ONTs that are provisioned and online but never actually used.
// These represent revenue leakage: the ISP is paying for equipment and
// a port on the splitter, but the customer either never connected their
// router or has abandoned the service without cancelling.
//
// Detection criteria:
//   1. ONT consistently online (uptime > 90%)
//   2. Rx power healthy (avg > -25 dBm) — rules out degraded/dead ONTs
//   3. Ethernet port shows no activity:
//      - NoLink: eth_speed always 0 or None (no cable connected)
//      - NoTraffic: eth_speed present but Rx power variance near zero
//        (active customers cause slight power fluctuations from traffic)

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// A detected ghost customer — provisioned and online but never used.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostCustomer {
    pub ont_serial: String,
    pub port: String,
    pub distance_m: Option<u32>,
    pub rx_power_dbm: f64,
    pub rx_power_variance: f64,
    pub eth_status: GhostEthStatus,
    pub days_online: f64,
    pub estimated_monthly_revenue: f64,
}

/// Why the ghost ONT is considered unused.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum GhostEthStatus {
    /// Ethernet speed always 0 or None — no cable connected.
    NoLink,
    /// Ethernet speed present but Rx power variance near zero — no real traffic.
    NoTraffic,
}

impl std::fmt::Display for GhostEthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoLink => write!(f, "no_link"),
            Self::NoTraffic => write!(f, "no_traffic"),
        }
    }
}

/// Minimum uptime ratio for an ONT to be considered "consistently online".
const MIN_UPTIME_RATIO: f64 = 0.90;

/// Minimum average Rx power (dBm) for a healthy ONT.
const MIN_HEALTHY_RX_DBM: f64 = -25.0;

/// Maximum Rx power variance (dBm^2) to flag as "no traffic".
/// Active customers cause slight power fluctuations from traffic and temperature.
const MAX_FLAT_VARIANCE: f64 = 0.01;

/// Detect ghost customers from ONT readings.
///
/// Groups readings by serial number and checks each ONT for:
///   - High uptime (> 90% of readings Online)
///   - Healthy Rx power (average > -25 dBm)
///   - No ethernet activity (NoLink or NoTraffic)
///
/// Returns a list of ghost customers sorted by estimated revenue impact.
pub fn detect_ghost_customers(readings: &[OntReading], arpu: f64) -> Vec<GhostCustomer> {
    let mut by_serial: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial
            .entry(r.serial_number.clone())
            .or_default()
            .push(r);
    }

    let mut results = Vec::new();

    for (serial, mut ont_readings) in by_serial {
        ont_readings.sort_by_key(|r| r.timestamp);

        if ont_readings.len() < 3 {
            continue;
        }

        // 1. Check uptime > 90%
        let online_count = ont_readings
            .iter()
            .filter(|r| r.status == OntReadingStatus::Online)
            .count();
        let uptime_ratio = online_count as f64 / ont_readings.len() as f64;
        if uptime_ratio < MIN_UPTIME_RATIO {
            continue;
        }

        // 2. Check Rx power healthy (avg > -25 dBm)
        let rx_values: Vec<f64> = ont_readings
            .iter()
            .filter_map(|r| r.rx_power_dbm)
            .collect();
        if rx_values.is_empty() {
            continue;
        }
        let rx_avg = rx_values.iter().sum::<f64>() / rx_values.len() as f64;
        if rx_avg <= MIN_HEALTHY_RX_DBM {
            continue;
        }

        // Calculate Rx power variance
        let rx_variance = if rx_values.len() > 1 {
            let mean = rx_avg;
            rx_values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / rx_values.len() as f64
        } else {
            0.0
        };

        // 3. Check ethernet status
        let has_any_eth = ont_readings.iter().any(|r| {
            r.eth_speed_mbps.map_or(false, |s| s > 0)
        });

        let eth_status = if !has_any_eth {
            // eth_speed always 0 or None — no link
            GhostEthStatus::NoLink
        } else if rx_variance < MAX_FLAT_VARIANCE {
            // eth_speed present but Rx power variance near zero — no real traffic
            GhostEthStatus::NoTraffic
        } else {
            // Active customer — skip
            continue;
        };

        // 4. Calculate days online from first to last reading
        let first_ts = ont_readings.first().unwrap().timestamp;
        let last_ts = ont_readings.last().unwrap().timestamp;
        let days_online = (last_ts - first_ts).num_seconds() as f64 / 86400.0;

        // Get distance from any reading that has it
        let distance_m = ont_readings.iter().find_map(|r| r.distance_meters);

        // Get port from first reading
        let port = ont_readings[0].pon_port.clone();

        results.push(GhostCustomer {
            ont_serial: serial,
            port,
            distance_m,
            rx_power_dbm: rx_avg,
            rx_power_variance: rx_variance,
            eth_status,
            days_online,
            estimated_monthly_revenue: arpu,
        });
    }

    // Sort by estimated revenue descending (all same ARPU, so by days_online)
    results.sort_by(|a, b| {
        b.days_online
            .partial_cmp(&a.days_online)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
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
    fn test_ghost_no_traffic_flat_signal() {
        let now = Utc::now();
        // ONT online with eth_speed present but perfectly flat Rx power
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "GHOST02",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0), // perfectly flat — no variance
                    Some(1000),  // ethernet link present
                )
            })
            .collect();

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert_eq!(ghosts.len(), 1);
        assert_eq!(ghosts[0].ont_serial, "GHOST02");
        assert_eq!(ghosts[0].eth_status, GhostEthStatus::NoTraffic);
        assert!(ghosts[0].rx_power_variance < MAX_FLAT_VARIANCE);
    }

    #[test]
    fn test_ghost_excludes_active_customers() {
        let now = Utc::now();
        // ONT online with eth_speed and normal Rx variance (active customer)
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

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert!(
            ghosts.is_empty(),
            "Active customer with varying Rx should not be flagged as ghost"
        );
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
}
