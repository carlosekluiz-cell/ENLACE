// SPDX-License-Identifier: Apache-2.0
// Mass-offline pattern detector — transition-based, stateful incident tracking.
//
// Semantics:
//   - An ONT only counts toward a fault if it was seen ONLINE in a previous
//     cycle and transitioned to offline within `time_window_seconds`.
//   - Chronically-offline ONTs (never seen online since agent start) never
//     trigger fault events.
//   - The first poll cycle after startup establishes a baseline only.
//   - Incidents are tracked in an active map keyed by (olt, pon_port):
//     ONE Open update when an incident starts, ONE Resolve update when the
//     port recovers. Nothing is re-emitted while an incident stays open.
//   - If multiple PON ports on the same OLT open incidents in the same cycle,
//     they are rolled up into a single OLT-level (feeder) incident.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use crate::config::FaultDetectionConfig;
use crate::vendors::{OntData, OntStatus, UNKNOWN_PON_PORT};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultEvent {
    pub timestamp: DateTime<Utc>,
    pub pon_port: String,
    pub olt_id: String,
    pub severity: String,
    pub fault_type: FaultType,
    pub affected_onts: Vec<AffectedOnt>,
    pub detection_latency_seconds: u64,
}

/// Fault classification based on dying gasp differentiation.
/// - FibreCut: ONTs went offline without sending dying gasp → physical fibre break
/// - PowerOutage: ONTs sent dying gasp before going offline → power loss at premises/area
/// - Mixed: Some ONTs sent dying gasp, others didn't → partial power + possible break
///
/// Classification is ratio-based, not exact-zero: real events are noisy.
/// Dying gasps are a single burst on a contended upstream and get lost, and
/// UPS-backed ONTs mask power loss by staying up until the battery dies.
/// See `POWER_GASP_RATIO_MIN` / `FIBRE_GASP_RATIO_MAX` for the thresholds
/// and `ClassificationEvidence` for the evidence emitted alongside.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FaultType {
    FibreCut,
    PowerOutage,
    Mixed,
}

/// Minimum dying-gasp ratio to classify PowerOutage. A clear majority of
/// gasps is strong evidence of premises/area power loss even when some
/// gasps are lost in upstream contention (field experience: 60% is a safe
/// majority; exact-100% almost never happens on real PONs).
pub const POWER_GASP_RATIO_MIN: f64 = 0.6;

/// Maximum dying-gasp ratio to classify FibreCut. A cut severs the fibre
/// while ONTs keep power, so almost nothing gasps — but allow up to 10%
/// stragglers (a co-incident premises power blip, or vendors that put
/// "power" strings in unrelated last-down-cause fields).
pub const FIBRE_GASP_RATIO_MAX: f64 = 0.1;

/// Minimum affected ONTs before a FibreCut call is made from the gasp
/// ratio. Below 5 members the ratio is too coarse (1 gasp in 4 = 0.25) to
/// distinguish a cut from coincidence; such incidents are labelled Mixed.
pub const FIBRE_MIN_AFFECTED: usize = 5;

/// Ratio at which a PowerOutage call is considered strong evidence
/// (comfortably above `POWER_GASP_RATIO_MIN`, not scraping the boundary).
pub const POWER_STRONG_GASP_RATIO: f64 = 0.8;

/// Ratio at which a FibreCut call is considered strong evidence (half of
/// `FIBRE_GASP_RATIO_MAX`).
pub const FIBRE_STRONG_GASP_RATIO: f64 = 0.05;

/// A fibre cut drops every ONT on the segment within 1-2 poll cycles.
/// Transition spread beyond this many observed poll cycles means the
/// incident built up gradually (attrition/degradation), which contradicts
/// a cut and downgrades classification confidence.
pub const SIMULTANEOUS_MAX_CYCLES: i32 = 2;

/// Minimum distinct OLTs opening PowerOutage-classified incidents in one
/// detector pass before an area power event is suspected (see
/// [`correlate_cycle`]). Two independent OLTs losing power-classified
/// populations at once is grid, not N coincidental premises events.
pub const AREA_POWER_MIN_OLTS: usize = 2;

/// Temporal tightness of an incident's member transitions.
#[derive(Debug, Clone, Copy, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OnsetPattern {
    /// First-to-last transition spread ≤ `SIMULTANEOUS_MAX_CYCLES` poll
    /// cycles — consistent with a single physical event.
    #[default]
    Simultaneous,
    /// Members dropped over more than `SIMULTANEOUS_MAX_CYCLES` cycles —
    /// gradual attrition, inconsistent with a clean cut.
    Staggered,
}

impl std::fmt::Display for OnsetPattern {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Simultaneous => write!(f, "simultaneous"),
            Self::Staggered => write!(f, "staggered"),
        }
    }
}

/// Confidence in the `fault_type` call, derived from ratio distance from
/// threshold × onset tightness (see `confidence_for`). Defaults to Low —
/// never claim confidence that was not computed.
#[derive(Debug, Clone, Copy, Default, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ClassificationConfidence {
    High,
    Medium,
    #[default]
    Low,
}

impl std::fmt::Display for ClassificationConfidence {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::High => write!(f, "high"),
            Self::Medium => write!(f, "medium"),
            Self::Low => write!(f, "low"),
        }
    }
}

/// The evidence behind a `fault_type` call, emitted on every incident
/// update so webhooks/ES receivers can show WHY the classifier decided —
/// never just the label.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ClassificationEvidence {
    /// Members that sent a dying gasp at their offline transition.
    pub dying_gasp_count: usize,
    /// Members that went dark without a gasp.
    pub hard_offline_count: usize,
    /// dying_gasp_count / member count at open time.
    pub dying_gasp_ratio: f64,
    pub onset: OnsetPattern,
    /// First-to-last offline-transition spread across members at open time.
    pub onset_spread_seconds: u64,
    pub confidence: ClassificationConfidence,
    /// Human-readable one-liner with ratio, counts, onset and confidence.
    pub summary: String,
}

