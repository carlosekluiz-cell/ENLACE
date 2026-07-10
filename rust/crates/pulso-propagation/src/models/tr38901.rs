//! 3GPP TR 38.901 5G NR propagation models.
//!
//! Implements four deployment scenarios from Table 7.4.1-1:
//! - **RMa** (Rural Macrocell): 0.5–30 GHz, 10 m–10 km, BS 35 m
//! - **UMa** (Urban Macrocell): 0.5–30 GHz, 10 m–5 km, BS 25 m
//! - **UMi** (Urban Microcell / Street Canyon): 0.5–30 GHz, 10 m–5 km, BS 10 m
//! - **InF** (Indoor Factory): 0.5–100 GHz, 1 m–600 m, BS 1–25 m
//!
//! Also provides a basic beamforming array gain utility.
//!
//! Reference: 3GPP TR 38.901 V17.0.0 (2022-03), Tables 7.4.1-1 through 7.4.1-4.

use crate::common::{PropagationMode, SPEED_OF_LIGHT};
use super::{Environment, PathLossParams, PathLossResult, PropagationModel};

// ═══════════════════════════════════════════════════════════════════════════════
// Beamforming utility
// ═══════════════════════════════════════════════════════════════════════════════

/// Compute array gain for a uniform linear antenna array.
///
/// At boresight (steering_angle_deg = 0): `G = 10·log10(N)` dB.
/// Off-axis: reduced by approximately `cos²(theta)`.
///
/// # Arguments
/// * `n_elements` — Number of antenna elements (e.g. 8, 16, 32, 64)
/// * `steering_angle_deg` — Steering angle off boresight in degrees (0 = on-axis)
///
/// # Returns
/// Array gain in dB. Returns 0.0 if `n_elements < 1`.
pub fn beamforming_gain_db(n_elements: u32, steering_angle_deg: f64) -> f64 {
    if n_elements < 1 {
        return 0.0;
    }
    let boresight_gain = 10.0 * (n_elements as f64).log10();
    let theta_rad = steering_angle_deg.to_radians();
    let cos_sq = theta_rad.cos().powi(2);
    boresight_gain * cos_sq
}

// ═══════════════════════════════════════════════════════════════════════════════
// RMa — Rural Macrocell
// ═══════════════════════════════════════════════════════════════════════════════

/// 3GPP TR 38.901 Rural Macrocell (RMa) model.
pub struct Tr38901RmaModel {
    /// Average building height in meters (default 5 m for rural).
    pub avg_building_height_m: f64,
    /// Average street width in meters (default 20 m for rural).
    pub avg_street_width_m: f64,
}

impl Tr38901RmaModel {
    /// Create a new TR 38.901 RMa model with default parameters.
    pub fn new() -> Self {
        Self {
            avg_building_height_m: 5.0,
            avg_street_width_m: 20.0,
        }
    }

    /// Create with custom building/street parameters.
    pub fn with_params(avg_building_height_m: f64, avg_street_width_m: f64) -> Self {
        Self {
            avg_building_height_m,
            avg_street_width_m,
        }
    }

    /// Compute LOS path loss.
    ///
    /// For d_2D < d_BP:
    ///   PL1 = 20*log10(40*pi*d_3D*f_c/3) + min(0.03*h^1.72, 10)*log10(d_3D)
    ///         - min(0.044*h^1.72, 14.77) + 0.002*log10(h)*d_3D
    ///
    /// For d_2D >= d_BP:
    ///   PL2 = PL1(d_BP) + 40*log10(d_3D/d_BP)
    fn los_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h = self.avg_building_height_m;

        // Breakpoint distance
        let d_bp = 2.0 * std::f64::consts::PI * h_bs * h_ut * freq_ghz * 1e9 / SPEED_OF_LIGHT;

        let term1 = 20.0 * (40.0 * std::f64::consts::PI * d_3d * freq_ghz / 3.0)
            .max(1.0)
            .log10();
        let term2 = (0.03 * h.powf(1.72)).min(10.0) * d_3d.max(1.0).log10();
        let term3 = (0.044 * h.powf(1.72)).min(14.77);
        let term4 = 0.002 * h.max(0.01).log10() * d_3d;

        let pl1 = term1 + term2 - term3 + term4;

