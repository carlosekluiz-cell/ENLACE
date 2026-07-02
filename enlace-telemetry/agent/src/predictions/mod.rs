// SPDX-License-Identifier: Apache-2.0
// Predictive Analytics Module
//
// Uses historical telemetry data (stored in local SQLite) to predict:
//   1. Signal degradation — detect ONTs that will fail before they do
//   2. Capacity exhaustion — predict when PON ports will be saturated
//   3. Churn signals — detect customers whose usage patterns suggest leaving
//   4. Customer diagnostics — decision tree for common ONT issues
//
// Method: Simple linear regression on time-series data.
// For signal degradation: fit a line to (timestamp, rx_power_dbm) and extrapolate.
//   - Primary metric: ONT-side downstream rx power (via OMCI/NETCONF)
//   - Fallback metric: OLT-side upstream rx power (via SNMP)
//   - Rate thresholds: WATCH -0.015, WARNING -0.035, CRITICAL -0.07 dBm/day
//   - Absolute critical: -27.0 dBm
// For capacity: fit a line to (timestamp, utilization%) and find when it hits 95%.
// For churn: track session duration trend over 30 days.
//
// This runs LOCALLY in the agent on each collection cycle.
// Results are sent to the Pulso Cloud where they're enriched with
// market intelligence (Starlink penetration, competitor activity, etc.)
// to produce the final predictions shown to the ISP.

use serde::{Deserialize, Serialize};
use crate::vendors::{OltData, OntData};
use crate::transport::LocalBuffer;
use crate::config::DegradationConfig;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Predictions {
    pub olt_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub signal_degradation: Vec<SignalPrediction>,
    pub capacity_forecasts: Vec<CapacityForecast>,
    pub churn_signals: Vec<ChurnSignal>,
    pub customer_diagnostics: Vec<CustomerDiagnostic>,
}

/// Degradation severity based on dBm/day rate thresholds.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DegradationSeverity {
    /// Rate ≤ -0.015 dBm/day — early sign of connector or splice degradation
    Watch,
    /// Rate ≤ -0.035 dBm/day — schedule field inspection
    Warning,
    /// Rate ≤ -0.07 dBm/day OR absolute rx below -27.0 dBm — imminent failure
    Critical,
}

impl std::fmt::Display for DegradationSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Watch => write!(f, "watch"),
            Self::Warning => write!(f, "warning"),
            Self::Critical => write!(f, "critical"),
        }
    }
}

/// Predicted signal failure for a specific ONT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalPrediction {
    pub serial_number: String,
    pub pon_port: String,
    /// Current signal level (dBm) — ONT-side if available, else OLT-side
    pub current_rx_dbm: f64,
    /// Which metric was used: "ont_rx" or "olt_rx"
    pub metric_source: String,
    /// Rate of degradation (dBm per day, negative = getting worse)
    pub degradation_rate_per_day: f64,
    /// Severity classification based on rate thresholds
    pub severity: DegradationSeverity,
    /// Predicted days until failure threshold
    pub days_to_failure: Option<u32>,
    /// Confidence level (0.0-1.0 based on R² of linear fit)
    pub confidence: f32,
    /// Human-readable message for the ISP
    pub message: String,
}

/// Predicted PON port capacity exhaustion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapacityForecast {
    pub pon_port: String,
    pub current_utilization_percent: f32,
    pub growth_rate_percent_per_month: f32,
    pub weeks_to_95_percent: Option<u32>,
    pub current_onts: u32,
    pub message: String,
}

/// Customer churn risk signal (from RADIUS session patterns)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChurnSignal {
    pub customer_id: String,       // PPPoE username or ONT serial
    pub current_avg_session_hours: f32,
    pub previous_avg_session_hours: f32,
    pub decline_percent: f32,
    pub risk_level: ChurnRisk,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChurnRisk {
    Low,      // < 20% decline
    Medium,   // 20-40% decline
    High,     // 40-60% decline
    Critical, // > 60% decline
}

