// SPDX-License-Identifier: Apache-2.0
// MikroTik RouterOS API Collector
//
// Protocol: Binary, TCP 8728 (plaintext) or 8729 (TLS)
// Authentication: Username + password (same as Winbox/WebFig)
// All commands are read-only (/print, /monitor, /getall)

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tracing::{debug, warn};
use crate::config::MikrotikConfig;

/// RouterOS API wire protocol connection
struct RouterOsConnection {
    stream: TcpStream,
}

impl RouterOsConnection {
    async fn connect(addr: &str, port: u16) -> anyhow::Result<Self> {
        let stream = tokio::time::timeout(
            std::time::Duration::from_secs(10),
            TcpStream::connect(format!("{}:{}", addr, port)),
        ).await
            .map_err(|_| anyhow::anyhow!("MikroTik connection timeout"))??;
        Ok(Self { stream })
    }

    async fn login(&mut self, user: &str, pass: &str) -> anyhow::Result<()> {
        // RouterOS v6.43+ uses plain login
        self.send_sentence(&["/login", &format!("=name={}", user), &format!("=password={}", pass)]).await?;
        let resp = self.read_sentence().await?;
        if resp.iter().any(|w| w.starts_with("!trap")) {
            anyhow::bail!("MikroTik login failed: {:?}", resp);
        }
        // Might get !done with =ret= (challenge), or just !done
        // For v6.43+ plain auth, just !done means success
        Ok(())
    }

    async fn command(&mut self, cmd: &str) -> anyhow::Result<Vec<HashMap<String, String>>> {
        self.send_sentence(&[cmd]).await?;
        let mut records = Vec::new();

        loop {
            let sentence = self.read_sentence().await?;
            if sentence.is_empty() {
                continue;
            }

            let first = &sentence[0];
            if first == "!done" {
                break;
            } else if first == "!trap" {
                let msg = sentence.iter()
                    .find(|w| w.starts_with("=message="))
                    .map(|w| w.trim_start_matches("=message=").to_string())
                    .unwrap_or_else(|| "Unknown error".into());
                warn!(cmd = cmd, error = %msg, "MikroTik trap");
                break;
            } else if first == "!re" {
                let mut record = HashMap::new();
                for word in &sentence[1..] {
                    if let Some(kv) = word.strip_prefix('=') {
                        if let Some((key, val)) = kv.split_once('=') {
                            record.insert(key.to_string(), val.to_string());
                        }
                    }
                }
                records.push(record);
            }
        }
        Ok(records)
    }

    async fn send_sentence(&mut self, words: &[&str]) -> anyhow::Result<()> {
        for word in words {
            let encoded = Self::encode_word(word);
            self.stream.write_all(&encoded).await?;
        }
        // Empty word terminates sentence
        self.stream.write_all(&[0]).await?;
        self.stream.flush().await?;
        Ok(())
    }

    async fn read_sentence(&mut self) -> anyhow::Result<Vec<String>> {
        let mut words = Vec::new();
        loop {
            let word = self.decode_word().await?;
            if word.is_empty() {
                break;
            }
            words.push(word);
        }
        Ok(words)
    }

    /// Encode word length as RouterOS wire format (1/2/4 byte prefix)
    fn encode_word(word: &str) -> Vec<u8> {
        let len = word.len();
        let mut buf = Vec::new();
        if len < 0x80 {
            buf.push(len as u8);
        } else if len < 0x4000 {
            buf.push(((len >> 8) as u8) | 0x80);
            buf.push((len & 0xFF) as u8);
        } else if len < 0x200000 {
            buf.push(((len >> 16) as u8) | 0xC0);
            buf.push(((len >> 8) & 0xFF) as u8);
            buf.push((len & 0xFF) as u8);
        } else if len < 0x10000000 {
            buf.push(((len >> 24) as u8) | 0xE0);
            buf.push(((len >> 16) & 0xFF) as u8);
            buf.push(((len >> 8) & 0xFF) as u8);
            buf.push((len & 0xFF) as u8);
        } else {
            buf.push(0xF0);
            buf.push(((len >> 24) & 0xFF) as u8);
            buf.push(((len >> 16) & 0xFF) as u8);
            buf.push(((len >> 8) & 0xFF) as u8);
            buf.push((len & 0xFF) as u8);
        }
        buf.extend_from_slice(word.as_bytes());
        buf
    }

