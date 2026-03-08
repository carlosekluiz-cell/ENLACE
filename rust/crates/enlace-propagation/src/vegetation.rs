//! Brazilian biome-specific vegetation correction layer.
//!
//! Provides RF attenuation corrections based on vegetation type and density
//! for the six major Brazilian biomes. Corrections are applied after the
//! base propagation model calculation.
//!
//! The default correction values are derived from published IEEE research
//! on vegetation attenuation in tropical environments.

use enlace_terrain::TerrainProfile;
use serde::{Deserialize, Serialize};

/// Vegetation correction calculator.
///
/// Holds a table of per-biome, per-frequency attenuation values and provides
/// methods to compute total vegetation correction along a path.
pub struct VegetationCorrector {
    corrections: Vec<BiomeCorrection>,
}

/// Attenuation parameters for a specific biome and frequency band.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BiomeCorrection {
    /// Biome identifier (e.g., "amazonia", "cerrado").
    pub biome_type: String,
    /// Lower bound of the applicable frequency band (MHz).
    pub freq_min_mhz: f64,
    /// Upper bound of the applicable frequency band (MHz).
    pub freq_max_mhz: f64,
    /// Mean attenuation per 100 m of vegetation depth (dB).
    pub loss_db_per_100m: f64,
    /// Standard deviation of the attenuation (dB).
    pub loss_db_stddev: f64,
}

/// Land cover information for a point along a path.
#[derive(Debug, Clone)]
pub struct LandCoverInfo {
    /// Land cover type (e.g., "forest", "grassland").
    pub cover_type: String,
    /// Biome name (e.g., "amazonia", "cerrado").
    pub biome: String,
    /// Vegetation density percentage (0-100).
    pub density_pct: f64,
}

/// Result of vegetation correction along a path.
#[derive(Debug, Clone)]
pub struct VegetationCorrectionResult {
    /// Total vegetation correction in dB.
    pub total_correction_db: f64,
    /// Per-segment breakdown.
    pub segments: Vec<PathSegmentCorrection>,
}

/// Vegetation correction for a single path segment.
#[derive(Debug, Clone)]
pub struct PathSegmentCorrection {
    /// Start distance from TX in meters.
    pub start_distance_m: f64,
    /// End distance from TX in meters.
    pub end_distance_m: f64,
    /// Biome type for this segment.
    pub biome: String,
    /// Vegetation correction for this segment in dB.
    pub correction_db: f64,
}

