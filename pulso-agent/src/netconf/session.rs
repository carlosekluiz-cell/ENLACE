// SPDX-License-Identifier: Apache-2.0
// NETCONF 1.0/1.1 Session over SSH (RFC 6241 / RFC 6242)
//
// Uses russh (pure Rust SSH) for transport to NETCONF port 830.
// After SSH handshake, requests "netconf" subsystem, exchanges <hello>
// capabilities, and negotiates framing version (EOM vs chunked).
//
// SSH host keys are verified with trust-on-first-use (TOFU): the first
// connection to a host records its key fingerprint; any later mismatch is a
// hard failure (possible MITM on the management network).

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use tracing::{debug, info, warn};

use super::framing::FrameBuffer;

/// Required BBF YANG capabilities for Adtran SDX PON management
pub const CAP_BBF_XPON: &str = "urn:bbf:yang:bbf-xpon";
pub const CAP_BBF_ONU_STATE: &str = "urn:bbf:yang:bbf-xpon-onu-state";
pub const CAP_NOTIFICATION: &str = "urn:ietf:params:netconf:capability:notification:1.0";
pub const CAP_BASE_11: &str = "urn:ietf:params:netconf:base:1.1";
pub const CAP_BASE_10: &str = "urn:ietf:params:netconf:base:1.0";

// ── Trust-on-first-use host key store ───────────────────────────────────────

/// Outcome of checking a server host key against the persisted store.
#[derive(Debug, Clone, PartialEq)]
pub enum HostKeyVerdict {
    /// Key matches the fingerprint recorded on a previous connection.
    KnownGood,
    /// First connection to this host — fingerprint recorded (or attempted).
    FirstUse { persisted: bool },
    /// Key does NOT match the recorded fingerprint. Possible MITM.
    Mismatch { expected: String, presented: String },
}

/// Persistent store of `host:port → SSH host key fingerprint` pairs.
///
/// File format, one entry per line: `<host>:<port> <key-algo> <sha256-b64>`.
/// Lives under the agent data dir ($PULSO_DATA_DIR, default
/// /var/lib/pulso-agent) next to the offline buffer, overridable with
/// $PULSO_NETCONF_KNOWN_HOSTS.
pub struct HostKeyStore {
    path: PathBuf,
}

impl HostKeyStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self { path: path.into() }
    }

    /// Default store location.
    pub fn default_path() -> PathBuf {
        if let Ok(p) = std::env::var("PULSO_NETCONF_KNOWN_HOSTS") {
            return PathBuf::from(p);
        }
        let data_dir = std::env::var("PULSO_DATA_DIR")
            .unwrap_or_else(|_| "/var/lib/pulso-agent".to_string());
        Path::new(&data_dir).join("netconf_known_hosts")
    }

    /// Check `fingerprint` for `host:port` against the store, recording it on
    /// first use. Never returns Err for I/O problems — an unreadable store
    /// degrades to first-use (with a loud warning), but a genuine fingerprint
    /// mismatch is always reported as `Mismatch`.
    pub fn verify_and_record(
        &self,
        host: &str,
        port: u16,
        algo: &str,
        fingerprint: &str,
    ) -> HostKeyVerdict {
        let entry_key = format!("{}:{}", host, port);

        let existing = std::fs::read_to_string(&self.path).unwrap_or_default();
        for line in existing.lines() {
            let mut parts = line.split_whitespace();
            let (Some(hp), Some(_algo), Some(fp)) = (parts.next(), parts.next(), parts.next())
            else {
                continue;
            };
            if hp == entry_key {
                if fp == fingerprint {
                    return HostKeyVerdict::KnownGood;
                }
                return HostKeyVerdict::Mismatch {
                    expected: fp.to_string(),
                    presented: fingerprint.to_string(),
                };
            }
        }

        // First use — persist the fingerprint (best-effort).
        let persisted = self.append_entry(&entry_key, algo, fingerprint);
        HostKeyVerdict::FirstUse { persisted }
    }

    fn append_entry(&self, entry_key: &str, algo: &str, fingerprint: &str) -> bool {
        if let Some(parent) = self.path.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                warn!(
                    path = %self.path.display(),
                    error = %e,
                    "Cannot create host-key store directory; TOFU fingerprint NOT persisted"
                );
                return false;
            }
        }
        let line = format!("{} {} {}\n", entry_key, algo, fingerprint);
        let result = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
            .and_then(|mut f| std::io::Write::write_all(&mut f, line.as_bytes()));
        match result {
            Ok(()) => true,
            Err(e) => {
                warn!(
                    path = %self.path.display(),
                    error = %e,
                    "Cannot write host-key store; TOFU fingerprint NOT persisted"
                );
                false
            }
        }
    }
}

