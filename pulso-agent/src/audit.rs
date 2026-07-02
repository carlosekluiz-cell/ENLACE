// SPDX-License-Identifier: Apache-2.0
// Audit Engine
//
// Takes a Vec<OntReading> (from CSV parser), builds a latest-snapshot OltData,
// runs all 10 detection modules + fault detection + diagnostics, and produces
// a serializable AuditResult struct with all findings.

use std::collections::HashMap;

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::Serialize;

use crate::config::{FaultDetectionConfig, FaultSeverityConfig};
use crate::csv_import::{self, ImportReport};
use crate::detection::tickets::{DetectionResults, generate_fault_tickets};
use crate::detection::{OntReading, OntReadingStatus};
use crate::diagnostics;
use crate::fault::FaultDetector;
use crate::vendors::{ExtendedOntMetrics, OltData, OntData, OntStatus, PonPortData};

/// Default ARPU used for revenue calculations when not specified.
const DEFAULT_ARPU: f64 = 89.90;

/// Max skipped-row samples surfaced to clients (server logs keep the full set).
const MAX_CLIENT_SKIP_SAMPLES: usize = 5;

/// Complete audit result combining all detection module outputs.
#[derive(Debug, Clone, Serialize)]
pub struct AuditResult {
    pub summary: AuditSummary,
    /// CSV import honesty counters (rows skipped, unknown statuses, snapshot
    /// mode). Present when the audit was fed from a CSV import; None when the
    /// readings came from elsewhere.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub import_report: Option<ImportReportSummary>,
    pub faults: serde_json::Value,
    pub ghosts: serde_json::Value,
    pub capacity: serde_json::Value,
    pub flapping: serde_json::Value,
    pub weather_correlation: serde_json::Value,
    pub reflectance: serde_json::Value,
    pub optical_budget: serde_json::Value,
    pub sfp_health: serde_json::Value,
    pub churn_risk: serde_json::Value,
    pub tickets: serde_json::Value,
    pub diagnostics: serde_json::Value,
    pub impact: serde_json::Value,
    pub onts: serde_json::Value,
}

/// Summary statistics for the audit.
#[derive(Debug, Clone, Serialize)]
pub struct AuditSummary {
    pub total_onts: usize,
    pub total_readings: usize,
    pub analysis_period_days: i64,
    pub health_score: u8,
    /// ONTs Online or LowSignal in the latest snapshot.
    pub online: usize,
    /// ONTs Offline/PowerFail/FiberCut in the latest snapshot. ONTs with
    /// Unknown status (unrecognized vendor vocabulary / missing status) are
    /// NOT counted here — Unknown is not an outage.
    pub offline: usize,
    /// ONTs whose status could not be determined in the latest snapshot.
    /// Counted separately so totals reconcile:
    /// total_onts = online + offline + unknown.
    pub unknown: usize,
    pub avg_rx_dbm: f64,
    pub worst_rx_dbm: f64,
}

/// Client-safe view of a CSV [`ImportReport`]: same honesty counters, with
/// skip samples capped and stripped of anything path-like so server-side
/// file locations never leak into HTTP responses.
#[derive(Debug, Clone, Serialize)]
pub struct ImportReportSummary {
    /// Rows successfully converted into readings.
    pub rows_ok: usize,
    /// Rows dropped (structural errors, bad timestamps, missing serials).
    pub rows_skipped: usize,
    /// Up to MAX_CLIENT_SKIP_SAMPLES sanitized skip messages.
    pub skip_samples: Vec<String>,
    /// Non-empty cells whose value could not be parsed (kept as None).
    pub cells_unparsed: usize,
    /// Rows whose status value was not recognized (imported as Unknown).
    pub unknown_statuses: usize,
    /// Distinct unrecognized status values seen (normalized, up to 10).
    pub unknown_status_values: Vec<String>,
    /// True when the file had no timestamp column (snapshot export) and row
    /// timestamps were defaulted to the import/upload time.
    pub snapshot_mode: bool,
    /// Delimiter sniffed from the header line (",", ";" or "\t").
    pub delimiter: String,
}

