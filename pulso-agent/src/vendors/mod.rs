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

/// pon_port value used when the real PON port cannot be decoded from the
/// vendor's SNMP index encoding. NEVER fabricate a sequential port number:
/// fault detection groups ONTs by pon_port, and a fabricated port turns a
/// random sample of ONTs into a fake "trunk cut" (or hides a real one).
pub const UNKNOWN_PON_PORT: &str = "unknown";

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
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
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

    /// FEC corrected codewords counter — pre-FEC BER trending is the
    /// earliest degradation signal (errors corrected long before rx power
    /// visibly drops).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fec_corrected: Option<u64>,
    /// FEC uncorrectable codewords counter — non-zero means user-visible
    /// errors already happened.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fec_uncorrected: Option<u64>,
    /// BIP-8 (bit interleaved parity) error counter.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bip_errors: Option<u64>,

    /// Ethernet port speed on the ONT (Mbps) — reported by some vendors via NETCONF/gRPC
    pub eth_speed_mbps: Option<u32>,

    /// Extended vendor-specific ONT metrics (ONT-side OMCI data, available from
    /// Adtran SDX and other NETCONF/YANG-capable OLTs)
    pub extended: Option<ExtendedOntMetrics>,
}

/// Extended ONT metrics from OMCI transceiver data.
/// Available on Adtran SDX (via NETCONF) and other OLTs with YANG support.
/// This is the OntData home for transceiver DDM detail (temperature,
/// voltage, laser bias current) — do NOT add duplicate top-level fields.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ExtendedOntMetrics {
    /// ONT-side downstream rx power (dBm) — primary degradation metric
    pub ont_rx_power_dbm: Option<f64>,
    /// ONT transceiver temperature (°C)
    pub ont_temperature_c: Option<f64>,
    /// ONT supply voltage (V)
    pub ont_voltage_v: Option<f64>,
    /// ONT laser bias current (mA)
    pub ont_bias_current_ma: Option<f64>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub enum OntStatus {
    Online,
    Offline,
    LowSignal,       // Online but rx_power below warning threshold
    Dying,            // Signal degrading — predicted failure
    PowerFail,        // Offline due to power failure
    FiberCut,         // Offline, suspected fiber cut (no dying gasp)
    #[default]
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
    if config.vendor == "auto" {
        // Auto-detect by probing sysObjectID/sysDescr via SNMP on first use.
        // Detection is async, so it cannot run inside this sync factory; the
        // wrapper resolves the real vendor collector on the first collect()
        // and hard-errors if detection fails — it never silently degrades to
        // the generic IF-MIB collector (which collects zero ONT optical data).
        return Ok(Box::new(AutoDetectCollector::new(config)?));
    }

    create_collector_for_vendor(&config.vendor, config)
}

/// Create a collector for an explicitly named vendor.
/// Unknown vendor names are a configuration error, not a silent generic.
fn create_collector_for_vendor(vendor: &str, config: &OltConfig) -> anyhow::Result<Box<dyn OltCollector>> {
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
        "generic" => Ok(Box::new(generic::GenericCollector::new(config))),
        other => Err(anyhow::anyhow!(
            "Unknown vendor \"{}\" configured for {}: supported vendors are \
             huawei, zte, fiberhome, intelbras, datacom, parks, bdcom, vsol, \
             cdata, ubiquiti, nokia, adtran, generic, or \"auto\" for \
             sysObjectID-based detection",
            other, config.ip
        )),
    }
}