/// SSH handler for NETCONF — trust-on-first-use host key verification.
/// OLTs use self-generated keys, so there is no CA to chain to: we pin the
/// key seen on the first connection and hard-fail if it ever changes.
struct NetconfHandler {
    host: String,
    port: u16,
    store: HostKeyStore,
}

#[async_trait::async_trait]
impl russh::client::Handler for NetconfHandler {
    type Error = anyhow::Error;

    async fn check_server_key(
        &mut self,
        server_public_key: &russh_keys::key::PublicKey,
    ) -> Result<bool, Self::Error> {
        let algo = server_public_key.name();
        let fingerprint = server_public_key.fingerprint();

        match self
            .store
            .verify_and_record(&self.host, self.port, algo, &fingerprint)
        {
            HostKeyVerdict::KnownGood => Ok(true),
            HostKeyVerdict::FirstUse { persisted } => {
                warn!(
                    host = %self.host,
                    port = self.port,
                    algo = algo,
                    fingerprint = %fingerprint,
                    persisted = persisted,
                    "FIRST CONNECTION to this NETCONF host: trusting and pinning its SSH host key \
                     (trust-on-first-use). Verify this fingerprint against the OLT out-of-band."
                );
                Ok(true)
            }
            HostKeyVerdict::Mismatch { expected, presented } => Err(anyhow::anyhow!(
                "SSH HOST KEY MISMATCH for {}:{} — pinned SHA256:{} but server presented \
                 SHA256:{}. Possible man-in-the-middle on the management network, or the OLT \
                 was re-keyed. Refusing to connect; if the re-key is legitimate, remove the \
                 entry from the host-key store.",
                self.host,
                self.port,
                expected,
                presented
            )),
        }
    }
}

/// A NETCONF session over SSH, supporting both 1.0 (EOM) and 1.1 (chunked) framing.
///
/// Lifecycle:
///   1. `connect()` — SSH handshake, authenticate, open "netconf" subsystem
///   2. Capability exchange — read server <hello>, send ours, negotiate version
///   3. `get()` / `get_config()` / `create_subscription()` — RPC operations
///   4. `close()` — send <close-session> and drop
pub struct NetconfSession {
    channel: russh::Channel<russh::client::Msg>,
    /// True if NETCONF 1.1 chunked framing was negotiated
    use_11: bool,
    message_id: AtomicU32,
    server_capabilities: Vec<String>,
    frames: FrameBuffer,
}

impl NetconfSession {
    /// Connect to a NETCONF server via SSH and perform capability exchange.
    ///
    /// # Arguments
    /// * `host` — OLT management IP
    /// * `port` — NETCONF port (standard: 830)
    /// * `username` — SSH username
    /// * `password` — SSH password (mutually exclusive with key_file)
    /// * `key_file` — Path to SSH private key
    ///
    /// The server host key is checked with trust-on-first-use against
    /// `HostKeyStore::default_path()`.
    pub async fn connect(
        host: &str,
        port: u16,
        username: &str,
        password: Option<&str>,
        key_file: Option<&std::path::Path>,
    ) -> anyhow::Result<Self> {
        let config = russh::client::Config::default();
        let addr = format!("{}:{}", host, port);
        debug!(addr = %addr, "Connecting SSH for NETCONF");

        let handler = NetconfHandler {
            host: host.to_string(),
            port,
            store: HostKeyStore::new(HostKeyStore::default_path()),
        };

        let mut handle = russh::client::connect(Arc::new(config), &*addr, handler).await?;

        // Authenticate — key_file takes priority over password
        let authenticated = if let Some(key_path) = key_file {
            let key = russh_keys::load_secret_key(key_path, None)?;
            handle
                .authenticate_publickey(username, Arc::new(key))
                .await?
        } else if let Some(pw) = password {
            handle.authenticate_password(username, pw).await?
        } else {
            return Err(anyhow::anyhow!(
                "NETCONF requires password or key_file for SSH auth"
            ));
        };

        if !authenticated {
            return Err(anyhow::anyhow!("SSH authentication failed for {}", host));
        }

        // Open session channel and request NETCONF subsystem
        let channel = handle.channel_open_session().await?;
        channel.request_subsystem(true, "netconf").await?;

        let mut session = Self {
            channel,
            use_11: false,
            message_id: AtomicU32::new(1),
            server_capabilities: Vec::new(),
            frames: FrameBuffer::new(),
        };

        // Perform <hello> exchange (always uses 1.0 EOM framing per RFC 6241 §8.1)
        session.capability_exchange().await?;

        Ok(session)
    }

