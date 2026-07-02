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

/// Find a varbind in a list by matching OID suffix.
pub fn find_by_suffix<'a>(entries: &'a [SnmpValue], suffix: &str) -> Option<&'a SnmpData> {
    entries.iter()
        .find(|e| e.oid.ends_with(suffix))
        .map(|e| &e.value)
}
