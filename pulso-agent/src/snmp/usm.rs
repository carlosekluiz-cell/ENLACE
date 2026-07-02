// SPDX-License-Identifier: Apache-2.0
// SNMPv3 User-based Security Model (USM)
//
// Implements the client side of:
//   - RFC 3414: USM message format, engine discovery, time-window sync,
//     key localization (A.2), HMAC-MD5-96 and HMAC-SHA1-96
//   - RFC 7860: HMAC-128-SHA-224 and HMAC-192-SHA-256
//   - RFC 3826: AES-128-CFB privacy (boots|time|salt IV, 64-bit salt counter)
//
// DES-CBC (RFC 3414 §8) is deliberately NOT implemented: it is
// cryptographically obsolete, and configuring it produces a clear error
// instead of a silent downgrade or a mysterious timeout.
//
// Honesty rule: authentication and decryption failures (usmStatsWrongDigests,
// usmStatsDecryptionErrors, HMAC mismatch on responses, garbage plaintext)
// are mapped to explicit errors — never to silent empty results.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::Instant;

use hmac::{Hmac, Mac};
use md5_rc::Md5;
use num_traits::ToPrimitive;
use rasn::types::{Integer, OctetString};
use rasn_snmp::v2::{GetRequest, Pdu, Pdus};
use rasn_snmp::v3::{HeaderData, Message, ScopedPdu, ScopedPduData, USMSecurityParameters};
use sha1::Sha1;
use sha2::{Digest, Sha224, Sha256};

use super::SnmpError;
use crate::config::SnmpV3Config;

/// msgFlags bits (RFC 3412 §6.4)
const FLAG_AUTH: u8 = 0x01;
const FLAG_PRIV: u8 = 0x02;
const FLAG_REPORTABLE: u8 = 0x04;

/// msgMaxSize we advertise (max UDP payload).
const MSG_MAX_SIZE: i64 = 65507;

/// RFC 3414 A.2: the password is stretched by digesting 1MB of repetitions.
const KU_STRETCH_BYTES: usize = 1_048_576;

/// RFC 3414 §11.2: passwords shorter than 8 characters are rejected.
pub const MIN_PASSWORD_LEN: usize = 8;

/// usmStats report OIDs (RFC 3414 §5), instance ".0"
pub(crate) mod report_oids {
    pub const UNSUPPORTED_SEC_LEVELS: &str = "1.3.6.1.6.3.15.1.1.1.0";
    pub const NOT_IN_TIME_WINDOWS: &str = "1.3.6.1.6.3.15.1.1.2.0";
    pub const UNKNOWN_USER_NAMES: &str = "1.3.6.1.6.3.15.1.1.3.0";
    pub const UNKNOWN_ENGINE_IDS: &str = "1.3.6.1.6.3.15.1.1.4.0";
    pub const WRONG_DIGESTS: &str = "1.3.6.1.6.3.15.1.1.5.0";
    pub const DECRYPTION_ERRORS: &str = "1.3.6.1.6.3.15.1.1.6.0";
}

// ---------------------------------------------------------------------------
// Protocols
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthProtocol {
    /// HMAC-MD5-96 (RFC 3414 §6)
    Md5,
    /// HMAC-SHA1-96 (RFC 3414 §7)
    Sha1,
    /// usmHMAC128SHA224AuthProtocol (RFC 7860)
    Sha224,
    /// usmHMAC192SHA256AuthProtocol (RFC 7860)
    Sha256,
}

impl AuthProtocol {
    pub fn parse(s: &str) -> Result<Self, SnmpError> {
        match s.trim().to_ascii_lowercase().as_str() {
            "md5" => Ok(Self::Md5),
            "sha" | "sha1" | "sha-1" => Ok(Self::Sha1),
            "sha224" | "sha-224" => Ok(Self::Sha224),
            "sha256" | "sha-256" => Ok(Self::Sha256),
            other => Err(SnmpError::Config(format!(
                "unsupported SNMPv3 auth_protocol \"{}\" (supported: md5, sha1, sha224, sha256)",
                other
            ))),
        }
    }

