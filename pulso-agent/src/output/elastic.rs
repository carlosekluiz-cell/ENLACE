// SPDX-License-Identifier: Apache-2.0
// Elasticsearch NDJSON bulk output for ONT telemetry and fault events
//
// `_bulk` semantics: HTTP 200 does NOT mean success — the response body must
// be parsed for per-item failures ("errors": true). Retryable items (429/503)
// are retried with backoff; non-retryable items (e.g. 400 mapping errors) are
// dead-lettered with a counter. Batches still failing after all attempts are
// returned to the caller in `BulkReport::failed` and, when a retry buffer is
// configured, automatically re-queued into the local SQLite buffer.

use anyhow::{Context, Result};
// bytes 1.x re-export (same crate reqwest consumes) — lets retries clone a
// refcounted handle instead of copying the full body per attempt.
use axum::body::Bytes;
use base64::Engine;
use chrono::Utc;
use std::fmt::Write as _;
use std::sync::atomic::{AtomicU64, Ordering};
use tracing::{debug, warn};

use crate::config::ElasticConfig;
use crate::fault::detector::{FaultEvent, IncidentUpdate};
use crate::predictions::{CustomerDiagnostic, SignalPrediction};
use crate::transport::LocalBuffer;
use crate::vendors::OntData;

/// One action+source pair from an NDJSON bulk body.
#[derive(Debug, Clone)]
pub struct BulkDoc {
    pub action: String,
    pub source: String,
}

/// Outcome of a bulk send. HTTP status alone is never trusted; this reflects
/// per-item results after retries.
#[derive(Debug, Default)]
pub struct BulkReport {
    /// Documents in the original request
    pub attempted: usize,
    /// Documents confirmed indexed
    pub indexed: usize,
    /// Documents rejected with non-retryable errors (mapping errors etc.)
    pub dead_lettered: usize,
    /// Documents that still failed retryably (429/503/transport) after all
    /// attempts. Automatically re-queued when a retry buffer is configured;
    /// otherwise the caller should re-buffer them (see `to_ndjson`).
    pub failed: Vec<BulkDoc>,
    /// How many of `failed` were re-queued into the local retry buffer
    pub requeued: usize,
}

impl BulkReport {
    pub fn fully_indexed(&self) -> bool {
        self.dead_lettered == 0 && self.failed.is_empty()
    }

    fn merge(&mut self, other: BulkReport) {
        self.attempted += other.attempted;
        self.indexed += other.indexed;
        self.dead_lettered += other.dead_lettered;
        self.failed.extend(other.failed);
        self.requeued += other.requeued;
    }
}

/// Rebuild an NDJSON bulk body from action+source pairs.
pub fn docs_to_ndjson(docs: &[BulkDoc]) -> String {
    let mut buf = String::with_capacity(
        docs.iter().map(|d| d.action.len() + d.source.len() + 2).sum(),
    );
    for doc in docs {
        buf.push_str(&doc.action);
        buf.push('\n');
        buf.push_str(&doc.source);
        buf.push('\n');
    }
    buf
}

/// Split an NDJSON bulk body into action+source pairs. All bodies this agent
/// builds use `index` actions, which always carry a source line.
fn split_ndjson(body: &str) -> Vec<BulkDoc> {
    let mut docs = Vec::new();
    let mut lines = body.lines();
    while let Some(action) = lines.next() {
        if action.trim().is_empty() {
            continue;
        }
        if let Some(source) = lines.next() {
            docs.push(BulkDoc {
                action: action.to_string(),
                source: source.to_string(),
            });
        }
    }
    docs
}

/// Item-level statuses worth retrying (transient pressure), per ES docs.
fn is_retryable_status(status: u16) -> bool {
    status == 429 || status == 503
}

fn truncate_for_log(text: &str, max_chars: usize) -> String {
    text.chars().take(max_chars).collect()
}

/// Elasticsearch bulk output — batches ONT telemetry and fault events
/// into NDJSON format and ships them via the _bulk API.
pub struct ElasticOutput {
    client: reqwest::Client,
    url: String,
    index_prefix: String,
    bulk_size: usize,
    auth_header: Option<String>,
    /// Local buffer used to re-queue batches that exhaust their retries.
    retry_buffer: Option<LocalBuffer>,
    /// Total documents dead-lettered (non-retryable rejections) since startup.
    dead_letters: AtomicU64,
    /// Backoff base for retries; shrunk in tests.
    retry_base_delay: std::time::Duration,
}

impl ElasticOutput {
    fn write_json_string(buf: &mut String, value: &str) {
        buf.push_str(&serde_json::to_string(value).unwrap());
    }

    fn write_json_string_field(buf: &mut String, key: &str, value: &str) {
        Self::write_json_string(buf, key);
        buf.push(':');
        Self::write_json_string(buf, value);
    }

    fn write_json_opt_f64_field(buf: &mut String, key: &str, value: Option<f64>) {
        Self::write_json_string(buf, key);
        buf.push(':');
        match value {
            Some(v) => {
                let _ = write!(buf, "{}", v);
            }
            None => buf.push_str("null"),
        }
    }

    fn write_json_opt_u32_field(buf: &mut String, key: &str, value: Option<u32>) {
        Self::write_json_string(buf, key);
        buf.push(':');
        match value {
            Some(v) => {
                let _ = write!(buf, "{}", v);
            }
            None => buf.push_str("null"),
        }
    }

    fn write_json_opt_u64_field(buf: &mut String, key: &str, value: Option<u64>) {
        Self::write_json_string(buf, key);
        buf.push(':');
        match value {
            Some(v) => {
                let _ = write!(buf, "{}", v);
            }
            None => buf.push_str("null"),
        }
    }

