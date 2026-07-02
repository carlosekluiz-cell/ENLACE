#[cfg(test)]
mod incident_benchmark {
    use std::fs;
    use std::path::PathBuf;

    use chrono::{Duration, TimeZone, Utc};
    use serde::{Deserialize, Serialize};
    use sha2::{Digest, Sha256};

    use crate::config::{FaultDetectionConfig, FaultSeverityConfig};
    use crate::detection::capacity::{predict_splitter_capacity, CapacityAlert};
    use crate::detection::churn::predict_churn_risk;
    use crate::detection::flapping::{detect_flapping, FlappingCause};
    use crate::detection::optical_budget::{analyze_optical_budget, BudgetStatus};
    use crate::detection::reflectance::detect_reflectance;
    use crate::detection::sfp_health::{analyze_sfp_health, SfpSeverity};
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

    #[derive(Clone, Serialize)]
    struct RealSeedNode {
        branch: String,
        building: String,
        distance_m: u32,
        dwellings: u32,
    }

    #[derive(Serialize)]
    struct ScenarioReport {
        scenario_id: String,
        fixture_hash: String,
        outcome: String,
        details: serde_json::Value,
    }

    #[derive(Serialize)]
    struct BenchmarkReport {
        generated_at: String,
        seed_artifact: String,
        scenarios_passed: usize,
        scenarios_total: usize,
        scenarios: Vec<ScenarioReport>,
    }

