// SPDX-License-Identifier: Apache-2.0
// SFP Transceiver Health Monitor
//
// Detects OLT SFP module degradation at the PORT level by analyzing
// correlated Rx power shifts across all ONTs on a PON port. When an
// SFP degrades, ALL ONTs on that port show a coordinated Rx power
// decline — regardless of distance. This distinguishes SFP issues from:
//
//   - Weather degradation (distance-grouped ONTs affected)
//   - Per-ONT fibre faults (individual ONT affected)
//   - Fibre cuts (sudden total loss, not gradual trend)
//
// Detection method:
//   1. Group readings by port
//   2. Calculate daily average Rx power of all online ONTs per port
//   3. Linear regression on daily port-average Rx over the data window
//   4. Cross-port comparison: flag ports degrading faster than siblings
//   5. Classify severity by slope and absolute power level

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// SFP health assessment for a single OLT port.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SfpHealth {
    pub port: String,
    pub olt_id: String,
    pub avg_rx_power_dbm: f64,
    pub rx_trend_per_week: f64,
    pub ont_count: u32,
    pub correlation: f64,
    pub severity: SfpSeverity,
    pub estimated_weeks_to_failure: Option<f64>,
    pub is_outlier_vs_siblings: bool,
}

/// SFP degradation severity level.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SfpSeverity {
    Healthy,
    Watch,
    Warning,
    Critical,
}

/// Slope threshold (dBm/week): slopes flatter than this are Healthy.
const SLOPE_HEALTHY_LIMIT: f64 = -0.01;

/// Slope threshold (dBm/week): slopes between this and HEALTHY are Watch.
const SLOPE_WATCH_LIMIT: f64 = -0.05;

/// Slope threshold (dBm/week): slopes between this and WATCH are Warning.
const SLOPE_WARNING_LIMIT: f64 = -0.1;

/// Absolute Rx power (dBm) below which a port is Critical regardless of trend.
const CRITICAL_RX_THRESHOLD_DBM: f64 = -26.0;

/// Rx power (dBm) at which the SFP is considered failed.
const FAILURE_RX_THRESHOLD_DBM: f64 = -28.0;

/// Number of standard deviations from sibling mean to flag as outlier.
const OUTLIER_STDEV_FACTOR: f64 = 1.0;

/// Minimum number of daily samples to perform regression.
const MIN_DAILY_SAMPLES: usize = 3;

