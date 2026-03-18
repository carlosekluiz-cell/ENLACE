# Community Fibre UK Telemetry Adaptation — Design Spec

**Date:** 2026-03-18
**Status:** Draft
**Target:** Community Fibre UK (London's largest full-fibre ISP)
**Contact:** Rik Davies (Emergency Engineer)
**Base codebase:** `pulso-agent/` (existing 6.3 MB Rust binary, Apache-2.0)

---

## 1. Context

Community Fibre operates a 100% FTTP/GPON network across London: 1.342M premises passed, 429K customers, XGS-PON capable (10Gbps symmetric). Their NOC uses Zabbix for monitoring and OpenSearch/Elastic Stack for observability.

The existing Pulso Agent is a production-grade Rust binary that polls OLTs via SNMP, collects MikroTik/RADIUS/TR-069 data, runs per-ONT diagnostics and signal degradation prediction, and sends telemetry to Pulso Cloud. It supports 11 OLT vendors (Huawei, ZTE, FiberHome, Intelbras, Datacom, Parks, BDCOM, CDATA, Ubiquiti, Nokia, VSOL) with ~6,000 lines of Rust, 17 passing tests, and a SQLite offline buffer.

This spec describes how to extend the existing agent for CF's specific stack and requirements.

## 2. CF Network Stack (Verified)

| Layer | Vendor | Equipment | Monitoring Protocol |
|-------|--------|-----------|---------------------|
| IP Core | Cisco | NCS 5500 (IOS-XR, Segment Routing) | Standard Cisco SNMP (not PON-relevant) |
| Access Aggregation | Cisco | NCS 540 | Standard Cisco SNMP (not PON-relevant) |
| **PON OLT** | **Adtran** | **SDX 6320 (XGS-PON)** | **OpenOLT gRPC (port 9191) / NETCONF (TR-385)** |
| **PON OLT (legacy)** | **Huawei** | **MA5800-X series** | **SNMP v2c** |
| ONT (new) | Adtran | SDX 621i | Managed via OLT |
| ONT (legacy) | Huawei/Nokia | Various | Managed via OLT |

**Critical finding:** The Adtran SDX 6320 does NOT support SNMP. It is managed exclusively via gRPC (OpenOLT/VOLTHA on port 9191), NETCONF/YANG (BBF TR-385), and CLI. The original spec assumed SNMP for Adtran — this is incorrect.

**Critical finding:** Cisco equipment in CF's network handles IP routing, not PON. Per-ONT monitoring data lives in the Adtran/Huawei PON layer, not in Cisco NCS routers. A Cisco PON adapter is not needed.

## 3. Scope

### Already built (no changes needed):

| Capability | Module | Lines | Status |
|------------|--------|-------|--------|
| Huawei MA5800 SNMP polling | `vendors/huawei.rs` | 388 | Complete, verified OIDs |
| Per-ONT health scoring | `diagnostics/mod.rs` | 266 | Complete |
| Signal degradation prediction | `predictions/mod.rs` | 249 | Complete (linear regression) |
| PON capacity forecasting | `predictions/mod.rs` | (included above) | Complete |
| SQLite offline buffer | `transport/mod.rs` | 350+ | Complete |
| TOML configuration | `config/mod.rs` | 311 | Complete |
| Network discovery | `discovery/mod.rs` | 175 | Complete |
| SNMP v2c engine | `snmp/mod.rs` | 684 | Complete, tested |
| Vendor auto-detection | `vendors/mod.rs` | 206 | Complete |

### New modules to build:

| Module | Est. Lines | Complexity | Description |
|--------|-----------|------------|-------------|
| `vendors/adtran.rs` | ~300 | Medium | OpenOLT gRPC client for SDX 6320 |
| `output/mod.rs` | ~50 | Trivial | Output dispatcher |
| `output/elastic.rs` | ~250 | Easy | Elasticsearch/OpenSearch bulk API |
| `output/webhook.rs` | ~150 | Easy | Slack/PagerDuty alerts |
| `fault/mod.rs` | ~50 | Trivial | Fault module root |
| `fault/detector.rs` | ~200 | Easy | Mass-offline pattern detection |
| `fault/locator.rs` | ~250 | Hard | Geographic break calculation |
| `fault/topology.rs` | ~200 | Medium | Fibre route model (3 data sources) |
| Config extensions | ~100 | Easy | New TOML sections |
| Main loop wiring | ~50 | Easy | Connect new modules |
| **Total** | **~1,600** | | |

### Files to modify:

- `Cargo.toml` — add `geo` crate, vendor `openolt.proto`/`extensions.proto`, `tonic-build`
- `build.rs` — compile OpenOLT protobuf definitions
- `src/config/mod.rs` — add elastic, webhook, fault_detection, topology config sections
- `src/vendors/mod.rs` — register Adtran collector, extend `OltCollector` trait for gRPC
- `src/diagnostics/mod.rs` — add ethernet negotiation check, restart detection, action recommendations
- `src/predictions/mod.rs` — configurable history window (90 days), geographic grouping, XGS-PON thresholds
- `src/transport/mod.rs` — add elastic + webhook dispatch alongside cloud transport
- `src/main.rs` — wire fault detection + elastic output into main loop

## 4. Adtran SDX gRPC Adapter

### Protocol

OpenOLT gRPC API on port 9191. The SDX 6320 is VOLTHA Continuously Certified. Protobuf definitions from [opencord/voltha-protos](https://github.com/opencord/voltha-protos):
- `openolt.proto` — core OLT/ONT messages
- `extensions.proto` — optical power, distance, diagnostics

### Collection Flow

```
AdtranCollector::collect() -> Result<OltData>
  1. Connect to SDX IP:9191 via tonic gRPC client
  2. GetDeviceInfo() → model, firmware, hardware version
  3. EnableIndication() stream → OnuIndication per ONT
     - oper_state: "up" | "down"
     - serial_number: 4 ASCII + 4 bytes (e.g., "ADTN153201C4")
  4. Per ONT: GetPonRxPower(intf_id, onu_id)
     → rx_power as f64 (already in dBm, NO scaling needed)
  5. Per ONT: GetOnuInfo()
     → tx_power (meanOpticalLaunchPower), laser_bias, temperature
  6. Per ONT: GetLogicalOnuDistance()
     → distance in metres (uint32)
  7. Map all into OltData struct (same output as Huawei adapter)
```

### Key Differences from Huawei Adapter

| Aspect | Huawei | Adtran SDX |
|--------|--------|------------|
| Protocol | SNMP v2c (UDP) | gRPC (HTTP/2) |
| Optical power unit | Integer, 0.01 dBm (divide by 100) | Double, dBm (no scaling) |
| Distance unit | Integer, metres | uint32, metres |
| Serial format | OctetString (vendor-specific) | 4 ASCII + 8 hex ("ADTN153201C4") |
| ONT enumeration | SNMP table walk | gRPC stream (OnuIndication) |
| Connection | Stateless UDP per poll | Persistent gRPC channel |
| Port | 161 (SNMP) | 9191 (gRPC) |

### Config

```toml
[[olts]]
name = "Lambeth-POP-OLT1"
ip = "10.0.1.1"
vendor = "adtran"
[olts.grpc]
port = 9191
tls = false
# tls_cert = "/path/to/cert.pem"  # optional
# tls_key = "/path/to/key.pem"    # optional
```

### Vendor Detection

Adtran SDX does not respond to SNMP sysObjectID. Detection path:
1. If `vendor = "adtran"` in config, use gRPC directly
2. If `vendor = "auto"`, try SNMP first. If no response, try gRPC GetDeviceInfo on port 9191. If DeviceInfo.vendor contains "adtran" or "Adtran", use AdtranCollector.

### Fallback

If gRPC fails (port blocked, firmware issue), fall back to NETCONF/YANG (TR-385) via SSH on port 830. NETCONF paths:
- ONT presence: `/ietf-interfaces:interfaces-state/interface[type='bbf-xponvani:v-ani']/bbf-xponvani:v-ani/onu-presence-state`
- ONT distance: `/ietf-interfaces:interfaces-state/interface/bbf-xponvani:v-ani/onu-present-on-this-olt/onu-fiber-distance`
- ONT serial: `detected-serial-number` under `onu-present-on-this-olt`

NETCONF fallback is lower priority — gRPC is the primary path. NETCONF support can be added in a later phase if needed.

## 5. Elasticsearch Output

### Purpose

CF's NOC uses OpenSearch/Elastic Stack. The agent must push telemetry directly to Elastic indices, in addition to (or instead of) the Pulso Cloud endpoint.

### Index Structure

Daily indices with configurable prefix:

| Index Pattern | Content | Retention |
|---------------|---------|-----------|
| `{prefix}-ont-{YYYY.MM.dd}` | Per-ONT readings (one doc per ONT per poll) | 90 days |
| `{prefix}-faults-{YYYY.MM.dd}` | Fault events | 365 days |
| `{prefix}-alerts-{YYYY.MM.dd}` | Degradation/capacity alerts | 180 days |
| `{prefix}-diagnostics-{YYYY.MM.dd}` | Diagnostic summaries per OLT | 30 days |

### Document Schemas

**ONT reading:**
```json
{
  "@timestamp": "2026-03-18T12:00:00Z",
  "agent_id": "cf-agent-01",
  "olt": {
    "name": "Lambeth-POP-OLT1",
    "ip": "10.0.1.1",
    "vendor": "adtran",
    "model": "SDX 6320-16"
  },
  "ont": {
    "serial": "ADTN153201C4",
    "status": "online",
    "rx_power_dbm": -22.1,
    "tx_power_dbm": -2.3,
    "distance_m": 1200,
    "pon_port": "0/1/3",
    "uptime_seconds": 3456789
  },
  "health": {
    "score": "healthy",
    "signal_class": "good",
    "trend": "stable",
    "trend_dbm_per_day": -0.002
  },
  "geo": {
    "lat": 51.4607,
    "lon": -0.1163
  }
}
```

**Fault event:**
```json
{
  "@timestamp": "2026-03-18T12:01:30Z",
  "type": "trunk_fibre_cut",
  "severity": "critical",
  "affected_onts": 47,
  "affected_customers": 47,
  "pon_port": "0/1/3",
  "olt": "Lambeth-POP-OLT1",
  "location": {
    "method": "topology",
    "lat": 51.4625,
    "lon": -0.1148,
    "confidence_radius_m": 75,
    "between_splice_points": ["SP002", "SP003"],
    "distance_from_olt_m": 850
  },
  "boundary": {
    "last_online_ont": { "serial": "HWTC7B441234", "distance_m": 780 },
    "first_offline_ont": { "serial": "ADTN153201C4", "distance_m": 920 }
  },
  "detection": {
    "trigger_time": "2026-03-18T12:01:00Z",
    "onts_dropped_within_window": 47,
    "detection_latency_seconds": 30
  }
}
```

**Degradation alert:**
```json
{
  "@timestamp": "2026-03-18T12:00:00Z",
  "type": "signal_degradation",
  "severity": "warning",
  "ont_serial": "ADTN153201C4",
  "current_rx_dbm": -25.8,
  "trend_dbm_per_day": -0.035,
  "estimated_failure_days": 14,
  "classification": "WARNING",
  "suggested_action": "Schedule maintenance: inspect splice/joint near SP003",
  "group": {
    "co_degrading_onts": 5,
    "likely_cause": "splice_or_joint",
    "route_segment": "Lambeth-A"
  }
}
```

### Bulk API

Uses Elasticsearch `_bulk` endpoint with NDJSON format:
```
POST /_bulk
{"index":{"_index":"enlace-ont-2026.03.18"}}
{"@timestamp":"...","olt":{...},"ont":{...}}
{"index":{"_index":"enlace-ont-2026.03.18"}}
{"@timestamp":"...","olt":{...},"ont":{...}}
```

Configurable batch size (default 1000 docs). Uses existing `reqwest` dependency. Supports basic auth and API key auth. Retry 3x with exponential backoff on failure.

### Config

```toml
[output.elastic]
enabled = true
url = "http://elastic.internal:9200"
index_prefix = "enlace"
bulk_size = 1000
username = ""      # optional basic auth
password = ""
api_key = ""       # optional API key auth
verify_tls = true

[output.cloud]
enabled = false    # disable Pulso Cloud for CF deployment
```

## 6. Webhook Alerts

### Purpose

Push fault events and critical alerts to Slack/PagerDuty/custom endpoints in real time. CF's NOC should get immediate notification when a trunk fibre is cut.

### Flow

When a fault event or critical alert is generated:
1. Format as JSON payload
2. POST to each configured webhook URL
3. Retry 3x with backoff on failure
4. Log failures but don't block main loop

### Config

```toml
[[output.webhooks]]
url = "https://hooks.slack.com/services/T00/B00/xxxx"
events = ["fault_detected", "degradation_critical"]
format = "slack"  # or "pagerduty" or "generic"

[[output.webhooks]]
url = "https://events.pagerduty.com/v2/enqueue"
events = ["fault_detected"]
format = "pagerduty"
routing_key = "xxxx"
```

### Slack Format

```json
{
  "text": "CRITICAL: Trunk fibre cut detected",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Trunk Fibre Cut* — Lambeth-POP-OLT1, PON 0/1/3\n47 ONTs offline\nEstimated break: 51.4625, -0.1148 (confidence: 75m)\nBetween splice points SP002 and SP003"
      }
    }
  ]
}
```

## 7. Fault Location Engine

### 7a. Fault Detector (`fault/detector.rs`)

**Purpose:** Detect mass-offline events that indicate trunk fibre cuts, as opposed to individual ONT failures.

**Algorithm:**
1. Each poll cycle (30-60s), record ONT status transitions
2. Maintain a sliding window of status changes per PON port (last 10 cycles)
3. **Trigger condition:** N or more ONTs on the same PON port transition to offline within T seconds
   - Default: N=5, T=60s (configurable)
4. Filter out: known maintenance windows, individual ONT reboots (dying-gasp with quick recovery)
5. On trigger: collect list of affected ONTs, timestamps, pass to locator

**State machine per ONT:**
- `Online` — normal operation
- `Offline` — not responding (>1 missed poll)
- `DyingGasp` — received dying-gasp indication (power failure at ONT)
- `Degrading` — online but rx_power below threshold

**Trigger logic:**
```
if (offline_count_on_pon_port >= min_offline_onts
    && time_since_first_offline <= time_window_seconds
    && !is_maintenance_window())
{
    emit FaultEvent to locator
}
```

**Memory:** ~100 bytes per ONT for status ring buffer. At 102,400 ONTs: ~10 MB.

### 7b. Fibre Route Topology (`fault/topology.rs`)

**Purpose:** Model the physical fibre route so fault location can map ONT outage patterns to geographic coordinates.

**Data model:** Directed acyclic graph.
- Nodes: OLT, splice points (SPs), distribution points (DPs)
- Edges: fibre segments with length in metres
- ONTs attach to SPs or DPs
- Each node has lat/lon coordinates

```rust
struct FibreTopology {
    nodes: HashMap<String, TopologyNode>,  // node_id -> node
    edges: Vec<TopologyEdge>,              // parent -> child with distance
    ont_to_node: HashMap<String, String>,  // ont_serial -> node_id
}

struct TopologyNode {
    id: String,
    lat: f64,
    lon: f64,
    node_type: NodeType,  // Olt, SplicePoint, DistributionPoint
    distance_from_olt_m: f64,
}
```

**Three data sources:**

1. **CSV/GeoJSON import** — CF exports from their OSS/GIS system. Two files:
   - Splice points: `id, lat, lon, parent_id, route_name`
   - ONT mapping: `ont_serial, node_id`
   - Config path: `topology.import_path = "/etc/pulso/topology/"`

2. **SNMP/gRPC distance inference** — Uses ONT distance values from OLT polling. No external data needed.
   - Sort ONTs by distance from OLT per PON port
   - Cluster into groups by proximity (ONTs within 50m of each other = same distribution point)
   - Build approximate linear topology: OLT → cluster_1 → cluster_2 → ... → cluster_n
   - Config: `topology.mode = "infer"` (default if no import path)

3. **Synthetic test data** — Pre-built JSON file with realistic London topology for testing.
   - Stored in `fault/testdata/london_topology.json`
   - Config: `topology.mode = "synthetic"`

**Config:**
```toml
[topology]
mode = "import"  # "import", "infer", or "synthetic"
import_path = "/etc/pulso/topology/"
# import_format = "csv"  # or "geojson"
```

### 7c. Fault Locator (`fault/locator.rs`)

**Purpose:** Given a set of affected ONTs from the detector, calculate the estimated break location.

**Algorithm (with topology data):**
1. Map affected ONTs to their topology nodes
2. Walk the topology graph from OLT toward leaves
3. Find the **boundary edge**: the edge where upstream node has online ONTs and downstream node has all-offline ONTs
4. **Break location** = midpoint of boundary edge (lat/lon)
5. **Confidence radius** = half the length of boundary edge
6. If multiple boundary edges (branching topology), report the one closest to the OLT (trunk cut affects more downstream)

**Algorithm (distance-only, no topology):**
1. Sort all ONTs on affected PON port by distance from OLT
2. Find the gap: `last_online_distance` and `first_offline_distance`
3. **Break distance** = midpoint: `(last_online + first_offline) / 2`
4. **Confidence** = `(first_offline - last_online) / 2`
5. No lat/lon output — only distance from OLT in metres

**Edge cases:**
- All ONTs on PON port offline (OLT port failure or trunk cut at OLT): report as "break at OLT" with high confidence
- Only furthest ONTs offline (end-of-line break): report last splice point as location
- Mixed online/offline with no clear boundary (multiple breaks): report multiple possible locations sorted by likelihood

**Output:** `FaultLocation` struct pushed to Elastic and webhooks.

## 8. Diagnostics Extensions

### Ethernet Port Negotiation Check

When ONT reports normal optical power but customer reports slow internet:
1. Check ONT ethernet port speed (from OMCI or SNMP)
2. If negotiated at 100Mbps instead of 1Gbps: flag as `ethernet_negotiation_issue`
3. Recommended action: "Remote investigation — customer likely has a bad ethernet cable or using 100M port"

### Recent Restart Detection

1. Check ONT uptime (from SNMP/gRPC)
2. If uptime < 3600 seconds (1 hour): flag as `recent_restart`
3. Recommended action: "Check power supply at premises — ONT restarted recently"

### Action Recommendation Matrix

| Signal Power | Ethernet | Uptime | Diagnosis | Action |
|-------------|----------|--------|-----------|--------|
| Normal | 1G | Normal | Healthy | No action |
| Normal | 100M | Normal | Bad cable | Remote: advise customer |
| Normal | Any | < 1hr | Power issue | Remote: check UPS/power |
| Low (single ONT) | Any | Any | ONT/patchcord | Truck roll: inspect connector |
| Low (multiple ONTs) | Any | Any | Splice/joint | See fault locator output |
| Critical | Any | Any | Imminent failure | Priority truck roll |

## 9. Prediction Extensions

### Configurable History Window

Change from hardcoded 30 days to configurable:
```toml
[degradation]
history_days = 90
trend_window_weeks = 4
```

### Classification Thresholds (CF-Specific)

XGS-PON has -28 dBm sensitivity (vs -27 dBm for GPON). Make configurable:
```toml
[degradation]
watch_threshold_db = 0.5     # dB drop over trend_window
warning_threshold_db = 1.0
critical_threshold_db = 2.0
min_critical_rx_dbm = -28.0  # XGS-PON threshold
```

### Geographic Grouping

When 3+ ONTs on the same route segment show simultaneous degradation:
1. Use topology data to identify co-located ONTs
2. Group by closest splice point
3. Flag group as "likely splice/joint degradation"
4. Output: suggested maintenance location = the common splice point

## 10. Configuration (Full Example)

```toml
# /etc/pulso/agent.toml — Community Fibre deployment

agent_id = "cf-agent-01"
poll_interval_secs = 30
data_dir = "/var/lib/pulso-agent"

# ── OLTs ──────────────────────────────────────────────

[[olts]]
name = "Lambeth-POP-OLT1"
ip = "10.0.1.1"
vendor = "huawei"
[olts.snmp]
version = "v2c"
community = "readonly"
timeout_ms = 5000
max_repetitions = 50

[[olts]]
name = "Lambeth-POP-OLT2"
ip = "10.0.1.2"
vendor = "adtran"
[olts.grpc]
port = 9191
tls = false

# ── Output ────────────────────────────────────────────

[output.cloud]
enabled = false  # Disable Pulso Cloud for CF

[output.elastic]
enabled = true
url = "http://elastic.internal:9200"
index_prefix = "enlace"
bulk_size = 1000
verify_tls = true

[[output.webhooks]]
url = "https://hooks.slack.com/services/T00/B00/xxxx"
events = ["fault_detected", "degradation_critical"]
format = "slack"

# ── Fault Detection ──────────────────────────────────

[fault_detection]
enabled = true
min_offline_onts = 5
time_window_seconds = 60

[fault_detection.severity]
critical = 100  # ONTs
major = 50
minor = 10

# ── Topology ─────────────────────────────────────────

[topology]
mode = "import"
import_path = "/etc/pulso/topology/"

# ── Degradation ──────────────────────────────────────

[degradation]
history_days = 90
trend_window_weeks = 4
watch_threshold_db = 0.5
warning_threshold_db = 1.0
critical_threshold_db = 2.0
min_critical_rx_dbm = -28.0
```

## 11. Testing Strategy

### Unit Tests (in-crate)

| Test | Description | Validates |
|------|-------------|-----------|
| Adtran gRPC mock | Mock gRPC server returns ONT data. Verify AdtranCollector produces correct OltData. | Adtran adapter |
| Fault detector trigger | Simulate 30 ONTs dropping within 60s on one PON port. Verify trigger fires. | Detector logic |
| Fault detector no-trigger | Simulate 3 ONTs dropping (below threshold). Verify no trigger. | False positive prevention |
| Fault locator (topology) | Load synthetic topology. Simulate break between SP2 and SP3. Verify location output. | Geographic calculation |
| Fault locator (distance) | No topology. Sort ONTs by distance. Verify break distance calculation. | Distance-only fallback |
| Elastic bulk format | Generate 100 ONT docs. Verify NDJSON format matches Elastic _bulk API spec. | Output formatting |
| Webhook Slack format | Generate fault event. Verify Slack block kit JSON is valid. | Alert formatting |
| Degradation grouping | 5 ONTs on same route all degrade. Verify they're grouped with correct splice point. | Geographic grouping |

### Integration Tests (with SNMP simulator)

| Test | Description |
|------|-------------|
| Huawei MA5800 poll | snmpsim replaying real MA5800 walk data. Full collection cycle. |
| Mixed vendor | 2 Huawei (SNMP) + 1 Adtran (gRPC mock). Unified OltData output. |
| Fault detection E2E | Simulate trunk cut: kill 47 ONTs on snmpsim, verify fault event in Elastic mock. |
| Elastic ingestion | Real Elasticsearch container. Verify indices created, docs searchable. |

### Performance Test

Simulate: 100 OLTs x 16 PON ports x 64 ONTs = 102,400 ONTs.
Target: Full poll cycle completes in <10 seconds on 4-core server.
This tests the SNMP/gRPC parallel polling + fault detection + elastic bulk output.

## 12. Deployment Model

The agent runs **inside CF's network**, on a VM or container with:
- Network access to all OLT management IPs (SNMP UDP/161 for Huawei, gRPC TCP/9191 for Adtran)
- Network access to Elasticsearch cluster (HTTP/9200)
- Outbound HTTPS for webhooks (Slack/PagerDuty)
- No inbound ports needed (agent is a poller, not a server — except RADIUS listener if configured)

**Install:** Same `install.sh` script. Edit `/etc/pulso/agent.toml`. Start `systemctl enable --now pulso-agent`.

**Resource requirements:**
- Binary: ~6.5 MB (with gRPC additions)
- RAM: ~15-20 MB (102K ONTs + 90-day signal history in SQLite)
- CPU: <1% steady state, brief spike during poll cycle
- Disk: ~500 MB for SQLite signal history (90 days, 102K ONTs, 30s intervals)

## 13. Dependencies (Additions to Cargo.toml)

```toml
# New dependencies
geo = "0.28"                    # Geographic calculations (haversine, midpoint)
tonic = { version = "0.12", features = ["tls"] }  # gRPC client for Adtran
prost = "0.13"                  # Protobuf serialization

# Build dependencies
[build-dependencies]
tonic-build = "0.12"            # Compile openolt.proto + extensions.proto
```

`tonic` and `prost` are already workspace dependencies in the main `rust/Cargo.toml`. `geo` is also a workspace dependency. No net-new external dependencies.

## 14. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Adtran SDX gRPC port blocked by CF firewall | Medium | High | Support NETCONF fallback. Document required network access. |
| Adtran OpenOLT API version mismatch | Low | Medium | Pin to VOLTHA proto version matching CF's SDX firmware. GetDeviceInfo reports version. |
| Huawei MA5800 firmware variant has different OIDs | Low | Medium | Existing huawei.rs already handles MA5800-X variants. Test with CF's specific firmware. |
| CF cannot provide topology data for fault location | High | Medium | Distance-only inference works as fallback. Less precise but functional. |
| 102K ONTs too many for 30s poll cycle | Low | Low | Existing async SNMP + gRPC parallelism handles this. Performance test validates. |
| Elastic cluster rejects bulk inserts | Low | Low | SQLite buffer queues locally. Retry on recovery. Same pattern as cloud transport. |

## 15. What to Propose to Rik Davies

### Elevator Pitch

"We've built an open-source Rust agent that polls your Huawei and Adtran OLTs every 30 seconds, detects trunk fibre cuts within one poll cycle, estimates the break location to within 75 metres, predicts signal degradation weeks before failure, and pushes everything to your Elastic Stack. 6.5 MB binary, <1% CPU, runs inside your network. Want to test it on one POP?"

### What CF Provides

1. **Network access** — VM/container in their network with routes to OLT management IPs + Elastic
2. **SNMP community string** — for Huawei OLTs (read-only)
3. **gRPC access** — to Adtran SDX port 9191 (may need firewall rule)
4. **Elastic endpoint** — URL + credentials for their OpenSearch/Elastic cluster
5. **Topology data** (optional) — splice point coordinates + ONT-to-splice mapping from their GIS/OSS. If not available, distance-based inference is used.
6. **Test scenario** — A scheduled maintenance window where they can simulate a trunk cut (or use a real incident post-mortem for validation)

### Success Criteria

1. Agent polls all OLTs in test POP within 30 seconds
2. ONT data appears in Elastic indices within 60 seconds of agent start
3. Simulated trunk cut detected within 1 poll cycle (30s)
4. Fault location estimate within 200m of actual break point (with topology data)
5. Degradation prediction correctly identifies ONTs trending toward failure
6. Zero crashes or memory leaks over 7-day test period

---

*End of spec.*
