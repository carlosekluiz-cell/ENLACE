// SPDX-License-Identifier: Apache-2.0
// Nokia OLT Collector (ISAM 7360, 7342, G-240 series)
//
// Enterprise OID: 1.3.6.1.4.1.637
// MIBs: ASAM-SYSTEM-MIB (CPU, memory), APON-MIB (ONT status, serial, SW version)
//
// Collects via SNMP v2c:
//   - ONT serial, status, software version (APON-MIB)
//   - OLT CPU, memory (ASAM-SYSTEM-MIB)
//   - Standard IF-MIB for interfaces

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct NokiaCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl NokiaCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("nokia-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // APON-MIB ONT tables
        let serials = snmp.walk_table(oids::nokia::ONT_SERIAL).await.unwrap_or_default();
        let statuses = snmp.walk_table(oids::nokia::ONT_STATUS).await.unwrap_or_default();
        let sw_versions = snmp.walk_table(oids::nokia::ONT_SW_VER).await.unwrap_or_default();

        let primary = if !serials.is_empty() { &serials } else { &statuses };
        if primary.is_empty() {
            return Ok(Vec::new());
        }

        let mut onts = Vec::new();
        for (idx, entry) in primary.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 1);

            let serial = if !serials.is_empty() {
                match &entry.value {
                    crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                    _ => format!("nokia-{}", index),
                }
            } else {
                format!("nokia-{}", index)
            };

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(1) => OntStatus::Online,
                    crate::snmp::SnmpData::Integer(2) => OntStatus::Offline,
                    _ => OntStatus::Offline,
                })
                .unwrap_or(OntStatus::Unknown);

            let firmware = super::snmp_helper::find_by_suffix(&sw_versions, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => Some(s.clone()),
                    _ => None,
                });

            onts.push(OntData {
                serial_number: serial,
                pon_port: format!("pon-{}", idx / 64),
                ont_index: (idx % 64) as u32,
                status,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: None, tx_power_dbm: None, // Nokia RX/TX requires proprietary MIB access
                distance_meters: None,
                vendor_id: Some("nokia".into()),
                equipment_id: None,
                firmware_version: firmware,
                in_octets: None, out_octets: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        Ok(onts)
    }

    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None),
        };

        let cpu = snmp.get(oids::nokia::CPU_LOAD).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });

        // Calculate memory percent from total/usage if both available
        let mem_total = snmp.get(oids::nokia::MEM_TOTAL).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f64),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f64),
                _ => None,
            });
        let mem_usage = snmp.get(oids::nokia::MEM_USAGE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f64),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f64),
                _ => None,
            });
        let mem_pct = match (mem_total, mem_usage) {
            (Some(total), Some(usage)) if total > 0.0 => Some((usage / total * 100.0) as f32),
            _ => None,
        };

        (cpu, mem_pct)
    }
}

#[async_trait]
impl OltCollector for NokiaCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "nokia" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for Nokia OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_snmp().await.unwrap_or_default();
        let (cpu, mem) = self.collect_system_health().await;

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
            vendor: "nokia".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(), serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: cpu, memory_percent: mem,
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
