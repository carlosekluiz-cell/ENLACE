// SPDX-License-Identifier: Apache-2.0
// CSV Import Module
//
// Parses vendor-specific CSV telemetry exports and converts each row
// into an OntReading for use by the detection engine. Imports are
// best-effort: bad rows are skipped and counted (never aborting the
// whole file) and per-file quality counters are reported.

pub mod adtran;

use crate::detection::OntReading;
use anyhow::Result;
use chrono::{DateTime, Utc};
use std::path::Path;

/// Result of a CSV import: parsed readings plus per-file quality counters.
#[derive(Debug)]
pub struct ImportReport {
    pub readings: Vec<OntReading>,
    /// Rows successfully converted into readings.
    pub rows_ok: usize,
    /// Rows dropped (structural errors, bad timestamps, missing serials,
    /// unrecognized statuses).
    pub rows_skipped: usize,
    /// Up to 10 sample messages describing skipped rows.
    pub skip_samples: Vec<String>,
    /// Non-empty cells whose value could not be parsed (kept as None).
    pub cells_unparsed: usize,
    /// Rows whose status value was not recognized. These are never imported
    /// as Offline; they are skipped and the values reported below.
    pub unknown_statuses: usize,
    /// Distinct unrecognized status values seen (normalized, up to 10).
    pub unknown_status_values: Vec<String>,
    /// True when the file had no timestamp column (snapshot export) and row
    /// timestamps were defaulted.
    pub snapshot_mode: bool,
    /// Delimiter sniffed from the header line (b',', b';' or b'\t').
    pub delimiter: u8,
}

/// Parse a CSV file into OntReadings, optionally specifying the vendor.
/// If no vendor is given, auto-detect from the CSV headers.
///
/// Backward-compatible wrapper around [`parse_csv_with_report`]; import
/// quality counters are logged rather than returned.
pub fn parse_csv(path: &Path, vendor: Option<&str>) -> Result<Vec<OntReading>> {
    let report = parse_csv_with_report(path, vendor, None)?;
    if report.rows_skipped > 0 || report.cells_unparsed > 0 {
        tracing::warn!(
            path = %path.display(),
            rows_ok = report.rows_ok,
            rows_skipped = report.rows_skipped,
            cells_unparsed = report.cells_unparsed,
            unknown_statuses = report.unknown_statuses,
            unknown_status_values = ?report.unknown_status_values,
            skip_samples = ?report.skip_samples,
            snapshot_mode = report.snapshot_mode,
            delimiter = %(report.delimiter as char),
            "CSV import skipped rows or cells"
        );
    }
    Ok(report.readings)
}

/// Parse a CSV file into an [`ImportReport`] with per-file counters.
///
/// `default_timestamp` is applied to every row of snapshot exports that
/// carry no timestamp column (defaults to the import time).
pub fn parse_csv_with_report(
    path: &Path,
    vendor: Option<&str>,
    default_timestamp: Option<DateTime<Utc>>,
) -> Result<ImportReport> {
    let vendor = match vendor {
        Some(v) => v,
        None => {
            let header_line = adtran::read_header_line(path)?;
            detect_vendor(&header_line)
        }
    };
    match vendor {
        "adtran" => adtran::parse_with_report(path, default_timestamp),
        other => anyhow::bail!("Unsupported vendor CSV format: {}", other),
    }
}

/// Detect the vendor from the raw header line: sniff the delimiter, then
/// score the headers against the normalized alias tables so realistic
/// Mosaic / Mission Control exports ("Serial Number", "RX Power (dBm)"...)
/// are recognized. Legacy substring checks are kept as a fallback.
fn detect_vendor(header_line: &str) -> &'static str {
    let delimiter = adtran::sniff_delimiter(header_line);
    let cells: Vec<&str> = header_line.split(delimiter as char).collect();
    let score = adtran::header_score(&cells);
    let lower = header_line.to_lowercase();
    if (score >= 3 && adtran::has_serial_column(&cells))
        || lower.contains("ctp")
        || lower.contains("adtn")
        || lower.contains("pon_port")
    {
        "adtran"
    } else {
        "unknown"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::path::PathBuf;
    use tempfile::NamedTempFile;

    fn fixture(name: &str) -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("src/csv_import/testdata")
            .join(name)
    }

    #[test]
    fn test_detect_adtran_from_headers() {
        let f = {
            let mut f = NamedTempFile::new().unwrap();
            writeln!(f, "timestamp,ont_serial,pon_port,rx_power_dbm,status,distance").unwrap();
            writeln!(f, "2026-03-01 08:00:00,ADTN-1234,CTP-0/3,-22.0,online,1000").unwrap();
            f
        };
        let readings = parse_csv(f.path(), None).unwrap();
        assert_eq!(readings.len(), 1);
    }

    #[test]
    fn test_explicit_vendor_override() {
        let f = {
            let mut f = NamedTempFile::new().unwrap();
            writeln!(f, "timestamp,ont_serial,pon_port,rx_power_dbm,status,distance").unwrap();
            writeln!(f, "2026-03-01 08:00:00,ADTN-1234,CTP-0/3,-22.0,online,1000").unwrap();
            f
        };
        let readings = parse_csv(f.path(), Some("adtran")).unwrap();
        assert_eq!(readings.len(), 1);
    }

    #[test]
    fn test_unknown_vendor_errors() {
        let f = {
            let mut f = NamedTempFile::new().unwrap();
            writeln!(f, "col_a,col_b,col_c").unwrap();
            writeln!(f, "1,2,3").unwrap();
            f
        };
        let result = parse_csv(f.path(), None);
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Unsupported"));
    }

    #[test]
    fn test_detect_mission_control_export_as_adtran() {
        // Realistic Mosaic-style headers: no "ctp"/"adtn"/"pon_port"
        // substrings in the header line — detection must come from the
        // normalized alias scoring.
        let readings = parse_csv(&fixture("mission_control.csv"), None).unwrap();
        assert_eq!(readings.len(), 4);
    }

    #[test]
    fn test_detect_semicolon_export_as_adtran() {
        let report =
            parse_csv_with_report(&fixture("uk_excel_semicolon.csv"), None, None).unwrap();
        assert_eq!(report.delimiter, b';');
        assert_eq!(report.rows_ok, 3);
    }

    #[test]
    fn test_snapshot_export_via_parse_csv() {
        // Snapshot exports without a timestamp column must be accepted.
        let readings = parse_csv(&fixture("snapshot_no_timestamp.csv"), None).unwrap();
        assert_eq!(readings.len(), 3);
    }
}
