// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Enlace (enlace.network)
//
// Pulso Agent — Open-source, vendor-agnostic ISP network intelligence collector.

use clap::Parser;
use std::path::PathBuf;
use tracing::{info, warn, error};

mod config;
mod snmp;
mod vendors;
mod mikrotik;
mod radius;
mod tr069;
mod transport;
mod discovery;
mod diagnostics;
mod predictions;
mod netconf;
mod fault;
mod output;
mod detection;
mod csv_import;
mod audit;
mod serve;
mod metrics;
mod systemd;
#[cfg(test)]
mod audit_tests;
#[cfg(test)]
mod real_seed_tests;
#[cfg(test)]
mod runtime_replay_tests;
#[cfg(test)]
mod incident_benchmark_tests;

struct OltCycleArtifacts {
    diagnostics: diagnostics::OltDiagnostics,
    predictions: predictions::Predictions,
    fault_events: Vec<fault::FaultEvent>,
}

/// Per-(OLT, PON-port) fibre topologies for fault location.
///
/// Ports without configured topology resolve to the empty topology, which
/// makes the locator fall back to its distance-only estimator — better than
/// the old behaviour of sharing one (usually wrong) global topology across
/// every port on every OLT.
struct TopologyRegistry {
    /// Explicit global topology ([topology] mode = "csv"/"synthetic").
    global: Option<fault::FibreTopology>,
    /// Keyed "<olt_id>:<pon_port>", with "<pon_port>" as a fallback key.
    per_port: std::collections::HashMap<String, fault::FibreTopology>,
    empty: fault::FibreTopology,
}

impl TopologyRegistry {
    fn from_config(cfg: Option<&config::TopologyConfig>) -> Self {
        let mut per_port = std::collections::HashMap::new();
        let mut global = None;

        if let Some(t) = cfg {
            for (key, path) in &t.ports {
                let topo = fault::FibreTopology::import_csv(path);
                info!(
                    key = %key,
                    path = %path.display(),
                    nodes = topo.nodes.len(),
                    "Loaded per-port fibre topology"
                );
                per_port.insert(key.clone(), topo);
            }

            global = match t.mode.as_str() {
                "csv" => match t.import_path.as_deref() {
                    Some(path) => Some(fault::FibreTopology::import_csv(path)),
                    None => {
                        warn!("topology mode=csv but no import_path configured — ignoring");
                        None
                    }
                },
                "synthetic" => Some(fault::FibreTopology::synthetic()),
                // "infer" needs live per-port ONT distances; a global
                // topology inferred once from empty inputs is dead weight.
                _ => None,
            };
        }

        Self { global, per_port, empty: fault::FibreTopology::empty() }
    }

    fn resolve(&self, olt_id: &str, pon_port: &str) -> &fault::FibreTopology {
        self.per_port
            .get(&format!("{olt_id}:{pon_port}"))
            .or_else(|| self.per_port.get(pon_port))
            .or(self.global.as_ref())
            .unwrap_or(&self.empty)
    }
}

