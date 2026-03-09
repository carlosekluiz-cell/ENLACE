//! enlace-tiles — XYZ tile generator for Sentinel-2 COG composites
//!
//! Reads a Cloud-Optimized GeoTIFF and produces XYZ map tiles (PNG) that can
//! be served by the FastAPI satellite router.  Designed to be invoked from the
//! Python `SentinelGrowthPipeline.post_load()` step.

use std::fs;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;
use gdal::raster::ResampleAlg;
use gdal::Dataset;
use image::RgbImage;
use tracing::{debug, info};

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

/// XYZ tile generator for Sentinel-2 COG composites.
#[derive(Parser, Debug)]
#[command(name = "enlace-tiles", version, about)]
struct Cli {
    /// Path to input GeoTIFF file.
    #[arg(short = 'i', long)]
    input: PathBuf,

    /// Output directory for tiles.
    #[arg(short = 'o', long)]
    output: PathBuf,

    /// Minimum zoom level.
    #[arg(long, default_value_t = 10)]
    zoom_min: u32,

    /// Maximum zoom level.
    #[arg(long, default_value_t = 16)]
    zoom_max: u32,

    /// Tile size in pixels.
    #[arg(long, default_value_t = 256)]
    tile_size: u32,
}

// ---------------------------------------------------------------------------
// Web-Mercator helpers
// ---------------------------------------------------------------------------

/// Convert geographic coordinates (WGS-84) to tile coordinates at a given
/// zoom level.
///
/// Formula:
///   n = 2^zoom
///   x = floor((lon + 180) / 360 * n)
///   y = floor((1 - asinh(tan(lat_rad)) / PI) / 2 * n)
fn lat_lon_to_tile(lat: f64, lon: f64, zoom: u32) -> (u32, u32) {
    let n = f64::from(1u32 << zoom);
    let lat_rad = lat.to_radians();

    let x = ((lon + 180.0) / 360.0 * n).floor() as u32;
    let y = ((1.0 - lat_rad.tan().asinh() / std::f64::consts::PI) / 2.0 * n).floor() as u32;

    // Clamp to valid tile range [0, 2^zoom - 1]
    let max_tile = (1u32 << zoom).saturating_sub(1);
    (x.min(max_tile), y.min(max_tile))
}

/// Convert tile coordinates to geographic coordinates (northwest corner of the
/// tile).
fn tile_to_lat_lon(x: u32, y: u32, zoom: u32) -> (f64, f64) {
    let n = f64::from(1u32 << zoom);

    let lon = f64::from(x) / n * 360.0 - 180.0;
    let lat_rad = (std::f64::consts::PI * (1.0 - 2.0 * f64::from(y) / n)).sinh().atan();
    let lat = lat_rad.to_degrees();

    (lat, lon)
}

// ---------------------------------------------------------------------------
// Tile rendering
// ---------------------------------------------------------------------------

