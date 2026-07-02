// SPDX-License-Identifier: Apache-2.0
// VSOL OLT Collector (V1600G, V1600D series)
//
// Enterprise OID: 1.3.6.1.4.1.37950
// Uses NSCRTV-FTTX-GPON-MIB (enterprise .17409) — Chinese national standard.
// VSOL uses the same GPON chipset as many Chinese OLTs that implement this MIB.
//
// Collects via SNMP v2c:
//   - ONT serial, status, RX/TX power, distance (NSCRTV OIDs)
//   - OLT system info via standard MIBs

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct VsolCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl VsolCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("vsol-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_nscrtv(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // NSCRTV-FTTX-GPON-MIB ONT tables
        let serials = snmp.walk_table(oids::nscrtv::ONT_SERIAL).await.unwrap_or_default();
        let statuses = snmp.walk_table(oids::nscrtv::ONT_STATUS).await.unwrap_or_default();
        let rx_powers = snmp.walk_table(oids::nscrtv::ONT_RX_POWER).await.unwrap_or_default();
        let tx_powers = snmp.walk_table(oids::nscrtv::ONT_TX_POWER).await.unwrap_or_default();
        let distances = snmp.walk_table(oids::nscrtv::ONT_DISTANCE).await.unwrap_or_default();

        // If NSCRTV serials empty, fall back to ifDescr for interface enumeration
        if serials.is_empty() && statuses.is_empty() {
            return Ok(Vec::new());
        }

        let primary = if !serials.is_empty() { &serials } else { &statuses };

        let mut onts = Vec::new();
        for (idx, entry) in primary.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 1);

            let serial = if !serials.is_empty() {
                match &entry.value {
                    crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                    _ => format!("vsol-{}", index),
                }
            } else {
                format!("vsol-{}", index)
            };

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(1) => OntStatus::Online,
                    crate::snmp::SnmpData::Integer(2) => OntStatus::Offline,
                    crate::snmp::SnmpData::Integer(3) => OntStatus::PowerFail,
                    _ => OntStatus::Offline,
                })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 100.0), // 0.01 dBm
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 100.0),
                    _ => None,
                });

            let distance = super::snmp_helper::find_by_suffix(&distances, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as u32),
                    _ => None,
                });

            let refined_status = match (&status, rx_power) {
                (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                _ => status,
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port: format!("pon-{}", idx / 64),
                ont_index: (idx % 64) as u32,
                status: refined_status,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: rx_power, tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        Ok(onts)
    }
}

#[async_trait]
impl OltCollector for VsolCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "vsol" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for VSOL OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_nscrtv().await.unwrap_or_default();

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
            vendor: "vsol".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(), serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: None, memory_percent: None,
            temperature_celsius: None, power_supply_status: None,
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
