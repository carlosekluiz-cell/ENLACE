// SPDX-License-Identifier: Apache-2.0
// Optical Budget Analyzer
//
// Analyzes the optical power budget for each ONT path and attributes loss
// to components: fibre attenuation, splitter loss, connector loss, or
// excess loss (bend/splice).
//
// When a customer has poor signal (-28 dBm), this tells the technician
// WHERE the problem is. Excess loss > 3 dB means there is a problem
// somewhere in the path (dirty connector, bad splice, macro-bend).
//
// Detection method:
//   1. For each ONT, calculate average online Rx/Tx power
//   2. Calculate expected fibre attenuation: 0.35 dB/km x distance
//   3. Estimate splitter loss from ONT count on port (1:32 or 1:64)
//   4. Calculate expected connector loss: 0.5 dB x 4 connectors
//   5. Compare expected vs actual to find excess loss
//   6. Classify margin relative to -28 dBm sensitivity threshold

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// OLT transmit power in dBm (Class B+ typical).
const OLT_TX_POWER_DBM: f64 = 3.0;

/// Fibre attenuation at 1310 nm in dB per kilometre.
const FIBRE_ATTENUATION_DB_PER_KM: f64 = 0.35;

/// Insertion loss for a 1:32 splitter in dB.
const SPLITTER_LOSS_32_DB: f64 = 17.5;

/// Insertion loss for a 1:64 splitter in dB.
const SPLITTER_LOSS_64_DB: f64 = 21.0;

/// Loss per connector in dB.
const CONNECTOR_LOSS_DB: f64 = 0.5;

/// Typical number of connectors in an ODN path.
const TYPICAL_CONNECTORS: u32 = 4;

/// Class B+ receiver sensitivity in dBm.
const SENSITIVITY_DBM: f64 = -28.0;

/// Excess loss threshold (dB) above which we flag a probable issue.
const EXCESS_LOSS_THRESHOLD_DB: f64 = 3.0;

/// Maximum ONT count for inferring a 1:32 splitter (above this we assume 1:64).
const MAX_ONTS_FOR_32_SPLIT: usize = 32;

/// Optical budget analysis result for a single ONT path.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpticalBudget {
    pub ont_serial: String,
    pub port: String,
    pub distance_m: u32,
    pub avg_rx_power_dbm: f64,
    pub avg_tx_power_dbm: f64,
    pub fibre_loss_db: f64,
    pub splitter_loss_db: f64,
    pub connector_loss_db: f64,
    pub expected_rx_dbm: f64,
    pub excess_loss_db: f64,
    pub margin_db: f64,
    pub budget_status: BudgetStatus,
    pub probable_issue: Option<BudgetIssue>,
}

/// Classification of the optical margin relative to receiver sensitivity.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum BudgetStatus {
    Excellent,
    Good,
    Marginal,
    Critical,
    Failed,
}

/// Probable root cause when excess loss is detected.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum BudgetIssue {
    /// Excess > 3 dB and no distance correlation across peers.
    ExcessConnectorLoss,
    /// Excess > 3 dB with distance/temperature sensitivity.
    MacroBend,
    /// Excess 1-3 dB, consistent over time.
    SpliceDegradation,
    /// All ONTs on the same splitter have similar excess loss.
    SplitterOverloss,
    /// All ONTs on the port have low margin.
    InsufficientOltPower,
}

/// Classify the optical margin into a budget status.
fn classify_margin(margin_db: f64) -> BudgetStatus {
    if margin_db < 0.0 {
        BudgetStatus::Failed
    } else if margin_db < 1.0 {
        BudgetStatus::Critical
    } else if margin_db < 3.0 {
        BudgetStatus::Marginal
    } else if margin_db <= 6.0 {
        BudgetStatus::Good
    } else {
        BudgetStatus::Excellent
    }
}

