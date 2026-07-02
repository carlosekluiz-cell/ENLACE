// SPDX-License-Identifier: Apache-2.0
// XML parsers for BBF TR-385 YANG model responses (NETCONF).
//
// Parses NETCONF <rpc-reply> data for:
//   - <hello> capability URIs
//   - ONT state — tolerant of BOTH published generations of the BBF model
//     (verified 2026-07-02 against github.com/BroadbandForum/yang and
//     github.com/BroadbandForum/obbaa fixtures):
//       * CURRENT `bbf-xpon-onu-state` (SINGULAR — TR-385 Issue 2/3,
//         revisions 2019-02-25…2024-04-23,
//         standard/interface/bbf-xpon-onu-state.yang): leaf
//         `onu-presence-state` (identityref, base
//         bbf-xpon-onu-types:onu-presence-state-base), container
//         `onus-present-on-local-channel-termination` with
//         `list onu { key "detected-serial-number"; }`, augmenting
//         /if:interfaces-state/if:interface/bbf-xpon:channel-termination;
//         notification `onu-presence-state-change` nested under the
//         channel-termination.
//       * LEGACY `bbf-xpon-onu-states` (PLURAL — TR-385 Issue 1 /
//         OB-BAA R1.x era, ns urn:bbf:yang:bbf-xpon-onu-states): leaf
//         `onu-state`, top-level notification `onu-state-change` with
//         `channel-termination-ref` (see obbaa voltmf test fixture
//         onu-state-change-notification_1_0.txt).
//   - Optical power (OLT-side upstream rx, ONT-side OMCI transceiver)
//   - Ranging (equalization-delay TQ → distance meters)
//   - Interface octet counters (ietf-interfaces statistics, RFC 8343)
//   - xPON PHY FEC/BIP counters (bbf-xpon-performance-management)
//   - Notifications (onu-state-change, dying-gasp alarms)
//   - ietf-yang-library (RFC 7895 <modules-state> / RFC 8525 <yang-library>)
//   - ietf-alarms alarm-list (RFC 8632) for down-cause classification
//
// All parsers surface XML errors instead of silently truncating: a reply
// that fails to parse must never be read as "success with fewer ONTs".

use quick_xml::events::Event;
use quick_xml::Reader;
use tracing::debug;

// ── Capability parsing ──────────────────────────────────────────────────────

