// SPDX-License-Identifier: Apache-2.0
// Webhook dispatcher — Slack, PagerDuty, and generic webhook integration
//
// Dispatch is incident-based: one payload when an incident opens, one when it
// resolves, with a stable per-incident dedup key ("{olt}:{pon_port}:{opened_at}")
// carried as PagerDuty `dedup_key` / generic `incident_id`. Endpoints are
// contacted concurrently so a dead endpoint never serially blocks the poll
// loop; each HTTP request is bounded by a 10s timeout.

use std::sync::Arc;

use tracing::{debug, warn};

use crate::config::WebhookConfig;
use crate::fault::detector::{FaultType, IncidentAction, IncidentScope, IncidentUpdate};

/// Per-request HTTP timeout (seconds)
const REQUEST_TIMEOUT_SECS: u64 = 10;

/// Webhook dispatcher — sends incident updates to configured webhook endpoints
/// with format-specific payloads (Slack, PagerDuty, or generic JSON).
pub struct WebhookDispatcher {
    client: reqwest::Client,
    webhooks: Vec<WebhookEndpoint>,
}

/// A configured webhook with its bearer token resolved once at startup.
struct WebhookEndpoint {
    config: WebhookConfig,
    /// `Authorization: Bearer` token for generic-format webhooks; resolved
    /// from `bearer_token` / `bearer_token_env` by [`resolve_bearer_token`].
    bearer_token: Option<String>,
}

impl WebhookDispatcher {
    /// Create a new dispatcher with the given webhook configurations.
    /// Bearer tokens (`bearer_token` / `bearer_token_env`) are resolved here,
    /// once, so a missing environment variable warns at startup rather than
    /// failing silently at dispatch time.
    pub fn new(webhooks: &[WebhookConfig]) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .build()
            .expect("Failed to build HTTP client");

        Self {
            client,
            webhooks: webhooks
                .iter()
                .map(|w| WebhookEndpoint {
                    bearer_token: resolve_bearer_token(w),
                    config: w.clone(),
                })
                .collect(),
        }
    }

    /// Fire-and-forget dispatch: spawns the delivery in the background so the
    /// poll loop is never blocked by slow or dead endpoints.
    pub fn dispatch_incident_detached(self: &Arc<Self>, update: &IncidentUpdate) {
        let dispatcher = Arc::clone(self);
        let update = update.clone();
        tokio::spawn(async move {
            dispatcher.dispatch_incident(&update).await;
        });
    }

    /// Dispatch an incident update to all matching webhooks concurrently.
    /// Filters webhooks by event type, formats the payload per webhook format,
    /// and sends with 3x retry on failure.
    pub async fn dispatch_incident(&self, update: &IncidentUpdate) {
        let event_types = event_types_for(update);

        let mut handles = Vec::new();
        for endpoint in &self.webhooks {
            let webhook = &endpoint.config;
            if !event_types.iter().any(|t| should_send(webhook, t)) {
                continue;
            }

            let body = match webhook.format.as_str() {
                "slack" => format_slack(update),
                "pagerduty" => {
                    format_pagerduty(update, webhook.routing_key.as_deref().unwrap_or(""))
                }
                _ => format_generic(update),
            };

            let client = self.client.clone();
            let url = webhook.url.clone();
            let format = webhook.format.clone();
            let bearer_token = endpoint.bearer_token.clone();
            handles.push(tokio::spawn(async move {
                send_with_retry(&client, &url, &format, body, bearer_token.as_deref()).await;
            }));
        }

        for handle in handles {
            let _ = handle.await;
        }
    }
}

