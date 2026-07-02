// SPDX-License-Identifier: Apache-2.0
// Huawei OLT Collector (MA5800-X2/X7, MA5600T, MA5608T)
//
// Data collection methods:
//   1. SNMP: ONT table, optical power, status, distance (enterprise .2011)
//   2. SSH CLI: "display ont info", "display ont optical-info" (for data not in SNMP)
//   3. NETCONF: Available on MA5800 with iMaster NCE (optional)
//
// Huawei GPON MIB tree: 1.3.6.1.4.1.2011.6.128
//   ONT registration: .1.1.2.43.1
//   ONT status: .1.1.2.46.1
//   ONT optical DDM: .1.1.2.51.1
//
// CLI (currently DISABLED as a transport — see collect_onts_cli):
//   Real command forms (verified against ntc-templates captures + netmiko
//   huawei_smartax driver):
//     display ont info <F> <S> <P> all      (enable/config mode, 3 args)
//     display ont info <port> all           (inside interface gpon F/S only)
//     display ont info summary <F/S/P>      (config mode, slash token)
//     display ont optical-info <port> all   (inside interface gpon)
//   Pagination off: `scroll` (SmartAX; NOT `screen-length 0 temporary`);
//   also `undo smart` + `infoswitch cli OFF`. More prompt text:
//   "---- More ( Press 'Q' to break ) ----".
//
// No vendor partnership or license required.
// SNMP community must be configured on the OLT by the ISP.
// Huawei enables SNMP by default on most firmware versions.
// Firmware R019+ may require: sysman server source snmp any-interface

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::{SnmpPoller, oids};
use super::*;

pub struct HuaweiCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
}

impl HuaweiCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;

        Ok(Self {
            olt_id: format!("huawei-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
        })
    }

    /// Collect ONT data via SNMP (preferred, more efficient)
    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        let mut onts = Vec::new();

        // Walk ONT registration table
        let serials = snmp.walk_table(oids::huawei::ONT_SERIAL).await?;
        let statuses = snmp.walk_table(oids::huawei::ONT_STATUS).await?;
        let rx_powers = snmp.walk_table(oids::huawei::ONT_RX_POWER).await?;
        let tx_powers = snmp.walk_table(oids::huawei::ONT_TX_POWER).await?;
        let distances = snmp.walk_table(oids::huawei::ONT_DISTANCE).await?;

        // Correlate by OID index: <gponPortIfIndex>.<ontId>, matched on
        // component boundaries (a plain ends_with would attribute ONT 8.1's
        // metrics to 48.1/108.1 — audit finding 14).
        for serial_entry in &serials {
            let index = super::snmp_helper::extract_oid_suffix(&serial_entry.oid, 2);
            let (slot, port, ont_id) = parse_huawei_index(&index);

            let serial = match &serial_entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };

            // Find matching status, rx_power, tx_power, distance
            let status = super::snmp_helper::find_by_suffix(&statuses, &index)
                .map(|v| match v { crate::snmp::SnmpData::Integer(1) => OntStatus::Online, _ => OntStatus::Offline })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = super::snmp_helper::find_by_suffix(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => huawei_optical_dbm(*i),
                    _ => None,
                });

            let tx_power = super::snmp_helper::find_by_suffix(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => huawei_optical_dbm(*i),
                    _ => None,
                });

            let distance = super::snmp_helper::find_by_suffix(&distances, &index)
                .and_then(|v| match v {
                    // 2147483647 is Huawei's "invalid" sentinel here too
                    crate::snmp::SnmpData::Integer(i) if (0..=200_000).contains(i) => Some(*i as u32),
                    _ => None,
                });

            // Determine refined status based on signal level
            let refined_status = match (&status, rx_power) {
                (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                _ => status,
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port: format!("0/{}/{}", slot, port),
                ont_index: ont_id,
                status: refined_status,
                last_down_cause: None, // Requires CLI for detailed cause
                uptime_seconds: None,
                rx_power_dbm: rx_power,
                tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: None,
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }

        Ok(onts)
    }

    /// CLI collection is DISABLED pending validation against real firmware.
    ///
    /// The previous implementation was written against invented output: it
    /// ran `display ont info 0 all` via SSH exec at the login prompt — a form
    /// that is only valid *inside* `interface gpon` config mode (globally the
    /// command needs three F/S/P arguments: `display ont info 0 1 0 all`) —
    /// did not enter enable/config mode, did not disable pagination
    /// (SmartAX uses `scroll`, and emits `---- More ( Press 'Q' to break ) ----`),
    /// and its regex matched a column layout that does not exist on
    /// MA5600T/MA5800 firmware. Net effect: it silently parsed 0 ONTs.
    ///
    /// The *parser* for the real `display ont info <F> <S> <P> all` table is
    /// implemented below (`parse_display_ont_info_all`) and tested against
    /// byte-exact captures from networktocode/ntc-templates. The interactive
    /// session driver (login banner, `enable` → `undo smart` →
    /// `infoswitch cli OFF` → `scroll`, PON-port enumeration via
    /// `display board 0`, More-prompt handling) is NOT yet validated against
    /// a real device, so this transport refuses to run rather than risk
    /// reporting a healthy OLT as empty.
    #[allow(dead_code)] // deliberately unreachable from collect() until validated
    async fn collect_onts_cli(&self) -> anyhow::Result<Vec<OntData>> {
        let _ssh_cfg = self.config.ssh.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SSH not configured"))?;
        Err(anyhow::anyhow!(
            "Huawei CLI collection not yet validated against real \
             MA5600T/MA5800 firmware; use the SNMP transport (primary). \
             The CLI table parser is ready (see parse_display_ont_info_all) \
             but the interactive session driver needs a real-device \
             transcript before it can be trusted not to return 0 ONTs."
        ))
    }

    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None),
        };
        let cpu = snmp.get(oids::huawei_sys::CPU_RATE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let temp = snmp.get(oids::huawei_sys::BOARD_TEMP).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        (cpu, temp)
    }
}

