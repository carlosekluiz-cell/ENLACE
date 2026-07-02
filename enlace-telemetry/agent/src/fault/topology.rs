// SPDX-License-Identifier: Apache-2.0
// Fibre route model — three data sources: CSV import, distance inference, synthetic

use std::collections::HashMap;
use std::path::Path;
use serde::{Deserialize, Serialize};

/// Type of node in the fibre topology graph
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum NodeType {
    Olt,
    SplicePoint,
    DistributionPoint,
}

/// A single node in the topology (OLT rack, splice joint, distribution box)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopologyNode {
    pub id: String,
    pub lat: f64,
    pub lon: f64,
    pub node_type: NodeType,
    /// Cumulative fibre distance from the OLT headend (metres)
    pub distance_from_olt_m: u32,
}

/// A directed edge between two topology nodes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TopologyEdge {
    pub from: String,
    pub to: String,
    pub length_m: u32,
}

/// Full fibre topology for one PON port
#[derive(Debug, Clone, Default)]
pub struct FibreTopology {
    /// All nodes, keyed by node id
    pub nodes: HashMap<String, TopologyNode>,
    /// All edges (directed, from OLT outward)
    pub edges: Vec<TopologyEdge>,
    /// Maps ONT serial number → nearest topology node id
    pub ont_to_node: HashMap<String, String>,
}

impl FibreTopology {
    /// Return an empty topology (no nodes, no edges)
    pub fn empty() -> Self {
        Self::default()
    }

    /// Load topology according to the configured mode.
    ///
    /// `mode`        — "csv", "infer", or "synthetic"
    /// `import_path` — path used when mode == "csv"
    /// `port`        — PON port string (used when mode == "infer")
    /// `ont_distances` — (serial, distance_m) pairs (used when mode == "infer")
    pub fn load(
        mode: &str,
        import_path: Option<&Path>,
        port: &str,
        ont_distances: &[(String, u32)],
    ) -> Self {
        match mode {
            "csv" => {
                if let Some(path) = import_path {
                    Self::import_csv(path)
                } else {
                    tracing::warn!("topology mode=csv but no import_path configured — using empty");
                    Self::empty()
                }
            }
            "synthetic" => Self::synthetic(),
            _ => {
                // "infer" or anything else
                Self::infer_from_distances(port, ont_distances)
            }
        }
    }

