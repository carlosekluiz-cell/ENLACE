// SPDX-License-Identifier: Apache-2.0
// SNMP Polling Engine
//
// Supports SNMPv2c with async UDP transport.
// Uses GetBulk for efficient table walking.
// Designed for high-throughput polling of thousands of ONTs per OLT.
//
// Standard MIBs used (work on ALL vendors, zero licensing):
//   - IF-MIB (RFC 2863): Interface traffic, status, errors
//   - SNMPv2-MIB (RFC 3418): sysDescr, sysObjectID, sysUpTime
//   - ENTITY-MIB (RFC 4133): Physical inventory
//
// Vendor-private OIDs are queried NUMERICALLY — no MIB files needed.

use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::time::Duration;
use thiserror::Error;
use tracing::{debug, trace, warn};

/// Well-known SNMP OIDs (standard, works on every device)
pub mod oids {
    // SNMPv2-MIB
    pub const SYS_DESCR: &str = "1.3.6.1.2.1.1.1.0";
    pub const SYS_OBJECT_ID: &str = "1.3.6.1.2.1.1.2.0";
    pub const SYS_UPTIME: &str = "1.3.6.1.2.1.1.3.0";
    pub const SYS_NAME: &str = "1.3.6.1.2.1.1.5.0";
    pub const SYS_LOCATION: &str = "1.3.6.1.2.1.1.6.0";

    // IF-MIB (interface table)
    pub const IF_TABLE: &str = "1.3.6.1.2.1.2.2";
    pub const IF_DESCR: &str = "1.3.6.1.2.1.2.2.1.2";
    pub const IF_TYPE: &str = "1.3.6.1.2.1.2.2.1.3";
    pub const IF_SPEED: &str = "1.3.6.1.2.1.2.2.1.5";
    pub const IF_OPER_STATUS: &str = "1.3.6.1.2.1.2.2.1.8";
    pub const IF_HC_IN_OCTETS: &str = "1.3.6.1.2.1.31.1.1.1.6";
    pub const IF_HC_OUT_OCTETS: &str = "1.3.6.1.2.1.31.1.1.1.10";

    // ENTITY-MIB
    pub const ENT_PHYSICAL_DESCR: &str = "1.3.6.1.2.1.47.1.1.1.1.2";
    pub const ENT_PHYSICAL_NAME: &str = "1.3.6.1.2.1.47.1.1.1.1.7";
    pub const ENT_PHYSICAL_SERIAL: &str = "1.3.6.1.2.1.47.1.1.1.1.11";
    pub const ENT_PHYSICAL_MFG: &str = "1.3.6.1.2.1.47.1.1.1.1.12";
    pub const ENT_PHYSICAL_MODEL: &str = "1.3.6.1.2.1.47.1.1.1.1.13";

    pub mod enterprise {
        pub const HUAWEI: &str = "1.3.6.1.4.1.2011";
        pub const ZTE: &str = "1.3.6.1.4.1.3902";
        pub const FIBERHOME: &str = "1.3.6.1.4.1.5875";
        pub const DATACOM: &str = "1.3.6.1.4.1.3709";
        pub const INTELBRAS_NATIVE: &str = "1.3.6.1.4.1.13464";
        pub const PARKS: &str = "1.3.6.1.4.1.6771";
        pub const BDCOM: &str = "1.3.6.1.4.1.3320";
        pub const NOKIA: &str = "1.3.6.1.4.1.637";
        pub const UBIQUITI: &str = "1.3.6.1.4.1.41112";
        pub const NSCRTV: &str = "1.3.6.1.4.1.17409";
        pub const CDATA: &str = "1.3.6.1.4.1.34592";
        pub const VSOL: &str = "1.3.6.1.4.1.37950"; // Approx — detected at runtime
    }

    pub mod huawei_sys {
        pub const CPU_RATE: &str = "1.3.6.1.4.1.2011.2.6.7.1.1.2.1.5";
        pub const BOARD_TEMP: &str = "1.3.6.1.4.1.2011.2.6.7.1.1.2.1.10";
    }