async fn process_olt_cycle(
    cfg: &config::AgentConfig,
    db: &transport::LocalBuffer,
    telemetry: &mut transport::TelemetryPayload,
    fault_detector: Option<&mut fault::FaultDetector>,
    diag_state: &mut diagnostics::OfflineAlertState,
    topologies: &TopologyRegistry,
    elastic: Option<&output::ElasticOutput>,
    webhooks: Option<&std::sync::Arc<output::WebhookDispatcher>>,
    agent_metrics: &metrics::Metrics,
    data: vendors::OltData,
) -> OltCycleArtifacts {
    if let Err(e) = db.store_signal_history(&data.onts) {
        warn!(error = %e, "Failed to store signal history");
    }
    if let Err(e) = db.store_pon_utilization(&data.olt_id, &data.pon_ports) {
        warn!(error = %e, "Failed to store PON utilization");
    }

    let diagnostics = diagnostics::analyze_olt_stateful(&data, diag_state);
    let predictions = predictions::forecast_olt_configured(&data, db, cfg.degradation.as_ref());

    let mut fault_events = Vec::new();
    if let Some(detector) = fault_detector {
        let updates = detector.check_incidents(&data.olt_id, &data.onts);
        if !updates.is_empty() {
            let online: Vec<String> = data.onts.iter()
                .filter(|o| matches!(o.status, vendors::OntStatus::Online))
                .map(|o| o.serial_number.clone())
                .collect();

            for update in &updates {
                match update.action {
                    fault::IncidentAction::Open => {
                        agent_metrics.record_incident_opened();
                        // Per-(OLT, port) topology; unmapped ports fall back
                        // to the distance-only locator via the empty topology
                        let locator = fault::FaultLocator::new(
                            topologies.resolve(&update.event.olt_id, &update.event.pon_port),
                        );
                        let location = locator.locate(&update.event, &online);
                        info!(
                            olt = %update.event.olt_id,
                            ports = %update.event.pon_port,
                            incident = %update.incident_id,
                            affected = update.event.affected_onts.len(),
                            severity = %update.event.severity,
                            fault_type = %update.event.fault_type,
                            location = %location.description,
                            "Fault incident opened"
                        );
                    }
                    fault::IncidentAction::Resolve => {
                        agent_metrics.record_incident_resolved();
                        info!(
                            olt = %update.event.olt_id,
                            ports = %update.event.pon_port,
                            incident = %update.incident_id,
                            "Fault incident resolved"
                        );
                    }
                }

                // Index open AND resolve transitions — a resolve that never
                // reaches the dashboard is an incident that pages forever
                if let Some(elastic) = elastic {
                    if let Err(e) = elastic.send_incident(update).await {
                        agent_metrics.record_send_failure();
                        warn!(error = %e, "Failed to send incident to Elastic");
                    }
                }

                // Fire-and-forget: never block the poll loop on webhook endpoints
                if let Some(wh) = webhooks {
                    wh.dispatch_incident_detached(update);
                }
            }
        }
        fault_events = updates
            .into_iter()
            .filter(|u| matches!(u.action, fault::IncidentAction::Open))
            .map(|u| u.event)
            .collect();
    }

    if let Some(elastic) = elastic {
        if let Err(e) = elastic.send_onts(
            &cfg.agent_id, &data.olt_id, &data.vendor, &data.model, &data.onts
        ).await {
            agent_metrics.record_send_failure();
            warn!(error = %e, "Failed to send ONTs to Elastic");
        }
    }

    telemetry.add_olt(data);
    telemetry.add_diagnostics(diagnostics.clone());
    telemetry.add_predictions(predictions.clone());

    OltCycleArtifacts {
        diagnostics,
        predictions,
        fault_events,
    }
}

#[derive(Parser, Debug)]
#[command(name = "pulso-agent", version, about)]
struct Args {
    /// Path to configuration file
    #[arg(short, long, default_value = "/etc/pulso-agent/agent.toml")]
    config: PathBuf,

    /// Run in discovery mode (scan network for devices, then exit)
    #[arg(long)]
    discover: bool,

    /// Run a single collection cycle and exit (useful for testing)
    #[arg(long)]
    once: bool,

    /// Print collected data to stdout instead of sending to cloud
    #[arg(long)]
    dry_run: bool,

    /// Verbosity level (-v info, -vv debug, -vvv trace)
    #[arg(short, long, action = clap::ArgAction::Count)]
    verbose: u8,

    /// Path to CSV file for one-time audit (outputs JSON to stdout)
    #[arg(long)]
    audit_csv: Option<PathBuf>,

