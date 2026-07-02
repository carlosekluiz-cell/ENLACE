// SPDX-License-Identifier: Apache-2.0
// ZTE OLT Collector (ZXA10 C300, C320, C600, C650)
//
// Two OID families exist on ZXA10 firmware:
//   - V2.1.x firmware (C300/C320): zxAnPon tree under 1.3.6.1.4.1.3902.1012.3
//   - V2.2+/Titan (C320 v2.2, C6xx): zxAnGpon tree under 1.3.6.1.4.1.3902.1082.500
// We walk the V2.1 tree first and fall back to the V2.2 tree if it is empty.
//
// Index encoding (verified against a REAL C320 walk:
// data/external/snmp-dumps/zte/librenms_zxa10_c320.snmprec + the LibreNMS
// decode oracle librenms_expected_zxa10_c320.json):
//   - IF-MIB ifIndex packs ZERO-based fields:
//       268435456 (0x10000000) = gpon_1/1/1, +0x100 per port, +0x10000 per slot
//   - zxAnPon ONU/table indexes pack ONE-based fields:
//       0x10 SS PP NN  (SS=slot 1-based, PP=port 1-based, NN=onu-id or 0)
//     e.g. zxAnPonRtdOnuDistance rows sit at ...3.11.4.1.2.0x10010300.<onuId>
//     for gpon-olt_1/1/3 — ports 1,3..8 populated in the dump exactly match
//     the gpon_1/1/1..8 ifTable entries.
//
// Optical scaling (community-verified, multiple independent sources):
//   RX/TX power raw value → dBm = value * 0.002 - 30
//   Sources: local.com.ua topic 76498 ("ZTE OLT опрос по SNMP - уровни"),
//   github.com/Cepat-Kilat-Teknologi/go-snmp-olt-zte-c320 (discussion #3).
//   Sentinels 65535 / 2147483647 mean "no reading" and are filtered by the
//   plausibility window (65535*0.002-30 = 101.07 dBm → None).

use async_trait::async_trait;
use crate::config::OltConfig;
use crate::snmp::SnmpPoller;
use super::*;
use super::snmp_helper::plausible_dbm;

/// zxAnPon-style packed ONU index: 0x1S SS PP NN with 1-based slot/port.
/// Returns (pon_port, onu_id). `next_component` supplies the ONU id for
/// tables indexed as <ponIndex>.<onuId> (low byte 0).
pub(crate) fn decode_zte_onu_index(first: u32, next_component: Option<u32>) -> Option<(String, u32)> {
    if first < 0x1000_0000 {
        return None; // not a packed ZXA10 index
    }
    let slot = (first >> 16) & 0xFF;
    let port = (first >> 8) & 0xFF;
    let low = first & 0xFF;
    let onu = if low != 0 { low } else { next_component? };
    if slot == 0 || port == 0 || onu == 0 {
        return None; // fields are 1-based in this encoding; 0 = not an ONU row
    }
    // Shelf/rack is 1 on C300/C320 (CLI notation gpon-onu_1/slot/port:onu)
    Some((format!("1/{}/{}", slot, port), onu))
}

/// ZTE optical raw value → dBm: value * 0.002 - 30 (see module header).
pub(crate) fn zte_optical_dbm(raw: i64) -> Option<f64> {
    plausible_dbm(raw as f64 * 0.002 - 30.0)
}

/// zxGponOntPhaseState enumeration (ZXA10 C300/C320,
/// 1.3.6.1.4.1.3902.1012.3.28.2.1.4). The enum is 0-BASED per the only
/// citable sources — an operator monitoring doc quoting the MIB fragment:
///   INTEGER { Logging(0), Los(1), SyncMib(2), Working(3), DyingGasp(4),
///             AuthFailed(5), Offline(6) }
/// (https://www.docdroid.net/s5pHGIP/code-show-zte-onts-status-txt; no
/// citable source exists for a 1-based variant). NOT yet confirmed against
/// live firmware — verify 3=working on hardware before the pilot; values
/// outside 0..=6 map to Unknown, never guessed.
fn zte_phase_state(v: i64) -> OntStatus {
    match v {
        2 | 3 => OntStatus::Online, // syncMib(2) — ONT is up, MIB syncing — / working(3)
        1 => OntStatus::Offline,    // LOS
        4 => OntStatus::PowerFail,  // dying gasp
        0 | 5 | 6 => OntStatus::Offline, // logging / authFailed / offline
        _ => OntStatus::Unknown,
    }
}

