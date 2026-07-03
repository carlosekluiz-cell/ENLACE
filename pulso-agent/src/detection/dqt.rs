// SPDX-License-Identifier: Apache-2.0
// Dual-Field Quasi-Static Tomography (DQT) — EXPERIMENTAL
//
// Research module: treats the PON plant as a passive quasi-static
// environmental sensor and runs four pre-registered falsification tests
// against the same telemetry the operational modules already parse.
//
//   Field A (electrical): endpoint PSUs sample the low-voltage grid.
//     Co-timed power-loss events (dying gasp / power_fail causes) across
//     ONTs are samples of grid-failure domains; stable co-failure
//     communities across repeated events ARE the hidden LV topology.
//   Field B (ground): buried fiber samples the soil thermo-mechanical
//     state. Ground temperature reaches a buried element through a
//     diffusive low-pass filter (T(z,t) lags surface by z/d radians,
//     d = sqrt(2*alpha/omega)), so any loss signature that tracks the
//     diurnal cycle WITH a phase lag is reporting from underground.
//     FEC corrected-codeword rates sit on the erfc() waterfall and act
//     as a logarithmic amplifier resolving attenuation changes below
//     the DDM quantization floor.
//
// HONESTY RULES (mirrors the rest of the engine):
//   - This module NEVER generates tickets. Unvalidated physics must not
//     page an engineer. Output is research evidence only.
//   - Every test carries its exact kill-threshold in the output, and a
//     verdict of Supported / Refuted / Indeterminate / InsufficientData.
//     Absence of data is InsufficientData, never support.
//   - Known confounder handled, not hidden: responders whose optical
//     diurnal cycle is in phase with their own traffic cycle are counted
//     separately as traffic-confounded and excluded from verdicts
//     (self-heating from load, not the earth).
//   - Sampling reality stated up front: at 30 s-15 min cadence the
//     Nyquist ceiling is ~mHz. This sensor sees hours-to-seasons
//     dynamics only. It is not, and cannot be, an acoustic/seismic
//     instrument (no optical phase is measured).
//
// Pre-registered tests (thresholds fixed before looking at data):
//   T1 grid-community stability: >=5 multi-ONT power events; median
//      max-Jaccard between event member-sets >= 0.5 => Supported,
//      < 0.5 => Refuted.
//   T2 thermal phase lag: among diurnally-coherent responders
//      (single-tone fit R^2 >= 0.5, not traffic-confounded, >= 10 of
//      them): >= 20% with |folded lag| >= 2 h => Supported; >= 95% with
//      |folded lag| < 0.5 h => Refuted; else Indeterminate. Lags are
//      folded mod 12 h (coupling polarity is mechanism-dependent).
//   T3 FEC amplifier gain: ONTs whose rx wandered >= 0.5 dB with >= 8
//      usable FEC intervals; >= 5 eligible: median |slope| >= 0.3
//      decades/dB AND negative sign in >= 60% => Supported; else
//      Refuted.
//   T4 wavelength asymmetry (water vs strain): requires BOTH the
//      ONT-side downstream rx and the OLT-side upstream rx per reading.
//      CSV audits carry only the ONT-side value, so this test reports
//      InsufficientData until the upstream field lands in the export.

use std::collections::{BTreeMap, HashMap};

use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

use super::{sane_rx, OntReading, OntReadingStatus};

// ---------------------------------------------------------------------------
// Pre-registered thresholds (T1-T4). Fixed constants, echoed into output.
// ---------------------------------------------------------------------------

/// T1: minimum distinct multi-ONT power events before any verdict.
const T1_MIN_EVENTS: usize = 5;
/// T1: minimum ONTs losing power together to count as one grid event.
const T1_MIN_ONTS_PER_EVENT: usize = 3;
/// T1: co-loss window — transitions within this many seconds are one event.
const T1_EVENT_WINDOW_SECS: i64 = 600;
/// T1: median max-Jaccard at or above this => stable communities.
const T1_JACCARD_SUPPORT: f64 = 0.5;
/// T1: pair must co-fail in >= this many events to join a community.
const T1_MIN_CO_EVENTS: usize = 2;

/// T2: single-tone diurnal fit R^2 for an ONT to count as a responder.
const T2_MIN_COHERENCE_R2: f64 = 0.5;
/// T2: minimum non-confounded responders before any verdict.
const T2_MIN_RESPONDERS: usize = 10;
/// T2: lag (hours) marking a buried/filtered response.
const T2_BURIED_LAG_HOURS: f64 = 2.0;
/// T2: fraction of responders with lag >= T2_BURIED_LAG_HOURS => Supported.
const T2_SUPPORT_FRACTION: f64 = 0.20;
/// T2: |lag| below this is "tracks ambient directly" (aerial/indoor).
const T2_ZERO_LAG_HOURS: f64 = 0.5;
/// T2: fraction of responders inside +/-T2_ZERO_LAG_HOURS => Refuted.
const T2_REFUTE_FRACTION: f64 = 0.95;
/// T2: responder whose octet-rate diurnal phase sits within this many
/// hours of its optical phase (and octet fit R^2 >= T2_MIN_COHERENCE_R2)
/// is traffic-confounded: self-heating, not soil.
const T2_TRAFFIC_CONFOUND_HOURS: f64 = 1.0;
/// T2: minimum time span (days) and samples for a diurnal fit.
const T2_MIN_SPAN_DAYS: f64 = 3.0;
const T2_MIN_SAMPLES: usize = 48;
/// T2: minimum ONTs contributing temperature to form the ambient proxy.
const T2_MIN_AMBIENT_SOURCES: usize = 5;

