// SPDX-License-Identifier: Apache-2.0
// HTTP Audit Server
//
// Axum-based HTTP server that accepts CSV uploads via multipart form,
// runs the audit engine, and returns results as JSON.
//
// Security model (pilot-readiness finding 28):
//   - Bearer-token auth on every endpoint except GET /healthz.
//     Token comes from PULSO_AUDIT_TOKEN, or is generated at startup
//     (crypto-random UUIDv4) and printed once to stderr.
//   - Binds 127.0.0.1 by default; override with PULSO_AUDIT_BIND.
//   - No CORS headers unless PULSO_AUDIT_CORS_ORIGIN names an explicit origin.
//   - Request bodies capped (default 50 MB; PULSO_AUDIT_BODY_LIMIT_MB).
//     Uploads stream to a temp file instead of buffering fully in RAM.
//   - CPU-heavy parse + audit runs on the blocking thread pool.
//   - Results are evicted after a TTL (default 1 h; PULSO_AUDIT_RESULT_TTL_SECS)
//     and capped in count (default 100; PULSO_AUDIT_MAX_RESULTS).
//   - Error responses carry generic client-safe messages; full detail goes
//     to server-side tracing only.

use crate::audit::AuditResult;
use crate::csv_import;

use axum::{
    extract::{DefaultBodyLimit, Multipart, Path, Request, State},
    http::{header, HeaderValue, Method, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Json, Response},
    routing::{get, post},
    Router,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::io::Write;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tower_http::cors::CorsLayer;
use tracing::{error, info, warn};
use uuid::Uuid;

const DEFAULT_BIND: &str = "127.0.0.1";
const DEFAULT_BODY_LIMIT_MB: usize = 50;
const DEFAULT_RESULT_TTL_SECS: u64 = 3600;
const DEFAULT_MAX_RESULTS: usize = 100;

/// Runtime options for the audit server. Built from environment variables
/// with safe defaults; a `[serve]` config section can supersede this later.
pub struct ServeOptions {
    /// Address to bind (PULSO_AUDIT_BIND, default 127.0.0.1).
    pub bind: String,
    /// Bearer token required on all endpoints except GET /healthz
    /// (PULSO_AUDIT_TOKEN, or generated at startup).
    pub token: String,
    /// True when the token was generated rather than configured.
    pub token_generated: bool,
    /// Explicit CORS origin (PULSO_AUDIT_CORS_ORIGIN). None = no CORS headers.
    pub cors_origin: Option<String>,
    /// Max request body size in bytes (PULSO_AUDIT_BODY_LIMIT_MB, default 50 MB).
    pub body_limit_bytes: usize,
    /// How long audit results are retained (PULSO_AUDIT_RESULT_TTL_SECS, default 1 h).
    pub result_ttl: Duration,
    /// Max number of retained results; oldest evicted first (PULSO_AUDIT_MAX_RESULTS).
    pub max_results: usize,
}

impl ServeOptions {
    pub fn from_env() -> Self {
        let bind = std::env::var("PULSO_AUDIT_BIND")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .unwrap_or_else(|| DEFAULT_BIND.to_string());

        let (token, token_generated) = match std::env::var("PULSO_AUDIT_TOKEN") {
            Ok(t) if !t.trim().is_empty() => (t.trim().to_string(), false),
            _ => (Uuid::new_v4().to_string(), true),
        };

        let cors_origin = std::env::var("PULSO_AUDIT_CORS_ORIGIN")
            .ok()
            .filter(|v| !v.trim().is_empty());

        let body_limit_mb = env_parse("PULSO_AUDIT_BODY_LIMIT_MB", DEFAULT_BODY_LIMIT_MB);
        let ttl_secs = env_parse("PULSO_AUDIT_RESULT_TTL_SECS", DEFAULT_RESULT_TTL_SECS);
        let max_results = env_parse("PULSO_AUDIT_MAX_RESULTS", DEFAULT_MAX_RESULTS);

        ServeOptions {
            bind,
            token,
            token_generated,
            cors_origin,
            body_limit_bytes: body_limit_mb.saturating_mul(1024 * 1024),
            result_ttl: Duration::from_secs(ttl_secs),
            max_results,
        }
    }
}

fn env_parse<T: std::str::FromStr>(var: &str, default: T) -> T {
    match std::env::var(var) {
        Ok(v) => match v.trim().parse::<T>() {
            Ok(parsed) => parsed,
            Err(_) => {
                warn!(var, value = %v, "Invalid value for env var; using default");
                default
            }
        },
        Err(_) => default,
    }
}

/// In-memory audit result store with TTL + max-count eviction.
pub struct ResultStore {
    entries: HashMap<String, StoredResult>,
    ttl: Duration,
    max_results: usize,
}

struct StoredResult {
    result: AuditResult,
    inserted_at: Instant,
}

impl ResultStore {
    pub fn new(ttl: Duration, max_results: usize) -> Self {
        ResultStore {
            entries: HashMap::new(),
            ttl,
            max_results: max_results.max(1),
        }
    }

    pub fn insert(&mut self, id: String, result: AuditResult) {
        self.evict_expired();
        // Cap: evict oldest entries until there is room for the new one.
        while self.entries.len() >= self.max_results {
            let oldest = self
                .entries
                .iter()
                .min_by_key(|(_, v)| v.inserted_at)
                .map(|(k, _)| k.clone());
            match oldest {
                Some(k) => {
                    self.entries.remove(&k);
                }
                None => break,
            }
        }
        self.entries.insert(
            id,
            StoredResult {
                result,
                inserted_at: Instant::now(),
            },
        );
    }

    pub fn get(&self, id: &str) -> Option<&AuditResult> {
        self.entries
            .get(id)
            .filter(|e| e.inserted_at.elapsed() < self.ttl)
            .map(|e| &e.result)
    }

    pub fn evict_expired(&mut self) {
        let ttl = self.ttl;
        self.entries.retain(|_, e| e.inserted_at.elapsed() < ttl);
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }
}

#[derive(Clone)]
pub struct AppState {
    pub results: Arc<Mutex<ResultStore>>,
    /// SHA-256 of the bearer token; comparison is constant-time over the digest.
    token_hash: Arc<[u8; 32]>,
    body_limit_bytes: usize,
}

impl AppState {
    pub fn new(opts: &ServeOptions) -> Self {
        AppState {
            results: Arc::new(Mutex::new(ResultStore::new(
                opts.result_ttl,
                opts.max_results,
            ))),
            token_hash: Arc::new(Sha256::digest(opts.token.as_bytes()).into()),
            body_limit_bytes: opts.body_limit_bytes,
        }
    }

    fn lock_results(&self) -> std::sync::MutexGuard<'_, ResultStore> {
        // A poisoned lock only means a panic mid-insert on a cache; recover.
        self.results.lock().unwrap_or_else(|p| p.into_inner())
    }
}

