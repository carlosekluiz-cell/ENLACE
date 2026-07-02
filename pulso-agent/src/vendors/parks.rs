// SPDX-License-Identifier: Apache-2.0
// Parks OLT Collector (Fiberlink 200xx / 100xx series)
//
// Enterprise OIDs seen in the wild: 6771 (classic) and 50224 (newer gear —
// a real PK-700 reports sysObjectID 1.3.6.1.4.1.50224.3.1.1, see
// data/external/snmp-dumps/parks/librenms_parks-switch.snmprec).
//
// Parks Fiberlink OLTs use Chinese GPON chipsets that implement the
// NSCRTV-FTTX-GPON-MIB (enterprise .17409.2.8):
//   - gponOnuInfoTable (…2.8.4.1.1): single packed GponDeviceIndex
//     (device<<24 | slot<<16 | pon<<8 | onuId), onuOperationStatus up(1)/down(2),
//     onuTestDistance in meters
//   - optical table (…2.8.4.4.1): columns in centi-dBm → dBm = value/100
// Source: https://github.com/librenms/librenms/blob/master/mibs/cdata/NSCRTV-FTTX-GPON-MIB
// Index decode + assembly shared with the VSOL collector (vsol.rs).
//
// NOT yet verified against a live Parks OLT — the only real Parks capture
// available is an ethernet switch with no PON tables. Optical values are
// gated by the plausibility window either way.

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

        // Walk errors (incl. partial walks) propagate — never a silent 0.
        let statuses = snmp.walk_table(oids::nscrtv::ONT_STATUS).await?;
        let serials = snmp.walk_table(oids::nscrtv::ONT_SERIAL).await?;
        if statuses.is_empty() && serials.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "Parks OLT returned no rows from the NSCRTV gponOnuInfoTable \
                 (17409.2.8.4.1) — no ONT data collected; this device may be \
                 an ethernet switch or use a different firmware MIB"
            );
            return Ok(Vec::new());
        }
        let rx_powers = snmp.walk_table(oids::nscrtv::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(oids::nscrtv::ONT_TX_POWER).await?;
        let distances = snmp.walk_table(oids::nscrtv::ONT_DISTANCE).await?;

        Ok(super::vsol::assemble_nscrtv(
            &self.olt_id, "parks",
            &statuses, &serials, &rx_powers, &tx_powers, &distances,
        ))
    }

    async fn collect_uplinks(&self) -> anyhow::Result<Vec<UplinkPortData>> {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return Ok(Vec::new()),
        };

        let if_descrs = snmp.walk_table(oids::IF_DESCR).await?;
        let if_statuses = snmp.walk_table(oids::IF_OPER_STATUS).await?;
        let if_in = snmp.walk_table(oids::IF_HC_IN_OCTETS).await?;
        let if_out = snmp.walk_table(oids::IF_HC_OUT_OCTETS).await?;

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
        Ok(uplinks)
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

        let onts = self.collect_onts_nscrtv().await?;
        let uplinks = self.collect_uplinks().await?;

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parks_uses_shared_nscrtv_decode() {
        // Same packed-index semantics as VSOL: device 1 slot 3 pon 2 onu 9
        assert_eq!(
            super::super::vsol::decode_nscrtv_index(0x0103_0209),
            Some(("3/2".into(), 9))
        );
        // The OLD code fabricated pon_port from walk order ("pon-{idx/64}")
        // — verify the shared path rejects port-level (onu=0) rows instead
        assert_eq!(super::super::vsol::decode_nscrtv_index(0x0103_0200), None);
    }
}
