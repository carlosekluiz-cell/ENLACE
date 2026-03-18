// SPDX-License-Identifier: Apache-2.0
// Parks OLT Collector (Fiberlink 200xx series)
//
// Enterprise OID: 1.3.6.1.4.1.6771
// Parks Fiberlink OLTs use Chinese GPON chipsets that implement the
// NSCRTV-FTTX-GPON-MIB (enterprise .17409).
//
// Collects via SNMP v2c:
//   - ONT serial, status, RX/TX power, distance (NSCRTV OIDs)
//   - Interface data (standard IF-MIB)

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct ParksCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl ParksCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("parks-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_nscrtv(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // NSCRTV-FTTX-GPON-MIB ONT tables (same as VSOL)
        let serials = snmp.walk_table(oids::nscrtv::ONT_SERIAL).await.unwrap_or_default();
        let statuses = snmp.walk_table(oids::nscrtv::ONT_STATUS).await.unwrap_or_default();
        let rx_powers = snmp.walk_table(oids::nscrtv::ONT_RX_POWER).await.unwrap_or_default();
        let tx_powers = snmp.walk_table(oids::nscrtv::ONT_TX_POWER).await.unwrap_or_default();
        let distances = snmp.walk_table(oids::nscrtv::ONT_DISTANCE).await.unwrap_or_default();

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
                    _ => format!("parks-{}", index),
                }
            } else {
                format!("parks-{}", index)
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
                pon_port: format!("pon-{}", idx / 64),
                ont_index: (idx % 64) as u32,
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

    async fn collect_uplinks(&self) -> Vec<UplinkPortData> {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return Vec::new(),
        };

        let if_descrs = snmp.walk_table(oids::IF_DESCR).await.unwrap_or_default();
        let if_statuses = snmp.walk_table(oids::IF_OPER_STATUS).await.unwrap_or_default();
        let if_in = snmp.walk_table(oids::IF_HC_IN_OCTETS).await.unwrap_or_default();
        let if_out = snmp.walk_table(oids::IF_HC_OUT_OCTETS).await.unwrap_or_default();

        let mut uplinks = Vec::new();
        for entry in &if_descrs {
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 1);
            let name = match &entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };

            let oper_status = super::snmp_helper::find_by_suffix(&if_statuses, &index)
                .map(|v| match v { crate::snmp::SnmpData::Integer(1) => "up", _ => "down" })
                .unwrap_or("unknown");

            let in_octets = super::snmp_helper::find_by_suffix(&if_in, &index)
                .and_then(|v| match v { crate::snmp::SnmpData::Counter64(c) => Some(*c), _ => None })
                .unwrap_or(0);
            let out_octets = super::snmp_helper::find_by_suffix(&if_out, &index)
                .and_then(|v| match v { crate::snmp::SnmpData::Counter64(c) => Some(*c), _ => None })
                .unwrap_or(0);

            uplinks.push(UplinkPortData {
                port_id: name, oper_status: oper_status.into(), speed_mbps: 1000,
                in_octets, out_octets, in_errors: 0, out_errors: 0,
            });
        }
        uplinks
    }
}

#[async_trait]
impl OltCollector for ParksCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "parks" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for Parks OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_nscrtv().await.unwrap_or_default();
        let uplinks = self.collect_uplinks().await;

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
            vendor: "parks".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(), serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: None, memory_percent: None,
            temperature_celsius: None, power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: uplinks, onts,
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
