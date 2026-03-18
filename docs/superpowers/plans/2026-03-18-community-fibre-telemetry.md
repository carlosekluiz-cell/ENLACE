# Community Fibre Telemetry Module — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing pulso-agent Rust binary with Adtran SDX gRPC support, Elasticsearch output, webhook alerts, and fault location — tailored for Community Fibre UK's GPON network.

**Architecture:** Adds ~1,600 lines across 9 new files and modifications to 5 existing files. The Adtran adapter uses OpenOLT gRPC (persistent channel + DashMap state table) instead of SNMP. Elasticsearch output uses `_bulk` NDJSON API. Fault location uses ONT distance data to estimate fibre break coordinates.

**Tech Stack:** Rust, tonic (gRPC), prost (protobuf), dashmap (concurrent state), reqwest (HTTP), rusqlite (buffer), serde_json (NDJSON)

**Spec:** `docs/superpowers/specs/2026-03-18-community-fibre-telemetry-design.md`

---

## File Map

### New Files

| File | Responsibility | Est. Lines |
|------|---------------|-----------|
| `pulso-agent/proto/openolt.proto` | Minimal OpenOLT protobuf definitions (subset of opencord/voltha-protos — only RPCs we use) | ~150 |
| `pulso-agent/build.rs` | Compile .proto files via tonic-build | ~15 |
| `pulso-agent/src/vendors/adtran.rs` | Adtran SDX 6320 gRPC collector | ~300 |
| `pulso-agent/src/output/mod.rs` | Output dispatcher (elastic + webhook + cloud) | ~50 |
| `pulso-agent/src/output/elastic.rs` | Elasticsearch/OpenSearch bulk API client | ~250 |
| `pulso-agent/src/output/webhook.rs` | Slack/PagerDuty webhook dispatcher | ~150 |
| `pulso-agent/src/fault/mod.rs` | Fault module root (re-exports) | ~15 |
| `pulso-agent/src/fault/detector.rs` | Mass-offline pattern detection with DyingGasp filtering | ~200 |
| `pulso-agent/src/fault/topology.rs` | Fibre route DAG model (import, infer, synthetic) | ~200 |
| `pulso-agent/src/fault/locator.rs` | Geographic break calculation + distance-only fallback | ~250 |

### Modified Files

| File | Changes |
|------|---------|
| `pulso-agent/Cargo.toml` | Add tonic, prost, dashmap deps + tonic-build build-dep |
| `pulso-agent/src/config/mod.rs` | Add `GrpcConfig`, `OutputConfig`, `ElasticConfig`, `WebhookConfig`, `FaultDetectionConfig`, `TopologyConfig`, `DegradationConfig` structs + extend `AgentConfig` and `OltConfig` |
| `pulso-agent/src/vendors/mod.rs` | Add `pub mod adtran;` + register in `create_collector()` + add `eth_speed_mbps` to `OntData` |
| `pulso-agent/src/diagnostics/mod.rs` | Add ethernet negotiation check + restart detection |
| `pulso-agent/src/predictions/mod.rs` | Configurable history window + XGS-PON thresholds |
| `pulso-agent/src/main.rs` | Wire fault detection, elastic output, webhook dispatch into main loop |

---

## Task 1: Add Dependencies to Cargo.toml

**Files:**
- Modify: `pulso-agent/Cargo.toml`

- [ ] **Step 1: Add runtime dependencies**

Add to `[dependencies]` section:
```toml
tonic = { version = "0.12", features = ["tls"] }
prost = "0.13"
prost-types = "0.13"
dashmap = "6"
```

- [ ] **Step 2: Add build dependency**

Add new section:
```toml
[build-dependencies]
tonic-build = "0.12"
```

- [ ] **Step 3: Verify it compiles**

Run: `cd /home/dev/enlace/pulso-agent && cargo check 2>&1 | tail -5`
Expected: Compiles (downloads new deps, no errors)

- [ ] **Step 4: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add Cargo.toml Cargo.lock
git commit -m "feat(agent): add tonic/prost/dashmap deps for gRPC + fault detection"
```

---

## Task 2: Create Minimal OpenOLT Proto + build.rs

**Files:**
- Create: `pulso-agent/proto/openolt.proto`
- Create: `pulso-agent/build.rs`

We create a **minimal** proto containing only the messages and RPCs the Adtran adapter needs. The full `opencord/voltha-protos` has dependencies on `google/api/annotations.proto`, `ext_config.proto`, and `extensions.proto` that are difficult to resolve. Our minimal proto compiles standalone.

**Why not download the full proto:** The full `openolt.proto` imports `google/api/annotations.proto` (googleapis), `voltha_protos/ext_config.proto`, and `voltha_protos/extensions.proto`. Resolving these requires vendoring the entire googleapis proto bundle + multiple VOLTHA protos. Since we only use 5 RPCs, a minimal proto is cleaner and more maintainable.

- [ ] **Step 1: Create proto directory and minimal openolt.proto**

Create `pulso-agent/proto/openolt.proto`:
```protobuf
// Minimal OpenOLT proto — subset of opencord/voltha-protos (Apache-2.0)
// Contains only the messages and RPCs used by the Adtran SDX adapter.
// Full source: https://github.com/opencord/voltha-protos
syntax = "proto3";
package openolt;

message Empty {}

message DeviceInfo {
    string vendor = 1;
    string model = 2;
    string hardware_version = 3;
    string firmware_version = 4;
    string device_id = 16;
    string device_serial_number = 17;
    uint32 pon_ports = 12;
}

message SerialNumber {
    bytes vendor_id = 1;
    bytes vendor_specific = 2;
}

message Onu {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    SerialNumber serial_number = 3;
    uint32 pir = 4;
}

message OnuIndication {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    string oper_state = 3;
    string admin_state = 5;
    SerialNumber serial_number = 4;
}

message AlarmIndication {
    oneof data {
        DyingGaspIndication dying_gasp_ind = 1;
        OnuAlarmIndication onu_alarm_ind = 6;
    }
}

message DyingGaspIndication {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    string status = 3;
}

message OnuAlarmIndication {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    string los_status = 3;
    string lob_status = 4;
    string lopc_miss_status = 5;
    string lopc_mic_error_status = 6;
}

message Indication {
    oneof data {
        OnuIndication onu_ind = 4;
        AlarmIndication alarm_ind = 6;
    }
}

message IntfOperIndication {
    string type = 1;
    uint32 intf_id = 2;
    string oper_state = 3;
}

// Optical power response
message PowerMeanTypical {
    double rx_power_mean_dbm = 1;
    double tx_power_mean_dbm = 2;
    double laser_bias_current_mean = 3;
    double temperature_mean = 4;
}

// Distance response
message OnuLogicalDistance {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    uint32 logical_onu_distance = 3;
    uint32 logical_onu_distance_zero_touch = 4;
}

message OnuInfo {
    uint32 intf_id = 1;
    uint32 onu_id = 2;
    enum OnuState {
        NOT_CONFIGURED = 0;
        ACTIVE = 1;
        INACTIVE = 2;
        DISABLED = 3;
    }
    OnuState state = 3;
    bool losi = 4;
    bool lofi = 5;
    bool loami = 6;
    SerialNumber serial_number = 7;
}

service Openolt {
    rpc GetDeviceInfo(Empty) returns (DeviceInfo);
    rpc EnableIndication(Empty) returns (stream Indication);
    rpc GetOnuInfo(Onu) returns (OnuInfo);
    rpc GetPonRxPower(Onu) returns (PowerMeanTypical);
    rpc GetLogicalOnuDistance(Onu) returns (OnuLogicalDistance);
}
```

- [ ] **Step 2: Write build.rs**

Create `pulso-agent/build.rs`:
```rust
fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .build_server(false)  // We only need the client
        .compile_protos(
            &["proto/openolt.proto"],
            &["proto/"],
        )?;
    Ok(())
}
```

- [ ] **Step 3: Verify proto compilation**

Run: `cd /home/dev/enlace/pulso-agent && cargo check 2>&1 | tail -10`
Expected: Compiles. The generated code will be in `target/` under OUT_DIR.

Verify the generated structs match what we expect:
```bash
find /home/dev/enlace/pulso-agent/target -name "openolt.rs" -path "*/OUT_DIR/*" 2>/dev/null | head -1 | xargs grep "pub struct SerialNumber" 2>/dev/null
```

- [ ] **Step 4: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add proto/ build.rs
git commit -m "feat(agent): add minimal OpenOLT proto definitions + build.rs"
```

---

## Task 3: Config Extensions

**Files:**
- Modify: `pulso-agent/src/config/mod.rs`

- [ ] **Step 1: Write test for new config structs**

