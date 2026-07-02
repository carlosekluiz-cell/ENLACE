// SPDX-License-Identifier: Apache-2.0
// Transport: Pulso Cloud HTTPS + local SQLite buffer
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tracing::{debug, info, warn};
use crate::config::CloudConfig;
use crate::vendors::OltData;
use crate::mikrotik::MikrotikData;
use crate::diagnostics::OltDiagnostics;
use crate::predictions::Predictions;
use crate::tr069::CpeDevice;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelemetryPayload {
    pub agent_id: String,
    pub agent_version: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub olts: Vec<OltData>,
    pub mikrotiks: Vec<MikrotikData>,
    pub diagnostics: Vec<OltDiagnostics>,
    pub predictions: Vec<Predictions>,
    pub radius_summary: Option<RadiusSummary>,
    pub tr069_devices: Vec<CpeDevice>,
    pub errors: Vec<CollectionError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RadiusSummary {
    pub active_sessions: u32,
    pub sessions_started_last_hour: u32,
    pub sessions_ended_last_hour: u32,
    pub avg_session_duration_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectionError {
    pub source: String,
    pub error: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

impl TelemetryPayload {
    pub fn new(agent_id: &str) -> Self {
        Self {
            agent_id: agent_id.into(),
            agent_version: env!("CARGO_PKG_VERSION").into(),
            timestamp: chrono::Utc::now(),
            olts: vec![],
            mikrotiks: vec![],
            diagnostics: vec![],
            predictions: vec![],
            radius_summary: None,
            tr069_devices: vec![],
            errors: vec![],
        }
    }
    pub fn add_olt(&mut self, d: OltData) { self.olts.push(d); }
    pub fn add_mikrotik(&mut self, d: MikrotikData) { self.mikrotiks.push(d); }
    pub fn add_diagnostics(&mut self, d: OltDiagnostics) { self.diagnostics.push(d); }
    pub fn add_predictions(&mut self, d: Predictions) { self.predictions.push(d); }
    pub fn add_radius(&mut self, s: RadiusSummary) { self.radius_summary = Some(s); }
    pub fn add_tr069(&mut self, devices: Vec<CpeDevice>) { self.tr069_devices = devices; }
    pub fn add_error(&mut self, src: &str, err: String) {
        self.errors.push(CollectionError {
            source: src.into(), error: err, timestamp: chrono::Utc::now(),
        });
    }
    pub fn olt_count(&self) -> usize { self.olts.len() }
    pub fn mikrotik_count(&self) -> usize { self.mikrotiks.len() }
    pub fn total_onts(&self) -> usize { self.olts.iter().map(|o| o.onts.len()).sum() }
}

/// Caps for the offline telemetry buffer. When any cap is exceeded the OLDEST
/// buffered payloads are evicted first (an eviction counter is surfaced in
/// logs and via `eviction_count()`).
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct BufferLimits {
    /// Maximum number of buffered telemetry payload rows (default: 1,000,000)
    #[serde(default = "default_buffer_max_rows")]
    pub max_rows: u64,
    /// Maximum total bytes of buffered payload JSON (default: 512 MiB)
    #[serde(default = "default_buffer_max_bytes")]
    pub max_bytes: u64,
    /// Maximum age of a buffered payload in days (default: 7)
    #[serde(default = "default_buffer_max_age_days")]
    pub max_age_days: u32,
}

fn default_buffer_max_rows() -> u64 { 1_000_000 }
fn default_buffer_max_bytes() -> u64 { 512 * 1024 * 1024 }
fn default_buffer_max_age_days() -> u32 { 7 }

impl Default for BufferLimits {
    fn default() -> Self {
        Self {
            max_rows: default_buffer_max_rows(),
            max_bytes: default_buffer_max_bytes(),
            max_age_days: default_buffer_max_age_days(),
        }
    }
}

/// Age-based retention for local history tables (signal history, PON
/// utilization, RADIUS sessions, quarantined payloads).
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RetentionConfig {
    /// Days of per-ONT signal history to keep (default: 30)
    #[serde(default = "default_history_days")]
    pub signal_history_days: u32,
    /// Days of PON utilization history to keep (default: 30)
    #[serde(default = "default_history_days")]
    pub utilization_history_days: u32,
    /// Days to keep RADIUS sessions after they stopped (default: 30)
    #[serde(default = "default_history_days")]
    pub radius_closed_session_days: u32,
    /// Days after which never-stopped RADIUS sessions are considered stale
    /// (NAS reboot without Stop) and pruned (default: 30)
    #[serde(default = "default_history_days")]
    pub radius_stale_open_days: u32,
    /// Days to keep quarantined (undeserializable) payloads (default: 30)
    #[serde(default = "default_history_days")]
    pub dead_letter_days: u32,
}

fn default_history_days() -> u32 { 30 }

impl Default for RetentionConfig {
    fn default() -> Self {
        Self {
            signal_history_days: 30,
            utilization_history_days: 30,
            radius_closed_session_days: 30,
            radius_stale_open_days: 30,
            dead_letter_days: 30,
        }
    }
}

/// Rows removed by a `prune_history` pass.
#[derive(Debug, Default)]
pub struct PruneStats {
    pub signal_rows: usize,
    pub utilization_rows: usize,
    pub radius_sessions: usize,
    pub dead_letters: usize,
}

pub struct CloudTransport {
    client: reqwest::Client,
    endpoint: String,
    api_key: String,
    dry_run: bool,
}

impl CloudTransport {
    pub fn new(config: &CloudConfig, dry_run: bool) -> anyhow::Result<Self> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .danger_accept_invalid_certs(!config.verify_tls)
            .gzip(true)
            .build()?;
        Ok(Self {
            client,
            endpoint: config.endpoint.clone(),
            api_key: config.api_key.clone(),
            dry_run,
        })
    }

    pub async fn send(&self, payload: &TelemetryPayload) -> anyhow::Result<()> {
        if self.dry_run {
            println!("{}", serde_json::to_string_pretty(payload)?);
            return Ok(());
        }

        // Retry with exponential backoff (3 attempts)
        let mut delay = std::time::Duration::from_secs(1);
        for attempt in 0..3u32 {
            match self.send_once(payload).await {
                Ok(()) => return Ok(()),
                Err(e) if attempt < 2 => {
                    warn!(attempt = attempt + 1, error = %e, "Cloud send failed, retrying");
                    tokio::time::sleep(delay).await;
                    delay *= 2;
                }
                Err(e) => return Err(e),
            }
        }
        unreachable!()
    }

    async fn send_once(&self, payload: &TelemetryPayload) -> anyhow::Result<()> {
        let resp = self.client
            .post(&self.endpoint)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("X-Agent-Version", env!("CARGO_PKG_VERSION"))
            .json(payload)
            .send()
            .await?;
        if !resp.status().is_success() {
            anyhow::bail!("Cloud returned {}", resp.status());
        }
        Ok(())
    }

    /// Drain the local buffer to the cloud.
    ///
    /// Undeserializable rows (e.g. schema changed across an agent upgrade) are
    /// quarantined into the dead-letter table and flushing CONTINUES — a
    /// single poison row must never wedge the buffer. Send failures abort the
    /// pass (cloud is down); the next flush picks up where this one stopped.
    pub async fn flush_buffer(&self, db: &LocalBuffer) -> anyhow::Result<()> {
        loop {
            let buffered = db.get_buffered_payloads()?;
            if buffered.is_empty() {
                return Ok(());
            }
            debug!(count = buffered.len(), "Flushing buffered payloads");
            for (id, payload_json) in buffered {
                match serde_json::from_str::<TelemetryPayload>(&payload_json) {
                    Ok(payload) => {
                        self.send(&payload).await?;
                        db.delete_buffered(id)?;
                    }
                    Err(e) => {
                        db.quarantine_buffered(id, &e.to_string())?;
                    }
                }
            }
        }
    }
}

/// Spawn the background flusher task. Telemetry writes go to the local buffer
/// (cheap, local SQLite insert); this task drains the buffer to the cloud —
/// including the ~97s worst-case retry backoff — WITHOUT blocking the poll
/// loop.
pub fn spawn_flusher(
    transport: Arc<CloudTransport>,
    db: LocalBuffer,
    interval: std::time::Duration,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut tick = tokio::time::interval(interval);
        tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        info!(interval_secs = interval.as_secs(), "Cloud buffer flusher started");
        loop {
            tick.tick().await;
            if let Err(e) = transport.flush_buffer(&db).await {
                warn!(error = %e, "Background buffer flush failed (will retry)");
            }
        }
    })
}

