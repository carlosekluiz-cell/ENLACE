// SPDX-License-Identifier: Apache-2.0
// NETCONF 1.1 Transport over SSH (RFC 6241)
//
// Uses russh (pure Rust SSH) for transport to NETCONF port 830.
// Implements chunked framing, capability exchange, <get>, <get-config>,
// and <create-subscription> for BBF TR-385 YANG models.

pub mod session;
pub mod framing;
pub mod xml;

pub use session::NetconfSession;
#[allow(unused_imports)]
pub use session::{HostKeyStore, HostKeyVerdict};
#[allow(unused_imports)]
pub use framing::{encode_netconf11, decode_netconf11, FrameBuffer};
#[allow(unused_imports)]
pub use xml::{parse_capabilities, parse_ont_state, parse_optical_power, parse_ranging};