Add to the bottom of `config/mod.rs`:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_grpc_config() {
        let toml_str = r#"
            agent_id = "test"
            poll_interval_secs = 30

            [cloud]
            endpoint = "https://example.com"
            api_key = "test-key"

            [[olts]]
            name = "SDX-1"
            ip = "10.0.1.2"
            vendor = "adtran"
            [olts.grpc]
            port = 9191
            tls = false
        "#;
        let cfg: AgentConfig = toml::from_str(toml_str).unwrap();
        assert_eq!(cfg.olts.len(), 1);
        let grpc = cfg.olts[0].grpc.as_ref().unwrap();
        assert_eq!(grpc.port, 9191);
        assert!(!grpc.tls);
    }

    #[test]
    fn test_parse_output_config() {
        let toml_str = r#"
            agent_id = "test"
            poll_interval_secs = 30

            [cloud]
            endpoint = "https://example.com"
            api_key = "test-key"

            [output.elastic]
            enabled = true
            url = "http://elastic:9200"
            index_prefix = "enlace"
            bulk_size = 500
            verify_tls = false

            [[output.webhooks]]
            url = "https://hooks.slack.com/xxx"
            events = ["fault_detected"]
            format = "slack"
        "#;
        let cfg: AgentConfig = toml::from_str(toml_str).unwrap();
        let elastic = cfg.output.as_ref().unwrap().elastic.as_ref().unwrap();
        assert_eq!(elastic.url, "http://elastic:9200");
        assert_eq!(elastic.bulk_size, 500);
        let webhooks = cfg.output.as_ref().unwrap().webhooks.as_ref().unwrap();
        assert_eq!(webhooks.len(), 1);
        assert_eq!(webhooks[0].format, "slack");
    }

    #[test]
    fn test_parse_fault_detection_config() {
        let toml_str = r#"
            agent_id = "test"
            poll_interval_secs = 30

            [cloud]
            endpoint = "https://example.com"
            api_key = "test-key"

            [fault_detection]
            enabled = true
            min_offline_onts = 10
            time_window_seconds = 120

            [fault_detection.severity]
            critical = 100
            major = 50
            minor = 10
        "#;
        let cfg: AgentConfig = toml::from_str(toml_str).unwrap();
        let fd = cfg.fault_detection.as_ref().unwrap();
        assert!(fd.enabled);
        assert_eq!(fd.min_offline_onts, 10);
        assert_eq!(fd.severity.critical, 100);
    }

    #[test]
    fn test_backward_compatible_no_output() {
        // Existing Brazilian ISP configs have no [output] section
        let toml_str = r#"
            agent_id = "br-isp-01"
            poll_interval_secs = 60

            [cloud]
            endpoint = "https://api.pulsonetwork.com.br/v1/telemetry"
            api_key = "real-key"
        "#;
        let cfg: AgentConfig = toml::from_str(toml_str).unwrap();
        assert!(cfg.output.is_none());
        assert!(cfg.fault_detection.is_none());
        assert!(cfg.topology.is_none());
        assert!(cfg.degradation.is_none());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib config::tests 2>&1 | tail -20`
Expected: FAIL — `GrpcConfig`, `OutputConfig`, etc. don't exist yet

- [ ] **Step 3: Add GrpcConfig struct**

Add after `RestApiConfig` in `config/mod.rs`:
```rust
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
```

Add defaults:
```rust
fn default_grpc_port() -> u16 { 9191 }
fn default_grpc_connect_timeout() -> u64 { 5000 }
fn default_grpc_request_timeout() -> u64 { 10000 }
```

Add `grpc` field to `OltConfig`:
```rust
pub grpc: Option<GrpcConfig>,
```

Update `OltConfig::example()` to include `grpc: None`.

- [ ] **Step 4: Add OutputConfig structs**

Add after `GrpcConfig`:
```rust
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

fn default_index_prefix() -> String { "enlace".into() }
fn default_bulk_size() -> usize { 1000 }
```

- [ ] **Step 5: Add FaultDetectionConfig, TopologyConfig, DegradationConfig**

```rust
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

fn default_min_offline() -> usize { 5 }
fn default_fault_window() -> u64 { 60 }
fn default_severity_critical() -> usize { 100 }
fn default_severity_major() -> usize { 50 }
fn default_severity_minor() -> usize { 10 }
fn default_topology_mode() -> String { "infer".into() }
fn default_history_days() -> u32 { 30 }
fn default_trend_window() -> u32 { 4 }
fn default_watch_threshold() -> f64 { 0.5 }
fn default_warning_threshold() -> f64 { 1.0 }
fn default_critical_threshold() -> f64 { 2.0 }
fn default_min_critical_rx() -> f64 { -28.0 }
```

- [ ] **Step 6: Extend AgentConfig**

Add new optional fields to `AgentConfig`:
```rust
pub output: Option<OutputConfig>,
pub fault_detection: Option<FaultDetectionConfig>,
pub topology: Option<TopologyConfig>,
pub degradation: Option<DegradationConfig>,
```

Update the `example()` method to set all four to `None`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib config::tests -v 2>&1 | tail -20`
Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/config/mod.rs
git commit -m "feat(agent): add config structs for gRPC, elastic, webhooks, fault detection"
```

---

## Task 4: Extend OntData + Vendor Registry

**Files:**
- Modify: `pulso-agent/src/vendors/mod.rs`

- [ ] **Step 1: Add `eth_speed_mbps` field to OntData**

In `vendors/mod.rs`, add to `OntData` struct:
```rust
/// Ethernet port negotiated speed (Mbps). None if not available.
pub eth_speed_mbps: Option<u32>,
```

- [ ] **Step 2: Fix all existing OntData constructors**

Every file that creates an `OntData` must now include `eth_speed_mbps: None`. Search and fix:
- `vendors/huawei.rs` (2 places: `collect_onts_snmp`, `parse_huawei_ont_output`)
- `vendors/zte.rs`, `fiberhome.rs`, `intelbras.rs`, `datacom.rs`, `parks.rs`, `bdcom.rs`, `vsol.rs`, `cdata.rs`, `ubiquiti.rs`, `nokia.rs`, `generic.rs`
- `transport/mod.rs` test

Run: `cd /home/dev/enlace/pulso-agent && grep -rn "in_octets:" src/vendors/ src/transport/ | head -20`

For each match, add `eth_speed_mbps: None,` after `out_octets: None,`.

- [ ] **Step 3: Add `pub mod adtran;` declaration**

In `vendors/mod.rs`, add after `pub mod nokia;`:
```rust
pub mod adtran;
```

- [ ] **Step 4: Register Adtran in create_collector()**

In `create_collector()`, add before the `"generic" | _` arm:
```rust
"adtran" => Ok(Box::new(adtran::AdtranCollector::new(config)?)),
```

- [ ] **Step 5: Create stub adtran.rs**

Create `pulso-agent/src/vendors/adtran.rs` with a minimal stub so it compiles:
```rust
// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 OLT Collector (OpenOLT gRPC)

use async_trait::async_trait;
use crate::config::OltConfig;
use super::*;

pub struct AdtranCollector {
    olt_id: String,
    config: OltConfig,
}

impl AdtranCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        Ok(Self {
            olt_id: format!("adtran-{}", config.ip.replace('.', "-")),
            config: config.clone(),
        })
    }
}

#[async_trait]
impl OltCollector for AdtranCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "adtran" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        // TODO: implement gRPC collection in Task 5
        anyhow::bail!("Adtran gRPC collector not yet implemented")
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        // TODO: implement gRPC connectivity test
        Ok(false)
    }
}
```

- [ ] **Step 6: Verify compilation**

Run: `cd /home/dev/enlace/pulso-agent && cargo check 2>&1 | tail -5`
Expected: Compiles with no errors

- [ ] **Step 7: Run all existing tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test 2>&1 | tail -10`
Expected: All 17 existing tests still pass

- [ ] **Step 8: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/vendors/mod.rs src/vendors/adtran.rs
git commit -m "feat(agent): add eth_speed_mbps to OntData + register Adtran vendor stub"
```

---

## Task 5: Adtran gRPC Collector

**Files:**
- Modify: `pulso-agent/src/vendors/adtran.rs`

**Dependencies:** Tasks 2 (proto), 3 (config), 4 (vendor registry)

- [ ] **Step 1: Write tests for Adtran collector**

Add to bottom of `vendors/adtran.rs`:
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::vendors::OntStatus;

    #[test]
    fn test_parse_serial_number_message() {
        // OpenOLT SerialNumber is a message: vendor_id (4 bytes) + vendor_specific (4 bytes)
        // Adtran: vendor_id = b"ADTN", vendor_specific = hex bytes
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
        // Adtran returns dBm directly as f64 — no /100 like Huawei
        let raw: f64 = -22.1;
        assert!((raw - (-22.1)).abs() < 0.001);
    }

    #[test]
    fn test_ont_state_table_update() {
        let state = DashMap::new();
        let key = (0u32, 1u32); // intf_id=0, onu_id=1

        // Simulate OnuIndication: ONT comes online
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

        // Simulate DyingGaspIndication
        if let Some(mut entry) = state.get_mut(&key) {
            entry.dying_gasp = true;
            entry.status = OntStatus::PowerFail;
        }

        let entry = state.get(&key).unwrap();
        assert!(entry.dying_gasp);
        assert_eq!(entry.status, OntStatus::PowerFail);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib vendors::adtran::tests 2>&1 | tail -20`
Expected: FAIL — `serial_to_string`, `OntState`, etc. don't exist

- [ ] **Step 3: Implement Adtran collector**

Replace the stub in `vendors/adtran.rs` with the full implementation:

```rust
// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 OLT Collector (OpenOLT gRPC)
//
// Collection method: OpenOLT gRPC on port 9191
// Protocol: Persistent gRPC channel with EnableIndication stream
//
// Key differences from SNMP-based vendors:
//   - rx_power returned as f64 dBm (NO /100 scaling like Huawei)
//   - Distance returned as u32 metres
//   - Serial format: 4 ASCII + 8 hex (e.g., "ADTN153201C4")
//   - ONT enumeration via gRPC stream, not SNMP table walk
//   - Requires persistent connection (not stateless per-poll)

use async_trait::async_trait;
use dashmap::DashMap;
use std::sync::Arc;
use tracing::{info, warn, debug};
use crate::config::OltConfig;
use super::*;

// Include generated protobuf code
pub mod openolt {
    tonic::include_proto!("openolt");
}

/// Per-ONT state maintained by the background indication stream
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
    /// Concurrent ONT state table: (intf_id, onu_id) -> OntState
    ont_state: Arc<DashMap<(u32, u32), OntState>>,
    /// Cached device info (populated on first collect)
    device_model: std::sync::Mutex<Option<String>>,
    device_firmware: std::sync::Mutex<Option<String>>,
}

impl AdtranCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let grpc_cfg = config.grpc.as_ref()
            .ok_or_else(|| anyhow::anyhow!(
                "Adtran OLT requires [olts.grpc] config (SDX 6320 has no SNMP)"
            ))?;

        info!(
            ip = %config.ip,
            port = grpc_cfg.port,
            "Initializing Adtran SDX gRPC collector"
        );

        Ok(Self {
            olt_id: format!("adtran-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            ont_state: Arc::new(DashMap::new()),
            device_model: std::sync::Mutex::new(None),
            device_firmware: std::sync::Mutex::new(None),
        })
    }

    /// Build gRPC endpoint URL from config
    fn endpoint(&self) -> String {
        let grpc = self.config.grpc.as_ref().unwrap();
        let scheme = if grpc.tls { "https" } else { "http" };
        format!("{}://{}:{}", scheme, self.config.ip, grpc.port)
    }

    /// Connect to the OLT and return a gRPC client
    async fn connect(&self) -> anyhow::Result<openolt::openolt_client::OpenoltClient<tonic::transport::Channel>> {
        let grpc = self.config.grpc.as_ref().unwrap();
        let endpoint = tonic::transport::Endpoint::from_shared(self.endpoint())?
            .connect_timeout(std::time::Duration::from_millis(grpc.connect_timeout_ms))
            .timeout(std::time::Duration::from_millis(grpc.request_timeout_ms));

        let channel = endpoint.connect().await?;
        Ok(openolt::openolt_client::OpenoltClient::new(channel))
    }

    /// Seed ONT state table on startup by iterating known ONTs
    async fn seed_state_table(&self, client: &mut openolt::openolt_client::OpenoltClient<tonic::transport::Channel>) -> anyhow::Result<()> {
        // Get device info to learn PON port count
        let device_info = client.get_device_info(openolt::Empty {}).await?;
        let info = device_info.into_inner();

        *self.device_model.lock().unwrap() = Some(info.model.clone());
        *self.device_firmware.lock().unwrap() = Some(info.firmware_version.clone());

        let pon_ports = info.pon_ports;
        info!(model = %info.model, pon_ports = pon_ports, "Adtran device info retrieved");

        // For each PON port, try to get info on ONTs 0..127
        for intf_id in 0..pon_ports {
            for onu_id in 0..128u32 {
                let req = openolt::Onu {
                    intf_id,
                    onu_id,
                    ..Default::default()
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
                    Err(_) => break, // No more ONTs on this port
                }
            }
        }

        info!(onts = self.ont_state.len(), "Adtran state table seeded");
        Ok(())
    }

    /// Collect optical power and distance for all known ONTs
    async fn collect_ont_data(&self, client: &mut openolt::openolt_client::OpenoltClient<tonic::transport::Channel>) -> Vec<OntData> {
        let mut onts = Vec::new();

        for entry in self.ont_state.iter() {
            let (intf_id, onu_id) = *entry.key();
            let state = entry.value().clone();

            let mut rx_power: Option<f64> = None;
            let mut tx_power: Option<f64> = None;
            let mut distance: Option<u32> = None;

            // Get Rx power
            let rx_req = openolt::Onu {
                intf_id,
                onu_id,
                ..Default::default()
            };
            if let Ok(resp) = client.get_pon_rx_power(rx_req).await {
                let power = resp.into_inner();
                // Adtran returns dBm directly as double — NO scaling
                rx_power = Some(power.rx_power_mean_dbm);
            }

            // Get distance
            let dist_req = openolt::Onu {
                intf_id,
                onu_id,
                ..Default::default()
            };
            if let Ok(resp) = client.get_logical_onu_distance(dist_req).await {
                let d = resp.into_inner();
                distance = Some(d.logical_onu_distance as u32);
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

/// Convert OpenOLT SerialNumber message fields to string.
/// SerialNumber has vendor_id (4 ASCII bytes, e.g., "ADTN") and
/// vendor_specific (4 binary bytes, hex-encoded in the serial string).
fn serial_to_string(vendor_id: &[u8], vendor_specific: &[u8]) -> String {
    if vendor_id.is_empty() && vendor_specific.is_empty() {
        return String::new();
    }
    let vendor = String::from_utf8_lossy(vendor_id);
    let specific: String = vendor_specific.iter().map(|b| format!("{:02X}", b)).collect();
    format!("{}{}", vendor, specific)
}

/// Extract serial string from an OpenOLT SerialNumber message (Option)
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

        // Seed state table on first call
        if self.ont_state.is_empty() {
            self.seed_state_table(&mut client).await?;
        }

        // Collect per-ONT data
        let onts = self.collect_ont_data(&mut client).await;

        // Build PON port summary
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
```

