// SPDX-License-Identifier: Apache-2.0
// NETCONF 1.1 Chunked Framing (RFC 6242)
//
// NETCONF 1.0 uses ]]>]]> as message delimiter.
// NETCONF 1.1 uses chunked framing: \n#<length>\n<data>\n##\n
//
// We support both — negotiate on connect via capability exchange.
//
// Decoding is done through `FrameBuffer`, an incremental decoder that scans
// each received byte at most once. The naive alternative (re-running
// `find("]]>]]>")` over the whole accumulated buffer on every SSH packet) is
// O(n²): a 50 MB <rpc-reply> arriving in 32 KB SSH packets would re-scan the
// buffer ~1600 times (~40 TB of memory traffic).

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

/// Maximum digits in a chunk-size header. RFC 6242 §4.2 caps chunk-size at
/// 4294967295 (10 digits); anything longer is a framing violation.
const MAX_CHUNK_SIZE_DIGITS: usize = 10;

/// Incremental NETCONF frame decoder.
///
/// Push raw SSH channel bytes with [`push`](Self::push), then call
/// [`try_decode_10`](Self::try_decode_10) or
/// [`try_decode_11`](Self::try_decode_11) (per negotiated framing) until it
/// yields a message. State is kept between calls so that:
///   - EOM scanning resumes where the last scan stopped (each byte is
///     examined once, minus a 5-byte overlap for delimiters that straddle
///     packet boundaries);
///   - fully-received 1.1 chunks are moved out of the buffer as they
///     complete, so chunk headers are never re-parsed and chunk bodies are
///     never re-scanned.
///
/// Framing violations (bad chunk header, non-UTF-8 payload) are surfaced as
/// errors instead of silently stalling the session.
#[derive(Default)]
pub struct FrameBuffer {
    buf: Vec<u8>,
    /// 1.0 EOM scan cursor: bytes before this offset are known to be free of
    /// the `]]>]]>` delimiter.
    scan_pos: usize,
    /// 1.1: decoded chunk payload bytes of the in-progress message.
    decoded: Vec<u8>,
}

impl FrameBuffer {
    pub fn new() -> Self {
        Self {
            buf: Vec::with_capacity(65536),
            scan_pos: 0,
            decoded: Vec::new(),
        }
    }

    /// Append raw bytes received from the transport.
    pub fn push(&mut self, data: &[u8]) {
        self.buf.extend_from_slice(data);
    }

    /// Number of buffered (not yet decoded) bytes. Used for diagnostics.
    pub fn buffered_len(&self) -> usize {
        self.buf.len()
    }

    /// Try to decode a NETCONF 1.0 (EOM-delimited) message.
    /// Returns Ok(None) if the message is not yet complete.
    pub fn try_decode_10(&mut self) -> anyhow::Result<Option<String>> {
        let eom = EOM_10.as_bytes();
        // Resume the scan just before where we stopped, so a delimiter split
        // across two SSH packets is still found.
        let start = self
            .scan_pos
            .saturating_sub(eom.len() - 1)
            .min(self.buf.len());

        match find_subslice(&self.buf[start..], eom) {
            Some(rel) => {
                let idx = start + rel;
                let msg = std::str::from_utf8(&self.buf[..idx])
                    .map_err(|e| {
                        anyhow::anyhow!("NETCONF 1.0 message is not valid UTF-8: {}", e)
                    })?
                    .to_string();
                self.buf.drain(..idx + eom.len());
                self.scan_pos = 0;
                Ok(Some(msg))
            }
            None => {
                self.scan_pos = self.buf.len();
                Ok(None)
            }
        }
    }

