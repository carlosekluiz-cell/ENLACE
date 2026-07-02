// SPDX-License-Identifier: Apache-2.0
// Shared SNMP helpers for vendor modules.

use crate::snmp::{SnmpValue, SnmpData};

/// Extract the last N components of an OID as a suffix key.
/// e.g., extract_oid_suffix("1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3.4294967808.1", 2) → "4294967808.1"
pub fn extract_oid_suffix(oid: &str, n: usize) -> String {
    let parts: Vec<&str> = oid.rsplitn(n + 1, '.').collect();
    if parts.len() > n {
        parts[..n].iter().rev().copied().collect::<Vec<_>>().join(".")
    } else {
        oid.to_string()
    }
}

/// True if `oid` ends with `suffix` aligned on a '.' component boundary.
///
/// Plain `ends_with` would match index "8.1" against "...48.1" or "...108.1",
/// attributing metrics to the wrong ONT on any OLT with more than a handful
/// of index values.
pub fn oid_suffix_matches(oid: &str, suffix: &str) -> bool {
    match oid.strip_suffix(suffix) {
        Some(rest) => rest.is_empty() || rest.ends_with('.'),
        None => false,
    }
}

/// Find a varbind in a list by matching OID suffix (component-boundary aligned).
pub fn find_by_suffix<'a>(entries: &'a [SnmpValue], suffix: &str) -> Option<&'a SnmpData> {
    entries.iter()
        .find(|e| oid_suffix_matches(&e.oid, suffix))
        .map(|e| &e.value)
}

/// Return `v` if it is a physically plausible dBm reading, `None` otherwise.
///
/// GPON optics live roughly in −40..−8 dBm at the ONT and up to ~+5 dBm at
/// launch; we accept a −45.0..=+10.0 dBm window. Everything outside is either
/// a broken conversion or a vendor "no reading" sentinel. Common sentinels
/// seen in the wild (raw and after the usual /100 scaling):
///   - Huawei: 2147483647 (i32::MAX)          → 21474836.47 after /100
///   - ZTE:    65535 (u16::MAX)               → 655.35
///   - BDCOM:  0x7FFF = 32767 (i16::MAX)      → 327.67
///   - misc:   -32768 (i16::MIN), 0x7FFFFFFF  → -327.68, 21474836.47
/// All of these fall outside the window and map to `None`, as do NaN/±inf.
pub fn plausible_dbm(v: f64) -> Option<f64> {
    if (-45.0..=10.0).contains(&v) {
        Some(v)
    } else {
        None
    }
}

/// Return `v` if it is a physically plausible transceiver temperature (°C),
/// `None` otherwise.
///
/// SFF-8472 (DDM) encodes temperature as a signed 1/256 °C value spanning
/// −128..+128 °C; real optics are specified for −40..+85 °C (industrial
/// grade) and alarm well below +100 °C. We accept −50.0..=120.0 °C —
/// anything outside is a broken conversion or a vendor "no reading"
/// sentinel (e.g. 0x7FFF / 327.67 after the usual /100 scaling), as are
/// NaN/±inf.
pub fn plausible_temp_c(v: f64) -> Option<f64> {
    if (-50.0..=120.0).contains(&v) {
        Some(v)
    } else {
        None
    }
}

/// Return `v` if it is a physically plausible transceiver supply voltage
/// (V), `None` otherwise.
///
/// SFF-8472 encodes Vcc in 100 µV steps over 0..6.5535 V; real modules run
/// at 3.3 V (some legacy at 5 V). We accept 0.0..=6.0 V — anything outside
/// is a broken conversion or sentinel (65535 raw, 655.35 after /100...),
/// as are NaN/±inf. Note 0.0 is accepted: "powered off" is a real reading.
pub fn plausible_voltage_v(v: f64) -> Option<f64> {
    if (0.0..=6.0).contains(&v) {
        Some(v)
    } else {
        None
    }
}