impl From<&ImportReport> for ImportReportSummary {
    fn from(report: &ImportReport) -> Self {
        ImportReportSummary {
            rows_ok: report.rows_ok,
            rows_skipped: report.rows_skipped,
            skip_samples: report
                .skip_samples
                .iter()
                .take(MAX_CLIENT_SKIP_SAMPLES)
                .map(|s| sanitize_skip_sample(s))
                .collect(),
            cells_unparsed: report.cells_unparsed,
            unknown_statuses: report.unknown_statuses,
            unknown_status_values: report.unknown_status_values.clone(),
            snapshot_mode: report.snapshot_mode,
            delimiter: (report.delimiter as char).to_string(),
        }
    }
}

/// Strip absolute paths from a skip-sample message: any whitespace-delimited
/// token starting with '/' is replaced. Skip messages are error strings, but
/// wrapped parser errors can embed the (temp) file path.
fn sanitize_skip_sample(sample: &str) -> String {
    sample
        .split_whitespace()
        .map(|tok| if tok.starts_with('/') { "[path]" } else { tok })
        .collect::<Vec<_>>()
        .join(" ")
}

/// Operator-supplied context for an audit. Defaults are honest fallbacks:
/// UTC business hours and no known plant topology (detection modules then
/// flag splitter ratios as assumed and widen tolerances).
#[derive(Debug, Clone, Default)]
pub struct AuditOptions {
    /// Local-time offset applied to business-hours/day-night logic.
    pub utc_offset_hours: i32,
    /// Known plant topology (configured splitter ratios, PON technology).
    pub topology: Option<crate::detection::PonTopology>,
}

/// Parse a CSV file and run a full audit, surfacing the import quality
/// counters in the result. `default_timestamp` is applied to snapshot-mode
/// exports without a timestamp column (pass the upload/import time).
pub fn run_csv_audit(
    path: &std::path::Path,
    vendor: Option<&str>,
    default_timestamp: Option<DateTime<Utc>>,
) -> Result<AuditResult> {
    run_csv_audit_with_options(path, vendor, default_timestamp, &AuditOptions::default())
}

/// [`run_csv_audit`] with operator context (timezone offset, plant topology).
pub fn run_csv_audit_with_options(
    path: &std::path::Path,
    vendor: Option<&str>,
    default_timestamp: Option<DateTime<Utc>>,
    options: &AuditOptions,
) -> Result<AuditResult> {
    let report = csv_import::parse_csv_with_report(path, vendor, default_timestamp)?;
    let import_report = ImportReportSummary::from(&report);
    let mut result = run_audit_with_options(report.readings, options)?;
    result.import_report = Some(import_report);
    Ok(result)
}

/// Run a full audit on a set of ONT readings.
///
/// Steps:
///   1. Build latest snapshot (most recent reading per ONT -> OntData)
///   2. Run all detection modules on the readings
///   3. Run fault detector on the latest ONT snapshot
///   4. Run diagnostics::analyze_olt() on constructed OltData
///   5. Calculate health_score
///   6. Serialize everything to AuditResult
pub fn run_audit(readings: Vec<OntReading>) -> Result<AuditResult> {
    run_audit_with_options(readings, &AuditOptions::default())
}