/// Resolve the effective bearer token for a webhook at startup.
/// `bearer_token` wins; otherwise `bearer_token_env` is read from the
/// environment (mirroring how the audit server reads PULSO_AUDIT_TOKEN).
/// Only generic-format webhooks send `Authorization: Bearer` — Slack and
/// PagerDuty authenticate via the webhook URL / `routing_key`, so a token
/// configured on those formats is ignored with a warning.
fn resolve_bearer_token(config: &WebhookConfig) -> Option<String> {
    let token = match (&config.bearer_token, &config.bearer_token_env) {
        (Some(token), _) => Some(token.clone()),
        (None, Some(var)) => match std::env::var(var) {
            Ok(value) if !value.is_empty() => Some(value),
            _ => {
                warn!(
                    url = %config.url,
                    env = %var,
                    "bearer_token_env is set but the environment variable is \
                     unset or empty — webhook will POST without Authorization"
                );
                None
            }
        },
        (None, None) => None,
    }?;

    if matches!(config.format.as_str(), "slack" | "pagerduty") {
        warn!(
            url = %config.url,
            format = %config.format,
            "bearer_token is only sent on generic-format webhooks; Slack and \
             PagerDuty use their own auth — ignoring the configured token"
        );
        return None;
    }

    Some(token)
}

/// POST `body` to `url` with 3 attempts and exponential backoff.
/// When `bearer_token` is set, sends `Authorization: Bearer <token>`.
async fn send_with_retry(
    client: &reqwest::Client,
    url: &str,
    format: &str,
    body: String,
    bearer_token: Option<&str>,
) {
    for attempt in 0..3u32 {
        if attempt > 0 {
            let delay = std::time::Duration::from_millis(500 * 2u64.pow(attempt - 1));
            tokio::time::sleep(delay).await;
            debug!(attempt, url = %url, "Retrying webhook dispatch");
        }

        let mut request = client
            .post(url)
            .header("Content-Type", "application/json")
            .body(body.clone());
        if let Some(token) = bearer_token {
            request = request.header("Authorization", format!("Bearer {token}"));
        }

        match request.send().await {
            Ok(resp) if resp.status().is_success() => {
                debug!(url = %url, format = %format, "Webhook dispatched");
                return;
            }
            Ok(resp) => {
                let status = resp.status();
                warn!(
                    url = %url,
                    status = %status,
                    attempt,
                    "Webhook returned error"
                );
            }
            Err(e) => {
                warn!(
                    url = %url,
                    error = %e,
                    attempt,
                    "Webhook dispatch failed"
                );
            }
        }
    }
}

/// Event types that this update matches against webhook `events` filters.
fn event_types_for(update: &IncidentUpdate) -> Vec<String> {
    match update.action {
        IncidentAction::Open => vec![
            "fault_detected".to_string(),
            format!("fault_{}", update.event.severity),
        ],
        // Resolves go to the same receivers that got the open
        IncidentAction::Resolve => vec![
            "fault_resolved".to_string(),
            "fault_detected".to_string(),
            format!("fault_{}", update.event.severity),
        ],
    }
}

/// Check if a webhook should receive a given event type.
/// Returns true if the webhook's events list contains the event type or "*" (wildcard).
pub fn should_send(config: &WebhookConfig, event_type: &str) -> bool {
    config.events.iter().any(|e| e == event_type || e == "*")
}

/// Human-readable headline for a fault type — never hardcode "fibre cut".
fn fault_headline(fault_type: &FaultType) -> &'static str {
    match fault_type {
        FaultType::FibreCut => "Fibre cut",
        FaultType::PowerOutage => "Power outage",
        FaultType::Mixed => "Mixed outage (power loss + possible fibre fault)",
    }
}

/// Where the incident is: single port or OLT-level (feeder) rollup.
fn location_phrase(update: &IncidentUpdate) -> String {
    match update.scope {
        IncidentScope::Port => format!("PON port {}", update.event.pon_port),
        IncidentScope::Olt => format!(
            "{} PON ports ({})",
            update.ports.len(),
            update.event.pon_port
        ),
    }
}