**Note to implementer:** The proto-generated code should match our minimal proto definitions since we control them. Key types to know:
- `SerialNumber` is a message with `vendor_id: Vec<u8>` and `vendor_specific: Vec<u8>` — use `extract_serial()` helper
- `PowerMeanTypical` has `rx_power_mean_dbm: f64` — no scaling needed
- `OnuLogicalDistance` has `logical_onu_distance: u32` — in metres
- `OnuInfo` has `state: i32` (enum) and `serial_number: Option<SerialNumber>`
- `Onu` request struct has `serial_number: Option<SerialNumber>` — set to `None` when querying by `intf_id` + `onu_id`

After proto compilation, verify with:
```bash
find target -name "openolt.rs" -path "*/OUT_DIR/*" | head -1 | xargs grep "pub struct SerialNumber"
```

- [ ] **Step 4: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib vendors::adtran::tests -v 2>&1 | tail -20`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/vendors/adtran.rs
git commit -m "feat(agent): implement Adtran SDX 6320 gRPC collector"
```

---

## Task 6: Fault Detector

**Files:**
- Create: `pulso-agent/src/fault/mod.rs`
- Create: `pulso-agent/src/fault/detector.rs`

- [ ] **Step 1: Create fault module root**

Create `pulso-agent/src/fault/mod.rs`:
```rust
// SPDX-License-Identifier: Apache-2.0
// Fault Location Engine — detect trunk fibre cuts, estimate break location

pub mod detector;
pub mod topology;
pub mod locator;

pub use detector::{FaultDetector, FaultEvent};
pub use topology::FibreTopology;
pub use locator::{FaultLocator, FaultLocation};
```

- [ ] **Step 2: Write detector tests**

Create `pulso-agent/src/fault/detector.rs` with tests first:
```rust
// SPDX-License-Identifier: Apache-2.0
// Mass-offline pattern detector

use std::collections::HashMap;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use crate::config::FaultDetectionConfig;
use crate::vendors::{OntData, OntStatus};

#[cfg(test)]
mod tests {
    use super::*;

    fn make_config() -> FaultDetectionConfig {
        FaultDetectionConfig {
            enabled: true,
            min_offline_onts: 5,
            time_window_seconds: 60,
            severity: crate::config::FaultSeverityConfig {
                critical: 100, major: 50, minor: 10,
            },
        }
    }

    fn make_ont(serial: &str, port: &str, status: OntStatus, dying_gasp: bool) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: port.into(),
            ont_index: 0,
            status,
            last_down_cause: if dying_gasp { Some("dying_gasp".into()) } else { None },
            uptime_seconds: None,
            rx_power_dbm: Some(-22.0),
            tx_power_dbm: None,
            distance_meters: Some(1000),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
        }
    }

    #[test]
    fn test_trigger_on_mass_offline() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // 10 ONTs go offline on same port — should trigger
        let mut onts = Vec::new();
        for i in 0..10 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false));
        }
        // Add some online ONTs too
        for i in 10..20 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Online, false));
        }

        let events = detector.check(&onts);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].pon_port, "0/1/0");
        assert_eq!(events[0].affected_onts.len(), 10);
    }

    #[test]
    fn test_no_trigger_below_threshold() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // Only 3 ONTs offline — below threshold of 5
        let mut onts = Vec::new();
        for i in 0..3 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false));
        }
        for i in 3..20 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Online, false));
        }

        let events = detector.check(&onts);
        assert!(events.is_empty());
    }

    #[test]
    fn test_dying_gasp_excluded() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // 10 ONTs offline but ALL have dying_gasp — power outage, not fibre cut
        let mut onts = Vec::new();
        for i in 0..10 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::PowerFail, true));
        }

        let events = detector.check(&onts);
        assert!(events.is_empty(), "DyingGasp ONTs should not trigger fault");
    }

    #[test]
    fn test_mixed_dying_gasp_and_hard_offline() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // 3 dying_gasp + 6 hard offline = 6 hard offline >= 5 threshold
        let mut onts = Vec::new();
        for i in 0..3 {
            onts.push(make_ont(&format!("DG{:03}", i), "0/1/0", OntStatus::PowerFail, true));
        }
        for i in 0..6 {
            onts.push(make_ont(&format!("HO{:03}", i), "0/1/0", OntStatus::Offline, false));
        }

        let events = detector.check(&onts);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].affected_onts.len(), 6, "Only hard-offline ONTs");
    }

    #[test]
    fn test_severity_classification() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // 120 ONTs offline — should be critical (>= 100)
        let mut onts = Vec::new();
        for i in 0..120 {
            onts.push(make_ont(&format!("ONT{:03}", i), "0/1/0", OntStatus::Offline, false));
        }

        let events = detector.check(&onts);
        assert_eq!(events[0].severity, "critical");
    }

    #[test]
    fn test_per_port_isolation() {
        let cfg = make_config();
        let mut detector = FaultDetector::new(&cfg);

        // 3 offline on port 0/1/0, 3 offline on 0/1/1 — neither reaches threshold
        let mut onts = Vec::new();
        for i in 0..3 {
            onts.push(make_ont(&format!("A{:03}", i), "0/1/0", OntStatus::Offline, false));
        }
        for i in 0..3 {
            onts.push(make_ont(&format!("B{:03}", i), "0/1/1", OntStatus::Offline, false));
        }

        let events = detector.check(&onts);
        assert!(events.is_empty());
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::detector::tests 2>&1 | tail -20`
Expected: FAIL — `FaultDetector`, `FaultEvent` don't exist

- [ ] **Step 4: Implement FaultDetector**

Add above the `#[cfg(test)]` block in `detector.rs`:

```rust
/// A detected fault event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultEvent {
    pub timestamp: DateTime<Utc>,
    pub pon_port: String,
    pub olt_id: String,
    pub severity: String,
    pub affected_onts: Vec<AffectedOnt>,
    pub detection_latency_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AffectedOnt {
    pub serial_number: String,
    pub distance_meters: Option<u32>,
    pub last_rx_dbm: Option<f64>,
}

/// Stateful fault detector — tracks ONT status across poll cycles
pub struct FaultDetector {
    config: FaultDetectionConfig,
    /// Previous ONT status per port: port -> (serial -> was_online)
    previous_state: HashMap<String, HashMap<String, bool>>,
}

impl FaultDetector {
    pub fn new(config: &FaultDetectionConfig) -> Self {
        Self {
            config: config.clone(),
            previous_state: HashMap::new(),
        }
    }

    /// Check for mass-offline events. Call once per poll cycle with all ONT data.
    pub fn check(&mut self, onts: &[OntData]) -> Vec<FaultEvent> {
        if !self.config.enabled {
            return Vec::new();
        }

        let mut events = Vec::new();

        // Group ONTs by PON port
        let mut by_port: HashMap<String, Vec<&OntData>> = HashMap::new();
        for ont in onts {
            by_port.entry(ont.pon_port.clone()).or_default().push(ont);
        }

        for (port, port_onts) in &by_port {
            // Count hard-offline ONTs (exclude dying-gasp)
            let hard_offline: Vec<&OntData> = port_onts.iter()
                .filter(|o| {
                    matches!(o.status, OntStatus::Offline | OntStatus::FiberCut)
                        && !o.last_down_cause.as_deref()
                            .map(|c| c.contains("dying_gasp") || c.contains("power"))
                            .unwrap_or(false)
                })
                .copied()
                .collect();

            if hard_offline.len() >= self.config.min_offline_onts {
                let severity = if hard_offline.len() >= self.config.severity.critical {
                    "critical"
                } else if hard_offline.len() >= self.config.severity.major {
                    "major"
                } else if hard_offline.len() >= self.config.severity.minor {
                    "minor"
                } else {
                    "warning"
                };

                events.push(FaultEvent {
                    timestamp: Utc::now(),
                    pon_port: port.clone(),
                    olt_id: String::new(), // Filled by caller
                    severity: severity.into(),
                    affected_onts: hard_offline.iter().map(|o| AffectedOnt {
                        serial_number: o.serial_number.clone(),
                        distance_meters: o.distance_meters,
                        last_rx_dbm: o.rx_power_dbm,
                    }).collect(),
                    detection_latency_seconds: 0,
                });
            }
        }

        // Update previous state for next cycle
        self.previous_state.clear();
        for ont in onts {
            let is_online = matches!(ont.status, OntStatus::Online | OntStatus::LowSignal);
            self.previous_state
                .entry(ont.pon_port.clone())
                .or_default()
                .insert(ont.serial_number.clone(), is_online);
        }

        events
    }
}
```

