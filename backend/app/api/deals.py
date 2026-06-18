import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.deal_extractor import run_deal_extractor
from app.auth.dependencies import get_current_user
from app.config import settings
from app.db import get_db
from app.llm.client import LLMClient
from app.services.llm_config import resolve_llm_config, resolve_llm_profile_config
from app.models.customer import Customer, CustomerCar
from app.models.deal import Deal, DealLineItem, DealTrade
from app.models.user import User
from app.schemas.deal import (
    CustomerCandidate,
    DealCreate,
    DealDetailOut,
    DealOut,
    ExtractResponse,
)
from app.services.deal_dates import compute_contract_end_date

router = APIRouter(tags=["deals"])

_ALLOWED_MIMES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _uploads_dir() -> Path:
    # backend/uploads/deals/
    d = Path(__file__).resolve().parent.parent.parent / settings.uploads_dir / "deals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_image_path(filename: str) -> Path:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image filename"
        )
    return _uploads_dir() / filename


def _normalize_phone(phone: Optional[str]) -> str:
    return re.sub(r"\D", "", phone or "")


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


async def _match_customer_candidates(
    db: AsyncSession, user: User, extracted_customer: dict[str, Any]
) -> list[CustomerCandidate]:
    """Match-or-create support: exact phone/email matches first, then name ILIKE."""
    name = (extracted_customer.get("name") or "").strip()
    phone_digits = _normalize_phone(extracted_customer.get("phone"))
    email = (extracted_customer.get("email") or "").strip().lower()

    scoped = select(Customer)
    if user.role != "manager":
        scoped = scoped.where(Customer.assigned_sales_id == user.id)

    candidates: dict[int, CustomerCandidate] = {}

    if phone_digits:
        result = await db.execute(scoped.where(Customer.phone.is_not(None)))
        for c in result.scalars().all():
            if _normalize_phone(c.phone) == phone_digits:
                candidates[c.id] = CustomerCandidate(
                    id=c.id, full_name=c.full_name, email=c.email, phone=c.phone,
                    matched_on="phone",
                )

    if email:
        result = await db.execute(scoped.where(func.lower(Customer.email) == email))
        for c in result.scalars().all():
            candidates.setdefault(
                c.id,
                CustomerCandidate(
                    id=c.id, full_name=c.full_name, email=c.email, phone=c.phone,
                    matched_on="email",
                ),
            )

    if name:
        # Try the full name plus first/last tokens to tolerate middle initials
        tokens = [name] + ([name.split()[0], name.split()[-1]] if " " in name else [])
        clauses = [Customer.full_name.ilike(f"%{t}%") for t in tokens]
        result = await db.execute(scoped.where(or_(*clauses)).limit(10))
        for c in result.scalars().all():
            candidates.setdefault(
                c.id,
                CustomerCandidate(
                    id=c.id, full_name=c.full_name, email=c.email, phone=c.phone,
                    matched_on="name",
                ),
            )

    ordered = sorted(candidates.values(), key=lambda c: {"phone": 0, "email": 1, "name": 2}[c.matched_on])
    return ordered[:5]