/// T3: rx must wander at least this many dB for slope identifiability.
const T3_MIN_RX_RANGE_DB: f64 = 0.5;
/// T3: minimum usable (rx, FEC-delta) intervals per ONT.
const T3_MIN_INTERVALS: usize = 8;
/// T3: minimum eligible ONTs before any verdict.
const T3_MIN_ELIGIBLE: usize = 5;
/// T3: median |slope| (decades of corrected rate per dB) to support.
const T3_MIN_ABS_SLOPE: f64 = 0.3;
/// T3: fraction of eligible ONTs with the physical (negative) sign.
const T3_MIN_SIGN_FRACTION: f64 = 0.6;

const SECS_PER_DAY: f64 = 86_400.0;

// ---------------------------------------------------------------------------
// Output types
// ---------------------------------------------------------------------------

/// Verdict of one pre-registered falsification test.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum HypothesisVerdict {
    /// Passed its pre-registered support criterion.
    Supported,
    /// Hit its pre-registered kill-threshold.
    Refuted,
    /// Enough data to test, but neither criterion met.
    Indeterminate,
    /// Not enough data to run the test at all. Never counts as support.
    InsufficientData,
}

/// Top-level DQT report. `experimental` is always true; the module never
/// emits tickets and its findings are research evidence, not operations.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DqtReport {
    pub experimental: bool,
    pub note: String,
    pub grid: GridFieldTest,
    pub thermal: ThermalPhaseTest,
    pub fec_amplifier: FecGainTest,
    pub wavelength: WavelengthAsymmetryTest,
}

/// T1 — LV-grid co-failure community stability.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GridFieldTest {
    pub verdict: HypothesisVerdict,
    pub kill_threshold: String,
    /// Multi-ONT power events found (>= T1_MIN_ONTS_PER_EVENT gasping ONTs
    /// inside one T1_EVENT_WINDOW_SECS window).
    pub events_found: usize,
    /// Median over events of the best Jaccard overlap with any other event.
    pub median_max_jaccard: Option<f64>,
    /// Inferred co-failure communities (candidate shared-transformer
    /// domains): ONT serials that co-failed in >= T1_MIN_CO_EVENTS events.
    pub communities: Vec<Vec<String>>,
    pub note: String,
}

/// T2 — diurnal phase-lag (buried-medium) test.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalPhaseTest {
    pub verdict: HypothesisVerdict,
    pub kill_threshold: String,
    /// ONTs with enough rx samples/span to attempt a diurnal fit.
    pub onts_fitted: usize,
    /// Diurnally-coherent responders (R^2 >= threshold), excluding
    /// traffic-confounded ones.
    pub responders: usize,
    /// Responders excluded because their optical cycle is in phase with
    /// their own traffic cycle (self-heating, not environment).
    pub traffic_confounded: usize,
    /// Fraction of responders with lag >= T2_BURIED_LAG_HOURS.
    pub lagged_fraction: Option<f64>,
    /// Fraction of responders with |lag| < T2_ZERO_LAG_HOURS.
    pub zero_lag_fraction: Option<f64>,
    /// Median lag (hours) across responders, folded modulo 12 h into
    /// (-6, +6] because coupling polarity is mechanism-dependent (an
    /// inverted in-phase response aliases a 12 h lag). Only the folded
    /// magnitude carries burial-depth information.
    pub median_lag_hours: Option<f64>,
    pub note: String,
}

/// T3 — FEC waterfall amplifier gain test.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FecGainTest {
    pub verdict: HypothesisVerdict,
    pub kill_threshold: String,
    /// ONTs with rx range >= T3_MIN_RX_RANGE_DB and >= T3_MIN_INTERVALS
    /// usable FEC intervals.
    pub eligible_onts: usize,
    /// Median of |slope| across eligible ONTs (decades per dB).
    pub median_abs_slope: Option<f64>,
    /// Fraction of eligible ONTs with the physical (negative) slope sign.
    pub negative_sign_fraction: Option<f64>,
    pub note: String,
}

/// T4 — wavelength-asymmetric loss (water vs strain) classifier.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WavelengthAsymmetryTest {
    pub verdict: HypothesisVerdict,
    pub kill_threshold: String,
    pub note: String,
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

/// Run all four pre-registered DQT falsification tests over the readings.
/// Pure function over already-parsed telemetry; adds no collection, no
/// device interaction, and never produces tickets.
pub fn run_dqt(readings: &[OntReading]) -> DqtReport {
    DqtReport {
        experimental: true,
        note: "Dual-Field Quasi-Static Tomography (research). Pre-registered \
               falsification tests over existing read-only telemetry. \
               Generates no tickets. Nyquist ceiling at polling cadence is \
               ~mHz: results concern hours-to-seasons dynamics only; this is \
               not an acoustic or seismic sensor."
            .to_string(),
        grid: test_grid_communities(readings),
        thermal: test_thermal_phase(readings),
        fec_amplifier: test_fec_gain(readings),
        wavelength: test_wavelength_asymmetry(readings),
    }
}

// ---------------------------------------------------------------------------
// T1 — grid co-failure communities
// ---------------------------------------------------------------------------

fn is_power_cause(cause: &Option<String>) -> bool {
    cause
        .as_deref()
        .map(|c| {
            let c = c.to_ascii_lowercase();
            c.contains("power") || c.contains("gasp")
        })
        .unwrap_or(false)
}

/// Online->Offline transitions with a power-like down cause, per ONT.
fn power_loss_transitions(readings: &[OntReading]) -> Vec<(DateTime<Utc>, String)> {
    let mut by_ont: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_ont.entry(r.serial_number.as_str()).or_default().push(r);
    }
    let mut transitions = Vec::new();
    for (serial, mut series) in by_ont {
        series.sort_by_key(|r| r.timestamp);
        for pair in series.windows(2) {
            let (prev, cur) = (pair[0], pair[1]);
            // Unknown is not an outage: only a witnessed Online -> Offline
            // edge with a power-like cause counts as a grid sample.
            if prev.status == OntReadingStatus::Online
                && cur.status == OntReadingStatus::Offline
                && is_power_cause(&cur.last_down_cause)
            {
                transitions.push((cur.timestamp, serial.to_string()));
            }
        }
    }
    transitions.sort_by_key(|(t, _)| *t);
    transitions
}