    /// Perform NETCONF capability exchange (<hello> handshake).
    /// The hello is always framed with 1.0 EOM (]]>]]>) per RFC 6241.
    async fn capability_exchange(&mut self) -> anyhow::Result<()> {
        // Read server's <hello> (1.0 EOM framing)
        let server_hello = self.read_message_10().await?;
        self.server_capabilities = super::xml::parse_capabilities(&server_hello)?;

        info!(
            count = self.server_capabilities.len(),
            "NETCONF server capabilities received"
        );

        let has_xpon = self
            .server_capabilities
            .iter()
            .any(|c| c.contains("bbf-xpon"));
        let has_onu_state = self
            .server_capabilities
            .iter()
            .any(|c| c.contains("bbf-xpon-onu-state"));
        let has_notification = self
            .server_capabilities
            .iter()
            .any(|c| c.contains("notification"));

        if has_xpon {
            debug!("Server supports bbf-xpon");
        }
        if has_onu_state {
            debug!("Server supports bbf-xpon-onu-state(s)");
        }
        if has_notification {
            debug!("Server supports notifications");
        }

        // Negotiate version — prefer 1.1 chunked framing if server supports it
        self.use_11 = self.server_capabilities.iter().any(|c| c == CAP_BASE_11);

        // Send our <hello> — always advertise both base:1.0 and base:1.1
        let our_hello = r#"<?xml version="1.0" encoding="UTF-8"?>
<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <capabilities>
    <capability>urn:ietf:params:netconf:base:1.0</capability>
    <capability>urn:ietf:params:netconf:base:1.1</capability>
  </capabilities>
</hello>"#;

        // Hello is always sent with 1.0 EOM framing (RFC 6241 §8.1)
        let encoded = super::framing::encode_netconf10(our_hello);
        self.channel.data(&encoded[..]).await?;

        info!(
            version = if self.use_11 { "1.1" } else { "1.0" },
            "NETCONF session established"
        );

        Ok(())
    }

    /// Read a complete NETCONF message using 1.0 EOM framing (]]>]]> delimiter).
    /// Used during the hello exchange before version negotiation.
    async fn read_message_10(&mut self) -> anyhow::Result<String> {
        loop {
            if let Some(msg) = self.frames.try_decode_10()? {
                return Ok(msg);
            }

            match self.channel.wait().await {
                Some(russh::ChannelMsg::Data { data }) => {
                    self.frames.push(&data);
                }
                Some(russh::ChannelMsg::Eof) => {
                    return Err(anyhow::anyhow!("NETCONF channel EOF during read"));
                }
                None => {
                    return Err(anyhow::anyhow!("NETCONF channel dropped"));
                }
                _ => {} // Ignore ExtendedData, WindowAdjusted, etc.
            }
        }
    }

    /// Read a complete NETCONF message using the negotiated framing.
    async fn read_message(&mut self) -> anyhow::Result<String> {
        loop {
            let decoded = if self.use_11 {
                self.frames.try_decode_11()?
            } else {
                self.frames.try_decode_10()?
            };

            if let Some(msg) = decoded {
                return Ok(msg);
            }

            match self.channel.wait().await {
                Some(russh::ChannelMsg::Data { data }) => {
                    self.frames.push(&data);
                }
                Some(russh::ChannelMsg::Eof) => {
                    return Err(anyhow::anyhow!("NETCONF channel EOF during read"));
                }
                None => {
                    return Err(anyhow::anyhow!("NETCONF channel dropped"));
                }
                _ => {}
            }
        }
    }