    /// Truncated HMAC length in the message (RFC 3414 §6/§7; RFC 7860 §4.1/§4.2).
    pub const fn mac_len(self) -> usize {
        match self {
            Self::Md5 => 12,
            Self::Sha1 => 12,
            Self::Sha224 => 16,
            Self::Sha256 => 24,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PrivProtocol {
    /// AES-128-CFB (RFC 3826)
    Aes128,
}

impl PrivProtocol {
    pub fn parse(s: &str) -> Result<Self, SnmpError> {
        match s.trim().to_ascii_lowercase().as_str() {
            "aes" | "aes128" | "aes-128" => Ok(Self::Aes128),
            "des" | "des-cbc" | "3des" => Err(SnmpError::Config(
                "SNMPv3 priv_protocol DES is not supported (cryptographically obsolete); \
                 use AES: priv_protocol = \"aes128\""
                    .into(),
            )),
            "aes192" | "aes-192" | "aes256" | "aes-256" => Err(SnmpError::Config(format!(
                "SNMPv3 priv_protocol \"{}\" is not implemented (non-standard key expansion \
                 varies by vendor); use the standard priv_protocol = \"aes128\" (RFC 3826)",
                s.trim()
            ))),
            other => Err(SnmpError::Config(format!(
                "unsupported SNMPv3 priv_protocol \"{}\" (supported: aes128)",
                other
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// Key derivation (RFC 3414 A.2)
// ---------------------------------------------------------------------------

fn ku<D: Digest>(password: &[u8]) -> Vec<u8> {
    assert!(!password.is_empty(), "password must not be empty (validated in config)");
    let mut digest = D::new();
    let mut fed = 0usize;
    let mut pw = password.iter().cycle();
    let mut block = [0u8; 64];
    while fed < KU_STRETCH_BYTES {
        for b in block.iter_mut() {
            *b = *pw.next().expect("cycle never ends");
        }
        digest.update(block);
        fed += block.len();
    }
    digest.finalize().to_vec()
}

fn localize<D: Digest>(password: &[u8], engine_id: &[u8]) -> Vec<u8> {
    let ku = ku::<D>(password);
    let mut digest = D::new();
    digest.update(&ku);
    digest.update(engine_id);
    digest.update(&ku);
    digest.finalize().to_vec()
}

/// Password -> Kul (localized key) per RFC 3414 A.2 / RFC 7860 §9.3.
pub fn localized_key(proto: AuthProtocol, password: &[u8], engine_id: &[u8]) -> Vec<u8> {
    match proto {
        AuthProtocol::Md5 => localize::<Md5>(password, engine_id),
        AuthProtocol::Sha1 => localize::<Sha1>(password, engine_id),
        AuthProtocol::Sha224 => localize::<Sha224>(password, engine_id),
        AuthProtocol::Sha256 => localize::<Sha256>(password, engine_id),
    }
}

macro_rules! hmac_full {
    ($digest:ty, $key:expr, $data:expr) => {{
        let mut mac = <Hmac<$digest> as Mac>::new_from_slice($key)
            .expect("HMAC accepts any key length");
        mac.update($data);
        mac.finalize().into_bytes().to_vec()
    }};
}

/// HMAC over `data`, truncated to the protocol's msgAuthenticationParameters length.
pub fn hmac_truncated(proto: AuthProtocol, key: &[u8], data: &[u8]) -> Vec<u8> {
    let mut full = match proto {
        AuthProtocol::Md5 => hmac_full!(Md5, key, data),
        AuthProtocol::Sha1 => hmac_full!(Sha1, key, data),
        AuthProtocol::Sha224 => hmac_full!(Sha224, key, data),
        AuthProtocol::Sha256 => hmac_full!(Sha256, key, data),
    };
    full.truncate(proto.mac_len());
    full
}

// ---------------------------------------------------------------------------
// AES-128-CFB privacy (RFC 3826)
// ---------------------------------------------------------------------------

type Aes128CfbEnc = cfb_mode::Encryptor<aes::Aes128>;
type Aes128CfbDec = cfb_mode::Decryptor<aes::Aes128>;

/// IV = engineBoots (4B BE) || engineTime (4B BE) || salt (8B) — RFC 3826 §3.1.2.1
fn aes_iv(boots: u32, time: u32, salt: &[u8; 8]) -> [u8; 16] {
    let mut iv = [0u8; 16];
    iv[..4].copy_from_slice(&boots.to_be_bytes());
    iv[4..8].copy_from_slice(&time.to_be_bytes());
    iv[8..].copy_from_slice(salt);
    iv
}

pub fn aes128_cfb_encrypt(
    key: &[u8],
    boots: u32,
    time: u32,
    salt: &[u8; 8],
    data: &mut [u8],
) -> Result<(), SnmpError> {
    let iv = aes_iv(boots, time, salt);
    use cfb_mode::cipher::{AsyncStreamCipher, KeyIvInit};
    let enc = Aes128CfbEnc::new_from_slices(&key[..16], &iv)
        .map_err(|e| SnmpError::Protocol(format!("AES key/IV init failed: {}", e)))?;
    enc.encrypt(data);
    Ok(())
}

pub fn aes128_cfb_decrypt(
    key: &[u8],
    boots: u32,
    time: u32,
    salt: &[u8; 8],
    data: &mut [u8],
) -> Result<(), SnmpError> {
    let iv = aes_iv(boots, time, salt);
    use cfb_mode::cipher::{AsyncStreamCipher, KeyIvInit};
    let dec = Aes128CfbDec::new_from_slices(&key[..16], &iv)
        .map_err(|e| SnmpError::Protocol(format!("AES key/IV init failed: {}", e)))?;
    dec.decrypt(data);
    Ok(())
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

/// Discovered authoritative engine state + localized keys.
#[derive(Clone)]
struct Engine {
    engine_id: Vec<u8>,
    boots: u32,
    /// snmpEngineTime at the moment of sync
    time_base: u32,
    synced_at: Instant,
    /// Localized auth key (empty for noAuth)
    auth_key: Vec<u8>,
    /// First 16 bytes of the localized priv key (empty for noPriv)
    priv_key: Vec<u8>,
}

impl Engine {
    /// Extrapolated current snmpEngineTime (RFC 3414 §2.3: the non-authoritative
    /// engine keeps a local notion of the authoritative engine's clock).
    fn current_time(&self) -> u32 {
        self.time_base
            .saturating_add(self.synced_at.elapsed().as_secs().min(u32::MAX as u64) as u32)
    }
}

/// usmStats report classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReportStat {
    UnsupportedSecLevels,
    NotInTimeWindows,
    UnknownUserNames,
    UnknownEngineIds,
    WrongDigests,
    DecryptionErrors,
    Other,
}

impl ReportStat {
    fn from_oid(oid: &str) -> Self {
        match oid {
            report_oids::UNSUPPORTED_SEC_LEVELS => Self::UnsupportedSecLevels,
            report_oids::NOT_IN_TIME_WINDOWS => Self::NotInTimeWindows,
            report_oids::UNKNOWN_USER_NAMES => Self::UnknownUserNames,
            report_oids::UNKNOWN_ENGINE_IDS => Self::UnknownEngineIds,
            report_oids::WRONG_DIGESTS => Self::WrongDigests,
            report_oids::DECRYPTION_ERRORS => Self::DecryptionErrors,
            _ => Self::Other,
        }
    }

    /// Map a report to a human-actionable error (the core honesty rule:
    /// wrong keys must never look like an empty network).
    pub fn to_error(self, oid: &str, user: &str) -> SnmpError {
        let msg = match self {
            Self::WrongDigests => format!(
                "SNMPv3 authentication failed for user \"{}\" (usmStatsWrongDigests): \
                 wrong auth_password or auth_protocol",
                user
            ),
            Self::UnknownUserNames => format!(
                "SNMPv3 user \"{}\" is unknown to the agent (usmStatsUnknownUserNames): \
                 check the username / agent user configuration",
                user
            ),
            Self::DecryptionErrors => format!(
                "agent could not decrypt request for user \"{}\" (usmStatsDecryptionErrors): \
                 wrong priv_password or priv_protocol",
                user
            ),
            Self::UnsupportedSecLevels => format!(
                "security level not accepted for user \"{}\" (usmStatsUnsupportedSecLevels): \
                 the agent user requires a different auth/priv combination",
                user
            ),
            Self::UnknownEngineIds => "agent reports usmStatsUnknownEngineIDs after discovery \
                 (engine ID changed mid-session?)"
                .to_string(),
            Self::NotInTimeWindows => format!(
                "SNMPv3 time-window sync failed for user \"{}\" (usmStatsNotInTimeWindows \
                 persisted after resync)",
                user
            ),
            Self::Other => format!("agent returned SNMPv3 Report {} for user \"{}\"", oid, user),
        };
        SnmpError::Protocol(msg)
    }
}

/// Result of unwrapping a received v3 message.
pub enum V3Reply {
    /// A Response PDU (already authenticated/decrypted as required)
    Response(Pdu),
    /// A Report PDU; on NotInTimeWindows the session has already resynced.
    Report { stat: ReportStat, oid: String },
}

/// Per-target SNMPv3 USM session: user credentials, discovered engine state,
/// localized keys, and the privacy salt counter.
pub struct V3Session {
    user: Vec<u8>,
    auth: Option<(AuthProtocol, Vec<u8>)>,
    /// Privacy password (protocol is always AES-128; DES is rejected at parse)
    privacy: Option<(PrivProtocol, Vec<u8>)>,
    context_name: Vec<u8>,
    engine: Mutex<Option<Engine>>,
    salt: AtomicU64,
}

/// Manual Debug: never print passwords or localized keys.
impl std::fmt::Debug for V3Session {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("V3Session")
            .field("user", &self.user_name())
            .field("level", &self.security_level())
            .finish_non_exhaustive()
    }
}

impl V3Session {
    /// Build a session from config, validating combination coherence.
    /// This is the single source of truth also used by config validation.
    pub fn from_config(cfg: &SnmpV3Config) -> Result<Self, SnmpError> {
        if cfg.username.trim().is_empty() {
            return Err(SnmpError::Config(
                "SNMPv3 requires a non-empty username (snmp.v3.username)".into(),
            ));
        }

        let auth = match (&cfg.auth_protocol, &cfg.auth_password) {
            (Some(proto), Some(pw)) => {
                let proto = AuthProtocol::parse(proto)?;
                if pw.len() < MIN_PASSWORD_LEN {
                    return Err(SnmpError::Config(format!(
                        "SNMPv3 auth_password must be at least {} characters (RFC 3414 §11.2)",
                        MIN_PASSWORD_LEN
                    )));
                }
                Some((proto, pw.as_bytes().to_vec()))
            }
            (None, None) => None,
            (Some(_), None) => {
                return Err(SnmpError::Config(
                    "SNMPv3 auth_protocol is set but auth_password is missing".into(),
                ))
            }
            (None, Some(_)) => {
                return Err(SnmpError::Config(
                    "SNMPv3 auth_password is set but auth_protocol is missing".into(),
                ))
            }
        };

        let privacy = match (&cfg.priv_protocol, &cfg.priv_password) {
            (Some(proto), Some(pw)) => {
                let proto = PrivProtocol::parse(proto)?;
                if pw.len() < MIN_PASSWORD_LEN {
                    return Err(SnmpError::Config(format!(
                        "SNMPv3 priv_password must be at least {} characters (RFC 3414 §11.2)",
                        MIN_PASSWORD_LEN
                    )));
                }
                Some((proto, pw.as_bytes().to_vec()))
            }
            (None, None) => None,
            (Some(_), None) => {
                return Err(SnmpError::Config(
                    "SNMPv3 priv_protocol is set but priv_password is missing".into(),
                ))
            }
            (None, Some(_)) => {
                return Err(SnmpError::Config(
                    "SNMPv3 priv_password is set but priv_protocol is missing".into(),
                ))
            }
        };

        if privacy.is_some() && auth.is_none() {
            return Err(SnmpError::Config(
                "SNMPv3 privacy (authPriv) requires authentication: set auth_protocol \
                 and auth_password as well (priv without auth is not a valid USM level)"
                    .into(),
            ));
        }

        // Random-ish initial salt (RFC 3826 §3.1.2.1 only requires the salt
        // never repeat for the same key; a random start + counter satisfies it).
        let salt0 = uuid::Uuid::new_v4().as_u128() as u64;

        Ok(Self {
            user: cfg.username.as_bytes().to_vec(),
            auth,
            privacy,
            context_name: cfg.context_name.as_bytes().to_vec(),
            engine: Mutex::new(None),
            salt: AtomicU64::new(salt0),
        })
    }

    pub fn user_name(&self) -> String {
        String::from_utf8_lossy(&self.user).into_owned()
    }

    /// "noAuthNoPriv" | "authNoPriv" | "authPriv"
    pub fn security_level(&self) -> &'static str {
        match (&self.auth, &self.privacy) {
            (None, _) => "noAuthNoPriv",
            (Some(_), None) => "authNoPriv",
            (Some(_), Some(_)) => "authPriv",
        }
    }

    fn flags_byte(&self) -> u8 {
        let mut f = FLAG_REPORTABLE;
        if self.auth.is_some() {
            f |= FLAG_AUTH;
        }
        if self.privacy.is_some() {
            f |= FLAG_PRIV;
        }
        f
    }

    pub fn needs_discovery(&self) -> bool {
        self.engine.lock().unwrap().is_none()
    }

    fn next_salt(&self) -> u64 {
        self.salt.fetch_add(1, Ordering::Relaxed)
    }

    /// Install engine state and localize keys. Used after discovery (and by tests).
    pub fn install_engine(&self, engine_id: Vec<u8>, boots: u32, time: u32) {
        let auth_key = self
            .auth
            .as_ref()
            .map(|(proto, pw)| localized_key(*proto, pw, &engine_id))
            .unwrap_or_default();
        let priv_key = match (&self.auth, &self.privacy) {
            (Some((proto, _)), Some((PrivProtocol::Aes128, pw))) => {
                // RFC 3826 §1.2: first 128 bits of the localized key
                let mut k = localized_key(*proto, pw, &engine_id);
                k.truncate(16);
                k
            }
            _ => Vec::new(),
        };
        *self.engine.lock().unwrap() = Some(Engine {
            engine_id,
            boots,
            time_base: time,
            synced_at: Instant::now(),
            auth_key,
            priv_key,
        });
    }

    /// Update boots/time from an authoritative report (notInTimeWindows resync).
    fn resync(&self, boots: u32, time: u32) {
        if let Some(engine) = self.engine.lock().unwrap().as_mut() {
            engine.boots = boots;
            engine.time_base = time;
            engine.synced_at = Instant::now();
        }
    }

    fn engine(&self) -> Result<Engine, SnmpError> {
        self.engine
            .lock()
            .unwrap()
            .clone()
            .ok_or_else(|| SnmpError::Protocol("SNMPv3 engine not discovered yet".into()))
    }

    pub fn engine_id(&self) -> Option<Vec<u8>> {
        self.engine.lock().unwrap().as_ref().map(|e| e.engine_id.clone())
    }

    // -- Message building ---------------------------------------------------

    /// RFC 3414 §4: engine-ID discovery probe — noAuthNoPriv, empty user name,
    /// empty engine ID, empty varbinds.
    pub fn build_discovery(&self, msg_id: u32, request_id: u32) -> Result<Vec<u8>, SnmpError> {
        let scoped = ScopedPdu {
            engine_id: OctetString::default(),
            name: OctetString::default(),
            data: Pdus::GetRequest(GetRequest(Pdu {
                request_id: request_id as i32,
                error_status: 0,
                error_index: 0,
                variable_bindings: vec![],
            })),
        };
        let usm = USMSecurityParameters {
            authoritative_engine_id: OctetString::default(),
            authoritative_engine_boots: 0.into(),
            authoritative_engine_time: 0.into(),
            user_name: OctetString::default(),
            authentication_parameters: OctetString::default(),
            privacy_parameters: OctetString::default(),
        };
        let mut msg = Message {
            version: 3.into(),
            global_data: HeaderData {
                message_id: (msg_id as i64).into(),
                max_size: MSG_MAX_SIZE.into(),
                flags: vec![FLAG_REPORTABLE].into(),
                security_model: 3.into(),
            },
            security_parameters: OctetString::default(),
            scoped_data: ScopedPduData::CleartextPdu(scoped),
        };
        encode_usm(&mut msg, &usm)?;
        encode_msg(&msg)
    }

    /// Absorb the Report answering the discovery probe: capture
    /// msgAuthoritativeEngineID/Boots/Time and localize keys.
    pub fn absorb_discovery(&self, raw: &[u8]) -> Result<(), SnmpError> {
        let msg = decode_msg(raw)?;
        let usm = decode_usm(&msg)?;

        // The discovery answer must be a (cleartext) Report carrying the engine ID.
        match &msg.scoped_data {
            ScopedPduData::CleartextPdu(scoped) => match &scoped.data {
                Pdus::Report(_) => {}
                other => {
                    return Err(SnmpError::Protocol(format!(
                        "SNMPv3 engine discovery expected a Report PDU, got {:?}",
                        std::mem::discriminant(other)
                    )))
                }
            },
            ScopedPduData::EncryptedPdu(_) => {
                return Err(SnmpError::Protocol(
                    "SNMPv3 engine discovery got an encrypted PDU (agent misbehaving)".into(),
                ))
            }
        }

        let engine_id = usm.authoritative_engine_id.to_vec();
        if engine_id.is_empty() {
            return Err(SnmpError::Protocol(
                "SNMPv3 engine discovery: agent returned an empty engine ID".into(),
            ));
        }
        let boots = int_to_u32(&usm.authoritative_engine_boots);
        let time = int_to_u32(&usm.authoritative_engine_time);
        self.install_engine(engine_id, boots, time);
        Ok(())
    }

    /// Wrap a v2 PDU into a fully secured SNMPv3 message at this session's
    /// security level (encrypt if authPriv, then authenticate).
    pub fn wrap(&self, msg_id: u32, pdus: Pdus) -> Result<Vec<u8>, SnmpError> {
        let engine = self.engine()?;
        let engine_time = engine.current_time();

        let scoped = ScopedPdu {
            engine_id: engine.engine_id.clone().into(),
            name: self.context_name.clone().into(),
            data: pdus,
        };

        let (scoped_data, priv_params): (ScopedPduData, Vec<u8>) = if self.privacy.is_some() {
            let mut plaintext = rasn::ber::encode(&scoped)
                .map_err(|e| SnmpError::Protocol(format!("BER encode error: {}", e)))?;
            let salt = self.next_salt().to_be_bytes();
            aes128_cfb_encrypt(&engine.priv_key, engine.boots, engine_time, &salt, &mut plaintext)?;
            (ScopedPduData::EncryptedPdu(plaintext.into()), salt.to_vec())
        } else {
            (ScopedPduData::CleartextPdu(scoped), Vec::new())
        };

        let mac_len = self.auth.as_ref().map(|(p, _)| p.mac_len()).unwrap_or(0);
        let mut usm = USMSecurityParameters {
            authoritative_engine_id: engine.engine_id.clone().into(),
            authoritative_engine_boots: (engine.boots as i64).into(),
            authoritative_engine_time: (engine_time as i64).into(),
            user_name: self.user.clone().into(),
            // Zero-filled placeholder; replaced by the real MAC below (RFC 3414 §6.3.1)
            authentication_parameters: vec![0u8; mac_len].into(),
            privacy_parameters: priv_params.into(),
        };
        let mut msg = Message {
            version: 3.into(),
            global_data: HeaderData {
                message_id: (msg_id as i64).into(),
                max_size: MSG_MAX_SIZE.into(),
                flags: vec![self.flags_byte()].into(),
                security_model: 3.into(),
            },
            security_parameters: OctetString::default(),
            scoped_data,
        };
        encode_usm(&mut msg, &usm)?;
        let mut bytes = encode_msg(&msg)?;

        if let Some((proto, _)) = &self.auth {
            let mac = hmac_truncated(*proto, &engine.auth_key, &bytes);
            usm.authentication_parameters = mac.into();
            encode_usm(&mut msg, &usm)?;
            bytes = encode_msg(&msg)?;
        }
        Ok(bytes)
    }

    /// Unwrap a received v3 message: verify HMAC, decrypt, classify Reports.
    /// On a NotInTimeWindows report the session boots/time are resynced before
    /// returning, so the caller can retry once.
    pub fn unwrap(&self, raw: &[u8], expected_msg_id: u32) -> Result<V3Reply, SnmpError> {
        let msg = decode_msg(raw)?;
        let usm = decode_usm(&msg)?;

        let msg_id = int_to_u32(&msg.global_data.message_id);
        if msg_id != expected_msg_id {
            return Err(SnmpError::Protocol(format!(
                "SNMPv3 msgID mismatch: expected {}, got {}",
                expected_msg_id, msg_id
            )));
        }

        let flags = msg.global_data.flags.first().copied().unwrap_or(0);
        let authenticated = flags & FLAG_AUTH != 0;

        // Verify the HMAC before trusting anything else in the message.
        if authenticated {
            let engine = self.engine()?;
            let proto = self
                .auth
                .as_ref()
                .map(|(p, _)| *p)
                .ok_or_else(|| {
                    SnmpError::Protocol(
                        "agent sent an authenticated SNMPv3 message but no auth is configured"
                            .into(),
                    )
                })?;
            verify_mac(proto, &engine.auth_key, raw, &msg, &usm)?;
        }

        // Decrypt (or take cleartext) the scoped PDU.
        let scoped: ScopedPdu = match &msg.scoped_data {
            ScopedPduData::CleartextPdu(s) => s.clone(),
            ScopedPduData::EncryptedPdu(ct) => {
                if !authenticated {
                    return Err(SnmpError::Protocol(
                        "SNMPv3 message is encrypted but not authenticated (invalid: \
                         priv requires auth)"
                            .into(),
                    ));
                }
                let engine = self.engine()?;
                if engine.priv_key.is_empty() {
                    return Err(SnmpError::Protocol(
                        "agent sent an encrypted SNMPv3 message but privacy is not configured"
                            .into(),
                    ));
                }
                let salt: [u8; 8] = usm
                    .privacy_parameters
                    .as_ref()
                    .try_into()
                    .map_err(|_| {
                        SnmpError::Protocol(format!(
                            "SNMPv3 privacy parameters must be 8 bytes, got {}",
                            usm.privacy_parameters.len()
                        ))
                    })?;
                let boots = int_to_u32(&usm.authoritative_engine_boots);
                let time = int_to_u32(&usm.authoritative_engine_time);
                let mut buf = ct.to_vec();
                aes128_cfb_decrypt(&engine.priv_key, boots, time, &salt, &mut buf)?;
                rasn::ber::decode::<ScopedPdu>(&buf).map_err(|_| {
                    SnmpError::Protocol(
                        "SNMPv3 decryption produced garbage — wrong priv_password or \
                         priv_protocol (check credentials; refusing to return empty data)"
                            .into(),
                    )
                })?
            }
        };

        match scoped.data {
            Pdus::Response(resp) => {
                // Never accept a downgraded (unauthenticated) response when
                // authentication is configured.
                if self.auth.is_some() && !authenticated {
                    return Err(SnmpError::Protocol(
                        "agent returned an UNAUTHENTICATED response to an authenticated \
                         SNMPv3 request — refusing (possible downgrade attack or agent bug)"
                            .into(),
                    ));
                }
                if self.privacy.is_some() && flags & FLAG_PRIV == 0 {
                    return Err(SnmpError::Protocol(
                        "agent returned an UNENCRYPTED response to an authPriv SNMPv3 \
                         request — refusing"
                            .into(),
                    ));
                }
                Ok(V3Reply::Response(resp.0))
            }
            Pdus::Report(report) => {
                let oid = report
                    .0
                    .variable_bindings
                    .first()
                    .map(|vb| super::format_oid(&vb.name))
                    .unwrap_or_default();
                let stat = ReportStat::from_oid(&oid);
                if stat == ReportStat::NotInTimeWindows {
                    let boots = int_to_u32(&usm.authoritative_engine_boots);
                    let time = int_to_u32(&usm.authoritative_engine_time);
                    self.resync(boots, time);
                }
                Ok(V3Reply::Report { stat, oid })
            }
            other => Err(SnmpError::Protocol(format!(
                "SNMPv3: expected Response or Report PDU, got {:?}",
                std::mem::discriminant(&other)
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// Encoding helpers
// ---------------------------------------------------------------------------

fn encode_msg(msg: &Message) -> Result<Vec<u8>, SnmpError> {
    rasn::ber::encode(msg).map_err(|e| SnmpError::Protocol(format!("BER encode error: {}", e)))
}

fn decode_msg(raw: &[u8]) -> Result<Message, SnmpError> {
    let msg: Message = rasn::ber::decode(raw)
        .map_err(|e| SnmpError::Parse(format!("SNMPv3 BER decode error: {}", e)))?;
    if int_to_u32(&msg.version) != 3 {
        return Err(SnmpError::Protocol(format!(
            "expected SNMPv3 message, got version {:?}",
            msg.version
        )));
    }
    Ok(msg)
}

fn encode_usm(msg: &mut Message, usm: &USMSecurityParameters) -> Result<(), SnmpError> {
    msg.encode_security_parameters(rasn::Codec::Ber, usm)
        .map_err(|e| SnmpError::Protocol(format!("USM parameter encode error: {}", e)))
}

fn decode_usm(msg: &Message) -> Result<USMSecurityParameters, SnmpError> {
    msg.decode_security_parameters::<USMSecurityParameters>(rasn::Codec::Ber)
        .map_err(|e| SnmpError::Parse(format!("USM parameter decode error: {}", e)))
}

fn int_to_u32(i: &Integer) -> u32 {
    i.to_u32().unwrap_or(0)
}

fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || haystack.len() < needle.len() {
        return None;
    }
    haystack.windows(needle.len()).position(|w| w == needle)
}

/// Verify the truncated HMAC of a received message (RFC 3414 §6.3.2): locate
/// msgAuthenticationParameters in the exact received bytes, zero it, recompute.
/// Working on the received bytes (not a re-encoding) keeps us correct against
/// agents whose BER serialization differs from ours.
fn verify_mac(
    proto: AuthProtocol,
    key: &[u8],
    raw: &[u8],
    msg: &Message,
    usm: &USMSecurityParameters,
) -> Result<(), SnmpError> {
    let mac = usm.authentication_parameters.as_ref();
    if mac.len() != proto.mac_len() {
        return Err(SnmpError::Protocol(format!(
            "SNMPv3 authentication parameter length {} does not match protocol ({} expected) — \
             agent may use a different auth_protocol",
            mac.len(),
            proto.mac_len()
        )));
    }

    // The msgSecurityParameters OCTET STRING content appears verbatim in the
    // datagram; search inside it for the encoded auth params (04 <len> <mac>).
    let sec = msg.security_parameters.as_ref();
    let sec_pos = find_subslice(raw, sec).ok_or_else(|| {
        SnmpError::Protocol("cannot locate USM security parameters in datagram".into())
    })?;
    let mut pattern = Vec::with_capacity(2 + mac.len());
    pattern.push(0x04);
    pattern.push(mac.len() as u8);
    pattern.extend_from_slice(mac);
    let rel = find_subslice(&raw[sec_pos..sec_pos + sec.len()], &pattern).ok_or_else(|| {
        SnmpError::Protocol("cannot locate msgAuthenticationParameters in datagram".into())
    })?;
    let mac_off = sec_pos + rel + 2;

    let mut zeroed = raw.to_vec();
    zeroed[mac_off..mac_off + mac.len()].fill(0);
    let expected = hmac_truncated(proto, key, &zeroed);

    // Constant-time-ish comparison (single UDP response; timing is a non-issue,
    // but it costs nothing).
    let equal = expected.len() == mac.len()
        && expected
            .iter()
            .zip(mac.iter())
            .fold(0u8, |acc, (a, b)| acc | (a ^ b))
            == 0;
    if !equal {
        return Err(SnmpError::Protocol(
            "SNMPv3 response failed HMAC verification — wrong auth_password/auth_protocol \
             or a tampered response (refusing to use the data)"
                .into(),
        ));
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Test support (shared with snmp::tests' loopback mock agent)
// ---------------------------------------------------------------------------

/// Build a cleartext noAuthNoPriv Report message the way a real agent answers
/// out-of-band conditions (engine discovery, wrong digests, ...): the usmStats
/// OID identifies the condition, USM params carry engine id/boots/time.
#[cfg(test)]
pub(crate) fn mock_v3_report(
    msg_id: u32,
    engine_id: &[u8],
    boots: u32,
    time: u32,
    report_oid: &str,
) -> Vec<u8> {
    use rasn_smi::v2::{ApplicationSyntax, ObjectSyntax};
    let report = Pdus::Report(rasn_snmp::v2::Report(Pdu {
        request_id: 0,
        error_status: 0,
        error_index: 0,
        variable_bindings: vec![rasn_snmp::v2::VarBind {
            name: super::parse_oid(report_oid).unwrap(),
            value: rasn_snmp::v2::VarBindValue::Value(ObjectSyntax::ApplicationWide(
                ApplicationSyntax::Counter(rasn_smi::v1::Counter(1)),
            )),
        }],
    }));
    let usm = USMSecurityParameters {
        authoritative_engine_id: engine_id.to_vec().into(),
        authoritative_engine_boots: (boots as i64).into(),
        authoritative_engine_time: (time as i64).into(),
        user_name: OctetString::default(),
        authentication_parameters: OctetString::default(),
        privacy_parameters: OctetString::default(),
    };
    let mut msg = Message {
        version: 3.into(),
        global_data: HeaderData {
            message_id: (msg_id as i64).into(),
            max_size: MSG_MAX_SIZE.into(),
            flags: vec![0u8].into(),
            security_model: 3.into(),
        },
        security_parameters: OctetString::default(),
        scoped_data: ScopedPduData::CleartextPdu(ScopedPdu {
            engine_id: engine_id.to_vec().into(),
            name: OctetString::default(),
            data: report,
        }),
    };
    encode_usm(&mut msg, &usm).unwrap();
    encode_msg(&msg).unwrap()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{:02x}", b)).collect()
    }

    /// RFC 3414 A.3 shared inputs
    const PASSWORD: &[u8] = b"maplesyrup";
    const ENGINE_ID: [u8; 12] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2];

    #[test]
    fn test_rfc3414_a3_1_md5_key_localization() {
        // RFC 3414 A.3.1 documented intermediate + final keys
        let ku = super::ku::<Md5>(PASSWORD);
        assert_eq!(hex(&ku), "9faf3283884e92834ebc9847d8edd963");
        let kul = localized_key(AuthProtocol::Md5, PASSWORD, &ENGINE_ID);
        assert_eq!(hex(&kul), "526f5eed9fcce26f8964c2930787d82b");
    }

    #[test]
    fn test_rfc3414_a3_2_sha1_key_localization() {
        // RFC 3414 A.3.2 documented localized key
        let kul = localized_key(AuthProtocol::Sha1, PASSWORD, &ENGINE_ID);
        assert_eq!(hex(&kul), "6695febc9288e36282235fc7151f128497b38f3f");
    }

    #[test]
    fn test_hmac_truncation_lengths_per_protocol() {
        let key = localized_key(AuthProtocol::Sha1, PASSWORD, &ENGINE_ID);
        let data = b"test message";
        assert_eq!(hmac_truncated(AuthProtocol::Md5, &key, data).len(), 12);
        assert_eq!(hmac_truncated(AuthProtocol::Sha1, &key, data).len(), 12);
        assert_eq!(hmac_truncated(AuthProtocol::Sha224, &key, data).len(), 16);
        assert_eq!(hmac_truncated(AuthProtocol::Sha256, &key, data).len(), 24);
        // Truncation takes the LEADING bytes of the full HMAC
        let full = hmac_full!(Sha1, &key, data.as_slice());
        assert_eq!(hmac_truncated(AuthProtocol::Sha1, &key, data), &full[..12]);
    }

    #[test]
    fn test_auth_protocol_parse_aliases_and_rejects() {
        assert_eq!(AuthProtocol::parse("SHA").unwrap(), AuthProtocol::Sha1);
        assert_eq!(AuthProtocol::parse("sha1").unwrap(), AuthProtocol::Sha1);
        assert_eq!(AuthProtocol::parse("md5").unwrap(), AuthProtocol::Md5);
        assert_eq!(AuthProtocol::parse("sha-256").unwrap(), AuthProtocol::Sha256);
        assert_eq!(AuthProtocol::parse("SHA224").unwrap(), AuthProtocol::Sha224);
        assert!(AuthProtocol::parse("sha512").is_err());
    }

    #[test]
    fn test_priv_protocol_des_gives_clear_error_not_silence() {
        let err = PrivProtocol::parse("des").unwrap_err();
        assert!(err.to_string().contains("DES"));
        assert!(err.to_string().contains("aes128"));
        let err = PrivProtocol::parse("aes256").unwrap_err();
        assert!(err.to_string().contains("aes128"));
        assert_eq!(PrivProtocol::parse("AES").unwrap(), PrivProtocol::Aes128);
        assert_eq!(PrivProtocol::parse("aes128").unwrap(), PrivProtocol::Aes128);
    }

    #[test]
    fn test_aes_cfb_round_trip_and_salt_sensitivity() {
        let key = &localized_key(AuthProtocol::Sha1, PASSWORD, &ENGINE_ID)[..16];
        let plaintext = b"a scoped PDU would live here (arbitrary, non-block-aligned length!)";

        let salt_a: [u8; 8] = 42u64.to_be_bytes();
        let mut buf = plaintext.to_vec();
        aes128_cfb_encrypt(key, 7, 12345, &salt_a, &mut buf).unwrap();
        assert_ne!(&buf[..], &plaintext[..], "ciphertext must differ from plaintext");

        // Different salt → different ciphertext for the same plaintext
        let salt_b: [u8; 8] = 43u64.to_be_bytes();
        let mut buf_b = plaintext.to_vec();
        aes128_cfb_encrypt(key, 7, 12345, &salt_b, &mut buf_b).unwrap();
        assert_ne!(buf, buf_b, "distinct salts must yield distinct ciphertexts");

        aes128_cfb_decrypt(key, 7, 12345, &salt_a, &mut buf).unwrap();
        assert_eq!(&buf[..], &plaintext[..]);

        // Wrong key does NOT round-trip
        let wrong = &localized_key(AuthProtocol::Sha1, b"wrongwrong", &ENGINE_ID)[..16];
        let mut buf_c = plaintext.to_vec();
        aes128_cfb_encrypt(key, 7, 12345, &salt_a, &mut buf_c).unwrap();
        aes128_cfb_decrypt(wrong, 7, 12345, &salt_a, &mut buf_c).unwrap();
        assert_ne!(&buf_c[..], &plaintext[..]);
    }

    fn v3_cfg(auth: Option<(&str, &str)>, privacy: Option<(&str, &str)>) -> SnmpV3Config {
        SnmpV3Config {
            username: "pulso".into(),
            auth_protocol: auth.map(|(p, _)| p.to_string()),
            auth_password: auth.map(|(_, pw)| pw.to_string()),
            priv_protocol: privacy.map(|(p, _)| p.to_string()),
            priv_password: privacy.map(|(_, pw)| pw.to_string()),
            context_name: String::new(),
        }
    }

    fn auth_priv_session() -> V3Session {
        let sess = V3Session::from_config(&v3_cfg(
            Some(("sha1", "maplesyrup")),
            Some(("aes128", "maplesyrup")),
        ))
        .unwrap();
        sess.install_engine(ENGINE_ID.to_vec(), 5, 1000);
        sess
    }

    #[test]
    fn test_salt_monotonicity() {
        let sess = auth_priv_session();
        let first = sess.next_salt();
        for i in 1..=100u64 {
            assert_eq!(sess.next_salt(), first.wrapping_add(i), "salt must be a counter");
        }
    }

    #[test]
    fn test_session_config_coherence() {
        // priv without auth is not a valid USM level
        let err = V3Session::from_config(&v3_cfg(None, Some(("aes128", "maplesyrup"))))
            .unwrap_err();
        assert!(err.to_string().contains("requires authentication"));

        // protocol without password (and vice versa)
        let mut cfg = v3_cfg(Some(("sha1", "maplesyrup")), None);
        cfg.auth_password = None;
        assert!(V3Session::from_config(&cfg).is_err());
        let mut cfg = v3_cfg(Some(("sha1", "maplesyrup")), None);
        cfg.auth_protocol = None;
        assert!(V3Session::from_config(&cfg).is_err());

        // empty username
        let mut cfg = v3_cfg(None, None);
        cfg.username = "  ".into();
        assert!(V3Session::from_config(&cfg).is_err());

        // short password (RFC 3414 §11.2)
        let err = V3Session::from_config(&v3_cfg(Some(("sha1", "short")), None)).unwrap_err();
        assert!(err.to_string().contains("8 characters"));

        // security level derivation
        assert_eq!(V3Session::from_config(&v3_cfg(None, None)).unwrap().security_level(), "noAuthNoPriv");
        assert_eq!(
            V3Session::from_config(&v3_cfg(Some(("sha1", "maplesyrup")), None))
                .unwrap()
                .security_level(),
            "authNoPriv"
        );
        assert_eq!(auth_priv_session().security_level(), "authPriv");
    }

    fn sample_response(request_id: i32) -> Pdus {
        use rasn_smi::v2::{ObjectSyntax, SimpleSyntax};
        Pdus::Response(rasn_snmp::v2::Response(Pdu {
            request_id,
            error_status: 0,
            error_index: 0,
            variable_bindings: vec![rasn_snmp::v2::VarBind {
                name: super::super::parse_oid("1.3.6.1.2.1.1.1.0").unwrap(),
                value: rasn_snmp::v2::VarBindValue::Value(ObjectSyntax::Simple(
                    SimpleSyntax::String(OctetString::from_static(b"Mock OLT")),
                )),
            }],
        }))
    }

    /// Encode → decode round-trip at every security level, asserting flags.
    #[test]
    fn test_message_round_trip_all_security_levels() {
        let sessions = [
            (V3Session::from_config(&v3_cfg(None, None)).unwrap(), 0x04u8),
            (
                V3Session::from_config(&v3_cfg(Some(("sha256", "maplesyrup")), None)).unwrap(),
                0x05,
            ),
            (auth_priv_session(), 0x07),
        ];
        for (sess, want_flags) in &sessions {
            sess.install_engine(ENGINE_ID.to_vec(), 5, 1000);
            let wire = sess.wrap(99, sample_response(1234)).unwrap();

            // Flags on the wire are what the level demands
            let msg = decode_msg(&wire).unwrap();
            assert_eq!(
                msg.global_data.flags.first().copied().unwrap(),
                *want_flags,
                "level {}",
                sess.security_level()
            );
            // authPriv messages must actually be encrypted
            if *want_flags & FLAG_PRIV != 0 {
                assert!(matches!(msg.scoped_data, ScopedPduData::EncryptedPdu(_)));
            }

            // And the session can unwrap its own message back to the PDU
            match sess.unwrap(&wire, 99).unwrap() {
                V3Reply::Response(pdu) => {
                    assert_eq!(pdu.request_id, 1234);
                    assert_eq!(pdu.variable_bindings.len(), 1);
                }
                V3Reply::Report { .. } => panic!("expected Response"),
            }
        }
    }

    #[test]
    fn test_tampered_message_fails_hmac() {
        let sess = auth_priv_session();
        let mut wire = sess.wrap(7, sample_response(1)).unwrap();
        // Flip one bit near the end (inside the encrypted scoped PDU)
        let n = wire.len();
        wire[n - 1] ^= 0x01;
        let err = match sess.unwrap(&wire, 7) {
            Err(e) => e,
            Ok(_) => panic!("tampered message must not verify"),
        };
        assert!(err.to_string().contains("HMAC"), "got: {err}");
    }

    #[test]
    fn test_wrong_auth_key_fails_verification_loudly() {
        // Peer signs with a different password — receiver must refuse.
        let signer = V3Session::from_config(&v3_cfg(
            Some(("sha1", "wrongwrong")),
            Some(("aes128", "maplesyrup")),
        ))
        .unwrap();
        signer.install_engine(ENGINE_ID.to_vec(), 5, 1000);
        let wire = signer.wrap(7, sample_response(1)).unwrap();

        let sess = auth_priv_session();
        let err = match sess.unwrap(&wire, 7) {
            Err(e) => e,
            Ok(_) => panic!("wrong key must not verify"),
        };
        assert!(err.to_string().contains("HMAC"), "got: {err}");
    }

    #[test]
    fn test_unauthenticated_response_rejected_when_auth_configured() {
        // A noAuthNoPriv peer responds to an authNoPriv session: downgrade → refuse.
        let peer = V3Session::from_config(&v3_cfg(None, None)).unwrap();
        peer.install_engine(ENGINE_ID.to_vec(), 5, 1000);
        let wire = peer.wrap(7, sample_response(1)).unwrap();

        let sess =
            V3Session::from_config(&v3_cfg(Some(("sha1", "maplesyrup")), None)).unwrap();
        sess.install_engine(ENGINE_ID.to_vec(), 5, 1000);
        let err = match sess.unwrap(&wire, 7) {
            Err(e) => e,
            Ok(_) => panic!("unauthenticated response must be refused"),
        };
        assert!(err.to_string().contains("UNAUTHENTICATED"), "got: {err}");
    }

    /// Canned-Report engine discovery state machine.
    #[test]
    fn test_engine_discovery_from_canned_report() {
        let sess = auth_priv_session();
        // Fresh session (auth_priv_session installs an engine; make a new one)
        let sess2 = V3Session::from_config(&v3_cfg(
            Some(("sha1", "maplesyrup")),
            Some(("aes128", "maplesyrup")),
        ))
        .unwrap();
        assert!(sess2.needs_discovery());

        let probe = sess2.build_discovery(1, 2).unwrap();
        // The probe is noAuthNoPriv + reportable with an empty user name
        let probe_msg = decode_msg(&probe).unwrap();
        assert_eq!(probe_msg.global_data.flags.first().copied().unwrap(), 0x04);
        let probe_usm = decode_usm(&probe_msg).unwrap();
        assert!(probe_usm.user_name.is_empty());
        assert!(probe_usm.authoritative_engine_id.is_empty());

        // Agent side: canned unknownEngineIDs Report carrying engine id/boots/time
        let report =
            mock_v3_report(1, &ENGINE_ID, 5, 1000, report_oids::UNKNOWN_ENGINE_IDS);
        sess2.absorb_discovery(&report).unwrap();
        assert!(!sess2.needs_discovery());
        assert_eq!(sess2.engine_id().unwrap(), ENGINE_ID.to_vec());

        // Localized keys must equal a directly-installed session's
        let wire = sess2.wrap(50, sample_response(9)).unwrap();
        // sess (same creds, same engine) must be able to unwrap it
        match sess.unwrap(&wire, 50).unwrap() {
            V3Reply::Response(pdu) => assert_eq!(pdu.request_id, 9),
            _ => panic!("expected Response"),
        }
    }

    #[test]
    fn test_discovery_rejects_empty_engine_id() {
        let sess = V3Session::from_config(&v3_cfg(None, None)).unwrap();
        let report = mock_v3_report(1, &[], 0, 0, report_oids::UNKNOWN_ENGINE_IDS);
        let err = sess.absorb_discovery(&report).unwrap_err();
        assert!(err.to_string().contains("empty engine ID"));
    }

    #[test]
    fn test_not_in_time_windows_report_resyncs_session() {
        let sess = auth_priv_session();
        // Agent (same creds) reports notInTimeWindows with new boots/time,
        // authenticated as RFC 3414 §3.2 step 7b prescribes.
        let agent = auth_priv_session();
        agent.install_engine(ENGINE_ID.to_vec(), 6, 999_999);
        let report = {
            let pdus = Pdus::Report(rasn_snmp::v2::Report(Pdu {
                request_id: 1,
                error_status: 0,
                error_index: 0,
                variable_bindings: vec![rasn_snmp::v2::VarBind {
                    name: super::super::parse_oid(report_oids::NOT_IN_TIME_WINDOWS).unwrap(),
                    value: rasn_snmp::v2::VarBindValue::Unspecified,
                }],
            }));
            agent.wrap(11, pdus).unwrap()
        };
        match sess.unwrap(&report, 11).unwrap() {
            V3Reply::Report { stat, .. } => assert_eq!(stat, ReportStat::NotInTimeWindows),
            _ => panic!("expected Report"),
        }
        // Session must have adopted the agent's boots
        let engine = sess.engine().unwrap();
        assert_eq!(engine.boots, 6);
        assert!(engine.time_base >= 999_999);
    }

    #[test]
    fn test_report_stat_error_messages_are_actionable() {
        let e = ReportStat::WrongDigests.to_error(report_oids::WRONG_DIGESTS, "pulso");
        assert!(e.to_string().contains("usmStatsWrongDigests"));
        assert!(e.to_string().contains("auth_password"));
        let e = ReportStat::UnknownUserNames.to_error(report_oids::UNKNOWN_USER_NAMES, "pulso");
        assert!(e.to_string().contains("unknown"));
        let e = ReportStat::DecryptionErrors.to_error(report_oids::DECRYPTION_ERRORS, "pulso");
        assert!(e.to_string().contains("priv_password"));
    }

}