/// Map a sysObjectID / sysDescr pair to a vendor collector name, extending
/// `SnmpPoller::detect_vendor` with enterprises it does not know about.
///
/// Enterprise numbers verified against real captures in
/// data/external/snmp-dumps/ (LibreNMS snmpsim fixtures from production gear):
///   - CData OLTs report sysObjectID = 1.3.6.1.4.1.17409 (NSCRTV enterprise,
///     not CData's own 34592) — cdata/librenms_cdata.snmprec
///   - VSOL V1600D reports 1.3.6.1.4.1.37950.1.1.5.10.14.1 —
///     vsol/librenms_vsolution_v1600d.snmprec
///   - Newer Parks gear reports 1.3.6.1.4.1.50224.x (older uses 6771) —
///     parks/librenms_parks-switch.snmprec
fn refine_detected_vendor(vendor: &str, sys_oid: &str, sys_descr: &str) -> String {
    if vendor != "generic" {
        return vendor.to_string();
    }
    let descr = sys_descr.to_lowercase();
    if sys_oid.starts_with("1.3.6.1.4.1.37950") || descr.contains("v1600") {
        "vsol".into()
    } else if sys_oid.starts_with("1.3.6.1.4.1.34592") {
        "cdata".into()
    } else if sys_oid.starts_with("1.3.6.1.4.1.50224") || sys_oid.starts_with("1.3.6.1.4.1.6771") {
        "parks".into()
    } else if sys_oid.starts_with("1.3.6.1.4.1.664") || descr.contains("adtran") {
        "adtran".into()
    } else if sys_oid == "1.3.6.1.4.1.17409" || sys_oid.starts_with("1.3.6.1.4.1.17409.") {
        // Bare NSCRTV enterprise: CData FD-series identify this way (see
        // cdata dump above). The CData collector speaks FD-MIB with NSCRTV
        // fallback semantics.
        "cdata".into()
    } else {
        vendor.to_string()
    }
}

/// Collector for `vendor = "auto"`: probes sysObjectID/sysDescr on first use,
/// then delegates to the real vendor collector. Detection failure is a hard
/// error — a pilot must never run for weeks on the generic collector
/// (zero ONT data) because of a typo'd community string.
pub struct AutoDetectCollector {
    config: OltConfig,
    olt_id: String,
    inner: tokio::sync::OnceCell<Box<dyn OltCollector>>,
}

impl AutoDetectCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        if config.snmp.is_none() {
            anyhow::bail!(
                "vendor = \"auto\" for {} requires SNMP to be configured \
                 (detection probes sysObjectID); set the vendor explicitly \
                 for NETCONF/REST-only devices",
                config.ip
            );
        }
        Ok(Self {
            olt_id: format!("auto-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            inner: tokio::sync::OnceCell::new(),
        })
    }

    async fn resolve(&self) -> anyhow::Result<&Box<dyn OltCollector>> {
        self.inner
            .get_or_try_init(|| async {
                let snmp_cfg = self.config.snmp.as_ref()
                    .expect("checked in new()");
                let poller = crate::snmp::SnmpPoller::new(&self.config.ip, snmp_cfg)?;
                let (vendor, sys_oid, sys_descr) = poller.detect_vendor().await
                    .map_err(|e| anyhow::anyhow!(
                        "vendor auto-detection failed for {}: {}. The agent \
                         refuses to fall back to the generic collector (it \
                         would silently collect zero ONT data). Check SNMP \
                         reachability/community, or set vendor explicitly.",
                        self.config.ip, e
                    ))?;
                let vendor = refine_detected_vendor(&vendor, &sys_oid, &sys_descr);
                if vendor == "generic" {
                    anyhow::bail!(
                        "vendor auto-detection for {} matched no supported OLT \
                         vendor (sysObjectID {}, sysDescr {:?}). Refusing to \
                         silently use the generic collector: it collects zero \
                         ONT optical data. Set vendor explicitly if this \
                         device really is a plain switch/router.",
                        self.config.ip, sys_oid, sys_descr
                    );
                }
                tracing::info!(
                    ip = %self.config.ip,
                    vendor = %vendor,
                    sys_object_id = %sys_oid,
                    "Auto-detected OLT vendor"
                );
                create_collector_for_vendor(&vendor, &self.config)
            })
            .await
    }
}

#[async_trait]
impl OltCollector for AutoDetectCollector {
    fn olt_id(&self) -> &str {
        self.inner.get().map(|c| c.olt_id()).unwrap_or(&self.olt_id)
    }

    fn vendor_name(&self) -> &str {
        self.inner.get().map(|c| c.vendor_name()).unwrap_or("auto")
    }

