// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Pulso Network (pulsonetwork.com.br)
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
mod fault;
mod output;

#[derive(Parser, Debug)]
#[command(name = "pulso-agent", version, about)]
struct Args {
    /// Path to configuration file
    #[arg(short, long, default_value = "/etc/pulso/agent.toml")]
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
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(log_level)),
        )
        .with_target(false)
        .json()
        .init();

    info!(
        version = env!("CARGO_PKG_VERSION"),
        "Pulso Agent starting"
    );

    // Load configuration
    let cfg = config::AgentConfig::load(&args.config)?;
    info!(
        agent_id = %cfg.agent_id,
        cloud_endpoint = %cfg.cloud.endpoint,
        olt_count = cfg.olts.len(),
        mikrotik_count = cfg.mikrotiks.len(),
        "Configuration loaded"
    );

    // Initialize local SQLite buffer for offline resilience
    let db = transport::LocalBuffer::open(&cfg.data_dir)?;
    info!("Local buffer initialized at {:?}", cfg.data_dir);

    // Initialize cloud transport
    let cloud = transport::CloudTransport::new(&cfg.cloud, args.dry_run)?;

    // Initialize Elasticsearch output (if configured)
    let elastic = cfg.output.as_ref()
        .and_then(|o| o.elastic.as_ref())
        .filter(|e| e.enabled)
        .map(|e| output::ElasticOutput::new(e))
        .transpose()?;

    if elastic.is_some() {
        info!("Elasticsearch output enabled");
    }

    // Initialize webhook dispatcher (if configured)
    let webhooks = cfg.output.as_ref()
        .and_then(|o| o.webhooks.as_ref())
        .map(|w| output::WebhookDispatcher::new(w));

    // Initialize fault detector (if configured)
    let mut fault_detector = cfg.fault_detection.as_ref()
        .filter(|f| f.enabled)
        .map(|f| fault::FaultDetector::new(f));

    if fault_detector.is_some() {
        info!("Fault detection enabled");
    }

    // Load fibre topology (if configured)
    let topology = cfg.topology.as_ref()
        .map(|t| fault::FibreTopology::load(&t.mode, t.import_path.as_deref(), "", &[]))
        .unwrap_or_else(|| fault::FibreTopology::empty());

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

    // Initialize vendor-specific collectors
    let mut olt_collectors: Vec<Box<dyn vendors::OltCollector>> = Vec::new();

    for olt_cfg in &cfg.olts {
        match vendors::create_collector(olt_cfg) {
            Ok(collector) => {
                info!(
                    ip = %olt_cfg.ip,
                    vendor = %olt_cfg.vendor,
                    "OLT collector initialized"
                );
                olt_collectors.push(collector);
            }
            Err(e) => {
                warn!(
                    ip = %olt_cfg.ip,
                    vendor = %olt_cfg.vendor,
                    error = %e,
                    "Failed to initialize OLT collector, will use generic SNMP"
                );
                olt_collectors.push(Box::new(vendors::generic::GenericCollector::new(olt_cfg)));
            }
        }
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

    // Main collection loop with graceful shutdown
    info!("Entering main collection loop (interval: {}s)", cfg.poll_interval_secs);

    let mut interval = tokio::time::interval(
        std::time::Duration::from_secs(cfg.poll_interval_secs)
    );

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

        // Collect from all OLTs (with per-device timeout)
        for collector in &olt_collectors {
            let result = tokio::time::timeout(
                std::time::Duration::from_secs(60),
                collector.collect(),
            ).await;

            match result {
                Ok(Ok(data)) => {
                    // Store signal history for predictions
                    if let Err(e) = db.store_signal_history(&data.onts) {
                        warn!(error = %e, "Failed to store signal history");
                    }
                    if let Err(e) = db.store_pon_utilization(&data.olt_id, &data.pon_ports) {
                        warn!(error = %e, "Failed to store PON utilization");
                    }

                    // Run diagnostics
                    let diag = diagnostics::analyze_olt(&data);
                    // Run predictions (with configurable thresholds)
                    let preds = predictions::forecast_olt_configured(
                        &data, &db, cfg.degradation.as_ref()
                    );

                    // Fault detection (runs before data is moved)
                    if let Some(ref mut detector) = fault_detector {
                        let mut events = detector.check(&data.onts);
                        for event in &mut events {
                            event.olt_id = data.olt_id.clone();
                        }
                        if !events.is_empty() {
                            let locator = fault::FaultLocator::new(&topology);
                            let online: Vec<String> = data.onts.iter()
                                .filter(|o| matches!(o.status, vendors::OntStatus::Online))
                                .map(|o| o.serial_number.clone())
                                .collect();

                            for event in &events {
                                let _location = locator.locate(event, &online);
                                info!(
                                    olt = %event.olt_id,
                                    port = %event.pon_port,
                                    affected = event.affected_onts.len(),
                                    severity = %event.severity,
                                    "Fault detected"
                                );

                                // Send fault to Elasticsearch
                                if let Some(ref elastic) = elastic {
                                    if let Err(e) = elastic.send_fault(event).await {
                                        warn!(error = %e, "Failed to send fault to Elastic");
                                    }
                                }

                                // Dispatch webhooks
                                if let Some(ref wh) = webhooks {
                                    wh.dispatch_fault(event).await;
                                }
                            }
                        }
                    }

                    // Send ONT data to Elasticsearch
                    if let Some(ref elastic) = elastic {
                        if let Err(e) = elastic.send_onts(
                            &cfg.agent_id, &data.olt_id, &data.vendor, &data.model, &data.onts
                        ).await {
                            warn!(error = %e, "Failed to send ONTs to Elastic");
                        }
                    }

                    // NOW move data into telemetry payload
                    telemetry.add_olt(data);
                    telemetry.add_diagnostics(diag);
                    telemetry.add_predictions(preds);
                }
                Ok(Err(e)) => {
                    warn!(olt = %collector.olt_id(), error = %e, "OLT collection failed");
                    telemetry.add_error(collector.olt_id(), e.to_string());
                }
                Err(_) => {
                    warn!(olt = %collector.olt_id(), "OLT collection timed out after 60s");
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

        // Send to cloud (or buffer locally if offline)
        match cloud.send(&telemetry).await {
            Ok(_) => {
                info!("Telemetry sent to Pulso Cloud");
                if let Err(e) = cloud.flush_buffer(&db).await {
                    warn!(error = %e, "Failed to flush offline buffer");
                }
            }
            Err(e) => {
                warn!(error = %e, "Cloud unreachable, buffering locally");
                if let Err(e) = db.store(&telemetry) {
                    error!(error = %e, "Failed to buffer telemetry locally");
                }
            }
        }

        if args.once {
            info!("Single collection cycle complete, exiting");
            break;
        }

        // Periodically downsample old signal readings (every cycle)
        if let Err(e) = db.downsample_old_readings(24) {
            warn!(error = %e, "Failed to downsample signal readings");
        }
    }

    // Cleanup
    if let Some(handle) = radius_handle {
        handle.abort();
    }

    info!("Pulso Agent shutting down");
    Ok(())
}
