// SPDX-License-Identifier: Apache-2.0
// Ghost Customer Detector
//
// Detects ONTs that are provisioned and online but never actually used.
// These represent revenue leakage: the ISP is paying for equipment and
// a port on the splitter, but the customer either never connected their
// router or has abandoned the service without cancelling.
//
// Detection criteria:
//   1. ONT consistently online (uptime > 90% of Online/Offline observations)
//   2. Rx power healthy (avg > -25 dBm) — rules out degraded/dead ONTs
//   3. Evidence of non-use, in order of strength:
//      a. Traffic octet counters present with ≥ 7 days of valid coverage
//         and total bytes below the background floor → NoTraffic (or NoLink
//         when the ethernet port also never linked).
//      b. No octet data (or too little coverage) AND ethernet port never
//         linked (eth_speed always 0 or None) → NoLink.
//      c. No octet data but an ethernet link exists → insufficient data;
//         counted, never guessed.
//
// PHYSICS NOTE (why there is no Rx-variance check): GPON downstream is a
// CONTINUOUS broadcast — the OLT transmits at constant power to every ONT
// on the splitter regardless of who is passing traffic. An idle customer's
// ONT Rx power is exactly as stable as a busy customer's, so "flat Rx
// variance" carries zero information about usage and previously flagged
// perfectly healthy paying customers as revenue leakage. Usage detection
// for eth-linked ONTs requires traffic octet counters — `OntReading` now
// carries `in_octets`/`out_octets` (cumulative), so the NoTraffic class is
// evidence-based. ONTs without octet data remain insufficient-data.

use std::collections::HashMap;
use serde::{Deserialize, Serialize};

use super::{sane_rx, OntReading, OntReadingStatus};

/// A detected ghost customer — provisioned and online but never used.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostCustomer {
    pub ont_serial: String,
    pub port: String,
    pub distance_m: Option<u32>,
    pub rx_power_dbm: f64,
    pub eth_status: GhostEthStatus,
    pub days_online: f64,
    /// Assumed monthly revenue for this subscriber (= configured ARPU).
    /// An assumption echoed for context, not a measured value.
    pub estimated_monthly_revenue: f64,
}

/// Why the ghost ONT is considered unused.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum GhostEthStatus {
    /// Ethernet speed always 0 or None — no cable connected.
    NoLink,
    /// Ethernet link exists, but octet counters prove near-zero traffic:
    /// fewer than `GHOST_TRAFFIC_FLOOR_BYTES_PER_WEEK` (pro-rated) moved
    /// across ≥ `MIN_OCTET_COVERAGE_DAYS` of valid counter coverage. This is
    /// the physically-sound revenue-leakage signal.
    NoTraffic {
        /// Total measured bytes (in + out) over the valid coverage.
        total_bytes: u64,
        /// Days of valid octet-counter coverage the total was measured over.
        coverage_days: f64,
    },
}

impl std::fmt::Display for GhostEthStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::NoLink => write!(f, "no_link"),
            Self::NoTraffic { .. } => write!(f, "no_traffic"),
        }
    }
}

/// Full ghost-detection output, including the honest "cannot tell" bucket.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostDetection {
    /// ONTs confirmed unused: either no ethernet link ever seen (`NoLink`)
    /// or measured near-zero traffic over ≥ a week (`NoTraffic`).
    pub ghosts: Vec<GhostCustomer>,
    /// ONT serials that are online and healthy with an ethernet link, whose
    /// actual usage CANNOT be determined: no traffic octet data (or less
    /// than `MIN_OCTET_COVERAGE_DAYS` of valid coverage), and GPON
    /// downstream Rx power carries no usage information (continuous
    /// broadcast). These are NOT ghosts — they are unknowns.
    pub insufficient_data_serials: Vec<String>,
}

/// Minimum uptime ratio for an ONT to be considered "consistently online".
const MIN_UPTIME_RATIO: f64 = 0.90;

/// Minimum average Rx power (dBm) for a healthy ONT.
const MIN_HEALTHY_RX_DBM: f64 = -25.0;