    /// Try to decode a NETCONF 1.1 (chunked) message.
    /// Returns Ok(None) if the message is not yet complete.
    pub fn try_decode_11(&mut self) -> anyhow::Result<Option<String>> {
        let mut pos = 0usize;

        loop {
            // Leniency at message start only: skip stray whitespace between
            // messages (some stacks emit an extra CR/LF around frames).
            // An LF might be the first byte of the "\n#" header — only skip
            // it once the following byte proves it is not.
            if self.decoded.is_empty() {
                while pos < self.buf.len() {
                    let b = self.buf[pos];
                    if !b.is_ascii_whitespace() {
                        break;
                    }
                    if b == b'\n' {
                        match self.buf.get(pos + 1) {
                            Some(b'#') => break, // chunk header starts here
                            Some(_) => pos += 1, // lone newline — skip
                            None => {
                                // Undecidable until the next byte arrives.
                                self.buf.drain(..pos);
                                return Ok(None);
                            }
                        }
                    } else {
                        pos += 1;
                    }
                }
            }

            // Need at least "\n#" to know what comes next.
            if self.buf.len() < pos + 2 {
                break;
            }
            if &self.buf[pos..pos + 2] != b"\n#" {
                return Err(anyhow::anyhow!(
                    "NETCONF 1.1 framing violation: expected chunk header \"\\n#\", got {:?}",
                    String::from_utf8_lossy(&self.buf[pos..(pos + 8).min(self.buf.len())])
                ));
            }
            let header_start = pos;
            pos += 2;

            // End-of-chunks marker: \n##\n
            if pos < self.buf.len() && self.buf[pos] == b'#' {
                pos += 1;
                if pos >= self.buf.len() {
                    pos = header_start; // wait for the trailing \n
                    break;
                }
                if self.buf[pos] != b'\n' {
                    return Err(anyhow::anyhow!(
                        "NETCONF 1.1 framing violation: end-of-chunks marker not terminated by LF"
                    ));
                }
                pos += 1;
                self.buf.drain(..pos);
                let msg_bytes = std::mem::take(&mut self.decoded);
                let msg = String::from_utf8(msg_bytes).map_err(|e| {
                    anyhow::anyhow!("NETCONF 1.1 message is not valid UTF-8: {}", e)
                })?;
                return Ok(Some(msg));
            }

            // Parse chunk-size digits terminated by \n.
            let mut len_end = pos;
            while len_end < self.buf.len() && self.buf[len_end].is_ascii_digit() {
                len_end += 1;
            }
            if len_end - pos > MAX_CHUNK_SIZE_DIGITS {
                return Err(anyhow::anyhow!(
                    "NETCONF 1.1 framing violation: chunk-size longer than {} digits",
                    MAX_CHUNK_SIZE_DIGITS
                ));
            }
            if len_end >= self.buf.len() {
                pos = header_start; // incomplete header — wait for more bytes
                break;
            }
            if self.buf[len_end] != b'\n' || len_end == pos {
                return Err(anyhow::anyhow!(
                    "NETCONF 1.1 framing violation: malformed chunk-size header {:?}",
                    String::from_utf8_lossy(&self.buf[header_start..(header_start + 16).min(self.buf.len())])
                ));
            }
            let chunk_len: usize = std::str::from_utf8(&self.buf[pos..len_end])
                .expect("digits are ASCII")
                .parse()
                .map_err(|e| anyhow::anyhow!("NETCONF 1.1 chunk-size parse error: {}", e))?;
            let data_start = len_end + 1;

            if self.buf.len() < data_start + chunk_len {
                pos = header_start; // chunk body incomplete — wait for more bytes
                break;
            }

            // Complete chunk: move payload into `decoded`. UTF-8 validation
            // happens once, on the assembled message — a multibyte character
            // may legally straddle a chunk boundary.
            self.decoded
                .extend_from_slice(&self.buf[data_start..data_start + chunk_len]);
            pos = data_start + chunk_len;
        }

        // Drop everything we fully consumed; the (small) incomplete tail is
        // re-examined on the next call, so no byte is scanned more than a
        // constant number of times.
        if pos > 0 {
            self.buf.drain(..pos);
        }
        Ok(None)
    }
}

/// Find `needle` in `haystack` (first occurrence).
fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || haystack.len() < needle.len() {
        return None;
    }
    haystack
        .windows(needle.len())
        .position(|w| w == needle)
}

// ── Legacy one-shot decoders ────────────────────────────────────────────────
// Kept for the audit test suite and offline tooling. Production sessions use
// `FrameBuffer` (incremental, O(n) across packets).

/// Decode a NETCONF 1.1 chunked message from a byte buffer (one-shot).
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

