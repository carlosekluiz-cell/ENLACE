// SPDX-License-Identifier: Apache-2.0
// TR-069 / GenieACS integration for the Pulso Agent.
//
// Polls GenieACS REST API (port 7557) for CPE device data:
// - Device inventory (serial, manufacturer, model, firmware, last inform)
// - WiFi diagnostics (SSID, channel, connected stations, signal)
// - WAN status (IP, uptime, bytes transferred)
// - Signal strength (for DSL/fiber CPEs that expose it)
//
// Reference: TR-069 Amendment 6 (CPE WAN Management Protocol)
// GenieACS API: https://github.com/genieacs/genieacs/wiki/API-Reference

use serde::{Deserialize, Serialize};
use tracing::{debug, warn, info};
use crate::config::Tr069Config;

/// Health classification for a CPE device.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum CpeHealth {
    /// Everything normal.
    Green,
    /// Minor issues (stale inform, weak WiFi signal).
    Yellow,
    /// Critical (offline, no inform in >24h, very weak signal).
    Red,
}

/// A CPE device discovered from GenieACS.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CpeDevice {
    /// GenieACS device ID (usually serial or encoded identifier).
    pub device_id: String,
    /// Manufacturer name (e.g., "TP-Link", "Huawei", "Intelbras").
    pub manufacturer: Option<String>,
    /// Model name/number.
    pub model: Option<String>,
    /// Serial number.
    pub serial_number: Option<String>,
    /// Firmware version.
    pub firmware_version: Option<String>,
    /// WAN IP address.
    pub wan_ip: Option<String>,
    /// Last inform timestamp (ISO 8601).
    pub last_inform: Option<String>,
    /// Uptime in seconds.
    pub uptime_seconds: Option<u64>,
    /// Number of connected WiFi stations.
    pub wifi_stations: Option<u32>,
    /// WiFi channel in use.
    pub wifi_channel: Option<u32>,
    /// WiFi SSID.
    pub wifi_ssid: Option<String>,
    /// Total bytes received on WAN.
    pub wan_bytes_received: Option<u64>,
    /// Total bytes sent on WAN.
    pub wan_bytes_sent: Option<u64>,
    /// Health classification based on last inform age and signal.
    pub health: CpeHealth,
}

/// GenieACS REST API response for a device query.
#[derive(Debug, Deserialize)]
struct GenieDevice {
    #[serde(rename = "_id")]
    id: String,
    #[serde(rename = "_lastInform")]
    last_inform: Option<String>,
    #[serde(rename = "_registered")]
    registered: Option<String>,
    // Nested parameter tree — we extract specific paths
    #[serde(flatten)]
    params: serde_json::Value,
}

/// TR-069 / GenieACS collector.
pub struct Tr069Collector {
    client: reqwest::Client,
    base_url: String,
    username: Option<String>,
    password: Option<String>,
}

impl Tr069Collector {
    pub fn new(config: &Tr069Config) -> anyhow::Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()?;

        let base_url = config.genieacs_url.trim_end_matches('/').to_string();