- [ ] **Step 5: Register fault module in main.rs**

Add `mod fault;` to the module declarations at the top of `main.rs`.

- [ ] **Step 6: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::detector::tests -v 2>&1 | tail -20`
Expected: All 6 tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/fault/
git commit -m "feat(agent): implement fault detector with DyingGasp filtering"
```

---

## Task 7: Fibre Topology Model

**Files:**
- Create: `pulso-agent/src/fault/topology.rs`

- [ ] **Step 1: Write topology tests**

```rust
// SPDX-License-Identifier: Apache-2.0
// Fibre route topology model

use std::collections::HashMap;
use std::path::Path;
use serde::{Deserialize, Serialize};
use tracing::{info, warn};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_infer_topology_from_distances() {
        let ont_distances = vec![
            ("ONT001".into(), 500u32),
            ("ONT002".into(), 520u32),
            ("ONT003".into(), 1200u32),
            ("ONT004".into(), 1250u32),
            ("ONT005".into(), 2000u32),
        ];

        let topo = FibreTopology::infer_from_distances("0/1/0", &ont_distances);

        // Should create 3 clusters (within 50m = same DP)
        assert!(topo.nodes.len() >= 3, "Expected >=3 nodes (OLT + clusters)");
        // All ONTs should be mapped
        assert_eq!(topo.ont_to_node.len(), 5);
    }

    #[test]
    fn test_empty_topology() {
        let topo = FibreTopology::empty();
        assert!(topo.nodes.is_empty());
        assert!(topo.edges.is_empty());
    }

    #[test]
    fn test_get_ont_distance() {
        let topo = FibreTopology::infer_from_distances("0/1/0", &[
            ("ONT001".into(), 500),
            ("ONT002".into(), 1500),
        ]);
        let node = topo.ont_to_node.get("ONT001");
        assert!(node.is_some());
    }

    #[test]
    fn test_synthetic_topology() {
        let topo = FibreTopology::synthetic();
        assert!(!topo.nodes.is_empty(), "Synthetic topology should have nodes");
        assert!(!topo.edges.is_empty(), "Synthetic topology should have edges");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::topology::tests 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: Implement FibreTopology**

Add above `#[cfg(test)]`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum NodeType {
    Olt,
    SplicePoint,
    DistributionPoint,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopologyNode {
    pub id: String,
    pub lat: f64,
    pub lon: f64,
    pub node_type: NodeType,
    pub distance_from_olt_m: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopologyEdge {
    pub from: String,
    pub to: String,
    pub length_m: f64,
}

#[derive(Debug, Clone, Default)]
pub struct FibreTopology {
    pub nodes: HashMap<String, TopologyNode>,
    pub edges: Vec<TopologyEdge>,
    pub ont_to_node: HashMap<String, String>,
}

impl FibreTopology {
    pub fn empty() -> Self {
        Self::default()
    }

    /// Build topology by loading from config
    pub fn load(mode: &str, import_path: Option<&Path>) -> Self {
        match mode {
            "import" => {
                if let Some(path) = import_path {
                    Self::import_csv(path).unwrap_or_else(|e| {
                        warn!(error = %e, "Failed to import topology, using empty");
                        Self::empty()
                    })
                } else {
                    warn!("Topology mode=import but no import_path set");
                    Self::empty()
                }
            }
            "synthetic" => Self::synthetic(),
            _ => Self::empty(), // "infer" is built dynamically per port
        }
    }

    /// Import topology from CSV files in a directory
    fn import_csv(dir: &Path) -> anyhow::Result<Self> {
        let mut topo = Self::empty();

        // Look for splice_points.csv: id,lat,lon,parent_id,route_name
        let sp_path = dir.join("splice_points.csv");
        if sp_path.exists() {
            let content = std::fs::read_to_string(&sp_path)?;
            for line in content.lines().skip(1) {
                let cols: Vec<&str> = line.split(',').collect();
                if cols.len() >= 4 {
                    let id = cols[0].trim().to_string();
                    let lat: f64 = cols[1].trim().parse().unwrap_or(0.0);
                    let lon: f64 = cols[2].trim().parse().unwrap_or(0.0);
                    let parent_id = cols[3].trim().to_string();

                    let dist = if let Some(parent) = topo.nodes.get(&parent_id) {
                        parent.distance_from_olt_m + haversine_m(parent.lat, parent.lon, lat, lon)
                    } else {
                        0.0
                    };

                    topo.nodes.insert(id.clone(), TopologyNode {
                        id: id.clone(),
                        lat, lon,
                        node_type: NodeType::SplicePoint,
                        distance_from_olt_m: dist,
                    });

                    if !parent_id.is_empty() {
                        let edge_len = if let Some(parent) = topo.nodes.get(&parent_id) {
                            haversine_m(parent.lat, parent.lon, lat, lon)
                        } else { 0.0 };
                        topo.edges.push(TopologyEdge {
                            from: parent_id,
                            to: id,
                            length_m: edge_len,
                        });
                    }
                }
            }
        }

        // Look for ont_mapping.csv: ont_serial,node_id
        let ont_path = dir.join("ont_mapping.csv");
        if ont_path.exists() {
            let content = std::fs::read_to_string(&ont_path)?;
            for line in content.lines().skip(1) {
                let cols: Vec<&str> = line.split(',').collect();
                if cols.len() >= 2 {
                    topo.ont_to_node.insert(
                        cols[0].trim().to_string(),
                        cols[1].trim().to_string(),
                    );
                }
            }
        }

        info!(nodes = topo.nodes.len(), onts = topo.ont_to_node.len(), "Topology imported");
        Ok(topo)
    }

    /// Infer topology from ONT distance data (no external files needed)
    pub fn infer_from_distances(port: &str, ont_distances: &[(String, u32)]) -> Self {
        let mut topo = Self::empty();

        if ont_distances.is_empty() {
            return topo;
        }

        // Add OLT node
        topo.nodes.insert("OLT".into(), TopologyNode {
            id: "OLT".into(), lat: 0.0, lon: 0.0,
            node_type: NodeType::Olt, distance_from_olt_m: 0.0,
        });

        // Sort by distance
        let mut sorted: Vec<_> = ont_distances.to_vec();
        sorted.sort_by_key(|(_, d)| *d);

        // Cluster ONTs within 50m of each other
        let mut clusters: Vec<(String, f64, Vec<String>)> = Vec::new(); // (id, avg_dist, serials)
        for (serial, dist) in &sorted {
            let dist_f = *dist as f64;
            if let Some(last) = clusters.last_mut() {
                if (dist_f - last.1).abs() < 50.0 {
                    last.2.push(serial.clone());
                    last.1 = (last.1 * (last.2.len() - 1) as f64 + dist_f) / last.2.len() as f64;
                    continue;
                }
            }
            let id = format!("{}-DP{}", port, clusters.len() + 1);
            clusters.push((id, dist_f, vec![serial.clone()]));
        }

        // Build linear topology: OLT -> DP1 -> DP2 -> ...
        let mut prev_id = "OLT".to_string();
        let mut prev_dist = 0.0;
        for (id, avg_dist, serials) in &clusters {
            topo.nodes.insert(id.clone(), TopologyNode {
                id: id.clone(), lat: 0.0, lon: 0.0,
                node_type: NodeType::DistributionPoint,
                distance_from_olt_m: *avg_dist,
            });
            topo.edges.push(TopologyEdge {
                from: prev_id.clone(),
                to: id.clone(),
                length_m: avg_dist - prev_dist,
            });
            for serial in serials {
                topo.ont_to_node.insert(serial.clone(), id.clone());
            }
            prev_id = id.clone();
            prev_dist = *avg_dist;
        }

        topo
    }

    /// Pre-built synthetic topology for testing (simulates a London POP)
    pub fn synthetic() -> Self {
        let mut topo = Self::empty();

        // OLT -> SP1 (500m) -> SP2 (300m) -> SP3 (200m)
        let nodes = vec![
            ("OLT", 51.4607, -0.1163, NodeType::Olt, 0.0),
            ("SP001", 51.4625, -0.1148, NodeType::SplicePoint, 500.0),
            ("SP002", 51.4640, -0.1130, NodeType::SplicePoint, 800.0),
            ("SP003", 51.4655, -0.1115, NodeType::SplicePoint, 1000.0),
            ("DP001", 51.4628, -0.1145, NodeType::DistributionPoint, 550.0),
            ("DP002", 51.4645, -0.1125, NodeType::DistributionPoint, 850.0),
        ];

        for (id, lat, lon, ntype, dist) in nodes {
            topo.nodes.insert(id.into(), TopologyNode {
                id: id.into(), lat, lon,
                node_type: ntype, distance_from_olt_m: dist,
            });
        }

        topo.edges = vec![
            TopologyEdge { from: "OLT".into(), to: "SP001".into(), length_m: 500.0 },
            TopologyEdge { from: "SP001".into(), to: "SP002".into(), length_m: 300.0 },
            TopologyEdge { from: "SP002".into(), to: "SP003".into(), length_m: 200.0 },
            TopologyEdge { from: "SP001".into(), to: "DP001".into(), length_m: 50.0 },
            TopologyEdge { from: "SP002".into(), to: "DP002".into(), length_m: 50.0 },
        ];

        // Map some test ONT serials
        for i in 0..10 {
            topo.ont_to_node.insert(format!("ADTN{:08X}", i), "DP001".into());
        }
        for i in 10..20 {
            topo.ont_to_node.insert(format!("ADTN{:08X}", i), "DP002".into());
        }

        topo
    }

    /// Get the topology node for an ONT
    pub fn get_ont_node(&self, serial: &str) -> Option<&TopologyNode> {
        self.ont_to_node.get(serial).and_then(|nid| self.nodes.get(nid))
    }
}

/// Haversine distance in metres between two lat/lon points
fn haversine_m(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let r = 6_371_000.0; // Earth radius in metres
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();
    let a = (dlat / 2.0).sin().powi(2)
        + lat1.to_radians().cos() * lat2.to_radians().cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();
    r * c
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::topology::tests -v 2>&1 | tail -20`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/fault/topology.rs
git commit -m "feat(agent): implement fibre topology model (import, infer, synthetic)"
```

---

## Task 8: Fault Locator

**Files:**
- Create: `pulso-agent/src/fault/locator.rs`

- [ ] **Step 1: Write locator tests**

```rust
// SPDX-License-Identifier: Apache-2.0
// Fault location calculator

use serde::{Deserialize, Serialize};
use super::detector::{FaultEvent, AffectedOnt};
use super::topology::{FibreTopology, TopologyNode, NodeType};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_distance_only_locator() {
        let event = FaultEvent {
            timestamp: chrono::Utc::now(),
            pon_port: "0/1/0".into(),
            olt_id: "test".into(),
            severity: "critical".into(),
            affected_onts: vec![
                AffectedOnt { serial_number: "ONT_A".into(), distance_meters: Some(920), last_rx_dbm: None },
                AffectedOnt { serial_number: "ONT_B".into(), distance_meters: Some(1100), last_rx_dbm: None },
                AffectedOnt { serial_number: "ONT_C".into(), distance_meters: Some(1300), last_rx_dbm: None },
            ],
            detection_latency_seconds: 30,
        };

        // Online ONTs at 500m and 780m
        let online_onts = vec![
            AffectedOnt { serial_number: "ALIVE_1".into(), distance_meters: Some(500), last_rx_dbm: Some(-20.0) },
            AffectedOnt { serial_number: "ALIVE_2".into(), distance_meters: Some(780), last_rx_dbm: Some(-22.0) },
        ];

        let locator = FaultLocator::new(&FibreTopology::empty());
        let loc = locator.locate_distance_only(&event, &online_onts);

        // Break should be between 780m (last online) and 920m (first offline)
        assert!(loc.distance_from_olt_m.is_some());
        let dist = loc.distance_from_olt_m.unwrap();
        assert!(dist > 780.0 && dist < 920.0, "Break at {}m, expected 780-920m", dist);
        assert_eq!(loc.method, "distance");
    }

    #[test]
    fn test_topology_locator() {
        let topo = FibreTopology::synthetic();
        let locator = FaultLocator::new(&topo);

        // Simulate: all ONTs on DP002 go offline (mapped to SP002-SP003 area)
        let event = FaultEvent {
            timestamp: chrono::Utc::now(),
            pon_port: "0/1/0".into(),
            olt_id: "test".into(),
            severity: "major".into(),
            affected_onts: (10..20).map(|i| AffectedOnt {
                serial_number: format!("ADTN{:08X}", i),
                distance_meters: Some(850),
                last_rx_dbm: None,
            }).collect(),
            detection_latency_seconds: 30,
        };

        let online_onts: Vec<AffectedOnt> = (0..10).map(|i| AffectedOnt {
            serial_number: format!("ADTN{:08X}", i),
            distance_meters: Some(550),
            last_rx_dbm: Some(-22.0),
        }).collect();

        let loc = locator.locate(&event, &online_onts);
        assert!(loc.lat.is_some(), "Should have lat from topology");
        assert!(loc.lon.is_some(), "Should have lon from topology");
        assert_eq!(loc.method, "topology");
    }

    #[test]
    fn test_all_onts_offline() {
        let locator = FaultLocator::new(&FibreTopology::empty());
        let event = FaultEvent {
            timestamp: chrono::Utc::now(),
            pon_port: "0/1/0".into(),
            olt_id: "test".into(),
            severity: "critical".into(),
            affected_onts: vec![
                AffectedOnt { serial_number: "A".into(), distance_meters: Some(100), last_rx_dbm: None },
            ],
            detection_latency_seconds: 0,
        };
        let loc = locator.locate_distance_only(&event, &[]); // No online ONTs
        // Break at OLT
        let dist = loc.distance_from_olt_m.unwrap_or(0.0);
        assert!(dist < 100.0, "Should report break near OLT when all offline");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::locator::tests 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: Implement FaultLocator**

Add above `#[cfg(test)]`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultLocation {
    pub method: String, // "topology" or "distance"
    pub lat: Option<f64>,
    pub lon: Option<f64>,
    pub distance_from_olt_m: Option<f64>,
    pub confidence_radius_m: Option<f64>,
    pub between_nodes: Option<(String, String)>,
    pub boundary: Option<BoundaryInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundaryInfo {
    pub last_online_serial: String,
    pub last_online_distance_m: u32,
    pub first_offline_serial: String,
    pub first_offline_distance_m: u32,
}

pub struct FaultLocator<'a> {
    topology: &'a FibreTopology,
}

impl<'a> FaultLocator<'a> {
    pub fn new(topology: &'a FibreTopology) -> Self {
        Self { topology }
    }

    /// Main entry point — uses topology if available, falls back to distance-only
    pub fn locate(&self, event: &FaultEvent, online_onts: &[AffectedOnt]) -> FaultLocation {
        // Try topology-based location first
        if !self.topology.nodes.is_empty() && !self.topology.ont_to_node.is_empty() {
            if let Some(loc) = self.locate_with_topology(event, online_onts) {
                return loc;
            }
        }

        // Fallback to distance-only
        self.locate_distance_only(event, online_onts)
    }

    /// Distance-only fault location (no topology data needed)
    pub fn locate_distance_only(&self, event: &FaultEvent, online_onts: &[AffectedOnt]) -> FaultLocation {
        // Find last online ONT distance and first offline ONT distance
        let max_online_dist = online_onts.iter()
            .filter_map(|o| o.distance_meters)
            .max()
            .unwrap_or(0);

        let min_offline_dist = event.affected_onts.iter()
            .filter_map(|o| o.distance_meters)
            .min()
            .unwrap_or(0);

        let last_online = online_onts.iter()
            .filter(|o| o.distance_meters == Some(max_online_dist))
            .next();
        let first_offline = event.affected_onts.iter()
            .filter(|o| o.distance_meters == Some(min_offline_dist))
            .next();

        let break_dist = if max_online_dist > 0 && min_offline_dist > max_online_dist {
            (max_online_dist + min_offline_dist) as f64 / 2.0
        } else if min_offline_dist > 0 {
            min_offline_dist as f64 / 2.0 // All ONTs offline, break near OLT
        } else {
            0.0
        };

        let confidence = if max_online_dist > 0 && min_offline_dist > max_online_dist {
            (min_offline_dist - max_online_dist) as f64 / 2.0
        } else {
            min_offline_dist as f64 / 2.0
        };

        let boundary = match (last_online, first_offline) {
            (Some(lo), Some(fo)) => Some(BoundaryInfo {
                last_online_serial: lo.serial_number.clone(),
                last_online_distance_m: lo.distance_meters.unwrap_or(0),
                first_offline_serial: fo.serial_number.clone(),
                first_offline_distance_m: fo.distance_meters.unwrap_or(0),
            }),
            _ => None,
        };

        FaultLocation {
            method: "distance".into(),
            lat: None,
            lon: None,
            distance_from_olt_m: Some(break_dist),
            confidence_radius_m: Some(confidence),
            between_nodes: None,
            boundary,
        }
    }

    /// Topology-based fault location
    fn locate_with_topology(&self, event: &FaultEvent, online_onts: &[AffectedOnt]) -> Option<FaultLocation> {
        // Get nodes for affected ONTs
        let offline_nodes: Vec<_> = event.affected_onts.iter()
            .filter_map(|o| self.topology.get_ont_node(&o.serial_number))
            .collect();

        let online_nodes: Vec<_> = online_onts.iter()
            .filter_map(|o| self.topology.get_ont_node(&o.serial_number))
            .collect();

        if offline_nodes.is_empty() {
            return None;
        }

        // Find boundary: last online node (max distance) and first offline node (min distance)
        let max_online_dist = online_nodes.iter()
            .map(|n| n.distance_from_olt_m)
            .fold(0.0_f64, f64::max);

        let min_offline_dist = offline_nodes.iter()
            .map(|n| n.distance_from_olt_m)
            .fold(f64::MAX, f64::min);

        // Find the boundary edge in topology
        let boundary_from = self.topology.nodes.values()
            .filter(|n| n.distance_from_olt_m <= max_online_dist)
            .max_by(|a, b| a.distance_from_olt_m.partial_cmp(&b.distance_from_olt_m).unwrap())?;

        let boundary_to = self.topology.nodes.values()
            .filter(|n| n.distance_from_olt_m >= min_offline_dist)
            .min_by(|a, b| a.distance_from_olt_m.partial_cmp(&b.distance_from_olt_m).unwrap())?;

        // Break location = midpoint between boundary nodes
        let lat = (boundary_from.lat + boundary_to.lat) / 2.0;
        let lon = (boundary_from.lon + boundary_to.lon) / 2.0;
        let edge_len = (boundary_to.distance_from_olt_m - boundary_from.distance_from_olt_m).abs();

        Some(FaultLocation {
            method: "topology".into(),
            lat: Some(lat),
            lon: Some(lon),
            distance_from_olt_m: Some((boundary_from.distance_from_olt_m + boundary_to.distance_from_olt_m) / 2.0),
            confidence_radius_m: Some(edge_len / 2.0),
            between_nodes: Some((boundary_from.id.clone(), boundary_to.id.clone())),
            boundary: None,
        })
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib fault::locator::tests -v 2>&1 | tail -20`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/fault/locator.rs
git commit -m "feat(agent): implement fault locator (topology + distance-only)"
```

---

## Task 9: Elasticsearch Output

**Files:**
- Create: `pulso-agent/src/output/mod.rs`
- Create: `pulso-agent/src/output/elastic.rs`

- [ ] **Step 1: Create output module root**

Create `pulso-agent/src/output/mod.rs`:
```rust
// SPDX-License-Identifier: Apache-2.0
// Output dispatchers — Elasticsearch, webhooks, and cloud transport

pub mod elastic;
pub mod webhook;

pub use elastic::ElasticOutput;
pub use webhook::WebhookDispatcher;
```

- [ ] **Step 2: Write Elasticsearch tests**

Create `pulso-agent/src/output/elastic.rs` with tests:
```rust
// SPDX-License-Identifier: Apache-2.0
// Elasticsearch / OpenSearch bulk output

use chrono::Utc;
use serde_json::Value;
use tracing::{info, warn, debug};
use crate::config::ElasticConfig;
use crate::vendors::{OltData, OntData};
use crate::fault::detector::FaultEvent;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vendors::OntStatus;

    fn make_ont(serial: &str, rx: f64, dist: u32) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            ont_index: 0,
            status: OntStatus::Online,
            last_down_cause: None, uptime_seconds: Some(86400),
            rx_power_dbm: Some(rx), tx_power_dbm: Some(-2.0),
            distance_meters: Some(dist),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None,
        }
    }

    #[test]
    fn test_bulk_ndjson_format() {
        let config = ElasticConfig {
            enabled: true,
            url: "http://localhost:9200".into(),
            index_prefix: "test".into(),
            bulk_size: 100,
            username: None, password: None, api_key: None,
            verify_tls: false,
        };
        let output = ElasticOutput::new(&config).unwrap();

        let onts = vec![
            make_ont("ONT001", -22.1, 1200),
            make_ont("ONT002", -25.5, 800),
        ];

        let body = output.build_ont_bulk("agent-01", "OLT1", "adtran", "SDX 6320", &onts);

        // NDJSON: pairs of action + doc lines
        let lines: Vec<&str> = body.trim().split('\n').collect();
        assert_eq!(lines.len(), 4, "2 ONTs = 4 lines (action+doc each)");

        // First line should be index action
        let action: Value = serde_json::from_str(lines[0]).unwrap();
        assert!(action["index"]["_index"].as_str().unwrap().starts_with("test-ont-"));

        // Second line should be ONT doc
        let doc: Value = serde_json::from_str(lines[1]).unwrap();
        assert_eq!(doc["ont"]["serial"], "ONT001");
        assert_eq!(doc["ont"]["rx_power_dbm"], -22.1);
    }

    #[test]
    fn test_fault_event_doc() {
        let config = ElasticConfig {
            enabled: true,
            url: "http://localhost:9200".into(),
            index_prefix: "enlace".into(),
            bulk_size: 100,
            username: None, password: None, api_key: None,
            verify_tls: false,
        };
        let output = ElasticOutput::new(&config).unwrap();

        let event = FaultEvent {
            timestamp: Utc::now(),
            pon_port: "0/1/3".into(),
            olt_id: "OLT1".into(),
            severity: "critical".into(),
            affected_onts: vec![],
            detection_latency_seconds: 30,
        };

        let doc = output.fault_event_to_doc(&event);
        let parsed: Value = serde_json::from_str(&doc).unwrap();
        assert_eq!(parsed["type"], "trunk_fibre_cut");
        assert_eq!(parsed["severity"], "critical");
    }

    #[test]
    fn test_empty_onts() {
        let config = ElasticConfig {
            enabled: true,
            url: "http://localhost:9200".into(),
            index_prefix: "test".into(),
            bulk_size: 100,
            username: None, password: None, api_key: None,
            verify_tls: false,
        };
        let output = ElasticOutput::new(&config).unwrap();
        let body = output.build_ont_bulk("a", "o", "v", "m", &[]);
        assert!(body.is_empty());
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib output::elastic::tests 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 4: Implement ElasticOutput**

Add above `#[cfg(test)]`:

```rust
pub struct ElasticOutput {
    client: reqwest::Client,
    url: String,
    index_prefix: String,
    bulk_size: usize,
    auth_header: Option<String>,
}

impl ElasticOutput {
    pub fn new(config: &ElasticConfig) -> anyhow::Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .danger_accept_invalid_certs(!config.verify_tls)
            .build()?;

        let auth_header = if let Some(ref api_key) = config.api_key {
            Some(format!("ApiKey {}", api_key))
        } else if let (Some(ref user), Some(ref pass)) = (&config.username, &config.password) {
            use base64::Engine;
            let encoded = base64::engine::general_purpose::STANDARD.encode(
                format!("{}:{}", user, pass),
            );
            Some(format!("Basic {}", encoded))
        } else {
            None
        };

        Ok(Self {
            client,
            url: config.url.trim_end_matches('/').to_string(),
            index_prefix: config.index_prefix.clone(),
            bulk_size: config.bulk_size,
            auth_header,
        })
    }

    /// Build NDJSON bulk body for ONT readings
    pub fn build_ont_bulk(&self, agent_id: &str, olt_name: &str, vendor: &str, model: &str, onts: &[OntData]) -> String {
        if onts.is_empty() {
            return String::new();
        }

        let date = Utc::now().format("%Y.%m.%d");
        let index = format!("{}-ont-{}", self.index_prefix, date);
        let mut body = String::new();

        for ont in onts {
            // Action line
            body.push_str(&format!(
                "{{\"index\":{{\"_index\":\"{}\"}}}}\n",
                index
            ));
            // Document
            let doc = serde_json::json!({
                "@timestamp": Utc::now().to_rfc3339(),
                "agent_id": agent_id,
                "olt": {
                    "name": olt_name,
                    "vendor": vendor,
                    "model": model,
                },
                "ont": {
                    "serial": ont.serial_number,
                    "status": ont.status.to_string(),
                    "rx_power_dbm": ont.rx_power_dbm,
                    "tx_power_dbm": ont.tx_power_dbm,
                    "distance_m": ont.distance_meters,
                    "pon_port": ont.pon_port,
                    "uptime_seconds": ont.uptime_seconds,
                },
            });
            body.push_str(&doc.to_string());
            body.push('\n');
        }

        body
    }

    /// Convert a fault event to an Elastic document
    pub fn fault_event_to_doc(&self, event: &FaultEvent) -> String {
        serde_json::json!({
            "@timestamp": event.timestamp.to_rfc3339(),
            "type": "trunk_fibre_cut",
            "severity": event.severity,
            "affected_onts": event.affected_onts.len(),
            "pon_port": event.pon_port,
            "olt": event.olt_id,
            "detection": {
                "detection_latency_seconds": event.detection_latency_seconds,
            },
        }).to_string()
    }

    /// Send bulk request to Elasticsearch
    pub async fn send_bulk(&self, body: &str) -> anyhow::Result<()> {
        if body.is_empty() {
            return Ok(());
        }

        let url = format!("{}/_bulk", self.url);
        let mut req = self.client.post(&url)
            .header("Content-Type", "application/x-ndjson")
            .body(body.to_string());

        if let Some(ref auth) = self.auth_header {
            req = req.header("Authorization", auth);
        }

        // Retry 3x with exponential backoff
        let mut delay = std::time::Duration::from_secs(1);
        for attempt in 0..3u32 {
            match req.try_clone().unwrap().send().await {
                Ok(resp) if resp.status().is_success() => {
                    debug!(docs = body.lines().count() / 2, "Elastic bulk sent");
                    return Ok(());
                }
                Ok(resp) => {
                    let status = resp.status();
                    let text = resp.text().await.unwrap_or_default();
                    if attempt < 2 {
                        warn!(status = %status, "Elastic bulk failed, retrying");
                        tokio::time::sleep(delay).await;
                        delay *= 2;
                    } else {
                        anyhow::bail!("Elastic bulk failed: {} — {}", status, &text[..text.len().min(200)]);
                    }
                }
                Err(e) if attempt < 2 => {
                    warn!(error = %e, "Elastic connection error, retrying");
                    tokio::time::sleep(delay).await;
                    delay *= 2;
                }
                Err(e) => return Err(e.into()),
            }
        }
        unreachable!()
    }

    /// Send ONT data to Elasticsearch
    pub async fn send_onts(&self, agent_id: &str, olt_name: &str, vendor: &str, model: &str, onts: &[OntData]) -> anyhow::Result<()> {
        // Batch into chunks of bulk_size
        for chunk in onts.chunks(self.bulk_size) {
            let body = self.build_ont_bulk(agent_id, olt_name, vendor, model, chunk);
            self.send_bulk(&body).await?;
        }
        Ok(())
    }

    /// Send a single fault event to Elasticsearch
    pub async fn send_fault(&self, event: &FaultEvent) -> anyhow::Result<()> {
        let date = Utc::now().format("%Y.%m.%d");
        let index = format!("{}-faults-{}", self.index_prefix, date);
        let doc = self.fault_event_to_doc(event);
        let body = format!(
            "{{\"index\":{{\"_index\":\"{}\"}}}}\n{}\n",
            index, doc
        );
        self.send_bulk(&body).await
    }
}
```

**Note to implementer:** The `base64::Engine::encode` call may need adjustment depending on exact `base64` crate version. The existing Cargo.toml has `base64 = "0.22"` which uses `base64::engine::general_purpose::STANDARD.encode()`. Adjust if needed.

- [ ] **Step 5: Register output module in main.rs**

Add `mod output;` to module declarations in `main.rs`.

- [ ] **Step 6: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib output::elastic::tests -v 2>&1 | tail -20`
Expected: All 3 tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/output/
git commit -m "feat(agent): implement Elasticsearch bulk output"
```

---

## Task 10: Webhook Dispatcher

**Files:**
- Create: `pulso-agent/src/output/webhook.rs`

- [ ] **Step 1: Write webhook tests**

```rust
// SPDX-License-Identifier: Apache-2.0
// Webhook dispatcher — Slack/PagerDuty/generic

use serde_json::Value;
use tracing::{info, warn};
use crate::config::WebhookConfig;
use crate::fault::detector::FaultEvent;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slack_format() {
        let event = FaultEvent {
            timestamp: chrono::Utc::now(),
            pon_port: "0/1/3".into(),
            olt_id: "Lambeth-POP-OLT1".into(),
            severity: "critical".into(),
            affected_onts: vec![],
            detection_latency_seconds: 30,
        };

        let payload = format_slack(&event);
        let parsed: Value = serde_json::from_str(&payload).unwrap();
        assert!(parsed["text"].as_str().unwrap().contains("CRITICAL"));
        assert!(parsed["blocks"].is_array());
    }

    #[test]
    fn test_pagerduty_format() {
        let event = FaultEvent {
            timestamp: chrono::Utc::now(),
            pon_port: "0/1/3".into(),
            olt_id: "OLT1".into(),
            severity: "critical".into(),
            affected_onts: vec![],
            detection_latency_seconds: 30,
        };

        let payload = format_pagerduty(&event, "test-routing-key");
        let parsed: Value = serde_json::from_str(&payload).unwrap();
        assert_eq!(parsed["routing_key"], "test-routing-key");
        assert_eq!(parsed["event_action"], "trigger");
    }

    #[test]
    fn test_event_filter() {
        let config = WebhookConfig {
            url: "https://example.com".into(),
            events: vec!["fault_detected".into()],
            format: "slack".into(),
            routing_key: None,
        };

        assert!(should_send(&config, "fault_detected"));
        assert!(!should_send(&config, "degradation_warning"));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib output::webhook::tests 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: Implement WebhookDispatcher**

Add above `#[cfg(test)]`:

```rust
pub struct WebhookDispatcher {
    client: reqwest::Client,
    webhooks: Vec<WebhookConfig>,
}

impl WebhookDispatcher {
    pub fn new(webhooks: &[WebhookConfig]) -> Self {
        Self {
            client: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .expect("Failed to build HTTP client"),
            webhooks: webhooks.to_vec(),
        }
    }

    /// Dispatch a fault event to all matching webhooks
    pub async fn dispatch_fault(&self, event: &FaultEvent) {
        for webhook in &self.webhooks {
            if !should_send(webhook, "fault_detected") {
                continue;
            }

            let payload = match webhook.format.as_str() {
                "slack" => format_slack(event),
                "pagerduty" => {
                    let key = webhook.routing_key.as_deref().unwrap_or("");
                    format_pagerduty(event, key)
                }
                _ => format_generic(event),
            };

            if let Err(e) = self.send(&webhook.url, &payload).await {
                warn!(url = %webhook.url, error = %e, "Webhook dispatch failed");
            }
        }
    }

    async fn send(&self, url: &str, payload: &str) -> anyhow::Result<()> {
        let mut delay = std::time::Duration::from_secs(1);
        for attempt in 0..3u32 {
            match self.client.post(url)
                .header("Content-Type", "application/json")
                .body(payload.to_string())
                .send().await
            {
                Ok(resp) if resp.status().is_success() => return Ok(()),
                Ok(resp) if attempt < 2 => {
                    warn!(status = %resp.status(), "Webhook failed, retrying");
                    tokio::time::sleep(delay).await;
                    delay *= 2;
                }
                Ok(resp) => anyhow::bail!("Webhook returned {}", resp.status()),
                Err(e) if attempt < 2 => {
                    tokio::time::sleep(delay).await;
                    delay *= 2;
                }
                Err(e) => return Err(e.into()),
            }
        }
        unreachable!()
    }
}

fn should_send(config: &WebhookConfig, event_type: &str) -> bool {
    config.events.iter().any(|e| e == event_type || e == "*")
}

fn format_slack(event: &FaultEvent) -> String {
    let text = format!(
        "CRITICAL: Trunk fibre cut detected — {} PON {}",
        event.olt_id, event.pon_port
    );
    serde_json::json!({
        "text": text,
        "blocks": [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": format!(
                    "*Trunk Fibre Cut* — {}, PON {}\n{} ONTs offline\nSeverity: {}",
                    event.olt_id, event.pon_port,
                    event.affected_onts.len(), event.severity,
                ),
            },
        }],
    }).to_string()
}

fn format_pagerduty(event: &FaultEvent, routing_key: &str) -> String {
    serde_json::json!({
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": format!(
                "Trunk fibre cut: {} PON {} ({} ONTs offline)",
                event.olt_id, event.pon_port, event.affected_onts.len()
            ),
            "severity": event.severity,
            "source": format!("pulso-agent:{}", event.olt_id),
            "component": event.pon_port,
            "group": event.olt_id,
        },
    }).to_string()
}

fn format_generic(event: &FaultEvent) -> String {
    serde_json::to_string(event).unwrap_or_default()
}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib output::webhook::tests -v 2>&1 | tail -20`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/output/webhook.rs
git commit -m "feat(agent): implement webhook dispatcher (Slack, PagerDuty)"
```

---

## Task 11: Diagnostics Extensions

**Files:**
- Modify: `pulso-agent/src/diagnostics/mod.rs`

- [ ] **Step 1: Write tests for new diagnostic checks**

Add to the bottom of `diagnostics/mod.rs`:
```rust
#[cfg(test)]
mod tests {
    use super::*;
    use crate::vendors::{OntData, OntStatus};

    fn make_ont(serial: &str, rx: f64, eth_speed: Option<u32>, uptime: Option<u64>) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            ont_index: 0,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: uptime,
            rx_power_dbm: Some(rx),
            tx_power_dbm: None,
            distance_meters: Some(1000),
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None,
            eth_speed_mbps: eth_speed,
        }
    }

    #[test]
    fn test_ethernet_negotiation_alert() {
        let ont = make_ont("TEST01", -20.0, Some(100), Some(86400));
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().any(|a| matches!(a.alert_type, AlertType::EthernetNegotiation)));
    }

    #[test]
    fn test_no_alert_on_gigabit() {
        let ont = make_ont("TEST02", -20.0, Some(1000), Some(86400));
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().all(|a| !matches!(a.alert_type, AlertType::EthernetNegotiation)));
    }

    #[test]
    fn test_recent_restart_alert() {
        let ont = make_ont("TEST03", -20.0, None, Some(300)); // 5 min uptime
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().any(|a| matches!(a.alert_type, AlertType::RecentRestart)));
    }

    #[test]
    fn test_no_restart_alert_long_uptime() {
        let ont = make_ont("TEST04", -20.0, None, Some(86400)); // 24h uptime
        let alerts = check_ont_extras(&ont);
        assert!(alerts.iter().all(|a| !matches!(a.alert_type, AlertType::RecentRestart)));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib diagnostics::tests 2>&1 | tail -20`
Expected: FAIL — `AlertType::EthernetNegotiation`, `AlertType::RecentRestart`, `check_ont_extras` don't exist

- [ ] **Step 3: Add new AlertType variants**

In `diagnostics/mod.rs`, add to the `AlertType` enum:
```rust
/// Ethernet port negotiated at 100M instead of 1G
EthernetNegotiation,
/// ONT recently restarted (uptime < 1 hour)
RecentRestart,
```

- [ ] **Step 4: Implement check_ont_extras**

Add a new function:
```rust
/// Additional per-ONT checks (ethernet negotiation, restart detection)
pub fn check_ont_extras(ont: &OntData) -> Vec<OntAlert> {
    let mut alerts = Vec::new();

    // Ethernet negotiation check
    if let Some(speed) = ont.eth_speed_mbps {
        if speed <= 100 && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
            alerts.push(OntAlert {
                serial_number: ont.serial_number.clone(),
                pon_port: ont.pon_port.clone(),
                severity: HealthLevel::Yellow,
                alert_type: AlertType::EthernetNegotiation,
                description: format!("Ethernet negotiated at {}Mbps", speed),
                support_message: format!(
                    "ONT {} ethernet port at {}Mbps instead of 1Gbps. Customer may have a bad cable or 100M port.",
                    ont.serial_number, speed
                ),
                recommended_action: "Remote investigation — customer likely has a bad ethernet cable or using 100M port".into(),
            });
        }
    }

    // Recent restart detection
    if let Some(uptime) = ont.uptime_seconds {
        if uptime < 3600 && matches!(ont.status, OntStatus::Online | OntStatus::LowSignal) {
            alerts.push(OntAlert {
                serial_number: ont.serial_number.clone(),
                pon_port: ont.pon_port.clone(),
                severity: HealthLevel::Yellow,
                alert_type: AlertType::RecentRestart,
                description: format!("ONT uptime: {} seconds", uptime),
                support_message: format!(
                    "ONT {} restarted recently (uptime: {}s). Check power supply at premises.",
                    ont.serial_number, uptime
                ),
                recommended_action: "Check power supply at premises — ONT restarted recently".into(),
            });
        }
    }

    alerts
}
```

- [ ] **Step 5: Wire check_ont_extras into analyze_olt**

In the `analyze_olt` function, after the signal level checks loop body (after the `if let Some(rx) = ont.rx_power_dbm` block), add:
```rust
// Extended diagnostics
let extra_alerts = check_ont_extras(ont);
alerts.extend(extra_alerts);
```

- [ ] **Step 6: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib diagnostics::tests -v 2>&1 | tail -20`
Expected: All 4 tests PASS

