// SPDX-License-Identifier: Apache-2.0
// Network device auto-discovery via SNMP scan.
// Scans management VLAN and identifies OLTs, MikroTik routers, switches.

use serde::{Serialize, Deserialize};
use std::net::Ipv4Addr;
use tokio::sync::Semaphore;
use tracing::{debug, info, warn};
use crate::config::{AgentConfig, SnmpConfig};
use crate::snmp::SnmpPoller;

const MAX_CONCURRENT_PROBES: usize = 50;

#[derive(Debug, Serialize, Deserialize)]
pub struct DiscoveredDevice {
    pub ip: String,
    pub vendor: String,
    pub model: String,
    pub sys_descr: String,
    pub sys_object_id: String,
    pub device_type: String,
}

pub async fn scan_network(config: &AgentConfig) -> anyhow::Result<Vec<DiscoveredDevice>> {
    let scan_range = config.scan_range.as_deref().unwrap_or("10.0.0.0/24");
    let communities: Vec<String> = config.scan_communities.clone()
        .unwrap_or_else(|| vec!["public".into(), "private".into()]);

    let ips = parse_cidr(scan_range)?;
    info!(range = scan_range, ips = ips.len(), "Starting network discovery");

    let semaphore = std::sync::Arc::new(Semaphore::new(MAX_CONCURRENT_PROBES));
    let mut handles = Vec::new();

    for ip in ips {
        let sem = semaphore.clone();
        let communities = communities.clone();
        handles.push(tokio::spawn(async move {
            let _permit = sem.acquire().await.unwrap();
            probe_device(&ip.to_string(), &communities).await
        }));
    }

    let mut devices = Vec::new();
    for handle in handles {
        match handle.await {
            Ok(Some(device)) => {
                info!(ip = %device.ip, vendor = %device.vendor, "Discovered device");
                devices.push(device);
            }
            Ok(None) => {}
            Err(e) => {
                debug!(error = %e, "Probe task failed");
            }
        }
    }

    info!(count = devices.len(), "Discovery complete");
    Ok(devices)
}

async fn probe_device(ip: &str, communities: &[String]) -> Option<DiscoveredDevice> {
    for community in communities {
        let snmp_cfg = SnmpConfig {
            version: "v2c".into(),
            community: Some(community.clone()),
            v3: None,
            port: 161,
            timeout_ms: 2000, // Short timeout for scanning
            max_repetitions: 10,
        };

        let poller = match SnmpPoller::new(ip, &snmp_cfg) {
            Ok(p) => p,
            Err(_) => continue,
        };

        match poller.detect_vendor().await {
            Ok((vendor, sys_oid, sys_descr)) => {
                let device_type = classify_device(&vendor, &sys_descr);
                return Some(DiscoveredDevice {
                    ip: ip.to_string(),
                    vendor,
                    model: extract_model(&sys_descr),
                    sys_descr,
                    sys_object_id: sys_oid,
                    device_type,
                });
            }
            Err(_) => continue,
        }
    }
    None
}

fn classify_device(vendor: &str, descr: &str) -> String {
    let descr_lower = descr.to_lowercase();
    if descr_lower.contains("olt") || descr_lower.contains("gpon") || descr_lower.contains("ma5") {
        "olt".into()
    } else if descr_lower.contains("mikrotik") || descr_lower.contains("routeros") {
        "router".into()
    } else if descr_lower.contains("switch") {
        "switch".into()
    } else if descr_lower.contains("router") {
        "router".into()
    } else if vendor == "huawei" || vendor == "zte" || vendor == "fiberhome" {
        "olt".into() // Most likely an OLT from these vendors
    } else {
        "unknown".into()
    }
}

fn extract_model(descr: &str) -> String {
    // Take first meaningful word from sysDescr as model
    descr.split_whitespace()
        .find(|w| w.len() > 2 && !w.eq_ignore_ascii_case("software") && !w.eq_ignore_ascii_case("version"))
        .unwrap_or("unknown")
        .to_string()
}

/// Parse CIDR notation to list of IPs (e.g., "10.0.0.0/24" → 254 IPs)
fn parse_cidr(cidr: &str) -> anyhow::Result<Vec<Ipv4Addr>> {
    let parts: Vec<&str> = cidr.split('/').collect();
    if parts.len() != 2 {
        anyhow::bail!("Invalid CIDR: {}", cidr);
    }

    let base: Ipv4Addr = parts[0].parse()
        .map_err(|e| anyhow::anyhow!("Invalid IP in CIDR: {}", e))?;
    let prefix_len: u32 = parts[1].parse()
        .map_err(|e| anyhow::anyhow!("Invalid prefix length: {}", e))?;

    if prefix_len > 32 {
        anyhow::bail!("Prefix length must be <= 32");
    }

    let base_u32 = u32::from(base);
    let host_bits = 32 - prefix_len;
    let num_hosts = 1u32 << host_bits;

    let mut ips = Vec::new();
    // Skip network address (first) and broadcast (last)
    for i in 1..num_hosts.saturating_sub(1) {
        ips.push(Ipv4Addr::from(base_u32 | i));
    }

    Ok(ips)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_cidr() {
        let ips = parse_cidr("10.0.0.0/24").unwrap();
        assert_eq!(ips.len(), 254);
        assert_eq!(ips[0], Ipv4Addr::new(10, 0, 0, 1));
        assert_eq!(ips[253], Ipv4Addr::new(10, 0, 0, 254));
    }

    #[test]
    fn test_parse_cidr_small() {
        let ips = parse_cidr("192.168.1.0/30").unwrap();
        assert_eq!(ips.len(), 2); // .1 and .2
    }

    #[test]
    fn test_classify_device() {
        assert_eq!(classify_device("huawei", "Huawei MA5800-X7"), "olt");
        assert_eq!(classify_device("generic", "MikroTik RouterOS 7.10"), "router");
        assert_eq!(classify_device("generic", "Cisco Switch"), "switch");
    }
}
