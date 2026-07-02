#[cfg(test)]
mod real_seed {
    use std::fs;
    use std::path::PathBuf;

    use chrono::{Duration, TimeZone, Utc};
    use serde::Deserialize;

    use crate::config::{FaultDetectionConfig, FaultSeverityConfig};
    use crate::detection::capacity::{predict_splitter_capacity, CapacityAlert};
    use crate::detection::churn::predict_churn_risk;
    use crate::detection::ghost::detect_ghost_customers;
    use crate::detection::reflectance::detect_reflectance;
    use crate::detection::weather::{detect_weather_correlation, WeatherPattern};
    use crate::detection::{OntReading, OntReadingStatus};
    use crate::fault::{FaultDetector, FaultType};
    use crate::vendors::{OntData, OntStatus};

    #[derive(Deserialize)]
    struct SeedScorecard {
        cases: Vec<SeedCase>,
    }

    #[derive(Deserialize)]
    struct SeedCase {
        case_id: String,
        json: SeedJson,
    }

    #[derive(Deserialize)]
    struct SeedJson {
        branches: Vec<SeedBranch>,
    }

    #[derive(Deserialize)]
    struct SeedBranch {
        name: String,
        nodes: Vec<SeedNode>,
    }

    #[derive(Deserialize)]
    struct SeedNode {
        building: String,
        dwelling_count: u32,
        distance_from_aux_m: f64,
    }

    #[derive(Clone)]
    struct RealSeedNode {
        branch: String,
        building: String,
        distance_m: u32,
        dwellings: u32,
    }