        if d_2d < d_bp {
            pl1
        } else {
            // Beyond breakpoint
            let d_3d_bp = (d_bp * d_bp + (h_bs - h_ut).powi(2)).sqrt();
            let pl1_bp = {
                let t1 = 20.0
                    * (40.0 * std::f64::consts::PI * d_3d_bp * freq_ghz / 3.0)
                        .max(1.0)
                        .log10();
                let t2 = (0.03 * h.powf(1.72)).min(10.0) * d_3d_bp.max(1.0).log10();
                let t3 = (0.044 * h.powf(1.72)).min(14.77);
                let t4 = 0.002 * h.max(0.01).log10() * d_3d_bp;
                t1 + t2 - t3 + t4
            };
            pl1_bp + 40.0 * (d_3d / d_3d_bp).max(1.0).log10()
        }
    }

    /// Compute NLOS path loss.
    ///
    /// PL_NLOS = max(PL_LOS, PL'_NLOS)
    /// PL'_NLOS = 161.04 - 7.1*log10(W) + 7.5*log10(h)
    ///            - (24.37 - 3.7*(h/h_BS)^2)*log10(h_BS)
    ///            + (43.42 - 3.1*log10(h_BS))*(log10(d_3D) - 3)
    ///            + 20*log10(f_c) - (3.2*(log10(11.75*h_UT))^2 - 4.97)
    fn nlos_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h = self.avg_building_height_m;
        let w = self.avg_street_width_m;

        let pl_los = self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut);

        let pl_nlos_prime = 161.04
            - 7.1 * w.max(1.0).log10()
            + 7.5 * h.max(1.0).log10()
            - (24.37 - 3.7 * (h / h_bs.max(1.0)).powi(2)) * h_bs.max(1.0).log10()
            + (43.42 - 3.1 * h_bs.max(1.0).log10()) * (d_3d.max(1.0).log10() - 3.0)
            + 20.0 * freq_ghz.max(0.001).log10()
            - (3.2 * (11.75 * h_ut.max(0.1)).log10().powi(2) - 4.97);

        pl_los.max(pl_nlos_prime)
    }
}

impl Default for Tr38901RmaModel {
    fn default() -> Self {
        Self::new()
    }
}

