// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 CSV Parser
//
// Parses Adtran telemetry CSV exports (Mosaic / Mission Control style as
// well as synthetic snake_case exports) into OntReading structs. Handles:
//   - flexible column names via normalized-header alias tables
//   - comma / semicolon / tab delimiters (sniffed from the header line)
//   - multiple timestamp formats (ISO 8601, day-first UK, month-first US)
//   - snapshot exports with no timestamp column (rows get a default)
//   - unit suffixes ("-22.4 dBm"), Unicode minus, decimal commas
// Bad rows are skipped and counted rather than aborting the whole file,
// and unrecognized status values are NEVER defaulted to Offline.

use super::ImportReport;
use crate::detection::{OntReading, OntReadingStatus};
use crate::vendors::snmp_helper::{plausible_bias_ma, plausible_temp_c, plausible_voltage_v};
use anyhow::{Context, Result};
use chrono::{DateTime, NaiveDateTime, Utc};
use std::io::{BufRead, BufReader};
use std::path::Path;

/// Maximum number of sample messages / values retained per import.
const MAX_SAMPLES: usize = 10;

// ---------------------------------------------------------------------------
// Header alias tables (matched against normalize_header() output)
// ---------------------------------------------------------------------------

const TIMESTAMP_ALIASES: &[&str] = &[
    "timestamp", "time", "date time", "datetime", "reading time", "date",
    "sample time", "collection time", "poll time", "polled at",
    "last updated", "last update", "last seen", "report time", "record time",
];

const SERIAL_ALIASES: &[&str] = &[
    "ont serial", "onu serial", "serial", "serial number", "serial no",
    "ont serial number", "onu serial number", "sn", "ont sn", "onu sn",
    "device serial", "fsan", "fsan serial",
];

/// Fallback identity columns when no serial column is present.
const ONT_ID_ALIASES: &[&str] = &[
    "ont id", "onu id", "ont", "onu", "ont name", "onu name",
    "device id", "subscriber id",
];

const PON_PORT_ALIASES: &[&str] = &[
    "pon port", "port", "pon", "ctp", "interface", "slot port",
    "pon interface", "olt port", "olt pon port", "channel termination",
    "pon id", "port id", "port name", "interface name",
];

/// Fallback grouping column when no PON port column is present.
const OLT_ALIASES: &[&str] = &["olt", "olt name", "olt id"];

const RX_POWER_ALIASES: &[&str] = &[
    "rx power dbm", "rx power", "rx dbm", "rx", "optical rx",
    "optical rx power", "rx optical power", "ont rx", "onu rx",
    "ont rx power", "onu rx power", "rx level", "rx power level",
    "rx signal level", "received power", "received optical power",
];

const TX_POWER_ALIASES: &[&str] = &[
    "tx power dbm", "tx power", "tx dbm", "tx", "optical tx",
    "optical tx power", "tx optical power", "ont tx", "onu tx",
    "ont tx power", "onu tx power", "tx level", "tx power level",
    "tx signal level", "transmit power", "transmitted power",
];

const STATUS_ALIASES: &[&str] = &[
    "status", "ont status", "onu status", "state", "ont state", "onu state",
    "oper status", "oper state", "operational status", "operational state",
    "run state", "running status", "connection status", "link status",
    "service status",
];

const DISTANCE_ALIASES: &[&str] = &[
    "distance", "distance meters", "distance m", "range", "ranging distance",
    "ont distance", "onu distance", "fiber length", "fibre length",
    "fiber distance", "fibre distance",
];

const ETH_SPEED_ALIASES: &[&str] = &[
    "eth speed", "eth speed mbps", "speed", "link speed", "ethernet speed",
    "negotiated speed", "port speed",
];

const DOWN_CAUSE_ALIASES: &[&str] = &[
    "last down cause", "down cause", "down reason", "last cause",
    "last down reason", "deactivation reason", "last deactivation reason",
    "offline reason", "last offline reason",
];

/// Transceiver DDM: temperature (°C — units in parentheses are stripped by
/// normalize_header, suffixes like "45.2 C" by parse_number).
const TEMPERATURE_ALIASES: &[&str] = &[
    "temperature", "temp", "ont temperature", "onu temperature",
    "transceiver temperature", "temperature c", "temp c",
];

/// Transceiver DDM: supply voltage (V).
const VOLTAGE_ALIASES: &[&str] = &[
    "voltage", "supply voltage", "vcc", "voltage v", "supply voltage v",
    "ont voltage", "onu voltage",
];

/// Transceiver DDM: laser bias current (mA).
const BIAS_ALIASES: &[&str] = &[
    "bias current", "bias", "tx bias", "tx bias current", "laser bias",
    "laser bias current", "bias current ma", "tx bias ma",
];

/// FEC corrected codewords counter.
const FEC_CORRECTED_ALIASES: &[&str] = &[
    "fec corrected", "fec corrected errors", "corrected errors",
    "corrected codewords", "fec corrected codewords", "corrected fec",
];

/// FEC uncorrectable codewords counter.
const FEC_UNCORRECTED_ALIASES: &[&str] = &[
    "fec uncorrected", "fec uncorrected errors", "uncorrected errors",
    "uncorrected codewords", "fec uncorrectable", "fec uncorrectable errors",
    "uncorrectable codewords", "fec uncorrectable codewords",
    "uncorrectable errors",
];

/// BIP-8 error counter.
const BIP_ALIASES: &[&str] = &["bip", "bip errors", "bip8 errors", "bip 8 errors"];

/// Traffic octets received by the ONT (downstream).
const IN_OCTETS_ALIASES: &[&str] = &[
    "rx octets", "in octets", "octets in", "bytes in", "in bytes",
    "rx bytes", "received bytes", "bytes received", "received octets",
    "input octets", "downstream octets", "downstream bytes",
];

