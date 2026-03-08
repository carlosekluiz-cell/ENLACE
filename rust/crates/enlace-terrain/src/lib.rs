//! # enlace-terrain
//!
//! Terrain elevation data access for the ENLACE RF propagation platform.
//!
//! This crate provides:
//! - **SRTM HGT tile reader** with memory-mapped I/O ([`srtm`])
//! - **LRU tile cache** for efficient repeated queries ([`cache`])
//! - **High-level elevation queries** for single and batch lookups ([`elevation`])
//! - **Terrain profile extraction** along great-circle paths ([`profile`])
//!
//! ## Quick Start
//!
//! ```rust,no_run
//! use enlace_terrain::{ElevationQuery, extract_profile, GeoPoint};
//! use enlace_terrain::profile::DEFAULT_K_FACTOR;
//!
//! // Query a single elevation
//! let mut eq = ElevationQuery::new("/path/to/srtm/tiles");
//! if let Some(elev) = eq.get(-23.55, -46.63) {
//!     println!("Elevation: {} m", elev);
//! }
//!
//! // Extract a terrain profile
//! let start = GeoPoint::new(-23.55, -46.63);
//! let end = GeoPoint::new(-22.90, -43.17);
//! let profile = extract_profile(eq.cache_mut(), start, end, 100.0, DEFAULT_K_FACTOR);
//! println!("Profile has {} points over {} m", profile.points.len(), profile.distance_m);
//! ```

pub mod cache;
pub mod elevation;
pub mod profile;
pub mod srtm;

pub use cache::TileCache;
pub use elevation::ElevationQuery;
pub use profile::{extract_profile, GeoPoint, ProfilePoint, TerrainProfile};
pub use srtm::{MmapTile, SrtmReader};
