//! gRPC service handler implementations for the ENLACE RF Engine.
//!
//! Each handler maps a protobuf request to the appropriate crate function,
//! converts the result back to a protobuf response, and handles errors
//! gracefully via `tonic::Status`.

use std::sync::Mutex;

use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;
use tonic::{Request, Response, Status};
use tracing::{info, warn};

use enlace_propagation::common::{haversine_distance, Polarization};
use enlace_propagation::coverage::{
    compute_coverage as prop_compute_coverage, CoverageArea, TowerConfig,
};
use enlace_propagation::models::fspl::FsplModel;
use enlace_propagation::models::hata::{CitySize, HataModel};
use enlace_propagation::models::itm::{itm_path_loss, ItmParams};
use enlace_propagation::models::p1812::P1812Model;
use enlace_propagation::models::p530::{compute_link_budget, LinkBudgetParams};
use enlace_propagation::models::tr38901::Tr38901RmaModel;
use enlace_propagation::models::{Environment, PathLossParams, PathLossResult, PropagationModel};
use enlace_propagation::vegetation::VegetationCorrector;
use enlace_propagation::AntennaPattern;

use enlace_optimizer::output::{optimize_tower_placement, OptimizationParams};

use enlace_terrain::cache::TileCache;
use enlace_terrain::profile::{extract_profile, GeoPoint, DEFAULT_K_FACTOR};

use crate::config::ServiceConfig;
use crate::proto;
use crate::proto::rf_engine_server::RfEngine;

/// The gRPC service implementation wrapping all ENLACE RF engine functionality.
pub struct RfEngineService {
    #[allow(dead_code)]
    config: ServiceConfig,
    /// Shared tile cache protected by a mutex (used for terrain queries).
    tile_cache: Mutex<TileCache>,
}

impl RfEngineService {
    /// Create a new RF Engine service with the given configuration.
    pub fn new(config: ServiceConfig) -> Self {
        let tile_cache = TileCache::new(&config.srtm_tile_dir, config.tile_cache_size);
        Self {
            config,
            tile_cache: Mutex::new(tile_cache),
        }
    }
}

#[tonic::async_trait]
impl RfEngine for RfEngineService {
    /// Calculate point-to-point path loss using the specified propagation model.
    async fn calculate_path_loss(
        &self,
        request: Request<proto::PathLossRequest>,
    ) -> Result<Response<proto::PathLossResponse>, Status> {
        let req = request.into_inner();
        info!(
            model = %req.model,
            freq_mhz = req.frequency_mhz,
            "CalculatePathLoss request"
        );

        // Compute distance between TX and RX
        let distance_m = haversine_distance(req.tx_lat, req.tx_lon, req.rx_lat, req.rx_lon);

        if distance_m < 0.1 {
            return Err(Status::invalid_argument(
                "TX and RX positions are too close (< 0.1 m)",
            ));
        }

        let params = PathLossParams {
            frequency_mhz: req.frequency_mhz,
            distance_m,
            tx_height_m: req.tx_height_m,
            rx_height_m: req.rx_height_m,
            terrain_profile: None,
            environment: Environment::Rural,
        };

        // Dispatch to the appropriate propagation model
        let result = match req.model.to_lowercase().as_str() {
            "fspl" | "" => {
                let model = FsplModel::new();
                model.path_loss(&params)
            }
            "hata" => {
                let model = HataModel::new(CitySize::SmallMedium);
                model.path_loss(&params)
            }
            "itm" => {
                // ITM uses its own parameter struct and a flat terrain profile
                // when no real profile is available
                let num_steps = (distance_m / 30.0).ceil() as usize;
                let profile: Vec<(f64, f64)> = (0..=num_steps)
                    .map(|i| (i as f64 * 30.0, 0.0))
                    .collect();
                let itm_params = ItmParams {
                    frequency_mhz: req.frequency_mhz,
                    tx_height_m: req.tx_height_m,
                    rx_height_m: req.rx_height_m,
                    ..ItmParams::default()
                };
                let itm_result = itm_path_loss(&profile, &itm_params);
                PathLossResult {
                    loss_db: itm_result.path_loss_db,
                    mode: itm_result.mode,
                    variability_db: itm_result.variability_db,
                    warnings: itm_result.warnings,
                }
            }
            "tr38901" => {
                let model = Tr38901RmaModel::new();
                model.path_loss(&params)
            }
            "p1812" => {
                let model = P1812Model::new(0.5, 0.5);
                model.path_loss(&params)
            }
            other => {
                return Err(Status::invalid_argument(format!(
                    "Unknown propagation model: '{}'. Supported: fspl, hata, itm, tr38901, p1812",
                    other
                )));
            }
        };

        // Optional vegetation correction
        let vegetation_correction_db = if req.apply_vegetation {
            let corrector = VegetationCorrector::with_defaults();
            // Simple estimation: assume 50m average vegetation depth for Brazil
            let biome = if req.country_code == "BR" || req.country_code.is_empty() {
                "cerrado" // Default biome for Brazil
            } else {
                ""
            };
            corrector.correction_for_segment(biome, req.frequency_mhz, 50.0)
        } else {
            0.0
        };

        let total_loss = result.loss_db + vegetation_correction_db;

        // Received power assuming 0 dBm TX (path loss only)
        let received_power_dbm = -total_loss;

        let mode_str = format!("{:?}", result.mode);

        let response = proto::PathLossResponse {
            path_loss_db: total_loss,
            received_power_dbm,
            propagation_mode: mode_str,
            variability_db: result.variability_db,
            vegetation_correction_db,
            warnings: result.warnings,
        };

        Ok(Response::new(response))
    }

