// SPDX-License-Identifier: Apache-2.0
// Pre-FEC Degradation Trending
//
// FEC corrected-codeword counters are the earliest optical degradation
// signal available on a PON: the decoder repairs errors long before rx
// power visibly moves or customers notice anything. Trending the
// CORRECTED rate therefore sees impairments weeks before an rx-power
// alarm, and the SHAPE of the rx trend alongside it separates two root
// causes rx power alone cannot:
//
//   THE KILLER DIAGNOSTIC (per-ONT, over the same window):
//     rising corrected-FEC + STABLE rx (|fitted rx change| below the
//       DDM resolution floor)      => DispersionOrReflection — a timing
//       or reflective impairment (chromatic dispersion, a reflective
//       connector, MPI) degrades the eye WITHOUT attenuating average
//       power, so the rx meter is blind to it. Only FEC sees it.
//     rising corrected-FEC + FALLING rx => Attenuation — consistent
//       with plain optical-budget loss (bending, splice creep, dirty
//       connector); the errors are explained by the power drop.
//     any UNCORRECTED-FEC delta > 0   => ErrorFloorBreached — the
//       decoder is already losing codewords, so the customer is already
//       experiencing errored frames. P1-adjacent regardless of trend.
//
// Counter handling: FEC counters are CUMULATIVE. Per ONT we pair
// consecutive readings that HAVE a counter value and take the delta:
//   - delta < 0  => counter reset (ONT reboot / rollover); the interval
//     is skipped, never clamped to zero or treated as negative errors.
//   - Missing (None) values are GAPS, not zeros: the next present value
//     still pairs with the last present value, so the delta correctly
//     spans the gap (the counter kept counting through it).
//
// Coverage honesty: ONTs with no FEC data at all are ABSENT from the
// findings — absence means "not assessed", never "healthy". The report
// carries `onts_with_fec_data` / `total_onts` and a coverage note so a
// report can say "FEC analysis covered N of M ONTs".

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use super::{OntReading, OntReadingStatus};

/// Module-level FEC health report: findings plus coverage honesty counters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FecHealthReport {
    /// ONTs for which at least one FEC counter value was seen.
    pub onts_with_fec_data: usize,
    /// Total unique ONTs in the input readings.
    pub total_onts: usize,
    /// Human note: "FEC analysis covered N of M ONTs ..." — ONTs without
    /// FEC data are not assessed, not healthy.
    pub coverage_note: String,
    pub findings: Vec<FecFinding>,
}

/// A per-ONT FEC degradation finding.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FecFinding {
    pub serial_number: String,
    pub pon_port: String,
    pub window_start: DateTime<Utc>,
    pub window_end: DateTime<Utc>,
    /// Mean corrected-codeword rate over the window (errors/hour).
    pub corrected_rate_per_hour: f64,
    /// Corrected codewords per downstream gigabyte, when in_octets deltas
    /// were available over the same window (traffic-normalized rate).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub corrected_per_gbyte: Option<f64>,
    /// Which normalization was possible: "time" (per-hour only) or
    /// "time+traffic" (per-hour and per-gigabyte).
    pub normalization: String,
    /// Total uncorrectable codewords accumulated across valid intervals.
    pub uncorrected_total: u64,
    /// Fitted rx trend over the window (dBm/day). None when there were too
    /// few plausible rx samples to quote a trend honestly.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rx_trend_dbm_per_day: Option<f64>,
    pub hypothesis: FecHypothesis,
    pub confidence: FecConfidence,
    /// Human-readable summary naming the evidence behind the hypothesis.
    pub summary: String,
}

/// Root-cause hypothesis from the corrected-FEC trend x rx-trend matrix.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum FecHypothesis {
    /// Rising corrected-FEC with rx power stable (or rising) — a timing or
    /// reflective impairment that average rx power cannot see.
    DispersionOrReflection,
    /// Rising corrected-FEC with falling rx power — consistent with plain
    /// optical-budget loss.
    Attenuation,
    /// Uncorrectable codewords observed — the customer is already
    /// experiencing errored frames.
    ErrorFloorBreached,
    /// Rising corrected-FEC but not enough rx samples to compute an rx
    /// trend: the dispersion-vs-attenuation split cannot be made honestly.
    RisingFecRxUnknown,
}

