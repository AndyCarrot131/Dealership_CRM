"""add deals, deal_line_items, deal_trades tables (DEAL_TABLE.md)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False so create_table doesn't try to re-create types; we create
# them explicitly with checkfirst in upgrade() and drop them in downgrade().
deal_type = postgresql.ENUM("cash", "finance", "lease", name="deal_type", create_type=False)
vehicle_condition = postgresql.ENUM(
    "new", "used", "demo", "cpo", name="vehicle_condition", create_type=False
)
payment_frequency = postgresql.ENUM(
    "weekly", "biweekly", "semimonthly", "monthly", name="payment_frequency", create_type=False
)
deal_source = postgresql.ENUM("photo", "manual", name="deal_source", create_type=False)

_ENUMS = (deal_type, vehicle_condition, payment_frequency, deal_source)


def upgrade() -> None:
    bind = op.get_bind()
    for e in _ENUMS:
        e.create(bind, checkfirst=True)

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        # 归属
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("sales_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rep_name_raw", sa.Text(), nullable=True),
        sa.Column("dealership", sa.Text(), nullable=True),
        # 交易性质与时间
        sa.Column("deal_type", deal_type, nullable=False),
        sa.Column("contract_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=True),
        sa.Column("first_payment_date", sa.Date(), nullable=True),
        # 车辆标识
        sa.Column("make", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("model_year", sa.SmallInteger(), nullable=False),
        sa.Column("trim_base", sa.Text(), nullable=True),
        sa.Column("trim_package", sa.Text(), nullable=True),
        sa.Column("model_code", sa.Text(), nullable=True),
        sa.Column("vin", sa.Text(), nullable=True),
        sa.Column("stock_number", sa.Text(), nullable=True),
        sa.Column("condition", vehicle_condition, nullable=False, server_default="new"),
        sa.Column("odometer_at_deal", sa.Integer(), nullable=True),
        sa.Column("exterior_color", sa.Text(), nullable=True),
        sa.Column("engine", sa.Text(), nullable=True),
        sa.Column("transmission", sa.Text(), nullable=True),
        sa.Column("drivetrain", sa.Text(), nullable=True),
        # 价格核心
        sa.Column("base_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("options_adjustment", sa.Numeric(10, 2), nullable=True),
        sa.Column("selling_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column("fees_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("tax_total", sa.Numeric(10, 2), nullable=True),
        sa.Column("capital_cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_with_tax", sa.Numeric(10, 2), nullable=True),
        # 首付结构
        sa.Column("cash_down", sa.Numeric(10, 2), nullable=True),
        sa.Column("trade_equity", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column("cap_reduction", sa.Numeric(10, 2), nullable=True),
        sa.Column("drive_off_total", sa.Numeric(10, 2), nullable=True),
        # 融资/租赁共同条款（rate_pct: 0 = 0% 促销，NULL = 未抽到）
        sa.Column("lender", sa.Text(), nullable=True),
        sa.Column("rate_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("term_months", sa.SmallInteger(), nullable=True),
        sa.Column("payment_frequency", payment_frequency, nullable=True),
        sa.Column("num_payments", sa.SmallInteger(), nullable=True),
        sa.Column("base_payment", sa.Numeric(10, 2), nullable=True),
        sa.Column("payment_amount", sa.Numeric(10, 2), nullable=True),
        # lease 专属
        sa.Column("residual_msrp", sa.Numeric(10, 2), nullable=True),
        sa.Column("residual_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("residual_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("buy_option_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("km_per_year", sa.Integer(), nullable=True),
        sa.Column("excess_km_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("security_deposit", sa.Numeric(10, 2), nullable=True),
        # 溯源与审核
        sa.Column("source", deal_source, nullable=False, server_default="photo"),
        sa.Column("source_image_path", sa.Text(), nullable=True),
        sa.Column("extraction_raw", postgresql.JSONB(), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "deal_type = 'lease' OR "
            "(residual_pct IS NULL AND km_per_year IS NULL AND buy_option_price IS NULL)",
            name="lease_fields_only_for_lease",
        ),
    )

    op.create_table(
        "deal_line_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_name", sa.Text(), nullable=False),
        sa.Column("category", sa.String(30), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
    )

    op.create_table(
        "deal_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "deal_id",
            sa.Integer(),
            sa.ForeignKey("deals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("make", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("model_year", sa.SmallInteger(), nullable=True),
        sa.Column("trim_base", sa.Text(), nullable=True),
        sa.Column("vin", sa.Text(), nullable=True),
        sa.Column("mileage", sa.Integer(), nullable=True),
        sa.Column("exterior_color", sa.Text(), nullable=True),
        sa.Column("allocation", sa.Numeric(10, 2), nullable=True),
        sa.Column("lien_payout", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column(
            "customer_car_id", sa.Integer(), sa.ForeignKey("customer_car.id"), nullable=True
        ),
    )

    # 索引：按使用路径设计
    op.create_index("ix_deals_customer_id", "deals", ["customer_id"])
    op.create_index("idx_deals_vehicle", "deals", ["make", "model", "model_year", "trim_base"])
    op.create_index(
        "idx_deals_model_code",
        "deals",
        ["model_code"],
        postgresql_where=sa.text("model_code IS NOT NULL"),
    )
    op.create_index("idx_deals_contract_date", "deals", ["contract_date"])
    op.create_index("ix_deal_line_items_deal_id", "deal_line_items", ["deal_id"])
    op.create_index("ix_deal_trades_deal_id", "deal_trades", ["deal_id"])
    op.create_index("idx_deal_trades_vehicle", "deal_trades", ["make", "model", "model_year"])


def downgrade() -> None:
    op.drop_table("deal_trades")
    op.drop_table("deal_line_items")
    op.drop_table("deals")
    bind = op.get_bind()
    for e in _ENUMS:
        e.drop(bind, checkfirst=True)