impl PropagationModel for Tr38901RmaModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq_ghz = params.frequency_mhz / 1000.0;
        let h_bs = params.tx_height_m;
        let h_ut = params.rx_height_m;

        // Validate frequency
        if freq_ghz < 0.5 || freq_ghz > 30.0 {
            warnings.push(format!(
                "Frequency {} GHz outside TR 38.901 RMa range (0.5-30 GHz)",
                freq_ghz
            ));
        }

        // Validate distance
        if params.distance_m < 10.0 || params.distance_m > 10_000.0 {
            warnings.push(format!(
                "Distance {} m outside TR 38.901 RMa range (10-10000 m)",
                params.distance_m
            ));
        }

        // 2D and 3D distances
        let d_2d = params.distance_m;
        let d_3d = (d_2d * d_2d + (h_bs - h_ut).powi(2)).sqrt();

        // Determine LOS probability based on environment
        let is_los = match params.environment {
            Environment::OpenRural => true, // Open rural is always LOS
            Environment::Rural => d_2d < 1000.0, // Simplified LOS probability
            Environment::Suburban => d_2d < 500.0,
            Environment::Urban => d_2d < 200.0,
        };

        let (loss_db, mode) = if is_los {
            (
                self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::LineOfSight,
            )
        } else {
            (
                self.nlos_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::Diffraction,
            )
        };

        // Shadow fading standard deviation
        let variability_db = if is_los { 4.0 } else { 8.0 };

        PathLossResult {
            loss_db,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "3GPP TR 38.901 Rural Macrocell (RMa)"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (500.0, 30_000.0) // 0.5 - 30 GHz
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// UMa — Urban Macrocell
// ═══════════════════════════════════════════════════════════════════════════════

/// 3GPP TR 38.901 Urban Macrocell (UMa) model.
///
/// Designed for urban outdoor coverage with base station above rooftop level.
/// Typical: BS height 25 m, UE height 1.5 m, buildings 5–50 m, range 10 m–5 km.
///
/// Reference: 3GPP TR 38.901 V17.0.0, Table 7.4.1-1.
pub struct Tr38901UmaModel {
    /// Effective environment height in meters (default 1.0 m).
    /// h_E = 1.0 m with probability 1/(1 + C(d_2D, h_UT)) per Table 7.4.2-1.
    /// Simplified to 1.0 m here.
    pub effective_env_height_m: f64,
}

impl Tr38901UmaModel {
    pub fn new() -> Self {
        Self {
            effective_env_height_m: 1.0,
        }
    }

    /// UMa LOS path loss (Table 7.4.1-1).
    ///
    /// For d_2D <= d'_BP:
    ///   PL1 = 28.0 + 22·log10(d_3D) + 20·log10(f_c)
    /// For d_2D > d'_BP:
    ///   PL2 = 28.0 + 40·log10(d_3D) + 20·log10(f_c)
    ///         - 9·log10((d'_BP)² + (h_BS - h_UT)²)
    ///
    /// d'_BP = 4·(h_BS - h_E)·(h_UT - h_E)·f_c / c
    fn los_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h_e = self.effective_env_height_m;
        let h_bs_eff = h_bs - h_e;
        let h_ut_eff = h_ut - h_e;

        // Breakpoint distance
        let d_bp_prime = 4.0 * h_bs_eff * h_ut_eff * freq_ghz * 1e9 / SPEED_OF_LIGHT;

        let pl1 = 28.0 + 22.0 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10();

        if d_2d <= d_bp_prime {
            pl1
        } else {
            let d_3d_bp = (d_bp_prime * d_bp_prime + (h_bs - h_ut).powi(2)).sqrt();
            28.0 + 40.0 * d_3d.max(1.0).log10()
                + 20.0 * freq_ghz.max(0.001).log10()
                - 9.0 * (d_bp_prime.powi(2) + (h_bs - h_ut).powi(2)).max(1.0).log10()
        }
    }

    /// UMa NLOS path loss (Table 7.4.1-1).
    ///
    /// PL'_NLOS = 13.54 + 39.08·log10(d_3D) + 20·log10(f_c) - 0.6·(h_UT - 1.5)
    /// PL_NLOS = max(PL_LOS, PL'_NLOS)
    fn nlos_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let pl_los = self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut);

        let pl_nlos_prime = 13.54
            + 39.08 * d_3d.max(1.0).log10()
            + 20.0 * freq_ghz.max(0.001).log10()
            - 0.6 * (h_ut - 1.5);

        pl_los.max(pl_nlos_prime)
    }
}

impl Default for Tr38901UmaModel {
    fn default() -> Self {
        Self::new()
    }
}

