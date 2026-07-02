// SPDX-License-Identifier: Apache-2.0
// Passive Rogue-ONT Scoring (ITU-T G.Sup49 symptoms)
//
// A rogue ONT transmits outside its assigned upstream timeslot and corrupts
// its NEIGHBOURS' upstream bursts — the transmitter itself often looks fine
// while everyone else on the PON suffers. Vendors ship active detection
// commands (per-ONT mute-and-test); this module builds the passive case
// from telemetry alone so an operator knows WHEN to run them.
//
// Passive signature scored per PON port:
//   MULTIPLE ONTs simultaneously show BIP/FEC error bursts or flapping,
//   WITHOUT correlated rx-power drops (rules out fibre/splitter attenuation
//   as the common cause) and WITHOUT dying gasps (rules out power events),
//   while one candidate ONT deviates — e.g. its own counters stay clean
//   while neighbours suffer, or it shows an extreme bias-current / tx-power
//   anomaly (a stressed or stuck-on laser).
//
// HONESTY: this is a HYPOTHESIS generator, not a verdict. Passive telemetry
// cannot prove which ONT transmits out-of-slot — only vendor-native rogue
// detection or physical bisection can. Findings therefore require >= 3
// victims corroborated by >= 2 independent signal types before anything is
// emitted, and every finding names the confirmation step.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeSet, HashMap};

use super::fec_health::counter_deltas;
use super::{OntReading, OntReadingStatus};

/// A multi-victim upstream-integrity event on a PON port with ranked
/// rogue-ONT candidates. A hypothesis, not a verdict.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoguePortFinding {
    pub olt: String,
    pub pon_port: String,
    pub victim_count: u32,
    pub window_start: DateTime<Utc>,
    pub window_end: DateTime<Utc>,
    /// Human-readable port-level evidence (victim breakdown, ruled-out
    /// common causes).
    pub evidence: Vec<String>,
    /// Candidate culprits ranked by score, best first. May be empty: a
    /// multi-victim event with no deviant ONT is still worth investigating.
    pub candidates: Vec<RogueCandidate>,
    pub confidence: RogueConfidence,
    /// The vendor-native confirmation step — passive scoring cannot prove
    /// a rogue on its own.
    pub recommended_action: String,
}

/// A candidate culprit ONT on a rogue-suspect port.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RogueCandidate {
    pub serial_number: String,
    pub score: f64,
    pub evidence: Vec<String>,
}

/// Confidence that the port event is a rogue ONT (vs an unexplained
/// multi-victim event).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RogueConfidence {
    Low,
    Medium,
    High,
}

// ---------------------------------------------------------------------------
// Gating constants
// ---------------------------------------------------------------------------

/// Minimum simultaneous victims before a port event exists at all. One or
/// two suffering ONTs are individually explainable (own optics, own patch
/// cords); the G.Sup49 rogue symptom is specifically MULTI-ONT corruption.
const MIN_VICTIMS: usize = 3;

/// Minimum independent signal types (BIP burst / FEC burst / flapping)
/// across the victims. A single shared symptom can have a benign common
/// cause (e.g. an OLT port reset flaps everyone); two independent symptom
/// families corroborate real upstream corruption.
const MIN_SIGNAL_TYPES: usize = 2;

/// BIP-8 error total across the window that counts as a burst. Out-of-slot
/// collisions register hundreds to thousands of parity violations per
/// event; healthy links log single digits from isolated noise hits.
const BIP_BURST_MIN: u64 = 100;

/// Corrected-FEC rate (codewords/hour) that counts as a burst: 10x the
/// fec_health trending floor — burst territory, not slow-trend territory.
const FEC_BURST_RATE_PER_HOUR: f64 = 1000.0;

/// Minimum online/offline transitions (without dying gasp) for a victim's
/// flapping signal. Looser than the standalone flapping module's gate (4)
/// because here each flapper is corroborated by >= 2 other victims on the
/// same port — the cross-ONT correlation is the statistic.
const MIN_FLAP_TRANSITIONS: usize = 2;

/// Median rx drop (first half vs second half of the window) that marks an
/// ONT's suffering as attenuation-explained. 1.0 dB is >3x the 0.3 dB DDM
/// resolution floor — a real optical move, not sensor noise.
const RX_DROP_DB: f64 = 1.0;

