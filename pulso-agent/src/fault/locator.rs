// SPDX-License-Identifier: Apache-2.0
// Fault locator — narrows down the break point on a PON fibre run.
//
// Strategy:
//   1. If a FibreTopology is available, use topology-aware boundary search.
//   2. Otherwise fall back to a pure distance-based estimate.

use serde::{Deserialize, Serialize};
use crate::fault::detector::{AffectedOnt, FaultEvent};
use crate::fault::topology::FibreTopology;

/// The estimated location of a fibre break
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaultLocation {
    /// Estimated distance from the OLT to the break point (metres)
    pub estimated_distance_m: u32,
    /// Lower bound of the break location (metres from OLT)
    pub min_distance_m: u32,
    /// Upper bound of the break location (metres from OLT)
    pub max_distance_m: u32,
    /// True when the evidence does not pin the break to a single span
    /// (e.g. undecided no-ONT nodes sit between the last confirmed-online
    /// node and the first confirmed-offline node)
    pub ambiguous: bool,
    /// Human-readable description of where the break is
    pub description: String,
    /// Which algorithm produced this estimate
    pub method: String,
    /// Optional boundary info (topology-based only)
    pub boundary: Option<BoundaryInfo>,
}

/// The topology edge that the break sits on
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundaryInfo {
    /// Last online node (closest to OLT that still has online ONTs)
    pub last_online_node: String,
    /// First offline node (first node beyond the break)
    pub first_offline_node: String,
    /// The break lies somewhere on this span (metres)
    pub span_length_m: u32,
}

pub struct FaultLocator<'a> {
    topology: &'a FibreTopology,
}

impl<'a> FaultLocator<'a> {
    pub fn new(topology: &'a FibreTopology) -> Self {
        Self { topology }
    }

    /// Top-level entry point.
    ///
    /// `event`       — the fault event produced by `FaultDetector`
    /// `online_onts` — serials of ONTs on the same port that are still online
    pub fn locate(&self, event: &FaultEvent, online_onts: &[String]) -> FaultLocation {
        // Try topology-aware algorithm first if we have nodes
        if !self.topology.nodes.is_empty() {
            if let Some(loc) = self.locate_with_topology(event, online_onts) {
                return loc;
            }
        }
        // Fall back to distance-only
        self.locate_distance_only(event, online_onts)
    }

    /// Pure distance-based estimator.
    ///
    /// The break is placed at the midpoint between the furthest online ONT
    /// and the nearest offline ONT (sorted by `distance_meters`).
    /// If all ONTs are offline the break is placed at the nearest offline ONT.
    pub fn locate_distance_only(
        &self,
        event: &FaultEvent,
        online_onts: &[String],
    ) -> FaultLocation {
        // Collect distances of affected (offline) ONTs
        let offline_dists: Vec<u32> = event
            .affected_onts
            .iter()
            .filter_map(|o| o.distance_meters)
            .collect();

        if offline_dists.is_empty() {
            return FaultLocation {
                estimated_distance_m: 0,
                min_distance_m: 0,
                max_distance_m: 0,
                ambiguous: true,
                description: "No distance data available for affected ONTs".into(),
                method: "distance_only".into(),
                boundary: None,
            };
        }

        let nearest_offline = *offline_dists.iter().min().unwrap();

        // Find the furthest *online* ONT with a known distance
        // We need to look up online ONTs in the event's ONT list by serial
        // The caller supplies the serial list; the distance is in AffectedOnt only for
        // offline ones, so we accept online serials but have no distance for them here.
        // We therefore use the nearest offline ONT as the break upper-bound and
        // compare against zero (OLT) as the lower bound when no online distances exist.
        let _ = online_onts; // reserved for future: online ONT distances via topology

        let estimated = nearest_offline;
        let description = format!(
            "Break estimated within {} m of OLT (nearest offline ONT at {} m)",
            estimated, nearest_offline
        );

        FaultLocation {
            estimated_distance_m: estimated,
            min_distance_m: 0,
            max_distance_m: nearest_offline,
            ambiguous: true,
            description,
            method: "distance_only".into(),
            boundary: None,
        }
    }

