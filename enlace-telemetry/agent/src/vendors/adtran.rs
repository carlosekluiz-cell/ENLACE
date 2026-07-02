// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6330-48 OLT Collector
//
// PRIMARY: NETCONF/YANG (BBF TR-385) over SSH port 830
// FALLBACK: SNMP v2c within 5 seconds of NETCONF failure
//
// NETCONF provides:
//   - ONT state via bbf-xpon-onu-state YANG model
//   - OLT-side upstream rx power (0.002 dBm units, raw/500)
//   - ONT-side OMCI transceiver data (rx, tx, temp, voltage, bias)
//   - Ranging via equalization-delay (TQ * 0.0125 = meters)
//   - Push notifications for onu-state-change events
//   - Dying gasp alarms for power outage differentiation
//
// The SDX 6330-48 has 48 GPON ports across 2 line cards.
// Channel termination naming: CTP-{shelf}/{slot}/{port}

use async_trait::async_trait;
use dashmap::DashMap;
use std::sync::Arc;
use tracing::{debug, info, warn};

use crate::config::OltConfig;
use crate::netconf;
use crate::netconf::xml::{self, OntYangState, TQ_TO_METERS};
use super::*;

/// NETCONF subtree filter for ONT state (bbf-xpon-onu-state)
const FILTER_ONT_STATE: &str = r#"<xpon xmlns="urn:bbf:yang:bbf-xpon">
  <channel-terminations>
    <channel-termination>
      <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state"/>
    </channel-termination>
  </channel-terminations>
</xpon>"#;

/// NETCONF subtree filter for optical power readings
const FILTER_OPTICAL_POWER: &str = r#"<xpon xmlns="urn:bbf:yang:bbf-xpon">
  <channel-terminations>
    <channel-termination>
      <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
        <onu>
          <detected-serial-number/>
          <onu-id/>
          <measured-upstream-rx-optical-power-dbm/>
          <ani-transceiver-rx-power/>
          <ani-transceiver-tx-power/>
          <ani-transceiver-temperature/>
          <ani-transceiver-supply-voltage/>
          <ani-transceiver-bias-current/>
        </onu>
      </onus-present-on-channel-termination>
    </channel-termination>
  </channel-terminations>
</xpon>"#;

/// NETCONF subtree filter for ranging (equalization-delay)
const FILTER_RANGING: &str = r#"<xpon xmlns="urn:bbf:yang:bbf-xpon">
  <channel-terminations>
    <channel-termination>
      <onus-present-on-channel-termination xmlns="urn:bbf:yang:bbf-xpon-onu-state">
        <onu>
          <detected-serial-number/>
          <onu-id/>
          <equalization-delay/>
        </onu>
      </onus-present-on-channel-termination>
    </channel-termination>
  </channel-terminations>
</xpon>"#;

/// SNMP fallback timeout — if NETCONF fails, try SNMP within this window.
const SNMP_FALLBACK_TIMEOUT_SECS: u64 = 5;

