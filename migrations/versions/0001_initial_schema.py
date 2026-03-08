"""initial schema

Revision ID: 0001
Revises: None
Create Date: 2026-03-08

Full schema from infrastructure/init.sql including all 23 tables,
PostGIS extensions, indexes, and seed data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # === Geographic Entities ===

    op.create_table(
        "countries",
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_local", sa.String(100), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("regulator_name", sa.String(200)),
        sa.Column("regulator_url", sa.String(500)),
        sa.Column("national_crs", sa.Integer),
        sa.Column("timezone", sa.String(50)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    # Seed Brazil
    op.execute(
        "INSERT INTO countries (code, name, name_local, currency_code, language_code, "
        "regulator_name, regulator_url, national_crs, timezone) VALUES "
        "('BR', 'Brazil', 'Brasil', 'BRL', 'pt-BR', 'Anatel', "
        "'https://www.anatel.gov.br', 4674, 'America/Sao_Paulo')"
    )

    op.create_table(
        "admin_level_1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("abbrev", sa.String(10)),
        sa.Column("area_km2", sa.Float),
        sa.UniqueConstraint("country_code", "code"),
    )
    op.execute("SELECT AddGeometryColumn('admin_level_1', 'geom', 4326, 'MULTIPOLYGON', 2)")
    op.create_index("idx_al1_geom", "admin_level_1", ["geom"], postgresql_using="gist")
    op.create_index("idx_al1_country", "admin_level_1", ["country_code"])

    op.create_table(
        "admin_level_2",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("l1_id", sa.Integer, sa.ForeignKey("admin_level_1.id")),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("area_km2", sa.Float),
        sa.UniqueConstraint("country_code", "code"),
    )
    op.execute("SELECT AddGeometryColumn('admin_level_2', 'geom', 4326, 'MULTIPOLYGON', 2)")
    op.execute("SELECT AddGeometryColumn('admin_level_2', 'centroid', 4326, 'POINT', 2)")
    op.create_index("idx_al2_geom", "admin_level_2", ["geom"], postgresql_using="gist")
    op.create_index("idx_al2_l1", "admin_level_2", ["l1_id"])
    op.create_index("idx_al2_country", "admin_level_2", ["country_code"])

    op.create_table(
        "census_tracts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("area_km2", sa.Float),
        sa.Column("situation", sa.String(10)),
        sa.Column("tract_type", sa.String(50)),
        sa.UniqueConstraint("country_code", "code"),
    )
    op.execute("SELECT AddGeometryColumn('census_tracts', 'geom', 4326, 'MULTIPOLYGON', 2)")
    op.execute("SELECT AddGeometryColumn('census_tracts', 'centroid', 4326, 'POINT', 2)")
    op.create_index("idx_ct_geom", "census_tracts", ["geom"], postgresql_using="gist")
    op.create_index("idx_ct_l2", "census_tracts", ["l2_id"])
    op.create_index("idx_ct_country", "census_tracts", ["country_code"])

    # === Demographics ===

    op.create_table(
        "census_demographics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tract_id", sa.Integer, sa.ForeignKey("census_tracts.id")),
        sa.Column("census_year", sa.Integer, nullable=False),
        sa.Column("total_population", sa.Integer),
        sa.Column("total_households", sa.Integer),
        sa.Column("occupied_households", sa.Integer),
        sa.Column("avg_residents_per_household", sa.Numeric(4, 2)),
        sa.Column("income_data", JSONB),
        sa.Column("education_data", JSONB),
        sa.Column("housing_data", JSONB),
        sa.UniqueConstraint("tract_id", "census_year"),
    )
    op.create_index("idx_cd_tract", "census_demographics", ["tract_id"])

    op.create_table(
        "population_projections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("projected_population", sa.Integer),
        sa.Column("growth_rate", sa.Numeric(6, 4)),
        sa.Column("source", sa.String(100)),
        sa.UniqueConstraint("l2_id", "year"),
    )

    op.create_table(
        "economic_indicators",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("pib_municipal_brl", sa.Numeric(15, 2)),
        sa.Column("pib_per_capita_brl", sa.Numeric(10, 2)),
        sa.Column("formal_employment", sa.Integer),
        sa.Column("sector_breakdown", JSONB),
        sa.Column("source", sa.String(100)),
        sa.UniqueConstraint("l2_id", "year"),
    )

    # === Telecom Market ===

    op.create_table(
        "providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("name_normalized", sa.String(300), nullable=False),
        sa.Column("national_id", sa.String(30)),
        sa.Column("classification", sa.String(20)),
        sa.Column("services", JSONB),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("first_seen_date", sa.Date),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_prov_country", "providers", ["country_code"])

    op.create_table(
        "broadband_subscribers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("technology", sa.String(20), nullable=False),
        sa.Column("subscribers", sa.Integer, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_bs_provider", "broadband_subscribers", ["provider_id"])
    op.create_index("idx_bs_l2", "broadband_subscribers", ["l2_id"])
    op.create_index("idx_bs_yearmonth", "broadband_subscribers", ["year_month"])
    op.create_index("idx_bs_l2_ym", "broadband_subscribers", ["l2_id", "year_month"])

    op.create_table(
        "base_stations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("station_id", sa.String(50)),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("technology", sa.String(10), nullable=False),
        sa.Column("frequency_mhz", sa.Float),
        sa.Column("bandwidth_mhz", sa.Float),
        sa.Column("antenna_height_m", sa.Float),
        sa.Column("azimuth_degrees", sa.Float),
        sa.Column("mechanical_tilt", sa.Float),
        sa.Column("power_watts", sa.Float),
        sa.Column("authorization_date", sa.Date),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("raw_data", JSONB),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.execute(
        "SELECT AddGeometryColumn('base_stations', 'geom', 4326, 'POINT', 2)"
    )
    op.create_index("idx_bst_geom", "base_stations", ["geom"], postgresql_using="gist")
    op.create_index("idx_bst_provider", "base_stations", ["provider_id"])
    op.create_index("idx_bst_tech", "base_stations", ["technology"])
    op.create_index("idx_bst_country", "base_stations", ["country_code"])

    op.create_table(
        "spectrum_licenses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("frequency_start_mhz", sa.Float, nullable=False),
        sa.Column("frequency_end_mhz", sa.Float, nullable=False),
        sa.Column("bandwidth_mhz", sa.Float),
        sa.Column("geographic_area", sa.String(200)),
        sa.Column("license_type", sa.String(50)),
        sa.Column("grant_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("conditions", JSONB),
        sa.Column("source", sa.String(200)),
    )
    op.execute(
        "SELECT AddGeometryColumn('spectrum_licenses', 'geographic_geom', 4326, 'MULTIPOLYGON', 2)"
    )

    op.create_table(
        "quality_indicators",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("source", sa.String(100)),
    )
    op.create_index("idx_qi_l2_ym", "quality_indicators", ["l2_id", "year_month"])

    # === Terrain & Environment ===

    op.create_table(
        "terrain_tiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tile_name", sa.String(50), nullable=False),
        sa.Column("filepath", sa.String(500), nullable=False),
        sa.Column("resolution_m", sa.Float, nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger),
        sa.Column("loaded_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.execute("SELECT AddGeometryColumn('terrain_tiles', 'bbox', 4326, 'POLYGON', 2)")
    op.create_index("idx_tt_bbox", "terrain_tiles", ["bbox"], postgresql_using="gist")

    op.create_table(
        "land_cover",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("h3_index", sa.String(20), nullable=False),
        sa.Column("cover_type", sa.String(50), nullable=False),
        sa.Column("biome", sa.String(50)),
        sa.Column("cover_pct", sa.Float),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("source", sa.String(100)),
    )
    op.create_index("idx_lc_h3", "land_cover", ["h3_index"])
    op.create_index("idx_lc_biome", "land_cover", ["biome"])

    op.create_table(
        "biome_rf_corrections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("biome_type", sa.String(50), nullable=False),
        sa.Column("frequency_min_mhz", sa.Float, nullable=False),
        sa.Column("frequency_max_mhz", sa.Float, nullable=False),
        sa.Column("additional_loss_db_min", sa.Float, nullable=False),
        sa.Column("additional_loss_db_max", sa.Float, nullable=False),
        sa.Column("additional_loss_db_mean", sa.Float),
        sa.Column("additional_loss_db_stddev", sa.Float),
        sa.Column("measurement_distance_range", sa.String(50)),
        sa.Column("source_paper", sa.String(500), nullable=False),
        sa.Column("source_institution", sa.String(200)),
        sa.Column("source_year", sa.Integer),
        sa.Column("confidence", sa.String(20)),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "weather_stations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("station_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("elevation_m", sa.Float),
        sa.Column("station_type", sa.String(50)),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.UniqueConstraint("country_code", "station_code"),
    )
    op.execute("SELECT AddGeometryColumn('weather_stations', 'geom', 4326, 'POINT', 2)")
    op.create_index("idx_ws_geom", "weather_stations", ["geom"], postgresql_using="gist")

    op.create_table(
        "weather_observations",
        sa.Column("station_id", sa.Integer, sa.ForeignKey("weather_stations.id"), primary_key=True),
        sa.Column("observed_at", TIMESTAMP(timezone=True), primary_key=True),
        sa.Column("precipitation_mm", sa.Float),
        sa.Column("temperature_c", sa.Float),
        sa.Column("humidity_pct", sa.Float),
        sa.Column("wind_speed_ms", sa.Float),
        sa.Column("wind_direction_deg", sa.Float),
        sa.Column("pressure_hpa", sa.Float),
        sa.Column("solar_radiation_wm2", sa.Float),
    )

    # === Infrastructure Corridors ===

    op.create_table(
        "road_segments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("osm_id", sa.BigInteger),
        sa.Column("highway_class", sa.String(30)),
        sa.Column("name", sa.String(300)),
        sa.Column("surface_type", sa.String(30)),
        sa.Column("length_m", sa.Float),
    )
    op.execute("SELECT AddGeometryColumn('road_segments', 'geom', 4326, 'LINESTRING', 2)")
    op.create_index("idx_rs_geom", "road_segments", ["geom"], postgresql_using="gist")
    op.create_index("idx_rs_class", "road_segments", ["highway_class"])

    op.create_table(
        "power_lines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("voltage_kv", sa.Float),
        sa.Column("operator_name", sa.String(200)),
        sa.Column("line_type", sa.String(30)),
        sa.Column("source", sa.String(100)),
    )
    op.execute("SELECT AddGeometryColumn('power_lines', 'geom', 4326, 'LINESTRING', 2)")
    op.create_index("idx_pl_geom", "power_lines", ["geom"], postgresql_using="gist")

    op.create_table(
        "railways",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("operator_name", sa.String(200)),
        sa.Column("gauge_mm", sa.Integer),
        sa.Column("status", sa.String(20)),
        sa.Column("source", sa.String(100)),
    )
    op.execute("SELECT AddGeometryColumn('railways', 'geom', 4326, 'LINESTRING', 2)")
    op.create_index("idx_rw_geom", "railways", ["geom"], postgresql_using="gist")

    # === Computed Metrics ===

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), sa.ForeignKey("countries.code")),
        sa.Column("geographic_type", sa.String(20), nullable=False),
        sa.Column("geographic_id", sa.String(30), nullable=False),
        sa.Column("computed_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("demand_score", sa.Float),
        sa.Column("competition_score", sa.Float),
        sa.Column("infrastructure_score", sa.Float),
        sa.Column("growth_score", sa.Float),
        sa.Column("composite_score", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("features", JSONB),
        sa.Column("model_version", sa.String(50)),
    )
    op.execute("SELECT AddGeometryColumn('opportunity_scores', 'centroid', 4326, 'POINT', 2)")
    op.create_index("idx_os_geom", "opportunity_scores", ["centroid"], postgresql_using="gist")
    op.create_index("idx_os_composite", "opportunity_scores", [sa.text("composite_score DESC")])

    op.create_table(
        "competitive_analysis",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("computed_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("hhi_index", sa.Float),
        sa.Column("leader_provider_id", sa.Integer, sa.ForeignKey("providers.id")),
        sa.Column("leader_market_share", sa.Float),
        sa.Column("provider_details", JSONB),
        sa.Column("growth_trend", sa.String(20)),
        sa.Column("threat_level", sa.String(20)),
        sa.UniqueConstraint("l2_id", "year_month"),
    )

    # === Pipeline Tracking ===

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("pipeline_name", sa.String(100), nullable=False),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("completed_at", TIMESTAMP(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_processed", sa.Integer),
        sa.Column("rows_inserted", sa.Integer),
        sa.Column("rows_updated", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("metadata", JSONB),
    )

    # Log successful migration
    op.execute(
        "INSERT INTO pipeline_runs (pipeline_name, started_at, completed_at, status, metadata) "
        "VALUES ('alembic_initial', NOW(), NOW(), 'success', "
        "'{\"version\": \"1.0\", \"migration\": \"0001_initial_schema\"}')"
    )


def downgrade() -> None:
    op.drop_table("pipeline_runs")
    op.drop_table("competitive_analysis")
    op.drop_table("opportunity_scores")
    op.drop_table("railways")
    op.drop_table("power_lines")
    op.drop_table("road_segments")
    op.drop_table("weather_observations")
    op.drop_table("weather_stations")
    op.drop_table("biome_rf_corrections")
    op.drop_table("land_cover")
    op.drop_table("terrain_tiles")
    op.drop_table("quality_indicators")
    op.drop_table("spectrum_licenses")
    op.drop_table("base_stations")
    op.drop_table("broadband_subscribers")
    op.drop_table("providers")
    op.drop_table("economic_indicators")
    op.drop_table("population_projections")
    op.drop_table("census_demographics")
    op.drop_table("census_tracts")
    op.drop_table("admin_level_2")
    op.drop_table("admin_level_1")
    op.drop_table("countries")