/// Greedy time-window clustering of power-loss transitions into events.
fn cluster_events(transitions: &[(DateTime<Utc>, String)]) -> Vec<Vec<String>> {
    let mut events: Vec<Vec<String>> = Vec::new();
    let mut i = 0;
    while i < transitions.len() {
        let window_end = transitions[i].0 + Duration::seconds(T1_EVENT_WINDOW_SECS);
        let mut members: Vec<String> = Vec::new();
        let mut j = i;
        while j < transitions.len() && transitions[j].0 <= window_end {
            if !members.contains(&transitions[j].1) {
                members.push(transitions[j].1.clone());
            }
            j += 1;
        }
        if members.len() >= T1_MIN_ONTS_PER_EVENT {
            members.sort();
            events.push(members);
        }
        i = j.max(i + 1);
    }
    events
}

fn jaccard(a: &[String], b: &[String]) -> f64 {
    let sa: std::collections::HashSet<&String> = a.iter().collect();
    let sb: std::collections::HashSet<&String> = b.iter().collect();
    let inter = sa.intersection(&sb).count();
    let union = sa.union(&sb).count();
    if union == 0 {
        0.0
    } else {
        inter as f64 / union as f64
    }
}

/// Union-find over ONTs that co-failed in >= T1_MIN_CO_EVENTS events.
fn co_failure_communities(events: &[Vec<String>]) -> Vec<Vec<String>> {
    let mut pair_counts: HashMap<(String, String), usize> = HashMap::new();
    for ev in events {
        for i in 0..ev.len() {
            for j in (i + 1)..ev.len() {
                let key = (ev[i].clone(), ev[j].clone());
                *pair_counts.entry(key).or_insert(0) += 1;
            }
        }
    }
    // Union-find over serials linked by recurring co-failure.
    let mut parent: HashMap<String, String> = HashMap::new();
    fn find(parent: &mut HashMap<String, String>, x: &str) -> String {
        let p = parent.get(x).cloned().unwrap_or_else(|| x.to_string());
        if p == x {
            return p;
        }
        let root = find(parent, &p);
        parent.insert(x.to_string(), root.clone());
        root
    }
    for ((a, b), n) in &pair_counts {
        if *n >= T1_MIN_CO_EVENTS {
            let ra = find(&mut parent, a);
            let rb = find(&mut parent, b);
            if ra != rb {
                parent.insert(ra, rb);
            }
        }
    }
    let mut groups: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let members: Vec<String> = pair_counts
        .keys()
        .flat_map(|(a, b)| [a.clone(), b.clone()])
        .collect();
    for m in members {
        let root = find(&mut parent, &m);
        let g = groups.entry(root).or_default();
        if !g.contains(&m) {
            g.push(m);
        }
    }
    let mut communities: Vec<Vec<String>> = groups
        .into_values()
        .filter(|g| g.len() >= 2)
        .map(|mut g| {
            g.sort();
            g
        })
        .collect();
    communities.sort();
    communities
}

fn test_grid_communities(readings: &[OntReading]) -> GridFieldTest {
    let kill = format!(
        "median max-Jaccard between event member-sets < {T1_JACCARD_SUPPORT} \
         over >= {T1_MIN_EVENTS} multi-ONT power events => Refuted"
    );
    let transitions = power_loss_transitions(readings);
    let events = cluster_events(&transitions);
    if events.len() < T1_MIN_EVENTS {
        return GridFieldTest {
            verdict: HypothesisVerdict::InsufficientData,
            kill_threshold: kill,
            events_found: events.len(),
            median_max_jaccard: None,
            communities: Vec::new(),
            note: format!(
                "{} multi-ONT power event(s) found; {} required. Not enough \
                 grid-failure samples in this window to test topology \
                 stability.",
                events.len(),
                T1_MIN_EVENTS
            ),
        };
    }
    // Per event, best overlap with any OTHER event; median across events.
    let mut best: Vec<f64> = Vec::with_capacity(events.len());
    for (i, ev) in events.iter().enumerate() {
        let m = events
            .iter()
            .enumerate()
            .filter(|(j, _)| *j != i)
            .map(|(_, other)| jaccard(ev, other))
            .fold(0.0_f64, f64::max);
        best.push(m);
    }
    best.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = best[best.len() / 2];
    let communities = co_failure_communities(&events);
    let verdict = if median >= T1_JACCARD_SUPPORT {
        HypothesisVerdict::Supported
    } else {
        HypothesisVerdict::Refuted
    };
    GridFieldTest {
        verdict,
        kill_threshold: kill,
        events_found: events.len(),
        median_max_jaccard: Some(median),
        communities,
        note: match verdict {
            HypothesisVerdict::Supported => {
                "Recurring co-failure structure found: the same ONT sets \
                 lose power together across events — candidate shared \
                 LV-transformer domains. Communities need field validation \
                 (postcode-to-substation mapping) before any operational use."
                    .to_string()
            }
            _ => "Power events found but membership does not repeat: no \
                  stable electrical structure detectable in this window."
                .to_string(),
        },
    }
}

// ---------------------------------------------------------------------------
// T2 — diurnal phase lag
// ---------------------------------------------------------------------------

