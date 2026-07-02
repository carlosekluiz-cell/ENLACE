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
// Direction/wavelength model: this module models the DOWNSTREAM path —
// OLT launch power minus ODN losses should equal the ONT-side downstream
// Rx (`OntReading.rx_power_dbm` is ONT-side downstream; see detection/mod.rs).
// Downstream wavelengths: 1490 nm (GPON) / 1577 nm (XGS-PON), which
// attenuate at ~0.25 dB/km — NOT the 0.35 dB/km of the 1310/1270 nm
// upstream band. Do not mix this up with `vendors::OntData.rx_power_dbm`,
// which is the OLT-side UPSTREAM Rx (predictions/mod.rs documents that side).
//
// Detection method:
//   1. For each ONT, calculate average online Rx/Tx power
//   2. Calculate expected fibre attenuation: downstream dB/km x distance
//   3. Splitter loss from operator topology; if absent, INFER from ONT count
//      and flag `splitter_assumed`, widening the excess-loss tolerance by the
//      inter-ratio step (~3.5 dB) so an assumption error can't flag a
//      port-wide "excess loss"
//   4. Calculate expected connector loss: 0.5 dB x 4 connectors
//   5. Compare expected vs actual to find excess loss
//   6. Classify margin relative to -28 dBm receiver sensitivity

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{sane_rx, OntReading, OntReadingStatus, PonTechnology, PonTopology};

/// Downstream fibre attenuation (dB/km) at 1490 nm (GPON downstream).
const FIBRE_ATTEN_1490_DB_PER_KM: f64 = 0.25;

/// Downstream fibre attenuation (dB/km) at 1577 nm (XGS-PON downstream).
const FIBRE_ATTEN_1577_DB_PER_KM: f64 = 0.25;

/// Insertion loss for a 1:32 splitter in dB.
const SPLITTER_LOSS_32_DB: f64 = 17.5;

/// Insertion loss for a 1:64 splitter in dB.
const SPLITTER_LOSS_64_DB: f64 = 21.0;

/// Loss per connector in dB.
const CONNECTOR_LOSS_DB: f64 = 0.5;

/// Typical number of connectors in an ODN path.
const TYPICAL_CONNECTORS: u32 = 4;

/// Excess loss threshold (dB) above which we flag a probable issue —
/// applies when the splitter ratio is KNOWN from topology.
const EXCESS_LOSS_THRESHOLD_DB: f64 = 3.0;

/// Extra tolerance (dB) added to every excess-loss decision when the
/// splitter ratio is only ASSUMED from subscriber count. The step between
/// adjacent split ratios (1:32 -> 1:64) is ~3.5 dB, so an assumption error
/// alone can produce up to ~3.5 dB of phantom "excess loss".
const SPLITTER_ASSUMPTION_TOLERANCE_DB: f64 =
    SPLITTER_LOSS_64_DB - SPLITTER_LOSS_32_DB;

/// Maximum ONT count for inferring a 1:32 splitter (above this we assume 1:64).
const MAX_ONTS_FOR_32_SPLIT: usize = 32;

/// Per-technology downstream launch power and receiver sensitivity.
/// GPON Class B+ launch ~ +1.5..+5 dBm (use +3.0 typical), sensitivity -28 dBm.
/// XGS-PON N1 launch ~ +2.0..+5.0 dBm (use +3.5 typical), sensitivity -28 dBm.
fn tech_params(tech: PonTechnology) -> (f64, f64, f64) {
    // (olt_tx_dbm, downstream_atten_db_per_km, sensitivity_dbm)
    match tech {
        PonTechnology::Gpon => (3.0, FIBRE_ATTEN_1490_DB_PER_KM, -28.0),
        PonTechnology::XgsPon => (3.5, FIBRE_ATTEN_1577_DB_PER_KM, -28.0),
    }
}

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
    /// True when the splitter ratio was INFERRED from subscriber count
    /// because no topology entry exists for this port. When set, the
    /// expected-loss model carries up to ~3.5 dB of systematic uncertainty
    /// and excess-loss decisions use a widened tolerance.
    pub splitter_assumed: bool,
    /// The excess-loss threshold (dB) actually applied for this ONT
    /// (widened when `splitter_assumed`).
    pub excess_threshold_db: f64,
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
/// This is a FALLBACK inference only — a real 1:64 splitter with 20
/// subscribers would be modelled as 1:32 (~3.5 dB systematic error), which is
/// why results derived from it carry `splitter_assumed = true` and a widened
/// excess-loss tolerance.
fn infer_splitter_loss(onts_on_port: usize) -> f64 {
    if onts_on_port <= MAX_ONTS_FOR_32_SPLIT {
        SPLITTER_LOSS_32_DB
    } else {
        SPLITTER_LOSS_64_DB
    }
}

/// Insertion loss (dB) for a configured splitter ratio.
fn splitter_loss_for_ratio(ratio: u32) -> f64 {
    match ratio {
        2 => 3.7,
        4 => 7.3,
        8 => 10.5,
        16 => 14.0,
        32 => SPLITTER_LOSS_32_DB,
        64 => SPLITTER_LOSS_64_DB,
        128 => 24.5,
        // Theoretical 10*log10(n) plus ~1 dB excess for non-standard ratios.
        n => 10.0 * (n.max(2) as f64).log10() + 1.0,
    }
}

