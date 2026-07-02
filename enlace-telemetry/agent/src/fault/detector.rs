// SPDX-License-Identifier: Apache-2.0
// Mass-offline pattern detector

use std::collections::HashMap;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use crate::config::FaultDetectionConfig;
use crate::vendors::{OntData, OntStatus};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultEvent {
    pub timestamp: DateTime<Utc>,
    pub pon_port: String,
    pub olt_id: String,
    pub severity: String,
    pub fault_type: FaultType,
    pub affected_onts: Vec<AffectedOnt>,
    pub detection_latency_seconds: u64,
}

/// Fault classification based on dying gasp differentiation.
/// - FibreCut: ONTs went offline without sending dying gasp → physical fibre break
/// - PowerOutage: ONTs sent dying gasp before going offline → power loss at premises/area
/// - Mixed: Some ONTs sent dying gasp, others didn't → partial power + possible break
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FaultType {
    FibreCut,
    PowerOutage,
    Mixed,
}

impl std::fmt::Display for FaultType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::FibreCut => write!(f, "fibre_cut"),
            Self::PowerOutage => write!(f, "power_outage"),
            Self::Mixed => write!(f, "mixed"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectedOnt {
    pub serial_number: String,
    pub distance_meters: Option<u32>,
    pub last_rx_dbm: Option<f64>,
    /// True if this ONT sent a dying gasp (power failure)
    pub had_dying_gasp: bool,
}

pub struct FaultDetector {
    config: FaultDetectionConfig,
    previous_state: HashMap<String, HashMap<String, bool>>,
}

impl FaultDetector {
    pub fn new(config: &FaultDetectionConfig) -> Self {
        Self {
            config: config.clone(),
            previous_state: HashMap::new(),
        }
    }

    pub fn check(&mut self, onts: &[OntData]) -> Vec<FaultEvent> {
        if !self.config.enabled {
            return Vec::new();
        }

        let mut events = Vec::new();

        // Group ONTs by PON port
        let mut by_port: HashMap<String, Vec<&OntData>> = HashMap::new();
        for ont in onts {
            by_port.entry(ont.pon_port.clone()).or_default().push(ont);
        }

        for (port, port_onts) in &by_port {
            // Count hard-offline ONTs (exclude dying-gasp = power failure)
            let hard_offline: Vec<&OntData> = port_onts.iter()
                .filter(|o| {
                    matches!(o.status, OntStatus::Offline | OntStatus::FiberCut)
                        && !o.last_down_cause.as_deref()
                            .map(|c| c.contains("dying_gasp") || c.contains("power"))
                            .unwrap_or(false)
                })
                .copied()
                .collect();

            if hard_offline.len() >= self.config.min_offline_onts {
                let severity = if hard_offline.len() >= self.config.severity.critical {
                    "critical"
                } else if hard_offline.len() >= self.config.severity.major {
                    "major"
                } else if hard_offline.len() >= self.config.severity.minor {
                    "minor"
                } else {
                    "warning"
                };

                // Also count dying-gasp ONTs on this port for fault classification
                let dying_gasp_onts: Vec<&OntData> = port_onts.iter()
                    .filter(|o| {
                        o.last_down_cause.as_deref()
                            .map(|c| c.contains("dying_gasp") || c.contains("power"))
                            .unwrap_or(false)
                    })
                    .copied()
                    .collect();

                // Classify: if dying_gasp ONTs also offline → power outage
                // If only hard-offline (no dying gasp) → fibre cut
                let fault_type = if !dying_gasp_onts.is_empty() && hard_offline.is_empty() {
                    FaultType::PowerOutage
                } else if dying_gasp_onts.is_empty() {
                    FaultType::FibreCut
                } else {
                    FaultType::Mixed
                };

                let mut affected: Vec<AffectedOnt> = hard_offline.iter().map(|o| AffectedOnt {
                    serial_number: o.serial_number.clone(),
                    distance_meters: o.distance_meters,
                    last_rx_dbm: o.rx_power_dbm,
                    had_dying_gasp: false,
                }).collect();

                // Include dying-gasp ONTs in the affected list for Mixed events
                if fault_type == FaultType::Mixed {
                    for o in &dying_gasp_onts {
                        affected.push(AffectedOnt {
                            serial_number: o.serial_number.clone(),
                            distance_meters: o.distance_meters,
                            last_rx_dbm: o.rx_power_dbm,
                            had_dying_gasp: true,
                        });
                    }
                }

                events.push(FaultEvent {
                    timestamp: Utc::now(),
                    pon_port: port.clone(),
                    olt_id: String::new(),
                    severity: severity.into(),
                    fault_type,
                    affected_onts: affected,
                    detection_latency_seconds: 0,
                });
            }
        }

        self.previous_state.clear();
        for ont in onts {
            let is_online = matches!(ont.status, OntStatus::Online | OntStatus::LowSignal);
            self.previous_state
                .entry(ont.pon_port.clone())
                .or_default()
                .insert(ont.serial_number.clone(), is_online);
        }

        events
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_config() -> FaultDetectionConfig {
        FaultDetectionConfig {
            enabled: true,
            min_offline_onts: 5,
            time_window_seconds: 60,
            severity: crate::config::FaultSeverityConfig {
                critical: 100, major: 50, minor: 10,
            },
        }
    }

    fn make_ont(serial: &str, port: &str, status: OntStatus, dying_gasp: bool) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: port.into(),
            ont_index: 0,
            status,
            last_down_cause: if dying_gasp { Some("dying_gasp".into()) } else { None },
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: Some(1000),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None, extended: None,
        }
    }

    #[test]
    fn test_trigger_on_mass_offline() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..10 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false));
        }
        for i in 10..20 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Online, false));
        }
        let events = detector.check(&onts);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].pon_port, "0/1/0");
        assert_eq!(events[0].affected_onts.len(), 10);
        assert_eq!(events[0].fault_type, FaultType::FibreCut);
    }

    #[test]
    fn test_no_trigger_below_threshold() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..3 { onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        for i in 3..20 { onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Online, false)); }
        let events = detector.check(&onts);
        assert!(events.is_empty());
    }

    #[test]
    fn test_dying_gasp_excluded() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..10 { onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::PowerFail, true)); }
        let events = detector.check(&onts);
        assert!(events.is_empty());
    }

    #[test]
    fn test_mixed_dying_gasp_and_hard_offline() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..3 { onts.push(make_ont(&format!("DG{:03}", i), "0/1/0", OntStatus::PowerFail, true)); }
        for i in 0..6 { onts.push(make_ont(&format!("HO{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        let events = detector.check(&onts);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].fault_type, FaultType::Mixed);
        // Mixed events include both hard-offline (6) and dying-gasp (3) ONTs
        assert_eq!(events[0].affected_onts.len(), 9);
        let dying_gasp_count = events[0].affected_onts.iter().filter(|o| o.had_dying_gasp).count();
        assert_eq!(dying_gasp_count, 3);
    }

    #[test]
    fn test_severity_classification() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..120 { onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        let events = detector.check(&onts);
        assert_eq!(events[0].severity, "critical");
    }

    #[test]
    fn test_per_port_isolation() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut onts = Vec::new();
        for i in 0..3 { onts.push(make_ont(&format!("A{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        for i in 0..3 { onts.push(make_ont(&format!("B{:03}", i), "0/1/1", OntStatus::Offline, false)); }
        let events = detector.check(&onts);
        assert!(events.is_empty());
    }
}
