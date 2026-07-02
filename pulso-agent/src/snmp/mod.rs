// SPDX-License-Identifier: Apache-2.0
// SNMP Polling Engine
//
// Supports SNMPv2c and SNMPv3 (USM: noAuthNoPriv / authNoPriv / authPriv,
// see snmp::usm) with async UDP transport.
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

pub(crate) mod usm;

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
        /// Newer Parks gear registers under 50224 (older uses 6771) —
        /// data/external/snmp-dumps/parks/librenms_parks-switch.snmprec
        pub const PARKS_NEW: &str = "1.3.6.1.4.1.50224";
        /// Adtran PEN is 664 (NOT 18070 — see audit finding 11)
        pub const ADTRAN: &str = "1.3.6.1.4.1.664";
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
        // The previous OID set here (3902.1082.500.10.2.2.7.1.x / .4.1.x) is
        // documented NOWHERE (vendor MIBs, LibreNMS, Zabbix templates, forums)
        // and was replaced wholesale — including the suspected RX/TX swap —
        // with community-verified OIDs.
        //
        // ZXA10 C300/C320 V2.1 firmware (zxAnPon/zxGpon tree, .1012):
        // zxGponOntPhaseState — 1=logging 2=los 3=syncMib 4=working
        // 5=dyingGasp 6=authFailed 7=offline
        // (chinnurtb/xiaoli node/monitd/include/snmp/zte.hrl; SmartOLT/Zabbix
        // community templates)
        pub const ONT_PHASE_STATE: &str = "1.3.6.1.4.1.3902.1012.3.28.2.1.4";
        /// zxGponOntDevMgmtProvisionSn (chinnurtb/xiaoli zte.hrl)
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.3902.1012.3.28.1.1.5";
        /// ONT-side RX power, dBm = value*0.002-30
        /// (local.com.ua topic 76498; go-snmp-olt-zte-c320)
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.3902.1012.3.50.12.1.1.10";
        /// ONT TX power, same table/scaling (go-api-c320 config, V2.x profile)
        pub const ONT_TX_POWER: &str = "1.3.6.1.4.1.3902.1012.3.50.12.1.1.14";
        /// zxAnPonRtdOnuDistance, metres — verified against the real C320 walk
        /// data/external/snmp-dumps/zte/librenms_zxa10_c320.snmprec
        /// (values 1235..3743 m) and local.com.ua topic 76498.
        pub const ONT_DISTANCE: &str = "1.3.6.1.4.1.3902.1012.3.11.4.1.2";

        // ZXA10 C320 V2.2+ / C6xx Titan (zxAnGpon tree, .1082.500) — OIDs from
        // github.com/s4lfanet/go-api-c320 (config package, "Firmware V2.2+"
        // profile). Scaling on V2_ONT_RX_POWER is NOT independently verified;
        // readings are gated by the plausibility window.
        pub const V2_ONT_STATUS: &str = "1.3.6.1.4.1.3902.1082.500.10.2.3.8.1.4";
        pub const V2_ONT_SERIAL: &str = "1.3.6.1.4.1.3902.1082.500.10.2.3.3.1.18";
        pub const V2_ONT_RX_POWER: &str = "1.3.6.1.4.1.3902.1082.500.20.2.2.2.1.10";
        pub const V2_ONT_DISTANCE: &str = "1.3.6.1.4.1.3902.1082.500.10.2.3.10.1.2";
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
        // EPON fallback (legacy, .101 branch).
        // Index/scaling verified against a real P3608B capture with CLI
        // cross-check (data/external/snmp-dumps/bdcom/
        // nagwiki_bdcom_p3608b_gp3600-08b_excerpts.txt):
        //   EPON_ONT_STATUS rows: .5.<ponIfIndex>.<onuId> (5=online, 2=dereg)
        //   EPON_ONT_RX/TX rows: .<onuIfIndex>, units 0.1 dBm
        //   (SNMP -226 ↔ CLI -22.7 dBm; SNMP 17 ↔ CLI 1.7 dBm)
        pub const EPON_ONT_STATUS: &str = "1.3.6.1.4.1.3320.101.11.4.1.5";
        pub const EPON_ONT_RX: &str = "1.3.6.1.4.1.3320.101.10.5.1.5";
        pub const EPON_ONT_TX: &str = "1.3.6.1.4.1.3320.101.10.5.1.6";
        /// OLT-side RX per ONU, 0.1 dBm, indexed by ONU ifIndex
        /// (same capture: -340 ↔ CLI -34.0 dBm)
        pub const EPON_OLT_RX_PER_ONU: &str = "1.3.6.1.4.1.3320.101.108.1.3";
    }

    pub mod datacom {
        // GPON-ONU-IF-MIB onuIfTable (.3709.3.6.2.1.1) — VERIFIED against
        // the official "DmOS MIB Reference 204.4381.02" (DmOS 9.4.0, §29)
        // and github.com/datacom-teracom/dmos-zabbix-template.
        // NOTE: ONT_TX_POWER (.21 onuIfOnuPowerTx) and ONT_RX_POWER
        // (.22 onuIfOnuPowerRx) return STRINGS in dBm, not scaled integers.
        // Index is the table's own flat onuifIndex; PON port / ONU id are
        // parsed from onuifDescr ("gpon-1/1/1-onu-1").
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
        // ASAM-SYSTEM-MIB (asam = 637.61.1; present in the real 7360 walk
        // data/external/snmp-dumps/nokia/librenms_nokia-isam.snmprec)
        pub const CPU_LOAD: &str = "1.3.6.1.4.1.637.61.1.9.29.1.1.4";
        pub const MEM_TOTAL: &str = "1.3.6.1.4.1.637.61.1.9.29.2.1.1";
        pub const MEM_USAGE: &str = "1.3.6.1.4.1.637.61.1.9.29.2.1.2";
        // APON-MIB ({asam 35}) — the GPON/BPON ONT MIB is only distributed
        // with ISAM software (customer-gated), so these columns are only
        // partially corroborated: .35.10.1.1.9 confirmed as "active ONT sw
        // version" (SolarWinds THWACK #99271), .35.10.18.1.2 sighted as
        // OLT-side RX per ONT (community.librenms.org/t/22334) with unknown
        // index/scaling. ONT_STATUS/ONT_SERIAL below are UNVERIFIED; the
        // collector treats an empty walk as "not supported", never fabricates.
        pub const ONT_STATUS: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.2";
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.3";
        pub const ONT_SW_VER: &str = "1.3.6.1.4.1.637.61.1.35.10.1.1.9";
    }

    /// NSCRTV-FTTX-GPON-MIB — Chinese national standard (enterprise .17409)
    /// Used by VSOL, Parks, and other Chinese-chipset OLTs.
    ///
    /// Verified against the MIB text itself:
    /// https://github.com/librenms/librenms/blob/master/mibs/cdata/NSCRTV-FTTX-GPON-MIB
    ///   - gponOnuInfoTable (…4.1.1) INDEX is a packed GponDeviceIndex:
    ///     device<<24 | slot<<16 | pon<<8 | onuId
    ///   - onuOperationStatus: up(1), down(2)
    ///   - onuTestDistance: UNITS "Meter"
    ///   - optical table (…4.4.1) columns: UNITS "centi-dBm" (dBm = v/100),
    ///     bias "centi-mA", temperature "Centi-degree centigrade"
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

    /// VSOL-native GPON tables (V1600G family, enterprise .37950) — optical
    /// values are ASCII strings like "-19.32(dBm)".
    /// Source: github.com/LuizQuintana/TEMPLATES_OLT_VSOL_GPON (Zabbix
    /// template "Template Olt vsol 1600g"); LibreNMS PR #14853 (os vsolution).
    pub mod vsol_native {
        pub const ONT_SERIAL: &str = "1.3.6.1.4.1.37950.1.1.6.1.1.2.1.5";
        pub const ONT_RX_POWER: &str = "1.3.6.1.4.1.37950.1.1.6.1.1.3.1.7";
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
    #[error("SNMP configuration error: {0}")]
    Config(String),
    #[error("SNMP walk of {base_oid} incomplete after {rows} rows: {source}")]
    PartialWalk {
        base_oid: String,
        rows: usize,
        #[source]
        source: Box<SnmpError>,
    },
}

