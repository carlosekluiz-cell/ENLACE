// SPDX-License-Identifier: Apache-2.0
// BDCOM OLT Collector (GP3600, P3310 series)
//
// Enterprise OID: 1.3.6.1.4.1.3320
// GPON branch: .10, EPON legacy branch: .101
// Sources: NAG Wiki, ixnfo.com, LibreNMS
//
// Collects via SNMP v2c:
//   - ONT status, RX/TX power (GPON .10.3)
//   - OLT CPU, memory, temperature
//   - Serial from ifDescr fallback (GPON{slot}/{port}:{onu_id})

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct BdcomCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl BdcomCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("bdcom-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // Try GPON branch first (.10.3)
        let statuses = snmp.walk_table(oids::bdcom::ONT_STATUS).await.unwrap_or_default();
        let rx_powers = snmp.walk_table(oids::bdcom::ONT_RX_POWER).await.unwrap_or_default();
        let tx_powers = snmp.walk_table(oids::bdcom::ONT_TX_POWER).await.unwrap_or_default();

        // If GPON branch empty, try EPON legacy
        let (statuses, rx_powers, tx_powers, is_epon) = if statuses.is_empty() {
            let epon_rx = snmp.walk_table(oids::bdcom::EPON_ONT_RX).await.unwrap_or_default();
            let epon_tx = snmp.walk_table(oids::bdcom::EPON_ONT_TX).await.unwrap_or_default();
            // For EPON, status can be derived from ifOperStatus
            let if_statuses = snmp.walk_table(oids::IF_OPER_STATUS).await.unwrap_or_default();
            (if_statuses, epon_rx, epon_tx, true)
        } else {
            (statuses, rx_powers, tx_powers, false)
        };

        // Get ifDescr for serial number extraction (format: "GPON0/8:5")
        let if_descrs = snmp.walk_table(oids::IF_DESCR).await.unwrap_or_default();

        let mut onts = Vec::new();
        for (idx, status_entry) in statuses.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&status_entry.oid, 1);

            let status_val = match &status_entry.value {
                crate::snmp::SnmpData::Integer(i) => *i,
                _ => -1,
            };

            let status = if is_epon {
                match status_val { 1 => OntStatus::Online, _ => OntStatus::Offline }
            } else {
                match status_val { 3 => OntStatus::Online, 0 => OntStatus::Offline, _ => OntStatus::Unknown }
            };

            // Extract serial from ifDescr if available (e.g., "GPON0/1:3")
            let serial = super::snmp_helper::find_by_suffix(&if_descrs, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) if s.contains("GPON") || s.contains("EPON") => Some(s.clone()),
                    _ => None,
                })
                .unwrap_or_else(|| format!("bdcom-{}", index));

            // Parse port from serial string
            let pon_port = if serial.contains('/') && serial.contains(':') {
                // "GPON0/8:5" → "0/8"
                serial.split(':').next()
                    .and_then(|s| s.strip_prefix("GPON").or(s.strip_prefix("EPON")))
                    .unwrap_or("unknown").to_string()
            } else {
                format!("pon-{}", idx / 64)
            };

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 10.0), // BDCOM: 0.1 dBm units
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 10.0),
                    _ => None,
                });

            let refined_status = match (&status, rx_power) {
                (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                _ => status,
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port,
                ont_index: (idx % 64) as u32,
                status: refined_status,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: rx_power, tx_power_dbm: tx_power,
                distance_meters: None,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        Ok(onts)
    }

    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None, None),
        };
        let cpu = snmp.get(oids::bdcom::CPU_1MIN).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        let mem = snmp.get(oids::bdcom::MEM_UTIL).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        let temp = snmp.get(oids::bdcom::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        (cpu, mem, temp)
    }
}

#[async_trait]
impl OltCollector for BdcomCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "bdcom" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for BDCOM OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_snmp().await.unwrap_or_default();
        let (cpu, mem, temp) = self.collect_system_health().await;

        let mut pon_ports = std::collections::HashMap::new();
        for ont in &onts {
            let entry = pon_ports.entry(ont.pon_port.clone()).or_insert(PonPortData {
                port_id: ont.pon_port.clone(), oper_status: "up".into(),
                onts_registered: 0, onts_online: 0, onts_offline: 0,
                bw_down_bps: 0, bw_up_bps: 0, utilization_percent: 0.0,
            });
            entry.onts_registered += 1;
            match ont.status {
                OntStatus::Online | OntStatus::LowSignal => entry.onts_online += 1,
                _ => entry.onts_offline += 1,
            }
        }

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "bdcom".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(), serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: cpu, memory_percent: mem,
            temperature_celsius: temp, power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: Vec::new(), onts,
        })
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        if let Some(snmp) = &self.snmp {
            snmp.get(oids::SYS_DESCR).await.map(|_| true).map_err(Into::into)
        } else {
            Ok(false)
        }
    }
}