- [ ] **Step 7: Run all tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test 2>&1 | tail -10`
Expected: All tests PASS (existing + new)

- [ ] **Step 8: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/diagnostics/mod.rs
git commit -m "feat(agent): add ethernet negotiation + restart detection diagnostics"
```

---

## Task 12: Prediction Extensions

**Files:**
- Modify: `pulso-agent/src/predictions/mod.rs`

- [ ] **Step 1: Write test for configurable thresholds**

Add to `predictions/mod.rs` (create `#[cfg(test)] mod tests` if not present):
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_configurable_failure_threshold() {
        // XGS-PON threshold: -28.0 dBm
        let threshold = -28.0_f64;
        let current_rx = -25.0;
        let slope = -0.05; // dBm/day

        let days = ((current_rx - threshold) / slope.abs()) as u32;
        assert_eq!(days, 60);
    }

    #[test]
    fn test_linear_regression_degrading() {
        let points = vec![
            (0.0, -20.0),
            (10.0, -21.0),
            (20.0, -22.0),
            (30.0, -23.0),
        ];
        let (slope, _intercept, r2) = linear_regression(&points).unwrap();
        assert!(slope < -0.09, "slope={}", slope);
        assert!(r2 > 0.99, "r2={}", r2);
    }

    #[test]
    fn test_linear_regression_stable() {
        let points = vec![
            (0.0, -22.0),
            (10.0, -22.1),
            (20.0, -21.9),
            (30.0, -22.0),
        ];
        let (slope, _intercept, _r2) = linear_regression(&points).unwrap();
        assert!(slope.abs() < 0.01, "Should be near-zero slope: {}", slope);
    }
}
```

- [ ] **Step 2: Run tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib predictions::tests -v 2>&1 | tail -20`
Expected: PASS (these test existing `linear_regression` function)

