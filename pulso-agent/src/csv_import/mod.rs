// SPDX-License-Identifier: Apache-2.0
// CSV Import Module
//
// Parses vendor-specific CSV telemetry exports and converts each row
// into an OntReading for use by the detection engine.

pub mod adtran;

use crate::detection::OntReading;
use anyhow::Result;
use std::path::Path;

/// Parse a CSV file into OntReadings, optionally specifying the vendor.
/// If no vendor is given, auto-detect from the CSV headers.
pub fn parse_csv(path: &Path, vendor: Option<&str>) -> Result<Vec<OntReading>> {
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .from_path(path)?;
    let headers = rdr.headers()?.clone();
    let detected = detect_vendor(&headers);
    let vendor = vendor.unwrap_or(detected);
    match vendor {
        "adtran" => adtran::parse(path),
        other => anyhow::bail!("Unsupported vendor CSV format: {}", other),
    }
}

fn detect_vendor(headers: &csv::StringRecord) -> &'static str {
    let h = headers
        .iter()
        .map(|s| s.to_lowercase())
        .collect::<Vec<_>>()
        .join(",");
    if h.contains("ctp") || h.contains("adtn") || h.contains("pon_port") {
        "adtran"
    } else {
        "unknown"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

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
}
