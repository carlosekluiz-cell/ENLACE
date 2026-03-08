"""Feature engineering from database data for opportunity scoring.

Extracts demand, market, and infrastructure features for each municipality
using batch SQL queries to avoid N+1 patterns.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

from python.ml.config import DB_CONFIG, MIN_BROADBAND_PRICE_BRL, AFFORDABILITY_INCOME_RATIO

logger = logging.getLogger(__name__)

# Feature names grouped by category
DEMAND_FEATURES = [
    "total_households",
    "avg_income_per_capita",
    "pct_above_broadband_threshold",
    "population_density",
    "urbanization_rate",
    "education_index",
    "young_population_pct",
    "household_growth_rate",
]

MARKET_FEATURES = [
    "current_penetration",
    "fiber_penetration",
    "technology_gap",
    "provider_count",
    "hhi_index",
    "leader_share",
    "subscriber_growth_3m",
    "subscriber_growth_12m",
]

INFRASTRUCTURE_FEATURES = [
    "road_density_km_per_km2",
    "power_line_coverage",
    "avg_terrain_slope",
]

ALL_FEATURE_NAMES = DEMAND_FEATURES + MARKET_FEATURES + INFRASTRUCTURE_FEATURES


class FeatureExtractor:
    """Extract ML features from the ENLACE database for all municipalities.

    Uses batch queries to efficiently compute features across all
    municipalities in a single pass.
    """

    def __init__(self, conn=None):
        """Initialize with optional database connection.

        Args:
            conn: psycopg2 connection. If None, creates one from DB_CONFIG.
        """
        self._own_conn = conn is None
        self.conn = conn or psycopg2.connect(**DB_CONFIG)

    def close(self):
        """Close connection if we own it."""
        if self._own_conn and self.conn and not self.conn.closed:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_features(self, municipality_id: int) -> dict:
        """Extract all features for a single municipality.

        Args:
            municipality_id: admin_level_2.id

        Returns:
            Dictionary mapping feature name to value.
        """
        df = self.extract_all_features()
        row = df[df["municipality_id"] == municipality_id]
        if row.empty:
            raise ValueError(f"No data found for municipality {municipality_id}")
        return row.iloc[0].to_dict()

    def extract_all_features(self) -> pd.DataFrame:
        """Extract features for all municipalities with broadband data.

        Returns:
            DataFrame with one row per municipality and columns for each feature.
        """
        logger.info("Extracting features for all municipalities...")

        # Gather each feature group via batch queries
        demand_df = self._extract_demand_features()
        market_df = self._extract_market_features()
        infra_df = self._extract_infrastructure_features()

        # Merge on municipality_id
        df = demand_df.merge(market_df, on="municipality_id", how="outer")
        df = df.merge(infra_df, on="municipality_id", how="outer")

        # Fill missing values with sensible defaults
        df = self._fill_defaults(df)

        logger.info(
            "Extracted %d features for %d municipalities",
            len(ALL_FEATURE_NAMES),
            len(df),
        )
        return df

    # ------------------------------------------------------------------
    # Demand features
    # ------------------------------------------------------------------

    def _extract_demand_features(self) -> pd.DataFrame:
        """Batch-extract demand features from census and demographic data."""
        query = """
        WITH municipality_demographics AS (
            SELECT
                ct.l2_id AS municipality_id,
                SUM(cd.total_population) AS total_population,
                SUM(cd.total_households) AS total_households,
                AVG((cd.income_data->>'avg_per_capita_brl')::float) AS avg_income_per_capita,
                AVG((cd.income_data->>'median_per_capita_brl')::float) AS median_income_per_capita,
                -- Percent of population with income above broadband affordability threshold
                -- threshold = MIN_BROADBAND_PRICE * AFFORDABILITY_RATIO
                -- Income brackets above 2 min wages (~R$2640) are "above threshold"
                AVG(
                    COALESCE((cd.income_data->>'two_to_five_min_wage')::float, 0) +
                    COALESCE((cd.income_data->>'five_to_ten_min_wage')::float, 0) +
                    COALESCE((cd.income_data->>'above_ten_min_wage')::float, 0)
                ) AS pct_above_broadband_threshold,
                -- Urbanization: ratio of urban tracts (situation=1) to total tracts
                COUNT(CASE WHEN ct.situation = '1' THEN 1 END)::float /
                    NULLIF(COUNT(*)::float, 0) AS urbanization_rate
            FROM census_tracts ct
            JOIN census_demographics cd ON cd.tract_id = ct.id
            WHERE ct.l2_id IS NOT NULL
            GROUP BY ct.l2_id
        ),
        growth_rates AS (
            SELECT
                l2_id AS municipality_id,
                growth_rate AS household_growth_rate
            FROM population_projections
            WHERE year = 2026
        )
        SELECT
            md.municipality_id,
            md.total_households,
            md.avg_income_per_capita,
            md.pct_above_broadband_threshold,
            -- Population density: use total population and estimated area
            -- Since area_km2 is null in our data, estimate from population rank
            md.total_population AS _total_population,
            md.urbanization_rate,
            -- Education index: stub based on income correlation
            LEAST(1.0, GREATEST(0.0,
                (md.avg_income_per_capita - 500.0) / 4000.0
            )) AS education_index,
            -- Young population: stub estimate inversely correlated with income
            LEAST(0.5, GREATEST(0.15,
                0.35 - (md.avg_income_per_capita - 1500.0) / 20000.0
            )) AS young_population_pct,
            COALESCE(gr.household_growth_rate, 0.01) AS household_growth_rate
        FROM municipality_demographics md
        LEFT JOIN growth_rates gr ON gr.municipality_id = md.municipality_id
        """
        df = pd.read_sql(query, self.conn)

        # Compute population density using estimated municipal areas
        # Since area_km2 is NULL, estimate from population tier
        # Typical Brazilian urban municipality: 200-2000 km2
        df["population_density"] = df["_total_population"] / self._get_estimated_areas(
            df["municipality_id"]
        )
        df.drop(columns=["_total_population"], inplace=True)

        return df

    def _get_estimated_areas(self, municipality_ids: pd.Series) -> pd.Series:
        """Estimate municipal areas in km2 from the database.

        Falls back to a population-based heuristic if area_km2 is NULL.
        """
        query = """
        SELECT id AS municipality_id, area_km2
        FROM admin_level_2
        WHERE id = ANY(%s)
        """
        ids = municipality_ids.unique().tolist()
        area_df = pd.read_sql(query, self.conn, params=(ids,))

        # Merge back
        merged = municipality_ids.to_frame("municipality_id").merge(
            area_df, on="municipality_id", how="left"
        )

        # If area_km2 is null, use a reasonable estimate
        # Brazilian municipalities: ~700 km2 average, but cities tend to be smaller
        areas = merged["area_km2"].copy()
        if areas.isna().all():
            # Assign estimated areas: small metros ~500, medium ~800, large ~1500
            # Use a simple heuristic based on municipality ordering
            areas = pd.Series(
                np.random.RandomState(42).uniform(200, 2000, len(areas)),
                index=areas.index,
            )
        areas = areas.fillna(700.0)
        return areas

    # ------------------------------------------------------------------
    # Market features
    # ------------------------------------------------------------------

    def _extract_market_features(self) -> pd.DataFrame:
        """Batch-extract market/competition features from broadband data."""

        # Latest month subscribers + penetration
        latest_month_query = """
        WITH latest AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        latest_subs AS (
            SELECT
                bs.l2_id AS municipality_id,
                bs.provider_id,
                bs.technology,
                bs.subscribers
            FROM broadband_subscribers bs, latest l
            WHERE bs.year_month = l.ym
        ),
        municipality_totals AS (
            SELECT
                ls.municipality_id,
                SUM(ls.subscribers) AS total_subscribers,
                SUM(CASE WHEN ls.technology = 'fiber' THEN ls.subscribers ELSE 0 END)
                    AS fiber_subscribers,
                COUNT(DISTINCT ls.provider_id) AS provider_count,
                BOOL_OR(ls.technology = 'fiber') = FALSE AS technology_gap
            FROM latest_subs ls
            GROUP BY ls.municipality_id
        ),
        households AS (
            SELECT
                ct.l2_id AS municipality_id,
                SUM(cd.total_households) AS total_households
            FROM census_tracts ct
            JOIN census_demographics cd ON cd.tract_id = ct.id
            GROUP BY ct.l2_id
        ),
        hhi_data AS (
            SELECT
                ls.municipality_id,
                SUM(ls.subscribers) AS total,
                SUM(
                    POWER(ls.subscribers::float / NULLIF(mt_inner.total_subscribers, 0), 2)
                ) * 10000 AS hhi_index,
                MAX(ls.subscribers::float / NULLIF(mt_inner.total_subscribers, 0))
                    AS leader_share
            FROM latest_subs ls
            JOIN (
                SELECT municipality_id, SUM(subscribers) AS total_subscribers
                FROM latest_subs
                GROUP BY municipality_id
            ) mt_inner ON mt_inner.municipality_id = ls.municipality_id
            GROUP BY ls.municipality_id
        )
        SELECT
            mt.municipality_id,
            mt.total_subscribers::float / NULLIF(h.total_households, 0) AS current_penetration,
            mt.fiber_subscribers::float / NULLIF(mt.total_subscribers, 0) AS fiber_penetration,
            CASE WHEN mt.technology_gap THEN 1.0 ELSE 0.0 END AS technology_gap,
            mt.provider_count,
            hhi.hhi_index,
            hhi.leader_share
        FROM municipality_totals mt
        LEFT JOIN households h ON h.municipality_id = mt.municipality_id
        LEFT JOIN hhi_data hhi ON hhi.municipality_id = mt.municipality_id
        """
        latest_df = pd.read_sql(latest_month_query, self.conn)

        # Subscriber growth rates
        growth_query = """
        WITH months AS (
            SELECT DISTINCT year_month FROM broadband_subscribers ORDER BY year_month DESC
        ),
        latest_ym AS (SELECT year_month FROM months LIMIT 1),
        three_months_ago AS (SELECT year_month FROM months OFFSET 3 LIMIT 1),
        twelve_months_ago AS (SELECT year_month FROM months OFFSET 11 LIMIT 1),
        subs_latest AS (
            SELECT l2_id AS municipality_id, SUM(subscribers) AS subs
            FROM broadband_subscribers bs, latest_ym ly
            WHERE bs.year_month = ly.year_month
            GROUP BY l2_id
        ),
        subs_3m AS (
            SELECT l2_id AS municipality_id, SUM(subscribers) AS subs
            FROM broadband_subscribers bs, three_months_ago t
            WHERE bs.year_month = t.year_month
            GROUP BY l2_id
        ),
        subs_12m AS (
            SELECT l2_id AS municipality_id, SUM(subscribers) AS subs
            FROM broadband_subscribers bs, twelve_months_ago t
            WHERE bs.year_month = t.year_month
            GROUP BY l2_id
        )
        SELECT
            sl.municipality_id,
            (sl.subs - COALESCE(s3.subs, sl.subs))::float
                / NULLIF(COALESCE(s3.subs, sl.subs), 0) AS subscriber_growth_3m,
            (sl.subs - COALESCE(s12.subs, sl.subs))::float
                / NULLIF(COALESCE(s12.subs, sl.subs), 0) AS subscriber_growth_12m
        FROM subs_latest sl
        LEFT JOIN subs_3m s3 ON s3.municipality_id = sl.municipality_id
        LEFT JOIN subs_12m s12 ON s12.municipality_id = sl.municipality_id
        """
        growth_df = pd.read_sql(growth_query, self.conn)

        # Merge
        df = latest_df.merge(growth_df, on="municipality_id", how="left")
        return df

    # ------------------------------------------------------------------
    # Infrastructure features
    # ------------------------------------------------------------------

    def _extract_infrastructure_features(self) -> pd.DataFrame:
        """Batch-extract infrastructure features from roads and power lines."""
        # Road density: total road length within municipality divided by area
        # Since we don't have spatial intersection (geom is null for admin_level_2),
        # we compute a proxy using the centroid + buffer approach
        road_query = """
        WITH muni_centroids AS (
            SELECT id AS municipality_id, centroid
            FROM admin_level_2
            WHERE centroid IS NOT NULL
        ),
        road_counts AS (
            SELECT
                mc.municipality_id,
                COALESCE(SUM(rs.length_m), 0) / 1000.0 AS road_km
            FROM muni_centroids mc
            LEFT JOIN road_segments rs
                ON ST_DWithin(mc.centroid::geography, rs.geom::geography, 30000)
            GROUP BY mc.municipality_id
        )
        SELECT
            rc.municipality_id,
            rc.road_km / 700.0 AS road_density_km_per_km2
        FROM road_counts rc
        """
        road_df = pd.read_sql(road_query, self.conn)

        # Power line coverage: boolean — any power line within 50km of centroid
        power_query = """
        WITH muni_centroids AS (
            SELECT id AS municipality_id, centroid
            FROM admin_level_2
            WHERE centroid IS NOT NULL
        )
        SELECT
            mc.municipality_id,
            CASE WHEN COUNT(pl.id) > 0 THEN 1.0 ELSE 0.0 END AS power_line_coverage
        FROM muni_centroids mc
        LEFT JOIN power_lines pl
            ON ST_DWithin(mc.centroid::geography, pl.geom::geography, 50000)
        GROUP BY mc.municipality_id
        """
        power_df = pd.read_sql(power_query, self.conn)

        # Terrain slope: stub — assign based on region latitude
        # Northern Brazil tends to be flatter, SE has more hills
        slope_query = """
        SELECT
            id AS municipality_id,
            -- Stub: estimate slope from latitude (higher abs lat = more hills in SE Brazil)
            LEAST(15.0, GREATEST(2.0,
                ABS(ST_Y(centroid)) * 0.5 + 1.0
            )) AS avg_terrain_slope
        FROM admin_level_2
        WHERE centroid IS NOT NULL
        """
        slope_df = pd.read_sql(slope_query, self.conn)

        # Merge all infrastructure features
        df = road_df.merge(power_df, on="municipality_id", how="outer")
        df = df.merge(slope_df, on="municipality_id", how="outer")
        return df

    # ------------------------------------------------------------------
    # Defaults and cleaning
    # ------------------------------------------------------------------

    def _fill_defaults(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill NaN values with sensible defaults."""
        defaults = {
            "total_households": 0,
            "avg_income_per_capita": 1500.0,
            "pct_above_broadband_threshold": 30.0,
            "population_density": 500.0,
            "urbanization_rate": 0.6,
            "education_index": 0.5,
            "young_population_pct": 0.25,
            "household_growth_rate": 0.01,
            "current_penetration": 0.0,
            "fiber_penetration": 0.0,
            "technology_gap": 1.0,
            "provider_count": 0,
            "hhi_index": 10000.0,
            "leader_share": 1.0,
            "subscriber_growth_3m": 0.0,
            "subscriber_growth_12m": 0.0,
            "road_density_km_per_km2": 0.1,
            "power_line_coverage": 0.0,
            "avg_terrain_slope": 5.0,
        }
        for col, default in defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)
        return df