    pub mod zte_sys {
        pub const CPU_USAGE: &str = "1.3.6.1.4.1.3902.1015.2.1.1.3.1.4.0";
        pub const MEM_USAGE: &str = "1.3.6.1.4.1.3902.1015.2.1.1.3.1.6.0";
        pub const TEMPERATURE: &str = "1.3.6.1.4.1.3902.1015.2.1.1.3.1.12.0";
    }

    pub mod huawei {
        pub const ONT_TABLE: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.43.1";
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3";
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.46.1.15";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.51.1.5";
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.46.1.20";
        pub const ONT_UPTIME: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.46.1.24";
        pub const ONT_DOWN_CAUSE: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.46.1.22";
        pub const PON_BW_UTIL: &str = "1.3.6.1.4.1.2011.6.128.1.1.2.23.1";
    }

    pub mod zte {
        pub const ONT_TABLE: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.7.1";
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.7.1.11";
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.7.1.2";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.4.1.3";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.4.1.2";
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.3902.1082.500.10.2.2.7.1.8";
    }

    pub mod fiberhome {
        pub const ONT_DESCR: &str = "1.3.6.1.4.1.5875.800.3.10.1.1.1";
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.5875.800.3.10.1.1.8";
        pub const ONT_MAC: &str = "1.3.6.1.4.1.5875.800.3.10.1.1.10";
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.5875.800.3.10.1.1.11";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.5875.800.3.9.3.6.1";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.5875.800.3.9.3.3.1.7";
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.5875.800.3.9.6.1.1";
        pub const OLT_RX_POWER: &str = "1.3.6.1.4.1.5875.800.3.9.3.7.1.2";
        pub const CPU_UTIL: &str = "1.3.6.1.4.1.5875.800.3.8.6.1.1";
        pub const MEM_UTIL: &str = "1.3.6.1.4.1.5875.800.3.8.6.1.2";
        pub const TEMPERATURE: &str = "1.3.6.1.4.1.5875.800.3.8.6.1.3";
    }

    pub mod cdata {
        // FD-ONU-MIB (proprietary, recommended)
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.34592.1.3.4.1.1.3";
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.34592.1.3.4.1.1.11";
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.34592.1.3.4.1.1.13";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.34592.1.3.4.1.1.36";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.34592.1.3.4.1.1.37";
        // FD-SYSTEM-MIB
        pub const CPU_UTIL: &str = "1.3.6.1.4.1.34592.1.3.1.1.8";
        pub const MODEL_NAME: &str = "1.3.6.1.4.1.34592.1.3.1.1.1";
        pub const TEMPERATURE: &str = "1.3.6.1.4.1.34592.1.3.1.3.4";
    }

    pub mod bdcom {
        // GPON branch (.10)
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.3320.10.3.3.1.4";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.3320.10.3.4.1.2";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.3320.10.3.4.1.3";
        pub const OLT_PON_RX: &str = "1.3.6.1.4.1.3320.10.2.3.1.3";
        pub const ACTIVE_ONU_COUNT: &str = "1.3.6.1.4.1.3320.10.2.1.1.4";
        pub const INACTIVE_ONU_COUNT: &str = "1.3.6.1.4.1.3320.10.2.1.1.5";
        // System
        pub const CPU_5SEC: &str = "1.3.6.1.4.1.3320.9.109.1.1.1.1.3.1";
        pub const CPU_1MIN: &str = "1.3.6.1.4.1.3320.9.109.1.1.1.1.4.1";
        pub const MEM_UTIL: &str = "1.3.6.1.4.1.3320.9.48.1.1.1.6.1";
        pub const TEMPERATURE: &str = "1.3.6.1.4.1.3320.3.6.10.1.13";
        // EPON fallback (legacy, .101 branch)
        pub const EPON_ONT_RX: &str = "1.3.6.1.4.1.3320.101.10.5.1.5";
        pub const EPON_ONT_TX: &str = "1.3.6.1.4.1.3320.101.10.5.1.6";
    }

    pub mod datacom {
        // GPON-ONU-IF-MIB (.3709.3.6.2.1.1)
        pub const ONT_DESCR: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.3";
        pub const ONT_ADMIN_STATUS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.6";
        pub const ONT_OPER_STATUS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.7";
        pub const ONT_IN_OCTETS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.8";
        pub const ONT_IN_ERRORS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.13";
        pub const ONT_OUT_OCTETS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.15";
        pub const ONT_OUT_ERRORS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.20";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.21";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.22";
        pub const ONT_ALIAS: &str = "1.3.6.1.4.1.3709.3.6.2.1.1.23";
    }

