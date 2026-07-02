// SPDX-License-Identifier: Apache-2.0
// RADIUS Accounting Listener (RFC 2866)
// Tracks PPPoE session start/stop for churn prediction and customer analytics.
//
// Security: the Request Authenticator of every Accounting-Request is verified
// against the shared secret (RFC 2866 Section 3) and packets that fail are
// silently dropped — otherwise session state would be spoofable by anyone who
// can reach the UDP port.
//
// Throughput: database writes are handed to a dedicated writer task through a
// bounded channel so the UDP recv loop keeps draining even while SQLite is
// busy. If the queue fills, records are dropped (and counted) rather than
// letting the socket buffer overflow silently.

use crate::config::RadiusConfig;
use crate::transport::LocalBuffer;
use tokio::sync::mpsc;
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
// RFC 2869: high-order 32 bits of the octet counters — without these,
// byte counts wrap at 4 GiB.
const ATTR_ACCT_INPUT_GIGAWORDS: u8 = 52;
const ATTR_ACCT_OUTPUT_GIGAWORDS: u8 = 53;

// Acct-Status-Type values
const ACCT_STATUS_START: u32 = 1;
const ACCT_STATUS_STOP: u32 = 2;
const ACCT_STATUS_INTERIM: u32 = 3;

/// Bounded queue between the UDP recv loop and the DB writer task.
const WRITE_QUEUE_DEPTH: usize = 1024;

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

