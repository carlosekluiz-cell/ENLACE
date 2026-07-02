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
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum FaultType {
    FibreCut,
    PowerOutage,
    Mixed,
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
        let mut opening: Vec<(String, BTreeMap<String, AffectedOnt>, DateTime<Utc>)> = Vec::new();
        for (port, port_onts) in &by_port {
            if self.port_incident.contains_key(&(olt_id.to_string(), port.to_string())) {
                continue;
            }

            let mut members: BTreeMap<String, AffectedOnt> = BTreeMap::new();
            let mut earliest = now;
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
                                }
                            }
                        }
                    }
                }
            }

            if members.len() >= self.config.min_offline_onts {
                opening.push((port.to_string(), members, earliest));
            }
        }
        opening.sort_by(|a, b| a.0.cmp(&b.0));

        // 4. Open incidents: one per port, or one OLT-level rollup when
        //    multiple ports fail in the same cycle (feeder/OLT fault).
        if opening.len() == 1 {
            let (port, members, earliest) = opening.remove(0);
            let incident = self.open_incident(
                olt_id,
                IncidentScope::Port,
                BTreeSet::from([port]),
                members,
                now,
                earliest,
            );
            updates.push(incident);
        } else if opening.len() >= 2 {
            let mut ports = BTreeSet::new();
            let mut members: BTreeMap<String, AffectedOnt> = BTreeMap::new();
            let mut earliest = now;
            for (port, port_members, port_earliest) in opening {
                ports.insert(port);
                members.extend(port_members);
                if port_earliest < earliest {
                    earliest = port_earliest;
                }
            }
            let incident = self.open_incident(
                olt_id,
                IncidentScope::Olt,
                ports,
                members,
                now,
                earliest,
            );
            updates.push(incident);
        }

        updates
    }

    fn open_incident(
        &mut self,
        olt_id: &str,
        scope: IncidentScope,
        ports: BTreeSet<String>,
        members: BTreeMap<String, AffectedOnt>,
        now: DateTime<Utc>,
        earliest_transition: DateTime<Utc>,
    ) -> IncidentUpdate {
        let key_part = match scope {
            IncidentScope::Port => ports.iter().next().cloned().unwrap_or_default(),
            IncidentScope::Olt => "olt".to_string(),
        };
        let incident_id = format!("{}:{}:{}", olt_id, key_part, now.timestamp());

        let gasp = members.values().filter(|m| m.had_dying_gasp).count();
        let hard = members.len() - gasp;
        let fault_type = if hard == 0 {
            FaultType::PowerOutage
        } else if gasp == 0 {
            FaultType::FibreCut
        } else {
            FaultType::Mixed
        };

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