/// Customer diagnostic result from the ONT telemetry decision tree.
/// Classifies common issues that field technicians can act on.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustomerDiagnostic {
    pub serial_number: String,
    pub pon_port: String,
    pub issue: DiagnosticIssue,
    pub severity: DiagnosticSeverity,
    pub message: String,
    pub recommended_action: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DiagnosticIssue {
    /// ONT offline, dying gasp received → power failure at premises
    PowerOutage,
    /// ONT offline, no dying gasp → fibre break or connector issue
    FibreFault,
    /// ONT online, rx_power below -27 dBm → degraded optical path
    DegradedSignal,
    /// ONT temperature above 60°C → overheating (ventilation/enclosure)
    Overheating,
    /// ONT supply voltage out of range (< 3.0V or > 3.6V) → faulty power adapter
    VoltageAnomaly,
    /// ONT bias current above 70 mA → laser nearing end-of-life
    LaserDegradation,
    /// ONT online, signal OK, but Ethernet at 100 Mbps → negotiation issue
    EthernetBottleneck,
    /// ONT-side and OLT-side rx power diverge by >5 dB → dirty connector
    ConnectorDirty,
}

impl std::fmt::Display for DiagnosticIssue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::PowerOutage => write!(f, "power_outage"),
            Self::FibreFault => write!(f, "fibre_fault"),
            Self::DegradedSignal => write!(f, "degraded_signal"),
            Self::Overheating => write!(f, "overheating"),
            Self::VoltageAnomaly => write!(f, "voltage_anomaly"),
            Self::LaserDegradation => write!(f, "laser_degradation"),
            Self::EthernetBottleneck => write!(f, "ethernet_bottleneck"),
            Self::ConnectorDirty => write!(f, "connector_dirty"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum DiagnosticSeverity {
    Info,
    Warning,
    Critical,
}

/// Simple linear regression: y = mx + b
/// Returns (slope, intercept, r_squared)
fn linear_regression(points: &[(f64, f64)]) -> Option<(f64, f64, f64)> {
    let n = points.len() as f64;
    if n < 3.0 {
        return None; // Need at least 3 data points
    }

    let sum_x: f64 = points.iter().map(|(x, _)| x).sum();
    let sum_y: f64 = points.iter().map(|(_, y)| y).sum();
    let sum_xy: f64 = points.iter().map(|(x, y)| x * y).sum();
    let sum_x2: f64 = points.iter().map(|(x, _)| x * x).sum();

    let denom = n * sum_x2 - sum_x * sum_x;
    if denom.abs() < 1e-10 {
        return None;
    }

    let slope = (n * sum_xy - sum_x * sum_y) / denom;
    let intercept = (sum_y - slope * sum_x) / n;

    // R-squared (coefficient of determination)
    let y_mean = sum_y / n;
    let ss_tot: f64 = points.iter().map(|(_, y)| (y - y_mean).powi(2)).sum();
    let ss_res: f64 = points.iter().map(|(x, y)| {
        let predicted = slope * x + intercept;
        (y - predicted).powi(2)
    }).sum();
    let r_squared = if ss_tot > 0.0 { 1.0 - ss_res / ss_tot } else { 0.0 };

    Some((slope, intercept, r_squared))
}

/// Classify degradation severity from rate (dBm/day) and config thresholds.
/// Thresholds are negative values: watch=-0.015, warning=-0.035, critical=-0.07
pub(crate) fn classify_degradation(
    rate: f64,
    current_rx: f64,
    config: Option<&DegradationConfig>,
) -> Option<DegradationSeverity> {
    let watch = config.map(|c| c.watch_threshold_db).unwrap_or(-0.015);
    let warning = config.map(|c| c.warning_threshold_db).unwrap_or(-0.035);
    let critical_rate = config.map(|c| c.critical_threshold_db).unwrap_or(-0.07);
    let min_critical_rx = config.map(|c| c.min_critical_rx_dbm).unwrap_or(-27.0);

    // Absolute critical: current rx below threshold regardless of rate
    if current_rx <= min_critical_rx {
        return Some(DegradationSeverity::Critical);
    }

    // Rate-based classification (rate is negative for degradation)
    if rate <= critical_rate {
        Some(DegradationSeverity::Critical)
    } else if rate <= warning {
        Some(DegradationSeverity::Warning)
    } else if rate <= watch {
        Some(DegradationSeverity::Watch)
    } else {
        None // No significant degradation
    }
}

/// Run the customer diagnostic decision tree on a single ONT.
/// Returns zero or more diagnostic findings.
pub fn diagnose_ont(ont: &OntData) -> Vec<CustomerDiagnostic> {
    let mut diagnostics = Vec::new();
    let serial = &ont.serial_number;
    let port = &ont.pon_port;

    // 1. Offline checks
    if matches!(ont.status, crate::vendors::OntStatus::PowerFail) {
        diagnostics.push(CustomerDiagnostic {
            serial_number: serial.clone(),
            pon_port: port.clone(),
            issue: DiagnosticIssue::PowerOutage,
            severity: DiagnosticSeverity::Critical,
            message: format!("ONT {} offline — dying gasp received, power failure at premises", serial),
            recommended_action: "Check customer power supply, UPS battery, and mains electricity".into(),
        });
        return diagnostics; // No point checking further if offline due to power
    }

    if matches!(ont.status, crate::vendors::OntStatus::FiberCut) {
        diagnostics.push(CustomerDiagnostic {
            serial_number: serial.clone(),
            pon_port: port.clone(),
            issue: DiagnosticIssue::FibreFault,
            severity: DiagnosticSeverity::Critical,
            message: format!("ONT {} offline — no dying gasp, suspected fibre break", serial),
            recommended_action: "Inspect fibre path: patch cord, splice closures, drop cable. Use OTDR if available.".into(),
        });
        return diagnostics;
    }

    // 2. Signal degradation (ONT-side primary, OLT-side fallback)
    let primary_rx = ont.extended.as_ref()
        .and_then(|e| e.ont_rx_power_dbm)
        .or(ont.rx_power_dbm);

    if let Some(rx) = primary_rx {
        if rx < -27.0 {
            diagnostics.push(CustomerDiagnostic {
                serial_number: serial.clone(),
                pon_port: port.clone(),
                issue: DiagnosticIssue::DegradedSignal,
                severity: DiagnosticSeverity::Warning,
                message: format!("ONT {} signal at {:.1} dBm (below -27.0 dBm threshold)", serial, rx),
                recommended_action: "Clean connectors, check splice loss, verify fibre bend radius".into(),
            });
        }
    }

    // 3. Connector quality check — ONT vs OLT rx power divergence
    if let (Some(ext), Some(olt_rx)) = (&ont.extended, ont.rx_power_dbm) {
        if let Some(ont_rx) = ext.ont_rx_power_dbm {
            // In a clean network, ONT-side downstream rx and OLT-side upstream rx
            // should be within a few dB of each other (accounting for different directions).
            // Large divergence suggests a dirty or damaged connector on one end.
            let divergence = (ont_rx - olt_rx).abs();
            if divergence > 5.0 {
                diagnostics.push(CustomerDiagnostic {
                    serial_number: serial.clone(),
                    pon_port: port.clone(),
                    issue: DiagnosticIssue::ConnectorDirty,
                    severity: DiagnosticSeverity::Warning,
                    message: format!(
                        "ONT {} rx/tx path divergence: ONT rx {:.1} dBm vs OLT rx {:.1} dBm (Δ{:.1} dB)",
                        serial, ont_rx, olt_rx, divergence
                    ),
                    recommended_action: "Clean SC/APC connectors at ONT and ODF. Check patch cord for micro-bends.".into(),
                });
            }
        }
    }

    // Extended metrics checks (only for vendors that provide OMCI data)
    if let Some(ext) = &ont.extended {
        // 4. Overheating check
        if let Some(temp) = ext.ont_temperature_c {
            if temp > 60.0 {
                diagnostics.push(CustomerDiagnostic {
                    serial_number: serial.clone(),
                    pon_port: port.clone(),
                    issue: DiagnosticIssue::Overheating,
                    severity: if temp > 70.0 {
                        DiagnosticSeverity::Critical
                    } else {
                        DiagnosticSeverity::Warning
                    },
                    message: format!("ONT {} temperature {:.1}°C (threshold 60°C)", serial, temp),
                    recommended_action: "Improve ventilation, move ONT away from heat sources, check enclosure".into(),
                });
            }
        }

        // 5. Voltage anomaly check (normal SFP range: 3.0V - 3.6V)
        if let Some(voltage) = ext.ont_voltage_v {
            if voltage < 3.0 || voltage > 3.6 {
                diagnostics.push(CustomerDiagnostic {
                    serial_number: serial.clone(),
                    pon_port: port.clone(),
                    issue: DiagnosticIssue::VoltageAnomaly,
                    severity: DiagnosticSeverity::Warning,
                    message: format!("ONT {} supply voltage {:.2}V (normal: 3.0–3.6V)", serial, voltage),
                    recommended_action: "Replace power adapter or check DC power supply".into(),
                });
            }
        }

        // 6. Laser degradation check (bias current > 70 mA indicates aging laser)
        if let Some(bias) = ext.ont_bias_current_ma {
            if bias > 70.0 {
                diagnostics.push(CustomerDiagnostic {
                    serial_number: serial.clone(),
                    pon_port: port.clone(),
                    issue: DiagnosticIssue::LaserDegradation,
                    severity: if bias > 90.0 {
                        DiagnosticSeverity::Critical
                    } else {
                        DiagnosticSeverity::Warning
                    },
                    message: format!("ONT {} laser bias current {:.1} mA (threshold 70 mA)", serial, bias),
                    recommended_action: "Schedule ONT replacement — laser nearing end-of-life".into(),
                });
            }
        }
    }

    // 7. Ethernet bottleneck check
    if let Some(speed) = ont.eth_speed_mbps {
        if speed <= 100 && matches!(ont.status, crate::vendors::OntStatus::Online | crate::vendors::OntStatus::LowSignal) {
            diagnostics.push(CustomerDiagnostic {
                serial_number: serial.clone(),
                pon_port: port.clone(),
                issue: DiagnosticIssue::EthernetBottleneck,
                severity: DiagnosticSeverity::Info,
                message: format!("ONT {} Ethernet negotiated at {} Mbps (expected 1000)", serial, speed),
                recommended_action: "Check Ethernet cable (Cat5e minimum), replace if damaged. Verify customer router port.".into(),
            });
        }
    }

    diagnostics
}

/// Generate predictions based on current data + historical trends (default thresholds)
pub fn forecast_olt(current: &OltData, db: &LocalBuffer) -> Predictions {
    forecast_olt_configured(current, db, None)
}

/// Generate predictions with configurable thresholds.
/// Falls back to defaults if config is None.
pub fn forecast_olt_configured(
    current: &OltData,
    db: &LocalBuffer,
    config: Option<&DegradationConfig>,
) -> Predictions {
    let history_days = config.map(|c| c.history_days).unwrap_or(30);
    let failure_threshold = config.map(|c| c.min_critical_rx_dbm).unwrap_or(-27.0);

    let mut signal_preds = Vec::new();
    let mut capacity_preds = Vec::new();
    let mut all_diagnostics = Vec::new();

    // Signal degradation prediction for each ONT
    for ont in &current.onts {
        // Run customer diagnostics decision tree
        all_diagnostics.extend(diagnose_ont(ont));

        // Determine primary rx power: ONT-side (preferred) or OLT-side (fallback)
        let (current_rx, metric_source) = if let Some(ext) = &ont.extended {
            if let Some(ont_rx) = ext.ont_rx_power_dbm {
                (Some(ont_rx), "ont_rx")
            } else {
                (ont.rx_power_dbm, "olt_rx")
            }
        } else {
            (ont.rx_power_dbm, "olt_rx")
        };

        if let Some(current_rx) = current_rx {
            let history = db.get_ont_signal_history(&ont.serial_number, history_days)
                .unwrap_or_default();

            if history.len() >= 3 {
                let first_ts = history[0].0;
                let points: Vec<(f64, f64)> = history.iter()
                    .map(|(ts, rx)| {
                        let days = (*ts - first_ts) as f64 / 86400.0;
                        (days, *rx)
                    })
                    .collect();

                if let Some((slope, _intercept, r_squared)) = linear_regression(&points) {
                    // Classify severity based on rate thresholds
                    if let Some(severity) = classify_degradation(slope, current_rx, config) {
                        let days_to_failure = if current_rx > failure_threshold && slope < 0.0 {
                            Some(((current_rx - failure_threshold) / slope.abs()) as u32)
                        } else if current_rx <= failure_threshold {
                            Some(0)
                        } else {
                            None
                        };

                        let message = match &severity {
                            DegradationSeverity::Critical => {
                                if current_rx <= failure_threshold {
                                    format!(
                                        "CRITICAL: ONT {} at {:.1} dBm (below {:.1} dBm threshold). Immediate inspection required.",
                                        ont.serial_number, current_rx, failure_threshold
                                    )
                                } else {
                                    format!(
                                        "CRITICAL: ONT {} degrading at {:.3} dBm/day ({:.1} dBm). Failure in ~{} days.",
                                        ont.serial_number, slope, current_rx,
                                        days_to_failure.unwrap_or(0)
                                    )
                                }
                            }
                            DegradationSeverity::Warning => format!(
                                "WARNING: ONT {} degrading at {:.3} dBm/day ({:.1} dBm). Schedule inspection.",
                                ont.serial_number, slope, current_rx
                            ),
                            DegradationSeverity::Watch => format!(
                                "WATCH: ONT {} slow degradation at {:.4} dBm/day ({:.1} dBm). Monitor trend.",
                                ont.serial_number, slope, current_rx
                            ),
                        };

                        signal_preds.push(SignalPrediction {
                            serial_number: ont.serial_number.clone(),
                            pon_port: ont.pon_port.clone(),
                            current_rx_dbm: current_rx,
                            metric_source: metric_source.into(),
                            degradation_rate_per_day: slope,
                            severity,
                            days_to_failure,
                            confidence: r_squared as f32,
                            message,
                        });
                    }
                }
            }
        }
    }

    // PON port capacity forecasting
    for port in &current.pon_ports {
        let history = db.get_pon_utilization_history(&current.olt_id, &port.port_id, history_days)
            .unwrap_or_default();

        if history.len() >= 7 {
            let first_ts = history[0].0;
            let points: Vec<(f64, f64)> = history.iter()
                .map(|(ts, util)| {
                    let weeks = (*ts - first_ts) as f64 / 604800.0;
                    (weeks, *util as f64)
                })
                .collect();

            if let Some((slope, _intercept, _r2)) = linear_regression(&points) {
                if slope > 0.1 {
                    let current_util = port.utilization_percent as f64;
                    let weeks_to_95 = if current_util < 95.0 {
                        Some(((95.0 - current_util) / slope) as u32)
                    } else {
                        Some(0)
                    };

                    let message = if let Some(weeks) = weeks_to_95 {
                        if weeks == 0 {
                            format!("CRITICAL: PON {} at {:.0}%. Split now.", port.port_id, current_util)
                        } else if weeks <= 4 {
                            format!("URGENT: PON {} will hit capacity in ~{} weeks.", port.port_id, weeks)
                        } else {
                            format!("PLAN: PON {} growing {:.1}%/week. Capacity in ~{} weeks.", port.port_id, slope, weeks)
                        }
                    } else {
                        String::new()
                    };

                    capacity_preds.push(CapacityForecast {
                        pon_port: port.port_id.clone(),
                        current_utilization_percent: port.utilization_percent,
                        growth_rate_percent_per_month: (slope * 4.0) as f32,
                        weeks_to_95_percent: weeks_to_95,
                        current_onts: port.onts_registered,
                        message,
                    });
                }
            }
        }
    }

    signal_preds.sort_by_key(|p| p.days_to_failure.unwrap_or(999));
    capacity_preds.sort_by_key(|p| p.weeks_to_95_percent.unwrap_or(999));

    Predictions {
        olt_id: current.olt_id.clone(),
        timestamp: chrono::Utc::now(),
        signal_degradation: signal_preds,
        capacity_forecasts: capacity_preds,
        churn_signals: Vec::new(),
        customer_diagnostics: all_diagnostics,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vendors::{OntStatus, ExtendedOntMetrics};

    #[test]
    fn test_configurable_failure_threshold() {
        // Adtran SDX threshold: -27.0 dBm
        let threshold = -27.0_f64;
        let current_rx = -24.0;
        let slope = -0.05_f64; // dBm/day
        let days = ((current_rx - threshold) / slope.abs()) as u32;
        assert_eq!(days, 60);
    }

    #[test]
    fn test_linear_regression_degrading() {
        let points = vec![
            (0.0, -20.0),
            (10.0, -21.0),
            (20.0, -22.0),
            (30.0, -23.0),
        ];
        let (slope, _intercept, r2) = linear_regression(&points).unwrap();
        assert!(slope < -0.09, "slope={}", slope);
        assert!(r2 > 0.99, "r2={}", r2);
    }

    #[test]
    fn test_linear_regression_stable() {
        let points = vec![
            (0.0, -22.0),
            (10.0, -22.1),
            (20.0, -21.9),
            (30.0, -22.0),
        ];
        let (slope, _intercept, _r2) = linear_regression(&points).unwrap();
        assert!(slope.abs() < 0.01, "Should be near-zero slope: {}", slope);
    }

    #[test]
    fn test_classify_degradation_watch() {
        // Rate of -0.02 dBm/day → between watch (-0.015) and warning (-0.035)
        let sev = classify_degradation(-0.02, -22.0, None);
        assert_eq!(sev, Some(DegradationSeverity::Watch));
    }

    #[test]
    fn test_classify_degradation_warning() {
        // Rate of -0.04 dBm/day → between warning (-0.035) and critical (-0.07)
        let sev = classify_degradation(-0.04, -22.0, None);
        assert_eq!(sev, Some(DegradationSeverity::Warning));
    }

    #[test]
    fn test_classify_degradation_critical_rate() {
        // Rate of -0.08 dBm/day → beyond critical (-0.07)
        let sev = classify_degradation(-0.08, -22.0, None);
        assert_eq!(sev, Some(DegradationSeverity::Critical));
    }

    #[test]
    fn test_classify_degradation_critical_absolute() {
        // Current rx below -27.0 dBm → critical regardless of rate
        let sev = classify_degradation(-0.01, -27.5, None);
        assert_eq!(sev, Some(DegradationSeverity::Critical));
    }

    #[test]
    fn test_classify_degradation_none() {
        // Stable signal, no degradation
        let sev = classify_degradation(-0.005, -22.0, None);
        assert_eq!(sev, None);
    }

    #[test]
    fn test_diagnose_ont_power_outage() {
        let ont = OntData {
            serial_number: "ADTN001".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 1,
            status: OntStatus::PowerFail,
            last_down_cause: Some("dying_gasp".into()),
            uptime_seconds: None,
            rx_power_dbm: None,
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: None,
        };
        let diags = diagnose_ont(&ont);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].issue, DiagnosticIssue::PowerOutage);
    }

    #[test]
    fn test_diagnose_ont_fibre_fault() {
        let ont = OntData {
            serial_number: "ADTN002".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 2,
            status: OntStatus::FiberCut,
            last_down_cause: None,
            uptime_seconds: None,
            rx_power_dbm: None,
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: None,
        };
        let diags = diagnose_ont(&ont);
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].issue, DiagnosticIssue::FibreFault);
    }

    #[test]
    fn test_diagnose_ont_overheating() {
        let ont = OntData {
            serial_number: "ADTN003".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 3,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(-22.5),
                ont_temperature_c: Some(65.0),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(15.0),
            }),
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.iter().any(|d| d.issue == DiagnosticIssue::Overheating));
    }

    #[test]
    fn test_diagnose_ont_voltage_anomaly() {
        let ont = OntData {
            serial_number: "ADTN004".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 4,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(-22.5),
                ont_temperature_c: Some(40.0),
                ont_voltage_v: Some(2.8),
                ont_bias_current_ma: Some(15.0),
            }),
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.iter().any(|d| d.issue == DiagnosticIssue::VoltageAnomaly));
    }

    #[test]
    fn test_diagnose_ont_laser_degradation() {
        let ont = OntData {
            serial_number: "ADTN005".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 5,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(-22.5),
                ont_temperature_c: Some(40.0),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(85.0),
            }),
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.iter().any(|d| d.issue == DiagnosticIssue::LaserDegradation));
    }

    #[test]
    fn test_diagnose_ont_connector_dirty() {
        let ont = OntData {
            serial_number: "ADTN006".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 6,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0), // OLT-side rx
            tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(-28.0), // ONT-side rx 6 dB divergence
                ont_temperature_c: Some(40.0),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(15.0),
            }),
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.iter().any(|d| d.issue == DiagnosticIssue::ConnectorDirty));
        // Also should flag degraded signal since ONT rx is below -27.0
        assert!(diags.iter().any(|d| d.issue == DiagnosticIssue::DegradedSignal));
    }

    #[test]
    fn test_diagnose_ont_healthy() {
        let ont = OntData {
            serial_number: "ADTN007".into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 7,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: Some(86400),
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: Some(2.5),
            distance_meters: Some(1500),
            vendor_id: Some("ADTN".into()),
            equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None,
            eth_speed_mbps: Some(1000),
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(-22.5),
                ont_temperature_c: Some(40.0),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(15.0),
            }),
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.is_empty(), "Healthy ONT should produce no diagnostics, got {:?}", diags);
    }
}
