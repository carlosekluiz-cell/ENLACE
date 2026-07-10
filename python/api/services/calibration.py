"""
Measurement-calibration loop: prediction vs. ground truth.

This is the foundation of the fleet-as-sensor calibration track: every RF
measurement with a known transmitter lets us compute the residual between
what the propagation engine predicted and what was actually received, per
clutter class and environment. Aggregated residuals are (a) the published
accuracy benchmark (RMSE per biome/clutter) and (b) the correction table a
calibrated model applies on top of the physics.

Measurement sources (all land in one schema):
- ISP fleet telemetry (pulso-agent CPE RSSI/SNR) — the compounding moat
- Anatel open data: "Medições de campos eletromagnéticos — Estações de
  telefonia Móvel" (geolocated conformity measurements)
- nic.br SIMET probes, drive tests, site surveys

Tables are created lazily (same pattern as auth/tenant.py).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from python.api.config import Settings

logger = logging.getLogger(__name__)

_tables_ensured = False


def _get_connection():
    settings = Settings()
    return psycopg2.connect(settings.database_sync_url)


def _ensure_tables_once() -> None:
    global _tables_ensured
    if _tables_ensured:
        return
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rf_measurements (
                id BIGSERIAL PRIMARY KEY,
                lat DOUBLE PRECISION NOT NULL,
                lon DOUBLE PRECISION NOT NULL,
                frequency_mhz DOUBLE PRECISION NOT NULL,
                measured_dbm DOUBLE PRECISION NOT NULL,
                rx_height_m DOUBLE PRECISION NOT NULL DEFAULT 1.5,
                tx_lat DOUBLE PRECISION,
                tx_lon DOUBLE PRECISION,
                tx_height_m DOUBLE PRECISION,
                tx_power_dbm DOUBLE PRECISION,
                tx_gain_dbi DOUBLE PRECISION,
                source VARCHAR(100) NOT NULL,
                campaign VARCHAR(200),
                measured_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                meta JSONB
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rf_residuals (
                measurement_id BIGINT PRIMARY KEY
                    REFERENCES rf_measurements(id) ON DELETE CASCADE,
                predicted_dbm DOUBLE PRECISION NOT NULL,
                residual_db DOUBLE PRECISION NOT NULL,
                model VARCHAR(40) NOT NULL,
                environment VARCHAR(20),
                clutter VARCHAR(20),
                distance_m DOUBLE PRECISION,
                computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_rf_meas_geo ON rf_measurements (lat, lon)"
        )
        conn.commit()
        cur.close()
        _tables_ensured = True
    finally:
        conn.close()


@dataclass
class Measurement:
    lat: float
    lon: float
    frequency_mhz: float
    measured_dbm: float
    rx_height_m: float = 1.5
    tx_lat: Optional[float] = None
    tx_lon: Optional[float] = None
    tx_height_m: Optional[float] = None
    tx_power_dbm: Optional[float] = None
    tx_gain_dbi: Optional[float] = None
    source: str = "manual"
    campaign: Optional[str] = None
    measured_at: Optional[str] = None
    meta: Optional[dict] = None


def record_measurements(measurements: list[Measurement]) -> int:
    """Insert a batch of measurements; returns the number stored."""
    if not measurements:
        return 0
    _ensure_tables_once()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO rf_measurements
            (lat, lon, frequency_mhz, measured_dbm, rx_height_m,
             tx_lat, tx_lon, tx_height_m, tx_power_dbm, tx_gain_dbi,
             source, campaign, measured_at, meta)
            VALUES %s
            """,
            [
                (
                    m.lat, m.lon, m.frequency_mhz, m.measured_dbm, m.rx_height_m,
                    m.tx_lat, m.tx_lon, m.tx_height_m, m.tx_power_dbm, m.tx_gain_dbi,
                    m.source, m.campaign, m.measured_at,
                    json.dumps(m.meta) if m.meta else None,
                )
                for m in measurements
            ],
        )
        conn.commit()
        n = cur.rowcount
        cur.close()
        return n
    finally:
        conn.close()


