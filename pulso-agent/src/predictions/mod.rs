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
// For signal degradation: fit a line to daily-mean rx power and extrapolate.
//   - Primary metric: ONT-side downstream rx power (via OMCI/NETCONF) —
//     `OntData.extended.ont_rx_power_dbm`, 1490 nm (GPON) / 1577 nm (XGS-PON)
//   - Fallback metric: OLT-side upstream rx power (via SNMP) —
//     `OntData.rx_power_dbm`, 1310 nm (GPON) / 1270 nm (XGS-PON).
//     These are DIFFERENT directions on different wavelengths and must never
//     be mixed within one ONT's history; `metric_source` records which one
//     was used. (`detection::OntReading.rx_power_dbm`, used by the CSV/audit
//     path, is the ONT-side downstream reading.)
//
// SENSOR-RESOLUTION MATH (why the gates exist): SFP DDM quantizes rx power
// at ~0.1 dB (SFF-8472 LSB) and real plants show a ±0.5-1 dB diurnal thermal
// swing. The smallest total drop distinguishable from noise is ~3x the
// quantization step = 0.3 dB; over the 7-day minimum window that is a rate
// of ~0.043 dBm/day. The old defaults (WATCH at -0.015 dBm/day, predictions
// from 3 samples with no minimum elapsed time, R² computed but never used)
// classified pure sensor noise as CRITICAL. Every degradation trend now has
// to pass ALL of these gates or NOTHING is emitted:
//   - >= 7 days elapsed between first and last sample
//   - >= 20 raw samples, aggregated into >= 5 daily means
//     (24h-mean aggregation cancels the diurnal cycle)
//   - R² of the daily-mean fit >= 0.6 (the fit is actually a line)
//   - fitted total drop across the window > 0.3 dB (above quantization)
//   - rate thresholds floored at -0.043 dBm/day:
//     WATCH -0.05, WARNING -0.10, CRITICAL -0.20 dBm/day (defaults)
// ETAs are reported as a 95%-confidence RANGE from the slope standard error,
// not a false-precision point estimate.
//   - Absolute critical: measured rx at/below -27.0 dBm is reported directly
//     (that is a measurement of the current level, not a forecast).
// For capacity: fit a line to (timestamp, utilization%) and find when it hits 95%.
// For churn: track session duration trend over 30 days.
//
// This runs LOCALLY in the agent on each collection cycle.
// Results are sent to the Pulso Cloud where they're enriched with
// market intelligence (Starlink penetration, competitor activity, etc.)
// to produce the final predictions shown to the ISP.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use crate::vendors::{OltData, OntData};
use crate::vendors::snmp_helper::plausible_dbm;
use crate::transport::LocalBuffer;
use crate::config::DegradationConfig;

/// DDM rx-power quantization step (dB), per SFF-8472.
const SENSOR_RESOLUTION_DB: f64 = 0.1;

/// Minimum fitted total drop (dB) across the window for a trend to be
/// considered real: 3x the sensor quantization step.
const MIN_TOTAL_DROP_DB: f64 = 3.0 * SENSOR_RESOLUTION_DB;

/// Minimum elapsed days between first and last sample.
const MIN_WINDOW_DAYS: f64 = 7.0;

/// Minimum raw sample count before fitting a trend.
const MIN_SAMPLES: usize = 20;

/// Minimum number of daily-mean buckets for the regression.
const MIN_DAILY_BUCKETS: usize = 5;

/// Minimum R² of the daily-mean fit for a trend to be quoted.
const MIN_R_SQUARED: f64 = 0.6;

/// Smallest defensible degradation rate (dBm/day): MIN_TOTAL_DROP_DB over
/// the minimum window. Configured thresholds shallower than this are
/// floored here — they would otherwise classify quantization noise.
const MIN_DEFENSIBLE_RATE_PER_DAY: f64 = MIN_TOTAL_DROP_DB / MIN_WINDOW_DAYS;

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
    /// Rate ≤ -0.05 dBm/day — early sign of connector or splice degradation
    Watch,
    /// Rate ≤ -0.10 dBm/day — schedule field inspection
    Warning,
    /// Rate ≤ -0.20 dBm/day OR absolute rx below -27.0 dBm — imminent failure
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
    /// Rate of degradation (dBm per day, negative = getting worse).
    /// 0.0 for absolute-level (measured) criticals with no fitted trend.
    pub degradation_rate_per_day: f64,
    /// Severity classification based on rate thresholds
    pub severity: DegradationSeverity,
    /// Point estimate of days until the failure threshold. The honest
    /// 95%-confidence RANGE derived from the slope standard error is in
    /// `message` — treat this field as the midpoint, not a promise.
    pub days_to_failure: Option<u32>,
    /// Confidence level: R² of the daily-mean linear fit (always >= 0.6 —
    /// lower fits are suppressed), or 1.0 for measured absolute-level
    /// criticals.
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
    linear_regression_full(points).map(|(m, b, r2, _se)| (m, b, r2))
}

