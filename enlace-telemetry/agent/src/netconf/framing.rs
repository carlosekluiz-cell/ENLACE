// SPDX-License-Identifier: Apache-2.0
// NETCONF 1.1 Chunked Framing (RFC 6242)
//
// NETCONF 1.0 uses ]]>]]> as message delimiter.
// NETCONF 1.1 uses chunked framing: \n#<length>\n<data>\n##\n
//
// We support both — negotiate on connect via capability exchange.

/// NETCONF 1.0 end-of-message delimiter
pub const EOM_10: &str = "]]>]]>";

/// Encode a NETCONF 1.1 chunked message.
/// Format: \n#<length>\n<data>\n##\n
pub fn encode_netconf11(msg: &str) -> Vec<u8> {
    let mut buf = Vec::with_capacity(msg.len() + 32);
    buf.extend_from_slice(format!("\n#{}\n", msg.len()).as_bytes());
    buf.extend_from_slice(msg.as_bytes());
    buf.extend_from_slice(b"\n##\n");
    buf
}

/// Encode a NETCONF 1.0 message (append ]]>]]> delimiter).
pub fn encode_netconf10(msg: &str) -> Vec<u8> {
    let mut buf = Vec::with_capacity(msg.len() + 8);
    buf.extend_from_slice(msg.as_bytes());
    buf.extend_from_slice(EOM_10.as_bytes());
    buf
}

/// Decode a NETCONF 1.1 chunked message from a byte buffer.
/// Returns the decoded XML string and the number of bytes consumed.
/// Returns None if the buffer does not contain a complete message.
pub fn decode_netconf11(buf: &[u8]) -> Option<(String, usize)> {
    let s = std::str::from_utf8(buf).ok()?;
    let mut result = String::new();
    let mut pos = 0;

    loop {
        // Skip to next \n#
        while pos < s.len() && !s[pos..].starts_with("\n#") {
            pos += 1;
        }
        if pos >= s.len() {
            return None;
        }

        pos += 2; // skip \n#

        // Check for end-of-chunks marker: ##\n
        if s[pos..].starts_with('#') {
            // \n##\n — end of message
            pos += 1; // skip second #
            if pos < s.len() && s.as_bytes()[pos] == b'\n' {
                pos += 1;
            }
            return Some((result, pos));
        }

        // Parse chunk length
        let len_end = s[pos..].find('\n')?;
        let len_str = &s[pos..pos + len_end];
        let chunk_len: usize = len_str.parse().ok()?;
        pos += len_end + 1; // skip length + \n

        if pos + chunk_len > s.len() {
            return None; // incomplete chunk
        }

        result.push_str(&s[pos..pos + chunk_len]);
        pos += chunk_len;
    }
}

/// Decode a NETCONF 1.0 message (delimited by ]]>]]>).
/// Returns the XML content before the delimiter and total bytes consumed.
pub fn decode_netconf10(buf: &[u8]) -> Option<(String, usize)> {
    let s = std::str::from_utf8(buf).ok()?;
    let idx = s.find(EOM_10)?;
    let xml = s[..idx].to_string();
    Some((xml, idx + EOM_10.len()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_decode_netconf11() {
        let msg = r#"<rpc xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><get/></rpc>"#;
        let encoded = encode_netconf11(msg);
        let (decoded, consumed) = decode_netconf11(&encoded).expect("decode should succeed");
        assert_eq!(decoded, msg);
        assert_eq!(consumed, encoded.len());
    }

    #[test]
    fn test_encode_decode_netconf10() {
        let msg = r#"<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"/>"#;
        let encoded = encode_netconf10(msg);
        let (decoded, consumed) = decode_netconf10(&encoded).expect("decode should succeed");
        assert_eq!(decoded, msg);
        assert_eq!(consumed, encoded.len());
    }

    #[test]
    fn test_decode_incomplete_11() {
        let partial = b"\n#10\nhello";
        assert!(decode_netconf11(partial).is_none());
    }

    #[test]
    fn test_decode_multi_chunk_11() {
        // Two chunks: "Hello" (5 bytes) + " World" (6 bytes)
        let msg = b"\n#5\nHello\n#6\n World\n##\n";
        let (decoded, _consumed) = decode_netconf11(msg).expect("multi-chunk decode");
        assert_eq!(decoded, "Hello World");
    }
}