    /// Start HTTP audit server on this port. Tunables come from env vars:
    /// PULSO_AUDIT_TOKEN (bearer token; generated at startup if unset),
    /// PULSO_AUDIT_BIND (default 127.0.0.1), PULSO_AUDIT_CORS_ORIGIN,
    /// PULSO_AUDIT_BODY_LIMIT_MB (default 50), PULSO_AUDIT_RESULT_TTL_SECS
    /// (default 3600), PULSO_AUDIT_MAX_RESULTS (default 100).
    #[arg(long)]
    serve_port: Option<u16>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    // Initialize structured logging
    let log_level = match args.verbose {
        0 => "warn",
        1 => "info",
        2 => "debug",
        _ => "trace",
    };
    // Logs ALWAYS go to stderr: stdout is reserved for machine-readable
    // output (--audit-csv / --discover JSON), which pipelines consume.
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(log_level)),
        )
        .with_target(false)
        .with_writer(std::io::stderr)
        .json()
        .init();

    info!(
        version = env!("CARGO_PKG_VERSION"),
        "Pulso Agent starting"
    );

    // Handle audit mode: JSON result (including CSV import-quality counters)
    // on stdout, logs on stderr
    if let Some(csv_path) = &args.audit_csv {
        // Operator context (timezone, splitter topology) comes from the agent
        // config when one is present; audits must still run without it, so a
        // missing/broken config only downgrades to honest defaults.
        let options = match config::AgentConfig::load(&args.config) {
            Ok(cfg) => audit::AuditOptions {
                utc_offset_hours: cfg.utc_offset_hours,
                topology: cfg.topology.as_ref().map(|t| {
                    crate::detection::PonTopology {
                        splitter_ratio_by_port: t.splitter_ratios.clone(),
                        technology: Default::default(),
                    }
                }),
            },
            Err(e) => {
                info!(
                    error = %e,
                    "No usable agent config; auditing with default operator context (UTC, assumed splitters)"
                );
                audit::AuditOptions::default()
            }
        };
        // Snapshot exports without a timestamp column get the import time
        let result = crate::audit::run_csv_audit_with_options(
            csv_path,
            None,
            Some(chrono::Utc::now()),
            &options,
        )?;
        println!("{}", serde_json::to_string_pretty(&result)?);
        return Ok(());
    }

    // Handle serve mode
    if let Some(port) = args.serve_port {
        crate::serve::start_server(port).await?;
        return Ok(());
    }

    // Load configuration (validated at load: intervals, SNMP version,
    // placeholder credentials, file permissions)
    let cfg = config::AgentConfig::load(&args.config)?;
    info!(
        agent_id = %cfg.agent_id,
        cloud_endpoint = %cfg.cloud.endpoint,
        olt_count = cfg.olts.len(),
        mikrotik_count = cfg.mikrotiks.len(),
        "Configuration loaded"
    );

    // Point the NETCONF TOFU host-key store at the configured locations
    // before any NETCONF session is opened
    std::env::set_var("PULSO_DATA_DIR", &cfg.data_dir);
    if let Some(path) = &cfg.known_hosts_path {
        std::env::set_var("PULSO_NETCONF_KNOWN_HOSTS", path);
    }

    // Handle SIGHUP gracefully (reload not supported — log instead of dying)
    let _sighup_handle = systemd::spawn_sighup_handler();

    // Initialize local SQLite buffer for offline resilience
    let db = transport::LocalBuffer::open(&cfg.data_dir)?;
    info!("Local buffer initialized at {:?}", cfg.data_dir);

    // Initialize cloud transport + background flusher: the poll loop only
    // writes to the local buffer; delivery (with its retry backoff) happens
    // off the loop
    let cloud = std::sync::Arc::new(transport::CloudTransport::new(&cfg.cloud, args.dry_run)?);
    let flusher_handle = transport::spawn_flusher(
        cloud.clone(),
        db.clone(),
        std::time::Duration::from_secs(30),
    );

    // Agent self-observability: /healthz + /metrics (default 127.0.0.1:9464)
    let agent_metrics = metrics::Metrics::new();
    let metrics_cfg = cfg.metrics.clone().unwrap_or_default();
    let _metrics_server = if metrics_cfg.enabled {
        metrics::spawn_server(&metrics_cfg.bind, agent_metrics.clone(), db.clone()).await
    } else {
        info!("Metrics listener disabled by config");
        None
    };

    // Initialize Elasticsearch output (if configured)
    let mut elastic = cfg.output.as_ref()
        .and_then(|o| o.elastic.as_ref())
        .filter(|e| e.enabled)
        .map(|e| output::ElasticOutput::new(e))
        .transpose()?;

    if let Some(e) = elastic.as_mut() {
        // Failed bulk batches survive restarts via the local buffer
        e.set_retry_buffer(db.clone());
    }
    if let Some(e) = elastic.as_ref() {
        e.ensure_index_setup().await;
        info!("Elasticsearch output enabled");
    }
    let elastic = elastic; // freeze

    // Initialize webhook dispatcher (if configured); Arc so incident
    // notifications can be dispatched off the poll loop
    let webhooks = cfg.output.as_ref()
        .and_then(|o| o.webhooks.as_ref())
        .map(|w| std::sync::Arc::new(output::WebhookDispatcher::new(w)));

    // Initialize fault detector (if configured)
    let mut fault_detector = cfg.fault_detection.as_ref()
        .filter(|f| f.enabled)
        .map(|f| fault::FaultDetector::new(f));

    if fault_detector.is_some() {
        info!("Fault detection enabled");
    }

    // Cross-cycle diagnostics state (offline-alert debounce/dedup)
    let mut diag_state = diagnostics::OfflineAlertState::default();

    // Load fibre topologies (per-(OLT, port) when configured; ports without
    // one get the distance-only locator fallback instead of a dead global)
    let topologies = TopologyRegistry::from_config(cfg.topology.as_ref());

    // Device Discovery mode
    if args.discover {
        info!("Running network discovery...");
        let discovered = discovery::scan_network(&cfg).await?;
        for device in &discovered {
            info!(
                ip = %device.ip,
                vendor = %device.vendor,
                model = %device.model,
                "Discovered device"
            );
        }
        println!("{}", serde_json::to_string_pretty(&discovered)?);
        return Ok(());
    }

    // Initialize vendor-specific collectors. A collector that fails to
    // initialize is a fatal configuration error: silently degrading to the
    // generic IF-MIB collector collects zero ONT optical data.
    let mut olt_collectors: Vec<std::sync::Arc<dyn vendors::OltCollector>> = Vec::new();

    for olt_cfg in &cfg.olts {
        let collector = vendors::create_collector(olt_cfg).map_err(|e| {
            anyhow::anyhow!(
                "Failed to initialize collector for OLT '{}' ({}, vendor \"{}\"): {}. \
                 Fix the vendor name/credentials in the config — the agent no longer \
                 falls back to the generic SNMP collector (it collects no ONT data).",
                olt_cfg.name, olt_cfg.ip, olt_cfg.vendor, e
            )
        })?;
        info!(
            ip = %olt_cfg.ip,
            vendor = %olt_cfg.vendor,
            "OLT collector initialized"
        );
        olt_collectors.push(std::sync::Arc::from(collector));
    }

    // Initialize MikroTik collectors
    let mut mk_collectors: Vec<mikrotik::MikrotikCollector> = Vec::new();
    for mk_cfg in &cfg.mikrotiks {
        match mikrotik::MikrotikCollector::new(mk_cfg).await {
            Ok(collector) => {
                info!(ip = %mk_cfg.ip, "MikroTik collector initialized");
                mk_collectors.push(collector);
            }
            Err(e) => {
                warn!(ip = %mk_cfg.ip, error = %e, "Failed to initialize MikroTik collector");
            }
        }
    }

    // Initialize RADIUS listener (if configured)
    let radius_handle = if let Some(ref radius_cfg) = cfg.radius {
        info!(port = radius_cfg.port, "Starting RADIUS accounting listener");
        Some(tokio::spawn(radius::listen(radius_cfg.clone(), db.clone())))
    } else {
        None
    };

    // Initialize TR-069/GenieACS collector (if configured)
    let tr069_collector = if let Some(ref tr069_cfg) = cfg.tr069 {
        match tr069::Tr069Collector::new(tr069_cfg) {
            Ok(collector) => {
                info!(url = %tr069_cfg.genieacs_url, "TR-069/GenieACS collector initialized");
                Some(collector)
            }
            Err(e) => {
                warn!(error = %e, "Failed to initialize TR-069 collector");
                None
            }
        }
    } else {
        None
    };

    // Startup complete — tell systemd (Type=notify) and start feeding the
    // watchdog (WatchdogSec=) at half its interval
    systemd::notify("READY=1");
    let _watchdog_handle = systemd::spawn_watchdog();

    // Main collection loop with graceful shutdown
    info!(
        "Entering main collection loop (interval: {}s, concurrency: {})",
        cfg.poll_interval_secs, cfg.poll_concurrency
    );

    let mut interval = tokio::time::interval(
        std::time::Duration::from_secs(cfg.poll_interval_secs)
    );
    // A cycle overrun must not trigger a burst of back-to-back cycles
    // (thundering herd against every OLT at once)
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

    let poll_concurrency = cfg.poll_concurrency.max(1);
    let retention = cfg.retention.clone().unwrap_or_default();
    let mut first_cycle = true;

    let shutdown = async {
        let mut sigterm = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("Failed to install SIGTERM handler");
        tokio::select! {
            _ = tokio::signal::ctrl_c() => info!("Received SIGINT"),
            _ = sigterm.recv() => info!("Received SIGTERM"),
        }
    };
    tokio::pin!(shutdown);

    loop {
        tokio::select! {
            _ = &mut shutdown => {
                systemd::notify("STOPPING=1");
                info!("Shutdown signal received, flushing buffers...");
                if let Err(e) = cloud.flush_buffer(&db).await {
                    warn!(error = %e, "Failed to flush buffer on shutdown");
                }
                break;
            }
            _ = interval.tick() => {
                // Collection cycle
            }
        }

        let cycle_start = std::time::Instant::now();
        let mut telemetry = transport::TelemetryPayload::new(&cfg.agent_id);

        // Collect from all OLTs with bounded concurrency. Each OLT gets its
        // own timeout scaled to its last-seen size, so one big/slow OLT can
        // neither discard its own partial cycle budget nor anyone else's
        // results.
        let semaphore = std::sync::Arc::new(tokio::sync::Semaphore::new(poll_concurrency));
        let mut collect_tasks = Vec::with_capacity(olt_collectors.len());

        for (idx, collector) in olt_collectors.iter().enumerate() {
            let semaphore = semaphore.clone();
            let collector = collector.clone();
            let timeout = olt_collect_timeout(&cfg, agent_metrics.last_ont_count(collector.olt_id()));
            // Small startup stagger so all OLTs are not hit at the same
            // instant on the very first cycle
            let jitter = if first_cycle {
                std::time::Duration::from_millis((idx as u64 % poll_concurrency as u64) * 500)
            } else {
                std::time::Duration::ZERO
            };

            collect_tasks.push(tokio::spawn(async move {
                let _permit = semaphore.acquire_owned().await;
                if !jitter.is_zero() {
                    tokio::time::sleep(jitter).await;
                }
                let result = tokio::time::timeout(timeout, collector.collect()).await;
                (collector, timeout, result)
            }));
        }
        first_cycle = false;

        // Process results sequentially (detector/diagnostics state is
        // per-cycle mutable); collection itself ran concurrently above
        for task in collect_tasks {
            let (collector, timeout, result) = match task.await {
                Ok(r) => r,
                Err(e) => {
                    warn!(error = %e, "OLT collection task panicked");
                    continue;
                }
            };

            match result {
                Ok(Ok(data)) => {
                    agent_metrics.record_olt_success(collector.olt_id(), data.onts.len());
                    let _artifacts = process_olt_cycle(
                        &cfg,
                        &db,
                        &mut telemetry,
                        fault_detector.as_mut(),
                        &mut diag_state,
                        &topologies,
                        elastic.as_ref(),
                        webhooks.as_ref(),
                        &agent_metrics,
                        data,
                    ).await;
                }
                Ok(Err(e)) => {
                    agent_metrics.record_olt_failure(collector.olt_id());
                    warn!(olt = %collector.olt_id(), error = %e, "OLT collection failed");
                    telemetry.add_error(collector.olt_id(), e.to_string());
                }
                Err(_) => {
                    agent_metrics.record_olt_failure(collector.olt_id());
                    warn!(
                        olt = %collector.olt_id(),
                        timeout_secs = timeout.as_secs(),
                        "OLT collection timed out (other OLTs unaffected)"
                    );
                    telemetry.add_error(collector.olt_id(), "Collection timeout".into());
                }
            }
        }

        // Collect from all MikroTik routers (with per-device timeout)
        for collector in &mk_collectors {
            let result = tokio::time::timeout(
                std::time::Duration::from_secs(30),
                collector.collect(),
            ).await;

            match result {
                Ok(Ok(data)) => telemetry.add_mikrotik(data),
                Ok(Err(e)) => {
                    warn!(mikrotik = %collector.router_id(), error = %e, "MikroTik collection failed");
                }
                Err(_) => {
                    warn!(mikrotik = %collector.router_id(), "MikroTik collection timed out");
                }
            }
        }

        // Add RADIUS session summary
        if cfg.radius.is_some() {
            if let Ok(sessions) = db.get_radius_summary() {
                telemetry.add_radius(sessions);
            }
        }

        // Collect TR-069/GenieACS CPE devices
        if let Some(ref collector) = tr069_collector {
            let result = tokio::time::timeout(
                std::time::Duration::from_secs(30),
                collector.collect(),
            ).await;

            match result {
                Ok(Ok(devices)) => {
                    info!(count = devices.len(), "TR-069 CPE devices collected");
                    telemetry.add_tr069(devices);
                }
                Ok(Err(e)) => {
                    warn!(error = %e, "TR-069 collection failed");
                }
                Err(_) => {
                    warn!("TR-069 collection timed out after 30s");
                }
            }
        }

        let elapsed = cycle_start.elapsed();
        info!(
            olts = telemetry.olt_count(),
            onts = telemetry.total_onts(),
            mikrotiks = telemetry.mikrotik_count(),
            elapsed_ms = elapsed.as_millis() as u64,
            "Collection cycle complete"
        );

        // Queue locally; the background flusher delivers to the cloud
        // (including its retry backoff) without blocking the poll loop
        if let Err(e) = db.store(&telemetry) {
            agent_metrics.record_send_failure();
            error!(error = %e, "Failed to buffer telemetry locally");
        }

        // Drain any Elasticsearch batches that failed on earlier cycles
        if let Some(e) = elastic.as_ref() {
            if let Err(err) = e.flush_retry_buffer(&db).await {
                warn!(error = %err, "Failed to flush Elasticsearch retry buffer");
            }
        }

        agent_metrics.record_cycle_completed();

        if args.once {
            info!("Single collection cycle complete, flushing and exiting");
            if let Err(e) = cloud.flush_buffer(&db).await {
                warn!(error = %e, "Failed to flush buffer before exit");
            }
            break;
        }

        // Periodically downsample old signal readings (every cycle) and
        // apply age-based retention to all local history tables
        if let Err(e) = db.downsample_old_readings(24) {
            warn!(error = %e, "Failed to downsample signal readings");
        }
        if let Err(e) = db.prune_history(&retention) {
            warn!(error = %e, "Failed to prune local history");
        }
    }

    // Cleanup
    systemd::notify("STOPPING=1");
    flusher_handle.abort();
    if let Some(handle) = radius_handle {
        handle.abort();
    }

    info!("Pulso Agent shutting down");
    Ok(())
}