impl VegetationCorrector {
    /// Create a corrector with default Brazilian biome corrections.
    ///
    /// Default values from published IEEE research on vegetation attenuation:
    ///
    /// | Biome           | 700 MHz | 900 MHz | 1800 MHz | 2100 MHz | 3500 MHz |
    /// |-----------------|---------|---------|----------|----------|----------|
    /// | amazonia         | 15/100m | 22/100m | 30/100m  | 35/100m  | 45/100m  |
    /// | mata_atlantica   | 8/100m  | 12/100m | 18/100m  | 22/100m  | 30/100m  |
    /// | cerrado          | 3/100m  | 5/100m  | 8/100m   | 10/100m  | 15/100m  |
    /// | caatinga         | 1/100m  | 2/100m  | 3/100m   | 4/100m   | 6/100m   |
    /// | pampa            | 0.5/100m| 1/100m  | 1.5/100m | 2/100m   | 3/100m   |
    /// | pantanal         | 5/100m  | 8/100m  | 12/100m  | 15/100m  | 20/100m  |
    pub fn with_defaults() -> Self {
        let corrections = vec![
            // Amazonia
            BiomeCorrection { biome_type: "amazonia".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 15.0, loss_db_stddev: 5.0 },
            BiomeCorrection { biome_type: "amazonia".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 22.0, loss_db_stddev: 6.0 },
            BiomeCorrection { biome_type: "amazonia".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 30.0, loss_db_stddev: 8.0 },
            BiomeCorrection { biome_type: "amazonia".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 35.0, loss_db_stddev: 9.0 },
            BiomeCorrection { biome_type: "amazonia".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 45.0, loss_db_stddev: 12.0 },

            // Mata Atlantica
            BiomeCorrection { biome_type: "mata_atlantica".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 8.0, loss_db_stddev: 3.0 },
            BiomeCorrection { biome_type: "mata_atlantica".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 12.0, loss_db_stddev: 4.0 },
            BiomeCorrection { biome_type: "mata_atlantica".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 18.0, loss_db_stddev: 5.0 },
            BiomeCorrection { biome_type: "mata_atlantica".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 22.0, loss_db_stddev: 6.0 },
            BiomeCorrection { biome_type: "mata_atlantica".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 30.0, loss_db_stddev: 8.0 },

            // Cerrado
            BiomeCorrection { biome_type: "cerrado".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 3.0, loss_db_stddev: 1.5 },
            BiomeCorrection { biome_type: "cerrado".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 5.0, loss_db_stddev: 2.0 },
            BiomeCorrection { biome_type: "cerrado".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 8.0, loss_db_stddev: 3.0 },
            BiomeCorrection { biome_type: "cerrado".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 10.0, loss_db_stddev: 3.5 },
            BiomeCorrection { biome_type: "cerrado".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 15.0, loss_db_stddev: 5.0 },

            // Caatinga
            BiomeCorrection { biome_type: "caatinga".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 1.0, loss_db_stddev: 0.5 },
            BiomeCorrection { biome_type: "caatinga".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 2.0, loss_db_stddev: 1.0 },
            BiomeCorrection { biome_type: "caatinga".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 3.0, loss_db_stddev: 1.5 },
            BiomeCorrection { biome_type: "caatinga".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 4.0, loss_db_stddev: 2.0 },
            BiomeCorrection { biome_type: "caatinga".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 6.0, loss_db_stddev: 2.5 },

            // Pampa
            BiomeCorrection { biome_type: "pampa".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 0.5, loss_db_stddev: 0.3 },
            BiomeCorrection { biome_type: "pampa".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 1.0, loss_db_stddev: 0.5 },
            BiomeCorrection { biome_type: "pampa".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 1.5, loss_db_stddev: 0.8 },
            BiomeCorrection { biome_type: "pampa".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 2.0, loss_db_stddev: 1.0 },
            BiomeCorrection { biome_type: "pampa".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 3.0, loss_db_stddev: 1.5 },

            // Pantanal
            BiomeCorrection { biome_type: "pantanal".into(), freq_min_mhz: 600.0, freq_max_mhz: 800.0, loss_db_per_100m: 5.0, loss_db_stddev: 3.0 },
            BiomeCorrection { biome_type: "pantanal".into(), freq_min_mhz: 800.0, freq_max_mhz: 1000.0, loss_db_per_100m: 8.0, loss_db_stddev: 4.0 },
            BiomeCorrection { biome_type: "pantanal".into(), freq_min_mhz: 1700.0, freq_max_mhz: 1900.0, loss_db_per_100m: 12.0, loss_db_stddev: 5.0 },
            BiomeCorrection { biome_type: "pantanal".into(), freq_min_mhz: 1900.0, freq_max_mhz: 2200.0, loss_db_per_100m: 15.0, loss_db_stddev: 6.0 },
            BiomeCorrection { biome_type: "pantanal".into(), freq_min_mhz: 3300.0, freq_max_mhz: 3800.0, loss_db_per_100m: 20.0, loss_db_stddev: 8.0 },
        ];

        Self { corrections }
    }

    /// Create a corrector with custom corrections.
    pub fn new(corrections: Vec<BiomeCorrection>) -> Self {
        Self { corrections }
    }

