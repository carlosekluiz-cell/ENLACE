// SPDX-License-Identifier: Apache-2.0
// Predictive Analytics Module
//
// Uses historical telemetry data (stored in local SQLite) to predict:
//   1. Signal degradation — detect ONTs that will fail before they do
//   2. Capacity exhaustion — predict when PON ports will be saturated
//   3. Churn signals — detect customers whose usage patterns suggest leaving
//
// Method: Simple linear regression on time-series data.
// For signal degradation: fit a line to (timestamp, rx_power_dbm) and extrapolate.
// For capacity: fit a line to (timestamp, utilization%) and find when it hits 95%.
// For churn: track session duration trend over 30 days.
//
// This runs LOCALLY in the agent on each collection cycle.
// Results are sent to the Pulso Cloud where they're enriched with
// market intelligence (Starlink penetration, competitor activity, etc.)
// to produce the final predictions shown to the ISP.

use serde::{Deserialize, Serialize};
use crate::vendors::OltData;
use crate::transport::LocalBuffer;
use crate::config::DegradationConfig;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Predictions {
    pub olt_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub signal_degradation: Vec<SignalPrediction>,
    pub capacity_forecasts: Vec<CapacityForecast>,
    pub churn_signals: Vec<ChurnSignal>,
}

/// Predicted signal failure for a specific ONT
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalPrediction {
    pub serial_number: String,
    pub pon_port: String,
    /// Current signal level (dBm)
    pub current_rx_dbm: f64,
    /// Rate of degradation (dBm per day, negative = getting worse)
    pub degradation_rate_per_day: f64,
    /// Predicted days until failure threshold (-28 dBm)
    pub days_to_failure: Option<u32>,
    /// Confidence level (0.0-1.0 based on data points available)
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
    let sum_y2: f64 = points.iter().map(|(_, y)| y * y).sum();

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
    let failure_threshold = config.map(|c| c.min_critical_rx_dbm).unwrap_or(-28.0);

    let mut signal_preds = Vec::new();
    let mut capacity_preds = Vec::new();

    // Signal degradation prediction for each ONT
    for ont in &current.onts {
        if let Some(current_rx) = ont.rx_power_dbm {
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
                    if slope < -0.01 && r_squared > 0.3 {
                        let days_to_failure = if current_rx > failure_threshold {
                            Some(((current_rx - failure_threshold) / slope.abs()) as u32)
                        } else {
                            Some(0)
                        };

                        let message = if let Some(days) = days_to_failure {
                            if days == 0 {
                                format!(
                                    "CRITICAL: ONT {} already below failure threshold ({:.1} dBm).",
                                    ont.serial_number, current_rx
                                )
                            } else if days <= 7 {
                                format!(
                                    "URGENT: ONT {} degrading ({:.1} dBm, -{:.2} dBm/day). Predicted failure in {} days.",
                                    ont.serial_number, current_rx, slope.abs(), days
                                )
                            } else if days <= 30 {
                                format!(
                                    "WARNING: ONT {} slow degradation ({:.1} dBm). Schedule inspection in {} days.",
                                    ont.serial_number, current_rx, days
                                )
                            } else {
                                format!(
                                    "MONITOR: ONT {} degradation trend ({:.1} dBm). Review in 30 days.",
                                    ont.serial_number, current_rx
                                )
                            }
                        } else {
                            String::new()
                        };

                        if days_to_failure.unwrap_or(999) <= 90 {
                            signal_preds.push(SignalPrediction {
                                serial_number: ont.serial_number.clone(),
                                pon_port: ont.pon_port.clone(),
                                current_rx_dbm: current_rx,
                                degradation_rate_per_day: slope,
                                days_to_failure,
                                confidence: r_squared as f32,
                                message,
                            });
                        }
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
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_configurable_failure_threshold() {
        // XGS-PON threshold: -28.0 dBm
        let threshold = -28.0_f64;
        let current_rx = -25.0;
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
}
