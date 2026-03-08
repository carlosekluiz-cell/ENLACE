//! SRTM HGT tile reader with memory-mapped I/O.
//!
//! Supports both SRTM1 (3601x3601, 1 arc-second) and SRTM3 (1201x1201, 3 arc-second)
//! resolution tiles. Tile format is big-endian i16 values encoding elevation in meters.
//! Void/ocean cells are marked with -32768.

use std::fs::File;
use std::path::PathBuf;

use anyhow::{Context, Result};
use byteorder::{BigEndian, ByteOrder};
use memmap2::Mmap;
use tracing::{debug, warn};

/// Void value in SRTM data indicating no elevation data (ocean or missing).
pub const SRTM_VOID: i16 = -32768;

/// Number of samples per row/column in SRTM1 (1 arc-second) tiles.
pub const SRTM1_SAMPLES: usize = 3601;

/// Number of samples per row/column in SRTM3 (3 arc-second) tiles.
pub const SRTM3_SAMPLES: usize = 1201;

/// Expected file size for SRTM1 tiles in bytes: 3601 * 3601 * 2.
const SRTM1_FILE_SIZE: usize = SRTM1_SAMPLES * SRTM1_SAMPLES * 2;

/// Expected file size for SRTM3 tiles in bytes: 1201 * 1201 * 2.
const SRTM3_FILE_SIZE: usize = SRTM3_SAMPLES * SRTM3_SAMPLES * 2;

/// Reader that loads SRTM HGT tiles from a directory.
pub struct SrtmReader {
    tile_dir: PathBuf,
}

/// A memory-mapped SRTM HGT tile.
pub struct MmapTile {
    mmap: Mmap,
    /// Latitude of the south-west corner (integer degrees).
    pub sw_lat: i32,
    /// Longitude of the south-west corner (integer degrees).
    pub sw_lon: i32,
    /// Number of samples per row/column (3601 for SRTM1, 1201 for SRTM3).
    pub samples: usize,
}

impl SrtmReader {
    /// Create a new SRTM reader that loads tiles from the given directory.
    pub fn new(tile_dir: impl Into<PathBuf>) -> Self {
        Self {
            tile_dir: tile_dir.into(),
        }
    }

    /// Load a tile by its south-west corner coordinates.
    ///
    /// The `lat` and `lon` parameters specify the integer-degree SW corner.
    /// For example, a point at -23.55, -46.63 would need tile S24W047.
    pub fn load_tile(&self, lat: i32, lon: i32) -> Result<MmapTile> {
        let filename = Self::tile_filename(lat, lon);
        let path = self.tile_dir.join(&filename);

        debug!("Loading SRTM tile: {}", path.display());

        let file = File::open(&path)
            .with_context(|| format!("Failed to open SRTM tile: {}", path.display()))?;

        let metadata = file
            .metadata()
            .with_context(|| format!("Failed to read metadata for: {}", path.display()))?;

        let file_size = metadata.len() as usize;
        let samples = match file_size {
            SRTM1_FILE_SIZE => {
                debug!("Detected SRTM1 tile (3601x3601)");
                SRTM1_SAMPLES
            }
            SRTM3_FILE_SIZE => {
                debug!("Detected SRTM3 tile (1201x1201)");
                SRTM3_SAMPLES
            }
            _ => {
                anyhow::bail!(
                    "Unexpected SRTM tile size: {} bytes (expected {} for SRTM1 or {} for SRTM3)",
                    file_size,
                    SRTM1_FILE_SIZE,
                    SRTM3_FILE_SIZE
                );
            }
        };

        // SAFETY: We only read from the memory-mapped region, and the file is opened read-only.
        let mmap = unsafe {
            Mmap::map(&file)
                .with_context(|| format!("Failed to memory-map tile: {}", path.display()))?
        };

        Ok(MmapTile {
            mmap,
            sw_lat: lat,
            sw_lon: lon,
            samples,
        })
    }

