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

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// A single ONT reading at a point in time.
/// Used by all detection sub-modules as the common input type.
#[derive(Debug, Clone, Serialize, Deserialize)]
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
}

/// ONT status at the time of reading.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum OntReadingStatus {
    Online,
    Offline,
}
