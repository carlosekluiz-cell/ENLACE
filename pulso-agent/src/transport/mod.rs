// SPDX-License-Identifier: Apache-2.0
// Transport: Pulso Cloud HTTPS + local SQLite buffer
use serde::{Deserialize, Serialize};
use tracing::{debug, warn};
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

    pub async fn flush_buffer(&self, db: &LocalBuffer) -> anyhow::Result<()> {
        let buffered = db.get_buffered_payloads()?;
        if buffered.is_empty() {
            return Ok(());
        }
        debug!(count = buffered.len(), "Flushing buffered payloads");
        for (id, payload_json) in buffered {
            let payload: TelemetryPayload = serde_json::from_str(&payload_json)?;
            self.send(&payload).await?;
            db.delete_buffered(id)?;
        }
        Ok(())
    }
}

#[derive(Clone)]
pub struct LocalBuffer {
    path: std::path::PathBuf,
}

impl LocalBuffer {
    pub fn open(data_dir: &std::path::Path) -> anyhow::Result<Self> {
        std::fs::create_dir_all(data_dir)?;
        let path = data_dir.join("pulso_buffer.db");
        let conn = rusqlite::Connection::open(&path)?;
        conn.execute_batch("
            CREATE TABLE IF NOT EXISTS ont_signal_history (
                serial_number TEXT NOT NULL,
                rx_power_dbm REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (serial_number, timestamp)
            );
            CREATE TABLE IF NOT EXISTS pon_utilization_history (
                olt_id TEXT NOT NULL,
                port_id TEXT NOT NULL,
                utilization_percent REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                PRIMARY KEY (olt_id, port_id, timestamp)
            );
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
        ")?;
        Ok(Self { path })
    }

    pub(crate) fn conn(&self) -> anyhow::Result<rusqlite::Connection> {
        Ok(rusqlite::Connection::open(&self.path)?)
    }

    pub fn store(&self, payload: &TelemetryPayload) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let json = serde_json::to_string(payload)?;
        conn.execute(
            "INSERT INTO telemetry_buffer (payload) VALUES (?1)",
            rusqlite::params![json],
        )?;
        Ok(())
    }

    pub fn get_buffered_payloads(&self) -> anyhow::Result<Vec<(i64, String)>> {
        let conn = self.conn()?;
        let mut stmt = conn.prepare(
            "SELECT id, payload FROM telemetry_buffer ORDER BY id LIMIT 100"
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
        })?;
        Ok(rows.filter_map(|r| r.ok()).collect())
    }

    pub fn delete_buffered(&self, id: i64) -> anyhow::Result<()> {
        let conn = self.conn()?;
        conn.execute("DELETE FROM telemetry_buffer WHERE id = ?1", rusqlite::params![id])?;
        Ok(())
    }

    pub fn store_signal_history(&self, onts: &[crate::vendors::OntData]) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let now = chrono::Utc::now().timestamp();
        let mut stmt = conn.prepare(
            "INSERT OR REPLACE INTO ont_signal_history (serial_number, rx_power_dbm, timestamp) VALUES (?1, ?2, ?3)"
        )?;
        for ont in onts {
            if let Some(rx) = ont.rx_power_dbm {
                stmt.execute(rusqlite::params![ont.serial_number, rx, now])?;
            }
        }
        Ok(())
    }

    pub fn store_pon_utilization(&self, olt_id: &str, ports: &[crate::vendors::PonPortData]) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let now = chrono::Utc::now().timestamp();
        let mut stmt = conn.prepare(
            "INSERT OR REPLACE INTO pon_utilization_history (olt_id, port_id, utilization_percent, timestamp) VALUES (?1, ?2, ?3, ?4)"
        )?;
        for port in ports {
            stmt.execute(rusqlite::params![olt_id, port.port_id, port.utilization_percent, now])?;
        }
        Ok(())
    }

    pub fn get_ont_signal_history(&self, serial: &str, days: u32) -> anyhow::Result<Vec<(i64, f64)>> {
        let conn = self.conn()?;
        let cutoff = chrono::Utc::now().timestamp() - (days as i64 * 86400);
        let mut stmt = conn.prepare(
            "SELECT timestamp, rx_power_dbm FROM ont_signal_history WHERE serial_number = ?1 AND timestamp > ?2 ORDER BY timestamp"
        )?;
        let rows = stmt.query_map(rusqlite::params![serial, cutoff], |row| {
            Ok((row.get::<_, i64>(0)?, row.get::<_, f64>(1)?))
        })?;
        Ok(rows.filter_map(|r| r.ok()).collect())
    }

    pub fn get_pon_utilization_history(&self, olt_id: &str, port_id: &str, days: u32) -> anyhow::Result<Vec<(i64, f32)>> {
        let conn = self.conn()?;
        let cutoff = chrono::Utc::now().timestamp() - (days as i64 * 86400);
        let mut stmt = conn.prepare(
            "SELECT timestamp, utilization_percent FROM pon_utilization_history WHERE olt_id = ?1 AND port_id = ?2 AND timestamp > ?3 ORDER BY timestamp"
        )?;
        let rows = stmt.query_map(rusqlite::params![olt_id, port_id, cutoff], |row| {
            Ok((row.get::<_, i64>(0)?, row.get::<_, f32>(1)?))
        })?;
        Ok(rows.filter_map(|r| r.ok()).collect())
    }

    /// Downsample old signal readings to 1 per hour.
    /// Keeps all readings from the last `keep_hours` hours at full resolution.
    pub fn downsample_old_readings(&self, keep_hours: u32) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let cutoff = chrono::Utc::now().timestamp() - (keep_hours as i64 * 3600);

        conn.execute_batch(&format!(
            "DELETE FROM ont_signal_history
             WHERE timestamp < {cutoff}
             AND rowid NOT IN (
                 SELECT MAX(rowid)
                 FROM ont_signal_history
                 WHERE timestamp < {cutoff}
                 GROUP BY serial_number, timestamp / 3600
             )"
        ))?;

        Ok(())
    }

    // RADIUS session management
    pub fn radius_session_start(&self, session_id: &str, username: &str) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let now = chrono::Utc::now().timestamp();
        conn.execute(
            "INSERT OR REPLACE INTO radius_sessions (session_id, username, start_time) VALUES (?1, ?2, ?3)",
            rusqlite::params![session_id, username, now],
        )?;
        Ok(())
    }

    pub fn radius_session_stop(&self, session_id: &str, bytes_in: u64, bytes_out: u64) -> anyhow::Result<()> {
        let conn = self.conn()?;
        let now = chrono::Utc::now().timestamp();
        conn.execute(
            "UPDATE radius_sessions SET stop_time = ?1, bytes_in = ?2, bytes_out = ?3 WHERE session_id = ?4",
            rusqlite::params![now, bytes_in, bytes_out, session_id],
        )?;
        Ok(())
    }

    pub fn radius_session_interim(&self, session_id: &str, bytes_in: u64, bytes_out: u64) -> anyhow::Result<()> {
        let conn = self.conn()?;
        conn.execute(
            "UPDATE radius_sessions SET bytes_in = ?1, bytes_out = ?2 WHERE session_id = ?3",
            rusqlite::params![bytes_in, bytes_out, session_id],
        )?;
        Ok(())
    }

    pub fn get_radius_summary(&self) -> anyhow::Result<RadiusSummary> {
        let conn = self.conn()?;
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
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
            in_octets: None, out_octets: None, eth_speed_mbps: None,
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
    }
}