/// Per-OLT collection timeout: base + per-ONT allowance scaled by the ONT
/// count seen on the last successful collect, floored at 60s. The per-ONT
/// allowance covers SNMP worst case (each PDU can cost 3x the SNMP timeout
/// plus 600ms of retransmit backoff before failing).
fn olt_collect_timeout(
    cfg: &config::AgentConfig,
    last_ont_count: Option<usize>,
) -> std::time::Duration {
    let scaled_ms = cfg
        .olt_timeout_base_secs
        .saturating_mul(1000)
        .saturating_add(cfg.olt_timeout_per_ont_ms.saturating_mul(last_ont_count.unwrap_or(0) as u64));
    std::time::Duration::from_millis(scaled_ms.max(60_000))
}

#[cfg(test)]
mod main_tests {
    use super::*;

    fn cfg_with_timeouts(base_secs: u64, per_ont_ms: u64) -> config::AgentConfig {
        let toml = format!(
            r#"
agent_id = "t"
olt_timeout_base_secs = {base_secs}
olt_timeout_per_ont_ms = {per_ont_ms}

[cloud]
endpoint = "https://api.example.com"
api_key = "k"
"#
        );
        toml::from_str(&toml).unwrap()
    }

    #[test]
    fn olt_timeout_floors_at_60s() {
        let cfg = cfg_with_timeouts(5, 10);
        assert_eq!(
            olt_collect_timeout(&cfg, None),
            std::time::Duration::from_secs(60)
        );
        assert_eq!(
            olt_collect_timeout(&cfg, Some(10)),
            std::time::Duration::from_secs(60)
        );
    }

