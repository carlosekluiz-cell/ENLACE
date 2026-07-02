// SPDX-License-Identifier: Apache-2.0
// Detection Module
//
// Advanced telemetry detection engines that analyze ONT readings
// over time to detect reflectance events, predict churn risk,
// and score fault impact for prioritization.
//
// Sub-modules:
//   reflectance — Detect ONTs causing reflectance that knock others offline
//   churn       — Predict customer churn from signal degradation patterns
//   impact      — Score fault impact by customer count, time, and activity

pub mod reflectance;
pub mod churn;
pub mod impact;
pub mod ghost;
pub mod capacity;
pub mod weather;
pub mod tickets;
pub mod flapping;
pub mod sfp_health;
pub mod optical_budget;
pub mod fec_health;
pub mod rogue;

use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// A single ONT reading at a point in time.
/// Used by all detection sub-modules as the common input type.
///
/// Optical-direction semantics: `rx_power_dbm` is the ONT-side DOWNSTREAM
/// receive level (what the ONT measures on the 1490 nm GPON / 1577 nm XGS-PON
/// downstream wavelength) and `tx_power_dbm` is the ONT-side upstream launch
/// power (1310 nm GPON / 1270 nm XGS-PON). This matches Mission Control / SDX
/// CSV exports. Contrast with `vendors::OntData`, where `rx_power_dbm` is the
/// OLT-side UPSTREAM receive level and only `extended.ont_rx_power_dbm` is the
/// ONT-side downstream reading.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct OntReading {
    pub timestamp: DateTime<Utc>,
    pub serial_number: String,
    pub pon_port: String,
    pub rx_power_dbm: Option<f64>,
    pub tx_power_dbm: Option<f64>,
    pub status: OntReadingStatus,
    pub distance_meters: Option<u32>,
    pub eth_speed_mbps: Option<u32>,
    pub last_down_cause: Option<String>,

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

    /// Transceiver DDM detail (SFF-8472): laser-death prediction inputs.
    /// ONT transceiver temperature (°C).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temperature_c: Option<f64>,
    /// ONT transceiver supply voltage (V).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub voltage_v: Option<f64>,
    /// ONT laser bias current (mA).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub bias_current_ma: Option<f64>,

    /// Traffic octet counters (ONT perspective: `in_octets` = received by
    /// the ONT / downstream, `out_octets` = sent by the ONT / upstream).
    /// Named to match `vendors::OntData`. Real traffic data makes
    /// ghost-connection detection evidence-based instead of rx-variance-based.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub in_octets: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub out_octets: Option<u64>,
}

/// ONT status at the time of reading.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub enum OntReadingStatus {
    Online,
    Offline,
    /// Status could not be determined (unrecognized vendor vocabulary,
    /// missing status column, polling gap). Unknown is NOT Offline: it is
    /// excluded from outage/uptime math and counted separately so that a
    /// vocabulary miss can never read as a 100% outage.
    #[default]
    Unknown,
}

/// PON technology, used for wavelength-correct optical modelling.
///
/// GPON (G.984): 1490 nm downstream / 1310 nm upstream.
/// XGS-PON (G.9807.1): 1577 nm downstream / 1270 nm upstream.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize, Default)]
pub enum PonTechnology {
    #[default]
    Gpon,
    XgsPon,
}

/// Known plant topology supplied by the operator (config/GIS import).
///
/// Detection modules must NOT silently infer physical plant facts (splitter
/// ratios in particular) from subscriber counts: a 1:64 splitter with 20
/// subscribers modelled as 1:32 is a ~3.5 dB systematic error. When a port is
/// missing from this map the modules fall back to inference but flag the
/// result as assumed and widen tolerances accordingly.
#[derive(Debug, Clone, Default)]
pub struct PonTopology {
    /// Port id -> configured splitter ratio (e.g. 32 for 1:32, 64 for 1:64).
    pub splitter_ratio_by_port: HashMap<String, u32>,
    /// PON technology deployed on this plant segment.
    pub technology: PonTechnology,
}

/// Sanitized ONT-side rx power: drops vendor sentinels and physically
/// implausible values before they reach any statistics (defense in depth
/// until every vendor parser clamps at conversion time).
pub(crate) fn sane_rx(r: &OntReading) -> Option<f64> {
    r.rx_power_dbm
        .and_then(crate::vendors::snmp_helper::plausible_dbm)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ont_reading_new_optional_fields_skip_null_serialization() {
        // FEC/BIP/DDM/octet fields must not bloat serialized readings with
        // nulls, and old payloads without them must still deserialize.
        let bare = OntReading {
            serial_number: "TEST-001".into(),
            pon_port: "0/1/0".into(),
            status: OntReadingStatus::Online,
            rx_power_dbm: Some(-21.0),
            ..Default::default()
        };
        let json = serde_json::to_value(&bare).unwrap();
        for key in [
            "fec_corrected", "fec_uncorrected", "bip_errors",
            "temperature_c", "voltage_v", "bias_current_ma",
            "in_octets", "out_octets",
        ] {
            assert!(json.get(key).is_none(), "{key} must be skipped when None");
        }
        let old: OntReading = serde_json::from_value(json).unwrap();
        assert_eq!(old.fec_corrected, None);
        assert_eq!(old.temperature_c, None);

        let full = OntReading {
            fec_corrected: Some(18_234),
            fec_uncorrected: Some(2),
            bip_errors: Some(7),
            temperature_c: Some(45.5),
            voltage_v: Some(3.31),
            bias_current_ma: Some(12.4),
            in_octets: Some(182_347_776),
            out_octets: Some(23_456_789),
            ..bare
        };
        let json = serde_json::to_value(&full).unwrap();
        assert_eq!(json["fec_corrected"], 18_234);
        assert_eq!(json["fec_uncorrected"], 2);
        assert_eq!(json["bip_errors"], 7);
        assert_eq!(json["temperature_c"], 45.5);
        assert_eq!(json["voltage_v"], 3.31);
        assert_eq!(json["bias_current_ma"], 12.4);
        assert_eq!(json["in_octets"], 182_347_776_u64);
        assert_eq!(json["out_octets"], 23_456_789_u64);
    }
}
