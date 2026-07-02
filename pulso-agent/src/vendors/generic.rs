// SPDX-License-Identifier: Apache-2.0
// Generic OLT/Switch Collector (IF-MIB only)
// Fallback for unrecognized vendors — collects interface stats only, no ONT data.

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::SnmpPoller;
use super::*;

pub struct GenericCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl GenericCollector {
    /// Note: returns Self directly (no Result) because main.rs calls this as fallback without `?`
    pub fn new(config: &OltConfig) -> Self {
        let snmp = config.snmp.as_ref()
            .and_then(|s| SnmpPoller::new(&config.ip, s).ok());
        Self {
            olt_id: format!("generic-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        }
    }
}

#[async_trait]
impl OltCollector for GenericCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "generic" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for generic device"))?;

        let sys_descr = snmp.get(crate::snmp::oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(crate::snmp::oids::SYS_UPTIME).await.ok();

        // Collect standard IF-MIB interface data. Walk failures propagate:
        // swallowing them (`unwrap_or_default`) turned SNMP outages into a
        // clean "device with zero interfaces" (audit finding 13/16 pattern).
        // HC octet counters legitimately don't exist on some devices, so an
        // empty *successful* walk of those is fine — but errors are not.
        let if_descrs = snmp.walk_table(crate::snmp::oids::IF_DESCR).await?;
        let if_statuses = snmp.walk_table(crate::snmp::oids::IF_OPER_STATUS).await?;
        let if_in = snmp.walk_table(crate::snmp::oids::IF_HC_IN_OCTETS).await?;
        let if_out = snmp.walk_table(crate::snmp::oids::IF_HC_OUT_OCTETS).await?;

        let mut uplinks = Vec::new();
        for descr_entry in &if_descrs {
            let index = super::snmp_helper::extract_oid_suffix(&descr_entry.oid, 1);
            let name = match &descr_entry.value {
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
                port_id: name, oper_status: oper_status.into(),
                speed_mbps: 1000,
                in_octets, out_octets,
                in_errors: 0, out_errors: 0,
            });
        }

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "generic".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(), serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: None, memory_percent: None,
            temperature_celsius: None, power_supply_status: None,
            pon_ports: Vec::new(), uplink_ports: uplinks, onts: Vec::new(),
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