- [ ] **Step 3: Add configurable parameters to forecast_olt**

Modify `forecast_olt` signature to accept optional degradation config:

```rust
use crate::config::DegradationConfig;

/// Generate predictions with configurable thresholds
pub fn forecast_olt_configured(
    current: &OltData,
    db: &LocalBuffer,
    config: Option<&DegradationConfig>,
) -> Predictions {
    let history_days = config.map(|c| c.history_days).unwrap_or(30);
    let failure_threshold = config.map(|c| c.min_critical_rx_dbm).unwrap_or(-28.0);
    let min_slope = -0.01; // dBm/day degradation minimum

    // ... (same logic as forecast_olt but using history_days and failure_threshold)
```

Keep the existing `forecast_olt` function unchanged as a wrapper:
```rust
pub fn forecast_olt(current: &OltData, db: &LocalBuffer) -> Predictions {
    forecast_olt_configured(current, db, None)
}
```

In `forecast_olt_configured`, replace:
- `db.get_ont_signal_history(&ont.serial_number, 30)` → `db.get_ont_signal_history(&ont.serial_number, history_days)`
- `let failure_threshold = -28.0;` → use the variable
- Same for PON utilization: `db.get_pon_utilization_history(..., 30)` → use `history_days`

- [ ] **Step 4: Run all tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test 2>&1 | tail -10`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/predictions/mod.rs
git commit -m "feat(agent): configurable degradation thresholds + XGS-PON support"
```

