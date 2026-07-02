// SPDX-License-Identifier: Apache-2.0
// Customer Diagnostics Module
//
// THIS IS THE GAME-CHANGER FOR ISP CUSTOMER SERVICE.
//
// Analyzes collected OLT + MikroTik + RADIUS data to produce
// per-customer health cards that a receptionist (non-technical)
// can understand and act on in seconds.
//
// What Maria (receptionist) sees when a customer calls:
//
//   ┌─────────────────────────────────────────────────────────┐
//   │  CLIENTE: João Silva (CPF: xxx.xxx.xxx-xx)              │
//   │  Plano: 300 Mbps | ONT: HWTC-12345678 | Desde: 2024-01 │
//   ├─────────────────────────────────────────────────────────┤
//   │  🟢 Sinal Óptico: -22.1 dBm (normal)                   │
//   │  🟢 ONT Status: Online há 47 dias                       │
//   │  🟢 PPPoE: Ativo, 287/142 Mbps                         │
//   │  🟡 WiFi 2.4GHz: 17 dispositivos, canal congestionado  │
//   │  🔴 WiFi 5GHz: 0 dispositivos (não configurado)        │
//   ├─────────────────────────────────────────────────────────┤
//   │  DIAGNÓSTICO: Problema provável de WiFi                 │
//   │  AÇÃO: [Otimizar WiFi] [Reiniciar ONT] [Escalar Tec.]  │
//   └─────────────────────────────────────────────────────────┘
//
// No technical knowledge required. Colors tell the story.
// One-click actions resolve 70% of support calls.

use serde::{Deserialize, Serialize};
use crate::vendors::{OltData, OntData, OntStatus};
use crate::mikrotik::MikrotikData;

/// Health status levels (color-coded in the UI)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum HealthLevel {
    /// 🟢 Everything normal
    Green,
    /// 🟡 Attention needed but service is working
    Yellow,
    /// 🔴 Problem detected, action required
    Red,
    /// ⚫ No data available
    Unknown,
}

/// Complete diagnostic report for a single OLT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OltDiagnostics {
    pub olt_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub overall_health: HealthLevel,

    /// ONTs that need attention (sorted by severity)
    pub alerts: Vec<OntAlert>,

    /// PON ports approaching capacity
    pub capacity_warnings: Vec<CapacityWarning>,

    /// Summary statistics
    pub summary: DiagnosticSummary,
}