/// Retransmits per PDU after the initial attempt (total attempts = SNMP_RETRANSMITS + 1).
const SNMP_RETRANSMITS: u32 = 2;
/// Base delay between retransmits; doubles on each retry.
const RETRANSMIT_BACKOFF: Duration = Duration::from_millis(200);
/// Safety backstop: abort any table walk that returns more rows than this
/// (a healthy 16-port OLT tops out well below this; beyond it we are almost
/// certainly looping on buggy firmware).
const MAX_WALK_ROWS: usize = 200_000;

/// True if `oid` is a strict child of `prefix`, aligned on a component boundary.
/// Plain `starts_with` would let "1.3.6.1.2.1.2.2.1.10.1" match prefix
/// "1.3.6.1.2.1.2.2.1.1" and bleed the adjacent column into the walk.
fn oid_has_prefix(oid: &str, prefix: &str) -> bool {
    oid.strip_prefix(prefix)
        .map_or(false, |rest| rest.starts_with('.'))
}

/// Numeric component-wise OID comparison. String comparison is wrong for OIDs
/// ("10" sorts before "9" lexicographically).
fn compare_oids(a: &str, b: &str) -> std::cmp::Ordering {
    let parse = |s: &str| {
        s.split('.')
            .filter(|p| !p.is_empty())
            .map(|p| p.parse::<u64>().unwrap_or(0))
            .collect::<Vec<_>>()
    };
    parse(a).cmp(&parse(b))
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

/// Wire security for a poller: classic v2c community or a full SNMPv3 USM
/// session (engine discovery, HMAC auth, AES privacy — see snmp::usm).
enum Security {
    V2c { community: Vec<u8> },
    V3(usm::V3Session),
}

/// Async SNMP poller for a single device
pub struct SnmpPoller {
    target: SocketAddr,
    security: Security,
    timeout: Duration,
    max_repetitions: u32,
    max_walk_rows: usize,
    request_id: std::sync::atomic::AtomicU32,
}

impl SnmpPoller {
    pub fn new(ip: &str, config: &super::config::SnmpConfig) -> Result<Self, SnmpError> {
        let version = config.version.trim().to_ascii_lowercase();
        let security = match version.as_str() {
            "v2c" | "2c" => {
                // Never fall back to community "public" — a wrong community must
                // surface as a config error, not as an agent that silently polls
                // nothing.
                let community = config
                    .community
                    .as_deref()
                    .ok_or_else(|| {
                        SnmpError::Config(format!(
                            "SNMPv2c configured for {} without a community string; \
                             set snmp.community (refusing to default to \"public\")",
                            ip
                        ))
                    })?
                    .as_bytes()
                    .to_vec();
                Security::V2c { community }
            }
            "v3" | "3" => {
                let v3 = config.v3.as_ref().ok_or_else(|| {
                    SnmpError::Config(format!(
                        "SNMPv3 configured for {} without credentials; add an \
                         [olts.snmp.v3] section with at least a username",
                        ip
                    ))
                })?;
                let session = usm::V3Session::from_config(v3).map_err(|e| {
                    SnmpError::Config(format!("SNMPv3 configuration for {}: {}", ip, e))
                })?;
                Security::V3(session)
            }
            _ => {
                return Err(SnmpError::Config(format!(
                    "SNMP version \"{}\" configured for {} is not supported \
                     (supported: \"v2c\", \"v3\")",
                    config.version, ip
                )))
            }
        };

        let addr: SocketAddr = format!("{}:{}", ip, config.port)
            .parse()
            .map_err(|e| SnmpError::Parse(format!("Invalid address: {}", e)))?;

        Ok(Self {
            target: addr,
            security,
            timeout: Duration::from_millis(config.timeout_ms),
            max_repetitions: config.max_repetitions,
            max_walk_rows: MAX_WALK_ROWS,
            request_id: std::sync::atomic::AtomicU32::new(1),
        })
    }

    /// GET a single OID value
    pub async fn get(&self, oid: &str) -> Result<SnmpValue, SnmpError> {
        debug!(oid = oid, target = %self.target, "SNMP GET");

        let request_id = self.next_request_id();
        let request = build_get_request(request_id, oid)?;
        let pdu = self.transact(request).await?;

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

    /// Walk a table using GetBulk (efficient for large ONT tables).
    ///
    /// A walk that fails mid-way returns `SnmpError::PartialWalk` — never `Ok`
    /// with silently missing rows (downstream would read the missing ONTs as a
    /// mass outage and page the NOC for a fibre cut that never happened).
    pub async fn walk_table(&self, base_oid: &str) -> Result<Vec<SnmpValue>, SnmpError> {
        debug!(base_oid = base_oid, target = %self.target, "SNMP table walk");

        let mut results: Vec<SnmpValue> = Vec::new();
        let mut current_oid = base_oid.to_string();

        loop {
            let request_id = self.next_request_id();
            let request = build_getbulk_request(request_id, &current_oid, self.max_repetitions)?;

            let pdu = match self.transact(request).await {
                Ok(r) => r,
                Err(e) if !results.is_empty() => {
                    warn!(
                        base_oid = base_oid,
                        rows = results.len(),
                        error = %e,
                        "SNMP walk failed mid-way; discarding partial result"
                    );
                    return Err(SnmpError::PartialWalk {
                        base_oid: base_oid.to_string(),
                        rows: results.len(),
                        source: Box::new(e),
                    });
                }
                Err(e) => return Err(e),
            };

            let now = chrono::Utc::now();
            let varbinds: Vec<SnmpValue> = pdu
                .variable_bindings
                .iter()
                .map(|vb| SnmpValue {
                    oid: format_oid(&vb.name),
                    value: convert_varbind_value(&vb.value),
                    timestamp: now,
                })
                .collect();

            if varbinds.is_empty() {
                break;
            }

            let mut done = false;
            for vb in varbinds {
                if !oid_has_prefix(&vb.oid, base_oid) {
                    done = true;
                    break;
                }
                if matches!(vb.value, SnmpData::EndOfMibView | SnmpData::NoSuchObject) {
                    done = true;
                    break;
                }
                // Forward-progress guard: buggy firmware that repeats or rewinds
                // OIDs would otherwise loop forever.
                if compare_oids(&vb.oid, &current_oid) != std::cmp::Ordering::Greater {
                    return Err(SnmpError::Protocol(format!(
                        "SNMP walk of {} not advancing: agent returned {} after {} (buggy firmware?)",
                        base_oid, vb.oid, current_oid
                    )));
                }
                current_oid = vb.oid.clone();
                results.push(vb);
                if results.len() > self.max_walk_rows {
                    return Err(SnmpError::Protocol(format!(
                        "SNMP walk of {} exceeded {} rows; aborting runaway walk",
                        base_oid, self.max_walk_rows
                    )));
                }
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

        let vendor = vendor_from_sysinfo(&oid, &descr);

        Ok((vendor.to_string(), oid, descr))
    }

    // --- Internal methods ---

    fn next_request_id(&self) -> u32 {
        self.request_id.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    }

    /// Send a request PDU using whichever wire security is configured and
    /// return the Response PDU. The v2c and v3 paths share the same
    /// retransmit / timeout machinery (`send_receive`); v3 additionally does
    /// engine discovery, HMAC authentication, encryption, and Report handling.
    async fn transact(&self, request: rasn_snmp::v2::Pdus) -> Result<rasn_snmp::v2::Pdu, SnmpError> {
        match &self.security {
            Security::V2c { community } => {
                let bytes = encode_v2c(community, request)?;
                let raw = self.send_receive(&bytes).await?;
                let resp: rasn_snmp::v2c::Message<rasn_snmp::v2::Pdus> = rasn::ber::decode(&raw)
                    .map_err(|e| SnmpError::Parse(format!("BER decode error: {}", e)))?;
                expect_response(resp.data)
            }
            Security::V3(session) => self.transact_v3(session, request).await,
        }
    }

    async fn transact_v3(
        &self,
        session: &usm::V3Session,
        request: rasn_snmp::v2::Pdus,
    ) -> Result<rasn_snmp::v2::Pdu, SnmpError> {
        // RFC 3414 §4: discover the authoritative engine ID (and boots/time)
        // before the first real request.
        if session.needs_discovery() {
            let msg_id = self.next_request_id();
            let probe_rid = self.next_request_id();
            let probe = session.build_discovery(msg_id, probe_rid)?;
            debug!(target = %self.target, "SNMPv3 engine discovery");
            let raw = self.send_receive(&probe).await?;
            session.absorb_discovery(&raw)?;
            debug!(
                target = %self.target,
                engine_id = %session.engine_id().map(|e| hex::encode(&e)).unwrap_or_default(),
                level = session.security_level(),
                "SNMPv3 engine discovered"
            );
        }

        let mut resynced = false;
        loop {
            let msg_id = self.next_request_id();
            let bytes = session.wrap(msg_id, request.clone())?;
            let raw = self.send_receive(&bytes).await?;
            match session.unwrap(&raw, msg_id)? {
                usm::V3Reply::Response(pdu) => {
                    if pdu.error_status != 0 {
                        return Err(SnmpError::Protocol(format!(
                            "SNMP error status {} at index {}",
                            pdu.error_status, pdu.error_index
                        )));
                    }
                    return Ok(pdu);
                }
                usm::V3Reply::Report { stat, .. }
                    if stat == usm::ReportStat::NotInTimeWindows && !resynced =>
                {
                    // The session already resynced boots/time from the report;
                    // retry exactly once (RFC 3414 §3.2 step 7b).
                    debug!(target = %self.target, "SNMPv3 notInTimeWindows — resynced, retrying");
                    resynced = true;
                }
                usm::V3Reply::Report { stat, oid } => {
                    return Err(stat.to_error(&oid, &session.user_name()));
                }
            }
        }
    }

    /// Send a PDU with retransmits: UDP drops single datagrams routinely, and a
    /// single lost packet must not abort (or truncate) a whole table walk.
    async fn send_receive(&self, pdu: &[u8]) -> Result<Vec<u8>, SnmpError> {
        let mut last_err = SnmpError::Timeout(self.timeout.as_millis() as u64);

        for attempt in 0..=SNMP_RETRANSMITS {
            if attempt > 0 {
                let backoff = RETRANSMIT_BACKOFF * (1 << (attempt - 1));
                debug!(
                    target = %self.target,
                    attempt = attempt + 1,
                    backoff_ms = backoff.as_millis() as u64,
                    "SNMP timeout, retransmitting"
                );
                tokio::time::sleep(backoff).await;
            }

            match self.send_receive_once(pdu).await {
                Ok(r) => return Ok(r),
                // Retransmit only on timeout; protocol/network errors are not
                // transient packet loss and retrying them just adds latency.
                Err(e @ SnmpError::Timeout(_)) => last_err = e,
                Err(e) => return Err(e),
            }
        }

        Err(last_err)
    }

    async fn send_receive_once(&self, pdu: &[u8]) -> Result<Vec<u8>, SnmpError> {
        let socket = tokio::net::UdpSocket::bind("0.0.0.0:0").await?;
        socket.send_to(pdu, self.target).await?;

        let mut buf = vec![0u8; 65535];
        match tokio::time::timeout(self.timeout, socket.recv_from(&mut buf)).await {
            Ok(Ok((len, _))) => Ok(buf[..len].to_vec()),
            Ok(Err(e)) => Err(SnmpError::Network(e)),
            Err(_) => Err(SnmpError::Timeout(self.timeout.as_millis() as u64)),
        }
    }

}

/// Build a GetRequest PDU (version-independent: the v2 PDU format is shared
/// by v2c messages and v3 ScopedPDUs).
fn build_get_request(request_id: u32, oid: &str) -> Result<rasn_snmp::v2::Pdus, SnmpError> {
    use rasn_snmp::v2::*;

    let varbind = VarBind {
        name: parse_oid(oid)?,
        value: VarBindValue::Unspecified,
    };

    Ok(Pdus::GetRequest(GetRequest(Pdu {
        request_id: request_id as i32,
        error_status: 0,
        error_index: 0,
        variable_bindings: vec![varbind],
    })))
}

/// Build a GetBulkRequest PDU (version-independent, like `build_get_request`).
fn build_getbulk_request(
    request_id: u32,
    oid: &str,
    max_reps: u32,
) -> Result<rasn_snmp::v2::Pdus, SnmpError> {
    use rasn_snmp::v2::*;

    let varbind = VarBind {
        name: parse_oid(oid)?,
        value: VarBindValue::Unspecified,
    };

    Ok(Pdus::GetBulkRequest(GetBulkRequest(BulkPdu {
        request_id: request_id as i32,
        non_repeaters: 0,
        max_repetitions: max_reps,
        variable_bindings: vec![varbind],
    })))
}

/// Encode a v2c message wrapping the given request PDU.
fn encode_v2c(community: &[u8], data: rasn_snmp::v2::Pdus) -> Result<Vec<u8>, SnmpError> {
    let msg = rasn_snmp::v2c::Message {
        version: 1.into(),
        community: community.to_vec().into(),
        data,
    };
    rasn::ber::encode(&msg).map_err(|e| SnmpError::Protocol(format!("BER encode error: {}", e)))
}

/// Expect a Response PDU with error-status 0.
fn expect_response(pdus: rasn_snmp::v2::Pdus) -> Result<rasn_snmp::v2::Pdu, SnmpError> {
    use rasn_snmp::v2::Pdus;

    let pdu = match pdus {
        Pdus::Response(p) => p.0,
        other => {
            return Err(SnmpError::Protocol(format!(
                "Expected Response PDU, got {:?}",
                std::mem::discriminant(&other)
            )))
        }
    };

    if pdu.error_status != 0 {
        return Err(SnmpError::Protocol(format!(
            "SNMP error status {} at index {}",
            pdu.error_status, pdu.error_index
        )));
    }

    Ok(pdu)
}

/// Map a sysObjectID / sysDescr pair to a vendor collector name.
///
/// Keep this in sync with `vendors::refine_detected_vendor` (same enterprise
/// numbers, same order): discovery calls `detect_vendor` directly, so any
/// enterprise known only to the refine step would classify as "generic"
/// during network scans.
///
/// Enterprise numbers verified against real captures in
/// data/external/snmp-dumps/ (LibreNMS snmpsim fixtures from production gear):
///   - CData OLTs report sysObjectID = 1.3.6.1.4.1.17409 (bare NSCRTV
///     enterprise, not CData's own 34592) — cdata/librenms_cdata.snmprec
///   - VSOL V1600D reports 1.3.6.1.4.1.37950.1.1.5.10.14.1 —
///     vsol/librenms_vsolution_v1600d.snmprec
///   - Newer Parks gear reports 1.3.6.1.4.1.50224.x (older uses 6771) —
///     parks/librenms_parks-switch.snmprec
///   - Adtran PEN is 664 (NOT 18070 — see audit finding 11)
pub(crate) fn vendor_from_sysinfo(oid: &str, descr: &str) -> &'static str {
    let descr_lower = descr.to_lowercase();
    if oid.starts_with(oids::enterprise::HUAWEI) {
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
    } else if oid.starts_with(oids::enterprise::PARKS)
        || oid.starts_with(oids::enterprise::PARKS_NEW)
    {
        "parks"
    } else if oid.starts_with(oids::enterprise::BDCOM) {
        "bdcom"
    } else if oid.starts_with(oids::enterprise::NOKIA) {
        "nokia"
    } else if oid.starts_with(oids::enterprise::UBIQUITI) {
        "ubiquiti"
    } else if oid.starts_with(oids::enterprise::VSOL) || descr_lower.contains("v1600") {
        "vsol"
    } else if oid.starts_with(oids::enterprise::CDATA) {
        "cdata"
    } else if oid.starts_with(oids::enterprise::ADTRAN) || descr_lower.contains("adtran") {
        "adtran"
    } else if oid == oids::enterprise::NSCRTV
        || oid.starts_with("1.3.6.1.4.1.17409.")
    {
        // Bare NSCRTV enterprise: CData FD-series identify this way (see
        // cdata dump above). The CData collector speaks FD-MIB with NSCRTV
        // fallback semantics.
        "cdata"
    } else {
        "generic"
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
    fn test_vendor_from_sysinfo_tier1_vendors() {
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.2011.2.80.108", "MA5800-X7"), "huawei");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.3902.1012", "ZXA10 C320"), "zte");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.5875.800", "AN5516-01"), "fiberhome");
        // Rebranded FiberHome under the Intelbras enterprise
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.13464.1", "AN5516-04"), "fiberhome");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.13464.1", "G16 OLT"), "intelbras");
    }

    #[test]
    fn test_vendor_from_sysinfo_enterprise_coverage() {
        // Mirrors vendors::refine_detected_vendor — discovery calls
        // detect_vendor directly, so these must resolve here too.
        // CData FD-series report the bare NSCRTV enterprise —
        // data/external/snmp-dumps/cdata/librenms_cdata.snmprec
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.17409", "zaporojskoe-olt"), "cdata");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.17409.2.3", "FD1104S"), "cdata");
        // CData's own enterprise
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.34592.1.3", "FD1616GS"), "cdata");
        // VSOL V1600D — vsol/librenms_vsolution_v1600d.snmprec
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.37950.1.1.5.10.14.1", "V1600D"), "vsol");
        // VSOL identified by sysDescr only
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.8072.3.2.10", "V1600G2 GPON OLT"), "vsol");
        // Parks: legacy 6771 and newer 50224
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.6771.1.2", "Fiberlink"), "parks");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.50224.3.1.1", "PK-700"), "parks");
        // Adtran PEN 664, or by sysDescr
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.664.1.1", "SDX 6320"), "adtran");
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.8072.3.2.10", "ADTRAN SDX 6330"), "adtran");
        // Genuinely unknown stays generic
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.8072.3.2.10", "Linux server"), "generic");
        // 17409 must not shadow longer prefixes it merely resembles
        assert_eq!(vendor_from_sysinfo("1.3.6.1.4.1.174091.1", "mystery box"), "generic");
    }

    #[test]
    fn test_build_get_pdu_roundtrip() {
        let request = build_get_request(1, "1.3.6.1.2.1.1.1.0").unwrap();
        let pdu = encode_v2c(b"public", request).unwrap();
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
        let request = build_get_request(42, "1.3.6.1.2.1.1.1.0").unwrap();
        let pdu = encode_v2c(b"public", request).unwrap();

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
        let request = build_getbulk_request(1, "1.3.6.1.2.1.2.2.1.2", 25).unwrap();
        let pdu = encode_v2c(b"public", request).unwrap();
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

    #[test]
    fn test_compare_oids_is_numeric_not_lexicographic() {
        use std::cmp::Ordering;
        // String comparison would say "10" < "9" — numeric must not.
        assert_eq!(compare_oids("1.3.6.10", "1.3.6.9"), Ordering::Greater);
        assert_eq!(compare_oids("1.3.6.9", "1.3.6.10"), Ordering::Less);
        assert_eq!(compare_oids("1.3.6.1", "1.3.6.1"), Ordering::Equal);
        // Shorter prefix sorts before its children
        assert_eq!(compare_oids("1.3.6", "1.3.6.1"), Ordering::Less);
        assert_eq!(compare_oids("1.3.6.1.1", "1.3.6"), Ordering::Greater);
    }

    #[test]
    fn test_oid_has_prefix_respects_component_boundaries() {
        // True children
        assert!(oid_has_prefix("1.3.6.1.2.1.2.2.1.1.5", "1.3.6.1.2.1.2.2.1.1"));
        // Adjacent column that string-starts_with the prefix must NOT match
        assert!(!oid_has_prefix("1.3.6.1.2.1.2.2.1.10.5", "1.3.6.1.2.1.2.2.1.1"));
        assert!(!oid_has_prefix("1.3.6.1.2.1.2.2.1.15.5", "1.3.6.1.2.1.2.2.1.1"));
        // The base OID itself is not a table row
        assert!(!oid_has_prefix("1.3.6.1.2.1.2.2.1.1", "1.3.6.1.2.1.2.2.1.1"));
        // Unrelated OID
        assert!(!oid_has_prefix("1.3.6.1.4.1.2011", "1.3.6.1.2.1"));
    }

    /// `unwrap_err` needs `SnmpPoller: Debug`, which we deliberately don't
    /// derive (it would Debug-print the community secret).
    fn expect_new_err(cfg: &crate::config::SnmpConfig) -> SnmpError {
        match SnmpPoller::new("127.0.0.1", cfg) {
            Err(e) => e,
            Ok(_) => panic!("Expected SnmpPoller::new to fail"),
        }
    }

    #[test]
    fn test_new_rejects_unknown_version() {
        let cfg = crate::config::SnmpConfig {
            version: "v1".into(),
            community: Some("secret".into()),
            v3: None,
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let err = expect_new_err(&cfg);
        assert!(matches!(err, SnmpError::Config(_)));
        assert!(err.to_string().contains("not supported"));
    }

    #[test]
    fn test_new_v3_requires_credentials_section() {
        let cfg = crate::config::SnmpConfig {
            version: "v3".into(),
            community: None,
            v3: None,
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let err = expect_new_err(&cfg);
        assert!(matches!(err, SnmpError::Config(_)));
        assert!(err.to_string().contains("without credentials"), "got: {err}");
    }

    #[test]
    fn test_new_v3_accepts_coherent_credentials_and_rejects_priv_without_auth() {
        let v3 = crate::config::SnmpV3Config {
            username: "pulso".into(),
            auth_protocol: Some("sha1".into()),
            auth_password: Some("maplesyrup".into()),
            priv_protocol: Some("aes128".into()),
            priv_password: Some("maplesyrup".into()),
            context_name: String::new(),
        };
        let cfg = crate::config::SnmpConfig {
            version: "v3".into(),
            community: None,
            v3: Some(v3.clone()),
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let poller = SnmpPoller::new("127.0.0.1", &cfg).unwrap();
        match &poller.security {
            Security::V3(sess) => assert_eq!(sess.security_level(), "authPriv"),
            _ => panic!("expected V3 security"),
        }

        // priv without auth is incoherent and must fail at construction
        let mut bad = v3;
        bad.auth_protocol = None;
        bad.auth_password = None;
        let cfg = crate::config::SnmpConfig {
            version: "v3".into(),
            community: None,
            v3: Some(bad),
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let err = expect_new_err(&cfg);
        assert!(err.to_string().contains("requires authentication"), "got: {err}");
    }

    #[test]
    fn test_new_requires_community_never_defaults_to_public() {
        let cfg = crate::config::SnmpConfig {
            version: "v2c".into(),
            community: None,
            v3: None,
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let err = expect_new_err(&cfg);
        assert!(matches!(err, SnmpError::Config(_)));
        assert!(err.to_string().contains("community"));
        assert!(!err.to_string().contains("falling back"));
    }

    #[test]
    fn test_new_accepts_v2c_case_insensitive_and_uses_configured_community() {
        let cfg = crate::config::SnmpConfig {
            version: "V2C".into(),
            community: Some("not-public".into()),
            v3: None,
            port: 161,
            timeout_ms: 1000,
            max_repetitions: 10,
        };
        let poller = SnmpPoller::new("127.0.0.1", &cfg).unwrap();
        match &poller.security {
            Security::V2c { community } => assert_eq!(community, &b"not-public".to_vec()),
            _ => panic!("expected V2c security"),
        }
    }

    // --- Loopback UDP mock agent tests (retransmit / partial walk / robustness) ---

    /// Poller aimed at a mock agent, with a short timeout so tests run fast.
    fn mock_poller(target: SocketAddr, max_walk_rows: usize) -> SnmpPoller {
        SnmpPoller {
            target,
            security: Security::V2c { community: b"private".to_vec() },
            timeout: Duration::from_millis(100),
            max_repetitions: 10,
            max_walk_rows,
            request_id: std::sync::atomic::AtomicU32::new(1),
        }
    }

    fn decode_request_id(buf: &[u8]) -> i32 {
        use rasn_snmp::v2::Pdus;
        let msg: rasn_snmp::v2c::Message<Pdus> = rasn::ber::decode(buf).unwrap();
        match msg.data {
            Pdus::GetRequest(p) => p.0.request_id,
            Pdus::GetBulkRequest(p) => p.0.request_id,
            other => panic!("Unexpected request PDU: {:?}", other),
        }
    }

    /// Build a v2c Response with Integer varbinds.
    fn encode_response(request_id: i32, error_status: u32, varbinds: &[(&str, i64)]) -> Vec<u8> {
        use rasn_smi::v2::{ObjectSyntax, SimpleSyntax};
        use rasn_snmp::v2::{Pdu, Pdus, Response, VarBind, VarBindValue};

        let bindings = varbinds
            .iter()
            .map(|(oid, v)| VarBind {
                name: parse_oid(oid).unwrap(),
                value: VarBindValue::Value(ObjectSyntax::Simple(SimpleSyntax::Integer(
                    rasn::types::Integer::from(*v),
                ))),
            })
            .collect();

        let msg = rasn_snmp::v2c::Message {
            version: 1.into(),
            community: b"private".to_vec().into(),
            data: Pdus::Response(Response(Pdu {
                request_id,
                error_status,
                error_index: 0,
                variable_bindings: bindings,
            })),
        };
        rasn::ber::encode(&msg).unwrap()
    }

    /// Spawn a scripted mock SNMP agent on loopback. The script gets the
    /// zero-based datagram number and the raw request; `None` drops the packet.
    async fn spawn_mock_agent<F>(mut script: F) -> SocketAddr
    where
        F: FnMut(usize, &[u8]) -> Option<Vec<u8>> + Send + 'static,
    {
        let socket = tokio::net::UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let addr = socket.local_addr().unwrap();
        tokio::spawn(async move {
            let mut buf = vec![0u8; 65535];
            let mut n = 0usize;
            while let Ok((len, peer)) = socket.recv_from(&mut buf).await {
                if let Some(reply) = script(n, &buf[..len]) {
                    let _ = socket.send_to(&reply, peer).await;
                }
                n += 1;
            }
        });
        addr
    }

    #[tokio::test]
    async fn test_get_retransmits_and_recovers_after_packet_loss() {
        // Drop the first two datagrams; answer the third (second retransmit).
        let addr = spawn_mock_agent(|n, req| {
            if n < 2 {
                None
            } else {
                Some(encode_response(
                    decode_request_id(req),
                    0,
                    &[("1.3.6.1.2.1.1.3.0", 7)],
                ))
            }
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let value = poller.get("1.3.6.1.2.1.1.3.0").await.unwrap();
        assert!(matches!(value.value, SnmpData::Integer(7)));
    }

    #[tokio::test]
    async fn test_get_times_out_after_exhausting_retransmits() {
        let received = std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0));
        let counter = received.clone();
        let addr = spawn_mock_agent(move |_, _| {
            counter.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            None // never answer
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let err = poller.get("1.3.6.1.2.1.1.3.0").await.unwrap_err();
        assert!(matches!(err, SnmpError::Timeout(_)));
        // Initial attempt + SNMP_RETRANSMITS retransmits all hit the wire
        assert_eq!(
            received.load(std::sync::atomic::Ordering::SeqCst),
            (SNMP_RETRANSMITS + 1) as usize
        );
    }

    #[tokio::test]
    async fn test_partial_walk_is_an_error_not_silent_success() {
        const BASE: &str = "1.3.6.1.4.9";
        // First GetBulk gets two rows; every later request is dropped.
        let addr = spawn_mock_agent(|n, req| {
            if n == 0 {
                Some(encode_response(
                    decode_request_id(req),
                    0,
                    &[("1.3.6.1.4.9.1.1", 10), ("1.3.6.1.4.9.1.2", 20)],
                ))
            } else {
                None
            }
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let err = poller.walk_table(BASE).await.unwrap_err();
        match err {
            SnmpError::PartialWalk { base_oid, rows, source } => {
                assert_eq!(base_oid, BASE);
                assert_eq!(rows, 2);
                assert!(matches!(*source, SnmpError::Timeout(_)));
            }
            other => panic!("Expected PartialWalk, got: {other}"),
        }
    }

    #[tokio::test]
    async fn test_walk_stops_at_column_boundary_without_bleeding() {
        const BASE: &str = "1.3.6.1.2.1.2.2.1.1";
        // Third varbind is the adjacent column ...1.10.x — a string prefix of
        // BASE but not a component-aligned child. It must terminate the walk,
        // not be returned as a row.
        let addr = spawn_mock_agent(|_, req| {
            Some(encode_response(
                decode_request_id(req),
                0,
                &[
                    ("1.3.6.1.2.1.2.2.1.1.1", 1),
                    ("1.3.6.1.2.1.2.2.1.1.2", 2),
                    ("1.3.6.1.2.1.2.2.1.10.1", 99),
                ],
            ))
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let rows = poller.walk_table(BASE).await.unwrap();
        assert_eq!(rows.len(), 2);
        assert!(rows.iter().all(|r| !matches!(r.value, SnmpData::Integer(99))));
    }

    #[tokio::test]
    async fn test_walk_aborts_when_agent_makes_no_forward_progress() {
        // Buggy firmware returns the same OID forever.
        let addr = spawn_mock_agent(|_, req| {
            Some(encode_response(
                decode_request_id(req),
                0,
                &[("1.3.6.1.4.9.1.1", 5)],
            ))
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let err = poller.walk_table("1.3.6.1.4.9").await.unwrap_err();
        assert!(matches!(err, SnmpError::Protocol(_)));
        assert!(err.to_string().contains("not advancing"));
    }

    #[tokio::test]
    async fn test_walk_surfaces_nonzero_error_status() {
        let addr = spawn_mock_agent(|_, req| {
            // genErr(5) with no varbinds
            Some(encode_response(decode_request_id(req), 5, &[]))
        })
        .await;

        let poller = mock_poller(addr, MAX_WALK_ROWS);
        let err = poller.walk_table("1.3.6.1.4.9").await.unwrap_err();
        assert!(matches!(err, SnmpError::Protocol(_)));
        assert!(err.to_string().contains("error status 5"));
    }

    #[tokio::test]
    async fn test_walk_row_cap_aborts_runaway_walk() {
        // Agent hands out ever-increasing OIDs forever; the cap must stop it.
        let addr = spawn_mock_agent(|n, req| {
            let a = (2 * n + 1) as i64;
            let b = (2 * n + 2) as i64;
            Some(encode_response(
                decode_request_id(req),
                0,
                &[
                    (&format!("1.3.6.1.4.9.1.{}", a), a),
                    (&format!("1.3.6.1.4.9.1.{}", b), b),
                ],
            ))
        })
        .await;

        let poller = mock_poller(addr, 3);
        let err = poller.walk_table("1.3.6.1.4.9").await.unwrap_err();
        assert!(matches!(err, SnmpError::Protocol(_)));
        assert!(err.to_string().contains("exceeded 3 rows"));
    }

    // --- SNMPv3 loopback mock agent tests -----------------------------------

    /// A stable, RFC-shaped engine ID for the mock agent.
    const V3_ENGINE_ID: &[u8] = &[0x80, 0x00, 0x1f, 0x88, 0x04, b'm', b'o', b'c', b'k'];
    const V3_AUTH_PW: &str = "maplesyrup";
    const V3_PRIV_PW: &str = "aes-priv-secret";

    fn v3_test_config() -> crate::config::SnmpV3Config {
        crate::config::SnmpV3Config {
            username: "pulso".into(),
            auth_protocol: Some("sha1".into()),
            auth_password: Some(V3_AUTH_PW.into()),
            priv_protocol: Some("aes128".into()),
            priv_password: Some(V3_PRIV_PW.into()),
            context_name: String::new(),
        }
    }

    fn v3_poller(target: SocketAddr) -> SnmpPoller {
        let session = usm::V3Session::from_config(&v3_test_config()).unwrap();
        SnmpPoller {
            target,
            security: Security::V3(session),
            timeout: Duration::from_millis(200),
            max_repetitions: 10,
            max_walk_rows: MAX_WALK_ROWS,
            request_id: std::sync::atomic::AtomicU32::new(1),
        }
    }

    /// Agent-side session with the same credentials and an installed engine —
    /// used to build authenticated/encrypted replies (self-consistency: the
    /// mock agent uses our own encoder, exactly like the v2c mock tests).
    fn v3_agent_session(boots: u32, time: u32) -> usm::V3Session {
        let sess = usm::V3Session::from_config(&v3_test_config()).unwrap();
        sess.install_engine(V3_ENGINE_ID.to_vec(), boots, time);
        sess
    }

    /// Decode an incoming v3 request on the agent side: returns
    /// (msg_id, flags, user, decrypted GetRequest request-id + first OID).
    fn v3_agent_decode_get(req: &[u8]) -> (u32, u8, Vec<u8>, Option<(i32, String)>) {
        use num_traits::ToPrimitive;
        let msg: rasn_snmp::v3::Message = rasn::ber::decode(req).unwrap();
        let msg_id = msg.global_data.message_id.to_u32().unwrap();
        let flags = msg.global_data.flags.first().copied().unwrap();
        let usm_params = msg
            .decode_security_parameters::<rasn_snmp::v3::USMSecurityParameters>(rasn::Codec::Ber)
            .map_err(|e| e.to_string())
            .unwrap();
        let user = usm_params.user_name.to_vec();
        if user.is_empty() {
            return (msg_id, flags, user, None); // discovery probe
        }

        // Decrypt the scoped PDU with the agent's own localized priv key
        let ct = match &msg.scoped_data {
            rasn_snmp::v3::ScopedPduData::EncryptedPdu(ct) => ct.to_vec(),
            other => panic!("authPriv request must be encrypted, got {:?}", other),
        };
        let priv_key = &usm::localized_key(
            usm::AuthProtocol::Sha1,
            V3_PRIV_PW.as_bytes(),
            V3_ENGINE_ID,
        )[..16];
        let salt: [u8; 8] = usm_params.privacy_parameters.as_ref().try_into().unwrap();
        let boots = usm_params.authoritative_engine_boots.to_u32().unwrap();
        let time = usm_params.authoritative_engine_time.to_u32().unwrap();
        let mut buf = ct;
        usm::aes128_cfb_decrypt(priv_key, boots, time, &salt, &mut buf).unwrap();
        let scoped: rasn_snmp::v3::ScopedPdu = rasn::ber::decode(&buf).unwrap();
        let (rid, oid) = match scoped.data {
            rasn_snmp::v2::Pdus::GetRequest(g) => {
                let oid = format_oid(&g.0.variable_bindings[0].name);
                (g.0.request_id, oid)
            }
            other => panic!("expected GetRequest, got {:?}", other),
        };
        (msg_id, flags, user, Some((rid, oid)))
    }

    fn v3_string_response(request_id: i32, oid: &str, text: &'static [u8]) -> rasn_snmp::v2::Pdus {
        use rasn_smi::v2::{ObjectSyntax, SimpleSyntax};
        use rasn_snmp::v2::{Pdu, Pdus, Response, VarBind, VarBindValue};
        Pdus::Response(Response(Pdu {
            request_id,
            error_status: 0,
            error_index: 0,
            variable_bindings: vec![VarBind {
                name: parse_oid(oid).unwrap(),
                value: VarBindValue::Value(ObjectSyntax::Simple(SimpleSyntax::String(
                    rasn::types::OctetString::from_static(text),
                ))),
            }],
        }))
    }

    #[tokio::test]
    async fn test_v3_authpriv_get_with_engine_discovery_over_loopback() {
        let flags_seen = std::sync::Arc::new(std::sync::Mutex::new(Vec::<u8>::new()));
        let flags_rec = flags_seen.clone();

        let agent = v3_agent_session(3, 1234);
        let addr = spawn_mock_agent(move |_, req| {
            let (msg_id, flags, user, get) = v3_agent_decode_get(req);
            flags_rec.lock().unwrap().push(flags);
            match get {
                None => {
                    // Engine discovery probe: empty user, noAuthNoPriv+reportable
                    assert!(user.is_empty());
                    Some(usm::mock_v3_report(
                        msg_id,
                        V3_ENGINE_ID,
                        3,
                        1234,
                        usm::report_oids::UNKNOWN_ENGINE_IDS,
                    ))
                }
                Some((rid, oid)) => {
                    assert_eq!(user, b"pulso");
                    assert_eq!(oid, oids::SYS_DESCR);
                    Some(agent.wrap(msg_id, v3_string_response(rid, &oid, b"Mock OLT v3")).unwrap())
                }
            }
        })
        .await;

        let poller = v3_poller(addr);
        let value = poller.get(oids::SYS_DESCR).await.unwrap();
        assert!(
            matches!(value.value, SnmpData::OctetString(ref s) if s == "Mock OLT v3"),
            "got: {:?}",
            value.value
        );

        // Discovery went out reportable-only; the GET went out authPriv+reportable.
        let flags = flags_seen.lock().unwrap().clone();
        assert_eq!(flags, vec![0x04, 0x07]);
    }

    #[tokio::test]
    async fn test_v3_not_in_time_window_resyncs_and_retries_once() {
        let boots_seen = std::sync::Arc::new(std::sync::Mutex::new(Vec::<u32>::new()));
        let boots_rec = boots_seen.clone();

        // The agent rebooted: it now runs at boots=4 while discovery said 3.
        let agent = v3_agent_session(4, 777);
        let addr = spawn_mock_agent(move |n, req| {
            use num_traits::ToPrimitive;
            let (msg_id, _flags, user, get) = v3_agent_decode_get(req);
            if user.is_empty() {
                // Stale discovery: old boots/time
                return Some(usm::mock_v3_report(
                    msg_id,
                    V3_ENGINE_ID,
                    3,
                    100,
                    usm::report_oids::UNKNOWN_ENGINE_IDS,
                ));
            }
            let msg: rasn_snmp::v3::Message = rasn::ber::decode(req).unwrap();
            let usm_params = msg
                .decode_security_parameters::<rasn_snmp::v3::USMSecurityParameters>(rasn::Codec::Ber)
                .map_err(|e| e.to_string())
                .unwrap();
            boots_rec
                .lock()
                .unwrap()
                .push(usm_params.authoritative_engine_boots.to_u32().unwrap());
            let (rid, oid) = get.unwrap();
            if n == 1 {
                // First real request arrives with stale boots → authenticated
                // notInTimeWindows report carrying the true boots/time.
                let report = rasn_snmp::v2::Pdus::Report(rasn_snmp::v2::Report(
                    rasn_snmp::v2::Pdu {
                        request_id: rid,
                        error_status: 0,
                        error_index: 0,
                        variable_bindings: vec![rasn_snmp::v2::VarBind {
                            name: parse_oid(usm::report_oids::NOT_IN_TIME_WINDOWS).unwrap(),
                            value: rasn_snmp::v2::VarBindValue::Unspecified,
                        }],
                    },
                ));
                Some(agent.wrap(msg_id, report).unwrap())
            } else {
                Some(agent.wrap(msg_id, v3_string_response(rid, &oid, b"synced")).unwrap())
            }
        })
        .await;

        let poller = v3_poller(addr);
        let value = poller.get(oids::SYS_DESCR).await.unwrap();
        assert!(matches!(value.value, SnmpData::OctetString(ref s) if s == "synced"));

        // Request 1 carried the stale boots=3; after the resync the retry
        // carried the agent's true boots=4.
        let boots = boots_seen.lock().unwrap().clone();
        assert_eq!(boots, vec![3, 4]);
    }

    #[tokio::test]
    async fn test_v3_wrong_digest_report_is_a_clear_error_not_empty_data() {
        let addr = spawn_mock_agent(move |_, req| {
            let (msg_id, _flags, user, _get) = v3_agent_decode_get(req);
            if user.is_empty() {
                Some(usm::mock_v3_report(
                    msg_id,
                    V3_ENGINE_ID,
                    3,
                    1234,
                    usm::report_oids::UNKNOWN_ENGINE_IDS,
                ))
            } else {
                // Agent rejects our credentials
                Some(usm::mock_v3_report(
                    msg_id,
                    V3_ENGINE_ID,
                    3,
                    1234,
                    usm::report_oids::WRONG_DIGESTS,
                ))
            }
        })
        .await;

        let poller = v3_poller(addr);
        let err = poller.get(oids::SYS_DESCR).await.unwrap_err();
        assert!(err.to_string().contains("usmStatsWrongDigests"), "got: {err}");
        assert!(err.to_string().contains("auth_password"), "got: {err}");
    }
}