    async fn collect(&self) -> anyhow::Result<OltData> {
        self.resolve().await?.collect().await
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        self.resolve().await?.test_connection().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_refine_detected_vendor_maps_unlisted_enterprises() {
        // CData FD-series identify with the bare NSCRTV enterprise OID —
        // observed in data/external/snmp-dumps/cdata/librenms_cdata.snmprec
        // (sysObjectID = .1.3.6.1.4.1.17409).
        assert_eq!(refine_detected_vendor("generic", "1.3.6.1.4.1.17409", "zaporojskoe-olt"), "cdata");
        // VSOL V1600D — vsol/librenms_vsolution_v1600d.snmprec
        assert_eq!(refine_detected_vendor("generic", "1.3.6.1.4.1.37950.1.1.5.10.14.1", "V1600D"), "vsol");
        // Parks PK-700 — parks/librenms_parks-switch.snmprec
        assert_eq!(refine_detected_vendor("generic", "1.3.6.1.4.1.50224.3.1.1", "PK-700"), "parks");
        // Adtran PEN is 664 (NOT 18070 — see audit finding 11)
        assert_eq!(refine_detected_vendor("generic", "1.3.6.1.4.1.664.1.1", "SDX 6320"), "adtran");
        // Vendors detect_vendor already resolved pass through untouched
        assert_eq!(refine_detected_vendor("huawei", "1.3.6.1.4.1.2011.2.80", "MA5800"), "huawei");
        // Genuinely unknown stays generic (and resolve() then hard-errors)
        assert_eq!(refine_detected_vendor("generic", "1.3.6.1.4.1.8072.3.2.10", "Linux"), "generic");
    }

    #[test]
    fn test_ont_data_new_optional_fields_skip_null_serialization() {
        // FEC/BIP counters must not bloat Elastic/audit JSON with nulls.
        let ont = OntData {
            serial_number: "TEST-001".into(),
            pon_port: "0/1/0".into(),
            status: OntStatus::Online,
            ..Default::default()
        };
        let json = serde_json::to_value(&ont).unwrap();
        for key in ["fec_corrected", "fec_uncorrected", "bip_errors"] {
            assert!(json.get(key).is_none(), "{key} must be skipped when None");
        }
        // Old payloads without the new keys still deserialize (serde default).
        let old: OntData = serde_json::from_value(json).unwrap();
        assert_eq!(old.fec_corrected, None);
        // ...but serialize when present.
        let with = OntData {
            fec_corrected: Some(18_234),
            fec_uncorrected: Some(2),
            bip_errors: Some(7),
            ..ont
        };
        let json = serde_json::to_value(&with).unwrap();
        assert_eq!(json["fec_corrected"], 18_234);
        assert_eq!(json["fec_uncorrected"], 2);
        assert_eq!(json["bip_errors"], 7);
    }

    #[test]
    fn test_create_collector_rejects_unknown_vendor() {
        let cfg = test_config("notavendor");
        let err = create_collector(&cfg).err().expect("unknown vendor must error");
        assert!(err.to_string().contains("Unknown vendor"));
    }

    #[test]
    fn test_create_collector_auto_requires_snmp() {
        let mut cfg = test_config("auto");
        cfg.snmp = None;
        let err = create_collector(&cfg).err().expect("auto without SNMP must error");
        assert!(err.to_string().contains("requires SNMP"));
    }

    #[tokio::test]
    async fn test_auto_collector_hard_errors_when_detection_fails() {
        // Point at an unroutable address with a tiny timeout: detection must
        // surface a hard error mentioning the refusal to go generic — not an
        // Ok(OltData) with zero ONTs.
        let cfg = test_config("auto");
        let collector = create_collector(&cfg).expect("auto collector should construct");
        assert_eq!(collector.vendor_name(), "auto");
        let err = collector.collect().await.err().expect("detection must fail");
        assert!(
            err.to_string().contains("auto-detection failed"),
            "unexpected error: {err}"
        );
        assert!(err.to_string().contains("generic collector"));
    }

    #[tokio::test]
    async fn test_auto_collector_resolves_vendor_from_mocked_sysobjectid() {
        // Mock SNMP agent answering sysDescr + sysObjectID as a Huawei MA5800.
        let addr = spawn_sysinfo_mock_agent(
            "MA5800-X7 Huawei Integrated Access Software",
            "1.3.6.1.4.1.2011.2.80.108",
        )
        .await;

        let mut cfg = test_config("auto");
        cfg.ip = addr.ip().to_string();
        if let Some(s) = cfg.snmp.as_mut() {
            s.port = addr.port();
        }

        let collector = AutoDetectCollector::new(&cfg).unwrap();
        let resolved = collector.resolve().await.expect("detection should succeed");
        assert_eq!(resolved.vendor_name(), "huawei");
        // After resolution the wrapper reports the inner collector's identity
        assert_eq!(collector.vendor_name(), "huawei");
    }

    fn test_config(vendor: &str) -> OltConfig {
        OltConfig {
            name: "test".into(),
            vendor: vendor.into(),
            // TEST-NET-1 (RFC 5737): guaranteed unroutable in real networks
            ip: "192.0.2.1".into(),
            model: String::new(),
            snmp: Some(crate::config::SnmpConfig {
                version: "v2c".into(),
                community: Some("test".into()),
                v3: None,
                port: 161,
                timeout_ms: 100,
                max_repetitions: 10,
            }),
            ssh: None,
            netconf: None,
            rest_api: None,
            grpc: None,
        }
    }

    /// Minimal loopback SNMP agent that answers GETs for sysDescr (string)
    /// and sysObjectID (OID) — enough to drive detect_vendor.
    async fn spawn_sysinfo_mock_agent(sys_descr: &str, sys_oid: &str) -> std::net::SocketAddr {
        use rasn_smi::v2::{ObjectSyntax, SimpleSyntax};
        use rasn_snmp::v2::{Pdu, Pdus, Response, VarBind, VarBindValue};

        let sys_descr = sys_descr.to_string();
        let sys_oid = sys_oid.to_string();
        let socket = tokio::net::UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let addr = socket.local_addr().unwrap();

        tokio::spawn(async move {
            let parse_oid = |s: &str| {
                let arcs: Vec<u32> = s.split('.').map(|p| p.parse().unwrap()).collect();
                rasn::types::ObjectIdentifier::new_unchecked(arcs.into())
            };
            let mut buf = vec![0u8; 65535];
            while let Ok((len, peer)) = socket.recv_from(&mut buf).await {
                let msg: rasn_snmp::v2c::Message<Pdus> =
                    match rasn::ber::decode(&buf[..len]) {
                        Ok(m) => m,
                        Err(_) => continue,
                    };
                let req = match msg.data {
                    Pdus::GetRequest(p) => p.0,
                    _ => continue,
                };
                let name = req.variable_bindings[0]
                    .name
                    .iter()
                    .map(|a| a.to_string())
                    .collect::<Vec<_>>()
                    .join(".");
                let value = if name == "1.3.6.1.2.1.1.1.0" {
                    VarBindValue::Value(ObjectSyntax::Simple(SimpleSyntax::String(
                        sys_descr.clone().into_bytes().into(),
                    )))
                } else if name == "1.3.6.1.2.1.1.2.0" {
                    VarBindValue::Value(ObjectSyntax::Simple(SimpleSyntax::ObjectId(
                        parse_oid(&sys_oid),
                    )))
                } else {
                    VarBindValue::NoSuchObject
                };
                let reply = rasn_snmp::v2c::Message {
                    version: 1.into(),
                    community: msg.community.clone(),
                    data: Pdus::Response(Response(Pdu {
                        request_id: req.request_id,
                        error_status: 0,
                        error_index: 0,
                        variable_bindings: vec![VarBind {
                            name: req.variable_bindings[0].name.clone(),
                            value,
                        }],
                    })),
                };
                let _ = socket.send_to(&rasn::ber::encode(&reply).unwrap(), peer).await;
            }
        });
        addr
    }
}
