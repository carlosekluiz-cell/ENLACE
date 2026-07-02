// SPDX-License-Identifier: Apache-2.0
// Honest statistics primitives for the predictive layer.
//
// Shared, dependency-free building blocks used by the prediction modules
// (degradation trending, laser health) so that every module applies the SAME
// defensible statistics instead of re-inventing ad-hoc thresholds.
//
// Design rules (module contract):
//   - Every primitive documents exactly what it DOES and DOES NOT claim.
//   - Robust statistics (median / MAD) are preferred over mean / stddev so a
//     single vendor sentinel or polling glitch cannot poison a baseline.
//   - Nothing here is Bayesian. The changepoint detector is a plain
//     binary-segmentation single-split model comparison; it must never be
//     described as BOCPD or given probabilistic credences it cannot back.
//   - MAD-to-sigma: for Gaussian data, sigma ≈ 1.4826 * MAD. This constant
//     appears wherever a MAD is used as a robust stand-in for a standard
//     deviation; where a value is stated to be "in MAD units" it is the raw
//     MAD without that factor.

use serde::{Deserialize, Serialize};

/// Consistency factor: sigma ≈ 1.4826 * MAD for normally distributed data.
pub const MAD_TO_SIGMA: f64 = 1.4826;

/// Robust baseline: (median, MAD) of `values`.
///
/// MAD = median(|x - median|), the median absolute deviation — a robust
/// scale estimate that a single outlier cannot inflate (breakdown point 50%,
/// vs 0% for the standard deviation).
///
/// Claims: a robust location + scale summary of the sample as given.
/// Does NOT claim: normality, independence, or that MAD*1.4826 equals the
/// true sigma for skewed/multi-modal data. Non-finite inputs are ignored.
/// Returns None when no finite values remain.
pub fn median_mad(values: &[f64]) -> Option<(f64, f64)> {
    let mut v: Vec<f64> = values.iter().copied().filter(|x| x.is_finite()).collect();
    if v.is_empty() {
        return None;
    }
    let med = median_of_sorted(&mut v);
    let mut devs: Vec<f64> = v.iter().map(|x| (x - med).abs()).collect();
    let mad = median_of_sorted(&mut devs);
    Some((med, mad))
}

/// Median of a slice (sorts in place).
fn median_of_sorted(v: &mut [f64]) -> f64 {
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        (v[n / 2 - 1] + v[n / 2]) / 2.0
    }
}

/// Robust z-score: (value - median) / (1.4826 * MAD).
///
/// Claims: how many robust-sigma the value sits from the baseline, IF the
/// baseline noise is roughly Gaussian.
/// Does NOT claim: a p-value. With mad == 0 (constant baseline) any deviation
/// is infinitely surprising relative to observed scatter: returns ±INFINITY
/// for a non-zero deviation and 0.0 for none — callers must gate on sample
/// count before treating that as meaningful.
pub fn robust_z(value: f64, median: f64, mad: f64) -> f64 {
    let dev = value - median;
    let sigma = MAD_TO_SIGMA * mad;
    if sigma <= f64::EPSILON {
        return if dev == 0.0 {
            0.0
        } else if dev > 0.0 {
            f64::INFINITY
        } else {
            f64::NEG_INFINITY
        };
    }
    dev / sigma
}

/// Exponentially weighted moving average with an exponentially weighted
/// variance estimate (incremental form, cf. West 1979).
///
/// Claims: a smoothed level and a smoothed squared-deviation-around-that-
/// level, weighting recent samples by `alpha`.
/// Does NOT claim: an unbiased variance of the underlying process (EW
/// variance under-estimates during level shifts and has no degrees-of-
/// freedom correction), nor any detection decision by itself.
#[derive(Debug, Clone)]
pub struct Ewma {
    alpha: f64,
    mean: f64,
    var: f64,
    count: u64,
}

impl Ewma {
    /// `alpha` in (0, 1]: weight of the newest sample. Clamped to that range.
    pub fn new(alpha: f64) -> Self {
        Self {
            alpha: alpha.clamp(f64::EPSILON, 1.0),
            mean: 0.0,
            var: 0.0,
            count: 0,
        }
    }

    /// Feed one sample; returns the updated mean.
    pub fn update(&mut self, x: f64) -> f64 {
        self.count += 1;
        if self.count == 1 {
            self.mean = x;
            self.var = 0.0;
            return self.mean;
        }
        let diff = x - self.mean;
        let incr = self.alpha * diff;
        self.mean += incr;
        // EW variance: var <- (1 - alpha) * (var + diff * incr)
        self.var = (1.0 - self.alpha) * (self.var + diff * incr);
        self.mean
    }