/// Weekly traffic floor below which an online ONT is not a using household.
///
/// Justification: an idle-but-connected CPE still generates background
/// traffic — DHCP renewals, ARP/ND chatter, NTP, TR-069/ACS heartbeats,
/// router firmware phone-home, smart-TV and phone keepalives — typically
/// hundreds of KB to a few MB per day. Any human use blows straight past
/// this: one app update or a few minutes of SD video is tens of MB. An ONT
/// that moves < 10 MiB in a whole week has nothing (or nothing powered)
/// behind it.
const GHOST_TRAFFIC_FLOOR_BYTES_PER_WEEK: u64 = 10 * 1024 * 1024;

/// Minimum days of valid octet-counter coverage before a no-traffic claim
/// is made. One quiet weekend is not abandonment; a full week spans
/// weekday/weekend usage patterns and short trips. Below this, the ONT is
/// reported as insufficient data, never guessed.
const MIN_OCTET_COVERAGE_DAYS: f64 = 7.0;

/// Measured traffic totals from cumulative octet counters.
struct OctetUsage {
    /// Sum of in+out deltas across all valid intervals.
    total_bytes: u64,
    /// Days covered by valid intervals (resets and gaps excluded).
    coverage_days: f64,
}

/// Sum octet deltas across consecutive reading pairs.
///
/// Counters are cumulative, so honesty requires:
///   - Reset handling: a negative delta in EITHER direction means the
///     counter restarted (ONT reboot / 64-bit wrap) — the whole interval is
///     skipped, its bytes and its duration. Never fabricate a delta.
///   - Gap handling: readings where a direction is `None` simply cannot
///     pair; an interval where NO direction is computable contributes
///     nothing to totals or coverage.
///
/// Returns `None` when there is no usable octet data or when valid coverage
/// is under `MIN_OCTET_COVERAGE_DAYS` — too little evidence for any claim.
fn octet_usage(readings: &[&OntReading]) -> Option<OctetUsage> {
    let mut total_bytes: u64 = 0;
    let mut coverage = chrono::Duration::zero();
    let mut valid_intervals = 0usize;

    for pair in readings.windows(2) {
        let (a, b) = (pair[0], pair[1]);
        let mut interval_bytes: u64 = 0;
        let mut computed = false;
        let mut reset = false;
        for (prev, curr) in [(a.in_octets, b.in_octets), (a.out_octets, b.out_octets)] {
            if let (Some(p), Some(c)) = (prev, curr) {
                if c < p {
                    reset = true;
                } else {
                    interval_bytes += c - p;
                    computed = true;
                }
            }
        }
        if reset || !computed {
            continue;
        }
        total_bytes += interval_bytes;
        coverage = coverage + (b.timestamp - a.timestamp);
        valid_intervals += 1;
    }

    if valid_intervals == 0 {
        return None;
    }
    let coverage_days = coverage.num_seconds() as f64 / 86400.0;
    if coverage_days < MIN_OCTET_COVERAGE_DAYS {
        return None;
    }
    Some(OctetUsage { total_bytes, coverage_days })
}

/// Detect ghost customers from ONT readings (confirmed no-link ghosts only).
///
/// Convenience wrapper around [`detect_ghost_customers_detailed`] that
/// returns just the confirmed ghosts. ONTs whose usage cannot be determined
/// (ethernet link present but no traffic counters available) are excluded —
/// they are reported in the detailed variant, never flagged as leakage.
pub fn detect_ghost_customers(readings: &[OntReading], arpu: f64) -> Vec<GhostCustomer> {
    detect_ghost_customers_detailed(readings, arpu).ghosts
}

