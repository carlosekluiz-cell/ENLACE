// SPDX-License-Identifier: Apache-2.0
// Configuration for the Pulso Agent.
// The ISP fills in their OLT IPs, SNMP credentials, and MikroTik details.
// Credentials are stored locally and NEVER sent to the cloud.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use anyhow::{Context, Result};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AgentConfig {
    /// Unique agent identifier (auto-generated on first run)
    pub agent_id: String,

    /// Directory for local data storage (SQLite buffer, logs)
    #[serde(default = "default_data_dir")]
    pub data_dir: PathBuf,

    /// Polling interval in seconds (default: 60)
    #[serde(default = "default_poll_interval")]
    pub poll_interval_secs: u64,

    /// Pulso Cloud connection settings
    pub cloud: CloudConfig,

    /// OLT devices to monitor
    #[serde(default)]
    pub olts: Vec<OltConfig>,

    /// MikroTik routers to monitor
    #[serde(default)]
    pub mikrotiks: Vec<MikrotikConfig>,

    /// RADIUS accounting listener (optional)
    pub radius: Option<RadiusConfig>,

    /// TR-069 / GenieACS integration (optional)
    pub tr069: Option<Tr069Config>,

    /// Network scan range for discovery (CIDR notation, e.g., "10.0.0.0/24")
    pub scan_range: Option<String>,

    /// SNMP communities to try during discovery
    pub scan_communities: Option<Vec<String>>,

    /// Output destinations (cloud, Elasticsearch, webhooks)
    pub output: Option<OutputConfig>,

    /// Fault detection configuration
    pub fault_detection: Option<FaultDetectionConfig>,

    /// Network topology configuration
    pub topology: Option<TopologyConfig>,

    /// Optical signal degradation tracking
    pub degradation: Option<DegradationConfig>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CloudConfig {
    /// Pulso Cloud API endpoint
    #[serde(default = "default_cloud_endpoint")]
    pub endpoint: String,

    /// API key for authentication (obtained from pulsonetwork.com.br)
    pub api_key: String,

    /// Send interval in seconds (aggregate data before sending)
    #[serde(default = "default_send_interval")]
    pub send_interval_secs: u64,

    /// Enable TLS certificate verification (default: true)
    #[serde(default = "default_true")]
    pub verify_tls: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct OltConfig {
    /// Human-readable name for this OLT
    pub name: String,

    /// IP address of the OLT management interface
    pub ip: String,

    /// OLT vendor (auto-detected if omitted)
    /// Supported: huawei, zte, fiberhome, intelbras, datacom, parks, bdcom, vsol, cdata, ubiquiti, nokia, adtran, generic
    #[serde(default = "default_vendor")]
    pub vendor: String,

    /// OLT model (auto-detected if omitted)
    #[serde(default)]
    pub model: String,

    /// SNMP configuration
    pub snmp: Option<SnmpConfig>,

    /// SSH/CLI configuration (for data not available via SNMP)
    pub ssh: Option<SshConfig>,

    /// NETCONF configuration (for Datacom DmOS, Huawei MA5800, ZTE C600+)
    pub netconf: Option<NetconfConfig>,

    /// REST API configuration (for Ubiquiti UISP)
    pub rest_api: Option<RestApiConfig>,

    /// gRPC configuration (for Adtran SDX, OpenOLT)
    pub grpc: Option<GrpcConfig>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SnmpConfig {
    /// SNMP version: "v2c" or "v3"
    #[serde(default = "default_snmp_version")]
    pub version: String,

    /// Community string (for v2c)
    pub community: Option<String>,

    /// SNMPv3 credentials
    pub v3: Option<SnmpV3Config>,

    /// SNMP port (default: 161)
    #[serde(default = "default_snmp_port")]
    pub port: u16,

    /// Timeout in milliseconds (default: 5000)
    #[serde(default = "default_snmp_timeout")]
    pub timeout_ms: u64,

    /// Maximum OIDs per GetBulk request (default: 50)
    #[serde(default = "default_max_repetitions")]
    pub max_repetitions: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SnmpV3Config {
    pub username: String,
    pub auth_protocol: Option<String>,  // MD5, SHA, SHA256
    pub auth_password: Option<String>,
    pub priv_protocol: Option<String>,  // DES, AES128, AES256
    pub priv_password: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SshConfig {
    pub username: String,
    /// Password or path to SSH key file
    pub password: Option<String>,
    pub key_file: Option<PathBuf>,
    #[serde(default = "default_ssh_port")]
    pub port: u16,
    /// Enable CLI scraping (default: true, set false to disable for this OLT)
    #[serde(default = "default_true")]
    pub enabled: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NetconfConfig {
    pub username: String,
    pub password: Option<String>,
    pub key_file: Option<PathBuf>,
    #[serde(default = "default_netconf_port")]
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RestApiConfig {
    pub base_url: String,
    pub api_key: Option<String>,
    pub username: Option<String>,
    pub password: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct GrpcConfig {
    #[serde(default = "default_grpc_port")]
    pub port: u16,
    #[serde(default)]
    pub tls: bool,
    pub tls_cert: Option<PathBuf>,
    pub tls_key: Option<PathBuf>,
    pub tls_ca: Option<PathBuf>,
    #[serde(default = "default_grpc_connect_timeout")]
    pub connect_timeout_ms: u64,
    #[serde(default = "default_grpc_request_timeout")]
    pub request_timeout_ms: u64,
}

#[derive(Debug, Clone, Deserialize, Serialize, Default)]
pub struct OutputConfig {
    pub cloud: Option<CloudOutputConfig>,
    pub elastic: Option<ElasticConfig>,
    pub webhooks: Option<Vec<WebhookConfig>>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CloudOutputConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    pub endpoint: String,
    pub api_key: String,
    #[serde(default = "default_send_interval")]
    pub send_interval_secs: u64,
    #[serde(default = "default_true")]
    pub verify_tls: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ElasticConfig {
    #[serde(default)]
    pub enabled: bool,
    pub url: String,
    #[serde(default = "default_index_prefix")]
    pub index_prefix: String,
    #[serde(default = "default_bulk_size")]
    pub bulk_size: usize,
    pub username: Option<String>,
    pub password: Option<String>,
    pub api_key: Option<String>,
    #[serde(default = "default_true")]
    pub verify_tls: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct WebhookConfig {
    pub url: String,
    pub events: Vec<String>,
    pub format: String,
    pub routing_key: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FaultDetectionConfig {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_min_offline")]
    pub min_offline_onts: usize,
    #[serde(default = "default_fault_window")]
    pub time_window_seconds: u64,
    #[serde(default)]
    pub severity: FaultSeverityConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FaultSeverityConfig {
    #[serde(default = "default_severity_critical")]
    pub critical: usize,
    #[serde(default = "default_severity_major")]
    pub major: usize,
    #[serde(default = "default_severity_minor")]
    pub minor: usize,
}

impl Default for FaultSeverityConfig {
    fn default() -> Self {
        Self { critical: 100, major: 50, minor: 10 }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TopologyConfig {
    #[serde(default = "default_topology_mode")]
    pub mode: String,
    pub import_path: Option<PathBuf>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct DegradationConfig {
    #[serde(default = "default_history_days")]
    pub history_days: u32,
    #[serde(default = "default_trend_window")]
    pub trend_window_weeks: u32,
    #[serde(default = "default_watch_threshold")]
    pub watch_threshold_db: f64,
    #[serde(default = "default_warning_threshold")]
    pub warning_threshold_db: f64,
    #[serde(default = "default_critical_threshold")]
    pub critical_threshold_db: f64,
    #[serde(default = "default_min_critical_rx")]
    pub min_critical_rx_dbm: f64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MikrotikConfig {
    pub name: String,
    pub ip: String,
    #[serde(default = "default_mikrotik_port")]
    pub port: u16,
    pub username: String,
    pub password: String,
    /// Collect PPPoE session data (default: true)
    #[serde(default = "default_true")]
    pub collect_pppoe: bool,
    /// Collect BGP session data (default: true)
    #[serde(default = "default_true")]
    pub collect_bgp: bool,
    /// Collect interface traffic (default: true)
    #[serde(default = "default_true")]
    pub collect_interfaces: bool,
    /// Collect queue/bandwidth data (default: true)
    #[serde(default = "default_true")]
    pub collect_queues: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RadiusConfig {
    /// Listen port for RADIUS accounting (default: 1813)
    #[serde(default = "default_radius_port")]
    pub port: u16,
    /// Shared secret for RADIUS packets
    pub secret: String,
    /// Listen address (default: 0.0.0.0)
    #[serde(default = "default_listen_addr")]
    pub listen_addr: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Tr069Config {
    /// GenieACS API endpoint (e.g., http://localhost:7557)
    pub genieacs_url: String,
    /// GenieACS credentials (optional)
    pub username: Option<String>,
    pub password: Option<String>,
    /// Poll interval for TR-069 data (default: 300 seconds)
    #[serde(default = "default_tr069_interval")]
    pub poll_interval_secs: u64,
}

// Defaults
fn default_data_dir() -> PathBuf { PathBuf::from("/var/lib/pulso-agent") }
fn default_poll_interval() -> u64 { 60 }
fn default_cloud_endpoint() -> String { "https://api.pulsonetwork.com.br/v1/telemetry".into() }
fn default_send_interval() -> u64 { 300 }
fn default_true() -> bool { true }
fn default_vendor() -> String { "auto".into() }
fn default_snmp_version() -> String { "v2c".into() }
fn default_snmp_port() -> u16 { 161 }
fn default_snmp_timeout() -> u64 { 5000 }
fn default_max_repetitions() -> u32 { 50 }
fn default_ssh_port() -> u16 { 22 }
pub(crate) fn default_netconf_port() -> u16 { 830 }
fn default_mikrotik_port() -> u16 { 8728 }
fn default_radius_port() -> u16 { 1813 }
fn default_listen_addr() -> String { "0.0.0.0".into() }
fn default_tr069_interval() -> u64 { 300 }
fn default_grpc_port() -> u16 { 9191 }
fn default_grpc_connect_timeout() -> u64 { 5000 }
fn default_grpc_request_timeout() -> u64 { 10000 }
fn default_index_prefix() -> String { "enlace".into() }
fn default_bulk_size() -> usize { 1000 }
fn default_min_offline() -> usize { 5 }
fn default_fault_window() -> u64 { 60 }
fn default_severity_critical() -> usize { 100 }
fn default_severity_major() -> usize { 50 }
fn default_severity_minor() -> usize { 10 }
fn default_topology_mode() -> String { "infer".into() }
fn default_history_days() -> u32 { 30 }
fn default_trend_window() -> u32 { 4 }
fn default_watch_threshold() -> f64 { -0.015 }   // dBm/day rate
fn default_warning_threshold() -> f64 { -0.035 }  // dBm/day rate
fn default_critical_threshold() -> f64 { -0.07 }  // dBm/day rate
fn default_min_critical_rx() -> f64 { -27.0 }

impl AgentConfig {
    pub fn load(path: &Path) -> Result<Self> {
        if path.exists() {
            let content = std::fs::read_to_string(path)
                .with_context(|| format!("Failed to read config: {:?}", path))?;
            let mut cfg: AgentConfig = toml::from_str(&content)
                .with_context(|| "Failed to parse config TOML")?;

            // Auto-generate agent_id if not set
            if cfg.agent_id.is_empty() {
                cfg.agent_id = uuid::Uuid::new_v4().to_string();
                // Save back with generated ID
                let updated = toml::to_string_pretty(&cfg)?;
                std::fs::write(path, updated)?;
            }

            Ok(cfg)
        } else {
            // Generate example config for the ISP
            let example = Self::example();
            let dir = path.parent().unwrap_or(Path::new("/etc/pulso"));
            std::fs::create_dir_all(dir)?;
            let content = toml::to_string_pretty(&example)?;
            std::fs::write(path, &content)?;
            println!("Example configuration written to {:?}", path);
            println!("Please edit the file with your OLT and router details, then restart.");
            println!();
            println!("Quick start:");
            println!("  1. Set your Pulso API key (from pulsonetwork.com.br)");
            println!("  2. Add your OLT IP and SNMP community string");
            println!("  3. Add your MikroTik IP and credentials");
            println!("  4. Run: pulso-agent -v");
            std::process::exit(0);
        }
    }

    fn example() -> Self {
        AgentConfig {
            agent_id: String::new(),
            data_dir: default_data_dir(),
            poll_interval_secs: 60,
            cloud: CloudConfig {
                endpoint: default_cloud_endpoint(),
                api_key: "YOUR_API_KEY_FROM_PULSONETWORK".into(),
                send_interval_secs: 300,
                verify_tls: true,
            },
            olts: vec![OltConfig {
                name: "OLT-Principal".into(),
                ip: "10.0.0.1".into(),
                vendor: "auto".into(),
                model: String::new(),
                snmp: Some(SnmpConfig {
                    version: "v2c".into(),
                    community: Some("public".into()),
                    v3: None,
                    port: 161,
                    timeout_ms: 5000,
                    max_repetitions: 50,
                }),
                ssh: Some(SshConfig {
                    username: "admin".into(),
                    password: Some("admin".into()),
                    key_file: None,
                    port: 22,
                    enabled: true,
                }),
                netconf: None,
                rest_api: None,
                grpc: None,
            }],
            mikrotiks: vec![MikrotikConfig {
                name: "MK-Core".into(),
                ip: "10.0.0.254".into(),
                port: 8728,
                username: "pulso".into(),
                password: "CHANGE_ME".into(),
                collect_pppoe: true,
                collect_bgp: true,
                collect_interfaces: true,
                collect_queues: true,
            }],
            radius: None,
            tr069: None,
            scan_range: None,
            scan_communities: None,
            output: None,
            fault_detection: None,
            topology: None,
            degradation: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_grpc_config() {
        let toml = r#"
agent_id = "test-agent"

[cloud]
endpoint = "https://api.example.com"
api_key = "test-key"

[[olts]]
name = "OLT-Adtran"
ip = "192.168.1.1"
vendor = "adtran"

[olts.grpc]
port = 9191
tls = false
"#;
        let cfg: AgentConfig = toml::from_str(toml).expect("TOML parse failed");
        assert_eq!(cfg.olts.len(), 1);
        let grpc = cfg.olts[0].grpc.as_ref().expect("grpc should be Some");
        assert_eq!(grpc.port, 9191);
        assert!(!grpc.tls);
    }

    #[test]
    fn test_parse_output_config() {
        let toml = r#"
agent_id = "test-agent"

[cloud]
endpoint = "https://api.example.com"
api_key = "test-key"

[output.elastic]
enabled = true
url = "http://localhost:9200"
index_prefix = "pulso"

[[output.webhooks]]
url = "https://hooks.example.com/alert"
events = ["ont_offline", "fiber_cut"]
format = "json"

[[output.webhooks]]
url = "https://pagerduty.example.com/v2/enqueue"
events = ["fault_critical"]
format = "pagerduty"
routing_key = "abc123"
"#;
        let cfg: AgentConfig = toml::from_str(toml).expect("TOML parse failed");
        let output = cfg.output.as_ref().expect("output should be Some");
        let elastic = output.elastic.as_ref().expect("elastic should be Some");
        assert_eq!(elastic.url, "http://localhost:9200");
        assert_eq!(elastic.index_prefix, "pulso");
        let webhooks = output.webhooks.as_ref().expect("webhooks should be Some");
        assert_eq!(webhooks.len(), 2);
        assert_eq!(webhooks[1].routing_key.as_deref(), Some("abc123"));
    }

    #[test]
    fn test_parse_fault_detection_config() {
        let toml = r#"
agent_id = "test-agent"

[cloud]
endpoint = "https://api.example.com"
api_key = "test-key"

[fault_detection]
enabled = true
min_offline_onts = 10
time_window_seconds = 120

[fault_detection.severity]
critical = 200
major = 75
minor = 15
"#;
        let cfg: AgentConfig = toml::from_str(toml).expect("TOML parse failed");
        let fd = cfg.fault_detection.as_ref().expect("fault_detection should be Some");
        assert!(fd.enabled);
        assert_eq!(fd.min_offline_onts, 10);
        assert_eq!(fd.time_window_seconds, 120);
        assert_eq!(fd.severity.critical, 200);
        assert_eq!(fd.severity.major, 75);
        assert_eq!(fd.severity.minor, 15);
    }

    #[test]
    fn test_backward_compatible_no_output() {
        let toml = r#"
agent_id = "legacy-agent"

[cloud]
endpoint = "https://api.example.com"
api_key = "legacy-key"
"#;
        let cfg: AgentConfig = toml::from_str(toml).expect("TOML parse failed");
        assert_eq!(cfg.agent_id, "legacy-agent");
        assert!(cfg.output.is_none());
        assert!(cfg.fault_detection.is_none());
        assert!(cfg.topology.is_none());
        assert!(cfg.degradation.is_none());
    }
}