/// Traffic octets sent by the ONT (upstream).
const OUT_OCTETS_ALIASES: &[&str] = &[
    "tx octets", "out octets", "octets out", "bytes out", "out bytes",
    "tx bytes", "transmitted bytes", "bytes sent", "sent bytes",
    "transmitted octets", "output octets", "upstream octets",
    "upstream bytes",
];

/// Columns we recognize but do not (yet) map into OntReading — a bare "fec"
/// column is ambiguous (corrected? uncorrected?) and BER ratios need their
/// own representation. They still count toward delimiter sniffing and
/// vendor auto-detection scores.
const RECOGNIZED_EXTRA_ALIASES: &[&str] = &["fec", "pre fec ber", "post fec ber"];

const ALL_ALIAS_GROUPS: &[&[&str]] = &[
    TIMESTAMP_ALIASES,
    SERIAL_ALIASES,
    ONT_ID_ALIASES,
    PON_PORT_ALIASES,
    OLT_ALIASES,
    RX_POWER_ALIASES,
    TX_POWER_ALIASES,
    STATUS_ALIASES,
    DISTANCE_ALIASES,
    ETH_SPEED_ALIASES,
    DOWN_CAUSE_ALIASES,
    TEMPERATURE_ALIASES,
    VOLTAGE_ALIASES,
    BIAS_ALIASES,
    FEC_CORRECTED_ALIASES,
    FEC_UNCORRECTED_ALIASES,
    BIP_ALIASES,
    IN_OCTETS_ALIASES,
    OUT_OCTETS_ALIASES,
    RECOGNIZED_EXTRA_ALIASES,
];

/// Column indices resolved from CSV headers.
struct ColumnMap {
    /// None when the export is a snapshot with no timestamp column.
    timestamp: Option<usize>,
    serial: usize,
    pon_port: usize,
    rx_power: Option<usize>,
    tx_power: Option<usize>,
    status: Option<usize>,
    distance: Option<usize>,
    eth_speed: Option<usize>,
    last_down_cause: Option<usize>,
    temperature: Option<usize>,
    voltage: Option<usize>,
    bias_current: Option<usize>,
    fec_corrected: Option<usize>,
    fec_uncorrected: Option<usize>,
    bip_errors: Option<usize>,
    in_octets: Option<usize>,
    out_octets: Option<usize>,
}

/// Parse an Adtran SDX 6320 CSV file into OntReadings plus import counters.
///
/// `default_timestamp` is used for every row when the file has no timestamp
/// column (snapshot export); it defaults to the import time.
pub fn parse_with_report(
    path: &Path,
    default_timestamp: Option<DateTime<Utc>>,
) -> Result<ImportReport> {
    let header_line = read_header_line(path)?;
    let delimiter = sniff_delimiter(&header_line);

    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .trim(csv::Trim::All)
        .delimiter(delimiter)
        .from_path(path)
        .with_context(|| format!("Failed to open CSV: {}", path.display()))?;

    let headers = rdr.headers()?.clone();
    let col_map = resolve_columns(&headers)?;
    let snapshot_mode = col_map.timestamp.is_none();
    let snapshot_ts = default_timestamp.unwrap_or_else(Utc::now);

    let mut report = ImportReport {
        readings: Vec::new(),
        rows_ok: 0,
        rows_skipped: 0,
        skip_samples: Vec::new(),
        cells_unparsed: 0,
        unknown_statuses: 0,
        unknown_status_values: Vec::new(),
        snapshot_mode,
        delimiter,
    };

    for (row_idx, result) in rdr.records().enumerate() {
        let row_num = row_idx + 2; // 1-based, after the header row
        let record = match result {
            Ok(r) => r,
            Err(e) => {
                skip_row(&mut report, row_num, &format!("unreadable row: {}", e));
                continue;
            }
        };

        let timestamp = match col_map.timestamp {
            None => snapshot_ts,
            Some(i) => {
                let raw = record.get(i).unwrap_or("");
                match parse_timestamp(raw) {
                    Ok(t) => t,
                    Err(_) => {
                        skip_row(
                            &mut report,
                            row_num,
                            &format!("invalid timestamp '{}'", raw.trim()),
                        );
                        continue;
                    }
                }
            }
        };

        let serial_number = clean_cell(record.get(col_map.serial).unwrap_or("")).to_string();
        if serial_number.is_empty() {
            skip_row(&mut report, row_num, "missing serial number");
            continue;
        }

        let pon_port = clean_cell(record.get(col_map.pon_port).unwrap_or("")).to_string();

        let rx_power_dbm = col_map
            .rx_power
            .and_then(|i| parse_f64_cell(record.get(i), &mut report.cells_unparsed));

        let tx_power_dbm = col_map
            .tx_power
            .and_then(|i| parse_f64_cell(record.get(i), &mut report.cells_unparsed));

        let raw_status = col_map.status.and_then(|i| record.get(i)).unwrap_or("");
        let norm_status = normalize_header(raw_status);

        let status = match parse_status(&norm_status) {
            ParsedStatus::Online => OntReadingStatus::Online,
            ParsedStatus::Offline => OntReadingStatus::Offline,
            ParsedStatus::Unknown => {
                if norm_status.is_empty() && rx_power_dbm.is_some() {
                    // No status value but a live optical reading: the ONT is
                    // transmitting, so treat it as Online rather than
                    // dropping the row.
                    OntReadingStatus::Online
                } else {
                    // NEVER default an unrecognized status to Offline — a
                    // vocabulary miss would read as a 100% outage. Emit
                    // Unknown: excluded from outage math downstream and
                    // counted separately here.
                    report.unknown_statuses += 1;
                    if !norm_status.is_empty()
                        && !report.unknown_status_values.contains(&norm_status)
                        && report.unknown_status_values.len() < MAX_SAMPLES
                    {
                        report.unknown_status_values.push(norm_status.clone());
                    }
                    OntReadingStatus::Unknown
                }
            }
        };

        // Capture dying_gasp / power_fail / los from the status column as
        // last_down_cause when no explicit cause column exists.
        let cause_from_status = status_cause(&norm_status).map(String::from);

        let distance_meters = col_map
            .distance
            .and_then(|i| parse_u32_cell(record.get(i), &mut report.cells_unparsed));

        let eth_speed_mbps = col_map
            .eth_speed
            .and_then(|i| parse_u32_cell(record.get(i), &mut report.cells_unparsed));

        let explicit_cause = col_map
            .last_down_cause
            .and_then(|i| record.get(i))
            .map(clean_cell)
            .filter(|s| !s.is_empty())
            .map(String::from);

        // Use explicit last_down_cause column if present, otherwise infer from status
        let last_down_cause = explicit_cause.or(cause_from_status);

        // Transceiver DDM: unit suffixes ("45.2 °C", "3.31 V", "12.4 mA")
        // are stripped by parse_number; physically implausible values and
        // vendor sentinels are dropped by the SFF-8472 plausibility windows.
        let temperature_c = col_map
            .temperature
            .and_then(|i| parse_f64_cell(record.get(i), &mut report.cells_unparsed))
            .and_then(plausible_temp_c);

        let voltage_v = col_map
            .voltage
            .and_then(|i| parse_f64_cell(record.get(i), &mut report.cells_unparsed))
            .and_then(plausible_voltage_v);

        let bias_current_ma = col_map
            .bias_current
            .and_then(|i| parse_f64_cell(record.get(i), &mut report.cells_unparsed))
            .and_then(plausible_bias_ma);

        let fec_corrected = col_map
            .fec_corrected
            .and_then(|i| parse_u64_cell(record.get(i), &mut report.cells_unparsed));

        let fec_uncorrected = col_map
            .fec_uncorrected
            .and_then(|i| parse_u64_cell(record.get(i), &mut report.cells_unparsed));

        let bip_errors = col_map
            .bip_errors
            .and_then(|i| parse_u64_cell(record.get(i), &mut report.cells_unparsed));

        let in_octets = col_map
            .in_octets
            .and_then(|i| parse_u64_cell(record.get(i), &mut report.cells_unparsed));

        let out_octets = col_map
            .out_octets
            .and_then(|i| parse_u64_cell(record.get(i), &mut report.cells_unparsed));

        report.readings.push(OntReading {
            timestamp,
            serial_number,
            pon_port,
            rx_power_dbm,
            tx_power_dbm,
            status,
            distance_meters,
            eth_speed_mbps,
            last_down_cause,
            fec_corrected,
            fec_uncorrected,
            bip_errors,
            temperature_c,
            voltage_v,
            bias_current_ma,
            in_octets,
            out_octets,
        });
        report.rows_ok += 1;
    }

    Ok(report)
}

