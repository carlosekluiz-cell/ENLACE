// SPDX-License-Identifier: Apache-2.0
// VSOL OLT Collector (V1600G, V1600D series)
//
// Enterprise OID: 1.3.6.1.4.1.37950 (sysObjectID 37950.1.1.5.10.14.1 on a
// real V1600D — data/external/snmp-dumps/vsol/librenms_vsolution_v1600d.snmprec).
//
// Two OID families:
//  1. NSCRTV-FTTX-GPON-MIB (enterprise .17409.2.8) — Chinese standard tree.
//     gponOnuInfoTable index is a single packed GponDeviceIndex:
//       device<<24 | slot<<16 | pon<<8 | onuId
//     (verbatim TC description: "Olt device-8bit OLT Card-8bit Pon
//     port-8bit OnuNUM-8bit"; device and pon must not be 0; onuId 0 means
//     "meaningless" i.e. a non-ONU row).
//     Optical columns are centi-dBm (UNITS "centi-dBm" → dBm = value/100).
//     Source: https://github.com/librenms/librenms/blob/master/mibs/cdata/NSCRTV-FTTX-GPON-MIB
//  2. VSOL-native tables under 37950.1.1.6 (GPON, V1600G) where optical
//     values are ASCII strings like "-19.32(dBm)" — no numeric scaling.
//     Source: github.com/LuizQuintana/TEMPLATES_OLT_VSOL_GPON (Zabbix
//     template: RTRIM "(dBm)"); LibreNMS PR #14853 (V1600D, os vsolution).
//
// The real V1600D capture contains NO NSCRTV rows at all — VSOL firmware
// support for .17409 is model/firmware dependent, hence the fallback.

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;
use super::snmp_helper::plausible_dbm;

/// Decode a packed NSCRTV GponDeviceIndex: device<<24 | slot<<16 | pon<<8 | onu.
/// Returns (pon_port "slot/pon", onu_id). Rows with onu byte 0 are port-level
/// rows, not ONUs (per the TC description) → None.
pub(crate) fn decode_nscrtv_index(v: u64) -> Option<(String, u32)> {
    if v > u32::MAX as u64 {
        return None;
    }
    let v = v as u32;
    let device = (v >> 24) & 0xFF;
    let slot = (v >> 16) & 0xFF;
    let pon = (v >> 8) & 0xFF;
    let onu = v & 0xFF;
    // "OLT device must not be 0 … Pon port must not be 0 … ONU logical ID
    // MUST never be set to 0" — anything violating that is not an ONU row.
    if device == 0 || pon == 0 || onu == 0 {
        return None;
    }
    Some((format!("{}/{}", slot, pon), onu))
}

/// NSCRTV optical value: centi-dBm (UNITS "centi-dBm") → dBm = value/100.
/// Firmware-specific sentinels (0x7FFF etc., not in the standard MIB) fall
/// outside the plausibility window and become None.
pub(crate) fn nscrtv_optical_dbm(raw: i64) -> Option<f64> {
    plausible_dbm(raw as f64 / 100.0)
}

/// Parse VSOL-native optical strings: "-19.32(dBm)", "-19.32 dBm", "-19.32".
pub(crate) fn parse_vsol_dbm_string(s: &str) -> Option<f64> {
    let cleaned = s.trim()
        .trim_end_matches("(dBm)")
        .trim_end_matches("dBm")
        .trim();
    plausible_dbm(cleaned.parse().ok()?)
}

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

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // NSCRTV standard tree first (walk errors propagate — no silent 0)
        let statuses = snmp.walk_table(oids::nscrtv::ONT_STATUS).await?;
        if !statuses.is_empty() {
            let serials = snmp.walk_table(oids::nscrtv::ONT_SERIAL).await?;
            let rx_powers = snmp.walk_table(oids::nscrtv::ONT_RX_POWER).await?;
            let tx_powers = snmp.walk_table(oids::nscrtv::ONT_TX_POWER).await?;
            let distances = snmp.walk_table(oids::nscrtv::ONT_DISTANCE).await?;
            return Ok(assemble_nscrtv(
                &self.olt_id, "vsol",
                &statuses, &serials, &rx_powers, &tx_powers, &distances,
            ));
        }

        // VSOL-native GPON tables (V1600G family, string-valued optical)
        let serials = snmp.walk_table(oids::vsol_native::ONT_SERIAL).await?;
        if serials.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "VSOL OLT returned no ONTs on the NSCRTV (.17409.2.8) or \
                 native (.37950.1.1.6) trees — EPON-only V1600D units expose \
                 a different diag table; no ONT data collected"
            );
            return Ok(Vec::new());
        }
        let rx_powers = snmp.walk_table(oids::vsol_native::ONT_RX_POWER).await?;

        let mut unknown_port_warned = false;
        let mut onts = Vec::new();
        for (idx, entry) in serials.iter().enumerate() {
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 1);
            let serial = match &entry.value {
                crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => s.clone(),
                _ => format!("vsol-{}", index),
            };
            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) => parse_vsol_dbm_string(s),
                    crate::snmp::SnmpData::Integer(i) => nscrtv_optical_dbm(*i),
                    _ => None,
                });

            // The native-table index encoding is not publicly documented —
            // report the port honestly as unknown instead of inventing one.
            if !unknown_port_warned {
                tracing::warn!(
                    olt = %self.olt_id,
                    "VSOL native table index encoding is undocumented — \
                     pon_port set to \"{}\"; port-level fault localization \
                     degraded (NSCRTV tree unavailable on this firmware)",
                    UNKNOWN_PON_PORT
                );
                unknown_port_warned = true;
            }

            onts.push(OntData {
                serial_number: serial,
                pon_port: UNKNOWN_PON_PORT.to_string(),
                ont_index: idx as u32,
                status: match rx_power {
                    Some(rx) if rx < -27.0 => OntStatus::LowSignal,
                    Some(_) => OntStatus::Online,
                    // No optical reading and no verified status column:
                    // Unknown, never guessed Offline
                    None => OntStatus::Unknown,
                },
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: rx_power, tx_power_dbm: None,
                distance_meters: None,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        Ok(onts)
    }
}