    pub mod nokia {
        // ASAM-SYSTEM-MIB
        pub const CPU_LOAD: &str = "1.3.6.1.4.1.637.61.1.9.29.1.1.4";
        pub const MEM_TOTAL: &str = "1.3.6.1.4.1.637.61.1.9.29.2.1.1";
        pub const MEM_USAGE: &str = "1.3.6.1.4.1.637.61.1.9.29.2.1.2";
        // APON-MIB (partial — public OIDs only)
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.2";
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.3";
        pub const ONT_SW_VER: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.9";
    }

    /// NSCRTV-FTTX-GPON-MIB — Chinese national standard (enterprise .17409)
    /// Used by VSOL, Parks, and other Chinese-chipset OLTs
    pub mod nscrtv {
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.17409.2.8.4.1.1.3";
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.17409.2.8.4.1.1.7";
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.17409.2.8.4.1.1.9";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.17409.2.8.4.4.1.4";
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.17409.2.8.4.4.1.5";
        pub const ONT_BIAS: &str = "1.3.6.1.4.1.17409.2.8.4.4.1.6";
        pub const ONT_VOLTAGE: &str = "1.3.6.1.4.1.17409.2.8.4.4.1.7";
        pub const ONT_TEMPERATURE: &str = "1.3.6.1.4.1.17409.2.8.4.4.1.8";
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnmpValue {
    pub oid: String,
    pub value: SnmpData,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "value")]
pub enum SnmpData {
    Integer(i64),
    Counter32(u32),
    Counter64(u64),
    Gauge32(u32),
    OctetString(String),
    ObjectId(String),
    TimeTicks(u32),
    IpAddress(String),
    Null,
    NoSuchObject,
    NoSuchInstance,
    EndOfMibView,
}

#[derive(Error, Debug)]
pub enum SnmpError {
    #[error("SNMP timeout after {0}ms")]
    Timeout(u64),
    #[error("SNMP no response from {0}")]
    NoResponse(String),
    #[error("SNMP error: {0}")]
    Protocol(String),
    #[error("Network error: {0}")]
    Network(#[from] std::io::Error),
    #[error("Parse error: {0}")]
    Parse(String),
}

/// Parse dotted OID string → rasn ObjectIdentifier
fn parse_oid(oid_str: &str) -> Result<rasn::types::ObjectIdentifier, SnmpError> {
    let arcs: Vec<u32> = oid_str.split('.')
        .filter(|s| !s.is_empty())
        .map(|s| s.parse::<u32>().map_err(|e| SnmpError::Parse(format!("Invalid OID arc: {}", e))))
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rasn::types::ObjectIdentifier::new_unchecked(arcs.into()))
}

/// Format rasn ObjectIdentifier → dotted string
fn format_oid(oid: &rasn::types::ObjectIdentifier) -> String {
    oid.iter().map(|a| a.to_string()).collect::<Vec<_>>().join(".")
}

/// Convert an SNMPv2c VarBind value to our SnmpData enum
fn convert_varbind_value(value: &rasn_snmp::v2::VarBindValue) -> SnmpData {
    use rasn_snmp::v2::VarBindValue;
    match value {
        VarBindValue::Value(obj_syntax) => convert_object_syntax(obj_syntax),
        VarBindValue::Unspecified => SnmpData::Null,
        VarBindValue::NoSuchObject => SnmpData::NoSuchObject,
        VarBindValue::NoSuchInstance => SnmpData::NoSuchInstance,
        VarBindValue::EndOfMibView => SnmpData::EndOfMibView,
    }
}

fn convert_object_syntax(syntax: &rasn_snmp::v2::ObjectSyntax) -> SnmpData {
    use rasn_snmp::v2::ObjectSyntax;
    match syntax {
        ObjectSyntax::Simple(simple) => convert_simple_syntax(simple),
        ObjectSyntax::ApplicationWide(app) => convert_application_syntax(app),
    }
}

fn convert_simple_syntax(syntax: &rasn_smi::v2::SimpleSyntax) -> SnmpData {
    use rasn_smi::v2::SimpleSyntax;
    use num_traits::ToPrimitive;
    match syntax {
        SimpleSyntax::Integer(i) => SnmpData::Integer(i.to_i64().unwrap_or(0)),
        SimpleSyntax::String(s) => {
            // Try to interpret as UTF-8 text, fall back to hex
            match std::str::from_utf8(s) {
                Ok(text) => SnmpData::OctetString(text.to_string()),
                Err(_) => SnmpData::OctetString(hex::encode(s)),
            }
        }
        SimpleSyntax::ObjectId(oid) => SnmpData::ObjectId(format_oid(oid)),
    }
}

fn convert_application_syntax(syntax: &rasn_smi::v2::ApplicationSyntax) -> SnmpData {
    use rasn_smi::v2::ApplicationSyntax;
    match syntax {
        ApplicationSyntax::Address(addr) => {
            // NetworkAddress contains IpAddress
            let bytes = addr.0.as_ref();
            if bytes.len() == 4 {
                SnmpData::IpAddress(format!("{}.{}.{}.{}", bytes[0], bytes[1], bytes[2], bytes[3]))
            } else {
                SnmpData::IpAddress(hex::encode(bytes))
            }
        }
        ApplicationSyntax::Counter(c) => SnmpData::Counter32(c.0),
        ApplicationSyntax::Ticks(t) => SnmpData::TimeTicks(t.0),
        ApplicationSyntax::Arbitrary(o) => {
            match std::str::from_utf8(o.as_ref()) {
                Ok(text) => SnmpData::OctetString(text.to_string()),
                Err(_) => SnmpData::OctetString(hex::encode(o.as_ref())),
            }
        }
        ApplicationSyntax::BigCounter(c) => SnmpData::Counter64(c.0),
        ApplicationSyntax::Unsigned(g) => SnmpData::Gauge32(g.0),
    }
}

/// Async SNMP poller for a single device
pub struct SnmpPoller {
    target: SocketAddr,
    community: Vec<u8>,
    timeout: Duration,
    max_repetitions: u32,
    request_id: std::sync::atomic::AtomicU32,
}

impl SnmpPoller {
    pub fn new(ip: &str, config: &super::config::SnmpConfig) -> Result<Self, SnmpError> {
        let addr: SocketAddr = format!("{}:{}", ip, config.port)
            .parse()
            .map_err(|e| SnmpError::Parse(format!("Invalid address: {}", e)))?;

        let community = config
            .community
            .as_deref()
            .unwrap_or("public")
            .as_bytes()
            .to_vec();

        Ok(Self {
            target: addr,
            community,
            timeout: Duration::from_millis(config.timeout_ms),
            max_repetitions: config.max_repetitions,
            request_id: std::sync::atomic::AtomicU32::new(1),
        })
    }