fn skip_row(report: &mut ImportReport, row_num: usize, reason: &str) {
    report.rows_skipped += 1;
    if report.skip_samples.len() < MAX_SAMPLES {
        report.skip_samples.push(format!("row {}: {}", row_num, reason));
    }
}

// ---------------------------------------------------------------------------
// Header normalization, delimiter sniffing, column resolution
// ---------------------------------------------------------------------------

/// Normalize a header cell (or status value) for alias matching: lowercase,
/// drop parenthesized/bracketed units ("RX Power (dBm)" -> "rx power"), map
/// every other non-alphanumeric character (including BOM) to a space, and
/// collapse runs of spaces.
pub(crate) fn normalize_header(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut depth = 0u32;
    for c in raw.chars() {
        match c {
            '(' | '[' => depth += 1,
            ')' | ']' => depth = depth.saturating_sub(1),
            _ if depth > 0 => {}
            c if c.is_ascii_alphanumeric() => out.push(c.to_ascii_lowercase()),
            _ => out.push(' '),
        }
    }
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Count how many header cells match any known alias group.
pub(crate) fn header_score(cells: &[&str]) -> usize {
    cells
        .iter()
        .map(|c| normalize_header(c))
        .filter(|n| {
            !n.is_empty() && ALL_ALIAS_GROUPS.iter().any(|g| g.contains(&n.as_str()))
        })
        .count()
}

/// True when any header cell is a recognized serial/ONT identity column.
pub(crate) fn has_serial_column(cells: &[&str]) -> bool {
    cells.iter().any(|c| {
        let n = normalize_header(c);
        SERIAL_ALIASES.contains(&n.as_str()) || ONT_ID_ALIASES.contains(&n.as_str())
    })
}

/// Pick the delimiter (comma, semicolon, or tab) that yields the most
/// recognized header fields; ties fall back to the most columns.
pub(crate) fn sniff_delimiter(header_line: &str) -> u8 {
    let mut best = b',';
    let mut best_key = (0usize, 0usize);
    for &d in &[b',', b';', b'\t'] {
        let cells: Vec<&str> = header_line.split(d as char).collect();
        let key = (header_score(&cells), cells.len());
        if key > best_key {
            best_key = key;
            best = d;
        }
    }
    best
}

/// Read the raw header line of a file (for delimiter sniffing and vendor
/// detection) without committing to a delimiter.
pub(crate) fn read_header_line(path: &Path) -> Result<String> {
    let f = std::fs::File::open(path)
        .with_context(|| format!("Failed to open CSV: {}", path.display()))?;
    let mut line = String::new();
    BufReader::new(f)
        .read_line(&mut line)
        .with_context(|| format!("Failed to read CSV header: {}", path.display()))?;
    Ok(line.trim_end_matches(['\r', '\n']).to_string())
}

/// Match CSV header names to column indices via normalized alias tables.
fn resolve_columns(headers: &csv::StringRecord) -> Result<ColumnMap> {
    let normalized: Vec<String> = headers.iter().map(normalize_header).collect();

    let find = |aliases: &[&str]| -> Option<usize> {
        normalized.iter().position(|h| aliases.contains(&h.as_str()))
    };

    let serial = find(SERIAL_ALIASES)
        .or_else(|| find(ONT_ID_ALIASES))
        .context("CSV missing required serial number column")?;

    let pon_port = find(PON_PORT_ALIASES)
        .or_else(|| find(OLT_ALIASES))
        .context("CSV missing required PON port column")?;

    Ok(ColumnMap {
        timestamp: find(TIMESTAMP_ALIASES),
        serial,
        pon_port,
        rx_power: find(RX_POWER_ALIASES),
        tx_power: find(TX_POWER_ALIASES),
        status: find(STATUS_ALIASES),
        distance: find(DISTANCE_ALIASES),
        eth_speed: find(ETH_SPEED_ALIASES),
        last_down_cause: find(DOWN_CAUSE_ALIASES),
        temperature: find(TEMPERATURE_ALIASES),
        voltage: find(VOLTAGE_ALIASES),
        bias_current: find(BIAS_ALIASES),
        fec_corrected: find(FEC_CORRECTED_ALIASES),
        fec_uncorrected: find(FEC_UNCORRECTED_ALIASES),
        bip_errors: find(BIP_ALIASES),
        in_octets: find(IN_OCTETS_ALIASES),
        out_octets: find(OUT_OCTETS_ALIASES),
    })
}

// ---------------------------------------------------------------------------
// Timestamp parsing
// ---------------------------------------------------------------------------

/// Parse a timestamp string in multiple common formats, returning UTC DateTime.
fn parse_timestamp(s: &str) -> Result<DateTime<Utc>> {
    let s = clean_cell(s);

    // ISO 8601 with timezone
    if let Ok(dt) = DateTime::parse_from_rfc3339(s) {
        return Ok(dt.with_timezone(&Utc));
    }

    // Unix epoch: seconds (10 digits) or milliseconds (13 digits)
    if !s.is_empty() && s.chars().all(|c| c.is_ascii_digit()) {
        if let Ok(n) = s.parse::<i64>() {
            let dt = match s.len() {
                10 => DateTime::from_timestamp(n, 0),
                13 => DateTime::from_timestamp(n / 1000, ((n % 1000) * 1_000_000) as u32),
                _ => None,
            };
            if let Some(dt) = dt {
                return Ok(dt);
            }
        }
    }

    // Explicit UTC offsets without the strict RFC 3339 shape
    for fmt in ["%Y-%m-%d %H:%M:%S%.f %z", "%Y-%m-%d %H:%M:%S%.f%z", "%Y-%m-%dT%H:%M:%S%.f%z"] {
        if let Ok(dt) = DateTime::parse_from_str(s, fmt) {
            return Ok(dt.with_timezone(&Utc));
        }
    }

    // Slash dates: UK day-first vs US month-first, disambiguated below
    if let Some(ndt) = parse_slash_datetime(s) {
        return Ok(ndt.and_utc());
    }

    // Common naive formats (all interpreted as UTC)
    let formats = [
        "%Y-%m-%d %H:%M:%S%.f",
        "%Y-%m-%dT%H:%M:%S%.f",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
    ];
    for fmt in &formats {
        if let Ok(ndt) = NaiveDateTime::parse_from_str(s, fmt) {
            return Ok(ndt.and_utc());
        }
    }

    // Date-only formats
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"] {
        if let Ok(nd) = chrono::NaiveDate::parse_from_str(s, fmt) {
            return Ok(nd
                .and_hms_opt(0, 0, 0)
                .expect("midnight is always valid")
                .and_utc());
        }
    }

    anyhow::bail!("Unrecognized timestamp format: '{}'", s)
}