/// Decode a NETCONF 1.0 message (delimited by ]]>]]>) — one-shot.
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

    // ── FrameBuffer (incremental) ───────────────────────────────────────────

    #[test]
    fn test_framebuffer_10_single_push() {
        let mut fb = FrameBuffer::new();
        fb.push(b"<hello/>]]>]]>");
        let msg = fb.try_decode_10().unwrap().expect("complete message");
        assert_eq!(msg, "<hello/>");
        assert_eq!(fb.buffered_len(), 0);
    }

    #[test]
    fn test_framebuffer_10_delimiter_split_across_pushes() {
        // Delimiter straddles the packet boundary — the resumed scan must
        // still find it despite the cursor having advanced.
        let mut fb = FrameBuffer::new();
        fb.push(b"<rpc-reply>data</rpc-reply>]]>");
        assert!(fb.try_decode_10().unwrap().is_none());
        fb.push(b"]]>");
        let msg = fb.try_decode_10().unwrap().expect("complete after 2nd push");
        assert_eq!(msg, "<rpc-reply>data</rpc-reply>");
    }

    #[test]
    fn test_framebuffer_10_two_messages_back_to_back() {
        let mut fb = FrameBuffer::new();
        fb.push(b"<a/>]]>]]><b/>]]>]]>");
        assert_eq!(fb.try_decode_10().unwrap().as_deref(), Some("<a/>"));
        assert_eq!(fb.try_decode_10().unwrap().as_deref(), Some("<b/>"));
        assert!(fb.try_decode_10().unwrap().is_none());
    }

    #[test]
    fn test_framebuffer_11_multi_push_assembly() {
        let msg = r#"<rpc-reply message-id="1"><data/></rpc-reply>"#;
        let encoded = encode_netconf11(msg);
        let mut fb = FrameBuffer::new();
        // Feed one byte at a time — worst case for any re-scanning decoder.
        for b in &encoded[..encoded.len() - 1] {
            fb.push(&[*b]);
            assert!(fb.try_decode_11().unwrap().is_none());
        }
        fb.push(&encoded[encoded.len() - 1..]);
        assert_eq!(fb.try_decode_11().unwrap().as_deref(), Some(msg));
    }

    #[test]
    fn test_framebuffer_11_multibyte_char_split_across_chunks() {
        // "é" (2 UTF-8 bytes) split across two chunks — must reassemble.
        let mut raw = Vec::new();
        raw.extend_from_slice(b"\n#2\n<\xc3");
        raw.extend_from_slice(b"\n#2\n\xa9>");
        raw.extend_from_slice(b"\n##\n");
        let mut fb = FrameBuffer::new();
        fb.push(&raw);
        assert_eq!(fb.try_decode_11().unwrap().as_deref(), Some("<é>"));
    }

    #[test]
    fn test_framebuffer_11_garbage_header_is_error() {
        let mut fb = FrameBuffer::new();
        fb.push(b"\n#abc\ndata\n##\n");
        assert!(fb.try_decode_11().is_err());
    }

    #[test]
    fn test_framebuffer_11_not_a_chunk_is_error() {
        let mut fb = FrameBuffer::new();
        fb.push(b"totally not netconf framing");
        assert!(fb.try_decode_11().is_err());
    }

    #[test]
    fn test_framebuffer_11_large_payload_incremental() {
        // A ~24 MB reply delivered in 32 KB SSH packets. With the old
        // rescan-everything decoder this took O(n²) (~9 * 10^15 byte
        // comparisons); incrementally it is O(n) and finishes instantly.
        let chunk_body = "x".repeat(65000);
        let n_chunks = 370; // ~24 MB total
        let mut fb = FrameBuffer::new();

        let mut wire = Vec::with_capacity(n_chunks * (chunk_body.len() + 16));
        for _ in 0..n_chunks {
            wire.extend_from_slice(format!("\n#{}\n", chunk_body.len()).as_bytes());
            wire.extend_from_slice(chunk_body.as_bytes());
        }
        wire.extend_from_slice(b"\n##\n");

        let start = std::time::Instant::now();
        let mut result = None;
        for packet in wire.chunks(32 * 1024) {
            fb.push(packet);
            if let Some(msg) = fb.try_decode_11().unwrap() {
                result = Some(msg);
            }
        }
        let msg = result.expect("large message should decode");
        assert_eq!(msg.len(), n_chunks * chunk_body.len());
        // Generous bound: incremental decode of 24 MB is well under a second
        // even on slow CI; the O(n²) version would take minutes.
        assert!(
            start.elapsed() < std::time::Duration::from_secs(10),
            "large-payload decode too slow: {:?} (framing re-scan regression?)",
            start.elapsed()
        );
    }

    #[test]
    fn test_framebuffer_10_large_payload_incremental() {
        let body = "y".repeat(20 * 1024 * 1024);
        let mut fb = FrameBuffer::new();
        let start = std::time::Instant::now();
        let mut result = None;
        let encoded = encode_netconf10(&body);
        for packet in encoded.chunks(32 * 1024) {
            fb.push(packet);
            if let Some(msg) = fb.try_decode_10().unwrap() {
                result = Some(msg);
            }
        }
        assert_eq!(result.expect("decode").len(), body.len());
        assert!(
            start.elapsed() < std::time::Duration::from_secs(10),
            "large-payload EOM decode too slow: {:?}",
            start.elapsed()
        );
    }

    #[test]
    fn test_framebuffer_11_header_split_across_pushes() {
        let mut fb = FrameBuffer::new();
        fb.push(b"\n#1");
        assert!(fb.try_decode_11().unwrap().is_none());
        fb.push(b"1\nhello world");
        assert!(fb.try_decode_11().unwrap().is_none());
        fb.push(b"\n##\n");
        assert_eq!(fb.try_decode_11().unwrap().as_deref(), Some("hello world"));
    }
}