    /// Smoothed level; None before the first sample.
    pub fn mean(&self) -> Option<f64> {
        (self.count > 0).then_some(self.mean)
    }

    /// EW variance estimate; None before the second sample.
    pub fn variance(&self) -> Option<f64> {
        (self.count > 1).then_some(self.var)
    }

    /// sqrt of `variance()`.
    pub fn std_dev(&self) -> Option<f64> {
        self.variance().map(f64::sqrt)
    }

    pub fn sample_count(&self) -> u64 {
        self.count
    }
}

/// Direction of a CUSUM alarm.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CusumSignal {
    /// Sustained shift ABOVE the baseline median.
    UpShift,
    /// Sustained shift BELOW the baseline median.
    DownShift,
}

/// Two-sided CUSUM detector for sustained small mean shifts.
///
/// Standardizes each sample against a FIXED robust baseline (median, MAD —
/// both in plain MAD units, no 1.4826 factor) and accumulates
///   pos <- max(0, pos + z - k),  neg <- max(0, neg - z - k)
/// alarming when either sum exceeds `h`. With reference value `k`, drifts
/// smaller than k*MAD per sample are absorbed; a sustained shift of s MADs
/// accumulates at (s - k) per sample and alarms after ~h/(s - k) samples —
/// this is how CUSUM catches shifts far too small for any single-point
/// threshold to see.
///
/// Claims: a sustained shift of the level relative to the frozen baseline,
/// with sensitivity/false-alarm trade-off set entirely by (k, h).
/// Does NOT claim: shift onset time (the alarm lags onset), shift size
/// (the sums are not magnitude estimates), or adaptation to a moving
/// baseline — the caller chooses when the baseline was representative.
/// Both sums reset after an alarm.
#[derive(Debug, Clone)]
pub struct Cusum {
    /// Reference value (slack) in MAD units.
    k: f64,
    /// Decision threshold in MAD units.
    h: f64,
    median: f64,
    mad: f64,
    pos: f64,
    neg: f64,
}

impl Cusum {
    /// `k_mads`: per-sample slack; `h_mads`: alarm threshold — both in MAD
    /// units of the provided baseline. A `mad` of 0 (constant baseline) is
    /// clamped to a tiny epsilon, making any deviation alarm quickly; gate on
    /// sample count before trusting a baseline that flat.
    pub fn new(k_mads: f64, h_mads: f64, median: f64, mad: f64) -> Self {
        Self {
            k: k_mads.max(0.0),
            h: h_mads.max(f64::EPSILON),
            median,
            mad: mad.max(f64::EPSILON),
            pos: 0.0,
            neg: 0.0,
        }
    }

    /// Feed one sample; Some(signal) when a cumulative sum crosses `h`.
    pub fn update(&mut self, x: f64) -> Option<CusumSignal> {
        let z = (x - self.median) / self.mad;
        self.pos = (self.pos + z - self.k).max(0.0);
        self.neg = (self.neg - z - self.k).max(0.0);
        if self.pos > self.h {
            self.reset();
            return Some(CusumSignal::UpShift);
        }
        if self.neg > self.h {
            self.reset();
            return Some(CusumSignal::DownShift);
        }
        None
    }

    /// Clear both cumulative sums (baseline is kept).
    pub fn reset(&mut self) {
        self.pos = 0.0;
        self.neg = 0.0;
    }

    /// Current (pos, neg) cumulative sums, in MAD units.
    pub fn sums(&self) -> (f64, f64) {
        (self.pos, self.neg)
    }
}

/// A single detected level step in a series.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StepChange {
    /// Index of the FIRST sample after the step (the right segment starts
    /// here); 2 <= index <= len-2 by construction.
    pub index: usize,
    /// mean(after) - mean(before): negative = the level dropped.
    pub magnitude: f64,
    /// True only when the step passes BOTH significance requirements
    /// documented on [`detect_step`].
    pub significant: bool,
}

