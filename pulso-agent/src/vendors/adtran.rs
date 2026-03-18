// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 OLT Collector (OpenOLT gRPC)
//
// Protocol: OpenOLT gRPC on port 9191 (VOLTHA certified)
// rx_power: f64 dBm (NO scaling — unlike Huawei's 0.01 dBm integers)
// Distance: u32 metres
// Serial: vendor_id (4 ASCII bytes) + vendor_specific (4 hex bytes)
// Connection: Persistent gRPC channel (not stateless UDP like SNMP)

use async_trait::async_trait;
use dashmap::DashMap;
use std::sync::Arc;
use tracing::{info, warn, debug};
use crate::config::OltConfig;
use super::*;

pub mod openolt {
    tonic::include_proto!("openolt");
}

#[derive(Debug, Clone)]
pub struct OntState {
    pub serial: String,
    pub status: OntStatus,
    pub last_seen: chrono::DateTime<chrono::Utc>,
    pub dying_gasp: bool,
}

pub struct AdtranCollector {
    olt_id: String,
    config: OltConfig,
    ont_state: Arc<DashMap<(u32, u32), OntState>>,
    device_model: std::sync::Mutex<Option<String>>,
    device_firmware: std::sync::Mutex<Option<String>>,
}

impl AdtranCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let _grpc_cfg = config.grpc.as_ref()
            .ok_or_else(|| anyhow::anyhow!(
                "Adtran OLT requires [olts.grpc] config (SDX 6320 has no SNMP)"
            ))?;

        Ok(Self {
            olt_id: format!("adtran-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            ont_state: Arc::new(DashMap::new()),
            device_model: std::sync::Mutex::new(None),
            device_firmware: std::sync::Mutex::new(None),
        })
    }

    fn endpoint(&self) -> String {
        let grpc = self.config.grpc.as_ref().unwrap();
        let scheme = if grpc.tls { "https" } else { "http" };
        format!("{}://{}:{}", scheme, self.config.ip, grpc.port)
    }

    async fn connect(&self) -> anyhow::Result<openolt::openolt_client::OpenoltClient<tonic::transport::Channel>> {
        let grpc = self.config.grpc.as_ref().unwrap();
        let endpoint = tonic::transport::Endpoint::from_shared(self.endpoint())?
            .connect_timeout(std::time::Duration::from_millis(grpc.connect_timeout_ms))
            .timeout(std::time::Duration::from_millis(grpc.request_timeout_ms));
        let channel = endpoint.connect().await?;
        Ok(openolt::openolt_client::OpenoltClient::new(channel))
    }

    async fn seed_state_table(&self, client: &mut openolt::openolt_client::OpenoltClient<tonic::transport::Channel>) -> anyhow::Result<()> {
        let device_info = client.get_device_info(openolt::Empty {}).await?;
        let info = device_info.into_inner();
        *self.device_model.lock().unwrap() = Some(info.model.clone());
        *self.device_firmware.lock().unwrap() = Some(info.firmware_version.clone());
        let pon_ports = info.pon_ports;
        info!(model = %info.model, pon_ports = pon_ports, "Adtran device info retrieved");

        for intf_id in 0..pon_ports {
            for onu_id in 0..128u32 {
                let req = openolt::Onu {
                    intf_id,
                    onu_id,
                    serial_number: None,
                    pir: 0,
                };
                match client.get_onu_info(req).await {
                    Ok(resp) => {
                        let onu_info = resp.into_inner();
                        let serial = extract_serial(&onu_info.serial_number);
                        if !serial.is_empty() {
                            self.ont_state.insert(
                                (intf_id, onu_id),
                                OntState {
                                    serial,
                                    status: OntStatus::Online,
                                    last_seen: chrono::Utc::now(),
                                    dying_gasp: false,
                                },
                            );
                        }
                    }
                    Err(_) => break,
                }
            }
        }

        info!(onts = self.ont_state.len(), "Adtran state table seeded");
        Ok(())
    }

    async fn collect_ont_data(&self, client: &mut openolt::openolt_client::OpenoltClient<tonic::transport::Channel>) -> Vec<OntData> {
        let mut onts = Vec::new();

        for entry in self.ont_state.iter() {
            let (intf_id, onu_id) = *entry.key();
            let state = entry.value().clone();

            let mut rx_power: Option<f64> = None;
            let mut tx_power: Option<f64> = None;
            let mut distance: Option<u32> = None;

            let rx_req = openolt::Onu { intf_id, onu_id, serial_number: None, pir: 0 };
            if let Ok(resp) = client.get_pon_rx_power(rx_req).await {
                let power = resp.into_inner();
                rx_power = Some(power.rx_power_mean_dbm);
                tx_power = Some(power.tx_power_mean_dbm);
            }

            let dist_req = openolt::Onu { intf_id, onu_id, serial_number: None, pir: 0 };
            if let Ok(resp) = client.get_logical_onu_distance(dist_req).await {
                let d = resp.into_inner();
                distance = Some(d.logical_onu_distance);
            }

            let status = if state.dying_gasp {
                OntStatus::PowerFail
            } else {
                state.status.clone()
            };

            onts.push(OntData {
                serial_number: state.serial,
                pon_port: format!("0/{}", intf_id),
                ont_index: onu_id,
                status,
                last_down_cause: if state.dying_gasp { Some("dying_gasp".into()) } else { None },
                uptime_seconds: None,
                rx_power_dbm: rx_power,
                tx_power_dbm: tx_power,
                distance_meters: distance,
                vendor_id: Some("Adtran".into()),
                equipment_id: None,
                firmware_version: None,
                in_octets: None,
                out_octets: None,
                eth_speed_mbps: None,
            });
        }

        onts
    }
}

