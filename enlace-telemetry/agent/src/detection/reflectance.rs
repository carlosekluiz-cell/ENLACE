// SPDX-License-Identifier: Apache-2.0
// Reflectance Event Detector
//
// Detects ONTs causing reflectance events that knock other ONTs offline
// on the same PON port. Reflectance occurs when a faulty ONT's Tx power
// spikes due to a dirty connector or damaged fiber, causing optical
// reflections that disrupt the upstream TDMA timing on the port.
//
// Detection method:
//   1. Find mass dropout events (5+ ONTs offline within 60s on same port)
//   2. Identify suspect ONT with Tx power anomaly before the event
//   3. Correlate across multiple events to build confidence

use std::collections::HashMap;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use super::{OntReading, OntReadingStatus};

/// A detected reflectance event with suspect ONT identification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReflectanceEvent {
    pub timestamp: DateTime<Utc>,
    pub port: String,
    pub affected_ont_count: u32,
    pub affected_ont_serials: Vec<String>,
    pub suspect_ont_serial: String,
    pub suspect_ont_distance_m: f64,
    pub suspect_tx_anomaly_dbm: f64,
    pub confidence: f64,
    pub events_correlated: u32,
}

/// Minimum number of ONTs that must go offline to qualify as a mass dropout.
const MIN_DROPOUT_COUNT: usize = 5;

/// Maximum time window (seconds) within which dropouts must occur.
const DROPOUT_WINDOW_SECS: i64 = 60;

/// Minimum Rx power (dBm) for affected ONTs — must have been healthy before dropout.
const MIN_HEALTHY_RX_DBM: f64 = -25.0;

/// Time window (seconds) before the dropout event to look for Tx anomalies.
const TX_LOOKBACK_SECS: i64 = 300;

/// Minimum Tx power spike above baseline to flag as anomalous.
const TX_SPIKE_THRESHOLD_DBM: f64 = 0.3;

