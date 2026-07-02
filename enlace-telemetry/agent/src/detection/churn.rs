// SPDX-License-Identifier: Apache-2.0
// Customer Churn Risk Predictor
//
// Predicts customer churn probability from ONT signal degradation patterns.
// Uses linear regression on rx_power over time plus micro-dropout counting
// to estimate the likelihood that a customer will cancel their service
// within 90 days due to quality issues.
//
// This is the bridge between raw telemetry and business impact:
//   Signal degradation -> Service quality impact -> Customer dissatisfaction -> Churn
//
// Impact classification:
//   None:       Rx > -20, slope > -0.01       — customer is happy (2% baseline)
//   Subtle:     Rx > -22, slope -0.01 to -0.03 — minor buffering, may not notice (5%)
//   Noticeable: Rx > -24, slope -0.03 to -0.05 — dropped video calls, slow pages (15%)
//   Severe:     Else or slope < -0.05           — constant complaints (35%)
//   +10% if micro_dropout_count > 5

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// Churn risk assessment for a single ONT / customer.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChurnRisk {
    pub ont_serial: String,
    pub current_rx_dbm: f64,
    pub degradation_rate: f64,
    pub days_degrading: u32,
    pub micro_dropout_count: u32,
    pub impact: ChurnImpact,
    pub churn_probability_90day: f64,
    pub monthly_revenue_at_risk: f64,
}

/// Customer-perceived impact level from signal degradation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ChurnImpact {
    None,
    Subtle,
    Noticeable,
    Severe,
}

impl std::fmt::Display for ChurnImpact {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::None => write!(f, "none"),
            Self::Subtle => write!(f, "subtle"),
            Self::Noticeable => write!(f, "noticeable"),
            Self::Severe => write!(f, "severe"),
        }
    }
}

/// Baseline churn probability when signal is healthy.
const BASELINE_CHURN_PROB: f64 = 0.02;

/// Maximum time gap (seconds) for a dropout to be considered "micro" (< 5 min).
const MICRO_DROPOUT_MAX_SECS: i64 = 300;