def compute_residuals(limit: int = 500) -> dict:
    """Predict each un-scored measurement and store the residual.

    Only measurements with full TX parameters can be scored. The prediction
    uses the same engine the planner uses (gRPC, with local ITU-R fallback),
    with environment/clutter from MapBiomas at the RX point.
    """
    from python.api.services import clutter as clutter_svc
    from python.api.services import terrain_tiles
    from python.api.services.rf_client import get_rf_client
    from python.api.services.terrain_reader import get_landcover_reader

    _ensure_tables_once()
    conn = _get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT m.* FROM rf_measurements m
            LEFT JOIN rf_residuals r ON r.measurement_id = m.id
            WHERE r.measurement_id IS NULL
              AND m.tx_lat IS NOT NULL AND m.tx_lon IS NOT NULL
              AND m.tx_power_dbm IS NOT NULL
            ORDER BY m.id
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        if not rows:
            return {"scored": 0, "remaining_unscorable": _count_unscorable(cur)}

        client = get_rf_client()
        lc = get_landcover_reader()
        scored = 0
        for m in rows:
            try:
                terrain_tiles.get_tile_store().ensure_landcover(
                    [terrain_tiles.tile_name(m["lat"], m["lon"])]
                )
            except Exception:
                pass
            code = lc.code(m["lat"], m["lon"])
            clutter_key = clutter_svc.classify(code).key if code is not None else None
            environment = clutter_svc.infer_environment([code] if code is not None else [])

            freq = m["frequency_mhz"]
            model = "hata" if 150 <= freq <= 2000 else "tr38901" if freq > 2000 else "fspl"
            pred = client.calculate_path_loss(
                tx_lat=m["tx_lat"],
                tx_lon=m["tx_lon"],
                tx_height_m=m["tx_height_m"] or 30.0,
                rx_lat=m["lat"],
                rx_lon=m["lon"],
                rx_height_m=m["rx_height_m"] or 1.5,
                frequency_mhz=freq,
                model=model,
                environment=environment,
            )
            loss = pred.get("path_loss_db")
            if loss is None:
                continue
            predicted_dbm = (
                m["tx_power_dbm"] + (m["tx_gain_dbi"] or 0.0) - loss
            )
            residual = m["measured_dbm"] - predicted_dbm
            distance_m = _haversine_m(m["tx_lat"], m["tx_lon"], m["lat"], m["lon"])
            cur.execute(
                """
                INSERT INTO rf_residuals
                (measurement_id, predicted_dbm, residual_db, model,
                 environment, clutter, distance_m)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (measurement_id) DO NOTHING
                """,
                (
                    m["id"], predicted_dbm, residual, model,
                    environment, clutter_key, distance_m,
                ),
            )
            scored += 1
        conn.commit()
        return {"scored": scored, "remaining_unscorable": _count_unscorable(cur)}
    finally:
        conn.close()