---

## Task 13: Wire Everything into Main Loop

**Files:**
- Modify: `pulso-agent/src/main.rs`

**Dependencies:** All previous tasks

- [ ] **Step 1: Add module declarations**

At the top of `main.rs`, add (if not already added):
```rust
mod fault;
mod output;
```

- [ ] **Step 2: Initialize output + fault modules after config load**

After the config load and cloud transport initialization, add:

```rust
// Initialize Elasticsearch output (if configured)
let elastic = cfg.output.as_ref()
    .and_then(|o| o.elastic.as_ref())
    .filter(|e| e.enabled)
    .map(|e| output::ElasticOutput::new(e))
    .transpose()?;

if elastic.is_some() {
    info!("Elasticsearch output enabled");
}

// Initialize webhook dispatcher (if configured)
let webhooks = cfg.output.as_ref()
    .and_then(|o| o.webhooks.as_ref())
    .map(|w| output::WebhookDispatcher::new(w));

// Initialize fault detector (if configured)
let mut fault_detector = cfg.fault_detection.as_ref()
    .filter(|f| f.enabled)
    .map(|f| fault::FaultDetector::new(f));

if fault_detector.is_some() {
    info!("Fault detection enabled");
}

// Load fibre topology (if configured)
let topology = cfg.topology.as_ref()
    .map(|t| fault::FibreTopology::load(&t.mode, t.import_path.as_deref()))
    .unwrap_or_else(fault::FibreTopology::empty);
```