    /// GET a single OID value
    pub async fn get(&self, oid: &str) -> Result<SnmpValue, SnmpError> {
        debug!(oid = oid, target = %self.target, "SNMP GET");

        let request_id = self.next_request_id();
        let pdu = self.build_get_pdu(request_id, oid)?;
        let response = self.send_receive(&pdu).await?;
        self.parse_response(&response, oid)
    }

    /// Walk a table using GetBulk (efficient for large ONT tables)
    pub async fn walk_table(&self, base_oid: &str) -> Result<Vec<SnmpValue>, SnmpError> {
        debug!(base_oid = base_oid, target = %self.target, "SNMP table walk");

        let mut results = Vec::new();
        let mut current_oid = base_oid.to_string();

        loop {
            let request_id = self.next_request_id();
            let pdu = self.build_getbulk_pdu(request_id, &current_oid, self.max_repetitions)?;

            let response = match self.send_receive(&pdu).await {
                Ok(r) => r,
                Err(SnmpError::Timeout(_)) if !results.is_empty() => {
                    warn!("Timeout during table walk after {} entries, returning partial", results.len());
                    break;
                }
                Err(e) => return Err(e),
            };

            let varbinds = self.parse_varbinds(&response)?;

            if varbinds.is_empty() {
                break;
            }

            let mut done = false;
            for vb in varbinds {
                if !vb.oid.starts_with(base_oid) {
                    done = true;
                    break;
                }
                if matches!(vb.value, SnmpData::EndOfMibView | SnmpData::NoSuchObject) {
                    done = true;
                    break;
                }
                current_oid = vb.oid.clone();
                results.push(vb);
            }

            if done {
                break;
            }

            trace!(entries = results.len(), "Table walk progress");
        }

        debug!(base_oid = base_oid, entries = results.len(), "Table walk complete");
        Ok(results)
    }

