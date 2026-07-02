// SPDX-License-Identifier: Apache-2.0
// FiberHome OLT Collector (AN5516, AN5116, AN6001, AN6000)
// Also used for Intelbras-branded FiberHome equipment.
//
// Enterprise OID: 1.3.6.1.4.1.5875
//
// Index encoding (VERIFIED — snmp-fiberhome npm package README + source
// `parseOnuIndex()`, https://github.com/tqandrade/snmp-fiberhome, matching
// the FiberHome GEPON 5116/5516 MIB Open Interface Specification):
//   onuIndex = slot*(2^25) + pon*(2^19) + onuId*(2^8) [+ port]
//   → slot = bits 25.. (8 bits), pon = bits 19..24 (6 bits),
//     onuId = bits 8..18 (11 bits); e.g. 369623296 = slot 11, pon 1, onu 1
//
// Status enum for 5875.800.3.10.1.1.11 (VERIFIED — snmp-fiberhome
// src/tables.js + the FiberHome MIB spec; AN5516):
//   0 = fiber cut, 1 = online, 2 = power cut (dying gasp), 3 = offline
//   (AN5516 NG-PON firmware only uses 0 = offline / 1 = online)
//
// Optical scaling (VERIFIED): "The parameter value divided by 100 equals
// actual value" (FiberHome MIB spec, PON Rx optical power) — dBm = v/100;
// the npm package decodes all per-ONU optical metrics as signed/100 too.
//
// Collects via SNMP v2c:
//   - ONT serial (authOnuListSnLoid), status, RX/TX power, distance
//   - OLT CPU, memory, temperature

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

/// Decode a FiberHome AN5516 onuIndex → (slot, pon, onuId).
/// Layout verified in snmp-fiberhome (`parseOnuIndex()`):
/// slot = 8 bits from bit 25, pon = 6 bits from bit 19, onu = 11 bits from bit 8.
pub(crate) fn decode_fiberhome_index(encoded: u64) -> (u64, u64, u64) {
    let slot = (encoded >> 25) & 0xFF;
    let pon = (encoded >> 19) & 0x3F;
    let onu_id = (encoded >> 8) & 0x7FF;
    (slot, pon, onu_id)
}

/// FiberHome ONU status (5875.800.3.10.1.1.11, AN5516 — see module header):
/// 0 = fiber cut, 1 = online, 2 = power cut, 3 = offline.
/// The previous mapping (2→PowerFail was right, but 3→FiberCut and
/// default→Offline were wrong: 0 is the fiber cut, 3 is a plain offline).
pub(crate) fn fiberhome_status(v: i64) -> OntStatus {
    match v {
        0 => OntStatus::FiberCut,
        1 => OntStatus::Online,
        2 => OntStatus::PowerFail,
        3 => OntStatus::Offline,
        _ => OntStatus::Unknown,
    }
}

/// FiberHome optical value: dBm = value/100 (verified, see module header),
/// gated by the plausibility window (sentinels → None).
pub(crate) fn fiberhome_optical_dbm(raw: i64) -> Option<f64> {
    super::snmp_helper::plausible_dbm(raw as f64 / 100.0)
}

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

        // Walk ONT tables — use serial OID (.8) for primary identification.
        // Walk errors (incl. partial walks) propagate — never silently
        // degrade to "OLT with zero ONTs" (audit finding 13).
        let serials = snmp.walk_table(oids::fiberhome::ONT_SERIAL).await?;
        let statuses = snmp.walk_table(oids::fiberhome::ONT_STATUS).await?;
        let rx_powers = snmp.walk_table(oids::fiberhome::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(oids::fiberhome::ONT_TX_POWER).await?;
        let distances = snmp.walk_table(oids::fiberhome::ONT_DISTANCE).await?;

        // If serial OID returns nothing, fall back to MAC or description
        let primary_ids = if !serials.is_empty() {
            serials
        } else {
            let macs = snmp.walk_table(oids::fiberhome::ONT_MAC).await?;
            if !macs.is_empty() { macs } else {
                let descrs = snmp.walk_table(oids::fiberhome::ONT_DESCR).await?;
                if descrs.is_empty() {
                    tracing::warn!(
                        olt = %self.olt_id,
                        "FiberHome OLT returned no ONTs from serial, MAC or \
                         description tables (5875.800.3.10.1.1) — suspicious \
                         for a production OLT; check MIB exposure/community"
                    );
                }
                descrs
            }
        };

        let mut onts = Vec::new();
        for id_entry in primary_ids.iter() {
            let index = super::snmp_helper::extract_oid_suffix(&id_entry.oid, 1);
            let serial = match &id_entry.value {
                crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                _ => format!("fh-{}", index),
            };

            // Decode slot/pon/onuId from the FiberHome onuIndex (see module
            // header for the verified bit layout)
            let encoded: u64 = index.parse().unwrap_or(0);
            let (slot, pon, onu_id) = decode_fiberhome_index(encoded);

            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => fiberhome_status(*i),
                    _ => OntStatus::Unknown,
                })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => fiberhome_optical_dbm(*i),
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => fiberhome_optical_dbm(*i),
                    _ => None,
                });

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
                pon_port: if slot == 0 && pon == 0 {
                    // Index didn't decode (non-numeric or zero) — say so
                    // rather than grouping ONTs on a fictitious "0/0" port
                    UNKNOWN_PON_PORT.to_string()
                } else {
                    format!("{}/{}", slot, pon)
                },
                ont_index: onu_id as u32,
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

        let onts = self.collect_onts_snmp().await?;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_fiberhome_index_documented_example() {
        // snmp-fiberhome README worked example: onuIndex 369623296 =
        // slot 11, pon 1, onu 1 (369623296 = 11*2^25 + 1*2^19 + 1*2^8)
        assert_eq!(decode_fiberhome_index(369623296), (11, 1, 1));
        // Round-trip the formula: slot*(2^25) + pon*(2^19) + onuId*(2^8)
        let idx = 14u64 * (1 << 25) + 8 * (1 << 19) + 120 * (1 << 8);
        assert_eq!(decode_fiberhome_index(idx), (14, 8, 120));
        // Slot is 8 bits — slots above 31 must not be masked away
        // (the old 0x1F mask corrupted slot 32+ chassis)
        let idx = 33u64 * (1 << 25) + 2 * (1 << 19) + 5 * (1 << 8);
        assert_eq!(decode_fiberhome_index(idx), (33, 2, 5));
    }

    #[test]
    fn test_fiberhome_status_an5516_enum() {
        // Verified enum: 0=fiber cut, 1=online, 2=power cut, 3=offline
        assert_eq!(fiberhome_status(0), OntStatus::FiberCut);
        assert_eq!(fiberhome_status(1), OntStatus::Online);
        assert_eq!(fiberhome_status(2), OntStatus::PowerFail);
        assert_eq!(fiberhome_status(3), OntStatus::Offline);
        assert_eq!(fiberhome_status(7), OntStatus::Unknown);
    }

    #[test]
    fn test_fiberhome_optical_scaling_and_sentinels() {
        // "The parameter value divided by 100 equals actual value" (dBm)
        assert_eq!(fiberhome_optical_dbm(-2245), Some(-22.45));
        assert_eq!(fiberhome_optical_dbm(305), Some(3.05));
        // Sentinels / garbage outside the physical window → None
        assert_eq!(fiberhome_optical_dbm(2147483647), None);
        assert_eq!(fiberhome_optical_dbm(65535), None);
        assert_eq!(fiberhome_optical_dbm(-32768), None);
    }
}
