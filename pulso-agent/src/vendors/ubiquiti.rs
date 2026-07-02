// SPDX-License-Identifier: Apache-2.0
// Ubiquiti Collector (UFiber OLT, via UISP REST API)
// Does NOT use SNMP for ONT data — uses the UISP API.

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::SnmpPoller;
use super::*;

pub struct UbiquitiCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
    http_client: reqwest::Client,
}

impl UbiquitiCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        let http_client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(15))
            .danger_accept_invalid_certs(true) // UISP often has self-signed certs
            .build()?;
        Ok(Self {
            olt_id: format!("ubiquiti-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
            http_client,
        })
    }

    async fn collect_via_uisp(&self) -> anyhow::Result<Vec<OntData>> {
        let rest = self.config.rest_api.as_ref()
            .ok_or_else(|| anyhow::anyhow!("UISP REST API not configured"))?;

        let url = format!("{}/nms/api/v2.1/devices?role=onu", rest.base_url.trim_end_matches('/'));
        let mut req = self.http_client.get(&url);

        if let Some(key) = &rest.api_key {
            req = req.header("x-auth-token", key);
        }

        let resp = req.send().await?;
        if !resp.status().is_success() {
            anyhow::bail!("UISP API returned {}", resp.status());
        }

        let devices: Vec<serde_json::Value> = resp.json().await?;
        let mut onts = Vec::new();

        if !devices.is_empty() {
            // Finding 9: the UISP device list does not carry a verified
            // OLT-port attribute (the previous code stuffed the ONU's *name*
            // into pon_port, making every ONT its own fake "port"). Until a
            // real UISP capture confirms a port field, report the port as
            // unknown rather than fabricate one.
            tracing::warn!(
                olt = %self.olt_id,
                onts = devices.len(),
                "UISP API does not expose a verified PON-port field — \
                 pon_port set to \"{}\" for all ONTs; port-level fault \
                 localization is degraded on Ubiquiti",
                UNKNOWN_PON_PORT
            );
        }

        for dev in &devices {
            let serial = dev["identification"]["serialNumber"]
                .as_str().unwrap_or("unknown").to_string();
            let is_online = dev["overview"]["status"]
                .as_str().map(|s| s == "active").unwrap_or(false);
            // UISP reports dBm directly, but gate through the plausibility
            // window: API glitches / sentinel exports (0-filled or huge
            // values) must become None, not poison signal history.
            let rx_power = dev["overview"]["signal"]
                .as_f64()
                .and_then(super::snmp_helper::plausible_dbm);
            let tx_power = dev["overview"]["signalLocal"]
                .as_f64()
                .or_else(|| dev["overview"]["txPower"].as_f64())
                .and_then(super::snmp_helper::plausible_dbm);
            let distance = dev["overview"]["distance"]
                .as_f64()
                .map(|d| d as u32);
            let uptime = dev["overview"]["uptime"]
                .as_u64();

            let status = if is_online {
                match rx_power {
                    Some(rx) if rx < -27.0 => OntStatus::LowSignal,
                    _ => OntStatus::Online,
                }
            } else {
                OntStatus::Offline
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port: UNKNOWN_PON_PORT.to_string(),
                ont_index: onts.len() as u32,
                status,
                last_down_cause: None, uptime_seconds: uptime,
                rx_power_dbm: rx_power, tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: Some("ubiquiti".into()),
                equipment_id: dev["identification"]["model"].as_str().map(String::from),
                firmware_version: dev["identification"]["firmwareVersion"].as_str().map(String::from),
                in_octets: None, out_octets: None,
                fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                eth_speed_mbps: None,
                extended: None,
            });
        }
        Ok(onts)
    }
}

#[async_trait]
impl OltCollector for UbiquitiCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "ubiquiti" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        // UISP API failures propagate — an API error reported as "0 ONTs"
        // reads as a mass outage downstream (silent-zero, audit theme 2).
        let onts = if self.config.rest_api.is_some() {
            self.collect_via_uisp().await?
        } else {
            tracing::warn!(
                olt = %self.olt_id,
                "Ubiquiti collector has no UISP REST API configured — ONT \
                 data cannot be collected via SNMP on UFiber; configure \
                 rest_api for this OLT"
            );
            Vec::new()
        };

        let (model, uptime) = if let Some(snmp) = &self.snmp {
            let descr = snmp.get(crate::snmp::oids::SYS_DESCR).await.ok();
            let uptime_val = snmp.get(crate::snmp::oids::SYS_UPTIME).await.ok();
            (
                super::huawei::extract_string_pub(&descr),
                super::huawei::extract_timeticks_pub(&uptime_val),
            )
        } else {
            (String::new(), 0)
        };

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
            vendor: "ubiquiti".into(),
            model, firmware: String::new(), serial: String::new(),
            uptime_seconds: uptime,
            timestamp: chrono::Utc::now(),
            cpu_percent: None, memory_percent: None,
            temperature_celsius: None, power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: Vec::new(), onts,
        })
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        if let Some(ref rest) = self.config.rest_api {
            let url = format!("{}/nms/api/v2.1/nms", rest.base_url.trim_end_matches('/'));
            let resp = self.http_client.get(&url).send().await?;
            Ok(resp.status().is_success())
        } else if let Some(snmp) = &self.snmp {
            snmp.get(crate::snmp::oids::SYS_DESCR).await.map(|_| true).map_err(Into::into)
        } else {
            Ok(false)
        }
    }
}