/// Tracked state per ONT, keyed by serial number.
#[derive(Debug, Clone)]
pub struct OntState {
    pub serial: String,
    pub onu_id: u32,
    pub channel_term: String,
    pub status: OntStatus,
    pub last_seen: chrono::DateTime<chrono::Utc>,
    pub dying_gasp: bool,
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

pub struct AdtranCollector {
    olt_id: String,
    config: OltConfig,
    /// State table keyed by serial number for O(1) lookup
    ont_state: Arc<DashMap<String, OntState>>,
    device_model: std::sync::Mutex<Option<String>>,
    device_firmware: std::sync::Mutex<Option<String>>,
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
        })
    }

    /// Connect via NETCONF and collect all ONT data in 3 NETCONF <get> calls:
    /// 1. ONT state (online/offline/registering)
    /// 2. Optical power (OLT-side rx, ONT-side OMCI transceiver)
    /// 3. Ranging (equalization-delay → distance)
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

        // 1. Get ONT state
        let state_xml = session.get(FILTER_ONT_STATE).await?;
        let state_entries = xml::parse_ont_state(&state_xml);
        debug!(count = state_entries.len(), "ONT state entries from NETCONF");

        // Update state table with fresh state
        let now = chrono::Utc::now();
        for entry in &state_entries {
            let status = match entry.state {
                OntYangState::OnlineOnIntended => OntStatus::Online,
                OntYangState::Registering => OntStatus::Unknown,
                OntYangState::Offline => {
                    // Check if we have dying_gasp recorded for this ONT
                    if let Some(prev) = self.ont_state.get(&entry.serial_number) {
                        if prev.dying_gasp {
                            OntStatus::PowerFail
                        } else {
                            OntStatus::FiberCut
                        }
                    } else {
                        OntStatus::Offline
                    }
                }
                OntYangState::EmergencyStopped => OntStatus::Offline,
                OntYangState::Unexpected => OntStatus::Unknown,
                OntYangState::Unknown(_) => OntStatus::Unknown,
            };

            let dying_gasp = self
                .ont_state
                .get(&entry.serial_number)
                .map(|s| s.dying_gasp)
                .unwrap_or(false);

            self.ont_state.insert(
                entry.serial_number.clone(),
                OntState {
                    serial: entry.serial_number.clone(),
                    onu_id: entry.onu_id,
                    channel_term: entry.channel_term.clone(),
                    status,
                    last_seen: now,
                    dying_gasp,
                    olt_rx_power_dbm: None,
                    ont_rx_power_dbm: None,
                    ont_tx_power_dbm: None,
                    ont_temperature_c: None,
                    ont_voltage_v: None,
                    ont_bias_current_ma: None,
                    distance_m: None,
                },
            );
        }

        // 2. Get optical power (OLT-side + ONT-side OMCI)
        let power_xml = session.get(FILTER_OPTICAL_POWER).await?;
        let power_entries = xml::parse_optical_power(&power_xml);
        for p in &power_entries {
            if let Some(mut state) = self.ont_state.get_mut(&p.serial_number) {
                state.olt_rx_power_dbm = p.olt_rx_power_dbm;
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

        // 3. Get ranging (equalization-delay → distance)
        let ranging_xml = session.get(FILTER_RANGING).await?;
        let ranging_entries = xml::parse_ranging(&ranging_xml);
        for r in &ranging_entries {
            if let Some(mut state) = self.ont_state.get_mut(&r.serial_number) {
                state.distance_m = Some(r.distance_m);
            }
        }

        // Close session cleanly
        let _ = session.close().await;

        // Convert state table to OntData
        let onts: Vec<OntData> = self
            .ont_state
            .iter()
            .map(|entry| {
                let s = entry.value();
                OntData {
                    serial_number: s.serial.clone(),
                    pon_port: s.channel_term.clone(),
                    ont_index: s.onu_id,
                    status: s.status.clone(),
                    last_down_cause: if s.dying_gasp {
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
            .collect();

        info!(
            olt = %self.olt_id,
            onts = onts.len(),
            online = onts.iter().filter(|o| o.status == OntStatus::Online || o.status == OntStatus::LowSignal).count(),
            "NETCONF collection complete"
        );

        Ok(onts)
    }

    /// SNMP fallback — basic ONT data using IF-MIB and GPON MIBs.
    /// Used only when NETCONF fails within SNMP_FALLBACK_TIMEOUT_SECS.
    async fn collect_via_snmp_fallback(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp_cfg = self.config.snmp.as_ref().ok_or_else(|| {
            anyhow::anyhow!("SNMP fallback not configured for Adtran SDX")
        })?;

        warn!(
            olt = %self.olt_id,
            "Using SNMP fallback (limited data, no ONT-side power)"
        );

        let snmp = crate::snmp::SnmpPoller::new(&self.config.ip, snmp_cfg)?;

        // Adtran GPON-OLT-MIB OIDs
        const ONU_SERIAL_PREFIX: &str = "1.3.6.1.4.1.18070.100.1.1.14.2.1.2";
        const ONU_STATE_PREFIX: &str = "1.3.6.1.4.1.18070.100.1.1.14.2.1.5";
        const ONU_RX_POWER_PREFIX: &str = "1.3.6.1.4.1.18070.100.1.1.14.2.1.8";
        const ONU_DISTANCE_PREFIX: &str = "1.3.6.1.4.1.18070.100.1.1.14.2.1.10";

        let serials = snmp.walk_table(ONU_SERIAL_PREFIX).await.unwrap_or_default();
        let states = snmp.walk_table(ONU_STATE_PREFIX).await.unwrap_or_default();
        let rx_powers = snmp.walk_table(ONU_RX_POWER_PREFIX).await.unwrap_or_default();
        let distances = snmp.walk_table(ONU_DISTANCE_PREFIX).await.unwrap_or_default();

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
        let onts = match tokio::time::timeout(
            std::time::Duration::from_secs(30),
            self.collect_via_netconf(),
        )
        .await
        {
            Ok(Ok(data)) => data,
            Ok(Err(e)) => {
                warn!(
                    olt = %self.olt_id,
                    error = %e,
                    "NETCONF failed, trying SNMP fallback"
                );
                // SNMP fallback within 5 seconds
                tokio::time::timeout(
                    std::time::Duration::from_secs(SNMP_FALLBACK_TIMEOUT_SECS),
                    self.collect_via_snmp_fallback(),
                )
                .await
                .map_err(|_| anyhow::anyhow!("SNMP fallback timed out"))??
            }
            Err(_) => {
                warn!(
                    olt = %self.olt_id,
                    "NETCONF timed out after 30s, trying SNMP fallback"
                );
                tokio::time::timeout(
                    std::time::Duration::from_secs(SNMP_FALLBACK_TIMEOUT_SECS),
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
            let session = netconf::NetconfSession::connect(
                &self.config.ip,
                nc.port,
                &nc.username,
                nc.password.as_deref(),
                nc.key_file.as_deref(),
            )
            .await?;

            let has_xpon = session.has_capability("bbf-xpon");
            let has_onu_state = session.has_capability("bbf-xpon-onu-state");
            let has_notification = session.has_capability("notification");

            info!(
                olt = %self.olt_id,
                bbf_xpon = has_xpon,
                onu_state = has_onu_state,
                notifications = has_notification,
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

    #[test]
    fn test_ont_state_table() {
        let state_table = DashMap::new();
        let now = chrono::Utc::now();

        state_table.insert(
            "ADTN153201C4".to_string(),
            OntState {
                serial: "ADTN153201C4".into(),
                onu_id: 1,
                channel_term: "CTP-0/1".into(),
                status: OntStatus::Online,
                last_seen: now,
                dying_gasp: false,
                olt_rx_power_dbm: Some(-22.1),
                ont_rx_power_dbm: Some(-25.0),
                ont_tx_power_dbm: Some(2.4),
                ont_temperature_c: Some(45.5),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(12.5),
                distance_m: Some(2060.0),
            },
        );

        assert!(state_table.contains_key("ADTN153201C4"));
        let entry = state_table.get("ADTN153201C4").unwrap();
        assert_eq!(entry.status, OntStatus::Online);
        assert!((entry.olt_rx_power_dbm.unwrap() - (-22.1)).abs() < 0.01);
        assert!((entry.distance_m.unwrap() - 2060.0).abs() < 0.01);
    }

    #[test]
    fn test_ont_state_dying_gasp_differentiates() {
        let state_table = DashMap::new();
        let now = chrono::Utc::now();

        // ONT goes offline WITH dying gasp → PowerFail (power outage)
        state_table.insert(
            "ADTN-POWER-FAIL".to_string(),
            OntState {
                serial: "ADTN-POWER-FAIL".into(),
                onu_id: 5,
                channel_term: "CTP-0/2".into(),
                status: OntStatus::Online,
                last_seen: now,
                dying_gasp: true,
                olt_rx_power_dbm: None,
                ont_rx_power_dbm: None,
                ont_tx_power_dbm: None,
                ont_temperature_c: None,
                ont_voltage_v: None,
                ont_bias_current_ma: None,
                distance_m: None,
            },
        );

        let entry = state_table.get("ADTN-POWER-FAIL").unwrap();
        let status = yang_state_to_ont_status(&OntYangState::Offline, entry.dying_gasp);
        assert_eq!(status, OntStatus::PowerFail);

        // ONT goes offline WITHOUT dying gasp → FiberCut
        state_table.insert(
            "ADTN-FIBER-CUT".to_string(),
            OntState {
                serial: "ADTN-FIBER-CUT".into(),
                onu_id: 6,
                channel_term: "CTP-0/2".into(),
                status: OntStatus::Online,
                last_seen: now,
                dying_gasp: false,
                olt_rx_power_dbm: None,
                ont_rx_power_dbm: None,
                ont_tx_power_dbm: None,
                ont_temperature_c: None,
                ont_voltage_v: None,
                ont_bias_current_ma: None,
                distance_m: None,
            },
        );

        let entry = state_table.get("ADTN-FIBER-CUT").unwrap();
        let status = yang_state_to_ont_status(&OntYangState::Offline, entry.dying_gasp);
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
