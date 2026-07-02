// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320/6330 OLT Collector
//
// PRIMARY: NETCONF/YANG (BBF TR-385) over SSH port 830
// FALLBACK: SNMP v2c (older Adtran lines only — per Adtran's SDX 6000-series
//           data sheet the SDX 6320/6330 are managed via NETCONF/YANG open
//           APIs and expose no SNMP agent)
//
// NETCONF provides:
//   - ONT state via the BBF onu-state model. Both published generations are
//     supported and selected via the server's ietf-yang-library
//     (verified 2026-07-02 against github.com/BroadbandForum/yang and
//     github.com/BroadbandForum/obbaa):
//       * CURRENT: module `bbf-xpon-onu-state` (TR-385 Issue 2/3, revisions
//         2019-02-25…2024-04-23) — container
//         `onus-present-on-local-channel-termination` with identityref leaf
//         `onu-presence-state`, augmenting
//         /if:interfaces-state/if:interface/bbf-xpon:channel-termination
//       * LEGACY: module `bbf-xpon-onu-states` (TR-385 Issue 1 / OB-BAA R1
//         era) — leaf `onu-state`, notification `onu-state-change`
//   - OLT-side upstream rx power per ONU via bbf-hardware-transceivers-xpon
//     `rssi-onu` list (0.1 dBm units)
//   - ONT-side OMCI transceiver data where exposed (rx, tx, temp, voltage, bias)
//   - Ranging via equalization-delay (TQ * 0.0125 = meters)
//   - Down-cause classification via ietf-alarms polling (RFC 8632) —
//     dying gasp is identity `dgi` in bbf-xpon-defects — with RFC 5277
//     notification subscription as a best-effort enhancement
//
// The SDX 6330-48 has 48 GPON ports across 2 line cards.
// Channel termination naming: CTP-{shelf}/{slot}/{port}

use async_trait::async_trait;
use dashmap::DashMap;
use std::collections::HashSet;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use tracing::{debug, info, warn};

use crate::config::{NetconfConfig, OltConfig};
use crate::netconf;
use crate::netconf::xml::{self, OntYangState, TQ_TO_METERS};
use super::*;

// ── NETCONF subtree filters ─────────────────────────────────────────────────

/// ietf-yang-library, RFC 7895 tree (deprecated but universally present).
const FILTER_YANG_LIBRARY_RFC7895: &str =
    r#"<modules-state xmlns="urn:ietf:params:xml:ns:yang:ietf-yang-library"/>"#;

/// ietf-yang-library, RFC 8525 tree.
const FILTER_YANG_LIBRARY_RFC8525: &str =
    r#"<yang-library xmlns="urn:ietf:params:xml:ns:yang:ietf-yang-library"/>"#;

/// ONT state — CURRENT model (module bbf-xpon-onu-state, TR-385 Issue 2/3).
///
/// Structure verified against
/// standard/interface/bbf-xpon-onu-state.yang in
/// github.com/BroadbandForum/yang (rev 2024-04-23): the state container
/// `onus-present-on-local-channel-termination` augments
/// `/if:interfaces-state/if:interface/bbf-xpon:channel-termination`.
/// The whole container is requested (no leaf-level selection) so one reply
/// carries state + any OMCI/ranging leaves the firmware exposes there.
const FILTER_ONT_STATE_CURRENT: &str = r#"<interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
  <interface>
    <name/>
    <channel-termination xmlns="urn:bbf:yang:bbf-xpon">
      <onus-present-on-local-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state"/>
    </channel-termination>
  </interface>
</interfaces-state>"#;

/// ONT state — LEGACY plural model (module bbf-xpon-onu-states,
/// ns urn:bbf:yang:bbf-xpon-onu-states, TR-385 Issue 1 / OB-BAA R1 era).
/// The plural module's .yang source is no longer published; this mirrors the
/// current structure under the plural namespace (unverified — legacy
/// firmware should be captured and a fixture added when encountered).
const FILTER_ONT_STATE_LEGACY_PLURAL: &str = r#"<interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
  <interface>
    <name/>
    <channel-termination xmlns="urn:bbf:yang:bbf-xpon">
      <onus-present-on-local-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-states"/>
    </channel-termination>
  </interface>
</interfaces-state>"#;

/// ONT state — last-resort filter kept from the original implementation
/// (top-level <xpon> with a channel-terminations list). This shape does NOT
/// exist in any published BBF module (bbf-xpon's top-level `xpon` container
/// holds only ICTP config — see bbf-xpon-base.yang) but is retained as a
/// final fallback for firmware that happened to match it.
const FILTER_ONT_STATE_XPON_ROOTED: &str = r#"<xpon xmlns="urn:bbf:yang:bbf-xpon">
  <channel-terminations>
    <channel-termination>
      <name/>
      <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state"/>
    </channel-termination>
  </channel-terminations>
</xpon>"#;

/// OLT-side per-ONU upstream RX power: bbf-hardware-transceivers-xpon
/// `rssi-onu` (leaf `rssi`, 0.1 dBm units) under
/// /hw:hardware/hw:component/transceiver-link/diagnostics.
/// This is where OLT-side upstream RX actually lives in the published BBF
/// models — there is no `measured-upstream-rx-optical-power-dbm` leaf.
const FILTER_RSSI_ONU: &str = r#"<hardware xmlns="urn:ietf:params:xml:ns:yang:ietf-hardware">
  <component>
    <name/>
    <transceiver-link xmlns="urn:bbf:yang:bbf-hardware-transceivers">
      <diagnostics>
        <rssi-onu xmlns="urn:bbf:yang:bbf-hardware-transceivers-xpon"/>
      </diagnostics>
    </transceiver-link>
  </component>
</hardware>"#;

/// ietf-alarms alarm list (RFC 8632). Polled every cycle via plain <get> —
/// works without notification support and is the primary source of
/// `last_down_cause` (dying-gasp vs LOS/LOB) for PowerOutage/FibreCut
/// classification.
const FILTER_ALARM_LIST: &str =
    r#"<alarms xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms"><alarm-list/></alarms>"#;

// ── Tunables ────────────────────────────────────────────────────────────────

