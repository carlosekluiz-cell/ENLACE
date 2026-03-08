//! # enlace-raster
//!
//! GeoTIFF rasterizer and coverage visualization for the ENLACE platform.
//!
//! This crate provides tools for converting RF coverage data into
//! geospatially-referenced raster images:
//!
//! - [`geotiff`]: Minimal GeoTIFF writer producing valid TIFF files with
//!   WGS84 georeferencing tags (avoids heavy GDAL dependency).
//! - [`renderer`]: Industry-standard RF signal strength to RGBA color
//!   mapping for coverage visualization.
//!
//! ## Quick Start
//!
//! ```rust,no_run
//! use enlace_raster::geotiff::{GeoTiffWriter, RasterBounds};
//! use enlace_raster::renderer::ColorMapper;
//!
//! let bounds = RasterBounds {
//!     west: -47.0, south: -24.0,
//!     east: -46.0, north: -23.0,
//!     width: 100, height: 100,
//! };
//!
//! // Signal strength data (dBm)
//! let data: Vec<f32> = (0..10_000)
//!     .map(|i| -60.0 - (i as f32) * 0.004)
//!     .collect();
//!
//! // Write GeoTIFF
//! let writer = GeoTiffWriter::new("/tmp/coverage.tif");
//! writer.write(&data, &bounds).unwrap();
//!
//! // Or render as RGBA image
//! let mapper = ColorMapper::default_rf();
//! let color = mapper.map_color(-75.0);
//! println!("Color for -75 dBm: {:?}", color);
//! ```

pub mod geotiff;
pub mod renderer;

// Re-export key types for convenience
pub use geotiff::{GeoTiffWriter, RasterBounds};
pub use renderer::ColorMapper;