/// Minimum plausible rx samples before an rx drop is assessed at all.
const MIN_RX_SAMPLES_FOR_DROP: usize = 6;

/// If this fraction (or more) of suffering ONTs shows an rx drop, the port
/// event is a fibre/splitter problem, not a rogue — emit nothing here and
/// let the optical modules own it.
const RX_DROP_SUPPRESS_FRACTION: f64 = 0.5;

/// Tx launch power above the port median that counts as a transmitter
/// anomaly. ONTs of one class on one port cluster within ~1 dB; +2.0 dB is
/// outside normal spread and consistent with a stuck-high laser.
const TX_ANOMALY_DB: f64 = 2.0;

/// Bias-current anomaly: >= 1.5x the port median AND >= 5 mA above it.
/// Bias climbs as a laser degrades; a strongly elevated bias marks the
/// stressed/failing transmitter that rogue behaviour typically comes from.
const BIAS_ANOMALY_FACTOR: f64 = 1.5;
const BIAS_ANOMALY_MIN_DELTA_MA: f64 = 5.0;

/// Minimum peers with tx/bias data before a port median is trusted for
/// anomaly comparison.
const MIN_PEER_SAMPLES: usize = 5;

/// Maximum candidates listed per finding.
const MAX_CANDIDATES: usize = 3;

/// Victim signal families (independence corroboration).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum SignalType {
    BipBurst,
    FecBurst,
    Flapping,
}

impl std::fmt::Display for SignalType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::BipBurst => write!(f, "BIP error burst"),
            Self::FecBurst => write!(f, "FEC error burst"),
            Self::Flapping => write!(f, "flapping (no dying gasp)"),
        }
    }
}

/// Per-ONT profile over the analysis window.
struct OntProfile {
    serial: String,
    signals: Vec<SignalType>,
    dying_gasp: bool,
    rx_dropped: bool,
    /// Had BIP or FEC counter data at all (a clean profile only counts as
    /// "quiet" evidence when the counters were actually observed).
    has_error_counters: bool,
    transitions: usize,
    mean_tx: Option<f64>,
    mean_bias: Option<f64>,
}

