// SPDX-License-Identifier: Apache-2.0
// Elasticsearch NDJSON bulk output for ONT telemetry and fault events

use anyhow::{Context, Result};
use base64::Engine;
use chrono::Utc;
use std::fmt::Write as _;
use tracing::{debug, warn};

use crate::config::ElasticConfig;
use crate::fault::detector::FaultEvent;
use crate::predictions::{CustomerDiagnostic, SignalPrediction};
use crate::vendors::OntData;

/// Elasticsearch bulk output — batches ONT telemetry and fault events
/// into NDJSON format and ships them via the _bulk API.
pub struct ElasticOutput {
    client: reqwest::Client,
    url: String,
    index_prefix: String,
    bulk_size: usize,
    auth_header: Option<String>,
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
        })
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
    /// Index pattern: `enlace-adtran-{YYYY.MM.DD}`
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
        let index = format!("enlace-adtran-{}", date_suffix);
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
    pub fn fault_event_to_doc(event: &FaultEvent) -> String {
        let doc = serde_json::json!({
            "@timestamp": event.timestamp.to_rfc3339(),
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

    /// Send a raw NDJSON bulk body to Elasticsearch with retry.
    pub async fn send_bulk(&self, body: &str) -> Result<()> {
        if body.is_empty() {
            return Ok(());
        }

        let url = format!("{}/_bulk", self.url);
        let mut last_err = None;

        for attempt in 0..3u32 {
            if attempt > 0 {
                let delay = std::time::Duration::from_millis(500 * 2u64.pow(attempt - 1));
                tokio::time::sleep(delay).await;
                debug!(attempt, "Retrying Elasticsearch bulk send");
            }

            let mut req = self
                .client
                .post(&url)
                .header("Content-Type", "application/x-ndjson")
                .body(body.to_string());

            if let Some(ref auth) = self.auth_header {
                req = req.header("Authorization", auth);
            }

            match req.send().await {
                Ok(resp) => {
                    if resp.status().is_success() {
                        debug!("Elasticsearch bulk send succeeded");
                        return Ok(());
                    }
                    let status = resp.status();
                    let text = resp.text().await.unwrap_or_default();
                    warn!(
                        status = %status,
                        body = %text,
                        "Elasticsearch bulk send returned error"
                    );
                    last_err = Some(anyhow::anyhow!(
                        "Elasticsearch returned HTTP {}: {}",
                        status,
                        text
                    ));
                }
                Err(e) => {
                    warn!(error = %e, attempt, "Elasticsearch bulk send failed");
                    last_err = Some(e.into());
                }
            }
        }

        Err(last_err.unwrap_or_else(|| anyhow::anyhow!("Elasticsearch bulk send failed")))
    }

    /// Send ONT telemetry to Elasticsearch, chunked by bulk_size.
    pub async fn send_onts(
        &self,
        agent_id: &str,
        olt_name: &str,
        vendor: &str,
        model: &str,
        onts: &[OntData],
    ) -> Result<()> {
        for chunk in onts.chunks(self.bulk_size) {
            let body = self.build_ont_bulk(agent_id, olt_name, vendor, model, chunk);
            self.send_bulk(&body).await?;
        }
        Ok(())
    }

    /// Send a fault event to Elasticsearch.
    pub async fn send_fault(&self, event: &FaultEvent) -> Result<()> {
        let now = Utc::now();
        let date_suffix = now.format("%Y.%m.%d").to_string();
        let index = format!("{}-faults-{}", self.index_prefix, date_suffix);

        let action = serde_json::json!({
            "index": { "_index": &index }
        });
        let doc = Self::fault_event_to_doc(event);

        let body = format!("{}\n{}\n", action, doc);
        self.send_bulk(&body).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fault::detector::AffectedOnt;
    use crate::predictions::{
        CustomerDiagnostic, DiagnosticIssue, DiagnosticSeverity, DegradationSeverity,
        SignalPrediction,
    };
    use crate::vendors::{ExtendedOntMetrics, OntStatus};

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
        }
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

        // Check index pattern is enlace-adtran-{date}
        let action: serde_json::Value = serde_json::from_str(lines[0]).unwrap();
        let index_name = action["index"]["_index"].as_str().unwrap();
        assert!(
            index_name.starts_with("enlace-adtran-"),
            "Adtran index should start with enlace-adtran-: {}",
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

    #[test]
    fn test_fault_event_doc() {
        use crate::fault::detector::FaultType;

        let event = FaultEvent {
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
        };

        let doc_str = ElasticOutput::fault_event_to_doc(&event);
        let doc: serde_json::Value = serde_json::from_str(&doc_str).unwrap();

        assert_eq!(doc["type"], "fibre_cut");
        assert_eq!(doc["severity"], "critical");
        assert_eq!(doc["affected_onts_count"], 2);
        assert_eq!(doc["dying_gasp_count"], 0);
        assert_eq!(doc["pon_port"], "0/2/0");
        assert_eq!(doc["olt_id"], "olt-norte");
        assert_eq!(doc["detection_latency_seconds"], 15);
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
