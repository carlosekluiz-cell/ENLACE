"""Ookla Speedtest open data pipeline.

Source: Ookla Open Data on AWS S3
URL: s3://ookla-open-data/parquet/performance/type=fixed/year={year}/quarter={quarter}/
Format: Apache Parquet with tile-level speedtest aggregations (quadkey-based)
Reference: https://github.com/teamookla/ookla-open-data

Downloads fixed-broadband performance tiles from Ookla's public S3 bucket,
filters to Brazil's bounding box, spatial-joins to admin_level_2 municipalities,
and stores both raw tile data and per-municipality aggregations.

Schedule: quarterly (new data released ~45 days after quarter end)
"""
import logging
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from python.pipeline.base import BasePipeline
from python.pipeline.config import BRAZIL_BBOX, DOWNLOAD_CACHE_DIR

logger = logging.getLogger(__name__)

# Ookla Open Data S3 bucket (public, no auth required)
OOKLA_S3_BASE = "https://ookla-open-data.s3.amazonaws.com/parquet/performance"

# Quarters to attempt, most recent first
QUARTERS_TO_TRY = [
    (2025, 1),
    (2024, 4),
    (2024, 3),
    (2024, 2),
    (2024, 1),
]


def _quadkey_to_tile(quadkey: str) -> tuple[int, int, int]:
    """Convert a quadkey string to (x, y, zoom) tile coordinates."""
    x, y = 0, 0
    zoom = len(quadkey)
    for i in range(zoom):
        bit = zoom - i - 1
        mask = 1 << bit
        ch = quadkey[i]
        if ch == "1":
            x |= mask
        elif ch == "2":
            y |= mask
        elif ch == "3":
            x |= mask
            y |= mask
    return x, y, zoom


