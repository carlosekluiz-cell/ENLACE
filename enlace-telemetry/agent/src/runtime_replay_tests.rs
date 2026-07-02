#[cfg(test)]
mod runtime_replay {
    use std::fs;
    use std::path::PathBuf;
    use std::sync::{Arc, Mutex};

    use chrono::{Duration, TimeZone, Utc};
    use serde::Deserialize;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    use crate::config::{
        AgentConfig, CloudConfig, ElasticConfig, FaultDetectionConfig, FaultSeverityConfig,
        OutputConfig, WebhookConfig,
    };
    use crate::fault::{FaultDetector, FibreTopology};
    use crate::output::{ElasticOutput, WebhookDispatcher};
    use crate::transport::{CloudTransport, LocalBuffer, TelemetryPayload};
    use crate::vendors::{OltData, OntData, OntStatus, PonPortData, UplinkPortData};
    use crate::process_olt_cycle;

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

    #[derive(Clone, Debug)]
    struct RecordedRequest {
        path: String,
        body: String,
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

    async fn spawn_http_sink() -> (String, Arc<Mutex<Vec<RecordedRequest>>>, tokio::task::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let records = Arc::new(Mutex::new(Vec::<RecordedRequest>::new()));
        let sink_records = Arc::clone(&records);

        let handle = tokio::spawn(async move {
            loop {
                let (mut socket, _) = match listener.accept().await {
                    Ok(pair) => pair,
                    Err(_) => break,
                };
                let records = Arc::clone(&sink_records);
                tokio::spawn(async move {
                    let mut bytes = Vec::new();
                    let mut tmp = [0u8; 4096];
                    let header_end;
                    loop {
                        let n = socket.read(&mut tmp).await.unwrap_or(0);
                        if n == 0 {
                            return;
                        }
                        bytes.extend_from_slice(&tmp[..n]);
                        if let Some(pos) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
                            header_end = pos + 4;
                            break;
                        }
                    }

                    let header = String::from_utf8_lossy(&bytes[..header_end]);
                    let mut path = "/".to_string();
                    if let Some(line) = header.lines().next() {
                        let mut parts = line.split_whitespace();
                        let _method = parts.next();
                        if let Some(p) = parts.next() {
                            path = p.to_string();
                        }
                    }

                    let content_length = header
                        .lines()
                        .find_map(|line| {
                            let (name, value) = line.split_once(':')?;
                            if name.eq_ignore_ascii_case("content-length") {
                                value.trim().parse::<usize>().ok()
                            } else {
                                None
                            }
                        })
                        .unwrap_or(0);

                    while bytes.len() < header_end + content_length {
                        let n = socket.read(&mut tmp).await.unwrap_or(0);
                        if n == 0 {
                            break;
                        }
                        bytes.extend_from_slice(&tmp[..n]);
                    }

                    let body = String::from_utf8_lossy(
                        &bytes[header_end..bytes.len().min(header_end + content_length)]
                    ).to_string();
                    records.lock().unwrap().push(RecordedRequest { path, body });

                    let response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok";
                    let _ = socket.write_all(response).await;
                    let _ = socket.shutdown().await;
                });
            }
        });

        (format!("http://{}", addr), records, handle)
    }

    fn make_agent_config() -> AgentConfig {
        AgentConfig {
            agent_id: "replay-agent".into(),
            data_dir: PathBuf::new(),
            poll_interval_secs: 60,
            cloud: CloudConfig {
                endpoint: "http://127.0.0.1:1/ingest".into(),
                api_key: "test-key".into(),
                send_interval_secs: 60,
                verify_tls: false,
            },
            olts: Vec::new(),
            mikrotiks: Vec::new(),
            radius: None,
            tr069: None,
            scan_range: None,
            scan_communities: None,
            output: Some(OutputConfig {
                cloud: None,
                elastic: None,
                webhooks: None,
            }),
            fault_detection: Some(FaultDetectionConfig {
                enabled: true,
                min_offline_onts: 5,
                time_window_seconds: 60,
                severity: FaultSeverityConfig {
                    critical: 100,
                    major: 50,
                    minor: 10,
                },
            }),
            topology: None,
            degradation: None,
        }
    }