impl std::fmt::Display for FecHypothesis {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::DispersionOrReflection => write!(f, "Dispersion/Reflection"),
            Self::Attenuation => write!(f, "Attenuation"),
            Self::ErrorFloorBreached => write!(f, "Error Floor Breached"),
            Self::RisingFecRxUnknown => write!(f, "Rising FEC (rx trend unknown)"),
        }
    }
}

/// Confidence in a finding, from data volume and fit quality.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum FecConfidence {
    Low,
    Medium,
    High,
}

// ---------------------------------------------------------------------------
// Gating constants (resolution math)
// ---------------------------------------------------------------------------

/// Minimum valid counter intervals before a trend may be quoted. Matches the
/// honest-gating floor used across detection modules: fewer than 20 points
/// gives a Theil-Sen slope whose sign flips on a single noisy interval.
const MIN_INTERVALS: usize = 20;

/// Minimum elapsed window (days) before a trend may be quoted. Corrected-FEC
/// rates swing diurnally with temperature (laser wavelength drift); a trend
/// fitted inside one thermal cycle mostly measures the weather.
const MIN_SPAN_DAYS: f64 = 3.0;

/// Corrected-rate floor (codewords/hour): the fitted end-of-window rate must
/// exceed this before a rising trend is reported. Why 100/h: a GPON
/// downstream processes ~10^8 FEC codewords per second, so 100 corrections
/// per hour is a corrected-codeword ratio of ~3e-10 — comfortably above the
/// sporadic single-codeword corrections every healthy link logs (a handful
/// per day, from isolated noise hits), yet ~5 orders of magnitude below the
/// pre-FEC BER alarm region, i.e. still weeks-early detection.
const CORRECTED_RATE_FLOOR_PER_HOUR: f64 = 100.0;

/// Minimum fraction of positive pairwise slopes (Mann-Kendall-style
/// monotonicity) for the corrected-rate series to count as "rising".
/// 0.65 approximates MK significance at alpha=0.05 for n=20 intervals.
const MIN_RISE_FRACTION: f64 = 0.65;

/// Minimum plausible rx samples before an rx trend is quoted at all.
const MIN_RX_SAMPLES: usize = 8;

/// Rx resolution floor: fitted TOTAL rx change across the window must exceed
/// 3x the ~0.1 dB SFF-8472 DDM quantization step to count as a real move
/// (same resolution math as sfp_health). Below this the rx trend is quoted
/// as observed but classified STABLE.
const RX_MIN_TOTAL_CHANGE_DB: f64 = 0.3;

// Confidence tiers (data volume + fit quality):
/// High: >= 40 intervals with >= 80% monotone-rising pairs.
const HIGH_CONF_INTERVALS: usize = 40;
const HIGH_CONF_RISE_FRACTION: f64 = 0.80;
/// Medium: >= 25 intervals with >= 70% monotone-rising pairs.
const MED_CONF_INTERVALS: usize = 25;
const MED_CONF_RISE_FRACTION: f64 = 0.70;

/// ErrorFloorBreached confidence: uncorrected codewords in >= 2 distinct
/// intervals (persistent, not a one-off read glitch) rates High.
const ERROR_FLOOR_HIGH_CONF_INTERVALS: usize = 2;

/// A per-interval counter delta with its time span.
#[derive(Debug, Clone, Copy)]
pub(crate) struct CounterDelta {
    /// Interval midpoint (seconds since epoch) — regression x-axis.
    pub mid_ts: f64,
    /// Counter increase over the interval.
    pub delta: u64,
    /// Interval duration in hours.
    pub hours: f64,
}