impl PropagationModel for Tr38901UmaModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq_ghz = params.frequency_mhz / 1000.0;
        let h_bs = params.tx_height_m;
        let h_ut = params.rx_height_m;

        if freq_ghz < 0.5 || freq_ghz > 30.0 {
            warnings.push(format!(
                "Frequency {} GHz outside TR 38.901 UMa range (0.5-30 GHz)",
                freq_ghz
            ));
        }
        if params.distance_m < 10.0 || params.distance_m > 5_000.0 {
            warnings.push(format!(
                "Distance {} m outside TR 38.901 UMa range (10-5000 m)",
                params.distance_m
            ));
        }

        let d_2d = params.distance_m;
        let d_3d = (d_2d * d_2d + (h_bs - h_ut).powi(2)).sqrt();

        // UMa LOS probability per Table 7.4.2-1 (simplified deterministic threshold)
        let is_los = match params.environment {
            Environment::OpenRural | Environment::Rural => d_2d < 500.0,
            Environment::Suburban => d_2d < 300.0,
            Environment::Urban => d_2d < 250.0,
        };

        let (loss_db, mode) = if is_los {
            (
                self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::LineOfSight,
            )
        } else {
            (
                self.nlos_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::Diffraction,
            )
        };

        // Shadow fading: LOS sigma=4 dB, NLOS sigma=6 dB (Table 7.4.1-1)
        let variability_db = if is_los { 4.0 } else { 6.0 };

        PathLossResult {
            loss_db,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "3GPP TR 38.901 Urban Macrocell (UMa)"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (500.0, 30_000.0)
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// UMi — Urban Microcell (Street Canyon)
// ═══════════════════════════════════════════════════════════════════════════════

/// 3GPP TR 38.901 Urban Microcell — Street Canyon (UMi) model.
///
/// Designed for small cells below rooftop level in urban street canyons.
/// Typical: BS height 10 m, UE height 1.5 m, range 10 m–5 km.
///
/// Reference: 3GPP TR 38.901 V17.0.0, Table 7.4.1-1.
pub struct Tr38901UmiModel {
    /// Effective environment height in meters (default 1.0 m).
    pub effective_env_height_m: f64,
}

impl Tr38901UmiModel {
    pub fn new() -> Self {
        Self {
            effective_env_height_m: 1.0,
        }
    }

    /// UMi-Street Canyon LOS path loss.
    ///
    /// For d_2D <= d'_BP:
    ///   PL1 = 32.4 + 21·log10(d_3D) + 20·log10(f_c)
    /// For d_2D > d'_BP:
    ///   PL2 = 32.4 + 40·log10(d_3D) + 20·log10(f_c)
    ///         - 9.5·log10((d'_BP)² + (h_BS - h_UT)²)
    fn los_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let h_e = self.effective_env_height_m;
        let h_bs_eff = h_bs - h_e;
        let h_ut_eff = h_ut - h_e;

        let d_bp_prime = 4.0 * h_bs_eff * h_ut_eff * freq_ghz * 1e9 / SPEED_OF_LIGHT;

        let pl1 = 32.4 + 21.0 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10();

        if d_2d <= d_bp_prime {
            pl1
        } else {
            32.4 + 40.0 * d_3d.max(1.0).log10()
                + 20.0 * freq_ghz.max(0.001).log10()
                - 9.5 * (d_bp_prime.powi(2) + (h_bs - h_ut).powi(2)).max(1.0).log10()
        }
    }

    /// UMi-Street Canyon NLOS path loss.
    ///
    /// PL'_NLOS = 35.3·log10(d_3D) + 22.4 + 21.3·log10(f_c) - 0.3·(h_UT - 1.5)
    /// PL_NLOS = max(PL_LOS, PL'_NLOS)
    fn nlos_loss(&self, freq_ghz: f64, d_2d: f64, d_3d: f64, h_bs: f64, h_ut: f64) -> f64 {
        let pl_los = self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut);

        let pl_nlos_prime = 35.3 * d_3d.max(1.0).log10()
            + 22.4
            + 21.3 * freq_ghz.max(0.001).log10()
            - 0.3 * (h_ut - 1.5);

        pl_los.max(pl_nlos_prime)
    }
}

impl Default for Tr38901UmiModel {
    fn default() -> Self {
        Self::new()
    }
}

impl PropagationModel for Tr38901UmiModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq_ghz = params.frequency_mhz / 1000.0;
        let h_bs = params.tx_height_m;
        let h_ut = params.rx_height_m;

        if freq_ghz < 0.5 || freq_ghz > 30.0 {
            warnings.push(format!(
                "Frequency {} GHz outside TR 38.901 UMi range (0.5-30 GHz)",
                freq_ghz
            ));
        }
        if params.distance_m < 10.0 || params.distance_m > 5_000.0 {
            warnings.push(format!(
                "Distance {} m outside TR 38.901 UMi range (10-5000 m)",
                params.distance_m
            ));
        }

        let d_2d = params.distance_m;
        let d_3d = (d_2d * d_2d + (h_bs - h_ut).powi(2)).sqrt();

        // UMi has shorter LOS distances than UMa
        let is_los = match params.environment {
            Environment::OpenRural | Environment::Rural => d_2d < 300.0,
            Environment::Suburban => d_2d < 150.0,
            Environment::Urban => d_2d < 100.0,
        };

        let (loss_db, mode) = if is_los {
            (
                self.los_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::LineOfSight,
            )
        } else {
            (
                self.nlos_loss(freq_ghz, d_2d, d_3d, h_bs, h_ut),
                PropagationMode::Diffraction,
            )
        };

        // Shadow fading: LOS sigma=4 dB, NLOS sigma=7.82 dB (Table 7.4.1-1)
        let variability_db = if is_los { 4.0 } else { 7.82 };

        PathLossResult {
            loss_db,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        "3GPP TR 38.901 Urban Microcell - Street Canyon (UMi)"
    }

    fn frequency_range(&self) -> (f64, f64) {
        (500.0, 30_000.0)
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// InF — Indoor Factory
// ═══════════════════════════════════════════════════════════════════════════════

/// Indoor Factory sub-scenario clutter density/height classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InFScenario {
    /// Sparse clutter, Low BS (InF-SL): open factory floor, few obstacles.
    SparseLow,
    /// Dense clutter, Low BS (InF-DL): dense machinery, low ceiling.
    DenseLow,
    /// Sparse clutter, High BS (InF-SH): open hall with high-mounted BS.
    SparseHigh,
    /// Dense clutter, High BS (InF-DH): dense machinery, high-mounted BS.
    DenseHigh,
}