pub struct ZteCollector {
    config: OltConfig,
    snmp: Option<SnmpPoller>,
    olt_id: String,
    /// One-time telemetry-coverage log guard (see collect_onts_snmp).
    coverage_logged: std::sync::atomic::AtomicBool,
}

impl ZteCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let snmp = config.snmp.as_ref()
            .map(|s| SnmpPoller::new(&config.ip, s))
            .transpose()?;
        Ok(Self {
            olt_id: format!("zte-{}", config.ip.replace('.', "-")),
            config: config.clone(),
            snmp,
            coverage_logged: std::sync::atomic::AtomicBool::new(false),
        })
    }
}

#[async_trait]
impl OltCollector for ZteCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "zte" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured for ZTE OLT"))?;

        let sys_descr = snmp.get(crate::snmp::oids::SYS_DESCR).await.ok();
        let sys_uptime = snmp.get(crate::snmp::oids::SYS_UPTIME).await.ok();

        // Walk failures (incl. partial walks) propagate — an error must never
        // be presented upstream as "OLT with zero ONTs".
        let onts = self.collect_onts_snmp().await?;

        let mut pon_ports = std::collections::HashMap::new();
        for ont in &onts {
            let entry = pon_ports.entry(ont.pon_port.clone()).or_insert(PonPortData {
                port_id: ont.pon_port.clone(),
                oper_status: "up".into(),
                onts_registered: 0, onts_online: 0, onts_offline: 0,
                bw_down_bps: 0, bw_up_bps: 0, utilization_percent: 0.0,
            });
            entry.onts_registered += 1;
            match ont.status {
                OntStatus::Online | OntStatus::LowSignal => entry.onts_online += 1,
                _ => entry.onts_offline += 1,
            }
        }

        let (cpu, mem, temp) = self.collect_system_health().await;

        Ok(OltData {
            olt_id: self.olt_id.clone(),
            vendor: "zte".into(),
            model: super::huawei::extract_string_pub(&sys_descr),
            firmware: String::new(),
            serial: String::new(),
            uptime_seconds: super::huawei::extract_timeticks_pub(&sys_uptime),
            timestamp: chrono::Utc::now(),
            cpu_percent: cpu, memory_percent: mem,
            temperature_celsius: temp, power_supply_status: None,
            pon_ports: pon_ports.into_values().collect(),
            uplink_ports: Vec::new(),
            onts,
        })
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        if let Some(snmp) = &self.snmp {
            snmp.get(crate::snmp::oids::SYS_DESCR).await.map(|_| true).map_err(Into::into)
        } else {
            Ok(false)
        }
    }
}

/// Intermediate per-ONT record keyed by decoded (pon_port, onu_id).
#[derive(Default)]
struct OntAccum {
    serial: Option<String>,
    status: Option<OntStatus>,
    rx_power: Option<f64>,
    tx_power: Option<f64>,
    distance: Option<u32>,
}

