// SPDX-License-Identifier: Apache-2.0
// Elasticsearch NDJSON bulk output for ONT telemetry and fault events

use anyhow::{Context, Result};
use base64::Engine;
use chrono::Utc;
use tracing::{debug, warn};

use crate::config::ElasticConfig;
use crate::fault::detector::FaultEvent;
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

    /// Convert a FaultEvent into a JSON document string for Elasticsearch.
    pub fn fault_event_to_doc(event: &FaultEvent) -> String {
        let doc = serde_json::json!({
            "@timestamp": event.timestamp.to_rfc3339(),
            "type": "trunk_fibre_cut",
            "severity": &event.severity,
            "pon_port": &event.pon_port,
            "olt_id": &event.olt_id,
            "affected_onts_count": event.affected_onts.len(),
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
    use crate::vendors::OntStatus;

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
    fn test_fault_event_doc() {
        let event = FaultEvent {
            timestamp: Utc::now(),
            pon_port: "0/2/0".into(),
            olt_id: "olt-norte".into(),
            severity: "critical".into(),
            affected_onts: vec![
                AffectedOnt {
                    serial_number: "ONT001".into(),
                    distance_meters: Some(500),
                    last_rx_dbm: Some(-26.0),
                },
                AffectedOnt {
                    serial_number: "ONT002".into(),
                    distance_meters: Some(800),
                    last_rx_dbm: Some(-27.5),
                },
            ],
            detection_latency_seconds: 15,
        };

        let doc_str = ElasticOutput::fault_event_to_doc(&event);
        let doc: serde_json::Value = serde_json::from_str(&doc_str).unwrap();

        assert_eq!(doc["type"], "trunk_fibre_cut");
        assert_eq!(doc["severity"], "critical");
        assert_eq!(doc["affected_onts_count"], 2);
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
}