    /// Decode one word from the stream
    async fn decode_word(&mut self) -> anyhow::Result<String> {
        let first = self.stream.read_u8().await?;

        let len = if first < 0x80 {
            first as usize
        } else if first < 0xC0 {
            let second = self.stream.read_u8().await?;
            (((first & 0x7F) as usize) << 8) | (second as usize)
        } else if first < 0xE0 {
            let second = self.stream.read_u8().await?;
            let third = self.stream.read_u8().await?;
            (((first & 0x1F) as usize) << 16) | ((second as usize) << 8) | (third as usize)
        } else if first < 0xF0 {
            let second = self.stream.read_u8().await?;
            let third = self.stream.read_u8().await?;
            let fourth = self.stream.read_u8().await?;
            (((first & 0x0F) as usize) << 24) | ((second as usize) << 16) | ((third as usize) << 8) | (fourth as usize)
        } else {
            let b1 = self.stream.read_u8().await?;
            let b2 = self.stream.read_u8().await?;
            let b3 = self.stream.read_u8().await?;
            let b4 = self.stream.read_u8().await?;
            ((b1 as usize) << 24) | ((b2 as usize) << 16) | ((b3 as usize) << 8) | (b4 as usize)
        };

        if len == 0 {
            return Ok(String::new());
        }

        let mut buf = vec![0u8; len];
        self.stream.read_exact(&mut buf).await?;
        Ok(String::from_utf8_lossy(&buf).to_string())
    }
}