/// Compute reset-aware deltas for a cumulative counter over a time-sorted
/// series of readings. `get` extracts the counter; None values are gaps
/// (the next present value pairs with the last present value), and a
/// decrease means a counter reset — that interval is skipped entirely.
pub(crate) fn counter_deltas(
    sorted: &[&OntReading],
    get: impl Fn(&OntReading) -> Option<u64>,
) -> Vec<CounterDelta> {
    let mut deltas = Vec::new();
    let mut prev: Option<(DateTime<Utc>, u64)> = None;
    for r in sorted {
        let Some(v) = get(r) else { continue }; // gap, not zero
        if let Some((prev_ts, prev_v)) = prev {
            let secs = (r.timestamp - prev_ts).num_seconds();
            if secs > 0 {
                if v >= prev_v {
                    deltas.push(CounterDelta {
                        mid_ts: (prev_ts.timestamp() as f64 + r.timestamp.timestamp() as f64)
                            / 2.0,
                        delta: v - prev_v,
                        hours: secs as f64 / 3600.0,
                    });
                }
                // v < prev_v => counter reset: skip the interval (the true
                // increase across a reset is unknowable).
            }
        }
        prev = Some((r.timestamp, v));
    }
    deltas
}

/// Theil-Sen robust slope (median of pairwise slopes) plus the fraction of
/// positive pairwise slopes (monotonicity measure). Returns None with fewer
/// than 2 points.
fn theil_sen(points: &[(f64, f64)]) -> Option<(f64, f64)> {
    let mut slopes = Vec::new();
    let mut positive = 0usize;
    for i in 0..points.len() {
        for j in (i + 1)..points.len() {
            let dx = points[j].0 - points[i].0;
            if dx.abs() < 1e-9 {
                continue;
            }
            let s = (points[j].1 - points[i].1) / dx;
            if s > 0.0 {
                positive += 1;
            }
            slopes.push(s);
        }
    }
    if slopes.is_empty() {
        return None;
    }
    slopes.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let median = slopes[slopes.len() / 2];
    let rise_fraction = positive as f64 / slopes.len() as f64;
    Some((median, rise_fraction))
}

/// Simple linear regression slope (per x-unit). None with < 2 points.
fn regression_slope(points: &[(f64, f64)]) -> Option<f64> {
    let n = points.len() as f64;
    if points.len() < 2 {
        return None;
    }
    let sum_x: f64 = points.iter().map(|(x, _)| x).sum();
    let sum_y: f64 = points.iter().map(|(_, y)| y).sum();
    let sum_xy: f64 = points.iter().map(|(x, y)| x * y).sum();
    let sum_xx: f64 = points.iter().map(|(x, _)| x * x).sum();
    let denom = n * sum_xx - sum_x * sum_x;
    if denom.abs() < 1e-12 {
        return None;
    }
    Some((n * sum_xy - sum_x * sum_y) / denom)
}

/// Rx trend over the window: (slope dBm/day, fitted total change dB).
/// None unless MIN_RX_SAMPLES plausible online samples span MIN_SPAN_DAYS.
fn rx_trend(sorted: &[&OntReading]) -> Option<(f64, f64)> {
    let points: Vec<(f64, f64)> = sorted
        .iter()
        .filter(|r| r.status == OntReadingStatus::Online)
        .filter_map(|r| super::sane_rx(r).map(|rx| (r.timestamp.timestamp() as f64 / 86400.0, rx)))
        .collect();
    if points.len() < MIN_RX_SAMPLES {
        return None;
    }
    let span_days = points.last().unwrap().0 - points[0].0;
    if span_days < MIN_SPAN_DAYS {
        return None;
    }
    let slope_per_day = regression_slope(&points)?;
    Some((slope_per_day, slope_per_day * span_days))
}