/// [`run_audit`] with operator context (timezone offset, plant topology).
pub fn run_audit_with_options(
    readings: Vec<OntReading>,
    options: &AuditOptions,
) -> Result<AuditResult> {
    let total_readings = readings.len();

    if readings.is_empty() {
        anyhow::bail!("No readings to audit");
    }

    // Determine analysis period
    let min_ts = readings.iter().map(|r| r.timestamp).min().unwrap();
    let max_ts = readings.iter().map(|r| r.timestamp).max().unwrap();
    let analysis_period_days = (max_ts - min_ts).num_days().max(1);

    // 1. Build latest snapshot: most recent reading per ONT -> OntData
    let (ont_snapshot, pon_port_map) = build_latest_snapshot(&readings);

    // Build PON port data from the snapshot
    let pon_ports = build_pon_ports(&ont_snapshot, &pon_port_map);

    // Build OltData for diagnostics
    let olt_data = OltData {
        olt_id: "csv-audit".to_string(),
        vendor: "csv".to_string(),
        model: "import".to_string(),
        firmware: String::new(),
        serial: String::new(),
        uptime_seconds: 0,
        timestamp: Utc::now(),
        cpu_percent: None,
        memory_percent: None,
        temperature_celsius: None,
        power_supply_status: None,
        pon_ports,
        uplink_ports: Vec::new(),
        onts: ont_snapshot.clone(),
    };

    // 2. Run all detection modules
    let ghosts = crate::detection::ghost::detect_ghost_customers(&readings, DEFAULT_ARPU);
    let churn_risks = crate::detection::churn::predict_churn_risk(&readings, DEFAULT_ARPU);
    let capacity = crate::detection::capacity::predict_splitter_capacity_with_topology(
        &readings,
        options.topology.as_ref(),
    );
    let weather = crate::detection::weather::detect_weather_correlation_with_offset(
        &readings,
        options.utc_offset_hours,
    );
    let flapping = crate::detection::flapping::detect_flapping(&readings);
    let optical_budget = crate::detection::optical_budget::analyze_optical_budget_with_topology(
        &readings,
        options.topology.as_ref(),
    );
    let sfp_health = crate::detection::sfp_health::analyze_sfp_health(&readings);

    // Reflectance: run per unique port
    let unique_ports: Vec<String> = {
        let mut ports: Vec<String> = readings.iter().map(|r| r.pon_port.clone()).collect();
        ports.sort();
        ports.dedup();
        ports
    };
    let mut reflectance_events = Vec::new();
    for port in &unique_ports {
        let mut events = crate::detection::reflectance::detect_reflectance(&readings, port);
        reflectance_events.append(&mut events);
    }

    // Impact scoring: collect offline ONT serials from latest snapshot
    let offline_serials: Vec<String> = ont_snapshot
        .iter()
        .filter(|o| matches!(o.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut))
        .map(|o| o.serial_number.clone())
        .collect();
    let impact = if !offline_serials.is_empty() {
        Some(crate::detection::impact::score_fault_impact_with_offset(
            &offline_serials,
            &readings,
            Utc::now(),
            options.utc_offset_hours,
        ))
    } else {
        None
    };

    // Tickets
    let detection_results = DetectionResults {
        reflectance_events: reflectance_events.clone(),
        churn_risks: churn_risks.clone(),
        ghost_customers: ghosts.clone(),
        splitter_capacity: capacity.clone(),
        weather_correlations: weather.clone(),
    };
    let tickets = generate_fault_tickets(&detection_results, DEFAULT_ARPU);

    // 3. Replay fault detection across all time windows
    //    Group readings by timestamp, replay each snapshot through the detector
    let fault_config = FaultDetectionConfig {
        enabled: true,
        min_offline_onts: 3, // Lower threshold for CSV audit (catching more events)
        time_window_seconds: 60,
        severity: FaultSeverityConfig::default(),
    };
    let mut fault_detector = FaultDetector::new(&fault_config);

    // Group readings by timestamp for replay
    let mut readings_by_ts: std::collections::BTreeMap<chrono::DateTime<chrono::Utc>, Vec<&OntReading>> =
        std::collections::BTreeMap::new();
    for r in &readings {
        readings_by_ts.entry(r.timestamp).or_default().push(r);
    }

    // Replay each time window through fault detector
    let mut all_fault_events = Vec::new();
    for (_ts, window_readings) in &readings_by_ts {
        let window_onts: Vec<OntData> = window_readings
            .iter()
            .map(|r| reading_to_ont_data(r))
            .collect();
        let events = fault_detector.check(&window_onts);
        all_fault_events.extend(events);
    }
    let fault_events = all_fault_events;

    // 4. Run diagnostics
    let diag = diagnostics::analyze_olt(&olt_data);

    // 5. Calculate summary statistics
    let online_count = ont_snapshot
        .iter()
        .filter(|o| matches!(o.status, OntStatus::Online | OntStatus::LowSignal))
        .count();
    let offline_count = ont_snapshot
        .iter()
        .filter(|o| matches!(o.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut))
        .count();
    // Unknown ≠ Offline: excluded from both counts above and reported
    // separately, so total_onts = online + offline + unknown.
    let unknown_count = ont_snapshot
        .iter()
        .filter(|o| matches!(o.status, OntStatus::Unknown))
        .count();
    let total_onts = ont_snapshot.len();

    let rx_values: Vec<f64> = ont_snapshot.iter().filter_map(|o| o.rx_power_dbm).collect();
    let avg_rx = if !rx_values.is_empty() {
        rx_values.iter().sum::<f64>() / rx_values.len() as f64
    } else {
        0.0
    };
    let worst_rx = rx_values.iter().copied().fold(f64::INFINITY, f64::min);
    let worst_rx = if worst_rx.is_infinite() { 0.0 } else { worst_rx };

    // Health score: 100 minus penalties
    let health_score = compute_health_score(
        &fault_events,
        &ghosts,
        &churn_risks,
        &capacity,
        offline_count,
        total_onts,
    );

    // 6. Serialize everything into AuditResult
    Ok(AuditResult {
        summary: AuditSummary {
            total_onts,
            total_readings,
            analysis_period_days,
            health_score,
            online: online_count,
            offline: offline_count,
            unknown: unknown_count,
            avg_rx_dbm: avg_rx,
            worst_rx_dbm: worst_rx,
        },
        import_report: None,
        faults: serde_json::to_value(&fault_events)?,
        ghosts: serde_json::to_value(&ghosts)?,
        capacity: serde_json::to_value(&capacity)?,
        flapping: serde_json::to_value(&flapping)?,
        weather_correlation: serde_json::to_value(&weather)?,
        reflectance: serde_json::to_value(&reflectance_events)?,
        optical_budget: serde_json::to_value(&optical_budget)?,
        sfp_health: serde_json::to_value(&sfp_health)?,
        churn_risk: serde_json::to_value(&churn_risks)?,
        tickets: serde_json::to_value(&tickets)?,
        diagnostics: serde_json::to_value(&diag)?,
        impact: serde_json::to_value(&impact)?,
        onts: serde_json::to_value(&ont_snapshot)?,
    })
}

