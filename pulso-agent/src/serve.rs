// SPDX-License-Identifier: Apache-2.0
// HTTP Audit Server
//
// Axum-based HTTP server that accepts CSV uploads via multipart form,
// runs the audit engine, and returns results as JSON.

use crate::audit::AuditResult;
use crate::csv_import;

use axum::{
    extract::{Multipart, Path, State},
    http::StatusCode,
    response::{IntoResponse, Json},
    routing::{get, post},
    Router,
};
use serde_json::json;
use std::collections::HashMap;
use std::io::Write;
use std::sync::{Arc, Mutex};
use tower_http::cors::{Any, CorsLayer};
use tracing::info;
use uuid::Uuid;

#[derive(Clone)]
pub struct AppState {
    pub results: Arc<Mutex<HashMap<String, AuditResult>>>,
}

pub async fn start_server(port: u16) -> anyhow::Result<()> {
    let state = AppState {
        results: Arc::new(Mutex::new(HashMap::new())),
    };

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(health))
        .route("/audit", post(upload_audit))
        .route("/audit/:id", get(get_audit))
        .layer(cors)
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    info!(port = port, "Audit HTTP server starting on {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health() -> &'static str {
    "ok"
}

async fn upload_audit(
    State(state): State<AppState>,
    mut multipart: Multipart,
) -> Result<impl IntoResponse, (StatusCode, Json<serde_json::Value>)> {
    let mut csv_bytes: Option<Vec<u8>> = None;
    let mut vendor: Option<String> = None;

    while let Some(field) = multipart
        .next_field()
        .await
        .map_err(|e| bad_request("multipart_error", &e.to_string()))?
    {
        let name = field.name().unwrap_or("").to_string();
        match name.as_str() {
            "file" | "csv" => {
                let bytes = field
                    .bytes()
                    .await
                    .map_err(|e| bad_request("read_error", &e.to_string()))?;
                csv_bytes = Some(bytes.to_vec());
            }
            "vendor" => {
                let text = field
                    .text()
                    .await
                    .map_err(|e| bad_request("read_error", &e.to_string()))?;
                if !text.is_empty() {
                    vendor = Some(text);
                }
            }
            _ => {}
        }
    }

    let csv_bytes =
        csv_bytes.ok_or_else(|| bad_request("missing_field", "No 'file' or 'csv' field found"))?;

    if csv_bytes.is_empty() {
        return Err(bad_request("empty_file", "Uploaded CSV file is empty"));
    }

    // Write to temp file
    let mut tmp = tempfile::NamedTempFile::new()
        .map_err(|e| internal_error("tempfile_error", &e.to_string()))?;
    tmp.write_all(&csv_bytes)
        .map_err(|e| internal_error("write_error", &e.to_string()))?;

    // Parse CSV
    let readings = csv_import::parse_csv(tmp.path(), vendor.as_deref())
        .map_err(|e| bad_request("csv_parse_error", &e.to_string()))?;

    // Run audit
    let result = crate::audit::run_audit(readings)
        .map_err(|e| internal_error("audit_error", &e.to_string()))?;

    let audit_id = Uuid::new_v4().to_string();

    // Store result
    {
        let mut results = state
            .results
            .lock()
            .map_err(|e| internal_error("lock_error", &e.to_string()))?;
        results.insert(audit_id.clone(), result.clone());
    }

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
    let results = state
        .results
        .lock()
        .map_err(|e| internal_error("lock_error", &e.to_string()))?;

    match results.get(&id) {
        Some(result) => Ok(Json(json!({
            "audit_id": id,
            "result": result,
        }))),
        None => Err((
            StatusCode::NOT_FOUND,
            Json(json!({
                "error": "not_found",
                "message": format!("No audit found with id: {}", id),
            })),
        )),
    }
}

fn bad_request(
    error: &str,
    message: &str,
) -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::BAD_REQUEST,
        Json(json!({
            "error": error,
            "message": message,
        })),
    )
}

fn internal_error(
    error: &str,
    message: &str,
) -> (StatusCode, Json<serde_json::Value>) {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(json!({
            "error": error,
            "message": message,
        })),
    )
}