def _deal_to_dict(deal: Deal, detail: bool = False) -> dict[str, Any]:
    base = {
        "id": deal.id,
        "customer_id": deal.customer_id,
        "customer_name": deal.customer.full_name,
        "sales_id": deal.sales_id,
        "deal_type": deal.deal_type,
        "contract_date": deal.contract_date,
        "make": deal.make,
        "model": deal.model,
        "model_year": deal.model_year,
        "trim_base": deal.trim_base,
        "trim_package": deal.trim_package,
        "selling_price": deal.selling_price,
        "payment_amount": deal.payment_amount,
        "payment_frequency": deal.payment_frequency,
        "source": deal.source,
        "extraction_confidence": deal.extraction_confidence,
        "created_at": deal.created_at,
    }
    if not detail:
        return base
    base.update(
        {
            "rep_name_raw": deal.rep_name_raw,
            "dealership": deal.dealership,
            "delivery_date": deal.delivery_date,
            "first_payment_date": deal.first_payment_date,
            "model_code": deal.model_code,
            "vin": deal.vin,
            "stock_number": deal.stock_number,
            "condition": deal.condition,
            "odometer_at_deal": deal.odometer_at_deal,
            "exterior_color": deal.exterior_color,
            "engine": deal.engine,
            "transmission": deal.transmission,
            "drivetrain": deal.drivetrain,
            "base_price": deal.base_price,
            "options_adjustment": deal.options_adjustment,
            "discount": deal.discount,
            "fees_total": deal.fees_total,
            "tax_total": deal.tax_total,
            "capital_cost": deal.capital_cost,
            "total_with_tax": deal.total_with_tax,
            "cash_down": deal.cash_down,
            "trade_equity": deal.trade_equity,
            "cap_reduction": deal.cap_reduction,
            "drive_off_total": deal.drive_off_total,
            "lender": deal.lender,
            "rate_pct": deal.rate_pct,
            "term": deal.term,
            "num_payments": deal.num_payments,
            "base_payment": deal.base_payment,
            "residual_msrp": deal.residual_msrp,
            "residual_pct": deal.residual_pct,
            "residual_value": deal.residual_value,
            "buy_option_price": deal.buy_option_price,
            "km_per_year": deal.km_per_year,
            "excess_km_rate": deal.excess_km_rate,
            "security_deposit": deal.security_deposit,
            "source_image_path": deal.source_image_path,
            "verified_by": deal.verified_by,
            "verified_at": deal.verified_at,
            "line_items": deal.line_items,
            "trades": deal.trades,
        }
    )
    return base


async def _get_deal_checked(
    db: AsyncSession, deal_id: int, user: User, detail: bool = False
) -> Deal:
    q = select(Deal).where(Deal.id == deal_id).options(selectinload(Deal.customer))
    if detail:
        q = q.options(selectinload(Deal.line_items), selectinload(Deal.trades))
    result = await db.execute(q)
    deal = result.scalar_one_or_none()
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    if user.role != "manager" and deal.customer.assigned_sales_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return deal


async def _llm_for_extract(
    profile_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LLMClient:
    if profile_id is not None:
        try:
            llm_config = await resolve_llm_profile_config(db, current_user.id, profile_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LLM profile not found",
            )
    else:
        llm_config = await resolve_llm_config(db, current_user.id)
    return LLMClient(llm_config)


@router.post("/extract", response_model=ExtractResponse)
async def extract_deal(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(_llm_for_extract),
) -> ExtractResponse:
    mime = (file.content_type or "").lower()
    if mime not in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported image type: {mime or 'unknown'} (use JPEG, PNG, or WebP)",
        )
    image_bytes = await file.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image too large (max 15 MB)",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty image upload"
        )

    # Never trust the client filename — generate an opaque one
    filename = f"{uuid4().hex}.{_ALLOWED_MIMES[mime]}"
    (_uploads_dir() / filename).write_bytes(image_bytes)

    try:
        result = await run_deal_extractor(image_bytes, mime, llm)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {exc}",
        )

    extracted = result["extracted"]
    end = compute_contract_end_date(
        extracted.get("deal_type"),
        _parse_iso_date(extracted.get("contract_date")),
        delivery_date=_parse_iso_date(extracted.get("delivery_date")),
        first_payment_date=_parse_iso_date(extracted.get("first_payment_date")),
        term=extracted.get("term"),
        num_payments=extracted.get("num_payments"),
    )
    if end is not None:
        extracted["contract_end_date"] = end.isoformat()
    candidates = await _match_customer_candidates(
        db, current_user, extracted.get("customer") or {}
    )
    return ExtractResponse(
        extracted=extracted,
        raw=result["raw"],
        candidates=candidates,
        image_filename=filename,
    )