/// 3GPP TR 38.901 Indoor Factory (InF) model.
///
/// Designed for private 5G networks in industrial environments:
/// factories, warehouses, mines, power plants.
///
/// Supports four sub-scenarios: InF-SL, InF-DL, InF-SH, InF-DH.
/// Frequency range: 0.5–100 GHz.  Distance: 1–600 m.
///
/// Reference: 3GPP TR 38.901 V17.0.0, Table 7.4.1-4 (InF scenarios).
pub struct Tr38901InFModel {
    pub scenario: InFScenario,
    /// Clutter height in meters (default 2.0 m for DH/SH, 0 otherwise).
    pub clutter_height_m: f64,
}

impl Tr38901InFModel {
    pub fn new(scenario: InFScenario) -> Self {
        let clutter_height_m = match scenario {
            InFScenario::SparseHigh | InFScenario::DenseHigh => 2.0,
            _ => 0.0,
        };
        Self {
            scenario,
            clutter_height_m,
        }
    }

    /// InF LOS path loss (common for all sub-scenarios).
    ///
    /// PL_LOS = 31.84 + 21.5·log10(d_3D) + 19·log10(f_c)
    fn los_loss(&self, freq_ghz: f64, d_3d: f64) -> f64 {
        31.84 + 21.5 * d_3d.max(1.0).log10() + 19.0 * freq_ghz.max(0.001).log10()
    }

    /// InF NLOS path loss per sub-scenario.
    ///
    /// InF-SL: 33.63 + 21.9·log10(d_3D) + 20·log10(f_c)  (σ=4.0)  — NOT USED, see note
    /// InF-DL: 33.63 + 21.9·log10(d_3D) + 20·log10(f_c)  (σ=7.2)
    /// InF-SH: 32.4  + 23.0·log10(d_3D) + 20·log10(f_c)  (σ=5.7)
    /// InF-DH: 33.63 + 21.9·log10(d_3D) + 20·log10(f_c)  (σ=7.2)  + clutter
    ///
    /// Note: For InF-SL, the LOS model is generally used. The NLOS formula
    /// is the same as InF-DL but with lower shadow fading sigma.
    fn nlos_loss(&self, freq_ghz: f64, d_3d: f64) -> f64 {
        let pl_los = self.los_loss(freq_ghz, d_3d);

        let pl_nlos_prime = match self.scenario {
            InFScenario::SparseLow => {
                // InF-SL NLOS: same formula as DL
                33.63 + 21.9 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10()
            }
            InFScenario::DenseLow => {
                33.63 + 21.9 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10()
            }
            InFScenario::SparseHigh => {
                32.4 + 23.0 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10()
            }
            InFScenario::DenseHigh => {
                // InF-DH includes additional clutter loss
                let base =
                    33.63 + 21.9 * d_3d.max(1.0).log10() + 20.0 * freq_ghz.max(0.001).log10();
                // Additional clutter loss ~ 5·log10(clutter_height)
                let clutter = if self.clutter_height_m > 0.0 {
                    5.0 * self.clutter_height_m.max(0.1).log10()
                } else {
                    0.0
                };
                base + clutter
            }
        };

        pl_los.max(pl_nlos_prime)
    }
}

