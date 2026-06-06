"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("assigned_sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(30)),
        sa.Column("note", sa.String(2000)),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "customer_car",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("make", sa.String(60)),
        sa.Column("model", sa.String(60)),
        sa.Column("year", sa.Integer()),
        sa.Column("ownership_type", sa.String(10)),
        sa.Column("lease_end_date", sa.Date()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("make", sa.String(60), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("trim", sa.String(60)),
        sa.Column("mileage", sa.Integer()),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("vin", sa.String(17), unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sample_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "style_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("style_md", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sales_id", "channel", name="uq_style_sales_channel"),
    )

    op.create_table(
        "outreach_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("compiled_filter", sa.JSON()),
        sa.Column("cadence_days", sa.Integer()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "email_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("outreach_rules.id", ondelete="SET NULL")),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("email_drafts")
    op.drop_table("outreach_rules")
    op.drop_table("style_profiles")
    op.drop_table("sample_messages")
    op.drop_table("inventory")
    op.drop_table("interactions")
    op.drop_table("customer_car")
    op.drop_table("customers")
    op.drop_table("users")
