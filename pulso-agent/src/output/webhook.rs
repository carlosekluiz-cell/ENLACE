// SPDX-License-Identifier: Apache-2.0
// Webhook dispatcher — Slack, PagerDuty, and generic webhook integration

use tracing::{debug, warn};

use crate::config::WebhookConfig;
use crate::fault::detector::FaultEvent;

/// Webhook dispatcher — sends fault events to configured webhook endpoints
/// with format-specific payloads (Slack, PagerDuty, or generic JSON).
pub struct WebhookDispatcher {
    client: reqwest::Client,
    webhooks: Vec<WebhookConfig>,
}

impl WebhookDispatcher {
    /// Create a new dispatcher with the given webhook configurations.
    pub fn new(webhooks: &[WebhookConfig]) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .expect("Failed to build HTTP client");

        Self {
            client,
            webhooks: webhooks.to_vec(),
        }
    }

    /// Dispatch a fault event to all matching webhooks.
    /// Filters webhooks by event type, formats the payload per webhook format,
    /// and sends with 3x retry on failure.
    pub async fn dispatch_fault(&self, event: &FaultEvent) {
        let severity_type = format!("fault_{}", event.severity);

        for webhook in &self.webhooks {
            // Match both "fault_detected" (spec-documented) and "fault_{severity}" (granular)
            if !should_send(webhook, "fault_detected") && !should_send(webhook, &severity_type) {
                continue;
            }

            let body = match webhook.format.as_str() {
                "slack" => format_slack(event),
                "pagerduty" => format_pagerduty(event, webhook.routing_key.as_deref().unwrap_or("")),
                _ => format_generic(event),
            };

            let content_type = "application/json";

            for attempt in 0..3u32 {
                if attempt > 0 {
                    let delay = std::time::Duration::from_millis(500 * 2u64.pow(attempt - 1));
                    tokio::time::sleep(delay).await;
                    debug!(attempt, url = %webhook.url, "Retrying webhook dispatch");
                }

                match self
                    .client
                    .post(&webhook.url)
                    .header("Content-Type", content_type)
                    .body(body.clone())
                    .send()
                    .await
                {
                    Ok(resp) if resp.status().is_success() => {
                        debug!(url = %webhook.url, format = %webhook.format, "Webhook dispatched");
                        break;
                    }
                    Ok(resp) => {
                        let status = resp.status();
                        warn!(
                            url = %webhook.url,
                            status = %status,
                            attempt,
                            "Webhook returned error"
                        );
                    }
                    Err(e) => {
                        warn!(
                            url = %webhook.url,
                            error = %e,
                            attempt,
                            "Webhook dispatch failed"
                        );
                    }
                }
            }
        }
    }
}

/// Check if a webhook should receive a given event type.
/// Returns true if the webhook's events list contains the event type or "*" (wildcard).
pub fn should_send(config: &WebhookConfig, event_type: &str) -> bool {
    config.events.iter().any(|e| e == event_type || e == "*")
}

/// Format a fault event as a Slack incoming webhook payload.
/// Uses Block Kit with a mrkdwn section for rich formatting.
pub fn format_slack(event: &FaultEvent) -> String {
    let summary = format!(
        "CRITICAL: Trunk fibre cut detected on PON port {} (OLT: {}). {} ONTs affected.",
        event.pon_port,
        event.olt_id,
        event.affected_onts.len()
    );

    let payload = serde_json::json!({
        "text": &summary,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": format!(
                        "*{}*\n\n*PON Port:* `{}`\n*OLT:* `{}`\n*Affected ONTs:* {}\n*Severity:* {}\n*Detection Latency:* {}s",
                        summary,
                        event.pon_port,
                        event.olt_id,
                        event.affected_onts.len(),
                        event.severity,
                        event.detection_latency_seconds
                    )
                }
            }
        ]
    });

    payload.to_string()
}

/// Format a fault event as a PagerDuty Events API v2 payload.
/// See: https://developer.pagerduty.com/docs/events-api-v2/trigger-events/
pub fn format_pagerduty(event: &FaultEvent, routing_key: &str) -> String {
    let summary = format!(
        "Trunk fibre cut on {} (OLT: {}): {} ONTs offline",
        event.pon_port, event.olt_id, event.affected_onts.len()
    );

    let payload = serde_json::json!({
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": &summary,
            "severity": &event.severity,
            "source": format!("pulso-agent:{}", event.olt_id),
            "component": "fibre-network",
            "group": &event.pon_port,
            "timestamp": event.timestamp.to_rfc3339(),
            "custom_details": {
                "affected_onts_count": event.affected_onts.len(),
                "detection_latency_seconds": event.detection_latency_seconds,
                "pon_port": &event.pon_port,
                "olt_id": &event.olt_id
            }
        }
    });

    payload.to_string()
}