/// Linear regression with slope standard error:
/// returns (slope, intercept, r_squared, slope_stderr).
fn linear_regression_full(points: &[(f64, f64)]) -> Option<(f64, f64, f64, f64)> {
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

    // Standard error of the slope: sqrt( (ss_res / (n-2)) / Σ(x - x̄)² )
    let sxx = sum_x2 - sum_x * sum_x / n;
    let slope_stderr = if n > 2.0 && sxx > 1e-12 {
        ((ss_res / (n - 2.0)) / sxx).sqrt()
    } else {
        f64::INFINITY
    };

    Some((slope, intercept, r_squared, slope_stderr))
}

/// A degradation trend that passed every statistical gate.
#[derive(Debug, Clone)]
pub(crate) struct DegradationTrend {
    /// Fitted slope on daily means (dBm/day, negative = degrading).
    pub slope_per_day: f64,
    /// Standard error of the slope (dBm/day).
    pub slope_stderr_per_day: f64,
    /// R² of the daily-mean fit (>= MIN_R_SQUARED by construction).
    pub r_squared: f64,
    /// Elapsed days between first and last sample.
    pub window_days: f64,
    /// Raw (plausible) sample count.
    pub samples: usize,
    /// Fitted total drop across the window (dB, positive = drop).
    /// > MIN_TOTAL_DROP_DB by construction; kept for diagnostics/tests.
    #[allow(dead_code)]
    pub total_fitted_drop_db: f64,
}

/// Fit a degradation trend from raw signal history `(unix_ts, rx_dbm)`,
/// applying every statistical gate from the module header. Returns None —
/// i.e. NO prediction, never a CRITICAL — unless the history contains
/// >= MIN_SAMPLES plausible samples spanning >= MIN_WINDOW_DAYS, aggregated
/// into >= MIN_DAILY_BUCKETS daily means, fitting a line with
/// R² >= MIN_R_SQUARED whose total drop across the window exceeds
/// MIN_TOTAL_DROP_DB.
///
/// Daily-mean (24h) aggregation is the detrending step: it averages out the
/// diurnal thermal cycle and the DDM quantization steps so the fit sees the
/// day-over-day movement only.
pub(crate) fn fit_degradation_trend(history: &[(i64, f64)]) -> Option<DegradationTrend> {
    // Sanitize: drop vendor sentinels / implausible values before statistics.
    let clean: Vec<(i64, f64)> = history
        .iter()
        .filter_map(|(ts, rx)| plausible_dbm(*rx).map(|v| (*ts, v)))
        .collect();

    if clean.len() < MIN_SAMPLES {
        return None;
    }

    let first_ts = clean.iter().map(|(t, _)| *t).min()?;
    let last_ts = clean.iter().map(|(t, _)| *t).max()?;
    let window_days = (last_ts - first_ts) as f64 / 86400.0;
    if window_days < MIN_WINDOW_DAYS {
        return None;
    }

    // 24h-mean detrending: bucket into UTC days and average.
    let mut buckets: BTreeMap<i64, (f64, u32)> = BTreeMap::new();
    for (ts, rx) in &clean {
        let day = ts.div_euclid(86400);
        let entry = buckets.entry(day).or_insert((0.0, 0));
        entry.0 += rx;
        entry.1 += 1;
    }
    if buckets.len() < MIN_DAILY_BUCKETS {
        return None;
    }

    let daily_points: Vec<(f64, f64)> = buckets
        .iter()
        .map(|(day, (sum, count))| (*day as f64, sum / *count as f64))
        .collect();

    let (slope, _intercept, r_squared, slope_stderr) =
        linear_regression_full(&daily_points)?;

    // The fit must actually be a line, not noise.
    if r_squared < MIN_R_SQUARED {
        return None;
    }

    // Only negative (degrading) trends whose total drop clears the sensor
    // resolution gate are real.
    let total_fitted_drop_db = -slope * window_days;
    if slope >= 0.0 || total_fitted_drop_db <= MIN_TOTAL_DROP_DB {
        return None;
    }

    Some(DegradationTrend {
        slope_per_day: slope,
        slope_stderr_per_day: slope_stderr,
        r_squared,
        window_days,
        samples: clean.len(),
        total_fitted_drop_db,
    })
}

