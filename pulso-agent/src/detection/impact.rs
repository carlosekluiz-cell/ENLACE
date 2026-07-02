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
    /// ONTs confirmed active (seen Online) in the last hour.
    pub active_onts: u32,
    /// ONTs with NO observation in the last hour (polling gap / Unknown
    /// status). These count as active for scoring — missing data must not
    /// reduce impact — but are reported separately for honesty.
    pub unknown_activity_onts: u32,
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
/// Time-of-day classification uses UTC. For plants outside UTC use
/// [`score_fault_impact_with_offset`] with the operator's UTC offset —
/// hardcoded UTC misclassifies business hours in BST (UTC+1) or Brazil
/// (UTC-3).
pub fn score_fault_impact(
    offline_serials: &[String],
    all_readings: &[OntReading],
    current_time: DateTime<Utc>,
) -> FaultImpact {
    score_fault_impact_with_offset(offline_serials, all_readings, current_time, 0)
}

/// Score fault impact with an explicit local-time UTC offset (hours).
///
/// Steps:
///   1. Count affected ONTs from the offline serials list
///   2. Determine which affected ONTs were active (Online) in the last hour.
///      ONTs with NO observation in the window are UNKNOWN and count as
///      active for scoring — a polling gap must never downgrade a real
///      outage to P4.
///   3. Classify time sensitivity from the current timestamp (offset applied)
///   4. Compute score = affected * (active+unknown ratio) * time_multiplier
///   5. Map score to priority level
pub fn score_fault_impact_with_offset(
    offline_serials: &[String],
    all_readings: &[OntReading],
    current_time: DateTime<Utc>,
    utc_offset_hours: i32,
) -> FaultImpact {
    let affected_count = offline_serials.len() as u32;

    // Determine which affected ONTs were active in the last hour.
    // Three-way outcome per ONT: confirmed active (Online seen), confirmed
    // inactive (observed but never Online), unknown (no observation at all).
    let one_hour_ago = current_time - chrono::Duration::hours(1);
    let mut active_count: u32 = 0;
    let mut unknown_count: u32 = 0;

    for serial in offline_serials {
        let mut observed = false;
        let mut was_active = false;
        for r in all_readings.iter() {
            if r.serial_number != *serial
                || r.timestamp < one_hour_ago
                || r.timestamp > current_time
            {
                continue;
            }
            match r.status {
                OntReadingStatus::Online => {
                    observed = true;
                    was_active = true;
                }
                OntReadingStatus::Offline => observed = true,
                // Unknown status is a polling gap, not an observation.
                OntReadingStatus::Unknown => {}
            }
        }
        if was_active {
            active_count += 1;
        } else if !observed {
            unknown_count += 1;
        }
    }

    // Time sensitivity
    let time_sensitivity = classify_time_sensitivity(current_time, utc_offset_hours);

    let time_multiplier = match time_sensitivity {
        TimeSensitivity::Critical => 2.0,
        TimeSensitivity::High => 1.5,
        TimeSensitivity::Medium => 1.0,
        TimeSensitivity::Low => 0.5,
    };

    // Score: affected * effective_active_ratio * time_multiplier.
    // Unknown-activity ONTs count as active: missing data must not reduce
    // impact (the old behaviour scored a 50-ONT outage P4 whenever the
    // poller had no data from the last hour).
    let effective_active = active_count + unknown_count;
    let active_ratio = if affected_count > 0 {
        effective_active as f64 / affected_count as f64
    } else {
        0.0
    };
    let score = affected_count as f64 * active_ratio * time_multiplier;

    // Priority classification
    let priority = if score > 80.0 || affected_count > 50 {
        Priority::P1Emergency
    } else if score > 50.0 || effective_active > 20 {
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
        unknown_activity_onts: unknown_count,
        time_sensitivity,
        priority,
    }
}

/// Classify time sensitivity based on day of week and hour in the
/// operator's local time (UTC + `utc_offset_hours`).
fn classify_time_sensitivity(time: DateTime<Utc>, utc_offset_hours: i32) -> TimeSensitivity {
    let time = time + chrono::Duration::hours(utc_offset_hours as i64);
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
            ..Default::default()
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

        // Only 3 were active; the other 7 were OBSERVED offline (chronic),
        // so their inactivity is confirmed data, not a polling gap.
        let mut readings = Vec::new();
        for i in 0..3 {
            readings.push(make_reading(
                &format!("ONT{:03}", i),
                current_time - Duration::minutes(20),
                OntReadingStatus::Online,
            ));
        }
        for i in 3..10 {
            readings.push(make_reading(
                &format!("ONT{:03}", i),
                current_time - Duration::minutes(20),
                OntReadingStatus::Offline,
            ));
        }

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.time_sensitivity, TimeSensitivity::Low);
        assert_eq!(impact.active_onts, 3);
        assert_eq!(impact.unknown_activity_onts, 0);
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
    fn test_impact_missing_data_is_neutral() {
        // Weekday 14:00 — a 30-ONT outage with NO readings in the last hour
        // (poller gap). Missing data must not reduce impact: unknown ONTs
        // count as active, so this scores like a real business-hours outage
        // instead of collapsing to P4.
        let current_time = Utc.with_ymd_and_hms(2026, 3, 18, 14, 0, 0).unwrap();

        let offline: Vec<String> = (0..30).map(|i| format!("ONT{:03}", i)).collect();
        let readings: Vec<OntReading> = Vec::new();

        let impact = score_fault_impact(&offline, &readings, current_time);
        assert_eq!(impact.active_onts, 0);
        assert_eq!(impact.unknown_activity_onts, 30);
        assert_eq!(impact.time_sensitivity, TimeSensitivity::Critical);
        // Score = 30 * (30/30) * 2.0 = 60.0 — not zero
        assert!((impact.impact_score - 60.0).abs() < 0.01);
        assert_eq!(
            impact.priority,
            Priority::P2High,
            "polling gap must not downgrade a 30-ONT business-hours outage to P4"
        );
    }

    #[test]
    fn test_impact_utc_offset_shifts_business_hours() {
        // 11:00 UTC on a Wednesday is 08:00 in Brazil (UTC-3): before
        // business hours -> Medium, whereas plain UTC would say Critical.
        let current_time = Utc.with_ymd_and_hms(2026, 3, 18, 11, 0, 0).unwrap();
        let offline: Vec<String> = (0..10).map(|i| format!("ONT{:03}", i)).collect();
        let readings: Vec<OntReading> = offline
            .iter()
            .map(|s| make_reading(s, current_time - Duration::minutes(30), OntReadingStatus::Online))
            .collect();

        let utc = score_fault_impact_with_offset(&offline, &readings, current_time, 0);
        assert_eq!(utc.time_sensitivity, TimeSensitivity::Critical);

        let brazil = score_fault_impact_with_offset(&offline, &readings, current_time, -3);
        assert_eq!(brazil.time_sensitivity, TimeSensitivity::Medium);
    }
}
