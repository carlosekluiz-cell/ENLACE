// SPDX-License-Identifier: Apache-2.0
// BDCOM OLT Collector (GP3600, P3310, P3608 series; FS.com IES5100 rebrands)
//
// Enterprise OID: 1.3.6.1.4.1.3320
// GPON branch: .10, EPON legacy branch: .101
//
// Ground truth: real P3608B (EPON) + GP3600-08B (GPON) lab captures with
// CLI cross-checks — data/external/snmp-dumps/bdcom/
// nagwiki_bdcom_p3608b_gp3600-08b_excerpts.txt (NAG wiki ".xPON. BDCOM. SNMP",
// https://nag.wiki/pages/viewpage.action?pageId=38764878):
//
//   - ONU status tables are indexed <ponPortIfIndex>.<onuId>
//     (3320.101.11.4.1.5.76.17 → EPON port ifIndex 76, ONU 17)
//   - Per-ONU DDM tables are indexed by the ONU's OWN ifIndex
//     (3320.101.10.5.1.5.113 → ONU interface ifIndex 113)
//   - PON port names come from IF-MIB ifDescr: "EPON0/1", "GPON0/8";
//     ONU interfaces are "EPON0/1:17", "GPON0/8:5"
//   - Optical scaling is 0.1 dBm, CLI-cross-checked:
//     SNMP -226 ↔ CLI RxPow -22.7…-22.6 dBm; SNMP 17 ↔ CLI TxPow 1.7 dBm;
//     OLT-side SNMP -340 ↔ CLI -34.0 dBm
//   - EPON status enumeration: real capture shows deregistered ONUs = 2 and
//     the single CLI-confirmed online ONU ("auto-configured", link up) = 5.

use async_trait::async_trait;
use std::collections::HashMap;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, SnmpValue, SnmpData, oids};
use super::*;
use super::snmp_helper::plausible_dbm;

/// BDCOM optical raw value → dBm (0.1 dBm units, CLI-cross-checked above).
/// 0x7FFF (32767) and other sentinels land outside the plausibility window.
pub(crate) fn bdcom_optical_dbm(raw: i64) -> Option<f64> {
    plausible_dbm(raw as f64 / 10.0)
}

/// Parse "GPON0/8:5" / "epon0/1:17" → (pon_port "0/8", onu_id 5).
pub(crate) fn parse_bdcom_onu_descr(descr: &str) -> Option<(String, u32)> {
    let upper = descr.to_ascii_uppercase();
    let rest = upper.strip_prefix("GPON").or_else(|| upper.strip_prefix("EPON"))?;
    let (port, onu) = rest.split_once(':')?;
    if !port.contains('/') {
        return None;
    }
    Some((port.to_string(), onu.parse().ok()?))
}

/// Parse "GPON0/1" (no colon) → pon port name "0/1".
fn parse_bdcom_port_descr(descr: &str) -> Option<String> {
    let upper = descr.to_ascii_uppercase();
    let rest = upper.strip_prefix("GPON").or_else(|| upper.strip_prefix("EPON"))?;
    if rest.contains('/') && !rest.contains(':') {
        Some(rest.to_string())
    } else {
        None
    }
}

/// EPON ONU status (3320.101.11.4.1.5): 5 = registered/online (CLI-confirmed
/// "auto-configured" + link up), 2 = deregistered. Other values unobserved on
/// real gear → Unknown, never guessed.
fn epon_status(v: i64) -> OntStatus {
    match v {
        5 => OntStatus::Online,
        2 => OntStatus::Offline,
        _ => OntStatus::Unknown,
    }
}

/// GPON ONU status (3320.10.3.3.1.4): 3 = online, 0 = offline per community
/// usage (ixnfo.com / LibreNMS); NOT yet cross-checked against a live GP3600 —
/// unobserved values map to Unknown rather than being guessed offline.
fn gpon_status(v: i64) -> OntStatus {
    match v {
        3 => OntStatus::Online,
        0 => OntStatus::Offline,
        _ => OntStatus::Unknown,
    }
}