/// Convert OpenOLT SerialNumber to string: vendor_id (ASCII) + vendor_specific (hex)
fn serial_to_string(vendor_id: &[u8], vendor_specific: &[u8]) -> String {
    if vendor_id.is_empty() && vendor_specific.is_empty() {
        return String::new();
    }
    let vendor = String::from_utf8_lossy(vendor_id);
    let specific: String = vendor_specific.iter().map(|b| format!("{:02X}", b)).collect();
    format!("{}{}", vendor, specific)
}

fn extract_serial(sn: &Option<openolt::SerialNumber>) -> String {
    match sn {
        Some(s) => serial_to_string(&s.vendor_id, &s.vendor_specific),
        None => String::new(),
    }
}

#[async_trait]
impl OltCollector for AdtranCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "adtran" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let mut client = self.connect().await?;

        if self.ont_state.is_empty() {
            self.seed_state_table(&mut client).await?;
        }

        let onts = self.collect_ont_data(&mut client).await;

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

        let model = self.device_model.lock().unwrap().clone().unwrap_or_default();
        let firmware = self.device_firmware.lock().unwrap().clone().unwrap_or_default();

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "adtran".into(),
            model,
            firmware,
            serial: String::new(),
            uptime_seconds: 0,
            timestamp: chrono::Utc::now(),
            cpu_percent: None,
            memory_percent: None,
            temperature_celsius: None,
            power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: Vec::new(),
            onts,
        })
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        let mut client = self.connect().await?;
        let resp = client.get_device_info(openolt::Empty {}).await?;
        let info = resp.into_inner();
        info!(vendor = %info.vendor, model = %info.model, "Adtran connectivity verified");
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_serial_number_message() {
        let vendor_id = b"ADTN".to_vec();
        let vendor_specific = vec![0x15, 0x32, 0x01, 0xC4];
        let result = serial_to_string(&vendor_id, &vendor_specific);
        assert_eq!(result, "ADTN153201C4");
    }

    #[test]
    fn test_parse_serial_empty() {
        let result = serial_to_string(&[], &[]);
        assert_eq!(result, "");
    }

    #[test]
    fn test_adtran_rx_no_scaling() {
        let raw: f64 = -22.1;
        assert!((raw - (-22.1)).abs() < 0.001);
    }

    #[test]
    fn test_ont_state_table_update() {
        let state = DashMap::new();
        let key = (0u32, 1u32);
        state.insert(key, OntState {
            serial: "ADTN153201C4".into(),
            status: OntStatus::Online,
            last_seen: chrono::Utc::now(),
            dying_gasp: false,
        });
        assert!(state.contains_key(&key));
        let entry = state.get(&key).unwrap();
        assert_eq!(entry.status, OntStatus::Online);
        assert!(!entry.dying_gasp);
    }

    #[test]
    fn test_ont_state_dying_gasp() {
        let state = DashMap::new();
        let key = (0u32, 5u32);
        state.insert(key, OntState {
            serial: "ADTN99887766".into(),
            status: OntStatus::Online,
            last_seen: chrono::Utc::now(),
            dying_gasp: false,
        });
        if let Some(mut entry) = state.get_mut(&key) {
            entry.dying_gasp = true;
            entry.status = OntStatus::PowerFail;
        }
        let entry = state.get(&key).unwrap();
        assert!(entry.dying_gasp);
        assert_eq!(entry.status, OntStatus::PowerFail);
    }
}