    fn seed_signal_history(
        db: &LocalBuffer,
        olt_id: &str,
        nodes: &[RealSeedNode],
        port_id: &str,
    ) {
        let conn = db.conn().unwrap();
        let base = Utc::now().timestamp() - (10 * 86400);

        for (idx, node) in nodes.iter().enumerate() {
            let serial = make_serial("REPLAY", node, idx + 1);
            for day in 0..10 {
                let ts = base + (day as i64 * 86400);
                let rx = -20.5 - (day as f64 * 0.08) - ((idx % 3) as f64 * 0.1);
                conn.execute(
                    "INSERT OR REPLACE INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES (?1, ?2, ?3)",
                    rusqlite::params![serial, rx, ts],
                ).unwrap();
            }
        }

        for day in 0..10 {
            let ts = base + (day as i64 * 86400);
            let util = 66.0 + day as f32 * 2.2;
            conn.execute(
                "INSERT OR REPLACE INTO pon_utilization_history (olt_id, port_id, utilization_percent, timestamp) VALUES (?1, ?2, ?3, ?4)",
                rusqlite::params![olt_id, port_id, util, ts],
            ).unwrap();
        }
    }

    fn make_replay_olt(nodes: &[RealSeedNode]) -> OltData {
        let port_id = "replay/pon0";
        let mut onts = Vec::new();
        for (idx, node) in nodes.iter().enumerate() {
            let serial = make_serial("REPLAY", node, idx + 1);
            let is_faulted = idx >= 3 && idx < 9;
            let status = if is_faulted {
                OntStatus::Offline
            } else if idx == 0 {
                OntStatus::LowSignal
            } else {
                OntStatus::Online
            };
            let rx = if is_faulted {
                Some(-29.4)
            } else if idx == 0 {
                Some(-28.3)
            } else {
                Some(-24.0 - ((idx % 4) as f64 * 0.35))
            };

            onts.push(OntData {
                serial_number: serial,
                pon_port: port_id.into(),
                ont_index: idx as u32 + 1,
                status,
                last_down_cause: if is_faulted { Some("los".into()) } else { None },
                uptime_seconds: Some(86_400),
                rx_power_dbm: rx,
                tx_power_dbm: Some(2.5),
                distance_meters: Some(node.distance_m),
                vendor_id: Some(node.branch.clone()),
                equipment_id: Some(format!("{}-{}", node.branch, node.dwellings)),
                firmware_version: Some("seeded-1.0".into()),
                in_octets: Some((idx as u64 + 1) * 1_000_000),
                out_octets: Some((idx as u64 + 1) * 2_000_000),
                eth_speed_mbps: Some(if idx == 0 { 100 } else { 1000 }),
                extended: None,
            });
        }

        OltData {
            olt_id: "Replay-OLT-01".into(),
            vendor: "seeded".into(),
            model: "ReplayHarness".into(),
            firmware: "2026.03".into(),
            serial: "REPLAY-0001".into(),
            uptime_seconds: 1_234_567,
            timestamp: Utc.with_ymd_and_hms(2026, 3, 23, 12, 0, 0).unwrap(),
            cpu_percent: Some(37.5),
            memory_percent: Some(42.0),
            temperature_celsius: Some(49.0),
            power_supply_status: Some("ok".into()),
            pon_ports: vec![PonPortData {
                port_id: port_id.into(),
                oper_status: "up".into(),
                onts_registered: onts.len() as u32,
                onts_online: onts.iter().filter(|o| matches!(o.status, OntStatus::Online | OntStatus::LowSignal)).count() as u32,
                onts_offline: onts.iter().filter(|o| matches!(o.status, OntStatus::Offline | OntStatus::PowerFail | OntStatus::FiberCut)).count() as u32,
                bw_down_bps: 7_800_000_000,
                bw_up_bps: 1_950_000_000,
                utilization_percent: 88.0,
            }],
            uplink_ports: vec![UplinkPortData {
                port_id: "xe-0/0/1".into(),
                oper_status: "up".into(),
                speed_mbps: 10_000,
                in_octets: 9_000_000_000,
                out_octets: 3_000_000_000,
                in_errors: 0,
                out_errors: 0,
            }],
            onts,
        }
    }