pub async fn start_server(port: u16) -> anyhow::Result<()> {
    let opts = ServeOptions::from_env();

    if opts.token_generated {
        // Printed once, to stderr only, so operators can copy it at boot.
        eprintln!(
            "pulso-agent audit server: PULSO_AUDIT_TOKEN not set; generated bearer token (shown once): {}",
            opts.token
        );
    }

    let state = AppState::new(&opts);
    let app = build_router(state, opts.cors_origin.as_deref())?;

    let addr = format!("{}:{}", opts.bind, port);
    info!(
        bind = %opts.bind,
        port = port,
        body_limit_bytes = opts.body_limit_bytes,
        result_ttl_secs = opts.result_ttl.as_secs(),
        max_results = opts.max_results,
        cors_enabled = opts.cors_origin.is_some(),
        "Audit HTTP server starting on {}",
        addr
    );

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

/// Build the router. Split out from start_server so tests can drive it
/// with injected options (custom token, TTL, body limit).
pub fn build_router(state: AppState, cors_origin: Option<&str>) -> anyhow::Result<Router> {
    let protected = Router::new()
        .route("/audit", post(upload_audit))
        .route("/audit/:id", get(get_audit))
        // Legacy path kept for compatibility, but now requires auth;
        // GET /healthz is the unauthenticated probe.
        .route("/health", get(healthz))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_auth));

    let mut app = Router::new()
        .route("/healthz", get(healthz))
        .merge(protected)
        .layer(middleware::from_fn_with_state(
            state.clone(),
            enforce_content_length,
        ))
        .layer(DefaultBodyLimit::max(state.body_limit_bytes))
        .with_state(state);

    if let Some(origin) = cors_origin {
        let origin_value: HeaderValue = origin
            .parse()
            .map_err(|_| anyhow::anyhow!("PULSO_AUDIT_CORS_ORIGIN is not a valid origin"))?;
        let cors = CorsLayer::new()
            .allow_origin(origin_value)
            .allow_methods([Method::GET, Method::POST])
            .allow_headers([header::AUTHORIZATION, header::CONTENT_TYPE]);
        app = app.layer(cors);
    }

    Ok(app)
}

