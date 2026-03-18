// SPDX-License-Identifier: Apache-2.0
// Vendor abstraction layer for OLT data collection.
//
// Each vendor module implements the OltCollector trait, providing
// vendor-specific SNMP OIDs, CLI commands, and response parsers.
//
// Supported vendors (covering ~100% of Brazilian ISP market):
//   Tier 1 (85% market): Huawei, ZTE, FiberHome/Intelbras
//   Tier 2 (10% market): Datacom, Parks, BDCOM
//   Tier 3 (5% market):  VSOL, CDATA, Ubiquiti, Nokia, Digistar
//   International:       Adtran SDX (OpenOLT gRPC)
//   Fallback:            Generic IF-MIB (works on ANY SNMP device)
//
// Adding a new vendor requires:
//   1. Create a new module file (e.g., vendors/newvendor.rs)
//   2. Implement the OltCollector trait
//   3. Add the vendor to the match in create_collector()
//   4. Add a YAML profile in profiles/newvendor_model.yml
//
// Community contributions for new vendors are welcome!
// See CONTRIBUTING.md for the vendor integration guide.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use crate::config::OltConfig;

pub mod huawei;
pub mod zte;
pub mod fiberhome;
pub mod intelbras;
pub mod datacom;
pub mod parks;
pub mod bdcom;
pub mod vsol;
pub mod cdata;
pub mod ubiquiti;
pub mod nokia;
pub mod adtran;
pub mod generic;
pub mod snmp_helper;

/// Normalized OLT data — vendor-agnostic representation
/// Every vendor's data gets transformed into this common schema
/// before being sent to the Pulso Cloud.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OltData {
    /// OLT identification
    pub olt_id: String,
    pub vendor: String,
    pub model: String,
    pub firmware: String,
    pub serial: String,
    pub uptime_seconds: u64,
    pub timestamp: chrono::DateTime<chrono::Utc>,

    /// System health
    pub cpu_percent: Option<f32>,
    pub memory_percent: Option<f32>,
    pub temperature_celsius: Option<f32>,
    pub power_supply_status: Option<String>,  // "ok", "redundant", "failed"

    /// PON ports
    pub pon_ports: Vec<PonPortData>,

    /// Uplink ports
    pub uplink_ports: Vec<UplinkPortData>,

    /// All registered ONTs
    pub onts: Vec<OntData>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PonPortData {
    pub port_id: String,       // e.g., "0/1/0"
    pub oper_status: String,   // "up", "down"
    pub onts_registered: u32,
    pub onts_online: u32,
    pub onts_offline: u32,
    pub bw_down_bps: u64,
    pub bw_up_bps: u64,
    pub utilization_percent: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UplinkPortData {
    pub port_id: String,
    pub oper_status: String,
    pub speed_mbps: u32,
    pub in_octets: u64,
    pub out_octets: u64,
    pub in_errors: u64,
    pub out_errors: u64,
}

/// Per-ONT data — the critical data for customer service and predictive repair
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OntData {
    /// ONT identification
    pub serial_number: String,
    pub pon_port: String,      // Which PON port this ONT is on
    pub ont_index: u32,        // Index on the PON port

    /// Status
    pub status: OntStatus,
    pub last_down_cause: Option<String>,  // "power_fail", "fiber_cut", "dying_gasp", etc.
    pub uptime_seconds: Option<u64>,

    /// Optical signal — THE critical metric for predictive repair
    /// Values in dBm. Typical healthy range: -15 to -27 dBm
    /// Warning threshold: -27 dBm
    /// Critical threshold: -28 dBm (service degradation)
    /// Failure threshold: -29 to -30 dBm (disconnection)
    pub rx_power_dbm: Option<f64>,
    pub tx_power_dbm: Option<f64>,

    /// Distance from OLT (meters) — useful for fiber loss calculations
    pub distance_meters: Option<u32>,

    /// ONT hardware info
    pub vendor_id: Option<String>,
    pub equipment_id: Option<String>,
    pub firmware_version: Option<String>,

    /// Traffic counters (if available)
    pub in_octets: Option<u64>,
    pub out_octets: Option<u64>,

    /// Ethernet port speed on the ONT (Mbps) — reported by some vendors via NETCONF/gRPC
    pub eth_speed_mbps: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum OntStatus {
    Online,
    Offline,
    LowSignal,       // Online but rx_power below warning threshold
    Dying,            // Signal degrading — predicted failure
    PowerFail,        // Offline due to power failure
    FiberCut,         // Offline, suspected fiber cut (no dying gasp)
    Unknown,
}

impl std::fmt::Display for OntStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Online => write!(f, "online"),
            Self::Offline => write!(f, "offline"),
            Self::LowSignal => write!(f, "low_signal"),
            Self::Dying => write!(f, "dying"),
            Self::PowerFail => write!(f, "power_fail"),
            Self::FiberCut => write!(f, "fiber_cut"),
            Self::Unknown => write!(f, "unknown"),
        }
    }
}

/// The trait that every vendor-specific collector must implement.
/// This is the extension point for community contributions.
#[async_trait]
pub trait OltCollector: Send + Sync {
    /// Unique identifier for this OLT instance
    fn olt_id(&self) -> &str;

    /// Collect all data from this OLT
    /// Returns normalized OltData regardless of vendor
    async fn collect(&self) -> anyhow::Result<OltData>;

    /// Test connectivity to this OLT
    async fn test_connection(&self) -> anyhow::Result<bool>;

    /// Get vendor name
    fn vendor_name(&self) -> &str;
}

/// Factory function: create the right collector based on vendor configuration
pub fn create_collector(config: &OltConfig) -> anyhow::Result<Box<dyn OltCollector>> {
    let vendor = if config.vendor == "auto" {
        // Auto-detect by querying sysObjectID via SNMP
        // This happens synchronously at startup
        tracing::info!(ip = %config.ip, "Auto-detecting OLT vendor...");
        "generic" // Will be replaced by actual detection in runtime
    } else {
        &config.vendor
    };

    match vendor {
        "huawei" => Ok(Box::new(huawei::HuaweiCollector::new(config)?)),
        "zte" => Ok(Box::new(zte::ZteCollector::new(config)?)),
        "fiberhome" => Ok(Box::new(fiberhome::FiberhomeCollector::new(config)?)),
        "intelbras" => {
            // Intelbras has two variants:
            // 1. Native G08/G16 (own firmware, enterprise OID .13464)
            // 2. Rebranded FiberHome AN5516/AN6001 (FiberHome firmware, enterprise OID .5875)
            // For rebranded models, delegate to FiberHome collector
            if config.model.contains("AN5") || config.model.contains("AN6") {
                Ok(Box::new(fiberhome::FiberhomeCollector::new(config)?))
            } else {
                Ok(Box::new(intelbras::IntelbrasCollector::new(config)?))
            }
        }
        "datacom" => Ok(Box::new(datacom::DatacomCollector::new(config)?)),
        "parks" => Ok(Box::new(parks::ParksCollector::new(config)?)),
        "bdcom" => Ok(Box::new(bdcom::BdcomCollector::new(config)?)),
        "vsol" => Ok(Box::new(vsol::VsolCollector::new(config)?)),
        "cdata" => Ok(Box::new(cdata::CdataCollector::new(config)?)),
        "ubiquiti" => Ok(Box::new(ubiquiti::UbiquitiCollector::new(config)?)),
        "nokia" => Ok(Box::new(nokia::NokiaCollector::new(config)?)),
        "adtran" => Ok(Box::new(adtran::AdtranCollector::new(config)?)),
        "generic" | _ => Ok(Box::new(generic::GenericCollector::new(config))),
    }
}