    /// Send a NETCONF message using the negotiated framing.
    async fn send_message(&self, msg: &str) -> anyhow::Result<()> {
        let encoded = if self.use_11 {
            super::framing::encode_netconf11(msg)
        } else {
            super::framing::encode_netconf10(msg)
        };
        self.channel.data(&encoded[..]).await?;
        Ok(())
    }

    /// Get the next message-id and increment the counter.
    fn next_message_id(&self) -> u32 {
        self.message_id.fetch_add(1, Ordering::Relaxed)
    }

    /// Check a reply for `<rpc-error>` (namespace-aware — catches prefixed
    /// forms like `<nc:rpc-error>` that a substring check would miss).
    fn check_rpc_error(reply: &str, op: &str) -> anyhow::Result<()> {
        if let Some(summary) = super::xml::rpc_error_summary(reply) {
            return Err(anyhow::anyhow!(
                "NETCONF {} rpc-error: {} (reply: {})",
                op,
                summary,
                truncate(reply, 500)
            ));
        }
        Ok(())
    }

    /// NETCONF `<get>` operation with a subtree filter.
    /// Returns the raw XML `<rpc-reply>`.
    pub async fn get(&mut self, filter: &str) -> anyhow::Result<String> {
        let msg_id = self.next_message_id();
        let rpc = format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="{}">
  <get>
    <filter type="subtree">
      {}
    </filter>
  </get>
</rpc>"#,
            msg_id, filter
        );

        self.send_message(&rpc).await?;
        let reply = self.read_message().await?;
        Self::check_rpc_error(&reply, "<get>")?;

        Ok(reply)
    }

    /// NETCONF `<get-config>` operation.
    pub async fn get_config(&mut self, source: &str, filter: &str) -> anyhow::Result<String> {
        let msg_id = self.next_message_id();
        let rpc = format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="{}">
  <get-config>
    <source><{}/></source>
    <filter type="subtree">
      {}
    </filter>
  </get-config>
</rpc>"#,
            msg_id, source, filter
        );

        self.send_message(&rpc).await?;
        let reply = self.read_message().await?;
        Self::check_rpc_error(&reply, "<get-config>")?;

        Ok(reply)
    }

    /// NETCONF `<create-subscription>` for push notifications (RFC 5277).
    /// Used for onu-state-change and alarm event streams on Adtran SDX.
    pub async fn create_subscription(&mut self, stream: Option<&str>) -> anyhow::Result<()> {
        let msg_id = self.next_message_id();
        let stream_elem = match stream {
            Some(s) => format!("<stream>{}</stream>", s),
            None => String::new(),
        };

        let rpc = format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="{}">
  <create-subscription xmlns="urn:ietf:params:xml:ns:netconf:notification:1.0">
    {}
  </create-subscription>
</rpc>"#,
            msg_id, stream_elem
        );

        self.send_message(&rpc).await?;
        let reply = self.read_message().await?;
        Self::check_rpc_error(&reply, "<create-subscription>")?;

        info!("NETCONF subscription active");
        Ok(())
    }

    /// Read the next notification from the subscription stream.
    pub async fn read_notification(&mut self) -> anyhow::Result<String> {
        self.read_message().await
    }

    /// Send `<close-session>` and shut down cleanly.
    pub async fn close(self) -> anyhow::Result<()> {
        let msg_id = self.next_message_id();
        let rpc = format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0" message-id="{}">
  <close-session/>
</rpc>"#,
            msg_id
        );

        // Best-effort — don't fail if the channel is already closed
        let _ = self.send_message(&rpc).await;
        Ok(())
    }

    /// Check if the server advertised a specific capability (substring match).
    pub fn has_capability(&self, cap: &str) -> bool {
        self.server_capabilities.iter().any(|c| c.contains(cap))
    }

    /// Get all server capabilities.
    pub fn capabilities(&self) -> &[String] {
        &self.server_capabilities
    }

    /// Whether we negotiated NETCONF 1.1 chunked framing.
    pub fn is_netconf_11(&self) -> bool {
        self.use_11
    }
}

