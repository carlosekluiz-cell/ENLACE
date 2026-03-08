//! Simple GeoTIFF writer for coverage maps.
//!
//! Writes coverage data as a minimal valid GeoTIFF file with:
//! - Single band: signal strength in dBm (Float32)
//! - ModelTiepointTag and ModelPixelScaleTag for georeferencing
//! - GeoKeyDirectoryTag for CRS identification (WGS84)
//!
//! This is a simplified writer that avoids the heavy GDAL dependency.
//! For production use with complex projections, a GDAL-based approach
//! would be preferred.

use std::io::Write;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use byteorder::{LittleEndian, WriteBytesExt};
use serde::{Deserialize, Serialize};

/// Geographic bounds and pixel dimensions of a raster.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RasterBounds {
    /// Western (left) longitude in decimal degrees.
    pub west: f64,
    /// Southern (bottom) latitude in decimal degrees.
    pub south: f64,
    /// Eastern (right) longitude in decimal degrees.
    pub east: f64,
    /// Northern (top) latitude in decimal degrees.
    pub north: f64,
    /// Width in pixels.
    pub width: usize,
    /// Height in pixels.
    pub height: usize,
}

impl RasterBounds {
    /// Pixel size in the X (longitude) direction.
    pub fn pixel_width(&self) -> f64 {
        if self.width > 0 {
            (self.east - self.west) / self.width as f64
        } else {
            0.0
        }
    }

    /// Pixel size in the Y (latitude) direction.
    pub fn pixel_height(&self) -> f64 {
        if self.height > 0 {
            (self.north - self.south) / self.height as f64
        } else {
            0.0
        }
    }
}

/// Writer for GeoTIFF files containing coverage raster data.
pub struct GeoTiffWriter {
    /// Path to the output file.
    pub output_path: PathBuf,
}

// TIFF Tag IDs
const TAG_IMAGE_WIDTH: u16 = 256;
const TAG_IMAGE_LENGTH: u16 = 257;
const TAG_BITS_PER_SAMPLE: u16 = 258;
const TAG_COMPRESSION: u16 = 259;
const TAG_PHOTOMETRIC: u16 = 262;
const TAG_STRIP_OFFSETS: u16 = 273;
const TAG_SAMPLES_PER_PIXEL: u16 = 277;
const TAG_ROWS_PER_STRIP: u16 = 278;
const TAG_STRIP_BYTE_COUNTS: u16 = 279;
const TAG_SAMPLE_FORMAT: u16 = 339;

// GeoTIFF Tag IDs
const TAG_MODEL_PIXEL_SCALE: u16 = 33550;
const TAG_MODEL_TIEPOINT: u16 = 33922;
const TAG_GEO_KEY_DIRECTORY: u16 = 34735;

// TIFF data types
const TIFF_SHORT: u16 = 3; // uint16
const TIFF_LONG: u16 = 4; // uint32
const TIFF_DOUBLE: u16 = 12; // float64

// Compression: no compression
const COMPRESSION_NONE: u16 = 1;

// Photometric interpretation: min-is-black
const PHOTOMETRIC_MINISBLACK: u16 = 1;

// Sample format: IEEE float
const SAMPLE_FORMAT_FLOAT: u16 = 3;

