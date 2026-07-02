// SPDX-License-Identifier: Apache-2.0
// Configuration for the Pulso Agent.
// The ISP fills in their OLT IPs, SNMP credentials, and MikroTik details.
// Credentials are stored locally and NEVER sent to the cloud.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use anyhow::{bail, Context, Result};
use tracing::warn;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AgentConfig {
    /// Unique agent identifier (auto-generated on first run)
    pub agent_id: String,

    /// Directory for local data storage (SQLite buffer, logs)
    #[serde(default = "default_data_dir")]
    pub data_dir: PathBuf,

    /// Polling interval in seconds (default: 60, minimum: 10)
    #[serde(default = "default_poll_interval")]
    pub poll_interval_secs: u64,

    /// How many OLTs to poll concurrently per cycle (default: 4)
    #[serde(default = "default_poll_concurrency")]
    pub poll_concurrency: usize,

    /// Base per-OLT collection timeout in seconds (default: 60). The
    /// effective timeout is `base + per_ont_allowance * last_ont_count`,
    /// floored at 60s, so big OLTs are not discarded wholesale.
    #[serde(default = "default_olt_timeout_base")]
    pub olt_timeout_base_secs: u64,

    /// Extra collection-timeout allowance per ONT in milliseconds
    /// (default: 100). Sized for SNMP worst case: each PDU can cost up to
    /// 3x the SNMP timeout + 600ms retransmit backoff.
    #[serde(default = "default_olt_timeout_per_ont_ms")]
    pub olt_timeout_per_ont_ms: u64,

    /// Operator UTC offset in hours (e.g. 0 for UK winter, 1 for BST, -3
    /// for Brazil) used by day/night and business-hours aware analyses.
    #[serde(default)]
    pub utc_offset_hours: i32,

    /// Path to the NETCONF TOFU host-key store (known_hosts). When unset,
    /// the store lives under the agent data dir.
    pub known_hosts_path: Option<PathBuf>,

    /// Age-based retention for local history tables (signal history, PON
    /// utilization, RADIUS sessions, dead letters). Defaults to 30 days.
    pub retention: Option<crate::transport::RetentionConfig>,

    /// Self-observability listener (/healthz + /metrics). Enabled by
    /// default on 127.0.0.1:9464.
    pub metrics: Option<MetricsConfig>,

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
pub struct MetricsConfig {
    /// Enable the /healthz + /metrics listener (default: true)
    #[serde(default = "default_true")]
    pub enabled: bool,
    /// Bind address (default: 127.0.0.1:9464 — loopback only)
    #[serde(default = "default_metrics_bind")]
    pub bind: String,
}

impl Default for MetricsConfig {
    fn default() -> Self {
        Self { enabled: true, bind: default_metrics_bind() }
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CloudConfig {
    /// Enlace Cloud API endpoint
    #[serde(default = "default_cloud_endpoint")]
    pub endpoint: String,

    /// API key for authentication (obtained from enlace.network)
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

/// SNMPv3 USM credentials. The security level is derived from which fields
/// are set: username only = noAuthNoPriv; + auth_protocol/auth_password =
/// authNoPriv; + priv_protocol/priv_password = authPriv.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SnmpV3Config {
    /// USM security name (the SNMPv3 user)
    pub username: String,
    /// "md5" | "sha1" | "sha224" | "sha256" (RFC 3414 / RFC 7860)
    pub auth_protocol: Option<String>,
    pub auth_password: Option<String>,
    /// "aes128" (RFC 3826). DES is NOT supported and rejected with a clear error.
    pub priv_protocol: Option<String>,
    pub priv_password: Option<String>,
    /// SNMPv3 context name (default: "")
    #[serde(default)]
    pub context_name: String,
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
    /// Bearer token sent as `Authorization: Bearer <token>` on every POST.
    /// Only generic-format webhooks send it (e.g. the enlace-app
    /// `/api/hooks/agent-events` ingress) — Slack and PagerDuty authenticate
    /// through the webhook URL / `routing_key` and ignore this.
    pub bearer_token: Option<String>,
    /// Name of an environment variable to read the bearer token from at
    /// startup (e.g. "ENLACE_HOOK_TOKEN") — keeps the secret out of the
    /// config file. `bearer_token` takes precedence when both are set.
    pub bearer_token_env: Option<String>,
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

    /// Per-port topology CSV directories, keyed "<olt_id>:<pon_port>" (or
    /// just "<pon_port>" to apply to that port on any OLT). Each directory
    /// holds nodes.csv/edges.csv[/ont_map.csv]. Ports without an entry get
    /// NO topology (distance-only fault location) instead of a shared,
    /// wrong global one.
    #[serde(default)]
    pub ports: HashMap<String, PathBuf>,

    /// Configured splitter ratios per PON port (e.g. "1/1/1" = 32 for a
    /// 1:32 splitter). Feeds the detection `_with_topology` analyses so
    /// splitter ratios come from records, not subscriber-count inference.
    #[serde(default)]
    pub splitter_ratios: HashMap<String, u32>,
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
fn default_poll_concurrency() -> usize { 4 }
fn default_olt_timeout_base() -> u64 { 60 }
fn default_olt_timeout_per_ont_ms() -> u64 { 100 }
fn default_metrics_bind() -> String { "127.0.0.1:9464".into() }
fn default_cloud_endpoint() -> String { "https://api.enlace.network/v1/telemetry".into() }
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
// Degradation-rate defaults (dBm/day). Kept above the honest sensor floor:
// DDM quantizes at ~0.1 dB, so the smallest real rate over the 7-day minimum
// window is ~0.043 dBm/day (see predictions/mod.rs header for the math).
fn default_watch_threshold() -> f64 { -0.05 }     // dBm/day rate
fn default_warning_threshold() -> f64 { -0.10 }   // dBm/day rate
fn default_critical_threshold() -> f64 { -0.20 }  // dBm/day rate
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
                // Save back with generated ID. Not fatal when the config is
                // root-owned read-only (the hardened install): the generated
                // ID just won't persist across restarts.
                match toml::to_string_pretty(&cfg) {
                    Ok(updated) => {
                        if let Err(e) = std::fs::write(path, updated) {
                            warn!(
                                error = %e,
                                path = %path.display(),
                                "Could not persist generated agent_id (config not writable); set agent_id in the config to keep it stable"
                            );
                        }
                    }
                    Err(e) => warn!(error = %e, "Could not serialize config to persist agent_id"),
                }
            }

            cfg.validate()?;
            cfg.check_file_permissions(path);
            Ok(cfg)
        } else {
            // Generate example config for the ISP
            let example = Self::example();
            let dir = path.parent().unwrap_or(Path::new("/etc/pulso-agent"));
            std::fs::create_dir_all(dir)?;
            let content = toml::to_string_pretty(&example)?;
            std::fs::write(path, &content)?;
            println!("Example configuration written to {:?}", path);
            println!("Please edit the file with your OLT and router details, then restart.");
            println!();
            println!("Quick start:");
            println!("  1. Set your API key (from enlace.network)");
            println!("  2. Add your OLT IP and SNMP community string");
            println!("  3. Add your MikroTik IP and credentials");
            println!("  4. Run: pulso-agent -v");
            std::process::exit(0);
        }
    }

    /// Validate the loaded configuration. Hard errors for values that would
    /// crash or silently collect nothing; loud warnings for placeholder
    /// credentials and empty device lists.
    pub fn validate(&self) -> Result<()> {
        if self.poll_interval_secs < 10 {
            bail!(
                "poll_interval_secs = {} is invalid (minimum 10; 0 would panic the interval timer)",
                self.poll_interval_secs
            );
        }
        if self.poll_concurrency == 0 {
            bail!("poll_concurrency = 0 is invalid (minimum 1)");
        }
        if !(-12..=14).contains(&self.utc_offset_hours) {
            bail!(
                "utc_offset_hours = {} is invalid (must be between -12 and +14)",
                self.utc_offset_hours
            );
        }

        for olt in &self.olts {
            if let Some(snmp) = &olt.snmp {
                if snmp.max_repetitions < 1 {
                    bail!(
                        "OLT '{}': snmp.max_repetitions = 0 is invalid (minimum 1; 0 makes every walk silently empty)",
                        olt.name
                    );
                }
                match snmp.version.trim().to_ascii_lowercase().as_str() {
                    "v2c" | "2c" => {
                        // A missing community must fail at load time, not as a
                        // runtime poller error hours later.
                        if snmp.community.is_none() {
                            bail!(
                                "OLT '{}': snmp.version = \"v2c\" requires snmp.community (refusing to default to \"public\")",
                                olt.name
                            );
                        }
                    }
                    "v3" | "3" => {
                        let Some(v3) = &snmp.v3 else {
                            bail!(
                                "OLT '{}': snmp.version = \"v3\" requires an [olts.snmp.v3] section with at least a username",
                                olt.name
                            );
                        };
                        // Single source of truth: the USM session constructor
                        // enforces coherent auth/priv combinations (priv
                        // requires auth, DES rejected, password lengths, ...).
                        if let Err(e) = crate::snmp::usm::V3Session::from_config(v3) {
                            bail!("OLT '{}': {}", olt.name, e);
                        }
                    }
                    other => bail!(
                        "OLT '{}': snmp.version = \"{}\" is not supported (supported: \"v2c\", \"v3\")",
                        olt.name, other
                    ),
                }
            }
        }

        if self.olts.is_empty() && self.mikrotiks.is_empty() {
            warn!("No OLTs or MikroTik routers configured — the agent will collect nothing");
        }

        self.warn_placeholder_credentials();
        Ok(())
    }

    /// Loud warnings when the config still carries example/placeholder
    /// credentials — the classic first-boot footgun.
    fn warn_placeholder_credentials(&self) {
        if self.cloud.api_key.is_empty()
            || self.cloud.api_key.starts_with("YOUR_API_KEY")
            || self.cloud.api_key == "CHANGE_ME"
        {
            warn!("cloud.api_key still has the placeholder value — telemetry uploads will be rejected. Get a key from enlace.network");
        }
        for olt in &self.olts {
            let example_host = olt.ip == "10.0.0.1";
            if let Some(snmp) = &olt.snmp {
                if snmp.community.as_deref() == Some("public") {
                    if example_host {
                        warn!(olt = %olt.name, "OLT still has the EXAMPLE ip (10.0.0.1) and \"public\" SNMP community — this looks like an unedited example config");
                    } else {
                        warn!(olt = %olt.name, "SNMP community is \"public\" — replace with your real community string");
                    }
                }
            }
            if let Some(ssh) = &olt.ssh {
                if ssh.enabled && ssh.username == "admin" && ssh.password.as_deref() == Some("admin") {
                    warn!(olt = %olt.name, "SSH credentials are the placeholder admin/admin");
                }
            }
        }
        for mk in &self.mikrotiks {
            if mk.password == "CHANGE_ME" || mk.password.is_empty() {
                warn!(mikrotik = %mk.name, "MikroTik password still has the placeholder value");
            }
        }
    }

    /// The config holds SNMP communities and device passwords — warn when
    /// other users on the box can read it.
    fn check_file_permissions(&self, path: &Path) {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            if let Ok(meta) = std::fs::metadata(path) {
                let mode = meta.permissions().mode();
                if mode & 0o004 != 0 {
                    warn!(
                        path = %path.display(),
                        mode = format!("{:o}", mode & 0o777),
                        "Config file is world-readable but contains credentials — run: chmod 640 {}",
                        path.display()
                    );
                }
            }
        }
    }

    fn example() -> Self {
        AgentConfig {
            agent_id: String::new(),
            data_dir: default_data_dir(),
            poll_interval_secs: 60,
            poll_concurrency: default_poll_concurrency(),
            olt_timeout_base_secs: default_olt_timeout_base(),
            olt_timeout_per_ont_ms: default_olt_timeout_per_ont_ms(),
            utc_offset_hours: 0,
            known_hosts_path: None,
            retention: None,
            metrics: None,
            cloud: CloudConfig {
                endpoint: default_cloud_endpoint(),
                api_key: "YOUR_API_KEY_FROM_ENLACE".into(),
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

[[output.webhooks]]
url = "https://app.enlace.network/api/hooks/agent-events"
events = ["fault_detected", "fault_resolved"]
format = "generic"
bearer_token_env = "ENLACE_HOOK_TOKEN"
"#;
        let cfg: AgentConfig = toml::from_str(toml).expect("TOML parse failed");
        let output = cfg.output.as_ref().expect("output should be Some");
        let elastic = output.elastic.as_ref().expect("elastic should be Some");
        assert_eq!(elastic.url, "http://localhost:9200");
        assert_eq!(elastic.index_prefix, "pulso");
        let webhooks = output.webhooks.as_ref().expect("webhooks should be Some");
        assert_eq!(webhooks.len(), 3);
        assert_eq!(webhooks[1].routing_key.as_deref(), Some("abc123"));
        // Bearer auth fields are optional and default to None
        assert_eq!(webhooks[0].bearer_token, None);
        assert_eq!(webhooks[0].bearer_token_env, None);
        assert_eq!(
            webhooks[2].bearer_token_env.as_deref(),
            Some("ENLACE_HOOK_TOKEN")
        );
        assert_eq!(webhooks[2].bearer_token, None);
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

    fn minimal_cfg(extra: &str) -> AgentConfig {
        // `extra` goes BEFORE [cloud] so bare keys stay top-level;
        // table sections in `extra` still work because [cloud] follows them
        // only lexically, not structurally.
        let toml = format!(
            r#"
agent_id = "validate-agent"
{extra}

[cloud]
endpoint = "https://api.example.com"
api_key = "real-key"
"#
        );
        toml::from_str(&toml).expect("TOML parse failed")
    }

    #[test]
    fn test_validate_rejects_short_poll_interval() {
        let cfg = minimal_cfg("poll_interval_secs = 0");
        let err = cfg.validate().unwrap_err().to_string();
        assert!(err.contains("poll_interval_secs"), "got: {err}");

        let cfg = minimal_cfg("poll_interval_secs = 9");
        assert!(cfg.validate().is_err());

        let cfg = minimal_cfg("poll_interval_secs = 10");
        assert!(cfg.validate().is_ok());
    }

    #[test]
    fn test_validate_rejects_incoherent_snmp_and_zero_max_repetitions() {
        // v3 without a [olts.snmp.v3] credentials section
        let cfg = minimal_cfg(
            r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v3"
community = "secret"
"#,
        );
        let err = cfg.validate().unwrap_err().to_string();
        assert!(err.contains("snmp.v3"), "got: {err}");

        // Unknown versions are rejected outright
        let cfg = minimal_cfg(
            r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v1"
community = "secret"
"#,
        );
        let err = cfg.validate().unwrap_err().to_string();
        assert!(err.contains("not supported"), "got: {err}");

        let cfg = minimal_cfg(
            r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v2c"
community = "secret"
max_repetitions = 0
"#,
        );
        let err = cfg.validate().unwrap_err().to_string();
        assert!(err.contains("max_repetitions"), "got: {err}");
    }

    #[test]
    fn test_validate_v2c_requires_community_and_stays_backward_compatible() {
        // v2c with a community: unchanged, valid
        let cfg = minimal_cfg(
            r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v2c"
community = "secret"
"#,
        );
        assert!(cfg.validate().is_ok());

        // v2c without a community fails at load time, never defaults to "public"
        let cfg = minimal_cfg(
            r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v2c"
"#,
        );
        let err = cfg.validate().unwrap_err().to_string();
        assert!(err.contains("community"), "got: {err}");
        assert!(err.contains("public"), "got: {err}");
    }

    #[test]
    fn test_validate_v3_credential_combinations() {
        let with_v3 = |v3_body: &str| {
            minimal_cfg(&format!(
                r#"
[[olts]]
name = "OLT-1"
ip = "192.0.2.1"
vendor = "huawei"

[olts.snmp]
version = "v3"

[olts.snmp.v3]
{v3_body}
"#
            ))
        };

        // Full authPriv config parses and validates
        let cfg = with_v3(
            r#"username = "pulso"
auth_protocol = "sha256"
auth_password = "correct-horse"
priv_protocol = "aes128"
priv_password = "battery-staple"
"#,
        );
        assert!(cfg.validate().is_ok());
        let v3 = cfg.olts[0].snmp.as_ref().unwrap().v3.as_ref().unwrap();
        assert_eq!(v3.context_name, ""); // serde default keeps old configs parsing

        // noAuthNoPriv (username only) is a valid level
        assert!(with_v3(r#"username = "pulso""#).validate().is_ok());

        // Empty username fails
        let err = with_v3(r#"username = """#).validate().unwrap_err().to_string();
        assert!(err.contains("username"), "got: {err}");

        // priv without auth fails
        let err = with_v3(
            r#"username = "pulso"
priv_protocol = "aes128"
priv_password = "battery-staple"
"#,
        )
        .validate()
        .unwrap_err()
        .to_string();
        assert!(err.contains("requires authentication"), "got: {err}");

        // DES is rejected with a clear pointer to AES, never a silent fallback
        let err = with_v3(
            r#"username = "pulso"
auth_protocol = "sha1"
auth_password = "correct-horse"
priv_protocol = "des"
priv_password = "battery-staple"
"#,
        )
        .validate()
        .unwrap_err()
        .to_string();
        assert!(err.contains("DES"), "got: {err}");
        assert!(err.contains("aes128"), "got: {err}");

        // auth_protocol without auth_password fails
        let err = with_v3(
            r#"username = "pulso"
auth_protocol = "sha1"
"#,
        )
        .validate()
        .unwrap_err()
        .to_string();
        assert!(err.contains("auth_password"), "got: {err}");
    }

    #[test]
    fn test_validate_rejects_zero_concurrency_and_bad_offset() {
        let cfg = minimal_cfg("poll_concurrency = 0");
        assert!(cfg.validate().is_err());

        let cfg = minimal_cfg("utc_offset_hours = 15");
        assert!(cfg.validate().is_err());

        let cfg = minimal_cfg("utc_offset_hours = -3");
        assert!(cfg.validate().is_ok());
    }

    #[test]
    fn test_new_fields_defaults_backward_compatible() {
        let cfg = minimal_cfg("");
        assert_eq!(cfg.poll_concurrency, 4);
        assert_eq!(cfg.olt_timeout_base_secs, 60);
        assert_eq!(cfg.olt_timeout_per_ont_ms, 100);
        assert_eq!(cfg.utc_offset_hours, 0);
        assert!(cfg.known_hosts_path.is_none());
        assert!(cfg.retention.is_none());
        assert!(cfg.metrics.is_none());
        assert_eq!(MetricsConfig::default().bind, "127.0.0.1:9464");
        assert!(MetricsConfig::default().enabled);
    }

    #[test]
    fn test_parse_topology_ports_and_splitter_ratios() {
        let cfg = minimal_cfg(
            r#"
[topology]
mode = "csv"
import_path = "/etc/pulso-agent/topology/global"

[topology.ports]
"OLT-1:1/1/1" = "/etc/pulso-agent/topology/olt1-p1"

[topology.splitter_ratios]
"1/1/1" = 32
"1/1/2" = 64
"#,
        );
        let topo = cfg.topology.as_ref().expect("topology");
        assert_eq!(
            topo.ports.get("OLT-1:1/1/1").unwrap(),
            &PathBuf::from("/etc/pulso-agent/topology/olt1-p1")
        );
        assert_eq!(topo.splitter_ratios.get("1/1/1"), Some(&32));
        assert_eq!(topo.splitter_ratios.get("1/1/2"), Some(&64));
    }

    #[test]
    fn test_parse_metrics_and_retention_sections() {
        let cfg = minimal_cfg(
            r#"
utc_offset_hours = 1
known_hosts_path = "/var/lib/pulso-agent/netconf_known_hosts"

[metrics]
enabled = true
bind = "127.0.0.1:9465"

[retention]
signal_history_days = 14
"#,
        );
        assert_eq!(cfg.metrics.as_ref().unwrap().bind, "127.0.0.1:9465");
        assert_eq!(cfg.retention.as_ref().unwrap().signal_history_days, 14);
        assert_eq!(cfg.utc_offset_hours, 1);
        assert_eq!(
            cfg.known_hosts_path.as_deref(),
            Some(std::path::Path::new("/var/lib/pulso-agent/netconf_known_hosts"))
        );
    }

    #[test]
    fn test_default_thresholds_match_honest_floor() {
        // Defaults must match the sensor-resolution floor documented in
        // predictions/mod.rs: watch -0.05, warning -0.10, critical -0.20.
        assert!((default_watch_threshold() - (-0.05)).abs() < 1e-9);
        assert!((default_warning_threshold() - (-0.10)).abs() < 1e-9);
        assert!((default_critical_threshold() - (-0.20)).abs() < 1e-9);
        assert!(default_cloud_endpoint().contains("enlace.network"));
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