/// Parse capability URIs from a NETCONF `<hello>` message.
pub fn parse_capabilities(hello_xml: &str) -> anyhow::Result<Vec<String>> {
    let mut caps = Vec::new();
    let mut reader = Reader::from_str(hello_xml);
    let mut in_capability = false;
    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                if local_name(e.name().as_ref()) == b"capability" {
                    in_capability = true;
                }
            }
            Ok(Event::Text(e)) if in_capability => {
                if let Ok(text) = e.unescape() {
                    let cap = text.trim().to_string();
                    if !cap.is_empty() {
                        caps.push(cap);
                    }
                }
            }
            Ok(Event::End(e)) => {
                if local_name(e.name().as_ref()) == b"capability" {
                    in_capability = false;
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("<hello> capabilities", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    Ok(caps)
}

// ── rpc-error detection ─────────────────────────────────────────────────────

/// Namespace-aware detection of `<rpc-error>` in an `<rpc-reply>`.
///
/// A substring check for "<rpc-error>" misses prefixed forms such as
/// `<nc:rpc-error>` (RFC 6241 allows any prefix bound to the base
/// namespace) and would also false-positive on the literal text
/// "&lt;rpc-error&gt;" inside an error-message. This walks actual element
/// events and matches on the local name.
///
/// Returns a human-readable summary ("error-tag: error-message") of the
/// first rpc-error if one is present, or None. Tolerant of malformed XML —
/// scanning simply stops at the first parse error (the caller surfaces the
/// raw reply separately).
pub fn rpc_error_summary(reply_xml: &str) -> Option<String> {
    let mut reader = Reader::from_str(reply_xml);
    let mut buf = Vec::new();

    let mut in_rpc_error = false;
    let mut found = false;
    let mut error_tag = String::new();
    let mut error_message = String::new();
    let mut error_severity = String::new();
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) | Ok(Event::Empty(e)) => {
                let local = String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "rpc-error" {
                    in_rpc_error = true;
                    found = true;
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_rpc_error => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if !text.is_empty() {
                        match current_elem.as_str() {
                            "error-tag" if error_tag.is_empty() => {
                                error_tag = text.to_string()
                            }
                            "error-message" if error_message.is_empty() => {
                                error_message = text.to_string()
                            }
                            "error-severity" if error_severity.is_empty() => {
                                error_severity = text.to_string()
                            }
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                if local_name(e.name().as_ref()) == b"rpc-error" {
                    in_rpc_error = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(_) => break, // best-effort scan; caller handles unparseable replies
            _ => {}
        }
        buf.clear();
    }

    if found {
        let mut parts = Vec::new();
        if !error_severity.is_empty() {
            parts.push(error_severity);
        }
        if !error_tag.is_empty() {
            parts.push(error_tag);
        }
        if !error_message.is_empty() {
            parts.push(error_message);
        }
        if parts.is_empty() {
            Some("rpc-error (no detail provided)".to_string())
        } else {
            Some(parts.join(": "))
        }
    } else {
        None
    }
}

// ── ONT state parsing ───────────────────────────────────────────────────────

/// BBF TR-385 ONU state enumeration values.
#[derive(Debug, Clone, PartialEq)]
pub enum OntYangState {
    /// onu-present-and-on-intended-channel-termination — fully operational
    OnlineOnIntended,
    /// onu-present-and-in-wavelength-discovery — registering
    Registering,
    /// onu-present-and-unexpected — wrong CT
    Unexpected,
    /// onu-not-present (with or without v-ani) — offline
    Offline,
    /// onu-present-and-emergency-stopped
    EmergencyStopped,
    /// Unrecognized state string
    Unknown(String),
}

impl OntYangState {
    /// Parse a YANG onu-state value, handling optional namespace prefix.
    pub fn from_yang(s: &str) -> Self {
        let s = s.rsplit(':').next().unwrap_or(s);
        match s {
            "onu-present-and-on-intended-channel-termination" => Self::OnlineOnIntended,
            "onu-present-and-in-wavelength-discovery" => Self::Registering,
            "onu-present-and-unexpected" => Self::Unexpected,
            "onu-not-present" | "onu-not-present-with-v-ani" | "onu-not-present-without-v-ani" => {
                Self::Offline
            }
            "onu-present-and-emergency-stopped" => Self::EmergencyStopped,
            other => Self::Unknown(other.to_string()),
        }
    }

    pub fn is_online(&self) -> bool {
        matches!(self, Self::OnlineOnIntended)
    }
}

/// Parsed ONT state entry from BBF TR-385 YANG.
#[derive(Debug, Clone)]
pub struct OntStateEntry {
    pub serial_number: String,
    pub onu_id: u32,
    pub channel_term: String,
    pub state: OntYangState,
    pub detected_datetime: Option<String>,
    pub v_ani_ref: Option<String>,
}

/// Parse ONT state entries from a NETCONF `<rpc-reply>` containing BBF TR-385 data.
///
/// Tolerant of both published generations of the model:
///
/// Legacy (`bbf-xpon-onu-state`, singular):
/// `/bbf-xpon:xpon/channel-terminations/channel-termination/
///   bbf-xpon-onu-state:onus-present-on-channel-termination/onu/onu-state`
///
/// Current (`bbf-xpon-onu-states`, plural — channel-termination is an
/// augmentation of ietf-interfaces, see
/// https://github.com/BroadbandForum/yang):
/// `/if:interfaces-state/if:interface/bbf-xpon:channel-termination/
///   bbf-xpon-onu-states:onus-present-on-local-channel-termination/
///   onu/onu-presence-state`
pub fn parse_ont_state(xml: &str) -> anyhow::Result<Vec<OntStateEntry>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut current_channel_term = String::new();
    let mut current_serial = String::new();
    let mut current_onu_id: u32 = 0;
    let mut current_state = String::new();
    let mut current_datetime: Option<String> = None;
    let mut current_v_ani: Option<String> = None;
    let mut in_onu = false;
    let mut in_interface = false;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    // Current model: the channel termination is an
                    // <interface> whose <name> identifies it — the nested
                    // <channel-termination> container must NOT clear it.
                    // Legacy model: channel-termination list entries carry
                    // their own <name> and there is no interface ancestor.
                    "interface" => {
                        in_interface = true;
                        current_channel_term.clear();
                    }
                    "channel-termination" if !in_interface => {
                        current_channel_term.clear();
                    }
                    "onu" => {
                        in_onu = true;
                        current_serial.clear();
                        current_onu_id = 0;
                        current_state.clear();
                        current_datetime = None;
                        current_v_ani = None;
                    }
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }

                    if !in_onu {
                        if current_elem == "name" && current_channel_term.is_empty() {
                            current_channel_term = text.to_string();
                        }
                    } else {
                        match current_elem.as_str() {
                            "detected-serial-number" => current_serial = text.to_string(),
                            "onu-id" => current_onu_id = text.parse().unwrap_or(0),
                            // "onu-state": legacy enumeration leaf.
                            // "onu-presence-state": current identityref leaf
                            // (values live in bbf-xpon-onu-types and arrive
                            // prefixed; from_yang strips the prefix).
                            "onu-state" | "onu-presence-state" => {
                                current_state = text.to_string()
                            }
                            "onu-detected-datetime" => {
                                current_datetime = Some(text.to_string())
                            }
                            "v-ani-ref" => current_v_ani = Some(text.to_string()),
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu" && in_onu {
                    if !current_serial.is_empty() {
                        entries.push(OntStateEntry {
                            serial_number: current_serial.clone(),
                            onu_id: current_onu_id,
                            channel_term: current_channel_term.clone(),
                            state: OntYangState::from_yang(&current_state),
                            detected_datetime: current_datetime.clone(),
                            v_ani_ref: current_v_ani.clone(),
                        });
                    }
                    in_onu = false;
                } else if local == "interface" {
                    in_interface = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("ONT state reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed ONT state entries");
    Ok(entries)
}

// ── Optical power parsing ───────────────────────────────────────────────────

/// Parsed optical power readings from BBF TR-385 YANG.
#[derive(Debug, Clone)]
pub struct OpticalPowerEntry {
    pub serial_number: String,
    pub onu_id: u32,
    pub channel_term: String,
    /// OLT-side upstream rx power in dBm (raw integer / 500.0)
    pub olt_rx_power_dbm: Option<f64>,
    /// ONT-side rx power in dBm (OMCI via NETCONF, raw / 500.0)
    pub ont_rx_power_dbm: Option<f64>,
    /// ONT-side tx power in dBm (raw / 500.0)
    pub ont_tx_power_dbm: Option<f64>,
    /// ONT transceiver temperature in Celsius
    pub ont_temperature_c: Option<f64>,
    /// ONT supply voltage in Volts
    pub ont_voltage_v: Option<f64>,
    /// ONT laser bias current in mA
    pub ont_bias_current_ma: Option<f64>,
}

/// Parse optical power entries from a NETCONF response.
///
/// Power values from BBF TR-385 are integers in 0.002 dBm units.
/// Conversion: `dBm = raw_integer / 500.0`
///
/// Tolerant of both bbf-xpon-onu-state (legacy) and bbf-xpon-onu-states
/// (current, channel-termination under ietf-interfaces) reply structures.
pub fn parse_optical_power(xml: &str) -> anyhow::Result<Vec<OpticalPowerEntry>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut current_channel_term = String::new();
    let mut current_serial = String::new();
    let mut current_onu_id: u32 = 0;
    let mut olt_rx_raw: Option<i64> = None;
    let mut ont_rx_raw: Option<i64> = None;
    let mut ont_tx_raw: Option<i64> = None;
    let mut ont_temp_raw: Option<i64> = None;
    let mut ont_voltage_raw: Option<i64> = None;
    let mut ont_bias_raw: Option<i64> = None;
    let mut in_onu = false;
    let mut in_interface = false;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "interface" => {
                        in_interface = true;
                        current_channel_term.clear();
                    }
                    "channel-termination" if !in_interface => current_channel_term.clear(),
                    "onu" => {
                        in_onu = true;
                        current_serial.clear();
                        current_onu_id = 0;
                        olt_rx_raw = None;
                        ont_rx_raw = None;
                        ont_tx_raw = None;
                        ont_temp_raw = None;
                        ont_voltage_raw = None;
                        ont_bias_raw = None;
                    }
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }

                    if !in_onu && current_elem == "name" && current_channel_term.is_empty() {
                        current_channel_term = text.to_string();
                    } else if in_onu {
                        match current_elem.as_str() {
                            "detected-serial-number" => current_serial = text.to_string(),
                            "onu-id" => current_onu_id = text.parse().unwrap_or(0),
                            // OLT-side upstream rx power (0.002 dBm units → raw/500)
                            "measured-upstream-rx-optical-power-dbm" => {
                                olt_rx_raw = text.parse().ok();
                            }
                            // ONT-side OMCI rx power (0.002 dBm units)
                            "ani-transceiver-rx-power" | "rx-power" => {
                                ont_rx_raw = text.parse().ok();
                            }
                            // ONT-side tx power (0.002 dBm units)
                            "ani-transceiver-tx-power" | "tx-power"
                            | "mean-optical-launch-power" => {
                                ont_tx_raw = text.parse().ok();
                            }
                            // ONT temperature (raw integer / 500.0 = °C)
                            "ani-transceiver-temperature" | "transceiver-temperature"
                            | "temperature" => {
                                ont_temp_raw = text.parse().ok();
                            }
                            // ONT voltage (raw integer / 5000.0 = Volts)
                            "ani-transceiver-supply-voltage" | "supply-voltage" => {
                                ont_voltage_raw = text.parse().ok();
                            }
                            // ONT bias current (raw integer / 500.0 = mA)
                            "ani-transceiver-bias-current" | "bias-current" => {
                                ont_bias_raw = text.parse().ok();
                            }
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu" && in_onu {
                    if !current_serial.is_empty() {
                        entries.push(OpticalPowerEntry {
                            serial_number: current_serial.clone(),
                            onu_id: current_onu_id,
                            channel_term: current_channel_term.clone(),
                            olt_rx_power_dbm: olt_rx_raw.map(|r| r as f64 / 500.0),
                            ont_rx_power_dbm: ont_rx_raw.map(|r| r as f64 / 500.0),
                            ont_tx_power_dbm: ont_tx_raw.map(|r| r as f64 / 500.0),
                            ont_temperature_c: ont_temp_raw.map(|r| r as f64 / 500.0),
                            ont_voltage_v: ont_voltage_raw.map(|r| r as f64 / 5000.0),
                            ont_bias_current_ma: ont_bias_raw.map(|r| r as f64 / 500.0),
                        });
                    }
                    in_onu = false;
                } else if local == "interface" {
                    in_interface = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("optical power reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed optical power entries");
    Ok(entries)
}

// ── Ranging / distance parsing ──────────────────────────────────────────────

/// Equalization delay TQ to meters conversion factor.
/// One TQ = 0.0125 meters (based on light speed in fibre, round-trip).
pub const TQ_TO_METERS: f64 = 0.0125;

/// Parsed ranging entry with equalization delay → distance conversion.
#[derive(Debug, Clone)]
pub struct RangingEntry {
    pub serial_number: String,
    pub onu_id: u32,
    pub channel_term: String,
    /// Raw equalization delay in TQ (time quanta)
    pub equalization_delay_tq: u32,
    /// Computed distance: `equalization_delay_tq * 0.0125` meters
    pub distance_m: f64,
}

/// Parse ranging (equalization-delay) entries from a NETCONF response.
///
/// Tolerant of both bbf-xpon-onu-state (legacy) and bbf-xpon-onu-states
/// (current) reply structures.
pub fn parse_ranging(xml: &str) -> anyhow::Result<Vec<RangingEntry>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut current_channel_term = String::new();
    let mut current_serial = String::new();
    let mut current_onu_id: u32 = 0;
    let mut current_eq_delay: Option<u32> = None;
    let mut in_onu = false;
    let mut in_interface = false;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "interface" => {
                        in_interface = true;
                        current_channel_term.clear();
                    }
                    "channel-termination" if !in_interface => current_channel_term.clear(),
                    "onu" => {
                        in_onu = true;
                        current_serial.clear();
                        current_onu_id = 0;
                        current_eq_delay = None;
                    }
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }

                    if !in_onu && current_elem == "name" && current_channel_term.is_empty() {
                        current_channel_term = text.to_string();
                    } else if in_onu {
                        match current_elem.as_str() {
                            "detected-serial-number" => current_serial = text.to_string(),
                            "onu-id" => current_onu_id = text.parse().unwrap_or(0),
                            "equalization-delay" => current_eq_delay = text.parse().ok(),
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu" && in_onu {
                    if !current_serial.is_empty() {
                        if let Some(eq_delay) = current_eq_delay {
                            entries.push(RangingEntry {
                                serial_number: current_serial.clone(),
                                onu_id: current_onu_id,
                                channel_term: current_channel_term.clone(),
                                equalization_delay_tq: eq_delay,
                                distance_m: eq_delay as f64 * TQ_TO_METERS,
                            });
                        }
                    }
                    in_onu = false;
                } else if local == "interface" {
                    in_interface = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("ranging reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed ranging entries");
    Ok(entries)
}

// ── ietf-yang-library parsing (RFC 7895 / RFC 8525) ────────────────────────

/// A YANG module advertised by the server's yang-library.
#[derive(Debug, Clone, PartialEq)]
pub struct YangModule {
    pub name: String,
    pub revision: Option<String>,
    pub namespace: Option<String>,
}

/// Parse the server's module list from an ietf-yang-library reply.
///
/// Handles both data trees (local-name based, so either works):
///   - RFC 7895:  /modules-state/module{name,revision,namespace}
///   - RFC 8525:  /yang-library/module-set/module{name,revision,namespace}
///
/// Namespace: urn:ietf:params:xml:ns:yang:ietf-yang-library
/// Submodule entries nested inside a module are ignored (their name/revision
/// must not overwrite the parent module's).
pub fn parse_yang_library(xml: &str) -> anyhow::Result<Vec<YangModule>> {
    let mut modules = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_module = false;
    let mut in_submodule = false;
    let mut name = String::new();
    let mut revision: Option<String> = None;
    let mut namespace: Option<String> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    // RFC 7895 list "module" and RFC 8525 module-set list
                    // "module"; "import-only-module" (RFC 8525) also names
                    // implemented-adjacent schemas — include it, it can only
                    // widen matching.
                    "module" | "import-only-module" if !in_module => {
                        in_module = true;
                        name.clear();
                        revision = None;
                        namespace = None;
                    }
                    "submodule" if in_module => in_submodule = true,
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_module && !in_submodule => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    match current_elem.as_str() {
                        "name" if name.is_empty() => name = text.to_string(),
                        "revision" if revision.is_none() => {
                            revision = Some(text.to_string())
                        }
                        "namespace" if namespace.is_none() => {
                            namespace = Some(text.to_string())
                        }
                        _ => {}
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "submodule" => in_submodule = false,
                    "module" | "import-only-module" if in_module && !in_submodule => {
                        if !name.is_empty() {
                            modules.push(YangModule {
                                name: name.clone(),
                                revision: revision.clone(),
                                namespace: namespace.clone(),
                            });
                        }
                        in_module = false;
                    }
                    _ => {}
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("yang-library reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = modules.len(), "Parsed yang-library modules");
    Ok(modules)
}

// ── ietf-alarms parsing (RFC 8632) ──────────────────────────────────────────

/// One entry from /alarms/alarm-list/alarm (RFC 8632).
#[derive(Debug, Clone)]
pub struct AlarmEntry {
    /// Instance identifier / resource string the alarm is raised against.
    /// On real gear this is often an instance-identifier XPath into
    /// ietf-interfaces or a vendor path — match ONT serials by substring.
    pub resource: String,
    /// Identity such as `bbf-xpon-onu-alarm-types:onu-dying-gasp`.
    pub alarm_type_id: String,
    pub alarm_type_qualifier: Option<String>,
    pub is_cleared: bool,
    pub perceived_severity: Option<String>,
    pub last_changed: Option<String>,
}

/// Parse the alarm list from an ietf-alarms `<get>` reply.
///
/// Expected structure (RFC 8632, ns urn:ietf:params:xml:ns:yang:ietf-alarms):
/// `<alarms><alarm-list><alarm><resource/><alarm-type-id/>
///   <alarm-type-qualifier/><is-cleared/><perceived-severity/>
///   <last-changed/>…</alarm></alarm-list></alarms>`
///
/// Nested `status-change` history entries also carry perceived-severity;
/// only the alarm's own (current) leaves are captured.
pub fn parse_alarm_list(xml: &str) -> anyhow::Result<Vec<AlarmEntry>> {
    let mut alarms = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_alarm = false;
    let mut in_status_change = false;
    let mut resource = String::new();
    let mut alarm_type_id = String::new();
    let mut alarm_type_qualifier: Option<String> = None;
    let mut is_cleared = false;
    let mut perceived_severity: Option<String> = None;
    let mut last_changed: Option<String> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "alarm" => {
                        in_alarm = true;
                        resource.clear();
                        alarm_type_id.clear();
                        alarm_type_qualifier = None;
                        is_cleared = false;
                        perceived_severity = None;
                        last_changed = None;
                    }
                    "status-change" if in_alarm => in_status_change = true,
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_alarm && !in_status_change => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    match current_elem.as_str() {
                        "resource" => resource = text.to_string(),
                        "alarm-type-id" => alarm_type_id = text.to_string(),
                        "alarm-type-qualifier" => {
                            alarm_type_qualifier = Some(text.to_string())
                        }
                        "is-cleared" => is_cleared = text.eq_ignore_ascii_case("true"),
                        "perceived-severity" => {
                            perceived_severity = Some(text.to_string())
                        }
                        "last-changed" => last_changed = Some(text.to_string()),
                        _ => {}
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "status-change" => in_status_change = false,
                    "alarm" if in_alarm => {
                        if !alarm_type_id.is_empty() {
                            alarms.push(AlarmEntry {
                                resource: resource.clone(),
                                alarm_type_id: alarm_type_id.clone(),
                                alarm_type_qualifier: alarm_type_qualifier.clone(),
                                is_cleared,
                                perceived_severity: perceived_severity.clone(),
                                last_changed: last_changed.clone(),
                            });
                        }
                        in_alarm = false;
                    }
                    _ => {}
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("ietf-alarms reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = alarms.len(), "Parsed ietf-alarms entries");
    Ok(alarms)
}

/// Map an alarm-type-id onto a `last_down_cause` string understood by the
/// fault detector (which matches on the substrings "dying_gasp"/"power").
///
/// Verified against standard/interface/bbf-xpon-defects.yang
/// (github.com/BroadbandForum/yang, ns urn:bbf:yang:bbf-xpon-defects,
/// rev 2024-04-23):
///   - dying gasp is identity `dgi` (G.984.3 §11.1.1 DGi) — there is no
///     `onu-dying-gasp` identity;
///   - per-ONU loss of signal/frame is folded into identity `lobi`
///     (loss of burst, refs LOSi/LOFi in G.984.3);
///   - channel-termination-wide loss of signal is identity `los`.
/// Common vendor spellings ("dying-gasp", "loss-of-signal", "power…") are
/// also accepted.
pub fn classify_down_cause(alarm_type_id: &str) -> Option<&'static str> {
    let t = alarm_type_id.to_ascii_lowercase();
    let ident = t.rsplit(':').next().unwrap_or(&t);
    if t.contains("dying-gasp") || t.contains("dying_gasp") || ident == "dgi" {
        Some("dying_gasp")
    } else if t.contains("loss-of-burst") || ident == "lobi" {
        Some("loss_of_burst")
    } else if t.contains("loss-of-signal") || ident == "losi" || ident == "los" {
        Some("los")
    } else if t.contains("loss-of-frame") || ident == "lofi" || ident == "lof" {
        Some("lof")
    } else if t.contains("power") {
        Some("power_fail")
    } else {
        None
    }
}

// ── Notification parsing ────────────────────────────────────────────────────

/// Parse a NETCONF notification for ONU state changes.
///
/// Handles both generations of the BBF notification:
///
/// Legacy (TR-385 Issue 1 / OB-BAA, module bbf-xpon-onu-states — top-level):
/// ```xml
/// <notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
///   <eventTime>2026-03-18T10:30:00Z</eventTime>
///   <onu-state-change xmlns="urn:bbf:yang:bbf-xpon-onu-states">
///     <detected-serial-number>ADTN153201C4</detected-serial-number>
///     <onu-id>1</onu-id>
///     <channel-termination-ref>CTP-0/1</channel-termination-ref>
///     <onu-state>onu-not-present-without-v-ani</onu-state>
///   </onu-state-change>
/// </notification>
/// ```
///
/// Current (module bbf-xpon-onu-state, notification
/// `onu-presence-state-change` nested under
/// interfaces-state/interface/channel-termination — see obbaa fixture
/// onu-state-change-notification_2_0.txt):
/// the channel termination is identified by the enclosing `<interface>`'s
/// `<name>` and the state leaf is `onu-presence-state`.
pub fn parse_onu_state_change_notification(xml: &str) -> anyhow::Result<Option<OntStateEntry>> {
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_state_change = false;
    let mut serial = String::new();
    let mut onu_id: u32 = 0;
    let mut state_str = String::new();
    let mut channel_term = String::new();
    let mut interface_name = String::new();
    let mut datetime: Option<String> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "onu-state-change" | "onu-presence-state-change" => {
                        in_state_change = true;
                    }
                    "interface" => interface_name.clear(),
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    if in_state_change {
                        match current_elem.as_str() {
                            "detected-serial-number" => serial = text.to_string(),
                            "onu-id" => onu_id = text.parse().unwrap_or(0),
                            "onu-state" | "onu-presence-state" => {
                                state_str = text.to_string()
                            }
                            "channel-termination-ref" => channel_term = text.to_string(),
                            "onu-state-last-change" | "last-change" | "eventTime" => {
                                datetime = Some(text.to_string())
                            }
                            _ => {}
                        }
                    } else if current_elem == "name" && interface_name.is_empty() {
                        // Current model: notification is nested under
                        // <interface><name>CTP…</name>…
                        interface_name = text.to_string();
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu-state-change" || local == "onu-presence-state-change" {
                    in_state_change = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("onu-state-change notification", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    if !serial.is_empty() {
        if channel_term.is_empty() {
            channel_term = interface_name;
        }
        Ok(Some(OntStateEntry {
            serial_number: serial,
            onu_id,
            channel_term,
            state: OntYangState::from_yang(&state_str),
            detected_datetime: datetime,
            v_ani_ref: None,
        }))
    } else {
        Ok(None)
    }
}

// ── OLT-side per-ONU RX power (bbf-hardware-transceivers-xpon) ─────────────

/// Parse OLT-side per-ONU received power from a bbf-hardware-transceivers-xpon
/// reply.
///
/// Standard location (verified against
/// github.com/BroadbandForum/yang standard/interface/
/// bbf-hardware-transceivers-xpon.yang): list `rssi-onu` (key
/// `detected-serial-number`) under /hw:hardware/hw:component/
/// transceiver-link/diagnostics, leaf `rssi` in **0.1 dBm units**
/// (type int16-or-unknown; non-numeric "unknown" values are skipped).
///
/// Note: there is NO `measured-upstream-rx-optical-power-dbm` leaf anywhere
/// in the published bbf-xpon family — this list is where OLT-side upstream
/// RX actually lives.
pub fn parse_rssi_onu(xml: &str) -> anyhow::Result<Vec<(String, f64)>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_rssi_onu = false;
    let mut serial = String::new();
    let mut rssi_raw: Option<f64> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "rssi-onu" {
                    in_rssi_onu = true;
                    serial.clear();
                    rssi_raw = None;
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_rssi_onu => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    match current_elem.as_str() {
                        "detected-serial-number" => serial = text.to_string(),
                        "rssi" => rssi_raw = text.parse().ok(),
                        _ => {}
                    }
                }
            }
            Ok(Event::End(e)) => {
                if local_name(e.name().as_ref()) == b"rssi-onu" {
                    if !serial.is_empty() {
                        if let Some(raw) = rssi_raw {
                            // 0.1 dBm units per bbf-hardware-transceivers-xpon
                            entries.push((serial.clone(), raw / 10.0));
                        }
                    }
                    in_rssi_onu = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("rssi-onu reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed rssi-onu entries");
    Ok(entries)
}

// ── ietf-interfaces statistics (per-ONU octet counters) ─────────────────────

/// Per-interface octet counters from an ietf-interfaces reply.
#[derive(Debug, Clone, PartialEq)]
pub struct InterfaceStatsEntry {
    pub name: String,
    pub in_octets: Option<u64>,
    pub out_octets: Option<u64>,
}

/// Parse `statistics/in-octets|out-octets` for every `<interface>` in an
/// ietf-interfaces reply.
///
/// Source model: ietf-interfaces (RFC 8343, revision 2018-02-20 — the
/// revision the OB-BAA standard OLT library advertises, see
/// data/external/adtran-samples/obbaa-yang-library/
/// bbf-olt-standard-2.1_yang-library.xml). `statistics { in-octets;
/// out-octets; }` (Counter64) exists identically in the `<interfaces>`
/// operational tree and the deprecated `<interfaces-state>` tree; the parser
/// matches on local names so both work.
///
/// Counters are parsed as u64 — negative or garbled values fail the parse
/// and become None rather than wrapping into fake huge counters.
pub fn parse_interface_statistics(xml: &str) -> anyhow::Result<Vec<InterfaceStatsEntry>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_interface = false;
    let mut in_statistics = false;
    let mut name = String::new();
    let mut in_octets: Option<u64> = None;
    let mut out_octets: Option<u64> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "interface" => {
                        in_interface = true;
                        in_statistics = false;
                        name.clear();
                        in_octets = None;
                        out_octets = None;
                    }
                    "statistics" if in_interface => in_statistics = true,
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_interface => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    if !in_statistics {
                        // The interface's own <name> — take the first only so
                        // nested name-ish leaves cannot overwrite it.
                        if current_elem == "name" && name.is_empty() {
                            name = text.to_string();
                        }
                    } else {
                        match current_elem.as_str() {
                            "in-octets" => in_octets = text.parse().ok(),
                            "out-octets" => out_octets = text.parse().ok(),
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                match local_name(e.name().as_ref()) {
                    b"interface" if in_interface => {
                        if !name.is_empty() && (in_octets.is_some() || out_octets.is_some()) {
                            entries.push(InterfaceStatsEntry {
                                name: name.clone(),
                                in_octets,
                                out_octets,
                            });
                        }
                        in_interface = false;
                        in_statistics = false;
                    }
                    b"statistics" => in_statistics = false,
                    _ => {}
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("interface statistics reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed interface statistics entries");
    Ok(entries)
}

// ── bbf-xpon-performance-management PHY counters (FEC / BIP) ────────────────

/// Per-interface xPON PHY performance counters (current 15-minute interval).
#[derive(Debug, Clone, PartialEq)]
pub struct XponPhyPmEntry {
    pub interface_name: String,
    /// `phy/corrected-fec-codewords`
    pub corrected_fec_codewords: Option<u64>,
    /// `phy/uncorrectable-fec-codewords`
    pub uncorrectable_fec_codewords: Option<u64>,
    /// `phy/in-bip-errors`
    pub in_bip_errors: Option<u64>,
}

/// Parse the xPON PHY counters from a bbf-interfaces-performance-management
/// reply.
///
/// Source model: bbf-xpon-performance-management (revisions
/// 2020-10-13…2024-04-23, data/external/broadband-forum-yang/
/// bbf-xpon-performance-management.yang) — grouping `xpon-phy-pm` container
/// `phy` with leaves `corrected-fec-codewords`, `uncorrectable-fec-codewords`
/// and `in-bip-errors` (all bbf-yang:performance-counter64), augmenting
/// /if:interfaces-state/if:interface/bbf-if-pm:performance/
/// bbf-if-pm:intervals-15min/bbf-if-pm:current — i.e. these are CURRENT
/// 15-MINUTE-BIN counters, reset at each interval boundary, reported per
/// v-ANI (and CT) interface. For G-PON, all three leaves are reported per
/// vANI (see the leaves' description text in the module).
///
/// Only the `<current>` bin is read; `<history>` bins in the same reply are
/// skipped so a firmware answering with more than requested cannot smear
/// stale intervals over live data.
pub fn parse_xpon_phy_pm(xml: &str) -> anyhow::Result<Vec<XponPhyPmEntry>> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_interface = false;
    let mut in_current = false;
    let mut in_history = false;
    let mut in_phy = false;
    let mut name = String::new();
    let mut corrected: Option<u64> = None;
    let mut uncorrectable: Option<u64> = None;
    let mut bip: Option<u64> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "interface" => {
                        in_interface = true;
                        in_current = false;
                        in_history = false;
                        in_phy = false;
                        name.clear();
                        corrected = None;
                        uncorrectable = None;
                        bip = None;
                    }
                    "current" if in_interface => in_current = true,
                    "history" if in_interface => in_history = true,
                    "phy" if in_current && !in_history => in_phy = true,
                    _ => {}
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_interface => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    if !in_current && !in_history {
                        if current_elem == "name" && name.is_empty() {
                            name = text.to_string();
                        }
                    } else if in_phy {
                        // performance-counter64 → u64; negative/garbled → None
                        match current_elem.as_str() {
                            "corrected-fec-codewords" => corrected = text.parse().ok(),
                            "uncorrectable-fec-codewords" => {
                                uncorrectable = text.parse().ok()
                            }
                            "in-bip-errors" => bip = text.parse().ok(),
                            _ => {}
                        }
                    }
                }
            }
            Ok(Event::End(e)) => {
                match local_name(e.name().as_ref()) {
                    b"interface" if in_interface => {
                        if !name.is_empty()
                            && (corrected.is_some()
                                || uncorrectable.is_some()
                                || bip.is_some())
                        {
                            entries.push(XponPhyPmEntry {
                                interface_name: name.clone(),
                                corrected_fec_codewords: corrected,
                                uncorrectable_fec_codewords: uncorrectable,
                                in_bip_errors: bip,
                            });
                        }
                        in_interface = false;
                        in_current = false;
                        in_history = false;
                        in_phy = false;
                    }
                    b"current" => {
                        in_current = false;
                        in_phy = false;
                    }
                    b"history" => in_history = false,
                    b"phy" => in_phy = false,
                    _ => {}
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("xpon phy pm reply", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed xPON PHY PM entries");
    Ok(entries)
}

/// Parse a dying-gasp alarm from a NETCONF notification.
///
/// Returns `(serial_number, true)` if this is a dying-gasp alarm.
/// Dying gasp = power outage (ONT sent last-gasp before losing power).
/// No dying gasp + offline = fibre cut (physical break, no warning).
pub fn parse_dying_gasp(xml: &str) -> anyhow::Result<Option<(String, bool)>> {
    // Expected:
    // <notification>
    //   <alarm-notification xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms">
    //     <resource>onu:ADTN153201C4</resource>
    //     <alarm-type-id>bbf-xpon-onu-alarm-types:onu-dying-gasp</alarm-type-id>
    //   </alarm-notification>
    // </notification>

    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut resource = String::new();
    let mut alarm_type = String::new();
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                current_elem =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
            }
            Ok(Event::Text(e)) => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    match current_elem.as_str() {
                        "resource" => resource = text.to_string(),
                        "alarm-type-id" => alarm_type = text.to_string(),
                        _ => {}
                    }
                }
            }
            Ok(Event::End(_)) => current_elem.clear(),
            Ok(Event::Eof) => break,
            Err(e) => return Err(parse_err("dying-gasp notification", &reader, e)),
            _ => {}
        }
        buf.clear();
    }

    if alarm_type.contains("dying-gasp") {
        let serial = resource
            .strip_prefix("onu:")
            .unwrap_or(&resource)
            .to_string();
        Ok(Some((serial, true)))
    } else {
        Ok(None)
    }
}

// ── Helpers ─────────────────────────────────────────────────────────────────

/// Strip namespace prefix from an XML element name.
/// e.g., `b"bbf-xpon:xpon"` → `b"xpon"`, `b"name"` → `b"name"`
fn local_name(name: &[u8]) -> &[u8] {
    match name.iter().position(|&b| b == b':') {
        Some(pos) => &name[pos + 1..],
        None => name,
    }
}

/// Build a contextual error for a quick-xml failure. Parse errors must
/// surface: a truncated/garbled reply silently read as "fewer ONTs" becomes
/// a phantom mass-outage downstream.
fn parse_err(what: &str, reader: &Reader<&[u8]>, e: quick_xml::Error) -> anyhow::Error {
    anyhow::anyhow!(
        "XML parse error in {} at byte offset {}: {}",
        what,
        reader.buffer_position(),
        e
    )
}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_capabilities() {
        let hello = r#"<?xml version="1.0" encoding="UTF-8"?>
<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <capabilities>
    <capability>urn:ietf:params:netconf:base:1.0</capability>
    <capability>urn:ietf:params:netconf:base:1.1</capability>
    <capability>urn:bbf:yang:bbf-xpon</capability>
    <capability>urn:bbf:yang:bbf-xpon-onu-state</capability>
    <capability>urn:ietf:params:netconf:capability:notification:1.0</capability>
  </capabilities>
  <session-id>42</session-id>
</hello>"#;

        let caps = parse_capabilities(hello).expect("hello should parse");
        assert_eq!(caps.len(), 5);
        assert!(caps.contains(&"urn:ietf:params:netconf:base:1.1".to_string()));
        assert!(caps.contains(&"urn:bbf:yang:bbf-xpon".to_string()));
        assert!(caps.contains(&"urn:bbf:yang:bbf-xpon-onu-state".to_string()));
        assert!(caps.contains(
            &"urn:ietf:params:netconf:capability:notification:1.0".to_string()
        ));
    }

    #[test]
    fn test_parse_ont_state() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
  <data>
    <xpon xmlns="urn:bbf:yang:bbf-xpon">
      <channel-terminations>
        <channel-termination>
          <name>CTP-0/1</name>
          <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
            <onu>
              <detected-serial-number>ADTN153201C4</detected-serial-number>
              <onu-id>1</onu-id>
              <onu-state>onu-present-and-on-intended-channel-termination</onu-state>
              <onu-detected-datetime>2026-03-18T10:30:00Z</onu-detected-datetime>
            </onu>
            <onu>
              <detected-serial-number>ADTN99887766</detected-serial-number>
              <onu-id>2</onu-id>
              <onu-state>onu-not-present-without-v-ani</onu-state>
            </onu>
          </onus-present-on-channel-termination>
        </channel-termination>
      </channel-terminations>
    </xpon>
  </data>
</rpc-reply>"#;

        let entries = parse_ont_state(xml).expect("should parse");
        assert_eq!(entries.len(), 2);

        assert_eq!(entries[0].serial_number, "ADTN153201C4");
        assert_eq!(entries[0].onu_id, 1);
        assert_eq!(entries[0].channel_term, "CTP-0/1");
        assert!(entries[0].state.is_online());
        assert_eq!(
            entries[0].detected_datetime.as_deref(),
            Some("2026-03-18T10:30:00Z")
        );

        assert_eq!(entries[1].serial_number, "ADTN99887766");
        assert_eq!(entries[1].onu_id, 2);
        assert_eq!(entries[1].state, OntYangState::Offline);
    }

    #[test]
    fn test_parse_optical_power() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="2">
  <data>
    <xpon xmlns="urn:bbf:yang:bbf-xpon">
      <channel-terminations>
        <channel-termination>
          <name>CTP-0/1</name>
          <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
            <onu>
              <detected-serial-number>ADTN153201C4</detected-serial-number>
              <onu-id>1</onu-id>
              <measured-upstream-rx-optical-power-dbm>-11050</measured-upstream-rx-optical-power-dbm>
              <ani-transceiver-rx-power>-12500</ani-transceiver-rx-power>
              <ani-transceiver-tx-power>1200</ani-transceiver-tx-power>
              <ani-transceiver-temperature>22750</ani-transceiver-temperature>
              <ani-transceiver-supply-voltage>16500</ani-transceiver-supply-voltage>
              <ani-transceiver-bias-current>6250</ani-transceiver-bias-current>
            </onu>
          </onus-present-on-channel-termination>
        </channel-termination>
      </channel-terminations>
    </xpon>
  </data>
</rpc-reply>"#;

        let entries = parse_optical_power(xml).expect("should parse");
        assert_eq!(entries.len(), 1);

        let e = &entries[0];
        assert_eq!(e.serial_number, "ADTN153201C4");
        // OLT rx: -11050 / 500 = -22.1 dBm
        assert!((e.olt_rx_power_dbm.unwrap() - (-22.1)).abs() < 0.01);
        // ONT rx: -12500 / 500 = -25.0 dBm
        assert!((e.ont_rx_power_dbm.unwrap() - (-25.0)).abs() < 0.01);
        // ONT tx: 1200 / 500 = 2.4 dBm
        assert!((e.ont_tx_power_dbm.unwrap() - 2.4).abs() < 0.01);
        assert!((e.ont_temperature_c.unwrap() - 45.5).abs() < 0.1);
        assert!((e.ont_voltage_v.unwrap() - 3.3).abs() < 0.1);
        assert!((e.ont_bias_current_ma.unwrap() - 12.5).abs() < 0.1);
    }

    #[test]
    fn test_parse_ranging() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="3">
  <data>
    <xpon xmlns="urn:bbf:yang:bbf-xpon">
      <channel-terminations>
        <channel-termination>
          <name>CTP-0/1</name>
          <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
            <onu>
              <detected-serial-number>ADTN153201C4</detected-serial-number>
              <onu-id>1</onu-id>
              <equalization-delay>164800</equalization-delay>
            </onu>
            <onu>
              <detected-serial-number>ADTN99887766</detected-serial-number>
              <onu-id>2</onu-id>
              <equalization-delay>240000</equalization-delay>
            </onu>
          </onus-present-on-channel-termination>
        </channel-termination>
      </channel-terminations>
    </xpon>
  </data>
</rpc-reply>"#;

        let entries = parse_ranging(xml).expect("should parse");
        assert_eq!(entries.len(), 2);

        // 164800 * 0.0125 = 2060.0 metres
        assert_eq!(entries[0].equalization_delay_tq, 164800);
        assert!((entries[0].distance_m - 2060.0).abs() < 0.1);

        // 240000 * 0.0125 = 3000.0 metres
        assert_eq!(entries[1].equalization_delay_tq, 240000);
        assert!((entries[1].distance_m - 3000.0).abs() < 0.1);
    }

    #[test]
    fn test_parse_onu_state_change_notification() {
        let xml = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-03-18T10:30:00Z</eventTime>
  <onu-state-change xmlns="urn:bbf:yang:bbf-xpon-onu-state">
    <detected-serial-number>ADTN153201C4</detected-serial-number>
    <onu-id>1</onu-id>
    <channel-termination-ref>CTP-0/1</channel-termination-ref>
    <onu-state>onu-not-present-without-v-ani</onu-state>
    <onu-state-last-change>2026-03-18T10:30:00Z</onu-state-last-change>
  </onu-state-change>
</notification>"#;

        let entry = parse_onu_state_change_notification(xml)
            .expect("should parse")
            .expect("should yield an entry");
        assert_eq!(entry.serial_number, "ADTN153201C4");
        assert_eq!(entry.onu_id, 1);
        assert_eq!(entry.channel_term, "CTP-0/1");
        assert_eq!(entry.state, OntYangState::Offline);
    }

    #[test]
    fn test_parse_dying_gasp_alarm() {
        let xml = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-03-18T10:30:00Z</eventTime>
  <alarm-notification xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms">
    <resource>onu:ADTN153201C4</resource>
    <alarm-type-id>bbf-xpon-onu-alarm-types:onu-dying-gasp</alarm-type-id>
    <alarm-type-qualifier/>
    <perceived-severity>critical</perceived-severity>
  </alarm-notification>
</notification>"#;

        let (serial, is_dying_gasp) = parse_dying_gasp(xml)
            .expect("should parse")
            .expect("should detect dying gasp");
        assert_eq!(serial, "ADTN153201C4");
        assert!(is_dying_gasp);
    }

    #[test]
    fn test_ont_yang_state_mapping() {
        assert_eq!(
            OntYangState::from_yang("onu-present-and-on-intended-channel-termination"),
            OntYangState::OnlineOnIntended
        );
        assert_eq!(
            OntYangState::from_yang("onu-present-and-in-wavelength-discovery"),
            OntYangState::Registering
        );
        assert_eq!(OntYangState::from_yang("onu-not-present"), OntYangState::Offline);
        assert_eq!(
            OntYangState::from_yang("onu-not-present-without-v-ani"),
            OntYangState::Offline
        );
        // With namespace prefix
        assert_eq!(
            OntYangState::from_yang(
                "bbf-xpon-onu-types:onu-present-and-on-intended-channel-termination"
            ),
            OntYangState::OnlineOnIntended
        );

        assert!(OntYangState::OnlineOnIntended.is_online());
        assert!(!OntYangState::Offline.is_online());
        assert!(!OntYangState::Registering.is_online());
    }

    #[test]
    fn test_tq_to_meters_conversion() {
        // distance_m = equalization_delay_tq * 0.0125
        assert!((164800.0 * TQ_TO_METERS - 2060.0).abs() < 0.01);
        assert!((0.0 * TQ_TO_METERS).abs() < 0.01);
        assert!((80000.0 * TQ_TO_METERS - 1000.0).abs() < 0.01);
    }

    #[test]
    fn test_no_dying_gasp_for_other_alarms() {
        let xml = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-03-18T10:30:00Z</eventTime>
  <alarm-notification xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms">
    <resource>onu:ADTN153201C4</resource>
    <alarm-type-id>bbf-xpon-onu-alarm-types:onu-loss-of-signal</alarm-type-id>
    <perceived-severity>major</perceived-severity>
  </alarm-notification>
</notification>"#;

        assert!(parse_dying_gasp(xml).expect("should parse").is_none());
    }

    // ── Current-model (bbf-xpon-onu-state, TR-385 Issue 2/3) fixtures ──────

    /// Fixture shaped per the CURRENT module: channel-termination as an
    /// ietf-interfaces augmentation, container
    /// onus-present-on-local-channel-termination, identityref leaf
    /// onu-presence-state (values from bbf-xpon-onu-types).
    #[test]
    fn test_parse_ont_state_current_model() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
  <data>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>CTP-0/1</name>
        <channel-termination xmlns="urn:bbf:yang:bbf-xpon">
          <onus-present-on-local-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
            <onu>
              <detected-serial-number>ADTN153201C4</detected-serial-number>
              <onu-id>1</onu-id>
              <onu-presence-state xmlns:bbf-xpon-onu-types="urn:bbf:yang:bbf-xpon-onu-types">bbf-xpon-onu-types:onu-present-and-on-intended-channel-termination</onu-presence-state>
              <onu-detected-datetime>2026-07-01T10:30:00Z</onu-detected-datetime>
            </onu>
            <onu>
              <detected-serial-number>ADTN99887766</detected-serial-number>
              <onu-id>2</onu-id>
              <onu-presence-state xmlns:bbf-xpon-onu-types="urn:bbf:yang:bbf-xpon-onu-types">bbf-xpon-onu-types:onu-not-present-with-v-ani</onu-presence-state>
            </onu>
          </onus-present-on-local-channel-termination>
        </channel-termination>
      </interface>
      <interface>
        <name>CTP-0/2</name>
        <channel-termination xmlns="urn:bbf:yang:bbf-xpon">
          <onus-present-on-local-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
            <onu>
              <detected-serial-number>ADTN55550001</detected-serial-number>
              <onu-id>7</onu-id>
              <onu-presence-state>onu-present-and-in-wavelength-discovery</onu-presence-state>
            </onu>
          </onus-present-on-local-channel-termination>
        </channel-termination>
      </interface>
    </interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_ont_state(xml).expect("current-model reply should parse");
        assert_eq!(entries.len(), 3);

        assert_eq!(entries[0].serial_number, "ADTN153201C4");
        assert_eq!(entries[0].channel_term, "CTP-0/1");
        assert!(entries[0].state.is_online());

        assert_eq!(entries[1].serial_number, "ADTN99887766");
        assert_eq!(entries[1].state, OntYangState::Offline);
        assert_eq!(entries[1].channel_term, "CTP-0/1");

        // Second interface gets its own channel-termination name
        assert_eq!(entries[2].serial_number, "ADTN55550001");
        assert_eq!(entries[2].channel_term, "CTP-0/2");
        assert_eq!(entries[2].state, OntYangState::Registering);
    }

    #[test]
    fn test_parse_onu_presence_state_change_notification_current_model() {
        // Shape per obbaa fixture onu-state-change-notification_2_0.txt:
        // notification nested under interfaces-state/interface/channel-termination.
        let xml = r#"<notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
  <eventTime>2026-07-01T10:30:00Z</eventTime>
  <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>CTP-0/3</name>
      <channel-termination xmlns="urn:bbf:yang:bbf-xpon">
        <onu-presence-state-change xmlns="urn:bbf:yang:bbf-xpon-onu-state">
          <detected-serial-number>ADTN153201C4</detected-serial-number>
          <onu-id>1</onu-id>
          <last-change>2026-07-01T10:30:00Z</last-change>
          <onu-presence-state xmlns:onut="urn:bbf:yang:bbf-xpon-onu-types">onut:onu-not-present-with-v-ani</onu-presence-state>
        </onu-presence-state-change>
      </channel-termination>
    </interface>
  </interfaces-state>
</notification>"#;

        let entry = parse_onu_state_change_notification(xml)
            .expect("should parse")
            .expect("should yield an entry");
        assert_eq!(entry.serial_number, "ADTN153201C4");
        assert_eq!(entry.channel_term, "CTP-0/3");
        assert_eq!(entry.state, OntYangState::Offline);
    }

    // ── Parse errors must surface ───────────────────────────────────────────

    #[test]
    fn test_truncated_xml_is_error_not_empty_success() {
        // Truncated mid-element: must be Err, never Ok(vec![]) — a garbled
        // reply read as "0 ONTs" becomes a phantom mass outage downstream.
        let truncated = r#"<rpc-reply><data><interfaces-state><interface><name>CTP-0/1</naXX"#;
        assert!(parse_ont_state(truncated).is_err());
        assert!(parse_optical_power(truncated).is_err());
        assert!(parse_ranging(truncated).is_err());
        let bad_hello = "<hello><capabilities><capability>urn:x</cap";
        assert!(parse_capabilities(bad_hello).is_err());
    }

    // ── rpc-error detection (namespace variants) ────────────────────────────

    #[test]
    fn test_rpc_error_detected_unprefixed() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="4">
  <rpc-error>
    <error-type>application</error-type>
    <error-tag>unknown-namespace</error-tag>
    <error-severity>error</error-severity>
    <error-message>namespace not recognized</error-message>
  </rpc-error>
</rpc-reply>"#;
        let summary = rpc_error_summary(xml).expect("should detect rpc-error");
        assert!(summary.contains("unknown-namespace"));
        assert!(summary.contains("namespace not recognized"));
    }

    #[test]
    fn test_rpc_error_detected_with_nc_prefix() {
        // RFC 6241 permits any prefix bound to the base namespace — real
        // gear commonly emits <nc:rpc-error>. Substring matching missed this.
        let xml = r#"<nc:rpc-reply xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0" nc:message-id="4">
  <nc:rpc-error>
    <nc:error-tag>operation-failed</nc:error-tag>
    <nc:error-severity>error</nc:error-severity>
    <nc:error-message>internal error</nc:error-message>
  </nc:rpc-error>
</nc:rpc-reply>"#;
        let summary = rpc_error_summary(xml).expect("prefixed rpc-error must be detected");
        assert!(summary.contains("operation-failed"));
    }

    #[test]
    fn test_rpc_error_empty_element_detected() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><rpc-error/></rpc-reply>"#;
        assert!(rpc_error_summary(xml).is_some());
    }

    #[test]
    fn test_rpc_error_not_falsely_detected_in_text() {
        // The literal string "<rpc-error>" inside escaped text content is
        // NOT an rpc-error element.
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="9">
  <data><log-line>client sent &lt;rpc-error&gt; yesterday</log-line></data>
</rpc-reply>"#;
        assert!(rpc_error_summary(xml).is_none());
    }

    #[test]
    fn test_rpc_error_none_on_clean_reply() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><data/></rpc-reply>"#;
        assert!(rpc_error_summary(xml).is_none());
    }

    // ── yang-library parsing ────────────────────────────────────────────────

    #[test]
    fn test_parse_yang_library_rfc7895_modules_state() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
  <data>
    <modules-state xmlns="urn:ietf:params:xml:ns:yang:ietf-yang-library">
      <module-set-id>abc123</module-set-id>
      <module>
        <name>ietf-interfaces</name>
        <revision>2018-02-20</revision>
        <namespace>urn:ietf:params:xml:ns:yang:ietf-interfaces</namespace>
        <conformance-type>implement</conformance-type>
      </module>
      <module>
        <name>bbf-xpon-onu-state</name>
        <revision>2024-04-23</revision>
        <namespace>urn:bbf:yang:bbf-xpon-onu-state</namespace>
        <submodule>
          <name>bbf-xpon-onu-state-body</name>
          <revision>2024-04-23</revision>
        </submodule>
      </module>
    </modules-state>
  </data>
