// SPDX-License-Identifier: Apache-2.0
// Fault Impact Scorer
//
// Scores fault impact by combining customer count, time of day,
// and recent activity to produce a prioritized impact assessment.
//
// This helps NOC operators focus on the faults that matter most:
//   - 50 ONTs offline at 3am (low impact — most customers sleeping)
//   - 10 ONTs offline at 10am on a weekday (high impact — work-from-home)
//
// Priority mapping:
//   P1 Emergency: score > 80 OR > 50 ONTs affected
//   P2 High:      score > 50 OR > 20 active ONTs
//   P3 Medium:    score > 20
//   P4 Low:       everything else

use chrono::{DateTime, Datelike, Timelike, Utc, Weekday};
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// Scored fault impact with priority classification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultImpact {
    pub fault_id: String,
    pub affected_onts: u32,
    pub impact_score: f64,
    pub active_onts: u32,
    pub time_sensitivity: TimeSensitivity,
    pub priority: Priority,
}

/// Time-of-day sensitivity classification.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TimeSensitivity {
    /// Weekday 9-18: business hours, work-from-home
    Critical,
    /// Weekday evening 18-22: streaming, gaming peak
    High,
    /// Weekend daytime 8-22: moderate usage
    Medium,
    /// Night 1-6 (any day): minimal usage
    Low,
}

impl std::fmt::Display for TimeSensitivity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Critical => write!(f, "critical"),
            Self::High => write!(f, "high"),
            Self::Medium => write!(f, "medium"),
            Self::Low => write!(f, "low"),
        }
    }
}

/// Fault priority for NOC dispatching.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum Priority {
    P1Emergency,
    P2High,
    P3Medium,
    P4Low,
}

impl std::fmt::Display for Priority {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::P1Emergency => write!(f, "P1"),
            Self::P2High => write!(f, "P2"),
            Self::P3Medium => write!(f, "P3"),
            Self::P4Low => write!(f, "P4"),
        }
    }
}

/// Score fault impact based on offline ONTs, recent activity, and time of day.
///
/// Steps:
///   1. Count affected ONTs from the offline serials list
///   2. Determine which affected ONTs were active (Online) in the last hour
///   3. Classify time sensitivity from the current timestamp
///   4. Compute score = affected * (active_ratio) * time_multiplier
///   5. Map score to priority level
pub fn score_fault_impact(
    offline_serials: &[String],
    all_readings: &[OntReading],
    current_time: DateTime<Utc>,
) -> FaultImpact {
    let affected_count = offline_serials.len() as u32;

    // Determine which affected ONTs were active in the last hour
    let one_hour_ago = current_time - chrono::Duration::hours(1);
    let mut active_count: u32 = 0;

    for serial in offline_serials {
        let was_active = all_readings.iter().any(|r| {
            r.serial_number == *serial
                && r.timestamp >= one_hour_ago
                && r.timestamp <= current_time
                && r.status == OntReadingStatus::Online
        });
        if was_active {
            active_count += 1;
        }
    }

    // Time sensitivity
    let time_sensitivity = classify_time_sensitivity(current_time);

    let time_multiplier = match time_sensitivity {
        TimeSensitivity::Critical => 2.0,
        TimeSensitivity::High => 1.5,
        TimeSensitivity::Medium => 1.0,
        TimeSensitivity::Low => 0.5,
    };

    // Score: affected * active_ratio * time_multiplier
    let active_ratio = if affected_count > 0 {
        active_count as f64 / affected_count as f64
    } else {
        0.0
    };
    let score = affected_count as f64 * active_ratio * time_multiplier;

    // Priority classification
    let priority = if score > 80.0 || affected_count > 50 {
        Priority::P1Emergency
    } else if score > 50.0 || active_count > 20 {
        Priority::P2High
    } else if score > 20.0 {
        Priority::P3Medium
    } else {
        Priority::P4Low
    };

    FaultImpact {
        fault_id: String::new(),
        affected_onts: affected_count,
        impact_score: score,
        active_onts: active_count,
        time_sensitivity,
        priority,
    }
}

