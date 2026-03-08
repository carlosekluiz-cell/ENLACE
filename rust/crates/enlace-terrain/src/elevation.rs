//! High-level elevation query interface.
//!
//! Provides a convenient API for querying elevation data, wrapping
//! the tile cache and SRTM reader layers.

use std::path::PathBuf;

use crate::cache::TileCache;

/// Default cache size (number of tiles).
const DEFAULT_CACHE_SIZE: usize = 50;

/// High-level elevation query interface.
///
/// Wraps a [`TileCache`] and provides single-point and batch query methods.
pub struct ElevationQuery {
    cache: TileCache,
}

impl ElevationQuery {
    /// Create an elevation query with the default cache size (50 tiles).
    pub fn new(tile_dir: impl Into<PathBuf>) -> Self {
        Self::with_cache_size(tile_dir, DEFAULT_CACHE_SIZE)
    }

    /// Create an elevation query with a custom cache size.
    pub fn with_cache_size(tile_dir: impl Into<PathBuf>, cache_size: usize) -> Self {
        Self {
            cache: TileCache::new(tile_dir, cache_size),
        }
    }

    /// Get elevation at a single point.
    ///
    /// Returns `None` if no elevation data is available for the point
    /// (tile missing, ocean, or void cell).
    pub fn get(&mut self, lat: f64, lon: f64) -> Option<f64> {
        self.cache.elevation(lat, lon)
    }

    /// Get elevations for multiple points (batch query).
    ///
    /// Returns a vector of `Option<f64>` in the same order as the input points.
    /// Each element is `None` if no elevation data is available for that point.
    pub fn get_batch(&mut self, points: &[(f64, f64)]) -> Vec<Option<f64>> {
        points
            .iter()
            .map(|&(lat, lon)| self.cache.elevation(lat, lon))
            .collect()
    }

    /// Access the underlying tile cache (e.g., for statistics).
    pub fn cache(&self) -> &TileCache {
        &self.cache
    }

    /// Access the underlying tile cache mutably.
    pub fn cache_mut(&mut self) -> &mut TileCache {
        &mut self.cache
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_elevation_query_creation() {
        let eq = ElevationQuery::new("/nonexistent");
        assert_eq!(eq.cache().stats().capacity, DEFAULT_CACHE_SIZE);
    }

    #[test]
    fn test_elevation_query_custom_cache() {
        let eq = ElevationQuery::with_cache_size("/nonexistent", 10);
        assert_eq!(eq.cache().stats().capacity, 10);
    }

    #[test]
    fn test_batch_query_missing_tiles() {
        let mut eq = ElevationQuery::new("/nonexistent");
        let points = vec![(45.0, 10.0), (-23.5, -46.6), (0.0, 0.0)];
        let results = eq.get_batch(&points);
        assert_eq!(results.len(), 3);
        assert!(results.iter().all(|r| r.is_none()));
    }
}