/// Detect ghost customers, separating confirmed ghosts from ONTs with
/// insufficient data.
///
/// Groups readings by serial number and checks each ONT for:
///   - High uptime (> 90% of Online/Offline observations Online;
///     Unknown-status readings are not observations and are excluded)
///   - Healthy Rx power (average > -25 dBm)
///   - Traffic evidence, in order of strength:
///     - Octet counters with ≥ 7 days valid coverage and total below the
///       floor -> confirmed ghost (NoTraffic, or NoLink when the eth port
///       also never linked)
///     - Octet counters showing real traffic -> active customer (never a
///       ghost, even if the eth port looks down: integrated-WiFi CPEs pass
///       traffic with no ethernet link)
///     - No usable octet data, eth never linked -> confirmed ghost (NoLink)
///     - No usable octet data, eth link observed -> insufficient data
pub fn detect_ghost_customers_detailed(readings: &[OntReading], arpu: f64) -> GhostDetection {
    let mut by_serial: HashMap<String, Vec<&OntReading>> = HashMap::new();
    for r in readings {
        by_serial
            .entry(r.serial_number.clone())
            .or_default()
            .push(r);
    }

    let mut ghosts = Vec::new();
    let mut insufficient_data_serials = Vec::new();

    for (serial, mut ont_readings) in by_serial {
        ont_readings.sort_by_key(|r| r.timestamp);

        if ont_readings.len() < 3 {
            continue;
        }

        // 1. Check uptime > 90% of definite (Online/Offline) observations.
        //    Unknown-status readings are polling gaps, not evidence.
        let online_count = ont_readings
            .iter()
            .filter(|r| r.status == OntReadingStatus::Online)
            .count();
        let observed_count = ont_readings
            .iter()
            .filter(|r| r.status != OntReadingStatus::Unknown)
            .count();
        if observed_count < 3 {
            continue;
        }
        let uptime_ratio = online_count as f64 / observed_count as f64;
        if uptime_ratio < MIN_UPTIME_RATIO {
            continue;
        }

        // 2. Check Rx power healthy (avg > -25 dBm, sentinels excluded)
        let rx_values: Vec<f64> = ont_readings.iter().filter_map(|r| sane_rx(r)).collect();
        if rx_values.is_empty() {
            continue;
        }
        let rx_avg = rx_values.iter().sum::<f64>() / rx_values.len() as f64;
        if rx_avg <= MIN_HEALTHY_RX_DBM {
            continue;
        }

        // 3. Usage evidence: octet counters first (direct measurement),
        //    ethernet link state second (proxy).
        let has_any_eth = ont_readings.iter().any(|r| {
            r.eth_speed_mbps.map_or(false, |s| s > 0)
        });

        let eth_status = match octet_usage(&ont_readings) {
            Some(usage) => {
                // Pro-rate the weekly floor to the actual coverage: 10 MiB
                // per 7 covered days.
                let floor = GHOST_TRAFFIC_FLOOR_BYTES_PER_WEEK as f64
                    * (usage.coverage_days / MIN_OCTET_COVERAGE_DAYS);
                if (usage.total_bytes as f64) < floor {
                    if has_any_eth {
                        GhostEthStatus::NoTraffic {
                            total_bytes: usage.total_bytes,
                            coverage_days: usage.coverage_days,
                        }
                    } else {
                        // No link AND ~zero octets: NoLink is the more
                        // specific physical cause, now corroborated.
                        GhostEthStatus::NoLink
                    }
                } else {
                    // Measured real traffic: an active customer, regardless
                    // of what the eth port claims (integrated-WiFi CPEs pass
                    // traffic with the ethernet port down). Never a ghost.
                    continue;
                }
            }
            None => {
                if has_any_eth {
                    // Link is up, but without usable traffic octet coverage
                    // we cannot know whether the customer actually uses the
                    // service. GPON downstream Rx does not vary with
                    // traffic, so there is no optical proxy. Report honestly
                    // as insufficient data — never as leakage.
                    insufficient_data_serials.push(serial);
                    continue;
                }
                GhostEthStatus::NoLink
            }
        };

        // 4. Calculate days online from first to last reading
        let first_ts = ont_readings.first().unwrap().timestamp;
        let last_ts = ont_readings.last().unwrap().timestamp;
        let days_online = (last_ts - first_ts).num_seconds() as f64 / 86400.0;

        // Get distance from any reading that has it
        let distance_m = ont_readings.iter().find_map(|r| r.distance_meters);

        // Get port from first reading
        let port = ont_readings[0].pon_port.clone();

        ghosts.push(GhostCustomer {
            ont_serial: serial,
            port,
            distance_m,
            rx_power_dbm: rx_avg,
            eth_status,
            days_online,
            estimated_monthly_revenue: arpu,
        });
    }

    // Sort by estimated revenue descending (all same ARPU, so by days_online)
    ghosts.sort_by(|a, b| {
        b.days_online
            .partial_cmp(&a.days_online)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    insufficient_data_serials.sort();

    GhostDetection {
        ghosts,
        insufficient_data_serials,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{DateTime, Duration, Utc};

    fn make_reading(
        serial: &str,
        ts: DateTime<Utc>,
        status: OntReadingStatus,
        rx: Option<f64>,
        eth_speed: Option<u32>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            rx_power_dbm: rx,
            tx_power_dbm: None,
            status,
            distance_meters: Some(500),
            eth_speed_mbps: eth_speed,
            last_down_cause: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_ghost_no_ethernet_link() {
        let now = Utc::now();
        // ONT online with good signal but eth_speed always None
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "GHOST01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0),
                    None, // no ethernet link
                )
            })
            .collect();

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert_eq!(ghosts.len(), 1);
        assert_eq!(ghosts[0].ont_serial, "GHOST01");
        assert_eq!(ghosts[0].eth_status, GhostEthStatus::NoLink);
        assert!((ghosts[0].estimated_monthly_revenue - 89.90).abs() < 0.01);
    }

    #[test]
    fn test_ghost_flat_signal_with_link_is_insufficient_data() {
        let now = Utc::now();
        // ONT online with eth link and perfectly flat Rx power. GPON downstream
        // is continuous broadcast, so a flat Rx says NOTHING about usage —
        // this must be reported as insufficient data, never as a ghost.
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "STABLE02",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0), // perfectly flat — irrelevant to usage
                    Some(1000),  // ethernet link present
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "Flat Rx with eth link must NOT be flagged as ghost: {:?}",
            detection.ghosts
        );
        assert_eq!(
            detection.insufficient_data_serials,
            vec!["STABLE02".to_string()],
            "eth-linked ONT without traffic counters is insufficient data"
        );
    }

    #[test]
    fn test_ghost_varying_signal_with_link_also_insufficient_data() {
        let now = Utc::now();
        // Varying Rx with eth link: equally unknowable (Rx variance is
        // thermal/quantization noise, not traffic).
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                let rx = -20.0 + (i as f64 * 0.1) - 0.5; // varying signal
                make_reading(
                    "ACTIVE01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(rx),
                    Some(1000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "eth-linked customer should never be flagged as ghost"
        );
        assert_eq!(detection.insufficient_data_serials, vec!["ACTIVE01".to_string()]);
    }

    /// Daily reading with cumulative octet counters.
    fn make_reading_with_octets(
        serial: &str,
        ts: DateTime<Utc>,
        eth_speed: Option<u32>,
        in_octets: Option<u64>,
        out_octets: Option<u64>,
    ) -> OntReading {
        OntReading {
            in_octets,
            out_octets,
            ..make_reading(serial, ts, OntReadingStatus::Online, Some(-20.0), eth_speed)
        }
    }

    #[test]
    fn test_real_usage_onts_with_octets_never_flagged() {
        let now = Utc::now();
        // 15 daily readings, counters growing ~2 GB/day: a real household.
        // Must be neither ghost NOR insufficient — octets prove usage.
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                make_reading_with_octets(
                    "HEAVY01",
                    now - Duration::days(14 - i),
                    Some(1000),
                    Some(i as u64 * 2_000_000_000),
                    Some(i as u64 * 150_000_000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "GBs of measured deltas must never be flagged: {:?}",
            detection.ghosts
        );
        assert!(
            detection.insufficient_data_serials.is_empty(),
            "octet-measured ONT is not insufficient data"
        );
    }

    #[test]
    fn test_near_zero_traffic_two_weeks_flagged_no_traffic() {
        let now = Utc::now();
        // 15 daily readings over 14 days, eth link up, ~70 KB/day of
        // background chatter (~1 MB total, floor pro-rated to 20 MiB).
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                make_reading_with_octets(
                    "IDLE01",
                    now - Duration::days(14 - i),
                    Some(1000),
                    Some(i as u64 * 50_000),
                    Some(i as u64 * 20_000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert_eq!(detection.ghosts.len(), 1, "near-zero traffic over 14 days IS a ghost");
        assert!(detection.insufficient_data_serials.is_empty());
        let ghost = &detection.ghosts[0];
        assert_eq!(ghost.ont_serial, "IDLE01");
        match &ghost.eth_status {
            GhostEthStatus::NoTraffic { total_bytes, coverage_days } => {
                assert_eq!(*total_bytes, 14 * 70_000, "total must be the measured deltas");
                assert!(
                    (*coverage_days - 14.0).abs() < 0.1,
                    "coverage must reflect the window: {coverage_days}"
                );
            }
            other => panic!("expected NoTraffic, got {:?}", other),
        }
    }

    #[test]
    fn test_counter_reset_mid_window_skipped_not_misread() {
        let now = Utc::now();
        // Active user whose ONT rebooted mid-window: counters grow 2 GB/day,
        // drop to 0 on day 8, grow again. The reset interval must be skipped
        // (never read as negative or as zero usage) and the surviving
        // intervals still prove real usage.
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                let in_o = if i < 8 {
                    i as u64 * 2_000_000_000
                } else {
                    (i as u64 - 8) * 2_000_000_000
                };
                make_reading_with_octets(
                    "RESET01",
                    now - Duration::days(14 - i),
                    Some(1000),
                    Some(in_o),
                    Some(in_o / 20),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "counter reset must not turn an active customer into a ghost: {:?}",
            detection.ghosts
        );
        assert!(detection.insufficient_data_serials.is_empty());
    }

    #[test]
    fn test_short_octet_coverage_is_insufficient_not_ghost() {
        let now = Utc::now();
        // Only 4 days of near-zero octet coverage with an eth link: too
        // little evidence for a weekly-floor claim — insufficient, not ghost.
        let readings: Vec<OntReading> = (0..5)
            .map(|i| {
                make_reading_with_octets(
                    "SHORT01",
                    now - Duration::days(4 - i),
                    Some(1000),
                    Some(i as u64 * 10_000),
                    Some(i as u64 * 5_000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "4 days of coverage must never support a no-traffic claim"
        );
        assert_eq!(detection.insufficient_data_serials, vec!["SHORT01".to_string()]);
    }

    #[test]
    fn test_no_link_with_zero_octets_stays_no_link() {
        let now = Utc::now();
        // Eth never linked AND octets flat: NoLink is the specific physical
        // cause, now corroborated by measured zero traffic.
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                make_reading_with_octets(
                    "DARK01",
                    now - Duration::days(14 - i),
                    None,
                    Some(500_000),
                    Some(200_000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert_eq!(detection.ghosts.len(), 1);
        assert_eq!(detection.ghosts[0].eth_status, GhostEthStatus::NoLink);
    }

    #[test]
    fn test_no_eth_but_real_octet_traffic_not_flagged() {
        let now = Utc::now();
        // Integrated-WiFi CPE: ethernet port never links, but octets show a
        // heavy user. Must NOT be flagged (the old eth-only logic would
        // have called this revenue leakage).
        let readings: Vec<OntReading> = (0..15)
            .map(|i| {
                make_reading_with_octets(
                    "WIFI01",
                    now - Duration::days(14 - i),
                    None,
                    Some(i as u64 * 1_000_000_000),
                    Some(i as u64 * 80_000_000),
                )
            })
            .collect();

        let detection = detect_ghost_customers_detailed(&readings, 89.90);
        assert!(
            detection.ghosts.is_empty(),
            "measured traffic overrides a down eth port: {:?}",
            detection.ghosts
        );
        assert!(detection.insufficient_data_serials.is_empty());
    }

    #[test]
    fn test_ghost_excludes_degraded_signal() {
        let now = Utc::now();
        // ONT online but with degraded signal (avg < -25 dBm) — not a ghost, just broken
        let readings: Vec<OntReading> = (0..10)
            .map(|i| {
                make_reading(
                    "DEGRADED01",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-27.0), // degraded signal
                    None,
                )
            })
            .collect();

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert!(
            ghosts.is_empty(),
            "ONT with degraded signal (< -25 dBm) should not be flagged as ghost"
        );
    }

    #[test]
    fn test_ghost_unknown_status_excluded_from_uptime() {
        let now = Utc::now();
        // 5 Online + 5 Unknown readings: uptime over definite observations is
        // 100%, so the Unknown polling gaps must not disqualify the ONT.
        let mut readings: Vec<OntReading> = (0..5)
            .map(|i| {
                make_reading(
                    "GHOST_UNK",
                    now - Duration::days(10 - i),
                    OntReadingStatus::Online,
                    Some(-20.0),
                    None,
                )
            })
            .collect();
        for i in 5..10 {
            readings.push(make_reading(
                "GHOST_UNK",
                now - Duration::days(10 - i),
                OntReadingStatus::Unknown,
                None,
                None,
            ));
        }

        let ghosts = detect_ghost_customers(&readings, 89.90);
        assert_eq!(ghosts.len(), 1, "Unknown readings must not count as downtime");
    }
}