    /// Generate the HGT filename for a given SW corner lat/lon.
    ///
    /// Format: `{N|S}{lat:02}{E|W}{lon:03}.hgt`
    /// Examples: N01E010.hgt, S23W044.hgt
    pub fn tile_filename(lat: i32, lon: i32) -> String {
        let lat_prefix = if lat >= 0 { 'N' } else { 'S' };
        let lon_prefix = if lon >= 0 { 'E' } else { 'W' };
        format!(
            "{}{:02}{}{:03}.hgt",
            lat_prefix,
            lat.unsigned_abs(),
            lon_prefix,
            lon.unsigned_abs()
        )
    }
}

impl MmapTile {
    /// Get elevation at a specific lat/lon within this tile.
    ///
    /// Uses bilinear interpolation between the 4 nearest grid points for
    /// sub-pixel accuracy. Returns `None` if any of the surrounding grid
    /// points contain void values.
    pub fn elevation(&self, lat: f64, lon: f64) -> Option<f64> {
        // Convert lat/lon to fractional row/col within the tile.
        // Row 0 is the NORTH edge (sw_lat + 1), row (samples-1) is the SOUTH edge (sw_lat).
        // Col 0 is the WEST edge (sw_lon), col (samples-1) is the EAST edge (sw_lon + 1).
        let row_f = (self.sw_lat as f64 + 1.0 - lat) * (self.samples - 1) as f64;
        let col_f = (lon - self.sw_lon as f64) * (self.samples - 1) as f64;

        // Check bounds
        if row_f < 0.0 || row_f > (self.samples - 1) as f64 {
            warn!(
                "Latitude {} out of tile bounds (sw_lat={})",
                lat, self.sw_lat
            );
            return None;
        }
        if col_f < 0.0 || col_f > (self.samples - 1) as f64 {
            warn!(
                "Longitude {} out of tile bounds (sw_lon={})",
                lon, self.sw_lon
            );
            return None;
        }

        // Compute base index and fractional part for bilinear interpolation.
        // Base index is clamped to [0, samples-2] so that base+1 stays in bounds.
        // The fractional part is computed from the original float position.
        let max_base = self.samples - 2;

        let row1 = (row_f.floor() as usize).min(max_base);
        let col1 = (col_f.floor() as usize).min(max_base);
        let row2 = row1 + 1;
        let col2 = col1 + 1;

        // Fractional parts for interpolation
        let row_frac = (row_f - row1 as f64).clamp(0.0, 1.0);
        let col_frac = (col_f - col1 as f64).clamp(0.0, 1.0);

        // Read the 4 surrounding grid values
        let v00 = self.raw_value(row1, col1);
        let v01 = self.raw_value(row1, col2);
        let v10 = self.raw_value(row2, col1);
        let v11 = self.raw_value(row2, col2);

        // Check for void values
        if v00 == SRTM_VOID || v01 == SRTM_VOID || v10 == SRTM_VOID || v11 == SRTM_VOID {
            return None;
        }

        // Bilinear interpolation
        let v00 = v00 as f64;
        let v01 = v01 as f64;
        let v10 = v10 as f64;
        let v11 = v11 as f64;

        let value = v00 * (1.0 - row_frac) * (1.0 - col_frac)
            + v01 * (1.0 - row_frac) * col_frac
            + v10 * row_frac * (1.0 - col_frac)
            + v11 * row_frac * col_frac;

        Some(value)
    }

    /// Read the raw i16 elevation value at a grid position.
    ///
    /// Row 0 is the northern edge of the tile, col 0 is the western edge.
    /// Values are stored as big-endian i16.
    fn raw_value(&self, row: usize, col: usize) -> i16 {
        let offset = (row * self.samples + col) * 2;
        if offset + 1 >= self.mmap.len() {
            return SRTM_VOID;
        }
        BigEndian::read_i16(&self.mmap[offset..offset + 2])
    }

}