    fn outputs_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../outputs")
    }

    fn benchmark_output_path() -> PathBuf {
        outputs_dir().join("pulso_agent_incident_benchmark_2026-03-24.json")
    }

    fn seed_path() -> PathBuf {
        outputs_dir().join("uk_blind_validation_scorecard_2026-03-23_98p8.json")
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

    fn fixture_hash<T: Serialize>(value: &T) -> String {
        let json = serde_json::to_vec(value).unwrap();
        let mut hasher = Sha256::new();
        hasher.update(&json);
        format!("{:x}", hasher.finalize())
    }

    fn make_serial(prefix: &str, node: &RealSeedNode, suffix: usize) -> String {
        let cleaned = node
            .building
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
            .collect::<String>();
        format!("{}-{}-{:02}", prefix, cleaned, suffix)
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
            ..Default::default()
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
            vendor_id: Some("INCIDENT-BENCH".into()),
            equipment_id: None,
            firmware_version: None,
            in_octets: None,
            out_octets: None,
            eth_speed_mbps: Some(1000),
            extended: None,
            ..Default::default()
        }
    }

    #[test]
    fn incident_benchmark_realistic_proactive_and_reactive_signatures() {
        let t1 = load_case_nodes("T1");
        let t2 = load_case_nodes("T2");
        let t5 = load_case_nodes("T5");
        let t13 = load_case_nodes("T13");

        let mut scenarios = Vec::new();

        // 1. Reflectance: one ONT throws back light, peers drop, suspect is identifiable.
        {
            let port = "incident/t1/reflectance";
            let suspect = t1[0].clone();
            let victims = t1[1..7].to_vec();
            let base = Utc.with_ymd_and_hms(2026, 3, 20, 0, 0, 0).unwrap();
            let mut readings = Vec::new();

            for hour in 0..24 {
                let ts = base + Duration::hours(hour);
                readings.push(make_reading(
                    make_serial("REFL", &suspect, 1),
                    port,
                    ts,
                    Some(-19.8),
                    Some(if hour % 6 == 0 { 3.2 } else { 2.4 }),
                    OntReadingStatus::Online,
                    suspect.distance_m,
                    Some(1000),
                    None,
                ));
                for (idx, victim) in victims.iter().enumerate() {
                    let serial = make_serial("REFL", victim, idx + 1);
                    let event_window = hour % 6 == 0;
                    readings.push(make_reading(
                        serial,
                        port,
                        ts,
                        Some(if event_window { -40.0 } else { -20.7 }),
                        Some(if event_window { 0.0 } else { 2.3 }),
                        if event_window { OntReadingStatus::Offline } else { OntReadingStatus::Online },
                        victim.distance_m,
                        Some(if event_window { 0 } else { 1000 }),
                        if event_window { Some("los") } else { None },
                    ));
                }
            }

            let hash = fixture_hash(&readings);
            let events = detect_reflectance(&readings, port);
            assert!(!events.is_empty());
            assert_eq!(events[0].suspect_ont_serial, make_serial("REFL", &suspect, 1));
            scenarios.push(ScenarioReport {
                scenario_id: "reflectance_bad_ont".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "suspect_ont": events[0].suspect_ont_serial,
                    "affected_onts": events[0].affected_ont_count,
                }),
            });
        }

        // 2. Hard break: branch mass-offline should classify as fibre cut, not reflectance.
        //    The detector is transition-based: a baseline cycle with the ONTs
        //    online is required before the mass-offline cycle alarms.
        {
            let port = "incident/t1/fibre-cut";
            let nodes = &t1[..10];
            let mut baseline = Vec::new();
            let mut onts = Vec::new();
            for (idx, node) in nodes.iter().enumerate() {
                baseline.push(make_ont(
                    make_serial("CUT", node, idx + 1),
                    port,
                    OntStatus::Online,
                    node.distance_m,
                    -21.0,
                    None,
                ));
                onts.push(make_ont(
                    make_serial("CUT", node, idx + 1),
                    port,
                    OntStatus::Offline,
                    node.distance_m,
                    -28.8,
                    None,
                ));
            }
            let hash = fixture_hash(&onts);
            let cfg = FaultDetectionConfig {
                enabled: true,
                min_offline_onts: 5,
                time_window_seconds: 60,
                severity: FaultSeverityConfig { critical: 100, major: 50, minor: 10 },
            };
            let mut detector = FaultDetector::new(&cfg);
            assert!(
                detector.check(&baseline).is_empty(),
                "baseline cycle must not alarm"
            );
            let events = detector.check(&onts);
            assert_eq!(events.len(), 1);
            assert_eq!(events[0].fault_type, FaultType::FibreCut);
            scenarios.push(ScenarioReport {
                scenario_id: "fibre_cut_branch_outage".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "fault_type": events[0].fault_type.to_string(),
                    "affected_onts": events[0].affected_onts.len(),
                }),
            });
        }

        // 3. Weak splice / cable degradation: proactive optical budget flags before total break.
        {
            let port = "incident/t2/splice";
            let base = Utc.with_ymd_and_hms(2026, 2, 20, 12, 0, 0).unwrap();
            let mut readings = Vec::new();
            for (idx, node) in t2.iter().take(5).enumerate() {
                let serial = make_serial("SPLICE", node, idx + 1);
                for day in 0..14 {
                    let ts = base + Duration::days(day);
                    let rx = if idx == 0 {
                        -26.4 - (day as f64 * 0.08)
                    } else {
                        -22.2 - (idx as f64 * 0.2)
                    };
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        ts,
                        Some(rx),
                        Some(2.6),
                        OntReadingStatus::Online,
                        node.distance_m,
                        Some(1000),
                        None,
                    ));
                }
            }
            let hash = fixture_hash(&readings);
            let budgets = analyze_optical_budget(&readings);
            let suspect = budgets.iter().find(|b| b.ont_serial == make_serial("SPLICE", &t2[0], 1)).unwrap();
            assert!(matches!(suspect.budget_status, BudgetStatus::Critical | BudgetStatus::Marginal | BudgetStatus::Failed));
            assert!(suspect.excess_loss_db > 1.0, "expected meaningful excess loss before break");
            scenarios.push(ScenarioReport {
                scenario_id: "splice_degradation_prebreak".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "suspect_ont": suspect.ont_serial,
                    "margin_db": suspect.margin_db,
                    "issue": suspect.probable_issue.as_ref().map(|i| format!("{:?}", i)).unwrap_or_else(|| "none".into()),
                }),
            });
        }

        // 4. OLT/SFP degradation: all ONTs on one port drift together before failure.
        {
            let base = Utc.with_ymd_and_hms(2026, 3, 1, 9, 0, 0).unwrap();
            let mut readings = Vec::new();
            for port_idx in 0..2 {
                let port = format!("olt-a/pon{}", port_idx);
                for (idx, node) in t13.iter().take(4).enumerate() {
                    for day in 0..21 {
                        let ts = base + Duration::days(day);
                        let slope = if port_idx == 0 { -0.035 } else { -0.002 };
                        let rx = -22.0 + (idx as f64 * -0.05) + slope * day as f64;
                        readings.push(make_reading(
                            make_serial(&format!("SFP{}", port_idx), node, idx + 1),
                            &port,
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
            let hash = fixture_hash(&readings);
            let sfp = analyze_sfp_health(&readings);
            let degraded = sfp.iter().find(|s| s.port == "olt-a/pon0").unwrap();
            assert!(matches!(degraded.severity, SfpSeverity::Warning | SfpSeverity::Critical));
            assert!(degraded.rx_trend_per_week < -0.1);
            scenarios.push(ScenarioReport {
                scenario_id: "sfp_port_degradation_prebreak".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "port": degraded.port,
                    "severity": format!("{:?}", degraded.severity),
                    "trend_per_week": degraded.rx_trend_per_week,
                    "outlier_vs_siblings": degraded.is_outlier_vs_siblings,
                }),
            });
        }

        // 5. Flapping ONT: instability should be isolated with probable cause.
        {
            let port = "incident/t5/flap";
            let node = t5[0].clone();
            let base = Utc.with_ymd_and_hms(2026, 3, 23, 18, 0, 0).unwrap();
            let mut readings = Vec::new();
            for i in 0..24 {
                let ts = base + Duration::minutes(i * 5);
                let online = i % 2 == 0;
                readings.push(make_reading(
                    make_serial("FLAP", &node, 1),
                    port,
                    ts,
                    Some(if online { -25.4 } else { -40.0 }),
                    Some(if online { 2.4 } else { 0.0 }),
                    if online { OntReadingStatus::Online } else { OntReadingStatus::Offline },
                    node.distance_m,
                    Some(if online { 1000 } else { 0 }),
                    if online { None } else { Some("los") },
                ));
            }
            for (idx, peer) in t5.iter().skip(1).take(6).enumerate() {
                readings.push(make_reading(
                    make_serial("FLAPPEER", peer, idx + 1),
                    port,
                    base,
                    Some(-21.8),
                    Some(2.4),
                    OntReadingStatus::Online,
                    peer.distance_m,
                    Some(1000),
                    None,
                ));
            }
            let hash = fixture_hash(&readings);
            let flappers = detect_flapping(&readings);
            assert_eq!(flappers.len(), 1);
            assert!(matches!(flappers[0].probable_cause, FlappingCause::DirtyConnector | FlappingCause::HardwareFault));
            scenarios.push(ScenarioReport {
                scenario_id: "flapping_ont_instability".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "ont": flappers[0].ont_serial,
                    "flap_rate_per_hour": flappers[0].flap_rate_per_hour,
                    "probable_cause": format!("{:?}", flappers[0].probable_cause),
                }),
            });
        }

        // 6. Weather-like degradation should not look like single-customer failure.
        {
            let port = "incident/t13/weather";
            let mut readings = Vec::new();
            for day in 0..7 {
                for hour_idx in 0..6 {
                    let hour = hour_idx * 4;
                    let ts = Utc.with_ymd_and_hms(2026, 3, 10 + day, hour, 0, 0).unwrap();
                    let is_night = hour >= 22 || hour < 6;
                    for (idx, node) in t13.iter().take(4).enumerate() {
                        let serial = make_serial("WX", node, idx + 1);
                        let rx = if is_night { -20.35 } else { -20.0 };
                        readings.push(make_reading(
                            serial,
                            port,
                            ts,
                            Some(rx),
                            Some(2.5),
                            OntReadingStatus::Online,
                            500 + idx as u32 * 20,
                            Some(1000),
                            None,
                        ));
                    }
                }
            }
            let hash = fixture_hash(&readings);
            let correlations = detect_weather_correlation(&readings);
            assert!(correlations.iter().any(|c| c.pattern == WeatherPattern::NighttimeCondensation));
            scenarios.push(ScenarioReport {
                scenario_id: "weather_correlated_degradation".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "patterns": correlations.iter().map(|c| format!("{:?}", c.pattern)).collect::<Vec<_>>(),
                }),
            });
        }

        // 7. Capacity planning should fire before the splitter hits a hard limit.
        {
            let port = "incident/t13/capacity";
            let base = Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap();
            let mut readings = Vec::new();
            for month in 0..7 {
                let ts = base + Duration::days(month * 30);
                let active = 24 + month * 3;
                for idx in 0..active {
                    readings.push(make_reading(
                        format!("CAP-{:02}-{:02}", month, idx),
                        port,
                        ts,
                        Some(-21.5),
                        Some(2.5),
                        OntReadingStatus::Online,
                        400 + idx as u32,
                        Some(1000),
                        None,
                    ));
                }
            }
            let hash = fixture_hash(&readings);
            let caps = predict_splitter_capacity(&readings);
            assert_eq!(caps.len(), 1);
            assert!(matches!(caps[0].alert_level, CapacityAlert::Warning | CapacityAlert::Critical));
            scenarios.push(ScenarioReport {
                scenario_id: "capacity_exhaustion_prebreak".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "active_onts": caps[0].active_onts,
                    "months_to_full": caps[0].months_to_full,
                    "alert_level": format!("{:?}", caps[0].alert_level),
                }),
            });
        }

        // 8. Churn risk / service deterioration should surface before cancellation.
        {
            let port = "incident/t2/churn";
            let base = Utc.with_ymd_and_hms(2026, 2, 1, 12, 0, 0).unwrap();
            let mut readings = Vec::new();
            for (idx, node) in t2.iter().take(4).enumerate() {
                let serial = make_serial("CHURN", node, idx + 1);
                for day in 0..30 {
                    let ts = base + Duration::days(day);
                    let rx = -22.5 - (day as f64 * 0.09);
                    readings.push(make_reading(
                        serial.clone(),
                        port,
                        ts,
                        Some(rx),
                        Some(2.4),
                        OntReadingStatus::Online,
                        node.distance_m,
                        Some(if day % 7 == 0 { 100 } else { 1000 }),
                        None,
                    ));
                    if day % 6 == 0 {
                        readings.push(make_reading(
                            serial.clone(),
                            port,
                            ts + Duration::minutes(30),
                            Some(-40.0),
                            Some(0.0),
                            OntReadingStatus::Offline,
                            node.distance_m,
                            Some(0),
                            Some("los"),
                        ));
                    }
                }
            }
            let hash = fixture_hash(&readings);
            let risks = predict_churn_risk(&readings, 100.0);
            assert!(risks.len() >= 4);
            scenarios.push(ScenarioReport {
                scenario_id: "service_degradation_churn_risk".into(),
                fixture_hash: hash,
                outcome: "pass".into(),
                details: serde_json::json!({
                    "flagged_onts": risks.len(),
                    "top_probability": risks.first().map(|r| r.estimated_churn_probability_90day).unwrap_or(0.0),
                }),
            });
        }

        let report = BenchmarkReport {
            generated_at: Utc::now().to_rfc3339(),
            seed_artifact: seed_path().display().to_string(),
            scenarios_passed: scenarios.len(),
            scenarios_total: scenarios.len(),
            scenarios,
        };

        fs::write(
            benchmark_output_path(),
            serde_json::to_string_pretty(&report).unwrap(),
        ).unwrap();

        assert_eq!(report.scenarios_passed, report.scenarios_total);
    }
}