        Ok(Self {
            client,
            base_url,
            username: config.username.clone(),
            password: config.password.clone(),
        })
    }

    /// Collect all CPE devices from GenieACS.
    pub async fn collect(&self) -> anyhow::Result<Vec<CpeDevice>> {
        let devices = self.list_devices().await?;
        info!(count = devices.len(), "TR-069 devices collected from GenieACS");
        Ok(devices)
    }

    /// GET /devices — list all CPE devices known to GenieACS.
    async fn list_devices(&self) -> anyhow::Result<Vec<CpeDevice>> {
        let url = format!("{}/devices", self.base_url);

        let mut req = self.client.get(&url);
        if let (Some(ref user), Some(ref pass)) = (&self.username, &self.password) {
            req = req.basic_auth(user, Some(pass));
        }

        let resp = req.send().await?;

        if !resp.status().is_success() {
            anyhow::bail!("GenieACS returned status {}", resp.status());
        }

        let raw: Vec<GenieDevice> = resp.json().await?;
        debug!(count = raw.len(), "GenieACS returned devices");

        let mut result = Vec::with_capacity(raw.len());
        for dev in raw {
            result.push(self.parse_device(dev));
        }

        Ok(result)
    }

    /// Parse a GenieACS device JSON into our CpeDevice struct.
    ///
    /// GenieACS stores the TR-069 parameter tree as nested objects with
    /// `_value`, `_type`, `_timestamp` fields. We extract commonly used paths.
    fn parse_device(&self, dev: GenieDevice) -> CpeDevice {
        let manufacturer = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.DeviceInfo.Manufacturer");
        let model = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.DeviceInfo.ModelName");
        let serial = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.DeviceInfo.SerialNumber");
        let firmware = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.DeviceInfo.SoftwareVersion");
        let uptime = self.extract_param_u64(&dev.params,
            "InternetGatewayDevice.DeviceInfo.UpTime");

        // WAN IP (try common paths)
        let wan_ip = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANIPConnection.1.ExternalIPAddress")
            .or_else(|| self.extract_param_str(&dev.params,
                "InternetGatewayDevice.WANDevice.1.WANConnectionDevice.1.WANPPPConnection.1.ExternalIPAddress"));

        // WAN bytes
        let wan_bytes_received = self.extract_param_u64(&dev.params,
            "InternetGatewayDevice.WANDevice.1.WANCommonInterfaceConfig.TotalBytesReceived");
        let wan_bytes_sent = self.extract_param_u64(&dev.params,
            "InternetGatewayDevice.WANDevice.1.WANCommonInterfaceConfig.TotalBytesSent");

        // WiFi stats (first SSID)
        let wifi_ssid = self.extract_param_str(&dev.params,
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.SSID");
        let wifi_channel = self.extract_param_u64(&dev.params,
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.Channel")
            .map(|v| v as u32);
        let wifi_stations = self.extract_param_u64(&dev.params,
            "InternetGatewayDevice.LANDevice.1.WLANConfiguration.1.TotalAssociations")
            .map(|v| v as u32);

        // Classify health based on last inform freshness
        let health = self.classify_health(&dev.last_inform, uptime);

        CpeDevice {
            device_id: dev.id,
            manufacturer,
            model,
            serial_number: serial,
            firmware_version: firmware,
            wan_ip,
            last_inform: dev.last_inform,
            uptime_seconds: uptime,
            wifi_stations,
            wifi_channel,
            wifi_ssid,
            wan_bytes_received,
            wan_bytes_sent,
            health,
        }
    }

    /// Extract a string value from the TR-069 parameter tree.
    ///
    /// GenieACS stores params as: `{ "Path.To.Param": { "_value": "foo", ... } }`
    fn extract_param_str(&self, params: &serde_json::Value, path: &str) -> Option<String> {
        // GenieACS flattens dot-separated paths into nested objects
        let mut current = params;
        for segment in path.split('.') {
            current = current.get(segment)?;
        }
        // The leaf has _value
        current
            .get("_value")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .or_else(|| {
                // Sometimes _value is a number stored as string
                current.get("_value").and_then(|v| {
                    if let Some(n) = v.as_i64() {
                        Some(n.to_string())
                    } else if let Some(n) = v.as_f64() {
                        Some(n.to_string())
                    } else {
                        None
                    }
                })
            })
    }

    /// Extract a u64 value from the TR-069 parameter tree.
    fn extract_param_u64(&self, params: &serde_json::Value, path: &str) -> Option<u64> {
        let mut current = params;
        for segment in path.split('.') {
            current = current.get(segment)?;
        }
        current.get("_value").and_then(|v| {
            v.as_u64()
                .or_else(|| v.as_i64().map(|n| n as u64))
                .or_else(|| v.as_str().and_then(|s| s.parse().ok()))
        })
    }

    /// Classify device health based on last inform timestamp.
    fn classify_health(&self, last_inform: &Option<String>, uptime: Option<u64>) -> CpeHealth {
        if let Some(ref ts) = last_inform {
            if let Ok(dt) = chrono::DateTime::parse_from_rfc3339(ts) {
                let age = chrono::Utc::now().signed_duration_since(dt.with_timezone(&chrono::Utc));
                if age.num_hours() > 24 {
                    return CpeHealth::Red;
                }
                if age.num_hours() > 6 {
                    return CpeHealth::Yellow;
                }
                return CpeHealth::Green;
            }
            // Try other common GenieACS timestamp formats
            if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(ts, "%Y-%m-%dT%H:%M:%S%.fZ") {
                let age = chrono::Utc::now()
                    .naive_utc()
                    .signed_duration_since(dt);
                if age.num_hours() > 24 {
                    return CpeHealth::Red;
                }
                if age.num_hours() > 6 {
                    return CpeHealth::Yellow;
                }
                return CpeHealth::Green;
            }
        }
        // No valid last_inform — consider unhealthy
        CpeHealth::Red
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cpe_health_recent() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let now = chrono::Utc::now().to_rfc3339();
        assert_eq!(collector.classify_health(&Some(now), None), CpeHealth::Green);
    }

    #[test]
    fn test_cpe_health_stale() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let old = (chrono::Utc::now() - chrono::Duration::hours(8)).to_rfc3339();
        assert_eq!(collector.classify_health(&Some(old), None), CpeHealth::Yellow);
    }

    #[test]
    fn test_cpe_health_offline() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let very_old = (chrono::Utc::now() - chrono::Duration::hours(48)).to_rfc3339();
        assert_eq!(collector.classify_health(&Some(very_old), None), CpeHealth::Red);
    }

    #[test]
    fn test_cpe_health_no_inform() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        assert_eq!(collector.classify_health(&None, None), CpeHealth::Red);
    }

    #[test]
    fn test_extract_param_str() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let json: serde_json::Value = serde_json::json!({
            "InternetGatewayDevice": {
                "DeviceInfo": {
                    "Manufacturer": { "_value": "TP-Link", "_type": "xsd:string" }
                }
            }
        });
        let result = collector.extract_param_str(&json, "InternetGatewayDevice.DeviceInfo.Manufacturer");
        assert_eq!(result, Some("TP-Link".to_string()));
    }

    #[test]
    fn test_extract_param_u64() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let json: serde_json::Value = serde_json::json!({
            "InternetGatewayDevice": {
                "DeviceInfo": {
                    "UpTime": { "_value": 86400, "_type": "xsd:unsignedInt" }
                }
            }
        });
        let result = collector.extract_param_u64(&json, "InternetGatewayDevice.DeviceInfo.UpTime");
        assert_eq!(result, Some(86400));
    }

    #[test]
    fn test_extract_missing_param() {
        let collector = Tr069Collector {
            client: reqwest::Client::new(),
            base_url: "http://localhost:7557".into(),
            username: None,
            password: None,
        };
        let json: serde_json::Value = serde_json::json!({});
        assert_eq!(collector.extract_param_str(&json, "Foo.Bar"), None);
        assert_eq!(collector.extract_param_u64(&json, "Foo.Bar"), None);
    }
}
