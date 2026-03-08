//! LRU cache for SRTM tiles.
//!
//! Keeps recently-used tiles in memory to avoid repeated disk I/O.
//! Default capacity is 50 tiles (~1.25 GB for SRTM1 data).

use std::num::NonZeroUsize;
use std::path::PathBuf;

use lru::LruCache;
use tracing::{debug, warn};

use crate::srtm::{self, MmapTile, SrtmReader};

/// Default number of tiles to keep in cache.
const DEFAULT_CAPACITY: usize = 50;

/// Statistics about the tile cache.
#[derive(Debug, Clone, Copy)]
pub struct CacheStats {
    /// Number of tiles currently cached.
    pub tiles_cached: usize,
    /// Maximum number of tiles the cache can hold.
    pub capacity: usize,
}

/// LRU cache for SRTM tiles, loading them on demand from disk.
pub struct TileCache {
    reader: SrtmReader,
    cache: LruCache<(i32, i32), MmapTile>,
}

impl TileCache {
    /// Create a new tile cache with the default capacity (50 tiles).
    pub fn new(tile_dir: impl Into<PathBuf>, capacity: usize) -> Self {
        let cap = if capacity == 0 {
            DEFAULT_CAPACITY
        } else {
            capacity
        };
        Self {
            reader: SrtmReader::new(tile_dir),
            cache: LruCache::new(NonZeroUsize::new(cap).unwrap()),
        }
    }

    /// Get elevation at any lat/lon, loading and caching tiles as needed.
    ///
    /// Returns `None` if the tile cannot be loaded or the point has no data.
    pub fn elevation(&mut self, lat: f64, lon: f64) -> Option<f64> {
        let (tile_lat, tile_lon) = srtm::tile_coords(lat, lon);
        self.ensure_tile(tile_lat, tile_lon);
        self.cache
            .get(&(tile_lat, tile_lon))
            .and_then(|tile| tile.elevation(lat, lon))
    }

    /// Ensure the tile for the given SW corner is loaded into the cache.
    fn ensure_tile(&mut self, lat: i32, lon: i32) {
        let key = (lat, lon);
        if self.cache.contains(&key) {
            return;
        }

        debug!("Loading tile into cache: ({}, {})", lat, lon);
        match self.reader.load_tile(lat, lon) {
            Ok(tile) => {
                self.cache.put(key, tile);
            }
            Err(e) => {
                warn!("Failed to load tile ({}, {}): {}", lat, lon, e);
            }
        }
    }

    /// Get a reference to a cached tile, loading it from disk if needed.
    pub fn get_tile(&mut self, lat: i32, lon: i32) -> Option<&MmapTile> {
        self.ensure_tile(lat, lon);
        self.cache.get(&(lat, lon))
    }

    /// Return cache statistics.
    pub fn stats(&self) -> CacheStats {
        CacheStats {
            tiles_cached: self.cache.len(),
            capacity: self.cache.cap().get(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_stats_empty() {
        let cache = TileCache::new("/nonexistent", 10);
        let stats = cache.stats();
        assert_eq!(stats.tiles_cached, 0);
        assert_eq!(stats.capacity, 10);
    }

    #[test]
    fn test_cache_elevation_missing_tile() {
        let mut cache = TileCache::new("/nonexistent", 5);
        // Should return None when tile doesn't exist
        let elev = cache.elevation(45.0, 10.0);
        assert!(elev.is_none());
    }

    #[test]
    fn test_default_capacity() {
        let cache = TileCache::new("/nonexistent", 0);
        assert_eq!(cache.stats().capacity, DEFAULT_CAPACITY);
    }
}