    /// Import topology from a CSV directory.
    ///
    /// Expects two files in `dir`:
    ///   nodes.csv  — id,lat,lon,node_type,distance_from_olt_m
    ///   edges.csv  — from,to,length_m
    ///   ont_map.csv — serial,node_id   (optional)
    pub fn import_csv(dir: &Path) -> Self {
        let mut topo = Self::empty();

        // nodes.csv
        let nodes_path = dir.join("nodes.csv");
        if nodes_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&nodes_path) {
                for line in content.lines().skip(1) {
                    let parts: Vec<&str> = line.splitn(5, ',').collect();
                    if parts.len() < 5 { continue; }
                    let node_type = match parts[3].trim() {
                        "OLT" | "Olt" | "olt" => NodeType::Olt,
                        "SplicePoint" | "splice" => NodeType::SplicePoint,
                        _ => NodeType::DistributionPoint,
                    };
                    let id = parts[0].trim().to_string();
                    if let (Ok(lat), Ok(lon), Ok(dist)) = (
                        parts[1].trim().parse::<f64>(),
                        parts[2].trim().parse::<f64>(),
                        parts[4].trim().parse::<u32>(),
                    ) {
                        topo.nodes.insert(id.clone(), TopologyNode {
                            id,
                            lat,
                            lon,
                            node_type,
                            distance_from_olt_m: dist,
                        });
                    }
                }
            }
        }

        // edges.csv
        let edges_path = dir.join("edges.csv");
        if edges_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&edges_path) {
                for line in content.lines().skip(1) {
                    let parts: Vec<&str> = line.splitn(3, ',').collect();
                    if parts.len() < 3 { continue; }
                    if let Ok(length_m) = parts[2].trim().parse::<u32>() {
                        topo.edges.push(TopologyEdge {
                            from: parts[0].trim().to_string(),
                            to: parts[1].trim().to_string(),
                            length_m,
                        });
                    }
                }
            }
        }

        // ont_map.csv (optional)
        let map_path = dir.join("ont_map.csv");
        if map_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&map_path) {
                for line in content.lines().skip(1) {
                    let parts: Vec<&str> = line.splitn(2, ',').collect();
                    if parts.len() < 2 { continue; }
                    topo.ont_to_node.insert(
                        parts[0].trim().to_string(),
                        parts[1].trim().to_string(),
                    );
                }
            }
        }

        topo
    }

    /// Infer a linear topology from ONT distance readings.
    ///
    /// Algorithm:
    ///   1. Sort ONTs by ascending distance.
    ///   2. Cluster ONTs that are within 50 m of each other into one
    ///      distribution point (DP).
    ///   3. Build a linear chain: OLT → DP1 → DP2 → …
    pub fn infer_from_distances(port: &str, ont_distances: &[(String, u32)]) -> Self {
        let mut topo = Self::empty();

        if ont_distances.is_empty() {
            return topo;
        }

        // Sort by distance ascending
        let mut sorted: Vec<(String, u32)> = ont_distances.to_vec();
        sorted.sort_by_key(|(_, d)| *d);

        // OLT root node at distance 0
        let olt_id = format!("OLT-{}", port.replace('/', "-"));
        topo.nodes.insert(olt_id.clone(), TopologyNode {
            id: olt_id.clone(),
            lat: 0.0,
            lon: 0.0,
            node_type: NodeType::Olt,
            distance_from_olt_m: 0,
        });

        // Cluster within 50 m
        const CLUSTER_RADIUS_M: u32 = 50;
        let mut dp_nodes: Vec<TopologyNode> = Vec::new();
        let mut current_cluster_start: u32 = sorted[0].1;
        let mut current_cluster_id = 1usize;
        let mut current_dp_id = format!("DP{:03}-{}", current_cluster_id, port.replace('/', "-"));

        // First DP
        dp_nodes.push(TopologyNode {
            id: current_dp_id.clone(),
            lat: 0.0,
            lon: 0.0,
            node_type: NodeType::DistributionPoint,
            distance_from_olt_m: sorted[0].1,
        });
        topo.ont_to_node.insert(sorted[0].0.clone(), current_dp_id.clone());

        for (serial, dist) in sorted.iter().skip(1) {
            if dist.saturating_sub(current_cluster_start) <= CLUSTER_RADIUS_M {
                // Same cluster
                topo.ont_to_node.insert(serial.clone(), current_dp_id.clone());
            } else {
                // New cluster
                current_cluster_id += 1;
                current_cluster_start = *dist;
                current_dp_id = format!("DP{:03}-{}", current_cluster_id, port.replace('/', "-"));
                dp_nodes.push(TopologyNode {
                    id: current_dp_id.clone(),
                    lat: 0.0,
                    lon: 0.0,
                    node_type: NodeType::DistributionPoint,
                    distance_from_olt_m: *dist,
                });
                topo.ont_to_node.insert(serial.clone(), current_dp_id.clone());
            }
        }

        // Register DP nodes and build chain edges
        let mut prev_id = olt_id.clone();
        for dp in dp_nodes {
            let length_m = dp.distance_from_olt_m
                - topo.nodes.get(&prev_id).map(|n| n.distance_from_olt_m).unwrap_or(0);
            topo.edges.push(TopologyEdge {
                from: prev_id.clone(),
                to: dp.id.clone(),
                length_m,
            });
            prev_id = dp.id.clone();
            topo.nodes.insert(dp.id.clone(), dp);
        }

        topo
    }

    /// Build a synthetic London-area topology for testing and demos.
    ///
    /// Layout (approximate distances, all fibre):
    ///   OLT  (Brixton) ──800m──> SP001 ──500m──> SP002 ──400m──> DP001
    ///                                         └──600m──> SP003 ──350m──> DP002
    ///
    /// ONT mappings:
    ///   ADTN00000000 … ADTN00000006  → DP001
    ///   ADTN00000007 … ADTN00000013  → DP002
    pub fn synthetic() -> Self {
        let mut topo = Self::empty();

        // --- Nodes ---
        let nodes = vec![
            TopologyNode {
                id: "OLT-BRIXTON".into(),
                lat: 51.4607,
                lon: -0.1163,
                node_type: NodeType::Olt,
                distance_from_olt_m: 0,
            },
            TopologyNode {
                id: "SP001".into(),
                lat: 51.4630,
                lon: -0.1140,
                node_type: NodeType::SplicePoint,
                distance_from_olt_m: 800,
            },
            TopologyNode {
                id: "SP002".into(),
                lat: 51.4650,
                lon: -0.1120,
                node_type: NodeType::SplicePoint,
                distance_from_olt_m: 1300,
            },
            TopologyNode {
                id: "SP003".into(),
                lat: 51.4620,
                lon: -0.1090,
                node_type: NodeType::SplicePoint,
                distance_from_olt_m: 1900,
            },
            TopologyNode {
                id: "DP001".into(),
                lat: 51.4670,
                lon: -0.1100,
                node_type: NodeType::DistributionPoint,
                distance_from_olt_m: 1700,
            },
            TopologyNode {
                id: "DP002".into(),
                lat: 51.4610,
                lon: -0.1065,
                node_type: NodeType::DistributionPoint,
                distance_from_olt_m: 2250,
            },
        ];
        for n in nodes {
            topo.nodes.insert(n.id.clone(), n);
        }

        // --- Edges ---
        topo.edges = vec![
            TopologyEdge { from: "OLT-BRIXTON".into(), to: "SP001".into(), length_m: 800 },
            TopologyEdge { from: "SP001".into(),       to: "SP002".into(), length_m: 500 },
            TopologyEdge { from: "SP002".into(),       to: "DP001".into(), length_m: 400 },
            TopologyEdge { from: "SP002".into(),       to: "SP003".into(), length_m: 600 },
            TopologyEdge { from: "SP003".into(),       to: "DP002".into(), length_m: 350 },
        ];

        // --- ONT mappings ---
        // ADTN00000000 … ADTN00000006 → DP001
        for i in 0u8..=6 {
            let serial = format!("ADTN{:08X}", i);
            topo.ont_to_node.insert(serial, "DP001".into());
        }
        // ADTN00000007 … ADTN00000013 → DP002
        for i in 7u8..=13 {
            let serial = format!("ADTN{:08X}", i);
            topo.ont_to_node.insert(serial, "DP002".into());
        }

        topo
    }

    /// Return the topology node that an ONT is attached to, if known.
    pub fn get_ont_node(&self, serial: &str) -> Option<&TopologyNode> {
        self.ont_to_node
            .get(serial)
            .and_then(|node_id| self.nodes.get(node_id))
    }
}