/// One-line summary reflecting the actual fault type, severity, and scope.
fn summary_for(update: &IncidentUpdate) -> String {
    let headline = fault_headline(&update.event.fault_type);
    let location = location_phrase(update);
    match update.action {
        IncidentAction::Open => match update.scope {
            IncidentScope::Port => format!(
                "{}: {} detected on {} (OLT: {}). {} ONTs affected.",
                update.event.severity.to_uppercase(),
                headline,
                location,
                update.event.olt_id,
                update.event.affected_onts.len()
            ),
            IncidentScope::Olt => format!(
                "{}: Feeder/OLT-level fault ({}) on OLT {}: {} ports, {} ONTs affected.",
                update.event.severity.to_uppercase(),
                headline,
                update.event.olt_id,
                update.ports.len(),
                update.event.affected_onts.len()
            ),
        },
        IncidentAction::Resolve => format!(
            "RESOLVED: {} on {} (OLT: {}) — {} ONTs recovering.",
            headline,
            location,
            update.event.olt_id,
            update.event.affected_onts.len()
        ),
    }
}

/// Format an incident update as a Slack incoming webhook payload.
/// Uses Block Kit with a mrkdwn section for rich formatting. The
/// classification evidence one-liner (gasp ratio, onset, confidence — and
/// the area-power note when the cross-OLT pass set it) renders alongside
/// the fault type so responders see WHY the call was made, not just the label.
pub fn format_slack(update: &IncidentUpdate) -> String {
    let summary = summary_for(update);

    let mut text = format!(
        "*{}*\n\n*Incident:* `{}`\n*Fault Type:* {}\n*PON Port(s):* `{}`\n*OLT:* `{}`\n*Affected ONTs:* {}\n*Severity:* {}\n*Detection Latency:* {}s",
        summary,
        update.incident_id,
        update.event.fault_type,
        update.event.pon_port,
        update.event.olt_id,
        update.event.affected_onts.len(),
        update.event.severity,
        update.event.detection_latency_seconds
    );
    if !update.classification.summary.is_empty() {
        text.push_str(&format!(
            "\n*Classification:* {}",
            update.classification.summary
        ));
    }

    let payload = serde_json::json!({
        "text": &summary,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
    });

    payload.to_string()
}

/// Map internal severity to PagerDuty Events API v2 severity
/// (critical | error | warning | info).
fn pagerduty_severity(severity: &str) -> &'static str {
    match severity {
        "critical" => "critical",
        "major" => "error",
        "minor" | "warning" => "warning",
        _ => "info",
    }
}

/// Format an incident update as a PagerDuty Events API v2 payload.
/// The stable `dedup_key` groups the open and resolve of the same incident.
/// See: https://developer.pagerduty.com/docs/events-api-v2/trigger-events/
pub fn format_pagerduty(update: &IncidentUpdate, routing_key: &str) -> String {
    let event_action = match update.action {
        IncidentAction::Open => "trigger",
        IncidentAction::Resolve => "resolve",
    };

    let payload = serde_json::json!({
        "routing_key": routing_key,
        "event_action": event_action,
        "dedup_key": &update.incident_id,
        "payload": {
            "summary": summary_for(update),
            "severity": pagerduty_severity(&update.event.severity),
            "source": format!("pulso-agent:{}", update.event.olt_id),
            "component": "fibre-network",
            "group": &update.event.pon_port,
            "timestamp": update.event.timestamp.to_rfc3339(),
            "custom_details": {
                "incident_id": &update.incident_id,
                "fault_type": update.event.fault_type.to_string(),
                "scope": match update.scope {
                    IncidentScope::Port => "port",
                    IncidentScope::Olt => "olt",
                },
                "ports": &update.ports,
                "affected_onts_count": update.event.affected_onts.len(),
                "detection_latency_seconds": update.event.detection_latency_seconds,
                "pon_port": &update.event.pon_port,
                "olt_id": &update.event.olt_id,
                "classification_summary": &update.classification.summary,
                "classification_confidence": update.classification.confidence.to_string(),
                "area_power_suspected": update.area_power_suspected
            }
        }
    });

    payload.to_string()
}