/// Detect reflectance events on a given PON port from a time-series of ONT readings.
///
/// Filters readings to the specified port, identifies mass dropout events where
/// previously-healthy ONTs go offline simultaneously, then correlates with Tx power
/// anomalies to identify the suspect ONT causing reflectance.
pub fn detect_reflectance(readings: &[OntReading], port: &str) -> Vec<ReflectanceEvent> {
    // Filter readings for this port
    let port_readings: Vec<&OntReading> = readings
        .iter()
        .filter(|r| r.pon_port == port)
        .collect();

    if port_readings.is_empty() {
        return Vec::new();
    }

    // Collect all unique ONT serials on this port
    let all_serials: Vec<String> = {
        let mut s: Vec<String> = port_readings
            .iter()
            .map(|r| r.serial_number.clone())
            .collect();
        s.sort();
        s.dedup();
        s
    };
    let total_onts_on_port = all_serials.len();

    // Find dropout events: ONTs that transition from Online to Offline
    // Group by serial to find the moment each ONT went offline
    let mut dropout_times: Vec<(DateTime<Utc>, String, f64)> = Vec::new(); // (time, serial, last_rx)

    let mut readings_by_serial: HashMap<&str, Vec<&OntReading>> = HashMap::new();
    for r in &port_readings {
        readings_by_serial
            .entry(&r.serial_number)
            .or_default()
            .push(r);
    }

    for (serial, mut serial_readings) in readings_by_serial.iter_mut() {
        serial_readings.sort_by_key(|r| r.timestamp);

        for window in serial_readings.windows(2) {
            let prev = window[0];
            let curr = window[1];

            // Transition from Online to Offline
            if prev.status == OntReadingStatus::Online && curr.status == OntReadingStatus::Offline {
                // Must have been healthy (Rx > -25 dBm) before dropout
                let last_rx = prev.rx_power_dbm.unwrap_or(-30.0);
                if last_rx > MIN_HEALTHY_RX_DBM {
                    // Must not have dying gasp (rules out power failure)
                    let has_dying_gasp = curr
                        .last_down_cause
                        .as_deref()
                        .map(|c| c.contains("dying_gasp") || c.contains("power"))
                        .unwrap_or(false);
                    if !has_dying_gasp {
                        dropout_times.push((curr.timestamp, serial.to_string(), last_rx));
                    }
                }
            }
        }
    }

    // Sort dropouts by time
    dropout_times.sort_by_key(|(ts, _, _)| *ts);

    // Find clusters of dropouts within the time window
    let mut dropout_events: Vec<Vec<(DateTime<Utc>, String, f64)>> = Vec::new();
    let mut i = 0;
    while i < dropout_times.len() {
        let start_ts = dropout_times[i].0;
        let mut cluster = vec![dropout_times[i].clone()];
        let mut j = i + 1;
        while j < dropout_times.len() {
            let delta = (dropout_times[j].0 - start_ts).num_seconds();
            if delta <= DROPOUT_WINDOW_SECS {
                cluster.push(dropout_times[j].clone());
                j += 1;
            } else {
                break;
            }
        }

        // Only consider if 5+ ONTs dropped AND not ALL ONTs on port (rules out fibre cut)
        if cluster.len() >= MIN_DROPOUT_COUNT && cluster.len() < total_onts_on_port {
            dropout_events.push(cluster);
        }

        i = j.max(i + 1);
    }

    if dropout_events.is_empty() {
        return Vec::new();
    }

    // Calculate Tx baseline for each ONT (average Tx across all readings)
    let mut tx_baselines: HashMap<String, (f64, u32)> = HashMap::new();
    for r in &port_readings {
        if let Some(tx) = r.tx_power_dbm {
            let entry = tx_baselines
                .entry(r.serial_number.clone())
                .or_insert((0.0, 0));
            entry.0 += tx;
            entry.1 += 1;
        }
    }
    let tx_avg: HashMap<String, f64> = tx_baselines
        .iter()
        .map(|(s, (sum, count))| (s.clone(), sum / *count as f64))
        .collect();

    // For each dropout event, look for Tx anomalies in the lookback window
    let mut suspect_counts: HashMap<String, u32> = HashMap::new();
    let mut event_suspects: Vec<(usize, String, f64, f64)> = Vec::new(); // (event_idx, serial, anomaly_dbm, distance)

    for (event_idx, cluster) in dropout_events.iter().enumerate() {
        let event_time = cluster[0].0;
        let lookback_start = event_time - chrono::Duration::seconds(TX_LOOKBACK_SECS);

        // Find Tx spikes in lookback window for ONTs NOT in the dropout list
        let dropout_serials: Vec<&str> = cluster.iter().map(|(_, s, _)| s.as_str()).collect();

        for r in &port_readings {
            if r.timestamp >= lookback_start
                && r.timestamp <= event_time
                && !dropout_serials.contains(&r.serial_number.as_str())
            {
                if let (Some(tx), Some(baseline)) =
                    (r.tx_power_dbm, tx_avg.get(&r.serial_number))
                {
                    let spike = tx - baseline;
                    if spike > TX_SPIKE_THRESHOLD_DBM {
                        let distance = r.distance_meters.unwrap_or(0) as f64;
                        *suspect_counts.entry(r.serial_number.clone()).or_insert(0) += 1;
                        event_suspects.push((
                            event_idx,
                            r.serial_number.clone(),
                            spike,
                            distance,
                        ));
                    }
                }
            }
        }
    }

    // Build result events, picking the best suspect per dropout event
    let mut results = Vec::new();

    for (event_idx, cluster) in dropout_events.iter().enumerate() {
        // Find suspects for this event
        let mut candidates: Vec<&(usize, String, f64, f64)> = event_suspects
            .iter()
            .filter(|(idx, _, _, _)| *idx == event_idx)
            .collect();

        if candidates.is_empty() {
            continue;
        }

        // Pick suspect with highest anomaly
        candidates.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(std::cmp::Ordering::Equal));
        let best = &candidates[0];
        let serial = &best.1;
        let anomaly = best.2;
        let distance = best.3;

        let total_appearances = suspect_counts.get(serial).copied().unwrap_or(1);

        // Confidence based on how many events this suspect appears in
        let confidence = match total_appearances {
            1 => 0.3,
            2 => 0.6,
            _ => 0.9,
        };

        let affected_serials: Vec<String> = cluster.iter().map(|(_, s, _)| s.clone()).collect();

        results.push(ReflectanceEvent {
            timestamp: cluster[0].0,
            port: port.to_string(),
            affected_ont_count: cluster.len() as u32,
            affected_ont_serials: affected_serials,
            suspect_ont_serial: serial.clone(),
            suspect_ont_distance_m: distance,
            suspect_tx_anomaly_dbm: anomaly,
            confidence,
            events_correlated: total_appearances,
        });
    }

    // Sort by confidence descending
    results.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap_or(std::cmp::Ordering::Equal));
    results
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Duration, Utc};

    fn make_reading(
        serial: &str,
        port: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
        tx: Option<f64>,
        distance: Option<u32>,
        down_cause: Option<&str>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: port.into(),
            rx_power_dbm: rx,
            tx_power_dbm: tx,
            status,
            distance_meters: distance,
            eth_speed_mbps: None,
            last_down_cause: down_cause.map(|s| s.into()),
        }
    }

    #[test]
    fn test_no_reflectance_healthy_network() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 20 ONTs, all online with stable signals
        for i in 0..20 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now - Duration::minutes(10),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Online, Some(-20.1), Some(2.5), Some(1000), None,
            ));
        }

        let events = detect_reflectance(&readings, port);
        assert!(events.is_empty(), "Healthy network should produce no reflectance events");
    }

    #[test]
    fn test_reflectance_single_event() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 15 ONTs total, 7 will drop out
        // First: everyone is online
        for i in 0..15 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now - Duration::minutes(10),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        // Suspect ONT014 has a Tx spike 2 minutes before the event
        readings.push(make_reading(
            "ONT014", port, now - Duration::minutes(2),
            OntReadingStatus::Online, Some(-20.0), Some(3.5), Some(500), None,
        ));

        // 7 ONTs go offline within 30 seconds (not all 15)
        for i in 0..7 {
            let serial = format!("ONT{:03}", i);
            let dropout_ts = now - Duration::seconds(30 - i as i64);
            readings.push(make_reading(
                &serial, port, dropout_ts,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }

        // Remaining 8 ONTs stay online
        for i in 7..15 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        let events = detect_reflectance(&readings, port);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].affected_ont_count, 7);
        assert_eq!(events[0].suspect_ont_serial, "ONT014");
        assert_eq!(events[0].confidence, 0.3); // Single event = 0.3
    }

    #[test]
    fn test_reflectance_multiple_events_high_confidence() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 20 ONTs total. Suspect ONT019 causes 3 separate dropout events.
        // Baseline readings for all ONTs
        for i in 0..20 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now - Duration::hours(6),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        // Event 1: 4 hours ago
        let event1_time = now - Duration::hours(4);
        readings.push(make_reading(
            "ONT019", port, event1_time - Duration::minutes(1),
            OntReadingStatus::Online, Some(-20.0), Some(3.2), Some(500), None,
        ));
        for i in 0..6 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, event1_time,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }
        // Recovery
        for i in 0..6 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, event1_time + Duration::minutes(5),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        // Event 2: 2 hours ago
        let event2_time = now - Duration::hours(2);
        readings.push(make_reading(
            "ONT019", port, event2_time - Duration::minutes(2),
            OntReadingStatus::Online, Some(-20.0), Some(3.3), Some(500), None,
        ));
        for i in 2..8 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, event2_time,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }
        // Recovery
        for i in 2..8 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, event2_time + Duration::minutes(5),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        // Event 3: 30 minutes ago
        let event3_time = now - Duration::minutes(30);
        readings.push(make_reading(
            "ONT019", port, event3_time - Duration::minutes(1),
            OntReadingStatus::Online, Some(-20.0), Some(3.4), Some(500), None,
        ));
        for i in 5..12 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, event3_time,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }
        // Keep remaining online
        for i in 12..20 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
        }

        let events = detect_reflectance(&readings, port);
        assert!(!events.is_empty(), "Should detect reflectance events");
        // The suspect should appear with high confidence (3+ correlated events)
        let high_conf = events.iter().any(|e| e.suspect_ont_serial == "ONT019" && e.confidence >= 0.6);
        assert!(high_conf, "ONT019 should have high confidence after multiple events: {:?}", events);
    }

    #[test]
    fn test_reflectance_ignores_fibre_cut() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // ALL 10 ONTs go offline = fibre cut, not reflectance
        for i in 0..10 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now - Duration::minutes(5),
                OntReadingStatus::Online, Some(-20.0), Some(2.5), Some(1000), None,
            ));
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }

        let events = detect_reflectance(&readings, port);
        assert!(events.is_empty(), "All ONTs offline = fibre cut, should not flag as reflectance");
    }

    #[test]
    fn test_reflectance_ignores_degraded_power() {
        let now = Utc::now();
        let port = "0/1/0";
        let mut readings = Vec::new();

        // 15 ONTs total, 7 go offline but their Rx was already below -25 dBm
        for i in 0..15 {
            let serial = format!("ONT{:03}", i);
            // All ONTs have degraded signal (< -25 dBm)
            readings.push(make_reading(
                &serial, port, now - Duration::minutes(5),
                OntReadingStatus::Online, Some(-27.0), Some(2.5), Some(1000), None,
            ));
        }

        // 7 ONTs go offline — but their last Rx was below threshold
        for i in 0..7 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Offline, None, None, Some(1000), None,
            ));
        }

        // Remaining stay online
        for i in 7..15 {
            let serial = format!("ONT{:03}", i);
            readings.push(make_reading(
                &serial, port, now,
                OntReadingStatus::Online, Some(-27.0), Some(2.5), Some(1000), None,
            ));
        }

        let events = detect_reflectance(&readings, port);
        assert!(
            events.is_empty(),
            "ONTs with degraded Rx (< -25 dBm) should not trigger reflectance detection"
        );
    }
}
