// SPDX-License-Identifier: Apache-2.0
// Laser Health — bias-current drift as a laser end-of-life predictor.
//
// PHYSICS: semiconductor laser diodes age by THRESHOLD-CURRENT INCREASE
// (facet oxidation, dark-line defects, dopant diffusion). The ONT's
// automatic power control (APC) loop compensates: it raises the drive/bias
// current to hold the optical output constant. The observable signature is
// therefore:
//
//     tx power FLAT + bias current CLIMBING  =  laser ageing (APC hiding it)
//     tx power FALLING + bias CLIMBING       =  APC out of headroom, the
//                                               laser is ALREADY failing
//
// A rising bias with flat tx is the canonical end-of-life precursor — the
// same divergence signal used at fleet scale in Meta's transceiver
// fleet-maintenance patent. SFF-8472 DDM exposes tx bias in 2 µA units
// (16-bit, 0..131 mA); typical GPON ONT lasers operate at 10–60 mA.
//
// TEMPERATURE DETRENDING IS MANDATORY: threshold current also rises with
// temperature, so bias tracks the transceiver temperature at roughly
// 0.2–0.5 %/°C at constant output. A warm fortnight looks exactly like
// ageing if you don't remove it. Where paired (bias, temperature) samples
// exist we fit bias ~ temperature (OLS) and trend the RESIDUALS
// (`temperature_detrended: true`). Where temperature is absent we fall back
// to the 24h-bucket-mean detrending used by rx-power trending — that
// cancels the diurnal cycle but NOT multi-day weather swings, so the output
// is marked `temperature_detrended: false` and consumers must weigh it
// accordingly.
//
// SENSOR-RESOLUTION MATH (why the drift floor sits at 1%/month): the DDM
// bias LSB is 2 µA = 0.003–0.02% of a 10–60 mA operating point, so
// quantization is NOT the binding constraint. The binding constraint is APC
// loop dither plus imperfect temperature compensation, empirically
// ~0.1–0.5% of the operating point even after detrending. Applying the same
// 3x rule the rx-power trending module uses (smallest credible change = 3x
// the noise floor): 3 x 0.15% ≈ 0.45% smallest credible total drift across
// a window. Over the 14-day minimum window that is a rate of
// 0.45% / 14 d x 30.44 d/month ≈ 1%/month — hence MIN_DRIFT_PCT_PER_MONTH.
// Slopes below that are unreadable and NOTHING is emitted for them.
//
// GATES (same spirit as predictions/mod.rs — all must pass or nothing is
// emitted):
//   - >= 14 days between first and last bias sample (laser ageing is a
//     months-scale process; sub-2-week windows are dominated by thermal
//     transients, and 14 days covers two full weekly usage/heating cycles)
//   - >= 30 raw bias samples, aggregated into >= 5 daily means
//   - R² of the residual daily-mean fit >= 0.6 (the drift is actually a line)
//   - drift > 1%/month of the ONT's own median bias (math above)
//
// END-OF-LIFE HEURISTIC: ETA is quoted to bias reaching +50% over the
// observed window median. Telcordia GR-468-style laser qualification
// commonly treats a 20–50% bias increase at constant power as end-of-life;
// we take the +50% edge because the window median is not true
// beginning-of-life. This is an explicitly documented HEURISTIC, not a
// vendor spec — the message says so, and the ETA is a 95%-confidence RANGE
// from the slope standard error, never a point promise.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::detection::OntReading;
use crate::vendors::snmp_helper::{plausible_bias_ma, plausible_dbm, plausible_temp_c};

use super::stats::{linear_fit, median_mad};

/// Minimum elapsed days between first and last bias sample.
pub const MIN_WINDOW_DAYS: f64 = 14.0;

/// Minimum raw bias sample count before fitting a drift.
pub const MIN_SAMPLES: usize = 30;

/// Minimum number of daily-mean buckets for the regression.
const MIN_DAILY_BUCKETS: usize = 5;

/// Minimum R² of the residual daily-mean fit for a drift to be quoted.
const MIN_R_SQUARED: f64 = 0.6;