impl std::fmt::Display for FaultType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::FibreCut => write!(f, "fibre_cut"),
            Self::PowerOutage => write!(f, "power_outage"),
            Self::Mixed => write!(f, "mixed"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectedOnt {
    pub serial_number: String,
    pub distance_meters: Option<u32>,
    pub last_rx_dbm: Option<f64>,
    /// True if this ONT sent a dying gasp (power failure)
    pub had_dying_gasp: bool,
}

/// Whether an incident update opens or closes an incident.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum IncidentAction {
    Open,
    Resolve,
}

impl std::fmt::Display for IncidentAction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Open => write!(f, "open"),
            Self::Resolve => write!(f, "resolve"),
        }
    }
}

/// Scope of an incident: a single PON port, or a multi-port (feeder/OLT-level) fault.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum IncidentScope {
    Port,
    Olt,
}

/// A single incident lifecycle update: emitted once when an incident opens
/// and once when it resolves. The stable `incident_id` is the dedup key for
/// downstream receivers (PagerDuty `dedup_key`, generic `incident_id`).
#[derive(Debug, Clone, Serialize)]
pub struct IncidentUpdate {
    pub action: IncidentAction,
    /// Stable per-incident dedup key: "{olt}:{pon_port}:{opened_at}" for
    /// port-scope incidents, "{olt}:olt:{opened_at}" for OLT-level rollups.
    pub incident_id: String,
    pub scope: IncidentScope,
    pub opened_at: DateTime<Utc>,
    pub resolved_at: Option<DateTime<Utc>>,
    /// PON ports involved (single entry for port-scope incidents)
    pub ports: Vec<String>,
    /// Evidence behind `event.fault_type` (gasp ratio, counts, onset,
    /// confidence). Additive: existing consumers keep reading `event.*`.
    pub classification: ClassificationEvidence,
    /// Fleet-level annotation set by [`correlate_cycle`]: true when ≥
    /// `AREA_POWER_MIN_OLTS` OLTs opened PowerOutage-classified incidents
    /// in the same detector pass — an area power event, not N local ones.
    /// Always false until the caller runs the correlation post-pass.
    pub area_power_suspected: bool,
    #[serde(flatten)]
    pub event: FaultEvent,
}

/// Per-ONT observation state, keyed by (olt_id, serial).
#[derive(Debug, Default)]
struct OntTrack {
    /// Currently online (as of the last observed cycle)
    online: bool,
    /// Ever seen online since agent start — gates chronic-offline ONTs out
    ever_online: bool,
    /// When the online→offline transition was observed
    went_offline_at: Option<DateTime<Utc>>,
    /// Snapshot taken at the moment of the offline transition
    offline_info: Option<AffectedOnt>,
}

/// An open incident on one port (or a multi-port OLT-level rollup).
#[derive(Debug)]
struct ActiveIncident {
    olt_id: String,
    incident_id: String,
    scope: IncidentScope,
    opened_at: DateTime<Utc>,
    ports: BTreeSet<String>,
    /// serial → snapshot at offline transition
    members: BTreeMap<String, AffectedOnt>,
    fault_type: FaultType,
    classification: ClassificationEvidence,
    severity: String,
    detection_latency_seconds: u64,
}

pub struct FaultDetector {
    config: FaultDetectionConfig,
    /// (olt_id, serial) → observation track
    onts: HashMap<(String, String), OntTrack>,
    /// incident_id → active incident
    incidents: HashMap<String, ActiveIncident>,
    /// (olt_id, pon_port) → incident_id
    port_incident: HashMap<(String, String), String>,
    /// OLTs already warned about degraded port-level localization
    /// (ONTs reporting UNKNOWN_PON_PORT) — log once per OLT, not per cycle.
    unknown_port_warned: HashSet<String>,
    /// olt_id → timestamp of the last check_incidents call, used to measure
    /// the observed poll-cycle length for onset-tightness classification.
    last_cycle: HashMap<String, DateTime<Utc>>,
    /// olt_id → last observed poll-cycle interval (now − previous call).
    cycle_interval: HashMap<String, chrono::Duration>,
}

fn is_online(ont: &OntData) -> bool {
    matches!(ont.status, OntStatus::Online | OntStatus::LowSignal | OntStatus::Dying)
}

fn is_offline(ont: &OntData) -> bool {
    matches!(ont.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut)
}

fn had_dying_gasp(ont: &OntData) -> bool {
    matches!(ont.status, OntStatus::PowerFail)
        || ont.last_down_cause.as_deref()
            .map(|c| c.contains("dying_gasp") || c.contains("power"))
            .unwrap_or(false)
}

impl FaultDetector {
    pub fn new(config: &FaultDetectionConfig) -> Self {
        Self {
            config: config.clone(),
            onts: HashMap::new(),
            incidents: HashMap::new(),
            port_incident: HashMap::new(),
            unknown_port_warned: HashSet::new(),
            last_cycle: HashMap::new(),
            cycle_interval: HashMap::new(),
        }
    }

    /// Legacy single-OLT entry point: returns only newly-opened fault events.
    /// Used by the CSV audit replay path where no OLT id is available.
    pub fn check(&mut self, onts: &[OntData]) -> Vec<FaultEvent> {
        self.check_incidents("", onts)
            .into_iter()
            .filter(|u| u.action == IncidentAction::Open)
            .map(|u| u.event)
            .collect()
    }

    /// Stateful incident check for one OLT's poll cycle.
    /// Emits Open updates for new incidents and Resolve updates for recovered ones.
    pub fn check_incidents(&mut self, olt_id: &str, onts: &[OntData]) -> Vec<IncidentUpdate> {
        self.check_incidents_at(olt_id, onts, Utc::now())
    }

