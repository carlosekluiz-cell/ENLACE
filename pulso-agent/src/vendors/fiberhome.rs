// SPDX-License-Identifier: Apache-2.0
// FiberHome OLT Collector (AN5516, AN5116, AN6001, AN6000)
// Also used for Intelbras-branded FiberHome equipment.
//
// Enterprise OID: 1.3.6.1.4.1.5875
// MIB sources: FIBERHOME-OLT-COMMON-MIB, snmp-fiberhome npm library
//
// Index encoding: onuIndex = slot*(2^25) + pon*(2^19) + onuId*(2^8)
//
// Collects via SNMP v2c:
//   - ONT serial (authOnuListSnLoid), status, RX/TX power, distance
//   - OLT CPU, memory, temperature

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct FiberhomeCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl FiberhomeCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("fiberhome-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // Walk ONT tables — use serial OID (.8) for primary identification
        let serials = snmp.walk_table(oids::fiberhome::ONT_SERIAL).await.unwrap_or_default();
        let statuses = snmp.walk_table(oids::fiberhome::ONT_STATUS).await.unwrap_or_default();
        let rx_powers = snmp.walk_table(oids::fiberhome::ONT_RX_POWER).await.unwrap_or_default();
        let tx_powers = snmp.walk_table(oids::fiberhome::ONT_TX_POWER).await.unwrap_or_default();
        let distances = snmp.walk_table(oids::fiberhome::ONT_DISTANCE).await.unwrap_or_default();

        // If serial OID returns nothing, fall back to MAC or description
        let primary_ids = if !serials.is_empty() {
            serials
        } else {
            let macs = snmp.walk_table(oids::fiberhome::ONT_MAC).await.unwrap_or_default();
            if !macs.is_empty() { macs } else {
                snmp.walk_table(oids::fiberhome::ONT_DESCR).await.unwrap_or_default()
            }
        };

        let mut onts = Vec::new();
        for (idx, id_entry) in primary_ids.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&id_entry.oid, 1);
            let serial = match &id_entry.value {
                crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                _ => format!("fh-{}", index),
            };

            // Decode slot/pon/onuId from FiberHome index
            let encoded: u64 = index.parse().unwrap_or(0);
            let slot = (encoded >> 25) & 0x1F;
            let pon = (encoded >> 19) & 0x3F;
            let onu_id = (encoded >> 8) & 0x7FF;

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(1) => OntStatus::Online,
                    crate::snmp::SnmpData::Integer(2) => OntStatus::PowerFail,
                    crate::snmp::SnmpData::Integer(3) => OntStatus::FiberCut,
                    _ => OntStatus::Offline,
                })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 100.0),
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
                pon_port: format!("{}/{}", slot, pon),
                ont_index: onu_id as u32,
                status: refined_status,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: rx_power, tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                eth_speed_mbps: None,
            });
        }
        Ok(onts)
    }

    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None, None),
        };

        let cpu = snmp.get(oids::fiberhome::CPU_UTIL).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let mem = snmp.get(oids::fiberhome::MEM_UTIL).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let temp = snmp.get(oids::fiberhome::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        (cpu, mem, temp)
    }
}

#[async_trait]
impl OltCollector for FiberhomeCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "fiberhome" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for FiberHome OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_snmp().await.unwrap_or_default();
        let (cpu, mem, temp) = self.collect_system_health().await;

        let mut pon_ports = std::collections::HashMap::new();
        for ont in &onts {
            let entry = pon_ports.entry(ont.pon_port.clone()).or_insert(PonPortData {
                port_id: ont.pon_port.clone(),
                oper_status: "up".into(),
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
            vendor: "fiberhome".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(),
            serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: cpu, memory_percent: mem,
            temperature_celsius: temp, power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: Vec::new(),
            onts,
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