/// Format an incident update as a generic JSON payload.
/// The event fields are flattened to the top level next to `incident_id`,
/// `action`, `scope`, `opened_at`, `resolved_at`, and `ports`.
pub fn format_generic(update: &IncidentUpdate) -> String {
    serde_json::to_string(update).unwrap_or_else(|_| "{}".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use crate::fault::detector::{AffectedOnt, FaultEvent};

    fn make_update(
        action: IncidentAction,
        scope: IncidentScope,
        fault_type: FaultType,
        severity: &str,
    ) -> IncidentUpdate {
        let opened_at = Utc::now();
        let event = FaultEvent {
            timestamp: opened_at,
            pon_port: "0/3/0".into(),
            olt_id: "olt-sul".into(),
            severity: severity.into(),
            fault_type,
            affected_onts: vec![
                AffectedOnt {
                    serial_number: "ONT100".into(),
                    distance_meters: Some(300),
                    last_rx_dbm: Some(-24.0),
                    had_dying_gasp: false,
                },
                AffectedOnt {
                    serial_number: "ONT101".into(),
                    distance_meters: Some(650),
                    last_rx_dbm: Some(-26.5),
                    had_dying_gasp: false,
                },
                AffectedOnt {
                    serial_number: "ONT102".into(),
                    distance_meters: Some(900),
                    last_rx_dbm: Some(-27.8),
                    had_dying_gasp: false,
                },
            ],
            detection_latency_seconds: 12,
        };
        IncidentUpdate {
            action,
            incident_id: format!("olt-sul:0/3/0:{}", opened_at.timestamp()),
            scope,
            opened_at,
            resolved_at: match action {
                IncidentAction::Open => None,
                IncidentAction::Resolve => Some(opened_at),
            },
            ports: vec!["0/3/0".into()],
            classification: Default::default(),
            area_power_suspected: false,
            event,
        }
    }

    #[test]
    fn test_slack_copy_matches_fault_type_and_severity() {
        // A critical fibre cut says "Fibre cut" and "CRITICAL"
        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        let body = format_slack(&update);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();
        let text = parsed["text"].as_str().unwrap();
        assert!(text.contains("CRITICAL"), "expected CRITICAL in: {}", text);
        assert!(text.contains("Fibre cut"), "expected Fibre cut in: {}", text);

        // Check blocks structure
        assert_eq!(parsed["blocks"].as_array().unwrap().len(), 1);
        assert_eq!(parsed["blocks"][0]["type"], "section");
        assert_eq!(parsed["blocks"][0]["text"]["type"], "mrkdwn");

        // A major power outage must NOT be reported as a critical fibre cut
        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::PowerOutage, "major",
        );
        let body = format_slack(&update);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();
        let text = parsed["text"].as_str().unwrap();
        assert!(text.contains("Power outage"), "expected Power outage in: {}", text);
        assert!(text.contains("MAJOR"), "expected MAJOR in: {}", text);
        assert!(!text.to_lowercase().contains("fibre cut"),
            "power outage must not be paged as a fibre cut: {}", text);
        assert!(!text.contains("CRITICAL"),
            "major severity must not be paged as CRITICAL: {}", text);
    }

    #[test]
    fn test_slack_olt_level_rollup_copy() {
        let mut update = make_update(
            IncidentAction::Open, IncidentScope::Olt, FaultType::FibreCut, "critical",
        );
        update.ports = vec!["0/1/0".into(), "0/1/1".into(), "0/1/2".into()];
        update.event.pon_port = "0/1/0,0/1/1,0/1/2".into();

        let body = format_slack(&update);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();
        let text = parsed["text"].as_str().unwrap();
        assert!(text.contains("Feeder/OLT-level fault"), "expected rollup copy: {}", text);
        assert!(text.contains("3 ports"), "expected port count: {}", text);
    }

    #[test]
    fn test_slack_resolve_copy() {
        let update = make_update(
            IncidentAction::Resolve, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        let body = format_slack(&update);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();
        let text = parsed["text"].as_str().unwrap();
        assert!(text.contains("RESOLVED"), "expected RESOLVED in: {}", text);
    }

    #[test]
    fn test_classification_summary_renders_in_slack_and_pagerduty() {
        use crate::fault::detector::{
            ClassificationConfidence, ClassificationEvidence, OnsetPattern,
        };
        let mut update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::PowerOutage, "major",
        );
        update.classification = ClassificationEvidence {
            dying_gasp_count: 7,
            hard_offline_count: 1,
            dying_gasp_ratio: 0.875,
            onset: OnsetPattern::Simultaneous,
            onset_spread_seconds: 12,
            confidence: ClassificationConfidence::High,
            summary: "power_outage: 7/8 dying gasps (ratio 0.88); area power event \
                      suspected — 2 OLTs opened power-classified incidents in the \
                      same pass"
                .into(),
        };
        update.area_power_suspected = true;

        let slack: serde_json::Value =
            serde_json::from_str(&format_slack(&update)).unwrap();
        let text = slack["blocks"][0]["text"]["text"].as_str().unwrap();
        assert!(
            text.contains("*Classification:*") && text.contains("7/8 dying gasps"),
            "Slack must render the classification evidence line: {}",
            text
        );
        assert!(
            text.contains("area power event suspected"),
            "area-power note must reach Slack: {}",
            text
        );

        let pd: serde_json::Value =
            serde_json::from_str(&format_pagerduty(&update, "RKEY")).unwrap();
        let details = &pd["payload"]["custom_details"];
        assert!(
            details["classification_summary"]
                .as_str()
                .unwrap()
                .contains("7/8 dying gasps"),
            "PagerDuty custom_details must carry the classification summary"
        );
        assert_eq!(details["classification_confidence"], "high");
        assert_eq!(details["area_power_suspected"], true);

        // Default (empty) classification must not render a dangling line.
        let bare = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        let slack: serde_json::Value =
            serde_json::from_str(&format_slack(&bare)).unwrap();
        let text = slack["blocks"][0]["text"]["text"].as_str().unwrap();
        assert!(!text.contains("*Classification:*"));
    }

    #[test]
    fn test_pagerduty_format_with_dedup_key() {
        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        let body = format_pagerduty(&update, "R0123456789ABCDEF");
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();

        assert_eq!(parsed["routing_key"], "R0123456789ABCDEF");
        assert_eq!(parsed["event_action"], "trigger");
        assert_eq!(
            parsed["dedup_key"].as_str().unwrap(),
            update.incident_id,
            "PagerDuty payload must carry the stable incident dedup_key"
        );
        assert_eq!(parsed["payload"]["severity"], "critical");
        assert_eq!(parsed["payload"]["component"], "fibre-network");
        assert_eq!(parsed["payload"]["group"], "0/3/0");
        assert!(parsed["payload"]["summary"].as_str().unwrap().contains("Fibre cut"));
    }

    #[test]
    fn test_pagerduty_resolve_event() {
        let update = make_update(
            IncidentAction::Resolve, IncidentScope::Port, FaultType::PowerOutage, "major",
        );
        let body = format_pagerduty(&update, "RKEY");
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();

        assert_eq!(parsed["event_action"], "resolve");
        assert_eq!(parsed["dedup_key"].as_str().unwrap(), update.incident_id);
    }

    #[test]
    fn test_pagerduty_severity_mapping() {
        // "major" is not a valid PagerDuty severity — must map to "error"
        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::PowerOutage, "major",
        );
        let body = format_pagerduty(&update, "RKEY");
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();
        assert_eq!(parsed["payload"]["severity"], "error");
        assert!(parsed["payload"]["summary"].as_str().unwrap().contains("Power outage"));
        assert_eq!(parsed["payload"]["custom_details"]["fault_type"], "power_outage");
    }

    #[test]
    fn test_generic_format_has_incident_id_and_action() {
        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::Mixed, "minor",
        );
        let body = format_generic(&update);
        let parsed: serde_json::Value = serde_json::from_str(&body).unwrap();

        assert_eq!(parsed["incident_id"].as_str().unwrap(), update.incident_id);
        assert_eq!(parsed["action"], "open");
        assert_eq!(parsed["scope"], "port");
        // Event fields are flattened to the top level
        assert_eq!(parsed["pon_port"], "0/3/0");
        assert_eq!(parsed["olt_id"], "olt-sul");
        assert_eq!(parsed["severity"], "minor");
        assert_eq!(parsed["fault_type"], "Mixed");

        let resolve = make_update(
            IncidentAction::Resolve, IncidentScope::Port, FaultType::Mixed, "minor",
        );
        let parsed: serde_json::Value =
            serde_json::from_str(&format_generic(&resolve)).unwrap();
        assert_eq!(parsed["action"], "resolve");
        assert!(parsed["resolved_at"].is_string());
    }

    #[test]
    fn test_event_filter() {
        let matching = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["fault_critical".into(), "fault_major".into()],
            format: "slack".into(),
            routing_key: None,
            bearer_token: None,
            bearer_token_env: None,
        };

        let wildcard = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["*".into()],
            format: "generic".into(),
            routing_key: None,
            bearer_token: None,
            bearer_token_env: None,
        };

        let non_matching = WebhookConfig {
            url: "https://hooks.example.com".into(),
            events: vec!["ont_offline".into()],
            format: "slack".into(),
            routing_key: None,
            bearer_token: None,
            bearer_token_env: None,
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
            bearer_token: None,
            bearer_token_env: None,
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

    fn make_webhook_config(url: &str, format: &str) -> WebhookConfig {
        WebhookConfig {
            url: url.into(),
            events: vec!["*".into()],
            format: format.into(),
            routing_key: None,
            bearer_token: None,
            bearer_token_env: None,
        }
    }

    #[test]
    fn test_resolve_bearer_token_direct_and_env_precedence() {
        // Direct token on a generic webhook resolves as-is
        let mut config = make_webhook_config("https://app.enlace.network/api/hooks/agent-events", "generic");
        config.bearer_token = Some("direct-secret".into());
        assert_eq!(resolve_bearer_token(&config).as_deref(), Some("direct-secret"));

        // bearer_token wins when both are set
        std::env::set_var("PULSO_TEST_HOOK_TOKEN_PRECEDENCE", "env-secret");
        config.bearer_token_env = Some("PULSO_TEST_HOOK_TOKEN_PRECEDENCE".into());
        assert_eq!(resolve_bearer_token(&config).as_deref(), Some("direct-secret"));

        // env-only falls back to the environment variable
        config.bearer_token = None;
        assert_eq!(resolve_bearer_token(&config).as_deref(), Some("env-secret"));

        // Missing/unset env var resolves to no token (warns, never panics)
        config.bearer_token_env = Some("PULSO_TEST_HOOK_TOKEN_DOES_NOT_EXIST".into());
        assert_eq!(resolve_bearer_token(&config), None);

        // Neither field set -> no token
        config.bearer_token_env = None;
        assert_eq!(resolve_bearer_token(&config), None);
    }

    #[test]
    fn test_resolve_bearer_token_ignored_for_slack_and_pagerduty() {
        // Slack and PagerDuty carry their own auth — a configured bearer
        // token must not leak into their requests.
        for format in ["slack", "pagerduty"] {
            let mut config = make_webhook_config("https://hooks.example.com", format);
            config.bearer_token = Some("secret".into());
            assert_eq!(
                resolve_bearer_token(&config),
                None,
                "{format} webhooks must not send Authorization: Bearer"
            );
        }
    }

    // --- Mock webhook sink recording the Authorization header ---------------

    /// Spawn a minimal HTTP sink that records the Authorization header (or
    /// None) of every POST. Returns (url, recorded_headers).
    async fn spawn_header_sink() -> (
        String,
        std::sync::Arc<std::sync::Mutex<Vec<Option<String>>>>,
    ) {
        let headers: std::sync::Arc<std::sync::Mutex<Vec<Option<String>>>> =
            std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
        let state = headers.clone();
        let app = axum::Router::new().route(
            "/hook",
            axum::routing::post(move |req_headers: axum::http::HeaderMap| {
                let state = state.clone();
                async move {
                    let auth = req_headers
                        .get("authorization")
                        .and_then(|v| v.to_str().ok())
                        .map(str::to_string);
                    state.lock().unwrap().push(auth);
                    "ok"
                }
            }),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        (format!("http://{}/hook", addr), headers)
    }

    #[tokio::test]
    async fn test_generic_webhook_sends_bearer_header_when_configured() {
        let (url, auths) = spawn_header_sink().await;
        let mut config = make_webhook_config(&url, "generic");
        config.bearer_token = Some("hook-secret".into());
        let dispatcher = WebhookDispatcher::new(&[config]);

        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        dispatcher.dispatch_incident(&update).await;

        let auths = auths.lock().unwrap();
        assert_eq!(auths.len(), 1, "exactly one webhook POST expected");
        assert_eq!(
            auths[0].as_deref(),
            Some("Bearer hook-secret"),
            "generic webhook must carry Authorization: Bearer <token>"
        );
    }

    #[tokio::test]
    async fn test_generic_webhook_from_env_sends_bearer_header() {
        std::env::set_var("PULSO_TEST_HOOK_TOKEN_DISPATCH", "env-hook-secret");
        let (url, auths) = spawn_header_sink().await;
        let mut config = make_webhook_config(&url, "generic");
        config.bearer_token_env = Some("PULSO_TEST_HOOK_TOKEN_DISPATCH".into());
        let dispatcher = WebhookDispatcher::new(&[config]);

        let update = make_update(
            IncidentAction::Resolve, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        dispatcher.dispatch_incident(&update).await;

        let auths = auths.lock().unwrap();
        assert_eq!(auths.len(), 1);
        assert_eq!(auths[0].as_deref(), Some("Bearer env-hook-secret"));
    }

    #[tokio::test]
    async fn test_webhook_without_token_sends_no_authorization_header() {
        let (url, auths) = spawn_header_sink().await;
        let dispatcher = WebhookDispatcher::new(&[make_webhook_config(&url, "generic")]);

        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        dispatcher.dispatch_incident(&update).await;

        let auths = auths.lock().unwrap();
        assert_eq!(auths.len(), 1);
        assert_eq!(
            auths[0], None,
            "no Authorization header when no bearer token is configured"
        );
    }

    #[tokio::test]
    async fn test_slack_webhook_never_sends_bearer_header() {
        let (url, auths) = spawn_header_sink().await;
        let mut config = make_webhook_config(&url, "slack");
        config.bearer_token = Some("must-not-leak".into());
        let dispatcher = WebhookDispatcher::new(&[config]);

        let update = make_update(
            IncidentAction::Open, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        dispatcher.dispatch_incident(&update).await;

        let auths = auths.lock().unwrap();
        assert_eq!(auths.len(), 1);
        assert_eq!(
            auths[0], None,
            "Slack webhooks use their own auth — bearer token must not leak"
        );
    }

    #[test]
    fn test_resolve_reaches_fault_detected_receivers() {
        let resolve = make_update(
            IncidentAction::Resolve, IncidentScope::Port, FaultType::FibreCut, "critical",
        );
        let types = event_types_for(&resolve);
        assert!(types.iter().any(|t| t == "fault_resolved"));
        assert!(
            types.iter().any(|t| t == "fault_detected"),
            "resolves must reach receivers subscribed to fault_detected"
        );
    }
}