/// Least-squares single-tone fit x(t) ~ a + b*cos(wt) + c*sin(wt) at the
/// diurnal frequency. Returns (amplitude, phase_rad, r2). Phase is the arg
/// of the fitted cosine: x(t) ~ a + A*cos(wt - phase). Handles irregular
/// sampling via the normal equations.
fn diurnal_fit(times_s: &[f64], values: &[f64]) -> Option<(f64, f64, f64)> {
    let n = times_s.len();
    if n < 3 || n != values.len() {
        return None;
    }
    let w = 2.0 * std::f64::consts::PI / SECS_PER_DAY;
    // Normal equations for design [1, cos(wt), sin(wt)].
    let (mut sc, mut ss, mut scc, mut sss, mut scs) = (0.0, 0.0, 0.0, 0.0, 0.0);
    let (mut sy, mut syc, mut sys) = (0.0, 0.0, 0.0);
    for (&t, &y) in times_s.iter().zip(values) {
        let (c, s) = ((w * t).cos(), (w * t).sin());
        sc += c;
        ss += s;
        scc += c * c;
        sss += s * s;
        scs += c * s;
        sy += y;
        syc += y * c;
        sys += y * s;
    }
    let nf = n as f64;
    // Solve the 3x3 symmetric system via Cramer's rule.
    let m = [[nf, sc, ss], [sc, scc, scs], [ss, scs, sss]];
    let rhs = [sy, syc, sys];
    let det = |m: &[[f64; 3]; 3]| {
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    };
    let d = det(&m);
    if d.abs() < 1e-12 {
        return None;
    }
    let solve_col = |col: usize| {
        let mut mm = m;
        for r in 0..3 {
            mm[r][col] = rhs[r];
        }
        det(&mm) / d
    };
    let a = solve_col(0);
    let b = solve_col(1);
    let c = solve_col(2);
    let amp = (b * b + c * c).sqrt();
    // x(t) ~ a + amp*cos(wt - phase), with phase = atan2(c, b).
    let phase = c.atan2(b);
    // R^2 of the tone against the mean-only model.
    let mean = sy / nf;
    let (mut ss_tot, mut ss_res) = (0.0, 0.0);
    for (&t, &y) in times_s.iter().zip(values) {
        let fit = a + b * (w * t).cos() + c * (w * t).sin();
        ss_tot += (y - mean) * (y - mean);
        ss_res += (y - fit) * (y - fit);
    }
    if ss_tot <= 0.0 {
        return None;
    }
    Some((amp, phase, 1.0 - ss_res / ss_tot))
}

/// Phase difference as hours of lag, FOLDED modulo 12 h into (-6, +6].
///
/// Why folded: the sign of the optical-thermal coupling is mechanism-
/// dependent (heat-driven duct expansion raises loss at the temperature
/// crest; frost mechanisms at the trough), and with a single diurnal tone
/// an inverted in-phase response is indistinguishable from a 12 h lag.
/// Polarity is therefore treated as a nuisance parameter: only the folded
/// lag magnitude carries burial-depth information. This halves the
/// unambiguous lag range to +/-6 h — stated, not hidden.
fn phase_to_lag_hours(reference_phase: f64, signal_phase: f64) -> f64 {
    let two_pi = 2.0 * std::f64::consts::PI;
    let mut lag_h = (signal_phase - reference_phase) / two_pi * 24.0;
    // Fold modulo 12 into (-6, +6].
    lag_h = lag_h.rem_euclid(12.0);
    if lag_h > 6.0 {
        lag_h -= 12.0;
    }
    lag_h
}

