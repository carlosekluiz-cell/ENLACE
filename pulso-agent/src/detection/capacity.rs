// SPDX-License-Identifier: Apache-2.0
// Splitter Capacity Predictor
//
// Predicts when PON splitters will run out of available ports based on
// current utilisation and growth trends from telemetry data.
//
// ISPs typically deploy 1:32 or 1:64 splitters. When a splitter fills up,
// new customers cannot be connected without a truck roll to install a
// new splitter — which can take weeks. Predicting capacity exhaustion
// ahead of time allows proactive splitter upgrades.
//
// Detection method:
//   1. Count unique ONT serials per port = active connections
//   2. Splitter type from operator topology when available; otherwise
//      INFERRED from count (≤32 ONTs → 1:32, else 1:64) and flagged
//      `splitter_assumed` — a real 1:64 with 20 subscribers would be
//      mis-modelled as 1:32, doubling the apparent utilisation
//   3. Growth rate: compare first vs last day unique ONT count
//   4. Extrapolate months to full capacity
//   5. Alert level based on utilisation % and time to full

use std::collections::{HashMap, HashSet};
use serde::{Deserialize, Serialize};

use super::{OntReading, PonTopology};

/// Capacity prediction for a single splitter / PON port.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SplitterCapacity {
    pub port: String,
    pub olt_id: String,
    pub splitter_type: String,
    pub max_ports: u32,
    pub active_onts: u32,
    pub utilisation_pct: f64,
    pub new_connections_per_month: f64,
    pub months_to_full: Option<f64>,
    pub alert_level: CapacityAlert,
    /// True when the splitter ratio was INFERRED from the subscriber count
    /// because no topology entry exists for this port. Utilisation figures
    /// may then be off by a factor of two (e.g. a real 1:64 modelled as
    /// 1:32) — treat the alert as advisory until the ratio is confirmed.
    pub splitter_assumed: bool,
}

/// Alert level for splitter capacity.
///
/// Derived ordering (Ok < Watch < Warning < Critical) lets the alert logic
/// take the max of the percentage tier and the absolute-headroom rule.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum CapacityAlert {
    /// Utilisation is acceptable and growth is manageable.
    Ok,
    /// Utilisation > 50% and will fill within 6 months.
    Watch,
    /// Utilisation > 75%, or 2 or fewer free ports remain.
    Warning,
    /// Utilisation > 90%.
    Critical,
}

impl std::fmt::Display for CapacityAlert {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Ok => write!(f, "ok"),
            Self::Watch => write!(f, "watch"),
            Self::Warning => write!(f, "warning"),
            Self::Critical => write!(f, "critical"),
        }
    }
}

/// Threshold above which a 1:64 splitter is inferred instead of 1:32.
const SPLITTER_32_MAX: u32 = 32;

/// Predict splitter capacity exhaustion without topology data (all splitter
/// ratios inferred from subscriber count and flagged as assumed). Prefer
/// [`predict_splitter_capacity_with_topology`] when the operator can supply
/// real splitter ratios.
pub fn predict_splitter_capacity(readings: &[OntReading]) -> Vec<SplitterCapacity> {
    predict_splitter_capacity_with_topology(readings, None)
}