    /// Detect vendor from sysObjectID
    pub async fn detect_vendor(&self) -> Result<(String, String, String), SnmpError> {
        let sys_descr = self.get(oids::SYS_DESCR).await?;
        let sys_oid = self.get(oids::SYS_OBJECT_ID).await?;

        let descr = match sys_descr.value {
            SnmpData::OctetString(s) => s,
            _ => String::new(),
        };
        let oid = match sys_oid.value {
            SnmpData::ObjectId(s) => s,
            _ => String::new(),
        };

        let vendor = if oid.starts_with(oids::enterprise::HUAWEI) {
            "huawei"
        } else if oid.starts_with(oids::enterprise::ZTE) {
            "zte"
        } else if oid.starts_with(oids::enterprise::FIBERHOME) {
            "fiberhome"
        } else if oid.starts_with(oids::enterprise::INTELBRAS_NATIVE) {
            if descr.contains("AN5516") || descr.contains("AN6001") || descr.contains("AN6000") {
                "fiberhome"
            } else {
                "intelbras"
            }
        } else if oid.starts_with(oids::enterprise::DATACOM) {
            "datacom"
        } else if oid.starts_with(oids::enterprise::PARKS) {
            "parks"
        } else if oid.starts_with(oids::enterprise::BDCOM) {
            "bdcom"
        } else if oid.starts_with(oids::enterprise::NOKIA) {
            "nokia"
        } else if oid.starts_with(oids::enterprise::UBIQUITI) {
            "ubiquiti"
        } else {
            "generic"
        };

        Ok((vendor.to_string(), oid, descr))
    }

    // --- Internal methods ---

    fn next_request_id(&self) -> u32 {
        self.request_id.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    }

    fn build_get_pdu(&self, request_id: u32, oid: &str) -> Result<Vec<u8>, SnmpError> {
        use rasn_snmp::v2::*;

        let oid_parsed = parse_oid(oid)?;

        let varbind = VarBind {
            name: oid_parsed,
            value: VarBindValue::Unspecified,
        };

        let pdu = Pdu {
            request_id: request_id as i32,
            error_status: 0,
            error_index: 0,
            variable_bindings: vec![varbind],
        };

        let msg = rasn_snmp::v2c::Message {
            version: 1.into(),
            community: self.community.clone().into(),
            data: Pdus::GetRequest(GetRequest(pdu)),
        };

        rasn::ber::encode(&msg)
            .map_err(|e| SnmpError::Protocol(format!("BER encode error: {}", e)))
    }

    fn build_getbulk_pdu(&self, request_id: u32, oid: &str, max_reps: u32) -> Result<Vec<u8>, SnmpError> {
        use rasn_snmp::v2::*;

        let oid_parsed = parse_oid(oid)?;

        let varbind = VarBind {
            name: oid_parsed,
            value: VarBindValue::Unspecified,
        };

        let pdu = BulkPdu {
            request_id: request_id as i32,
            non_repeaters: 0,
            max_repetitions: max_reps,
            variable_bindings: vec![varbind],
        };

        let msg = rasn_snmp::v2c::Message {
            version: 1.into(),
            community: self.community.clone().into(),
            data: Pdus::GetBulkRequest(GetBulkRequest(pdu)),
        };

        rasn::ber::encode(&msg)
            .map_err(|e| SnmpError::Protocol(format!("BER encode error: {}", e)))
    }

    async fn send_receive(&self, pdu: &[u8]) -> Result<Vec<u8>, SnmpError> {
        let socket = tokio::net::UdpSocket::bind("0.0.0.0:0").await?;
        socket.send_to(pdu, self.target).await?;

        let mut buf = vec![0u8; 65535];
        match tokio::time::timeout(self.timeout, socket.recv_from(&mut buf)).await {
            Ok(Ok((len, _))) => Ok(buf[..len].to_vec()),
            Ok(Err(e)) => Err(SnmpError::Network(e)),
            Err(_) => Err(SnmpError::Timeout(self.timeout.as_millis() as u64)),
        }
    }