/// Format a fault event as a generic JSON payload.
pub fn format_generic(event: &FaultEvent) -> String {
    serde_json::to_string(event).unwrap_or_else(|_| "{}".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use crate::fault::detector::AffectedOnt;

    fn make_fault_event() -> FaultEvent {
        FaultEvent {
            timestamp: Utc::now(),
            pon_port: "0/3/0".into(),
            olt_id: "olt-sul".into(),
            severity: "critical".into(),
            affected_onts: vec![
                AffectedOnt {
                    serial_number: "ONT100".into(),
                    distance_meters: Some(300),
                    last_rx_dbm: Some(-24.0),
                },
                AffectedOnt {
                    serial_number: "ONT101".into(),
                    distance_meters: Some(650),
                    last_rx_dbm: Some(-26.5),
                },
                AffectedOnt {
                    serial_number: "ONT102".into(),
                    distance_meters: Some(900),
                    last_rx_dbm: Some(-27.8),
                },
            ],
            detection_latency_seconds: 12,
        }
    }

    #[test]
    fn test_slack_format() {
        let event = make_fault_event();
        let body = format_slack(&event);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();

        // Check text contains CRITICAL
        let text = parsed["text"].as_str().unwrap();
        assert!(
            text.contains("CRITICAL"),
            "Slack text should contain CRITICAL: {}",
            text
        );

        // Check blocks is an array
        assert!(
            parsed["blocks"].is_array(),
            "Slack payload should have blocks array"
        );
        assert_eq!(
            parsed["blocks"].as_array().unwrap().len(),
            1,
            "Should have one block section"
        );

        // Check the block type
        assert_eq!(parsed["blocks"][0]["type"], "section");
        assert_eq!(parsed["blocks"][0]["text"]["type"], "mrkdwn");
    }

    #[test]
    fn test_pagerduty_format() {
        let event = make_fault_event();
        let body = format_pagerduty(&event, "R0123456789ABCDEF");
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();

        // Check routing_key
        assert_eq!(
            parsed["routing_key"], "R0123456789ABCDEF",
            "PagerDuty payload must include routing_key"
        );

        // Check event_action is "trigger"
        assert_eq!(
            parsed["event_action"], "trigger",
            "PagerDuty event_action should be trigger"
        );

        // Check payload fields
        assert_eq!(parsed["payload"]["severity"], "critical");
        assert!(parsed["payload"]["summary"]
            .as_str()
            .unwrap()
            .contains("ONTs offline"));
        assert_eq!(parsed["payload"]["component"], "fibre-network");
        assert_eq!(parsed["payload"]["group"], "0/3/0");
    }

    #[test]
    fn test_event_filter() {
        let matching = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["fault_critical".into(), "fault_major".into()],
            format: "slack".into(),
            routing_key: None,
        };

        let wildcard = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["*".into()],
            format: "generic".into(),
            routing_key: None,
        };

        let non_matching = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["ont_offline".into()],
            format: "slack".into(),
            routing_key: None,
        };

        // Matching event type
        assert!(
            should_send(&matching, "fault_critical"),
            "Should match fault_critical"
        );
        assert!(
            should_send(&matching, "fault_major"),
            "Should match fault_major"
        );

        // Wildcard matches everything
        assert!(
            should_send(&wildcard, "fault_critical"),
            "Wildcard should match any event"
        );
        assert!(
            should_send(&wildcard, "anything_at_all"),
            "Wildcard should match any event"
        );

        // "fault_detected" (spec-documented event type) should also work
        let spec_config = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["fault_detected".into()],
            format: "slack".into(),
            routing_key: None,
        };
        assert!(
            should_send(&spec_config, "fault_detected"),
            "fault_detected from spec config should match"
        );

        // Non-matching event type
        assert!(
            !should_send(&non_matching, "fault_critical"),
            "Should NOT match fault_critical when only ont_offline is configured"
        );
    }
}