/// 95%-confidence ETA range (days) to the failure threshold, from the slope
/// standard error. Returns (earliest, latest); `latest` is None when the
/// slow edge of the confidence band is non-degrading (open-ended).
pub(crate) fn eta_range_days(
    current_rx: f64,
    failure_threshold: f64,
    trend: &DegradationTrend,
) -> (u32, Option<u32>) {
    let margin = (current_rx - failure_threshold).max(0.0);
    let fast_slope = trend.slope_per_day - 1.96 * trend.slope_stderr_per_day;
    let slow_slope = trend.slope_per_day + 1.96 * trend.slope_stderr_per_day;

    let earliest = if fast_slope < 0.0 {
        (margin / fast_slope.abs()) as u32
    } else {
        0
    };
    let latest = if slow_slope < -1e-9 {
        Some((margin / slow_slope.abs()) as u32)
    } else {
        None
    };
    (earliest, latest)
}

/// Classify degradation severity from rate (dBm/day) and config thresholds.
///
/// Thresholds are negative values; defaults: watch=-0.05, warning=-0.10,
/// critical=-0.20 dBm/day. Any configured threshold shallower than the
/// sensor-resolution floor (-0.043 dBm/day = 0.3 dB over the 7-day minimum
/// window) is clamped to the floor: DDM hardware cannot resolve slower
/// rates, so alerting on them would be alerting on noise.
pub(crate) fn classify_degradation(
    rate: f64,
    current_rx: f64,
    config: Option<&DegradationConfig>,
) -> Option<DegradationSeverity> {
    // Floor: never accept a threshold below what the sensor can resolve.
    let floor = -MIN_DEFENSIBLE_RATE_PER_DAY;
    let watch = config.map(|c| c.watch_threshold_db).unwrap_or(-0.05).min(floor);
    let warning = config.map(|c| c.warning_threshold_db).unwrap_or(-0.10).min(floor);
    let critical_rate = config.map(|c| c.critical_threshold_db).unwrap_or(-0.20).min(floor);
    let min_critical_rx = config.map(|c| c.min_critical_rx_dbm).unwrap_or(-27.0);

    // Absolute critical: current rx at/below threshold regardless of rate.
    // This is a measured level, not a forecast.
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

        // Determine primary rx power: ONT-side downstream (preferred) or
        // OLT-side upstream (fallback). These are different directions on
        // different wavelengths — metric_source records which one this
        // prediction is about. Sentinels/implausible values are dropped.
        let (current_rx, metric_source) = if let Some(ext) = &ont.extended {
            if let Some(ont_rx) = ext.ont_rx_power_dbm {
                (Some(ont_rx), "ont_rx")
            } else {
                (ont.rx_power_dbm, "olt_rx")
            }
        } else {
            (ont.rx_power_dbm, "olt_rx")
        };
        let current_rx = current_rx.and_then(plausible_dbm);

        if let Some(current_rx) = current_rx {
            // Absolute critical: the CURRENT measured level is at/below the
            // failure threshold. This is a measurement, not a forecast, so
            // it is reported regardless of trend gates.
            if current_rx <= failure_threshold {
                signal_preds.push(SignalPrediction {
                    serial_number: ont.serial_number.clone(),
                    pon_port: ont.pon_port.clone(),
                    current_rx_dbm: current_rx,
                    metric_source: metric_source.into(),
                    degradation_rate_per_day: 0.0,
                    severity: DegradationSeverity::Critical,
                    days_to_failure: Some(0),
                    confidence: 1.0,
                    message: format!(
                        "CRITICAL: ONT {} measured at {:.1} dBm (at/below {:.1} dBm threshold). Immediate inspection required.",
                        ont.serial_number, current_rx, failure_threshold
                    ),
                });
                continue;
            }

            let history = db.get_ont_signal_history(&ont.serial_number, history_days)
                .unwrap_or_default();

            // Trend predictions must pass ALL statistical gates (window,
            // sample count, daily buckets, R², total-drop-above-resolution).
            // Anything that fails emits NOTHING — never a CRITICAL from noise.
            if let Some(trend) = fit_degradation_trend(&history) {
                let slope = trend.slope_per_day;
                if let Some(severity) = classify_degradation(slope, current_rx, config) {
                    let (eta_early, eta_late) = eta_range_days(current_rx, failure_threshold, &trend);
                    let days_to_failure =
                        Some(((current_rx - failure_threshold) / slope.abs()) as u32);
                    let eta_text = match eta_late {
                        Some(late) => format!("{}–{} days (95% confidence)", eta_early, late),
                        None => format!("{}+ days (slow edge of confidence band is flat)", eta_early),
                    };

                    let message = match &severity {
                        DegradationSeverity::Critical => format!(
                            "CRITICAL: ONT {} degrading at {:.3} dBm/day ({:.1} dBm, R²={:.2}, {} samples/{:.0}d). Failure window: {}.",
                            ont.serial_number, slope, current_rx,
                            trend.r_squared, trend.samples, trend.window_days, eta_text
                        ),
                        DegradationSeverity::Warning => format!(
                            "WARNING: ONT {} degrading at {:.3} dBm/day ({:.1} dBm, R²={:.2}). Failure window: {}. Schedule inspection.",
                            ont.serial_number, slope, current_rx, trend.r_squared, eta_text
                        ),
                        DegradationSeverity::Watch => format!(
                            "WATCH: ONT {} slow degradation at {:.4} dBm/day ({:.1} dBm, R²={:.2}). Monitor trend.",
                            ont.serial_number, slope, current_rx, trend.r_squared
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
                        confidence: trend.r_squared as f32,
                        message,
                    });
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
        // Rate of -0.06 dBm/day → between watch (-0.05) and warning (-0.10)
        let sev = classify_degradation(-0.06, -22.0, None);
        assert_eq!(sev, Some(DegradationSeverity::Watch));
    }

    #[test]
    fn test_classify_degradation_warning() {
        // Rate of -0.12 dBm/day → between warning (-0.10) and critical (-0.20)
        let sev = classify_degradation(-0.12, -22.0, None);
        assert_eq!(sev, Some(DegradationSeverity::Warning));
    }

    #[test]
    fn test_classify_degradation_critical_rate() {
        // Rate of -0.25 dBm/day → beyond critical (-0.20)
        let sev = classify_degradation(-0.25, -22.0, None);
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
    fn test_classify_degradation_below_resolution_none() {
        // -0.02 dBm/day = 0.14 dB over 7 days, below the 0.3 dB the DDM can
        // resolve. The OLD default flagged this as Watch; it must be None.
        let sev = classify_degradation(-0.02, -22.0, None);
        assert_eq!(sev, None);
    }

    #[test]
    fn test_classify_degradation_config_floored_at_resolution() {
        // A config below sensor resolution is clamped to the floor: rates
        // shallower than -0.043 dBm/day can never classify.
        let custom = crate::config::DegradationConfig {
            history_days: 30,
            trend_window_weeks: 4,
            watch_threshold_db: -0.001, // absurd: 10x below the DDM LSB
            warning_threshold_db: -0.002,
            critical_threshold_db: -0.003,
            min_critical_rx_dbm: -27.0,
        };
        let sev = classify_degradation(-0.02, -22.0, Some(&custom));
        assert_eq!(sev, None, "below-resolution config thresholds must be floored");
        // At/above the floor the (clamped) thresholds still work
        let sev2 = classify_degradation(-0.05, -22.0, Some(&custom));
        assert!(sev2.is_some());
    }

    /// Build a synthetic history: `days` days, `per_day` samples/day,
    /// rx = base + slope*day + diurnal sine + 0.1 dB quantization.
    fn synth_history(days: u32, per_day: u32, base: f64, slope_per_day: f64, diurnal_amp: f64) -> Vec<(i64, f64)> {
        let start: i64 = 1_770_000_000; // arbitrary epoch
        let mut history = Vec::new();
        for d in 0..days {
            for s in 0..per_day {
                let ts = start + (d as i64) * 86400 + (s as i64) * (86400 / per_day as i64);
                let hour = (s as f64 / per_day as f64) * 24.0;
                let diurnal = diurnal_amp * (2.0 * std::f64::consts::PI * hour / 24.0).sin();
                let raw = base + slope_per_day * d as f64 + diurnal;
                // DDM quantization at 0.1 dB
                let quantized = (raw * 10.0).round() / 10.0;
                history.push((ts, quantized));
            }
        }
        history
    }

    #[test]
    fn test_trend_gate_rejects_quantization_noise() {
        // ±0.1 dB quantization + ±0.7 dB diurnal sine, NO real trend, 14 days
        // of 4 samples/day: must produce NO trend (previously → CRITICAL).
        let history = synth_history(14, 4, -20.0, 0.0, 0.7);
        assert!(
            fit_degradation_trend(&history).is_none(),
            "quantization + diurnal noise must not fit a degradation trend"
        );
    }

    #[test]
    fn test_trend_gate_accepts_genuine_degradation() {
        // Genuine 0.1 dB/day drop over 14 days (1.4 dB total) with the same
        // quantization and a diurnal cycle: MUST predict, with a sane ETA.
        let history = synth_history(14, 4, -20.0, -0.1, 0.3);
        let trend = fit_degradation_trend(&history)
            .expect("a genuine 0.1 dB/day trend over 14 days must be detected");
        assert!(
            (trend.slope_per_day - (-0.1)).abs() < 0.03,
            "slope should be ~-0.1 dBm/day, got {}",
            trend.slope_per_day
        );
        assert!(trend.r_squared >= MIN_R_SQUARED);
        assert!(trend.total_fitted_drop_db > MIN_TOTAL_DROP_DB);

        // ETA range to -27 from ~-21.3: point estimate ~57 days; the 95%
        // band must bracket it and stay physically sane.
        let current_rx = -21.4;
        let (early, late) = eta_range_days(current_rx, -27.0, &trend);
        assert!(early >= 20 && early <= 80, "early ETA sane: {}", early);
        let late = late.expect("clean trend should have a bounded slow edge");
        assert!(late >= early, "range ordered: {}..{}", early, late);
        assert!(late <= 200, "late ETA sane: {}", late);
    }

    #[test]
    fn test_trend_gate_rejects_short_window() {
        // Strong genuine trend but only 5 days of data: below the 7-day
        // minimum window → no prediction.
        let history = synth_history(5, 6, -20.0, -0.3, 0.2);
        assert!(
            fit_degradation_trend(&history).is_none(),
            "5-day window is below the 7-day minimum"
        );
    }

    #[test]
    fn test_trend_gate_rejects_few_samples() {
        // 8 days but only 2 samples/day = 16 < 20 samples → no prediction.
        let history = synth_history(8, 2, -20.0, -0.3, 0.2);
        assert!(
            fit_degradation_trend(&history).is_none(),
            "16 samples is below the 20-sample minimum"
        );
    }

    #[test]
    fn test_trend_gate_rejects_low_r_squared() {
        // 14 days, enough samples, but the signal is a step + huge swings:
        // add alternating ±1.5 dB day-level noise so the daily-mean fit is
        // poor. R² < 0.6 → no prediction even though a naive fit would
        // find a negative slope.
        let start: i64 = 1_770_000_000;
        let mut history = Vec::new();
        for d in 0..14u32 {
            let day_noise = if d % 2 == 0 { 1.5 } else { -1.5 };
            for s in 0..4u32 {
                let ts = start + (d as i64) * 86400 + (s as i64) * 21600;
                let raw = -20.0 - 0.02 * d as f64 + day_noise;
                history.push((ts, (raw * 10.0f64).round() / 10.0));
            }
        }
        assert!(
            fit_degradation_trend(&history).is_none(),
            "R² below 0.6 must suppress the prediction"
        );
    }

    #[test]
    fn test_trend_gate_rejects_sentinel_poisoned_history() {
        // A genuine-looking trend created purely by one sentinel value must
        // not survive sanitization (Huawei 2147483647/100 etc.).
        let mut history = synth_history(14, 4, -20.0, 0.0, 0.2);
        history.push((1_770_000_000 + 15 * 86400, 21_474_836.47));
        history.push((1_770_000_000 + 15 * 86400 + 21600, -327.68));
        assert!(
            fit_degradation_trend(&history).is_none(),
            "sentinel values must be dropped, not fitted"
        );
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
            ..Default::default()
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
            ..Default::default()
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
            ..Default::default()
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
            ..Default::default()
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
            ..Default::default()
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
            ..Default::default()
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
            ..Default::default()
        };
        let diags = diagnose_ont(&ont);
        assert!(diags.is_empty(), "Healthy ONT should produce no diagnostics, got {:?}", diags);
    }
}