</rpc-reply>"#;

        let modules = parse_yang_library(xml).expect("should parse");
        assert_eq!(modules.len(), 2);
        assert_eq!(modules[0].name, "ietf-interfaces");
        assert_eq!(modules[0].revision.as_deref(), Some("2018-02-20"));
        // Submodule name/revision must not overwrite the parent module's.
        assert_eq!(modules[1].name, "bbf-xpon-onu-state");
        assert_eq!(modules[1].revision.as_deref(), Some("2024-04-23"));
        assert_eq!(
            modules[1].namespace.as_deref(),
            Some("urn:bbf:yang:bbf-xpon-onu-state")
        );
    }

    #[test]
    fn test_parse_yang_library_rfc8525_yang_library() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="1">
  <data>
    <yang-library xmlns="urn:ietf:params:xml:ns:yang:ietf-yang-library">
      <module-set>
        <name>state</name>
        <module>
          <name>bbf-xpon-onu-states</name>
          <revision>2018-10-01</revision>
          <namespace>urn:bbf:yang:bbf-xpon-onu-states</namespace>
        </module>
      </module-set>
    </yang-library>
  </data>
</rpc-reply>"#;

        let modules = parse_yang_library(xml).expect("should parse");
        assert_eq!(modules.len(), 1);
        assert_eq!(modules[0].name, "bbf-xpon-onu-states");
        assert_eq!(
            modules[0].namespace.as_deref(),
            Some("urn:bbf:yang:bbf-xpon-onu-states")
        );
    }

    // ── ietf-alarms parsing ─────────────────────────────────────────────────

    #[test]
    fn test_parse_alarm_list() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="5">
  <data>
    <alarms xmlns="urn:ietf:params:xml:ns:yang:ietf-alarms">
      <alarm-list>
        <number-of-alarms>2</number-of-alarms>
        <alarm>
          <resource>/if:interfaces-state/if:interface[if:name='onu ADTN153201C4']</resource>
          <alarm-type-id xmlns:bbf-xpon-def="urn:bbf:yang:bbf-xpon-defects">bbf-xpon-def:dgi</alarm-type-id>
          <alarm-type-qualifier/>
          <is-cleared>false</is-cleared>
          <last-changed>2026-07-02T08:15:00Z</last-changed>
          <perceived-severity>critical</perceived-severity>
          <alarm-text>Dying gasp received from ONU</alarm-text>
          <status-change>
            <time>2026-07-02T08:15:00Z</time>
            <perceived-severity>warning</perceived-severity>
          </status-change>
        </alarm>
        <alarm>
          <resource>onu:ADTN99887766</resource>
          <alarm-type-id>bbf-xpon-def:lobi</alarm-type-id>
          <is-cleared>true</is-cleared>
          <perceived-severity>major</perceived-severity>
        </alarm>
      </alarm-list>
    </alarms>
  </data>