/// Determine splitter insertion loss from the number of ONTs on the port.
///
/// If the port has 32 or fewer ONTs we assume a 1:32 splitter; otherwise 1:64.
fn infer_splitter_loss(onts_on_port: usize) -> f64 {
    if onts_on_port <= MAX_ONTS_FOR_32_SPLIT {
        SPLITTER_LOSS_32_DB
    } else {
        SPLITTER_LOSS_64_DB
    }
}

/// Analyze the optical power budget for every ONT that has distance data.
///
/// Groups readings by PON port to infer splitter type, then computes expected
/// vs actual received power for each ONT. ONTs without `distance_meters` are
/// skipped because fibre attenuation cannot be estimated.
pub fn analyze_optical_budget(readings: &[OntReading]) -> Vec<OpticalBudget> {
    if readings.is_empty() {
        return Vec::new();
    }

    // Count unique ONTs per port for splitter inference
    let mut onts_per_port: HashMap<&str, Vec<&str>> = HashMap::new();
    for r in readings {
        let serials = onts_per_port.entry(&r.pon_port).or_default();
        if !serials.contains(&r.serial_number.as_str()) {
            serials.push(&r.serial_number);
        }
    }

    // Compute average Rx/Tx power per ONT (online readings only)
    struct OntAccum {
        port: String,
        distance_m: Option<u32>,
        rx_sum: f64,
        rx_count: u32,
        tx_sum: f64,
        tx_count: u32,
    }

    let mut accum: HashMap<String, OntAccum> = HashMap::new();

    for r in readings {
        if r.status != OntReadingStatus::Online {
            continue;
        }

        let entry = accum.entry(r.serial_number.clone()).or_insert_with(|| OntAccum {
            port: r.pon_port.clone(),
            distance_m: r.distance_meters,
            rx_sum: 0.0,
            rx_count: 0,
            tx_sum: 0.0,
            tx_count: 0,
        });

        // Update distance if we get a value and didn't have one
        if entry.distance_m.is_none() && r.distance_meters.is_some() {
            entry.distance_m = r.distance_meters;
        }

        if let Some(rx) = r.rx_power_dbm {
            entry.rx_sum += rx;
            entry.rx_count += 1;
        }
        if let Some(tx) = r.tx_power_dbm {
            entry.tx_sum += tx;
            entry.tx_count += 1;
        }
    }

    // Compute per-port average excess loss (for detecting port-wide issues)
    let mut port_excess: HashMap<String, Vec<f64>> = HashMap::new();

    let mut results = Vec::new();

    for (serial, acc) in &accum {
        // Skip ONTs without distance data — cannot estimate fibre loss
        let distance_m = match acc.distance_m {
            Some(d) => d,
            None => continue,
        };

        // Need at least one Rx and one Tx reading
        if acc.rx_count == 0 || acc.tx_count == 0 {
            continue;
        }

        let avg_rx = acc.rx_sum / acc.rx_count as f64;
        let avg_tx = acc.tx_sum / acc.tx_count as f64;

        let fibre_loss = FIBRE_ATTENUATION_DB_PER_KM * (distance_m as f64 / 1000.0);
        let port_ont_count = onts_per_port
            .get(acc.port.as_str())
            .map(|v| v.len())
            .unwrap_or(1);
        let splitter_loss = infer_splitter_loss(port_ont_count);
        let connector_loss = CONNECTOR_LOSS_DB * TYPICAL_CONNECTORS as f64;

        let total_expected_loss = fibre_loss + splitter_loss + connector_loss;
        let expected_rx = OLT_TX_POWER_DBM - total_expected_loss;
        let excess_loss = expected_rx - avg_rx;
        let margin = avg_rx - SENSITIVITY_DBM;

        let budget_status = classify_margin(margin);

        // Track excess loss per port for port-wide issue detection
        port_excess
            .entry(acc.port.clone())
            .or_default()
            .push(excess_loss);

        results.push(OpticalBudget {
            ont_serial: serial.clone(),
            port: acc.port.clone(),
            distance_m,
            avg_rx_power_dbm: avg_rx,
            avg_tx_power_dbm: avg_tx,
            fibre_loss_db: fibre_loss,
            splitter_loss_db: splitter_loss,
            connector_loss_db: connector_loss,
            expected_rx_dbm: expected_rx,
            excess_loss_db: excess_loss,
            margin_db: margin,
            budget_status,
            probable_issue: None, // filled in second pass
        });
    }

    // Second pass: classify probable issues using per-port context
    for budget in &mut results {
        let port_excesses = port_excess.get(&budget.port).unwrap();
        let port_count = port_excesses.len();

        // Check if ALL ONTs on the port have low margin (insufficient OLT power)
        let low_margin_count = port_excesses
            .iter()
            .filter(|&&e| e > 1.0)
            .count();
        let all_low = port_count > 1 && low_margin_count == port_count;

        if budget.excess_loss_db > EXCESS_LOSS_THRESHOLD_DB {
            if all_low {
                // Every ONT on the port has significant excess — port-wide issue
                budget.probable_issue = Some(BudgetIssue::InsufficientOltPower);
            } else {
                // Check if peers at similar distances have similar excess (splitter overloss)
                let peer_excess: Vec<f64> = port_excesses
                    .iter()
                    .copied()
                    .filter(|&e| e > EXCESS_LOSS_THRESHOLD_DB)
                    .collect();
                if peer_excess.len() > 1 && peer_excess.len() as f64 / port_count as f64 > 0.7 {
                    budget.probable_issue = Some(BudgetIssue::SplitterOverloss);
                } else {
                    // Individual ONT excess — likely connector or bend
                    budget.probable_issue = Some(BudgetIssue::ExcessConnectorLoss);
                }
            }
        } else if budget.excess_loss_db > 1.0 {
            // Moderate excess — splice degradation
            budget.probable_issue = Some(BudgetIssue::SpliceDegradation);
        }
        // else: no issue detected
    }

    // Sort by margin ascending (worst first) for prioritization
    results.sort_by(|a, b| {
        a.margin_db
            .partial_cmp(&b.margin_db)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{DateTime, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
        tx: Option<f64>,
        distance: Option<u32>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: tx,
            status,
            distance_meters: distance,
            eth_speed_mbps: None,
            last_down_cause: None,
        }
    }

    #[test]
    fn test_budget_excellent_margin() {
        // ONT at 1 km, Rx = -18 dBm -> margin = 10 dB -> Excellent
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT001", "0/1/0", now, OntReadingStatus::Online, Some(-18.0), Some(2.0), Some(1000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert_eq!(b.ont_serial, "ONT001");
        assert_eq!(b.distance_m, 1000);
        assert!((b.avg_rx_power_dbm - (-18.0)).abs() < 0.01);
        assert!((b.fibre_loss_db - 0.35).abs() < 0.01);
        assert!((b.splitter_loss_db - SPLITTER_LOSS_32_DB).abs() < 0.01);
        assert!((b.connector_loss_db - 2.0).abs() < 0.01);
        // expected_rx = 3.0 - (0.35 + 17.5 + 2.0) = 3.0 - 19.85 = -16.85
        assert!((b.expected_rx_dbm - (-16.85)).abs() < 0.01);
        // margin = -18.0 - (-28.0) = 10.0
        assert!((b.margin_db - 10.0).abs() < 0.01);
        assert_eq!(b.budget_status, BudgetStatus::Excellent);
        assert!(b.probable_issue.is_none() || b.probable_issue == Some(BudgetIssue::SpliceDegradation),
            "Small excess loss at most triggers splice degradation");
    }

    #[test]
    fn test_budget_critical_margin() {
        // ONT at 3 km, Rx = -27.5 dBm -> margin = 0.5 dB -> Critical
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT002", "0/1/0", now, OntReadingStatus::Online, Some(-27.5), Some(2.0), Some(3000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert_eq!(b.budget_status, BudgetStatus::Critical);
        assert!((b.margin_db - 0.5).abs() < 0.01);
        // fibre_loss = 0.35 * 3 = 1.05
        assert!((b.fibre_loss_db - 1.05).abs() < 0.01);
        // expected_rx = 3.0 - (1.05 + 17.5 + 2.0) = -17.55
        // excess = -17.55 - (-27.5) = 9.95
        assert!(b.excess_loss_db > EXCESS_LOSS_THRESHOLD_DB);
        assert!(b.probable_issue.is_some(), "Critical margin with high excess should flag an issue");
    }

    #[test]
    fn test_budget_excess_loss_connector() {
        // ONT at 1 km with 5 dB excess loss -> ExcessConnectorLoss
        // expected_rx = 3.0 - (0.35 + 17.5 + 2.0) = -16.85
        // To get 5 dB excess: actual_rx = -16.85 - 5.0 = -21.85
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT003", "0/1/0", now, OntReadingStatus::Online, Some(-21.85), Some(2.0), Some(1000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert!((b.excess_loss_db - 5.0).abs() < 0.1);
        assert_eq!(b.probable_issue, Some(BudgetIssue::ExcessConnectorLoss));
    }

    #[test]
    fn test_budget_splitter_type_inference() {
        // 40 ONTs on the same port -> 1:64 splitter inferred
        let now = Utc::now();
        let mut readings = Vec::new();
        for i in 0..40 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, "0/2/0", now, OntReadingStatus::Online,
                Some(-22.0), Some(2.0), Some(2000),
            ));
        }

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 40);

        // All should use 1:64 splitter loss
        for b in &results {
            assert!((b.splitter_loss_db - SPLITTER_LOSS_64_DB).abs() < 0.01,
                "40 ONTs on port should infer 1:64 splitter, got {}", b.splitter_loss_db);
        }
    }

    #[test]
    fn test_budget_no_distance_skip() {
        // ONT with no distance data should be skipped
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT_NO_DIST", "0/1/0", now, OntReadingStatus::Online, Some(-20.0), Some(2.0), None),
            make_reading("ONT_WITH_DIST", "0/1/0", now, OntReadingStatus::Online, Some(-20.0), Some(2.0), Some(1500)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].ont_serial, "ONT_WITH_DIST");
    }

    #[test]
    fn test_budget_failed_below_sensitivity() {
        // ONT at -29 dBm -> margin = -1.0 -> Failed
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT_FAIL", "0/1/0", now, OntReadingStatus::Online, Some(-29.0), Some(2.0), Some(5000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert_eq!(b.budget_status, BudgetStatus::Failed);
        assert!((b.margin_db - (-1.0)).abs() < 0.01);
        assert!(b.probable_issue.is_some(), "Failed budget should flag an issue");
    }

    #[test]
    fn test_budget_averages_multiple_readings() {
        // Multiple readings for the same ONT should be averaged
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT010", "0/1/0", now, OntReadingStatus::Online, Some(-20.0), Some(2.0), Some(1000)),
            make_reading("ONT010", "0/1/0", now, OntReadingStatus::Online, Some(-22.0), Some(2.4), Some(1000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert!((b.avg_rx_power_dbm - (-21.0)).abs() < 0.01);
        assert!((b.avg_tx_power_dbm - 2.2).abs() < 0.01);
    }

    #[test]
    fn test_budget_offline_readings_excluded() {
        // Offline readings should not contribute to averages
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT011", "0/1/0", now, OntReadingStatus::Online, Some(-20.0), Some(2.0), Some(1000)),
            make_reading("ONT011", "0/1/0", now, OntReadingStatus::Offline, None, None, Some(1000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);
        assert!((results[0].avg_rx_power_dbm - (-20.0)).abs() < 0.01);
    }
}