/// NETCONF collection timeout. A 48-port SDX with thousands of ONTs produces
/// multi-MB replies; 30s was too tight once alarms + rssi are also fetched.
fn netconf_timeout() -> std::time::Duration {
    let secs = std::env::var("PULSO_ADTRAN_NETCONF_TIMEOUT_SECS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(90);
    std::time::Duration::from_secs(secs)
}

/// SNMP fallback timeout. The previous 5s window could never walk a 48-port
/// SDX (4 table walks over thousands of rows); default to 60s,
/// override with PULSO_ADTRAN_SNMP_FALLBACK_SECS.
fn snmp_fallback_timeout() -> std::time::Duration {
    let secs = std::env::var("PULSO_ADTRAN_SNMP_FALLBACK_SECS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(60);
    std::time::Duration::from_secs(secs)
}

/// How long an ONT may stay in the state table without being seen in any
/// NETCONF reply before it is pruned. Without pruning, an ONT that is
/// deleted/moved keeps its last status ("online") forever — ghost customers.
fn ont_state_retention() -> chrono::Duration {
    let days = std::env::var("PULSO_ONT_STATE_RETENTION_DAYS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(7i64);
    chrono::Duration::days(days.max(1))
}

/// Tracked state per ONT, keyed by serial number.
#[derive(Debug, Clone)]
pub struct OntState {
    pub serial: String,
    pub onu_id: u32,
    pub channel_term: String,
    pub status: OntStatus,
    pub last_seen: chrono::DateTime<chrono::Utc>,
    pub dying_gasp: bool,
    /// Classified cause of the last transition to offline
    /// ("dying_gasp", "los", "loss_of_burst", …) from ietf-alarms and/or
    /// dying-gasp notifications. Consumed by the fault detector to separate
    /// PowerOutage from FibreCut.
    pub last_down_cause: Option<String>,
    /// OLT-side upstream rx power (dBm)
    pub olt_rx_power_dbm: Option<f64>,
    /// ONT-side rx power (dBm) — primary degradation metric
    pub ont_rx_power_dbm: Option<f64>,
    /// ONT-side tx power (dBm)
    pub ont_tx_power_dbm: Option<f64>,
    /// ONT temperature (Celsius)
    pub ont_temperature_c: Option<f64>,
    /// ONT supply voltage (V)
    pub ont_voltage_v: Option<f64>,
    /// ONT laser bias current (mA)
    pub ont_bias_current_ma: Option<f64>,
    /// Ranging distance (meters), from equalization_delay_tq * 0.0125
    pub distance_m: Option<f64>,
}

impl OntState {
    fn new(
        serial: String,
        onu_id: u32,
        channel_term: String,
        status: OntStatus,
        last_seen: chrono::DateTime<chrono::Utc>,
    ) -> Self {
        Self {
            serial,
            onu_id,
            channel_term,
            status,
            last_seen,
            dying_gasp: false,
            last_down_cause: None,
            olt_rx_power_dbm: None,
            ont_rx_power_dbm: None,
            ont_tx_power_dbm: None,
            ont_temperature_c: None,
            ont_voltage_v: None,
            ont_bias_current_ma: None,
            distance_m: None,
        }
    }
}

pub struct AdtranCollector {
    olt_id: String,
    config: OltConfig,
    /// State table keyed by serial number for O(1) lookup
    ont_state: Arc<DashMap<String, OntState>>,
    device_model: std::sync::Mutex<Option<String>>,
    device_firmware: std::sync::Mutex<Option<String>>,
    /// ONT count from the last successful collection — used to flag
    /// suspicious empty replies (N ONTs yesterday, 0 today = filter/firmware
    /// problem, not a mass outage).
    last_ont_count: AtomicUsize,
    /// Best-effort RFC 5277 notification listener (dying gasp between polls).
    notif_task: std::sync::Mutex<Option<tokio::task::JoinHandle<()>>>,
    /// Set once the server has rejected create-subscription so we stop retrying.
    notif_unsupported: Arc<AtomicBool>,
}

impl AdtranCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        // NETCONF is required; SNMP and gRPC are optional fallbacks
        if config.netconf.is_none() && config.grpc.is_none() && config.snmp.is_none() {
            return Err(anyhow::anyhow!(
                "Adtran SDX 6330 requires [olts.netconf] config (primary) or [olts.snmp] (fallback)"
            ));
        }

        Ok(Self {
            olt_id: format!("adtran-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            ont_state: Arc::new(DashMap::new()),
            device_model: std::sync::Mutex::new(None),
            device_firmware: std::sync::Mutex::new(None),
            last_ont_count: AtomicUsize::new(0),
            notif_task: std::sync::Mutex::new(None),
            notif_unsupported: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Pick which ONT-state filters to try, in order, based on the server's
    /// yang-library module list. `None` (yang-library unavailable) tries all
    /// known variants.
    fn ont_state_filters_for_modules(
        modules: Option<&[xml::YangModule]>,
    ) -> Vec<&'static str> {
        let all = vec![
            FILTER_ONT_STATE_CURRENT,
            FILTER_ONT_STATE_LEGACY_PLURAL,
            FILTER_ONT_STATE_XPON_ROOTED,
        ];
        let Some(modules) = modules else { return all };
        let has = |name: &str| modules.iter().any(|m| m.name == name);

        if has("bbf-xpon-onu-state") {
            // Current singular module (TR-385 Issue 2/3).
            vec![FILTER_ONT_STATE_CURRENT]
        } else if has("bbf-xpon-onu-states") {
            // Legacy plural module (TR-385 Issue 1 / OB-BAA R1).
            vec![FILTER_ONT_STATE_LEGACY_PLURAL, FILTER_ONT_STATE_XPON_ROOTED]
        } else {
            warn!(
                "yang-library lists no bbf-xpon-onu-state(s) module — trying all filter variants"
            );
            all
        }
    }

    /// Fetch the server's YANG module list (RFC 7895 modules-state first,
    /// then RFC 8525 yang-library). Best-effort: None if neither tree exists.
    async fn fetch_yang_library(
        session: &mut netconf::NetconfSession,
    ) -> Option<Vec<xml::YangModule>> {
        for filter in [FILTER_YANG_LIBRARY_RFC7895, FILTER_YANG_LIBRARY_RFC8525] {
            match session.get(filter).await {
                Ok(reply) => match xml::parse_yang_library(&reply) {
                    Ok(modules) if !modules.is_empty() => return Some(modules),
                    Ok(_) => {}
                    Err(e) => {
                        warn!(error = %e, "yang-library reply failed to parse");
                    }
                },
                Err(e) => {
                    debug!(error = %e, filter = filter, "yang-library variant not available");
                }
            }
        }
        None
    }

    /// An ONT-state reply with zero entries on an established session is
    /// treated as an ERROR, never as "success with 0 ONTs": a mismatched
    /// subtree filter returns empty <data/>, and reporting that as a mass
    /// outage is the single most likely day-one failure mode.
    fn validate_ont_state_reply(entry_count: usize, prev_count: usize) -> anyhow::Result<()> {
        if entry_count > 0 {
            return Ok(());
        }
        Err(anyhow::anyhow!(
            "ONT-state query returned no ONUs on an established NETCONF session \
             (previous collection saw {} ONTs). Empty <data/> almost always means the \
             YANG subtree filter matched nothing on this firmware — refusing to \
             report 0 ONTs (it would read as a mass offline downstream). Capture the \
             OLT's ietf-yang-library module list to identify the right filter.",
            prev_count
        ))
    }

    /// Connect via NETCONF and collect all ONT data:
    ///   1. ietf-yang-library → select the ONT-state filter variant
    ///   2. ONT state (full subtree: state + any OMCI/ranging leaves)
    ///   3. OLT-side per-ONU RX (rssi-onu) — best effort
    ///   4. ietf-alarms → last_down_cause (dying gasp vs LOS) — best effort
    async fn collect_via_netconf(&self) -> anyhow::Result<Vec<OntData>> {
        let nc = self.config.netconf.as_ref().ok_or_else(|| {
            anyhow::anyhow!("NETCONF config missing for Adtran SDX")
        })?;

        let mut session = netconf::NetconfSession::connect(
            &self.config.ip,
            nc.port,
            &nc.username,
            nc.password.as_deref(),
            nc.key_file.as_deref(),
        )
        .await?;

        info!(
            olt = %self.olt_id,
            version = if session.is_netconf_11() { "1.1" } else { "1.0" },
            "NETCONF connected to Adtran SDX"
        );

        // 1. Discover which BBF onu-state module generation this firmware runs.
        let modules = Self::fetch_yang_library(&mut session).await;
        match &modules {
            Some(mods) => debug!(count = mods.len(), "yang-library modules discovered"),
            None => warn!(
                olt = %self.olt_id,
                "Server exposes no ietf-yang-library — trying all known ONT-state filter variants"
            ),
        }
        let filters = Self::ont_state_filters_for_modules(modules.as_deref());

        // 2. ONT state — first filter variant that yields entries wins.
        let mut state_entries = Vec::new();
        let mut state_xml = String::new();
        for filter in &filters {
            match session.get(filter).await {
                Ok(reply) => {
                    let entries = xml::parse_ont_state(&reply)?;
                    if entries.is_empty() {
                        debug!(olt = %self.olt_id, "ONT-state filter variant matched no data");
                        continue;
                    }
                    state_entries = entries;
                    state_xml = reply;
                    break;
                }
                Err(e) => {
                    debug!(olt = %self.olt_id, error = %e, "ONT-state filter variant rejected");
                }
            }
        }

        let prev_count = self.last_ont_count.load(Ordering::Relaxed);
        if let Err(e) = Self::validate_ont_state_reply(state_entries.len(), prev_count) {
            let _ = session.close().await;
            return Err(e);
        }

        // Optical power + ranging come from the same full-subtree reply —
        // parse failures here are hard errors (a garbled reply must not be
        // read as "ONTs with no optics").
        let power_entries = xml::parse_optical_power(&state_xml)?;
        let ranging_entries = xml::parse_ranging(&state_xml)?;

        // 3. OLT-side per-ONU RX via bbf-hardware-transceivers-xpon (best effort).
        let rssi_entries = match session.get(FILTER_RSSI_ONU).await {
            Ok(reply) => match xml::parse_rssi_onu(&reply) {
                Ok(entries) => entries,
                Err(e) => {
                    warn!(olt = %self.olt_id, error = %e, "rssi-onu reply failed to parse");
                    Vec::new()
                }
            },
            Err(e) => {
                debug!(olt = %self.olt_id, error = %e, "rssi-onu not available");
                Vec::new()
            }
        };

        // 4. ietf-alarms poll — primary down-cause source (dying gasp = dgi).
        //    Best effort: firmware without RFC 8632 support degrades to
        //    notification-only dying-gasp detection.
        let alarms = match session.get(FILTER_ALARM_LIST).await {
            Ok(reply) => match xml::parse_alarm_list(&reply) {
                Ok(list) => list,
                Err(e) => {
                    warn!(olt = %self.olt_id, error = %e, "ietf-alarms reply failed to parse");
                    Vec::new()
                }
            },
            Err(e) => {
                warn!(
                    olt = %self.olt_id,
                    error = %e,
                    "ietf-alarms poll failed — PowerOutage/FibreCut classification degraded \
                     to dying-gasp notifications only"
                );
                Vec::new()
            }
        };

        // Close session cleanly
        let _ = session.close().await;

        // Update the state table.
        let now = chrono::Utc::now();
        Self::apply_state_entries(&self.ont_state, &state_entries, now);
        Self::apply_power_entries(&self.ont_state, &power_entries);
        Self::apply_rssi_entries(&self.ont_state, &rssi_entries);
        Self::apply_ranging_entries(&self.ont_state, &ranging_entries);

        // ONTs previously tracked but absent from this (successful, non-empty)
        // reply are no longer present on any channel termination → offline.
        let seen: HashSet<String> = state_entries
            .iter()
            .map(|e| e.serial_number.clone())
            .collect();
        Self::mark_absent_onts_offline(&self.ont_state, &seen);

        Self::apply_alarms(&self.ont_state, &alarms);

        // Prune ONTs not seen for the retention horizon — otherwise deleted/
        // moved ONTs remain "online" ghosts forever.
        let pruned = Self::prune_stale_onts(&self.ont_state, now, ont_state_retention());
        if pruned > 0 {
            info!(olt = %self.olt_id, pruned = pruned, "Pruned stale ONT state entries");
        }

        self.last_ont_count
            .store(state_entries.len(), Ordering::Relaxed);

        // Best-effort: keep a notification listener running between polls so
        // dying gasps arriving mid-cycle are captured.
        self.ensure_notification_listener();

        let onts = Self::snapshot_ont_data(&self.ont_state);

        info!(
            olt = %self.olt_id,
            onts = onts.len(),
            online = onts.iter().filter(|o| o.status == OntStatus::Online || o.status == OntStatus::LowSignal).count(),
            alarms = alarms.len(),
            "NETCONF collection complete"
        );

        Ok(onts)
    }

    // ── State table maintenance (associated fns for testability) ───────────

    /// Merge fresh ONT-state entries into the table, updating in place so
    /// optical readings survive between phases.
    fn apply_state_entries(
        map: &DashMap<String, OntState>,
        entries: &[xml::OntStateEntry],
        now: chrono::DateTime<chrono::Utc>,
    ) {
        for entry in entries {
            let prev_gasp = map
                .get(&entry.serial_number)
                .map(|s| s.dying_gasp)
                .unwrap_or(false);
            let existed = map.contains_key(&entry.serial_number);

            // A never-before-seen ONT reported not-present gets plain
            // Offline — we have no evidence to claim a cause.
            let status = if !existed && matches!(entry.state, OntYangState::Offline) {
                OntStatus::Offline
            } else {
                yang_state_to_ont_status(&entry.state, prev_gasp)
            };

            let mut st = map
                .entry(entry.serial_number.clone())
                .or_insert_with(|| {
                    OntState::new(
                        entry.serial_number.clone(),
                        entry.onu_id,
                        entry.channel_term.clone(),
                        OntStatus::Unknown,
                        now,
                    )
                });
            st.onu_id = entry.onu_id;
            if !entry.channel_term.is_empty() {
                st.channel_term = entry.channel_term.clone();
            }
            st.status = status.clone();
            st.last_seen = now;
            if status == OntStatus::Online {
                // Back online: the previous down-cause is history.
                st.dying_gasp = false;
                st.last_down_cause = None;
            }
        }
    }

    fn apply_power_entries(map: &DashMap<String, OntState>, entries: &[xml::OpticalPowerEntry]) {
        for p in entries {
            if let Some(mut state) = map.get_mut(&p.serial_number) {
                state.olt_rx_power_dbm = p.olt_rx_power_dbm.or(state.olt_rx_power_dbm);
                state.ont_rx_power_dbm = p.ont_rx_power_dbm;
                state.ont_tx_power_dbm = p.ont_tx_power_dbm;
                state.ont_temperature_c = p.ont_temperature_c;
                state.ont_voltage_v = p.ont_voltage_v;
                state.ont_bias_current_ma = p.ont_bias_current_ma;

                // Flag low signal based on ONT rx (primary) or OLT rx (fallback)
                let primary_rx = p.ont_rx_power_dbm.or(p.olt_rx_power_dbm);
                if let Some(rx) = primary_rx {
                    if state.status == OntStatus::Online && rx < -27.0 {
                        state.status = OntStatus::LowSignal;
                    }
                }
            }
        }
    }

    /// OLT-side upstream RX from bbf-hardware-transceivers-xpon (0.1 dBm
    /// units, already converted to dBm by the parser).
    fn apply_rssi_entries(map: &DashMap<String, OntState>, entries: &[(String, f64)]) {
        for (serial, rssi_dbm) in entries {
            if let Some(mut state) = map.get_mut(serial) {
                state.olt_rx_power_dbm = Some(*rssi_dbm);
                if state.status == OntStatus::Online
                    && state.ont_rx_power_dbm.is_none()
                    && *rssi_dbm < -27.0
                {
                    state.status = OntStatus::LowSignal;
                }
            }
        }
    }

    fn apply_ranging_entries(map: &DashMap<String, OntState>, entries: &[xml::RangingEntry]) {
        for r in entries {
            if let Some(mut state) = map.get_mut(&r.serial_number) {
                state.distance_m = Some(r.distance_m);
            }
        }
    }

    /// ONTs tracked in the table but missing from the latest successful
    /// reply are no longer present on their channel termination: transition
    /// them to offline instead of leaving a ghost "online" entry forever.
    /// `last_seen` is intentionally NOT refreshed so retention pruning
    /// eventually removes them.
    fn mark_absent_onts_offline(map: &DashMap<String, OntState>, seen: &HashSet<String>) {
        for mut entry in map.iter_mut() {
            if seen.contains(entry.key()) {
                continue;
            }
            if matches!(entry.status, OntStatus::Online | OntStatus::LowSignal | OntStatus::Dying)
            {
                entry.status = if entry.dying_gasp {
                    OntStatus::PowerFail
                } else {
                    OntStatus::FiberCut
                };
            }
        }
    }

    /// Populate last_down_cause (and upgrade FiberCut→PowerFail) from
    /// ietf-alarms. Cleared alarms are applied first so an active alarm for
    /// the same ONT wins.
    fn apply_alarms(map: &DashMap<String, OntState>, alarms: &[xml::AlarmEntry]) {
        let ordered = alarms
            .iter()
            .filter(|a| a.is_cleared)
            .chain(alarms.iter().filter(|a| !a.is_cleared));

        for alarm in ordered {
            let Some(cause) = xml::classify_down_cause(&alarm.alarm_type_id) else {
                continue;
            };
            let Some(serial) = Self::resolve_alarm_serial(map, &alarm.resource) else {
                debug!(
                    resource = %alarm.resource,
                    alarm_type = %alarm.alarm_type_id,
                    "Alarm resource does not match any tracked ONT"
                );
                continue;
            };
            if let Some(mut st) = map.get_mut(&serial) {
                // Skip stale cleared alarms for ONTs that are back online —
                // their down-cause was already reset on recovery.
                if alarm.is_cleared
                    && matches!(st.status, OntStatus::Online | OntStatus::LowSignal)
                {
                    continue;
                }
                st.last_down_cause = Some(cause.to_string());
                if cause == "dying_gasp" || cause == "power_fail" {
                    st.dying_gasp = true;
                    if matches!(st.status, OntStatus::FiberCut | OntStatus::Offline) {
                        st.status = OntStatus::PowerFail;
                    }
                }
            }
        }
    }

    /// Map an ietf-alarms `resource` string onto a tracked ONT serial.
    /// Handles the simple `onu:<serial>` form and instance-identifier paths
    /// that embed the serial anywhere in the string.
    fn resolve_alarm_serial(map: &DashMap<String, OntState>, resource: &str) -> Option<String> {
        if let Some(s) = resource.strip_prefix("onu:") {
            return Some(s.trim().to_string());
        }
        map.iter()
            .map(|e| e.key().clone())
            .find(|serial| !serial.is_empty() && resource.contains(serial.as_str()))
    }

    /// Remove entries not seen within `retention`. Returns how many were pruned.
    fn prune_stale_onts(
        map: &DashMap<String, OntState>,
        now: chrono::DateTime<chrono::Utc>,
        retention: chrono::Duration,
    ) -> usize {
        let before = map.len();
        map.retain(|_, s| now.signed_duration_since(s.last_seen) < retention);
        before - map.len()
    }

    /// Convert the state table into the normalized OntData schema.
    fn snapshot_ont_data(map: &DashMap<String, OntState>) -> Vec<OntData> {
        map.iter()
            .map(|entry| {
                let s = entry.value();
                let offline_ish = matches!(
                    s.status,
                    OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut
                );
                OntData {
                    serial_number: s.serial.clone(),
                    pon_port: s.channel_term.clone(),
                    ont_index: s.onu_id,
                    status: s.status.clone(),
                    // Only meaningful for ONTs that are actually down.
                    last_down_cause: if !offline_ish {
                        None
                    } else if let Some(cause) = &s.last_down_cause {
                        Some(cause.clone())
                    } else if s.dying_gasp {
                        Some("dying_gasp".into())
                    } else if s.status == OntStatus::FiberCut {
                        Some("fiber_cut".into())
                    } else {
                        None
                    },
                    uptime_seconds: None,
                    rx_power_dbm: s.olt_rx_power_dbm,
                    tx_power_dbm: s.ont_tx_power_dbm,
                    distance_meters: s.distance_m.map(|d| d as u32),
                    vendor_id: Some("ADTN".into()),
                    equipment_id: None,
                    firmware_version: None,
                    in_octets: None,
                    out_octets: None,
                    fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                    eth_speed_mbps: None,
                    extended: if s.ont_rx_power_dbm.is_some()
                        || s.ont_temperature_c.is_some()
                        || s.ont_voltage_v.is_some()
                        || s.ont_bias_current_ma.is_some()
                    {
                        Some(ExtendedOntMetrics {
                            ont_rx_power_dbm: s.ont_rx_power_dbm,
                            ont_temperature_c: s.ont_temperature_c,
                            ont_voltage_v: s.ont_voltage_v,
                            ont_bias_current_ma: s.ont_bias_current_ma,
                        })
                    } else {
                        None
                    },
                }
            })
            .collect()
    }

    // ── Notification listener (best-effort enhancement) ────────────────────

    /// Spawn (or respawn) the background notification listener. Dying gasps
    /// arrive in the seconds after a power cut — a poll-only agent misses
    /// them if the alarm clears before the next cycle.
    fn ensure_notification_listener(&self) {
        if self.notif_unsupported.load(Ordering::Relaxed) {
            return;
        }
        let Some(nc) = self.config.netconf.clone() else {
            return;
        };

        let mut guard = self.notif_task.lock().unwrap();
        if guard.as_ref().map(|h| !h.is_finished()).unwrap_or(false) {
            return; // still running
        }

        let ip = self.config.ip.clone();
        let olt_id = self.olt_id.clone();
        let map = Arc::clone(&self.ont_state);
        let unsupported = Arc::clone(&self.notif_unsupported);
        *guard = Some(tokio::spawn(async move {
            notification_loop(ip, nc, olt_id, map, unsupported).await;
        }));
    }

    /// SNMP fallback — basic ONT data using Adtran enterprise MIBs.
    ///
    /// Adtran's IANA Private Enterprise Number is 664 (verified 2026-07-02:
    /// https://www.iana.org/assignments/enterprise-numbers/?q=adtran).
    /// The previously used 18070 belongs to BTI Photonic Systems (bti7000
    /// optical line, later acquired by Juniper — iana.org ?q=18070), so
    /// walks under it could never return Adtran data.
    ///
    /// NOTE: per Adtran's SDX 6000-series data sheet
    /// (adtran.com/-/media/adtran/resources/data-sheets/pdfs/sdx-6000-series.pdf)
    /// the SDX 6320/6330 are managed exclusively via NETCONF/YANG — they
    /// expose no SNMP agent. This fallback can only serve older Adtran OLT
    /// lines, and the table layout below is still unverified against a real
    /// walk; a zero-row serial table is therefore reported as an error, not
    /// as an empty (mass-offline) success.
    async fn collect_via_snmp_fallback(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp_cfg = self.config.snmp.as_ref().ok_or_else(|| {
            anyhow::anyhow!("SNMP fallback not configured for Adtran SDX")
        })?;

        warn!(
            olt = %self.olt_id,
            "Using SNMP fallback (limited data, no ONT-side power; SDX 6320/6330 \
             have no SNMP agent — expected to work only on legacy Adtran OLTs)"
        );

        let snmp = crate::snmp::SnmpPoller::new(&self.config.ip, snmp_cfg)?;

        // Adtran enterprise subtree (PEN 664). Sub-OID layout unverified —
        // see doc comment above.
        const ONU_SERIAL_PREFIX: &str = "1.3.6.1.4.1.664.100.1.1.14.2.1.2";
        const ONU_STATE_PREFIX: &str = "1.3.6.1.4.1.664.100.1.1.14.2.1.5";
        const ONU_RX_POWER_PREFIX: &str = "1.3.6.1.4.1.664.100.1.1.14.2.1.8";
        const ONU_DISTANCE_PREFIX: &str = "1.3.6.1.4.1.664.100.1.1.14.2.1.10";

        // Walk failures (including PartialWalk) must surface: an
        // `.unwrap_or_default()` here turns a mid-walk timeout into a clean
        // "0 ONTs" — i.e. a phantom mass outage.
        let serials = snmp.walk_table(ONU_SERIAL_PREFIX).await?;
        let states = snmp.walk_table(ONU_STATE_PREFIX).await?;
        let rx_powers = snmp.walk_table(ONU_RX_POWER_PREFIX).await?;
        let distances = snmp.walk_table(ONU_DISTANCE_PREFIX).await?;

        if serials.is_empty() {
            return Err(anyhow::anyhow!(
                "SNMP fallback walk of the Adtran ONU serial table ({}) returned zero \
                 rows — either this device exposes no Adtran GPON MIB (SDX 6320/6330 \
                 have no SNMP agent at all) or the table layout differs. Refusing to \
                 report 0 ONTs as success.",
                ONU_SERIAL_PREFIX
            ));
        }

        let mut onts = Vec::new();
        for serial_entry in &serials {
            let serial = match &serial_entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };
            if serial.is_empty() {
                continue;
            }

            // Extract OID suffix for cross-referencing with other tables
            let suffix = snmp_helper::extract_oid_suffix(&serial_entry.oid, 2);

            let status = states
                .iter()
                .find(|v| v.oid.ends_with(&suffix))
                .and_then(|v| match &v.value {
                    crate::snmp::SnmpData::Integer(i) => Some(*i),
                    _ => None,
                })
                .map(|s| match s {
                    1 => OntStatus::Online,
                    2 => OntStatus::Offline,
                    _ => OntStatus::Unknown,
                })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = rx_powers
                .iter()
                .find(|v| v.oid.ends_with(&suffix))
                .and_then(|v| match &v.value {
                    crate::snmp::SnmpData::Integer(i) => Some(*i),
                    _ => None,
                })
                .map(|r| r as f64 / 500.0);

            let distance = distances
                .iter()
                .find(|v| v.oid.ends_with(&suffix))
                .and_then(|v| match &v.value {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as u32),
                    crate::snmp::SnmpData::Gauge32(g) => Some(*g),
                    _ => None,
                });

            // Parse intf_id.onu_id from SNMP suffix
            let parts: Vec<&str> = suffix.splitn(2, '.').collect();
            let pon_port = parts.first().map(|p| format!("0/{}", p)).unwrap_or_default();
            let ont_index: u32 = parts.get(1).and_then(|p| p.parse().ok()).unwrap_or(0);

            onts.push(OntData {
                serial_number: serial,
                pon_port,
                ont_index,
                status,
                last_down_cause: None,
                uptime_seconds: None,
                rx_power_dbm: rx_power,
                tx_power_dbm: None,
                distance_meters: distance,
                vendor_id: Some("ADTN".into()),
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }

        info!(
            olt = %self.olt_id,
            onts = onts.len(),
            "SNMP fallback collection complete"
        );

        Ok(onts)
    }

    /// Build PON port summary from collected ONT data.
    fn build_pon_ports(onts: &[OntData]) -> Vec<PonPortData> {
        let mut ports = std::collections::HashMap::new();
        for ont in onts {
            let entry = ports
                .entry(ont.pon_port.clone())
                .or_insert(PonPortData {
                    port_id: ont.pon_port.clone(),
                    oper_status: "up".into(),
                    onts_registered: 0,
                    onts_online: 0,
                    onts_offline: 0,
                    bw_down_bps: 0,
                    bw_up_bps: 0,
                    utilization_percent: 0.0,
                });
            entry.onts_registered += 1;
            match ont.status {
                OntStatus::Online | OntStatus::LowSignal => entry.onts_online += 1,
                _ => entry.onts_offline += 1,
            }
        }
        ports.into_values().collect()
    }
}

// ── Notification listener implementation ────────────────────────────────────

/// Keep a NETCONF notification session alive between polls (best effort).
/// Reconnects with exponential backoff; gives up permanently if the server
/// does not support notifications (ietf-alarms polling remains the primary
/// down-cause source either way).
async fn notification_loop(
    ip: String,
    nc: NetconfConfig,
    olt_id: String,
    map: Arc<DashMap<String, OntState>>,
    unsupported: Arc<AtomicBool>,
) {
    let mut backoff_secs = 30u64;
    loop {
        match run_notification_session(&ip, &nc, &olt_id, &map).await {
            NotifSessionEnd::Unsupported(reason) => {
                info!(
                    olt = %olt_id,
                    reason = %reason,
                    "NETCONF notifications unsupported — dying-gasp capture relies on \
                     ietf-alarms polling only"
                );
                unsupported.store(true, Ordering::Relaxed);
                return;
            }
            NotifSessionEnd::Disconnected(e) => {
                warn!(
                    olt = %olt_id,
                    error = %e,
                    retry_secs = backoff_secs,
                    "NETCONF notification session ended; will reconnect"
                );
            }
        }
        tokio::time::sleep(std::time::Duration::from_secs(backoff_secs)).await;
        backoff_secs = (backoff_secs * 2).min(600);
    }
}

enum NotifSessionEnd {
    /// Server lacks notification support — stop retrying.
    Unsupported(String),
    /// Transport-level failure — retry with backoff.
    Disconnected(anyhow::Error),
}

async fn run_notification_session(
    ip: &str,
    nc: &NetconfConfig,
    olt_id: &str,
    map: &DashMap<String, OntState>,
) -> NotifSessionEnd {
    let mut session = match netconf::NetconfSession::connect(
        ip,
        nc.port,
        &nc.username,
        nc.password.as_deref(),
        nc.key_file.as_deref(),
    )
    .await
    {
        Ok(s) => s,
        Err(e) => return NotifSessionEnd::Disconnected(e),
    };

    if !session.has_capability("notification") {
        let _ = session.close().await;
        return NotifSessionEnd::Unsupported(
            "server hello does not advertise urn:ietf:params:netconf:capability:notification".into(),
        );
    }

    if let Err(e) = session.create_subscription(None).await {
        // An rpc-error on create-subscription means the operation itself is
        // rejected — retrying won't help. Anything else is transport.
        let msg = e.to_string();
        if msg.contains("rpc-error") {
            return NotifSessionEnd::Unsupported(msg);
        }
        return NotifSessionEnd::Disconnected(e);
    }

    info!(olt = %olt_id, "NETCONF notification subscription established");

    loop {
        let raw = match session.read_notification().await {
            Ok(n) => n,
            Err(e) => return NotifSessionEnd::Disconnected(e),
        };
        handle_notification(map, olt_id, &raw);
    }
}

/// Process one NETCONF notification: dying-gasp alarms and ONU state changes.
fn handle_notification(map: &DashMap<String, OntState>, olt_id: &str, raw: &str) {
    match xml::parse_dying_gasp(raw) {
        Ok(Some((serial, true))) => {
            info!(olt = %olt_id, serial = %serial, "Dying gasp received — power outage at ONT");
            record_dying_gasp(map, &serial);
            return;
        }
        Ok(_) => {}
        Err(e) => {
            warn!(olt = %olt_id, error = %e, "Unparseable NETCONF notification");
            return;
        }
    }

    match xml::parse_onu_state_change_notification(raw) {
        Ok(Some(entry)) => {
            debug!(
                olt = %olt_id,
                serial = %entry.serial_number,
                state = ?entry.state,
                "ONU state-change notification"
            );
            AdtranCollector::apply_state_entries(map, &[entry], chrono::Utc::now());
        }
        Ok(None) => {}
        Err(e) => {
            warn!(olt = %olt_id, error = %e, "Unparseable NETCONF notification");
        }
    }
}

/// Record a dying gasp for an ONT (creating a minimal entry if the poll
/// loop has not seen it yet).
fn record_dying_gasp(map: &DashMap<String, OntState>, serial: &str) {
    let mut st = map.entry(serial.to_string()).or_insert_with(|| {
        OntState::new(
            serial.to_string(),
            0,
            String::new(),
            OntStatus::Unknown,
            chrono::Utc::now(),
        )
    });
    st.dying_gasp = true;
    st.last_down_cause = Some("dying_gasp".into());
    if matches!(st.status, OntStatus::Offline | OntStatus::FiberCut) {
        st.status = OntStatus::PowerFail;
    }
}

/// Map BBF TR-385 ONU state to our OntStatus enum.
pub fn yang_state_to_ont_status(state: &OntYangState, had_dying_gasp: bool) -> OntStatus {
    match state {
        OntYangState::OnlineOnIntended => OntStatus::Online,
        OntYangState::Registering => OntStatus::Unknown,
        OntYangState::Offline => {
            if had_dying_gasp {
                OntStatus::PowerFail
            } else {
                OntStatus::FiberCut
            }
        }
        OntYangState::Unexpected | OntYangState::EmergencyStopped => OntStatus::Offline,
        OntYangState::Unknown(_) => OntStatus::Unknown,
    }
}

/// Convert equalization delay (TQ) to distance in meters.
pub fn eq_delay_to_meters(tq: u32) -> f64 {
    tq as f64 * TQ_TO_METERS
}

/// Convert Adtran raw optical power (0.002 dBm units) to dBm.
pub fn raw_power_to_dbm(raw: i64) -> f64 {
    raw as f64 / 500.0
}

#[async_trait]
impl OltCollector for AdtranCollector {
    fn olt_id(&self) -> &str {
        &self.olt_id
    }

    fn vendor_name(&self) -> &str {
        "adtran"
    }

    async fn collect(&self) -> anyhow::Result<OltData> {
        // Try NETCONF first (primary)
        let onts = match tokio::time::timeout(netconf_timeout(), self.collect_via_netconf())
            .await
        {
            Ok(Ok(data)) => data,
            Ok(Err(e)) => {
                warn!(
                    olt = %self.olt_id,
                    error = %e,
                    "NETCONF failed, trying SNMP fallback"
                );
                tokio::time::timeout(
                    snmp_fallback_timeout(),
                    self.collect_via_snmp_fallback(),
                )
                .await
                .map_err(|_| anyhow::anyhow!("SNMP fallback timed out"))??
            }
            Err(_) => {
                warn!(
                    olt = %self.olt_id,
                    timeout_secs = netconf_timeout().as_secs(),
                    "NETCONF timed out, trying SNMP fallback"
                );
                tokio::time::timeout(
                    snmp_fallback_timeout(),
                    self.collect_via_snmp_fallback(),
                )
                .await
                .map_err(|_| anyhow::anyhow!("SNMP fallback timed out"))??
            }
        };

        let pon_ports = Self::build_pon_ports(&onts);
        let model = self
            .device_model
            .lock()
            .unwrap()
            .clone()
            .unwrap_or_else(|| "SDX 6330-48".into());
        let firmware = self.device_firmware.lock().unwrap().clone().unwrap_or_default();

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "adtran".into(),
            model,
            firmware,
            serial: String::new(),
            uptime_seconds: 0,
            timestamp: chrono::Utc::now(),
            cpu_percent: None,
            memory_percent: None,
            temperature_celsius: None,
            power_supply_status: None,
            pon_ports,
            uplink_ports: Vec::new(),
            onts,
        })
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        if let Some(nc) = &self.config.netconf {
            let mut session = netconf::NetconfSession::connect(
                &self.config.ip,
                nc.port,
                &nc.username,
                nc.password.as_deref(),
                nc.key_file.as_deref(),
            )
            .await?;

            let has_xpon = session.has_capability("bbf-xpon");
            // Matches both bbf-xpon-onu-state (current) and -states (legacy)
            let has_onu_state = session.has_capability("bbf-xpon-onu-state");
            let has_notification = session.has_capability("notification");
            let has_alarms = session.has_capability("ietf-alarms");
            let has_yang_library =
                AdtranCollector::fetch_yang_library(&mut session).await.is_some();

            info!(
                olt = %self.olt_id,
                bbf_xpon = has_xpon,
                onu_state = has_onu_state,
                notifications = has_notification,
                ietf_alarms = has_alarms,
                yang_library = has_yang_library,
                "Adtran NETCONF connectivity verified"
            );

            let _ = session.close().await;
            Ok(true)
        } else {
            // Fallback: just check SNMP reachability
            warn!(olt = %self.olt_id, "No NETCONF config, testing SNMP only");
            Ok(true)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mk_state(
        serial: &str,
        status: OntStatus,
        last_seen: chrono::DateTime<chrono::Utc>,
        dying_gasp: bool,
    ) -> OntState {
        let mut s = OntState::new(serial.to_string(), 1, "CTP-0/1".into(), status, last_seen);
        s.dying_gasp = dying_gasp;
        s
    }

    fn mk_module(name: &str, revision: &str, namespace: &str) -> xml::YangModule {
        xml::YangModule {
            name: name.to_string(),
            revision: Some(revision.to_string()),
            namespace: Some(namespace.to_string()),
        }
    }

    #[test]
    fn test_yang_state_to_ont_status() {
        assert_eq!(
            yang_state_to_ont_status(&OntYangState::OnlineOnIntended, false),
            OntStatus::Online
        );
        assert_eq!(
            yang_state_to_ont_status(&OntYangState::Offline, true),
            OntStatus::PowerFail
        );
        assert_eq!(
            yang_state_to_ont_status(&OntYangState::Offline, false),
            OntStatus::FiberCut
        );
        assert_eq!(
            yang_state_to_ont_status(&OntYangState::Registering, false),
            OntStatus::Unknown
        );
    }

    #[test]
    fn test_eq_delay_to_meters() {
        // 164800 TQ * 0.0125 = 2060.0 metres
        assert!((eq_delay_to_meters(164800) - 2060.0).abs() < 0.01);
        // 240000 TQ * 0.0125 = 3000.0 metres
        assert!((eq_delay_to_meters(240000) - 3000.0).abs() < 0.01);
        // 0 TQ = 0 metres
        assert!((eq_delay_to_meters(0)).abs() < 0.01);
    }

    #[test]
    fn test_raw_power_to_dbm() {
        // -11050 / 500 = -22.1 dBm
        assert!((raw_power_to_dbm(-11050) - (-22.1)).abs() < 0.01);
        // -12500 / 500 = -25.0 dBm
        assert!((raw_power_to_dbm(-12500) - (-25.0)).abs() < 0.01);
        // 1200 / 500 = 2.4 dBm
        assert!((raw_power_to_dbm(1200) - 2.4).abs() < 0.01);
    }

    // ── yang-library-driven filter selection ────────────────────────────────

    #[test]
    fn test_filter_selection_current_module() {
        // Firmware implementing the CURRENT singular module (TR-385 Issue 2/3)
        let modules = vec![
            mk_module(
                "ietf-interfaces",
                "2018-02-20",
                "urn:ietf:params:xml:ns:yang:ietf-interfaces",
            ),
            mk_module(
                "bbf-xpon-onu-state",
                "2024-04-23",
                "urn:bbf:yang:bbf-xpon-onu-state",
            ),
        ];
        let filters = AdtranCollector::ont_state_filters_for_modules(Some(&modules));
        assert_eq!(filters, vec![FILTER_ONT_STATE_CURRENT]);
        assert!(filters[0].contains("urn:bbf:yang:bbf-xpon-onu-state\""));
        assert!(filters[0].contains("onus-present-on-local-channel-termination"));
        assert!(filters[0].contains("interfaces-state"));
    }

    #[test]
    fn test_filter_selection_legacy_plural_module() {
        // TR-385 Issue 1 / OB-BAA era firmware
        let modules = vec![mk_module(
            "bbf-xpon-onu-states",
            "2018-10-01",
            "urn:bbf:yang:bbf-xpon-onu-states",
        )];
        let filters = AdtranCollector::ont_state_filters_for_modules(Some(&modules));
        assert_eq!(filters.len(), 2);
        assert!(filters[0].contains("urn:bbf:yang:bbf-xpon-onu-states"));
        assert_eq!(filters[1], FILTER_ONT_STATE_XPON_ROOTED);
    }

    #[test]
    fn test_filter_selection_unknown_modules_tries_everything() {
        let modules = vec![mk_module(
            "ietf-system",
            "2014-08-06",
            "urn:ietf:params:xml:ns:yang:ietf-system",
        )];
        let filters = AdtranCollector::ont_state_filters_for_modules(Some(&modules));
        assert_eq!(filters.len(), 3);
    }

    #[test]
    fn test_filter_selection_no_yang_library_tries_everything() {
        let filters = AdtranCollector::ont_state_filters_for_modules(None);
        assert_eq!(
            filters,
            vec![
                FILTER_ONT_STATE_CURRENT,
                FILTER_ONT_STATE_LEGACY_PLURAL,
                FILTER_ONT_STATE_XPON_ROOTED,
            ]
        );
    }

    // ── Empty-data plausibility ─────────────────────────────────────────────

    #[test]
    fn test_empty_ont_state_reply_is_error_never_zero_onts() {
        // First contact, zero entries: still an error (filter mismatch is
        // indistinguishable from an OLT with no ONTs — refuse to guess).
        assert!(AdtranCollector::validate_ont_state_reply(0, 0).is_err());

        // Previously saw thousands of ONTs, now zero: definitely suspect.
        let err = AdtranCollector::validate_ont_state_reply(0, 4096).unwrap_err();
        assert!(err.to_string().contains("4096"));

        // Non-empty replies are fine.
        assert!(AdtranCollector::validate_ont_state_reply(1, 0).is_ok());
        assert!(AdtranCollector::validate_ont_state_reply(4000, 4096).is_ok());
    }

    // ── ietf-alarms → last_down_cause ───────────────────────────────────────

    #[test]
    fn test_apply_alarms_populates_last_down_cause() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        map.insert(
            "ADTN-PWR".to_string(),
            mk_state("ADTN-PWR", OntStatus::FiberCut, now, false),
        );
        map.insert(
            "ADTN-LOS".to_string(),
            mk_state("ADTN-LOS", OntStatus::FiberCut, now, false),
        );

        let alarms = vec![
            xml::AlarmEntry {
                // instance-identifier style resource — matched by substring
                resource: "/if:interfaces-state/if:interface[if:name='onu ADTN-PWR']".into(),
                alarm_type_id: "bbf-xpon-def:dgi".into(),
                alarm_type_qualifier: None,
                is_cleared: false,
                perceived_severity: Some("critical".into()),
                last_changed: None,
            },
            xml::AlarmEntry {
                resource: "onu:ADTN-LOS".into(),
                alarm_type_id: "bbf-xpon-def:lobi".into(),
                alarm_type_qualifier: None,
                is_cleared: false,
                perceived_severity: Some("major".into()),
                last_changed: None,
            },
        ];

        AdtranCollector::apply_alarms(&map, &alarms);

        // Dying gasp: cause recorded AND FiberCut upgraded to PowerFail.
        let pwr = map.get("ADTN-PWR").unwrap();
        assert_eq!(pwr.last_down_cause.as_deref(), Some("dying_gasp"));
        assert!(pwr.dying_gasp);
        assert_eq!(pwr.status, OntStatus::PowerFail);

        // Loss of burst: cause recorded, stays FiberCut.
        let los = map.get("ADTN-LOS").unwrap();
        assert_eq!(los.last_down_cause.as_deref(), Some("loss_of_burst"));
        assert_eq!(los.status, OntStatus::FiberCut);
    }

    #[test]
    fn test_apply_alarms_active_wins_over_cleared() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        map.insert(
            "ADTN-X".to_string(),
            mk_state("ADTN-X", OntStatus::FiberCut, now, false),
        );

        let alarms = vec![
            xml::AlarmEntry {
                resource: "onu:ADTN-X".into(),
                alarm_type_id: "bbf-xpon-def:dgi".into(),
                alarm_type_qualifier: None,
                is_cleared: false,
                perceived_severity: Some("critical".into()),
                last_changed: None,
            },
            xml::AlarmEntry {
                resource: "onu:ADTN-X".into(),
                alarm_type_id: "bbf-xpon-def:lobi".into(),
                alarm_type_qualifier: None,
                is_cleared: true,
                perceived_severity: Some("cleared".into()),
                last_changed: None,
            },
        ];

        AdtranCollector::apply_alarms(&map, &alarms);
        // The active dgi must win over the cleared lobi regardless of order.
        let st = map.get("ADTN-X").unwrap();
        assert_eq!(st.last_down_cause.as_deref(), Some("dying_gasp"));
    }

    #[test]
    fn test_alarms_flow_into_ont_data_last_down_cause() {
        let map = DashMap::new();
        let now = chrono::Utc::now();

        let entries = vec![
            xml::OntStateEntry {
                serial_number: "ADTN-DOWN".into(),
                onu_id: 1,
                channel_term: "CTP-0/1".into(),
                state: OntYangState::Offline,
                detected_datetime: None,
                v_ani_ref: None,
            },
            xml::OntStateEntry {
                serial_number: "ADTN-UP".into(),
                onu_id: 2,
                channel_term: "CTP-0/1".into(),
                state: OntYangState::OnlineOnIntended,
                detected_datetime: None,
                v_ani_ref: None,
            },
        ];
        AdtranCollector::apply_state_entries(&map, &entries, now);

        AdtranCollector::apply_alarms(
            &map,
            &[xml::AlarmEntry {
                resource: "onu:ADTN-DOWN".into(),
                alarm_type_id: "bbf-xpon-def:dgi".into(),
                alarm_type_qualifier: None,
                is_cleared: false,
                perceived_severity: Some("critical".into()),
                last_changed: None,
            }],
        );

        let onts = AdtranCollector::snapshot_ont_data(&map);
        let down = onts.iter().find(|o| o.serial_number == "ADTN-DOWN").unwrap();
        assert_eq!(down.last_down_cause.as_deref(), Some("dying_gasp"));
        assert_eq!(down.status, OntStatus::PowerFail);

        // Online ONTs never carry a down cause.
        let up = onts.iter().find(|o| o.serial_number == "ADTN-UP").unwrap();
        assert_eq!(up.status, OntStatus::Online);
        assert!(up.last_down_cause.is_none());
    }

    #[test]
    fn test_online_recovery_clears_down_cause() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        let mut st = mk_state("ADTN-REC", OntStatus::PowerFail, now, true);
        st.last_down_cause = Some("dying_gasp".into());
        map.insert("ADTN-REC".to_string(), st);

        AdtranCollector::apply_state_entries(
            &map,
            &[xml::OntStateEntry {
                serial_number: "ADTN-REC".into(),
                onu_id: 1,
                channel_term: "CTP-0/1".into(),
                state: OntYangState::OnlineOnIntended,
                detected_datetime: None,
                v_ani_ref: None,
            }],
            now,
        );

        let st = map.get("ADTN-REC").unwrap();
        assert_eq!(st.status, OntStatus::Online);
        assert!(!st.dying_gasp);
        assert!(st.last_down_cause.is_none());
    }

    // ── Dying-gasp notifications ────────────────────────────────────────────

    #[test]
    fn test_dying_gasp_notification_updates_state() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        map.insert(
            "ADTN153201C4".to_string(),
            mk_state("ADTN153201C4", OntStatus::Online, now, false),
        );

        let notif = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-07-02T08:15:00Z</eventTime>
  <alarm-notification xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms">
    <resource>onu:ADTN153201C4</resource>
    <alarm-type-id>bbf-xpon-defects:dgi</alarm-type-id>
    <perceived-severity>critical</perceived-severity>
  </alarm-notification>
</notification>"#;
        // parse_dying_gasp keys on "dying-gasp" in the type; the dgi identity
        // path is covered via ietf-alarms polling. Use the vendor spelling here.
        let notif = notif.replace("bbf-xpon-defects:dgi", "adtran:onu-dying-gasp");
        handle_notification(&map, "test-olt", &notif);

        let st = map.get("ADTN153201C4").unwrap();
        assert!(st.dying_gasp);
        assert_eq!(st.last_down_cause.as_deref(), Some("dying_gasp"));
    }

    #[test]
    fn test_state_change_notification_marks_offline_with_gasp_as_power_fail() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        let mut st = mk_state("ADTN-N1", OntStatus::Online, now, true);
        st.last_down_cause = Some("dying_gasp".into());
        map.insert("ADTN-N1".to_string(), st);

        let notif = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-07-02T08:15:10Z</eventTime>
  <onu-state-change xmlns="urn:bbf:yang:bbf-xpon-onu-states">
    <detected-serial-number>ADTN-N1</detected-serial-number>
    <onu-id>1</onu-id>
    <channel-termination-ref>CTP-0/1</channel-termination-ref>
    <onu-state>onu-not-present-with-v-ani</onu-state>
  </onu-state-change>
</notification>"#;
        handle_notification(&map, "test-olt", notif);

        let st = map.get("ADTN-N1").unwrap();
        // Offline + prior dying gasp = power outage, not fibre cut.
        assert_eq!(st.status, OntStatus::PowerFail);
    }

    // ── Ghost-entry pruning / absence handling ──────────────────────────────

    #[test]
    fn test_prune_stale_onts() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        map.insert(
            "FRESH".to_string(),
            mk_state("FRESH", OntStatus::Online, now - chrono::Duration::hours(1), false),
        );
        map.insert(
            "STALE".to_string(),
            mk_state("STALE", OntStatus::Online, now - chrono::Duration::days(8), false),
        );
        map.insert(
            "EDGE".to_string(),
            mk_state("EDGE", OntStatus::FiberCut, now - chrono::Duration::days(6), false),
        );

        let pruned =
            AdtranCollector::prune_stale_onts(&map, now, chrono::Duration::days(7));
        assert_eq!(pruned, 1);
        assert!(map.contains_key("FRESH"));
        assert!(map.contains_key("EDGE"));
        assert!(!map.contains_key("STALE"), "8-day-old entry must be pruned");
    }

    #[test]
    fn test_absent_onts_marked_offline_not_ghost_online() {
        let map = DashMap::new();
        let now = chrono::Utc::now();
        map.insert(
            "PRESENT".to_string(),
            mk_state("PRESENT", OntStatus::Online, now, false),
        );
        map.insert(
            "VANISHED".to_string(),
            mk_state("VANISHED", OntStatus::Online, now - chrono::Duration::minutes(5), false),
        );
        map.insert(
            "VANISHED-GASP".to_string(),
            mk_state(
                "VANISHED-GASP",
                OntStatus::Online,
                now - chrono::Duration::minutes(5),
                true,
            ),
        );
        map.insert(
            "ALREADY-DOWN".to_string(),
            mk_state("ALREADY-DOWN", OntStatus::Offline, now - chrono::Duration::hours(2), false),
        );

        let seen: HashSet<String> = ["PRESENT".to_string()].into_iter().collect();
        AdtranCollector::mark_absent_onts_offline(&map, &seen);

        assert_eq!(map.get("PRESENT").unwrap().status, OntStatus::Online);
        // No dying gasp: assume plant fault.
        assert_eq!(map.get("VANISHED").unwrap().status, OntStatus::FiberCut);
        // With dying gasp: power outage.
        assert_eq!(map.get("VANISHED-GASP").unwrap().status, OntStatus::PowerFail);
        // Already-offline entries are left alone.
        assert_eq!(map.get("ALREADY-DOWN").unwrap().status, OntStatus::Offline);
    }

    // ── Existing behaviour kept ─────────────────────────────────────────────

    #[test]
    fn test_ont_state_table() {
        let state_table = DashMap::new();
        let now = chrono::Utc::now();

        let mut st = mk_state("ADTN153201C4", OntStatus::Online, now, false);
        st.olt_rx_power_dbm = Some(-22.1);
        st.ont_rx_power_dbm = Some(-25.0);
        st.ont_tx_power_dbm = Some(2.4);
        st.ont_temperature_c = Some(45.5);
        st.ont_voltage_v = Some(3.3);
        st.ont_bias_current_ma = Some(12.5);
        st.distance_m = Some(2060.0);
        state_table.insert("ADTN153201C4".to_string(), st);

        assert!(state_table.contains_key("ADTN153201C4"));
        let entry = state_table.get("ADTN153201C4").unwrap();
        assert_eq!(entry.status, OntStatus::Online);
        assert!((entry.olt_rx_power_dbm.unwrap() - (-22.1)).abs() < 0.01);
        assert!((entry.distance_m.unwrap() - 2060.0).abs() < 0.01);
    }

    #[test]
    fn test_ont_state_dying_gasp_differentiates() {
        // ONT goes offline WITH dying gasp → PowerFail (power outage)
        let status = yang_state_to_ont_status(&OntYangState::Offline, true);
        assert_eq!(status, OntStatus::PowerFail);

        // ONT goes offline WITHOUT dying gasp → FiberCut
        let status = yang_state_to_ont_status(&OntYangState::Offline, false);
        assert_eq!(status, OntStatus::FiberCut);
    }

    #[test]
    fn test_build_pon_ports() {
        let onts = vec![
            OntData {
                serial_number: "ADTN001".into(),
                pon_port: "CTP-0/1".into(),
                ont_index: 1,
                status: OntStatus::Online,
                last_down_cause: None,
                uptime_seconds: None,
                rx_power_dbm: Some(-22.0),
                tx_power_dbm: None,
                distance_meters: Some(1000),
                vendor_id: Some("ADTN".into()),
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                eth_speed_mbps: None,
                extended: None,
                ..Default::default()
            },
            OntData {
                serial_number: "ADTN002".into(),
                pon_port: "CTP-0/1".into(),
                ont_index: 2,
                status: OntStatus::Offline,
                last_down_cause: Some("fiber_cut".into()),
                uptime_seconds: None,
                rx_power_dbm: None,
                tx_power_dbm: None,
                distance_meters: Some(2000),
                vendor_id: Some("ADTN".into()),
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                eth_speed_mbps: None,
                extended: None,
                ..Default::default()
            },
            OntData {
                serial_number: "ADTN003".into(),
                pon_port: "CTP-0/2".into(),
                ont_index: 1,
                status: OntStatus::Online,
                last_down_cause: None,
                uptime_seconds: None,
                rx_power_dbm: Some(-24.0),
                tx_power_dbm: None,
                distance_meters: Some(3000),
                vendor_id: Some("ADTN".into()),
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                eth_speed_mbps: None,
                extended: None,
                ..Default::default()
            },
        ];

        let ports = AdtranCollector::build_pon_ports(&onts);
        assert_eq!(ports.len(), 2);

        let port_1 = ports.iter().find(|p| p.port_id == "CTP-0/1").unwrap();
        assert_eq!(port_1.onts_registered, 2);
        assert_eq!(port_1.onts_online, 1);
        assert_eq!(port_1.onts_offline, 1);

        let port_2 = ports.iter().find(|p| p.port_id == "CTP-0/2").unwrap();
        assert_eq!(port_2.onts_registered, 1);
        assert_eq!(port_2.onts_online, 1);
    }
}