</rpc-reply>"#;

        let alarms = parse_alarm_list(xml).expect("should parse");
        assert_eq!(alarms.len(), 2);

        assert!(alarms[0].resource.contains("ADTN153201C4"));
        assert_eq!(alarms[0].alarm_type_id, "bbf-xpon-def:dgi");
        assert!(!alarms[0].is_cleared);
        // Must take the alarm's own severity, not the nested status-change's.
        assert_eq!(alarms[0].perceived_severity.as_deref(), Some("critical"));
        assert_eq!(
            alarms[0].last_changed.as_deref(),
            Some("2026-07-02T08:15:00Z")
        );

        assert_eq!(alarms[1].resource, "onu:ADTN99887766");
        assert!(alarms[1].is_cleared);
    }

    #[test]
    fn test_classify_down_cause() {
        // Verified identities from bbf-xpon-defects.yang
        assert_eq!(classify_down_cause("bbf-xpon-def:dgi"), Some("dying_gasp"));
        assert_eq!(classify_down_cause("bbf-xpon-def:lobi"), Some("loss_of_burst"));
        assert_eq!(classify_down_cause("bbf-xpon-def:los"), Some("los"));
        // Vendor spellings
        assert_eq!(
            classify_down_cause("adtran-alarms:onu-dying-gasp"),
            Some("dying_gasp")
        );
        assert_eq!(
            classify_down_cause("vendor:onu-loss-of-signal"),
            Some("los")
        );
        assert_eq!(classify_down_cause("vendor:ac-power-failure"), Some("power_fail"));
        // Unrelated alarms map to nothing
        assert_eq!(classify_down_cause("bbf-xpon-def:tiwi"), None);
        assert_eq!(classify_down_cause("ietf-alarms:high-temperature"), None);
    }

    // ── rssi-onu parsing (OLT-side per-ONU RX) ──────────────────────────────

    #[test]
    fn test_parse_rssi_onu() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="6">
  <data>
    <hardware xmlns="urn:ietf:params:xml:ns:yang:ietf-hardware">
      <component>
        <name>sfp-pon-0/1</name>
        <transceiver-link xmlns="urn:bbf:yang:bbf-hardware-transceivers">
          <diagnostics>
            <rssi-onu xmlns="urn:bbf:yang:bbf-hardware-transceivers-xpon">
              <detected-serial-number>ADTN153201C4</detected-serial-number>
              <rssi>-221</rssi>
            </rssi-onu>
            <rssi-onu xmlns="urn:bbf:yang:bbf-hardware-transceivers-xpon">
              <detected-serial-number>ADTN99887766</detected-serial-number>
              <rssi>unknown</rssi>
            </rssi-onu>
          </diagnostics>
        </transceiver-link>
      </component>
    </hardware>
  </data>
