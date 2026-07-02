// SPDX-License-Identifier: Apache-2.0
// CDATA OLT Collector (FD1104, FD1108, FD1216 series)
//
// Enterprise OID: 34592 (FD MIBs), but real FD-series report
// sysObjectID = 1.3.6.1.4.1.17409 (bare NSCRTV enterprise) — verified in
// data/external/snmp-dumps/cdata/librenms_cdata.snmprec and LibreNMS
// os_detection/cdata.yaml (matches on .17409).
//
// ONU table: FD-ONU-MIB onuBaseManageTable = 1.3.6.1.4.1.34592.1.3.4.1,
// INDEX { ponCardSlotId (1..4), oltId (PON port 1..16), onuId (1..64) } —
// i.e. row suffix is <slot>.<pon>.<onuId>, three components.
// Source: https://github.com/librenms/librenms/blob/master/mibs/cdata/FD-ONU-MIB
// (+ FD-OLT-MIB / FD-SYSTEM-MIB for the index TCs).
//
// onuOnLineStatus (.11) is EPON-EOC-MIB DeviceStatus:
//   notPresent(1), offline(2), online(3), normal(4), abnormal(5)
//
// Optical scaling: onuLaserRxPower (.36) / onuLaserTxPower (.37) are LINEAR
// power in 0.1 µW units — dBm = 10*log10(value * 0.0001); e.g. raw 1958 →
// -7.08 dBm, raw 60 → -22.22 dBm. NOT a centi-dBm integer: the old /100
// scaling reported raw 60 (= -22.2 dBm) as 0.6 dBm.
// Source: https://www.zabbix.com/forum/zabbix-help/43323-convert-miliwatts-to-dbm

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;
use super::snmp_helper::plausible_dbm;

/// FD-ONU-MIB laser power: raw is linear power in 0.1 µW units.
/// dBm = 10*log10(raw * 0.0001 mW). raw <= 0 (no light / sentinel) → None,
/// plus the shared plausibility window.
pub(crate) fn cdata_optical_dbm(raw: i64) -> Option<f64> {
    if raw <= 0 {
        return None;
    }
    plausible_dbm(10.0 * (raw as f64 * 0.0001).log10())
}

/// EPON-EOC-MIB DeviceStatus (verbatim MIB enum, see module header).
fn cdata_status(v: i64) -> OntStatus {
    match v {
        3 | 4 | 5 => OntStatus::Online, // online / normal / "online but abnormal"
        2 => OntStatus::Offline,
        1 => OntStatus::Offline, // notPresent
        _ => OntStatus::Unknown,
    }
}

/// Split an onuBaseManageTable row suffix "<slot>.<pon>.<onuId>" into
/// (pon_port "slot/pon", onu_id).
pub(crate) fn parse_cdata_index(index: &str) -> Option<(String, u32)> {
    let parts: Vec<u32> = index.split('.').map(|s| s.parse().ok()).collect::<Option<_>>()?;
    if parts.len() != 3 {
        return None;
    }
    Some((format!("{}/{}", parts[0], parts[1]), parts[2]))
}