@router.post("", response_model=DealDetailOut, status_code=status.HTTP_201_CREATED)
async def create_deal(
    body: DealCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    # Resolve customer: existing (ownership-checked) or match-or-create
    if body.customer.customer_id is not None:
        result = await db.execute(
            select(Customer).where(Customer.id == body.customer.customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    else:
        new = body.customer.new_customer
        customer = Customer(
            assigned_sales_id=current_user.id,
            full_name=new.full_name,
            phone=new.phone,
            email=new.email,
        )
        db.add(customer)
        await db.flush()

    source_image_path = None
    if body.image_filename:
        image_path = _safe_image_path(body.image_filename)
        if not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Uploaded image not found; re-run extraction",
            )
        source_image_path = body.image_filename

    fields = body.deal.model_dump()

    # Summary redundancy columns: fill from line items / trades when absent
    if fields.get("discount") is None:
        fields["discount"] = abs(sum((li.amount for li in body.line_items if li.amount < 0), Decimal("0")))
    if fields.get("fees_total") is None:
        fees = [li.amount for li in body.line_items if li.amount > 0 and li.category != "discount"]
        fields["fees_total"] = sum(fees, Decimal("0")) if fees else None
    if fields.get("trade_equity") is None and body.trades:
        fields["trade_equity"] = sum(
            ((t.allocation or Decimal("0")) - (t.lien_payout or Decimal("0")) for t in body.trades),
            Decimal("0"),
        )

    deal = Deal(
        customer_id=customer.id,
        sales_id=current_user.id,
        source="photo" if source_image_path else "manual",
        source_image_path=source_image_path,
        extraction_raw=body.extraction_raw,
        extraction_confidence=body.extraction_confidence,
        verified_by=current_user.id,
        verified_at=datetime.now(timezone.utc),
        **fields,
    )
    deal.line_items = [DealLineItem(**li.model_dump()) for li in body.line_items]
    deal.trades = [DealTrade(**tr.model_dump()) for tr in body.trades]
    db.add(deal)

    if fields.get("make") or fields.get("model") or fields.get("model_year"):
        deal_type = fields.get("deal_type") or ""
        ownership_type = {"cash": "own", "finance": "finance", "lease": "lease"}.get(deal_type)
        lease_end_date = compute_contract_end_date(
            deal_type,
            fields.get("contract_date"),
            delivery_date=fields.get("delivery_date"),
            first_payment_date=fields.get("first_payment_date"),
            term=fields.get("term"),
            num_payments=fields.get("num_payments"),
        )
        db.add(CustomerCar(
            customer_id=customer.id,
            make=fields.get("make"),
            model=fields.get("model"),
            year=fields.get("model_year"),
            ownership_type=ownership_type,
            lease_end_date=lease_end_date,
            is_primary=True,
        ))

    await db.commit()
    await db.refresh(deal, ["line_items", "trades", "customer"])
    return _deal_to_dict(deal, detail=True)


@router.get("", response_model=list[DealOut])
async def list_deals(
    customer_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = (
        select(Deal)
        .options(selectinload(Deal.customer))
        .order_by(Deal.contract_date.desc(), Deal.id.desc())
    )
    if current_user.role != "manager":
        # Scope through customer ownership — deals.sales_id may be NULL / a non-system rep
        q = q.join(Customer, Deal.customer_id == Customer.id).where(
            Customer.assigned_sales_id == current_user.id
        )
    if customer_id is not None:
        q = q.where(Deal.customer_id == customer_id)

    result = await db.execute(q)
    return [_deal_to_dict(d) for d in result.scalars().all()]


@router.get("/{deal_id}", response_model=DealDetailOut)
async def get_deal(
    deal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    deal = await _get_deal_checked(db, deal_id, current_user, detail=True)
    return _deal_to_dict(deal, detail=True)


@router.get("/{deal_id}/image")
async def get_deal_image(
    deal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    deal = await _get_deal_checked(db, deal_id, current_user)
    if not deal.source_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal has no source image")
    path = _safe_image_path(deal.source_image_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file missing")
    return FileResponse(path)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deal(
    deal_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    deal = await _get_deal_checked(db, deal_id, current_user)
    image_path = deal.source_image_path
    await db.delete(deal)
    await db.commit()
    if image_path:
        try:
            _safe_image_path(image_path).unlink(missing_ok=True)
        except HTTPException:
            pass  # legacy/bad path — nothing to remove
