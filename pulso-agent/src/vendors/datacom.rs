// SPDX-License-Identifier: Apache-2.0
// Datacom OLT Collector (DmOS — DM4610, DM4611, DM4615, DM4616, DM4618)
//
// Enterprise OID: 1.3.6.1.4.1.3709
// MIB: GPON-ONU-IF-MIB, root gponOnuIfMIB = 1.3.6.1.4.1.3709.3.6.2,
// onuIfTable = …3.6.2.1, entry …3.6.2.1.1 — VERIFIED against the official
// "DmOS MIB Reference 204.4381.02" (DmOS 9.4.0, section 29) and Datacom's
// own Zabbix templates (github.com/datacom-teracom/dmos-zabbix-template).
//
// Verified column semantics:
//   .3  onuifDescr       — String, e.g. "gpon-1/1/1-onu-1" (also carries
//                          "-gem-N" / "-ethernet-uni-N" rows — must filter)
//   .7  onuifOperStatus  — up(1), down(2), testing(3), unknown(4),
//                          dormant(5), notPresent(6), lowerLayerDown(7)
//   .21 onuIfOnuPowerTx  — STRING in dBm (e.g. "-21.32"), no scaling
//   .22 onuIfOnuPowerRx  — STRING in dBm
//   .23 onuIfAlias
// Index: the table's own flat onuifIndex — PON port and ONU id come from
// parsing onuifDescr (Datacom's Zabbix discovery filter:
// ^gpon-[0-9]/[0-9]/[0-9]{1,}-onu-[0-9]{1,}$).
//
// The previous implementation read .21/.22 as INTEGER centi-dBm (they are
// strings → it always got None) and fabricated pon_port from walk order.
//
// ONU serial number is NOT exposed by the DmOS polling MIBs (only in trap
// payloads, DATACOM-GPON-TRAPS-MIB 3709.3.5.200) — inventory identity here
// is alias/descr; real SNs need the NETCONF transport.

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;
use super::snmp_helper::plausible_dbm;

/// Parse a DmOS ONU interface description "gpon-1/1/1-onu-1" →
/// (pon_port "1/1/1", onu_id 1). GEM ports ("…-onu-1-gem-1") and UNI rows
/// ("…-onu-1-ethernet-uni-1") in the same table are rejected.
pub(crate) fn parse_dmos_onu_descr(descr: &str) -> Option<(String, u32)> {
    let rest = descr.trim().strip_prefix("gpon-")?;
    let (port, onu) = rest.split_once("-onu-")?;
    // port must be chassis/slot/port, all numeric
    let port_ok = {
        let parts: Vec<&str> = port.split('/').collect();
        parts.len() == 3 && parts.iter().all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()))
    };
    if !port_ok {
        return None;
    }
    // onu part must be purely numeric — anything else is a gem/uni sub-row
    if onu.is_empty() || !onu.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    Some((port.to_string(), onu.parse().ok()?))
}

/// DmOS onuifOperStatus (verbatim MIB enum, see module header).
fn dmos_oper_status(v: i64) -> OntStatus {
    match v {
        1 => OntStatus::Online,          // up
        2 | 6 | 7 => OntStatus::Offline, // down / notPresent / lowerLayerDown
        _ => OntStatus::Unknown,         // testing / unknown / dormant
    }
}

/// DmOS optical power strings are plain dBm ("-21.32"); tolerate a "dBm"
/// suffix defensively. Sentinel behavior on down ONUs is undocumented —
/// the plausibility window guards whatever the firmware emits.
pub(crate) fn parse_dmos_power(s: &str) -> Option<f64> {
    let cleaned = s.trim().trim_end_matches("dBm").trim();
    plausible_dbm(cleaned.parse().ok()?)
}

pub struct DatacomCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
    /// One-time telemetry-coverage log guard (see collect_onts_snmp).
    coverage_logged: std::sync::atomic::AtomicBool,
}