/// Compute the tile SW corner coordinates for a given lat/lon.
///
/// For positive latitudes, the SW corner is `floor(lat)`.
/// For negative latitudes, the SW corner is `floor(lat)` (e.g., -23.5 -> -24).
pub fn tile_coords(lat: f64, lon: f64) -> (i32, i32) {
    (lat.floor() as i32, lon.floor() as i32)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tile_filename_positive() {
        assert_eq!(SrtmReader::tile_filename(1, 10), "N01E010.hgt");
        assert_eq!(SrtmReader::tile_filename(0, 0), "N00E000.hgt");
        assert_eq!(SrtmReader::tile_filename(45, 90), "N45E090.hgt");
    }

    #[test]
    fn test_tile_filename_negative() {
        assert_eq!(SrtmReader::tile_filename(-23, -44), "S23W044.hgt");
        assert_eq!(SrtmReader::tile_filename(-1, -179), "S01W179.hgt");
    }

    #[test]
    fn test_tile_filename_mixed() {
        assert_eq!(SrtmReader::tile_filename(10, -20), "N10W020.hgt");
        assert_eq!(SrtmReader::tile_filename(-5, 30), "S05E030.hgt");
    }

    #[test]
    fn test_tile_coords() {
        assert_eq!(tile_coords(45.5, 10.3), (45, 10));
        assert_eq!(tile_coords(-23.55, -46.63), (-24, -47));
        assert_eq!(tile_coords(0.5, -0.5), (0, -1));
        assert_eq!(tile_coords(-0.5, 0.5), (-1, 0));
    }

    #[test]
    fn test_raw_value_and_bilinear() {
        // Create a small synthetic 3x3 tile for testing
        let samples = 3;
        let mut data = vec![0u8; samples * samples * 2];

        // Fill with known elevation values:
        //   row 0 (north): 100, 200, 300
        //   row 1 (mid):   400, 500, 600
        //   row 2 (south): 700, 800, 900
        let values: Vec<i16> = vec![100, 200, 300, 400, 500, 600, 700, 800, 900];
        for (i, &v) in values.iter().enumerate() {
            let offset = i * 2;
            BigEndian::write_i16(&mut data[offset..offset + 2], v);
        }

        // Write to a temp file for mmap
        let dir = std::env::temp_dir();
        let path = dir.join(format!("srtm_bilinear_test_{}.tmp", std::process::id()));
        {
            use std::io::Write;
            let mut f = File::create(&path).unwrap();
            f.write_all(&data).unwrap();
        }

        let file = File::open(&path).unwrap();
        let mmap = unsafe { Mmap::map(&file).unwrap() };
        let _ = std::fs::remove_file(&path);

        let tile = MmapTile {
            mmap,
            sw_lat: 0,
            sw_lon: 0,
            samples,
        };

        // Test raw values
        assert_eq!(tile.raw_value(0, 0), 100);
        assert_eq!(tile.raw_value(1, 1), 500);
        assert_eq!(tile.raw_value(2, 2), 900);

        // Test elevation at grid corners
        // North-west corner: lat=1.0, lon=0.0 -> row=0, col=0 -> 100
        let elev = tile.elevation(1.0, 0.0).unwrap();
        assert!((elev - 100.0).abs() < 0.01, "NW corner: {}", elev);

        // South-east corner: lat=0.0, lon=1.0 -> row=2, col=2 -> 900
        let elev = tile.elevation(0.0, 1.0).unwrap();
        assert!((elev - 900.0).abs() < 0.01, "SE corner: {}", elev);

        // Center: lat=0.5, lon=0.5 -> should interpolate to 500
        let elev = tile.elevation(0.5, 0.5).unwrap();
        assert!((elev - 500.0).abs() < 0.01, "Center: {}", elev);
    }

    #[test]
    fn test_void_handling() {
        let samples = 2;
        let mut data = vec![0u8; samples * samples * 2];

        // Set one cell to void
        BigEndian::write_i16(&mut data[0..2], 100);
        BigEndian::write_i16(&mut data[2..4], SRTM_VOID);
        BigEndian::write_i16(&mut data[4..6], 300);
        BigEndian::write_i16(&mut data[6..8], 400);

        let dir = std::env::temp_dir();
        let path = dir.join(format!("srtm_void_test_{}.tmp", std::process::id()));
        {
            use std::io::Write;
            let mut f = File::create(&path).unwrap();
            f.write_all(&data).unwrap();
        }

        let file = File::open(&path).unwrap();
        let mmap = unsafe { Mmap::map(&file).unwrap() };
        let _ = std::fs::remove_file(&path);

        let tile = MmapTile {
            mmap,
            sw_lat: 0,
            sw_lon: 0,
            samples,
        };

        // Any interpolation touching the void cell should return None
        let elev = tile.elevation(0.5, 0.5);
        assert!(elev.is_none(), "Should be None when void is present");
    }
}