/// Truncate a string for error messages — never splits a UTF-8 character
/// (byte-offset slicing like `&s[..500]` panics if byte 500 is mid-codepoint,
/// e.g. on an error-message containing non-ASCII text).
fn truncate(s: &str, max: usize) -> &str {
    if s.len() <= max {
        return s;
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_truncate_ascii() {
        assert_eq!(truncate("hello", 10), "hello");
        assert_eq!(truncate("hello world", 5), "hello");
        assert_eq!(truncate("", 5), "");
    }

    #[test]
    fn test_truncate_multibyte_no_panic() {
        // "aé" — 'é' occupies bytes 1..3; a cut at byte 2 lands mid-codepoint.
        let s = "aébc";
        assert_eq!(truncate(s, 2), "a");
        assert_eq!(truncate(s, 3), "aé");

        // Error message full of multibyte characters (e.g. a Portuguese or
        // Chinese error string from an OLT) — every cut point must be safe.
        let s = "falha crítica: 光纤中断 — ONU não responde";
        for max in 0..=s.len() {
            let t = truncate(s, max); // must not panic
            assert!(t.len() <= max || s.len() <= max);
            assert!(s.starts_with(t));
        }
    }

    #[test]
    fn test_host_key_store_tofu_first_use_then_known_good() {
        let dir = tempfile::tempdir().unwrap();
        let store = HostKeyStore::new(dir.path().join("known_hosts"));

        // First connection: fingerprint is recorded.
        let v = store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "AAAAfingerprint1");
        assert_eq!(v, HostKeyVerdict::FirstUse { persisted: true });

        // Same key again: known good.
        let v = store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "AAAAfingerprint1");
        assert_eq!(v, HostKeyVerdict::KnownGood);
    }

    #[test]
    fn test_host_key_store_mismatch_is_hard_failure() {
        let dir = tempfile::tempdir().unwrap();
        let store = HostKeyStore::new(dir.path().join("known_hosts"));

        store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "AAAAfingerprint1");
        let v = store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "BBBBdifferent");
        assert_eq!(
            v,
            HostKeyVerdict::Mismatch {
                expected: "AAAAfingerprint1".to_string(),
                presented: "BBBBdifferent".to_string(),
            }
        );
    }

    #[test]
    fn test_host_key_store_distinct_hosts_and_ports() {
        let dir = tempfile::tempdir().unwrap();
        let store = HostKeyStore::new(dir.path().join("known_hosts"));

        store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "KEY-A");
        // Different host: its own first-use entry, no clash with 10.0.0.1.
        let v = store.verify_and_record("10.0.0.2", 830, "ssh-ed25519", "KEY-B");
        assert!(matches!(v, HostKeyVerdict::FirstUse { .. }));
        // Same host, different port: also independent.
        let v = store.verify_and_record("10.0.0.1", 2830, "ssh-ed25519", "KEY-C");
        assert!(matches!(v, HostKeyVerdict::FirstUse { .. }));
        // All three keep verifying independently.
        assert_eq!(
            store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "KEY-A"),
            HostKeyVerdict::KnownGood
        );
        assert_eq!(
            store.verify_and_record("10.0.0.2", 830, "ssh-ed25519", "KEY-B"),
            HostKeyVerdict::KnownGood
        );
    }

    #[test]
    fn test_host_key_store_unwritable_path_degrades_loudly_not_fatally() {
        // Store under a path that cannot be created (parent is a file).
        let dir = tempfile::tempdir().unwrap();
        let blocker = dir.path().join("blocker");
        std::fs::write(&blocker, b"x").unwrap();
        let store = HostKeyStore::new(blocker.join("sub").join("known_hosts"));

        let v = store.verify_and_record("10.0.0.1", 830, "ssh-ed25519", "KEY-A");
        // Connection still allowed (first use), but not persisted.
        assert_eq!(v, HostKeyVerdict::FirstUse { persisted: false });
    }
}