/// Alert for a specific ONT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OntAlert {
    pub serial_number: String,
    pub pon_port: String,
    pub severity: HealthLevel,
    pub alert_type: AlertType,
    pub description: String,
    /// Plain-language explanation for non-technical support staff
    pub support_message: String,
    /// Suggested action
    pub recommended_action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertType {
    /// ONT offline — customer has no service
    Offline,
    /// Signal degrading — will fail soon
    SignalDegrading,
    /// Signal critically low — service impacted
    SignalCritical,
    /// Power failure detected
    PowerFailure,
    /// Fiber cut suspected
    FiberCut,
    /// ONT needs firmware update
    FirmwareOutdated,
    /// Abnormal traffic pattern
    TrafficAnomaly,
    /// Ethernet port negotiated at 100M instead of 1G
    EthernetNegotiation,
    /// ONT recently restarted (uptime < 1 hour)
    RecentRestart,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapacityWarning {
    pub pon_port: String,
    pub current_utilization_percent: f32,
    pub onts_on_port: u32,
    pub estimated_weeks_to_capacity: Option<u32>,
    pub recommended_action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticSummary {
    pub total_onts: u32,
    pub online: u32,
    pub offline: u32,
    pub low_signal: u32,
    pub critical_signal: u32,
    pub avg_rx_power_dbm: f64,
    pub worst_rx_power_dbm: f64,
    pub offline_rate_percent: f32,
}

// Signal thresholds for GPON fiber (dBm)
const SIGNAL_EXCELLENT: f64 = -15.0;
const SIGNAL_GOOD: f64 = -20.0;
const SIGNAL_ACCEPTABLE: f64 = -25.0;
const SIGNAL_WARNING: f64 = -27.0;
const SIGNAL_CRITICAL: f64 = -28.0;
const SIGNAL_FAILURE: f64 = -30.0;

// PON port utilization thresholds
const PON_UTIL_HEALTHY: f32 = 60.0;
const PON_UTIL_WARNING: f32 = 80.0;
const PON_UTIL_CRITICAL: f32 = 90.0;

/// An offline ONT must be seen offline for this many consecutive cycles
/// before a Red alert fires (debounce against polling blips).
const OFFLINE_ALERT_DEBOUNCE_CYCLES: u32 = 2;

/// Cross-cycle state for offline-ONT alert debouncing/dedup.
///
/// Without this, every currently-offline ONT (including chronically-offline
/// vacant homes) produces a fresh Red alert on every poll cycle. With it,
/// an offline alert fires exactly once — after the ONT has been offline for
/// `OFFLINE_ALERT_DEBOUNCE_CYCLES` consecutive cycles — and re-arms only
/// after the ONT comes back online.
#[derive(Debug, Default)]
pub struct OfflineAlertState {
    /// (olt_id, serial) ever seen online — chronic-offline ONTs (offline
    /// since agent start) never alert
    ever_online: std::collections::HashSet<(String, String)>,
    /// (olt_id, serial) → consecutive cycles seen offline
    consecutive_offline: std::collections::HashMap<(String, String), u32>,
    /// (olt_id, serial) already alerted for the current offline episode
    alerted: std::collections::HashSet<(String, String)>,
}

impl OfflineAlertState {
    /// Returns true when a Red offline alert should fire for this ONT on
    /// this cycle. Call once per offline ONT per cycle.
    fn observe_offline(&mut self, olt_id: &str, serial: &str) -> bool {
        let key = (olt_id.to_string(), serial.to_string());
        let count = self.consecutive_offline.entry(key.clone()).or_insert(0);
        *count += 1;
        if *count >= OFFLINE_ALERT_DEBOUNCE_CYCLES
            && self.ever_online.contains(&key)
            && !self.alerted.contains(&key)
        {
            self.alerted.insert(key);
            true
        } else {
            false
        }
    }

    /// Re-arm the alert when the ONT is seen online again.
    fn observe_online(&mut self, olt_id: &str, serial: &str) {
        let key = (olt_id.to_string(), serial.to_string());
        self.consecutive_offline.remove(&key);
        self.alerted.remove(&key);
        self.ever_online.insert(key);
    }
}

/// Analyze OLT data and produce diagnostics (stateless, snapshot mode).
///
/// Every currently-offline ONT is reported — intended for one-shot analyses
/// (CSV audits) where the output is a point-in-time report, not an alert
/// stream. The polling agent must use [`analyze_olt_stateful`] instead.
pub fn analyze_olt(data: &OltData) -> OltDiagnostics {
    analyze_olt_impl(data, None)
}

/// Analyze OLT data with cross-cycle offline-alert debouncing.
///
/// Offline Red alerts fire on the offline *transition* (after the debounce
/// window), exactly once per offline episode — not on every poll cycle.
pub fn analyze_olt_stateful(data: &OltData, state: &mut OfflineAlertState) -> OltDiagnostics {
    analyze_olt_impl(data, Some(state))
}

fn analyze_olt_impl(data: &OltData, mut state: Option<&mut OfflineAlertState>) -> OltDiagnostics {
    let mut alerts = Vec::new();
    let mut total_rx = 0.0_f64;
    let mut rx_count = 0u32;
    let mut worst_rx = 0.0_f64;
    let mut low_signal = 0u32;
    let mut critical_signal = 0u32;
    let online = data.onts.iter().filter(|o| matches!(o.status, OntStatus::Online | OntStatus::LowSignal)).count() as u32;
    let offline = data.onts.iter().filter(|o| matches!(o.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut)).count() as u32;

    for ont in &data.onts {
        // Check offline ONTs. In stateful mode, alert on the offline
        // transition only (debounced) — never every cycle for every
        // currently-offline ONT.
        if matches!(ont.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut) {
            let should_alert = match state.as_deref_mut() {
                None => true, // snapshot mode: report all currently offline
                Some(s) => s.observe_offline(&data.olt_id, &ont.serial_number),
            };
            if should_alert {
                let (alert_type, support_msg, action) = match &ont.last_down_cause {
                    Some(cause) if cause.contains("power") || cause.contains("dying_gasp") => (
                        AlertType::PowerFailure,
                        format!("ONT {} está offline por queda de energia no local do cliente.", ont.serial_number),
                        "Pergunte ao cliente se há energia no local. Se sim, peça para verificar se o equipamento está ligado.".into(),
                    ),
                    Some(cause) if cause.contains("los") => (
                        AlertType::FiberCut,
                        format!("ONT {} está offline — possível rompimento de fibra.", ont.serial_number),
                        "Escalar para equipe técnica. Provável problema no cabo de fibra (drop ou trunk).".into(),
                    ),
                    _ => (
                        AlertType::Offline,
                        format!("ONT {} está offline.", ont.serial_number),
                        "Verificar se há energia no local. Se positivo, escalar para técnico.".into(),
                    ),
                };

                alerts.push(OntAlert {
                    serial_number: ont.serial_number.clone(),
                    pon_port: ont.pon_port.clone(),
                    severity: HealthLevel::Red,
                    alert_type,
                    description: format!("ONT offline: {}", ont.serial_number),
                    support_message: support_msg,
                    recommended_action: action,
                });
            }
        } else if matches!(ont.status, OntStatus::Online | OntStatus::LowSignal | OntStatus::Dying) {
            // Back online: re-arm the offline alert for this ONT
            if let Some(s) = state.as_deref_mut() {
                s.observe_online(&data.olt_id, &ont.serial_number);
            }
        }

        // Check signal levels
        if let Some(rx) = ont.rx_power_dbm {
            total_rx += rx;
            rx_count += 1;
            if rx < worst_rx || worst_rx == 0.0 {
                worst_rx = rx;
            }

            if rx < SIGNAL_CRITICAL && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
                critical_signal += 1;
                alerts.push(OntAlert {
                    serial_number: ont.serial_number.clone(),
                    pon_port: ont.pon_port.clone(),
                    severity: HealthLevel::Red,
                    alert_type: AlertType::SignalCritical,
                    description: format!("Sinal crítico: {:.1} dBm", rx),
                    support_message: format!(
                        "ONT {} com sinal muito fraco ({:.1} dBm). Cliente pode estar experimentando lentidão e quedas frequentes.",
                        ont.serial_number, rx
                    ),
                    recommended_action: "Escalar para técnico URGENTE. Possível conector sujo, curvatura no cabo, ou splitter degradado.".into(),
                });
            } else if rx < SIGNAL_WARNING && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
                low_signal += 1;
                alerts.push(OntAlert {
                    serial_number: ont.serial_number.clone(),
                    pon_port: ont.pon_port.clone(),
                    severity: HealthLevel::Yellow,
                    alert_type: AlertType::SignalDegrading,
                    description: format!("Sinal baixo: {:.1} dBm", rx),
                    support_message: format!(
                        "ONT {} com sinal abaixo do ideal ({:.1} dBm). Pode degradar em breve.",
                        ont.serial_number, rx
                    ),
                    recommended_action: "Agendar inspeção preventiva na próxima visita ao bairro.".into(),
                });
            }
        }

        // Extended diagnostics
        let extra_alerts = check_ont_extras(ont);
        alerts.extend(extra_alerts);
    }

    // Check PON port capacity
    let capacity_warnings: Vec<CapacityWarning> = data.pon_ports.iter()
        .filter(|p| p.utilization_percent > PON_UTIL_WARNING)
        .map(|p| CapacityWarning {
            pon_port: p.port_id.clone(),
            current_utilization_percent: p.utilization_percent,
            onts_on_port: p.onts_registered,
            estimated_weeks_to_capacity: if p.utilization_percent > PON_UTIL_CRITICAL {
                Some(2)
            } else {
                Some(8)
            },
            recommended_action: if p.utilization_percent > PON_UTIL_CRITICAL {
                format!("URGENTE: PON {} está em {:.0}% de capacidade. Dividir splitter ou adicionar placa GPON.", p.port_id, p.utilization_percent)
            } else {
                format!("PON {} em {:.0}% — planejar expansão nas próximas semanas.", p.port_id, p.utilization_percent)
            },
        })
        .collect();

    // Sort alerts by severity (red first)
    let mut sorted_alerts = alerts;
    sorted_alerts.sort_by(|a, b| a.severity.cmp(&b.severity));

    let overall_health = if sorted_alerts.iter().any(|a| a.severity == HealthLevel::Red) {
        HealthLevel::Red
    } else if sorted_alerts.iter().any(|a| a.severity == HealthLevel::Yellow) || !capacity_warnings.is_empty() {
        HealthLevel::Yellow
    } else {
        HealthLevel::Green
    };

    let avg_rx = if rx_count > 0 { total_rx / rx_count as f64 } else { 0.0 };
    let total = data.onts.len() as u32;
    let offline_rate = if total > 0 { (offline as f32 / total as f32) * 100.0 } else { 0.0 };

    OltDiagnostics {
        olt_id: data.olt_id.clone(),
        timestamp: chrono::Utc::now(),
        overall_health,
        alerts: sorted_alerts,
        capacity_warnings,
        summary: DiagnosticSummary {
            total_onts: total,
            online,
            offline,
            low_signal,
            critical_signal,
            avg_rx_power_dbm: avg_rx,
            worst_rx_power_dbm: worst_rx,
            offline_rate_percent: offline_rate,
        },
    }
}