/// Analyze the optical power budget without topology data (all splitter
/// ratios inferred and flagged as assumed). Prefer
/// [`analyze_optical_budget_with_topology`] whenever the operator can supply
/// real splitter ratios.
pub fn analyze_optical_budget(readings: &[OntReading]) -> Vec<OpticalBudget> {
    analyze_optical_budget_with_topology(readings, None)
}

/// Analyze the optical power budget for every ONT that has distance data.
///
/// Splitter ratios come from `topology` when available; ports missing from
/// the topology fall back to subscriber-count inference with
/// `splitter_assumed = true` and a widened excess-loss tolerance. ONTs
/// without `distance_meters` are skipped because fibre attenuation cannot
/// be estimated.
pub fn analyze_optical_budget_with_topology(
    readings: &[OntReading],
    topology: Option<&PonTopology>,
) -> Vec<OpticalBudget> {
    if readings.is_empty() {
        return Vec::new();
    }

    let technology = topology.map(|t| t.technology).unwrap_or_default();
    let (olt_tx_dbm, atten_db_per_km, sensitivity_dbm) = tech_params(technology);

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

        if let Some(rx) = sane_rx(r) {
            entry.rx_sum += rx;
            entry.rx_count += 1;
        }
        if let Some(tx) = r.tx_power_dbm.and_then(crate::vendors::snmp_helper::plausible_dbm) {
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

        let fibre_loss = atten_db_per_km * (distance_m as f64 / 1000.0);

        // Splitter ratio: topology first, count-inference as a flagged fallback.
        let configured_ratio = topology
            .and_then(|t| t.splitter_ratio_by_port.get(acc.port.as_str()))
            .copied();
        let (splitter_loss, splitter_assumed) = match configured_ratio {
            Some(ratio) => (splitter_loss_for_ratio(ratio), false),
            None => {
                let port_ont_count = onts_per_port
                    .get(acc.port.as_str())
                    .map(|v| v.len())
                    .unwrap_or(1);
                (infer_splitter_loss(port_ont_count), true)
            }
        };
        let connector_loss = CONNECTOR_LOSS_DB * TYPICAL_CONNECTORS as f64;

        // Widened tolerance when the splitter ratio is an assumption:
        // an inference error alone shifts expected_rx by ~3.5 dB, so
        // anything inside that band is indistinguishable from a wrong guess.
        let excess_threshold = if splitter_assumed {
            EXCESS_LOSS_THRESHOLD_DB + SPLITTER_ASSUMPTION_TOLERANCE_DB
        } else {
            EXCESS_LOSS_THRESHOLD_DB
        };

        let total_expected_loss = fibre_loss + splitter_loss + connector_loss;
        let expected_rx = olt_tx_dbm - total_expected_loss;
        let excess_loss = expected_rx - avg_rx;
        let margin = avg_rx - sensitivity_dbm;

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
            splitter_assumed,
            excess_threshold_db: excess_threshold,
        });
    }

    // Second pass: classify probable issues using per-port context
    for budget in &mut results {
        let port_excesses = port_excess.get(&budget.port).unwrap();
        let port_count = port_excesses.len();

        // The moderate ("splice degradation") band also shifts up when the
        // splitter is assumed: 1 dB of "excess" is meaningless inside a
        // ~3.5 dB assumption error.
        let moderate_floor = budget.excess_threshold_db - EXCESS_LOSS_THRESHOLD_DB + 1.0;

        // Check if ALL ONTs on the port have low margin (insufficient OLT power)
        let low_margin_count = port_excesses
            .iter()
            .filter(|&&e| e > moderate_floor)
            .count();
        let all_low = port_count > 1 && low_margin_count == port_count;

        if budget.excess_loss_db > budget.excess_threshold_db {
            if all_low {
                // Every ONT on the port has significant excess — port-wide issue
                budget.probable_issue = Some(BudgetIssue::InsufficientOltPower);
            } else {
                // Check if peers at similar distances have similar excess (splitter overloss)
                let peer_excess: Vec<f64> = port_excesses
                    .iter()
                    .copied()
                    .filter(|&e| e > budget.excess_threshold_db)
                    .collect();
                if peer_excess.len() > 1 && peer_excess.len() as f64 / port_count as f64 > 0.7 {
                    budget.probable_issue = Some(BudgetIssue::SplitterOverloss);
                } else {
                    // Individual ONT excess — likely connector or bend
                    budget.probable_issue = Some(BudgetIssue::ExcessConnectorLoss);
                }
            }
        } else if budget.excess_loss_db > moderate_floor {
            // Moderate excess — splice degradation
            budget.probable_issue = Some(BudgetIssue::SpliceDegradation);
        }
        // else: no issue detected (or hidden inside assumption tolerance)
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
            ..Default::default()
        }
    }

    fn topology_1_32(port: &str) -> PonTopology {
        let mut t = PonTopology::default();
        t.splitter_ratio_by_port.insert(port.to_string(), 32);
        t
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
        // Downstream 1490 nm: 0.25 dB/km
        assert!((b.fibre_loss_db - 0.25).abs() < 0.01);
        assert!((b.splitter_loss_db - SPLITTER_LOSS_32_DB).abs() < 0.01);
        assert!((b.connector_loss_db - 2.0).abs() < 0.01);
        // expected_rx = 3.0 - (0.25 + 17.5 + 2.0) = 3.0 - 19.75 = -16.75
        assert!((b.expected_rx_dbm - (-16.75)).abs() < 0.01);
        // margin = -18.0 - (-28.0) = 10.0
        assert!((b.margin_db - 10.0).abs() < 0.01);
        assert_eq!(b.budget_status, BudgetStatus::Excellent);
        assert!(b.splitter_assumed, "no topology supplied -> ratio must be flagged as assumed");
        assert!(b.probable_issue.is_none(),
            "1.25 dB excess is inside the assumed-splitter tolerance");
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
        // fibre_loss = 0.25 * 3 = 0.75
        assert!((b.fibre_loss_db - 0.75).abs() < 0.01);
        // expected_rx = 3.0 - (0.75 + 17.5 + 2.0) = -17.25
        // excess = -17.25 - (-27.5) = 10.25 — beyond even the widened threshold
        assert!(b.excess_loss_db > b.excess_threshold_db);
        assert!(b.probable_issue.is_some(), "Critical margin with high excess should flag an issue");
    }

    #[test]
    fn test_budget_excess_loss_connector_with_known_splitter() {
        // Topology says 1:32, so the strict 3 dB threshold applies.
        // expected_rx = 3.0 - (0.25 + 17.5 + 2.0) = -16.75
        // 5 dB excess: actual_rx = -21.75 -> ExcessConnectorLoss
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT003", "0/1/0", now, OntReadingStatus::Online, Some(-21.75), Some(2.0), Some(1000)),
        ];

        let topo = topology_1_32("0/1/0");
        let results = analyze_optical_budget_with_topology(&readings, Some(&topo));
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert!(!b.splitter_assumed, "topology-supplied ratio must not be flagged assumed");
        assert!((b.excess_threshold_db - EXCESS_LOSS_THRESHOLD_DB).abs() < 0.01);
        assert!((b.excess_loss_db - 5.0).abs() < 0.1);
        assert_eq!(b.probable_issue, Some(BudgetIssue::ExcessConnectorLoss));
    }

    #[test]
    fn test_budget_assumed_splitter_widens_tolerance() {
        // Same 5 dB apparent excess as above, but WITHOUT topology the
        // splitter is assumed and 5 dB sits inside the widened tolerance
        // (3.0 + 3.5 dB): an inference error alone could explain it, so no
        // "excess loss" issue may be flagged.
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT003", "0/1/0", now, OntReadingStatus::Online, Some(-21.75), Some(2.0), Some(1000)),
        ];

        let results = analyze_optical_budget(&readings);
        assert_eq!(results.len(), 1);

        let b = &results[0];
        assert!(b.splitter_assumed);
        assert!(
            (b.excess_threshold_db
                - (EXCESS_LOSS_THRESHOLD_DB + SPLITTER_ASSUMPTION_TOLERANCE_DB))
                .abs()
                < 0.01
        );
        assert!((b.excess_loss_db - 5.0).abs() < 0.1);
        assert!(
            b.probable_issue != Some(BudgetIssue::ExcessConnectorLoss)
                && b.probable_issue != Some(BudgetIssue::SplitterOverloss)
                && b.probable_issue != Some(BudgetIssue::InsufficientOltPower),
            "5 dB excess under an assumed splitter must not flag excess loss, got {:?}",
            b.probable_issue
        );
    }

    #[test]
    fn test_budget_splitter_type_inference() {
        // 40 ONTs on the same port -> 1:64 splitter inferred (and flagged assumed)
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

        // All should use 1:64 splitter loss and carry the assumed flag
        for b in &results {
            assert!((b.splitter_loss_db - SPLITTER_LOSS_64_DB).abs() < 0.01,
                "40 ONTs on port should infer 1:64 splitter, got {}", b.splitter_loss_db);
            assert!(b.splitter_assumed);
        }
    }

    #[test]
    fn test_budget_xgs_pon_technology() {
        // XGS-PON topology: downstream modelled at 1577 nm with N1 launch power.
        let now = Utc::now();
        let readings = vec![
            make_reading("ONTX01", "0/9/0", now, OntReadingStatus::Online, Some(-18.0), Some(2.0), Some(2000)),
        ];

        let mut topo = topology_1_32("0/9/0");
        topo.technology = PonTechnology::XgsPon;
        let results = analyze_optical_budget_with_topology(&readings, Some(&topo));
        assert_eq!(results.len(), 1);

        let b = &results[0];
        // expected_rx = 3.5 - (0.25*2 + 17.5 + 2.0) = 3.5 - 20.0 = -16.5
        assert!((b.expected_rx_dbm - (-16.5)).abs() < 0.01);
        assert!(!b.splitter_assumed);
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