    /// Create a new ElasticOutput from configuration.
    /// Builds a reqwest client and resolves authentication (API key or Basic auth).
    pub fn new(config: &ElasticConfig) -> Result<Self> {
        let mut client_builder = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30));
        if !config.verify_tls {
            client_builder = client_builder.danger_accept_invalid_certs(true);
        }
        let client = client_builder
            .build()
            .context("Failed to build Elasticsearch HTTP client")?;

        let auth_header = if let Some(ref api_key) = config.api_key {
            Some(format!("ApiKey {}", api_key))
        } else if let (Some(ref user), Some(ref pass)) = (&config.username, &config.password) {
            let encoded = base64::engine::general_purpose::STANDARD
                .encode(format!("{}:{}", user, pass));
            Some(format!("Basic {}", encoded))
        } else {
            None
        };

        Ok(Self {
            client,
            url: config.url.trim_end_matches('/').to_string(),
            index_prefix: config.index_prefix.clone(),
            bulk_size: config.bulk_size,
            auth_header,
            retry_buffer: None,
            dead_letters: AtomicU64::new(0),
            retry_base_delay: std::time::Duration::from_millis(500),
        })
    }

    /// Configure the local buffer into which batches that exhaust their
    /// retries are re-queued (drained by `flush_retry_buffer`).
    pub fn set_retry_buffer(&mut self, db: LocalBuffer) {
        self.retry_buffer = Some(db);
    }

    /// Total documents rejected with non-retryable errors since startup.
    pub fn dead_letter_count(&self) -> u64 {
        self.dead_letters.load(Ordering::Relaxed)
    }

    /// Build NDJSON bulk body for ONT telemetry data.
    /// Each ONT produces two lines: an action line and a document line.
    /// Index pattern: `{prefix}-ont-{YYYY.MM.DD}`
    pub fn build_ont_bulk(
        &self,
        agent_id: &str,
        olt_name: &str,
        vendor: &str,
        model: &str,
        onts: &[OntData],
    ) -> String {
        if onts.is_empty() {
            return String::new();
        }

        let now = Utc::now();
        let date_suffix = now.format("%Y.%m.%d").to_string();
        let index = format!("{}-ont-{}", self.index_prefix, date_suffix);
        let timestamp = now.to_rfc3339();

        let mut buf = String::with_capacity(onts.len() * 512);

        for ont in onts {
            // Action line
            let action = serde_json::json!({
                "index": { "_index": &index }
            });
            buf.push_str(&action.to_string());
            buf.push('\n');

            // Document line
            let doc = serde_json::json!({
                "@timestamp": &timestamp,
                "agent_id": agent_id,
                "olt": {
                    "name": olt_name,
                    "vendor": vendor,
                    "model": model
                },
                "ont": {
                    "serial": &ont.serial_number,
                    "status": ont.status.to_string(),
                    "rx_power_dbm": ont.rx_power_dbm,
                    "tx_power_dbm": ont.tx_power_dbm,
                    "distance_m": ont.distance_meters,
                    "pon_port": &ont.pon_port,
                    "uptime_seconds": ont.uptime_seconds
                }
            });
            buf.push_str(&doc.to_string());
            buf.push('\n');
        }

        buf
    }

    /// Build NDJSON bulk body with Adtran-specific extended schema.
    /// Index pattern: `{prefix}-adtran-{YYYY.MM.DD}` (same configured
    /// index_prefix as every other write path)
    /// Includes: ONT-side power, temperature, voltage, bias current,
    /// degradation predictions, and customer diagnostics.
    pub fn build_adtran_bulk(
        &self,
        agent_id: &str,
        olt_name: &str,
        model: &str,
        onts: &[OntData],
        degradation: &[SignalPrediction],
        diagnostics: &[CustomerDiagnostic],
    ) -> String {
        if onts.is_empty() {
            return String::new();
        }

        let now = Utc::now();
        let date_suffix = now.format("%Y.%m.%d").to_string();
        let index = format!("{}-adtran-{}", self.index_prefix, date_suffix);
        let timestamp = now.to_rfc3339();
        let action_line = format!("{{\"index\":{{\"_index\":\"{}\"}}}}\n", index);
        let timestamp_json = serde_json::to_string(&timestamp).unwrap();
        let agent_id_json = serde_json::to_string(agent_id).unwrap();
        let olt_name_json = serde_json::to_string(olt_name).unwrap();
        let model_json = serde_json::to_string(model).unwrap();

        // Build lookup maps for degradation and diagnostics by serial
        let deg_map: std::collections::HashMap<&str, &SignalPrediction> = degradation
            .iter()
            .map(|d| (d.serial_number.as_str(), d))
            .collect();

        let diag_map: std::collections::HashMap<&str, Vec<&CustomerDiagnostic>> = {
            let mut m: std::collections::HashMap<&str, Vec<&CustomerDiagnostic>> =
                std::collections::HashMap::new();
            for d in diagnostics {
                m.entry(d.serial_number.as_str()).or_default().push(d);
            }
                m
        };

        let mut buf = String::with_capacity(onts.len() * 1024);

        for ont in onts {
            buf.push_str(&action_line);
            buf.push('{');
            buf.push_str("\"@timestamp\":");
            buf.push_str(&timestamp_json);
            buf.push_str(",\"agent_id\":");
            buf.push_str(&agent_id_json);
            buf.push_str(",\"olt\":{\"name\":");
            buf.push_str(&olt_name_json);
            buf.push_str(",\"vendor\":\"adtran\",\"model\":");
            buf.push_str(&model_json);
            buf.push_str("},\"ont\":{");

            Self::write_json_string_field(&mut buf, "serial", &ont.serial_number);
            buf.push(',');
            Self::write_json_string_field(&mut buf, "status", &ont.status.to_string());
            buf.push(',');
            Self::write_json_opt_f64_field(&mut buf, "olt_rx_power_dbm", ont.rx_power_dbm);
            buf.push(',');
            Self::write_json_opt_f64_field(&mut buf, "tx_power_dbm", ont.tx_power_dbm);
            buf.push(',');
            Self::write_json_opt_u32_field(&mut buf, "distance_m", ont.distance_meters);
            buf.push(',');
            Self::write_json_string_field(&mut buf, "pon_port", &ont.pon_port);
            buf.push(',');
            Self::write_json_opt_u64_field(&mut buf, "uptime_seconds", ont.uptime_seconds);
            buf.push_str(",\"extended\":");

            if let Some(ext) = &ont.extended {
                buf.push('{');
                Self::write_json_opt_f64_field(&mut buf, "ont_rx_power_dbm", ext.ont_rx_power_dbm);
                buf.push(',');
                Self::write_json_opt_f64_field(&mut buf, "temperature_c", ext.ont_temperature_c);
                buf.push(',');
                Self::write_json_opt_f64_field(&mut buf, "voltage_v", ext.ont_voltage_v);
                buf.push(',');
                Self::write_json_opt_f64_field(&mut buf, "bias_current_ma", ext.ont_bias_current_ma);
                buf.push('}');
            } else {
                buf.push_str("null");
            }

            buf.push_str(",\"degradation\":");
            if let Some(d) = deg_map.get(ont.serial_number.as_str()) {
                buf.push('{');
                Self::write_json_opt_f64_field(&mut buf, "rate_dbm_per_day", Some(d.degradation_rate_per_day));
                buf.push(',');
                Self::write_json_string_field(&mut buf, "severity", &d.severity.to_string());
                buf.push(',');
                Self::write_json_string_field(&mut buf, "metric_source", &d.metric_source);
                buf.push(',');
                Self::write_json_string(&mut buf, "days_to_failure");
                buf.push(':');
                match d.days_to_failure {
                    Some(days) => {
                        let _ = write!(buf, "{}", days);
                    }
                    None => buf.push_str("null"),
                }
                buf.push(',');
                Self::write_json_opt_f64_field(&mut buf, "confidence", Some(d.confidence as f64));
                buf.push('}');
            } else {
                buf.push_str("null");
            }

            buf.push_str(",\"diagnostics\":[");
            if let Some(diags) = diag_map.get(ont.serial_number.as_str()) {
                for (idx, d) in diags.iter().enumerate() {
                    if idx > 0 {
                        buf.push(',');
                    }
                    buf.push('{');
                    Self::write_json_string_field(&mut buf, "issue", &d.issue.to_string());
                    buf.push(',');
                    Self::write_json_string_field(
                        &mut buf,
                        "severity",
                        &format!("{:?}", d.severity).to_lowercase(),
                    );
                    buf.push(',');
                    Self::write_json_string_field(&mut buf, "message", &d.message);
                    buf.push(',');
                    Self::write_json_string_field(&mut buf, "action", &d.recommended_action);
                    buf.push('}');
                }
            }
            buf.push_str("]}}");
            buf.push('\n');
        }

        buf
    }

    /// Convert a FaultEvent into a JSON document string for Elasticsearch.
    /// Legacy open-only path — `incident_to_doc` carries the full lifecycle.
    pub fn fault_event_to_doc(event: &FaultEvent) -> String {
        let doc = serde_json::json!({
            "@timestamp": event.timestamp.to_rfc3339(),
            "event_action": "open",
            "type": event.fault_type.to_string(),
            "severity": &event.severity,
            "pon_port": &event.pon_port,
            "olt_id": &event.olt_id,
            "affected_onts_count": event.affected_onts.len(),
            "dying_gasp_count": event.affected_onts.iter().filter(|o| o.had_dying_gasp).count(),
            "detection_latency_seconds": event.detection_latency_seconds
        });
        doc.to_string()
    }

    /// Convert an incident lifecycle update (open OR resolve) into a fault
    /// document. `event_action` + `incident_id` let dashboards pair resolves
    /// with their opens. Classification evidence (gasp ratio, onset,
    /// confidence, summary) and the cross-OLT `area_power_suspected` flag
    /// ride along so dashboards can show WHY the fault_type was called,
    /// never just the label.
    pub fn incident_to_doc(update: &IncidentUpdate) -> String {
        let event = &update.event;
        let doc = serde_json::json!({
            "@timestamp": event.timestamp.to_rfc3339(),
            "event_action": update.action.to_string(),
            "incident_id": &update.incident_id,
            "scope": update.scope,
            "opened_at": update.opened_at.to_rfc3339(),
            "resolved_at": update.resolved_at.map(|t| t.to_rfc3339()),
            "ports": &update.ports,
            "type": event.fault_type.to_string(),
            "severity": &event.severity,
            "pon_port": &event.pon_port,
            "olt_id": &event.olt_id,
            "affected_onts_count": event.affected_onts.len(),
            "dying_gasp_count": event.affected_onts.iter().filter(|o| o.had_dying_gasp).count(),
            "dying_gasp_ratio": update.classification.dying_gasp_ratio,
            "onset": update.classification.onset.to_string(),
            "classification_confidence": update.classification.confidence.to_string(),
            "classification_summary": &update.classification.summary,
            "area_power_suspected": update.area_power_suspected,
            "detection_latency_seconds": event.detection_latency_seconds
        });
        doc.to_string()
    }

    /// Send a raw NDJSON bulk body to Elasticsearch.
    /// See module docs: parses the `_bulk` response, retries retryable items,
    /// dead-letters non-retryable ones, re-queues exhausted batches.
    pub async fn send_bulk(&self, body: &str) -> Result<BulkReport> {
        if body.is_empty() {
            return Ok(BulkReport::default());
        }
        self.send_docs(split_ndjson(body)).await
    }

    async fn send_docs(&self, mut docs: Vec<BulkDoc>) -> Result<BulkReport> {
        let url = format!("{}/_bulk", self.url);
        let mut report = BulkReport {
            attempted: docs.len(),
            ..Default::default()
        };
        if docs.is_empty() {
            return Ok(report);
        }

        // Build the body ONCE; Bytes clones are refcounted, so retries of the
        // same doc set never copy the payload.
        let mut body = Bytes::from(docs_to_ndjson(&docs));

        for attempt in 0..3u32 {
            if attempt > 0 {
                let delay = self.retry_base_delay * 2u32.pow(attempt - 1);
                tokio::time::sleep(delay).await;
                debug!(attempt, docs = docs.len(), "Retrying Elasticsearch bulk send");
            }

            let mut req = self
                .client
                .post(&url)
                .header("Content-Type", "application/x-ndjson")
                .body(body.clone());
            if let Some(ref auth) = self.auth_header {
                req = req.header("Authorization", auth);
            }

            let resp = match req.send().await {
                Ok(resp) => resp,
                Err(e) => {
                    warn!(error = %e, attempt, "Elasticsearch bulk send failed (transport)");
                    continue;
                }
            };

            let status = resp.status();
            if status.as_u16() == 429 || status.is_server_error() {
                let text = resp.text().await.unwrap_or_default();
                warn!(
                    status = %status,
                    attempt,
                    body = %truncate_for_log(&text, 500),
                    "Elasticsearch bulk send returned retryable error"
                );
                continue;
            }
            if !status.is_success() {
                // Non-retryable HTTP error (400 malformed, 401/403 auth…):
                // retrying the identical request cannot succeed.
                let text = resp.text().await.unwrap_or_default();
                self.dead_letters
                    .fetch_add(docs.len() as u64, Ordering::Relaxed);
                anyhow::bail!(
                    "Elasticsearch returned non-retryable HTTP {}: {}",
                    status,
                    truncate_for_log(&text, 500)
                );
            }

            // HTTP 2xx — but _bulk can still contain per-item failures.
            let resp_json: serde_json::Value = match resp.json().await {
                Ok(v) => v,
                Err(e) => {
                    warn!(error = %e, attempt, "Failed to parse Elasticsearch bulk response");
                    continue;
                }
            };

            if !resp_json["errors"].as_bool().unwrap_or(false) {
                report.indexed += docs.len();
                debug!(indexed = docs.len(), "Elasticsearch bulk send succeeded");
                return Ok(report);
            }

            // Partition per-item results: indexed / retryable / dead-letter.
            let empty = Vec::new();
            let items = resp_json["items"].as_array().unwrap_or(&empty);
            let mut retryable: Vec<BulkDoc> = Vec::new();
            let mut dead_reasons: Vec<String> = Vec::new();
            let mut dead_this_attempt = 0usize;

            for (i, doc) in docs.iter().enumerate() {
                let item = items
                    .get(i)
                    .and_then(|it| it.as_object())
                    .and_then(|obj| obj.values().next());
                let item_status = item
                    .and_then(|v| v["status"].as_u64())
                    .unwrap_or(0) as u16;

                if (200..300).contains(&(item_status as u32)) {
                    report.indexed += 1;
                } else if is_retryable_status(item_status) {
                    retryable.push(doc.clone());
                } else {
                    dead_this_attempt += 1;
                    if dead_reasons.len() < 3 {
                        let err = item.map(|v| &v["error"]);
                        dead_reasons.push(format!(
                            "status={} type={} reason={}",
                            item_status,
                            err.and_then(|e| e["type"].as_str()).unwrap_or("unknown"),
                            err.and_then(|e| e["reason"].as_str()).unwrap_or("unknown"),
                        ));
                    }
                }
            }

            if dead_this_attempt > 0 {
                report.dead_lettered += dead_this_attempt;
                let total = self
                    .dead_letters
                    .fetch_add(dead_this_attempt as u64, Ordering::Relaxed)
                    + dead_this_attempt as u64;
                warn!(
                    rejected = dead_this_attempt,
                    total_dead_lettered = total,
                    examples = ?dead_reasons,
                    "Elasticsearch rejected documents with non-retryable errors (dead-lettered)"
                );
            }

            if retryable.is_empty() {
                return Ok(report);
            }
            warn!(
                retryable = retryable.len(),
                attempt,
                "Elasticsearch bulk had retryable item failures (429/503)"
            );
            docs = retryable;
            body = Bytes::from(docs_to_ndjson(&docs));
        }

        // Retries exhausted — surface the remaining docs and re-queue them
        // into the local buffer when configured, instead of dropping.
        report.failed = docs;
        if let Some(ref db) = self.retry_buffer {
            let ndjson = docs_to_ndjson(&report.failed);
            match db.store_elastic_retry(&ndjson) {
                Ok(()) => report.requeued = report.failed.len(),
                Err(e) => warn!(error = %e, "Failed to re-queue Elasticsearch batch locally"),
            }
        }
        warn!(
            failed = report.failed.len(),
            requeued = report.requeued,
            "Elasticsearch bulk send exhausted retries"
        );
        Ok(report)
    }

    /// Drain re-queued bulk batches from the local buffer (best-effort; rows
    /// are taken before sending so a still-failing batch cycles back through
    /// `send_docs`' re-queue path rather than duplicating).
    pub async fn flush_retry_buffer(&self, db: &LocalBuffer) -> Result<usize> {
        let rows = db.get_elastic_retries(50)?;
        if rows.is_empty() {
            return Ok(0);
        }
        debug!(batches = rows.len(), "Flushing re-queued Elasticsearch batches");
        let mut indexed = 0usize;
        for (id, ndjson) in rows {
            db.delete_elastic_retry(id)?;
            let report = self.send_bulk(&ndjson).await?;
            indexed += report.indexed;
        }
        Ok(indexed)
    }

    /// Send ONT telemetry to Elasticsearch, chunked by bulk_size.
    pub async fn send_onts(
        &self,
        agent_id: &str,
        olt_name: &str,
        vendor: &str,
        model: &str,
        onts: &[OntData],
    ) -> Result<BulkReport> {
        let mut total = BulkReport::default();
        for chunk in onts.chunks(self.bulk_size) {
            let body = self.build_ont_bulk(agent_id, olt_name, vendor, model, chunk);
            total.merge(self.send_bulk(&body).await?);
        }
        Ok(total)
    }

    fn faults_index(&self) -> String {
        format!(
            "{}-faults-{}",
            self.index_prefix,
            Utc::now().format("%Y.%m.%d")
        )
    }

    /// Send a fault event (open-only legacy path) to Elasticsearch.
    pub async fn send_fault(&self, event: &FaultEvent) -> Result<BulkReport> {
        let action = serde_json::json!({ "index": { "_index": self.faults_index() } });
        let doc = Self::fault_event_to_doc(event);
        self.send_bulk(&format!("{}\n{}\n", action, doc)).await
    }

    /// Send an incident lifecycle update (open OR resolve) to Elasticsearch.
    pub async fn send_incident(&self, update: &IncidentUpdate) -> Result<BulkReport> {
        let action = serde_json::json!({ "index": { "_index": self.faults_index() } });
        let doc = Self::incident_to_doc(update);
        self.send_bulk(&format!("{}\n{}\n", action, doc)).await
    }

    /// Idempotent, best-effort startup setup: an ILM retention policy plus
    /// index templates mapping the fields this agent writes (dates as `date`,
    /// optical powers as `float`, serials/ids as `keyword`). Failures are
    /// loud warnings, never fatal — data still indexes with dynamic mappings.
    pub async fn ensure_index_setup(&self) {
        let policy_name = format!("{}-retention", self.index_prefix);
        let policy = serde_json::json!({
            "policy": {
                "phases": {
                    "hot": {
                        "actions": {
                            "rollover": { "max_age": "30d", "max_primary_shard_size": "50gb" }
                        }
                    },
                    "delete": {
                        "min_age": "180d",
                        "actions": { "delete": {} }
                    }
                }
            }
        });

        let ont_template = serde_json::json!({
            "index_patterns": [format!("{}-ont-*", self.index_prefix)],
            "priority": 100,
            "template": {
                "settings": { "index.lifecycle.name": policy_name },
                "mappings": {
                    "properties": {
                        "@timestamp": { "type": "date" },
                        "agent_id": { "type": "keyword" },
                        "olt": { "properties": {
                            "name": { "type": "keyword" },
                            "vendor": { "type": "keyword" },
                            "model": { "type": "keyword" }
                        }},
                        "ont": { "properties": {
                            "serial": { "type": "keyword" },
                            "status": { "type": "keyword" },
                            "pon_port": { "type": "keyword" },
                            "rx_power_dbm": { "type": "float" },
                            "tx_power_dbm": { "type": "float" },
                            "distance_m": { "type": "integer" },
                            "uptime_seconds": { "type": "long" }
                        }}
                    }
                }
            }
        });

        let faults_template = serde_json::json!({
            "index_patterns": [format!("{}-faults-*", self.index_prefix)],
            "priority": 100,
            "template": {
                "settings": { "index.lifecycle.name": policy_name },
                "mappings": {
                    "properties": {
                        "@timestamp": { "type": "date" },
                        "event_action": { "type": "keyword" },
                        "incident_id": { "type": "keyword" },
                        "scope": { "type": "keyword" },
                        "opened_at": { "type": "date" },
                        "resolved_at": { "type": "date" },
                        "ports": { "type": "keyword" },
                        "type": { "type": "keyword" },
                        "severity": { "type": "keyword" },
                        "pon_port": { "type": "keyword" },
                        "olt_id": { "type": "keyword" },
                        "affected_onts_count": { "type": "integer" },
                        "dying_gasp_count": { "type": "integer" },
                        "dying_gasp_ratio": { "type": "float" },
                        "onset": { "type": "keyword" },
                        "classification_confidence": { "type": "keyword" },
                        "classification_summary": { "type": "text" },
                        "area_power_suspected": { "type": "boolean" },
                        "detection_latency_seconds": { "type": "long" }
                    }
                }
            }
        });

        let adtran_template = serde_json::json!({
            "index_patterns": [format!("{}-adtran-*", self.index_prefix)],
            "priority": 100,
            "template": {
                "settings": { "index.lifecycle.name": policy_name },
                "mappings": {
                    "properties": {
                        "@timestamp": { "type": "date" },
                        "agent_id": { "type": "keyword" },
                        "olt": { "properties": {
                            "name": { "type": "keyword" },
                            "vendor": { "type": "keyword" },
                            "model": { "type": "keyword" }
                        }},
                        "ont": { "properties": {
                            "serial": { "type": "keyword" },
                            "status": { "type": "keyword" },
                            "pon_port": { "type": "keyword" },
                            "olt_rx_power_dbm": { "type": "float" },
                            "tx_power_dbm": { "type": "float" },
                            "distance_m": { "type": "integer" },
                            "uptime_seconds": { "type": "long" },
                            "extended": { "properties": {
                                "ont_rx_power_dbm": { "type": "float" },
                                "temperature_c": { "type": "float" },
                                "voltage_v": { "type": "float" },
                                "bias_current_ma": { "type": "float" }
                            }},
                            "degradation": { "properties": {
                                "rate_dbm_per_day": { "type": "float" },
                                "severity": { "type": "keyword" },
                                "metric_source": { "type": "keyword" },
                                "days_to_failure": { "type": "integer" },
                                "confidence": { "type": "float" }
                            }},
                            "diagnostics": { "properties": {
                                "issue": { "type": "keyword" },
                                "severity": { "type": "keyword" },
                                "message": { "type": "text" },
                                "action": { "type": "text" }
                            }}
                        }}
                    }
                }
            }
        });

        let mut ok = true;
        ok &= self
            .put_json(&format!("_ilm/policy/{}", policy_name), &policy, "ILM policy")
            .await;
        ok &= self
            .put_json(
                &format!("_index_template/{}-ont", self.index_prefix),
                &ont_template,
                "ONT index template",
            )
            .await;
        ok &= self
            .put_json(
                &format!("_index_template/{}-faults", self.index_prefix),
                &faults_template,
                "faults index template",
            )
            .await;
        ok &= self
            .put_json(
                &format!("_index_template/{}-adtran", self.index_prefix),
                &adtran_template,
                "Adtran index template",
            )
            .await;

        if ok {
            debug!("Elasticsearch index templates and ILM policy ensured");
        } else {
            warn!(
                "ELASTICSEARCH INDEX SETUP INCOMPLETE — telemetry will index with dynamic \
                 mappings and no retention policy; dashboards and disk usage may misbehave"
            );
        }
    }

    async fn put_json(&self, path: &str, body: &serde_json::Value, what: &str) -> bool {
        let url = format!("{}/{}", self.url, path);
        let mut req = self.client.put(&url).json(body);
        if let Some(ref auth) = self.auth_header {
            req = req.header("Authorization", auth);
        }
        match req.send().await {
            Ok(resp) if resp.status().is_success() => {
                debug!(what, "Elasticsearch setup PUT succeeded");
                true
            }
            Ok(resp) => {
                let status = resp.status();
                let text = resp.text().await.unwrap_or_default();
                warn!(
                    what,
                    status = %status,
                    body = %truncate_for_log(&text, 300),
                    "Elasticsearch setup PUT failed"
                );
                false
            }
            Err(e) => {
                warn!(what, error = %e, "Elasticsearch setup PUT failed (transport)");
                false
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fault::detector::{AffectedOnt, IncidentAction, IncidentScope};
    use crate::predictions::{
        CustomerDiagnostic, DiagnosticIssue, DiagnosticSeverity, DegradationSeverity,
        SignalPrediction,
    };
    use crate::vendors::{ExtendedOntMetrics, OntStatus};
    use std::collections::VecDeque;
    use std::sync::{Arc, Mutex};

    fn make_elastic_config() -> ElasticConfig {
        ElasticConfig {
            enabled: true,
            url: "http://localhost:9200".into(),
            index_prefix: "pulso".into(),
            bulk_size: 500,
            username: None,
            password: None,
            api_key: None,
            verify_tls: false,
        }
    }

    fn make_ont(serial: &str, rx_power: f64) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: "0/1/0".into(),
            ont_index: 1,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: Some(86400),
            rx_power_dbm: Some(rx_power),
            tx_power_dbm: Some(2.5),
            distance_meters: Some(1200),
            vendor_id: None,
            equipment_id: None,
            firmware_version: None,
            in_octets: None,
            out_octets: None,
            eth_speed_mbps: None,
            extended: None,
            ..Default::default()
        }
    }

    fn make_adtran_ont(serial: &str, olt_rx: f64, ont_rx: f64, temp: f64) -> OntData {
        OntData {
            serial_number: serial.into(),
            pon_port: "CTP-0/1".into(),
            ont_index: 1,
            status: OntStatus::Online,
            last_down_cause: None,
            uptime_seconds: Some(86400),
            rx_power_dbm: Some(olt_rx),
            tx_power_dbm: Some(2.5),
            distance_meters: Some(2060),
            vendor_id: Some("ADTN".into()),
            equipment_id: None,
            firmware_version: None,
            in_octets: None,
            out_octets: None,
            eth_speed_mbps: None,
            extended: Some(ExtendedOntMetrics {
                ont_rx_power_dbm: Some(ont_rx),
                ont_temperature_c: Some(temp),
                ont_voltage_v: Some(3.3),
                ont_bias_current_ma: Some(15.0),
            }),
            ..Default::default()
        }
    }

    // --- Mock Elasticsearch server -----------------------------------------

    struct MockEs {
        /// Scripted (status, body) responses, popped per request; when empty,
        /// answers 200 with an all-success bulk response.
        responses: Mutex<VecDeque<(u16, String)>>,
        /// Raw request bodies received, in order.
        requests: Mutex<Vec<String>>,
    }

    async fn mock_handler(
        axum::extract::State(state): axum::extract::State<Arc<MockEs>>,
        body: String,
    ) -> (axum::http::StatusCode, String) {
        state.requests.lock().unwrap().push(body);
        let (status, resp) = state
            .responses
            .lock()
            .unwrap()
            .pop_front()
            .unwrap_or((200, r#"{"errors":false,"items":[]}"#.to_string()));
        (axum::http::StatusCode::from_u16(status).unwrap(), resp)
    }

    /// Spawn a mock ES answering POST /_bulk (and PUT setup paths) with the
    /// scripted responses. Returns (base_url, state).
    async fn spawn_mock_es(responses: Vec<(u16, &str)>) -> (String, Arc<MockEs>) {
        let state = Arc::new(MockEs {
            responses: Mutex::new(
                responses.into_iter().map(|(s, b)| (s, b.to_string())).collect(),
            ),
            requests: Mutex::new(Vec::new()),
        });
        let app = axum::Router::new()
            .route("/_bulk", axum::routing::post(mock_handler))
            .with_state(state.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        (format!("http://{}", addr), state)
    }

    fn make_output(url: &str) -> ElasticOutput {
        let mut config = make_elastic_config();
        config.url = url.into();
        let mut output = ElasticOutput::new(&config).unwrap();
        output.retry_base_delay = std::time::Duration::from_millis(5); // fast tests
        output
    }

    fn three_doc_body() -> String {
        let mut body = String::new();
        for serial in ["S-OK", "S-RETRY", "S-BAD"] {
            body.push_str("{\"index\":{\"_index\":\"pulso-ont-test\"}}\n");
            body.push_str(&format!("{{\"ont\":{{\"serial\":\"{}\"}}}}\n", serial));
        }
        body
    }

    /// Fixture: HTTP 200 with mixed per-item results — success, 429 (retryable),
    /// 400 mapper_parsing_exception (dead-letter).
    const MIXED_BULK_RESPONSE: &str = r#"{
        "took": 30, "errors": true,
        "items": [
            {"index": {"_index": "pulso-ont-test", "status": 201}},
            {"index": {"_index": "pulso-ont-test", "status": 429,
                "error": {"type": "circuit_breaking_exception", "reason": "too much load"}}},
            {"index": {"_index": "pulso-ont-test", "status": 400,
                "error": {"type": "mapper_parsing_exception", "reason": "failed to parse field"}}}
        ]
    }"#;

    const ALL_OK_ONE_ITEM: &str =
        r#"{"took": 5, "errors": false, "items": [{"index": {"status": 201}}]}"#;

    #[tokio::test]
    async fn test_bulk_partial_failure_retries_429_dead_letters_400() {
        // HTTP 200 must NOT mean success: the 429 item is retried (and then
        // succeeds), the 400 mapping error is dead-lettered, never retried.
        let (url, state) = spawn_mock_es(vec![
            (200, MIXED_BULK_RESPONSE),
            (200, ALL_OK_ONE_ITEM),
        ])
        .await;
        let output = make_output(&url);

        let report = output.send_bulk(&three_doc_body()).await.unwrap();

        assert_eq!(report.attempted, 3);
        assert_eq!(report.indexed, 2, "S-OK on first attempt + S-RETRY on retry");
        assert_eq!(report.dead_lettered, 1, "400 mapping error dead-lettered");
        assert!(report.failed.is_empty());
        assert_eq!(output.dead_letter_count(), 1);

        let requests = state.requests.lock().unwrap();
        assert_eq!(requests.len(), 2, "one original send + one retry");
        // The retry body must contain ONLY the 429 doc
        assert!(requests[1].contains("S-RETRY"));
        assert!(!requests[1].contains("S-OK"));
        assert!(!requests[1].contains("S-BAD"));
    }

    #[tokio::test]
    async fn test_no_retry_on_http_400() {
        // A whole-request 400 (malformed) must NOT be retried identically.
        let (url, state) = spawn_mock_es(vec![
            (400, r#"{"error":{"type":"parse_exception","reason":"bad ndjson"}}"#),
        ])
        .await;
        let output = make_output(&url);

        let result = output.send_bulk(&three_doc_body()).await;
        assert!(result.is_err(), "HTTP 400 must be a hard error");
        assert_eq!(
            state.requests.lock().unwrap().len(),
            1,
            "400 must not be retried"
        );
        assert_eq!(output.dead_letter_count(), 3);
    }

    #[tokio::test]
    async fn test_http_429_retries_whole_body() {
        let (url, state) = spawn_mock_es(vec![
            (429, r#"{"error":"too many requests"}"#),
            (200, r#"{"errors":false,"items":[]}"#),
        ])
        .await;
        let output = make_output(&url);

        let report = output.send_bulk(&three_doc_body()).await.unwrap();
        assert_eq!(report.indexed, 3);
        assert!(report.fully_indexed());
        assert_eq!(state.requests.lock().unwrap().len(), 2);
    }

    #[tokio::test]
    async fn test_exhausted_retries_requeue_into_buffer() {
        // Every attempt keeps 429ing one item → after 3 attempts the doc is
        // returned as failed AND re-queued into the local buffer, not dropped.
        let per_item_429 = r#"{"errors": true, "items": [
            {"index": {"status": 429, "error": {"type": "es_rejected_execution_exception", "reason": "queue full"}}}
        ]}"#;
        let (url, state) = spawn_mock_es(vec![
            (200, per_item_429),
            (200, per_item_429),
            (200, per_item_429),
        ])
        .await;
        let mut output = make_output(&url);

        let dir = tempfile::tempdir().unwrap();
        let db = crate::transport::LocalBuffer::open(dir.path()).unwrap();
        output.set_retry_buffer(db.clone());

        let body = "{\"index\":{\"_index\":\"pulso-ont-test\"}}\n{\"ont\":{\"serial\":\"S-STUCK\"}}\n";
        let report = output.send_bulk(body).await.unwrap();

        assert_eq!(report.indexed, 0);
        assert_eq!(report.failed.len(), 1);
        assert_eq!(report.requeued, 1, "failed batch must be re-queued locally");
        assert_eq!(state.requests.lock().unwrap().len(), 3);

        let queued = db.get_elastic_retries(10).unwrap();
        assert_eq!(queued.len(), 1);
        assert!(queued[0].1.contains("S-STUCK"));

        // Once ES recovers, flush_retry_buffer drains the queue (mock now
        // answers all-success by default).
        let indexed = output.flush_retry_buffer(&db).await.unwrap();
        assert_eq!(indexed, 1);
        assert!(db.get_elastic_retries(10).unwrap().is_empty());
    }

    #[test]
    fn test_split_and_rebuild_ndjson_pairs() {
        let body = three_doc_body();
        let docs = split_ndjson(&body);
        assert_eq!(docs.len(), 3);
        assert_eq!(docs_to_ndjson(&docs), body);
    }

    #[test]
    fn test_bulk_ndjson_format() {
        let config = make_elastic_config();
        let output = ElasticOutput::new(&config).unwrap();

        let onts = vec![
            make_ont("HWTC-AABB0001", -21.5),
            make_ont("HWTC-AABB0002", -25.3),
        ];

        let body = output.build_ont_bulk("agent-01", "OLT-Centro", "huawei", "MA5800", &onts);

        let lines: Vec<&str> = body.lines().collect();
        // 2 ONTs = 4 lines (action + doc per ONT)
        assert_eq!(lines.len(), 4, "Expected 4 NDJSON lines for 2 ONTs");

        // Verify index name starts with the configured prefix
        let action: serde_json::Value = serde_json::from_str(lines[0]).unwrap();
        let index_name = action["index"]["_index"].as_str().unwrap();
        assert!(
            index_name.starts_with("pulso-ont-"),
            "Index should start with prefix: {}",
            index_name
        );

        // Verify first ONT document has serial and rx_power_dbm
        let doc: serde_json::Value = serde_json::from_str(lines[1]).unwrap();
        assert_eq!(doc["ont"]["serial"], "HWTC-AABB0001");
        assert_eq!(doc["ont"]["rx_power_dbm"], -21.5);

        // Verify second ONT document
        let doc2: serde_json::Value = serde_json::from_str(lines[3]).unwrap();
        assert_eq!(doc2["ont"]["serial"], "HWTC-AABB0002");
        assert_eq!(doc2["ont"]["rx_power_dbm"], -25.3);
    }

    #[test]
    fn test_adtran_bulk_format() {
        let config = make_elastic_config();
        let output = ElasticOutput::new(&config).unwrap();

        let onts = vec![
            make_adtran_ont("ADTN153201C4", -22.1, -25.0, 45.5),
            make_adtran_ont("ADTN153201C5", -23.5, -26.2, 42.0),
        ];

        let degradation = vec![SignalPrediction {
            serial_number: "ADTN153201C4".into(),
            pon_port: "CTP-0/1".into(),
            current_rx_dbm: -25.0,
            metric_source: "ont_rx".into(),
            degradation_rate_per_day: -0.04,
            severity: DegradationSeverity::Warning,
            days_to_failure: Some(50),
            confidence: 0.85,
            recent_step: None,
            message: "WARNING: ADTN153201C4 degrading".into(),
        }];

        let diagnostics = vec![CustomerDiagnostic {
            serial_number: "ADTN153201C5".into(),
            pon_port: "CTP-0/1".into(),
            issue: DiagnosticIssue::DegradedSignal,
            severity: DiagnosticSeverity::Warning,
            message: "ONT signal at -26.2 dBm".into(),
            recommended_action: "Clean connectors".into(),
        }];

        let body = output.build_adtran_bulk(
            "agent-01",
            "OLT-South",
            "SDX 6330-48",
            &onts,
            &degradation,
            &diagnostics,
        );

        let lines: Vec<&str> = body.lines().collect();
        assert_eq!(lines.len(), 4, "Expected 4 NDJSON lines for 2 ONTs");

        // Check index pattern is {configured prefix}-adtran-{date} — the
        // Adtran path must honour index_prefix like every other write path
        let action: serde_json::Value = serde_json::from_str(lines[0]).unwrap();
        let index_name = action["index"]["_index"].as_str().unwrap();
        assert!(
            index_name.starts_with("pulso-adtran-"),
            "Adtran index should start with configured prefix: {}",
            index_name
        );

        // Check first ONT (ADTN153201C4) has extended metrics + degradation
        let doc1: serde_json::Value = serde_json::from_str(lines[1]).unwrap();
        assert_eq!(doc1["ont"]["serial"], "ADTN153201C4");
        assert_eq!(doc1["olt"]["vendor"], "adtran");
        assert_eq!(doc1["ont"]["olt_rx_power_dbm"], -22.1);

        // Extended metrics
        let ext = &doc1["ont"]["extended"];
        assert_eq!(ext["ont_rx_power_dbm"], -25.0);
        assert_eq!(ext["temperature_c"], 45.5);
        assert_eq!(ext["voltage_v"], 3.3);
        assert_eq!(ext["bias_current_ma"], 15.0);

        // Degradation block
        let deg = &doc1["ont"]["degradation"];
        assert_eq!(deg["rate_dbm_per_day"], -0.04);
        assert_eq!(deg["severity"], "warning");
        assert_eq!(deg["metric_source"], "ont_rx");
        assert_eq!(deg["days_to_failure"], 50);

        // No diagnostics for first ONT
        assert!(doc1["ont"]["diagnostics"].as_array().unwrap().is_empty());

        // Check second ONT (ADTN153201C5) has diagnostics but no degradation
        let doc2: serde_json::Value = serde_json::from_str(lines[3]).unwrap();
        assert_eq!(doc2["ont"]["serial"], "ADTN153201C5");
        assert!(doc2["ont"]["degradation"].is_null());

        let diags = doc2["ont"]["diagnostics"].as_array().unwrap();
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0]["issue"], "degraded_signal");
        assert_eq!(diags[0]["severity"], "warning");
    }

    fn make_fault_event() -> FaultEvent {
        use crate::fault::detector::FaultType;
        FaultEvent {
            timestamp: Utc::now(),
            pon_port: "0/2/0".into(),
            olt_id: "olt-norte".into(),
            severity: "critical".into(),
            fault_type: FaultType::FibreCut,
            affected_onts: vec![
                AffectedOnt {
                    serial_number: "ONT001".into(),
                    distance_meters: Some(500),
                    last_rx_dbm: Some(-26.0),
                    had_dying_gasp: false,
                },
                AffectedOnt {
                    serial_number: "ONT002".into(),
                    distance_meters: Some(800),
                    last_rx_dbm: Some(-27.5),
                    had_dying_gasp: false,
                },
            ],
            detection_latency_seconds: 15,
        }
    }

    #[test]
    fn test_fault_event_doc() {
        let event = make_fault_event();
        let doc_str = ElasticOutput::fault_event_to_doc(&event);
        let doc: serde_json::Value = serde_json::from_str(&doc_str).unwrap();

        assert_eq!(doc["type"], "fibre_cut");
        assert_eq!(doc["event_action"], "open");
        assert_eq!(doc["severity"], "critical");
        assert_eq!(doc["affected_onts_count"], 2);
        assert_eq!(doc["dying_gasp_count"], 0);
        assert_eq!(doc["pon_port"], "0/2/0");
        assert_eq!(doc["olt_id"], "olt-norte");
        assert_eq!(doc["detection_latency_seconds"], 15);
    }

    #[test]
    fn test_resolve_incident_doc_shape() {
        let opened_at = Utc::now() - chrono::Duration::minutes(42);
        let resolved_at = Utc::now();
        let update = IncidentUpdate {
            action: IncidentAction::Resolve,
            incident_id: "olt-norte:0/2/0:1751400000".into(),
            scope: IncidentScope::Port,
            opened_at,
            resolved_at: Some(resolved_at),
            ports: vec!["0/2/0".into()],
            classification: Default::default(),
            area_power_suspected: false,
            event: make_fault_event(),
        };

        let doc: serde_json::Value =
            serde_json::from_str(&ElasticOutput::incident_to_doc(&update)).unwrap();

        assert_eq!(doc["event_action"], "resolve");
        assert_eq!(doc["incident_id"], "olt-norte:0/2/0:1751400000");
        assert_eq!(doc["scope"], "port");
        assert_eq!(doc["opened_at"], opened_at.to_rfc3339());
        assert_eq!(doc["resolved_at"], resolved_at.to_rfc3339());
        assert_eq!(doc["ports"][0], "0/2/0");
        assert_eq!(doc["type"], "fibre_cut");
        assert_eq!(doc["olt_id"], "olt-norte");

        // Open updates carry event_action=open and null resolved_at
        let open = IncidentUpdate {
            action: IncidentAction::Open,
            resolved_at: None,
            ..update
        };
        let doc: serde_json::Value =
            serde_json::from_str(&ElasticOutput::incident_to_doc(&open)).unwrap();
        assert_eq!(doc["event_action"], "open");
        assert!(doc["resolved_at"].is_null());
    }

    #[test]
    fn test_incident_doc_carries_classification_evidence() {
        use crate::fault::detector::{
            ClassificationConfidence, ClassificationEvidence, OnsetPattern,
        };
        let update = IncidentUpdate {
            action: IncidentAction::Open,
            incident_id: "olt-a:0/1/0:1751400000".into(),
            scope: IncidentScope::Port,
            opened_at: Utc::now(),
            resolved_at: None,
            ports: vec!["0/1/0".into()],
            classification: ClassificationEvidence {
                dying_gasp_count: 7,
                hard_offline_count: 1,
                dying_gasp_ratio: 0.875,
                onset: OnsetPattern::Simultaneous,
                onset_spread_seconds: 12,
                confidence: ClassificationConfidence::High,
                summary: "power_outage: 7/8 dying gasps (ratio 0.88)".into(),
            },
            area_power_suspected: true,
            event: make_fault_event(),
        };

        let doc: serde_json::Value =
            serde_json::from_str(&ElasticOutput::incident_to_doc(&update)).unwrap();
        assert_eq!(doc["dying_gasp_ratio"], 0.875);
        assert_eq!(doc["onset"], "simultaneous");
        assert_eq!(doc["classification_confidence"], "high");
        assert_eq!(
            doc["classification_summary"],
            "power_outage: 7/8 dying gasps (ratio 0.88)"
        );
        assert_eq!(doc["area_power_suspected"], true);
    }

    #[tokio::test]
    async fn test_send_incident_targets_faults_index() {
        let (url, state) = spawn_mock_es(vec![]).await;
        let output = make_output(&url);

        let update = IncidentUpdate {
            action: IncidentAction::Resolve,
            incident_id: "olt-1:0/1/0:1751400000".into(),
            scope: IncidentScope::Port,
            opened_at: Utc::now(),
            resolved_at: Some(Utc::now()),
            ports: vec!["0/1/0".into()],
            classification: Default::default(),
            area_power_suspected: false,
            event: make_fault_event(),
        };

        let report = output.send_incident(&update).await.unwrap();
        assert!(report.fully_indexed());

        let requests = state.requests.lock().unwrap();
        assert_eq!(requests.len(), 1);
        assert!(requests[0].contains("pulso-faults-"));
        assert!(requests[0].contains("\"event_action\":\"resolve\""));
        assert!(requests[0].contains("olt-1:0/1/0:1751400000"));
    }

    #[test]
    fn test_empty_onts() {
        let config = make_elastic_config();
        let output = ElasticOutput::new(&config).unwrap();

        let body = output.build_ont_bulk("agent-01", "OLT-Centro", "huawei", "MA5800", &[]);
        assert!(body.is_empty(), "Empty ONT slice should produce empty string");
    }

    #[test]
    fn test_empty_adtran_onts() {
        let config = make_elastic_config();
        let output = ElasticOutput::new(&config).unwrap();

        let body = output.build_adtran_bulk("agent-01", "OLT-South", "SDX 6330-48", &[], &[], &[]);
        assert!(body.is_empty(), "Empty ONT slice should produce empty string");
    }
}
