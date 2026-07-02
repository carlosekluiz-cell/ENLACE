// SPDX-License-Identifier: Apache-2.0
// RADIUS Accounting Listener (RFC 2866)
// Tracks PPPoE session start/stop for churn prediction and customer analytics.

use crate::config::RadiusConfig;
use crate::transport::LocalBuffer;
use tracing::{debug, warn, info};

// RADIUS packet codes
const CODE_ACCOUNTING_REQUEST: u8 = 4;
const CODE_ACCOUNTING_RESPONSE: u8 = 5;

// RADIUS attribute types
const ATTR_USER_NAME: u8 = 1;
const ATTR_NAS_IP_ADDRESS: u8 = 4;
const ATTR_ACCT_STATUS_TYPE: u8 = 40;
const ATTR_ACCT_SESSION_ID: u8 = 44;
const ATTR_ACCT_INPUT_OCTETS: u8 = 42;
const ATTR_ACCT_OUTPUT_OCTETS: u8 = 43;
const ATTR_ACCT_SESSION_TIME: u8 = 46;
const ATTR_ACCT_TERMINATE_CAUSE: u8 = 49;

// Acct-Status-Type values
const ACCT_STATUS_START: u32 = 1;
const ACCT_STATUS_STOP: u32 = 2;
const ACCT_STATUS_INTERIM: u32 = 3;

/// RADIUS attribute parsed from a packet
#[derive(Debug)]
struct RadiusAttribute {
    attr_type: u8,
    value: Vec<u8>,
}

/// Parsed RADIUS Accounting-Request
#[derive(Debug)]
struct AccountingRequest {
    identifier: u8,
    authenticator: [u8; 16],
    username: Option<String>,
    status_type: u32,
    session_id: Option<String>,
    input_octets: u64,
    output_octets: u64,
    session_time: u32,
    nas_ip: Option<String>,
}

/// Parse a RADIUS packet from raw bytes (RFC 2865/2866)
fn parse_radius_packet(data: &[u8]) -> Option<AccountingRequest> {
    if data.len() < 20 {
        return None;
    }

    let code = data[0];
    if code != CODE_ACCOUNTING_REQUEST {
        return None;
    }

    let identifier = data[1];
    let length = u16::from_be_bytes([data[2], data[3]]) as usize;
    if length > data.len() || length < 20 {
        return None;
    }

    let mut authenticator = [0u8; 16];
    authenticator.copy_from_slice(&data[4..20]);

    // Parse attributes
    let mut attrs = Vec::new();
    let mut pos = 20;
    while pos < length {
        if pos + 2 > length {
            break;
        }
        let attr_type = data[pos];
        let attr_len = data[pos + 1] as usize;
        if attr_len < 2 || pos + attr_len > length {
            break;
        }
        attrs.push(RadiusAttribute {
            attr_type,
            value: data[pos + 2..pos + attr_len].to_vec(),
        });
        pos += attr_len;
    }

    let mut req = AccountingRequest {
        identifier,
        authenticator,
        username: None,
        status_type: 0,
        session_id: None,
        input_octets: 0,
        output_octets: 0,
        session_time: 0,
        nas_ip: None,
    };

    for attr in &attrs {
        match attr.attr_type {
            ATTR_USER_NAME => {
                req.username = Some(String::from_utf8_lossy(&attr.value).to_string());
            }
            ATTR_ACCT_STATUS_TYPE => {
                if attr.value.len() >= 4 {
                    req.status_type = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]);
                }
            }
            ATTR_ACCT_SESSION_ID => {
                req.session_id = Some(String::from_utf8_lossy(&attr.value).to_string());
            }
            ATTR_ACCT_INPUT_OCTETS => {
                if attr.value.len() >= 4 {
                    req.input_octets = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]) as u64;
                }
            }
            ATTR_ACCT_OUTPUT_OCTETS => {
                if attr.value.len() >= 4 {
                    req.output_octets = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]) as u64;
                }
            }
            ATTR_ACCT_SESSION_TIME => {
                if attr.value.len() >= 4 {
                    req.session_time = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]);
                }
            }
            ATTR_NAS_IP_ADDRESS => {
                if attr.value.len() == 4 {
                    req.nas_ip = Some(format!("{}.{}.{}.{}", attr.value[0], attr.value[1], attr.value[2], attr.value[3]));
                }
            }
            _ => {} // Skip unknown attributes
        }
    }

    Some(req)
}

/// Build Accounting-Response per RFC 2866 Section 3:
/// Response Authenticator = MD5(Code + ID + Length + RequestAuth + Secret)
fn build_accounting_response(identifier: u8, request_auth: &[u8; 16], secret: &[u8]) -> Vec<u8> {
    // MD5 input: Code(1) + Identifier(1) + Length(2) + RequestAuthenticator(16) + Secret
    let mut ctx = md5::Context::new();
    ctx.consume(&[CODE_ACCOUNTING_RESPONSE]);
    ctx.consume(&[identifier]);
    ctx.consume(20u16.to_be_bytes());
    ctx.consume(request_auth);
    ctx.consume(secret);
    let response_auth = ctx.compute();

    let mut pkt = Vec::with_capacity(20);
    pkt.push(CODE_ACCOUNTING_RESPONSE);
    pkt.push(identifier);
    pkt.extend_from_slice(&20u16.to_be_bytes());
    pkt.extend_from_slice(response_auth.as_ref());
    pkt
}