    /// Compute coverage footprint for a tower position.
    async fn compute_coverage(
        &self,
        request: Request<proto::CoverageRequest>,
    ) -> Result<Response<proto::CoverageResponse>, Status> {
        let req = request.into_inner();
        info!(
            lat = req.tower_lat,
            lon = req.tower_lon,
            radius_m = req.radius_m,
            "ComputeCoverage request"
        );

        let tower = TowerConfig {
            latitude: req.tower_lat,
            longitude: req.tower_lon,
            antenna_height_m: req.tower_height_m,
            frequency_mhz: req.frequency_mhz,
            tx_power_dbm: req.tx_power_dbm,
            antenna_gain_dbi: req.antenna_gain_dbi,
            antenna_pattern: AntennaPattern::Omnidirectional,
        };

        let area = CoverageArea {
            center_lat: req.tower_lat,
            center_lon: req.tower_lon,
            radius_m: req.radius_m,
        };

        let grid_res = if req.grid_resolution_m > 0.0 {
            req.grid_resolution_m
        } else {
            30.0
        };

        let min_signal = if req.min_signal_dbm != 0.0 {
            req.min_signal_dbm
        } else {
            -95.0
        };

        let cov_result = prop_compute_coverage(&tower, &area, grid_res, min_signal);

        // Convert coverage points to proto
        let proto_points: Vec<proto::CoveragePoint> = cov_result
            .points
            .iter()
            .map(|p| proto::CoveragePoint {
                latitude: p.latitude,
                longitude: p.longitude,
                signal_strength_dbm: p.signal_strength_dbm,
                path_loss_db: p.path_loss_db,
            })
            .collect();

        let proto_stats = proto::CoverageStats {
            total_points: cov_result.stats.total_points as u64,
            covered_points: cov_result.stats.covered_points as u64,
            coverage_pct: cov_result.stats.coverage_pct,
            area_km2: cov_result.stats.area_km2,
            covered_area_km2: cov_result.stats.covered_area_km2,
            avg_signal_dbm: cov_result.stats.avg_signal_dbm,
            min_signal_dbm: cov_result.stats.min_signal_dbm,
            max_signal_dbm: cov_result.stats.max_signal_dbm,
        };

        let response = proto::CoverageResponse {
            points: proto_points,
            stats: Some(proto_stats),
        };

        Ok(Response::new(response))
    }

    /// Server-streaming RPC for tower placement optimization.
    /// Sends progress updates followed by a final result.
    type OptimizeTowersStream = ReceiverStream<Result<proto::OptimizeProgress, Status>>;