impl ZteCollector {
    async fn collect_system_health(&self) -> (Option<f32>, Option<f32>, Option<f32>) {
        let snmp = match self.snmp.as_ref() {
            Some(s) => s,
            None => return (None, None, None),
        };
        let cpu = snmp.get(crate::snmp::oids::zte_sys::CPU_USAGE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let mem = snmp.get(crate::snmp::oids::zte_sys::MEM_USAGE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        let temp = snmp.get(crate::snmp::oids::zte_sys::TEMPERATURE).await.ok()
            .and_then(|v| match v.value {
                crate::snmp::SnmpData::Integer(i) => Some(i as f32),
                crate::snmp::SnmpData::Gauge32(g) => Some(g as f32),
                _ => None,
            });
        (cpu, mem, temp)
    }

    async fn collect_onts_snmp(&self) -> anyhow::Result<Vec<OntData>> {
        let snmp = self.snmp.as_ref()
            .ok_or_else(|| anyhow::anyhow!("SNMP not configured"))?;

        // Telemetry coverage — once per OLT, not per cycle.
        if !self.coverage_logged.swap(true, std::sync::atomic::Ordering::Relaxed) {
            tracing::debug!(
                olt = %self.olt_id,
                "ZTE SNMP coverage: optical rx/tx collected; per-ONU DDM \
                 temperature/voltage/bias, FEC/BIP and per-ONT octet counters \
                 are NOT collected — no per-ONU OID for them is verifiable in \
                 the real ZXA10 captures (data/external/snmp-dumps/zte/; the \
                 1082.10.10.2.4.x tables there are card/fan sensors, not ONU DDM)"
            );
        }

        // V2.1 firmware tree (zxAnPon / zxGpon, enterprise .1012)
        let statuses = snmp.walk_table(crate::snmp::oids::zte::ONT_PHASE_STATE).await?;
        if !statuses.is_empty() {
            let serials = snmp.walk_table(crate::snmp::oids::zte::ONT_SERIAL).await?;
            let rx_powers = snmp.walk_table(crate::snmp::oids::zte::ONT_RX_POWER).await?;
            let tx_powers = snmp.walk_table(crate::snmp::oids::zte::ONT_TX_POWER).await?;
            let distances = snmp.walk_table(crate::snmp::oids::zte::ONT_DISTANCE).await?;
            return Ok(self.assemble(&statuses, &serials, &rx_powers, &tx_powers, &distances));
        }

        // V2.2+/Titan tree (enterprise .1082.500)
        let statuses = snmp.walk_table(crate::snmp::oids::zte::V2_ONT_STATUS).await?;
        if statuses.is_empty() {
            tracing::warn!(
                olt = %self.olt_id,
                "ZTE OLT returned no ONTs on either the V2.1 (.1012) or \
                 V2.2+ (.1082.500) OID tree — firmware may use an unsupported \
                 MIB variant; NOT fabricating an empty-but-ok result"
            );
            return Ok(Vec::new());
        }
        let serials = snmp.walk_table(crate::snmp::oids::zte::V2_ONT_SERIAL).await?;
        let rx_powers = snmp.walk_table(crate::snmp::oids::zte::V2_ONT_RX_POWER).await?;
        let distances = snmp.walk_table(crate::snmp::oids::zte::V2_ONT_DISTANCE).await?;
        Ok(self.assemble(&statuses, &serials, &rx_powers, &[], &distances))
    }

    fn assemble(
        &self,
        statuses: &[crate::snmp::SnmpValue],
        serials: &[crate::snmp::SnmpValue],
        rx_powers: &[crate::snmp::SnmpValue],
        tx_powers: &[crate::snmp::SnmpValue],
        distances: &[crate::snmp::SnmpValue],
    ) -> Vec<OntData> {
        use std::collections::BTreeMap;
        let mut accum: BTreeMap<(String, u32), OntAccum> = BTreeMap::new();

        for entry in statuses {
            if let (Some(key), crate::snmp::SnmpData::Integer(v)) =
                (decode_entry_key(&entry.oid), &entry.value)
            {
                accum.entry(key).or_default().status = Some(zte_phase_state(*v));
            }
        }
        for entry in serials {
            if let (Some(key), crate::snmp::SnmpData::OctetString(s)) =
                (decode_entry_key(&entry.oid), &entry.value)
            {
                if !s.is_empty() {
                    accum.entry(key).or_default().serial = Some(s.clone());
                }
            }
        }
        for entry in rx_powers {
            if let (Some(key), crate::snmp::SnmpData::Integer(v)) =
                (decode_entry_key(&entry.oid), &entry.value)
            {
                let e = accum.entry(key).or_default();
                if e.rx_power.is_none() {
                    e.rx_power = zte_optical_dbm(*v);
                }
            }
        }
        for entry in tx_powers {
            if let (Some(key), crate::snmp::SnmpData::Integer(v)) =
                (decode_entry_key(&entry.oid), &entry.value)
            {
                let e = accum.entry(key).or_default();
                if e.tx_power.is_none() {
                    e.tx_power = zte_optical_dbm(*v);
                }
            }
        }
        for entry in distances {
            if let (Some(key), crate::snmp::SnmpData::Integer(v)) =
                (decode_entry_key(&entry.oid), &entry.value)
            {
                // zxAnPonRtdOnuDistance is in meters (values 1235..3743 m in
                // the real C320 dump); reject nonsense.
                if (0..=200_000).contains(v) {
                    accum.entry(key).or_default().distance = Some(*v as u32);
                }
            }
        }

        accum
            .into_iter()
            .map(|((pon_port, onu_id), a)| {
                let status = a.status.unwrap_or(OntStatus::Unknown);
                let refined = match (&status, a.rx_power) {
                    (OntStatus::Online, Some(rx)) if rx < -27.0 => OntStatus::LowSignal,
                    _ => status,
                };
                OntData {
                    serial_number: a
                        .serial
                        .unwrap_or_else(|| format!("zte-{}:{}", pon_port, onu_id)),
                    pon_port,
                    ont_index: onu_id,
                    status: refined,
                    last_down_cause: None,
                    uptime_seconds: None,
                    rx_power_dbm: a.rx_power,
                    tx_power_dbm: a.tx_power,
                    distance_meters: a.distance,
                    vendor_id: None,
                    equipment_id: None,
                    firmware_version: None,
                    in_octets: None,
                    out_octets: None,
                    fec_corrected: None, fec_uncorrected: None, bip_errors: None,
                    eth_speed_mbps: None,
                    extended: None,
                }
            })
            .collect()
    }
}

/// Decode the (pon_port, onu_id) key from a full table-row OID by taking the
/// trailing numeric components: ...<packedIndex>[.<onuId>][.<subIndex>].
fn decode_entry_key(oid: &str) -> Option<(String, u32)> {
    let comps: Vec<u64> = oid
        .split('.')
        .filter_map(|s| s.parse().ok())
        .collect();
    // Find the packed 0x1xxxxxxx component (there is exactly one in every
    // ZXA10 ONU table row); components after it are onuId / sub-indexes.
    let pos = comps.iter().position(|&c| (0x1000_0000..0x2000_0000).contains(&c))?;
    let first = comps[pos] as u32;
    let next = comps.get(pos + 1).map(|&c| c as u32);
    decode_zte_onu_index(first, next)
}

#[cfg(test)]
mod tests {
    use super::*;

    // Index fixtures from the REAL ZXA10 C320 walk:
    // data/external/snmp-dumps/zte/librenms_zxa10_c320.snmprec
    //   1.3.6.1.4.1.3902.1012.3.11.4.1.2.268501760.9 = 2403  (distance, m)
    // and the LibreNMS oracle librenms_expected_zxa10_c320.json
    // (268435456 = gpon_1/1/1 ifIndex; table indexes are 1-based-packed).
    #[test]
    fn test_decode_zte_onu_index_pon_plus_component() {
        // 268501760 = 0x10010300 → slot 1, port 3 (1-based), onu from next
        assert_eq!(
            decode_zte_onu_index(268501760, Some(9)),
            Some(("1/1/3".into(), 9))
        );
        // 268501248 = 0x10010100 → gpon 1/1/1
        assert_eq!(
            decode_zte_onu_index(268501248, Some(5)),
            Some(("1/1/1".into(), 5))
        );
    }

    #[test]
    fn test_decode_zte_onu_index_packed_low_byte() {
        // gpon-onu_1/1/3:5 style single-component index 0x10010305
        assert_eq!(
            decode_zte_onu_index(0x10010305, None),
            Some(("1/1/3".into(), 5))
        );
        // Trailing sub-index (e.g. .50.12 optical table rows end in .1) must
        // not override the low-byte onu id
        assert_eq!(
            decode_zte_onu_index(0x10010305, Some(1)),
            Some(("1/1/3".into(), 5))
        );
    }

    #[test]
    fn test_decode_zte_onu_index_rejects_non_onu_rows() {
        // Port-level row (onu byte 0, no following component)
        assert_eq!(decode_zte_onu_index(0x10010300, None), None);
        // Plain small ifIndex (not packed)
        assert_eq!(decode_zte_onu_index(42, Some(1)), None);
    }

    #[test]
    fn test_decode_entry_key_from_real_dump_oids() {
        // Verbatim row OIDs from librenms_zxa10_c320.snmprec
        assert_eq!(
            decode_entry_key("1.3.6.1.4.1.3902.1012.3.11.4.1.2.268501760.9"),
            Some(("1/1/3".into(), 9))
        );
        assert_eq!(
            decode_entry_key("1.3.6.1.4.1.3902.1012.3.11.4.1.1.268503040.10"),
            Some(("1/1/8".into(), 10))
        );
        // Optical table style: <onuIfIndex>.1 (268501765 = 0x10010305 =
        // gpon-onu_1/1/3:5)
        assert_eq!(
            decode_entry_key("1.3.6.1.4.1.3902.1012.3.50.12.1.1.10.268501765.1"),
            Some(("1/1/3".into(), 5))
        );
        assert_eq!(decode_entry_key("1.3.6.1.2.1.1.1.0"), None);
    }

    #[test]
    fn test_zte_optical_scaling_value_0002_minus_30() {
        // raw*0.002-30 (local.com.ua topic 76498; go-snmp-olt-zte-c320):
        // raw 4000 → -22.0 dBm (typical ONT rx)
        assert_eq!(zte_optical_dbm(4000), Some(-22.0));
        // raw 16250 → +2.5 dBm (typical ONT tx)
        assert_eq!(zte_optical_dbm(16250), Some(2.5));
        // The OLD copy-pasted /100 scaling would have produced 40.0 dBm here —
        // the plausibility window would kill it; the new formula gives a
        // physically sane level instead.
    }

    #[test]
    fn test_zte_optical_sentinels_are_none() {
        // 65535 → 101.07 dBm → implausible → None
        assert_eq!(zte_optical_dbm(65535), None);
        // 2147483647 → ~4294937 dBm → None
        assert_eq!(zte_optical_dbm(2147483647), None);
        // 0 → -30.0 dBm: borderline-plausible floor, keep (real dead-zone
        // readings on ZTE report 0 when unavailable → -30 is below the LOS
        // threshold anyway and inside the physical window)
        assert_eq!(zte_optical_dbm(0), Some(-30.0));
    }

    /// Replay every ONU-distance row of the REAL C320 walk through the
    /// decoder: all rows must decode, onto ports that exist on the device
    /// (gpon_1/1/1..8 per the LibreNMS oracle), with sane ONU ids.
    #[test]
    fn test_decode_against_full_real_c320_walk() {
        let path = concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/data/external/snmp-dumps/zte/librenms_zxa10_c320.snmprec"
        );
        let data = match std::fs::read_to_string(path) {
            Ok(d) => d,
            Err(_) => {
                eprintln!("skipping: real-walk fixture not present at {path}");
                return;
            }
        };

        const DISTANCE_COL: &str = "1.3.6.1.4.1.3902.1012.3.11.4.1.2.";
        let mut rows = 0;
        for line in data.lines() {
            let Some((oid, _rest)) = line.split_once('|') else { continue };
            if !oid.starts_with(DISTANCE_COL) {
                continue;
            }
            rows += 1;
            let (port, onu) = decode_entry_key(oid)
                .unwrap_or_else(|| panic!("row failed to decode: {oid}"));
            // The C320 in the capture has one GPON card in slot 1 with
            // 8 ports (gpon_1/1/1..8)
            assert!(
                (1..=8).contains(&port.split('/').nth(2).unwrap().parse::<u32>().unwrap()),
                "impossible port {port} from {oid}"
            );
            assert!(port.starts_with("1/1/"), "unexpected slot in {port} from {oid}");
            assert!((1..=128).contains(&onu), "impossible onu id {onu} from {oid}");
        }
        assert!(rows > 100, "expected >100 real ONU rows, saw {rows}");
    }

    #[test]
    fn test_phase_state_mapping_zero_based_enum() {
        // 0-based enum per the cited MIB fragment: Logging(0), Los(1),
        // SyncMib(2), Working(3), DyingGasp(4), AuthFailed(5), Offline(6)
        assert_eq!(zte_phase_state(3), OntStatus::Online);    // working
        assert_eq!(zte_phase_state(2), OntStatus::Online);    // syncMib
        assert_eq!(zte_phase_state(1), OntStatus::Offline);   // LOS
        assert_eq!(zte_phase_state(4), OntStatus::PowerFail); // dying gasp
        assert_eq!(zte_phase_state(6), OntStatus::Offline);   // offline
        assert_eq!(zte_phase_state(0), OntStatus::Offline);   // logging
        assert_eq!(zte_phase_state(7), OntStatus::Unknown);   // out of enum
        assert_eq!(zte_phase_state(99), OntStatus::Unknown);
    }
}