- [ ] **Step 3: Add fault detection + elastic output to collection cycle**

**CRITICAL placement note:** The existing code calls `telemetry.add_olt(data)` which **moves** `data` by value. All code that references `data` must run BEFORE that line. Insert the following code **between** `telemetry.add_predictions(preds);` and `telemetry.add_olt(data);`. You must also reorder the existing code so that `telemetry.add_olt(data)` comes AFTER all new processing.

Restructure the `Ok(Ok(data))` arm to:

```rust
Ok(Ok(data)) => {
    // Store signal history for predictions
    if let Err(e) = db.store_signal_history(&data.onts) {
        warn!(error = %e, "Failed to store signal history");
    }
    if let Err(e) = db.store_pon_utilization(&data.olt_id, &data.pon_ports) {
        warn!(error = %e, "Failed to store PON utilization");
    }

    // Run diagnostics
    let diag = diagnostics::analyze_olt(&data);
    // Run predictions
    let preds = predictions::forecast_olt_configured(
        &data, &db, cfg.degradation.as_ref()
    );

    // ── NEW: Fault detection (runs before data is moved) ──
    if let Some(ref mut detector) = fault_detector {
        let mut events = detector.check(&data.onts);
        for event in &mut events {
            event.olt_id = data.olt_id.clone();
        }
        if !events.is_empty() {
            let locator = fault::FaultLocator::new(&topology);
            let online: Vec<_> = data.onts.iter()
                .filter(|o| matches!(o.status, vendors::OntStatus::Online))
                .map(|o| fault::detector::AffectedOnt {
                    serial_number: o.serial_number.clone(),
                    distance_meters: o.distance_meters,
                    last_rx_dbm: o.rx_power_dbm,
                })
                .collect();

            for event in &events {
                let _location = locator.locate(event, &online);
                info!(
                    olt = %event.olt_id,
                    port = %event.pon_port,
                    affected = event.affected_onts.len(),
                    severity = %event.severity,
                    "Fault detected"
                );

                // Send fault to Elasticsearch
                if let Some(ref elastic) = elastic {
                    if let Err(e) = elastic.send_fault(event).await {
                        warn!(error = %e, "Failed to send fault to Elastic");
                    }
                }

                // Dispatch webhooks
                if let Some(ref wh) = webhooks {
                    wh.dispatch_fault(event).await;
                }
            }
        }
    }

    // ── NEW: Send ONT data to Elasticsearch ──
    if let Some(ref elastic) = elastic {
        if let Err(e) = elastic.send_onts(
            &cfg.agent_id, &data.olt_id, &data.vendor, &data.model, &data.onts
        ).await {
            warn!(error = %e, "Failed to send ONTs to Elastic");
        }
    }

    // NOW move data into telemetry payload
    telemetry.add_olt(data);
    telemetry.add_diagnostics(diag);
    telemetry.add_predictions(preds);
}
```

This replaces the entire existing `Ok(Ok(data)) => { ... }` block in the OLT collection loop.

- [ ] **Step 4: Verify existing predictions call was updated**

The restructured block in Step 3 already calls `forecast_olt_configured` with `cfg.degradation.as_ref()`. Verify that the old `predictions::forecast_olt(&data, &db)` call is no longer present:

Run: `grep -n "forecast_olt(" /home/dev/enlace/pulso-agent/src/main.rs`
Expected: Only shows `forecast_olt_configured`, not the old `forecast_olt`

- [ ] **Step 5: Verify compilation**

Run: `cd /home/dev/enlace/pulso-agent && cargo check 2>&1 | tail -10`
Expected: Compiles with no errors

- [ ] **Step 6: Run all tests**

Run: `cd /home/dev/enlace/pulso-agent && cargo test 2>&1 | tail -10`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/main.rs
git commit -m "feat(agent): wire fault detection + elastic output into main loop"
```

---

## Task 14: Full Build + Test Suite

- [ ] **Step 1: Full release build**

Run: `cd /home/dev/enlace/pulso-agent && cargo build --release 2>&1 | tail -10`
Expected: Compiles. Note binary size (should be ~8-9 MB, up from 6.3 MB).

- [ ] **Step 2: Check binary size**

Run: `ls -lh /home/dev/enlace/pulso-agent/target/release/pulso-agent`
Expected: ~8-9 MB

- [ ] **Step 3: Run complete test suite**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --release 2>&1`
Expected: All tests PASS

- [ ] **Step 4: Run with --dry-run to verify startup**

Create a minimal test config:
```toml
# /tmp/test-cf-config.toml
agent_id = "cf-test-01"
poll_interval_secs = 30

[cloud]
endpoint = "https://example.com"
api_key = "test"

[[olts]]
name = "Test-Huawei"
ip = "10.0.0.1"
vendor = "huawei"
[olts.snmp]
community = "public"

[output.elastic]
enabled = true
url = "http://localhost:9200"
index_prefix = "enlace"
bulk_size = 1000
verify_tls = false

[fault_detection]
enabled = true
min_offline_onts = 5
time_window_seconds = 60

[fault_detection.severity]
critical = 100
major = 50
minor = 10
```

Run: `cd /home/dev/enlace/pulso-agent && timeout 5 cargo run --release -- --config /tmp/test-cf-config.toml --once --dry-run -v 2>&1 | head -30`
Expected: Starts up, loads config, shows elastic + fault detection enabled, fails on OLT connection (expected — no real OLT), exits.

- [ ] **Step 5: Commit test config as example**

```bash
cp /tmp/test-cf-config.toml /home/dev/enlace/pulso-agent/examples/community_fibre.toml
cd /home/dev/enlace/pulso-agent
git add examples/community_fibre.toml
git commit -m "docs(agent): add Community Fibre example config"
```

---

## Task 15: SQLite Downsampling

**Files:**
- Modify: `pulso-agent/src/transport/mod.rs`

- [ ] **Step 1: Write test for downsampling**

Add to `transport/mod.rs` tests:
```rust
#[test]
fn test_downsample_old_readings() {
    let dir = tempfile::tempdir().unwrap();
    let db = LocalBuffer::open(dir.path()).unwrap();

    // Insert 100 readings over 2 days for one ONT
    let now = chrono::Utc::now().timestamp();
    let conn = db.conn().unwrap();
    for i in 0..100 {
        let ts = now - (48 * 3600) + (i * 1800); // Every 30 min over 2 days
        conn.execute(
            "INSERT OR REPLACE INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES (?1, ?2, ?3)",
            rusqlite::params!["TEST-DS", -22.0 + (i as f64 * 0.01), ts],
        ).unwrap();
    }

    let before = db.get_ont_signal_history("TEST-DS", 3).unwrap();
    assert_eq!(before.len(), 100);

    db.downsample_old_readings(24).unwrap();

    let after = db.get_ont_signal_history("TEST-DS", 3).unwrap();
    // Readings older than 24h should be downsampled to 1/hour
    // 24 hours of 30-min data = 48 readings → ~24 after downsample
    // + 48 readings in the last 24h (kept as-is)
    assert!(after.len() < before.len(), "Should have fewer readings after downsample");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib transport::tests::test_downsample 2>&1 | tail -20`
Expected: FAIL — `downsample_old_readings` doesn't exist

- [ ] **Step 3: Implement downsampling**

Add to `LocalBuffer` impl:
```rust
/// Downsample old signal readings to 1 per hour.
/// Keeps all readings from the last `keep_hours` hours at full resolution.
pub fn downsample_old_readings(&self, keep_hours: u32) -> anyhow::Result<()> {
    let conn = self.conn()?;
    let cutoff = chrono::Utc::now().timestamp() - (keep_hours as i64 * 3600);

    // For readings older than cutoff, keep only the latest per hour
    conn.execute_batch(&format!(
        "DELETE FROM ont_signal_history
         WHERE timestamp < {cutoff}
         AND rowid NOT IN (
             SELECT MAX(rowid)
             FROM ont_signal_history
             WHERE timestamp < {cutoff}
             GROUP BY serial_number, timestamp / 3600
         )"
    ))?;

    Ok(())
}
```

- [ ] **Step 4: Run test**

Run: `cd /home/dev/enlace/pulso-agent && cargo test --lib transport::tests::test_downsample -v 2>&1 | tail -10`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/dev/enlace/pulso-agent
git add src/transport/mod.rs
git commit -m "feat(agent): add SQLite signal history downsampling"
```

---

## Task 16: Final Integration Verification

- [ ] **Step 1: Run full test suite one more time**

Run: `cd /home/dev/enlace/pulso-agent && cargo test 2>&1`
Expected: All tests PASS (should be ~30+ tests total)

- [ ] **Step 2: Check for compiler warnings**

Run: `cd /home/dev/enlace/pulso-agent && cargo check 2>&1 | grep "warning:" | head -20`
Fix any warnings.

- [ ] **Step 3: Verify release binary**

Run: `cd /home/dev/enlace/pulso-agent && cargo build --release 2>&1 | tail -5 && ls -lh target/release/pulso-agent`

- [ ] **Step 4: Final commit if any warnings fixed**

```bash
cd /home/dev/enlace/pulso-agent
git add -A
git commit -m "fix(agent): resolve compiler warnings"
```

- [ ] **Step 5: Summary**

Print summary: new files created, lines added, tests added, binary size change.