/// Analyze SFP health across all ports found in the readings.
///
/// Groups readings by port, computes daily average Rx power per port,
/// fits a linear trend, and compares each port against its siblings
/// (other ports sharing the same OLT prefix) to detect outliers.
pub fn analyze_sfp_health(readings: &[OntReading]) -> Vec<SfpHealth> {
    if readings.is_empty() {
        return Vec::new();
    }

    // Group readings by port
    let mut by_port: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_port.entry(r.pon_port.clone()).or_default().push(r);
    }

    // For each port, compute daily average Rx and per-ONT daily Rx
    let mut port_stats: Vec<PortStats> = Vec::new();

    for (port, port_readings) in &by_port {
        let online_readings: Vec<&&OntReading> = port_readings
            .iter()
            .filter(|r| r.status == OntReadingStatus::Online && r.rx_power_dbm.is_some())
            .collect();

        if online_readings.is_empty() {
            continue;
        }

        // Count unique ONTs
        let mut ont_serials: Vec<&str> = online_readings
            .iter()
            .map(|r| r.serial_number.as_str())
            .collect();
        ont_serials.sort();
        ont_serials.dedup();
        let ont_count = ont_serials.len() as u32;

        // Compute daily averages (day = days since epoch)
        let mut daily_sums: HashMap<i64, (f64, u32)> = HashMap::new();
        for r in &online_readings {
            let day = r.timestamp.timestamp() / 86400;
            let rx = r.rx_power_dbm.unwrap();
            let entry = daily_sums.entry(day).or_insert((0.0, 0));
            entry.0 += rx;
            entry.1 += 1;
        }

        let mut daily_avgs: Vec<(f64, f64)> = daily_sums
            .iter()
            .map(|(day, (sum, count))| (*day as f64, sum / *count as f64))
            .collect();
        daily_avgs.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

        if daily_avgs.len() < MIN_DAILY_SAMPLES {
            // Not enough data for regression; report current state only
            let overall_avg = online_readings
                .iter()
                .filter_map(|r| r.rx_power_dbm)
                .sum::<f64>()
                / online_readings.len() as f64;

            let severity = if overall_avg < CRITICAL_RX_THRESHOLD_DBM {
                SfpSeverity::Critical
            } else {
                SfpSeverity::Healthy
            };

            port_stats.push(PortStats {
                port: port.clone(),
                olt_id: extract_olt_id(port),
                avg_rx: overall_avg,
                slope_per_week: 0.0,
                ont_count,
                correlation: 0.0,
                severity,
            });
            continue;
        }

        // Linear regression: y = slope * x + intercept (x in days)
        let (slope_per_day, _intercept) = linear_regression(&daily_avgs);
        let slope_per_week = slope_per_day * 7.0;

        // Overall average Rx
        let overall_avg = daily_avgs.iter().map(|(_, y)| y).sum::<f64>() / daily_avgs.len() as f64;

        // Compute correlation: how uniformly do individual ONTs track the port trend?
        let correlation = compute_ont_correlation(&online_readings, &daily_avgs, &ont_serials);

        // Classify severity
        let severity = classify_severity(slope_per_week, overall_avg);

        port_stats.push(PortStats {
            port: port.clone(),
            olt_id: extract_olt_id(port),
            avg_rx: overall_avg,
            slope_per_week,
            ont_count,
            correlation,
            severity,
        });
    }

    // Cross-port comparison: group by OLT and find outliers
    let mut by_olt: HashMap<String, Vec<usize>> = HashMap::new();
    for (idx, ps) in port_stats.iter().enumerate() {
        by_olt.entry(ps.olt_id.clone()).or_default().push(idx);
    }

    let mut outlier_flags: Vec<bool> = vec![false; port_stats.len()];
    for (_olt_id, indices) in &by_olt {
        if indices.len() < 2 {
            continue;
        }

        let slopes: Vec<f64> = indices.iter().map(|&i| port_stats[i].slope_per_week).collect();
        let mean_slope = slopes.iter().sum::<f64>() / slopes.len() as f64;
        let variance = slopes.iter().map(|s| (s - mean_slope).powi(2)).sum::<f64>() / slopes.len() as f64;
        let stdev = variance.sqrt();

        if stdev < 1e-9 {
            continue;
        }

        for &idx in indices {
            let deviation = (port_stats[idx].slope_per_week - mean_slope) / stdev;
            // A port degrading faster means a more negative slope.
            // deviation < -OUTLIER_STDEV_FACTOR means it is degrading faster than siblings.
            if deviation < -OUTLIER_STDEV_FACTOR {
                outlier_flags[idx] = true;
            }
        }
    }

    // Build results
    port_stats
        .iter()
        .enumerate()
        .map(|(idx, ps)| {
            let estimated_weeks = if ps.slope_per_week < -1e-6 {
                let remaining = ps.avg_rx - FAILURE_RX_THRESHOLD_DBM;
                if remaining > 0.0 {
                    Some(remaining / ps.slope_per_week.abs())
                } else {
                    Some(0.0)
                }
            } else {
                None
            };

            SfpHealth {
                port: ps.port.clone(),
                olt_id: ps.olt_id.clone(),
                avg_rx_power_dbm: ps.avg_rx,
                rx_trend_per_week: ps.slope_per_week,
                ont_count: ps.ont_count,
                correlation: ps.correlation,
                severity: ps.severity.clone(),
                estimated_weeks_to_failure: estimated_weeks,
                is_outlier_vs_siblings: outlier_flags[idx],
            }
        })
        .collect()
}

/// Internal per-port statistics before cross-port comparison.
struct PortStats {
    port: String,
    olt_id: String,
    avg_rx: f64,
    slope_per_week: f64,
    ont_count: u32,
    correlation: f64,
    severity: SfpSeverity,
}