impl DatacomCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("datacom-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
            coverage_logged: std::sync::atomic::AtomicBool::new(false),
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // Telemetry coverage — once per OLT, not per cycle.
        if !self.coverage_logged.swap(true, std::sync::atomic::Ordering::Relaxed) {
            tracing::debug!(
                olt = %self.olt_id,
                "Datacom SNMP coverage: optical rx/tx + per-ONU octet counters \
                 collected; DDM temperature/voltage/bias and FEC/BIP are NOT \
                 collected — the verified DmOS onuIfTable columns (MIB Reference \
                 204.4381.02, see module header) expose only power strings, and \
                 the real DM4610 capture (data/external/snmp-dumps/datacom/) \
                 contains no per-ONU DDM table"
            );
        }

        // GPON-ONU-IF-MIB onuIfTable. Walk errors (incl. partial walks)
        // propagate — never silently degrade to "OLT with zero ONTs".
        let descrs = snmp.walk_table(oids::datacom::ONT_DESCR).await?;
        if descrs.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "Datacom OLT returned no rows from GPON-ONU-IF-MIB onuIfTable \
                 (3709.3.6.2.1) — no ONT data collected; table requires DmOS \
                 firmware with GPON support"
            );
            return Ok(Vec::new());
        }
        let oper_statuses = snmp.walk_table(oids::datacom::ONT_OPER_STATUS).await?;
        let rx_powers = snmp.walk_table(oids::datacom::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(oids::datacom::ONT_TX_POWER).await?;
        let aliases = snmp.walk_table(oids::datacom::ONT_ALIAS).await?;
        let in_octets = snmp.walk_table(oids::datacom::ONT_IN_OCTETS).await?;
        let out_octets = snmp.walk_table(oids::datacom::ONT_OUT_OCTETS).await?;

        let mut onts = Vec::new();
        for entry in descrs.iter() {
            let index = super::snmp_helper::extract_oid_suffix(&entry.oid, 1);

            // Only true ONU rows ("gpon-C/S/P-onu-N"); gem/uni sub-rows and
            // other interface types in the same table are skipped.
            let descr = match &entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };
            let (pon_port, onu_id) = match parse_dmos_onu_descr(&descr) {
                Some(v) => v,
                None => continue,
            };

            // Use alias (customer label) when set, else the interface name.
            // DmOS does not expose the ONU serial via SNMP (see header).
            let serial = super::snmp_helper::find_by_suffix(&aliases, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) if !s.is_empty() => Some(s.clone()),
                    _ => None,
                })
                .unwrap_or_else(|| descr.clone());

            let status = super::snmp_helper::find_by_suffix(&oper_statuses, &index)
                .map(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => dmos_oper_status(*i),
                    _ => OntStatus::Unknown,
                })
                .unwrap_or(OntStatus::Unknown);

            // onuIfOnuPowerRx/Tx are STRINGS in dBm (verified — see header)
            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) => parse_dmos_power(s),
                    // Defensive: some firmware may expose integers; treat as
                    // centi-dBm behind the plausibility gate
                    crate::snmp::SnmpData::Integer(i) => plausible_dbm(*i as f64 / 100.0),
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::OctetString(s) => parse_dmos_power(s),
                    crate::snmp::SnmpData::Integer(i) => plausible_dbm(*i as f64 / 100.0),
                    _ => None,
                });

            let in_oct = super::snmp_helper::find_by_suffix(&in_octets, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Counter64(c) => Some(*c),
                    crate::snmp::SnmpData::Counter32(c) => Some(*c as u64),
                    crate::snmp::SnmpData::Integer(i) => Some(*i as u64),
                    _ => None,
                });

            let out_oct = super::snmp_helper::find_by_suffix(&out_octets, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Counter64(c) => Some(*c),
                    crate::snmp::SnmpData::Counter32(c) => Some(*c as u64),
                    crate::snmp::SnmpData::Integer(i) => Some(*i as u64),
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
                distance_meters: None, // not exposed in onuIfTable
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: in_oct, out_octets: out_oct, eth_speed_mbps: None, extended: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
            });
        }

        if onts.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                rows = descrs.len(),
                "Datacom onuIfTable answered but no row matched the \
                 \"gpon-C/S/P-onu-N\" description format — firmware naming \
                 may differ; no ONT data collected"
            );
        }
        Ok(onts)
    }

    async fn collect_interfaces_ifmib(&self) -> anyhow::Result<Vec<UplinkPortData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        let if_descrs = snmp.walk_table(oids::IF_DESCR).await?;
        let if_statuses = snmp.walk_table(oids::IF_OPER_STATUS).await?;
        let if_in = snmp.walk_table(oids::IF_HC_IN_OCTETS).await?;
        let if_out = snmp.walk_table(oids::IF_HC_OUT_OCTETS).await?;

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
                port_id: name, oper_status: oper_status.into(), speed_mbps: 1000,
                in_octets, out_octets, in_errors: 0, out_errors: 0,
            });
        }
        Ok(uplinks)
    }
}