fn test_thermal_phase(readings: &[OntReading]) -> ThermalPhaseTest {
    let kill = format!(
        ">= {:.0}% of coherent responders with |lag| < {T2_ZERO_LAG_HOURS} h \
         => Refuted (everything tracks ambient directly; no buried-medium \
         filtering present)",
        T2_REFUTE_FRACTION * 100.0
    );
    // --- Ambient reference: fleet-median transceiver temperature per 30-min
    // bin. A proxy, not a met feed; its own diurnal phase defines lag zero.
    let t0 = match readings.iter().map(|r| r.timestamp).min() {
        Some(t) => t,
        None => {
            return insufficient_thermal(kill, "no readings");
        }
    };
    let mut temp_bins: BTreeMap<i64, Vec<f64>> = BTreeMap::new();
    let mut temp_sources: std::collections::HashSet<&str> = Default::default();
    for r in readings {
        if let Some(tc) = r.temperature_c {
            let bin = (r.timestamp - t0).num_seconds() / 1800;
            temp_bins.entry(bin).or_default().push(tc);
            temp_sources.insert(r.serial_number.as_str());
        }
    }
    if temp_sources.len() < T2_MIN_AMBIENT_SOURCES {
        return insufficient_thermal(
            kill,
            &format!(
                "ambient proxy needs temperature from >= {} ONTs; {} have it",
                T2_MIN_AMBIENT_SOURCES,
                temp_sources.len()
            ),
        );
    }
    let (ref_times, ref_vals): (Vec<f64>, Vec<f64>) = temp_bins
        .iter()
        .map(|(bin, v)| {
            let mut vv = v.clone();
            vv.sort_by(|a, b| a.partial_cmp(b).unwrap());
            ((*bin as f64) * 1800.0 + 900.0, vv[vv.len() / 2])
        })
        .unzip();
    let (_, ref_phase, ref_r2) = match diurnal_fit(&ref_times, &ref_vals) {
        Some(f) => f,
        None => return insufficient_thermal(kill, "ambient proxy fit failed"),
    };
    if ref_r2 < T2_MIN_COHERENCE_R2 {
        return insufficient_thermal(
            kill,
            &format!(
                "ambient proxy itself has no coherent diurnal cycle \
                 (R^2 = {ref_r2:.2}); cannot define lag zero"
            ),
        );
    }
    // --- Per-ONT optical diurnal fits.
    let mut by_ont: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_ont.entry(r.serial_number.as_str()).or_default().push(r);
    }
    let mut onts_fitted = 0usize;
    let mut confounded = 0usize;
    let mut lags: Vec<f64> = Vec::new();
    for (_, mut series) in by_ont {
        series.sort_by_key(|r| r.timestamp);
        let pts: Vec<(f64, f64)> = series
            .iter()
            .filter_map(|r| {
                sane_rx(r).map(|rx| ((r.timestamp - t0).num_seconds() as f64, rx))
            })
            .collect();
        if pts.len() < T2_MIN_SAMPLES {
            continue;
        }
        let span_days = (pts.last().unwrap().0 - pts[0].0) / SECS_PER_DAY;
        if span_days < T2_MIN_SPAN_DAYS {
            continue;
        }
        let times: Vec<f64> = pts.iter().map(|p| p.0).collect();
        let vals: Vec<f64> = pts.iter().map(|p| p.1).collect();
        onts_fitted += 1;
        let (_, phase, r2) = match diurnal_fit(&times, &vals) {
            Some(f) => f,
            None => continue,
        };
        if r2 < T2_MIN_COHERENCE_R2 {
            continue;
        }
        let lag = phase_to_lag_hours(ref_phase, phase);
        // Traffic-confound guard: if this ONT's own octet rate carries a
        // coherent diurnal cycle in phase with its optical cycle, the
        // optical cycle is explained by load self-heating, not the soil.
        if let Some(octet_phase) = octet_diurnal_phase(&series, t0) {
            let sep = phase_to_lag_hours(octet_phase, phase).abs();
            if sep < T2_TRAFFIC_CONFOUND_HOURS {
                confounded += 1;
                continue;
            }
        }
        lags.push(lag);
    }
    if lags.len() < T2_MIN_RESPONDERS {
        return ThermalPhaseTest {
            verdict: HypothesisVerdict::InsufficientData,
            kill_threshold: kill,
            onts_fitted,
            responders: lags.len(),
            traffic_confounded: confounded,
            lagged_fraction: None,
            zero_lag_fraction: None,
            median_lag_hours: None,
            note: format!(
                "{} coherent non-confounded responder(s); {} required. No \
                 verdict on the buried-medium hypothesis from this window.",
                lags.len(),
                T2_MIN_RESPONDERS
            ),
        };
    }
    let lagged = lags
        .iter()
        .filter(|l| l.abs() >= T2_BURIED_LAG_HOURS)
        .count() as f64
        / lags.len() as f64;
    let zeroish = lags.iter().filter(|l| l.abs() < T2_ZERO_LAG_HOURS).count() as f64
        / lags.len() as f64;
    let mut sorted = lags.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median_lag = sorted[sorted.len() / 2];
    let verdict = if zeroish >= T2_REFUTE_FRACTION {
        HypothesisVerdict::Refuted
    } else if lagged >= T2_SUPPORT_FRACTION {
        HypothesisVerdict::Supported
    } else {
        HypothesisVerdict::Indeterminate
    };
    ThermalPhaseTest {
        verdict,
        kill_threshold: kill,
        onts_fitted,
        responders: lags.len(),
        traffic_confounded: confounded,
        lagged_fraction: Some(lagged),
        zero_lag_fraction: Some(zeroish),
        median_lag_hours: Some(median_lag),
        note: match verdict {
            HypothesisVerdict::Supported => {
                "A population of optical signatures follows the diurnal \
                 cycle with a multi-hour lag — consistent with thermally \
                 filtered (buried) plant elements. Lag encodes depth over \
                 thermal diffusivity; validation against known burial \
                 depths required before any geophysical claim."
                    .to_string()
            }
            HypothesisVerdict::Refuted => {
                "Essentially all coherent responders track the ambient \
                 proxy with no lag: no evidence of buried-medium thermal \
                 filtering in the optical plant."
                    .to_string()
            }
            _ => "Some lag structure present but below the pre-registered \
                  support fraction; neither supported nor killed."
                .to_string(),
        },
    }
}

fn insufficient_thermal(kill: String, why: &str) -> ThermalPhaseTest {
    ThermalPhaseTest {
        verdict: HypothesisVerdict::InsufficientData,
        kill_threshold: kill,
        onts_fitted: 0,
        responders: 0,
        traffic_confounded: 0,
        lagged_fraction: None,
        zero_lag_fraction: None,
        median_lag_hours: None,
        note: why.to_string(),
    }
}

/// Diurnal phase of an ONT's total octet RATE (per-interval deltas of the
/// cumulative counters). None when counters are absent or the fit is not
/// coherent — in which case there is nothing to confound.
fn octet_diurnal_phase(series: &[&OntReading], t0: DateTime<Utc>) -> Option<f64> {
    let mut times = Vec::new();
    let mut rates = Vec::new();
    let mut last: Option<(f64, u128)> = None;
    for r in series {
        let total = match (r.in_octets, r.out_octets) {
            (Some(i), Some(o)) => i as u128 + o as u128,
            (Some(i), None) => i as u128,
            (None, Some(o)) => o as u128,
            (None, None) => continue,
        };
        let t = (r.timestamp - t0).num_seconds() as f64;
        if let Some((pt, pv)) = last {
            let dt = t - pt;
            // Counter resets (delta < 0) are skipped, never clamped.
            if dt > 0.0 && total >= pv {
                times.push((pt + t) / 2.0);
                rates.push((total - pv) as f64 / dt);
            }
        }
        last = Some((t, total));
    }
    if times.len() < T2_MIN_SAMPLES / 2 {
        return None;
    }
    let (_, phase, r2) = diurnal_fit(&times, &rates)?;
    (r2 >= T2_MIN_COHERENCE_R2).then_some(phase)
}

// ---------------------------------------------------------------------------
// T3 — FEC amplifier gain
// ---------------------------------------------------------------------------