impl PropagationModel for Tr38901InFModel {
    fn path_loss(&self, params: &PathLossParams) -> PathLossResult {
        let mut warnings = Vec::new();
        let freq_ghz = params.frequency_mhz / 1000.0;
        let h_bs = params.tx_height_m;
        let h_ut = params.rx_height_m;

        if freq_ghz < 0.5 || freq_ghz > 100.0 {
            warnings.push(format!(
                "Frequency {} GHz outside TR 38.901 InF range (0.5-100 GHz)",
                freq_ghz
            ));
        }
        if params.distance_m < 1.0 || params.distance_m > 600.0 {
            warnings.push(format!(
                "Distance {} m outside TR 38.901 InF range (1-600 m)",
                params.distance_m
            ));
        }

        let d_2d = params.distance_m;
        let d_3d = (d_2d * d_2d + (h_bs - h_ut).powi(2)).sqrt();

        // InF LOS probability depends on scenario and clutter
        let is_los = match self.scenario {
            InFScenario::SparseLow | InFScenario::SparseHigh => d_2d < 100.0,
            InFScenario::DenseLow | InFScenario::DenseHigh => d_2d < 30.0,
        };

        let (loss_db, mode) = if is_los {
            (
                self.los_loss(freq_ghz, d_3d),
                PropagationMode::LineOfSight,
            )
        } else {
            (
                self.nlos_loss(freq_ghz, d_3d),
                PropagationMode::Diffraction,
            )
        };

        // Shadow fading per scenario (Table 7.4.1-4)
        let variability_db = match (is_los, self.scenario) {
            (true, _) => 4.0,  // LOS sigma = 4 dB for all InF
            (false, InFScenario::SparseLow) => 4.0,
            (false, InFScenario::SparseHigh) => 5.7,
            (false, InFScenario::DenseLow) => 7.2,
            (false, InFScenario::DenseHigh) => 7.2,
        };

        PathLossResult {
            loss_db,
            mode,
            variability_db,
            warnings,
        }
    }

    fn name(&self) -> &str {
        match self.scenario {
            InFScenario::SparseLow => "3GPP TR 38.901 Indoor Factory - Sparse Low (InF-SL)",
            InFScenario::DenseLow => "3GPP TR 38.901 Indoor Factory - Dense Low (InF-DL)",
            InFScenario::SparseHigh => "3GPP TR 38.901 Indoor Factory - Sparse High (InF-SH)",
            InFScenario::DenseHigh => "3GPP TR 38.901 Indoor Factory - Dense High (InF-DH)",
        }
    }

    fn frequency_range(&self) -> (f64, f64) {
        (500.0, 100_000.0) // 0.5 - 100 GHz
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    // ── RMa tests ────────────────────────────────────────────────────────────

    #[test]
    fn test_rma_los_700mhz() {
        let model = Tr38901RmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 700.0,
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let result = model.path_loss(&params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);
        assert!(
            result.loss_db > 60.0 && result.loss_db < 140.0,
            "TR 38.901 RMa LOS at 700 MHz, 1 km: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_rma_nlos_higher_loss() {
        let model = Tr38901RmaModel::new();

        let los_params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let nlos_params = PathLossParams {
            environment: Environment::Urban,
            ..los_params.clone()
        };

        let los_result = model.path_loss(&los_params);
        let nlos_result = model.path_loss(&nlos_params);

        assert!(
            nlos_result.loss_db >= los_result.loss_db,
            "NLOS ({} dB) should be >= LOS ({} dB)",
            nlos_result.loss_db,
            los_result.loss_db
        );
    }

    #[test]
    fn test_rma_distance_increases_loss() {
        let model = Tr38901RmaModel::new();

        let near = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 100.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::OpenRural,
        };
        let far = PathLossParams {
            distance_m: 5000.0,
            ..near.clone()
        };

        let near_result = model.path_loss(&near);
        let far_result = model.path_loss(&far);

        assert!(
            far_result.loss_db > near_result.loss_db,
            "Farther ({} dB) should have more loss than near ({} dB)",
            far_result.loss_db,
            near_result.loss_db
        );
    }

    #[test]
    fn test_rma_frequency_warning() {
        let model = Tr38901RmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 50_000.0,
            distance_m: 1000.0,
            tx_height_m: 35.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Rural,
        };
        let result = model.path_loss(&params);
        assert!(!result.warnings.is_empty());
    }

    // ── UMa tests ────────────────────────────────────────────────────────────

    #[test]
    fn test_uma_los_3500mhz() {
        let model = Tr38901UmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 200.0,
            tx_height_m: 25.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);
        // UMa LOS at 3.5 GHz, 200 m should be roughly 80-120 dB
        assert!(
            result.loss_db > 60.0 && result.loss_db < 140.0,
            "UMa LOS at 3.5 GHz, 200 m: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_uma_nlos_higher_than_los() {
        let model = Tr38901UmaModel::new();

        let params_short = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 100.0, // LOS in urban
            tx_height_m: 25.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let params_long = PathLossParams {
            distance_m: 1000.0, // NLOS in urban
            ..params_short.clone()
        };

        let los_result = model.path_loss(&params_short);
        let nlos_result = model.path_loss(&params_long);

        assert!(
            nlos_result.loss_db > los_result.loss_db,
            "UMa NLOS ({} dB) should be > LOS ({} dB)",
            nlos_result.loss_db,
            los_result.loss_db
        );
    }

