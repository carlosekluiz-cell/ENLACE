//! Signal strength to color mapping for RF coverage visualization.
//!
//! Provides an industry-standard color scale mapping received signal
//! strength (dBm) to RGBA colors, from deep blue (excellent) through
//! green (good), yellow (fair), orange (poor), to red (marginal).

use crate::geotiff::RasterBounds;

/// Maps signal strength values to RGBA colors.
pub struct ColorMapper {
    /// Threshold-color pairs, sorted from strongest to weakest signal.
    /// Each entry is (minimum_dbm, RGBA_color).
    pub thresholds: Vec<(f64, [u8; 4])>,
}

impl ColorMapper {
    /// Create a color mapper with the default RF coverage color scale.
    ///
    /// Color scale (similar to industry standard):
    /// - >= -60 dBm: deep blue (excellent)
    /// - -60 to -70: blue
    /// - -70 to -80: green (good)
    /// - -80 to -85: yellow (fair)
    /// - -85 to -95: orange (poor)
    /// - -95 to -105: red (marginal)
    /// - < -105: transparent (no coverage)
    pub fn default_rf() -> Self {
        Self {
            thresholds: vec![
                (-60.0, [0, 0, 180, 255]),    // deep blue — excellent
                (-70.0, [30, 100, 255, 255]),  // blue
                (-80.0, [0, 200, 50, 255]),    // green — good
                (-85.0, [255, 255, 0, 255]),   // yellow — fair
                (-95.0, [255, 165, 0, 255]),   // orange — poor
                (-105.0, [255, 0, 0, 255]),    // red — marginal
            ],
        }
    }

    /// Map a single signal strength value to an RGBA color.
    ///
    /// # Parameters
    /// - `signal_dbm`: Received signal strength in dBm
    ///
    /// # Returns
    /// RGBA color as `[R, G, B, A]`.
    pub fn map_color(&self, signal_dbm: f64) -> [u8; 4] {
        for &(threshold, color) in &self.thresholds {
            if signal_dbm >= threshold {
                return color;
            }
        }
        // Below all thresholds: transparent (no coverage)
        [0, 0, 0, 0]
    }

    /// Render an entire coverage grid to RGBA pixel data.
    ///
    /// Maps a set of (lat, lon, signal_dbm) points onto a raster grid
    /// using nearest-neighbor assignment.
    ///
    /// # Parameters
    /// - `points`: Coverage data as (latitude, longitude, signal_dbm) tuples
    /// - `width`: Output raster width in pixels
    /// - `height`: Output raster height in pixels
    /// - `bounds`: Geographic bounds for the output raster
    ///
    /// # Returns
    /// RGBA pixel data in row-major order (north to south), 4 bytes per pixel.
    pub fn render_coverage(
        &self,
        points: &[(f64, f64, f64)],
        width: usize,
        height: usize,
        bounds: &RasterBounds,
    ) -> Vec<u8> {
        let num_pixels = width * height;
        let mut rgba = vec![0u8; num_pixels * 4]; // Initialize to transparent

        if width == 0 || height == 0 || points.is_empty() {
            return rgba;
        }

        let lon_range = bounds.east - bounds.west;
        let lat_range = bounds.north - bounds.south;

        if lon_range <= 0.0 || lat_range <= 0.0 {
            return rgba;
        }

        // For each point, find the nearest pixel and assign color
        for &(lat, lon, signal_dbm) in points {
            // Convert geographic coordinates to pixel coordinates
            let px = ((lon - bounds.west) / lon_range * width as f64) as isize;
            let py = ((bounds.north - lat) / lat_range * height as f64) as isize;

            if px >= 0 && px < width as isize && py >= 0 && py < height as isize {
                let idx = (py as usize * width + px as usize) * 4;
                let color = self.map_color(signal_dbm);

                // Only overwrite if the new signal is stronger (higher dBm)
                // or the pixel is currently transparent
                if rgba[idx + 3] == 0 || signal_dbm > self.current_dbm_at_pixel(&rgba, idx) {
                    rgba[idx] = color[0];
                    rgba[idx + 1] = color[1];
                    rgba[idx + 2] = color[2];
                    rgba[idx + 3] = color[3];
                }
            }
        }

        rgba
    }

    /// Estimate the dBm value at a pixel from its color (approximate inverse mapping).
    /// Used to determine which signal to prefer when multiple points map to the same pixel.
    fn current_dbm_at_pixel(&self, rgba: &[u8], idx: usize) -> f64 {
        if rgba[idx + 3] == 0 {
            return f64::NEG_INFINITY;
        }
        let current_color = [rgba[idx], rgba[idx + 1], rgba[idx + 2], rgba[idx + 3]];
        // Find matching threshold (approximate)
        for &(threshold, color) in &self.thresholds {
            if current_color == color {
                return threshold;
            }
        }
        f64::NEG_INFINITY
    }
}