/// Drift floor: fitted drift must exceed 1% of the ONT's own median bias
/// per month (derivation in the module header). Below this, APC dither and
/// temperature-compensation residuals make the slope unreadable.
pub const MIN_DRIFT_PCT_PER_MONTH: f64 = 1.0;

/// End-of-life heuristic: bias at +50% over the window-median baseline
/// (GR-468-style 20–50% EOL criterion, conservative edge). HEURISTIC.
const EOL_BIAS_RISE_FRACTION: f64 = 0.5;

/// tx power is "flat" when the fitted total change across the window is
/// within 3x the 0.1 dB DDM quantization step (same floor as rx trending).
const TX_FLAT_TOLERANCE_DB: f64 = 0.3;

/// Minimum tx samples / window before the tx cross-check is quoted at all.
const MIN_TX_SAMPLES: usize = 20;
const MIN_TX_WINDOW_DAYS: f64 = 7.0;

/// Mean Gregorian month length in days (for %/month rate conversion).
const DAYS_PER_MONTH: f64 = 30.44;

/// What the bias/tx divergence says about the failure mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LaserHealthUrgency {
    /// Bias rising, tx power flat: APC is compensating for threshold drift.
    /// The classic ageing signature — plan a replacement.
    ClassicAgeing,
    /// Bias rising AND tx power falling: APC has run out of headroom, the
    /// laser is already failing. Urgent replacement.
    ActivelyFailing,
    /// Bias rising but tx power data is missing/insufficient to classify
    /// the failure mode.
    BiasRiseOnly,
}

impl std::fmt::Display for LaserHealthUrgency {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ClassicAgeing => write!(f, "classic_ageing"),
            Self::ActivelyFailing => write!(f, "actively_failing"),
            Self::BiasRiseOnly => write!(f, "bias_rise_only"),
        }
    }
}

/// A laser-ageing prediction that passed every statistical gate.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LaserHealthPrediction {
    pub serial_number: String,
    pub pon_port: String,
    /// Median bias current across the window (mA) — the ONT's own baseline.
    pub median_bias_ma: f64,
    /// Fitted drift as % of median bias per month (> MIN_DRIFT_PCT_PER_MONTH
    /// by construction).
    pub drift_pct_per_month: f64,
    /// 95% confidence interval on the drift (%/month), from the slope
    /// standard error.
    pub drift_ci95_pct_per_month: (f64, f64),
    /// True when the drift was fitted on bias~temperature residuals; false
    /// when only 24h-bucket-mean detrending was possible (multi-day weather
    /// swings NOT removed — weigh accordingly).
    pub temperature_detrended: bool,
    /// Some(true) = tx flat (|fitted change| <= 0.3 dB): classic ageing.
    /// Some(false) = tx NOT flat. None = insufficient tx data.
    pub tx_power_stable: Option<bool>,
    /// Failure-mode classification from the bias/tx divergence.
    pub urgency: LaserHealthUrgency,
    /// Earliest days until bias reaches the +50%-over-baseline end-of-life
    /// heuristic (fast edge of the 95% slope band).
    pub eta_days_to_eol_earliest: u32,
    /// Latest days (slow edge); None when the slow edge of the band is
    /// non-rising (open-ended).
    pub eta_days_to_eol_latest: Option<u32>,
    /// R² of the residual daily-mean fit (>= 0.6 — lower fits are
    /// suppressed, so this never launders a bad fit into a prediction).
    pub confidence: f32,
    /// Human-readable summary for the ISP.
    pub message: String,
}

/// Coverage counters: how many ONTs could even be assessed. Absence of
/// bias data must be visible, never silently read as "healthy".
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LaserHealthCoverage {
    /// Distinct ONT serials seen in the readings.
    pub onts_total: usize,
    /// ONTs with at least one plausible bias-current sample.
    pub onts_with_bias: usize,
    /// ONTs with bias data that passed the data-sufficiency gates
    /// (samples/window/buckets) and were actually trend-analyzed.
    pub onts_analyzed: usize,
    /// ONTs with bias data that failed a data-sufficiency gate (too few
    /// samples, window too short, too few daily buckets). NOT "healthy" —
    /// "not assessable yet".
    pub onts_gated_out: usize,
    /// Of the analyzed ONTs, how many were temperature-detrended (vs the
    /// weaker 24h-bucket fallback).
    pub onts_temperature_detrended: usize,
    /// Analyzed ONTs that produced a prediction.
    pub onts_flagged: usize,
}