    /// Compute vegetation correction for a single path segment
    /// through a given biome at a given frequency.
    ///
    /// # Parameters
    /// - `biome`: biome identifier (e.g., "amazonia")
    /// - `freq_mhz`: carrier frequency in MHz
    /// - `depth_m`: depth of vegetation along the path in meters
    ///
    /// # Returns
    /// Vegetation attenuation in dB.
    pub fn correction_for_segment(&self, biome: &str, freq_mhz: f64, depth_m: f64) -> f64 {
        if depth_m <= 0.0 {
            return 0.0;
        }

        // Find the best matching correction entry
        let matching: Vec<&BiomeCorrection> = self
            .corrections
            .iter()
            .filter(|c| {
                c.biome_type == biome && freq_mhz >= c.freq_min_mhz && freq_mhz <= c.freq_max_mhz
            })
            .collect();

        if let Some(correction) = matching.first() {
            // Scale from per-100m to actual depth
            correction.loss_db_per_100m * (depth_m / 100.0)
        } else {
            // No exact match — try to interpolate from the closest entries
            self.interpolate_correction(biome, freq_mhz, depth_m)
        }
    }

    /// Interpolate correction when no exact frequency band match exists.
    fn interpolate_correction(&self, biome: &str, freq_mhz: f64, depth_m: f64) -> f64 {
        let biome_entries: Vec<&BiomeCorrection> = self
            .corrections
            .iter()
            .filter(|c| c.biome_type == biome)
            .collect();

        if biome_entries.is_empty() {
            return 0.0;
        }

        // Find the two closest frequency bands
        let mut lower: Option<&BiomeCorrection> = None;
        let mut upper: Option<&BiomeCorrection> = None;

        for entry in &biome_entries {
            let mid = (entry.freq_min_mhz + entry.freq_max_mhz) / 2.0;
            if mid <= freq_mhz {
                if lower.is_none()
                    || mid
                        > (lower.unwrap().freq_min_mhz + lower.unwrap().freq_max_mhz) / 2.0
                {
                    lower = Some(entry);
                }
            }
            if mid >= freq_mhz {
                if upper.is_none()
                    || mid
                        < (upper.unwrap().freq_min_mhz + upper.unwrap().freq_max_mhz) / 2.0
                {
                    upper = Some(entry);
                }
            }
        }

        let loss_per_100m = match (lower, upper) {
            (Some(l), Some(u)) => {
                let l_mid = (l.freq_min_mhz + l.freq_max_mhz) / 2.0;
                let u_mid = (u.freq_min_mhz + u.freq_max_mhz) / 2.0;
                if (u_mid - l_mid).abs() < 1.0 {
                    l.loss_db_per_100m
                } else {
                    let frac = (freq_mhz - l_mid) / (u_mid - l_mid);
                    l.loss_db_per_100m + frac * (u.loss_db_per_100m - l.loss_db_per_100m)
                }
            }
            (Some(l), None) => l.loss_db_per_100m,
            (None, Some(u)) => u.loss_db_per_100m,
            (None, None) => 0.0,
        };

        loss_per_100m * (depth_m / 100.0)
    }

    /// Compute total vegetation correction along a terrain profile.
    ///
    /// Uses a land cover function to determine the biome at each point
    /// along the profile, then sums the per-segment corrections.
    ///
    /// # Parameters
    /// - `profile`: terrain profile from `enlace-terrain`
    /// - `frequency_mhz`: carrier frequency in MHz
    /// - `land_cover_fn`: function that returns land cover info for a (lat, lon) point
    pub fn compute_correction<F>(
        &self,
        profile: &TerrainProfile,
        frequency_mhz: f64,
        land_cover_fn: F,
    ) -> VegetationCorrectionResult
    where
        F: Fn(f64, f64) -> Option<LandCoverInfo>,
    {
        let mut segments = Vec::new();
        let mut total_correction = 0.0;

        if profile.points.len() < 2 {
            return VegetationCorrectionResult {
                total_correction_db: 0.0,
                segments,
            };
        }

        // Walk through profile points, group consecutive points with the same biome
        let mut current_biome: Option<String> = None;
        let mut segment_start = 0.0_f64;

        for i in 0..profile.points.len() {
            let point = &profile.points[i];
            let land_cover = land_cover_fn(point.latitude, point.longitude);

            let biome = land_cover
                .as_ref()
                .map(|lc| lc.biome.clone())
                .unwrap_or_default();
            let density = land_cover
                .as_ref()
                .map(|lc| lc.density_pct)
                .unwrap_or(0.0);

            let is_last = i == profile.points.len() - 1;
            let biome_changed = current_biome.as_ref() != Some(&biome);

            if biome_changed || is_last {
                // Close the current segment
                if let Some(ref prev_biome) = current_biome {
                    if !prev_biome.is_empty() {
                        let segment_end = point.distance_m;
                        let depth = (segment_end - segment_start) * (density / 100.0);

                        let correction =
                            self.correction_for_segment(prev_biome, frequency_mhz, depth);

                        if correction > 0.0 {
                            segments.push(PathSegmentCorrection {
                                start_distance_m: segment_start,
                                end_distance_m: segment_end,
                                biome: prev_biome.clone(),
                                correction_db: correction,
                            });
                            total_correction += correction;
                        }
                    }
                }

                // Start new segment
                current_biome = Some(biome);
                segment_start = point.distance_m;
            }
        }

        VegetationCorrectionResult {
            total_correction_db: total_correction,
            segments,
        }
    }
}

