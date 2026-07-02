// SPDX-License-Identifier: Apache-2.0
// Nokia OLT Collector (ISAM 7360, 7342, G-240 series)
//
// Enterprise OID: 1.3.6.1.4.1.637 (asam = 637.61.1 — sysObjectID of a real
// 7360 R6.5, data/external/snmp-dumps/nokia/librenms_nokia-isam.snmprec)
// MIBs: ASAM-SYSTEM-MIB (CPU, memory), APON-MIB (ONT tables — customer-gated,
// see snmp::oids::nokia for verification status)
//
// HONEST LIMITATIONS on Nokia ISAM via SNMP v2c:
//   - Per-ONT optical power is NOT available from publicly documented MIBs.
//     Every public integration (LibreNMS/Observium/Zabbix) stops at
//     board-level SFP DDM (SFP-MIB {asam 56}, DisplayString "4.94 dBm" /
//     "not-available" — visible in the real 7360 walk). Per-ONT levels need
//     TL1 ("show equipment ont optics"), CLI, or the gated APON-MIB with a
//     live capture to confirm index/scaling. rx/tx are therefore None.
//   - The ONT ifIndex bit-packing is not publicly documented (Nokia's own
//     ITF-MIB-EXT mapping tables 637.61.1.6.13/.14 are the sanctioned
//     translation path) — pon_port is reported as "unknown" rather than
//     fabricated from walk order.
//
// Collects via SNMP v2c:
//   - ONT serial, status, software version (APON-MIB — unverified OIDs;
//     empty results are reported loudly, never as a healthy zero)
//   - OLT CPU, memory (ASAM-SYSTEM-MIB)

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

        // APON-MIB ONT tables. Walk errors (incl. partial walks) propagate.
        let serials = snmp.walk_table(oids::nokia::ONT_SERIAL).await?;
        let statuses = snmp.walk_table(oids::nokia::ONT_STATUS).await?;
        let sw_versions = snmp.walk_table(oids::nokia::ONT_SW_VER).await?;

        let primary = if !serials.is_empty() { &serials } else { &statuses };
        if primary.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "Nokia ISAM returned no rows from the APON ONT tables \
                 (637.61.1.35.10) — these OIDs are NOT verified against real \
                 GPON ISAM firmware (the available real capture is an FTTN \
                 unit without them); no ONT data collected"
            );
            return Ok(Vec::new());
        }

        tracing::info!(
            olt = %self.olt_id,
            "Nokia ISAM: collecting ONT status only — per-ONT optical power \
             is not available via the public SNMP MIBs (board-level SFP DDM \
             only); rx/tx will be None for all ONTs"
        );

        let mut onts = Vec::new();
        let mut unknown_port_warned = false;
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

            // Finding 9: the previous code fabricated pon_port from walk
            // order ("pon-{idx/64}") — pure fiction that made fault grouping
            // page on random ONT subsets. Until the ISAM ONT index encoding
            // is verified against a real GPON ISAM walk, report unknown.
            if !unknown_port_warned {
                tracing::warn!(
                    olt = %self.olt_id,
                    "Nokia ISAM ONT index → PON port decoding not yet \
                     verified — pon_port set to \"{}\"; port-level fault \
                     localization degraded on Nokia",
                    UNKNOWN_PON_PORT
                );
                unknown_port_warned = true;
            }

            onts.push(OntData {
                serial_number: serial,
                pon_port: UNKNOWN_PON_PORT.to_string(),
                ont_index: idx as u32,
                status,
                last_down_cause: None, uptime_seconds: None,
                // Per-ONT optical is NOT collected on Nokia ISAM: the public
                // SNMP fixtures expose only board-level SFP DDM as strings
                // ("4.94 dBm" / "not-available" — see data/external/
                // snmp-dumps/nokia/librenms_nokia-isam.snmprec, table
                // 637.61.1.56.5.1.6/.7); per-ONT levels need TL1/CLI or the
                // proprietary GPON MIBs. Explicitly None, never fabricated.
                rx_power_dbm: None, tx_power_dbm: None,
                distance_meters: None,
                vendor_id: Some("nokia".into()),
                equipment_id: None,
                firmware_version: firmware,
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
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

        let onts = self.collect_onts_snmp().await?;
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