pub async fn listen(config: RadiusConfig, db: LocalBuffer) -> anyhow::Result<()> {
    let addr = format!("{}:{}", config.listen_addr, config.port);
    let socket = tokio::net::UdpSocket::bind(&addr).await?;
    info!(addr = %addr, "RADIUS accounting listener started");

    let mut buf = vec![0u8; 4096];
    loop {
        let (len, src) = match socket.recv_from(&mut buf).await {
            Ok(r) => r,
            Err(e) => {
                warn!(error = %e, "RADIUS recv error");
                continue;
            }
        };

        let packet = &buf[..len];
        let req = match parse_radius_packet(packet) {
            Some(r) => r,
            None => {
                debug!("Ignoring non-Accounting-Request packet from {}", src);
                continue;
            }
        };

        debug!(
            username = ?req.username,
            status = req.status_type,
            session_id = ?req.session_id,
            "RADIUS accounting event"
        );

        // Process the accounting event
        if let (Some(session_id), Some(username)) = (&req.session_id, &req.username) {
            match req.status_type {
                ACCT_STATUS_START => {
                    if let Err(e) = db.radius_session_start(session_id, username) {
                        warn!(error = %e, "Failed to record RADIUS start");
                    }
                }
                ACCT_STATUS_STOP => {
                    if let Err(e) = db.radius_session_stop(session_id, req.input_octets, req.output_octets) {
                        warn!(error = %e, "Failed to record RADIUS stop");
                    }
                }
                ACCT_STATUS_INTERIM => {
                    if let Err(e) = db.radius_session_interim(session_id, req.input_octets, req.output_octets) {
                        warn!(error = %e, "Failed to record RADIUS interim");
                    }
                }
                _ => {
                    debug!(status = req.status_type, "Unknown Acct-Status-Type");
                }
            }
        }

        // Send Accounting-Response
        let response = build_accounting_response(req.identifier, &req.authenticator, config.secret.as_bytes());
        if let Err(e) = socket.send_to(&response, src).await {
            warn!(error = %e, "Failed to send RADIUS response");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_accounting_request() {
        // Build a minimal Accounting-Request packet
        let mut pkt = Vec::new();
        pkt.push(CODE_ACCOUNTING_REQUEST); // code
        pkt.push(42); // identifier
        // Length placeholder (will fill in)
        pkt.push(0); pkt.push(0);
        // Authenticator (16 zeros)
        pkt.extend_from_slice(&[0u8; 16]);

        // Add User-Name attribute
        let username = b"testuser";
        pkt.push(ATTR_USER_NAME);
        pkt.push((2 + username.len()) as u8);
        pkt.extend_from_slice(username);

        // Add Acct-Status-Type = Start (1)
        pkt.push(ATTR_ACCT_STATUS_TYPE);
        pkt.push(6);
        pkt.extend_from_slice(&1u32.to_be_bytes());

        // Add Acct-Session-Id
        let session = b"sess-001";
        pkt.push(ATTR_ACCT_SESSION_ID);
        pkt.push((2 + session.len()) as u8);
        pkt.extend_from_slice(session);

        // Fix length
        let len = pkt.len() as u16;
        pkt[2] = (len >> 8) as u8;
        pkt[3] = (len & 0xFF) as u8;

        let req = parse_radius_packet(&pkt).unwrap();
        assert_eq!(req.identifier, 42);
        assert_eq!(req.username.as_deref(), Some("testuser"));
        assert_eq!(req.status_type, ACCT_STATUS_START);
        assert_eq!(req.session_id.as_deref(), Some("sess-001"));
    }

    #[test]
    fn test_build_accounting_response() {
        let auth = [0u8; 16];
        let secret = b"testing123";
        let resp = build_accounting_response(42, &auth, secret);
        assert_eq!(resp.len(), 20);
        assert_eq!(resp[0], CODE_ACCOUNTING_RESPONSE);
        assert_eq!(resp[1], 42);
        // Response auth must NOT equal request auth (it's an MD5 hash)
        assert_ne!(&resp[4..20], &auth);
        // Verify it's a valid MD5: recompute and compare
        let mut ctx = md5::Context::new();
        ctx.consume(&[5u8]); // code
        ctx.consume(&[42u8]); // identifier
        ctx.consume(20u16.to_be_bytes()); // length
        ctx.consume(&auth); // request authenticator
        ctx.consume(secret);
        let expected = ctx.compute();
        assert_eq!(&resp[4..20], expected.as_ref());
    }
}