impl Default for ColorMapper {
    fn default() -> Self {
        Self::default_rf()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_color_mapping_excellent() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-50.0);
        assert_eq!(color, [0, 0, 180, 255], "Signal >= -60 dBm should be deep blue");
    }

    #[test]
    fn test_color_mapping_at_threshold() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-60.0);
        assert_eq!(color, [0, 0, 180, 255], "Signal at -60 dBm should be deep blue");
    }

    #[test]
    fn test_color_mapping_blue() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-65.0);
        assert_eq!(color, [30, 100, 255, 255], "Signal -60 to -70 should be blue");
    }

    #[test]
    fn test_color_mapping_green() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-75.0);
        assert_eq!(color, [0, 200, 50, 255], "Signal -70 to -80 should be green");
    }

    #[test]
    fn test_color_mapping_yellow() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-82.0);
        assert_eq!(color, [255, 255, 0, 255], "Signal -80 to -85 should be yellow");
    }

    #[test]
    fn test_color_mapping_orange() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-90.0);
        assert_eq!(color, [255, 165, 0, 255], "Signal -85 to -95 should be orange");
    }

    #[test]
    fn test_color_mapping_red() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-100.0);
        assert_eq!(color, [255, 0, 0, 255], "Signal -95 to -105 should be red");
    }

    #[test]
    fn test_color_mapping_no_coverage() {
        let mapper = ColorMapper::default_rf();
        let color = mapper.map_color(-110.0);
        assert_eq!(color, [0, 0, 0, 0], "Signal below -105 should be transparent");
    }

    #[test]
    fn test_render_coverage_basic() {
        let mapper = ColorMapper::default_rf();
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 10,
            height: 10,
        };

        // Single point at the center with strong signal
        let points = vec![(-23.5, -46.5, -50.0)];
        let rgba = mapper.render_coverage(&points, 10, 10, &bounds);

        assert_eq!(rgba.len(), 10 * 10 * 4);

        // Check that at least one pixel is non-transparent
        let has_color = rgba.chunks(4).any(|c| c[3] > 0);
        assert!(has_color, "Should have at least one colored pixel");
    }

    #[test]
    fn test_render_coverage_empty() {
        let mapper = ColorMapper::default_rf();
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 5,
            height: 5,
        };

        let rgba = mapper.render_coverage(&[], 5, 5, &bounds);
        assert_eq!(rgba.len(), 5 * 5 * 4);

        // All pixels should be transparent
        for chunk in rgba.chunks(4) {
            assert_eq!(chunk[3], 0, "Empty coverage should be all transparent");
        }
    }

    #[test]
    fn test_render_coverage_multiple_points() {
        let mapper = ColorMapper::default_rf();
        let bounds = RasterBounds {
            west: -47.0,
            south: -24.0,
            east: -46.0,
            north: -23.0,
            width: 100,
            height: 100,
        };

        let points = vec![
            (-23.2, -46.8, -50.0),  // excellent
            (-23.5, -46.5, -75.0),  // good
            (-23.8, -46.2, -100.0), // marginal
        ];

        let rgba = mapper.render_coverage(&points, 100, 100, &bounds);
        assert_eq!(rgba.len(), 100 * 100 * 4);

        let colored_count = rgba.chunks(4).filter(|c| c[3] > 0).count();
        assert!(
            colored_count >= 3,
            "Should have at least 3 colored pixels: {}",
            colored_count
        );
    }

    #[test]
    fn test_default_impl() {
        let mapper = ColorMapper::default();
        assert_eq!(mapper.thresholds.len(), 6, "Default mapper should have 6 thresholds");

        // Verify it behaves the same as default_rf
        let mapper_rf = ColorMapper::default_rf();
        assert_eq!(
            mapper.map_color(-50.0),
            mapper_rf.map_color(-50.0),
            "Default and default_rf should produce same results"
        );
    }

    #[test]
    fn test_color_mapping_boundary_values() {
        let mapper = ColorMapper::default_rf();

        // Right at each threshold boundary
        assert_eq!(mapper.map_color(-70.0)[0], 30, "At -70 should be blue");
        assert_eq!(mapper.map_color(-80.0)[1], 200, "At -80 should be green");
        assert_eq!(mapper.map_color(-85.0)[0], 255, "At -85 should be yellow");
        assert_eq!(mapper.map_color(-95.0)[0], 255, "At -95 should be orange");
        assert_eq!(mapper.map_color(-105.0)[0], 255, "At -105 should be red");
    }
}