/// Parse the REAL `display ont info <F> <S> <P> all` first table.
///
/// Format grounded in byte-exact captures from networktocode/ntc-templates
/// (tests/huawei_smartax/display_ont_info_0_1_2/*.raw):
///
///   -----------------------------------------------------------------------------
///   F/S/P   ONT         SN         Control     Run      Config   Match    Protect
///           ID                     flag        state    state    state    side
///   -----------------------------------------------------------------------------
///   0/ 1/0    0  1234567890ABCDEF  active      online   normal   match    no
///   0/ 1/0    1  1234567890ABCDEF  active      offline  initial  mismatch no
///
/// Notes that matter for the regex:
///   - Huawei pads the slot with a space: "0/ 1/0" — `/\s*` between fields
///   - Control flag: active|deactive|configuring; Run state: online|offline
///   - the second (Description) table and the "In port …, the total …"
///     trailer must not produce rows
#[allow(dead_code)] // exercised by tests; production wiring waits on CLI validation
pub(crate) fn parse_display_ont_info_all(output: &str) -> Vec<OntData> {
    let re = regex::Regex::new(
        r"^\s*(\d+)/\s*(\d+)/\s*(\d+)\s+(\d+)\s+([0-9A-Za-z]{8,20})\s+(\S+)\s+(online|offline)\b",
    )
    .unwrap();

    let mut onts = Vec::new();
    for line in output.lines() {
        if let Some(caps) = re.captures(line) {
            let frame: u32 = caps[1].parse().unwrap_or(0);
            let slot: u32 = caps[2].parse().unwrap_or(0);
            let port: u32 = caps[3].parse().unwrap_or(0);
            let ont_id: u32 = caps[4].parse().unwrap_or(0);
            let serial = caps[5].to_string();
            let status = match &caps[7] {
                "online" => OntStatus::Online,
                "offline" => OntStatus::Offline,
                _ => OntStatus::Unknown,
            };

            onts.push(OntData {
                serial_number: serial,
                // REAL F/S/P from the table row — never a placeholder
                // (the old parser hardcoded pon_port "cli", so fault
                // grouping lumped every ONT of the OLT into one fake port)
                pon_port: format!("{}/{}/{}", frame, slot, port),
                ont_index: ont_id,
                status,
                last_down_cause: None,
                uptime_seconds: None,
                rx_power_dbm: None,
                tx_power_dbm: None,
                distance_meters: None,
                vendor_id: None,
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
    }
    onts
}

#[async_trait]
impl OltCollector for HuaweiCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "huawei" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for Huawei OLT"))?;

        // Get system info
        let sys_descr = snmp.get(oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(oids::SYS_UPTIME).await.ok();

        // Collect ONTs (the main payload). SNMP errors — including partial
        // walks — must propagate: an SNMP failure presented as "0 ONTs" reads
        // as a mass outage downstream (audit findings 8/13).
        let onts = match self.collect_onts_snmp().await {
            Ok(o) => {
                if o.is_empty() {
                    tracing::warn!(
                        olt = %self.olt_id,
                        "Huawei SNMP walk succeeded but returned 0 ONTs — \
                         suspicious for a production OLT; check that the ONT \
                         tables (2011.6.128.1.1.2) are exposed to this community"
                    );
                }
                o
            }
            Err(e) => return Err(e),
        };

        // Build PON port summary from ONT data
        let mut pon_ports = std::collections::HashMap::new();
        for ont in &onts {
            let entry = pon_ports.entry(ont.pon_port.clone()).or_insert(PonPortData {
                port_id: ont.pon_port.clone(),
                oper_status: "up".into(),
                onts_registered: 0,
                onts_online: 0,
                onts_offline: 0,
                bw_down_bps: 0,
                bw_up_bps: 0,
                utilization_percent: 0.0,
            });
            entry.onts_registered += 1;
            match ont.status {
                OntStatus::Online | OntStatus::LowSignal => entry.onts_online += 1,
                _ => entry.onts_offline += 1,
            }
        }

        // Collect system health from Huawei-specific OIDs
        let (cpu, temp) = self.collect_system_health().await;

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "huawei".into(),
            model: extract_string(&sys_descr),
            firmware: String::new(),
            serial: String::new(),
            uptime_seconds: extract_timeticks(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: cpu,
            memory_percent: None,
            temperature_celsius: temp,
            power_supply_status: None,
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

// Helper functions (some pub for reuse by other vendor modules)
pub fn extract_string_pub(val: &Option<crate::snmp::SnmpValue>) -> String {
    extract_string(val)
}

pub fn extract_timeticks_pub(val: &Option<crate::snmp::SnmpValue>) -> u64 {
    extract_timeticks(val)
}

/// Huawei GPON DDM raw value → dBm. Units are 0.01 dBm; 2147483647
/// (0x7FFFFFFF) means "no reading" (ONT offline / DDM unsupported).
///
/// Verified against real MA5680T walks:
///   data/external/snmp-dumps/huawei/github_pr9023_ma5680t_ddm_excerpt.txt
///   (hwGponOntOpticalDdmRxPower .51.1.4: -1640 = -16.40 dBm) and
///   data/external/snmp-dumps/huawei/librenms_forum6801_ma5680t_ddm_rxpower.txt
///   (offline ONT row: INTEGER: 2147483647).
pub(crate) fn huawei_optical_dbm(raw: i64) -> Option<f64> {
    super::snmp_helper::plausible_dbm(raw as f64 / 100.0)
}

/// Decode frame/slot/port + ONT id from the hwGponDeviceOnt* table index
/// (<gponPortIfIndex>.<ontId>).
///
/// GPON port ifIndex bit-packing, verified against a real MA5600T V800R018
/// walk (data/external/snmp-dumps/huawei/librenms_smartax.snmprec: ifDescr
/// "…GPON_UNI" rows at 4194304000 + slot*8192 + port*256) and the MA5680T
/// excerpt above (4194312192 = frame 0 slot 1 port 0; 4194312448 = 0/1/1):
///   ifIndex = 0xFA000000 | slot << 13 | port << 8
pub(crate) fn parse_huawei_index(index: &str) -> (u32, u32, u32) {
    let parts: Vec<u32> = index.split('.').filter_map(|s| s.parse().ok()).collect();
    if parts.len() >= 2 {
        let encoded = parts[0];
        let ont_id = parts[1];
        let slot = (encoded >> 13) & 0x1F;
        let port = (encoded >> 8) & 0x1F;
        (slot, port, ont_id)
    } else {
        (0, 0, 0)
    }
}

fn extract_string(val: &Option<crate::snmp::SnmpValue>) -> String {
    val.as_ref().and_then(|v| match &v.value {
        crate::snmp::SnmpData::OctetString(s) => Some(s.clone()),
        _ => None,
    }).unwrap_or_default()
}

fn extract_timeticks(val: &Option<crate::snmp::SnmpValue>) -> u64 {
    val.as_ref().and_then(|v| match &v.value {
        crate::snmp::SnmpData::TimeTicks(t) => Some(*t as u64 / 100), // centiseconds to seconds
        _ => None,
    }).unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_huawei_index_real_ifindex_packing() {
        // Real MA5680T walk (data/external/snmp-dumps/huawei/
        // github_pr9023_ma5680t_ddm_excerpt.txt): 4194312192 = frame 0
        // slot 1 port 0; 4194312448 = 0/1/1.
        assert_eq!(parse_huawei_index("4194312192.0"), (1, 0, 0));
        assert_eq!(parse_huawei_index("4194312448.7"), (1, 1, 7));
        // Base of the GPON_UNI range in librenms_smartax.snmprec:
        // 4194304000 = slot 0 port 0
        assert_eq!(parse_huawei_index("4194304000.12"), (0, 0, 12));
        // Malformed index → zeros, never a panic
        assert_eq!(parse_huawei_index("garbage"), (0, 0, 0));
    }

    #[test]
    fn test_huawei_optical_scaling_real_values() {
        // Real MA5680T DDM rows (github_pr9023_ma5680t_ddm_excerpt.txt):
        // hwGponOntOpticalDdmRxPower -1640 = -16.40 dBm
        assert_eq!(huawei_optical_dbm(-1640), Some(-16.40));
        assert_eq!(huawei_optical_dbm(-2923), Some(-29.23));
    }

    #[test]
    fn test_huawei_sentinel_2147483647_is_none() {
        // Offline ONT in librenms_forum6801_ma5680t_ddm_rxpower.txt reports
        // INTEGER: 2147483647 — must become None, not 21474836.47 dBm.
        assert_eq!(huawei_optical_dbm(2147483647), None);
        assert_eq!(huawei_optical_dbm(i32::MIN as i64), None);
    }

    /// Byte-exact fixture from networktocode/ntc-templates
    /// tests/huawei_smartax/display_ont_info_0_1_2/ (both firmware variants).
    const DISPLAY_ONT_INFO_FSP: &str = "\
  -----------------------------------------------------------------------------
  F/S/P   ONT         SN         Control     Run      Config   Match    Protect
          ID                     flag        state    state    state    side
  -----------------------------------------------------------------------------
  0/ 1/0    0  1234567890ABCDEF  active      online   normal   match    no
  0/ 1/0    1  2234567890ABCDEF  active      online   normal   match    no
  0/ 2/0   16  3234567890ABCDEF  configuring offline  initial  mismatch yes
  -----------------------------------------------------------------------------
  F/S/P       ONT  Description
              ID
  -----------------------------------------------------------------------------
  0/ 1/0       0   Generic_description
  0/ 1/0       1   Generic_description
  -----------------------------------------------------------------------------
  In port 0/ 2/0, the total number of ONTs is: 16, online: 8, offline: 8
  -----------------------------------------------------------------------------
";

    #[test]
    fn test_parse_display_ont_info_all_real_capture() {
        let onts = parse_display_ont_info_all(DISPLAY_ONT_INFO_FSP);
        assert_eq!(onts.len(), 3, "description table / trailer must not add rows");

        assert_eq!(onts[0].serial_number, "1234567890ABCDEF");
        // Real F/S/P decoded despite Huawei's "0/ 1/0" slot padding —
        // NOT the old hardcoded pon_port = "cli"
        assert_eq!(onts[0].pon_port, "0/1/0");
        assert_eq!(onts[0].ont_index, 0);
        assert_eq!(onts[0].status, OntStatus::Online);

        assert_eq!(onts[2].pon_port, "0/2/0");
        assert_eq!(onts[2].ont_index, 16);
        assert_eq!(onts[2].status, OntStatus::Offline);
    }

    #[test]
    fn test_parse_display_ont_info_all_ignores_invented_format() {
        // The format the OLD parser expected ("ONT-ID State SN") does not
        // exist on real firmware; feeding it must yield zero rows rather
        // than garbage.
        let invented = "\
ONT-ID  State  SN            Password    Type
0       online HWTC-12345678 12345678    245H
1       offline HWTC-87654321            245H
";
        assert!(parse_display_ont_info_all(invented).is_empty());
    }

    #[tokio::test]
    async fn test_cli_transport_is_disabled_with_explicit_error() {
        let cfg = OltConfig {
            name: "test".into(),
            vendor: "huawei".into(),
            ip: "192.0.2.1".into(),
            model: String::new(),
            snmp: None,
            ssh: Some(crate::config::SshConfig {
                enabled: true,
                username: "admin".into(),
                password: Some("pw".into()),
                key_file: None,
                port: 22,
            }),
            netconf: None,
            rest_api: None,
            grpc: None,
        };
        let collector = HuaweiCollector::new(&cfg).unwrap();
        let err = collector.collect_onts_cli().await
            .err()
            .expect("CLI path must be a hard error, never silent 0 ONTs");
        assert!(err.to_string().contains("not yet validated against real"));
        assert!(err.to_string().contains("SNMP"));
    }
}
