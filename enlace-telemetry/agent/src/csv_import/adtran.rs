// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 CSV Parser
//
// Parses Adtran telemetry CSV exports into OntReading structs.
// Handles flexible column names, multiple timestamp formats,
// and missing/empty values gracefully.

use crate::detection::{OntReading, OntReadingStatus};
use anyhow::{Context, Result};
use chrono::{DateTime, NaiveDateTime, Utc};
use std::path::Path;

/// Column indices resolved from CSV headers.
struct ColumnMap {
    timestamp: usize,
    serial: usize,
    pon_port: usize,
    rx_power: Option<usize>,
    tx_power: Option<usize>,
    status: Option<usize>,
    distance: Option<usize>,
    eth_speed: Option<usize>,
    last_down_cause: Option<usize>,
}

/// Parse an Adtran SDX 6320 CSV file into OntReadings.
pub fn parse(path: &Path) -> Result<Vec<OntReading>> {
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .trim(csv::Trim::All)
        .from_path(path)
        .with_context(|| format!("Failed to open CSV: {}", path.display()))?;

    let headers = rdr.headers()?.clone();
    let col_map = resolve_columns(&headers)?;

    let mut readings = Vec::new();
    for (row_idx, result) in rdr.records().enumerate() {
        let record = result.with_context(|| format!("Failed to read CSV row {}", row_idx + 2))?;

        let timestamp = parse_timestamp(record.get(col_map.timestamp).unwrap_or(""))
            .with_context(|| format!("Invalid timestamp at row {}", row_idx + 2))?;

        let serial_number = record
            .get(col_map.serial)
            .unwrap_or("")
            .trim()
            .to_string();

        let pon_port = record
            .get(col_map.pon_port)
            .unwrap_or("")
            .trim()
            .to_string();

        let rx_power_dbm = col_map
            .rx_power
            .and_then(|i| parse_optional_f64(record.get(i)));

        let tx_power_dbm = col_map
            .tx_power
            .and_then(|i| parse_optional_f64(record.get(i)));

        let raw_status = col_map
            .status
            .and_then(|i| record.get(i))
            .unwrap_or("")
            .trim()
            .to_lowercase();

        let status = parse_status(&raw_status);

        // Capture dying_gasp / power_fail from status column as last_down_cause
        let status_as_cause = match raw_status.as_str() {
            "dying_gasp" | "dyinggasp" | "dying-gasp" => Some("dying_gasp".to_string()),
            "power_fail" | "powerfail" | "power-fail" => Some("power_fail".to_string()),
            "los" | "fiber_cut" | "fibercut" => Some("los".to_string()),
            _ => None,
        };

        let distance_meters = col_map
            .distance
            .and_then(|i| parse_optional_u32(record.get(i)));

        let eth_speed_mbps = col_map
            .eth_speed
            .and_then(|i| parse_optional_u32(record.get(i)));

        let explicit_cause = col_map
            .last_down_cause
            .and_then(|i| record.get(i))
            .map(|s| s.trim())
            .filter(|s| !s.is_empty())
            .map(String::from);

        // Use explicit last_down_cause column if present, otherwise infer from status
        let last_down_cause = explicit_cause.or(status_as_cause);

        readings.push(OntReading {
            timestamp,
            serial_number,
            pon_port,
            rx_power_dbm,
            tx_power_dbm,
            status,
            distance_meters,
            eth_speed_mbps,
            last_down_cause,
        });
    }

    Ok(readings)
}

/// Match CSV header names to column indices. Supports common Adtran naming variants.
fn resolve_columns(headers: &csv::StringRecord) -> Result<ColumnMap> {
    let lower: Vec<String> = headers.iter().map(|h| h.trim().to_lowercase()).collect();

    let find = |candidates: &[&str]| -> Option<usize> {
        lower.iter().position(|h| candidates.iter().any(|c| h == c))
    };

    let timestamp = find(&["timestamp", "time", "date_time", "datetime", "reading_time"])
        .context("CSV missing required timestamp column")?;

    let serial = find(&[
        "ont_serial",
        "serial",
        "serial_number",
        "ont_id",
        "sn",
        "device_serial",
    ])
    .context("CSV missing required serial number column")?;

    let pon_port = find(&[
        "pon_port",
        "port",
        "pon",
        "ctp",
        "interface",
        "slot_port",
    ])
    .context("CSV missing required PON port column")?;

    Ok(ColumnMap {
        timestamp,
        serial,
        pon_port,
        rx_power: find(&["rx_power_dbm", "rx_power", "rx_dbm", "optical_rx", "ont_rx"]),
        tx_power: find(&["tx_power_dbm", "tx_power", "tx_dbm", "optical_tx", "ont_tx"]),
        status: find(&["status", "ont_status", "state", "oper_status"]),
        distance: find(&["distance", "distance_meters", "distance_m", "range"]),
        eth_speed: find(&["eth_speed", "eth_speed_mbps", "speed", "link_speed"]),
        last_down_cause: find(&["last_down_cause", "down_cause", "last_cause", "deactivation_reason"]),
    })
}