/// Full laser-health analysis output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LaserHealthReport {
    pub predictions: Vec<LaserHealthPrediction>,
    pub coverage: LaserHealthCoverage,
}

/// One sanitized per-ONT sample.
struct Sample {
    ts: i64,
    bias_ma: f64,
    temp_c: Option<f64>,
    tx_dbm: Option<f64>,
}

/// Analyze laser health across all ONTs found in the readings.
///
/// Groups readings by serial, sanitizes DDM values (vendor sentinels and
/// implausible values dropped; bias of exactly 0 mA = laser not transmitting,
/// which is an offline datapoint, not an ageing one), applies every gate in
/// the module header, and emits one prediction per ONT whose bias drift
/// clears them all. ONTs with no bias data are ABSENT from predictions and
/// visible only in the coverage counters.
pub fn analyze_laser_health(readings: &[OntReading]) -> LaserHealthReport {
    // Group by serial; remember the latest pon_port per serial.
    let mut by_serial: BTreeMap<&str, (Vec<Sample>, &str, i64)> = BTreeMap::new();
    for r in readings {
        let ts = r.timestamp.timestamp();
        let entry = by_serial
            .entry(r.serial_number.as_str())
            .or_insert_with(|| (Vec::new(), r.pon_port.as_str(), i64::MIN));
        if ts >= entry.2 {
            entry.1 = r.pon_port.as_str();
            entry.2 = ts;
        }
        if let Some(bias) = r.bias_current_ma.and_then(plausible_bias_ma) {
            if bias > 0.0 {
                entry.0.push(Sample {
                    ts,
                    bias_ma: bias,
                    temp_c: r.temperature_c.and_then(plausible_temp_c),
                    tx_dbm: r.tx_power_dbm.and_then(plausible_dbm),
                });
            }
        }
    }

    let mut coverage = LaserHealthCoverage {
        onts_total: by_serial.len(),
        ..Default::default()
    };
    let mut predictions = Vec::new();

    for (serial, (mut samples, pon_port, _)) in by_serial {
        if samples.is_empty() {
            continue; // no bias data: absent, counted only in onts_total
        }
        coverage.onts_with_bias += 1;
        samples.sort_by_key(|s| s.ts);

        match analyze_ont(serial, pon_port, &samples) {
            OntOutcome::GatedOut => coverage.onts_gated_out += 1,
            OntOutcome::NoDrift { temperature_detrended } => {
                coverage.onts_analyzed += 1;
                if temperature_detrended {
                    coverage.onts_temperature_detrended += 1;
                }
            }
            OntOutcome::Flagged(pred) => {
                coverage.onts_analyzed += 1;
                if pred.temperature_detrended {
                    coverage.onts_temperature_detrended += 1;
                }
                coverage.onts_flagged += 1;
                predictions.push(pred);
            }
        }
    }

    // Most urgent / fastest drift first.
    predictions.sort_by(|a, b| {
        let ua = a.urgency == LaserHealthUrgency::ActivelyFailing;
        let ub = b.urgency == LaserHealthUrgency::ActivelyFailing;
        ub.cmp(&ua).then(
            b.drift_pct_per_month
                .partial_cmp(&a.drift_pct_per_month)
                .unwrap_or(std::cmp::Ordering::Equal),
        )
    });

    LaserHealthReport {
        predictions,
        coverage,
    }
}

enum OntOutcome {
    /// Failed a data-sufficiency gate — not assessable, NOT "healthy".
    GatedOut,
    /// Analyzed; no defensible rising drift (stable, falling, below the
    /// floor, or fit not line-like).
    NoDrift { temperature_detrended: bool },
    Flagged(LaserHealthPrediction),
}

