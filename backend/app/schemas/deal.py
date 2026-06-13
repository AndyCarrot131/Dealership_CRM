from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, model_validator

DealTypeStr = Literal["cash", "finance", "lease"]
ConditionStr = Literal["new", "used", "demo", "cpo"]
FrequencyStr = Literal["weekly", "biweekly", "semimonthly", "monthly"]

_LEASE_ONLY = (
    "residual_msrp",
    "residual_pct",
    "residual_value",
    "buy_option_price",
    "km_per_year",
    "excess_km_rate",
    "security_deposit",
)


class DealLineItemIn(BaseModel):
    item_name: str
    category: Optional[str] = None
    amount: Decimal  # signed: fees positive, discounts negative


class DealLineItemOut(DealLineItemIn):
    id: int

    model_config = {"from_attributes": True}


class DealTradeIn(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    model_year: Optional[int] = None
    trim_base: Optional[str] = None
    vin: Optional[str] = None
    mileage: Optional[int] = None
    exterior_color: Optional[str] = None
    allocation: Optional[Decimal] = None
    lien_payout: Optional[Decimal] = Decimal("0")
    customer_car_id: Optional[int] = None


class DealTradeOut(DealTradeIn):
    id: int

    model_config = {"from_attributes": True}


class DealFieldsIn(BaseModel):
    deal_type: DealTypeStr
    contract_date: date
    delivery_date: Optional[date] = None
    first_payment_date: Optional[date] = None
    dealership: Optional[str] = None
    rep_name_raw: Optional[str] = None

    make: str
    model: str
    model_year: int
    trim_base: Optional[str] = None
    trim_package: Optional[str] = None
    model_code: Optional[str] = None
    vin: Optional[str] = None
    stock_number: Optional[str] = None
    condition: ConditionStr = "new"
    odometer_at_deal: Optional[int] = None
    exterior_color: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    drivetrain: Optional[str] = None

    base_price: Optional[Decimal] = None
    options_adjustment: Optional[Decimal] = None
    selling_price: Decimal
    discount: Optional[Decimal] = None
    fees_total: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    capital_cost: Optional[Decimal] = None
    total_with_tax: Optional[Decimal] = None

    cash_down: Optional[Decimal] = None
    trade_equity: Optional[Decimal] = None
    cap_reduction: Optional[Decimal] = None
    drive_off_total: Optional[Decimal] = None

    lender: Optional[str] = None
    # 0 and NULL differ: 0 = explicit 0% promo rate, None = not extracted/unknown
    rate_pct: Optional[Decimal] = None
    term: Optional[int] = None
    payment_frequency: Optional[FrequencyStr] = None
    num_payments: Optional[int] = None
    base_payment: Optional[Decimal] = None
    payment_amount: Optional[Decimal] = None

    residual_msrp: Optional[Decimal] = None
    residual_pct: Optional[Decimal] = None
    residual_value: Optional[Decimal] = None
    buy_option_price: Optional[Decimal] = None
    km_per_year: Optional[int] = None
    excess_km_rate: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None

    @model_validator(mode="after")
    def _null_lease_fields_for_non_lease(self) -> "DealFieldsIn":
        # DB CHECK lease_fields_only_for_lease: keep non-lease deals clean
        if self.deal_type != "lease":
            for field in _LEASE_ONLY:
                setattr(self, field, None)
        return self


class NewCustomerIn(BaseModel):
    full_name: str
    phone: Optional[str] = None
    email: Optional[str] = None


class CustomerRef(BaseModel):
    customer_id: Optional[int] = None
    new_customer: Optional[NewCustomerIn] = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "CustomerRef":
        if (self.customer_id is None) == (self.new_customer is None):
            raise ValueError("Provide exactly one of customer_id or new_customer")
        return self


class DealCreate(BaseModel):
    customer: CustomerRef
    deal: DealFieldsIn
    line_items: list[DealLineItemIn] = []
    trades: list[DealTradeIn] = []
    image_filename: Optional[str] = None
    extraction_raw: Optional[dict[str, Any]] = None
    extraction_confidence: Optional[Decimal] = None


class CustomerCandidate(BaseModel):
    id: int
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    matched_on: str  # "phone" | "email" | "name"


class ExtractResponse(BaseModel):
    extracted: dict[str, Any]  # cleaned fields incl. line_items/trades/customer/confidence
    raw: dict[str, Any]  # full model output — client echoes it back as extraction_raw
    candidates: list[CustomerCandidate]
    image_filename: str


class DealOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    sales_id: Optional[int] = None
    deal_type: str
    contract_date: date
    make: str
    model: str
    model_year: int
    trim_base: Optional[str] = None
    trim_package: Optional[str] = None
    selling_price: Decimal
    payment_amount: Optional[Decimal] = None
    payment_frequency: Optional[str] = None
    source: str
    extraction_confidence: Optional[Decimal] = None
    created_at: datetime


class DealDetailOut(DealOut):
    rep_name_raw: Optional[str] = None
    dealership: Optional[str] = None
    delivery_date: Optional[date] = None
    first_payment_date: Optional[date] = None
    model_code: Optional[str] = None
    vin: Optional[str] = None
    stock_number: Optional[str] = None
    condition: Optional[str] = None
    odometer_at_deal: Optional[int] = None
    exterior_color: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    drivetrain: Optional[str] = None
    base_price: Optional[Decimal] = None
    options_adjustment: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    fees_total: Optional[Decimal] = None
    tax_total: Optional[Decimal] = None
    capital_cost: Optional[Decimal] = None
    total_with_tax: Optional[Decimal] = None
    cash_down: Optional[Decimal] = None
    trade_equity: Optional[Decimal] = None
    cap_reduction: Optional[Decimal] = None
    drive_off_total: Optional[Decimal] = None
    lender: Optional[str] = None
    rate_pct: Optional[Decimal] = None
    term: Optional[int] = None
    num_payments: Optional[int] = None
    base_payment: Optional[Decimal] = None
    residual_msrp: Optional[Decimal] = None
    residual_pct: Optional[Decimal] = None
    residual_value: Optional[Decimal] = None
    buy_option_price: Optional[Decimal] = None
    km_per_year: Optional[int] = None
    excess_km_rate: Optional[Decimal] = None
    security_deposit: Optional[Decimal] = None
    source_image_path: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    line_items: list[DealLineItemOut] = []
    trades: list[DealTradeOut] = []