    #[test]
    fn olt_timeout_scales_with_ont_count() {
        let cfg = cfg_with_timeouts(60, 100);
        // 60s base + 100ms * 4096 ONTs = 469.6s
        assert_eq!(
            olt_collect_timeout(&cfg, Some(4096)),
            std::time::Duration::from_millis(60_000 + 409_600)
        );
        // Unknown size (first cycle) = base only
        assert_eq!(
            olt_collect_timeout(&cfg, None),
            std::time::Duration::from_secs(60)
        );
    }

    #[test]
    fn topology_registry_resolves_per_port_then_global_then_empty() {
        // No config at all: everything resolves to the empty topology
        // (locator falls back to distance-only)
        let reg = TopologyRegistry::from_config(None);
        assert!(reg.resolve("OLT-1", "1/1/1").nodes.is_empty());

        // "infer" mode (the old dead-global path) must yield NO global
        let t: config::TopologyConfig = toml::from_str(r#"mode = "infer""#).unwrap();
        let reg = TopologyRegistry::from_config(Some(&t));
        assert!(reg.global.is_none());
        assert!(reg.resolve("OLT-1", "1/1/1").nodes.is_empty());

        // synthetic global applies to unmapped ports
        let t: config::TopologyConfig = toml::from_str(r#"mode = "synthetic""#).unwrap();
        let reg = TopologyRegistry::from_config(Some(&t));
        assert!(!reg.resolve("OLT-1", "1/1/1").nodes.is_empty());
    }
}