    /// Same as `check_incidents` but with an injectable clock (for tests).
    pub fn check_incidents_at(
        &mut self,
        olt_id: &str,
        onts: &[OntData],
        now: DateTime<Utc>,
    ) -> Vec<IncidentUpdate> {
        if !self.config.enabled {
            return Vec::new();
        }

        // Track the observed poll-cycle length per OLT: onset tightness
        // ("did everything drop within 1-2 cycles?") is measured against the
        // REAL polling cadence, not an assumed one.
        if let Some(prev) = self.last_cycle.insert(olt_id.to_string(), now) {
            let interval = now - prev;
            if interval > chrono::Duration::zero() {
                self.cycle_interval.insert(olt_id.to_string(), interval);
            }
        }

        let window = chrono::Duration::seconds(self.config.time_window_seconds as i64);
        let mut updates = Vec::new();

        // 1. Update per-ONT tracks; record online→offline transitions.
        for ont in onts {
            let key = (olt_id.to_string(), ont.serial_number.clone());
            let track = self.onts.entry(key).or_default();
            if is_online(ont) {
                track.online = true;
                track.ever_online = true;
                track.went_offline_at = None;
                track.offline_info = None;
            } else if is_offline(ont) {
                if track.online {
                    // Transition observed this cycle
                    track.went_offline_at = Some(now);
                    track.offline_info = Some(AffectedOnt {
                        serial_number: ont.serial_number.clone(),
                        distance_meters: ont.distance_meters,
                        last_rx_dbm: ont.rx_power_dbm,
                        had_dying_gasp: had_dying_gasp(ont),
                    });
                }
                track.online = false;
                // Never-online ONTs keep went_offline_at = None (chronic offline)
            }
            // Unknown status: leave track unchanged
        }

        // Group this cycle's ONTs by PON port for port-level (trunk-cut)
        // incident logic. ONTs whose real PON port could not be decoded
        // (vendors emit UNKNOWN_PON_PORT rather than fabricating one) are
        // excluded: grouping unrelated ONTs under a port literally named
        // "unknown" would aggregate them into a fake trunk-cut incident.
        // They still update per-ONT tracks above and remain visible to
        // per-ONT diagnostics elsewhere.
        let mut by_port: HashMap<&str, Vec<&OntData>> = HashMap::new();
        let mut saw_unknown_port = false;
        for ont in onts {
            if ont.pon_port == UNKNOWN_PON_PORT {
                saw_unknown_port = true;
                continue;
            }
            by_port.entry(ont.pon_port.as_str()).or_default().push(ont);
        }
        if saw_unknown_port && self.unknown_port_warned.insert(olt_id.to_string()) {
            tracing::warn!(
                olt_id = %olt_id,
                "ONTs with undecodable PON port present: port-level fault \
                 localization (trunk-cut detection) is degraded on this OLT; \
                 such ONTs are excluded from port/OLT incident grouping"
            );
        }

        // 2. Progress active incidents on this OLT: absorb new transitions
        //    silently, and resolve incidents whose ports have recovered.
        let incident_ids: Vec<String> = self.incidents.values()
            .filter(|i| i.olt_id == olt_id)
            .map(|i| i.incident_id.clone())
            .collect();

        for id in incident_ids {
            let incident = self.incidents.get_mut(&id).expect("incident id just listed");

            // Absorb ONTs that transitioned offline this cycle on incident ports
            for port in incident.ports.clone() {
                if let Some(port_onts) = by_port.get(port.as_str()) {
                    for ont in port_onts {
                        let key = (olt_id.to_string(), ont.serial_number.clone());
                        if let Some(track) = self.onts.get(&key) {
                            if !track.online && track.went_offline_at == Some(now) {
                                if let Some(info) = &track.offline_info {
                                    incident.members
                                        .entry(ont.serial_number.clone())
                                        .or_insert_with(|| info.clone());
                                }
                            }
                        }
                    }
                }
            }

            // Recovery: resolve when the still-offline member count drops
            // below the open threshold.
            let still_offline = incident.members.keys()
                .filter(|serial| {
                    self.onts
                        .get(&(olt_id.to_string(), (*serial).clone()))
                        .map(|t| !t.online)
                        .unwrap_or(true)
                })
                .count();

            if still_offline < self.config.min_offline_onts {
                let incident = self.incidents.remove(&id).expect("incident exists");
                for port in &incident.ports {
                    self.port_incident.remove(&(olt_id.to_string(), port.clone()));
                }
                updates.push(Self::incident_to_update(
                    &incident,
                    IncidentAction::Resolve,
                    now,
                ));
            }
        }

        // 3. Find ports (without an active incident) where enough ONTs
        //    transitioned offline within the time window to open one.
        type Opening = (String, BTreeMap<String, AffectedOnt>, DateTime<Utc>, DateTime<Utc>);
        let mut opening: Vec<Opening> = Vec::new();
        for (port, port_onts) in &by_port {
            if self.port_incident.contains_key(&(olt_id.to_string(), port.to_string())) {
                continue;
            }

            let mut members: BTreeMap<String, AffectedOnt> = BTreeMap::new();
            let mut earliest = now;
            let mut latest = now - window;
            for ont in port_onts {
                let key = (olt_id.to_string(), ont.serial_number.clone());
                if let Some(track) = self.onts.get(&key) {
                    if !track.online && track.ever_online {
                        if let Some(t) = track.went_offline_at {
                            if now - t <= window {
                                if let Some(info) = &track.offline_info {
                                    members.insert(ont.serial_number.clone(), info.clone());
                                    if t < earliest {
                                        earliest = t;
                                    }
                                    if t > latest {
                                        latest = t;
                                    }
                                }
                            }
                        }
                    }
                }
            }

            if members.len() >= self.config.min_offline_onts {
                opening.push((port.to_string(), members, earliest, latest));
            }
        }
        opening.sort_by(|a, b| a.0.cmp(&b.0));

        // 4. Open incidents: one per port, or one OLT-level rollup when
        //    multiple ports fail in the same cycle (feeder/OLT fault).
        if opening.len() == 1 {
            let (port, members, earliest, latest) = opening.remove(0);
            let incident = self.open_incident(
                olt_id,
                IncidentScope::Port,
                BTreeSet::from([port]),
                members,
                now,
                earliest,
                latest,
            );
            updates.push(incident);
        } else if opening.len() >= 2 {
            let mut ports = BTreeSet::new();
            let mut members: BTreeMap<String, AffectedOnt> = BTreeMap::new();
            let mut earliest = now;
            let mut latest = now - window;
            for (port, port_members, port_earliest, port_latest) in opening {
                ports.insert(port);
                members.extend(port_members);
                if port_earliest < earliest {
                    earliest = port_earliest;
                }
                if port_latest > latest {
                    latest = port_latest;
                }
            }
            let incident = self.open_incident(
                olt_id,
                IncidentScope::Olt,
                ports,
                members,
                now,
                earliest,
                latest,
            );
            updates.push(incident);
        }

        updates
    }