fn test_fec_gain(readings: &[OntReading]) -> FecGainTest {
    let kill = format!(
        "over >= {T3_MIN_ELIGIBLE} eligible ONTs: median |slope| < \
         {T3_MIN_ABS_SLOPE} decades/dB OR negative-sign fraction < \
         {:.0}% => Refuted",
        T3_MIN_SIGN_FRACTION * 100.0
    );
    let mut by_ont: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_ont.entry(r.serial_number.as_str()).or_default().push(r);
    }
    let mut slopes: Vec<f64> = Vec::new();
    for (_, mut series) in by_ont {
        series.sort_by_key(|r| r.timestamp);
        // Pair consecutive readings that HAVE a corrected-FEC counter.
        // delta < 0 => reset, interval skipped (mirrors fec_health).
        let mut xs: Vec<f64> = Vec::new(); // rx dBm at interval midpoint
        let mut ys: Vec<f64> = Vec::new(); // log10(1 + corrected per hour)
        let mut last: Option<(&OntReading, u64)> = None;
        for r in series {
            let Some(fec) = r.fec_corrected else { continue };
            if let Some((prev, pv)) = last {
                let dt_h =
                    (r.timestamp - prev.timestamp).num_seconds() as f64 / 3600.0;
                if dt_h > 0.0 && fec >= pv {
                    if let (Some(rx1), Some(rx2)) = (sane_rx(prev), sane_rx(r)) {
                        xs.push((rx1 + rx2) / 2.0);
                        ys.push((1.0 + (fec - pv) as f64 / dt_h).log10());
                    }
                }
            }
            last = Some((r, fec));
        }
        if xs.len() < T3_MIN_INTERVALS {
            continue;
        }
        let range = xs.iter().cloned().fold(f64::MIN, f64::max)
            - xs.iter().cloned().fold(f64::MAX, f64::min);
        if range < T3_MIN_RX_RANGE_DB {
            continue;
        }
        if let Some(slope) = linreg_slope(&xs, &ys) {
            slopes.push(slope);
        }
    }
    if slopes.len() < T3_MIN_ELIGIBLE {
        return FecGainTest {
            verdict: HypothesisVerdict::InsufficientData,
            kill_threshold: kill,
            eligible_onts: slopes.len(),
            median_abs_slope: None,
            negative_sign_fraction: None,
            note: format!(
                "{} ONT(s) with >= {} FEC intervals and >= {} dB of rx \
                 wander; {} required. The amplifier claim is untestable in \
                 this window.",
                slopes.len(),
                T3_MIN_INTERVALS,
                T3_MIN_RX_RANGE_DB,
                T3_MIN_ELIGIBLE
            ),
        };
    }
    let mut abs: Vec<f64> = slopes.iter().map(|s| s.abs()).collect();
    abs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median_abs = abs[abs.len() / 2];
    let neg_frac =
        slopes.iter().filter(|s| **s < 0.0).count() as f64 / slopes.len() as f64;
    let verdict = if median_abs >= T3_MIN_ABS_SLOPE && neg_frac >= T3_MIN_SIGN_FRACTION
    {
        HypothesisVerdict::Supported
    } else {
        HypothesisVerdict::Refuted
    };
    FecGainTest {
        verdict,
        kill_threshold: kill,
        eligible_onts: slopes.len(),
        median_abs_slope: Some(median_abs),
        negative_sign_fraction: Some(neg_frac),
        note: match verdict {
            HypothesisVerdict::Supported => {
                "Corrected-FEC rate rides the erfc() waterfall against rx \
                 power with the physical sign and gain: FEC counters resolve \
                 attenuation changes below the DDM quantization floor and \
                 can serve as the strain/thermal amplifier."
                    .to_string()
            }
            _ => "No consistent waterfall coupling between rx and corrected \
                  FEC in this fleet/window: treat FEC counters as vendor or \
                  traffic artifacts here, not as an optical transducer."
                .to_string(),
        },
    }
}

fn linreg_slope(xs: &[f64], ys: &[f64]) -> Option<f64> {
    let n = xs.len() as f64;
    if xs.len() != ys.len() || xs.len() < 2 {
        return None;
    }
    let mx = xs.iter().sum::<f64>() / n;
    let my = ys.iter().sum::<f64>() / n;
    let (mut sxx, mut sxy) = (0.0, 0.0);
    for (&x, &y) in xs.iter().zip(ys) {
        sxx += (x - mx) * (x - mx);
        sxy += (x - mx) * (y - my);
    }
    (sxx > 1e-12).then(|| sxy / sxx)
}

// ---------------------------------------------------------------------------
// T4 — wavelength asymmetry (water vs strain)
// ---------------------------------------------------------------------------