pub struct BdcomCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl BdcomCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("bdcom-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // ifDescr is the source of PON-port names AND ONU-interface ifIndexes;
        // errors propagate (a partial ifTable would mis-attribute ONUs).
        let if_descrs = snmp.walk_table(oids::IF_DESCR).await?;
        let descr_by_ifindex: HashMap<u64, String> = if_descrs.iter()
            .filter_map(|e| {
                let idx: u64 = super::snmp_helper::extract_oid_suffix(&e.oid, 1).parse().ok()?;
                match &e.value {
                    SnmpData::OctetString(s) => Some((idx, s.clone())),
                    _ => None,
                }
            })
            .collect();
        // (pon_port, onu_id) → ONU interface descr/ifIndex, for DDM lookup
        let onu_iface_by_key: HashMap<(String, u32), (u64, String)> = descr_by_ifindex.iter()
            .filter_map(|(idx, d)| parse_bdcom_onu_descr(d).map(|k| (k, (*idx, d.clone()))))
            .collect();

        // GPON branch first
        let statuses = snmp.walk_table(oids::bdcom::ONT_STATUS).await?;
        if !statuses.is_empty() {
            let rx_powers = snmp.walk_table(oids::bdcom::ONT_RX_POWER).await?;
            let tx_powers = snmp.walk_table(oids::bdcom::ONT_TX_POWER).await?;
            return Ok(self.assemble(
                &statuses, &rx_powers, &tx_powers,
                &descr_by_ifindex, &onu_iface_by_key,
                gpon_status, "GPON",
            ));
        }

        // EPON legacy branch
        let statuses = snmp.walk_table(oids::bdcom::EPON_ONT_STATUS).await?;
        if statuses.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "BDCOM OLT exposed neither GPON (.10.3.3) nor EPON (.101.11.4) \
                 ONU status tables — no ONT data collected"
            );
            return Ok(Vec::new());
        }
        let rx_powers = snmp.walk_table(oids::bdcom::EPON_ONT_RX).await?;
        let tx_powers = snmp.walk_table(oids::bdcom::EPON_ONT_TX).await?;
        Ok(self.assemble(
            &statuses, &rx_powers, &tx_powers,
            &descr_by_ifindex, &onu_iface_by_key,
            epon_status, "EPON",
        ))
    }

    #[allow(clippy::too_many_arguments)]
    fn assemble(
        &self,
        statuses: &[SnmpValue],
        rx_powers: &[SnmpValue],
        tx_powers: &[SnmpValue],
        descr_by_ifindex: &HashMap<u64, String>,
        onu_iface_by_key: &HashMap<(String, u32), (u64, String)>,
        status_map: fn(i64) -> OntStatus,
        family: &str,
    ) -> Vec<OntData> {
        let mut unknown_port_warned = false;
        let mut onts = Vec::new();

        for status_entry in statuses {
            // Status tables are indexed <ponPortIfIndex>.<onuId> (real capture:
            // 3320.101.11.4.1.5.76.17). Two components, boundary-safe.
            let index = super::snmp_helper::extract_oid_suffix(&status_entry.oid, 2);
            let mut parts = index.split('.');
            let pon_ifindex: Option<u64> = parts.next().and_then(|s| s.parse().ok());
            let onu_id: Option<u32> = parts.next().and_then(|s| s.parse().ok());
            let (pon_ifindex, onu_id) = match (pon_ifindex, onu_id) {
                (Some(p), Some(o)) => (p, o),
                _ => continue,
            };

            // Real PON port name from ifDescr; never a fabricated sequence.
            let pon_port = descr_by_ifindex
                .get(&pon_ifindex)
                .and_then(|d| parse_bdcom_port_descr(d))
                .unwrap_or_else(|| {
                    if !unknown_port_warned {
                        tracing::warn!(
                            olt = %self.olt_id,
                            pon_ifindex,
                            "BDCOM {} port ifIndex not found in ifDescr — \
                             pon_port set to \"{}\"; fault localization \
                             degraded for these ONUs",
                            family, UNKNOWN_PON_PORT
                        );
                        unknown_port_warned = true;
                    }
                    UNKNOWN_PON_PORT.to_string()
                });

            let status = match &status_entry.value {
                SnmpData::Integer(v) => status_map(*v),
                _ => OntStatus::Unknown,
            };

            // ONU interface (for serial-ish identity and DDM lookup)
            let onu_iface = onu_iface_by_key.get(&(pon_port.clone(), onu_id));
            let serial = onu_iface
                .map(|(_, d)| d.clone())
                .unwrap_or_else(|| format!("bdcom-{}:{}", pon_port, onu_id));

            // DDM: per real captures the per-ONU DDM tables are indexed by the
            // ONU's own ifIndex (3320.101.10.5.1.5.113); some GPON firmware
            // instead indexes <ponIfIndex>.<onuId> — try both, boundary-safe.
            let two_comp = format!("{}.{}", pon_ifindex, onu_id);
            let find_power = |table: &[SnmpValue]| -> Option<f64> {
                let by_onu_if = onu_iface.and_then(|(onu_ifindex, _)| {
                    super::snmp_helper::find_by_suffix(table, &onu_ifindex.to_string())
                        .and_then(|v| match v {
                            SnmpData::Integer(i) => Some(*i),
                            _ => None,
                        })
                });
                let raw = by_onu_if.or_else(|| {
                    super::snmp_helper::find_by_suffix(table, &two_comp)
                        .and_then(|v| match v {
                            SnmpData::Integer(i) => Some(*i),
                            _ => None,
                        })
                })?;
                bdcom_optical_dbm(raw)
            };
            let rx_power = find_power(rx_powers);
            let tx_power = find_power(tx_powers);

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
                distance_meters: None,
                vendor_id: None, equipment_id: None, firmware_version: None,
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        onts
    }

    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None, None),
        };
        let cpu = snmp.get(oids::bdcom::CPU_1MIN).await.ok()
            .and_then(|v| match v.value {
                SnmpData::Gauge32(g) => Some(g as f32),
                SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        let mem = snmp.get(oids::bdcom::MEM_UTIL).await.ok()
            .and_then(|v| match v.value {
                SnmpData::Gauge32(g) => Some(g as f32),
                SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        let temp = snmp.get(oids::bdcom::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                SnmpData::Integer(i) => Some(i as f32),
                _ => None,
            });
        (cpu, mem, temp)
    }
}

#[async_trait]
impl OltCollector for BdcomCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "bdcom" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for BDCOM OLT"))?;

        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

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
            vendor: "bdcom".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
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
    fn test_bdcom_optical_scaling_cli_crosschecked() {
        // Real capture (nagwiki_bdcom_p3608b_gp3600-08b_excerpts.txt):
        // SNMP 3320.101.10.5.1.5.113 = -226 ↔ CLI RxPow -22.7 dBm
        assert_eq!(bdcom_optical_dbm(-226), Some(-22.6));
        // SNMP 3320.101.10.5.1.6.113 = 17 ↔ CLI TxPow 1.7 dBm
        assert_eq!(bdcom_optical_dbm(17), Some(1.7));
        // OLT-side: SNMP 3320.101.108.1.3.113 = -340 ↔ CLI -34.0 dBm
        assert_eq!(bdcom_optical_dbm(-340), Some(-34.0));
    }

    #[test]
    fn test_bdcom_sentinels_are_none() {
        assert_eq!(bdcom_optical_dbm(32767), None);  // 0x7FFF → 3276.7
        assert_eq!(bdcom_optical_dbm(-32768), None); // i16::MIN → -3276.8
        assert_eq!(bdcom_optical_dbm(65535), None);
    }

    #[test]
    fn test_parse_bdcom_onu_descr_real_names() {
        // Verbatim interface names from the real captures
        assert_eq!(parse_bdcom_onu_descr("EPON0/1:17"), Some(("0/1".into(), 17)));
        assert_eq!(parse_bdcom_onu_descr("GPON0/8:5"), Some(("0/8".into(), 5)));
        assert_eq!(parse_bdcom_onu_descr("epon0/1:17"), Some(("0/1".into(), 17)));
        // PON ports and unrelated interfaces are not ONUs
        assert_eq!(parse_bdcom_onu_descr("GPON0/1"), None);
        assert_eq!(parse_bdcom_onu_descr("GigaEthernet0/5"), None);
    }

    #[test]
    fn test_parse_bdcom_port_descr() {
        assert_eq!(parse_bdcom_port_descr("EPON0/1"), Some("0/1".into()));
        assert_eq!(parse_bdcom_port_descr("GPON0/8"), Some("0/8".into()));
        assert_eq!(parse_bdcom_port_descr("GPON0/8:5"), None); // ONU, not port
        assert_eq!(parse_bdcom_port_descr("VLAN170"), None);
    }

    #[test]
    fn test_epon_status_real_values() {
        // Real capture: online ONU (CLI "auto-configured", link up) = 5;
        // deregistered ONUs = 2
        assert_eq!(epon_status(5), OntStatus::Online);
        assert_eq!(epon_status(2), OntStatus::Offline);
        // Unobserved values must not be guessed
        assert_eq!(epon_status(1), OntStatus::Unknown);
        assert_eq!(epon_status(3), OntStatus::Unknown);
    }
}
