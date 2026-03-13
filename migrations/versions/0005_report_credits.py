"""report credits and purchases

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-11

Adds tables for: report credit tracking and purchase history for
the freemium/paywall monetization model.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Report credits — tracks available credits per tenant
    op.create_table(
        "report_credits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(100), nullable=False, unique=True),
        sa.Column("credits_total", sa.Integer(), server_default="0"),
        sa.Column("credits_used", sa.Integer(), server_default="0"),
        sa.Column("plan_monthly_credits", sa.Integer(), server_default="0"),
        sa.Column("last_refill_date", sa.Date(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    # Report purchases — individual report unlock records
    op.create_table(
        "report_purchases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("report_type", sa.String(100), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=True),
        sa.Column("municipality_id", sa.Integer(), nullable=True),
        sa.Column("credits_spent", sa.Integer(), server_default="1"),
        sa.Column("unlocked_data", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_index("ix_report_credits_tenant", "report_credits", ["tenant_id"])
    op.create_index("ix_report_purchases_tenant", "report_purchases", ["tenant_id"])
    op.create_index("ix_report_purchases_user", "report_purchases", ["user_id"])


def downgrade() -> None:
    op.drop_table("report_purchases")
    op.drop_table("report_credits")