impl Default for VegetationCorrector {
    fn default() -> Self {
        Self::with_defaults()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_amazonia_900mhz() {
        let corrector = VegetationCorrector::with_defaults();
        let loss = corrector.correction_for_segment("amazonia", 900.0, 100.0);
        assert!(
            (loss - 22.0).abs() < 0.1,
            "Amazonia at 900 MHz, 100m: expected 22 dB, got {} dB",
            loss
        );
    }

    #[test]
    fn test_cerrado_900mhz() {
        let corrector = VegetationCorrector::with_defaults();
        let loss = corrector.correction_for_segment("cerrado", 900.0, 100.0);
        assert!(
            (loss - 5.0).abs() < 0.1,
            "Cerrado at 900 MHz, 100m: expected 5 dB, got {} dB",
            loss
        );
    }

    #[test]
    fn test_pampa_low_loss() {
        let corrector = VegetationCorrector::with_defaults();
        let loss = corrector.correction_for_segment("pampa", 900.0, 100.0);
        assert!(
            (loss - 1.0).abs() < 0.1,
            "Pampa at 900 MHz, 100m: expected 1 dB, got {} dB",
            loss
        );
    }

    #[test]
    fn test_zero_depth() {
        let corrector = VegetationCorrector::with_defaults();
        let loss = corrector.correction_for_segment("amazonia", 900.0, 0.0);
        assert_eq!(loss, 0.0, "Zero depth should give zero correction");
    }

    #[test]
    fn test_unknown_biome() {
        let corrector = VegetationCorrector::with_defaults();
        let loss = corrector.correction_for_segment("unknown_biome", 900.0, 100.0);
        assert_eq!(loss, 0.0, "Unknown biome should give zero correction");
    }

    #[test]
    fn test_frequency_interpolation() {
        let corrector = VegetationCorrector::with_defaults();
        // 1200 MHz is between the 900 and 1800 MHz bands for amazonia
        let loss = corrector.correction_for_segment("amazonia", 1200.0, 100.0);
        // Should interpolate between 22 (900 MHz) and 30 (1800 MHz)
        assert!(
            loss > 22.0 && loss < 30.0,
            "Interpolated loss at 1200 MHz: {} dB",
            loss
        );
    }

    #[test]
    fn test_higher_frequency_more_loss() {
        let corrector = VegetationCorrector::with_defaults();
        let loss_700 = corrector.correction_for_segment("mata_atlantica", 700.0, 100.0);
        let loss_3500 = corrector.correction_for_segment("mata_atlantica", 3500.0, 100.0);
        assert!(
            loss_3500 > loss_700,
            "Higher frequency should have more loss: 700={}, 3500={}",
            loss_700,
            loss_3500
        );
    }

    #[test]
    fn test_scaling_with_depth() {
        let corrector = VegetationCorrector::with_defaults();
        let loss_100m = corrector.correction_for_segment("amazonia", 900.0, 100.0);
        let loss_200m = corrector.correction_for_segment("amazonia", 900.0, 200.0);
        assert!(
            (loss_200m - 2.0 * loss_100m).abs() < 0.01,
            "Double depth should give double loss: 100m={}, 200m={}",
            loss_100m,
            loss_200m
        );
    }
}