    #[allow(clippy::too_many_arguments)]
    fn open_incident(
        &mut self,
        olt_id: &str,
        scope: IncidentScope,
        ports: BTreeSet<String>,
        members: BTreeMap<String, AffectedOnt>,
        now: DateTime<Utc>,
        earliest_transition: DateTime<Utc>,
        latest_transition: DateTime<Utc>,
    ) -> IncidentUpdate {
        let key_part = match scope {
            IncidentScope::Port => ports.iter().next().cloned().unwrap_or_default(),
            IncidentScope::Olt => "olt".to_string(),
        };
        let incident_id = format!("{}:{}:{}", olt_id, key_part, now.timestamp());

        // Onset tightness: spread of offline transitions across members,
        // measured against the observed poll cadence for this OLT. Members
        // exist only after a baseline cycle, so the interval is known by the
        // time any incident opens; if it somehow is not, only a zero spread
        // may claim Simultaneous — never guess tightness.
        let spread = (latest_transition - earliest_transition)
            .max(chrono::Duration::zero());
        let onset = match self.cycle_interval.get(olt_id) {
            Some(interval) if spread <= *interval * SIMULTANEOUS_MAX_CYCLES => {
                OnsetPattern::Simultaneous
            }
            None if spread.is_zero() => OnsetPattern::Simultaneous,
            _ => OnsetPattern::Staggered,
        };
        let spread_seconds = spread.num_seconds().max(0) as u64;

        let (fault_type, classification) = classify(&members, onset, spread_seconds);

        let severity = self.severity_for(members.len()).to_string();
        let detection_latency_seconds =
            (now - earliest_transition).num_seconds().max(0) as u64;

        let incident = ActiveIncident {
            olt_id: olt_id.to_string(),
            incident_id: incident_id.clone(),
            scope,
            opened_at: now,
            ports: ports.clone(),
            members,
            fault_type,
            classification,
            severity,
            detection_latency_seconds,
        };

        let update = Self::incident_to_update(&incident, IncidentAction::Open, now);

        for port in &ports {
            self.port_incident
                .insert((olt_id.to_string(), port.clone()), incident_id.clone());
        }
        self.incidents.insert(incident_id, incident);

        update
    }

    fn incident_to_update(
        incident: &ActiveIncident,
        action: IncidentAction,
        now: DateTime<Utc>,
    ) -> IncidentUpdate {
        let pon_port = incident.ports.iter().cloned().collect::<Vec<_>>().join(",");
        IncidentUpdate {
            action,
            incident_id: incident.incident_id.clone(),
            scope: incident.scope,
            opened_at: incident.opened_at,
            resolved_at: match action {
                IncidentAction::Open => None,
                IncidentAction::Resolve => Some(now),
            },
            ports: incident.ports.iter().cloned().collect(),
            classification: incident.classification.clone(),
            // Fleet-level flag: only the correlate_cycle post-pass may set
            // this; a single-OLT view never claims an area power event.
            area_power_suspected: false,
            event: FaultEvent {
                timestamp: now,
                pon_port,
                olt_id: incident.olt_id.clone(),
                severity: incident.severity.clone(),
                fault_type: incident.fault_type.clone(),
                affected_onts: incident.members.values().cloned().collect(),
                detection_latency_seconds: incident.detection_latency_seconds,
            },
        }
    }

    fn severity_for(&self, affected: usize) -> &'static str {
        if affected >= self.config.severity.critical {
            "critical"
        } else if affected >= self.config.severity.major {
            "major"
        } else if affected >= self.config.severity.minor {
            "minor"
        } else {
            "warning"
        }
    }
}

/// Ratio-based power-vs-fibre classification with evidence.
///
/// - gasp_ratio ≥ `POWER_GASP_RATIO_MIN` (0.6) → PowerOutage: a clear
///   majority gasped; the missing gasps are expected loss (upstream burst
///   contention, weak capacitors).
/// - gasp_ratio ≤ `FIBRE_GASP_RATIO_MAX` (0.1) with ≥ `FIBRE_MIN_AFFECTED`
///   members → FibreCut: powered ONTs went dark without gasping.
/// - anything between (or too few members for a cut call) → Mixed, with the
///   ratio in the evidence so operators see how mixed.
fn classify(
    members: &BTreeMap<String, AffectedOnt>,
    onset: OnsetPattern,
    spread_seconds: u64,
) -> (FaultType, ClassificationEvidence) {
    let total = members.len();
    let gasp = members.values().filter(|m| m.had_dying_gasp).count();
    let hard = total - gasp;
    let ratio = if total > 0 { gasp as f64 / total as f64 } else { 0.0 };

    let fault_type = if ratio >= POWER_GASP_RATIO_MIN {
        FaultType::PowerOutage
    } else if ratio <= FIBRE_GASP_RATIO_MAX && total >= FIBRE_MIN_AFFECTED {
        FaultType::FibreCut
    } else {
        FaultType::Mixed
    };

    let confidence = confidence_for(&fault_type, ratio, onset);

    let mut summary = format!(
        "{}: {}/{} dying gasps (ratio {:.2}), {} onset ({}s first-to-last spread) — confidence {}",
        fault_type, gasp, total, ratio, onset, spread_seconds, confidence,
    );
    if fault_type == FaultType::FibreCut && onset == OnsetPattern::Staggered {
        summary.push_str(&format!(
            "; staggered onset over {}s is atypical for a cut (a cut drops all ONTs \
             within {} poll cycles) — confidence downgraded",
            spread_seconds, SIMULTANEOUS_MAX_CYCLES,
        ));
    }

    let evidence = ClassificationEvidence {
        dying_gasp_count: gasp,
        hard_offline_count: hard,
        dying_gasp_ratio: ratio,
        onset,
        onset_spread_seconds: spread_seconds,
        confidence,
        summary,
    };
    (fault_type, evidence)
}