    #[tokio::test]
    async fn runtime_replay_exercises_live_cycle_path() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();
        let cfg = make_agent_config();
        let mut telemetry = TelemetryPayload::new(&cfg.agent_id);
        let mut detector = FaultDetector::new(cfg.fault_detection.as_ref().unwrap());
        let topology = FibreTopology::empty();

        let t1_nodes = load_case_nodes("T1");
        let replay_nodes: Vec<RealSeedNode> = t1_nodes.into_iter().take(12).collect();
        seed_signal_history(&db, "Replay-OLT-01", &replay_nodes, "replay/pon0");
        let olt = make_replay_olt(&replay_nodes);

        let (server_url, requests, server_handle) = spawn_http_sink().await;

        let elastic = ElasticOutput::new(&ElasticConfig {
            enabled: true,
            url: server_url.clone(),
            index_prefix: "replay".into(),
            bulk_size: 500,
            username: None,
            password: None,
            api_key: None,
            verify_tls: false,
        }).unwrap();

        let webhooks = WebhookDispatcher::new(&[WebhookConfig {
            url: server_url.clone(),
            events: vec!["fault_detected".into()],
            format: "generic".into(),
            routing_key: None,
        }]);

        let artifacts = process_olt_cycle(
            &cfg,
            &db,
            &mut telemetry,
            Some(&mut detector),
            &topology,
            Some(&elastic),
            Some(&webhooks),
            olt,
        ).await;

        let cloud = CloudTransport::new(&cfg.cloud, true).unwrap();
        cloud.send(&telemetry).await.unwrap();
        db.downsample_old_readings(24).unwrap();

        tokio::time::sleep(std::time::Duration::from_millis(150)).await;

        let captured = requests.lock().unwrap().clone();
        server_handle.abort();

        assert_eq!(telemetry.olt_count(), 1);
        assert_eq!(telemetry.diagnostics.len(), 1);
        assert_eq!(telemetry.predictions.len(), 1);
        assert_eq!(telemetry.total_onts(), 12);

        assert!(!artifacts.diagnostics.alerts.is_empty(), "expected runtime diagnostics");
        assert!(!artifacts.diagnostics.capacity_warnings.is_empty(), "expected capacity warning");
        assert!(!artifacts.predictions.signal_degradation.is_empty(), "expected signal degradation predictions");
        assert!(!artifacts.predictions.capacity_forecasts.is_empty(), "expected capacity forecasts");
        assert!(!artifacts.predictions.customer_diagnostics.is_empty(), "expected customer diagnostics");
        assert!(!artifacts.fault_events.is_empty(), "expected mass-offline fault event");

        assert!(captured.len() >= 3, "expected Elastic fault + Elastic ONTs + webhook HTTP sends");
        assert!(captured.iter().any(|r| r.path == "/_bulk" && r.body.contains("\"affected_onts_count\"")));
        assert!(captured.iter().any(|r| {
            r.path == "/_bulk"
                && r.body.contains("\"serial\":\"REPLAY-")
                && r.body.contains("\"pon_port\":\"replay/pon0\"")
        }));
        assert!(captured.iter().any(|r| r.path == "/" && r.body.contains("\"pon_port\":\"replay/pon0\"")));
    }
}
