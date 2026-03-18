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

        // Traverse edges (sorted by cumulative distance) to find the boundary edge.
        // Build a list of edges sorted by their "to" node's distance_from_olt_m.
        let mut edges_with_dist: Vec<(&str, &str, u32, u32)> = topo
            .edges
            .iter()
            .filter_map(|e| {
                let to_node = topo.nodes.get(&e.to)?;
                let from_node = topo.nodes.get(&e.from)?;
                Some((
                    e.from.as_str(),
                    e.to.as_str(),
                    e.length_m,
                    to_node.distance_from_olt_m,
                ))
            })
            .collect();

        // Sort by distance of destination node (OLT-outward traversal)
        edges_with_dist.sort_by_key(|&(_, _, _, d)| d);

        let mut last_online_node: Option<&str> = None;
        let mut first_offline_node: Option<&str> = None;
        let mut boundary_span_m = 0u32;

        for &(from, to, span_m, _dist) in &edges_with_dist {
            let from_status = node_has_online.get(from).copied().flatten();
            let to_status = node_has_online.get(to).copied().flatten();

            match (from_status, to_status) {
                (Some(true), Some(false)) => {
                    // Boundary edge found
                    last_online_node = Some(from);
                    first_offline_node = Some(to);
                    boundary_span_m = span_m;
                    break;
                }
                (None, Some(false)) => {
                    // "from" has no ONTs — trust the to-side verdict
                    last_online_node = Some(from);
                    first_offline_node = Some(to);
                    boundary_span_m = span_m;
                    break;
                }
                _ => {}
            }
        }

        let last_online = last_online_node?;
        let first_offline = first_offline_node?;

        let last_online_node_data = topo.nodes.get(last_online)?;
        let break_est = last_online_node_data.distance_from_olt_m + boundary_span_m / 2;

        let description = format!(
            "Break on span {} → {} (estimated {} m from OLT, span {} m)",
            last_online, first_offline, break_est, boundary_span_m
        );

        Some(FaultLocation {
            estimated_distance_m: break_est,
            description,
            method: "topology".into(),
            boundary: Some(BoundaryInfo {
                last_online_node: last_online.to_string(),
                first_offline_node: first_offline.to_string(),
                span_length_m: boundary_span_m,
            }),
        })
    }
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
            affected_onts: affected
                .into_iter()
                .map(|(s, d)| AffectedOnt {
                    serial_number: s.into(),
                    distance_meters: Some(d),
                    last_rx_dbm: Some(-30.0),
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
        // The break should be between SP002 (online side) and DP001 (offline side)
        assert_eq!(boundary.last_online_node, "SP002");
        assert_eq!(boundary.first_offline_node, "DP001");
        assert_eq!(boundary.span_length_m, 400);

        // Estimated break = 1300 (SP002) + 400/2 = 1500 m
        assert_eq!(loc.estimated_distance_m, 1500);
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