/// Confidence = ratio distance-from-threshold × onset tightness.
///
/// - Ratio is "strong" when comfortably past the classification threshold
///   (≥ `POWER_STRONG_GASP_RATIO` for power, ≤ `FIBRE_STRONG_GASP_RATIO`
///   for fibre, solidly inside the ambiguous band for Mixed).
/// - Onset contradicts only a FibreCut call: a cut is instantaneous, so a
///   staggered onset downgrades it. Power events legitimately stagger
///   (feeder sectionalising, differing UPS holdup times), so onset is
///   neutral for PowerOutage/Mixed.
fn confidence_for(
    fault_type: &FaultType,
    ratio: f64,
    onset: OnsetPattern,
) -> ClassificationConfidence {
    let ratio_strong = match fault_type {
        FaultType::PowerOutage => ratio >= POWER_STRONG_GASP_RATIO,
        FaultType::FibreCut => ratio <= FIBRE_STRONG_GASP_RATIO,
        // Mixed is a strong call only when the ratio is well inside the
        // ambiguous band, not scraping either classification boundary.
        FaultType::Mixed => {
            ratio > FIBRE_GASP_RATIO_MAX + 0.1 && ratio < POWER_GASP_RATIO_MIN - 0.1
        }
    };
    let onset_supports = match fault_type {
        FaultType::FibreCut => onset == OnsetPattern::Simultaneous,
        FaultType::PowerOutage | FaultType::Mixed => true,
    };
    match (ratio_strong, onset_supports) {
        (true, true) => ClassificationConfidence::High,
        (false, false) => ClassificationConfidence::Low,
        _ => ClassificationConfidence::Medium,
    }
}

