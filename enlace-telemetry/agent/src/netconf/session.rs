// SPDX-License-Identifier: Apache-2.0
// NETCONF 1.0/1.1 Session over SSH (RFC 6241 / RFC 6242)
//
// Uses russh (pure Rust SSH) for transport to NETCONF port 830.
// After SSH handshake, requests "netconf" subsystem, exchanges <hello>
// capabilities, and negotiates framing version (EOM vs chunked).

use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use tracing::{debug, info, warn};

use super::framing;

/// Required BBF YANG capabilities for Adtran SDX 6330 PON management
pub const CAP_BBF_XPON: &str = "urn:bbf:yang:bbf-xpon";
pub const CAP_BBF_ONU_STATE: &str = "urn:bbf:yang:bbf-xpon-onu-state";
pub const CAP_NOTIFICATION: &str = "urn:ietf:params:netconf:capability:notification:1.0";
pub const CAP_BASE_11: &str = "urn:ietf:params:netconf:base:1.1";
pub const CAP_BASE_10: &str = "urn:ietf:params:netconf:base:1.0";

/// SSH handler for NETCONF — accepts all server host keys.
/// OLTs (Adtran SDX, etc.) use self-signed certificates.
struct NetconfHandler;

#[async_trait::async_trait]
impl russh::client::Handler for NetconfHandler {
    type Error = anyhow::Error;

    async fn check_server_key(
        &mut self,
        _server_public_key: &russh_keys::key::PublicKey,
    ) -> Result<bool, Self::Error> {
        // OLTs use self-signed keys — accept unconditionally.
        // Production deployments should pin the server key.
        Ok(true)
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
    read_buf: Vec<u8>,
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

        let mut handle = russh::client::connect(
            Arc::new(config),
            &*addr,
            NetconfHandler,
        )
        .await?;

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
            read_buf: Vec::with_capacity(65536),
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
        self.server_capabilities = super::xml::parse_capabilities(&server_hello);

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
            debug!("Server supports bbf-xpon-onu-state");
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
        let encoded = framing::encode_netconf10(our_hello);
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
            if let Some((msg, consumed)) = framing::decode_netconf10(&self.read_buf) {
                self.read_buf.drain(..consumed);
                return Ok(msg);
            }

            match self.channel.wait().await {
                Some(russh::ChannelMsg::Data { data }) => {
                    self.read_buf.extend_from_slice(&data);
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
                framing::decode_netconf11(&self.read_buf)
            } else {
                framing::decode_netconf10(&self.read_buf)
            };

            if let Some((msg, consumed)) = decoded {
                self.read_buf.drain(..consumed);
                return Ok(msg);
            }

            match self.channel.wait().await {
                Some(russh::ChannelMsg::Data { data }) => {
                    self.read_buf.extend_from_slice(&data);
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
            framing::encode_netconf11(msg)
        } else {
            framing::encode_netconf10(msg)
        };
        self.channel.data(&encoded[..]).await?;
        Ok(())
    }

    /// Get the next message-id and increment the counter.
    fn next_message_id(&self) -> u32 {
        self.message_id.fetch_add(1, Ordering::Relaxed)
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

        if reply.contains("<rpc-error>") || reply.contains("<rpc-error ") {
            return Err(anyhow::anyhow!(
                "NETCONF rpc-error: {}",
                truncate(&reply, 500)
            ));
        }

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

        if reply.contains("<rpc-error>") || reply.contains("<rpc-error ") {
            return Err(anyhow::anyhow!(
                "NETCONF rpc-error: {}",
                truncate(&reply, 500)
            ));
        }

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

        if reply.contains("<rpc-error>") || reply.contains("<rpc-error ") {
            return Err(anyhow::anyhow!(
                "create-subscription failed: {}",
                truncate(&reply, 500)
            ));
        }

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

/// Truncate a string for error messages.
fn truncate(s: &str, max: usize) -> &str {
    if s.len() <= max {
        s
    } else {
        &s[..max]
    }
}