impl GeoTiffWriter {
    /// Create a new GeoTIFF writer targeting the given path.
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self {
            output_path: path.into(),
        }
    }

    /// Write coverage data as a GeoTIFF file.
    ///
    /// # Parameters
    /// - `data`: Row-major Float32 values (signal strength in dBm).
    ///   Length must equal `bounds.width * bounds.height`.
    /// - `bounds`: Geographic bounds and pixel dimensions.
    ///
    /// # Returns
    /// `Ok(())` on success, or an error if writing fails.
    pub fn write(&self, data: &[f32], bounds: &RasterBounds) -> Result<()> {
        let expected_len = bounds.width * bounds.height;
        anyhow::ensure!(
            data.len() == expected_len,
            "Data length {} does not match dimensions {}x{} = {}",
            data.len(),
            bounds.width,
            bounds.height,
            expected_len
        );

        // Create parent directory if needed
        if let Some(parent) = self.output_path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)
                    .with_context(|| format!("Creating directory {}", parent.display()))?;
            }
        }

        let mut buf: Vec<u8> = Vec::new();

        // --- TIFF Header (8 bytes) ---
        // Byte order: little-endian ("II")
        buf.write_all(b"II")?;
        // Magic number: 42
        buf.write_u16::<LittleEndian>(42)?;
        // Offset to first IFD (we'll put it right after the header)
        buf.write_u32::<LittleEndian>(8)?;

        // --- IFD ---
        // We need to lay out:
        // 1. IFD at offset 8
        // 2. Extended data (doubles, geo keys) after IFD
        // 3. Pixel data after extended data

        let num_tags: u16 = 13;
        let ifd_start = 8u32;
        let ifd_size = 2 + num_tags as u32 * 12 + 4; // count + entries + next IFD offset
        let extended_data_start = ifd_start + ifd_size;

        // Pre-compute extended data offsets
        // ModelPixelScaleTag: 3 doubles = 24 bytes
        let pixel_scale_offset = extended_data_start;
        // ModelTiepointTag: 6 doubles = 48 bytes
        let tiepoint_offset = pixel_scale_offset + 24;
        // GeoKeyDirectoryTag: 4 shorts per key-entry. We have 4 entries (header + 3 keys) = 16 shorts = 32 bytes
        let geokey_offset = tiepoint_offset + 48;
        // Pixel data starts after geo keys
        let pixel_data_offset = geokey_offset + 32;
        let pixel_data_size = (bounds.width * bounds.height * 4) as u32; // Float32 = 4 bytes

        // Write IFD entry count
        buf.write_u16::<LittleEndian>(num_tags)?;

        // Helper: write an IFD entry
        // Each entry: tag(2) + type(2) + count(4) + value/offset(4) = 12 bytes

        // Tag 1: ImageWidth
        Self::write_ifd_entry(&mut buf, TAG_IMAGE_WIDTH, TIFF_LONG, 1, bounds.width as u32)?;

        // Tag 2: ImageLength
        Self::write_ifd_entry(&mut buf, TAG_IMAGE_LENGTH, TIFF_LONG, 1, bounds.height as u32)?;

        // Tag 3: BitsPerSample = 32 (Float32)
        Self::write_ifd_entry(&mut buf, TAG_BITS_PER_SAMPLE, TIFF_SHORT, 1, 32)?;

        // Tag 4: Compression = None
        Self::write_ifd_entry(&mut buf, TAG_COMPRESSION, TIFF_SHORT, 1, COMPRESSION_NONE as u32)?;

        // Tag 5: PhotometricInterpretation = MinIsBlack
        Self::write_ifd_entry(
            &mut buf,
            TAG_PHOTOMETRIC,
            TIFF_SHORT,
            1,
            PHOTOMETRIC_MINISBLACK as u32,
        )?;

        // Tag 6: StripOffsets (offset to pixel data)
        Self::write_ifd_entry(&mut buf, TAG_STRIP_OFFSETS, TIFF_LONG, 1, pixel_data_offset)?;

        // Tag 7: SamplesPerPixel = 1
        Self::write_ifd_entry(&mut buf, TAG_SAMPLES_PER_PIXEL, TIFF_SHORT, 1, 1)?;

        // Tag 8: RowsPerStrip = ImageLength (single strip)
        Self::write_ifd_entry(
            &mut buf,
            TAG_ROWS_PER_STRIP,
            TIFF_LONG,
            1,
            bounds.height as u32,
        )?;

        // Tag 9: StripByteCounts
        Self::write_ifd_entry(&mut buf, TAG_STRIP_BYTE_COUNTS, TIFF_LONG, 1, pixel_data_size)?;

        // Tag 10: SampleFormat = IEEE float
        Self::write_ifd_entry(
            &mut buf,
            TAG_SAMPLE_FORMAT,
            TIFF_SHORT,
            1,
            SAMPLE_FORMAT_FLOAT as u32,
        )?;

        // Tag 11: ModelPixelScaleTag (3 doubles, offset to extended data)
        Self::write_ifd_entry(&mut buf, TAG_MODEL_PIXEL_SCALE, TIFF_DOUBLE, 3, pixel_scale_offset)?;

        // Tag 12: ModelTiepointTag (6 doubles, offset to extended data)
        Self::write_ifd_entry(&mut buf, TAG_MODEL_TIEPOINT, TIFF_DOUBLE, 6, tiepoint_offset)?;

        // Tag 13: GeoKeyDirectoryTag (16 shorts, offset to extended data)
        Self::write_ifd_entry(&mut buf, TAG_GEO_KEY_DIRECTORY, TIFF_SHORT, 16, geokey_offset)?;

        // Next IFD offset = 0 (no more IFDs)
        buf.write_u32::<LittleEndian>(0)?;

        // --- Extended data ---

        // ModelPixelScaleTag: [ScaleX, ScaleY, ScaleZ]
        let scale_x = bounds.pixel_width();
        let scale_y = bounds.pixel_height();
        buf.write_f64::<LittleEndian>(scale_x)?;
        buf.write_f64::<LittleEndian>(scale_y)?;
        buf.write_f64::<LittleEndian>(0.0)?; // ScaleZ

        // ModelTiepointTag: [I, J, K, X, Y, Z]
        // Ties pixel (0, 0) to the top-left corner (west, north)
        buf.write_f64::<LittleEndian>(0.0)?; // I (column)
        buf.write_f64::<LittleEndian>(0.0)?; // J (row)
        buf.write_f64::<LittleEndian>(0.0)?; // K
        buf.write_f64::<LittleEndian>(bounds.west)?; // X (longitude)
        buf.write_f64::<LittleEndian>(bounds.north)?; // Y (latitude)
        buf.write_f64::<LittleEndian>(0.0)?; // Z

        // GeoKeyDirectoryTag
        // Header: KeyDirectoryVersion=1, KeyRevision=1, MinorRevision=0, NumberOfKeys=3
        buf.write_u16::<LittleEndian>(1)?; // KeyDirectoryVersion
        buf.write_u16::<LittleEndian>(1)?; // KeyRevision
        buf.write_u16::<LittleEndian>(0)?; // MinorRevision
        buf.write_u16::<LittleEndian>(3)?; // NumberOfKeys

        // Key 1: GTModelTypeGeoKey (1024) = ModelTypeGeographic (2)
        buf.write_u16::<LittleEndian>(1024)?; // KeyID
        buf.write_u16::<LittleEndian>(0)?; // TIFFTagLocation (0 = value in ValueOffset)
        buf.write_u16::<LittleEndian>(1)?; // Count
        buf.write_u16::<LittleEndian>(2)?; // Value: ModelTypeGeographic

        // Key 2: GTRasterTypeGeoKey (1025) = RasterPixelIsArea (1)
        buf.write_u16::<LittleEndian>(1025)?;
        buf.write_u16::<LittleEndian>(0)?;
        buf.write_u16::<LittleEndian>(1)?;
        buf.write_u16::<LittleEndian>(1)?;

        // Key 3: GeographicTypeGeoKey (2048) = GCS_WGS_84 (4326)
        buf.write_u16::<LittleEndian>(2048)?;
        buf.write_u16::<LittleEndian>(0)?;
        buf.write_u16::<LittleEndian>(1)?;
        buf.write_u16::<LittleEndian>(4326)?;

        // --- Pixel data (Float32, row-major, north-to-south) ---
        for &val in data {
            buf.write_f32::<LittleEndian>(val)?;
        }

        // Write to file
        std::fs::write(&self.output_path, &buf)
            .with_context(|| format!("Writing GeoTIFF to {}", self.output_path.display()))?;

        Ok(())
    }

    /// Write a single IFD entry (12 bytes).
    fn write_ifd_entry(
        buf: &mut Vec<u8>,
        tag: u16,
        data_type: u16,
        count: u32,
        value_or_offset: u32,
    ) -> Result<()> {
        buf.write_u16::<LittleEndian>(tag)?;
        buf.write_u16::<LittleEndian>(data_type)?;
        buf.write_u32::<LittleEndian>(count)?;
        buf.write_u32::<LittleEndian>(value_or_offset)?;
        Ok(())
    }
}