/// Score all PON ports for passive rogue-ONT symptoms.
pub fn detect_rogue_onts(readings: &[OntReading]) -> Vec<RoguePortFinding> {
    let mut by_port: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_port.entry(&r.pon_port).or_default().push(r);
    }

    let mut findings: Vec<RoguePortFinding> = Vec::new();

    for (port, port_readings) in by_port {
        let mut by_serial: HashMap<&str, Vec<&OntReading>> = HashMap::new();
        for r in &port_readings {
            by_serial.entry(&r.serial_number).or_default().push(r);
        }

        let profiles: Vec<OntProfile> = by_serial
            .into_iter()
            .map(|(serial, mut sorted)| {
                sorted.sort_by_key(|r| r.timestamp);
                profile_ont(serial, &sorted)
            })
            .collect();

        // Victims: symptomatic WITHOUT dying gasp and WITHOUT an rx drop.
        // Sufferers with an rx drop are attenuation-explained; if they
        // dominate, the whole event is a fibre problem, not a rogue.
        let sufferers: Vec<&OntProfile> = profiles
            .iter()
            .filter(|p| !p.signals.is_empty() && !p.dying_gasp)
            .collect();
        let rx_dropped_sufferers = sufferers.iter().filter(|p| p.rx_dropped).count();
        let victims: Vec<&&OntProfile> =
            sufferers.iter().filter(|p| !p.rx_dropped).collect();

        if victims.len() < MIN_VICTIMS {
            continue;
        }
        if !sufferers.is_empty()
            && rx_dropped_sufferers as f64 / sufferers.len() as f64 >= RX_DROP_SUPPRESS_FRACTION
        {
            // Correlated rx drops => optical attenuation is the common
            // cause. That is a fibre/splitter fault, owned elsewhere.
            continue;
        }

        let signal_types: BTreeSet<SignalType> = victims
            .iter()
            .flat_map(|p| p.signals.iter().copied())
            .collect();
        if signal_types.len() < MIN_SIGNAL_TYPES {
            continue;
        }

        // Port-level evidence.
        let mut type_counts: Vec<String> = Vec::new();
        for t in &signal_types {
            let n = victims.iter().filter(|p| p.signals.contains(t)).count();
            type_counts.push(format!("{}x {}", n, t));
        }
        let mut evidence = vec![
            format!(
                "{} ONTs on port {} simultaneously showing upstream-integrity symptoms: {}",
                victims.len(),
                port,
                type_counts.join(", ")
            ),
            format!(
                "No correlated rx-power drop among victims ({} of {} sufferers show \
                 >= {:.1} dB drop) — shared attenuation ruled out as common cause",
                rx_dropped_sufferers,
                sufferers.len(),
                RX_DROP_DB
            ),
            "No dying-gasp events among victims — shared power failure ruled out".to_string(),
        ];

        // Rank candidate culprits.
        let victim_serials: BTreeSet<&str> =
            victims.iter().map(|p| p.serial.as_str()).collect();
        let candidates = rank_candidates(&profiles, &victim_serials, &mut evidence);

        let confidence = if victims.len() >= 4
            && candidates
                .first()
                .map(|c| c.evidence.len() >= 2)
                .unwrap_or(false)
        {
            RogueConfidence::High
        } else if victims.len() >= 4 || !candidates.is_empty() {
            RogueConfidence::Medium
        } else {
            RogueConfidence::Low
        };

        let window_start = port_readings.iter().map(|r| r.timestamp).min().unwrap();
        let window_end = port_readings.iter().map(|r| r.timestamp).max().unwrap();

        findings.push(RoguePortFinding {
            olt: extract_olt_id(port),
            pon_port: port.to_string(),
            victim_count: victims.len() as u32,
            window_start,
            window_end,
            evidence,
            candidates,
            confidence,
            recommended_action: "HYPOTHESIS ONLY — confirm via the OLT's vendor-native \
                rogue-ONU detection command, or by port-level bisection (disable suspect \
                ONTs one at a time) during a maintenance window. Passive telemetry cannot \
                prove which ONT transmits out-of-slot."
                .to_string(),
        });
    }

    // Deterministic ordering: highest confidence, then most victims.
    findings.sort_by(|a, b| {
        b.confidence
            .cmp(&a.confidence)
            .then(b.victim_count.cmp(&a.victim_count))
            .then(a.pon_port.cmp(&b.pon_port))
    });
    findings
}

/// Build the per-ONT window profile: signals, exclusions, tx/bias means.
fn profile_ont(serial: &str, sorted: &[&OntReading]) -> OntProfile {
    let bip = counter_deltas(sorted, |r| r.bip_errors);
    let fec_corr = counter_deltas(sorted, |r| r.fec_corrected);
    let fec_unc = counter_deltas(sorted, |r| r.fec_uncorrected);

    let bip_total: u64 = bip.iter().map(|d| d.delta).sum();
    let corr_total: u64 = fec_corr.iter().map(|d| d.delta).sum();
    let corr_hours: f64 = fec_corr.iter().map(|d| d.hours).sum();
    let corr_rate = if corr_hours > 0.0 {
        corr_total as f64 / corr_hours
    } else {
        0.0
    };
    let unc_total: u64 = fec_unc.iter().map(|d| d.delta).sum();

    // Transitions (Unknown readings are polling gaps, not observations) and
    // dying-gasp detection on offline readings.
    let observed: Vec<&&OntReading> = sorted
        .iter()
        .filter(|r| r.status != OntReadingStatus::Unknown)
        .collect();
    let mut transitions = 0usize;
    let mut dying_gasp = false;
    for w in observed.windows(2) {
        if w[0].status != w[1].status {
            transitions += 1;
        }
    }
    for r in &observed {
        if r.status == OntReadingStatus::Offline {
            if let Some(cause) = &r.last_down_cause {
                let c = cause.to_lowercase();
                if c.contains("dying_gasp") || c.contains("dying gasp") || c.contains("power") {
                    dying_gasp = true;
                }
            }
        }
    }

    let mut signals = Vec::new();
    if bip_total >= BIP_BURST_MIN {
        signals.push(SignalType::BipBurst);
    }
    if unc_total > 0 || corr_rate >= FEC_BURST_RATE_PER_HOUR {
        signals.push(SignalType::FecBurst);
    }
    if transitions >= MIN_FLAP_TRANSITIONS && !dying_gasp {
        signals.push(SignalType::Flapping);
    }

    // Rx drop: median of first half vs second half of plausible online rx.
    let rx: Vec<f64> = sorted
        .iter()
        .filter(|r| r.status == OntReadingStatus::Online)
        .filter_map(|r| super::sane_rx(r))
        .collect();
    let rx_dropped = if rx.len() >= MIN_RX_SAMPLES_FOR_DROP {
        let (first, second) = rx.split_at(rx.len() / 2);
        median(first) - median(second) >= RX_DROP_DB
    } else {
        false
    };

    let tx: Vec<f64> = sorted.iter().filter_map(|r| r.tx_power_dbm).collect();
    let bias: Vec<f64> = sorted.iter().filter_map(|r| r.bias_current_ma).collect();

    OntProfile {
        serial: serial.to_string(),
        signals,
        dying_gasp,
        rx_dropped,
        has_error_counters: sorted
            .iter()
            .any(|r| r.bip_errors.is_some() || r.fec_corrected.is_some()),
        transitions,
        mean_tx: mean(&tx),
        mean_bias: mean(&bias),
    }
}