def _count_unscorable(cur) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS n FROM rf_measurements
        WHERE tx_lat IS NULL OR tx_power_dbm IS NULL
        """
    )
    row = cur.fetchone()
    return row["n"] if isinstance(row, dict) else row[0]


def summarize_residuals(rows: list[dict]) -> dict:
    """Aggregate residual rows into the calibration benchmark.

    Pure function (unit-testable): rows need residual_db and optionally
    environment/clutter/model keys.
    """
    def _stats(vals: list[float]) -> dict:
        n = len(vals)
        if n == 0:
            return {"n": 0}
        mean = sum(vals) / n
        var = sum((v - mean) ** 2 for v in vals) / n
        rmse = math.sqrt(sum(v * v for v in vals) / n)
        return {
            "n": n,
            "bias_db": round(mean, 2),
            "std_db": round(math.sqrt(var), 2),
            "rmse_db": round(rmse, 2),
        }

    out: dict[str, Any] = {"overall": _stats([r["residual_db"] for r in rows])}
    for dim in ("environment", "clutter", "model"):
        groups: dict[str, list[float]] = {}
        for r in rows:
            key = r.get(dim) or "unknown"
            groups.setdefault(key, []).append(r["residual_db"])
        out[f"by_{dim}"] = {k: _stats(v) for k, v in sorted(groups.items())}
    return out


def calibration_summary() -> dict:
    """Current benchmark: residual stats overall and per dimension.

    Aggregates in SQL — the residual store holds millions of rows.
    """
    _ensure_tables_once()
    conn = _get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        def _agg(group_col: str | None) -> dict:
            sel = f"COALESCE({group_col}, 'unknown') AS grp," if group_col else "'overall' AS grp,"
            grp = f"GROUP BY COALESCE({group_col}, 'unknown')" if group_col else ""
            cur.execute(
                f"""
                SELECT {sel}
                       COUNT(*) AS n,
                       ROUND(AVG(residual_db)::numeric, 2) AS bias_db,
                       ROUND(COALESCE(STDDEV(residual_db), 0)::numeric, 2) AS std_db,
                       ROUND(SQRT(AVG(residual_db * residual_db))::numeric, 2) AS rmse_db
                FROM rf_residuals {grp}
                """
            )
            return {
                r["grp"]: {
                    "n": r["n"],
                    "bias_db": float(r["bias_db"]),
                    "std_db": float(r["std_db"]),
                    "rmse_db": float(r["rmse_db"]),
                }
                for r in cur.fetchall()
            }

        overall_map = _agg(None)
        overall = overall_map.get("overall", {"n": 0})
        summary: dict = {"overall": overall if overall["n"] else {"n": 0}}
        for dim in ("environment", "clutter", "model"):
            summary[f"by_{dim}"] = _agg(dim)
        cur.execute("SELECT COUNT(*) AS n, COUNT(DISTINCT source) AS sources FROM rf_measurements")
        meas = cur.fetchone()
        summary["measurements_total"] = meas["n"]
        summary["measurement_sources"] = meas["sources"]
        summary["residuals_scored"] = overall.get("n", 0)
        # Honesty invariant: a benchmark with no data is not a benchmark.
        summary["benchmark_valid"] = overall.get("n", 0) >= 100
        # Calibrated model v1: held-out evaluation, if the fit has run.
        try:
            cur.execute(
                """SELECT environment, n_test,
                          ROUND(rmse_before::numeric,2) AS rmse_before,
                          ROUND(rmse_after::numeric,2) AS rmse_after
                   FROM rf_calibration_eval ORDER BY n_test DESC"""
            )
            rows = cur.fetchall()
            if rows:
                summary["calibrated"] = {
                    r["environment"]: {
                        "n_test": r["n_test"],
                        "rmse_before_db": float(r["rmse_before"]),
                        "rmse_after_db": float(r["rmse_after"]),
                    }
                    for r in rows
                }
        except Exception:
            conn.rollback()  # eval table absent on fresh installs
        return summary
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Corrections: residual bias applied back onto predictions
# ---------------------------------------------------------------------------

MIN_GROUP_N = 30
_CORRECTIONS_TTL_S = 300.0
_corrections_cache: tuple[float, dict] | None = None


def corrections_from_summary(summary: dict) -> dict[str, float]:
    """Per-environment bias corrections (dB) from a calibration summary.

    Pure function. Returns {} unless the benchmark is valid (>=100
    residuals) AND the environment group has >= MIN_GROUP_N samples —
    corrections from thin data would be noise, not calibration.
    Positive bias means the model under-predicts received signal.
    """
    if not summary.get("benchmark_valid"):
        return {}
    out = {}
    for env, s in (summary.get("by_environment") or {}).items():
        if env != "unknown" and s.get("n", 0) >= MIN_GROUP_N:
            out[env] = s["bias_db"]
    return out


def get_corrections() -> dict[str, float]:
    """Current correction table (cached ~5 min to keep coverage cheap)."""
    global _corrections_cache
    import time

    now = time.monotonic()
    if _corrections_cache is not None and now - _corrections_cache[0] < _CORRECTIONS_TTL_S:
        return _corrections_cache[1]
    try:
        corrections = corrections_from_summary(calibration_summary())
    except Exception as e:
        logger.warning("Correction lookup failed: %s", e)
        corrections = {}
    _corrections_cache = (now, corrections)
    return corrections


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))