/// Simple binary-segmentation step-change detector: finds the single most
/// likely changepoint (the split minimizing the two-segment residual sum of
/// squares, equivalently maximizing the weighted between-segment mean
/// difference) and tests it for significance.
///
/// `significant` requires BOTH of:
///   1. |mean(after) - mean(before)| exceeds `threshold_mads` robust standard
///      errors: |Δ| > threshold_mads * (1.4826 * MAD_resid) * sqrt(1/n1+1/n2),
///      where MAD_resid is the MAD of the pooled residuals around the two
///      segment means. `threshold_mads` = 4.0 keeps the family-wise false-
///      positive rate over the ≲60 candidate splits of a daily series well
///      below 1% for roughly Gaussian noise.
///   2. The two-flat-segments (step) model has a strictly lower SSE than a
///      single straight line fitted to the whole series. Without this test a
///      pure RAMP is always "significant" (its two halves have different
///      means); a trend must stay a trend, and a step must beat the line
///      that would otherwise explain it.
///
/// Claims: ONE abrupt level shift explains these values better than a
/// straight line does, and the shift is large versus local scatter.
/// Does NOT claim: multiple changepoints, online detection, posterior
/// run-length probabilities (this is NOT a Bayesian online method), or the
/// physical cause of the shift. Minimum segment length is 2, so series
/// shorter than 4 return None (as does any series with non-finite values).
pub fn detect_step(values: &[f64], threshold_mads: f64) -> Option<StepChange> {
    let n = values.len();
    if n < 4 || values.iter().any(|v| !v.is_finite()) {
        return None;
    }

    // Prefix sums for O(n) segment means.
    let mut prefix = Vec::with_capacity(n + 1);
    prefix.push(0.0);
    for v in values {
        prefix.push(prefix.last().unwrap() + v);
    }
    let seg_mean = |a: usize, b: usize| (prefix[b] - prefix[a]) / (b - a) as f64; // [a, b)

    // Most likely single changepoint: split minimizing two-segment SSE.
    let mut best: Option<(usize, f64)> = None; // (split index, sse)
    for i in 2..=(n - 2) {
        let (ml, mr) = (seg_mean(0, i), seg_mean(i, n));
        let sse: f64 = values[..i].iter().map(|v| (v - ml).powi(2)).sum::<f64>()
            + values[i..].iter().map(|v| (v - mr).powi(2)).sum::<f64>();
        if best.map_or(true, |(_, b)| sse < b) {
            best = Some((i, sse));
        }
    }
    let (idx, sse_step) = best?;
    let (mean_l, mean_r) = (seg_mean(0, idx), seg_mean(idx, n));
    let magnitude = mean_r - mean_l;

    // Robust residual scale around the two segment means.
    let residuals: Vec<f64> = values
        .iter()
        .enumerate()
        .map(|(i, v)| if i < idx { v - mean_l } else { v - mean_r })
        .collect();
    let (_, mad_resid) = median_mad(&residuals)?;
    let sigma = MAD_TO_SIGMA * mad_resid;
    let stderr = sigma * (1.0 / idx as f64 + 1.0 / (n - idx) as f64).sqrt();

    // Test 1: magnitude vs robust standard error (infinite z when the two
    // segments are perfectly flat — a textbook step).
    let big_enough = if stderr <= f64::EPSILON {
        magnitude.abs() > 0.0
    } else {
        magnitude.abs() > threshold_mads * stderr
    };

    // Test 2: the step model must beat a single straight line.
    let line_points: Vec<(f64, f64)> = values
        .iter()
        .enumerate()
        .map(|(i, v)| (i as f64, *v))
        .collect();
    let sse_line = match linear_fit(&line_points) {
        Some(fit) => line_points
            .iter()
            .map(|(x, y)| (y - (fit.slope * x + fit.intercept)).powi(2))
            .sum::<f64>(),
        None => f64::INFINITY,
    };
    let beats_line = sse_step < sse_line;

    Some(StepChange {
        index: idx,
        magnitude,
        significant: big_enough && beats_line,
    })
}

/// Ordinary least-squares line fit.
#[derive(Debug, Clone, Copy)]
pub struct LinearFit {
    pub slope: f64,
    pub intercept: f64,
    /// Coefficient of determination of the fit (0 when the series is flat).
    pub r_squared: f64,
    /// Standard error of the slope: sqrt((SSE/(n-2)) / Σ(x-x̄)²);
    /// INFINITY when n <= 2 or x has no spread.
    pub slope_stderr: f64,
}