fn analyze_ont(serial: &str, pon_port: &str, samples: &[Sample]) -> OntOutcome {
    // --- Data-sufficiency gates -----------------------------------------
    if samples.len() < MIN_SAMPLES {
        return OntOutcome::GatedOut;
    }
    let first_ts = samples.first().map(|s| s.ts).unwrap_or(0);
    let last_ts = samples.last().map(|s| s.ts).unwrap_or(0);
    let window_days = (last_ts - first_ts) as f64 / 86400.0;
    if window_days < MIN_WINDOW_DAYS {
        return OntOutcome::GatedOut;
    }

    let bias_values: Vec<f64> = samples.iter().map(|s| s.bias_ma).collect();
    let Some((median_bias, _)) = median_mad(&bias_values) else {
        return OntOutcome::GatedOut;
    };
    if median_bias <= 0.0 {
        return OntOutcome::GatedOut;
    }

    // --- Temperature detrending (mandatory where possible) --------------
    // Paired (bias, temp) samples must themselves satisfy the sample and
    // window gates, otherwise the temp fit would be extrapolation.
    let paired: Vec<&Sample> = samples.iter().filter(|s| s.temp_c.is_some()).collect();
    let paired_window_days = match (paired.first(), paired.last()) {
        (Some(f), Some(l)) => (l.ts - f.ts) as f64 / 86400.0,
        _ => 0.0,
    };
    let use_temp = paired.len() >= MIN_SAMPLES && paired_window_days >= MIN_WINDOW_DAYS;

    // Residual series (ts, residual bias in mA) to trend over time.
    let residuals: Vec<(i64, f64)> = if use_temp {
        let temp_points: Vec<(f64, f64)> = paired
            .iter()
            .map(|s| (s.temp_c.unwrap(), s.bias_ma))
            .collect();
        match linear_fit(&temp_points) {
            Some(fit) => paired
                .iter()
                .map(|s| (s.ts, s.bias_ma - (fit.slope * s.temp_c.unwrap() + fit.intercept)))
                .collect(),
            // Degenerate temperature (constant): nothing to remove — the raw
            // series IS the constant-temperature series.
            None => paired.iter().map(|s| (s.ts, s.bias_ma)).collect(),
        }
    } else {
        samples.iter().map(|s| (s.ts, s.bias_ma)).collect()
    };

    // --- 24h-bucket daily means (cancels diurnal cycle + APC dither) ----
    let daily = daily_means(&residuals);
    if daily.len() < MIN_DAILY_BUCKETS {
        return OntOutcome::GatedOut;
    }

    let no_drift = OntOutcome::NoDrift {
        temperature_detrended: use_temp,
    };

    // --- Residual trend fit + statistical gates --------------------------
    let Some(fit) = linear_fit(&daily) else {
        return no_drift;
    };
    // Only RISING bias is an ageing signal.
    if fit.slope <= 0.0 {
        return no_drift;
    }
    let to_pct_per_month = DAYS_PER_MONTH / median_bias * 100.0;
    let drift_pct_per_month = fit.slope * to_pct_per_month;
    if drift_pct_per_month < MIN_DRIFT_PCT_PER_MONTH {
        return no_drift; // below the readable floor (module header math)
    }
    if fit.r_squared < MIN_R_SQUARED {
        return no_drift; // the "drift" is not actually a line
    }

    let ci_half = 1.96 * fit.slope_stderr * to_pct_per_month;
    let drift_ci95 = (drift_pct_per_month - ci_half, drift_pct_per_month + ci_half);

    // --- tx power cross-check --------------------------------------------
    let tx_points: Vec<(i64, f64)> = samples
        .iter()
        .filter_map(|s| s.tx_dbm.map(|tx| (s.ts, tx)))
        .collect();
    let tx_assessment = assess_tx_stability(&tx_points);
    let (tx_power_stable, urgency) = match tx_assessment {
        Some(TxAssessment { stable: true, .. }) => {
            (Some(true), LaserHealthUrgency::ClassicAgeing)
        }
        Some(TxAssessment {
            stable: false,
            falling: true,
            ..
        }) => (Some(false), LaserHealthUrgency::ActivelyFailing),
        // tx moving but not falling (e.g. rising after a swap/rework):
        // not the failing signature, but not the clean ageing one either.
        Some(TxAssessment { stable: false, .. }) => {
            (Some(false), LaserHealthUrgency::BiasRiseOnly)
        }
        None => (None, LaserHealthUrgency::BiasRiseOnly),
    };

    // --- ETA range to the +50% end-of-life heuristic ----------------------
    // Current level: last daily mean of the RAW bias (not residuals).
    let raw_series: Vec<(i64, f64)> = samples.iter().map(|s| (s.ts, s.bias_ma)).collect();
    let raw_daily = daily_means(&raw_series);
    let current_bias = raw_daily.last().map(|(_, v)| *v).unwrap_or(median_bias);
    let eol_bias = median_bias * (1.0 + EOL_BIAS_RISE_FRACTION);
    let margin_ma = (eol_bias - current_bias).max(0.0);

    let fast_slope = fit.slope + 1.96 * fit.slope_stderr; // mA/day, > 0
    let slow_slope = fit.slope - 1.96 * fit.slope_stderr;
    let eta_earliest = (margin_ma / fast_slope) as u32;
    let eta_latest = if slow_slope > 1e-12 {
        Some((margin_ma / slow_slope) as u32)
    } else {
        None
    };

    let eta_text = match eta_latest {
        Some(late) => format!("{}–{} days (95% confidence)", eta_earliest, late),
        None => format!(
            "{}+ days (slow edge of confidence band is flat)",
            eta_earliest
        ),
    };
    let detrend_text = if use_temp {
        "temperature-detrended"
    } else {
        "24h-mean detrended only (no temperature data — weigh accordingly)"
    };

    let message = match urgency {
        LaserHealthUrgency::ActivelyFailing => format!(
            "LASER FAILING: ONT {} bias current rising {:.2}%/month (95% CI {:.2}–{:.2}, R²={:.2}, {} samples/{:.0}d, {}) AND tx power falling — APC out of headroom, laser is already failing. Median bias {:.1} mA; +50%-over-baseline EOL heuristic reached in {}. Replace ONT urgently.",
            serial, drift_pct_per_month, drift_ci95.0, drift_ci95.1, fit.r_squared,
            samples.len(), window_days, detrend_text, median_bias, eta_text
        ),
        LaserHealthUrgency::ClassicAgeing => format!(
            "LASER AGEING: ONT {} bias current rising {:.2}%/month (95% CI {:.2}–{:.2}, R²={:.2}, {} samples/{:.0}d, {}) at flat tx power — APC compensating for laser threshold drift, the classic end-of-life precursor. Median bias {:.1} mA; +50%-over-baseline EOL heuristic reached in {}. Plan ONT replacement.",
            serial, drift_pct_per_month, drift_ci95.0, drift_ci95.1, fit.r_squared,
            samples.len(), window_days, detrend_text, median_bias, eta_text
        ),
        LaserHealthUrgency::BiasRiseOnly => format!(
            "LASER WATCH: ONT {} bias current rising {:.2}%/month (95% CI {:.2}–{:.2}, R²={:.2}, {} samples/{:.0}d, {}); tx power trend unavailable/unclassified, so ageing vs failing cannot be distinguished. Median bias {:.1} mA; +50%-over-baseline EOL heuristic reached in {}.",
            serial, drift_pct_per_month, drift_ci95.0, drift_ci95.1, fit.r_squared,
            samples.len(), window_days, detrend_text, median_bias, eta_text
        ),
    };

    OntOutcome::Flagged(LaserHealthPrediction {
        serial_number: serial.to_string(),
        pon_port: pon_port.to_string(),
        median_bias_ma: median_bias,
        drift_pct_per_month,
        drift_ci95_pct_per_month: drift_ci95,
        temperature_detrended: use_temp,
        tx_power_stable,
        urgency,
        eta_days_to_eol_earliest: eta_earliest,
        eta_days_to_eol_latest: eta_latest,
        confidence: fit.r_squared as f32,
        message,
    })
}