    /// Topology-aware locator.
    ///
    /// Walks the topology chain from the OLT outward.  The break sits on the
    /// edge between the last node that has at least one online ONT attached
    /// and the first node that has only offline ONTs attached.
    ///
    /// Returns `None` if the topology doesn't contain enough information.
    pub fn locate_with_topology(
        &self,
        event: &FaultEvent,
        online_onts: &[String],
    ) -> Option<FaultLocation> {
        let topo = self.topology;

        if topo.nodes.is_empty() || topo.edges.is_empty() {
            return None;
        }

        // Build a set of offline serials (from event) and online serials
        let offline_serials: std::collections::HashSet<&str> = event
            .affected_onts
            .iter()
            .map(|o| o.serial_number.as_str())
            .collect();

        let online_serials: std::collections::HashSet<&str> =
            online_onts.iter().map(|s| s.as_str()).collect();

        // For each topology node, decide if it's "online" (has at least one
        // online ONT) or "offline" (all attached ONTs are offline or none mapped).
        // Nodes with no mapped ONTs are treated as transparent pass-through.
        let node_has_online: std::collections::HashMap<&str, Option<bool>> = topo
            .nodes
            .keys()
            .map(|node_id| {
                let node_str = node_id.as_str();
                let attached: Vec<&str> = topo
                    .ont_to_node
                    .iter()
                    .filter(|(_, n)| n.as_str() == node_str)
                    .map(|(serial, _)| serial.as_str())
                    .collect();

                if attached.is_empty() {
                    // No ONTs mapped — can't decide from ONT data
                    (node_str, None)
                } else {
                    let any_online = attached.iter().any(|s| online_serials.contains(*s));
                    let any_offline = attached.iter().any(|s| offline_serials.contains(*s));
                    if any_online {
                        (node_str, Some(true))
                    } else if any_offline {
                        (node_str, Some(false))
                    } else {
                        (node_str, None)
                    }
                }
            })
            .collect();

        // Build adjacency (from → children) for the downstream-evidence walk
        let mut children: std::collections::HashMap<&str, Vec<&str>> =
            std::collections::HashMap::new();
        for e in &topo.edges {
            if topo.nodes.contains_key(&e.from) && topo.nodes.contains_key(&e.to) {
                children
                    .entry(e.from.as_str())
                    .or_default()
                    .push(e.to.as_str());
            }
        }

        // Propagate ONT evidence up the tree: a node with online ONTs anywhere
        // downstream has POSITIVE evidence that light still reaches it.
        // Undecided (no-ONT) nodes never count as online on their own — that
        // was the bug that sent splice crews past the break.
        let mut memo: std::collections::HashMap<&str, (bool, bool)> =
            std::collections::HashMap::new();
        for node_id in topo.nodes.keys() {
            subtree_status(node_id.as_str(), &children, &node_has_online, &mut memo);
        }

        // The boundary edge: light confirmed to reach `from` (online evidence
        // downstream of it), while the subtree under `to` has offline ONTs and
        // no online ones. Pick the shallowest such edge.
        let mut candidates: Vec<(&str, &str, u32, u32, u32)> = Vec::new();
        for e in &topo.edges {
            let from_node = match topo.nodes.get(&e.from) { Some(n) => n, None => continue };
            let to_node = match topo.nodes.get(&e.to) { Some(n) => n, None => continue };
            let (from_online, _) = *memo.get(e.from.as_str()).unwrap_or(&(false, false));
            let (to_online, to_offline) = *memo.get(e.to.as_str()).unwrap_or(&(false, false));
            if from_online && !to_online && to_offline {
                candidates.push((
                    e.from.as_str(),
                    e.to.as_str(),
                    e.length_m,
                    from_node.distance_from_olt_m,
                    to_node.distance_from_olt_m,
                ));
            }
        }
        candidates.sort_by_key(|&(_, _, _, _, to_dist)| to_dist);

        // No positive upstream-online evidence anywhere → decline, and let the
        // caller fall back to the distance-only estimator.
        let &(from, to, span_m, from_dist, to_dist) = candidates.first()?;

        let to_status = node_has_online.get(to).copied().flatten();
        if to_status == Some(false) {
            // Exact boundary: the offline evidence sits directly on `to`.
            let min = from_dist;
            let max = to_dist.max(from_dist + span_m);
            let break_est = from_dist + span_m / 2;
            let description = format!(
                "Break on span {} → {} (estimated {} m from OLT, range {}–{} m)",
                from, to, break_est, min, max
            );
            return Some(FaultLocation {
                estimated_distance_m: break_est,
                min_distance_m: min,
                max_distance_m: max,
                ambiguous: false,
                description,
                method: "topology".into(),
                boundary: Some(BoundaryInfo {
                    last_online_node: from.to_string(),
                    first_offline_node: to.to_string(),
                    span_length_m: span_m,
                }),
            });
        }

        // `to` itself is undecided (no ONTs mapped): the break lies somewhere
        // between the confirmed-online node and the shallowest node below `to`
        // with direct offline evidence — report the RANGE, not a point.
        let mut queue = vec![to];
        let mut seen: std::collections::HashSet<&str> = std::collections::HashSet::new();
        let mut first_offline: Option<(&str, u32)> = None;
        while let Some(n) = queue.pop() {
            if !seen.insert(n) {
                continue;
            }
            if node_has_online.get(n).copied().flatten() == Some(false) {
                if let Some(node) = topo.nodes.get(n) {
                    let d = node.distance_from_olt_m;
                    if first_offline.map(|(_, bd)| d < bd).unwrap_or(true) {
                        first_offline = Some((n, d));
                    }
                }
            }
            if let Some(kids) = children.get(n) {
                queue.extend(kids.iter().copied());
            }
        }
        let (offline_node, max) = first_offline?;

        let min = from_dist;
        let span = max.saturating_sub(min);
        let break_est = min + span / 2;
        let description = format!(
            "Break between {} and {} (evidence ambiguous — undecided nodes in \
             between; range {}–{} m from OLT)",
            from, offline_node, min, max
        );
        Some(FaultLocation {
            estimated_distance_m: break_est,
            min_distance_m: min,
            max_distance_m: max,
            ambiguous: true,
            description,
            method: "topology".into(),
            boundary: Some(BoundaryInfo {
                last_online_node: from.to_string(),
                first_offline_node: offline_node.to_string(),
                span_length_m: span,
            }),
        })
    }
}