    fn seed_path() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../outputs/uk_blind_validation_scorecard_2026-03-23_98p8.json")
    }

    fn load_case_nodes(case_id: &str) -> Vec<RealSeedNode> {
        let raw = fs::read_to_string(seed_path()).expect("real seed scorecard should exist");
        let scorecard: SeedScorecard = serde_json::from_str(&raw).expect("seed scorecard JSON");
        let case = scorecard
            .cases
            .into_iter()
            .find(|c| c.case_id == case_id)
            .unwrap_or_else(|| panic!("missing case {}", case_id));

        let mut nodes = Vec::new();
        for branch in case.json.branches {
            for node in branch.nodes {
                nodes.push(RealSeedNode {
                    branch: branch.name.clone(),
                    building: node.building,
                    distance_m: node.distance_from_aux_m.round() as u32,
                    dwellings: node.dwelling_count,
                });
            }
        }
        nodes
    }

    fn make_serial(case_id: &str, node: &RealSeedNode, suffix: usize) -> String {
        let cleaned = node
            .building
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
            .collect::<String>();
        format!("{}-{}-{:02}", case_id, cleaned, suffix)
    }

    fn make_reading(
        serial: String,
        port: &str,
        ts: chrono::DateTime<Utc>,
        rx: Option<f64>,
        tx: Option<f64>,
        status: OntReadingStatus,
        distance_m: u32,
        eth_speed: Option<u32>,
        cause: Option<&str>,
    ) -> OntReading {
        OntReading {
            timestamp: ts,
            serial_number: serial,
            pon_port: port.to_string(),
            rx_power_dbm: rx,
            tx_power_dbm: tx,
            status,
            distance_meters: Some(distance_m),
            eth_speed_mbps: eth_speed,
            last_down_cause: cause.map(|c| c.to_string()),
        }
    }

    fn make_ont(
        serial: String,
        port: &str,
        status: OntStatus,
        distance_m: u32,
        rx: f64,
        cause: Option<&str>,
    ) -> OntData {
        OntData {
            serial_number: serial,
            pon_port: port.to_string(),
            ont_index: 0,
            status,
            last_down_cause: cause.map(|c| c.to_string()),
            uptime_seconds: Some(86_400),
            rx_power_dbm: Some(rx),
            tx_power_dbm: Some(2.5),
            distance_meters: Some(distance_m),
            vendor_id: Some("REAL-SEED".into()),
            equipment_id: None,
            firmware_version: None,
            in_octets: None,
            out_octets: None,
            eth_speed_mbps: Some(1000),
            extended: None,
        }
    }

    #[test]
    fn real_seed_scorecard_from_uk_schematic_cases() {
        let t1 = load_case_nodes("T1");
        let t2 = load_case_nodes("T2");
        let t5 = load_case_nodes("T5");
        let t13 = load_case_nodes("T13");

        let mut scenario_results = Vec::new();

        // Scenario 1: Reflectance seeded from real T1 buildings/distances.
        {
            let port = "real-seed/t1/pon0";
            let suspect = t1[0].clone();
            let victims = t1[1..7].to_vec();
            let base = Utc.with_ymd_and_hms(2026, 3, 1, 12, 0, 0).unwrap();
            let mut readings = Vec::new();

            for day in 0..7 {
                let baseline_ts = base + Duration::days(day);
                readings.push(make_reading(
                    make_serial("T1", &suspect, 1),
                    port,
                    baseline_ts,
                    Some(-20.0),
                    Some(2.5),
                    OntReadingStatus::Online,
                    suspect.distance_m,
                    Some(1000),
                    None,
                ));
                for (idx, victim) in victims.iter().enumerate() {
                    readings.push(make_reading(
                        make_serial("T1", victim, idx + 1),
                        port,
                        baseline_ts,
                        Some(-20.5),
                        Some(2.4),
                        OntReadingStatus::Online,
                        victim.distance_m,
                        Some(1000),
                        None,
                    ));
                }
            }

            for day in [1_i64, 3, 5] {
                let event_ts = base + Duration::days(day);
                readings.push(make_reading(
                    make_serial("T1", &suspect, 1),
                    port,
                    event_ts - Duration::seconds(30),
                    Some(-20.0),
                    Some(3.2),
                    OntReadingStatus::Online,
                    suspect.distance_m,
                    Some(1000),
                    None,
                ));
                for (idx, victim) in victims.iter().enumerate() {
                    let serial = make_serial("T1", victim, idx + 1);
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        event_ts - Duration::minutes(1),
                        Some(-20.6),
                        Some(2.4),
                        OntReadingStatus::Online,
                        victim.distance_m,
                        Some(1000),
                        None,
                    ));
                    readings.push(make_reading(
                        serial,
                        port,
                        event_ts,
                        Some(-40.0),
                        Some(0.0),
                        OntReadingStatus::Offline,
                        victim.distance_m,
                        Some(0),
                        Some("los"),
                    ));
                }
            }

            let events = detect_reflectance(&readings, port);
            assert!(!events.is_empty(), "real-seed reflectance should detect");
            assert_eq!(events[0].suspect_ont_serial, make_serial("T1", &suspect, 1));
            assert!(events[0].affected_ont_count >= 5);
            scenario_results.push("reflectance");
        }

        // Scenario 2: Fault detector seeded from real T1 distances.
        {
            let cfg = FaultDetectionConfig {
                enabled: true,
                min_offline_onts: 5,
                time_window_seconds: 60,
                severity: FaultSeverityConfig {
                    critical: 100,
                    major: 50,
                    minor: 10,
                },
            };
            let mut detector = FaultDetector::new(&cfg);
            let port = "real-seed/t1/pon1";
            let mut onts = Vec::new();

            for (idx, node) in t1.iter().take(8).enumerate() {
                onts.push(make_ont(
                    make_serial("T1F", node, idx + 1),
                    port,
                    OntStatus::Offline,
                    node.distance_m,
                    -28.0,
                    None,
                ));
            }
            for (idx, node) in t1.iter().skip(8).take(4).enumerate() {
                onts.push(make_ont(
                    make_serial("T1F", node, idx + 20),
                    port,
                    OntStatus::Online,
                    node.distance_m,
                    -21.5,
                    None,
                ));
            }

            let events = detector.check(&onts);
            assert_eq!(events.len(), 1, "real-seed fault should trigger");
            assert_eq!(events[0].fault_type, FaultType::FibreCut);
            assert!(events[0].affected_onts.len() >= 5);
            scenario_results.push("fault");
        }

        // Scenario 3: Churn seeded from real T2 buildings/distances.
        {
            let port = "real-seed/t2/pon0";
            let base = Utc.with_ymd_and_hms(2026, 2, 1, 9, 0, 0).unwrap();
            let mut readings = Vec::new();

            for (idx, node) in t2.iter().take(5).enumerate() {
                let serial = make_serial("T2", node, idx + 1);
                for day in 0..30 {
                    let ts = base + Duration::days(day);
                    let rx = -20.0 - (day as f64 * 0.045);
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        ts,
                        Some(rx),
                        Some(2.5),
                        OntReadingStatus::Online,
                        node.distance_m,
                        Some(1000),
                        None,
                    ));
                }
                for dropout in [2_i64, 6, 10, 14, 18, 22] {
                    let off_ts = base + Duration::days(dropout) + Duration::minutes(2);
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        off_ts,
                        Some(-40.0),
                        Some(0.0),
                        OntReadingStatus::Offline,
                        node.distance_m,
                        Some(0),
                        Some("los"),
                    ));
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        off_ts + Duration::minutes(3),
                        Some(-20.8 - (dropout as f64 * 0.045)),
                        Some(2.5),
                        OntReadingStatus::Online,
                        node.distance_m,
                        Some(1000),
                        None,
                    ));
                }
            }

            let risks = predict_churn_risk(&readings, 100.0);
            assert!(risks.len() >= 5, "real-seed churn should flag all seeded ONTs");
            scenario_results.push("churn");
        }

        // Scenario 4: Ghost customers seeded from real T5 buildings.
        {
            let port = "real-seed/t5/pon0";
            let base = Utc.with_ymd_and_hms(2026, 3, 1, 12, 0, 0).unwrap();
            let mut readings = Vec::new();

            for (idx, node) in t5.iter().take(4).enumerate() {
                let serial = make_serial("T5", node, idx + 1);
                for day in 0..10 {
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        base + Duration::days(day),
                        Some(-19.4),
                        Some(2.5),
                        OntReadingStatus::Online,
                        node.distance_m,
                        None,
                        None,
                    ));
                }
            }

            let ghosts = detect_ghost_customers(&readings, 89.90);
            assert_eq!(ghosts.len(), 4, "real-seed ghost scenario should flag all four");
            scenario_results.push("ghost");
        }

        // Scenario 5: Weather correlation seeded from real T13 buildings.
        {
            let port = "real-seed/t13/pon0";
            let node = t13[0].clone();
            let base = Utc.with_ymd_and_hms(2026, 3, 1, 0, 0, 0).unwrap();
            let mut readings = Vec::new();

            for suffix in 1..=3 {
                let serial = make_serial("T13W", &node, suffix);
                for day in 0..7 {
                    for hour in [1_i64, 3, 12, 14] {
                        let ts = base + Duration::days(day) + Duration::hours(hour);
                        let rx = if hour < 6 { -20.7 } else { -19.9 };
                        readings.push(make_reading(
                            serial.clone(),
                            port,
                            ts,
                            Some(rx),
                            Some(2.5),
                            OntReadingStatus::Online,
                            node.distance_m,
                            Some(1000),
                            None,
                        ));
                    }
                }
            }

            let weather = detect_weather_correlation(&readings);
            assert!(weather.iter().any(|w| w.pattern == WeatherPattern::NighttimeCondensation));
            scenario_results.push("weather");
        }

        // Scenario 6: Capacity predictor seeded from real T13 topology.
        {
            let port = "real-seed/t13/pon1";
            let base = Utc.with_ymd_and_hms(2026, 1, 1, 12, 0, 0).unwrap();
            let mut readings = Vec::new();
            let seed_nodes: Vec<RealSeedNode> = t13.iter().take(8).cloned().collect();

            for i in 0..34 {
                let node = &seed_nodes[i % seed_nodes.len()];
                readings.push(make_reading(
                    make_serial("T13C", node, i + 1),
                    port,
                    base,
                    Some(-20.0),
                    Some(2.5),
                    OntReadingStatus::Online,
                    node.distance_m,
                    Some(1000),
                    None,
                ));
            }
            for i in 0..40 {
                let node = &seed_nodes[i % seed_nodes.len()];
                readings.push(make_reading(
                    make_serial("T13C", node, i + 1),
                    port,
                    base + Duration::days(30),
                    Some(-20.0),
                    Some(2.5),
                    OntReadingStatus::Online,
                    node.distance_m,
                    Some(1000),
                    None,
                ));
            }

            let capacity = predict_splitter_capacity(&readings);
            assert_eq!(capacity.len(), 1);
            assert_eq!(capacity[0].active_onts, 40);
            assert!(matches!(capacity[0].alert_level, CapacityAlert::Watch | CapacityAlert::Warning | CapacityAlert::Critical));
            scenario_results.push("capacity");
        }

        assert_eq!(scenario_results.len(), 6, "all real-seed telemetry scenarios should pass");
    }
}
