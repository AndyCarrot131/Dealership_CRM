import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class DealType(str, enum.Enum):
    cash = "cash"
    finance = "finance"
    lease = "lease"


class VehicleCondition(str, enum.Enum):
    new = "new"
    used = "used"
    demo = "demo"
    cpo = "cpo"


class PaymentFrequency(str, enum.Enum):
    weekly = "weekly"
    biweekly = "biweekly"
    semimonthly = "semimonthly"
    monthly = "monthly"


class DealSource(str, enum.Enum):
    photo = "photo"
    manual = "manual"


def _enum(py_enum: type[enum.Enum], name: str) -> sa.Enum:
    # values_callable so Postgres stores the values ('lease') not member names ('LEASE')
    return sa.Enum(py_enum, name=name, values_callable=lambda e: [m.value for m in e])


# Generic JSON on SQLite (tests), JSONB on Postgres
_JSONVariant = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 归属
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    sales_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))  # rep if a system user
    rep_name_raw: Mapped[Optional[str]] = mapped_column(Text)  # verbatim, e.g. 'Quinn West'
    dealership: Mapped[Optional[str]] = mapped_column(Text)  # e.g. "O'Regan's VW Halifax"

    # 交易性质与时间（成交时间以 contract_date 为准）
    deal_type: Mapped[DealType] = mapped_column(_enum(DealType, "deal_type"), nullable=False)
    contract_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    first_payment_date: Mapped[Optional[date]] = mapped_column(Date)

    # 车辆标识
    make: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    trim_base: Mapped[Optional[str]] = mapped_column(Text)  # drift 匹配键
    trim_package: Mapped[Optional[str]] = mapped_column(Text)
    model_code: Mapped[Optional[str]] = mapped_column(Text)  # catalog 强匹配键
    vin: Mapped[Optional[str]] = mapped_column(Text)
    stock_number: Mapped[Optional[str]] = mapped_column(Text)
    condition: Mapped[VehicleCondition] = mapped_column(
        _enum(VehicleCondition, "vehicle_condition"), nullable=False, default=VehicleCondition.new
    )
    odometer_at_deal: Mapped[Optional[int]] = mapped_column()
    exterior_color: Mapped[Optional[str]] = mapped_column(Text)
    engine: Mapped[Optional[str]] = mapped_column(Text)
    transmission: Mapped[Optional[str]] = mapped_column(Text)
    drivetrain: Mapped[Optional[str]] = mapped_column(Text)

    # 价格核心（行级明细在 deal_line_items）
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    options_adjustment: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # 可负
    selling_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    fees_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    tax_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    capital_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # lease: Capital Cost; finance: Balance to Finance
    total_with_tax: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # 首付结构
    cash_down: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    trade_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    cap_reduction: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    drive_off_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # 融资/租赁共同条款
    lender: Mapped[Optional[str]] = mapped_column(Text)
    # ⚠ rate_pct: 0 与 NULL 语义不同 — 0 = 0% 促销利率，NULL = 未知/未抽到。Never coerce.
    rate_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    # Sheet row "Term" (e.g. 48). Distinct from num_payments (e.g. 104 bi-weekly).
    term: Mapped[Optional[int]] = mapped_column(SmallInteger)
    payment_frequency: Mapped[Optional[PaymentFrequency]] = mapped_column(
        _enum(PaymentFrequency, "payment_frequency")
    )
    num_payments: Mapped[Optional[int]] = mapped_column(SmallInteger)
    base_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # 税前
    payment_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # 客户体感数字

    # lease 专属（finance/cash 为 NULL，见 CHECK）
    residual_msrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    residual_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    residual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    buy_option_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    km_per_year: Mapped[Optional[int]] = mapped_column()
    excess_km_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    security_deposit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # 溯源与审核（拍照管道）
    source: Mapped[DealSource] = mapped_column(
        _enum(DealSource, "deal_source"), nullable=False, default=DealSource.photo
    )
    source_image_path: Mapped[Optional[str]] = mapped_column(Text)
    extraction_raw: Mapped[Optional[dict]] = mapped_column(_JSONVariant)
    extraction_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    line_items: Mapped[List["DealLineItem"]] = relationship(
        "DealLineItem", back_populates="deal", cascade="all, delete-orphan"
    )
    trades: Mapped[List["DealTrade"]] = relationship(
        "DealTrade", back_populates="deal", cascade="all, delete-orphan"
    )
    customer: Mapped["Customer"] = relationship("Customer")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "deal_type = 'lease' OR "
            "(residual_pct IS NULL AND km_per_year IS NULL AND buy_option_price IS NULL)",
            name="lease_fields_only_for_lease",
        ),
        Index("idx_deals_vehicle", "make", "model", "model_year", "trim_base"),
        Index(
            "idx_deals_model_code",
            "model_code",
            postgresql_where=sa.text("model_code IS NOT NULL"),
        ),
        Index("idx_deals_contract_date", "contract_date"),
    )


# 行级明细：杂费 + 折扣（带符号金额：费用为正，折扣为负）
class DealLineItem(Base):
    __tablename__ = "deal_line_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(Text, nullable=False)  # 单上原文
    category: Mapped[Optional[str]] = mapped_column(
        String(30)
    )  # admin|gov_levy|protection|registration|discount|other
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    deal: Mapped["Deal"] = relationship("Deal", back_populates="line_items")


# 置换车辆（0..n 行）—— 客户的"上一辆车"
class DealTrade(Base):
    __tablename__ = "deal_trades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    make: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(Text)
    model_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    trim_base: Mapped[Optional[str]] = mapped_column(Text)
    vin: Mapped[Optional[str]] = mapped_column(Text)
    mileage: Mapped[Optional[int]] = mapped_column()
    exterior_color: Mapped[Optional[str]] = mapped_column(Text)
    allocation: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))  # 置换作价
    lien_payout: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    customer_car_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customer_car.id"))

    deal: Mapped["Deal"] = relationship("Deal", back_populates="trades")

    __table_args__ = (Index("idx_deal_trades_vehicle", "make", "model", "model_year"),)