/// Convert a single OntReading to OntData for fault detection.
fn reading_to_ont_data(r: &OntReading) -> OntData {
    let status = match r.status {
        OntReadingStatus::Online => {
            if let Some(rx) = r.rx_power_dbm {
                if rx < -27.0 { OntStatus::LowSignal } else { OntStatus::Online }
            } else {
                OntStatus::Online
            }
        }
        OntReadingStatus::Offline => {
            match r.last_down_cause.as_deref() {
                Some(c) if c.contains("power") || c.contains("dying_gasp") => OntStatus::PowerFail,
                Some(c) if c.contains("los") || c.contains("fiber") => OntStatus::FiberCut,
                _ => OntStatus::Offline,
            }
        }
        // Unknown ≠ Offline: keep it out of the outage math.
        OntReadingStatus::Unknown => OntStatus::Unknown,
    };

    OntData {
        serial_number: r.serial_number.clone(),
        pon_port: r.pon_port.clone(),
        ont_index: 0,
        status,
        last_down_cause: r.last_down_cause.clone(),
        uptime_seconds: None,
        rx_power_dbm: r.rx_power_dbm,
        tx_power_dbm: r.tx_power_dbm,
        distance_meters: r.distance_meters,
        vendor_id: None,
        equipment_id: None,
        firmware_version: None,
        in_octets: r.in_octets,
        out_octets: r.out_octets,
        fec_corrected: r.fec_corrected,
        fec_uncorrected: r.fec_uncorrected,
        bip_errors: r.bip_errors,
        eth_speed_mbps: r.eth_speed_mbps,
        extended: reading_extended(r),
    }
}