struct TxAssessment {
    stable: bool,
    falling: bool,
}

/// Fit the tx-power daily means and classify: flat (|fitted total change|
/// <= 0.3 dB, i.e. within 3x the DDM LSB), falling (fitted drop > 0.3 dB),
/// or otherwise moving. None when there is not enough tx data to say
/// anything (< 20 samples, < 7 days, or < 5 daily buckets).
fn assess_tx_stability(tx_points: &[(i64, f64)]) -> Option<TxAssessment> {
    if tx_points.len() < MIN_TX_SAMPLES {
        return None;
    }
    let first = tx_points.iter().map(|(t, _)| *t).min()?;
    let last = tx_points.iter().map(|(t, _)| *t).max()?;
    let tx_window_days = (last - first) as f64 / 86400.0;
    if tx_window_days < MIN_TX_WINDOW_DAYS {
        return None;
    }
    let daily = daily_means(tx_points);
    if daily.len() < MIN_DAILY_BUCKETS {
        return None;
    }
    let fit = linear_fit(&daily)?;
    let total_change_db = fit.slope * tx_window_days;
    Some(TxAssessment {
        stable: total_change_db.abs() <= TX_FLAT_TOLERANCE_DB,
        falling: total_change_db < -TX_FLAT_TOLERANCE_DB,
    })
}