pub struct CdataCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl CdataCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("cdata-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // Walk errors (incl. partial walks) propagate — never a silent 0.
        let serials = snmp.walk_table(oids::cdata::ONT_SERIAL).await?;
        let statuses = snmp.walk_table(oids::cdata::ONT_STATUS).await?;
        let rx_powers = snmp.walk_table(oids::cdata::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(oids::cdata::ONT_TX_POWER).await?;
        let distances = snmp.walk_table(oids::cdata::ONT_DISTANCE).await?;

        // Use serial column for enumeration; fall back to status column
        let primary = if !serials.is_empty() { &serials } else { &statuses };
        if primary.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "CData OLT returned no rows from onuBaseManageTable \
                 (34592.1.3.4.1) — no ONT data collected; check MIB \
                 exposure (older FD firmware may only speak NSCRTV .17409)"
            );
            return Ok(Vec::new());
        }

        let mut onts = Vec::new();
        for entry in primary.iter() {
            // INDEX { ponCardSlotId, oltId, onuId } → 3-component suffix
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 3);
            let (pon_port, onu_id) = match parse_cdata_index(&index) {
                Some(v) => v,
                None => continue,
            };

            let serial = if !serials.is_empty() {
                match &entry.value {
                    crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                    _ => format!("cdata-{}", index),
                }
            } else {
                format!("cdata-{}", index)
            };

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => cdata_status(*i),
                    _ => OntStatus::Unknown,
                })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => cdata_optical_dbm(*i),
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => cdata_optical_dbm(*i),
                    _ => None,
                });

            // onuRangeValue: units not documented in FD-ONU-MIB (meters by
            // common usage — unverified); reject clearly bogus values.
            let distance = super::snmp_helper::find_by_suffix(&distances, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) if (0..=200_000).contains(i) => Some(*i as u32),
                    _ => None,
                });

            let refined_status = match (&status, rx_power) {
                (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                _ => status,
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port,
                ont_index: onu_id,
                status: refined_status,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: rx_power, tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
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
        let cpu = snmp.get(oids::cdata::CPU_UTIL).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let temp = snmp.get(oids::cdata::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        (cpu, None, temp) // CDATA doesn't expose memory utilization via SNMP
    }
}

#[async_trait]
impl OltCollector for CdataCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "cdata" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for CDATA OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        // Try proprietary model OID first, fall back to sysDescr
        let model = snmp.get(oids::cdata::MODEL_NAME).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => Some(s),
                _ => None,
            })
            .unwrap_or_else(|| super::huawei::extract_string_pub(&sys_descr));

        let onts = self.collect_onts_snmp().await?;
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
            vendor: "cdata".into(),
            model,
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cdata_optical_linear_01uw_to_dbm() {
        // Community-verified examples (zabbix.com/forum/zabbix-help/43323):
        // raw 1958 (×0.1 µW) → -7.08 dBm; raw 60 → -22.22 dBm
        let v = cdata_optical_dbm(1958).unwrap();
        assert!((v - (-7.08)).abs() < 0.01, "got {v}");
        let v = cdata_optical_dbm(60).unwrap();
        assert!((v - (-22.22)).abs() < 0.01, "got {v}");
        // The old copy-pasted /100 scaling would have called raw 60
        // "0.6 dBm" — a healthy-looking level for a nearly-dead ONT.
    }

    #[test]
    fn test_cdata_optical_sentinels_and_zero() {
        assert_eq!(cdata_optical_dbm(0), None);   // no light
        assert_eq!(cdata_optical_dbm(-1), None);  // negative linear power
        // Huge linear values → above +10 dBm window → None
        assert_eq!(cdata_optical_dbm(2147483647), None);
    }

    #[test]
    fn test_parse_cdata_index_slot_pon_onu() {
        // FD-ONU-MIB INDEX { ponCardSlotId, oltId, onuId } — e.g. row
        // 34592.1.3.4.1.1.36.1.3.7 = slot 1, PON 3, ONU 7
        assert_eq!(parse_cdata_index("1.3.7"), Some(("1/3".into(), 7)));
        assert_eq!(parse_cdata_index("4.16.64"), Some(("4/16".into(), 64)));
        // Old code assumed 2 components (slot.onuId) — must be rejected
        assert_eq!(parse_cdata_index("1.3"), None);
        assert_eq!(parse_cdata_index("x.y.z"), None);
    }

    #[test]
    fn test_cdata_status_devicestatus_enum() {
        assert_eq!(cdata_status(3), OntStatus::Online);  // online
        assert_eq!(cdata_status(4), OntStatus::Online);  // normal
        assert_eq!(cdata_status(5), OntStatus::Online);  // abnormal but up
        assert_eq!(cdata_status(2), OntStatus::Offline);
        assert_eq!(cdata_status(1), OntStatus::Offline); // notPresent
        assert_eq!(cdata_status(99), OntStatus::Unknown);
    }
}