/// Validate a file has a valid TIFF header.
pub fn validate_tiff_header(path: &Path) -> Result<bool> {
    let data = std::fs::read(path).with_context(|| format!("Reading {}", path.display()))?;

    if data.len() < 8 {
        return Ok(false);
    }

    // Check byte order mark
    let byte_order_ok = (data[0] == b'I' && data[1] == b'I') // Little-endian
        || (data[0] == b'M' && data[1] == b'M'); // Big-endian

    if !byte_order_ok {
        return Ok(false);
    }

    // Check magic number (42)
    let magic = if data[0] == b'I' {
        u16::from_le_bytes([data[2], data[3]])
    } else {
        u16::from_be_bytes([data[2], data[3]])
    };

    Ok(magic == 42)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_raster_bounds_pixel_size() {
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 100,
            height: 100,
        };

        let pw = bounds.pixel_width();
        let ph = bounds.pixel_height();

        assert!(
            (pw - 0.01).abs() < 1e-10,
            "Pixel width should be 0.01 deg: {}",
            pw
        );
        assert!(
            (ph - 0.01).abs() < 1e-10,
            "Pixel height should be 0.01 deg: {}",
            ph
        );
    }

    #[test]
    fn test_geotiff_write_and_validate() {
        let dir = std::env::temp_dir().join("enlace_test_geotiff");
        let _ = fs::create_dir_all(&dir);
        let path = dir.join("test_coverage.tif");

        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 10,
            height: 10,
        };

        // Generate test data: gradient from -60 to -100 dBm
        let data: Vec<f32> = (0..100)
            .map(|i| -60.0 - (i as f32) * 0.4)
            .collect();

        let writer = GeoTiffWriter::new(&path);
        writer.write(&data, &bounds).expect("Should write GeoTIFF");

        // Validate the file exists and has a valid TIFF header
        assert!(path.exists(), "GeoTIFF file should exist");

        let valid = validate_tiff_header(&path).expect("Should read header");
        assert!(valid, "Should have valid TIFF header");

        // Check file size: header(8) + IFD(2+13*12+4) + extended(24+48+32) + pixels(100*4) = 8+162+104+400 = 674
        let metadata = fs::metadata(&path).expect("File metadata");
        assert!(
            metadata.len() > 100,
            "File should be larger than 100 bytes: {} bytes",
            metadata.len()
        );

        // Read back and check TIFF magic bytes
        let file_data = fs::read(&path).expect("Read file");
        assert_eq!(file_data[0], b'I'); // Little-endian
        assert_eq!(file_data[1], b'I');
        // Magic number 42 at bytes 2-3
        let magic = u16::from_le_bytes([file_data[2], file_data[3]]);
        assert_eq!(magic, 42, "TIFF magic should be 42");

        // Cleanup
        let _ = fs::remove_file(&path);
        let _ = fs::remove_dir(&dir);
    }

    #[test]
    fn test_geotiff_data_length_mismatch() {
        let path = std::env::temp_dir().join("enlace_test_bad.tif");
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 10,
            height: 10,
        };

        let data: Vec<f32> = vec![-80.0; 50]; // Wrong length: should be 100

        let writer = GeoTiffWriter::new(&path);
        let result = writer.write(&data, &bounds);
        assert!(result.is_err(), "Should fail with mismatched data length");
    }

    #[test]
    fn test_raster_bounds_zero_dimensions() {
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 0,
            height: 0,
        };

        assert_eq!(bounds.pixel_width(), 0.0);
        assert_eq!(bounds.pixel_height(), 0.0);
    }
}