/// Analyze pre-FEC degradation trends across all ONTs in the readings.
pub fn analyze_fec_health(readings: &[OntReading]) -> FecHealthReport {
    let mut by_serial: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial.entry(&r.serial_number).or_default().push(r);
    }
    let total_onts = by_serial.len();

    let mut onts_with_fec_data = 0usize;
    let mut findings: Vec<FecFinding> = Vec::new();

    for (serial, mut sorted) in by_serial {
        sorted.sort_by_key(|r| r.timestamp);

        let has_fec = sorted
            .iter()
            .any(|r| r.fec_corrected.is_some() || r.fec_uncorrected.is_some());
        if !has_fec {
            // No FEC data => not assessed. Absent from findings, counted
            // in the coverage note — never reported as "healthy".
            continue;
        }
        onts_with_fec_data += 1;

        let corrected = counter_deltas(&sorted, |r| r.fec_corrected);
        let uncorrected = counter_deltas(&sorted, |r| r.fec_uncorrected);

        let window_start = sorted.first().unwrap().timestamp;
        let window_end = sorted.last().unwrap().timestamp;
        let pon_port = sorted.last().unwrap().pon_port.clone();

        let total_hours: f64 = corrected.iter().map(|d| d.hours).sum();
        let total_corrected: u64 = corrected.iter().map(|d| d.delta).sum();
        let corrected_rate_per_hour = if total_hours > 0.0 {
            total_corrected as f64 / total_hours
        } else {
            0.0
        };

        // Traffic normalization where octet deltas exist over the window.
        let octet_deltas = counter_deltas(&sorted, |r| r.in_octets);
        let total_octets: u64 = octet_deltas.iter().map(|d| d.delta).sum();
        let (corrected_per_gbyte, normalization) = if total_octets > 0 {
            (
                Some(total_corrected as f64 / (total_octets as f64 / 1e9)),
                "time+traffic".to_string(),
            )
        } else {
            (None, "time".to_string())
        };

        let uncorrected_total: u64 = uncorrected.iter().map(|d| d.delta).sum();
        let uncorrected_intervals = uncorrected.iter().filter(|d| d.delta > 0).count();

        let rx = rx_trend(&sorted);
        let rx_trend_dbm_per_day = rx.map(|(slope, _)| slope);

        // --- ErrorFloorBreached: uncorrectable codewords are user-visible
        // errors NOW; no trend gate applies (the delta computation itself
        // already required two valid counter samples).
        if uncorrected_total > 0 {
            let confidence = if uncorrected_intervals >= ERROR_FLOOR_HIGH_CONF_INTERVALS {
                FecConfidence::High
            } else {
                FecConfidence::Medium
            };
            findings.push(FecFinding {
                serial_number: serial.to_string(),
                pon_port: pon_port.clone(),
                window_start,
                window_end,
                corrected_rate_per_hour,
                corrected_per_gbyte,
                normalization: normalization.clone(),
                uncorrected_total,
                rx_trend_dbm_per_day,
                hypothesis: FecHypothesis::ErrorFloorBreached,
                confidence,
                summary: format!(
                    "{}: {} UNCORRECTABLE FEC codewords across {} interval(s) — the \
                     decoder is already losing data, customer is experiencing errored \
                     frames now (corrected rate {:.0}/h alongside)",
                    serial, uncorrected_total, uncorrected_intervals, corrected_rate_per_hour
                ),
            });
            continue; // error floor supersedes the trend hypothesis
        }

        // --- Corrected-FEC trend gates: >= 20 intervals over >= 3 days,
        // monotone-rising by Theil-Sen, and the fitted end rate must clear
        // the noise floor (sporadic single-codeword corrections are normal).
        if corrected.len() < MIN_INTERVALS {
            continue;
        }
        let span_days = (window_end - window_start).num_seconds() as f64 / 86400.0;
        if span_days < MIN_SPAN_DAYS {
            continue;
        }

        let rate_points: Vec<(f64, f64)> = corrected
            .iter()
            .map(|d| (d.mid_ts / 3600.0, d.delta as f64 / d.hours)) // x in hours
            .collect();
        let Some((slope_per_hour2, rise_fraction)) = theil_sen(&rate_points) else {
            continue;
        };
        if slope_per_hour2 <= 0.0 || rise_fraction < MIN_RISE_FRACTION {
            continue;
        }
        // Fitted end-of-window rate = median rate + slope * (t_end - t_med).
        let mid_x = rate_points[rate_points.len() / 2].0;
        let median_rate = {
            let mut rates: Vec<f64> = rate_points.iter().map(|(_, y)| *y).collect();
            rates.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            rates[rates.len() / 2]
        };
        let end_x = rate_points.last().unwrap().0;
        let fitted_end_rate = median_rate + slope_per_hour2 * (end_x - mid_x);
        if fitted_end_rate < CORRECTED_RATE_FLOOR_PER_HOUR {
            // Below the floor this is indistinguishable from the sporadic
            // corrections every healthy link logs — emit nothing.
            continue;
        }

        // --- The killer diagnostic: split on the rx trend.
        let (hypothesis, rx_desc) = match rx {
            Some((slope, total_change)) => {
                if total_change <= -RX_MIN_TOTAL_CHANGE_DB {
                    (
                        FecHypothesis::Attenuation,
                        format!(
                            "rx FALLING {:.3} dBm/day ({:.2} dB over window, beyond the \
                             {:.1} dB DDM resolution floor) — errors consistent with \
                             optical-budget loss",
                            slope, total_change, RX_MIN_TOTAL_CHANGE_DB
                        ),
                    )
                } else {
                    (
                        FecHypothesis::DispersionOrReflection,
                        format!(
                            "rx STABLE ({:+.2} dB fitted change, within the {:.1} dB DDM \
                             resolution floor) — a timing/reflective impairment rx power \
                             cannot see",
                            total_change, RX_MIN_TOTAL_CHANGE_DB
                        ),
                    )
                }
            }
            None => (
                FecHypothesis::RisingFecRxUnknown,
                format!(
                    "rx trend UNAVAILABLE (fewer than {} plausible rx samples) — cannot \
                     separate dispersion/reflection from attenuation",
                    MIN_RX_SAMPLES
                ),
            ),
        };

        // Confidence from data volume + fit quality; capped at Low when the
        // rx side of the diagnostic is missing.
        let mut confidence =
            if corrected.len() >= HIGH_CONF_INTERVALS && rise_fraction >= HIGH_CONF_RISE_FRACTION {
                FecConfidence::High
            } else if corrected.len() >= MED_CONF_INTERVALS && rise_fraction >= MED_CONF_RISE_FRACTION
            {
                FecConfidence::Medium
            } else {
                FecConfidence::Low
            };
        if hypothesis == FecHypothesis::RisingFecRxUnknown {
            confidence = FecConfidence::Low;
        }

        let traffic_note = match corrected_per_gbyte {
            Some(pg) => format!(", {:.0} corrected/GB downstream", pg),
            None => " (no octet counters — time normalization only)".to_string(),
        };
        findings.push(FecFinding {
            serial_number: serial.to_string(),
            pon_port,
            window_start,
            window_end,
            corrected_rate_per_hour,
            corrected_per_gbyte,
            normalization,
            uncorrected_total: 0,
            rx_trend_dbm_per_day,
            hypothesis: hypothesis.clone(),
            confidence,
            summary: format!(
                "{}: corrected-FEC rate rising ({:.0}% of interval pairs rising, fitted \
                 end rate {:.0}/h over {:.1} days{}); {} => {}",
                serial,
                rise_fraction * 100.0,
                fitted_end_rate,
                span_days,
                traffic_note,
                rx_desc,
                hypothesis
            ),
        });
    }

    // Deterministic ordering: worst first (error floor, then confidence),
    // then serial.
    findings.sort_by(|a, b| {
        let sev = |f: &FecFinding| match f.hypothesis {
            FecHypothesis::ErrorFloorBreached => 0u8,
            _ => 1,
        };
        sev(a)
            .cmp(&sev(b))
            .then(b.confidence.cmp(&a.confidence))
            .then(a.serial_number.cmp(&b.serial_number))
    });

    let coverage_note = format!(
        "FEC analysis covered {} of {} ONTs; ONTs without FEC counters were not \
         assessed (absence of a finding is not evidence of health)",
        onts_with_fec_data, total_onts
    );

    FecHealthReport {
        onts_with_fec_data,
        total_onts,
        coverage_note,
        findings,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn base_reading(serial: &str, ts: DateTime<Utc>) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: "OLT01/0/1/0".into(),
            rx_power_dbm: Some(-21.0),
            tx_power_dbm: Some(2.5),
            status: OntReadingStatus::Online,
            distance_meters: Some(1000),
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
            ..Default::default()
        }
    }

    fn t0() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap()
    }

    /// 6-hourly readings over `days` days with a counter and rx generator.
    fn series(
        serial: &str,
        days: u32,
        fec: impl Fn(usize) -> Option<u64>,
        rx: impl Fn(usize) -> Option<f64>,
    ) -> Vec<OntReading> {
        let mut out = Vec::new();
        for i in 0..(days as usize * 4) {
            let ts = t0() + Duration::hours(6 * i as i64);
            let mut r = base_reading(serial, ts);
            r.fec_corrected = fec(i);
            r.rx_power_dbm = rx(i);
            out.push(r);
        }
        out
    }

    #[test]
    fn test_counter_deltas_resets_and_gaps() {
        // Counter: 100, 150, RESET to 5, 25, None (gap), 65.
        let ts: Vec<DateTime<Utc>> = (0..6).map(|i| t0() + Duration::hours(i)).collect();
        let vals = [Some(100u64), Some(150), Some(5), Some(25), None, Some(65)];
        let readings: Vec<OntReading> = ts
            .iter()
            .zip(vals.iter())
            .map(|(ts, v)| {
                let mut r = base_reading("D1", *ts);
                r.fec_corrected = *v;
                r
            })
            .collect();
        let refs: Vec<&OntReading> = readings.iter().collect();
        let deltas = counter_deltas(&refs, |r| r.fec_corrected);

        // 150-100=50; 5<150 reset skipped; 25-5=20; gap: 65-25=40 over 2h.
        assert_eq!(deltas.len(), 3, "reset interval must be skipped: {:?}", deltas);
        assert_eq!(deltas[0].delta, 50);
        assert_eq!(deltas[1].delta, 20);
        assert_eq!(deltas[2].delta, 40);
        assert!(
            (deltas[2].hours - 2.0).abs() < 1e-9,
            "gap must widen the interval, not read as zero"
        );
    }

    #[test]
    fn test_rising_fec_stable_rx_is_dispersion_not_attenuation() {
        // Corrected rate ramps from ~200/h to ~3500/h over 12 days while rx
        // stays flat at -21.0 dBm.
        let mut counter = 0u64;
        let mut cum = Vec::new();
        for i in 0..48usize {
            counter += (200.0 + 70.0 * i as f64) as u64 * 6; // per-6h increment
            cum.push(counter);
        }
        let readings = series("DISP-1", 12, |i| Some(cum[i]), |_| Some(-21.0));
        let report = analyze_fec_health(&readings);

        assert_eq!(report.findings.len(), 1);
        let f = &report.findings[0];
        assert_eq!(
            f.hypothesis,
            FecHypothesis::DispersionOrReflection,
            "rising FEC + stable rx must be Dispersion/Reflection, got: {}",
            f.summary
        );
        assert_ne!(f.hypothesis, FecHypothesis::Attenuation);
        assert!(f.rx_trend_dbm_per_day.is_some());
        assert!(f.rx_trend_dbm_per_day.unwrap().abs() < 0.03);
        assert_eq!(f.confidence, FecConfidence::High, "47 clean rising intervals");
        assert!(f.summary.contains("rx STABLE"), "summary must name the evidence");
    }

    #[test]
    fn test_rising_fec_falling_rx_is_attenuation() {
        // Same FEC ramp, but rx falls 0.15 dB/day (1.8 dB over the window).
        let mut counter = 0u64;
        let mut cum = Vec::new();
        for i in 0..48usize {
            counter += (200.0 + 70.0 * i as f64) as u64 * 6;
            cum.push(counter);
        }
        let readings = series(
            "ATTN-1",
            12,
            |i| Some(cum[i]),
            |i| Some(-21.0 - 0.15 * (i as f64 / 4.0)),
        );
        let report = analyze_fec_health(&readings);

        assert_eq!(report.findings.len(), 1);
        let f = &report.findings[0];
        assert_eq!(
            f.hypothesis,
            FecHypothesis::Attenuation,
            "rising FEC + falling rx must be Attenuation, got: {}",
            f.summary
        );
        assert!(f.rx_trend_dbm_per_day.unwrap() < -0.1);
        assert!(f.summary.contains("rx FALLING"));
    }

    #[test]
    fn test_uncorrected_deltas_yield_error_floor_breached() {
        let mut readings = series("UNCO-1", 4, |i| Some(i as u64 * 10), |_| Some(-21.0));
        // Uncorrected counter climbs in two intervals.
        for (i, r) in readings.iter_mut().enumerate() {
            r.fec_uncorrected = Some(match i {
                0..=4 => 0,
                5..=9 => 3,
                _ => 8,
            });
        }
        let report = analyze_fec_health(&readings);
        assert_eq!(report.findings.len(), 1);
        let f = &report.findings[0];
        assert_eq!(f.hypothesis, FecHypothesis::ErrorFloorBreached);
        assert_eq!(f.uncorrected_total, 8);
        assert_eq!(f.confidence, FecConfidence::High, "two distinct uncorrected intervals");
        assert!(f.summary.contains("UNCORRECTABLE"));
    }

    #[test]
    fn test_noise_floor_sporadic_corrections_emit_nothing() {
        // A healthy link: 1-2 corrected codewords per 6h interval, even in a
        // technically "rising" pattern — far below the 100/h floor.
        let cum: Vec<u64> = (0..40u64).map(|i| i + i / 8).collect();
        let readings = series("NOISE-1", 10, |i| Some(cum[i]), |_| Some(-21.0));
        let report = analyze_fec_health(&readings);
        assert!(
            report.findings.is_empty(),
            "sporadic single-codeword corrections are normal noise: {:?}",
            report.findings
        );
        assert_eq!(report.onts_with_fec_data, 1, "still counted as covered");
    }

    #[test]
    fn test_high_flat_rate_without_rising_trend_emits_nothing() {
        // Constant 5000/h corrected rate: high but NOT rising — the trend
        // module stays silent (a static error rate is optical_budget's job).
        let cum: Vec<u64> = (0..40u64).map(|i| i * 30_000).collect();
        let readings = series("FLAT-1", 10, |i| Some(cum[i]), |_| Some(-21.0));
        let report = analyze_fec_health(&readings);
        assert!(report.findings.is_empty(), "flat rate must not be a rising trend");
    }

    #[test]
    fn test_too_few_intervals_or_days_gated() {
        // 2 days of data at 6h cadence = 7 intervals: below both gates.
        let mut counter = 0u64;
        let mut cum = Vec::new();
        for i in 0..8usize {
            counter += (500 + 400 * i as u64) * 6;
            cum.push(counter);
        }
        let readings = series("SHORT-1", 2, |i| Some(cum[i]), |_| Some(-21.0));
        let report = analyze_fec_health(&readings);
        assert!(report.findings.is_empty(), "insufficient data must emit nothing");
    }

    #[test]
    fn test_coverage_counts_onts_without_fec_data() {
        let mut readings = series("COV-FEC", 4, |i| Some(i as u64), |_| Some(-21.0));
        // Second ONT with no FEC columns at all.
        for i in 0..16usize {
            readings.push(base_reading("COV-BARE", t0() + Duration::hours(6 * i as i64)));
        }
        let report = analyze_fec_health(&readings);
        assert_eq!(report.total_onts, 2);
        assert_eq!(report.onts_with_fec_data, 1);
        assert!(report.coverage_note.contains("1 of 2"));
        assert!(
            !report
                .findings
                .iter()
                .any(|f| f.serial_number == "COV-BARE"),
            "no FEC data => absent from findings, not 'healthy'"
        );
    }

    #[test]
    fn test_traffic_normalization_noted() {
        let mut counter = 0u64;
        let mut cum = Vec::new();
        for i in 0..40usize {
            counter += (200.0 + 70.0 * i as f64) as u64 * 6;
            cum.push(counter);
        }
        let mut readings = series("OCT-1", 10, |i| Some(cum[i]), |_| Some(-21.0));
        for (i, r) in readings.iter_mut().enumerate() {
            r.in_octets = Some(i as u64 * 50_000_000_000); // 50 GB per interval
        }
        let report = analyze_fec_health(&readings);
        assert_eq!(report.findings.len(), 1);
        let f = &report.findings[0];
        assert_eq!(f.normalization, "time+traffic");
        assert!(f.corrected_per_gbyte.is_some());

        // Without octets the output says so.
        let readings = series("OCT-2", 10, |i| Some(cum[i]), |_| Some(-21.0));
        let report = analyze_fec_health(&readings);
        assert_eq!(report.findings[0].normalization, "time");
        assert!(report.findings[0].corrected_per_gbyte.is_none());
    }
}