/// Cross-OLT power correlation post-pass.
///
/// The detector classifies one OLT at a time; when ≥ `AREA_POWER_MIN_OLTS`
/// OLTs open PowerOutage-classified incidents in the SAME detector pass,
/// that is one area power event (grid), not N independent premises events.
/// The caller collects every update from one poll pass (all OLTs) and runs
/// this before dispatching to webhooks/ES: matching updates come back with
/// `area_power_suspected = true` and the evidence appended to the summary.
/// All other updates pass through unchanged.
pub fn correlate_cycle(updates: &[IncidentUpdate]) -> Vec<IncidentUpdate> {
    let power_olts: BTreeSet<&str> = updates
        .iter()
        .filter(|u| {
            u.action == IncidentAction::Open && u.event.fault_type == FaultType::PowerOutage
        })
        .map(|u| u.event.olt_id.as_str())
        .collect();

    let mut out = updates.to_vec();
    if power_olts.len() >= AREA_POWER_MIN_OLTS {
        for update in out.iter_mut() {
            if update.action == IncidentAction::Open
                && update.event.fault_type == FaultType::PowerOutage
            {
                update.area_power_suspected = true;
                update.classification.summary.push_str(&format!(
                    "; area power event suspected — {} OLTs opened power-classified \
                     incidents in the same pass",
                    power_olts.len(),
                ));
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_config() -> FaultDetectionConfig {
        FaultDetectionConfig {
            enabled: true,
            min_offline_onts: 5,
            time_window_seconds: 60,
            severity: crate::config::FaultSeverityConfig {
                critical: 100, major: 50, minor: 10,
            },
        }
    }

    fn make_ont(serial: &str, port: &str, status: OntStatus, dying_gasp: bool) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: port.into(),
            ont_index: 0,
            status,
            last_down_cause: if dying_gasp { Some("dying_gasp".into()) } else { None },
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: Some(1000),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None, extended: None,
            ..Default::default()
        }
    }

    fn online_population(port: &str, count: usize) -> Vec<OntData> {
        (0..count)
            .map(|i| make_ont(&format!("ONT{:03}", i), port, OntStatus::Online, false))
            .collect()
    }

    #[test]
    fn test_first_cycle_baseline_silence() {
        // Mass-offline on the very first cycle must NOT alarm — no baseline yet.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        let events = detector.check(&onts);
        assert!(events.is_empty(), "first cycle must only establish baseline");
    }

    #[test]
    fn test_chronic_offline_never_alarms() {
        // ONTs offline since agent start (vacant homes) never trigger — even
        // across many cycles.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let onts: Vec<OntData> = (0..20)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        for _ in 0..5 {
            let events = detector.check(&onts);
            assert!(events.is_empty(), "chronic-offline ONTs must never alarm");
        }
    }

    #[test]
    fn test_transition_triggers_single_open_event() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // Cycle 1: 20 ONTs online (baseline)
        assert!(detector.check_incidents("olt-1", &online_population("0/1/0", 20)).is_empty());

        // Cycle 2: 10 go offline → exactly one Open event
        let mut onts = online_population("0/1/0", 20);
        for ont in onts.iter_mut().take(10) {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].action, IncidentAction::Open);
        assert_eq!(updates[0].scope, IncidentScope::Port);
        assert_eq!(updates[0].event.pon_port, "0/1/0");
        assert_eq!(updates[0].event.olt_id, "olt-1");
        assert_eq!(updates[0].event.affected_onts.len(), 10);
        assert_eq!(updates[0].event.fault_type, FaultType::FibreCut);

        // Cycles 3-5: same outage persists → NO re-emission
        for _ in 0..3 {
            let updates = detector.check_incidents("olt-1", &onts);
            assert!(updates.is_empty(), "open incident must not re-emit every cycle");
        }
    }

    #[test]
    fn test_resolve_emitted_on_recovery() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        detector.check_incidents("olt-1", &online_population("0/1/0", 20));

        let mut onts = online_population("0/1/0", 20);
        for ont in onts.iter_mut().take(10) {
            ont.status = OntStatus::Offline;
        }
        let open = detector.check_incidents("olt-1", &onts);
        assert_eq!(open.len(), 1);
        let incident_id = open[0].incident_id.clone();

        // Port recovers → exactly one Resolve with the SAME incident id
        let updates = detector.check_incidents("olt-1", &online_population("0/1/0", 20));
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].action, IncidentAction::Resolve);
        assert_eq!(updates[0].incident_id, incident_id);
        assert!(updates[0].resolved_at.is_some());

        // Nothing further after resolution
        assert!(detector.check_incidents("olt-1", &online_population("0/1/0", 20)).is_empty());
    }

    #[test]
    fn test_no_trigger_below_threshold() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-1", &online_population("0/1/0", 20));

        let mut onts = online_population("0/1/0", 20);
        for ont in onts.iter_mut().take(3) {
            ont.status = OntStatus::Offline;
        }
        assert!(detector.check_incidents("olt-1", &onts).is_empty());
    }

    #[test]
    fn test_power_outage_classification() {
        // All transitions carry a dying gasp → PowerOutage (this branch was
        // previously unreachable).
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-1", &online_population("0/1/0", 10));

        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::PowerFail, true))
            .collect();
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::PowerOutage);
        assert!(updates[0].event.affected_onts.iter().all(|o| o.had_dying_gasp));
    }

    #[test]
    fn test_mixed_dying_gasp_and_hard_offline() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        let mut baseline = Vec::new();
        for i in 0..3 { baseline.push(make_ont(&format!("DG{:03}", i), "0/1/0", OntStatus::Online, false)); }
        for i in 0..6 { baseline.push(make_ont(&format!("HO{:03}", i), "0/1/0", OntStatus::Online, false)); }
        detector.check_incidents("olt-1", &baseline);

        let mut onts = Vec::new();
        for i in 0..3 { onts.push(make_ont(&format!("DG{:03}", i), "0/1/0", OntStatus::PowerFail, true)); }
        for i in 0..6 { onts.push(make_ont(&format!("HO{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::Mixed);
        assert_eq!(updates[0].event.affected_onts.len(), 9);
        let dying_gasp_count = updates[0].event.affected_onts.iter().filter(|o| o.had_dying_gasp).count();
        assert_eq!(dying_gasp_count, 3);
    }

    #[test]
    fn test_severity_classification() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-1", &online_population("0/1/0", 120));

        let onts: Vec<OntData> = (0..120)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates[0].event.severity, "critical");
    }

    #[test]
    fn test_per_port_isolation() {
        // 3 offline per port — below threshold on each, no cross-port summing
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        let mut baseline = Vec::new();
        for i in 0..3 { baseline.push(make_ont(&format!("A{:03}", i), "0/1/0", OntStatus::Online, false)); }
        for i in 0..3 { baseline.push(make_ont(&format!("B{:03}", i), "0/1/1", OntStatus::Online, false)); }
        detector.check_incidents("olt-1", &baseline);

        let mut onts = Vec::new();
        for i in 0..3 { onts.push(make_ont(&format!("A{:03}", i), "0/1/0", OntStatus::Offline, false)); }
        for i in 0..3 { onts.push(make_ont(&format!("B{:03}", i), "0/1/1", OntStatus::Offline, false)); }
        assert!(detector.check_incidents("olt-1", &onts).is_empty());
    }

    #[test]
    fn test_unknown_port_group_never_opens_incident() {
        // ONTs whose PON port could not be decoded (vendors emit
        // UNKNOWN_PON_PORT) must never aggregate into a fake trunk-cut,
        // while a real port's mass-offline still alarms.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        let mut baseline = online_population("0/1/0", 10);
        for i in 0..10 {
            baseline.push(make_ont(
                &format!("UNK{:03}", i),
                crate::vendors::UNKNOWN_PON_PORT,
                OntStatus::Online,
                false,
            ));
        }
        assert!(detector.check_incidents("olt-1", &baseline).is_empty());

        // Cycle 2: ALL unknown-port ONTs transition offline → NO incident.
        let mut onts = baseline.clone();
        for ont in onts.iter_mut().filter(|o| o.pon_port == crate::vendors::UNKNOWN_PON_PORT) {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents("olt-1", &onts);
        assert!(
            updates.is_empty(),
            "unknown-port ONTs must not open a port/OLT incident: {:?}",
            updates.iter().map(|u| &u.incident_id).collect::<Vec<_>>()
        );

        // Cycle 3: the real port's ONTs go offline → exactly one Port
        // incident for the real port, unpolluted by the unknown group.
        for ont in onts.iter_mut().filter(|o| o.pon_port == "0/1/0") {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1, "real port transition must still alarm");
        assert_eq!(updates[0].action, IncidentAction::Open);
        assert_eq!(updates[0].scope, IncidentScope::Port);
        assert_eq!(updates[0].ports, vec!["0/1/0"]);
        assert_eq!(updates[0].event.affected_onts.len(), 10);
        assert!(
            updates[0].event.affected_onts.iter().all(|o| o.serial_number.starts_with("ONT")),
            "unknown-port serials must not be absorbed into the incident"
        );
    }

    #[test]
    fn test_unknown_port_does_not_rollup_into_olt_incident() {
        // Unknown-port ONTs failing in the SAME cycle as a real port must not
        // promote a single-port fault to a fake OLT-level (feeder) incident.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        let mut baseline = online_population("0/1/0", 8);
        for i in 0..8 {
            baseline.push(make_ont(
                &format!("UNK{:03}", i),
                crate::vendors::UNKNOWN_PON_PORT,
                OntStatus::Online,
                false,
            ));
        }
        detector.check_incidents("olt-1", &baseline);

        let mut onts = baseline.clone();
        for ont in onts.iter_mut() {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1);
        assert_eq!(
            updates[0].scope,
            IncidentScope::Port,
            "unknown group must not create a multi-port OLT rollup"
        );
        assert_eq!(updates[0].ports, vec!["0/1/0"]);
        assert!(!updates[0].incident_id.contains(":olt:"));
        assert_eq!(updates[0].event.affected_onts.len(), 8);
    }

    #[test]
    fn test_multi_port_collapse_to_one_olt_incident() {
        // A feeder cut takes down 3 ports at once → ONE OLT-level incident,
        // not 3 independent events.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        let mut baseline = Vec::new();
        for port in 0..3 {
            for i in 0..8 {
                baseline.push(make_ont(
                    &format!("P{}O{:03}", port, i),
                    &format!("0/1/{}", port),
                    OntStatus::Online,
                    false,
                ));
            }
        }
        detector.check_incidents("olt-1", &baseline);

        let mut onts = baseline.clone();
        for ont in onts.iter_mut() {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents("olt-1", &onts);
        assert_eq!(updates.len(), 1, "multi-port failure must collapse to one incident");
        assert_eq!(updates[0].scope, IncidentScope::Olt);
        assert_eq!(updates[0].ports.len(), 3);
        assert_eq!(updates[0].event.affected_onts.len(), 24);
        assert!(updates[0].incident_id.contains(":olt:"));

        // Still open → silent
        assert!(detector.check_incidents("olt-1", &onts).is_empty());

        // Full recovery → single resolve for the OLT incident
        let updates = detector.check_incidents("olt-1", &baseline);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].action, IncidentAction::Resolve);
    }

    #[test]
    fn test_incident_id_stable_dedup_key() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-sul", &online_population("0/3/0", 10));

        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/3/0", OntStatus::Offline, false))
            .collect();
        let updates = detector.check_incidents("olt-sul", &onts);
        assert_eq!(updates.len(), 1);
        let id = &updates[0].incident_id;
        assert!(id.starts_with("olt-sul:0/3/0:"), "dedup key must embed olt and port: {}", id);
        let ts_part = id.rsplit(':').next().unwrap();
        assert!(ts_part.parse::<i64>().is_ok(), "dedup key must end in opened_at timestamp");
    }

    #[test]
    fn test_olts_do_not_share_state() {
        // Same port name on two OLTs must not bleed state.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-a", &online_population("0/1/0", 10));
        detector.check_incidents("olt-b", &online_population("0/1/0", 10));

        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        let updates = detector.check_incidents("olt-a", &onts);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.olt_id, "olt-a");

        // olt-b untouched
        assert!(detector.check_incidents("olt-b", &online_population("0/1/0", 10)).is_empty());
    }

    #[test]
    fn test_transition_outside_window_does_not_open() {
        // ONTs that went offline long ago (outside time_window_seconds) do not
        // combine with fresh transitions into a mass-outage.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let t0 = Utc::now();

        detector.check_incidents_at("olt-1", &online_population("0/1/0", 20), t0);

        // 3 ONTs go offline at t0+10s
        let mut onts = online_population("0/1/0", 20);
        for ont in onts.iter_mut().take(3) {
            ont.status = OntStatus::Offline;
        }
        assert!(detector
            .check_incidents_at("olt-1", &onts, t0 + chrono::Duration::seconds(10))
            .is_empty());

        // 3 more go offline 10 minutes later — the first 3 are outside the
        // 60s window, so only 3 recent transitions → below threshold.
        for ont in onts.iter_mut().skip(3).take(3) {
            ont.status = OntStatus::Offline;
        }
        let updates =
            detector.check_incidents_at("olt-1", &onts, t0 + chrono::Duration::seconds(610));
        assert!(updates.is_empty(), "stale transitions must age out of the window");
    }

    /// Baseline then mass-offline with `gasp_of_n` ONTs gasping out of `n`.
    fn ratio_incident(detector: &mut FaultDetector, olt: &str, n: usize, gasp_of_n: usize) -> Vec<IncidentUpdate> {
        detector.check_incidents(olt, &online_population("0/1/0", n));
        let onts: Vec<OntData> = (0..n)
            .map(|i| {
                if i < gasp_of_n {
                    make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::PowerFail, true)
                } else {
                    make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false)
                }
            })
            .collect();
        detector.check_incidents(olt, &onts)
    }

    #[test]
    fn test_gasp_ratio_0_7_classifies_power_outage() {
        // 7/10 gasps: lost gasps must not veto a power call (old exact-zero
        // logic would have said Mixed).
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let updates = ratio_incident(&mut detector, "olt-1", 10, 7);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::PowerOutage);
        let c = &updates[0].classification;
        assert!((c.dying_gasp_ratio - 0.7).abs() < 1e-9);
        assert_eq!(c.dying_gasp_count, 7);
        assert_eq!(c.hard_offline_count, 3);
        // 0.7 is above the 0.6 threshold but below the 0.8 strong mark
        assert_eq!(c.confidence, ClassificationConfidence::Medium);
        assert!(c.summary.contains("0.70"), "summary must show the ratio: {}", c.summary);
    }

    #[test]
    fn test_gasp_ratio_0_05_classifies_fibre_cut_high_confidence() {
        // 1/20 gasps: one straggler gasp must not veto a cut call.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let updates = ratio_incident(&mut detector, "olt-1", 20, 1);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::FibreCut);
        let c = &updates[0].classification;
        assert!((c.dying_gasp_ratio - 0.05).abs() < 1e-9);
        // ratio ≤ strong mark (0.05) and same-cycle onset → High
        assert_eq!(c.onset, OnsetPattern::Simultaneous);
        assert_eq!(c.confidence, ClassificationConfidence::High);
    }

    #[test]
    fn test_gasp_ratio_0_3_classifies_mixed_with_evidence() {
        // 3/10 gasps is genuinely ambiguous → Mixed, with the ratio emitted
        // so operators see HOW mixed.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let updates = ratio_incident(&mut detector, "olt-1", 10, 3);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::Mixed);
        let c = &updates[0].classification;
        assert!((c.dying_gasp_ratio - 0.3).abs() < 1e-9);
        assert_eq!(c.dying_gasp_count, 3);
        assert_eq!(c.hard_offline_count, 7);
        assert!(c.summary.contains("mixed"), "summary: {}", c.summary);
    }

    #[test]
    fn test_small_incident_without_gasps_is_mixed_not_fibre_cut() {
        // Below FIBRE_MIN_AFFECTED the ratio is too coarse for a cut call.
        let mut cfg = make_config();
        cfg.min_offline_onts = 3;
        let mut detector = FaultDetector::new(&cfg);
        let updates = ratio_incident(&mut detector, "olt-1", 4, 0);
        assert_eq!(updates.len(), 1);
        assert_eq!(
            updates[0].event.fault_type,
            FaultType::Mixed,
            "4 members with 0 gasps is too few to confidently call a cut"
        );
    }

    #[test]
    fn test_simultaneous_onset_single_cycle_drop() {
        // Everything transitions in one poll cycle → Simultaneous, spread 0.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let t0 = Utc::now();
        detector.check_incidents_at("olt-1", &online_population("0/1/0", 10), t0);

        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        let updates =
            detector.check_incidents_at("olt-1", &onts, t0 + chrono::Duration::seconds(30));
        assert_eq!(updates.len(), 1);
        let c = &updates[0].classification;
        assert_eq!(c.onset, OnsetPattern::Simultaneous);
        assert_eq!(c.onset_spread_seconds, 0);
        assert_eq!(updates[0].event.fault_type, FaultType::FibreCut);
        assert_eq!(c.confidence, ClassificationConfidence::High);
    }

    #[test]
    fn test_staggered_onset_downgrades_fibre_cut_confidence() {
        // Transitions spread over 4 poll cycles (30s cadence, 120s spread)
        // contradict a clean cut → Staggered, confidence downgraded, and the
        // summary says so.
        let mut cfg = make_config();
        cfg.time_window_seconds = 300;
        let mut detector = FaultDetector::new(&cfg);
        let t0 = Utc::now();
        let cycle = chrono::Duration::seconds(30);

        let mut onts = online_population("0/1/0", 10);
        detector.check_incidents_at("olt-1", &onts, t0);

        // Cycle t0+30: 3 ONTs drop (below the 5-ONT open threshold)
        for ont in onts.iter_mut().take(3) {
            ont.status = OntStatus::Offline;
        }
        assert!(detector.check_incidents_at("olt-1", &onts, t0 + cycle).is_empty());

        // Quiet cycles keep the cadence observable
        assert!(detector.check_incidents_at("olt-1", &onts, t0 + cycle * 2).is_empty());
        assert!(detector.check_incidents_at("olt-1", &onts, t0 + cycle * 3).is_empty());
        assert!(detector.check_incidents_at("olt-1", &onts, t0 + cycle * 4).is_empty());

        // Cycle t0+150: 3 more drop → threshold crossed, spread = 120s > 2 cycles
        for ont in onts.iter_mut().skip(3).take(3) {
            ont.status = OntStatus::Offline;
        }
        let updates = detector.check_incidents_at("olt-1", &onts, t0 + cycle * 5);
        assert_eq!(updates.len(), 1);
        assert_eq!(updates[0].event.fault_type, FaultType::FibreCut);
        let c = &updates[0].classification;
        assert_eq!(c.onset, OnsetPattern::Staggered);
        assert_eq!(c.onset_spread_seconds, 120);
        assert_eq!(
            c.confidence,
            ClassificationConfidence::Medium,
            "staggered onset must downgrade a strong-ratio cut from High"
        );
        assert!(
            c.summary.contains("staggered") && c.summary.contains("downgraded"),
            "summary must say why: {}",
            c.summary
        );
    }

    #[test]
    fn test_correlate_cycle_flags_two_olt_power_event() {
        // PowerOutage incidents opening on 2 OLTs in the same pass = area
        // power event, not two coincidences.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut pass = Vec::new();
        pass.extend(ratio_incident(&mut detector, "olt-a", 10, 10));
        pass.extend(ratio_incident(&mut detector, "olt-b", 8, 8));
        assert_eq!(pass.len(), 2);
        assert!(pass.iter().all(|u| !u.area_power_suspected), "raw updates never claim area power");

        let correlated = correlate_cycle(&pass);
        assert!(correlated.iter().all(|u| u.area_power_suspected));
        assert!(correlated.iter().all(|u| u.classification.summary.contains("area power event suspected")));
    }

    #[test]
    fn test_correlate_cycle_single_olt_power_not_flagged() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let pass = ratio_incident(&mut detector, "olt-a", 10, 10);
        let correlated = correlate_cycle(&pass);
        assert_eq!(correlated.len(), 1);
        assert!(
            !correlated[0].area_power_suspected,
            "one OLT losing power is a local event, never an area claim"
        );
    }

    #[test]
    fn test_correlate_cycle_fibre_cuts_never_flagged() {
        // Two fibre cuts on two OLTs are two cuts, not an area power event.
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);
        let mut pass = Vec::new();
        pass.extend(ratio_incident(&mut detector, "olt-a", 10, 0));
        pass.extend(ratio_incident(&mut detector, "olt-b", 10, 0));
        assert_eq!(pass.len(), 2);
        let correlated = correlate_cycle(&pass);
        assert!(correlated.iter().all(|u| !u.area_power_suspected));
        assert!(correlated.iter().all(|u| u.event.fault_type == FaultType::FibreCut));
    }

    #[test]
    fn test_disabled_detector_is_silent() {
        let mut cfg = make_config();
        cfg.enabled = false;
        let mut detector = FaultDetector::new(&cfg);
        detector.check_incidents("olt-1", &online_population("0/1/0", 10));
        let onts: Vec<OntData> = (0..10)
            .map(|i| make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false))
            .collect();
        assert!(detector.check_incidents("olt-1", &onts).is_empty());
    }
}
