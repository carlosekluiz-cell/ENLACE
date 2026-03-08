"""
gRPC client for the ENLACE Rust RF Engine.

Provides a Python interface to the RF propagation, coverage computation,
tower optimization, link budget, and terrain profile services exposed by
the Rust enlace-service crate via gRPC.

If the gRPC server is not available or the generated protobuf stubs
are not present, the client gracefully degrades by returning estimated
mock responses suitable for development and testing.
"""

import logging
import math
import os
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# gRPC server address (matches Rust default)
RF_ENGINE_ADDR = os.getenv("RF_ENGINE_ADDR", "localhost:50051")

# Try to import gRPC and generated stubs
_grpc_available = False
_stubs_available = False

try:
    import grpc

    _grpc_available = True
except ImportError:
    logger.warning("grpcio not installed — RF Engine client will use mock responses")

# Generated protobuf stubs would be imported here once available:
# try:
#     from enlace.rf import rf_service_pb2, rf_service_pb2_grpc
#     _stubs_available = True
# except ImportError:
#     logger.info("Proto stubs not generated — using mock mode")


class RfEngineClient:
    """Client for the ENLACE RF Engine gRPC service.

    Supports two modes:
    - **Live mode**: connects to the Rust gRPC server when available
    - **Mock mode**: returns estimated responses for development/testing

    The client auto-detects which mode to use based on whether the gRPC
    library is installed and the server is reachable.
    """

    def __init__(self, address: str = None):
        self.address = address or RF_ENGINE_ADDR
        self._channel = None
        self._stub = None
        self._connected = False

    def connect(self) -> bool:
        """Establish gRPC channel to the RF Engine server.

        Returns True if connection was established, False otherwise.
        """
        if not _grpc_available:
            logger.warning("grpcio not available, using mock mode")
            return False

        try:
            self._channel = grpc.insecure_channel(self.address)
            # Try a quick health check to verify connectivity
            try:
                grpc.channel_ready_future(self._channel).result(timeout=2)
                self._connected = True
                logger.info(f"Connected to RF Engine at {self.address}")
            except grpc.FutureTimeoutError:
                logger.warning(
                    f"RF Engine at {self.address} not reachable, using mock mode"
                )
                self._connected = False
        except Exception as e:
            logger.warning(f"Failed to connect to RF Engine: {e}")
            self._connected = False

        return self._connected

    def close(self):
        """Close the gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
            self._connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def health_check(self) -> dict:
        """Check RF engine health.

        Returns:
            Dict with status, version, and tiles_cached fields.
        """
        if self._connected and _stubs_available:
            try:
                response = self._stub.Health(rf_service_pb2.HealthRequest())
                return {
                    "status": response.status,
                    "version": response.version,
                    "srtm_tiles_cached": response.srtm_tiles_cached,
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")

        return {
            "status": "mock",
            "version": "0.1.0-mock",
            "srtm_tiles_cached": 0,
            "_warning": "Using mock response — RF Engine not connected",
        }

    def calculate_path_loss(
        self,
        tx_lat: float,
        tx_lon: float,
        tx_height_m: float,
        rx_lat: float,
        rx_lon: float,
        rx_height_m: float,
        frequency_mhz: float,
        model: str = "fspl",
        apply_vegetation: bool = True,
        country_code: str = "BR",
    ) -> dict:
        """Calculate path loss between two points.

        Args:
            tx_lat: Transmitter latitude (decimal degrees).
            tx_lon: Transmitter longitude (decimal degrees).
            tx_height_m: Transmitter antenna height above ground (meters).
            rx_lat: Receiver latitude (decimal degrees).
            rx_lon: Receiver longitude (decimal degrees).
            rx_height_m: Receiver antenna height above ground (meters).
            frequency_mhz: Carrier frequency in MHz.
            model: Propagation model name (fspl, hata, itm, tr38901, p1812).
            apply_vegetation: Whether to apply vegetation attenuation.
            country_code: ISO country code (default BR for Brazil).

        Returns:
            Dict with path_loss_db, received_power_dbm, propagation_mode,
            variability_db, vegetation_correction_db, and warnings.
        """
        if self._connected and _stubs_available:
            try:
                request = rf_service_pb2.PathLossRequest(
                    tx_lat=tx_lat,
                    tx_lon=tx_lon,
                    tx_height_m=tx_height_m,
                    rx_lat=rx_lat,
                    rx_lon=rx_lon,
                    rx_height_m=rx_height_m,
                    frequency_mhz=frequency_mhz,
                    model=model,
                    apply_vegetation=apply_vegetation,
                    country_code=country_code,
                )
                response = self._stub.CalculatePathLoss(request)
                return {
                    "path_loss_db": response.path_loss_db,
                    "received_power_dbm": response.received_power_dbm,
                    "propagation_mode": response.propagation_mode,
                    "variability_db": response.variability_db,
                    "vegetation_correction_db": response.vegetation_correction_db,
                    "warnings": list(response.warnings),
                }
            except Exception as e:
                logger.error(f"CalculatePathLoss RPC failed: {e}")

        # Mock: compute FSPL
        distance_m = _haversine_distance(tx_lat, tx_lon, rx_lat, rx_lon)
        fspl_db = _mock_fspl(frequency_mhz, distance_m)
        veg_db = 2.5 if apply_vegetation else 0.0
        total_loss = fspl_db + veg_db

        return {
            "path_loss_db": round(total_loss, 2),
            "received_power_dbm": round(-total_loss, 2),
            "propagation_mode": "LineOfSight",
            "variability_db": 0.0,
            "vegetation_correction_db": round(veg_db, 2),
            "warnings": ["Mock response — RF Engine not connected"],
            "_mock": True,
        }

    def compute_coverage(
        self,
        tower_lat: float,
        tower_lon: float,
        tower_height_m: float,
        frequency_mhz: float,
        tx_power_dbm: float,
        antenna_gain_dbi: float,
        radius_m: float = 10000,
        grid_resolution_m: float = 30,
        min_signal_dbm: float = -95,
        apply_vegetation: bool = True,
        country_code: str = "BR",
    ) -> dict:
        """Compute coverage footprint for a tower.

        Args:
            tower_lat: Tower latitude (decimal degrees).
            tower_lon: Tower longitude (decimal degrees).
            tower_height_m: Antenna height above ground (meters).
            frequency_mhz: Carrier frequency in MHz.
            tx_power_dbm: Transmit power in dBm.
            antenna_gain_dbi: Antenna gain in dBi.
            radius_m: Coverage radius in meters (default 10000).
            grid_resolution_m: Grid spacing in meters (default 30).
            min_signal_dbm: Minimum signal threshold in dBm (default -95).
            apply_vegetation: Whether to apply vegetation correction.
            country_code: ISO country code.

        Returns:
            Dict with points (list of coverage points) and stats (summary).
        """
        if self._connected and _stubs_available:
            try:
                request = rf_service_pb2.CoverageRequest(
                    tower_lat=tower_lat,
                    tower_lon=tower_lon,
                    tower_height_m=tower_height_m,
                    frequency_mhz=frequency_mhz,
                    tx_power_dbm=tx_power_dbm,
                    antenna_gain_dbi=antenna_gain_dbi,
                    radius_m=radius_m,
                    grid_resolution_m=grid_resolution_m,
                    min_signal_dbm=min_signal_dbm,
                    apply_vegetation=apply_vegetation,
                    country_code=country_code,
                )
                response = self._stub.ComputeCoverage(request)
                points = [
                    {
                        "latitude": p.latitude,
                        "longitude": p.longitude,
                        "signal_strength_dbm": p.signal_strength_dbm,
                        "path_loss_db": p.path_loss_db,
                    }
                    for p in response.points
                ]
                stats = {
                    "total_points": response.stats.total_points,
                    "covered_points": response.stats.covered_points,
                    "coverage_pct": response.stats.coverage_pct,
                    "area_km2": response.stats.area_km2,
                    "covered_area_km2": response.stats.covered_area_km2,
                    "avg_signal_dbm": response.stats.avg_signal_dbm,
                    "min_signal_dbm": response.stats.min_signal_dbm,
                    "max_signal_dbm": response.stats.max_signal_dbm,
                }
                return {"points": points, "stats": stats}
            except Exception as e:
                logger.error(f"ComputeCoverage RPC failed: {e}")

        # Mock coverage response
        eirp = tx_power_dbm + antenna_gain_dbi
        area_km2 = math.pi * (radius_m / 1000) ** 2
        mock_loss_at_edge = _mock_fspl(frequency_mhz, radius_m)
        edge_signal = eirp - mock_loss_at_edge
        covered = edge_signal >= min_signal_dbm

        return {
            "points": [],
            "stats": {
                "total_points": 0,
                "covered_points": 0,
                "coverage_pct": 85.0 if covered else 40.0,
                "area_km2": round(area_km2, 2),
                "covered_area_km2": round(area_km2 * (0.85 if covered else 0.40), 2),
                "avg_signal_dbm": round(eirp - mock_loss_at_edge * 0.6, 1),
                "min_signal_dbm": round(edge_signal, 1),
                "max_signal_dbm": round(eirp - 30, 1),
            },
            "_mock": True,
            "_warning": "Mock response — RF Engine not connected",
        }

    def optimize_towers(
        self,
        center_lat: float,
        center_lon: float,
        radius_m: float,
        coverage_target_pct: float = 95,
        min_signal_dbm: float = -95,
        max_towers: int = 20,
        frequency_mhz: float = 700,
        tx_power_dbm: float = 43,
        antenna_gain_dbi: float = 15,
        antenna_height_m: float = 30,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """Run tower placement optimization (streaming).

        Args:
            center_lat: Center latitude of the coverage area.
            center_lon: Center longitude of the coverage area.
            radius_m: Radius of the coverage area in meters.
            coverage_target_pct: Target coverage percentage (default 95).
            min_signal_dbm: Minimum signal threshold in dBm.
            max_towers: Maximum number of towers to place.
            frequency_mhz: Carrier frequency in MHz.
            tx_power_dbm: Transmit power in dBm.
            antenna_gain_dbi: Antenna gain in dBi.
            antenna_height_m: Antenna height above ground in meters.
            progress_callback: Optional callback invoked with progress dicts.

        Returns:
            Dict with towers (list), total_coverage_pct, covered_area_km2,
            estimated_capex_brl, and computation_time_secs.
        """
        if self._connected and _stubs_available:
            try:
                request = rf_service_pb2.OptimizeRequest(
                    center_lat=center_lat,
                    center_lon=center_lon,
                    radius_m=radius_m,
                    coverage_target_pct=coverage_target_pct,
                    min_signal_dbm=min_signal_dbm,
                    max_towers=max_towers,
                    frequency_mhz=frequency_mhz,
                    tx_power_dbm=tx_power_dbm,
                    antenna_gain_dbi=antenna_gain_dbi,
                    antenna_height_m=antenna_height_m,
                )
                final_result = None
                for progress in self._stub.OptimizeTowers(request):
                    progress_dict = {
                        "is_final": progress.is_final,
                        "progress_pct": progress.progress_pct,
                        "phase": progress.phase,
                    }
                    if progress_callback:
                        progress_callback(progress_dict)
                    if progress.is_final:
                        final_result = {
                            "towers": [
                                {
                                    "id": t.id,
                                    "latitude": t.latitude,
                                    "longitude": t.longitude,
                                    "elevation_m": t.elevation_m,
                                    "antenna_height_m": t.antenna_height_m,
                                    "coverage_area_km2": t.coverage_area_km2,
                                }
                                for t in progress.towers
                            ],
                            "total_coverage_pct": progress.total_coverage_pct,
                            "covered_area_km2": progress.covered_area_km2,
                            "estimated_capex_brl": progress.estimated_capex_brl,
                            "computation_time_secs": progress.computation_time_secs,
                        }
                if final_result:
                    return final_result
            except Exception as e:
                logger.error(f"OptimizeTowers RPC failed: {e}")

        # Mock optimization response
        area_km2 = math.pi * (radius_m / 1000) ** 2
        num_towers = min(max_towers, max(1, int(area_km2 / 25)))
        per_tower_area = area_km2 / num_towers

        towers = []
        for i in range(num_towers):
            angle = 2 * math.pi * i / num_towers
            offset_lat = (radius_m * 0.5 * math.cos(angle)) / 111320.0
            offset_lon = (radius_m * 0.5 * math.sin(angle)) / (
                111320.0 * math.cos(math.radians(center_lat))
            )
            towers.append(
                {
                    "id": i,
                    "latitude": round(center_lat + offset_lat, 6),
                    "longitude": round(center_lon + offset_lon, 6),
                    "elevation_m": 800.0,
                    "antenna_height_m": antenna_height_m,
                    "coverage_area_km2": round(per_tower_area, 2),
                }
            )

        return {
            "towers": towers,
            "total_coverage_pct": min(coverage_target_pct, 92.0),
            "covered_area_km2": round(area_km2 * 0.92, 2),
            "estimated_capex_brl": num_towers * 300000,
            "computation_time_secs": 0.01,
            "_mock": True,
            "_warning": "Mock response — RF Engine not connected",
        }

    def link_budget(
        self,
        frequency_ghz: float,
        distance_km: float,
        tx_power_dbm: float,
        tx_antenna_gain_dbi: float,
        rx_antenna_gain_dbi: float,
        rx_threshold_dbm: float = -70,
        rain_rate_mmh: float = 145,
    ) -> dict:
        """Calculate microwave link budget.

        Args:
            frequency_ghz: Carrier frequency in GHz.
            distance_km: Path distance in km.
            tx_power_dbm: Transmitter output power in dBm.
            tx_antenna_gain_dbi: TX antenna gain in dBi.
            rx_antenna_gain_dbi: RX antenna gain in dBi.
            rx_threshold_dbm: Receiver sensitivity threshold in dBm.
            rain_rate_mmh: Rain rate exceeded 0.01% of time (mm/h).

        Returns:
            Dict with free_space_loss_db, atmospheric_absorption_db,
            rain_attenuation_db, total_path_loss_db, received_power_dbm,
            fade_margin_db, and availability_pct.
        """
        if self._connected and _stubs_available:
            try:
                request = rf_service_pb2.LinkBudgetRequest(
                    frequency_ghz=frequency_ghz,
                    distance_km=distance_km,
                    tx_power_dbm=tx_power_dbm,
                    tx_antenna_gain_dbi=tx_antenna_gain_dbi,
                    rx_antenna_gain_dbi=rx_antenna_gain_dbi,
                    rx_threshold_dbm=rx_threshold_dbm,
                    rain_rate_mmh=rain_rate_mmh,
                )
                response = self._stub.LinkBudget(request)
                return {
                    "free_space_loss_db": response.free_space_loss_db,
                    "atmospheric_absorption_db": response.atmospheric_absorption_db,
                    "rain_attenuation_db": response.rain_attenuation_db,
                    "total_path_loss_db": response.total_path_loss_db,
                    "received_power_dbm": response.received_power_dbm,
                    "fade_margin_db": response.fade_margin_db,
                    "availability_pct": response.availability_pct,
                }
            except Exception as e:
                logger.error(f"LinkBudget RPC failed: {e}")

        # Mock link budget using FSPL
        freq_mhz = frequency_ghz * 1000
        distance_m = distance_km * 1000
        fspl = _mock_fspl(freq_mhz, distance_m)
        atmos = 0.01 * distance_km  # Rough atmospheric absorption
        rain = 5.0 * frequency_ghz * 0.1 * distance_km  # Very rough rain estimate
        total_loss = fspl + atmos
        rx_power = tx_power_dbm + tx_antenna_gain_dbi + rx_antenna_gain_dbi - total_loss
        fade_margin = rx_power - rx_threshold_dbm

        return {
            "free_space_loss_db": round(fspl, 2),
            "atmospheric_absorption_db": round(atmos, 2),
            "rain_attenuation_db": round(rain, 2),
            "total_path_loss_db": round(total_loss, 2),
            "received_power_dbm": round(rx_power, 2),
            "fade_margin_db": round(fade_margin, 2),
            "availability_pct": 99.99 if fade_margin > rain else 99.5,
            "_mock": True,
            "_warning": "Mock response — RF Engine not connected",
        }

    def terrain_profile(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        step_m: float = 30,
        k_factor: float = 1.333,
    ) -> dict:
        """Extract terrain profile between two points.

        Args:
            start_lat: Start latitude (decimal degrees).
            start_lon: Start longitude (decimal degrees).
            end_lat: End latitude (decimal degrees).
            end_lon: End longitude (decimal degrees).
            step_m: Sample spacing in meters (default 30).
            k_factor: Effective Earth radius factor (default 4/3).

        Returns:
            Dict with points (list of profile points), total_distance_m,
            max_elevation_m, min_elevation_m, and num_obstructions.
        """
        if self._connected and _stubs_available:
            try:
                request = rf_service_pb2.ProfileRequest(
                    start_lat=start_lat,
                    start_lon=start_lon,
                    end_lat=end_lat,
                    end_lon=end_lon,
                    step_m=step_m,
                    k_factor=k_factor,
                )
                response = self._stub.TerrainProfile(request)
                points = [
                    {
                        "distance_m": p.distance_m,
                        "elevation_m": p.elevation_m,
                        "latitude": p.latitude,
                        "longitude": p.longitude,
                    }
                    for p in response.points
                ]
                return {
                    "points": points,
                    "total_distance_m": response.total_distance_m,
                    "max_elevation_m": response.max_elevation_m,
                    "min_elevation_m": response.min_elevation_m,
                    "num_obstructions": response.num_obstructions,
                }
            except Exception as e:
                logger.error(f"TerrainProfile RPC failed: {e}")

        # Mock terrain profile
        distance_m = _haversine_distance(start_lat, start_lon, end_lat, end_lon)
        num_points = max(2, int(distance_m / step_m))
        points = []
        for i in range(num_points + 1):
            frac = i / num_points
            lat = start_lat + frac * (end_lat - start_lat)
            lon = start_lon + frac * (end_lon - start_lon)
            d = frac * distance_m
            # Mock elevation: gentle sinusoidal terrain
            elev = 800.0 + 100.0 * math.sin(frac * math.pi)
            points.append(
                {
                    "distance_m": round(d, 1),
                    "elevation_m": round(elev, 1),
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                }
            )

        return {
            "points": points,
            "total_distance_m": round(distance_m, 1),
            "max_elevation_m": 900.0,
            "min_elevation_m": 800.0,
            "num_obstructions": 0,
            "_mock": True,
            "_warning": "Mock response — RF Engine not connected",
        }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in meters."""
    R = 6_371_000.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _mock_fspl(freq_mhz: float, distance_m: float) -> float:
    """Compute free-space path loss in dB (mock)."""
    if distance_m <= 0 or freq_mhz <= 0:
        return 0.0
    freq_hz = freq_mhz * 1e6
    return 20 * math.log10(distance_m) + 20 * math.log10(freq_hz) - 147.55
