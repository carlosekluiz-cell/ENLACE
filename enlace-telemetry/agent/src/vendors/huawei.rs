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
// CLI commands used (all read-only):
//   display ont info all
//   display ont optical-info {slot}/{port} all
//   display interface gpon {slot}/{port}
//   display ont autofind all
//   display board 0
//   display sysman service state
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

        // Correlate by OID index (the last numbers in the OID identify the ONT)
        for serial_entry in &serials {
            let index = extract_oid_index(&serial_entry.oid);
            let (slot, port, ont_id) = parse_huawei_index(&index);

            let serial = match &serial_entry.value {
                crate::snmp::SnmpData::OctetString(s) => s.clone(),
                _ => continue,
            };

            // Find matching status, rx_power, tx_power, distance
            let status = find_by_index(&statuses, &index)
                .map(|v| match v { crate::snmp::SnmpData::Integer(1) => OntStatus::Online, _ => OntStatus::Offline })
                .unwrap_or(OntStatus::Unknown);

            let rx_power = find_by_index(&rx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 100.0), // Huawei: 0.01 dBm units
                    _ => None,
                });

            let tx_power = find_by_index(&tx_powers, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as f64 / 100.0),
                    _ => None,
                });

            let distance = find_by_index(&distances, &index)
                .and_then(|v| match v {
                    crate::snmp::SnmpData::Integer(i) => Some(*i as u32),
                    _ => None,
                });

            // Determine refined status based on signal level
            let refined_status = match (&status, rx_power) {
                (OntStatus::Online, Some(rx)) if rx < -28.0 => OntStatus::LowSignal,
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
                eth_speed_mbps: None,
                extended: None,
            });
        }

        Ok(onts)
    }

    /// Collect ONT data via SSH CLI (fallback, slower but more detailed)
    async fn collect_onts_cli(&self) -> anyhow::Result<Vec<OntData>> {
        let ssh_cfg = self.config.ssh.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SSH not configured"))?;

        if !ssh_cfg.enabled {
            return Ok(Vec::new());
        }

        // Connect via SSH and execute read-only commands
        // Huawei VRP CLI commands:
        //   display ont info 0/1/0 all       → ONT registration, status, serial
        //   display ont optical-info 0/1/0 all → RX/TX power, temperature
        //   display interface gpon 0/1/0      → PON port statistics

        // Parse the text output using regex patterns
        // Huawei output format (example):
        //   ONT-ID  State  SN            Password    Type
        //   0       online HWTC-12345678 12345678    245H
        //   1       offline HWTC-87654321            245H

        let handler = SshHandler;
        let config = std::sync::Arc::new(russh::client::Config::default());
        let addr = format!("{}:{}", self.config.ip, ssh_cfg.port);

        let mut session = russh::client::connect(config, &addr, handler).await
            .map_err(|e| anyhow::anyhow!("SSH connect failed: {}", e))?;

        // Authenticate
        let authenticated = if let Some(ref password) = ssh_cfg.password {
            session.authenticate_password(&ssh_cfg.username, password).await
                .map_err(|e| anyhow::anyhow!("SSH auth failed: {}", e))?
        } else {
            return Err(anyhow::anyhow!("SSH key auth not yet implemented"));
        };

        if !authenticated {
            return Err(anyhow::anyhow!("SSH authentication failed"));
        }

        let mut channel = session.channel_open_session().await
            .map_err(|e| anyhow::anyhow!("SSH channel open failed: {}", e))?;

        // Execute command and collect output
        channel.exec(true, "display ont info 0 all").await
            .map_err(|e| anyhow::anyhow!("SSH exec failed: {}", e))?;

        let mut output = String::new();
        loop {
            match tokio::time::timeout(
                std::time::Duration::from_secs(30),
                channel.wait(),
            ).await {
                Ok(Some(russh::ChannelMsg::Data { data })) => {
                    output.push_str(&String::from_utf8_lossy(&data));
                }
                Ok(Some(russh::ChannelMsg::Eof)) | Ok(None) | Err(_) => break,
                Ok(Some(_)) => continue,
            }
        }

        let onts = parse_huawei_ont_output(&output);
        Ok(onts)
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

/// Minimal SSH client handler — accepts all host keys (ISP internal network)
struct SshHandler;

#[async_trait]
impl russh::client::Handler for SshHandler {
    type Error = anyhow::Error;

    async fn check_server_key(
        &mut self,
        _server_public_key: &russh::keys::key::PublicKey,
    ) -> Result<bool, Self::Error> {
        Ok(true) // Accept all host keys (internal ISP network)
    }
}

/// Parse Huawei "display ont info" CLI output
fn parse_huawei_ont_output(output: &str) -> Vec<OntData> {
    let re = regex::Regex::new(
        r"^\s*(\d+)\s+(online|offline)\s+(\S+)"
    ).unwrap();

    let mut onts = Vec::new();
    for line in output.lines() {
        if let Some(caps) = re.captures(line) {
            let ont_id: u32 = caps[1].parse().unwrap_or(0);
            let status_str = &caps[2];
            let serial = caps[3].to_string();

            let status = match status_str {
                "online" => OntStatus::Online,
                "offline" => OntStatus::Offline,
                _ => OntStatus::Unknown,
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port: "cli".into(),
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
        let sys_name = snmp.get(oids::SYS_NAME).await.ok();

        // Collect interface data (standard IF-MIB)
        let if_descrs = snmp.walk_table(oids::IF_DESCR).await.unwrap_or_default();
        let if_statuses = snmp.walk_table(oids::IF_OPER_STATUS).await.unwrap_or_default();

        // Collect ONTs (the main payload)
        let onts = match self.collect_onts_snmp().await {
            Ok(o) if !o.is_empty() => o,
            _ => self.collect_onts_cli().await.unwrap_or_default(),
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

fn extract_oid_index(oid: &str) -> String {
    // Extract the trailing index numbers from an OID
    // e.g., "1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3.4294967808.1" → "4294967808.1"
    oid.rsplit('.').take(2).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join(".")
}

fn parse_huawei_index(index: &str) -> (u32, u32, u32) {
    // Huawei encodes slot/port/ont-id in the SNMP index
    // The frame/slot/port is encoded in the high bits of the first index number
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

fn find_by_index<'a>(entries: &'a [crate::snmp::SnmpValue], index: &str) -> Option<&'a crate::snmp::SnmpData> {
    entries.iter().find(|e| e.oid.ends_with(index)).map(|e| &e.value)
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
