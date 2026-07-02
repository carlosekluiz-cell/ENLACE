# Enlace Telemetry Agent

**Open-source, vendor-agnostic PON/OLT telemetry agent built in Rust.** A product of [Pulso Technologies Limited](https://enlace.network).

Monitors OLTs (Adtran, Huawei, Nokia, ZTE, FiberHome, Datacom, Intelbras, Parks, BDCOM, VSOL, CDATA, Ubiquiti), MikroTik routers, RADIUS sessions, and TR-069 CPE — running edge fault detection and feeding real-time telemetry to the [Enlace](https://enlace.network) platform. It also runs offline: point it at a CSV export (`--audit-csv`) or the HTTP audit server (`--serve-port`) and it produces a full network audit.

> The Rust crate is named `pulso-agent` for historical reasons; the product is **Enlace**.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.75%2B-orange.svg)](https://www.rust-lang.org/)

## Why

Fibre operators worldwide manage their networks blind. The data exists — in OLTs, routers, RADIUS servers — but it's locked in vendor silos, so the NOC stays reactive: the customer calls before the operator knows anything is wrong.

**Enlace bridges that gap.** It reads from your existing equipment using standard protocols (SNMP, SSH, NETCONF/gRPC, RouterOS API, RADIUS, TR-069), runs fault and degradation detection at the edge, and turns raw telemetry into prioritised findings — fibre cuts, at-risk customers, ghost connections, capacity hot-spots — before they become support calls.

## Quick Start (60 seconds)

```bash
# Download
curl -sL https://pulsonetwork.com.br/install.sh | bash

# Configure (edit with your OLT IP and SNMP community)
nano /etc/pulso/agent.toml

# Run
pulso-agent -v
```

## What It Monitors

| Source | Protocol | Data Collected |
|--------|----------|----------------|
| **OLTs** (any vendor) | SNMP + SSH | ONT signal (dBm), status, PON utilization, port traffic |
| **MikroTik** routers | RouterOS API (8728) | PPPoE sessions, BGP health, bandwidth, CPU/memory |
| **RADIUS** server | UDP 1813 | Session start/stop, bytes, duration (for churn prediction) |
| **TR-069 CPE** | GenieACS API | WiFi diagnostics, channel interference, device count |

## Supported OLT Vendors

| Vendor | Models | Protocol | Coverage |
|--------|--------|----------|----------|
| **Huawei** | MA5800-X2/X7, MA5600T, MA5608T | SNMP + SSH + NETCONF | Full |
| **ZTE** | C320, C300, C600, C650 | SNMP + SSH | Full |
| **FiberHome** | AN5516-04/06, AN6001-G16 | SNMP + SSH | Full |
| **Intelbras** | G08, G16, AN6000 (FH-based) | SNMP + SSH | Full |
| **Datacom** | DM4610, DM4615 | SNMP + NETCONF | Full |
| **Parks** | FiberLink 20008/30028/40016 | SNMP + SSH | Full |
| **BDCOM** | GP3600 series | SNMP + SSH | Partial |
| **VSOL** | V1600D4/D8 | SNMP + SSH | Partial |
| **CDATA** | FD1604S/FD1608S | SNMP | Partial |
| **Ubiquiti** | UFiber OLT | UISP REST API | Partial |
| **Nokia** | ISAM/Lightspan | SNMP + NETCONF | Planned |
| **Any other** | Generic IF-MIB | SNMP | Basic |

## Architecture

```
ISP's Network                          Pulso Cloud (proprietary)
┌────────────────────┐                ┌─────────────────────────┐
│ OLT ──SNMP──┐      │                │ 37+ public data sources │
│ MikroTik─API─┤      │   HTTPS 443   │ Anatel, PGFN, IBGE...  │
│ RADIUS──UDP──┼─►AGENT├──────────────►│ Intelligence engine     │
│ CPE───TR069──┘      │                │ Predictions             │
│                     │                │ Dashboard               │
│ [SQLite buffer]     │                │ Customer health cards   │
└────────────────────┘                └─────────────────────────┘
```

**The agent is read-only** — it never modifies your OLT, router, or CPE configuration.
**Credentials stay local** — only aggregated metrics are sent to the cloud.

## Customer Service Revolution

When a customer calls, support staff sees a **health card** instantly:

- 🟢 **ONT Signal:** -22.1 dBm (normal)
- 🟢 **PPPoE Session:** Active, 287/142 Mbps
- 🟡 **WiFi 2.4GHz:** 17 devices, congested channel
- 🔴 **WiFi 5GHz:** Not configured (0 devices)
- **Diagnosis:** WiFi interference → One-click fix via TR-069

**70% of support calls resolved by receptionist. Zero truck rolls.**

## Predictive Repair

The agent tracks ONT signal trends over time:

- **Signal degradation:** "ONT losing 0.3 dBm/week → failure in 9 days"
- **Capacity planning:** "PON port at 87% → saturated in 6 weeks"
- **Churn prediction:** "Customer usage dropped 55% + Starlink active in area"

Fix problems **before** customers notice them.

## Building from Source

```bash
# Prerequisites: Rust 1.75+
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build
cargo build --release

# Binary is at target/release/pulso-agent (~8 MB, zero dependencies)
```

## Configuration

See [agent.example.toml](agent.example.toml) for a complete example.

Minimal config (one OLT + one MikroTik):

```toml
[cloud]
api_key = "YOUR_KEY"

[[olts]]
name = "My OLT"
ip = "10.0.0.1"
[olts.snmp]
community = "public"

[[mikrotiks]]
name = "My Router"
ip = "10.0.0.254"
username = "pulso"
password = "secret"
```

## Contributing

We welcome contributions! Especially:

- **New vendor support** — Add YAML profiles + Rust collectors for OLT brands
- **CLI parser improvements** — Better regex patterns for firmware variants
- **Bug fixes** — SNMP edge cases, timeout handling, error recovery
- **Documentation** — Translations (PT-BR, ES, FR), tutorials, setup guides

See [CONTRIBUTING.md](docs/CONTRIBUTING.md).

## License

Apache License 2.0 — use freely, including commercially.

The agent is open-source. The Pulso Network intelligence platform (cloud) is proprietary.
The agent without the cloud is a generic SNMP/MikroTik monitor.
The agent WITH the cloud is the world's first ISP operational intelligence platform.

## Links

- **Platform:** https://pulsonetwork.com.br
- **Documentation:** https://pulsonetwork.com.br/docs/agent
- **Issues:** https://github.com/pulso-network/pulso-agent/issues
- **Community:** https://community.pulsonetwork.com.br