    fn parse_response(&self, response: &[u8], oid: &str) -> Result<SnmpValue, SnmpError> {
        use rasn_snmp::v2::*;

        let msg: rasn_snmp::v2c::Message<Pdus> = rasn::ber::decode(response)
            .map_err(|e| SnmpError::Parse(format!("BER decode error: {}", e)))?;

        let pdu = match msg.data {
            Pdus::Response(p) => p.0,
            other => return Err(SnmpError::Protocol(format!("Expected Response PDU, got {:?}", std::mem::discriminant(&other)))),
        };

        if pdu.error_status != 0 {
            return Err(SnmpError::Protocol(format!(
                "SNMP error status {} at index {}", pdu.error_status, pdu.error_index
            )));
        }

        if let Some(vb) = pdu.variable_bindings.first() {
            Ok(SnmpValue {
                oid: format_oid(&vb.name),
                value: convert_varbind_value(&vb.value),
                timestamp: chrono::Utc::now(),
            })
        } else {
            Err(SnmpError::Parse(format!("No varbinds in response for {}", oid)))
        }
    }

    fn parse_varbinds(&self, response: &[u8]) -> Result<Vec<SnmpValue>, SnmpError> {
        use rasn_snmp::v2::*;

        let msg: rasn_snmp::v2c::Message<Pdus> = rasn::ber::decode(response)
            .map_err(|e| SnmpError::Parse(format!("BER decode error: {}", e)))?;

        let pdu = match msg.data {
            Pdus::Response(p) => p.0,
            other => return Err(SnmpError::Protocol(format!("Expected Response PDU, got {:?}", std::mem::discriminant(&other)))),
        };

        let now = chrono::Utc::now();
        let results: Vec<SnmpValue> = pdu.variable_bindings.iter()
            .map(|vb| SnmpValue {
                oid: format_oid(&vb.name),
                value: convert_varbind_value(&vb.value),
                timestamp: now,
            })
            .collect();

        Ok(results)
    }
}

/// Hex encoding helper (rasn uses bytes for OctetString)
mod hex {
    pub fn encode(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_oid() {
        let oid = parse_oid("1.3.6.1.2.1.1.1.0").unwrap();
        assert_eq!(format_oid(&oid), "1.3.6.1.2.1.1.1.0");
    }

    #[test]
    fn test_build_get_pdu_roundtrip() {
        let poller = SnmpPoller {
            target: "127.0.0.1:161".parse().unwrap(),
            community: b"public".to_vec(),
            timeout: Duration::from_secs(5),
            max_repetitions: 50,
            request_id: std::sync::atomic::AtomicU32::new(1),
        };

        let pdu = poller.build_get_pdu(1, "1.3.6.1.2.1.1.1.0").unwrap();
        assert!(!pdu.is_empty());

        // Verify it decodes back
        let msg: rasn_snmp::v2c::Message<rasn_snmp::v2::Pdus> = rasn::ber::decode(&pdu).unwrap();
        assert_eq!(msg.community.as_ref(), b"public");
        match msg.data {
            rasn_snmp::v2::Pdus::GetRequest(p) => {
                assert_eq!(p.0.request_id, 1);
                assert_eq!(p.0.variable_bindings.len(), 1);
            }
            _ => panic!("Expected GetRequest"),
        }
    }

    #[test]
    fn test_sysdescr_get_hex_dump_and_roundtrip() {
        // Build a real SNMPv2c GET for sysDescr (1.3.6.1.2.1.1.1.0)
        let poller = SnmpPoller {
            target: "127.0.0.1:161".parse().unwrap(),
            community: b"public".to_vec(),
            timeout: Duration::from_secs(5),
            max_repetitions: 50,
            request_id: std::sync::atomic::AtomicU32::new(42),
        };

        let pdu = poller.build_get_pdu(42, "1.3.6.1.2.1.1.1.0").unwrap();

        // Print hex dump for manual verification
        let hex_str: String = pdu.iter().map(|b| format!("{:02x}", b)).collect::<Vec<_>>().join(" ");
        eprintln!("SNMPv2c GET sysDescr hex ({} bytes): {}", pdu.len(), hex_str);

        // Verify BER structure:
        // 30 xx          SEQUENCE (Message)
        //   02 01 01     INTEGER 1 (version = SNMPv2c)
        //   04 06 70 75 62 6c 69 63  OCTET STRING "public"
        //   a0 xx        [0] CONSTRUCTED (GetRequest)
        //     02 xx xx   INTEGER (request-id = 42)
        //     02 01 00   INTEGER 0 (error-status)
        //     02 01 00   INTEGER 0 (error-index)
        //     30 xx      SEQUENCE (varbind list)
        //       30 xx    SEQUENCE (varbind)
        //         06 08 2b 06 01 02 01 01 01 00  OID 1.3.6.1.2.1.1.1.0
        //         05 00  NULL (unspecified)

        // Verify BER byte structure manually against known encoding:
        // 30 26          SEQUENCE (len=38)
        //   02 01 01     INTEGER 1 (version)
        //   04 06 "public"  OCTET STRING (community)
        //   a0 19        [0] GetRequest (len=25)
        //     02 01 2a   INTEGER 42 (request-id)
        //     02 01 00   INTEGER 0 (error-status)
        //     02 01 00   INTEGER 0 (error-index)
        //     30 0e      SEQUENCE (varbind list)
        //       30 0c    SEQUENCE (varbind)
        //         06 08 2b 06 01 02 01 01 01 00  OID 1.3.6.1.2.1.1.1.0
        //         05 00  NULL
        assert_eq!(pdu[0], 0x30, "outer SEQUENCE tag");
        assert_eq!(pdu[2], 0x02, "version tag = INTEGER");
        assert_eq!(pdu[3], 0x01, "version length = 1");
        assert_eq!(pdu[4], 0x01, "version value = 1 (SNMPv2c)");
        assert_eq!(pdu[5], 0x04, "community tag = OCTET STRING");
        assert_eq!(pdu[6], 0x06, "community length = 6");
        assert_eq!(&pdu[7..13], b"public");
        assert_eq!(pdu[13], 0xa0, "GetRequest context tag [0]");
        assert_eq!(pdu[15], 0x02, "request-id tag = INTEGER");
        assert_eq!(pdu[17], 0x2a, "request-id value = 42");

        // Decode back and verify full round-trip
        let msg: rasn_snmp::v2c::Message<rasn_snmp::v2::Pdus> = rasn::ber::decode(&pdu).unwrap();
        assert_eq!(msg.community.as_ref(), b"public");
        match msg.data {
            rasn_snmp::v2::Pdus::GetRequest(p) => {
                assert_eq!(p.0.request_id, 42);
                assert_eq!(p.0.error_status, 0);
                assert_eq!(p.0.error_index, 0);
                assert_eq!(p.0.variable_bindings.len(), 1);
                let vb = &p.0.variable_bindings[0];
                assert_eq!(format_oid(&vb.name), "1.3.6.1.2.1.1.1.0");
                assert!(matches!(vb.value, rasn_snmp::v2::VarBindValue::Unspecified));
            }
            _ => panic!("Expected GetRequest"),
        }
    }

    #[test]
    fn test_build_getbulk_pdu_roundtrip() {
        let poller = SnmpPoller {
            target: "127.0.0.1:161".parse().unwrap(),
            community: b"public".to_vec(),
            timeout: Duration::from_secs(5),
            max_repetitions: 50,
            request_id: std::sync::atomic::AtomicU32::new(1),
        };

        let pdu = poller.build_getbulk_pdu(1, "1.3.6.1.2.1.2.2.1.2", 25).unwrap();
        assert!(!pdu.is_empty());

        let msg: rasn_snmp::v2c::Message<rasn_snmp::v2::Pdus> = rasn::ber::decode(&pdu).unwrap();
        match msg.data {
            rasn_snmp::v2::Pdus::GetBulkRequest(p) => {
                assert_eq!(p.0.max_repetitions, 25);
                assert_eq!(p.0.non_repeaters, 0);
            }
            _ => panic!("Expected GetBulkRequest"),
        }
    }
}