pub struct MikrotikCollector {
    config: MikrotikConfig,
    router_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MikrotikData {
    pub router_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub system: SystemInfo,
    pub pppoe_sessions: Vec<PppoeSession>,
    pub pppoe_summary: PppoeSummary,
    pub bgp_sessions: Vec<BgpSession>,
    pub interfaces: Vec<InterfaceData>,
    pub queue_summary: Option<QueueSummary>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemInfo {
    pub board_name: String,
    pub version: String,
    pub cpu_load_percent: u32,
    pub free_memory_bytes: u64,
    pub total_memory_bytes: u64,
    pub free_disk_bytes: u64,
    pub total_disk_bytes: u64,
    pub uptime_seconds: u64,
    pub architecture: String,
    pub cpu_count: u32,
    pub cpu_frequency_mhz: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PppoeSession {
    pub name: String,
    pub caller_id: Option<String>,
    pub address: Option<String>,
    pub uptime: String,
    pub encoding: Option<String>,
    pub service: Option<String>,
    pub interface: String,
    pub rate_limit: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PppoeSummary {
    pub total_active: u32,
    pub total_connecting: u32,
    pub total_disconnecting: u32,
    pub peak_today: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BgpSession {
    pub name: String,
    pub remote_address: String,
    pub remote_as: u32,
    pub state: String,
    pub prefix_count: u32,
    pub uptime: String,
    pub updates_sent: u64,
    pub updates_received: u64,
    pub local_address: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterfaceData {
    pub name: String,
    pub interface_type: String,
    pub running: bool,
    pub tx_byte: u64,
    pub rx_byte: u64,
    pub tx_packet: u64,
    pub rx_packet: u64,
    pub tx_error: u64,
    pub rx_error: u64,
    pub speed: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueueSummary {
    pub total_queues: u32,
    pub active_queues: u32,
    pub total_target_upload_bps: u64,
    pub total_target_download_bps: u64,
}

impl MikrotikCollector {
    pub async fn new(config: &MikrotikConfig) -> anyhow::Result<Self> {
        Ok(Self {
            router_id: format!("mk-{}", config.ip.replace('.', "-")),
            config: config.clone(),
        })
    }

    pub fn router_id(&self) -> &str { &self.router_id }

    async fn connect(&self) -> anyhow::Result<RouterOsConnection> {
        let mut conn = RouterOsConnection::connect(&self.config.ip, self.config.port).await?;
        conn.login(&self.config.username, &self.config.password).await?;
        Ok(conn)
    }

    pub async fn collect(&self) -> anyhow::Result<MikrotikData> {
        let mut conn = self.connect().await?;

        let system = self.collect_system(&mut conn).await?;
        let pppoe_sessions = if self.config.collect_pppoe {
            self.collect_pppoe(&mut conn).await.unwrap_or_default()
        } else {
            Vec::new()
        };
        let bgp_sessions = if self.config.collect_bgp {
            self.collect_bgp(&mut conn).await.unwrap_or_default()
        } else {
            Vec::new()
        };
        let interfaces = if self.config.collect_interfaces {
            self.collect_interfaces(&mut conn).await.unwrap_or_default()
        } else {
            Vec::new()
        };
        let queue_summary = if self.config.collect_queues {
            self.collect_queues(&mut conn).await.ok()
        } else {
            None
        };

        let pppoe_summary = PppoeSummary {
            total_active: pppoe_sessions.len() as u32,
            total_connecting: 0,
            total_disconnecting: 0,
            peak_today: pppoe_sessions.len() as u32,
        };

        Ok(MikrotikData {
            router_id: self.router_id.clone(),
            timestamp: chrono::Utc::now(),
            system, pppoe_sessions, pppoe_summary,
            bgp_sessions, interfaces, queue_summary,
        })
    }

    async fn collect_system(&self, conn: &mut RouterOsConnection) -> anyhow::Result<SystemInfo> {
        let records = conn.command("/system/resource/print").await?;
        let r = records.first().unwrap_or(&HashMap::new()).clone();

        Ok(SystemInfo {
            board_name: r.get("board-name").cloned().unwrap_or_default(),
            version: r.get("version").cloned().unwrap_or_default(),
            cpu_load_percent: r.get("cpu-load").and_then(|v| v.parse().ok()).unwrap_or(0),
            free_memory_bytes: r.get("free-memory").and_then(|v| v.parse().ok()).unwrap_or(0),
            total_memory_bytes: r.get("total-memory").and_then(|v| v.parse().ok()).unwrap_or(0),
            free_disk_bytes: r.get("free-hdd-space").and_then(|v| v.parse().ok()).unwrap_or(0),
            total_disk_bytes: r.get("total-hdd-space").and_then(|v| v.parse().ok()).unwrap_or(0),
            uptime_seconds: parse_mikrotik_uptime(r.get("uptime").map(|s| s.as_str()).unwrap_or("")),
            architecture: r.get("architecture-name").cloned().unwrap_or_default(),
            cpu_count: r.get("cpu-count").and_then(|v| v.parse().ok()).unwrap_or(0),
            cpu_frequency_mhz: r.get("cpu-frequency").and_then(|v| v.parse().ok()).unwrap_or(0),
        })
    }

    async fn collect_pppoe(&self, conn: &mut RouterOsConnection) -> anyhow::Result<Vec<PppoeSession>> {
        let records = conn.command("/ppp/active/print").await?;
        Ok(records.iter().map(|r| PppoeSession {
            name: r.get("name").cloned().unwrap_or_default(),
            caller_id: r.get("caller-id").cloned(),
            address: r.get("address").cloned(),
            uptime: r.get("uptime").cloned().unwrap_or_default(),
            encoding: r.get("encoding").cloned(),
            service: r.get("service").cloned(),
            interface: r.get("interface").cloned().unwrap_or_default(),
            rate_limit: r.get("rate-limit").cloned(),
        }).collect())
    }

    async fn collect_bgp(&self, conn: &mut RouterOsConnection) -> anyhow::Result<Vec<BgpSession>> {
        // Try v7 first, then v6
        let records = match conn.command("/routing/bgp/session/print").await {
            Ok(r) if !r.is_empty() => r,
            _ => conn.command("/routing/bgp/peer/print").await.unwrap_or_default(),
        };

        Ok(records.iter().map(|r| BgpSession {
            name: r.get("name").cloned().unwrap_or_default(),
            remote_address: r.get("remote-address").or(r.get("remote.address")).cloned().unwrap_or_default(),
            remote_as: r.get("remote-as").or(r.get("remote.as")).and_then(|v| v.parse().ok()).unwrap_or(0),
            state: r.get("state").or(r.get("established")).cloned().unwrap_or_else(|| "unknown".into()),
            prefix_count: r.get("prefix-count").and_then(|v| v.parse().ok()).unwrap_or(0),
            uptime: r.get("uptime").cloned().unwrap_or_default(),
            updates_sent: r.get("updates-sent").and_then(|v| v.parse().ok()).unwrap_or(0),
            updates_received: r.get("updates-received").and_then(|v| v.parse().ok()).unwrap_or(0),
            local_address: r.get("local-address").or(r.get("local.address")).cloned(),
        }).collect())
    }

    async fn collect_interfaces(&self, conn: &mut RouterOsConnection) -> anyhow::Result<Vec<InterfaceData>> {
        let records = conn.command("/interface/print").await?;
        Ok(records.iter().map(|r| InterfaceData {
            name: r.get("name").cloned().unwrap_or_default(),
            interface_type: r.get("type").cloned().unwrap_or_default(),
            running: r.get("running").map(|v| v == "true").unwrap_or(false),
            tx_byte: r.get("tx-byte").and_then(|v| v.parse().ok()).unwrap_or(0),
            rx_byte: r.get("rx-byte").and_then(|v| v.parse().ok()).unwrap_or(0),
            tx_packet: r.get("tx-packet").and_then(|v| v.parse().ok()).unwrap_or(0),
            rx_packet: r.get("rx-packet").and_then(|v| v.parse().ok()).unwrap_or(0),
            tx_error: r.get("tx-error").and_then(|v| v.parse().ok()).unwrap_or(0),
            rx_error: r.get("rx-error").and_then(|v| v.parse().ok()).unwrap_or(0),
            speed: r.get("speed").cloned(),
        }).collect())
    }

    async fn collect_queues(&self, conn: &mut RouterOsConnection) -> anyhow::Result<QueueSummary> {
        let records = conn.command("/queue/simple/print").await?;
        let total_queues = records.len() as u32;
        let active_queues = records.iter().filter(|r| r.get("disabled").map(|v| v != "true").unwrap_or(true)).count() as u32;

        Ok(QueueSummary {
            total_queues,
            active_queues,
            total_target_upload_bps: 0,
            total_target_download_bps: 0,
        })
    }
}

/// Parse MikroTik uptime format "47d12h34m56s" → seconds
fn parse_mikrotik_uptime(uptime: &str) -> u64 {
    let mut total = 0u64;
    let mut num = String::new();
    for c in uptime.chars() {
        if c.is_ascii_digit() {
            num.push(c);
        } else {
            let n: u64 = num.parse().unwrap_or(0);
            match c {
                'w' => total += n * 7 * 86400,
                'd' => total += n * 86400,
                'h' => total += n * 3600,
                'm' => total += n * 60,
                's' => total += n,
                _ => {}
            }
            num.clear();
        }
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_decode_word() {
        // Short word
        let encoded = RouterOsConnection::encode_word("/login");
        assert_eq!(encoded[0], 6); // length byte
        assert_eq!(&encoded[1..], b"/login");

        // Empty word
        let encoded = RouterOsConnection::encode_word("");
        assert_eq!(encoded, vec![0]);
    }

    #[test]
    fn test_encode_long_word() {
        let word = "a".repeat(200);
        let encoded = RouterOsConnection::encode_word(&word);
        // 200 >= 0x80, so 2 bytes for length
        assert_eq!(encoded[0], 0x80 | (200 >> 8) as u8);
        assert_eq!(encoded[1], (200 & 0xFF) as u8);
    }

    #[test]
    fn test_parse_uptime() {
        assert_eq!(parse_mikrotik_uptime("47d12h34m56s"), 47 * 86400 + 12 * 3600 + 34 * 60 + 56);
        assert_eq!(parse_mikrotik_uptime("1w2d3h"), 7 * 86400 + 2 * 86400 + 3 * 3600);
        assert_eq!(parse_mikrotik_uptime("5m30s"), 5 * 60 + 30);
    }
}