/// Verify the Request Authenticator per RFC 2866 Section 3:
/// MD5(Code + Identifier + Length + 16 zero octets + request attributes + shared secret)
/// must equal the authenticator carried in octets 4..20.
fn verify_request_authenticator(data: &[u8], secret: &[u8]) -> bool {
    if data.len() < 20 {
        return false;
    }
    let length = u16::from_be_bytes([data[2], data[3]]) as usize;
    if length < 20 || length > data.len() {
        return false;
    }

    let mut ctx = md5::Context::new();
    ctx.consume(&data[0..4]); // Code + Identifier + Length
    ctx.consume([0u8; 16]); // Request Authenticator field zeroed
    ctx.consume(&data[20..length]); // attributes
    ctx.consume(secret);
    let expected = ctx.compute();

    // Constant-time-ish comparison (16 bytes, XOR-accumulated)
    expected
        .iter()
        .zip(&data[4..20])
        .fold(0u8, |acc, (a, b)| acc | (a ^ b))
        == 0
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

    let mut input_gigawords: u64 = 0;
    let mut output_gigawords: u64 = 0;

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
            ATTR_ACCT_INPUT_GIGAWORDS => {
                if attr.value.len() >= 4 {
                    input_gigawords = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]) as u64;
                }
            }
            ATTR_ACCT_OUTPUT_GIGAWORDS => {
                if attr.value.len() >= 4 {
                    output_gigawords = u32::from_be_bytes([attr.value[0], attr.value[1], attr.value[2], attr.value[3]]) as u64;
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

    // Combine 32-bit octet counters with their gigawords high halves
    // (RFC 2869 Sections 5.1/5.2): total = gigawords * 2^32 + octets.
    req.input_octets |= input_gigawords << 32;
    req.output_octets |= output_gigawords << 32;

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

/// An accounting record queued for the DB writer task.
#[derive(Debug)]
enum AcctRecord {
    Start { session_id: String, username: String },
    Stop { session_id: String, bytes_in: u64, bytes_out: u64 },
    Interim { session_id: String, bytes_in: u64, bytes_out: u64 },
}

fn record_for(req: &AccountingRequest) -> Option<AcctRecord> {
    let (session_id, username) = match (&req.session_id, &req.username) {
        (Some(s), Some(u)) => (s.clone(), u.clone()),
        _ => return None,
    };
    match req.status_type {
        ACCT_STATUS_START => Some(AcctRecord::Start { session_id, username }),
        ACCT_STATUS_STOP => Some(AcctRecord::Stop {
            session_id,
            bytes_in: req.input_octets,
            bytes_out: req.output_octets,
        }),
        ACCT_STATUS_INTERIM => Some(AcctRecord::Interim {
            session_id,
            bytes_in: req.input_octets,
            bytes_out: req.output_octets,
        }),
        other => {
            debug!(status = other, "Unknown Acct-Status-Type");
            None
        }
    }
}

/// Dedicated writer task: drains the bounded channel and performs the SQLite
/// writes off the UDP recv loop.
async fn writer_task(mut rx: mpsc::Receiver<AcctRecord>, db: LocalBuffer) {
    while let Some(record) = rx.recv().await {
        let result = match &record {
            AcctRecord::Start { session_id, username } => {
                db.radius_session_start(session_id, username)
            }
            AcctRecord::Stop { session_id, bytes_in, bytes_out } => {
                db.radius_session_stop(session_id, *bytes_in, *bytes_out)
            }
            AcctRecord::Interim { session_id, bytes_in, bytes_out } => {
                db.radius_session_interim(session_id, *bytes_in, *bytes_out)
            }
        };
        if let Err(e) = result {
            warn!(error = %e, record = ?record, "Failed to record RADIUS accounting event");
        }
    }
    debug!("RADIUS writer task exiting (channel closed)");
}

pub async fn listen(config: RadiusConfig, db: LocalBuffer) -> anyhow::Result<()> {
    let addr = format!("{}:{}", config.listen_addr, config.port);
    let socket = tokio::net::UdpSocket::bind(&addr).await?;
    info!(addr = %addr, "RADIUS accounting listener started");

    let (tx, rx) = mpsc::channel::<AcctRecord>(WRITE_QUEUE_DEPTH);
    tokio::spawn(writer_task(rx, db));

    let secret = config.secret.as_bytes().to_vec();
    let mut dropped_full: u64 = 0;
    let mut dropped_bad_auth: u64 = 0;

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
        if packet.len() < 20 || packet[0] != CODE_ACCOUNTING_REQUEST {
            debug!("Ignoring non-Accounting-Request packet from {}", src);
            continue;
        }

        // Silently drop spoofed/mis-secreted packets: no state change, no
        // response (RFC 2866 — a packet with an invalid authenticator MUST
        // be silently discarded).
        if !verify_request_authenticator(packet, &secret) {
            dropped_bad_auth += 1;
            if dropped_bad_auth == 1 || dropped_bad_auth % 100 == 0 {
                warn!(
                    src = %src,
                    total_dropped = dropped_bad_auth,
                    "Dropping RADIUS packet with invalid Request Authenticator (wrong shared secret or spoofing)"
                );
            }
            continue;
        }

        let req = match parse_radius_packet(packet) {
            Some(r) => r,
            None => {
                debug!("Ignoring malformed Accounting-Request packet from {}", src);
                continue;
            }
        };

        debug!(
            username = ?req.username,
            status = req.status_type,
            session_id = ?req.session_id,
            "RADIUS accounting event"
        );

        // Hand the record to the writer task — never block the recv loop on
        // SQLite. On a full queue we drop and count rather than stall.
        if let Some(record) = record_for(&req) {
            match tx.try_send(record) {
                Ok(()) => {}
                Err(mpsc::error::TrySendError::Full(_)) => {
                    dropped_full += 1;
                    if dropped_full == 1 || dropped_full % 100 == 0 {
                        warn!(
                            total_dropped = dropped_full,
                            queue_depth = WRITE_QUEUE_DEPTH,
                            "RADIUS write queue full — dropping accounting record"
                        );
                    }
                }
                Err(mpsc::error::TrySendError::Closed(_)) => {
                    warn!("RADIUS writer task gone — accounting record lost");
                }
            }
        }

        // Send Accounting-Response (only for verified requests)
        let response = build_accounting_response(req.identifier, &req.authenticator, &secret);
        if let Err(e) = socket.send_to(&response, src).await {
            warn!(error = %e, "Failed to send RADIUS response");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a raw Accounting-Request with the given attributes and a zeroed
    /// authenticator, fixing up the length field.
    fn build_request(attrs: &[(u8, Vec<u8>)]) -> Vec<u8> {
        let mut pkt = Vec::new();
        pkt.push(CODE_ACCOUNTING_REQUEST); // code
        pkt.push(42); // identifier
        pkt.push(0); pkt.push(0); // length placeholder
        pkt.extend_from_slice(&[0u8; 16]); // authenticator (zeroed)

        for (attr_type, value) in attrs {
            pkt.push(*attr_type);
            pkt.push((2 + value.len()) as u8);
            pkt.extend_from_slice(value);
        }

        let len = pkt.len() as u16;
        pkt[2] = (len >> 8) as u8;
        pkt[3] = (len & 0xFF) as u8;
        pkt
    }

    /// Compute and install a valid Request Authenticator (RFC 2866 §3):
    /// MD5 over the packet with a zeroed authenticator field, plus the secret.
    fn sign_request(pkt: &mut [u8], secret: &[u8]) {
        for b in &mut pkt[4..20] {
            *b = 0;
        }
        let mut ctx = md5::Context::new();
        ctx.consume(&pkt[..]);
        ctx.consume(secret);
        let digest = ctx.compute();
        pkt[4..20].copy_from_slice(digest.as_ref());
    }

    #[test]
    fn test_parse_accounting_request() {
        let pkt = build_request(&[
            (ATTR_USER_NAME, b"testuser".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, 1u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"sess-001".to_vec()),
        ]);

        let req = parse_radius_packet(&pkt).unwrap();
        assert_eq!(req.identifier, 42);
        assert_eq!(req.username.as_deref(), Some("testuser"));
        assert_eq!(req.status_type, ACCT_STATUS_START);
        assert_eq!(req.session_id.as_deref(), Some("sess-001"));
    }

    #[test]
    fn test_gigawords_extend_octet_counters() {
        // 2 input gigawords + 1000 octets = 2 * 2^32 + 1000 bytes; without
        // attrs 52/53 this would have read back as just 1000.
        let pkt = build_request(&[
            (ATTR_USER_NAME, b"heavy-user".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, ACCT_STATUS_STOP.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"sess-gw".to_vec()),
            (ATTR_ACCT_INPUT_OCTETS, 1000u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_INPUT_GIGAWORDS, 2u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_OUTPUT_OCTETS, 500u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_OUTPUT_GIGAWORDS, 1u32.to_be_bytes().to_vec()),
        ]);

        let req = parse_radius_packet(&pkt).unwrap();
        assert_eq!(req.input_octets, 2u64 * (1u64 << 32) + 1000);
        assert_eq!(req.output_octets, (1u64 << 32) + 500);
    }

    #[test]
    fn test_gigawords_attribute_order_independent() {
        // Gigawords attribute arriving BEFORE the octets attribute must
        // combine identically.
        let pkt = build_request(&[
            (ATTR_ACCT_STATUS_TYPE, ACCT_STATUS_STOP.to_be_bytes().to_vec()),
            (ATTR_ACCT_INPUT_GIGAWORDS, 3u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_INPUT_OCTETS, 7u32.to_be_bytes().to_vec()),
        ]);
        let req = parse_radius_packet(&pkt).unwrap();
        assert_eq!(req.input_octets, 3u64 * (1u64 << 32) + 7);
    }

    #[test]
    fn test_request_authenticator_accepts_valid() {
        let secret = b"testing123";
        let mut pkt = build_request(&[
            (ATTR_USER_NAME, b"legit".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, 1u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"sess-ok".to_vec()),
        ]);
        sign_request(&mut pkt, secret);
        assert!(verify_request_authenticator(&pkt, secret));
    }

    #[test]
    fn test_request_authenticator_rejects_spoofed() {
        let secret = b"testing123";

        // 1. Packet signed with the WRONG secret (attacker doesn't know ours)
        let mut spoofed = build_request(&[
            (ATTR_USER_NAME, b"attacker".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, ACCT_STATUS_STOP.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"victim-session".to_vec()),
        ]);
        sign_request(&mut spoofed, b"wrong-secret");
        assert!(
            !verify_request_authenticator(&spoofed, secret),
            "packet signed with the wrong secret must be rejected"
        );

        // 2. Unsigned packet (all-zero authenticator, as the old code accepted)
        let unsigned = build_request(&[
            (ATTR_USER_NAME, b"attacker".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, ACCT_STATUS_STOP.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"victim-session".to_vec()),
        ]);
        assert!(
            !verify_request_authenticator(&unsigned, secret),
            "zero-authenticator packet must be rejected"
        );

        // 3. Validly-signed packet tampered with after signing
        let mut tampered = build_request(&[
            (ATTR_USER_NAME, b"legit".to_vec()),
            (ATTR_ACCT_STATUS_TYPE, 1u32.to_be_bytes().to_vec()),
            (ATTR_ACCT_SESSION_ID, b"sess-t".to_vec()),
        ]);
        sign_request(&mut tampered, secret);
        let last = tampered.len() - 1;
        tampered[last] ^= 0xFF; // flip attribute bytes post-signature
        assert!(
            !verify_request_authenticator(&tampered, secret),
            "packet modified after signing must be rejected"
        );
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