/// Return `v` if it is a physically plausible laser bias current (mA),
/// `None` otherwise.
///
/// SFF-8472 encodes TX bias in 2 µA steps over 0..131 mA; typical GPON ONT
/// lasers run 5–80 mA and end-of-life drift stays double digits. We accept
/// 0.0..=150.0 mA — anything outside is a broken conversion or sentinel,
/// as are NaN/±inf.
pub fn plausible_bias_ma(v: f64) -> Option<f64> {
    if (0.0..=150.0).contains(&v) {
        Some(v)
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn value(oid: &str, v: i64) -> SnmpValue {
        SnmpValue {
            oid: oid.to_string(),
            value: SnmpData::Integer(v),
            timestamp: chrono::Utc::now(),
        }
    }

    #[test]
    fn test_extract_oid_suffix() {
        assert_eq!(
            extract_oid_suffix("1.3.6.1.4.1.2011.6.128.1.1.2.43.1.3.4294967808.1", 2),
            "4294967808.1"
        );
        assert_eq!(extract_oid_suffix("1.2.3", 1), "3");
        assert_eq!(extract_oid_suffix("7", 2), "7");
    }

    #[test]
    fn test_oid_suffix_matches_requires_component_boundary() {
        // Genuine matches
        assert!(oid_suffix_matches("1.3.6.1.4.1.2011.1.8.1", "8.1"));
        assert!(oid_suffix_matches("8.1", "8.1")); // exact
        // The audit's exact failure mode: index 8.1 vs ONTs 48.1 / 108.1
        assert!(!oid_suffix_matches("1.3.6.1.4.1.2011.1.48.1", "8.1"));
        assert!(!oid_suffix_matches("1.3.6.1.4.1.2011.1.108.1", "8.1"));
        // Single-component indices bleed too: index "5" vs interface 15
        assert!(oid_suffix_matches("1.3.6.1.2.1.2.2.1.8.5", "5"));
        assert!(!oid_suffix_matches("1.3.6.1.2.1.2.2.1.8.15", "5"));
        // Non-suffix never matches
        assert!(!oid_suffix_matches("1.2.3.4", "2.3"));
    }

    #[test]
    fn test_find_by_suffix_picks_the_right_ont() {
        let entries = vec![
            value("1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4.48.1", -4801),
            value("1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4.108.1", -10801),
            value("1.3.6.1.4.1.2011.6.128.1.1.2.51.1.4.8.1", -801),
        ];
        // Old ends_with matching would return the 48.1 entry (first match).
        match find_by_suffix(&entries, "8.1") {
            Some(SnmpData::Integer(v)) => assert_eq!(*v, -801),
            other => panic!("Expected Integer(-801), got {:?}", other),
        }
        assert!(find_by_suffix(&entries, "9.1").is_none());
    }

    /// Property-style test: suffix matching must agree with a reference
    /// implementation that compares whole OID components, across thousands of
    /// adversarial generated cases (no proptest dep, so a seeded LCG).
    #[test]
    fn test_property_suffix_match_never_crosses_component_boundaries() {
        // Reference: split into components and compare the tail.
        fn reference(oid: &str, suffix: &str) -> bool {
            let o: Vec<&str> = oid.split('.').collect();
            let s: Vec<&str> = suffix.split('.').collect();
            s.len() <= o.len() && o[o.len() - s.len()..] == s[..]
        }

        // Small deterministic LCG (numerical recipes constants)
        let mut state: u64 = 0xDEAD_BEEF_CAFE_1234;
        let mut next = move || {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
            (state >> 33) as usize
        };

        // Component pool biased toward digit-bleed collisions (8/48/108, 1/21/321…)
        let pool = ["1", "2", "3", "8", "9", "11", "21", "48", "81", "99",
                    "108", "111", "321", "480", "1081", "4294967808"];

        for case in 0..10_000 {
            let oid_len = 2 + next() % 10;
            let oid_parts: Vec<&str> = (0..oid_len).map(|_| pool[next() % pool.len()]).collect();
            let oid = oid_parts.join(".");

            let suffix = match case % 3 {
                // Genuine component-aligned tail of the OID
                0 => {
                    let n = 1 + next() % oid_len;
                    oid_parts[oid_len - n..].join(".")
                }
                // Random components (may or may not match)
                1 => {
                    let n = 1 + next() % 4;
                    (0..n).map(|_| pool[next() % pool.len()]).collect::<Vec<_>>().join(".")
                }
                // Digit-bleed: real tail with leading digits stripped from the
                // first component ("48.1" → "8.1") — the classic false match
                _ => {
                    let n = 1 + next() % oid_len;
                    let mut tail = oid_parts[oid_len - n..].to_vec();
                    let first = tail[0];
                    let stripped = &first[next() % first.len()..];
                    if stripped.is_empty() {
                        continue;
                    }
                    tail[0] = stripped;
                    tail.join(".")
                }
            };

            assert_eq!(
                oid_suffix_matches(&oid, &suffix),
                reference(&oid, &suffix),
                "mismatch for oid={:?} suffix={:?}",
                oid,
                suffix
            );
        }
    }

    #[test]
    fn test_plausible_dbm_window_and_sentinels() {
        // Typical healthy GPON readings
        assert_eq!(plausible_dbm(-22.4), Some(-22.4));
        assert_eq!(plausible_dbm(2.5), Some(2.5));
        assert_eq!(plausible_dbm(0.0), Some(0.0));
        // Window boundaries are inclusive
        assert_eq!(plausible_dbm(-45.0), Some(-45.0));
        assert_eq!(plausible_dbm(10.0), Some(10.0));
        assert_eq!(plausible_dbm(-45.01), None);
        assert_eq!(plausible_dbm(10.01), None);
        // Raw sentinels
        assert_eq!(plausible_dbm(2147483647.0), None); // Huawei i32::MAX
        assert_eq!(plausible_dbm(65535.0), None);      // ZTE u16::MAX
        assert_eq!(plausible_dbm(32767.0), None);      // BDCOM 0x7FFF
        assert_eq!(plausible_dbm(-32768.0), None);     // i16::MIN
        // Sentinels after the common /100 scaling
        assert_eq!(plausible_dbm(21474836.47), None);
        assert_eq!(plausible_dbm(655.35), None);
        assert_eq!(plausible_dbm(327.67), None);
        assert_eq!(plausible_dbm(-327.68), None);
        // Non-finite inputs
        assert_eq!(plausible_dbm(f64::NAN), None);
        assert_eq!(plausible_dbm(f64::INFINITY), None);
        assert_eq!(plausible_dbm(f64::NEG_INFINITY), None);
    }

    #[test]
    fn test_plausible_temp_c_window_and_sentinels() {
        // Typical transceiver temperatures
        assert_eq!(plausible_temp_c(45.5), Some(45.5));
        assert_eq!(plausible_temp_c(-10.0), Some(-10.0));
        // Boundaries inclusive
        assert_eq!(plausible_temp_c(-50.0), Some(-50.0));
        assert_eq!(plausible_temp_c(120.0), Some(120.0));
        assert_eq!(plausible_temp_c(-50.01), None);
        assert_eq!(plausible_temp_c(120.01), None);
        // Sentinels raw and after /100 scaling
        assert_eq!(plausible_temp_c(32767.0), None);
        assert_eq!(plausible_temp_c(327.67), None);
        assert_eq!(plausible_temp_c(2147483647.0), None);
        // Non-finite inputs
        assert_eq!(plausible_temp_c(f64::NAN), None);
        assert_eq!(plausible_temp_c(f64::INFINITY), None);
    }

    #[test]
    fn test_plausible_voltage_v_window_and_sentinels() {
        // 3.3 V is the normal reading; 0 V (powered off) is real data
        assert_eq!(plausible_voltage_v(3.3), Some(3.3));
        assert_eq!(plausible_voltage_v(0.0), Some(0.0));
        // Boundaries inclusive
        assert_eq!(plausible_voltage_v(6.0), Some(6.0));
        assert_eq!(plausible_voltage_v(6.01), None);
        assert_eq!(plausible_voltage_v(-0.01), None);
        // Sentinels raw and after /100 scaling
        assert_eq!(plausible_voltage_v(65535.0), None);
        assert_eq!(plausible_voltage_v(655.35), None);
        // Non-finite inputs
        assert_eq!(plausible_voltage_v(f64::NAN), None);
        assert_eq!(plausible_voltage_v(f64::NEG_INFINITY), None);
    }

    #[test]
    fn test_plausible_bias_ma_window_and_sentinels() {
        // Typical GPON laser bias
        assert_eq!(plausible_bias_ma(12.5), Some(12.5));
        assert_eq!(plausible_bias_ma(0.0), Some(0.0));
        // Boundaries inclusive
        assert_eq!(plausible_bias_ma(150.0), Some(150.0));
        assert_eq!(plausible_bias_ma(150.01), None);
        assert_eq!(plausible_bias_ma(-0.01), None);
        // Sentinels raw and after /100 scaling
        assert_eq!(plausible_bias_ma(65535.0), None);
        assert_eq!(plausible_bias_ma(655.35), None);
        // Non-finite inputs
        assert_eq!(plausible_bias_ma(f64::NAN), None);
        assert_eq!(plausible_bias_ma(f64::INFINITY), None);
    }
}