/// Build OntData transceiver DDM detail from a reading, when present.
///
/// OntReading.rx_power_dbm is the ONT-side downstream receive level (see the
/// OntReading docs), so it is carried as `ont_rx_power_dbm` here to give DDM
/// consumers the full transceiver picture in one place. When the reading has
/// no DDM detail, `extended` stays None (no empty objects in audit JSON).
fn reading_extended(r: &OntReading) -> Option<ExtendedOntMetrics> {
    if r.temperature_c.is_none() && r.voltage_v.is_none() && r.bias_current_ma.is_none() {
        return None;
    }
    Some(ExtendedOntMetrics {
        ont_rx_power_dbm: r.rx_power_dbm,
        ont_temperature_c: r.temperature_c,
        ont_voltage_v: r.voltage_v,
        ont_bias_current_ma: r.bias_current_ma,
    })
}

/// Build latest snapshot: for each ONT serial, pick the most recent reading
/// and convert to OntData. Also returns a map of port -> set of serials for
/// PON port construction.
fn build_latest_snapshot(
    readings: &[OntReading],
) -> (Vec<OntData>, HashMap<String, Vec<String>>) {
    let mut latest: HashMap<String, &OntReading> = HashMap::new();
    for r in readings {
        let entry = latest
            .entry(r.serial_number.clone())
            .or_insert(r);
        if r.timestamp > entry.timestamp {
            *entry = r;
        }
    }

    let mut pon_port_map: HashMap<String, Vec<String>> = HashMap::new();
    let mut ont_index_counter: HashMap<String, u32> = HashMap::new();

    let mut onts: Vec<OntData> = latest
        .into_iter()
        .map(|(serial, r)| {
            pon_port_map
                .entry(r.pon_port.clone())
                .or_default()
                .push(serial.clone());

            let idx = ont_index_counter
                .entry(r.pon_port.clone())
                .or_insert(0);
            let current_idx = *idx;
            *idx += 1;

            let status = match r.status {
                OntReadingStatus::Online => {
                    if let Some(rx) = r.rx_power_dbm {
                        if rx < -27.0 {
                            OntStatus::LowSignal
                        } else {
                            OntStatus::Online
                        }
                    } else {
                        OntStatus::Online
                    }
                }
                OntReadingStatus::Offline => {
                    match r.last_down_cause.as_deref() {
                        Some(c) if c.contains("power") || c.contains("dying_gasp") => {
                            OntStatus::PowerFail
                        }
                        Some(c) if c.contains("los") || c.contains("fiber") => {
                            OntStatus::FiberCut
                        }
                        _ => OntStatus::Offline,
                    }
                }
                // Unknown ≠ Offline: keep it out of the outage math.
                OntReadingStatus::Unknown => OntStatus::Unknown,
            };

            OntData {
                serial_number: serial,
                pon_port: r.pon_port.clone(),
                ont_index: current_idx,
                status,
                last_down_cause: r.last_down_cause.clone(),
                uptime_seconds: None,
                rx_power_dbm: r.rx_power_dbm,
                tx_power_dbm: r.tx_power_dbm,
                distance_meters: r.distance_meters,
                vendor_id: None,
                equipment_id: None,
                firmware_version: None,
                in_octets: r.in_octets,
                out_octets: r.out_octets,
                fec_corrected: r.fec_corrected,
                fec_uncorrected: r.fec_uncorrected,
                bip_errors: r.bip_errors,
                eth_speed_mbps: r.eth_speed_mbps,
                extended: reading_extended(r),
            }
        })
        .collect();

    onts.sort_by(|a, b| {
        a.pon_port.cmp(&b.pon_port).then(a.ont_index.cmp(&b.ont_index))
    });

    (onts, pon_port_map)
}