#[async_trait]
impl OltCollector for DatacomCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "datacom" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for Datacom OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        let onts = self.collect_onts_snmp().await?;
        let uplinks = self.collect_interfaces_ifmib().await?;

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
            vendor: "datacom".into(),
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
    fn test_parse_dmos_onu_descr_real_format() {
        // Format per the DmOS MIB Reference + Datacom's own Zabbix discovery
        // filter ^gpon-[0-9]/[0-9]/[0-9]{1,}-onu-[0-9]{1,}$
        assert_eq!(parse_dmos_onu_descr("gpon-1/1/1-onu-1"), Some(("1/1/1".into(), 1)));
        assert_eq!(parse_dmos_onu_descr("gpon-1/1/8-onu-127"), Some(("1/1/8".into(), 127)));
        // GEM and UNI sub-rows in the same table must be filtered out
        assert_eq!(parse_dmos_onu_descr("gpon-1/1/1-onu-1-gem-1"), None);
        assert_eq!(parse_dmos_onu_descr("gpon-1/1/1-onu-1-ethernet-uni-1"), None);
        // PON port rows and other interfaces are not ONUs
        assert_eq!(parse_dmos_onu_descr("gpon-1/1/1"), None);
        assert_eq!(parse_dmos_onu_descr("ethernet-1/1/1"), None);
    }

    #[test]
    fn test_parse_dmos_power_string_dbm() {
        // onuIfOnuPowerRx/Tx are strings in dBm, no scaling (MIB Reference;
        // Zabbix templates apply multiplier 1)
        assert_eq!(parse_dmos_power("-21.32"), Some(-21.32));
        assert_eq!(parse_dmos_power(" 2.5 "), Some(2.5));
        assert_eq!(parse_dmos_power("-21.32 dBm"), Some(-21.32));
        // Undocumented down-ONU sentinels must not pass
        assert_eq!(parse_dmos_power(""), None);
        assert_eq!(parse_dmos_power("N/A"), None);
        assert_eq!(parse_dmos_power("-65535"), None);
    }

    #[test]
    fn test_dmos_oper_status_enum() {
        // up(1), down(2), testing(3), unknown(4), dormant(5), notPresent(6),
        // lowerLayerDown(7) — verbatim from the DmOS MIB Reference
        assert_eq!(dmos_oper_status(1), OntStatus::Online);
        assert_eq!(dmos_oper_status(2), OntStatus::Offline);
        assert_eq!(dmos_oper_status(6), OntStatus::Offline);
        assert_eq!(dmos_oper_status(7), OntStatus::Offline);
        assert_eq!(dmos_oper_status(3), OntStatus::Unknown);
        assert_eq!(dmos_oper_status(4), OntStatus::Unknown);
        assert_eq!(dmos_oper_status(5), OntStatus::Unknown);
    }
}
