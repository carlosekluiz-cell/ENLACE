// SPDX-License-Identifier: Apache-2.0
// Agent self-observability: a minimal /healthz + /metrics HTTP listener for
// AGENT mode. The product is observability — the agent itself must be
// observable. Prometheus text format, hand-rolled (no prometheus crate);
// axum is already a dependency for the audit server.
//
// Default bind is loopback only (127.0.0.1:9464); operators opt in to wider
// exposure via `[metrics] bind` in the config.

use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use tracing::{info, warn};

use crate::transport::LocalBuffer;

/// Per-OLT collection stats, updated by the poll loop.
#[derive(Debug, Clone, Default)]
struct OltStats {
    /// Unix timestamp of the last successful collect (0 = never).
    last_successful_collect_ts: i64,
    /// ONT count from the last successful collect.
    ont_count: usize,
    /// Consecutive collect failures since the last success.
    consecutive_failures: u64,
}

/// Shared counters for the agent poll loop. Cheap to update (atomics + one
/// small mutex-guarded map), scraped by the /metrics endpoint.
#[derive(Debug, Default)]
pub struct Metrics {
    olts: Mutex<HashMap<String, OltStats>>,
    send_failures: AtomicU64,
    incidents_opened: AtomicU64,
    incidents_resolved: AtomicU64,
    cycles_completed: AtomicU64,
}

impl Metrics {
    pub fn new() -> Arc<Self> {
        Arc::new(Self::default())
    }

    pub fn record_olt_success(&self, olt_id: &str, ont_count: usize) {
        let mut olts = self.olts.lock().unwrap();
        let entry = olts.entry(olt_id.to_string()).or_default();
        entry.last_successful_collect_ts = chrono::Utc::now().timestamp();
        entry.ont_count = ont_count;
        entry.consecutive_failures = 0;
    }

    pub fn record_olt_failure(&self, olt_id: &str) {
        let mut olts = self.olts.lock().unwrap();
        let entry = olts.entry(olt_id.to_string()).or_default();
        entry.consecutive_failures += 1;
    }

    /// ONT count from the last successful collect, used to scale the
    /// per-OLT collection timeout. None before the first success.
    pub fn last_ont_count(&self, olt_id: &str) -> Option<usize> {
        let olts = self.olts.lock().unwrap();
        olts.get(olt_id)
            .filter(|s| s.last_successful_collect_ts > 0)
            .map(|s| s.ont_count)
    }