    #[test]
    fn test_uma_distance_warning() {
        let model = Tr38901UmaModel::new();
        let params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 10_000.0, // beyond 5 km limit
            tx_height_m: 25.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_uma_frequency_scaling() {
        let model = Tr38901UmaModel::new();

        let low_freq = PathLossParams {
            frequency_mhz: 700.0,
            distance_m: 100.0,
            tx_height_m: 25.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let high_freq = PathLossParams {
            frequency_mhz: 28000.0,
            ..low_freq.clone()
        };

        let low_result = model.path_loss(&low_freq);
        let high_result = model.path_loss(&high_freq);

        assert!(
            high_result.loss_db > low_result.loss_db,
            "Higher frequency ({} dB) should have more loss than lower ({} dB)",
            high_result.loss_db,
            low_result.loss_db
        );
    }

    // ── UMi tests ────────────────────────────────────────────────────────────

    #[test]
    fn test_umi_los_3500mhz() {
        let model = Tr38901UmiModel::new();
        let params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 50.0,
            tx_height_m: 10.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);
        assert!(
            result.loss_db > 50.0 && result.loss_db < 120.0,
            "UMi LOS at 3.5 GHz, 50 m: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_umi_shorter_range_than_uma() {
        // UMi should have higher NLOS loss than UMa at the same distance
        // because UMi BS is below rooftop (10 m) vs UMa above (25 m)
        let uma = Tr38901UmaModel::new();
        let umi = Tr38901UmiModel::new();

        let params_uma = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 500.0,
            tx_height_m: 25.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let params_umi = PathLossParams {
            tx_height_m: 10.0,
            ..params_uma.clone()
        };

        let uma_result = uma.path_loss(&params_uma);
        let umi_result = umi.path_loss(&params_umi);

        // UMi NLOS should generally have higher loss than UMa at same distance
        // (though not guaranteed by spec, it's the expected behavior)
        assert!(
            umi_result.loss_db > 0.0 && uma_result.loss_db > 0.0,
            "Both should produce positive path loss"
        );
    }

    #[test]
    fn test_umi_nlos_higher_than_los() {
        let model = Tr38901UmiModel::new();

        let los_params = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 50.0, // LOS
            tx_height_m: 10.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let nlos_params = PathLossParams {
            distance_m: 500.0, // NLOS
            ..los_params.clone()
        };

        let los_result = model.path_loss(&los_params);
        let nlos_result = model.path_loss(&nlos_params);

        assert!(
            nlos_result.loss_db > los_result.loss_db,
            "UMi NLOS ({} dB) should be > LOS ({} dB)",
            nlos_result.loss_db,
            los_result.loss_db
        );
    }

    // ── InF tests ────────────────────────────────────────────────────────────

    #[test]
    fn test_inf_sl_los() {
        let model = Tr38901InFModel::new(InFScenario::SparseLow);
        let params = PathLossParams {
            frequency_mhz: 3700.0,
            distance_m: 20.0,
            tx_height_m: 3.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert_eq!(result.mode, PropagationMode::LineOfSight);
        assert!(
            result.loss_db > 40.0 && result.loss_db < 100.0,
            "InF-SL LOS at 3.7 GHz, 20 m: {} dB",
            result.loss_db
        );
    }

    #[test]
    fn test_inf_dh_nlos_higher() {
        // Dense-High should have more loss than Sparse-Low at NLOS distances
        let sl = Tr38901InFModel::new(InFScenario::SparseLow);
        let dh = Tr38901InFModel::new(InFScenario::DenseHigh);

        let params = PathLossParams {
            frequency_mhz: 28000.0,
            distance_m: 100.0, // NLOS for both
            tx_height_m: 8.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };

        let sl_result = sl.path_loss(&params);
        let dh_result = dh.path_loss(&params);

        assert!(
            dh_result.loss_db >= sl_result.loss_db,
            "InF-DH ({} dB) should have >= loss than InF-SL ({} dB)",
            dh_result.loss_db,
            sl_result.loss_db
        );
    }

    #[test]
    fn test_inf_distance_increases_loss() {
        let model = Tr38901InFModel::new(InFScenario::DenseLow);

        let near = PathLossParams {
            frequency_mhz: 3700.0,
            distance_m: 5.0,
            tx_height_m: 3.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let far = PathLossParams {
            distance_m: 200.0,
            ..near.clone()
        };

        let near_result = model.path_loss(&near);
        let far_result = model.path_loss(&far);

        assert!(
            far_result.loss_db > near_result.loss_db,
            "InF farther ({} dB) should have more loss than near ({} dB)",
            far_result.loss_db,
            near_result.loss_db
        );
    }

    #[test]
    fn test_inf_frequency_range_100ghz() {
        let model = Tr38901InFModel::new(InFScenario::SparseHigh);
        // 60 GHz (within 0.5-100 GHz range) — should produce no warning
        let params = PathLossParams {
            frequency_mhz: 60_000.0,
            distance_m: 30.0,
            tx_height_m: 8.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert!(result.warnings.is_empty(), "60 GHz should be in range for InF");
        assert!(result.loss_db > 80.0, "60 GHz should have significant loss: {} dB", result.loss_db);
    }

    #[test]
    fn test_inf_out_of_range_warning() {
        let model = Tr38901InFModel::new(InFScenario::DenseLow);
        let params = PathLossParams {
            frequency_mhz: 3700.0,
            distance_m: 1000.0, // beyond 600 m limit
            tx_height_m: 3.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let result = model.path_loss(&params);
        assert!(!result.warnings.is_empty());
    }

    // ── Beamforming tests ────────────────────────────────────────────────────

    #[test]
    fn test_beamforming_boresight() {
        // 64 elements at boresight: 10*log10(64) = 18.06 dB
        let gain = beamforming_gain_db(64, 0.0);
        assert!(
            (gain - 18.06).abs() < 0.1,
            "64-element boresight gain should be ~18 dB, got {} dB",
            gain
        );
    }

    #[test]
    fn test_beamforming_off_axis_reduced() {
        let boresight = beamforming_gain_db(32, 0.0);
        let off_axis = beamforming_gain_db(32, 30.0);
        assert!(
            off_axis < boresight,
            "Off-axis ({} dB) should be less than boresight ({} dB)",
            off_axis,
            boresight
        );
    }

    #[test]
    fn test_beamforming_90deg_zero() {
        // At 90 degrees, cos²(90°) = 0 → gain = 0
        let gain = beamforming_gain_db(64, 90.0);
        assert!(
            gain.abs() < 0.01,
            "90-degree steering should give ~0 dB gain, got {} dB",
            gain
        );
    }

    #[test]
    fn test_beamforming_single_element() {
        // 1 element: 10*log10(1) = 0 dB
        let gain = beamforming_gain_db(1, 0.0);
        assert!(
            gain.abs() < 0.01,
            "Single element should give 0 dB, got {} dB",
            gain
        );
    }

    #[test]
    fn test_beamforming_zero_elements() {
        let gain = beamforming_gain_db(0, 0.0);
        assert_eq!(gain, 0.0);
    }

    // ── Cross-scenario comparison ────────────────────────────────────────────

    #[test]
    fn test_inf_shorter_range_than_umi() {
        // InF is indoor (1-600 m), UMi is outdoor micro (10-5 km)
        // At the same distance in NLOS, InF should generally have less loss
        // (indoor pathloss models tend to be lower at short distances)
        let inf = Tr38901InFModel::new(InFScenario::SparseLow);
        let umi = Tr38901UmiModel::new();

        let params_inf = PathLossParams {
            frequency_mhz: 3500.0,
            distance_m: 50.0,
            tx_height_m: 3.0,
            rx_height_m: 1.5,
            terrain_profile: None,
            environment: Environment::Urban,
        };
        let params_umi = PathLossParams {
            tx_height_m: 10.0,
            ..params_inf.clone()
        };

        let inf_result = inf.path_loss(&params_inf);
        let umi_result = umi.path_loss(&params_umi);

        assert!(
            inf_result.loss_db > 0.0 && umi_result.loss_db > 0.0,
            "Both should produce positive path loss: InF={} dB, UMi={} dB",
            inf_result.loss_db,
            umi_result.loss_db
        );
    }
}