/// Parse "A/B/Y[ H:M[:S]]" dates. "YYYY/…" is year-first; otherwise the date
/// is day-first (UK) unless the second component exceeds 12, which forces US
/// month-first. Ambiguous dates default to day-first (UK pilot).
fn parse_slash_datetime(s: &str) -> Option<NaiveDateTime> {
    let date_part = s.split_whitespace().next()?;
    let parts: Vec<&str> = date_part.split('/').collect();
    if parts.len() != 3 {
        return None;
    }

    if parts[0].len() == 4 {
        for fmt in ["%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"] {
            if let Ok(ndt) = NaiveDateTime::parse_from_str(s, fmt) {
                return Some(ndt);
            }
        }
        if let Ok(nd) = chrono::NaiveDate::parse_from_str(s, "%Y/%m/%d") {
            return nd.and_hms_opt(0, 0, 0);
        }
        return None;
    }

    let a: u32 = parts[0].parse().ok()?;
    let b: u32 = parts[1].parse().ok()?;
    let day_first = a > 12 || b <= 12;
    let year_tok = if parts[2].len() <= 2 { "%y" } else { "%Y" };

    let orders: [&str; 2] = if day_first {
        ["%d/%m/", "%m/%d/"]
    } else {
        ["%m/%d/", "%d/%m/"]
    };
    for prefix in orders {
        let date_fmt = format!("{}{}", prefix, year_tok);
        for time_fmt in [" %H:%M:%S", " %H:%M"] {
            let fmt = format!("{}{}", date_fmt, time_fmt);
            if let Ok(ndt) = NaiveDateTime::parse_from_str(s, &fmt) {
                return Some(ndt);
            }
        }
        if let Ok(nd) = chrono::NaiveDate::parse_from_str(s, &date_fmt) {
            return nd.and_hms_opt(0, 0, 0);
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Value parsing
// ---------------------------------------------------------------------------

/// Missing-value markers treated as empty rather than parse failures.
const NA_MARKERS: &[&str] = &["n/a", "na", "n a", "-", "--", "null", "none", "nil", "unknown"];

/// Trim whitespace and surrounding quotes from a raw cell.
fn clean_cell(raw: &str) -> &str {
    raw.trim().trim_matches(|c| c == '"' || c == '\'').trim()
}

fn is_missing(s: &str) -> bool {
    s.is_empty() || NA_MARKERS.contains(&s.to_ascii_lowercase().as_str())
}

/// Parse a numeric cell value: strips quotes and unit suffixes
/// ("-22.4 dBm", "1200m"), maps Unicode minus/dashes to '-', and handles
/// decimal commas ("−22,4") and thousands separators ("1,234.5").
fn parse_number(raw: &str) -> Option<f64> {
    let s: String = clean_cell(raw)
        .chars()
        .map(|c| match c {
            '\u{2212}' | '\u{2013}' | '\u{2014}' => '-',
            c => c,
        })
        .collect();

    // Take the leading numeric portion; stop at a unit suffix.
    let mut num = String::new();
    for c in s.trim_start().chars() {
        match c {
            '+' | '-' if num.is_empty() => num.push(c),
            c if c.is_ascii_digit() => num.push(c),
            '.' | ',' => num.push(c),
            _ => break,
        }
    }
    if num.is_empty() || num == "-" || num == "+" {
        return None;
    }

    let num = if num.contains(',') {
        if num.contains('.') || num.matches(',').count() > 1 {
            num.replace(',', "") // thousands separators: "1,234.5"
        } else {
            num.replace(',', ".") // unambiguous decimal comma: "−22,4"
        }
    } else {
        num
    };

    num.parse::<f64>().ok()
}

/// Parse an optional f64 cell; non-empty unparseable cells are counted.
fn parse_f64_cell(val: Option<&str>, cells_unparsed: &mut usize) -> Option<f64> {
    let s = clean_cell(val.unwrap_or(""));
    if is_missing(s) {
        return None;
    }
    match parse_number(s) {
        Some(v) => Some(v),
        None => {
            *cells_unparsed += 1;
            None
        }
    }
}

/// Parse an optional u32 cell; non-empty unparseable cells are counted.
fn parse_u32_cell(val: Option<&str>, cells_unparsed: &mut usize) -> Option<u32> {
    let s = clean_cell(val.unwrap_or(""));
    if is_missing(s) {
        return None;
    }
    match parse_number(s) {
        Some(v) if v.is_finite() && (0.0..=u32::MAX as f64).contains(&v) => {
            Some(v.round() as u32)
        }
        _ => {
            *cells_unparsed += 1;
            None
        }
    }
}

/// Parse an optional u64 counter cell (FEC/BIP counters, traffic octets);
/// non-empty unparseable or negative cells are counted.
fn parse_u64_cell(val: Option<&str>, cells_unparsed: &mut usize) -> Option<u64> {
    let s = clean_cell(val.unwrap_or(""));
    if is_missing(s) {
        return None;
    }
    match parse_number(s) {
        Some(v) if v.is_finite() && (0.0..=u64::MAX as f64).contains(&v) => {
            Some(v.round() as u64)
        }
        _ => {
            *cells_unparsed += 1;
            None
        }
    }
}

// ---------------------------------------------------------------------------
// Status parsing
// ---------------------------------------------------------------------------

#[derive(Debug, PartialEq)]
enum ParsedStatus {
    Online,
    Offline,
    Unknown,
}

/// Map a normalized status value to Online/Offline/Unknown. The vocabulary
/// covers real Mosaic / Mission Control / TL1-style exports (IS/OOS,
/// enabled/disabled, sync, los, dying gasp...). Anything else is Unknown —
/// never Offline.
fn parse_status(normalized: &str) -> ParsedStatus {
    const ONLINE: &[&str] = &[
        "online", "up", "active", "act", "1", "true", "yes", "is",
        "in service", "in svc", "insvc", "enabled", "enable", "working",
        "operational", "sync", "in sync", "synced", "registered",
        "authenticated", "auth", "normal", "ok", "run", "running",
        "connected", "up up",
    ];
    const OFFLINE: &[&str] = &[
        "offline", "down", "inactive", "0", "false", "no", "oos",
        "out of service", "out of svc", "disabled", "disable", "los", "lof",
        "loss of signal", "dying gasp", "dyinggasp", "dg", "power fail",
        "powerfail", "power off", "power outage", "fiber cut", "fibre cut",
        "fibercut", "lost", "silent", "dead", "failed", "fail",
        "deactivated", "deregistered", "unregistered", "mismatch",
        "sn mismatch", "not present", "absent", "disconnected",
    ];

    if ONLINE.contains(&normalized) {
        ParsedStatus::Online
    } else if OFFLINE.contains(&normalized) {
        ParsedStatus::Offline
    } else if normalized.starts_with("oos ") {
        ParsedStatus::Offline // TL1 qualifiers: "OOS-AU", "OOS-MA", ...
    } else if normalized.starts_with("is ") {
        ParsedStatus::Online // TL1 qualifiers: "IS-NR", ...
    } else {
        ParsedStatus::Unknown
    }
}

/// Infer last_down_cause from a normalized status value.
fn status_cause(normalized: &str) -> Option<&'static str> {
    match normalized {
        "dying gasp" | "dyinggasp" | "dg" => Some("dying_gasp"),
        "power fail" | "powerfail" | "power off" | "power outage" => Some("power_fail"),
        "los" | "lof" | "loss of signal" | "fiber cut" | "fibre cut" | "fibercut" => Some("los"),
        _ => None,
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

    fn parse(path: &Path) -> Result<Vec<OntReading>> {
        Ok(parse_with_report(path, None)?.readings)
    }

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
    fn test_synthetic_csv_report_counters() {
        let f = sample_csv();
        let report = parse_with_report(f.path(), None).unwrap();
        assert_eq!(report.rows_ok, 4);
        assert_eq!(report.rows_skipped, 0);
        assert_eq!(report.cells_unparsed, 0);
        assert_eq!(report.unknown_statuses, 0);
        assert!(!report.snapshot_mode);
        assert_eq!(report.delimiter, b',');
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

    #[test]
    fn test_snake_case_ddm_fec_and_octet_columns() {
        // Synthetic snake_case export: every frontier-signal column present.
        let mut f = NamedTempFile::new().unwrap();
        writeln!(
            f,
            "timestamp,ont_serial,pon_port,status,temperature_c,voltage_v,\
             bias_current_ma,fec_corrected,fec_uncorrected,bip_errors,\
             rx_octets,tx_octets"
        )
        .unwrap();
        writeln!(
            f,
            "2026-03-01 08:00:00,ADTN-001,CTP-0/1,online,44.9,3.29,11.8,\
             1200,4,17,\"1,234,567\",7654321"
        )
        .unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings.len(), 1);
        let r = &readings[0];
        assert_eq!(r.temperature_c, Some(44.9));
        assert_eq!(r.voltage_v, Some(3.29));
        assert_eq!(r.bias_current_ma, Some(11.8));
        assert_eq!(r.fec_corrected, Some(1200));
        assert_eq!(r.fec_uncorrected, Some(4));
        assert_eq!(r.bip_errors, Some(17));
        // rx_octets = received by the ONT (downstream) -> in_octets;
        // quoted thousands separators must parse.
        assert_eq!(r.in_octets, Some(1_234_567));
        assert_eq!(r.out_octets, Some(7_654_321));
    }

    #[test]
    fn test_implausible_ddm_values_dropped_but_counters_kept() {
        // A negative FEC counter is nonsense -> unparsed; DDM sentinels are
        // parseable but implausible -> dropped without counting as unparsed.
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial,pon_port,status,temperature_c,fec_corrected").unwrap();
        writeln!(f, "2026-03-01 08:00:00,ADTN-001,CTP-0/1,online,2147483647,-5").unwrap();
        let report = parse_with_report(f.path(), None).unwrap();
        assert_eq!(report.rows_ok, 1);
        let r = &report.readings[0];
        assert_eq!(r.temperature_c, None, "sentinel temperature must be dropped");
        assert_eq!(r.fec_corrected, None, "negative counter must be rejected");
        assert_eq!(report.cells_unparsed, 1, "only the negative counter counts as unparsed");
    }

    // -----------------------------------------------------------------
    // Realistic export fixtures
    // -----------------------------------------------------------------

    #[test]
    fn test_mission_control_style_export() {
        // "Serial Number" / "RX Power (dBm)" / "Operational Status" headers
        // with TL1-style IS/OOS statuses — the format the old exact-match
        // snake_case parser rejected outright.
        let report = parse_with_report(&fixture("mission_control.csv"), None).unwrap();
        assert_eq!(report.rows_ok, 4);
        assert_eq!(report.rows_skipped, 0);
        assert_eq!(report.cells_unparsed, 0);
        assert_eq!(report.unknown_statuses, 0);
        assert!(!report.snapshot_mode);
        assert_eq!(report.delimiter, b',');

        let r = &report.readings;
        assert_eq!(r[0].serial_number, "ADTN21341A8C");
        assert_eq!(r[0].pon_port, "1/1/xpon 1");
        assert_eq!(r[0].rx_power_dbm, Some(-21.7));
        assert_eq!(r[0].tx_power_dbm, Some(2.4));
        assert_eq!(r[0].distance_meters, Some(1204));
        assert_eq!(
            r[0].timestamp,
            "2026-06-30T08:15:00Z".parse::<DateTime<Utc>>().unwrap()
        );

        // DDM detail with unit suffixes ("45.5 °C", "3.31 V", "12.4 mA")
        assert_eq!(r[0].temperature_c, Some(45.5));
        assert_eq!(r[0].voltage_v, Some(3.31));
        assert_eq!(r[0].bias_current_ma, Some(12.4));
        // FEC/BIP counters and traffic octets
        assert_eq!(r[0].fec_corrected, Some(18234));
        assert_eq!(r[0].fec_uncorrected, Some(0));
        assert_eq!(r[0].bip_errors, Some(3));
        assert_eq!(r[0].in_octets, Some(182_347_776));
        assert_eq!(r[0].out_octets, Some(23_456_789));

        // Row 2 carries the classic /100-scaled DDM sentinels (327.67 /
        // 655.35): parseable numbers, but physically implausible — they must
        // be dropped by the SFF-8472 windows, NOT surface as real readings
        // (and NOT count as unparsed cells, asserted above).
        assert_eq!(r[1].temperature_c, None);
        assert_eq!(r[1].voltage_v, None);
        assert_eq!(r[1].bias_current_ma, None);
        assert_eq!(r[1].fec_corrected, Some(52));
        assert_eq!(r[1].fec_uncorrected, Some(1));
        assert_eq!(r[1].bip_errors, Some(0));

        // Offline row 3 has all-empty extras: None across the board.
        assert_eq!(r[2].temperature_c, None);
        assert_eq!(r[2].voltage_v, None);
        assert_eq!(r[2].bias_current_ma, None);
        assert_eq!(r[2].fec_corrected, None);
        assert_eq!(r[2].fec_uncorrected, None);
        assert_eq!(r[2].bip_errors, None);
        assert_eq!(r[2].in_octets, None);
        assert_eq!(r[2].out_octets, None);

        // "IS" / "IS-NR" must map to Online — never Offline.
        assert_eq!(r[0].status, OntReadingStatus::Online);
        assert_eq!(r[1].status, OntReadingStatus::Online);
        assert_eq!(r[3].status, OntReadingStatus::Online);
        // Only the genuine "OOS" row is Offline.
        assert_eq!(r[2].status, OntReadingStatus::Offline);
        let offline = r
            .iter()
            .filter(|x| x.status == OntReadingStatus::Offline)
            .count();
        assert_eq!(offline, 1);
    }

    #[test]
    fn test_uk_excel_semicolon_export() {
        // Semicolon delimiter, UTF-8 BOM, CRLF line endings, quoted numbers
        // with decimal commas and Unicode minus, day-first timestamps.
        let report = parse_with_report(&fixture("uk_excel_semicolon.csv"), None).unwrap();
        assert_eq!(report.delimiter, b';');
        assert_eq!(report.rows_ok, 3);
        assert_eq!(report.rows_skipped, 0);
        assert_eq!(report.cells_unparsed, 0);

        let r = &report.readings;
        assert_eq!(r[0].serial_number, "ADTN21341A8C");
        assert_eq!(r[0].rx_power_dbm, Some(-21.7)); // "−21,7" quoted, U+2212
        assert_eq!(r[0].tx_power_dbm, Some(2.4)); // "2,4"
        assert_eq!(r[1].rx_power_dbm, Some(-23.1)); // -23,1 unquoted
        // 30/06/2026 08:15 must parse day-first (June 30th).
        assert_eq!(
            r[0].timestamp,
            "2026-06-30T08:15:00Z".parse::<DateTime<Utc>>().unwrap()
        );
        // "enabled"/"up" are Online, "disabled" is Offline.
        assert_eq!(r[0].status, OntReadingStatus::Online);
        assert_eq!(r[1].status, OntReadingStatus::Online);
        assert_eq!(r[2].status, OntReadingStatus::Offline);
    }

    #[test]
    fn test_snapshot_export_without_timestamp_column() {
        let default_ts = "2026-07-01T12:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let report =
            parse_with_report(&fixture("snapshot_no_timestamp.csv"), Some(default_ts)).unwrap();
        assert!(report.snapshot_mode);
        assert_eq!(report.rows_ok, 3);
        assert_eq!(report.rows_skipped, 0);

        let r = &report.readings;
        assert!(r.iter().all(|x| x.timestamp == default_ts));
        // Unit suffixes stripped: "-21.7 dBm" and "-23.4dBm".
        assert_eq!(r[0].rx_power_dbm, Some(-21.7));
        assert_eq!(r[1].rx_power_dbm, Some(-23.4));
        assert_eq!(r[0].status, OntReadingStatus::Online);
        assert_eq!(r[2].status, OntReadingStatus::Offline);
    }

    #[test]
    fn test_snapshot_defaults_to_import_time() {
        let before = Utc::now();
        let report = parse_with_report(&fixture("snapshot_no_timestamp.csv"), None).unwrap();
        let after = Utc::now();
        assert!(report.snapshot_mode);
        for r in &report.readings {
            assert!(r.timestamp >= before && r.timestamp <= after);
        }
    }

    #[test]
    fn test_corrupt_rows_skipped_and_counted() {
        // One bad timestamp, one missing serial, one unrecognized status —
        // none of them may abort the file or land as Offline. The
        // unrecognized-status row is KEPT with status Unknown (excluded from
        // outage math downstream), not dropped.
        let report = parse_with_report(&fixture("corrupt_rows.csv"), None).unwrap();
        assert_eq!(report.rows_ok, 4);
        assert_eq!(report.rows_skipped, 2);
        assert_eq!(report.cells_unparsed, 1); // rx "not-a-number"
        assert_eq!(report.unknown_statuses, 1);
        assert_eq!(
            report.unknown_status_values,
            vec!["provisioning pending".to_string()]
        );
        assert_eq!(report.skip_samples.len(), 2);
        assert!(report.skip_samples[0].contains("invalid timestamp"));
        assert!(report.skip_samples[1].contains("missing serial"));

        let r = &report.readings;
        assert_eq!(r.len(), 4);
        assert_eq!(r[0].serial_number, "ADTN21341A8C");
        // Unrecognized status row is kept as Unknown — never Offline.
        assert_eq!(r[1].serial_number, "ADTN21349C77");
        assert_eq!(r[1].status, OntReadingStatus::Unknown);
        assert_eq!(r[2].serial_number, "ADTN2134D1E9");
        assert_eq!(r[2].rx_power_dbm, None); // unparseable cell kept as None
        assert_eq!(r[2].status, OntReadingStatus::Online);
        // Only the genuine OOS row is Offline — unknown status never is.
        let offline: Vec<_> = r
            .iter()
            .filter(|x| x.status == OntReadingStatus::Offline)
            .collect();
        assert_eq!(offline.len(), 1);
        assert_eq!(offline[0].serial_number, "ADTN2134EE00");
    }

    #[test]
    fn test_tab_delimited_export() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "Timestamp\tSerial Number\tPON Port\tStatus\tRX Power (dBm)").unwrap();
        writeln!(f, "2026-06-30 08:15:00\tADTN21341A8C\t1/1/xp1\tIS\t-21.7").unwrap();
        let report = parse_with_report(f.path(), None).unwrap();
        assert_eq!(report.delimiter, b'\t');
        assert_eq!(report.rows_ok, 1);
        assert_eq!(report.readings[0].status, OntReadingStatus::Online);
    }

    #[test]
    fn test_missing_status_column_infers_online_from_rx() {
        // Pure optical snapshot without a status column: rows with an RX
        // reading are Online (the ONT is transmitting), rows without one
        // are kept as Unknown — never Offline.
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "Serial Number,PON Port,RX Power (dBm)").unwrap();
        writeln!(f, "ADTN-001,1/1/xp1,-21.7").unwrap();
        writeln!(f, "ADTN-002,1/1/xp1,").unwrap();
        let report = parse_with_report(f.path(), None).unwrap();
        assert!(report.snapshot_mode);
        assert_eq!(report.rows_ok, 2);
        assert_eq!(report.readings[0].status, OntReadingStatus::Online);
        assert_eq!(report.readings[1].status, OntReadingStatus::Unknown);
        assert_eq!(report.rows_skipped, 0);
        assert_eq!(report.unknown_statuses, 1);
    }

    #[test]
    fn test_status_from_los_sets_down_cause() {
        let mut f = NamedTempFile::new().unwrap();
        writeln!(f, "timestamp,ont_serial,pon_port,status").unwrap();
        writeln!(f, "2026-03-01 08:00:00,SN-001,0/1/0,LOS").unwrap();
        writeln!(f, "2026-03-01 08:00:00,SN-002,0/1/0,Dying-Gasp").unwrap();
        let readings = parse(f.path()).unwrap();
        assert_eq!(readings[0].status, OntReadingStatus::Offline);
        assert_eq!(readings[0].last_down_cause.as_deref(), Some("los"));
        assert_eq!(readings[1].last_down_cause.as_deref(), Some("dying_gasp"));
    }

    // -----------------------------------------------------------------
    // Unit-level parsers
    // -----------------------------------------------------------------

    #[test]
    fn test_parse_number_variants() {
        assert_eq!(parse_number("-22.4"), Some(-22.4));
        assert_eq!(parse_number("-22.4 dBm"), Some(-22.4));
        assert_eq!(parse_number("-22.4dBm"), Some(-22.4));
        assert_eq!(parse_number("\u{2212}22,4"), Some(-22.4)); // Unicode minus + decimal comma
        assert_eq!(parse_number("\"-22.4\""), Some(-22.4)); // quoted
        assert_eq!(parse_number("1,234.5"), Some(1234.5)); // thousands separator
        assert_eq!(parse_number("+2.4"), Some(2.4));
        assert_eq!(parse_number("1200m"), Some(1200.0));
        assert_eq!(parse_number("abc"), None);
        assert_eq!(parse_number(""), None);
    }

    #[test]
    fn test_timestamp_variants() {
        let expected = "2026-06-30T08:15:00Z".parse::<DateTime<Utc>>().unwrap();
        assert_eq!(parse_timestamp("2026-06-30T08:15:00Z").unwrap(), expected);
        assert_eq!(parse_timestamp("2026-06-30 08:15:00").unwrap(), expected);
        assert_eq!(parse_timestamp("2026-06-30 09:15:00+01:00").unwrap(), expected);
        // Day-first forced by first component > 12
        assert_eq!(parse_timestamp("30/06/2026 08:15").unwrap(), expected);
        // Month-first forced by second component > 12
        assert_eq!(parse_timestamp("06/30/2026 08:15").unwrap(), expected);
        // Ambiguous dates default to day-first (UK): 1st of February
        let feb1 = "2026-02-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        assert_eq!(parse_timestamp("01/02/2026").unwrap(), feb1);
        // Unix epoch seconds
        let epoch = DateTime::from_timestamp(1_767_083_700, 0).unwrap();
        assert_eq!(parse_timestamp("1767083700").unwrap(), epoch);
        assert!(parse_timestamp("not-a-date").is_err());
    }

    #[test]
    fn test_status_vocabulary() {
        for s in ["IS", "IS-NR", "enabled", "up", "active", "Online", "working", "sync", "1"] {
            assert_eq!(
                parse_status(&normalize_header(s)),
                ParsedStatus::Online,
                "{} should be Online",
                s
            );
        }
        for s in ["OOS", "OOS-AU", "disabled", "down", "inactive", "Offline", "LOS", "DyingGasp", "mismatch", "0"] {
            assert_eq!(
                parse_status(&normalize_header(s)),
                ParsedStatus::Offline,
                "{} should be Offline",
                s
            );
        }
        for s in ["provisioning-pending", "wibble", ""] {
            assert_eq!(
                parse_status(&normalize_header(s)),
                ParsedStatus::Unknown,
                "{} should be Unknown",
                s
            );
        }
    }

    #[test]
    fn test_sniff_delimiter() {
        assert_eq!(sniff_delimiter("timestamp,ont_serial,pon_port,status"), b',');
        assert_eq!(
            sniff_delimiter("Serial Number;RX Power (dBm);Status"),
            b';'
        );
        assert_eq!(
            sniff_delimiter("Serial Number\tRX Power (dBm)\tStatus"),
            b'\t'
        );
    }

    #[test]
    fn test_normalize_header() {
        assert_eq!(normalize_header("RX Power (dBm)"), "rx power");
        assert_eq!(normalize_header("Serial Number"), "serial number");
        assert_eq!(normalize_header("rx_power_dbm"), "rx power dbm");
        assert_eq!(normalize_header("  ONT-ID  "), "ont id");
        assert_eq!(normalize_header("\u{feff}Serial Number"), "serial number");
    }
}