    pub fn record_send_failure(&self) {
        self.send_failures.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_incident_opened(&self) {
        self.incidents_opened.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_incident_resolved(&self) {
        self.incidents_resolved.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_cycle_completed(&self) {
        self.cycles_completed.fetch_add(1, Ordering::Relaxed);
    }

    /// Render Prometheus text exposition format (version 0.0.4).
    /// Buffer depth / dead-letter counts are read live from the local buffer.
    pub fn render(&self, db: Option<&LocalBuffer>) -> String {
        let mut out = String::with_capacity(2048);

        out.push_str("# HELP pulso_agent_up Whether the agent process is up.\n");
        out.push_str("# TYPE pulso_agent_up gauge\n");
        out.push_str("pulso_agent_up 1\n");

        out.push_str("# HELP pulso_collection_cycles_total Completed collection cycles.\n");
        out.push_str("# TYPE pulso_collection_cycles_total counter\n");
        out.push_str(&format!(
            "pulso_collection_cycles_total {}\n",
            self.cycles_completed.load(Ordering::Relaxed)
        ));

        {
            let olts = self.olts.lock().unwrap();
            out.push_str("# HELP pulso_last_successful_collect_timestamp_seconds Unix time of the last successful collect per OLT (0 = never).\n");
            out.push_str("# TYPE pulso_last_successful_collect_timestamp_seconds gauge\n");
            for (olt, stats) in olts.iter() {
                out.push_str(&format!(
                    "pulso_last_successful_collect_timestamp_seconds{{olt=\"{}\"}} {}\n",
                    escape_label(olt),
                    stats.last_successful_collect_ts
                ));
            }
            out.push_str("# HELP pulso_ont_count ONTs seen in the last successful collect per OLT.\n");
            out.push_str("# TYPE pulso_ont_count gauge\n");
            for (olt, stats) in olts.iter() {
                out.push_str(&format!(
                    "pulso_ont_count{{olt=\"{}\"}} {}\n",
                    escape_label(olt),
                    stats.ont_count
                ));
            }
            out.push_str("# HELP pulso_collect_consecutive_failures Consecutive collect failures since the last success per OLT.\n");
            out.push_str("# TYPE pulso_collect_consecutive_failures gauge\n");
            for (olt, stats) in olts.iter() {
                out.push_str(&format!(
                    "pulso_collect_consecutive_failures{{olt=\"{}\"}} {}\n",
                    escape_label(olt),
                    stats.consecutive_failures
                ));
            }
        }

        out.push_str("# HELP pulso_send_failures_total Failed telemetry/incident deliveries observed by the poll loop.\n");
        out.push_str("# TYPE pulso_send_failures_total counter\n");
        out.push_str(&format!(
            "pulso_send_failures_total {}\n",
            self.send_failures.load(Ordering::Relaxed)
        ));

        out.push_str("# HELP pulso_incidents_opened_total Fault incidents opened.\n");
        out.push_str("# TYPE pulso_incidents_opened_total counter\n");
        out.push_str(&format!(
            "pulso_incidents_opened_total {}\n",
            self.incidents_opened.load(Ordering::Relaxed)
        ));

        out.push_str("# HELP pulso_incidents_resolved_total Fault incidents resolved.\n");
        out.push_str("# TYPE pulso_incidents_resolved_total counter\n");
        out.push_str(&format!(
            "pulso_incidents_resolved_total {}\n",
            self.incidents_resolved.load(Ordering::Relaxed)
        ));

        if let Some(db) = db {
            out.push_str("# HELP pulso_buffer_depth Telemetry payloads queued in the local buffer.\n");
            out.push_str("# TYPE pulso_buffer_depth gauge\n");
            match buffer_depth(db) {
                Ok(n) => out.push_str(&format!("pulso_buffer_depth {}\n", n)),
                Err(e) => warn!(error = %e, "Failed to read buffer depth for /metrics"),
            }

            out.push_str("# HELP pulso_dead_letter_total Quarantined (undeserializable) payloads in the dead-letter table.\n");
            out.push_str("# TYPE pulso_dead_letter_total gauge\n");
            match db.dead_letter_count() {
                Ok(n) => out.push_str(&format!("pulso_dead_letter_total {}\n", n)),
                Err(e) => warn!(error = %e, "Failed to read dead-letter count for /metrics"),
            }
        }

        out
    }
}

/// Rows currently queued in the telemetry buffer.
fn buffer_depth(db: &LocalBuffer) -> anyhow::Result<u64> {
    let conn = db.conn()?;
    let n: i64 = conn.query_row("SELECT COUNT(*) FROM telemetry_buffer", [], |r| r.get(0))?;
    Ok(n as u64)
}

/// Escape a Prometheus label value (backslash, quote, newline).
fn escape_label(v: &str) -> String {
    v.replace('\\', "\\\\").replace('"', "\\\"").replace('\n', "\\n")
}

#[derive(Clone)]
struct ServerState {
    metrics: Arc<Metrics>,
    db: LocalBuffer,
}

/// Spawn the /healthz + /metrics listener. Returns None (with a logged
/// warning) if the bind address is unusable — self-observability must never
/// take the collector down.
pub async fn spawn_server(
    bind: &str,
    metrics: Arc<Metrics>,
    db: LocalBuffer,
) -> Option<tokio::task::JoinHandle<()>> {
    let listener = match tokio::net::TcpListener::bind(bind).await {
        Ok(l) => l,
        Err(e) => {
            warn!(bind, error = %e, "Failed to bind metrics listener — /healthz and /metrics disabled");
            return None;
        }
    };
    let addr = listener.local_addr().ok();
    info!(bind = %addr.map(|a| a.to_string()).unwrap_or_else(|| bind.to_string()),
          "Metrics listener started (/healthz, /metrics)");

    let state = ServerState { metrics, db };
    let app = axum::Router::new()
        .route("/healthz", axum::routing::get(healthz_handler))
        .route("/metrics", axum::routing::get(metrics_handler))
        .with_state(state);

    Some(tokio::spawn(async move {
        if let Err(e) = axum::serve(listener, app).await {
            warn!(error = %e, "Metrics listener exited");
        }
    }))
}

async fn healthz_handler() -> &'static str {
    "ok\n"
}

async fn metrics_handler(
    axum::extract::State(state): axum::extract::State<ServerState>,
) -> axum::response::Response {
    let body = state.metrics.render(Some(&state.db));
    axum::response::Response::builder()
        .status(axum::http::StatusCode::OK)
        .header(
            axum::http::header::CONTENT_TYPE,
            "text/plain; version=0.0.4; charset=utf-8",
        )
        .body(axum::body::Body::from(body))
        .unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_includes_counters_and_olts() {
        let m = Metrics::new();
        m.record_olt_success("OLT-1", 512);
        m.record_olt_failure("OLT-2");
        m.record_send_failure();
        m.record_incident_opened();
        m.record_incident_opened();
        m.record_incident_resolved();
        m.record_cycle_completed();

        let text = m.render(None);
        assert!(text.contains("pulso_agent_up 1"));
        assert!(text.contains("pulso_ont_count{olt=\"OLT-1\"} 512"));
        assert!(text.contains("pulso_last_successful_collect_timestamp_seconds{olt=\"OLT-1\"}"));
        assert!(text.contains("pulso_collect_consecutive_failures{olt=\"OLT-2\"} 1"));
        assert!(text.contains("pulso_send_failures_total 1"));
        assert!(text.contains("pulso_incidents_opened_total 2"));
        assert!(text.contains("pulso_incidents_resolved_total 1"));
        assert!(text.contains("pulso_collection_cycles_total 1"));
    }

    #[test]
    fn render_includes_buffer_depth_with_db() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();
        let m = Metrics::new();
        let text = m.render(Some(&db));
        assert!(text.contains("pulso_buffer_depth 0"));
        assert!(text.contains("pulso_dead_letter_total 0"));
    }

    #[test]
    fn last_ont_count_scaling_input() {
        let m = Metrics::new();
        assert_eq!(m.last_ont_count("OLT-1"), None);
        m.record_olt_failure("OLT-1");
        assert_eq!(m.last_ont_count("OLT-1"), None, "failures alone must not report a count");
        m.record_olt_success("OLT-1", 4096);
        assert_eq!(m.last_ont_count("OLT-1"), Some(4096));
    }

    #[test]
    fn label_escaping() {
        assert_eq!(escape_label("a\"b\\c"), "a\\\"b\\\\c");
    }
}