/// Simple linear regression: y = mx + b
/// Returns (slope, intercept, r_squared)
fn linear_regression(points: &[(f64, f64)]) -> Option<(f64, f64, f64)> {
    let n = points.len() as f64;
    if n < 3.0 {
        return None;
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

    let y_mean = sum_y / n;
    let ss_tot: f64 = points.iter().map(|(_, y)| (y - y_mean).powi(2)).sum();
    let ss_res: f64 = points
        .iter()
        .map(|(x, y)| {
            let predicted = slope * x + intercept;
            (y - predicted).powi(2)
        })
        .sum();
    let r_squared = if ss_tot > 0.0 {
        1.0 - ss_res / ss_tot
    } else {
        0.0
    };

    Some((slope, intercept, r_squared))
}

/// Predict churn risk for each ONT based on signal degradation and micro-dropouts.
///
/// For each ONT with sufficient readings:
///   1. Fit linear regression to rx_power over time to get degradation slope
///   2. Count micro-dropouts (offline < 5 min then back online)
///   3. Classify impact and compute churn probability
///   4. Calculate revenue at risk = arpu * churn_prob * 12 months
///
/// Only returns ONTs with churn probability above the 2% baseline.
pub fn predict_churn_risk(readings: &[OntReading], arpu: f64) -> Vec<ChurnRisk> {
    // Group readings by ONT serial
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

        // Get the latest Rx reading
        let current_rx = ont_readings
            .iter()
            .rev()
            .find_map(|r| r.rx_power_dbm)
            .unwrap_or(-30.0);

        // Build time-series of Rx power for linear regression
        let first_ts = ont_readings[0].timestamp;
        let points: Vec<(f64, f64)> = ont_readings
            .iter()
            .filter_map(|r| {
                r.rx_power_dbm.map(|rx| {
                    let days = (r.timestamp - first_ts).num_seconds() as f64 / 86400.0;
                    (days, rx)
                })
            })
            .collect();

        let (slope, days_span) = if let Some((s, _, _)) = linear_regression(&points) {
            let span = if let (Some(first), Some(last)) = (points.first(), points.last()) {
                (last.0 - first.0).max(0.0) as u32
            } else {
                0
            };
            (s, span)
        } else {
            continue;
        };

        // Count micro-dropouts: offline -> online transitions where the offline
        // duration was less than 5 minutes
        let mut micro_dropouts: u32 = 0;
        let mut offline_start: Option<chrono::DateTime<chrono::Utc>> = None;

        for r in &ont_readings {
            match r.status {
                OntReadingStatus::Offline => {
                    if offline_start.is_none() {
                        offline_start = Some(r.timestamp);
                    }
                }
                OntReadingStatus::Online => {
                    if let Some(start) = offline_start {
                        let duration = (r.timestamp - start).num_seconds();
                        if duration > 0 && duration < MICRO_DROPOUT_MAX_SECS {
                            micro_dropouts += 1;
                        }
                        offline_start = None;
                    }
                }
            }
        }

        // Classify impact and base churn probability
        let (impact, mut churn_prob) = classify_impact(current_rx, slope);

        // Micro-dropouts increase churn probability by 10%
        if micro_dropouts > 5 {
            churn_prob += 0.10;
        }

        // Cap at 95%
        churn_prob = churn_prob.min(0.95);

        // Only report if above baseline
        if churn_prob <= BASELINE_CHURN_PROB {
            continue;
        }

        let monthly_revenue_at_risk = arpu * churn_prob * 12.0;

        results.push(ChurnRisk {
            ont_serial: serial,
            current_rx_dbm: current_rx,
            degradation_rate: slope,
            days_degrading: days_span,
            micro_dropout_count: micro_dropouts,
            impact,
            churn_probability_90day: churn_prob,
            monthly_revenue_at_risk,
        });
    }

    // Sort by churn probability descending
    results.sort_by(|a, b| {
        b.churn_probability_90day
            .partial_cmp(&a.churn_probability_90day)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Classify the customer-perceived impact from current Rx power and degradation slope.
/// Returns (impact, base_churn_probability).
fn classify_impact(current_rx: f64, slope: f64) -> (ChurnImpact, f64) {
    if current_rx > -20.0 && slope > -0.01 {
        (ChurnImpact::None, 0.02)
    } else if current_rx > -22.0 && slope > -0.03 {
        (ChurnImpact::Subtle, 0.05)
    } else if current_rx > -24.0 && slope > -0.05 {
        (ChurnImpact::Noticeable, 0.15)
    } else {
        (ChurnImpact::Severe, 0.35)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, Utc};

    fn make_reading(
        serial: &str,
        ts: chrono::DateTime<chrono::Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            rx_power_dbm: rx,
            tx_power_dbm: None,
            status,
            distance_meters: None,
            eth_speed_mbps: None,
            last_down_cause: None,
        }
    }

    #[test]
    fn test_churn_healthy_no_risk() {
        let now = Utc::now();
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "HEALTHY01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-18.0), // Excellent signal, stable
                )
            })
            .collect();

        let risks = predict_churn_risk(&readings, 100.0);
        assert!(
            risks.is_empty(),
            "Healthy ONT with stable signal should not appear in churn risk"
        );
    }

    #[test]
    fn test_churn_subtle_degradation() {
        let now = Utc::now();
        // Signal slowly degrading from -19.0 to -21.5 over 30 days
        let readings: Vec<OntReading> = (0..30)
            .map(|i| {
                let rx = -19.0 - (i as f64 * 0.083); // ~-0.083/day slope -> ends at ~-21.5
                make_reading(
                    "SUBTLE01",
                    now - Duration::days(30 - i),
                    OntReadingStatus::Online,
                    Some(rx),
                )
            })
            .collect();

        let risks = predict_churn_risk(&readings, 100.0);
        assert!(!risks.is_empty(), "Subtle degradation should produce churn risk");
        let risk = &risks[0];
        assert_eq!(risk.impact, ChurnImpact::Severe);
        assert!(
            risk.churn_probability_90day > BASELINE_CHURN_PROB,
            "Churn probability should be above baseline"
        );
    }

    #[test]
    fn test_churn_severe_with_dropouts() {
        let now = Utc::now();
        let mut readings = Vec::new();

        // Degrading signal over 20 days
        for i in 0..20 {
            let rx = -22.0 - (i as f64 * 0.15); // ends at ~-24.85
            readings.push(make_reading(
                "SEVERE01",
                now - Duration::days(20 - i),
                OntReadingStatus::Online,
                Some(rx),
            ));
        }

        // Add 6 micro-dropouts (offline < 5 min each)
        for i in 0..6 {
            let dropout_time = now - Duration::hours(24 + i * 4);
            readings.push(make_reading(
                "SEVERE01",
                dropout_time,
                OntReadingStatus::Offline,
                None,
            ));
            readings.push(make_reading(
                "SEVERE01",
                dropout_time + Duration::minutes(2),
                OntReadingStatus::Online,
                Some(-24.5),
            ));
        }

        let risks = predict_churn_risk(&readings, 100.0);
        assert!(!risks.is_empty(), "Severe degradation with dropouts should produce risk");
        let risk = &risks[0];
        assert_eq!(risk.impact, ChurnImpact::Severe);
        assert!(
            risk.micro_dropout_count > 5,
            "Should count micro-dropouts: {}",
            risk.micro_dropout_count
        );
        // With severe (35%) + dropout bonus (10%) = 45%
        assert!(
            risk.churn_probability_90day >= 0.40,
            "Expected >= 40% churn prob, got {}",
            risk.churn_probability_90day
        );
    }

    #[test]
    fn test_churn_revenue_calculation() {
        let now = Utc::now();
        // Severely degrading signal
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                let rx = -24.0 - (i as f64 * 0.2);
                make_reading(
                    "REV01",
                    now - Duration::days(15 - i),
                    OntReadingStatus::Online,
                    Some(rx),
                )
            })
            .collect();

        let arpu = 89.90;
        let risks = predict_churn_risk(&readings, arpu);
        assert!(!risks.is_empty());
        let risk = &risks[0];
        let expected_rev = arpu * risk.churn_probability_90day * 12.0;
        assert!(
            (risk.monthly_revenue_at_risk - expected_rev).abs() < 0.01,
            "Revenue at risk should be arpu * prob * 12: expected {}, got {}",
            expected_rev,
            risk.monthly_revenue_at_risk
        );
    }

    #[test]
    fn test_churn_micro_dropout_increases_probability() {
        let now = Utc::now();

        // Create two identical ONTs with same signal degradation
        // but one has micro-dropouts and the other doesn't
        let make_base_readings = |serial: &str| -> Vec<OntReading> {
            (0..15)
                .map(|i| {
                    let rx = -23.0 - (i as f64 * 0.08); // moderate degradation
                    make_reading(
                        serial,
                        now - Duration::days(15 - i),
                        OntReadingStatus::Online,
                        Some(rx),
                    )
                })
                .collect()
        };

        let readings_no_dropouts = make_base_readings("NODROP01");
        let mut readings_with_dropouts = make_base_readings("WITHDROP01");

        // Add 6 micro-dropouts to the second ONT
        for i in 0..6 {
            let t = now - Duration::hours(12 + i * 2);
            readings_with_dropouts.push(make_reading(
                "WITHDROP01",
                t,
                OntReadingStatus::Offline,
                None,
            ));
            readings_with_dropouts.push(make_reading(
                "WITHDROP01",
                t + Duration::minutes(1),
                OntReadingStatus::Online,
                Some(-24.0),
            ));
        }

        let mut all_readings = readings_no_dropouts;
        all_readings.extend(readings_with_dropouts);

        let risks = predict_churn_risk(&all_readings, 100.0);

        let no_drop = risks.iter().find(|r| r.ont_serial == "NODROP01");
        let with_drop = risks.iter().find(|r| r.ont_serial == "WITHDROP01");

        // Both should appear (both are degrading)
        assert!(no_drop.is_some(), "NODROP01 should have churn risk");
        assert!(with_drop.is_some(), "WITHDROP01 should have churn risk");

        let no_drop = no_drop.unwrap();
        let with_drop = with_drop.unwrap();

        assert!(
            with_drop.churn_probability_90day > no_drop.churn_probability_90day,
            "Micro-dropouts should increase churn probability: {} > {}",
            with_drop.churn_probability_90day,
            no_drop.churn_probability_90day
        );
    }
}