/// Render a single XYZ tile from the GeoTIFF dataset.
///
/// Returns `None` when the tile falls entirely outside the raster extent.
fn render_tile(
    dataset: &Dataset,
    tile_x: u32,
    tile_y: u32,
    zoom: u32,
    tile_size: u32,
) -> Result<Option<RgbImage>> {
    let size = dataset.raster_size();
    let raster_w = size.0 as f64;
    let raster_h = size.1 as f64;

    // Geo-transform: [origin_x, pixel_width, 0, origin_y, 0, pixel_height]
    // pixel_height is typically negative (north-up).
    let gt = dataset
        .geo_transform()
        .context("Failed to read geotransform")?;

    let origin_x = gt[0];
    let pixel_w = gt[1];
    let origin_y = gt[3];
    let pixel_h = gt[5]; // negative for north-up

    // Geographic bounds of the tile (NW and SE corners).
    let (nw_lat, nw_lon) = tile_to_lat_lon(tile_x, tile_y, zoom);
    let (se_lat, se_lon) = tile_to_lat_lon(tile_x + 1, tile_y + 1, zoom);

    // Convert geographic bounds to pixel coordinates in the raster.
    // pixel_x = (lon - origin_x) / pixel_w
    // pixel_y = (lat - origin_y) / pixel_h
    let px_left = ((nw_lon - origin_x) / pixel_w).floor();
    let px_right = ((se_lon - origin_x) / pixel_w).ceil();
    let px_top = ((nw_lat - origin_y) / pixel_h).floor();
    let px_bottom = ((se_lat - origin_y) / pixel_h).ceil();

    // Clamp to raster extent.
    let src_x = px_left.max(0.0) as isize;
    let src_y = px_top.max(0.0) as isize;
    let src_right = px_right.min(raster_w) as isize;
    let src_bottom = px_bottom.min(raster_h) as isize;

    let src_w = src_right - src_x;
    let src_h = src_bottom - src_y;

    // If the tile has no overlap with the raster, skip it.
    if src_w <= 0 || src_h <= 0 {
        return Ok(None);
    }

    let src_w = src_w as usize;
    let src_h = src_h as usize;
    let ts = tile_size as usize;

    // Determine the destination region within the tile when the source window
    // is smaller than the full tile (i.e. partial overlap at raster edges).
    let full_px_w = (px_right - px_left).max(1.0);
    let full_px_h = (px_bottom - px_top).max(1.0);

    let dst_x_off = (((src_x as f64 - px_left) / full_px_w) * ts as f64).round() as u32;
    let dst_y_off = (((src_y as f64 - px_top) / full_px_h) * ts as f64).round() as u32;
    let dst_w = (((src_w as f64) / full_px_w) * ts as f64).round().max(1.0) as usize;
    let dst_h = (((src_h as f64) / full_px_h) * ts as f64).round().max(1.0) as usize;

    // Read RGB bands (1, 2, 3) with GDAL's windowed read, resampled to the
    // destination size.
    let mut band_data: [Vec<u8>; 3] = [Vec::new(), Vec::new(), Vec::new()];

    for (i, band_buf) in band_data.iter_mut().enumerate() {
        let band_idx = (i + 1) as isize; // GDAL bands are 1-indexed
        let band = dataset.rasterband(band_idx)?;

        let buf = band.read_as::<u8>(
            (src_x, src_y),
            (src_w, src_h),
            (dst_w, dst_h),
            Some(ResampleAlg::Bilinear),
        )?;
        *band_buf = buf.data().to_vec();
    }

    // Build an RgbImage.  Pixels outside the source window remain black (0).
    let mut img = RgbImage::new(tile_size, tile_size);

    for row in 0..dst_h {
        for col in 0..dst_w {
            let idx = row * dst_w + col;
            let px_x = dst_x_off + col as u32;
            let px_y = dst_y_off + row as u32;
            if px_x < tile_size && px_y < tile_size {
                let r = band_data[0][idx];
                let g = band_data[1][idx];
                let b = band_data[2][idx];
                img.put_pixel(px_x, px_y, image::Rgb([r, g, b]));
            }
        }
    }

    Ok(Some(img))
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() -> Result<()> {
    // Initialise structured logging.
    tracing_subscriber::fmt::init();

    let cli = Cli::parse();

    info!(
        input = %cli.input.display(),
        output = %cli.output.display(),
        zoom_min = cli.zoom_min,
        zoom_max = cli.zoom_max,
        tile_size = cli.tile_size,
        "Starting tile generation"
    );

    // Open the GeoTIFF with GDAL.
    let dataset = Dataset::open(&cli.input)
        .with_context(|| format!("Failed to open GeoTIFF: {}", cli.input.display()))?;

    let size = dataset.raster_size();
    let raster_w = size.0 as f64;
    let raster_h = size.1 as f64;

    info!(width = size.0, height = size.1, "Raster opened");

    // Compute geographic bounds from geotransform.
    let gt = dataset
        .geo_transform()
        .context("Failed to read geotransform")?;

    let min_lon = gt[0];
    let max_lat = gt[3];
    let max_lon = gt[0] + gt[1] * raster_w;
    let min_lat = gt[3] + gt[5] * raster_h; // gt[5] is negative

    info!(
        min_lat = min_lat,
        max_lat = max_lat,
        min_lon = min_lon,
        max_lon = max_lon,
        "Raster geographic bounds"
    );

    let mut total_tiles: u64 = 0;

    // Iterate over each zoom level.
    for zoom in cli.zoom_min..=cli.zoom_max {
        // Tile range covering the raster bounds.
        // NW corner uses max_lat / min_lon; SE corner uses min_lat / max_lon.
        let (tile_min_x, tile_min_y) = lat_lon_to_tile(max_lat, min_lon, zoom);
        let (tile_max_x, tile_max_y) = lat_lon_to_tile(min_lat, max_lon, zoom);

        let zoom_total =
            (tile_max_x - tile_min_x + 1) as u64 * (tile_max_y - tile_min_y + 1) as u64;

        info!(
            zoom = zoom,
            tile_x_range = format!("{}..{}", tile_min_x, tile_max_x),
            tile_y_range = format!("{}..{}", tile_min_y, tile_max_y),
            tiles = zoom_total,
            "Processing zoom level"
        );

        let mut zoom_rendered: u64 = 0;

        for tx in tile_min_x..=tile_max_x {
            // Create the column directory: {output}/{z}/{x}/
            let col_dir = cli.output.join(format!("{zoom}/{tx}"));
            fs::create_dir_all(&col_dir).with_context(|| {
                format!("Failed to create directory: {}", col_dir.display())
            })?;

            for ty in tile_min_y..=tile_max_y {
                match render_tile(&dataset, tx, ty, zoom, cli.tile_size)? {
                    Some(img) => {
                        let tile_path = col_dir.join(format!("{ty}.png"));
                        img.save(&tile_path).with_context(|| {
                            format!("Failed to save tile: {}", tile_path.display())
                        })?;
                        zoom_rendered += 1;
                        debug!(z = zoom, x = tx, y = ty, "Tile rendered");
                    }
                    None => {
                        debug!(z = zoom, x = tx, y = ty, "Tile outside raster bounds, skipped");
                    }
                }
            }
        }

        info!(
            zoom = zoom,
            rendered = zoom_rendered,
            skipped = zoom_total - zoom_rendered,
            "Zoom level complete"
        );

        total_tiles += zoom_rendered;
    }

    info!(total_tiles = total_tiles, "Tile generation complete");

    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lat_lon_to_tile_zoom_0() {
        // At zoom 0 there is exactly one tile (0, 0).
        let (x, y) = lat_lon_to_tile(0.0, 0.0, 0);
        assert_eq!(x, 0);
        assert_eq!(y, 0);
    }

    #[test]
    fn test_lat_lon_to_tile_known_values() {
        // Sao Paulo approx -23.55, -46.63
        // At zoom 10 the expected tile is roughly (348, 603).
        let (x, y) = lat_lon_to_tile(-23.55, -46.63, 10);
        assert_eq!(x, 348);
        assert_eq!(y, 603);
    }

    #[test]
    fn test_tile_to_lat_lon_roundtrip() {
        // For a known tile at zoom 10, converting back should give the NW
        // corner, and converting that corner back should return the same tile.
        let zoom = 10;
        let (orig_x, orig_y) = (348u32, 603u32);
        let (lat, lon) = tile_to_lat_lon(orig_x, orig_y, zoom);
        let (rt_x, rt_y) = lat_lon_to_tile(lat + 0.0001, lon + 0.0001, zoom);
        assert_eq!(rt_x, orig_x);
        assert_eq!(rt_y, orig_y);
    }

    #[test]
    fn test_tile_to_lat_lon_bounds() {
        // Tile (0, 0) at zoom 1 should be NW quadrant.
        let (lat, lon) = tile_to_lat_lon(0, 0, 1);
        assert!((lat - 85.05).abs() < 0.1);
        assert!((lon - (-180.0)).abs() < 0.001);
    }

    #[test]
    fn test_lat_lon_to_tile_clamping() {
        // Extreme south should not panic.
        let (x, y) = lat_lon_to_tile(-85.0, 179.9, 5);
        assert!(x < 32);
        assert!(y < 32);
    }
}