/// Constant-time bearer-token check: hash the candidate and compare digests
/// byte-by-byte without early exit. Hashing first also avoids leaking the
/// configured token's length.
fn token_matches(candidate: &str, expected_hash: &[u8; 32]) -> bool {
    let candidate_hash = Sha256::digest(candidate.as_bytes());
    let mut diff: u8 = 0;
    for (a, b) in candidate_hash.iter().zip(expected_hash.iter()) {
        diff |= a ^ b;
    }
    diff == 0
}

async fn require_auth(State(state): State<AppState>, req: Request, next: Next) -> Response {
    let authorized = req
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .map(|t| token_matches(t.trim(), &state.token_hash))
        .unwrap_or(false);

    if authorized {
        next.run(req).await
    } else {
        (
            StatusCode::UNAUTHORIZED,
            Json(json!({
                "error": "unauthorized",
                "message": "Missing or invalid bearer token",
            })),
        )
            .into_response()
    }
}

/// Reject oversized uploads up front when Content-Length is declared,
/// so clients get a deterministic 413 before streaming the body.
async fn enforce_content_length(
    State(state): State<AppState>,
    req: Request,
    next: Next,
) -> Response {
    let declared = req
        .headers()
        .get(header::CONTENT_LENGTH)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse::<u64>().ok());

    if let Some(len) = declared {
        if len > state.body_limit_bytes as u64 {
            return payload_too_large().into_response();
        }
    }
    next.run(req).await
}

async fn healthz(State(state): State<AppState>) -> Json<serde_json::Value> {
    let cached = state.lock_results().len();
    Json(json!({
        "status": "ok",
        "service": "pulso-audit",
        "version": env!("CARGO_PKG_VERSION"),
        "results_cached": cached,
    }))
}

/// Errors from the blocking parse+audit job, so client status codes can
/// distinguish bad input from server faults without echoing internals.
enum AuditJobError {
    Parse(anyhow::Error),
    Audit(anyhow::Error),
}

