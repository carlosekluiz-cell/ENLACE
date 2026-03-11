"""wave 2 feature tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-11

Adds tables for: spectrum holdings, RGST 777 compliance, 5G coverage obligations,
peering networks, peering IXPs, IXP locations, IXP traffic history.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Spectrum Holdings ──────────────────────────────────────────────
    op.create_table(
        "spectrum_holdings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("frequency_mhz", sa.Float, nullable=False),
        sa.Column("bandwidth_mhz", sa.Float),
        sa.Column("band_name", sa.String(50)),
        sa.Column("license_expiry", sa.Date),
        sa.Column("coverage_area_km2", sa.Float),
        sa.Column("population_covered", sa.BigInteger),
        sa.Column("license_type", sa.String(50)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_sh_provider ON spectrum_holdings (provider_id)")
    op.execute("CREATE INDEX idx_sh_freq ON spectrum_holdings (frequency_mhz)")

    # ── RGST 777 Compliance ────────────────────────────────────────────
    op.create_table(
        "rgst777_compliance",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("obligation_category", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),  # pass, fail, warning
        sa.Column("detail", sa.Text),
        sa.Column("evidence_source", sa.String(200)),
        sa.Column("checked_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_rgst_provider ON rgst777_compliance (provider_id)")
    op.execute("CREATE INDEX idx_rgst_status ON rgst777_compliance (status)")

    # ── 5G Coverage Obligations ────────────────────────────────────────
    op.create_table(
        "coverage_obligations_5g",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("provider_name", sa.String(200), nullable=False),
        sa.Column("obligation_tier", sa.String(50), nullable=False),
        sa.Column("deadline_date", sa.Date, nullable=False),
        sa.Column("l2_id", sa.Integer, sa.ForeignKey("admin_level_2.id")),
        sa.Column("requirement_description", sa.Text),
        sa.Column("actual_coverage", sa.Float),  # 0-100 pct
        sa.Column("target_coverage", sa.Float),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_co5g_provider ON coverage_obligations_5g (provider_name)")
    op.execute("CREATE INDEX idx_co5g_deadline ON coverage_obligations_5g (deadline_date)")

    # ── Peering Networks (PeeringDB) ───────────────────────────────────
    op.create_table(
        "peering_networks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("asn", sa.BigInteger, nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("aka", sa.String(300)),
        sa.Column("irr_as_set", sa.String(200)),
        sa.Column("info_type", sa.String(50)),  # NSP, Content, Enterprise
        sa.Column("info_prefixes4", sa.Integer),
        sa.Column("info_prefixes6", sa.Integer),
        sa.Column("policy_general", sa.String(50)),  # Open, Selective, Restrictive
        sa.Column("policy_url", sa.Text),
        sa.Column("website", sa.Text),
        sa.Column("info_traffic", sa.String(50)),
        sa.Column("info_scope", sa.String(50)),
        sa.Column("country", sa.String(10)),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_pn_country ON peering_networks (country)")

    # ── Peering IXPs (PeeringDB) ───────────────────────────────────────
    op.create_table(
        "peering_ixps",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("peeringdb_id", sa.Integer, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("name_long", sa.String(500)),
        sa.Column("city", sa.String(200)),
        sa.Column("country", sa.String(10)),
        sa.Column("region_continent", sa.String(50)),
        sa.Column("participants_count", sa.Integer),
        sa.Column("website", sa.Text),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )
    op.execute("CREATE INDEX idx_pixp_country ON peering_ixps (country)")

    # ── IX.br IXP Locations ────────────────────────────────────────────
    op.create_table(
        "ixp_locations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("city", sa.String(200)),
        sa.Column("state", sa.String(5)),
        sa.Column("traffic_gbps", sa.Float),
        sa.Column("participants", sa.Integer),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
    )

    # ── IX.br IXP Traffic History ──────────────────────────────────────
    op.create_table(
        "ixp_traffic_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ixp_code", sa.String(20), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("peak_traffic_gbps", sa.Float),
        sa.Column("avg_traffic_gbps", sa.Float),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("ixp_code", "date", name="uq_ixp_traffic_date"),
    )
    op.execute("CREATE INDEX idx_ith_code ON ixp_traffic_history (ixp_code)")
    op.execute("CREATE INDEX idx_ith_date ON ixp_traffic_history (date)")


def downgrade() -> None:
    op.drop_table("ixp_traffic_history")
    op.drop_table("ixp_locations")
    op.drop_table("peering_ixps")
    op.drop_table("peering_networks")
    op.drop_table("coverage_obligations_5g")
    op.drop_table("rgst777_compliance")
    op.drop_table("spectrum_holdings")
