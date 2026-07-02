// SPDX-License-Identifier: Apache-2.0
// XML parsers for BBF TR-385 YANG model responses (NETCONF).
//
// Parses NETCONF <rpc-reply> data for:
//   - <hello> capability URIs
//   - ONT state (onu-state enumeration from bbf-xpon-onu-state)
//   - Optical power (OLT-side upstream rx, ONT-side OMCI transceiver)
//   - Ranging (equalization-delay TQ → distance meters)
//   - Notifications (onu-state-change, dying-gasp alarms)

use quick_xml::events::Event;
use quick_xml::Reader;
use tracing::debug;

// ── Capability parsing ──────────────────────────────────────────────────────

/// Parse capability URIs from a NETCONF `<hello>` message.
pub fn parse_capabilities(hello_xml: &str) -> Vec<String> {
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
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    caps
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
/// Expected YANG path:
/// `/bbf-xpon:xpon/channel-terminations/channel-termination/
///   bbf-xpon-onu-state:onus-present-on-channel-termination/onu/...`
pub fn parse_ont_state(xml: &str) -> Vec<OntStateEntry> {
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
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "channel-termination" => {
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
                            "onu-state" => current_state = text.to_string(),
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
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed ONT state entries");
    entries
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
pub fn parse_optical_power(xml: &str) -> Vec<OpticalPowerEntry> {
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
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "channel-termination" => current_channel_term.clear(),
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
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed optical power entries");
    entries
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
pub fn parse_ranging(xml: &str) -> Vec<RangingEntry> {
    let mut entries = Vec::new();
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut current_channel_term = String::new();
    let mut current_serial = String::new();
    let mut current_onu_id: u32 = 0;
    let mut current_eq_delay: Option<u32> = None;
    let mut in_onu = false;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                match local.as_str() {
                    "channel-termination" => current_channel_term.clear(),
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
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    debug!(count = entries.len(), "Parsed ranging entries");
    entries
}

// ── Notification parsing ────────────────────────────────────────────────────

/// Parse a NETCONF notification for ONU state changes.
///
/// Expected structure:
/// ```xml
/// <notification xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
///   <eventTime>2026-03-18T10:30:00Z</eventTime>
///   <onu-state-change xmlns="urn:bbf:yang:bbf-xpon-onu-state">
///     <detected-serial-number>ADTN153201C4</detected-serial-number>
///     <onu-id>1</onu-id>
///     <channel-termination-ref>CTP-0/1</channel-termination-ref>
///     <onu-state>onu-not-present-without-v-ani</onu-state>
///   </onu-state-change>
/// </notification>
/// ```
pub fn parse_onu_state_change_notification(xml: &str) -> Option<OntStateEntry> {
    let mut reader = Reader::from_str(xml);
    let mut buf = Vec::new();

    let mut in_state_change = false;
    let mut serial = String::new();
    let mut onu_id: u32 = 0;
    let mut state_str = String::new();
    let mut channel_term = String::new();
    let mut datetime: Option<String> = None;
    let mut current_elem = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu-state-change" {
                    in_state_change = true;
                }
                current_elem = local;
            }
            Ok(Event::Text(e)) if in_state_change => {
                if let Ok(text) = e.unescape() {
                    let text = text.trim();
                    if text.is_empty() {
                        buf.clear();
                        continue;
                    }
                    match current_elem.as_str() {
                        "detected-serial-number" => serial = text.to_string(),
                        "onu-id" => onu_id = text.parse().unwrap_or(0),
                        "onu-state" => state_str = text.to_string(),
                        "channel-termination-ref" => channel_term = text.to_string(),
                        "onu-state-last-change" | "eventTime" => {
                            datetime = Some(text.to_string())
                        }
                        _ => {}
                    }
                }
            }
            Ok(Event::End(e)) => {
                let local =
                    String::from_utf8_lossy(local_name(e.name().as_ref())).to_string();
                if local == "onu-state-change" {
                    in_state_change = false;
                }
                current_elem.clear();
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    if !serial.is_empty() {
        Some(OntStateEntry {
            serial_number: serial,
            onu_id,
            channel_term,
            state: OntYangState::from_yang(&state_str),
            detected_datetime: datetime,
            v_ani_ref: None,
        })
    } else {
        None
    }
}

/// Parse a dying-gasp alarm from a NETCONF notification.
///
/// Returns `(serial_number, true)` if this is a dying-gasp alarm.
/// Dying gasp = power outage (ONT sent last-gasp before losing power).
/// No dying gasp + offline = fibre cut (physical break, no warning).
pub fn parse_dying_gasp(xml: &str) -> Option<(String, bool)> {
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
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    if alarm_type.contains("dying-gasp") {
        let serial = resource
            .strip_prefix("onu:")
            .unwrap_or(&resource)
            .to_string();
        Some((serial, true))
    } else {
        None
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

        let caps = parse_capabilities(hello);
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

        let entries = parse_ont_state(xml);
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

        let entries = parse_optical_power(xml);
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

        let entries = parse_ranging(xml);
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

        let entry = parse_onu_state_change_notification(xml).expect("should parse notification");
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

        let (serial, is_dying_gasp) = parse_dying_gasp(xml).expect("should parse dying gasp");
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

        assert!(parse_dying_gasp(xml).is_none());
    }
}
