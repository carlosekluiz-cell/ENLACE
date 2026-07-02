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
// HONESTY NOTE: the per-impact churn probabilities are ASSUMPTIONS, not
// measurements. No telemetry stream can measure a customer's probability of
// cancelling; these constants are configurable planning inputs, echoed back
// verbatim in every result's `assumptions` field so that nobody downstream
// can mistake an estimate for a measured value. All monetary outputs are
// named `estimated_*` for the same reason.
//
// Impact classification (assumed default probabilities):
//   None:       Rx > -20, slope > -0.01       — customer is happy (2% baseline)
//   Subtle:     Rx > -22, slope -0.01 to -0.03 — minor buffering, may not notice (5%)
//   Noticeable: Rx > -24, slope -0.03 to -0.05 — dropped video calls, slow pages (15%)
//   Severe:     Else or slope < -0.05           — constant complaints (35%)
//   +10% if micro_dropout_count > 5

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{sane_rx, OntReading, OntReadingStatus};

/// The assumed model constants behind a churn estimate. These are NOT
/// measured values — they are operator-configurable planning assumptions,
/// echoed into every `ChurnRisk` so the output is self-describing.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChurnAssumptions {
    /// Assumed 90-day churn probability with healthy signal.
    pub baseline_probability: f64,
    /// Assumed 90-day churn probability for Subtle impact.
    pub subtle_probability: f64,
    /// Assumed 90-day churn probability for Noticeable impact.
    pub noticeable_probability: f64,
    /// Assumed 90-day churn probability for Severe impact.
    pub severe_probability: f64,
    /// Assumed probability increase when micro-dropouts exceed the threshold.
    pub micro_dropout_bonus: f64,
    /// Assumed average revenue per user per month (operator currency).
    pub monthly_arpu: f64,
}

impl ChurnAssumptions {
    /// Default assumption set with the given ARPU.
    pub fn with_arpu(monthly_arpu: f64) -> Self {
        Self {
            baseline_probability: 0.02,
            subtle_probability: 0.05,
            noticeable_probability: 0.15,
            severe_probability: 0.35,
            micro_dropout_bonus: 0.10,
            monthly_arpu,
        }
    }
}

/// Churn risk assessment for a single ONT / customer.
///
/// `estimated_*` fields are model outputs derived from the `assumptions`
/// echoed below — they are not measurements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChurnRisk {
    pub ont_serial: String,
    pub current_rx_dbm: f64,
    pub degradation_rate: f64,
    pub days_degrading: u32,
    pub micro_dropout_count: u32,
    pub impact: ChurnImpact,
    /// Estimated (assumption-based) 90-day churn probability.
    pub estimated_churn_probability_90day: f64,
    /// Estimated ANNUAL revenue at risk = assumed ARPU x probability x 12.
    pub estimated_annual_revenue_at_risk: f64,
    /// The assumption set that produced the estimates above.
    pub assumptions: ChurnAssumptions,
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
///   3. Classify impact and compute estimated churn probability
///   4. Estimate annual revenue at risk = assumed ARPU * churn_prob * 12 months
///
/// Only returns ONTs with estimated churn probability above the baseline.
/// Uses the default assumption set — see `predict_churn_risk_with_assumptions`.
pub fn predict_churn_risk(readings: &[OntReading], arpu: f64) -> Vec<ChurnRisk> {
    predict_churn_risk_with_assumptions(readings, &ChurnAssumptions::with_arpu(arpu))
}