/// Calculate the great-circle distance between two WGS-84 coordinates.
/// Returns the distance in metres.
pub fn haversine_m(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    const R: f64 = 6_371_000.0; // Earth radius in metres
    let dlat = (lat2 - lat1).to_radians();
    let dlon = (lon2 - lon1).to_radians();
    let a = (dlat / 2.0).sin().powi(2)
        + lat1.to_radians().cos() * lat2.to_radians().cos() * (dlon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().asin();
    R * c
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_topology() {
        let topo = FibreTopology::empty();
        assert!(topo.nodes.is_empty());
        assert!(topo.edges.is_empty());
        assert!(topo.ont_to_node.is_empty());
        assert!(topo.get_ont_node("ANYSERIAL").is_none());
    }

    #[test]
    fn test_infer_topology_from_distances() {
        // 8 ONTs spread across three distance clusters
        let distances = vec![
            ("ONT001".to_string(), 500),
            ("ONT002".to_string(), 520),   // within 50 m of ONT001 → same DP
            ("ONT003".to_string(), 1000),  // new cluster
            ("ONT004".to_string(), 1030),  // within 50 m of ONT003 → same DP
            ("ONT005".to_string(), 1020),  // within 50 m of ONT003 → same DP
            ("ONT006".to_string(), 2000),  // new cluster
            ("ONT007".to_string(), 2010),  // within 50 m → same DP
            ("ONT008".to_string(), 2500),  // new cluster
        ];

        let topo = FibreTopology::infer_from_distances("0/1/0", &distances);

        // Should have 4 DP nodes + 1 OLT root = 5 nodes total
        assert_eq!(topo.nodes.len(), 5, "expected 5 nodes (OLT + 4 DPs)");
        // 4 edges (OLT→DP1, DP1→DP2, DP2→DP3, DP3→DP4)
        assert_eq!(topo.edges.len(), 4, "expected 4 edges");

        // Cluster check: ONT001 and ONT002 should map to the same node
        let node1 = topo.ont_to_node.get("ONT001").expect("ONT001 must be mapped");
        let node2 = topo.ont_to_node.get("ONT002").expect("ONT002 must be mapped");
        assert_eq!(node1, node2, "ONT001 and ONT002 should share a DP node");

        // ONT006 and ONT007 should share a node too
        let node6 = topo.ont_to_node.get("ONT006").expect("ONT006 must be mapped");
        let node7 = topo.ont_to_node.get("ONT007").expect("ONT007 must be mapped");
        assert_eq!(node6, node7, "ONT006 and ONT007 should share a DP node");

        // ONT008 is in its own cluster
        let node8 = topo.ont_to_node.get("ONT008").expect("ONT008 must be mapped");
        assert_ne!(node6, node8, "ONT008 should be in a separate DP from ONT006");
    }

    #[test]
    fn test_get_ont_distance() {
        let topo = FibreTopology::synthetic();

        // DP001 is at 1700 m
        let node_dp1 = topo.get_ont_node("ADTN00000000").expect("ONT must map to DP001");
        assert_eq!(node_dp1.id, "DP001");
        assert_eq!(node_dp1.distance_from_olt_m, 1700);

        // DP002 is at 2250 m
        let node_dp2 = topo.get_ont_node("ADTN0000000D").expect("ONT must map to DP002");
        assert_eq!(node_dp2.id, "DP002");
        assert_eq!(node_dp2.distance_from_olt_m, 2250);

        // Unknown serial returns None
        assert!(topo.get_ont_node("UNKNOWN999").is_none());
    }

    #[test]
    fn test_synthetic_topology() {
        let topo = FibreTopology::synthetic();

        // 6 nodes (OLT + SP001 + SP002 + SP003 + DP001 + DP002)
        assert_eq!(topo.nodes.len(), 6);
        // 5 edges as per layout
        assert_eq!(topo.edges.len(), 5);

        // OLT node exists and is at origin
        let olt = topo.nodes.get("OLT-BRIXTON").expect("OLT-BRIXTON must exist");
        assert_eq!(olt.node_type, NodeType::Olt);
        assert_eq!(olt.distance_from_olt_m, 0);
        assert!((olt.lat - 51.4607).abs() < 1e-4);

        // All 14 test ONTs are mapped
        for i in 0u8..=13 {
            let serial = format!("ADTN{:08X}", i);
            assert!(topo.ont_to_node.contains_key(&serial), "serial {} must be mapped", serial);
        }

        // DP001 onts (0–6) and DP002 onts (7–13) are distinct
        let dp1_serial = format!("ADTN{:08X}", 0u8);
        let dp2_serial = format!("ADTN{:08X}", 7u8);
        assert_ne!(
            topo.ont_to_node.get(&dp1_serial),
            topo.ont_to_node.get(&dp2_serial),
            "DP001 and DP002 ONTs must map to different nodes"
        );

        // Haversine sanity check: Brixton OLT → SP001 should be < 1 km
        let olt_node = topo.nodes.get("OLT-BRIXTON").unwrap();
        let sp1_node = topo.nodes.get("SP001").unwrap();
        let dist = haversine_m(olt_node.lat, olt_node.lon, sp1_node.lat, sp1_node.lon);
        assert!(dist < 1000.0, "OLT→SP001 haversine distance should be < 1 km, got {:.0} m", dist);
    }
}