/// Post-order walk: does the subtree rooted at `node` contain online /
/// offline ONTs? Memoized; tolerates cycles in malformed topologies via a
/// provisional memo entry.
fn subtree_status<'a>(
    node: &'a str,
    children: &std::collections::HashMap<&'a str, Vec<&'a str>>,
    node_has_online: &std::collections::HashMap<&'a str, Option<bool>>,
    memo: &mut std::collections::HashMap<&'a str, (bool, bool)>,
) -> (bool, bool) {
    if let Some(&status) = memo.get(node) {
        return status;
    }
    memo.insert(node, (false, false)); // cycle guard
    let own = node_has_online.get(node).copied().flatten();
    let mut has_online = own == Some(true);
    let mut has_offline = own == Some(false);
    if let Some(kids) = children.get(node) {
        for kid in kids {
            let (online, offline) = subtree_status(kid, children, node_has_online, memo);
            has_online |= online;
            has_offline |= offline;
        }
    }
    memo.insert(node, (has_online, has_offline));
    (has_online, has_offline)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fault::topology::FibreTopology;
    use chrono::Utc;

    fn make_event(port: &str, affected: Vec<(&str, u32)>) -> FaultEvent {
        FaultEvent {
            timestamp: Utc::now(),
            pon_port: port.into(),
            olt_id: "OLT-01".into(),
            severity: "major".into(),
            fault_type: crate::fault::detector::FaultType::FibreCut,
            affected_onts: affected
                .into_iter()
                .map(|(s, d)| AffectedOnt {
                    serial_number: s.into(),
                    distance_meters: Some(d),
                    last_rx_dbm: Some(-30.0),
                    had_dying_gasp: false,
                })
                .collect(),
            detection_latency_seconds: 5,
        }
    }

    #[test]
    fn test_distance_only_locator() {
        let topo = FibreTopology::empty();
        let locator = FaultLocator::new(&topo);

        // Offline ONTs at 800, 1200, 1500 m; one online ONT (no distance in event)
        let event = make_event("0/1/0", vec![
            ("ONT001", 800),
            ("ONT002", 1200),
            ("ONT003", 1500),
        ]);
        let online = vec!["ONT000".to_string()];

        let loc = locator.locate_distance_only(&event, &online);
        assert_eq!(loc.method, "distance_only");
        // Nearest offline is 800 m — estimate should equal that
        assert_eq!(loc.estimated_distance_m, 800);
        assert!(loc.boundary.is_none());
        assert!(loc.description.contains("800 m"));
    }

    #[test]
    fn test_topology_locator() {
        // Use the synthetic London topology:
        //   OLT-BRIXTON (0m) → SP001 (800m) → SP002 (1300m) → DP001 (1700m)
        //                                    → SP003 (1900m) → DP002 (2250m)
        //
        // Scenario: all DP001 ONTs offline, DP002 online → break on SP002→DP001 (400m span)
        let topo = FibreTopology::synthetic();
        let locator = FaultLocator::new(&topo);

        // Build event: ADTN00000000 … ADTN00000006 are offline (all DP001 ONTs)
        let affected: Vec<(&str, u32)> = [
            ("ADTN00000000", 1700),
            ("ADTN00000001", 1700),
            ("ADTN00000002", 1700),
            ("ADTN00000003", 1700),
            ("ADTN00000004", 1700),
            ("ADTN00000005", 1700),
            ("ADTN00000006", 1700),
        ].to_vec();
        let event = make_event("0/1/0", affected);

        // Online ONTs: ADTN00000007 … ADTN00000013 (all DP002)
        let online: Vec<String> = (7u8..=13)
            .map(|i| format!("ADTN{:08X}", i))
            .collect();

        let loc = locator.locate(&event, &online);
        assert_eq!(loc.method, "topology", "should use topology algorithm");

        let boundary = loc.boundary.as_ref().expect("topology result must have boundary info");
        // DP002 (fed through SP002 → SP003) is online, so light provably
        // reaches SP002 — the break sits on the SP002 → DP001 span.
        assert_eq!(boundary.last_online_node, "SP002");
        assert_eq!(boundary.first_offline_node, "DP001");
        assert_eq!(boundary.span_length_m, 400);
        assert!(!loc.ambiguous);

        // Estimated break = 1300 (SP002) + 400/2 = 1500 m, range 1300–1700 m
        assert_eq!(loc.estimated_distance_m, 1500);
        assert_eq!(loc.min_distance_m, 1300);
        assert_eq!(loc.max_distance_m, 1700);
    }

    #[test]
    fn test_all_offline_topology_falls_back_to_distance_only() {
        // Regression for the (None, Some(false)) first-match bug: a feeder cut
        // near the OLT with NO online ONTs anywhere used to be "localized" to
        // the SP002→DP001 span at ~1500 m. Without positive upstream-online
        // evidence the topology locator must decline and fall back.
        let topo = FibreTopology::synthetic();
        let locator = FaultLocator::new(&topo);

        // Every ONT on the port is offline (cut at ~400 m, before SP001)
        let affected: Vec<(&str, u32)> = vec![
            ("ADTN00000000", 1700), ("ADTN00000001", 1700), ("ADTN00000002", 1700),
            ("ADTN00000003", 1700), ("ADTN00000004", 1700), ("ADTN00000005", 1700),
            ("ADTN00000006", 1700),
            ("ADTN00000007", 2250), ("ADTN00000008", 2250), ("ADTN00000009", 2250),
            ("ADTN0000000A", 2250), ("ADTN0000000B", 2250), ("ADTN0000000C", 2250),
            ("ADTN0000000D", 2250),
        ];
        let event = make_event("0/1/0", affected);
        let online: Vec<String> = vec![];

        let loc = locator.locate(&event, &online);
        assert_eq!(loc.method, "distance_only",
            "no upstream online evidence → must not fire the topology rule");
        assert!(loc.ambiguous);
        assert_eq!(loc.min_distance_m, 0);
        assert_eq!(loc.max_distance_m, 1700);
    }

    #[test]
    fn test_ambiguous_boundary_reports_range() {
        // Chain: OLT(0m) → DP-A(500m, online ONT) → SP-B(1000m, no ONTs)
        //        → DP-C(1500m, offline ONTs).
        // The break is somewhere between 500 m and 1500 m — the locator must
        // report that RANGE, anchored on the confirmed-online node, not a
        // point estimate on the SP-B→DP-C span.
        use crate::fault::topology::{FibreTopology, TopologyNode, TopologyEdge, NodeType};

        let mut topo = FibreTopology::empty();
        for (id, dist, node_type) in [
            ("OLT", 0u32, NodeType::Olt),
            ("DP-A", 500, NodeType::DistributionPoint),
            ("SP-B", 1000, NodeType::SplicePoint),
            ("DP-C", 1500, NodeType::DistributionPoint),
        ] {
            topo.nodes.insert(id.to_string(), TopologyNode {
                id: id.to_string(),
                lat: 0.0,
                lon: 0.0,
                node_type,
                distance_from_olt_m: dist,
            });
        }
        topo.edges = vec![
            TopologyEdge { from: "OLT".into(), to: "DP-A".into(), length_m: 500 },
            TopologyEdge { from: "DP-A".into(), to: "SP-B".into(), length_m: 500 },
            TopologyEdge { from: "SP-B".into(), to: "DP-C".into(), length_m: 500 },
        ];
        topo.ont_to_node.insert("ONLINE1".into(), "DP-A".into());
        for i in 0..5 {
            topo.ont_to_node.insert(format!("OFF{}", i), "DP-C".into());
        }

        let locator = FaultLocator::new(&topo);
        let affected: Vec<(&str, u32)> = vec![
            ("OFF0", 1500), ("OFF1", 1500), ("OFF2", 1500), ("OFF3", 1500), ("OFF4", 1500),
        ];
        let event = make_event("0/1/0", affected);
        let online = vec!["ONLINE1".to_string()];

        let loc = locator.locate(&event, &online);
        assert_eq!(loc.method, "topology");
        assert!(loc.ambiguous, "undecided SP-B in the path → evidence is ambiguous");
        assert_eq!(loc.min_distance_m, 500, "range starts at last confirmed-online node");
        assert_eq!(loc.max_distance_m, 1500, "range ends at first offline node");
        let boundary = loc.boundary.as_ref().unwrap();
        assert_eq!(boundary.last_online_node, "DP-A");
        assert_eq!(boundary.first_offline_node, "DP-C");
        assert_eq!(boundary.span_length_m, 1000);
        assert!(loc.description.contains("ambiguous"));
    }

    #[test]
    fn test_all_onts_offline() {
        // When every ONT is offline (total blackout) the locator should
        // still produce a result rather than panicking or returning None.
        let topo = FibreTopology::empty();
        let locator = FaultLocator::new(&topo);

        let event = make_event("0/1/0", vec![
            ("ONT001", 300),
            ("ONT002", 600),
            ("ONT003", 900),
        ]);
        let online: Vec<String> = vec![]; // nobody online

        let loc = locator.locate(&event, &online);
        // Distance-only fallback; nearest offline = 300 m
        assert_eq!(loc.estimated_distance_m, 300);
        assert_eq!(loc.method, "distance_only");
    }
}