/// Bucket a (unix_ts, value) series into UTC-day means: (day-number as f64
/// days, mean). The same 24h-mean detrending step rx trending uses — it
/// averages out the diurnal cycle and quantization steps.
fn daily_means(points: &[(i64, f64)]) -> Vec<(f64, f64)> {
    let mut buckets: BTreeMap<i64, (f64, u32)> = BTreeMap::new();
    for (ts, v) in points {
        let day = ts.div_euclid(86400);
        let entry = buckets.entry(day).or_insert((0.0, 0));
        entry.0 += v;
        entry.1 += 1;
    }
    buckets
        .iter()
        .map(|(day, (sum, count))| (*day as f64, sum / *count as f64))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::DateTime;

    const BASE_TS: i64 = 1_770_000_000;

    /// Synthetic bias history for one ONT.
    ///
    /// bias = base * (1 + temp_coeff*(temp - 25)) + drift_ma_per_day*d,
    /// quantized to the 2 µA DDM LSB. Temperature (when present) swings
    /// ±8 °C diurnally around 25 °C. tx = 2.0 + tx_slope_db_per_day*d,
    /// quantized at 0.1 dB.
    fn synth_readings(
        serial: &str,
        days: u32,
        per_day: u32,
        base_bias_ma: f64,
        drift_pct_per_month: f64,
        with_temp: bool,
        tx_slope_db_per_day: f64,
    ) -> Vec<OntReading> {
        let drift_ma_per_day = base_bias_ma * drift_pct_per_month / 100.0 / DAYS_PER_MONTH;
        let mut readings = Vec::new();
        for d in 0..days {
            for s in 0..per_day {
                let ts = BASE_TS + (d as i64) * 86400 + (s as i64) * (86400 / per_day as i64);
                let hour = (s as f64 / per_day as f64) * 24.0;
                let temp = 25.0 + 8.0 * (2.0 * std::f64::consts::PI * hour / 24.0).sin();
                // ~0.4 %/°C temperature coefficient (mid-range of typical).
                let raw_bias = base_bias_ma * (1.0 + 0.004 * (temp - 25.0))
                    + drift_ma_per_day * d as f64;
                let bias = (raw_bias * 500.0).round() / 500.0; // 2 µA LSB
                let tx = ((2.0 + tx_slope_db_per_day * d as f64) * 10.0).round() / 10.0;
                readings.push(OntReading {
                    timestamp: DateTime::from_timestamp(ts, 0).unwrap(),
                    serial_number: serial.into(),
                    pon_port: "0/1".into(),
                    bias_current_ma: Some(bias),
                    temperature_c: with_temp.then_some(temp),
                    tx_power_dbm: Some(tx),
                    ..Default::default()
                });
            }
        }
        readings
    }

    #[test]
    fn test_classic_ageing_detected_with_temperature_detrend() {
        // 3%/month drift, 30 days, temperature present, tx flat.
        let readings = synth_readings("LSR001", 30, 4, 20.0, 3.0, true, 0.0);
        let report = analyze_laser_health(&readings);
        assert_eq!(report.coverage.onts_total, 1);
        assert_eq!(report.coverage.onts_with_bias, 1);
        assert_eq!(report.coverage.onts_analyzed, 1);
        assert_eq!(report.coverage.onts_flagged, 1);
        assert_eq!(report.coverage.onts_temperature_detrended, 1);

        let p = &report.predictions[0];
        assert_eq!(p.serial_number, "LSR001");
        assert!(p.temperature_detrended);
        assert!(
            (p.drift_pct_per_month - 3.0).abs() < 1.0,
            "drift={}",
            p.drift_pct_per_month
        );
        assert!(
            p.drift_ci95_pct_per_month.0 <= p.drift_pct_per_month
                && p.drift_pct_per_month <= p.drift_ci95_pct_per_month.1
        );
        assert!((p.median_bias_ma - 20.0).abs() < 1.0, "median={}", p.median_bias_ma);
        assert_eq!(p.tx_power_stable, Some(true));
        assert_eq!(p.urgency, LaserHealthUrgency::ClassicAgeing);
        assert!(p.confidence >= 0.6);
        assert!(p.message.contains("AGEING"));
        assert!(p.message.contains("heuristic"), "EOL must be labelled heuristic");
    }

    #[test]
    fn test_eta_range_is_sane_and_ordered() {
        // 3%/month of 20 mA = 0.6 mA/month; +50% EOL = ~10 mA of headroom
        // → point estimate roughly 500 days. The 95% range must bracket a
        // physically sane window.
        let readings = synth_readings("LSR002", 30, 4, 20.0, 3.0, true, 0.0);
        let report = analyze_laser_health(&readings);
        let p = &report.predictions[0];
        assert!(
            p.eta_days_to_eol_earliest >= 200 && p.eta_days_to_eol_earliest <= 600,
            "earliest={}",
            p.eta_days_to_eol_earliest
        );
        if let Some(late) = p.eta_days_to_eol_latest {
            assert!(late >= p.eta_days_to_eol_earliest, "range ordered");
            assert!(late <= 2000, "late={late}");
        }
    }

    #[test]
    fn test_fallback_without_temperature_marks_flag() {
        // Same drift but no temperature data: 24h-mean fallback must still
        // find it and mark temperature_detrended = false.
        let readings = synth_readings("LSR003", 30, 4, 20.0, 3.0, false, 0.0);
        let report = analyze_laser_health(&readings);
        assert_eq!(report.coverage.onts_flagged, 1);
        assert_eq!(report.coverage.onts_temperature_detrended, 0);
        let p = &report.predictions[0];
        assert!(!p.temperature_detrended);
        assert!(
            (p.drift_pct_per_month - 3.0).abs() < 1.0,
            "drift={}",
            p.drift_pct_per_month
        );
        assert!(p.message.contains("no temperature data"));
    }

    #[test]
    fn test_temperature_swing_without_drift_not_flagged() {
        // Pure thermal bias movement, zero ageing: must NOT be flagged.
        let readings = synth_readings("LSR004", 30, 4, 20.0, 0.0, true, 0.0);
        let report = analyze_laser_health(&readings);
        assert!(report.predictions.is_empty(), "thermal swing is not ageing");
        assert_eq!(report.coverage.onts_analyzed, 1);
        assert_eq!(report.coverage.onts_flagged, 0);
    }

    #[test]
    fn test_drift_below_floor_not_flagged() {
        // 0.5%/month is below the 1%/month readable floor.
        let readings = synth_readings("LSR005", 30, 4, 20.0, 0.5, true, 0.0);
        let report = analyze_laser_health(&readings);
        assert!(
            report.predictions.is_empty(),
            "sub-floor drift must be suppressed"
        );
        assert_eq!(report.coverage.onts_analyzed, 1);
    }

    #[test]
    fn test_short_window_gated_out() {
        // Strong drift but only 10 days — below the 14-day minimum.
        let readings = synth_readings("LSR006", 10, 4, 20.0, 6.0, true, 0.0);
        let report = analyze_laser_health(&readings);
        assert!(report.predictions.is_empty());
        assert_eq!(report.coverage.onts_gated_out, 1);
        assert_eq!(report.coverage.onts_analyzed, 0);
    }

    #[test]
    fn test_too_few_samples_gated_out() {
        // 15 days but 1 sample/day = 15 < 30 samples.
        let readings = synth_readings("LSR007", 15, 1, 20.0, 6.0, true, 0.0);
        let report = analyze_laser_health(&readings);
        assert!(report.predictions.is_empty());
        assert_eq!(report.coverage.onts_gated_out, 1);
    }

    #[test]
    fn test_bias_rise_with_falling_tx_is_actively_failing() {
        // 4%/month bias rise AND tx dropping 0.05 dB/day (1.5 dB over the
        // window): APC out of headroom → urgent.
        let readings = synth_readings("LSR008", 30, 4, 20.0, 4.0, true, -0.05);
        let report = analyze_laser_health(&readings);
        assert_eq!(report.coverage.onts_flagged, 1);
        let p = &report.predictions[0];
        assert_eq!(p.tx_power_stable, Some(false));
        assert_eq!(p.urgency, LaserHealthUrgency::ActivelyFailing);
        assert!(p.message.contains("FAILING"));
    }

    #[test]
    fn test_no_bias_data_absent_with_coverage() {
        // Readings with rx only: no laser prediction, coverage shows why.
        let readings: Vec<OntReading> = (0..40)
            .map(|i| OntReading {
                timestamp: DateTime::from_timestamp(BASE_TS + i * 21600, 0).unwrap(),
                serial_number: "NOBIAS1".into(),
                pon_port: "0/2".into(),
                rx_power_dbm: Some(-21.0),
                ..Default::default()
            })
            .collect();
        let report = analyze_laser_health(&readings);
        assert!(report.predictions.is_empty());
        assert_eq!(report.coverage.onts_total, 1);
        assert_eq!(report.coverage.onts_with_bias, 0);
        assert_eq!(report.coverage.onts_analyzed, 0);
    }

    #[test]
    fn test_sentinel_bias_values_dropped() {
        // A drift manufactured purely by sentinel values (655.35 mA style)
        // must not survive sanitization.
        let mut readings = synth_readings("LSR009", 30, 4, 20.0, 0.0, true, 0.0);
        for (i, r) in readings.iter_mut().enumerate() {
            if i % 10 == 0 {
                r.bias_current_ma = Some(655.35);
            }
        }
        let report = analyze_laser_health(&readings);
        assert!(report.predictions.is_empty(), "sentinels must be dropped");
    }

    #[test]
    fn test_mixed_fleet_coverage_counts_add_up() {
        let mut readings = synth_readings("FLEET-A", 30, 4, 20.0, 3.0, true, 0.0);
        readings.extend(synth_readings("FLEET-B", 30, 4, 25.0, 0.0, false, 0.0));
        readings.extend(synth_readings("FLEET-C", 5, 4, 15.0, 6.0, true, 0.0)); // short
        readings.push(OntReading {
            timestamp: DateTime::from_timestamp(BASE_TS, 0).unwrap(),
            serial_number: "FLEET-D".into(),
            pon_port: "0/9".into(),
            rx_power_dbm: Some(-20.0),
            ..Default::default()
        }); // no bias at all
        let report = analyze_laser_health(&readings);
        let c = &report.coverage;
        assert_eq!(c.onts_total, 4);
        assert_eq!(c.onts_with_bias, 3);
        assert_eq!(c.onts_analyzed + c.onts_gated_out, c.onts_with_bias);
        assert_eq!(c.onts_gated_out, 1); // FLEET-C
        assert_eq!(c.onts_flagged, 1); // FLEET-A
        assert_eq!(report.predictions[0].serial_number, "FLEET-A");
    }
}