/// Predict churn risk with an explicit, operator-supplied assumption set.
///
/// ONTs with no usable Rx readings produce NO score: missing data is not
/// evidence of degradation (a polling gap must never score a healthy ONT
/// as Severe).
pub fn predict_churn_risk_with_assumptions(
    readings: &[OntReading],
    assumptions: &ChurnAssumptions,
) -> Vec<ChurnRisk> {
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

        // Get the latest plausible Rx reading. Missing Rx -> no score:
        // never substitute a pessimistic default for absent data.
        let current_rx = match ont_readings.iter().rev().find_map(|r| sane_rx(r)) {
            Some(rx) => rx,
            None => continue,
        };

        // Build time-series of Rx power for linear regression
        // (sentinels and implausible values excluded).
        let first_ts = ont_readings[0].timestamp;
        let points: Vec<(f64, f64)> = ont_readings
            .iter()
            .filter_map(|r| {
                sane_rx(r).map(|rx| {
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
                // Unknown is not evidence of a dropout or a recovery.
                OntReadingStatus::Unknown => {}
            }
        }

        // Classify impact and base (assumed) churn probability
        let (impact, mut churn_prob) = classify_impact(current_rx, slope, assumptions);

        // Micro-dropouts increase the assumed churn probability
        if micro_dropouts > 5 {
            churn_prob += assumptions.micro_dropout_bonus;
        }

        // Cap at 95%
        churn_prob = churn_prob.min(0.95);

        // Only report if above baseline
        if churn_prob <= assumptions.baseline_probability {
            continue;
        }

        let estimated_annual_revenue_at_risk = assumptions.monthly_arpu * churn_prob * 12.0;

        results.push(ChurnRisk {
            ont_serial: serial,
            current_rx_dbm: current_rx,
            degradation_rate: slope,
            days_degrading: days_span,
            micro_dropout_count: micro_dropouts,
            impact,
            estimated_churn_probability_90day: churn_prob,
            estimated_annual_revenue_at_risk,
            assumptions: assumptions.clone(),
        });
    }

    // Sort by estimated churn probability descending
    results.sort_by(|a, b| {
        b.estimated_churn_probability_90day
            .partial_cmp(&a.estimated_churn_probability_90day)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Classify the customer-perceived impact from current Rx power and degradation slope.
/// Returns (impact, assumed_base_churn_probability).
fn classify_impact(current_rx: f64, slope: f64, a: &ChurnAssumptions) -> (ChurnImpact, f64) {
    if current_rx > -20.0 && slope > -0.01 {
        (ChurnImpact::None, a.baseline_probability)
    } else if current_rx > -22.0 && slope > -0.03 {
        (ChurnImpact::Subtle, a.subtle_probability)
    } else if current_rx > -24.0 && slope > -0.05 {
        (ChurnImpact::Noticeable, a.noticeable_probability)
    } else {
        (ChurnImpact::Severe, a.severe_probability)
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
            ..Default::default()
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
    fn test_churn_missing_rx_produces_no_score() {
        // An ONT with a polling gap (readings exist but no Rx values at all)
        // must produce NO churn score. The old code defaulted missing Rx to
        // -30 dBm, scoring a healthy ONT as Severe.
        let now = Utc::now();
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "NORX01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    None, // no Rx data — polling gap
                )
            })
            .collect();

        let risks = predict_churn_risk(&readings, 100.0);
        assert!(
            risks.is_empty(),
            "missing Rx is missing data, not degradation: {:?}",
            risks
        );
    }

    #[test]
    fn test_churn_sentinel_rx_produces_no_score() {
        // Vendor "no reading" sentinels (e.g. Huawei i32::MAX / 100) must be
        // dropped, not scored.
        let now = Utc::now();
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "SENT01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(21_474_836.47), // sentinel, not a measurement
                )
            })
            .collect();

        let risks = predict_churn_risk(&readings, 100.0);
        assert!(risks.is_empty(), "sentinel Rx must not be scored: {:?}", risks);
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
            risk.estimated_churn_probability_90day > risk.assumptions.baseline_probability,
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
            risk.estimated_churn_probability_90day >= 0.40,
            "Expected >= 40% churn prob, got {}",
            risk.estimated_churn_probability_90day
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
        let expected_rev = arpu * risk.estimated_churn_probability_90day * 12.0;
        assert!(
            (risk.estimated_annual_revenue_at_risk - expected_rev).abs() < 0.01,
            "Revenue at risk should be arpu * prob * 12: expected {}, got {}",
            expected_rev,
            risk.estimated_annual_revenue_at_risk
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
            with_drop.estimated_churn_probability_90day > no_drop.estimated_churn_probability_90day,
            "Micro-dropouts should increase churn probability: {} > {}",
            with_drop.estimated_churn_probability_90day,
            no_drop.estimated_churn_probability_90day
        );
    }
}