/// Extract OLT identifier from a port string.
/// Assumes format like "OLT01/0/1/0" → "OLT01" or "0/1/0" → "0".
fn extract_olt_id(port: &str) -> String {
    // Try splitting on '/' and taking everything before the last two segments
    let parts: Vec<&str> = port.split('/').collect();
    if parts.len() >= 3 {
        parts[..parts.len() - 2].join("/")
    } else {
        port.to_string()
    }
}

/// Simple linear regression: returns (slope, intercept).
fn linear_regression(points: &[(f64, f64)]) -> (f64, f64) {
    let n = points.len() as f64;
    let sum_x: f64 = points.iter().map(|(x, _)| x).sum();
    let sum_y: f64 = points.iter().map(|(_, y)| y).sum();
    let sum_xy: f64 = points.iter().map(|(x, y)| x * y).sum();
    let sum_xx: f64 = points.iter().map(|(x, _)| x * x).sum();

    let denom = n * sum_xx - sum_x * sum_x;
    if denom.abs() < 1e-12 {
        return (0.0, sum_y / n);
    }

    let slope = (n * sum_xy - sum_x * sum_y) / denom;
    let intercept = (sum_y - slope * sum_x) / n;
    (slope, intercept)
}

/// Compute how correlated individual ONT Rx trends are with the port-level trend.
///
/// Returns 0.0-1.0 where 1.0 means all ONTs degrade at the same rate (SFP issue)
/// and 0.0 means ONTs degrade independently (individual fibre issues).
fn compute_ont_correlation(
    readings: &[&&OntReading],
    daily_port_avgs: &[(f64, f64)],
    ont_serials: &[&str],
) -> f64 {
    if ont_serials.len() < 2 || daily_port_avgs.len() < MIN_DAILY_SAMPLES {
        return 0.0;
    }

    // Build per-ONT daily averages
    let mut ont_daily: HashMap<&str, HashMap<i64, (f64, u32)>> = HashMap::new();
    for r in readings {
        if let Some(rx) = r.rx_power_dbm {
            let day = r.timestamp.timestamp() / 86400;
            let entry = ont_daily
                .entry(&r.serial_number)
                .or_default()
                .entry(day)
                .or_insert((0.0, 0));
            entry.0 += rx;
            entry.1 += 1;
        }
    }

    // For each ONT, compute its slope
    let mut slopes: Vec<f64> = Vec::new();
    for serial in ont_serials {
        if let Some(daily) = ont_daily.get(serial) {
            let mut points: Vec<(f64, f64)> = daily
                .iter()
                .map(|(day, (sum, count))| (*day as f64, sum / *count as f64))
                .collect();
            points.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));

            if points.len() >= MIN_DAILY_SAMPLES {
                let (slope, _) = linear_regression(&points);
                slopes.push(slope);
            }
        }
    }

    if slopes.len() < 2 {
        return 0.0;
    }

    // Correlation = 1 - (coefficient of variation of slopes)
    // If all slopes are identical → CV=0 → correlation=1
    let mean = slopes.iter().sum::<f64>() / slopes.len() as f64;
    if mean.abs() < 1e-9 {
        // No trend at all; check if all slopes are near zero
        let all_near_zero = slopes.iter().all(|s| s.abs() < 1e-6);
        return if all_near_zero { 1.0 } else { 0.0 };
    }

    let variance = slopes.iter().map(|s| (s - mean).powi(2)).sum::<f64>() / slopes.len() as f64;
    let cv = variance.sqrt() / mean.abs();

    // Clamp to 0.0-1.0
    (1.0 - cv).clamp(0.0, 1.0)
}