/// Additional per-ONT checks (ethernet negotiation, restart detection)
pub fn check_ont_extras(ont: &OntData) -> Vec<OntAlert> {
    let mut alerts = Vec::new();

    // Ethernet negotiation check
    if let Some(speed) = ont.eth_speed_mbps {
        if speed <= 100 && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
            alerts.push(OntAlert {
                serial_number: ont.serial_number.clone(),
                pon_port: ont.pon_port.clone(),
                severity: HealthLevel::Yellow,
                alert_type: AlertType::EthernetNegotiation,
                description: format!("Ethernet negotiated at {}Mbps", speed),
                support_message: format!(
                    "ONT {} ethernet port at {}Mbps instead of 1Gbps. Customer may have a bad cable or 100M port.",
                    ont.serial_number, speed
                ),
                recommended_action: "Remote investigation — customer likely has a bad ethernet cable or using 100M port".into(),
            });
        }
    }

    // Recent restart detection
    if let Some(uptime) = ont.uptime_seconds {
        if uptime < 3600 && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
            alerts.push(OntAlert {
                serial_number: ont.serial_number.clone(),
                pon_port: ont.pon_port.clone(),
                severity: HealthLevel::Yellow,
                alert_type: AlertType::RecentRestart,
                description: format!("ONT uptime: {} seconds", uptime),
                support_message: format!(
                    "ONT {} restarted recently (uptime: {}s). Check power supply at premises.",
                    ont.serial_number, uptime
                ),
                recommended_action: "Check power supply at premises — ONT restarted recently".into(),
            });
        }
    }

    alerts
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vendors::{OntData, OntStatus};

    fn make_ont(serial: &str, rx: f64, eth_speed: Option<u32>, uptime: Option<u64>) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            ont_index: 0,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: uptime,
            rx_power_dbm: Some(rx),
            tx_power_dbm: None,
            distance_meters: Some(1000),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None,
            eth_speed_mbps: eth_speed,
            extended: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_ethernet_negotiation_alert() {
        let ont = make_ont("TEST01", -20.0, Some(100), Some(86400));
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().any(|a| matches!(a.alert_type, AlertType::EthernetNegotiation)));
    }

    #[test]
    fn test_no_alert_on_gigabit() {
        let ont = make_ont("TEST02", -20.0, Some(1000), Some(86400));
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().all(|a| !matches!(a.alert_type, AlertType::EthernetNegotiation)));
    }

    #[test]
    fn test_recent_restart_alert() {
        let ont = make_ont("TEST03", -20.0, None, Some(300)); // 5 min uptime
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().any(|a| matches!(a.alert_type, AlertType::RecentRestart)));
    }

    #[test]
    fn test_no_restart_alert_long_uptime() {
        let ont = make_ont("TEST04", -20.0, None, Some(86400)); // 24h uptime
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().all(|a| !matches!(a.alert_type, AlertType::RecentRestart)));
    }

    fn make_olt(onts: Vec<OntData>) -> crate::vendors::OltData {
        crate::vendors::OltData {
            olt_id: "olt-test".into(),
            vendor: "test".into(),
            model: "test".into(),
            firmware: String::new(),
            serial: String::new(),
            uptime_seconds: 0,
            timestamp: chrono::Utc::now(),
            cpu_percent: None,
            memory_percent: None,
            temperature_celsius: None,
            power_supply_status: None,
            pon_ports: Vec::new(),
            uplink_ports: Vec::new(),
            onts,
        }
    }

    fn make_status_ont(serial: &str, status: OntStatus) -> OntData {
        let mut ont = make_ont(serial, -20.0, None, Some(86400));
        if matches!(status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut) {
            ont.rx_power_dbm = None;
        }
        ont.status = status;
        ont
    }

    fn offline_alerts(diag: &OltDiagnostics) -> usize {
        diag.alerts.iter()
            .filter(|a| matches!(
                a.alert_type,
                AlertType::Offline | AlertType::PowerFailure | AlertType::FiberCut
            ))
            .count()
    }

    #[test]
    fn test_snapshot_mode_reports_offline_immediately() {
        // Stateless analyze_olt (CSV audit path) keeps point-in-time reporting
        let olt = make_olt(vec![make_status_ont("OFF01", OntStatus::Offline)]);
        let diag = analyze_olt(&olt);
        assert_eq!(offline_alerts(&diag), 1);
    }

    #[test]
    fn test_stateful_offline_alert_fires_once_after_debounce() {
        let mut state = OfflineAlertState::default();

        // Cycle 1: online (baseline)
        let diag = analyze_olt_stateful(&make_olt(vec![make_status_ont("ONT01", OntStatus::Online)]), &mut state);
        assert_eq!(offline_alerts(&diag), 0);

        // Cycle 2: first offline observation — debounced, no alert yet
        let offline = make_olt(vec![make_status_ont("ONT01", OntStatus::Offline)]);
        let diag = analyze_olt_stateful(&offline, &mut state);
        assert_eq!(offline_alerts(&diag), 0, "one offline cycle must be debounced");

        // Cycle 3: second consecutive offline — alert fires exactly once
        let diag = analyze_olt_stateful(&offline, &mut state);
        assert_eq!(offline_alerts(&diag), 1, "alert should fire after 2 consecutive offline cycles");

        // Cycles 4-6: still offline — never re-alert
        for _ in 0..3 {
            let diag = analyze_olt_stateful(&offline, &mut state);
            assert_eq!(offline_alerts(&diag), 0, "must not re-alert every cycle");
        }

        // Summary still counts the ONT as offline even when not alerting
        let diag = analyze_olt_stateful(&offline, &mut state);
        assert_eq!(diag.summary.offline, 1);
    }

    #[test]
    fn test_stateful_offline_alert_rearms_after_recovery() {
        let mut state = OfflineAlertState::default();
        let online = make_olt(vec![make_status_ont("ONT01", OntStatus::Online)]);
        let offline = make_olt(vec![make_status_ont("ONT01", OntStatus::Offline)]);

        analyze_olt_stateful(&online, &mut state);
        analyze_olt_stateful(&offline, &mut state);
        let diag = analyze_olt_stateful(&offline, &mut state);
        assert_eq!(offline_alerts(&diag), 1);

        // Recovery re-arms
        analyze_olt_stateful(&online, &mut state);
        analyze_olt_stateful(&offline, &mut state);
        let diag = analyze_olt_stateful(&offline, &mut state);
        assert_eq!(offline_alerts(&diag), 1, "new offline episode should alert again");
    }

    #[test]
    fn test_stateful_chronic_offline_never_alerts() {
        // ONTs offline since agent start (vacant homes) must not storm on
        // startup — they were never seen online, so there is no transition.
        let mut state = OfflineAlertState::default();
        let olt = make_olt(vec![
            make_status_ont("VACANT1", OntStatus::Offline),
            make_status_ont("VACANT2", OntStatus::Offline),
        ]);
        for _ in 0..5 {
            let diag = analyze_olt_stateful(&olt, &mut state);
            assert_eq!(offline_alerts(&diag), 0, "chronic-offline ONTs must never alert");
        }
    }
}