/// Rank candidate culprits on a firing port. Deviation evidence:
///   - clean counters + fully online while >= MIN_VICTIMS neighbours suffer
///     (the rogue's own upstream is fine — it IS the transmitter)
///   - extreme bias-current anomaly vs port median (stressed laser)
///   - extreme tx-power anomaly vs port median (stuck-high laser)
fn rank_candidates(
    profiles: &[OntProfile],
    victim_serials: &BTreeSet<&str>,
    port_evidence: &mut Vec<String>,
) -> Vec<RogueCandidate> {
    let tx_values: Vec<f64> = profiles.iter().filter_map(|p| p.mean_tx).collect();
    let bias_values: Vec<f64> = profiles.iter().filter_map(|p| p.mean_bias).collect();
    let tx_median = (tx_values.len() >= MIN_PEER_SAMPLES).then(|| median(&tx_values));
    let bias_median = (bias_values.len() >= MIN_PEER_SAMPLES).then(|| median(&bias_values));

    let mut candidates: Vec<RogueCandidate> = Vec::new();
    for p in profiles {
        if victim_serials.contains(p.serial.as_str()) {
            continue; // a victim is corrupted BY the rogue, not the rogue itself
        }
        let mut score = 0.0;
        let mut evidence = Vec::new();

        if p.has_error_counters
            && p.signals.is_empty()
            && p.transitions == 0
            && !p.rx_dropped
            && !p.dying_gasp
        {
            score += 1.0;
            evidence.push(format!(
                "{}: own error counters clean and fully online while {} neighbours \
                 suffered — consistent with being the out-of-slot transmitter",
                p.serial,
                victim_serials.len()
            ));
        }
        if let (Some(bias), Some(med)) = (p.mean_bias, bias_median) {
            if bias >= med * BIAS_ANOMALY_FACTOR && bias - med >= BIAS_ANOMALY_MIN_DELTA_MA {
                score += 1.5;
                evidence.push(format!(
                    "{}: laser bias current {:.1} mA vs port median {:.1} mA \
                     (>= {:.1}x + {:.0} mA) — stressed/failing transmitter",
                    p.serial, bias, med, BIAS_ANOMALY_FACTOR, BIAS_ANOMALY_MIN_DELTA_MA
                ));
            }
        }
        if let (Some(tx), Some(med)) = (p.mean_tx, tx_median) {
            if tx - med >= TX_ANOMALY_DB {
                score += 1.5;
                evidence.push(format!(
                    "{}: tx launch power {:.1} dBm is {:.1} dB above port median \
                     {:.1} dBm — outside normal per-port spread",
                    p.serial,
                    tx,
                    tx - med,
                    med
                ));
            }
        }

        if score > 0.0 {
            candidates.push(RogueCandidate {
                serial_number: p.serial.clone(),
                score,
                evidence,
            });
        }
    }

    candidates.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.serial_number.cmp(&b.serial_number))
    });
    candidates.truncate(MAX_CANDIDATES);

    if candidates.is_empty() {
        port_evidence.push(
            "No deviant candidate identified — multi-victim upstream event with \
             unknown source; bisection required"
                .to_string(),
        );
    }
    candidates
}