fn test_wavelength_asymmetry(readings: &[OntReading]) -> WavelengthAsymmetryTest {
    // The two-wavelength differential needs BOTH directions per reading:
    // ONT-side downstream rx (1490/1577 nm) and OLT-side upstream rx
    // (1310/1270 nm). `OntReading` carries only the ONT-side value
    // (tx_power_dbm is launch power, APC-held — not a received level, so
    // it cannot stand in for the upstream path loss).
    let _ = readings;
    WavelengthAsymmetryTest {
        verdict: HypothesisVerdict::InsufficientData,
        kill_threshold: "loss events with upstream degradation >= 2x \
                         downstream failing to correlate with precipitation \
                         within 48 h at odds ratio >= 3 => Refuted"
            .to_string(),
        note: "Not measured: current audit readings carry the ONT-side \
               downstream rx only. Unlock by mapping the OLT-side upstream \
               rx per ONT (present in NETCONF collection and in Mission \
               Control exports that include olt-rx columns) into the \
               reading schema; precipitation correlation additionally \
               needs a weather feed."
            .to_string(),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn ts(secs: i64) -> DateTime<Utc> {
        Utc.timestamp_opt(1_750_000_000 + secs, 0).unwrap()
    }

    fn reading(serial: &str, secs: i64) -> OntReading {
        OntReading {
            timestamp: ts(secs),
            serial_number: serial.to_string(),
            pon_port: "1/1/1".to_string(),
            status: OntReadingStatus::Online,
            ..Default::default()
        }
    }

    // ---- T1 -------------------------------------------------------------

    /// Two fixed communities alternate power events; membership repeats, so
    /// the topology must be Supported and both communities recovered.
    #[test]
    fn t1_stable_communities_supported() {
        let com_a = ["A1", "A2", "A3", "A4"];
        let com_b = ["B1", "B2", "B3"];
        let mut readings = Vec::new();
        for e in 0..6 {
            let group: &[&str] = if e % 2 == 0 { &com_a } else { &com_b };
            let base = e * 20_000;
            for s in group {
                readings.push(reading(s, base));
                let mut down = reading(s, base + 60);
                down.status = OntReadingStatus::Offline;
                down.last_down_cause = Some("dying_gasp".to_string());
                readings.push(down);
                // Recover before the next event so the next Online->Offline
                // edge is witnessed again.
                readings.push(reading(s, base + 10_000));
            }
        }
        let t = test_grid_communities(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Supported);
        assert_eq!(t.events_found, 6);
        assert!(t.median_max_jaccard.unwrap() > 0.99);
        assert_eq!(t.communities.len(), 2);
        assert!(t.communities.iter().any(|c| c.len() == 4)); // A
        assert!(t.communities.iter().any(|c| c.len() == 3)); // B
    }

    /// Five events with disjoint random membership => structure refuted.
    #[test]
    fn t1_disjoint_events_refuted() {
        let mut readings = Vec::new();
        for e in 0..5 {
            let base = e * 20_000;
            for k in 0..3 {
                let serial = format!("S{}_{}", e, k); // never repeats
                readings.push(reading(&serial, base));
                let mut down = reading(&serial, base + 60);
                down.status = OntReadingStatus::Offline;
                down.last_down_cause = Some("power_fail".to_string());
                readings.push(down);
            }
        }
        let t = test_grid_communities(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Refuted);
        assert_eq!(t.median_max_jaccard, Some(0.0));
        assert!(t.communities.is_empty());
    }

    /// Fewer than five events, or non-power causes => InsufficientData.
    #[test]
    fn t1_insufficient_events() {
        let mut readings = Vec::new();
        for e in 0..2 {
            for k in 0..3 {
                let serial = format!("S{}", k);
                readings.push(reading(&serial, e * 20_000));
                let mut down = reading(&serial, e * 20_000 + 60);
                down.status = OntReadingStatus::Offline;
                down.last_down_cause = Some("dying_gasp".to_string());
                readings.push(down);
            }
        }
        let t = test_grid_communities(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);

        // Fiber-cut causes are NOT grid samples.
        let mut fiber = Vec::new();
        for e in 0..6 {
            for k in 0..3 {
                let serial = format!("F{}", k);
                fiber.push(reading(&serial, e * 20_000));
                let mut down = reading(&serial, e * 20_000 + 60);
                down.status = OntReadingStatus::Offline;
                down.last_down_cause = Some("fiber_cut".to_string());
                fiber.push(down);
            }
        }
        let t = test_grid_communities(&fiber);
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);
        assert_eq!(t.events_found, 0);
    }

    // ---- T2 -------------------------------------------------------------

    /// 7 days at 15-min cadence. Ambient proxy from 6 ONTs' temperature.
    /// 12 "buried" ONTs lag the ambient crest by 3 h; they must be found
    /// and the hypothesis Supported with a ~3 h median lag.
    #[test]
    fn t2_buried_lag_supported() {
        let w = 2.0 * std::f64::consts::PI / SECS_PER_DAY;
        let mut readings = Vec::new();
        let step = 900i64;
        let n = (7 * SECS_PER_DAY as i64) / step;
        for i in 0..n {
            let t = i * step;
            let ambient = 20.0 + 5.0 * (w * t as f64).cos();
            for a in 0..6 {
                let mut r = reading(&format!("AMB{a}"), t);
                r.temperature_c = Some(ambient);
                r.rx_power_dbm = Some(-20.0); // flat: not a responder
                readings.push(r);
            }
            for b in 0..12 {
                let mut r = reading(&format!("BUR{b}"), t);
                // Optical loss crest 3 h after the ambient crest.
                let lagged = w * (t as f64 - 3.0 * 3600.0);
                r.rx_power_dbm = Some(-21.0 - 0.4 * lagged.cos());
                readings.push(r);
            }
        }
        let t = test_thermal_phase(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Supported);
        assert!(t.responders >= 12);
        let lag = t.median_lag_hours.unwrap();
        assert!((lag - 3.0).abs() < 0.5, "median lag {lag} != ~3h");
    }

    /// Every coherent responder tracks ambient with zero lag => Refuted.
    #[test]
    fn t2_zero_lag_refuted() {
        let w = 2.0 * std::f64::consts::PI / SECS_PER_DAY;
        let mut readings = Vec::new();
        let step = 900i64;
        let n = (7 * SECS_PER_DAY as i64) / step;
        for i in 0..n {
            let t = i * step;
            let ambient = 20.0 + 5.0 * (w * t as f64).cos();
            for a in 0..6 {
                let mut r = reading(&format!("AMB{a}"), t);
                r.temperature_c = Some(ambient);
                readings.push(r);
            }
            for b in 0..12 {
                let mut r = reading(&format!("AER{b}"), t);
                r.rx_power_dbm = Some(-21.0 - 0.4 * (w * t as f64).cos());
                readings.push(r);
            }
        }
        let t = test_thermal_phase(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Refuted);
        assert!(t.zero_lag_fraction.unwrap() >= 0.95);
    }

    /// A responder whose octet rate cycles in phase with its optical cycle
    /// is self-heating (traffic), must be excluded and counted.
    #[test]
    fn t2_traffic_confound_excluded() {
        let w = 2.0 * std::f64::consts::PI / SECS_PER_DAY;
        let mut readings = Vec::new();
        let step = 900i64;
        let n = (7 * SECS_PER_DAY as i64) / step;
        let mut octets: u64 = 0;
        for i in 0..n {
            let t = i * step;
            let ambient = 20.0 + 5.0 * (w * t as f64).cos();
            for a in 0..6 {
                let mut r = reading(&format!("AMB{a}"), t);
                r.temperature_c = Some(ambient);
                readings.push(r);
            }
            // Optical cycle AND octet-rate cycle share the same phase.
            let rate = (1_000_000.0 * (1.0 + (w * t as f64).cos())) as u64;
            octets += rate;
            let mut r = reading("TRAFFIC0", t);
            r.rx_power_dbm = Some(-21.0 - 0.4 * (w * t as f64).cos());
            r.in_octets = Some(octets);
            r.out_octets = Some(0);
            readings.push(r);
        }
        let t = test_thermal_phase(&readings);
        assert_eq!(t.traffic_confounded, 1);
        assert_eq!(t.responders, 0); // the only responder was confounded
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);
    }

    /// No temperature anywhere => no ambient proxy => InsufficientData.
    #[test]
    fn t2_no_ambient_proxy() {
        let readings: Vec<OntReading> =
            (0..100).map(|i| reading("X", i * 900)).collect();
        let t = test_thermal_phase(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);
    }

    // ---- T3 -------------------------------------------------------------

    /// Corrected-FEC rate follows the waterfall: one decade per dB of rx
    /// loss. Slope must be recovered (~ -1.0) and the claim Supported.
    #[test]
    fn t3_waterfall_supported() {
        let mut readings = Vec::new();
        for o in 0..6 {
            let serial = format!("W{o}");
            let mut fec: u64 = 0;
            for i in 0..24i64 {
                // rx ramps -18 -> -19.5 dB across the window.
                let rx = -18.0 - 1.5 * (i as f64) / 23.0;
                // rate per hour = 10^(2 - 1.0*(rx + 18)) => slope -1.0.
                let rate = 10f64.powf(2.0 - 1.0 * (rx + 18.0));
                fec += rate as u64;
                let mut r = reading(&serial, i * 3600);
                r.rx_power_dbm = Some(rx);
                r.fec_corrected = Some(fec);
                readings.push(r);
            }
        }
        let t = test_fec_gain(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Supported);
        assert_eq!(t.eligible_onts, 6);
        let slope = t.median_abs_slope.unwrap();
        assert!((slope - 1.0).abs() < 0.35, "median |slope| {slope} != ~1.0");
        assert!(t.negative_sign_fraction.unwrap() >= 0.99);
    }

    /// FEC counts independent of rx => no waterfall coupling => Refuted.
    #[test]
    fn t3_flat_fec_refuted() {
        let mut readings = Vec::new();
        for o in 0..6 {
            let serial = format!("F{o}");
            let mut fec: u64 = 0;
            for i in 0..24i64 {
                let rx = -18.0 - 1.5 * (i as f64) / 23.0;
                fec += 100; // constant rate regardless of rx
                let mut r = reading(&serial, i * 3600);
                r.rx_power_dbm = Some(rx);
                r.fec_corrected = Some(fec);
                readings.push(r);
            }
        }
        let t = test_fec_gain(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::Refuted);
        assert!(t.median_abs_slope.unwrap() < 0.05);
    }

    /// Stable rx (< 0.5 dB range) is not identifiable => InsufficientData.
    #[test]
    fn t3_no_rx_wander_insufficient() {
        let mut readings = Vec::new();
        for o in 0..6 {
            let serial = format!("S{o}");
            let mut fec: u64 = 0;
            for i in 0..24i64 {
                fec += 100;
                let mut r = reading(&serial, i * 3600);
                r.rx_power_dbm = Some(-18.0); // dead flat
                r.fec_corrected = Some(fec);
                readings.push(r);
            }
        }
        let t = test_fec_gain(&readings);
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);
    }

    // ---- T4 / integration ------------------------------------------------

    /// T4 is honestly not-measured until the upstream rx field exists.
    #[test]
    fn t4_always_insufficient_for_now() {
        let t = test_wavelength_asymmetry(&[]);
        assert_eq!(t.verdict, HypothesisVerdict::InsufficientData);
        assert!(t.note.contains("Not measured"));
    }

    /// Empty input: all four tests must return InsufficientData, no panics,
    /// and the report must be marked experimental.
    #[test]
    fn dqt_empty_input_is_insufficient_everywhere() {
        let report = run_dqt(&[]);
        assert!(report.experimental);
        assert_eq!(report.grid.verdict, HypothesisVerdict::InsufficientData);
        assert_eq!(report.thermal.verdict, HypothesisVerdict::InsufficientData);
        assert_eq!(
            report.fec_amplifier.verdict,
            HypothesisVerdict::InsufficientData
        );
        assert_eq!(
            report.wavelength.verdict,
            HypothesisVerdict::InsufficientData
        );
        // The report must state its bandwidth honesty note.
        assert!(report.note.contains("not an acoustic"));
    }

    /// Diurnal fit sanity: recovers amplitude, phase and high R^2 on a
    /// clean tone, irregular sampling included.
    #[test]
    fn diurnal_fit_recovers_tone() {
        let w = 2.0 * std::f64::consts::PI / SECS_PER_DAY;
        let phase_in = 1.2f64;
        let times: Vec<f64> = (0..300)
            .map(|i| i as f64 * 1234.5) // irregular-ish, ~4 days
            .collect();
        let vals: Vec<f64> = times
            .iter()
            .map(|t| 5.0 + 2.0 * (w * t - phase_in).cos())
            .collect();
        let (amp, phase, r2) = diurnal_fit(&times, &vals).unwrap();
        assert!((amp - 2.0).abs() < 0.05);
        assert!((phase - phase_in).abs() < 0.05);
        assert!(r2 > 0.99);
    }
}