/// Parse a timestamp string in multiple common formats, returning UTC DateTime.
fn parse_timestamp(s: &str) -> Result<DateTime<Utc>> {
    let s = s.trim();

    // Try ISO 8601 with timezone
    if let Ok(dt) = DateTime::parse_from_rfc3339(s) {
        return Ok(dt.with_timezone(&Utc));
    }

    // Try common formats (all interpreted as UTC)
    let formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ];

    for fmt in &formats {
        if let Ok(ndt) = NaiveDateTime::parse_from_str(s, fmt) {
            return Ok(ndt.and_utc());
        }
    }

    // Try date-only format
    if let Ok(nd) = chrono::NaiveDate::parse_from_str(s, "%Y-%m-%d") {
        return Ok(nd
            .and_hms_opt(0, 0, 0)
            .expect("midnight is always valid")
            .and_utc());
    }

    anyhow::bail!("Unrecognized timestamp format: '{}'", s)
}

fn parse_optional_f64(val: Option<&str>) -> Option<f64> {
    val.map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .and_then(|s| s.parse::<f64>().ok())
}

fn parse_optional_u32(val: Option<&str>) -> Option<u32> {
    val.map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .and_then(|s| s.parse::<u32>().ok())
}

fn parse_status(s: &str) -> OntReadingStatus {
    match s.trim().to_lowercase().as_str() {
        "online" | "up" | "active" | "1" => OntReadingStatus::Online,
        _ => OntReadingStatus::Offline,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    fn sample_csv() -> NamedTempFile {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(
            f,
            "timestamp,ont_serial,pon_port,rx_power_dbm,status,distance"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:00:00,ADTN-1534A8C2,CTP-0/3,-22.4,online,1200"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:00:00,ADTN-2847B1D5,CTP-0/1,-28.4,offline,800"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:01:00,ADTN-1534A8C2,CTP-0/3,-22.5,online,1200"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:01:00,ADTN-2847B1D5,CTP-0/1,,offline,800"
        )
        .unwrap();
        f
    }

    #[test]
    fn test_parse_adtran_csv() {
        let f = sample_csv();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings.len(), 4);
        assert_eq!(readings[0].serial_number, "ADTN-1534A8C2");
        assert_eq!(readings[0].rx_power_dbm, Some(-22.4));
        assert_eq!(readings[0].pon_port, "CTP-0/3");
        assert_eq!(readings[0].distance_meters, Some(1200));
        assert_eq!(readings[0].status, OntReadingStatus::Online);
        assert_eq!(readings[1].status, OntReadingStatus::Offline);
        assert_eq!(readings[1].rx_power_dbm, Some(-28.4));
        assert_eq!(readings[3].rx_power_dbm, None); // empty field
        assert_eq!(readings[3].distance_meters, Some(800));
    }

    #[test]
    fn test_optional_fields_none_when_missing() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial,pon_port,status").unwrap();
        writeln!(f, "2026-03-01 08:00:00,SN-001,0/1/0,online").unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings.len(), 1);
        assert_eq!(readings[0].rx_power_dbm, None);
        assert_eq!(readings[0].tx_power_dbm, None);
        assert_eq!(readings[0].distance_meters, None);
    }

    #[test]
    fn test_alternative_column_names() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "datetime,serial_number,ctp,optical_rx,optical_tx,oper_status,range").unwrap();
        writeln!(f, "2026-03-01T10:00:00,ADTN-AABB,CTP-0/2,-21.0,-2.5,active,500").unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings.len(), 1);
        assert_eq!(readings[0].serial_number, "ADTN-AABB");
        assert_eq!(readings[0].rx_power_dbm, Some(-21.0));
        assert_eq!(readings[0].tx_power_dbm, Some(-2.5));
        assert_eq!(readings[0].status, OntReadingStatus::Online);
        assert_eq!(readings[0].distance_meters, Some(500));
    }

    #[test]
    fn test_iso8601_timestamp() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial,pon_port,status").unwrap();
        writeln!(f, "2026-03-01T08:00:00+00:00,SN-001,0/1/0,online").unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings.len(), 1);
    }

    #[test]
    fn test_missing_required_column_errors() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial").unwrap(); // missing pon_port
        writeln!(f, "2026-03-01 08:00:00,SN-001").unwrap();
        let result = parse(f.path());
        assert!(result.is_err());
    }

    #[test]
    fn test_empty_csv_returns_empty_vec() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial,pon_port,status").unwrap();
        // headers only, no data rows
        let readings = parse(f.path()).unwrap();
        assert!(readings.is_empty());
    }

    #[test]
    fn test_with_tx_power_and_eth_speed() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(
            f,
            "timestamp,ont_serial,pon_port,rx_power_dbm,tx_power_dbm,status,distance,eth_speed_mbps,last_down_cause"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:00:00,ADTN-001,CTP-0/1,-22.0,-2.1,online,1000,1000,power-fail"
        )
        .unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings[0].tx_power_dbm, Some(-2.1));
        assert_eq!(readings[0].eth_speed_mbps, Some(1000));
        assert_eq!(
            readings[0].last_down_cause.as_deref(),
            Some("power-fail")
        );
    }
}