/// OLS regression y = slope*x + intercept over `points`.
///
/// Claims: the least-squares line, its R², and the classical slope standard
/// error (valid under independent, homoscedastic residuals).
/// Does NOT claim: causality, robustness to outliers (sanitize first), or a
/// forecast beyond the fitted window. None for < 3 points or degenerate x.
pub fn linear_fit(points: &[(f64, f64)]) -> Option<LinearFit> {
    let n = points.len() as f64;
    if n < 3.0 {
        return None;
    }

    let sum_x: f64 = points.iter().map(|(x, _)| x).sum();
    let sum_y: f64 = points.iter().map(|(_, y)| y).sum();
    let sum_xy: f64 = points.iter().map(|(x, y)| x * y).sum();
    let sum_x2: f64 = points.iter().map(|(x, _)| x * x).sum();

    let denom = n * sum_x2 - sum_x * sum_x;
    if denom.abs() < 1e-10 {
        return None;
    }

    let slope = (n * sum_xy - sum_x * sum_y) / denom;
    let intercept = (sum_y - slope * sum_x) / n;

    let y_mean = sum_y / n;
    let ss_tot: f64 = points.iter().map(|(_, y)| (y - y_mean).powi(2)).sum();
    let ss_res: f64 = points
        .iter()
        .map(|(x, y)| {
            let predicted = slope * x + intercept;
            (y - predicted).powi(2)
        })
        .sum();
    let r_squared = if ss_tot > 0.0 { 1.0 - ss_res / ss_tot } else { 0.0 };

    let sxx = sum_x2 - sum_x * sum_x / n;
    let slope_stderr = if n > 2.0 && sxx > 1e-12 {
        ((ss_res / (n - 2.0)) / sxx).sqrt()
    } else {
        f64::INFINITY
    };

    Some(LinearFit {
        slope,
        intercept,
        r_squared,
        slope_stderr,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Deterministic uniform noise in [-1, 1) — tests must not be flaky.
    fn lcg_noise(seed: u64, n: usize) -> Vec<f64> {
        let mut state = seed;
        (0..n)
            .map(|_| {
                state = state
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                ((state >> 33) as f64 / (1u64 << 31) as f64) * 2.0 - 1.0
            })
            .collect()
    }

    #[test]
    fn test_median_mad_known_values() {
        let (med, mad) = median_mad(&[1.0, 2.0, 3.0, 4.0, 100.0]).unwrap();
        assert_eq!(med, 3.0);
        assert_eq!(mad, 1.0, "MAD must ignore the 100.0 outlier");
        assert!(median_mad(&[]).is_none());
        assert!(median_mad(&[f64::NAN]).is_none());
        // Even count: median of middle pair.
        let (med2, _) = median_mad(&[1.0, 2.0, 3.0, 4.0]).unwrap();
        assert_eq!(med2, 2.5);
    }

    #[test]
    fn test_robust_z() {
        // value 3 sigma-equivalents away: (m + 3*1.4826*mad)
        let z = robust_z(3.0 * MAD_TO_SIGMA, 0.0, 1.0);
        assert!((z - 3.0).abs() < 1e-9);
        assert_eq!(robust_z(5.0, 5.0, 0.0), 0.0);
        assert_eq!(robust_z(6.0, 5.0, 0.0), f64::INFINITY);
        assert_eq!(robust_z(4.0, 5.0, 0.0), f64::NEG_INFINITY);
    }

    #[test]
    fn test_ewma_converges_and_estimates_variance() {
        let noise = lcg_noise(7, 400);
        let mut ew = Ewma::new(0.1);
        for x in &noise {
            ew.update(10.0 + x);
        }
        let mean = ew.mean().unwrap();
        assert!((mean - 10.0).abs() < 0.5, "mean={mean}");
        // Uniform[-1,1) variance = 1/3; EW estimate is noisy — loose bounds.
        let var = ew.variance().unwrap();
        assert!(var > 0.05 && var < 1.0, "var={var}");
    }

    #[test]
    fn test_ewma_empty_and_single() {
        let mut ew = Ewma::new(0.3);
        assert!(ew.mean().is_none());
        ew.update(4.0);
        assert_eq!(ew.mean(), Some(4.0));
        assert!(ew.variance().is_none(), "variance needs 2 samples");
    }

    #[test]
    fn test_detect_step_finds_known_step_within_two_indices() {
        // Noise sigma_uniform ~ 0.58, step of 5.0 at index 10.
        let mut values = lcg_noise(42, 30);
        for v in values.iter_mut().skip(10) {
            *v += 5.0;
        }
        let step = detect_step(&values, 4.0).expect("series long enough");
        assert!(step.significant, "5-sigma-class step must be significant");
        assert!(
            (step.index as i64 - 10).unsigned_abs() <= 2,
            "index {} not within ±2 of 10",
            step.index
        );
        assert!((step.magnitude - 5.0).abs() < 1.0, "magnitude={}", step.magnitude);
    }

    #[test]
    fn test_detect_step_pure_noise_not_significant() {
        // Documented false-positive setting: threshold_mads = 4.0. Pure
        // noise must not produce a significant step.
        for seed in [1u64, 2, 3, 4, 5] {
            let values = lcg_noise(seed, 30);
            if let Some(step) = detect_step(&values, 4.0) {
                assert!(
                    !step.significant,
                    "seed {seed}: noise flagged significant: {step:?}"
                );
            }
        }
    }

    #[test]
    fn test_detect_step_ramp_is_not_a_step() {
        // A pure linear trend has different segment means at any split, but
        // the LINE explains it better than a step: must NOT be significant.
        // (This is the guard that keeps splice-event detection from eating
        // genuine degradation trends.)
        let noise = lcg_noise(9, 28);
        let values: Vec<f64> = noise
            .iter()
            .enumerate()
            .map(|(i, n)| i as f64 * 0.5 + 0.05 * n)
            .collect();
        let step = detect_step(&values, 4.0).unwrap();
        assert!(!step.significant, "ramp misread as step: {step:?}");
    }

    #[test]
    fn test_detect_step_perfect_step_zero_noise() {
        // Flat, then flat 2 lower: residual MAD is 0; must still detect.
        let mut values = vec![-20.0; 7];
        values.extend(vec![-22.0; 7]);
        let step = detect_step(&values, 4.0).unwrap();
        assert!(step.significant);
        assert_eq!(step.index, 7);
        assert!((step.magnitude + 2.0).abs() < 1e-9);
    }

    #[test]
    fn test_detect_step_too_short_returns_none() {
        assert!(detect_step(&[1.0, 5.0, 5.0], 4.0).is_none());
    }

    #[test]
    fn test_cusum_catches_half_mad_shift_that_thresholds_miss() {
        // Baseline: uniform noise scaled to ±0.5 → MAD ~ 0.25.
        let baseline: Vec<f64> = lcg_noise(11, 80).iter().map(|x| x * 0.5).collect();
        let (med, mad) = median_mad(&baseline).unwrap();
        assert!(mad > 0.05, "baseline mad={mad}");

        // Sustained shift of 0.5 MAD — far below any single-point threshold.
        let shift = 0.5 * mad;
        let shifted: Vec<f64> = lcg_noise(12, 80).iter().map(|x| x * 0.5 + shift).collect();

        // 1) No single sample crosses a robust-z threshold of 3.
        let max_z = shifted
            .iter()
            .map(|x| robust_z(*x, med, mad))
            .fold(f64::NEG_INFINITY, f64::max);
        assert!(max_z < 3.0, "single-point threshold should miss: max_z={max_z}");

        // 2) CUSUM (k=0.25, h=5 MAD units) accumulates ~0.25 MAD/sample and
        // must alarm within the shifted window.
        let mut cusum = Cusum::new(0.25, 5.0, med, mad);
        for x in &baseline {
            assert!(
                cusum.update(*x).is_none(),
                "CUSUM must not alarm on its own baseline"
            );
        }
        let alarmed = shifted.iter().any(|x| cusum.update(*x) == Some(CusumSignal::UpShift));
        assert!(alarmed, "CUSUM must catch a sustained 0.5-MAD up-shift");
    }

    #[test]
    fn test_cusum_downshift_and_reset() {
        let mut cusum = Cusum::new(0.5, 4.0, 0.0, 1.0);
        let mut signal = None;
        for _ in 0..20 {
            if let Some(s) = cusum.update(-2.0) {
                signal = Some(s);
                break;
            }
        }
        assert_eq!(signal, Some(CusumSignal::DownShift));
        // Sums were reset by the alarm.
        assert_eq!(cusum.sums(), (0.0, 0.0));
    }

    #[test]
    fn test_linear_fit_matches_known_line() {
        let pts: Vec<(f64, f64)> = (0..10).map(|i| (i as f64, 2.0 * i as f64 + 1.0)).collect();
        let fit = linear_fit(&pts).unwrap();
        assert!((fit.slope - 2.0).abs() < 1e-9);
        assert!((fit.intercept - 1.0).abs() < 1e-9);
        assert!(fit.r_squared > 0.999);
        assert!(fit.slope_stderr < 1e-6);
        assert!(linear_fit(&pts[..2]).is_none(), "needs >= 3 points");
    }
}
