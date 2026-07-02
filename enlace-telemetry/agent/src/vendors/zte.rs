// SPDX-License-Identifier: Apache-2.0
// ZTE OLT Collector (C300, C320, C600, C650)

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::SnmpPoller;
use super::*;

pub struct ZteCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl ZteCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("zte-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }
}

#[async_trait]
impl OltCollector for ZteCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "zte" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for ZTE OLT"))?;

        let sys_descr = snmp.get(crate::snmp::oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(crate::snmp::oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_snmp().await.unwrap_or_default();

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

        let (cpu, mem, temp) = self.collect_system_health().await;

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "zte".into(),
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
            snmp.get(crate::snmp::oids::SYS_DESCR).await.map(|_| true).map_err(Into::into)
        } else {
            Ok(false)
        }
    }
}

impl ZteCollector {
    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None, None),
        };
        let cpu = snmp.get(crate::snmp::oids::zte_sys::CPU_USAGE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let mem = snmp.get(crate::snmp::oids::zte_sys::MEM_USAGE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let temp = snmp.get(crate::snmp::oids::zte_sys::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        (cpu, mem, temp)
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        let serials = snmp.walk_table(crate::snmp::oids::zte::ONT_SERIAL).await?;
        let statuses = snmp.walk_table(crate::snmp::oids::zte::ONT_STATUS).await?;
        let rx_powers = snmp.walk_table(crate::snmp::oids::zte::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(crate::snmp::oids::zte::ONT_TX_POWER).await?;
        let distances = snmp.walk_table(crate::snmp::oids::zte::ONT_DISTANCE).await?;

        let mut onts = Vec::new();
        for (idx, serial_entry) in serials.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&serial_entry.oid, 2);
            let serial = match &serial_entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v { crate::snmp::SnmpData::Integer(1) => OntStatus::Online, _ => OntStatus::Offline })
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
                pon_port: format!("pon-{}", idx / 128),
                ont_index: (idx % 128) as u32,
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