/// Shared NSCRTV gponOnuInfoTable + optical-table assembly (used by VSOL and
/// Parks — both ship NSCRTV-speaking Chinese GPON chipsets).
pub(crate) fn assemble_nscrtv(
    olt_id: &str,
    vendor: &str,
    statuses: &[crate::snmp::SnmpValue],
    serials: &[crate::snmp::SnmpValue],
    rx_powers: &[crate::snmp::SnmpValue],
    tx_powers: &[crate::snmp::SnmpValue],
    distances: &[crate::snmp::SnmpValue],
) -> Vec<OntData> {
    use std::collections::BTreeMap;

    #[derive(Default)]
    struct Accum {
        serial: Option<String>,
        status: Option<OntStatus>,
        rx: Option<f64>,
        tx: Option<f64>,
        dist: Option<u32>,
    }

    // Key rows by decoded (pon_port, onu). The info table has a single packed
    // index component; the optical table is <packedIndex>.<cardIdx>.<portIdx>
    // — in both cases the FIRST trailing component after the column OID that
    // decodes as a valid GponDeviceIndex identifies the ONU.
    fn key_of(oid: &str) -> Option<(String, u32)> {
        oid.split('.')
            .filter_map(|s| s.parse::<u64>().ok())
            .filter_map(decode_nscrtv_index)
            .next()
    }

    let mut accum: BTreeMap<(String, u32), Accum> = BTreeMap::new();

    for e in statuses {
        if let (Some(k), crate::snmp::SnmpData::Integer(v)) = (key_of(&e.oid), &e.value) {
            // onuOperationStatus: up(1), down(2) — verbatim MIB enum
            accum.entry(k).or_default().status = Some(match v {
                1 => OntStatus::Online,
                2 => OntStatus::Offline,
                _ => OntStatus::Unknown,
            });
        }
    }
    for e in serials {
        if let (Some(k), crate::snmp::SnmpData::OctetString(s)) = (key_of(&e.oid), &e.value) {
            if !s.is_empty() {
                accum.entry(k).or_default().serial = Some(s.clone());
            }
        }
    }
    for e in rx_powers {
        if let (Some(k), crate::snmp::SnmpData::Integer(v)) = (key_of(&e.oid), &e.value) {
            let a = accum.entry(k).or_default();
            if a.rx.is_none() {
                a.rx = nscrtv_optical_dbm(*v);
            }
        }
    }
    for e in tx_powers {
        if let (Some(k), crate::snmp::SnmpData::Integer(v)) = (key_of(&e.oid), &e.value) {
            let a = accum.entry(k).or_default();
            if a.tx.is_none() {
                a.tx = nscrtv_optical_dbm(*v);
            }
        }
    }
    for e in distances {
        if let (Some(k), crate::snmp::SnmpData::Integer(v)) = (key_of(&e.oid), &e.value) {
            // onuTestDistance: UNITS "Meter"
            if (0..=200_000).contains(v) {
                accum.entry(k).or_default().dist = Some(*v as u32);
            }
        }
    }

    if accum.is_empty() {
        tracing::warn!(
            olt = %olt_id,
            "NSCRTV tables answered but no row index decoded as a valid \
             GponDeviceIndex — firmware may use a non-standard index packing"
        );
    }

    accum
        .into_iter()
        .map(|((pon_port, onu), a)| {
            let status = a.status.unwrap_or(OntStatus::Unknown);
            let refined = match (&status, a.rx) {
                (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                _ => status,
            };
            OntData {
                serial_number: a.serial.unwrap_or_else(|| format!("{}-{}:{}", vendor, pon_port, onu)),
                pon_port,
                ont_index: onu,
                status: refined,
                last_down_cause: None, uptime_seconds: None,
                rx_power_dbm: a.rx, tx_power_dbm: a.tx,
                distance_meters: a.dist,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            }
        })
        .collect()
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

        let onts = self.collect_onts_snmp().await?;

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_nscrtv_index_packed_bytes() {
        // GponDeviceIndex TC: device<<24 | slot<<16 | pon<<8 | onu
        // device 1, slot 2, pon 3, onu 17 = 0x01020311
        assert_eq!(decode_nscrtv_index(0x0102_0311), Some(("2/3".into(), 17)));
        // Pizza-box (no slot concept): slot byte 0 is legal
        assert_eq!(decode_nscrtv_index(0x0100_0105), Some(("0/1".into(), 5)));
        // "OnuNUM of 0 … indicates that the ONU logical ID is meaningless"
        assert_eq!(decode_nscrtv_index(0x0102_0300), None);
        // device 0 / pon 0 are invalid per the TC description
        assert_eq!(decode_nscrtv_index(0x0002_0311), None);
        assert_eq!(decode_nscrtv_index(0x0102_0011), None);
        // Larger than 32 bits is not a GponDeviceIndex
        assert_eq!(decode_nscrtv_index(0x1_0000_0000), None);
    }

    #[test]
    fn test_nscrtv_optical_centi_dbm() {
        // UNITS "centi-dBm": -1932 → -19.32 dBm
        assert_eq!(nscrtv_optical_dbm(-1932), Some(-19.32));
        assert_eq!(nscrtv_optical_dbm(250), Some(2.5));
        // Firmware sentinels (not in the standard MIB) → None via window
        assert_eq!(nscrtv_optical_dbm(32767), None);   // 327.67
        assert_eq!(nscrtv_optical_dbm(65535), None);
        assert_eq!(nscrtv_optical_dbm(2147483647), None);
        assert_eq!(nscrtv_optical_dbm(-32768), None);  // -327.68
    }

    #[test]
    fn test_parse_vsol_dbm_string_zabbix_format() {
        // V1600G returns "-19.32(dBm)" (Zabbix template RTRIMs "(dBm)")
        assert_eq!(parse_vsol_dbm_string("-19.32(dBm)"), Some(-19.32));
        assert_eq!(parse_vsol_dbm_string("-19.32 dBm"), Some(-19.32));
        assert_eq!(parse_vsol_dbm_string("2.51"), Some(2.51));
        assert_eq!(parse_vsol_dbm_string("not-available"), None);
        assert_eq!(parse_vsol_dbm_string(""), None);
        // Garbled firmware values must not pass the window
        assert_eq!(parse_vsol_dbm_string("6553.5(dBm)"), None);
    }

    #[test]
    fn test_assemble_nscrtv_correlates_by_decoded_key() {
        fn v(oid: &str, val: crate::snmp::SnmpData) -> crate::snmp::SnmpValue {
            crate::snmp::SnmpValue { oid: oid.into(), value: val, timestamp: chrono::Utc::now() }
        }
        use crate::snmp::SnmpData::{Integer, OctetString};

        // ONU device 1, slot 2, pon 3, onu 17 → packed 16909073 (0x01020311)
        let statuses = [v("1.3.6.1.4.1.17409.2.8.4.1.1.7.16909073", Integer(1))];
        let serials = [v("1.3.6.1.4.1.17409.2.8.4.1.1.3.16909073", OctetString("GPON001122AA".into()))];
        // Optical table appends card/port indexes after the packed index
        let rx = [v("1.3.6.1.4.1.17409.2.8.4.4.1.4.16909073.65535.65535", Integer(-1932))];
        let onts = assemble_nscrtv("test", "vsol", &statuses, &serials, &rx, &[], &[]);

        assert_eq!(onts.len(), 1);
        assert_eq!(onts[0].pon_port, "2/3");
        assert_eq!(onts[0].ont_index, 17);
        assert_eq!(onts[0].serial_number, "GPON001122AA");
        assert_eq!(onts[0].status, OntStatus::Online);
        assert_eq!(onts[0].rx_power_dbm, Some(-19.32));
    }
}