def _tile_to_bbox(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    """Convert tile (x, y, zoom) to (west, south, east, north) in EPSG:4326."""
    import math
    n = 2 ** zoom
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def quadkey_to_polygon(quadkey: str):
    """Convert a quadkey to a Shapely polygon (tile bounding box)."""
    x, y, zoom = _quadkey_to_tile(quadkey)
    west, south, east, north = _tile_to_bbox(x, y, zoom)
    return box(west, south, east, north)


class OoklaSpeedtestPipeline(BasePipeline):
    """Ingest Ookla Speedtest open data tiles and aggregate by municipality."""

    def __init__(self):
        super().__init__("ookla_speedtest")

    def check_for_updates(self) -> bool:
        """Check if we have speedtest data for the latest available quarter."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM speedtest_tiles")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        # Run if we have no data at all, or force via scheduler
        return count == 0

    def download(self) -> pd.DataFrame:
        """Download Ookla Parquet tiles from S3 and filter to Brazil bbox."""
        brazil_bbox = box(
            BRAZIL_BBOX["min_lon"],
            BRAZIL_BBOX["min_lat"],
            BRAZIL_BBOX["max_lon"],
            BRAZIL_BBOX["max_lat"],
        )

        cache_dir = Path(DOWNLOAD_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        all_tiles = []

        for year, quarter in QUARTERS_TO_TRY:
            quarter_label = f"{year}-Q{quarter}"
            parquet_url = (
                f"{OOKLA_S3_BASE}/type=fixed/year={year}/quarter={quarter}/"
                f"{year}-{quarter}_performance_fixed_tiles.parquet"
            )
            cache_path = cache_dir / f"ookla_fixed_{year}_q{quarter}.parquet"

            try:
                # Download if not cached
                if not cache_path.exists():
                    logger.info(f"Downloading Ookla {quarter_label} from {parquet_url}")
                    import httpx
                    with httpx.Client(
                        timeout=httpx.Timeout(600, connect=30.0),
                        follow_redirects=True,
                        headers={"User-Agent": "ENLACE-Pipeline/1.0"},
                    ) as client:
                        with client.stream("GET", parquet_url) as resp:
                            resp.raise_for_status()
                            with open(cache_path, "wb") as f:
                                for chunk in resp.iter_bytes(chunk_size=65536):
                                    f.write(chunk)
                    logger.info(f"Downloaded {cache_path.stat().st_size:,} bytes")
                else:
                    logger.info(f"Using cached Ookla {quarter_label}: {cache_path}")

                # Read parquet
                logger.info(f"Reading Ookla {quarter_label} parquet...")
                df = pd.read_parquet(cache_path)
                logger.info(f"Raw tiles: {len(df):,} rows, columns: {list(df.columns)}")

                # The Ookla dataset has a 'tile' column with geometry WKT or
                # quadkey column. Handle both formats.
                if "tile" in df.columns:
                    # 'tile' column contains WKT geometry strings
                    from shapely import wkt
                    gdf = gpd.GeoDataFrame(
                        df,
                        geometry=df["tile"].apply(lambda t: wkt.loads(t) if isinstance(t, str) else t),
                        crs="EPSG:4326",
                    )
                elif "quadkey" in df.columns:
                    # Convert quadkeys to polygons
                    gdf = gpd.GeoDataFrame(
                        df,
                        geometry=df["quadkey"].apply(quadkey_to_polygon),
                        crs="EPSG:4326",
                    )
                else:
                    logger.warning(f"Unknown Ookla format. Columns: {list(df.columns)}")
                    continue

                # Filter to Brazil bounding box
                brazil_mask = gdf.geometry.intersects(brazil_bbox)
                gdf_brazil = gdf[brazil_mask].copy()
                logger.info(
                    f"Ookla {quarter_label}: {len(gdf_brazil):,} tiles in Brazil "
                    f"(from {len(gdf):,} total)"
                )

                if not gdf_brazil.empty:
                    gdf_brazil["quarter"] = quarter_label
                    gdf_brazil["year"] = year
                    gdf_brazil["quarter_num"] = quarter
                    all_tiles.append(gdf_brazil)

            except Exception as e:
                logger.warning(f"Could not load Ookla {quarter_label}: {e}")
                continue

        if not all_tiles:
            raise ValueError(
                "No Ookla speedtest data could be downloaded for any quarter. "
                "Check network connectivity to ookla-open-data.s3.amazonaws.com"
            )

        combined = pd.concat(all_tiles, ignore_index=True)
        logger.info(f"Total Ookla tiles for Brazil: {len(combined):,}")
        return combined

    def validate_raw(self, data) -> None:
        """Validate that we have speedtest data with required columns."""
        if data.empty:
            raise ValueError("Empty Ookla speedtest dataset")

        required_cols = {"avg_d_kbps", "avg_u_kbps", "avg_lat_ms", "tests", "devices"}
        available = set(data.columns)
        missing = required_cols - available
        if missing:
            logger.warning(
                f"Missing expected columns: {missing}. Available: {sorted(available)}"
            )

    def transform(self, raw_data) -> dict:
        """Spatial join tiles to municipalities and compute aggregations.

        Returns a dict with 'tiles' DataFrame and 'municipality' DataFrame.
        """
        gdf = raw_data if isinstance(raw_data, gpd.GeoDataFrame) else gpd.GeoDataFrame(raw_data)

        # Ensure standard column names (Ookla sometimes varies)
        col_map = {}
        for expected, alternatives in [
            ("avg_d_kbps", ["avg_d_kbps", "avg_d_mbps"]),
            ("avg_u_kbps", ["avg_u_kbps", "avg_u_mbps"]),
            ("avg_lat_ms", ["avg_lat_ms", "avg_latency_ms"]),
            ("tests", ["tests", "test_count"]),
            ("devices", ["devices", "device_count"]),
        ]:
            for alt in alternatives:
                if alt in gdf.columns:
                    col_map[alt] = expected
                    break

        if col_map:
            gdf = gdf.rename(columns=col_map)

        # Ensure numeric types
        for col in ["avg_d_kbps", "avg_u_kbps", "avg_lat_ms", "tests", "devices"]:
            if col in gdf.columns:
                gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

        # Get quadkey if available, else generate from centroid
        if "quadkey" not in gdf.columns:
            gdf["quadkey"] = ""

        # --- Load municipality geometries for spatial join ---
        logger.info("Loading municipality geometries for spatial join...")
        conn = self._get_connection()
        import io
        muni_sql = """
            SELECT id AS l2_id, code, name,
                   ST_AsText(geom) AS geom_wkt
            FROM admin_level_2
            WHERE country_code = 'BR' AND geom IS NOT NULL
        """
        muni_df = pd.read_sql(muni_sql, conn)
        conn.close()

        if muni_df.empty:
            logger.warning("No municipality geometries found, skipping spatial join")
            return {"tiles": gdf, "municipality": pd.DataFrame()}

        from shapely import wkt
        muni_gdf = gpd.GeoDataFrame(
            muni_df,
            geometry=muni_df["geom_wkt"].apply(wkt.loads),
            crs="EPSG:4326",
        )
        muni_gdf = muni_gdf.drop(columns=["geom_wkt"])

        # Spatial join: assign each tile to its municipality using centroid
        gdf["centroid"] = gdf.geometry.centroid
        gdf_centroids = gdf.set_geometry("centroid")

        logger.info("Performing spatial join (tile centroids -> municipalities)...")
        joined = gpd.sjoin(
            gdf_centroids,
            muni_gdf[["l2_id", "geometry"]],
            how="inner",
            predicate="within",
        )
        logger.info(f"Spatial join matched {len(joined):,} tiles to municipalities")

        # Reset geometry back to tile polygon
        joined = joined.set_geometry(gdf.geometry.name)
        if "centroid" in joined.columns:
            joined = joined.drop(columns=["centroid"])

        # --- Aggregate per municipality per quarter ---
        agg_rows = []
        for (l2_id, quarter), group in joined.groupby(["l2_id", "quarter"]):
            d_vals = group["avg_d_kbps"].dropna()
            u_vals = group["avg_u_kbps"].dropna()
            lat_vals = group["avg_lat_ms"].dropna()

            # Weighted average by number of tests
            weights = group["tests"].fillna(1)
            total_tests = int(weights.sum())
            total_devices = int(group["devices"].fillna(0).sum())

            if total_tests > 0 and not d_vals.empty:
                # Weighted averages
                w = weights.loc[d_vals.index]
                avg_d = float(np.average(d_vals, weights=w.loc[d_vals.index]))
                avg_u = float(np.average(u_vals, weights=w.loc[u_vals.index])) if not u_vals.empty else 0.0
                avg_lat = float(np.average(lat_vals, weights=w.loc[lat_vals.index])) if not lat_vals.empty else 0.0

                # Percentiles for download speed
                p10_d = float(np.percentile(d_vals, 10))
                p50_d = float(np.percentile(d_vals, 50))
                p90_d = float(np.percentile(d_vals, 90))
            else:
                avg_d = float(d_vals.mean()) if not d_vals.empty else 0.0
                avg_u = float(u_vals.mean()) if not u_vals.empty else 0.0
                avg_lat = float(lat_vals.mean()) if not lat_vals.empty else 0.0
                p10_d = float(np.percentile(d_vals, 10)) if not d_vals.empty else 0.0
                p50_d = float(np.percentile(d_vals, 50)) if not d_vals.empty else 0.0
                p90_d = float(np.percentile(d_vals, 90)) if not d_vals.empty else 0.0

            agg_rows.append({
                "l2_id": int(l2_id),
                "quarter": quarter,
                "avg_download_mbps": round(avg_d / 1000.0, 2),
                "avg_upload_mbps": round(avg_u / 1000.0, 2),
                "avg_latency_ms": round(avg_lat, 1),
                "total_tests": total_tests,
                "total_devices": total_devices,
                "p10_download_mbps": round(p10_d / 1000.0, 2),
                "p50_download_mbps": round(p50_d / 1000.0, 2),
                "p90_download_mbps": round(p90_d / 1000.0, 2),
            })

        muni_agg = pd.DataFrame(agg_rows)
        logger.info(
            f"Aggregated speedtest data for {muni_agg['l2_id'].nunique()} "
            f"municipalities across {muni_agg['quarter'].nunique()} quarters"
        )

        self.rows_processed = len(joined)
        return {"tiles": joined, "municipality": muni_agg}

    def load(self, data: dict) -> None:
        """Load tile-level and municipality-level speedtest data into PostgreSQL."""
        tiles_df = data.get("tiles")
        muni_df = data.get("municipality")

        conn = self._get_connection()
        cur = conn.cursor()

        tiles_inserted = 0
        muni_inserted = 0

        # --- Load raw tiles into speedtest_tiles ---
        if tiles_df is not None and not tiles_df.empty:
            logger.info(f"Loading {len(tiles_df):,} tiles into speedtest_tiles...")

            # Clear existing data for these quarters
            quarters = tiles_df["quarter"].unique().tolist()
            for q in quarters:
                cur.execute("DELETE FROM speedtest_tiles WHERE quarter = %s", (q,))

            from psycopg2.extras import execute_values
            tile_values = []
            for _, row in tiles_df.iterrows():
                quadkey = str(row.get("quadkey", ""))
                quarter = str(row["quarter"])
                avg_d = row.get("avg_d_kbps")
                avg_u = row.get("avg_u_kbps")
                avg_lat = row.get("avg_lat_ms")
                tests = row.get("tests")
                devices = row.get("devices")

                # Build polygon EWKT from geometry
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue

                coords = list(geom.exterior.coords)
                coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
                geom_ewkt = f"SRID=4326;POLYGON(({coord_str}))"

                tile_values.append((
                    quadkey, quarter,
                    float(avg_d) if pd.notna(avg_d) else None,
                    float(avg_u) if pd.notna(avg_u) else None,
                    float(avg_lat) if pd.notna(avg_lat) else None,
                    int(tests) if pd.notna(tests) else None,
                    int(devices) if pd.notna(devices) else None,
                    geom_ewkt,
                ))

            if tile_values:
                execute_values(cur, """
                    INSERT INTO speedtest_tiles
                    (quadkey, quarter, avg_d_kbps, avg_u_kbps, avg_lat_ms,
                     tests, devices, geom)
                    VALUES %s
                """, tile_values, template=(
                    "(%s, %s, %s, %s, %s, %s, %s, ST_GeomFromEWKT(%s))"
                ), page_size=5000)
                tiles_inserted = len(tile_values)
                logger.info(f"Inserted {tiles_inserted:,} speedtest tiles")

            conn.commit()

        # --- Load municipality aggregations into speedtest_municipality ---
        if muni_df is not None and not muni_df.empty:
            logger.info(
                f"Loading {len(muni_df):,} municipality aggregations "
                f"into speedtest_municipality..."
            )

            # Clear existing data for these quarters
            quarters = muni_df["quarter"].unique().tolist()
            for q in quarters:
                cur.execute(
                    "DELETE FROM speedtest_municipality WHERE quarter = %s", (q,)
                )

            from psycopg2.extras import execute_values
            muni_values = []
            for _, row in muni_df.iterrows():
                muni_values.append((
                    int(row["l2_id"]),
                    str(row["quarter"]),
                    float(row["avg_download_mbps"]),
                    float(row["avg_upload_mbps"]),
                    float(row["avg_latency_ms"]),
                    int(row["total_tests"]),
                    int(row["total_devices"]),
                    float(row["p10_download_mbps"]),
                    float(row["p50_download_mbps"]),
                    float(row["p90_download_mbps"]),
                ))

            if muni_values:
                execute_values(cur, """
                    INSERT INTO speedtest_municipality
                    (l2_id, quarter, avg_download_mbps, avg_upload_mbps,
                     avg_latency_ms, total_tests, total_devices,
                     p10_download_mbps, p50_download_mbps, p90_download_mbps)
                    VALUES %s
                """, muni_values, template=(
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ), page_size=5000)
                muni_inserted = len(muni_values)
                logger.info(f"Inserted {muni_inserted:,} municipality speedtest records")

            conn.commit()

        self.rows_inserted = tiles_inserted + muni_inserted
        cur.close()
        conn.close()
        logger.info(
            f"Ookla speedtest load complete: {tiles_inserted:,} tiles + "
            f"{muni_inserted:,} municipality aggregations"
        )