fn mean(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        None
    } else {
        Some(values.iter().sum::<f64>() / values.len() as f64)
    }
}

fn median(values: &[f64]) -> f64 {
    let mut v = values.to_vec();
    v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    v[v.len() / 2]
}

/// Extract OLT identifier from a port string ("OLT01/0/1/0" -> "OLT01").
fn extract_olt_id(port: &str) -> String {
    let parts: Vec<&str> = port.split('/').collect();
    if parts.len() >= 3 {
        parts[..parts.len() - 2].join("/")
    } else {
        port.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn t0() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 2, 1, 0, 0, 0).unwrap()
    }

    fn reading(serial: &str, i: usize) -> OntReading {
        OntReading {
            timestamp: t0() + Duration::hours(6 * i as i64),
            serial_number: serial.into(),
            pon_port: "OLT01/0/1/0".into(),
            rx_power_dbm: Some(-21.0),
            tx_power_dbm: Some(2.5),
            status: OntReadingStatus::Online,
            distance_meters: Some(1000),
            eth_speed_mbps: Some(1000),
            last_down_cause: None,
            bias_current_ma: Some(12.0),
            bip_errors: Some(0),
            fec_corrected: Some(0),
            ..Default::default()
        }
    }

    const N: usize = 12; // 3 days at 6h cadence

    /// Healthy quiet ONT: clean counters, online throughout.
    fn quiet_ont(serial: &str) -> Vec<OntReading> {
        (0..N).map(|i| reading(serial, i)).collect()
    }

    /// Victim with a BIP error burst (cumulative counter jumps mid-window).
    fn bip_victim(serial: &str) -> Vec<OntReading> {
        (0..N)
            .map(|i| {
                let mut r = reading(serial, i);
                r.bip_errors = Some(if i < N / 2 { 2 } else { 600 });
                r
            })
            .collect()
    }

    /// Victim flapping without dying gasp, stable rx while online.
    fn flap_victim(serial: &str) -> Vec<OntReading> {
        (0..N)
            .map(|i| {
                let mut r = reading(serial, i);
                if i % 3 == 2 {
                    r.status = OntReadingStatus::Offline;
                    r.rx_power_dbm = None;
                }
                r
            })
            .collect()
    }

    /// The deviant candidate: clean counters, online, but tx and bias far
    /// above port norms.
    fn deviant_ont(serial: &str) -> Vec<OntReading> {
        (0..N)
            .map(|i| {
                let mut r = reading(serial, i);
                r.tx_power_dbm = Some(5.5); // +3 dB above peers
                r.bias_current_ma = Some(45.0); // ~3.7x port median
                r
            })
            .collect()
    }

    #[test]
    fn test_four_victim_port_with_deviant_candidate_fires_ranked() {
        let mut readings = Vec::new();
        readings.extend(bip_victim("VIC-B1"));
        readings.extend(bip_victim("VIC-B2"));
        readings.extend(flap_victim("VIC-F1"));
        readings.extend(flap_victim("VIC-F2"));
        readings.extend(deviant_ont("ROGUE-1"));
        readings.extend(quiet_ont("OK-1"));
        readings.extend(quiet_ont("OK-2"));
        readings.extend(quiet_ont("OK-3"));

        let findings = detect_rogue_onts(&readings);
        assert_eq!(findings.len(), 1, "4 victims + 2 signal types must fire");
        let f = &findings[0];
        assert_eq!(f.pon_port, "OLT01/0/1/0");
        assert_eq!(f.olt, "OLT01/0"); // same segment-stripping as sfp_health
        assert_eq!(f.victim_count, 4);
        assert_eq!(f.confidence, RogueConfidence::High);
        assert!(!f.candidates.is_empty());
        assert_eq!(
            f.candidates[0].serial_number, "ROGUE-1",
            "deviant ONT must rank first: {:?}",
            f.candidates
        );
        assert!(
            f.candidates[0].score > f.candidates.get(1).map(|c| c.score).unwrap_or(0.0),
            "ranking must be strict"
        );
        assert!(f.candidates[0].evidence.len() >= 2, "quiet + tx + bias evidence");
        assert!(f.recommended_action.contains("rogue-ONU detection"));
        assert!(f.recommended_action.contains("bisection"));
        assert!(f.evidence.iter().any(|e| e.contains("BIP error burst")));
        assert!(f.evidence.iter().any(|e| e.contains("flapping")));
    }

    #[test]
    fn test_two_victim_port_emits_nothing() {
        let mut readings = Vec::new();
        readings.extend(bip_victim("VIC-B1"));
        readings.extend(flap_victim("VIC-F1"));
        readings.extend(deviant_ont("ROGUE-1"));
        readings.extend(quiet_ont("OK-1"));
        readings.extend(quiet_ont("OK-2"));

        let findings = detect_rogue_onts(&readings);
        assert!(
            findings.is_empty(),
            "2 victims are individually explainable — below the multi-victim gate"
        );
    }

    #[test]
    fn test_correlated_rx_drop_port_is_fibre_not_rogue() {
        // Same 4 victims, but each victim's rx falls ~2 dB mid-window —
        // shared attenuation explains the errors: fibre problem, not rogue.
        let mut readings = Vec::new();
        for serial in ["VIC-B1", "VIC-B2", "VIC-B3", "VIC-B4"] {
            let mut onts = bip_victim(serial);
            for (i, r) in onts.iter_mut().enumerate() {
                if r.rx_power_dbm.is_some() {
                    r.rx_power_dbm = Some(if i < N / 2 { -21.0 } else { -23.0 });
                }
            }
            readings.extend(onts);
        }
        readings.extend(quiet_ont("OK-1"));
        readings.extend(quiet_ont("OK-2"));

        let findings = detect_rogue_onts(&readings);
        assert!(
            findings.is_empty(),
            "correlated rx drops = attenuation as common cause; not a rogue event"
        );
    }

    #[test]
    fn test_dying_gasp_victims_are_power_events_not_rogue() {
        let mut readings = Vec::new();
        for serial in ["VIC-F1", "VIC-F2", "VIC-F3", "VIC-F4"] {
            let mut onts = flap_victim(serial);
            for (i, r) in onts.iter_mut().enumerate() {
                if r.status == OntReadingStatus::Offline {
                    r.last_down_cause = Some("dying_gasp".into());
                }
                // give them a real BIP burst too — must still be excluded
                r.bip_errors = Some(if i < N / 2 { 2 } else { 600 });
            }
            readings.extend(onts);
        }
        readings.extend(quiet_ont("OK-1"));

        let findings = detect_rogue_onts(&readings);
        assert!(
            findings.is_empty(),
            "dying gasps mark power events; those ONTs are not rogue victims"
        );
    }

    #[test]
    fn test_single_signal_type_insufficient() {
        // 4 flapping victims but no error-counter corroboration at all.
        let mut readings = Vec::new();
        for serial in ["VIC-F1", "VIC-F2", "VIC-F3", "VIC-F4"] {
            let mut onts = flap_victim(serial);
            for r in onts.iter_mut() {
                r.bip_errors = Some(0);
                r.fec_corrected = Some(0);
            }
            readings.extend(onts);
        }
        readings.extend(quiet_ont("OK-1"));

        let findings = detect_rogue_onts(&readings);
        assert!(
            findings.is_empty(),
            "one signal family alone (all flapping) can be a benign common cause"
        );
    }

    #[test]
    fn test_no_deviant_candidate_still_fires_low_confidence_noted() {
        // Multi-victim event, but every non-victim looks normal AND has no
        // quiet-counter evidence (no counters observed at all).
        let mut readings = Vec::new();
        readings.extend(bip_victim("VIC-B1"));
        readings.extend(bip_victim("VIC-B2"));
        readings.extend(flap_victim("VIC-F1"));
        for serial in ["OK-1", "OK-2"] {
            let onts: Vec<OntReading> = (0..N)
                .map(|i| {
                    let mut r = reading(serial, i);
                    r.bip_errors = None;
                    r.fec_corrected = None;
                    r.bias_current_ma = None;
                    r
                })
                .collect();
            readings.extend(onts);
        }

        let findings = detect_rogue_onts(&readings);
        assert_eq!(findings.len(), 1);
        let f = &findings[0];
        assert_eq!(f.victim_count, 3);
        assert!(f.candidates.is_empty(), "no deviation evidence => no candidates");
        assert_eq!(f.confidence, RogueConfidence::Low);
        assert!(f.evidence.iter().any(|e| e.contains("No deviant candidate")));
    }
}