    async fn optimize_towers(
        &self,
        request: Request<proto::OptimizeRequest>,
    ) -> Result<Response<Self::OptimizeTowersStream>, Status> {
        let req = request.into_inner();
        info!(
            center_lat = req.center_lat,
            center_lon = req.center_lon,
            radius_m = req.radius_m,
            max_towers = req.max_towers,
            "OptimizeTowers request"
        );

        let (tx, rx) = mpsc::channel(32);

        // Build optimization params from request
        let params = OptimizationParams {
            coverage_target_pct: if req.coverage_target_pct > 0.0 {
                req.coverage_target_pct
            } else {
                95.0
            },
            min_signal_dbm: if req.min_signal_dbm != 0.0 {
                req.min_signal_dbm
            } else {
                -95.0
            },
            max_towers: if req.max_towers > 0 {
                req.max_towers as usize
            } else {
                20
            },
            frequency_mhz: if req.frequency_mhz > 0.0 {
                req.frequency_mhz
            } else {
                700.0
            },
            tx_power_dbm: if req.tx_power_dbm != 0.0 {
                req.tx_power_dbm
            } else {
                43.0
            },
            antenna_gain_dbi: if req.antenna_gain_dbi != 0.0 {
                req.antenna_gain_dbi
            } else {
                15.0
            },
            antenna_height_m: if req.antenna_height_m > 0.0 {
                req.antenna_height_m
            } else {
                30.0
            },
            candidate_spacing_m: 500.0,
            annealing_iterations: 5_000,
            annealing_initial_temp: 100.0,
            annealing_cooling_rate: 0.995,
        };

        let center_lat = req.center_lat;
        let center_lon = req.center_lon;
        let radius_m = req.radius_m;

        // Spawn the optimization in a blocking task
        tokio::spawn(async move {
            // Phase 1: Candidates
            let _ = tx
                .send(Ok(proto::OptimizeProgress {
                    is_final: false,
                    progress_pct: 10.0,
                    phase: "candidates".into(),
                    towers: Vec::new(),
                    total_coverage_pct: 0.0,
                    covered_area_km2: 0.0,
                    estimated_capex_brl: 0.0,
                    computation_time_secs: 0.0,
                }))
                .await;

            // Phase 2: Set cover
            let _ = tx
                .send(Ok(proto::OptimizeProgress {
                    is_final: false,
                    progress_pct: 30.0,
                    phase: "setcover".into(),
                    towers: Vec::new(),
                    total_coverage_pct: 0.0,
                    covered_area_km2: 0.0,
                    estimated_capex_brl: 0.0,
                    computation_time_secs: 0.0,
                }))
                .await;

            // Phase 3: Annealing
            let _ = tx
                .send(Ok(proto::OptimizeProgress {
                    is_final: false,
                    progress_pct: 60.0,
                    phase: "annealing".into(),
                    towers: Vec::new(),
                    total_coverage_pct: 0.0,
                    covered_area_km2: 0.0,
                    estimated_capex_brl: 0.0,
                    computation_time_secs: 0.0,
                }))
                .await;

            // Run the actual optimization (blocking)
            let result = tokio::task::spawn_blocking(move || {
                optimize_tower_placement(center_lat, center_lon, radius_m, &params)
            })
            .await;

            match result {
                Ok(opt_result) => {
                    // Convert towers to proto
                    let proto_towers: Vec<proto::TowerPlacement> = opt_result
                        .towers
                        .iter()
                        .map(|t| proto::TowerPlacement {
                            id: t.id as u32,
                            latitude: t.latitude,
                            longitude: t.longitude,
                            elevation_m: t.elevation_m,
                            antenna_height_m: t.antenna_height_m,
                            coverage_area_km2: t.coverage_area_km2,
                        })
                        .collect();

                    // Phase 4: Complete
                    let _ = tx
                        .send(Ok(proto::OptimizeProgress {
                            is_final: true,
                            progress_pct: 100.0,
                            phase: "complete".into(),
                            towers: proto_towers,
                            total_coverage_pct: opt_result.total_coverage_pct,
                            covered_area_km2: opt_result.covered_area_km2,
                            estimated_capex_brl: opt_result.estimated_capex_brl,
                            computation_time_secs: opt_result.computation_time_secs,
                        }))
                        .await;
                }
                Err(e) => {
                    warn!("Optimization task failed: {:?}", e);
                    let _ = tx
                        .send(Err(Status::internal(format!(
                            "Optimization failed: {}",
                            e
                        ))))
                        .await;
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    /// Calculate microwave link budget using ITU-R P.530 model.
    async fn link_budget(
        &self,
        request: Request<proto::LinkBudgetRequest>,
    ) -> Result<Response<proto::LinkBudgetResponse>, Status> {
        let req = request.into_inner();
        info!(
            freq_ghz = req.frequency_ghz,
            distance_km = req.distance_km,
            "LinkBudget request"
        );

        if req.frequency_ghz <= 0.0 {
            return Err(Status::invalid_argument("frequency_ghz must be positive"));
        }
        if req.distance_km <= 0.0 {
            return Err(Status::invalid_argument("distance_km must be positive"));
        }

        let params = LinkBudgetParams {
            frequency_ghz: req.frequency_ghz,
            distance_km: req.distance_km,
            tx_power_dbm: req.tx_power_dbm,
            tx_antenna_gain_dbi: req.tx_antenna_gain_dbi,
            rx_antenna_gain_dbi: req.rx_antenna_gain_dbi,
            rx_threshold_dbm: if req.rx_threshold_dbm != 0.0 {
                req.rx_threshold_dbm
            } else {
                -70.0
            },
            polarization: Polarization::Vertical,
            rain_rate_mmh: if req.rain_rate_mmh > 0.0 {
                req.rain_rate_mmh
            } else {
                145.0 // Brazilian tropical default
            },
        };

        let result = compute_link_budget(&params);

        let response = proto::LinkBudgetResponse {
            free_space_loss_db: result.free_space_loss_db,
            atmospheric_absorption_db: result.atmospheric_absorption_db,
            rain_attenuation_db: result.rain_attenuation_db,
            total_path_loss_db: result.total_path_loss_db,
            received_power_dbm: result.received_power_dbm,
            fade_margin_db: result.fade_margin_db,
            availability_pct: result.availability_pct,
        };

        Ok(Response::new(response))
    }

    /// Extract terrain elevation profile between two geographic points.
    async fn terrain_profile(
        &self,
        request: Request<proto::ProfileRequest>,
    ) -> Result<Response<proto::ProfileResponse>, Status> {
        let req = request.into_inner();
        info!(
            start_lat = req.start_lat,
            start_lon = req.start_lon,
            end_lat = req.end_lat,
            end_lon = req.end_lon,
            "TerrainProfile request"
        );

        let step_m = if req.step_m > 0.0 { req.step_m } else { 30.0 };
        let k_factor = if req.k_factor > 0.0 {
            req.k_factor
        } else {
            DEFAULT_K_FACTOR
        };

        let start = GeoPoint::new(req.start_lat, req.start_lon);
        let end = GeoPoint::new(req.end_lat, req.end_lon);

        // Lock the tile cache for the profile extraction
        let profile = {
            let mut cache = self.tile_cache.lock().map_err(|e| {
                Status::internal(format!("Failed to acquire tile cache lock: {}", e))
            })?;
            extract_profile(&mut cache, start, end, step_m, k_factor)
        };

        let proto_points: Vec<proto::ProfilePoint> = profile
            .points
            .iter()
            .map(|p| proto::ProfilePoint {
                distance_m: p.distance_m,
                elevation_m: p.elevation_m,
                latitude: p.latitude,
                longitude: p.longitude,
            })
            .collect();

        let response = proto::ProfileResponse {
            points: proto_points,
            total_distance_m: profile.distance_m,
            max_elevation_m: profile.max_elevation_m,
            min_elevation_m: profile.min_elevation_m,
            num_obstructions: profile.num_obstructions as u32,
        };

        Ok(Response::new(response))
    }

    /// Health check returning service status and version info.
    async fn health(
        &self,
        _request: Request<proto::HealthRequest>,
    ) -> Result<Response<proto::HealthResponse>, Status> {
        let tiles_cached = {
            let cache = self.tile_cache.lock().map_err(|e| {
                Status::internal(format!("Failed to acquire tile cache lock: {}", e))
            })?;
            cache.stats().tiles_cached as u64
        };

        let response = proto::HealthResponse {
            status: "healthy".into(),
            version: env!("CARGO_PKG_VERSION").into(),
            srtm_tiles_cached: tiles_cached,
        };

        Ok(Response::new(response))
    }
}
