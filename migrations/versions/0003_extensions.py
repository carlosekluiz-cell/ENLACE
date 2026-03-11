"""extensions and new feature tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11

Adds pgRouting, H3 extensions. Creates tables for: building footprints,
speedtest data, OpenCelliD towers, coverage validation, tower co-location,
H3 hex cells, time-series aggregates, alerts, Pulso scores, ISP credit scores.
Adds routing columns to road_segments for pgRouting topology.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgrouting")
    op.execute("CREATE EXTENSION IF NOT EXISTS h3")
    op.execute("CREATE EXTENSION IF NOT EXISTS h3_postgis CASCADE")

    # ── Building Footprints (Microsoft + OSM) ─────────────────────────────
    op.create_table(
        "building_footprints",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id"), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="microsoft"),
        sa.Column("area_m2", sa.Float),
        sa.Column("height_m", sa.Float),
        sa.Column("geom", sa.Text, nullable=False),  # geometry(Polygon,4326)
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("""
        ALTER TABLE building_footprints
        ALTER COLUMN geom TYPE geometry(Polygon, 4326)
        USING ST_SetSRID(geom::geometry, 4326)
    """)
    op.execute("CREATE INDEX idx_bf_geom ON building_footprints USING GIST (geom)")
    op.execute("CREATE INDEX idx_bf_l2 ON building_footprints (l2_id)")

    # ── Speedtest Tiles (Ookla) ───────────────────────────────────────────
    op.create_table(
        "speedtest_tiles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("quadkey", sa.String(20), nullable=False),
        sa.Column("quarter", sa.String(7), nullable=False),  # 2025-Q1
        sa.Column("avg_d_kbps", sa.Integer),
        sa.Column("avg_u_kbps", sa.Integer),
        sa.Column("avg_lat_ms", sa.Float),
        sa.Column("tests", sa.Integer),
        sa.Column("devices", sa.Integer),
        sa.Column("geom", sa.Text, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("""
        ALTER TABLE speedtest_tiles
        ALTER COLUMN geom TYPE geometry(Polygon, 4326)
        USING ST_SetSRID(geom::geometry, 4326)
    """)
    op.execute("CREATE INDEX idx_st_geom ON speedtest_tiles USING GIST (geom)")
    op.execute("CREATE INDEX idx_st_quarter ON speedtest_tiles (quarter)")

    # ── Speedtest Municipality Aggregates ─────────────────────────────────
    op.create_table(
        "speedtest_municipality",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id"), nullable=False),
        sa.Column("quarter", sa.String(7), nullable=False),
        sa.Column("avg_download_mbps", sa.Float),
        sa.Column("avg_upload_mbps", sa.Float),
        sa.Column("avg_latency_ms", sa.Float),
        sa.Column("total_tests", sa.Integer),
        sa.Column("total_devices", sa.Integer),
        sa.Column("p10_download_mbps", sa.Float),
        sa.Column("p50_download_mbps", sa.Float),
        sa.Column("p90_download_mbps", sa.Float),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("l2_id", "quarter", name="uq_speedtest_muni_quarter"),
    )

    # ── OpenCelliD Towers ─────────────────────────────────────────────────
    op.create_table(
        "opencellid_towers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("cell_id", sa.BigInteger),
        sa.Column("mcc", sa.Integer, nullable=False),
        sa.Column("mnc", sa.Integer, nullable=False),
        sa.Column("lac", sa.Integer),
        sa.Column("radio", sa.String(10)),  # LTE, UMTS, GSM, NR
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("range_m", sa.Integer),
        sa.Column("samples", sa.Integer),
        sa.Column("matched_base_station_id", sa.Integer, sa.ForeignKey("base_stations.id")),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("geom", sa.Text),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("""
        ALTER TABLE opencellid_towers
        ADD COLUMN IF NOT EXISTS geom_point geometry(Point, 4326)
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)) STORED
    """)
    op.execute("CREATE INDEX idx_ocid_geom ON opencellid_towers USING GIST (geom_point)")
    op.execute("CREATE INDEX idx_ocid_matched ON opencellid_towers (matched_base_station_id)")

    # ── Coverage Validation ───────────────────────────────────────────────
    op.create_table(
        "coverage_validation",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id"), nullable=False),
        sa.Column("anatel_tower_count", sa.Integer),
        sa.Column("opencellid_tower_count", sa.Integer),
        sa.Column("osm_tower_count", sa.Integer),
        sa.Column("matched_count", sa.Integer),
        sa.Column("unmatched_opencellid", sa.Integer),
        sa.Column("coverage_confidence", sa.Float),  # 0-1
        sa.Column("gap_area_km2", sa.Float),
        sa.Column("gap_population", sa.Integer),
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_cv_l2 ON coverage_validation (l2_id)")

    # ── Tower Co-location Analysis ────────────────────────────────────────
    op.create_table(
        "tower_colocation_analysis",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("base_station_id", sa.Integer, sa.ForeignKey("base_stations.id"), nullable=False),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("provider_name", sa.String(200)),
        sa.Column("nearby_towers_500m", sa.Integer),
        sa.Column("nearby_providers", JSONB),  # [{"name": "Vivo", "distance_m": 120}, ...]
        sa.Column("underserved_pop_5km", sa.Integer),
        sa.Column("competitor_density_score", sa.Float),
        sa.Column("gap_coverage_score", sa.Float),
        sa.Column("spectrum_complement_score", sa.Float),
        sa.Column("colocation_score", sa.Float),  # weighted composite 0-100
        sa.Column("estimated_savings_brl", sa.Float),
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_tca_bs ON tower_colocation_analysis (base_station_id)")
    op.execute("CREATE INDEX idx_tca_score ON tower_colocation_analysis (colocation_score DESC)")

    # ── H3 Hex Cells ─────────────────────────────────────────────────────
    op.create_table(
        "h3_cells",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("h3_index", sa.String(20), nullable=False),
        sa.Column("resolution", sa.SmallInteger, nullable=False),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("subscribers", sa.Integer),
        sa.Column("tower_count", sa.Integer),
        sa.Column("building_count", sa.Integer),
        sa.Column("building_area_m2", sa.Float),
        sa.Column("population_estimate", sa.Integer),
        sa.Column("penetration_pct", sa.Float),
        sa.Column("growth_pct_12m", sa.Float),
        sa.Column("avg_download_mbps", sa.Float),
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE UNIQUE INDEX idx_h3_index_res ON h3_cells (h3_index, resolution)")
    op.execute("CREATE INDEX idx_h3_l2 ON h3_cells (l2_id)")
    op.execute("CREATE INDEX idx_h3_res ON h3_cells (resolution)")

    # ── Subscriber Time-Series (materialized view approach) ───────────────
    op.create_table(
        "subscriber_timeseries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id"), nullable=False),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("year_month", sa.String(7), nullable=False),  # 2025-01
        sa.Column("subscribers", sa.Integer),
        sa.Column("fiber_subscribers", sa.Integer),
        sa.Column("mom_growth_pct", sa.Float),  # month-over-month
        sa.Column("yoy_growth_pct", sa.Float),  # year-over-year
        sa.Column("churn_estimate_pct", sa.Float),
        sa.Column("arpu_estimate_brl", sa.Float),
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("""
        CREATE UNIQUE INDEX idx_sts_unique
        ON subscriber_timeseries (l2_id, COALESCE(provider_id, 0), year_month)
    """)
    op.execute("CREATE INDEX idx_sts_ym ON subscriber_timeseries (year_month)")

    # ── Alert Rules ───────────────────────────────────────────────────────
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("rule_type", sa.String(50), nullable=False),
        # subscriber_drop, competitor_entry, regulatory_deadline, quality_degradation, market_change
        sa.Column("conditions", JSONB, nullable=False),
        # {"metric": "subscribers", "operator": "decrease_pct", "threshold": 5, "scope": {"state": "SP"}}
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("channels", JSONB, server_default='["in_app"]'),  # in_app, email, webhook
        sa.Column("cooldown_hours", sa.Integer, server_default="24"),
        sa.Column("last_triggered_at", TIMESTAMP(timezone=True)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_ar_user ON alert_rules (user_id)")
    op.execute("CREATE INDEX idx_ar_type ON alert_rules (rule_type)")

    # ── Alert Events ──────────────────────────────────────────────────────
    op.create_table(
        "alert_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        # info, warning, critical
        sa.Column("data", JSONB),  # context payload
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("acknowledged_at", TIMESTAMP(timezone=True)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_ae_user_unread ON alert_events (user_id, is_read) WHERE NOT is_read")
    op.execute("CREATE INDEX idx_ae_rule ON alert_events (rule_id)")
    op.execute("CREATE INDEX idx_ae_created ON alert_events (created_at DESC)")

    # ── Pulso Scores ──────────────────────────────────────────────────────
    op.create_table(
        "pulso_scores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),  # 0-100 composite
        sa.Column("growth_score", sa.Float),
        sa.Column("fiber_score", sa.Float),
        sa.Column("quality_score", sa.Float),
        sa.Column("compliance_score", sa.Float),
        sa.Column("financial_score", sa.Float),
        sa.Column("market_score", sa.Float),
        sa.Column("bndes_score", sa.Float),
        sa.Column("tier", sa.String(10)),  # S, A, B, C, D
        sa.Column("rank", sa.Integer),
        sa.Column("previous_score", sa.Float),
        sa.Column("score_change", sa.Float),
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_ps_provider ON pulso_scores (provider_id)")
    op.execute("CREATE INDEX idx_ps_score ON pulso_scores (score DESC)")
    op.execute("CREATE INDEX idx_ps_tier ON pulso_scores (tier)")

    # ── ISP Credit Scores ─────────────────────────────────────────────────
    op.create_table(
        "isp_credit_scores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("credit_rating", sa.String(5), nullable=False),  # AAA, AA, A, BBB, BB, B, CCC
        sa.Column("probability_of_default", sa.Float),
        sa.Column("revenue_stability", sa.Float),  # 0-100
        sa.Column("growth_trajectory", sa.Float),  # 0-100
        sa.Column("market_position", sa.Float),  # 0-100
        sa.Column("infrastructure_quality", sa.Float),  # 0-100
        sa.Column("regulatory_compliance", sa.Float),  # 0-100
        sa.Column("debt_service_ratio", sa.Float),
        sa.Column("subscriber_concentration", sa.Float),  # HHI of geographic distribution
        sa.Column("composite_score", sa.Float),  # 0-100
        sa.Column("factors", JSONB),  # detailed breakdown
        sa.Column("computed_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_ics_provider ON isp_credit_scores (provider_id)")
    op.execute("CREATE INDEX idx_ics_rating ON isp_credit_scores (credit_rating)")

    # ── pgRouting: Add routing columns to road_segments ───────────────────
    op.add_column("road_segments", sa.Column("source", sa.BigInteger))
    op.add_column("road_segments", sa.Column("target", sa.BigInteger))
    op.add_column("road_segments", sa.Column("cost", sa.Float))
    op.add_column("road_segments", sa.Column("reverse_cost", sa.Float))

    # Set cost = length_m (bidirectional — all roads traversable both ways)
    op.execute("UPDATE road_segments SET cost = length_m, reverse_cost = length_m WHERE cost IS NULL")

    # Create indexes for routing columns
    op.execute("CREATE INDEX idx_rs_source ON road_segments (source)")
    op.execute("CREATE INDEX idx_rs_target ON road_segments (target)")

    # NOTE: pgr_createTopology must be run separately as it takes ~30 min
    # for 6.4M segments. Run via:
    #   psql -U enlace -d enlace -c "SELECT pgr_createTopology('road_segments', 0.00001, 'geom', 'id')"


def downgrade() -> None:
    # Drop routing columns
    op.execute("DROP INDEX IF EXISTS idx_rs_source")
    op.execute("DROP INDEX IF EXISTS idx_rs_target")
    op.drop_column("road_segments", "reverse_cost")
    op.drop_column("road_segments", "cost")
    op.drop_column("road_segments", "target")
    op.drop_column("road_segments", "source")

    # Drop tables in reverse order
    op.drop_table("isp_credit_scores")
    op.drop_table("pulso_scores")
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_table("subscriber_timeseries")
    op.drop_table("h3_cells")
    op.drop_table("tower_colocation_analysis")
    op.drop_table("coverage_validation")
    op.drop_table("opencellid_towers")
    op.drop_table("speedtest_municipality")
    op.drop_table("speedtest_tiles")
    op.drop_table("building_footprints")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS h3_postgis")
    op.execute("DROP EXTENSION IF EXISTS h3")
    op.execute("DROP EXTENSION IF EXISTS pgrouting")