/// Classify SFP severity from slope (dBm/week) and current average Rx power.
fn classify_severity(slope_per_week: f64, avg_rx: f64) -> SfpSeverity {
    if avg_rx < CRITICAL_RX_THRESHOLD_DBM {
        return SfpSeverity::Critical;
    }
    if slope_per_week < SLOPE_WARNING_LIMIT {
        return SfpSeverity::Critical;
    }
    if slope_per_week < SLOPE_WATCH_LIMIT {
        return SfpSeverity::Warning;
    }
    if slope_per_week < SLOPE_HEALTHY_LIMIT {
        return SfpSeverity::Watch;
    }
    SfpSeverity::Healthy
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: chrono::DateTime<Utc>,
        rx: Option<f64>,
        distance: Option<u32>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: Some(2.5),
            status: OntReadingStatus::Online,
            distance_meters: distance,
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
        }
    }

    /// Generate stable readings for a set of ONTs on a port over N days.
    fn generate_stable_readings(
        serials: &[String],
        port: &str,
        base_rx: f64,
        days: u32,
    ) -> Vec<OntReading> {
        let mut readings = Vec::new();
        for day in 0..days {
            for hour in (0..24).step_by(6) {
                let ts = Utc.with_ymd_and_hms(2026, 1, 1 + day, hour, 0, 0).unwrap();
                for (i, serial) in serials.iter().enumerate() {
                    let distance = 500 + i as u32 * 100;
                    readings.push(make_reading(serial, port, ts, Some(base_rx), Some(distance)));
                }
            }
        }
        readings
    }

    /// Generate degrading readings for a set of ONTs on a port over N days.
    fn generate_degrading_readings(
        serials: &[String],
        port: &str,
        base_rx: f64,
        slope_per_day: f64,
        days: u32,
    ) -> Vec<OntReading> {
        let mut readings = Vec::new();
        for day in 0..days {
            for hour in (0..24).step_by(6) {
                let ts = Utc.with_ymd_and_hms(2026, 1, 1 + day, hour, 0, 0).unwrap();
                let rx = base_rx + slope_per_day * day as f64;
                for (i, serial) in serials.iter().enumerate() {
                    let distance = 500 + i as u32 * 100;
                    readings.push(make_reading(serial, port, ts, Some(rx), Some(distance)));
                }
            }
        }
        readings
    }

    fn onts(prefix: &str, count: u32) -> Vec<String> {
        (0..count).map(|i| format!("{}{:03}", prefix, i)).collect()
    }

    #[test]
    fn test_sfp_healthy_stable() {
        let mut readings = Vec::new();
        // 3 ports on the same OLT, all stable
        for port_idx in 0..3 {
            let port = format!("OLT01/0/{}/0", port_idx);
            let serials = onts("S", 10);
            readings.extend(generate_stable_readings(&serials, &port, -20.0, 14));
        }

        let results = analyze_sfp_health(&readings);
        assert_eq!(results.len(), 3);
        for r in &results {
            assert_eq!(r.severity, SfpSeverity::Healthy, "port {} should be Healthy", r.port);
            assert!(!r.is_outlier_vs_siblings, "port {} should not be outlier", r.port);
            assert!(r.estimated_weeks_to_failure.is_none(), "stable port should have no ETA");
        }
    }

    #[test]
    fn test_sfp_single_port_degrading() {
        let mut readings = Vec::new();
        let serials = onts("D", 10);

        // Port 0 and 1 stable
        readings.extend(generate_stable_readings(&serials, "OLT02/0/0/0", -20.0, 21));
        readings.extend(generate_stable_readings(&serials, "OLT02/0/1/0", -20.0, 21));

        // Port 2 degrading at -0.08 dBm/week = -0.08/7 dBm/day
        let slope_per_day = -0.08 / 7.0;
        readings.extend(generate_degrading_readings(
            &serials, "OLT02/0/2/0", -20.0, slope_per_day, 21,
        ));

        let results = analyze_sfp_health(&readings);
        let degrading = results.iter().find(|r| r.port == "OLT02/0/2/0").unwrap();
        assert!(
            degrading.severity == SfpSeverity::Warning || degrading.severity == SfpSeverity::Critical,
            "degrading port should be Warning or Critical, got {:?}", degrading.severity
        );
        assert!(degrading.rx_trend_per_week < SLOPE_WATCH_LIMIT, "trend should be steep");
    }

    #[test]
    fn test_sfp_outlier_detection() {
        let mut readings = Vec::new();
        let serials = onts("O", 8);

        // 3 sibling ports: two stable, one degrading 3x faster
        readings.extend(generate_stable_readings(&serials, "OLT03/0/0/0", -20.0, 21));
        readings.extend(generate_stable_readings(&serials, "OLT03/0/1/0", -20.0, 21));

        // Port 2: -0.15 dBm/week = fast degradation
        let slope_per_day = -0.15 / 7.0;
        readings.extend(generate_degrading_readings(
            &serials, "OLT03/0/2/0", -20.0, slope_per_day, 21,
        ));

        let results = analyze_sfp_health(&readings);
        let outlier = results.iter().find(|r| r.port == "OLT03/0/2/0").unwrap();
        assert!(
            outlier.is_outlier_vs_siblings,
            "port degrading 3x faster than siblings should be flagged as outlier"
        );

        // Stable ports should NOT be outliers
        for r in results.iter().filter(|r| r.port != "OLT03/0/2/0") {
            assert!(!r.is_outlier_vs_siblings, "stable port {} should not be outlier", r.port);
        }
    }

    #[test]
    fn test_sfp_all_ports_degrading() {
        let mut readings = Vec::new();
        let serials = onts("A", 8);

        // All 3 ports degrade equally — environmental, NOT SFP
        let slope_per_day = -0.06 / 7.0;
        for port_idx in 0..3 {
            let port = format!("OLT04/0/{}/0", port_idx);
            readings.extend(generate_degrading_readings(
                &serials, &port, -20.0, slope_per_day, 21,
            ));
        }

        let results = analyze_sfp_health(&readings);
        assert_eq!(results.len(), 3);
        for r in &results {
            assert!(
                !r.is_outlier_vs_siblings,
                "when all ports degrade equally, none should be outlier (port {})", r.port
            );
        }
    }

    #[test]
    fn test_sfp_critical_low_power() {
        let mut readings = Vec::new();
        let serials = onts("L", 6);

        // Port with very low Rx power — should be Critical regardless of trend
        readings.extend(generate_stable_readings(&serials, "OLT05/0/0/0", -27.0, 14));
        // Sibling port at normal level for comparison
        readings.extend(generate_stable_readings(&serials, "OLT05/0/1/0", -20.0, 14));

        let results = analyze_sfp_health(&readings);
        let low_power = results.iter().find(|r| r.port == "OLT05/0/0/0").unwrap();
        assert_eq!(
            low_power.severity,
            SfpSeverity::Critical,
            "port avg below -26 dBm should be Critical regardless of trend"
        );
    }

    #[test]
    fn test_sfp_weeks_to_failure() {
        let mut readings = Vec::new();
        let serials = onts("W", 8);

        // Port degrading at -0.1 dBm/week from -22 dBm
        // Failure at -28 dBm → 6 dBm remaining → ~60 weeks
        let slope_per_day = -0.1 / 7.0;
        readings.extend(generate_degrading_readings(
            &serials, "OLT06/0/0/0", -22.0, slope_per_day, 21,
        ));
        // Sibling for comparison
        readings.extend(generate_stable_readings(&serials, "OLT06/0/1/0", -20.0, 21));

        let results = analyze_sfp_health(&readings);
        let degrading = results.iter().find(|r| r.port == "OLT06/0/0/0").unwrap();

        assert!(
            degrading.estimated_weeks_to_failure.is_some(),
            "degrading port should have estimated weeks to failure"
        );
        let weeks = degrading.estimated_weeks_to_failure.unwrap();
        // avg_rx is around -23 dBm (midpoint of 21-day degradation from -22),
        // failure at -28 → ~5 dBm remaining at ~0.1 dBm/week → ~50 weeks
        assert!(
            weeks > 10.0 && weeks < 200.0,
            "estimated weeks to failure should be reasonable, got {}", weeks
        );

        // Stable port should have no ETA
        let stable = results.iter().find(|r| r.port == "OLT06/0/1/0").unwrap();
        assert!(
            stable.estimated_weeks_to_failure.is_none(),
            "stable port should not have estimated weeks to failure"
        );
    }
}