async fn upload_audit(
    State(state): State<AppState>,
    mut multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let mut vendor: Option<String> = None;
    let mut tmp: Option<tempfile::NamedTempFile> = None;
    let mut total_bytes: usize = 0;

    while let Some(mut field) = multipart.next_field().await.map_err(|e| {
        warn!(error = %e, "Rejected malformed multipart upload");
        bad_request("multipart_error", "Malformed multipart upload")
    })? {
        let name = field.name().unwrap_or("").to_string();
        match name.as_str() {
            "file" | "csv" => {
                // Stream the field to a temp file instead of buffering in RAM.
                let mut file = tempfile::NamedTempFile::new().map_err(|e| {
                    error!(error = %e, "Failed to create temp file for upload");
                    internal_error()
                })?;
                loop {
                    let chunk = match field.chunk().await {
                        Ok(Some(c)) => c,
                        Ok(None) => break,
                        Err(e) => {
                            warn!(error = %e, "Failed reading upload stream");
                            return Err(bad_request(
                                "read_error",
                                "Upload could not be read; it may exceed the size limit",
                            ));
                        }
                    };
                    total_bytes = total_bytes.saturating_add(chunk.len());
                    if total_bytes > state.body_limit_bytes {
                        return Err(payload_too_large());
                    }
                    file.write_all(&chunk).map_err(|e| {
                        error!(error = %e, "Failed writing upload to temp file");
                        internal_error()
                    })?;
                }
                file.flush().map_err(|e| {
                    error!(error = %e, "Failed flushing upload temp file");
                    internal_error()
                })?;
                tmp = Some(file);
            }
            "vendor" => {
                let text = field.text().await.map_err(|e| {
                    warn!(error = %e, "Failed reading vendor field");
                    bad_request("read_error", "Could not read 'vendor' field")
                })?;
                if !text.is_empty() {
                    vendor = Some(text);
                }
            }
            _ => {}
        }
    }

    let tmp = tmp.ok_or_else(|| bad_request("missing_field", "No 'file' or 'csv' field found"))?;

    if total_bytes == 0 {
        return Err(bad_request("empty_file", "Uploaded CSV file is empty"));
    }

    // Parsing + the audit engine are CPU-bound; keep them off the async runtime.
    // Snapshot exports carry no timestamps; stamp their rows with the upload time.
    let upload_time = chrono::Utc::now();
    let job = tokio::task::spawn_blocking(move || {
        let report = csv_import::parse_csv_with_report(
            tmp.path(),
            vendor.as_deref(),
            Some(upload_time),
        )
        .map_err(AuditJobError::Parse)?;
        // Client-safe summary: skip samples are capped and path-stripped.
        let import_report = crate::audit::ImportReportSummary::from(&report);
        let mut result =
            crate::audit::run_audit(report.readings).map_err(AuditJobError::Audit)?;
        result.import_report = Some(import_report);
        Ok(result)
        // `tmp` drops here, deleting the temp file.
    })
    .await;

    let result = match job {
        Err(e) => {
            error!(error = %e, "Audit task panicked or was cancelled");
            return Err(internal_error());
        }
        Ok(Err(AuditJobError::Parse(e))) => {
            warn!(error = %format!("{e:#}"), "CSV parse failed");
            return Err(bad_request(
                "csv_parse_error",
                "CSV file could not be parsed; check the file format and vendor",
            ));
        }
        Ok(Err(AuditJobError::Audit(e))) => {
            warn!(error = %format!("{e:#}"), "Audit failed on uploaded data");
            return Err(bad_request(
                "audit_error",
                "The uploaded data could not be audited",
            ));
        }
        Ok(Ok(result)) => result,
    };

    let audit_id = Uuid::new_v4().to_string();
    state.lock_results().insert(audit_id.clone(), result.clone());

    Ok((
        StatusCode::OK,
        Json(json!({
            "audit_id": audit_id,
            "result": result,
        })),
    ))
}

async fn get_audit(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let store = state.lock_results();
    match store.get(&id) {
        Some(result) => Ok(Json(json!({
            "audit_id": id,
            "result": result,
        }))),
        None => Err((
            StatusCode::NOT_FOUND,
            Json(json!({
                "error": "not_found",
                "message": "No audit found with this id (results expire after a retention period)",
            })),
        )),
    }
}

fn bad_request(error: &str, message: &str) -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::BAD_REQUEST,
        Json(json!({
            "error": error,
            "message": message,
        })),
    )
}

fn payload_too_large() -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::PAYLOAD_TOO_LARGE,
        Json(json!({
            "error": "payload_too_large",
            "message": "Request body exceeds the configured size limit",
        })),
    )
}

/// Generic 500. Details never reach the client; callers must tracing::error!
/// the specifics before returning this.
fn internal_error() -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(json!({
            "error": "internal_error",
            "message": "An internal error occurred",
        })),
    )
}

#[cfg(test)]
mod serve_tests {
    use super::*;

    const TEST_TOKEN: &str = "test-token-1234";

    fn test_options() -> ServeOptions {
        ServeOptions {
            bind: "127.0.0.1".into(),
            token: TEST_TOKEN.into(),
            token_generated: false,
            cors_origin: None,
            body_limit_bytes: 1024 * 1024,
            result_ttl: Duration::from_secs(3600),
            max_results: 100,
        }
    }

    async fn spawn_server(opts: &ServeOptions) -> String {
        let state = AppState::new(opts);
        let app = build_router(state, opts.cors_origin.as_deref()).unwrap();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        format!("http://{}", addr)
    }

    fn csv_multipart_body(boundary: &str, csv: &str) -> String {
        format!(
            "--{b}\r\n\
             Content-Disposition: form-data; name=\"file\"; filename=\"test.csv\"\r\n\
             Content-Type: text/csv\r\n\r\n\
             {csv}\r\n\
             --{b}--\r\n",
            b = boundary,
            csv = csv
        )
    }

    fn sample_csv() -> String {
        let mut csv = String::from("timestamp,ont_serial,pon_port,rx_power_dbm,status,distance\n");
        for i in 0..5 {
            csv.push_str(&format!(
                "2026-03-01 08:00:00,ADTN-{i:03},CTP-0/1,-2{i}.0,online,1000\n"
            ));
        }
        csv
    }