/// Classify time sensitivity based on day of week and hour.
fn classify_time_sensitivity(time: DateTime<Utc>) -> TimeSensitivity {
    let hour = time.hour();
    let weekday = time.weekday();
    let is_weekend = matches!(weekday, Weekday::Sat | Weekday::Sun);

    // Night hours (1-6) on any day
    if hour >= 1 && hour < 6 {
        return TimeSensitivity::Low;
    }

    if is_weekend {
        // Weekend daytime
        TimeSensitivity::Medium
    } else {
        // Weekday
        if hour >= 9 && hour < 18 {
            TimeSensitivity::Critical
        } else if hour >= 18 && hour < 22 {
            TimeSensitivity::High
        } else {
            // Weekday 6-9 or 22-1
            TimeSensitivity::Medium
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, TimeZone, Utc};

    fn make_reading(
        serial: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            rx_power_dbm: Some(-20.0),
            tx_power_dbm: None,
            status,
            distance_meters: None,
            eth_speed_mbps: None,
            last_down_cause: None,
        }
    }

    #[test]
    fn test_impact_weekday_business_hours() {
        // Wednesday at 14:00 UTC
        let current_time = Utc.with_ymd_and_hms(2026, 3, 18, 14, 0, 0).unwrap();

        let offline: Vec<String> = (0..10).map(|i| format!("ONT{:03}", i)).collect();

        // All 10 were active in the last hour
        let readings: Vec<OntReading> = offline
            .iter()
            .map(|s| make_reading(s, current_time - Duration::minutes(30), OntReadingStatus::Online))
            .collect();

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.affected_onts, 10);
        assert_eq!(impact.active_onts, 10);
        assert_eq!(impact.time_sensitivity, TimeSensitivity::Critical);
        // Score = 10 * 1.0 * 2.0 = 20.0
        assert!((impact.impact_score - 20.0).abs() < 0.01);
    }

    #[test]
    fn test_impact_nighttime_low() {
        // Tuesday at 03:00 UTC
        let current_time = Utc.with_ymd_and_hms(2026, 3, 17, 3, 0, 0).unwrap();

        let offline: Vec<String> = (0..10).map(|i| format!("ONT{:03}", i)).collect();

        // Only 3 were active
        let mut readings = Vec::new();
        for i in 0..3 {
            readings.push(make_reading(
                &format!("ONT{:03}", i),
                current_time - Duration::minutes(20),
                OntReadingStatus::Online,
            ));
        }

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.time_sensitivity, TimeSensitivity::Low);
        assert_eq!(impact.active_onts, 3);
        // Score = 10 * (3/10) * 0.5 = 1.5
        assert!((impact.impact_score - 1.5).abs() < 0.01);
        assert_eq!(impact.priority, Priority::P4Low);
    }

    #[test]
    fn test_impact_p1_many_customers() {
        // Weekday 10:00
        let current_time = Utc.with_ymd_and_hms(2026, 3, 18, 10, 0, 0).unwrap();

        // 60 ONTs offline (> 50 threshold for P1)
        let offline: Vec<String> = (0..60).map(|i| format!("ONT{:03}", i)).collect();

        let readings: Vec<OntReading> = offline
            .iter()
            .map(|s| make_reading(s, current_time - Duration::minutes(15), OntReadingStatus::Online))
            .collect();

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.priority, Priority::P1Emergency);
        assert_eq!(impact.affected_onts, 60);
    }

    #[test]
    fn test_impact_no_active_onts() {
        // Weekday 14:00
        let current_time = Utc.with_ymd_and_hms(2026, 3, 18, 14, 0, 0).unwrap();

        let offline: Vec<String> = (0..8).map(|i| format!("ONT{:03}", i)).collect();

        // No recent readings — none were active
        let readings: Vec<OntReading> = Vec::new();

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.active_onts, 0);
        assert_eq!(impact.time_sensitivity, TimeSensitivity::Critical);
        // Score = 8 * 0.0 * 2.0 = 0.0
        assert!((impact.impact_score - 0.0).abs() < 0.01);
        assert_eq!(impact.priority, Priority::P4Low);
    }
}