#[derive(Clone)]
pub struct LocalBuffer {
    path: std::path::PathBuf,
    /// Persistent shared connection (WAL + busy_timeout). One connection
    /// guarded by a mutex avoids the SQLITE_BUSY storms that
    /// connection-per-call caused between the poll loop and the RADIUS task.
    conn: Arc<Mutex<rusqlite::Connection>>,
    limits: BufferLimits,
    evictions: Arc<AtomicU64>,
    quarantines: Arc<AtomicU64>,
}

/// Rows to evict per pass while over the byte cap.
const EVICT_CHUNK: usize = 100;
/// Cap on buffered Elasticsearch retry rows (each row is one NDJSON batch).
const ELASTIC_RETRY_MAX_ROWS: i64 = 10_000;

impl LocalBuffer {
    pub fn open(data_dir: &std::path::Path) -> anyhow::Result<Self> {
        Self::open_with_limits(data_dir, BufferLimits::default())
    }

    pub fn open_with_limits(
        data_dir: &std::path::Path,
        limits: BufferLimits,
    ) -> anyhow::Result<Self> {
        std::fs::create_dir_all(data_dir)?;
        let path = data_dir.join("pulso_buffer.db");
        let conn = rusqlite::Connection::open(&path)?;
        Self::configure_conn(&conn)?;
        conn.execute_batch("
            CREATE TABLE IF NOT EXISTS ont_signal_history (
                serial_number TEXT NOT NULL,
                rx_power_dbm REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (serial_number, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_signal_history_ts ON ont_signal_history(timestamp);
            CREATE TABLE IF NOT EXISTS pon_utilization_history (
                olt_id TEXT NOT NULL,
                port_id TEXT NOT NULL,
                utilization_percent REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (olt_id, port_id, timestamp)
            );
            CREATE INDEX IF NOT EXISTS idx_util_history_ts ON pon_utilization_history(timestamp);
            CREATE TABLE IF NOT EXISTS radius_sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                start_time INTEGER,
                stop_time INTEGER,
                bytes_in INTEGER DEFAULT 0,
                bytes_out INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS telemetry_buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS telemetry_deadletter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                error TEXT NOT NULL,
                quarantined_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS elastic_retry_buffer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS buffer_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        ")?;
        Ok(Self {
            path,
            conn: Arc::new(Mutex::new(conn)),
            limits,
            evictions: Arc::new(AtomicU64::new(0)),
            quarantines: Arc::new(AtomicU64::new(0)),
        })
    }

    fn configure_conn(conn: &rusqlite::Connection) -> anyhow::Result<()> {
        // WAL lets readers and the writer coexist; busy_timeout makes any
        // extra connection (tests, tools) wait instead of erroring SQLITE_BUSY.
        // journal_mode returns a result row, so query it rather than execute.
        let _mode: String = conn.query_row("PRAGMA journal_mode = WAL", [], |r| r.get(0))?;
        conn.execute_batch("PRAGMA synchronous = NORMAL;")?;
        conn.busy_timeout(std::time::Duration::from_secs(5))?;
        Ok(())
    }

    /// Run a closure against the shared persistent connection.
    fn with_conn<T>(
        &self,
        f: impl FnOnce(&rusqlite::Connection) -> anyhow::Result<T>,
    ) -> anyhow::Result<T> {
        let conn = self.conn.lock().expect("buffer connection mutex poisoned");
        f(&conn)
    }

    /// Open an EXTRA connection to the same database (tests/tools only —
    /// production code paths share the persistent connection).
    pub(crate) fn conn(&self) -> anyhow::Result<rusqlite::Connection> {
        let conn = rusqlite::Connection::open(&self.path)?;
        conn.busy_timeout(std::time::Duration::from_secs(5))?;
        Ok(conn)
    }

    pub fn store(&self, payload: &TelemetryPayload) -> anyhow::Result<()> {
        let json = serde_json::to_string(payload)?;
        self.with_conn(|conn| {
            conn.execute(
                "INSERT INTO telemetry_buffer (payload) VALUES (?1)",
                rusqlite::params![json],
            )?;
            Ok(())
        })?;
        self.enforce_limits()
    }

    /// Enforce row/byte/age caps on the telemetry buffer, evicting oldest first.
    fn enforce_limits(&self) -> anyhow::Result<()> {
        let evicted = self.with_conn(|conn| {
            let mut evicted = 0usize;

            // Age cap
            evicted += conn.execute(
                "DELETE FROM telemetry_buffer WHERE created_at < datetime('now', ?1)",
                rusqlite::params![format!("-{} days", self.limits.max_age_days)],
            )?;

            // Row cap
            let rows: i64 = conn.query_row(
                "SELECT COUNT(*) FROM telemetry_buffer", [], |r| r.get(0),
            )?;
            if rows as u64 > self.limits.max_rows {
                let excess = rows as u64 - self.limits.max_rows;
                evicted += conn.execute(
                    "DELETE FROM telemetry_buffer WHERE id IN (
                         SELECT id FROM telemetry_buffer ORDER BY id LIMIT ?1
                     )",
                    rusqlite::params![excess as i64],
                )?;
            }

            // Byte cap — evict oldest in chunks until under the cap
            loop {
                let bytes: i64 = conn.query_row(
                    "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM telemetry_buffer",
                    [], |r| r.get(0),
                )?;
                if bytes as u64 <= self.limits.max_bytes {
                    break;
                }
                let n = conn.execute(
                    "DELETE FROM telemetry_buffer WHERE id IN (
                         SELECT id FROM telemetry_buffer ORDER BY id LIMIT ?1
                     )",
                    rusqlite::params![EVICT_CHUNK as i64],
                )?;
                if n == 0 {
                    break;
                }
                evicted += n;
            }

            Ok(evicted)
        })?;

        if evicted > 0 {
            let total = self.evictions.fetch_add(evicted as u64, Ordering::Relaxed)
                + evicted as u64;
            warn!(
                evicted,
                total_evicted = total,
                max_rows = self.limits.max_rows,
                max_bytes = self.limits.max_bytes,
                max_age_days = self.limits.max_age_days,
                "Offline buffer over capacity — evicted oldest payloads"
            );
        }
        Ok(())
    }

    /// Total payload rows evicted by cap enforcement since startup.
    pub fn eviction_count(&self) -> u64 {
        self.evictions.load(Ordering::Relaxed)
    }

    pub fn get_buffered_payloads(&self) -> anyhow::Result<Vec<(i64, String)>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare_cached(
                "SELECT id, payload FROM telemetry_buffer ORDER BY id LIMIT 100"
            )?;
            let rows = stmt.query_map([], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            })?;
            Ok(rows.filter_map(|r| r.ok()).collect())
        })
    }

    pub fn delete_buffered(&self, id: i64) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "DELETE FROM telemetry_buffer WHERE id = ?1",
                rusqlite::params![id],
            )?;
            Ok(())
        })
    }

    /// Move an undeserializable buffered payload to the dead-letter table so
    /// it can never wedge flushing again (poison-pill protection).
    pub fn quarantine_buffered(&self, id: i64, error: &str) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "INSERT INTO telemetry_deadletter (payload, error)
                 SELECT payload, ?2 FROM telemetry_buffer WHERE id = ?1",
                rusqlite::params![id, error],
            )?;
            conn.execute(
                "DELETE FROM telemetry_buffer WHERE id = ?1",
                rusqlite::params![id],
            )?;
            Ok(())
        })?;
        let total = self.quarantines.fetch_add(1, Ordering::Relaxed) + 1;
        warn!(
            id,
            error,
            total_quarantined = total,
            "Quarantined undeserializable buffered payload (dead-letter)"
        );
        Ok(())
    }

    /// Number of payloads currently in the dead-letter table.
    pub fn dead_letter_count(&self) -> anyhow::Result<u64> {
        self.with_conn(|conn| {
            let n: i64 = conn.query_row(
                "SELECT COUNT(*) FROM telemetry_deadletter", [], |r| r.get(0),
            )?;
            Ok(n as u64)
        })
    }

    // Elasticsearch retry buffer — failed bulk batches are re-queued here by
    // ElasticOutput and drained by `ElasticOutput::flush_retry_buffer`.
    pub fn store_elastic_retry(&self, ndjson: &str) -> anyhow::Result<()> {
        let evicted = self.with_conn(|conn| {
            conn.execute(
                "INSERT INTO elastic_retry_buffer (body) VALUES (?1)",
                rusqlite::params![ndjson],
            )?;
            let rows: i64 = conn.query_row(
                "SELECT COUNT(*) FROM elastic_retry_buffer", [], |r| r.get(0),
            )?;
            let mut evicted = 0usize;
            if rows > ELASTIC_RETRY_MAX_ROWS {
                evicted = conn.execute(
                    "DELETE FROM elastic_retry_buffer WHERE id IN (
                         SELECT id FROM elastic_retry_buffer ORDER BY id LIMIT ?1
                     )",
                    rusqlite::params![rows - ELASTIC_RETRY_MAX_ROWS],
                )?;
            }
            Ok(evicted)
        })?;
        if evicted > 0 {
            let total = self.evictions.fetch_add(evicted as u64, Ordering::Relaxed)
                + evicted as u64;
            warn!(evicted, total_evicted = total,
                  "Elasticsearch retry buffer over capacity — evicted oldest batches");
        }
        Ok(())
    }

    pub fn get_elastic_retries(&self, limit: usize) -> anyhow::Result<Vec<(i64, String)>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare_cached(
                "SELECT id, body FROM elastic_retry_buffer ORDER BY id LIMIT ?1"
            )?;
            let rows = stmt.query_map(rusqlite::params![limit as i64], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            })?;
            Ok(rows.filter_map(|r| r.ok()).collect())
        })
    }

    pub fn delete_elastic_retry(&self, id: i64) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "DELETE FROM elastic_retry_buffer WHERE id = ?1",
                rusqlite::params![id],
            )?;
            Ok(())
        })
    }

    pub fn store_signal_history(&self, onts: &[crate::vendors::OntData]) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            let now = chrono::Utc::now().timestamp();
            let mut stmt = conn.prepare_cached(
                "INSERT OR REPLACE INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES (?1, ?2, ?3)"
            )?;
            for ont in onts {
                if let Some(rx) = ont.rx_power_dbm {
                    stmt.execute(rusqlite::params![ont.serial_number, rx, now])?;
                }
            }
            Ok(())
        })
    }

    pub fn store_pon_utilization(&self, olt_id: &str, ports: &[crate::vendors::PonPortData]) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            let now = chrono::Utc::now().timestamp();
            let mut stmt = conn.prepare_cached(
                "INSERT OR REPLACE INTO pon_utilization_history (olt_id, port_id, utilization_percent, timestamp) VALUES (?1, ?2, ?3, ?4)"
            )?;
            for port in ports {
                stmt.execute(rusqlite::params![olt_id, port.port_id, port.utilization_percent, now])?;
            }
            Ok(())
        })
    }

    pub fn get_ont_signal_history(&self, serial: &str, days: u32) -> anyhow::Result<Vec<(i64, f64)>> {
        self.with_conn(|conn| {
            let cutoff = chrono::Utc::now().timestamp() - (days as i64 * 86400);
            let mut stmt = conn.prepare_cached(
                "SELECT timestamp, rx_power_dbm FROM ont_signal_history WHERE serial_number = ?1 AND timestamp > ?2 ORDER BY timestamp"
            )?;
            let rows = stmt.query_map(rusqlite::params![serial, cutoff], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, f64>(1)?))
            })?;
            Ok(rows.filter_map(|r| r.ok()).collect())
        })
    }

    pub fn get_pon_utilization_history(&self, olt_id: &str, port_id: &str, days: u32) -> anyhow::Result<Vec<(i64, f32)>> {
        self.with_conn(|conn| {
            let cutoff = chrono::Utc::now().timestamp() - (days as i64 * 86400);
            let mut stmt = conn.prepare_cached(
                "SELECT timestamp, utilization_percent FROM pon_utilization_history WHERE olt_id = ?1 AND port_id = ?2 AND timestamp > ?3 ORDER BY timestamp"
            )?;
            let rows = stmt.query_map(rusqlite::params![olt_id, port_id, cutoff], |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, f32>(1)?))
            })?;
            Ok(rows.filter_map(|r| r.ok()).collect())
        })
    }

    /// Downsample old signal readings to 1 per hour.
    /// Keeps all readings from the last `keep_hours` hours at full resolution.
    ///
    /// Incremental: a watermark in `buffer_meta` tracks the timestamp up to
    /// which downsampling has already run, so each pass only scans the window
    /// of readings that newly aged past the cutoff — cost no longer grows
    /// with total table size.
    pub fn downsample_old_readings(&self, keep_hours: u32) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            let cutoff = chrono::Utc::now().timestamp() - (keep_hours as i64 * 3600);
            let watermark: i64 = conn
                .query_row(
                    "SELECT value FROM buffer_meta WHERE key = 'downsample_watermark'",
                    [], |r| r.get::<_, String>(0),
                )
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(0);

            if watermark >= cutoff {
                return Ok(()); // nothing newly aged past the cutoff
            }

            conn.execute(
                "DELETE FROM ont_signal_history
                 WHERE timestamp >= ?1 AND timestamp < ?2
                 AND rowid NOT IN (
                     SELECT MAX(rowid)
                     FROM ont_signal_history
                     WHERE timestamp >= ?1 AND timestamp < ?2
                     GROUP BY serial_number, timestamp / 3600
                 )",
                rusqlite::params![watermark, cutoff],
            )?;

            conn.execute(
                "INSERT OR REPLACE INTO buffer_meta (key, value) VALUES ('downsample_watermark', ?1)",
                rusqlite::params![cutoff.to_string()],
            )?;
            Ok(())
        })
    }

    /// Age-based retention pass: prune signal history, PON utilization,
    /// RADIUS sessions (closed past retention, or stale never-stopped), and
    /// old dead-letter payloads.
    pub fn prune_history(&self, retention: &RetentionConfig) -> anyhow::Result<PruneStats> {
        let stats = self.with_conn(|conn| {
            let now = chrono::Utc::now().timestamp();
            let mut stats = PruneStats::default();

            let signal_cutoff = now - retention.signal_history_days as i64 * 86400;
            stats.signal_rows = conn.execute(
                "DELETE FROM ont_signal_history WHERE timestamp < ?1",
                rusqlite::params![signal_cutoff],
            )?;

            let util_cutoff = now - retention.utilization_history_days as i64 * 86400;
            stats.utilization_rows = conn.execute(
                "DELETE FROM pon_utilization_history WHERE timestamp < ?1",
                rusqlite::params![util_cutoff],
            )?;

            let closed_cutoff = now - retention.radius_closed_session_days as i64 * 86400;
            let stale_cutoff = now - retention.radius_stale_open_days as i64 * 86400;
            stats.radius_sessions = conn.execute(
                "DELETE FROM radius_sessions
                 WHERE (stop_time IS NOT NULL AND stop_time < ?1)
                    OR (stop_time IS NULL AND start_time IS NOT NULL AND start_time < ?2)",
                rusqlite::params![closed_cutoff, stale_cutoff],
            )?;

            stats.dead_letters = conn.execute(
                "DELETE FROM telemetry_deadletter WHERE quarantined_at < datetime('now', ?1)",
                rusqlite::params![format!("-{} days", retention.dead_letter_days)],
            )?;

            Ok(stats)
        })?;

        if stats.signal_rows + stats.utilization_rows + stats.radius_sessions + stats.dead_letters > 0 {
            debug!(
                signal_rows = stats.signal_rows,
                utilization_rows = stats.utilization_rows,
                radius_sessions = stats.radius_sessions,
                dead_letters = stats.dead_letters,
                "Pruned aged local history"
            );
        }
        Ok(stats)
    }

    // RADIUS session management
    pub fn radius_session_start(&self, session_id: &str, username: &str) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            let now = chrono::Utc::now().timestamp();
            conn.execute(
                "INSERT OR REPLACE INTO radius_sessions (session_id, username, start_time) VALUES (?1, ?2, ?3)",
                rusqlite::params![session_id, username, now],
            )?;
            Ok(())
        })
    }

    pub fn radius_session_stop(&self, session_id: &str, bytes_in: u64, bytes_out: u64) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            let now = chrono::Utc::now().timestamp();
            conn.execute(
                "UPDATE radius_sessions SET stop_time = ?1, bytes_in = ?2, bytes_out = ?3 WHERE session_id = ?4",
                rusqlite::params![now, bytes_in, bytes_out, session_id],
            )?;
            Ok(())
        })
    }

    pub fn radius_session_interim(&self, session_id: &str, bytes_in: u64, bytes_out: u64) -> anyhow::Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "UPDATE radius_sessions SET bytes_in = ?1, bytes_out = ?2 WHERE session_id = ?3",
                rusqlite::params![bytes_in, bytes_out, session_id],
            )?;
            Ok(())
        })
    }

    pub fn get_radius_summary(&self) -> anyhow::Result<RadiusSummary> {
        self.with_conn(|conn| {
            let hour_ago = chrono::Utc::now().timestamp() - 3600;

            let active: u32 = conn.query_row(
                "SELECT COUNT(*) FROM radius_sessions WHERE stop_time IS NULL",
                [], |r| r.get(0),
            ).unwrap_or(0);

            let started: u32 = conn.query_row(
                "SELECT COUNT(*) FROM radius_sessions WHERE start_time > ?1",
                rusqlite::params![hour_ago], |r| r.get(0),
            ).unwrap_or(0);

            let ended: u32 = conn.query_row(
                "SELECT COUNT(*) FROM radius_sessions WHERE stop_time > ?1",
                rusqlite::params![hour_ago], |r| r.get(0),
            ).unwrap_or(0);

            let avg_duration: u64 = conn.query_row(
                "SELECT COALESCE(AVG(stop_time - start_time), 0) FROM radius_sessions WHERE stop_time IS NOT NULL AND start_time IS NOT NULL",
                [], |r| r.get(0),
            ).unwrap_or(0);

            Ok(RadiusSummary {
                active_sessions: active,
                sessions_started_last_hour: started,
                sessions_ended_last_hour: ended,
                avg_session_duration_secs: avg_duration,
            })
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_cloud_config() -> CloudConfig {
        CloudConfig {
            endpoint: "http://127.0.0.1:9".into(), // never contacted in dry_run
            api_key: "test".into(),
            send_interval_secs: 300,
            verify_tls: false,
        }
    }

    #[test]
    fn test_buffer_store_retrieve_delete() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        let payload = TelemetryPayload::new("test-agent");
        db.store(&payload).unwrap();

        let buffered = db.get_buffered_payloads().unwrap();
        assert_eq!(buffered.len(), 1);

        let (id, _json) = &buffered[0];
        db.delete_buffered(*id).unwrap();

        let after = db.get_buffered_payloads().unwrap();
        assert!(after.is_empty());
    }

    #[tokio::test]
    async fn test_poison_row_quarantined_flush_continues() {
        // A row that no longer deserializes (schema change across an upgrade)
        // must be quarantined — NOT abort the flush forever.
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        db.store(&TelemetryPayload::new("agent-a")).unwrap();
        // Inject a poison row between two good ones
        let conn = db.conn().unwrap();
        conn.execute(
            "INSERT INTO telemetry_buffer (payload) VALUES ('{\"not\": \"a payload\"}')",
            [],
        ).unwrap();
        drop(conn);
        db.store(&TelemetryPayload::new("agent-b")).unwrap();

        // dry_run transport: send() always succeeds without touching network
        let cloud = CloudTransport::new(&make_cloud_config(), true).unwrap();
        cloud.flush_buffer(&db).await.unwrap();

        assert!(
            db.get_buffered_payloads().unwrap().is_empty(),
            "good rows past the poison row must still flush"
        );
        assert_eq!(db.dead_letter_count().unwrap(), 1, "poison row must be dead-lettered");
    }

    #[test]
    fn test_row_cap_evicts_oldest() {
        let dir = tempfile::tempdir().unwrap();
        let limits = BufferLimits { max_rows: 3, ..Default::default() };
        let db = LocalBuffer::open_with_limits(dir.path(), limits).unwrap();

        for i in 0..5 {
            db.store(&TelemetryPayload::new(&format!("agent-{}", i))).unwrap();
        }

        let buffered = db.get_buffered_payloads().unwrap();
        assert_eq!(buffered.len(), 3, "row cap must hold");
        assert_eq!(db.eviction_count(), 2, "eviction counter must track evicted rows");
        // The three NEWEST payloads survive (oldest-first eviction)
        for (i, (_, json)) in buffered.iter().enumerate() {
            let p: TelemetryPayload = serde_json::from_str(json).unwrap();
            assert_eq!(p.agent_id, format!("agent-{}", i + 2));
        }
    }

    #[test]
    fn test_byte_cap_evicts_oldest() {
        let dir = tempfile::tempdir().unwrap();
        let one_payload = serde_json::to_string(&TelemetryPayload::new("agent-0")).unwrap();
        // Cap fits roughly two payloads
        let limits = BufferLimits {
            max_bytes: (one_payload.len() * 2 + 10) as u64,
            ..Default::default()
        };
        let db = LocalBuffer::open_with_limits(dir.path(), limits.clone()).unwrap();

        for i in 0..6 {
            db.store(&TelemetryPayload::new(&format!("agent-{}", i))).unwrap();
        }

        let conn = db.conn().unwrap();
        let bytes: i64 = conn.query_row(
            "SELECT COALESCE(SUM(LENGTH(payload)), 0) FROM telemetry_buffer",
            [], |r| r.get(0),
        ).unwrap();
        assert!(bytes as u64 <= limits.max_bytes, "byte cap must hold: {} bytes", bytes);
        assert!(db.eviction_count() > 0);
    }

    #[test]
    fn test_age_cap_evicts_expired() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        let conn = db.conn().unwrap();
        conn.execute(
            "INSERT INTO telemetry_buffer (payload, created_at) VALUES ('{}', datetime('now', '-10 days'))",
            [],
        ).unwrap();
        drop(conn);

        // Any store() pass enforces the caps
        db.store(&TelemetryPayload::new("fresh")).unwrap();

        let buffered = db.get_buffered_payloads().unwrap();
        assert_eq!(buffered.len(), 1, "10-day-old row must be evicted (7-day default)");
        assert_eq!(db.eviction_count(), 1);
    }

    #[test]
    fn test_signal_history() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        let onts = vec![crate::vendors::OntData {
            serial_number: "TEST-001".into(),
            pon_port: "0/1/0".into(),
            ont_index: 0,
            status: crate::vendors::OntStatus::Online,
            last_down_cause: None, uptime_seconds: None,
            rx_power_dbm: Some(-22.5), tx_power_dbm: None,
            distance_meters: None,
            vendor_id: None, equipment_id: None, firmware_version: None,
            in_octets: None, out_octets: None, eth_speed_mbps: None, extended: None,
            ..Default::default()
        }];

        db.store_signal_history(&onts).unwrap();

        let history = db.get_ont_signal_history("TEST-001", 1).unwrap();
        assert_eq!(history.len(), 1);
        assert!((history[0].1 - (-22.5)).abs() < 0.01);
    }

    #[test]
    fn test_downsample_old_readings() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        // Insert 100 readings over 2 days for one ONT
        let now = chrono::Utc::now().timestamp();
        let conn = db.conn().unwrap();
        for i in 0..100 {
            let ts = now - (48 * 3600) + (i * 1800); // Every 30 min over 2 days
            conn.execute(
                "INSERT OR REPLACE INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES (?1, ?2, ?3)",
                rusqlite::params!["TEST-DS", -22.0 + (i as f64 * 0.01), ts],
            ).unwrap();
        }
        drop(conn);

        let before = db.get_ont_signal_history("TEST-DS", 3).unwrap();
        assert_eq!(before.len(), 100);

        db.downsample_old_readings(24).unwrap();

        let after = db.get_ont_signal_history("TEST-DS", 3).unwrap();
        // Readings older than 24h should be downsampled to 1/hour
        assert!(after.len() < before.len(), "Should have fewer readings after downsample");

        // Second pass is incremental: watermark caught up, nothing changes
        db.downsample_old_readings(24).unwrap();
        let after2 = db.get_ont_signal_history("TEST-DS", 3).unwrap();
        assert_eq!(after.len(), after2.len(), "incremental pass must be a no-op");
    }

    #[test]
    fn test_prune_history_age_based() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        let now = chrono::Utc::now().timestamp();
        let old = now - 60 * 86400; // 60 days ago
        let conn = db.conn().unwrap();
        conn.execute(
            "INSERT INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES ('OLD', -20.0, ?1)",
            rusqlite::params![old],
        ).unwrap();
        conn.execute(
            "INSERT INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES ('NEW', -21.0, ?1)",
            rusqlite::params![now],
        ).unwrap();
        // Closed session 60 days old, stale open session 60 days old, fresh open session
        conn.execute(
            "INSERT INTO radius_sessions (session_id, username, start_time, stop_time) VALUES ('s-old', 'u', ?1, ?1)",
            rusqlite::params![old],
        ).unwrap();
        conn.execute(
            "INSERT INTO radius_sessions (session_id, username, start_time) VALUES ('s-stale', 'u', ?1)",
            rusqlite::params![old],
        ).unwrap();
        conn.execute(
            "INSERT INTO radius_sessions (session_id, username, start_time) VALUES ('s-live', 'u', ?1)",
            rusqlite::params![now],
        ).unwrap();
        drop(conn);

        let stats = db.prune_history(&RetentionConfig::default()).unwrap();
        assert_eq!(stats.signal_rows, 1);
        assert_eq!(stats.radius_sessions, 2, "closed-old and stale-open sessions pruned");

        assert!(db.get_ont_signal_history("OLD", 90).unwrap().is_empty());
        assert_eq!(db.get_ont_signal_history("NEW", 90).unwrap().len(), 1);
        let summary = db.get_radius_summary().unwrap();
        assert_eq!(summary.active_sessions, 1, "live session must survive pruning");
    }

    #[test]
    fn test_elastic_retry_buffer_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let db = LocalBuffer::open(dir.path()).unwrap();

        db.store_elastic_retry("{\"index\":{}}\n{\"doc\":1}\n").unwrap();
        let rows = db.get_elastic_retries(10).unwrap();
        assert_eq!(rows.len(), 1);
        db.delete_elastic_retry(rows[0].0).unwrap();
        assert!(db.get_elastic_retries(10).unwrap().is_empty());
    }
}