</rpc-reply>"#;

        let entries = parse_rssi_onu(xml).expect("should parse");
        // "unknown" rssi is skipped; -221 raw = -22.1 dBm (0.1 dBm units)
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].0, "ADTN153201C4");
        assert!((entries[0].1 - (-22.1)).abs() < 0.001);
    }

    #[test]
    fn test_parse_interface_statistics_v_ani_and_uplink() {
        // Interface naming ("vAni_ont1", type bbf-xponift:v-ani) taken from
        // the real OB-BAA payload data/external/adtran-samples/obbaa-examples/
        // vomci-end-to-end-config/9-create_onu_on_olt.xml; the statistics
        // container is ietf-interfaces (RFC 8343).
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="7">
  <data>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>vAni_ont1</name>
        <type xmlns:bbf-xponift="urn:bbf:yang:bbf-xpon-if-type">bbf-xponift:v-ani</type>
        <statistics>
          <in-octets>123456789012</in-octets>
          <out-octets>987654321098</out-octets>
        </statistics>
      </interface>
      <interface>
        <name>channeltermination.1</name>
        <type xmlns:bbf-xponift="urn:bbf:yang:bbf-xpon-if-type">bbf-xponift:channel-termination</type>
        <statistics>
          <in-octets>42</in-octets>
          <out-octets>43</out-octets>
        </statistics>
      </interface>
      <interface>
        <name>no-stats-if</name>
      </interface>
    </interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_interface_statistics(xml).expect("should parse");
        // The interface without a <statistics> container yields no entry.
        assert_eq!(entries.len(), 2);
        assert_eq!(entries[0].name, "vAni_ont1");
        assert_eq!(entries[0].in_octets, Some(123_456_789_012));
        assert_eq!(entries[0].out_octets, Some(987_654_321_098));
        assert_eq!(entries[1].name, "channeltermination.1");
    }

    #[test]
    fn test_parse_interface_statistics_rejects_negative_and_garbled() {
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>vAni_ont2</name>
        <statistics>
          <in-octets>-5</in-octets>
          <out-octets>18446744073709551615</out-octets>
        </statistics>
      </interface>
    </interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_interface_statistics(xml).expect("should parse");
        assert_eq!(entries.len(), 1);
        // Negative counters cannot exist (Counter64); parse to None, never
        // wrap into a fake huge value.
        assert_eq!(entries[0].in_octets, None);
        // u64::MAX is a valid Counter64 value.
        assert_eq!(entries[0].out_octets, Some(u64::MAX));
    }

    #[test]
    fn test_parse_interface_statistics_namespace_prefixed() {
        // Some servers emit explicit prefixes; local-name matching must cope.
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <if:interfaces-state xmlns:if="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <if:interface>
        <if:name>vAni_ont1</if:name>
        <if:statistics>
          <if:in-octets>1000</if:in-octets>
          <if:out-octets>2000</if:out-octets>
        </if:statistics>
      </if:interface>
    </if:interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_interface_statistics(xml).expect("should parse");
        assert_eq!(
            entries,
            vec![InterfaceStatsEntry {
                name: "vAni_ont1".into(),
                in_octets: Some(1000),
                out_octets: Some(2000),
            }]
        );
    }

    #[test]
    fn test_parse_xpon_phy_pm_current_bin_only() {
        // Structure per bbf-xpon-performance-management (rev 2024-04-23,
        // data/external/broadband-forum-yang/bbf-xpon-performance-management
        // .yang): container `phy` under bbf-if-pm performance/
        // intervals-15min/current on a v-ANI interface. The <history> bin in
        // the same reply must be ignored.
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="8">
  <data>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>vAni_ont1</name>
        <performance xmlns="urn:bbf:yang:bbf-interfaces-performance-management">
          <intervals-15min>
            <current>
              <xpon xmlns="urn:bbf:yang:bbf-xpon-performance-management">
                <phy>
                  <corrected-fec-bytes>987654</corrected-fec-bytes>
                  <corrected-fec-codewords>18234</corrected-fec-codewords>
                  <uncorrectable-fec-codewords>2</uncorrectable-fec-codewords>
                  <in-fec-codewords>91231234</in-fec-codewords>
                  <in-bip-errors>7</in-bip-errors>
                </phy>
              </xpon>
            </current>
            <history>
              <interval-number>1</interval-number>
              <xpon xmlns="urn:bbf:yang:bbf-xpon-performance-management">
                <phy>
                  <corrected-fec-codewords>999999</corrected-fec-codewords>
                  <uncorrectable-fec-codewords>500</uncorrectable-fec-codewords>
                  <in-bip-errors>400</in-bip-errors>
                </phy>
              </xpon>
            </history>
          </intervals-15min>
        </performance>
      </interface>
      <interface>
        <name>vAni_ont2</name>
        <performance xmlns="urn:bbf:yang:bbf-interfaces-performance-management">
          <intervals-15min>
            <current>
              <xpon xmlns="urn:bbf:yang:bbf-xpon-performance-management">
                <phy>
                  <in-bip-errors>0</in-bip-errors>
                </phy>
              </xpon>
            </current>
          </intervals-15min>
        </performance>
      </interface>
    </interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_xpon_phy_pm(xml).expect("should parse");
        assert_eq!(entries.len(), 2);
        // Current bin, not the stale history bin (999999/500/400).
        assert_eq!(entries[0].interface_name, "vAni_ont1");
        assert_eq!(entries[0].corrected_fec_codewords, Some(18_234));
        assert_eq!(entries[0].uncorrectable_fec_codewords, Some(2));
        assert_eq!(entries[0].in_bip_errors, Some(7));
        // Partial phy containers are fine — 0 is a real (good) reading.
        assert_eq!(entries[1].interface_name, "vAni_ont2");
        assert_eq!(entries[1].corrected_fec_codewords, None);
        assert_eq!(entries[1].in_bip_errors, Some(0));
    }

    #[test]
    fn test_parse_xpon_phy_pm_no_phy_yields_no_entries() {
        // An interface with performance data but no xpon/phy container
        // (e.g. an ethernet uplink) must not fabricate a zeroed entry.
        let xml = r#"<rpc-reply xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>eth-uplink-1</name>
        <performance xmlns="urn:bbf:yang:bbf-interfaces-performance-management">
          <intervals-15min>
            <current>
              <in-errors>3</in-errors>
            </current>
          </intervals-15min>
        </performance>
      </interface>
    </interfaces-state>
  </data>
</rpc-reply>"#;

        let entries = parse_xpon_phy_pm(xml).expect("should parse");
        assert!(entries.is_empty());
    }
}