/// Predict splitter capacity exhaustion for each PON port.
///
/// Groups ONT readings by port, counts unique serials, resolves the splitter
/// ratio (topology first, count-inference flagged as assumed otherwise),
/// calculates growth rate, and extrapolates time to full capacity.
pub fn predict_splitter_capacity_with_topology(
    readings: &[OntReading],
    topology: Option<&PonTopology>,
) -> Vec<SplitterCapacity> {
    // Group readings by port
    let mut by_port: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_port
            .entry(r.pon_port.clone())
            .or_default()
            .push(r);
    }

    let mut results = Vec::new();

    for (port, port_readings) in &by_port {
        if port_readings.is_empty() {
            continue;
        }

        // Count total unique ONT serials on this port
        let all_serials: HashSet<&str> = port_readings
            .iter()
            .map(|r| r.serial_number.as_str())
            .collect();
        let active_onts = all_serials.len() as u32;

        // Splitter ratio: topology first, count-inference as flagged fallback
        let configured_ratio = topology
            .and_then(|t| t.splitter_ratio_by_port.get(port.as_str()))
            .copied();
        let (splitter_type, max_ports, splitter_assumed) = match configured_ratio {
            Some(ratio) => (format!("1:{}", ratio), ratio, false),
            None if active_onts <= SPLITTER_32_MAX => ("1:32".to_string(), 32u32, true),
            None => ("1:64".to_string(), 64u32, true),
        };

        let utilisation_pct = (active_onts as f64 / max_ports as f64) * 100.0;

        // Calculate growth rate: compare unique ONTs on first day vs last day
        let mut sorted_readings: Vec<&&OntReading> = port_readings.iter().collect();
        sorted_readings.sort_by_key(|r| r.timestamp);

        let first_ts = sorted_readings.first().unwrap().timestamp;
        let last_ts = sorted_readings.last().unwrap().timestamp;
        let total_days = (last_ts - first_ts).num_seconds() as f64 / 86400.0;

        // Get unique serials on the first day (within 24h of first reading)
        let first_day_end = first_ts + chrono::Duration::hours(24);
        let first_day_serials: HashSet<&str> = port_readings
            .iter()
            .filter(|r| r.timestamp >= first_ts && r.timestamp < first_day_end)
            .map(|r| r.serial_number.as_str())
            .collect();

        // Get unique serials on the last day (within 24h before last reading)
        let last_day_start = last_ts - chrono::Duration::hours(24);
        let last_day_serials: HashSet<&str> = port_readings
            .iter()
            .filter(|r| r.timestamp > last_day_start && r.timestamp <= last_ts)
            .map(|r| r.serial_number.as_str())
            .collect();

        let first_count = first_day_serials.len() as f64;
        let last_count = last_day_serials.len() as f64;

        // Growth rate: new connections per month
        let new_per_month = if total_days > 0.0 {
            (last_count - first_count) / total_days * 30.0
        } else {
            0.0
        };

        // Months to full capacity
        let months_to_full = if new_per_month > 0.0 {
            let remaining = max_ports as f64 - active_onts as f64;
            Some(remaining / new_per_month)
        } else {
            None
        };

        // Alert level: percentage tiers
        let pct_alert = if utilisation_pct > 90.0 {
            CapacityAlert::Critical
        } else if utilisation_pct > 75.0 {
            CapacityAlert::Warning
        } else if utilisation_pct > 50.0 && months_to_full.map_or(false, |m| m < 6.0) {
            CapacityAlert::Watch
        } else {
            CapacityAlert::Ok
        };

        // Absolute-headroom rule: 2 or fewer free ports is at least a Warning
        // regardless of percentage. A 1:8 splitter at 6/8 is only 75% but has
        // just 2 ports left — one install away from a truck roll.
        let free_ports = max_ports.saturating_sub(active_onts);
        let headroom_alert = if free_ports <= 2 {
            CapacityAlert::Warning
        } else {
            CapacityAlert::Ok
        };

        let alert_level = pct_alert.max(headroom_alert);

        // Extract OLT ID from port string (e.g., "0/1/0" → OLT is implicit)
        let olt_id = port
            .split('/')
            .next()
            .unwrap_or("0")
            .to_string();

        results.push(SplitterCapacity {
            port: port.clone(),
            olt_id,
            splitter_type,
            max_ports,
            active_onts,
            utilisation_pct,
            new_connections_per_month: new_per_month,
            months_to_full,
            alert_level,
            splitter_assumed,
        });
    }

    // Sort by utilisation descending
    results.sort_by(|a, b| {
        b.utilisation_pct
            .partial_cmp(&a.utilisation_pct)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{DateTime, Duration, Utc};
    use super::super::OntReadingStatus;

    fn make_reading(
        serial: &str,
        port: &str,
        ts: DateTime<Utc>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: Some(-20.0),
            tx_power_dbm: None,
            status: OntReadingStatus::Online,
            distance_meters: Some(500),
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_capacity_nearly_full() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 30 ONTs on a 32-way splitter = 93.75% utilisation
        for i in 0..30 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, port, now - Duration::days(7)));
            readings.push(make_reading(&serial, port, now));
        }

        let caps = predict_splitter_capacity(&readings);
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].active_onts, 30);
        assert_eq!(caps[0].max_ports, 32);
        assert!(caps[0].utilisation_pct > 90.0);
        assert_eq!(caps[0].alert_level, CapacityAlert::Critical);
    }

    #[test]
    fn test_capacity_growing_fast() {
        let now = Utc::now();
        let port = "0/2/0";
        let mut readings = Vec::new();

        // Day 1: 10 ONTs online
        for i in 0..10 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, port, now - Duration::days(30)));
        }

        // Day 30: 20 ONTs online (10 new ones appeared)
        for i in 0..20 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, port, now));
        }

        let caps = predict_splitter_capacity(&readings);
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].active_onts, 20);
        assert!(
            caps[0].new_connections_per_month > 9.0,
            "Should detect ~10 new connections/month, got {}",
            caps[0].new_connections_per_month
        );
        // 20/32 = 62.5%, growing fast, months_to_full should be < 6
        assert!(caps[0].months_to_full.is_some());
        assert_eq!(caps[0].alert_level, CapacityAlert::Watch);
    }

    #[test]
    fn test_capacity_stable_ok() {
        let now = Utc::now();
        let port = "0/3/0";
        let mut readings = Vec::new();

        // 8 ONTs, stable over 30 days (same count first and last day)
        for i in 0..8 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, port, now - Duration::days(30)));
            readings.push(make_reading(&serial, port, now));
        }

        let caps = predict_splitter_capacity(&readings);
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].active_onts, 8);
        assert_eq!(caps[0].alert_level, CapacityAlert::Ok);
        // No growth → months_to_full should be None
        assert!(
            caps[0].months_to_full.is_none(),
            "Stable port with no growth should have no months_to_full"
        );
    }

    #[test]
    fn test_capacity_infers_splitter_type() {
        let now = Utc::now();
        let port_32 = "0/4/0";
        let port_64 = "0/5/0";
        let mut readings = Vec::new();

        // 20 ONTs → should infer 1:32
        for i in 0..20 {
            let serial = format!("ONT_A{:03}", i);
            readings.push(make_reading(&serial, port_32, now));
        }

        // 40 ONTs → should infer 1:64
        for i in 0..40 {
            let serial = format!("ONT_B{:03}", i);
            readings.push(make_reading(&serial, port_64, now));
        }

        let caps = predict_splitter_capacity(&readings);
        assert_eq!(caps.len(), 2);

        let cap_32 = caps.iter().find(|c| c.port == port_32).unwrap();
        let cap_64 = caps.iter().find(|c| c.port == port_64).unwrap();

        assert_eq!(cap_32.splitter_type, "1:32");
        assert_eq!(cap_32.max_ports, 32);
        assert!(cap_32.splitter_assumed, "count-inferred ratio must be flagged assumed");

        assert_eq!(cap_64.splitter_type, "1:64");
        assert_eq!(cap_64.max_ports, 64);
        assert!(cap_64.splitter_assumed, "count-inferred ratio must be flagged assumed");
    }

    /// Helper: n stable ONTs on `port` (same set on first and last day).
    fn stable_readings(n: u32, port: &str, prefix: &str) -> Vec<OntReading> {
        let now = Utc::now();
        let mut readings = Vec::new();
        for i in 0..n {
            let serial = format!("{}{:03}", prefix, i);
            readings.push(make_reading(&serial, port, now - Duration::days(30)));
            readings.push(make_reading(&serial, port, now));
        }
        readings
    }

    #[test]
    fn test_last_two_ports_rule_30_of_32_fires() {
        // 30/32 = 93.75%: Critical by percentage AND only 2 free ports.
        // The headroom rule must fire (>= Warning) and must NOT downgrade
        // the Critical percentage tier.
        let readings = stable_readings(30, "0/7/0", "ONT_H");
        let mut topo = super::super::PonTopology::default();
        topo.splitter_ratio_by_port.insert("0/7/0".to_string(), 32);

        let caps = predict_splitter_capacity_with_topology(&readings, Some(&topo));
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].max_ports - caps[0].active_onts, 2);
        assert!(
            caps[0].alert_level >= CapacityAlert::Warning,
            "2 free ports must fire at least Warning, got {}",
            caps[0].alert_level
        );
        assert_eq!(
            caps[0].alert_level,
            CapacityAlert::Critical,
            "critical-by-percentage must not be downgraded by the headroom rule"
        );
    }

    #[test]
    fn test_last_two_ports_rule_5_of_8_does_not_fire() {
        // 5/8 = 62.5% with 3 free ports and no growth: below every tier.
        let readings = stable_readings(5, "0/8/0", "ONT_I");
        let mut topo = super::super::PonTopology::default();
        topo.splitter_ratio_by_port.insert("0/8/0".to_string(), 8);

        let caps = predict_splitter_capacity_with_topology(&readings, Some(&topo));
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].max_ports - caps[0].active_onts, 3);
        assert_eq!(
            caps[0].alert_level,
            CapacityAlert::Ok,
            "3 free ports at 62.5% with no growth must stay Ok"
        );
    }

    #[test]
    fn test_last_two_ports_rule_6_of_8_fires() {
        // 6/8 = 75% exactly — the percentage tier (> 75%) does NOT fire,
        // but only 2 ports remain, so the headroom rule must raise Warning.
        let readings = stable_readings(6, "0/9/0", "ONT_J");
        let mut topo = super::super::PonTopology::default();
        topo.splitter_ratio_by_port.insert("0/9/0".to_string(), 8);

        let caps = predict_splitter_capacity_with_topology(&readings, Some(&topo));
        assert_eq!(caps.len(), 1);
        assert!((caps[0].utilisation_pct - 75.0).abs() < 0.01);
        assert_eq!(caps[0].max_ports - caps[0].active_onts, 2);
        assert_eq!(
            caps[0].alert_level,
            CapacityAlert::Warning,
            "2 free ports must be at least Warning even at exactly 75%"
        );
    }

    #[test]
    fn test_capacity_topology_overrides_inference() {
        // 20 ONTs would be inferred as a 1:32 splitter (62.5% utilisation),
        // but the operator topology says the port really has a 1:64 —
        // utilisation is actually 31.25% and nothing is assumed.
        let now = Utc::now();
        let port = "0/6/0";
        let mut readings = Vec::new();
        for i in 0..20 {
            let serial = format!("ONT_T{:03}", i);
            readings.push(make_reading(&serial, port, now));
        }

        let mut topo = super::super::PonTopology::default();
        topo.splitter_ratio_by_port.insert(port.to_string(), 64);

        let caps = predict_splitter_capacity_with_topology(&readings, Some(&topo));
        assert_eq!(caps.len(), 1);
        assert_eq!(caps[0].splitter_type, "1:64");
        assert_eq!(caps[0].max_ports, 64);
        assert!(!caps[0].splitter_assumed);
        assert!((caps[0].utilisation_pct - 31.25).abs() < 0.01);
    }
}