/// Build PON port data from the ONT snapshot.
fn build_pon_ports(
    onts: &[OntData],
    pon_port_map: &HashMap<String, Vec<String>>,
) -> Vec<PonPortData> {
    let mut ports: Vec<PonPortData> = pon_port_map
        .iter()
        .map(|(port_id, serials)| {
            let registered = serials.len() as u32;
            let online = onts
                .iter()
                .filter(|o| {
                    o.pon_port == *port_id
                        && matches!(o.status, OntStatus::Online | OntStatus::LowSignal)
                })
                .count() as u32;
            let offline = registered.saturating_sub(online);
            let utilization = if registered > 0 {
                (online as f32 / 32.0_f32.max(registered as f32)) * 100.0
            } else {
                0.0
            };

            PonPortData {
                port_id: port_id.clone(),
                oper_status: "up".to_string(),
                onts_registered: registered,
                onts_online: online,
                onts_offline: offline,
                bw_down_bps: 0,
                bw_up_bps: 0,
                utilization_percent: utilization,
            }
        })
        .collect();

    ports.sort_by(|a, b| a.port_id.cmp(&b.port_id));
    ports
}

/// Compute health score: 100 minus penalties from various detection findings.
fn compute_health_score(
    fault_events: &[crate::fault::FaultEvent],
    ghosts: &[crate::detection::ghost::GhostCustomer],
    churn_risks: &[crate::detection::churn::ChurnRisk],
    capacity: &[crate::detection::capacity::SplitterCapacity],
    offline_count: usize,
    total_onts: usize,
) -> u8 {
    let mut score: i32 = 100;

    // Fault penalty: up to 30 points
    let fault_penalty = (fault_events.len() as i32 * 10).min(30);
    score -= fault_penalty;

    // Ghost penalty: up to 10 points
    let ghost_penalty = (ghosts.len() as i32 * 2).min(10);
    score -= ghost_penalty;

    // Degrading/churn penalty: up to 15 points
    let degrading_penalty = (churn_risks.len() as i32 * 3).min(15);
    score -= degrading_penalty;

    // Capacity penalty: up to 15 points (only Warning/Critical)
    let capacity_issues = capacity
        .iter()
        .filter(|c| {
            matches!(
                c.alert_level,
                crate::detection::capacity::CapacityAlert::Warning
                    | crate::detection::capacity::CapacityAlert::Critical
            )
        })
        .count();
    let capacity_penalty = (capacity_issues as i32 * 5).min(15);
    score -= capacity_penalty;

    // Offline penalty: up to 30 points based on offline ratio
    let offline_penalty = if total_onts > 0 {
        let ratio = offline_count as f64 / total_onts as f64;
        (ratio * 100.0).min(30.0) as i32
    } else {
        0
    };
    score -= offline_penalty;

    score.clamp(0, 100) as u8
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: chrono::DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: Some(2.5),
            status,
            distance_meters: Some(1000),
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_audit_healthy_network() {
        let now = Utc::now();
        let mut readings = Vec::new();

        // 10 ONTs, all online with good signal over 7 days
        // Vary Rx power slightly to avoid ghost detection (flat variance triggers ghost)
        for day in 0..7 {
            for i in 0..10 {
                let serial = format!("ONT{:03}", i);
                let ts = now - Duration::days(7 - day);
                let rx = -20.0 + (day as f64 * 0.05) + (i as f64 * 0.02);
                readings.push(make_reading(&serial, "0/1/0", ts, OntReadingStatus::Online, Some(rx)));
            }
        }

        let result = run_audit(readings).unwrap();
        assert_eq!(result.summary.total_onts, 10);
        assert_eq!(result.summary.online, 10);
        assert_eq!(result.summary.offline, 0);
        assert!(result.summary.health_score >= 90, "healthy network should score >= 90, got {}", result.summary.health_score);
    }

    #[test]
    fn test_audit_empty_readings_errors() {
        let result = run_audit(Vec::new());
        assert!(result.is_err());
    }

    #[test]
    fn test_audit_with_offline_onts() {
        let now = Utc::now();
        let mut readings = Vec::new();

        // 8 ONTs online
        for i in 0..8 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, "0/1/0", now, OntReadingStatus::Online, Some(-20.0)));
        }
        // 2 ONTs offline
        for i in 8..10 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, "0/1/0", now, OntReadingStatus::Offline, None));
        }

        let result = run_audit(readings).unwrap();
        assert_eq!(result.summary.total_onts, 10);
        assert_eq!(result.summary.online, 8);
        assert_eq!(result.summary.offline, 2);
        assert!(result.summary.health_score < 100);
    }

    #[test]
    fn test_audit_unknown_status_not_evidence_of_outage() {
        let now = Utc::now();
        let mut readings = Vec::new();

        // 7 ONTs online, 3 with unknown status — NOT an outage.
        for i in 0..7 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, "0/1/0", now, OntReadingStatus::Online, Some(-20.0 + i as f64 * 0.02)));
        }
        for i in 7..10 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(&serial, "0/1/0", now, OntReadingStatus::Unknown, None));
        }

        let result = run_audit(readings).unwrap();
        assert_eq!(result.summary.total_onts, 10);
        assert_eq!(result.summary.online, 7);
        assert_eq!(result.summary.offline, 0, "Unknown must not count as offline");
        assert_eq!(result.summary.unknown, 3);
        assert_eq!(
            result.summary.total_onts,
            result.summary.online + result.summary.offline + result.summary.unknown,
            "totals must reconcile"
        );
        // No offline penalty and no fault events from unknowns: score stays high.
        assert!(
            result.summary.health_score >= 90,
            "unknown-status ONTs must not depress health score as an outage, got {}",
            result.summary.health_score
        );
        // Unknown serials are not fed into impact scoring (offline evidence only).
        assert!(result.impact.is_null(), "no offline ONTs → no impact section");
    }

    #[test]
    fn test_run_csv_audit_surfaces_import_report() {
        use std::io::Write;
        // Snapshot export (no timestamp column) with one unrecognized status
        // and one row missing the serial.
        let mut f = tempfile::NamedTempFile::new().unwrap();
        writeln!(f, "ont_serial,pon_port,rx_power_dbm,status,distance").unwrap();
        writeln!(f, "ADTN-001,CTP-0/1,-21.0,online,1000").unwrap();
        writeln!(f, "ADTN-002,CTP-0/1,-22.0,frobnicated,1100").unwrap();
        writeln!(f, ",CTP-0/1,-23.0,online,1200").unwrap();
        writeln!(f, "ADTN-004,CTP-0/1,-24.0,offline,1300").unwrap();

        let upload_time = Utc::now();
        let result = run_csv_audit(f.path(), None, Some(upload_time)).unwrap();

        let report = result.import_report.as_ref().expect("import_report must be attached");
        assert_eq!(report.rows_ok, 3);
        assert_eq!(report.rows_skipped, 1);
        assert!(report.snapshot_mode, "no timestamp column → snapshot mode");
        assert_eq!(report.unknown_statuses, 1);
        assert!(report.unknown_status_values.iter().any(|v| v.contains("frobnicated")));
        assert_eq!(report.delimiter, ",");
        assert!(report.skip_samples.len() <= 5);
        for s in &report.skip_samples {
            assert!(!s.contains('/'), "skip sample leaks a path: {s}");
        }

        // Snapshot rows are stamped with the provided upload time.
        assert_eq!(result.summary.analysis_period_days, 1);
        // Unknown status row surfaces in the summary, not as offline.
        assert_eq!(result.summary.online, 1);
        assert_eq!(result.summary.offline, 1);
        assert_eq!(result.summary.unknown, 1);
    }

    #[test]
    fn test_sanitize_skip_sample_strips_paths() {
        assert_eq!(
            sanitize_skip_sample("row 3: could not read /tmp/.tmpXYZ/upload.csv properly"),
            "row 3: could not read [path] properly"
        );
        assert_eq!(
            sanitize_skip_sample("row 5: invalid timestamp \"whenever\""),
            "row 5: invalid timestamp \"whenever\""
        );
    }

    #[test]
    fn test_snapshot_carries_fec_ddm_and_octets_through() {
        // The frontier detection modules read these from the OntData
        // snapshot — a reading that has them must not lose them in the
        // OntReading -> OntData conversion.
        let now = Utc::now();
        let mut reading = make_reading("ONT001", "0/1/0", now, OntReadingStatus::Online, Some(-21.0));
        reading.fec_corrected = Some(18_234);
        reading.fec_uncorrected = Some(2);
        reading.bip_errors = Some(7);
        reading.temperature_c = Some(45.5);
        reading.voltage_v = Some(3.31);
        reading.bias_current_ma = Some(12.4);
        reading.in_octets = Some(182_347_776);
        reading.out_octets = Some(23_456_789);

        for ont in [
            &build_latest_snapshot(std::slice::from_ref(&reading)).0[0],
            &reading_to_ont_data(&reading),
        ] {
            assert_eq!(ont.fec_corrected, Some(18_234));
            assert_eq!(ont.fec_uncorrected, Some(2));
            assert_eq!(ont.bip_errors, Some(7));
            assert_eq!(ont.in_octets, Some(182_347_776));
            assert_eq!(ont.out_octets, Some(23_456_789));
            let ext = ont.extended.as_ref().expect("DDM detail must build extended");
            assert_eq!(ext.ont_temperature_c, Some(45.5));
            assert_eq!(ext.ont_voltage_v, Some(3.31));
            assert_eq!(ext.ont_bias_current_ma, Some(12.4));
            // OntReading.rx_power_dbm is the ONT-side reading — mirrored
            // into the transceiver detail block.
            assert_eq!(ext.ont_rx_power_dbm, Some(-21.0));
        }

        // Readings without DDM detail must NOT emit an empty extended block.
        let bare = make_reading("ONT002", "0/1/0", now, OntReadingStatus::Online, Some(-20.0));
        assert!(reading_to_ont_data(&bare).extended.is_none());
    }

    #[test]
    fn test_build_latest_snapshot_picks_most_recent() {
        let now = Utc::now();
        let readings = vec![
            make_reading("ONT001", "0/1/0", now - Duration::hours(2), OntReadingStatus::Online, Some(-20.0)),
            make_reading("ONT001", "0/1/0", now - Duration::hours(1), OntReadingStatus::Offline, None),
            make_reading("ONT001", "0/1/0", now, OntReadingStatus::Online, Some(-22.0)),
        ];

        let (snapshot, _) = build_latest_snapshot(&readings);
        assert_eq!(snapshot.len(), 1);
        assert_eq!(snapshot[0].status, OntStatus::Online);
        assert_eq!(snapshot[0].rx_power_dbm, Some(-22.0));
    }

    #[test]
    fn test_health_score_perfect() {
        let score = compute_health_score(&[], &[], &[], &[], 0, 100);
        assert_eq!(score, 100);
    }

    #[test]
    fn test_health_score_with_faults() {
        let fault = crate::fault::FaultEvent {
            timestamp: Utc::now(),
            pon_port: "0/1/0".into(),
            olt_id: "test".into(),
            severity: "critical".into(),
            fault_type: crate::fault::FaultType::FibreCut,
            affected_onts: Vec::new(),
            detection_latency_seconds: 0,
        };
        let score = compute_health_score(&[fault], &[], &[], &[], 20, 100);
        // fault penalty = 10, offline penalty = 20
        assert_eq!(score, 70);
    }
}