    // ── Auth ────────────────────────────────────────────────────────────

    #[tokio::test]
    async fn healthz_is_open_without_token() {
        let base = spawn_server(&test_options()).await;
        let resp = reqwest::get(format!("{base}/healthz")).await.unwrap();
        assert_eq!(resp.status(), 200);
        let body: serde_json::Value = resp.json().await.unwrap();
        assert_eq!(body["status"], "ok");
        assert_eq!(body["service"], "pulso-audit");
    }

    #[tokio::test]
    async fn endpoints_reject_missing_token_with_401() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();

        // GET /audit/:id without a token
        let resp = client
            .get(format!("{base}/audit/some-id"))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 401);
        let body: serde_json::Value = resp.json().await.unwrap();
        assert_eq!(body["error"], "unauthorized");

        // POST /audit without a token
        let resp = client
            .post(format!("{base}/audit"))
            .body("irrelevant")
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 401);

        // Legacy /health also requires auth now
        let resp = client.get(format!("{base}/health")).send().await.unwrap();
        assert_eq!(resp.status(), 401);
    }

    #[tokio::test]
    async fn endpoints_reject_wrong_token_with_401() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();
        let resp = client
            .get(format!("{base}/audit/some-id"))
            .header("Authorization", "Bearer wrong-token")
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 401);
    }

    #[tokio::test]
    async fn upload_succeeds_with_valid_token() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();
        let boundary = "PulsoTestBoundary";

        let resp = client
            .post(format!("{base}/audit"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .header(
                "Content-Type",
                format!("multipart/form-data; boundary={boundary}"),
            )
            .body(csv_multipart_body(boundary, &sample_csv()))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 200);
        let body: serde_json::Value = resp.json().await.unwrap();
        let audit_id = body["audit_id"].as_str().expect("audit_id present");
        assert!(body["result"]["summary"]["total_onts"].as_u64().unwrap() == 5);

        // Result is retrievable with the token…
        let resp = client
            .get(format!("{base}/audit/{audit_id}"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 200);

        // …but not without it.
        let resp = client
            .get(format!("{base}/audit/{audit_id}"))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 401);
    }

    #[tokio::test]
    async fn upload_response_includes_import_report() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();
        let boundary = "PulsoTestBoundary";

        // Snapshot export (no timestamp column) with one bad row and one
        // unrecognized status value.
        let csv = "ont_serial,pon_port,rx_power_dbm,status,distance\n\
                   ADTN-001,CTP-0/1,-21.0,online,1000\n\
                   ADTN-002,CTP-0/1,-22.0,weird-status,1100\n\
                   ,CTP-0/1,-23.0,online,1200\n\
                   ADTN-004,CTP-0/1,-24.0,offline,1300\n\
                   ADTN-005,CTP-0/1,-20.5,online,900\n";
        let resp = client
            .post(format!("{base}/audit"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .header(
                "Content-Type",
                format!("multipart/form-data; boundary={boundary}"),
            )
            .body(csv_multipart_body(boundary, csv))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 200);
        let body: serde_json::Value = resp.json().await.unwrap();

        let report = &body["result"]["import_report"];
        assert!(!report.is_null(), "import_report must be in the response");
        assert_eq!(report["rows_ok"], 4);
        assert_eq!(report["rows_skipped"], 1);
        assert_eq!(report["snapshot_mode"], true);
        assert_eq!(report["unknown_statuses"], 1);
        assert_eq!(report["delimiter"], ",");

        // Skip samples are capped and never leak filesystem paths.
        let samples = report["skip_samples"].as_array().unwrap();
        assert!(samples.len() <= 5);
        for s in samples {
            let s = s.as_str().unwrap();
            assert!(!s.contains('/'), "skip sample leaks a path: {s}");
        }

        // Unknown-status ONT is counted separately, and totals reconcile.
        let summary = &body["result"]["summary"];
        assert_eq!(summary["unknown"], 1);
        assert_eq!(
            summary["total_onts"].as_u64().unwrap(),
            summary["online"].as_u64().unwrap()
                + summary["offline"].as_u64().unwrap()
                + summary["unknown"].as_u64().unwrap()
        );
    }

    #[tokio::test]
    async fn authed_get_of_unknown_id_is_404_not_401() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();
        let resp = client
            .get(format!("{base}/audit/does-not-exist"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 404);
    }

    // ── Body limits ─────────────────────────────────────────────────────

    #[tokio::test]
    async fn oversized_body_rejected_with_413() {
        let mut opts = test_options();
        opts.body_limit_bytes = 1024; // 1 KB limit
        let base = spawn_server(&opts).await;
        let client = reqwest::Client::new();
        let boundary = "PulsoTestBoundary";

        let big_csv = format!(
            "timestamp,ont_serial,pon_port,rx_power_dbm,status,distance\n{}",
            "2026-03-01 08:00:00,ADTN-000,CTP-0/1,-22.0,online,1000\n".repeat(200)
        );
        let resp = client
            .post(format!("{base}/audit"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .header(
                "Content-Type",
                format!("multipart/form-data; boundary={boundary}"),
            )
            .body(csv_multipart_body(boundary, &big_csv))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 413);
        let body: serde_json::Value = resp.json().await.unwrap();
        assert_eq!(body["error"], "payload_too_large");
    }

    // ── Error hygiene ───────────────────────────────────────────────────

    #[tokio::test]
    async fn parse_error_does_not_leak_temp_paths() {
        let base = spawn_server(&test_options()).await;
        let client = reqwest::Client::new();
        let boundary = "PulsoTestBoundary";

        // Unknown-vendor CSV → parse error
        let resp = client
            .post(format!("{base}/audit"))
            .header("Authorization", format!("Bearer {TEST_TOKEN}"))
            .header(
                "Content-Type",
                format!("multipart/form-data; boundary={boundary}"),
            )
            .body(csv_multipart_body(boundary, "col_a,col_b\n1,2\n"))
            .send()
            .await
            .unwrap();
        assert_eq!(resp.status(), 400);
        let text = resp.text().await.unwrap();
        assert!(!text.contains("/tmp"), "response leaks temp path: {text}");
        assert!(!text.contains(".tmp"), "response leaks temp file: {text}");
    }

    // ── Result retention ────────────────────────────────────────────────

    fn dummy_result(n: usize) -> AuditResult {
        AuditResult {
            summary: crate::audit::AuditSummary {
                total_onts: n,
                total_readings: n,
                analysis_period_days: 1,
                health_score: 100,
                online: n,
                offline: 0,
                unknown: 0,
                avg_rx_dbm: -22.0,
                worst_rx_dbm: -22.0,
            },
            import_report: None,
            faults: json!([]),
            ghosts: json!([]),
            capacity: json!([]),
            flapping: json!([]),
            weather_correlation: json!([]),
            reflectance: json!([]),
            optical_budget: json!([]),
            sfp_health: json!([]),
            churn_risk: json!([]),
            tickets: json!([]),
            diagnostics: json!([]),
            impact: json!(null),
            onts: json!([]),
        }
    }

    #[test]
    fn result_store_evicts_after_ttl() {
        let mut store = ResultStore::new(Duration::from_millis(10), 100);
        store.insert("a".into(), dummy_result(1));
        assert!(store.get("a").is_some(), "fresh result should be readable");

        std::thread::sleep(Duration::from_millis(30));
        assert!(store.get("a").is_none(), "expired result must not be served");

        store.evict_expired();
        assert_eq!(store.len(), 0, "expired result must be evicted");
    }

    #[test]
    fn result_store_caps_count_and_evicts_oldest() {
        let mut store = ResultStore::new(Duration::from_secs(3600), 3);
        for i in 0..5 {
            store.insert(format!("id-{i}"), dummy_result(i));
            // Instant has coarse resolution on some platforms; keep ordering distinct.
            std::thread::sleep(Duration::from_millis(2));
        }
        assert_eq!(store.len(), 3, "store must not exceed max_results");
        assert!(store.get("id-0").is_none(), "oldest must be evicted");
        assert!(store.get("id-1").is_none(), "second-oldest must be evicted");
        assert!(store.get("id-4").is_some(), "newest must be retained");
    }

    #[test]
    fn token_comparison_matches_and_rejects() {
        let hash: [u8; 32] = Sha256::digest(TEST_TOKEN.as_bytes()).into();
        assert!(token_matches(TEST_TOKEN, &hash));
        assert!(!token_matches("test-token-1235", &hash));
        assert!(!token_matches("", &hash));
        assert!(!token_matches(&format!("{TEST_TOKEN} "), &hash));
    }
}
