from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.email_composer import compose_email
from app.agents.rule_parser import run_rule_parser
from app.auth.dependencies import get_current_user
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.models.customer import Customer
from app.models.interaction import Interaction
from app.models.inventory import Inventory
from app.models.outreach import EmailDraft, OutreachRule
from app.models.style import StyleExtraRule, StyleProfile
from app.models.user import User
from app.services.filter_compiler import compile_filter, preview_sql

router = APIRouter(tags=["outreach"])


# ─── Schemas ─────────────────────────────────────────────────────────────────


class RuleCreate(BaseModel):
    name: str
    rule_text: str
    cadence_days: Optional[int] = 30
    email_type: str = "lease_finance_ending"
    custom_template: Optional[str] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_text: Optional[str] = None
    cadence_days: Optional[int] = None
    active: Optional[bool] = None
    email_type: Optional[str] = None
    custom_template: Optional[str] = None


class RuleOut(BaseModel):
    id: int
    name: str
    rule_text: str
    compiled_filter: Optional[dict]
    sql_preview: Optional[str] = None
    cadence_days: Optional[int]
    active: bool
    email_type: str
    custom_template: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunRequest(BaseModel):
    email_type: Optional[str] = None
    custom_template: Optional[str] = None
    selected_customer_ids: Optional[list[int]] = None


class RunResult(BaseModel):
    drafts_created: int
    customer_ids: list[int]
    customers_matched: int
    style_guide_active: bool = False


class MatchedCarInfo(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership_type: Optional[str] = None
    lease_end_date: Optional[str] = None


class MatchedCustomer(BaseModel):
    id: int
    full_name: str
    note: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    cars: list[MatchedCarInfo] = []


class PreviewResult(BaseModel):
    customers: list[MatchedCustomer]
    style_guide_active: bool


class DraftOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_email: Optional[str]
    rule_id: Optional[int]
    subject: str
    body: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime]


class DraftEdit(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None


# ─── Rules ────────────────────────────────────────────────────────────────────


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await db.execute(
        select(OutreachRule)
        .where(OutreachRule.sales_id == current_user.id)
        .order_by(OutreachRule.created_at.desc())
    )
    return [_rule_to_dict(r) for r in result.scalars().all()]


@router.post("/rules", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> OutreachRule:
    compiled = await _parse_rule(body.rule_text, llm)
    rule = OutreachRule(
        sales_id=current_user.id,
        name=body.name.strip(),
        rule_text=body.rule_text.strip(),
        compiled_filter=compiled,
        cadence_days=body.cadence_days,
        email_type=body.email_type,
        custom_template=body.custom_template,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.put("/rules/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: int,
    body: RuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> OutreachRule:
    rule = await _fetch_rule(rule_id, current_user, db)

    if body.name is not None:
        rule.name = body.name.strip()
    if body.rule_text is not None:
        rule.rule_text = body.rule_text.strip()
        rule.compiled_filter = await _parse_rule(body.rule_text, llm)
    if body.cadence_days is not None:
        rule.cadence_days = body.cadence_days
    if body.active is not None:
        rule.active = body.active
    if body.email_type is not None:
        rule.email_type = body.email_type
    if body.custom_template is not None:
        rule.custom_template = body.custom_template or None

    await db.commit()
    await db.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    rule = await _fetch_rule(rule_id, current_user, db)
    await db.delete(rule)
    await db.commit()


@router.get("/rules/{rule_id}/preview", response_model=PreviewResult)
async def preview_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewResult:
    rule = await _fetch_rule(rule_id, current_user, db)
    if rule.compiled_filter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rule has no compiled filter. Save the rule first.",
        )
    customers = await _match_customers(rule, current_user.id, db)
    style_active = await _check_style_active(current_user.id, db)
    return PreviewResult(
        customers=[_customer_to_matched(c) for c in customers],
        style_guide_active=style_active,
    )


@router.post("/rules/{rule_id}/run", response_model=RunResult)
async def run_rule(
    rule_id: int,
    body: RunRequest = Body(default=RunRequest()),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> RunResult:
    rule = await _fetch_rule(rule_id, current_user, db)

    if rule.compiled_filter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Rule has no compiled filter. Save the rule first.",
        )

    effective_email_type = body.email_type or rule.email_type
    effective_template = (
        body.custom_template if body.custom_template is not None else rule.custom_template
    )

    customers = await _match_customers(rule, current_user.id, db)
    if body.selected_customer_ids is not None:
        selected_ids = {int(cid) for cid in body.selected_customer_ids}
        customers = [c for c in customers if c.id in selected_ids]
    style_md = await _fetch_style_md(current_user.id, db)
    style_extra_rules = await _fetch_style_extra_rules(current_user.id, db)
    style_guide_active = bool(style_md)

    customer_ids = [c.id for c in customers]
    interactions_by_customer: dict[int, list] = {}
    if customer_ids:
        inter_result = await db.execute(
            select(Interaction)
            .where(Interaction.customer_id.in_(customer_ids))
            .where(Interaction.sales_id == current_user.id)
            .order_by(Interaction.contacted_at.desc())
        )
        for inter in inter_result.scalars().all():
            interactions_by_customer.setdefault(inter.customer_id, []).append(inter)

    inventory_result = await db.execute(
        select(Inventory).where(Inventory.status == "available").limit(20)
    )
    inventory_items = inventory_result.scalars().all()
    inventory_dicts = [
        {
            "id": inv.id,
            "make": inv.make,
            "model": inv.model,
            "year": inv.year,
            "trim": inv.trim,
            "price": float(inv.price) if inv.price else None,
        }
        for inv in inventory_items
    ]

    created_ids: list[int] = []
    for customer in customers:
        customer_dict = {
            "id": customer.id,
            "full_name": customer.full_name,
            "phone": customer.phone,
            "note": customer.note,
            "cars": [
                {
                    "make": car.make,
                    "model": car.model,
                    "year": car.year,
                    "ownership_type": car.ownership_type,
                    "lease_end_date": str(car.lease_end_date) if car.lease_end_date else None,
                }
                for car in customer.cars
            ],
            "interactions": [
                {
                    "channel": i.channel,
                    "date": i.contacted_at.strftime("%Y-%m-%d"),
                    "summary": i.summary,
                }
                for i in interactions_by_customer.get(customer.id, [])
            ],
        }
        matching_inv = _match_inventory(customer_dict, inventory_dicts)
        try:
            email = await compose_email(
                customer_dict,
                matching_inv,
                style_md,
                llm,
                extra_rules=style_extra_rules,
                email_type=effective_email_type,
                custom_template=effective_template,
            )
        except Exception:
            continue

        draft = EmailDraft(
            sales_id=current_user.id,
            customer_id=customer.id,
            rule_id=rule.id,
            subject=email["subject"],
            body=email["body"],
            status="pending",
        )
        db.add(draft)
        created_ids.append(customer.id)

    await db.commit()
    return RunResult(
        drafts_created=len(created_ids),
        customer_ids=created_ids,
        customers_matched=len(customers),
        style_guide_active=style_guide_active,
    )


# ─── Drafts ───────────────────────────────────────────────────────────────────


@router.get("/drafts", response_model=list[DraftOut])
async def list_drafts(
    draft_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = (
        select(EmailDraft)
        .options(selectinload(EmailDraft.customer))
        .where(EmailDraft.sales_id == current_user.id)
        .order_by(EmailDraft.created_at.desc())
    )
    if draft_status is not None:
        q = q.where(EmailDraft.status == draft_status)
    result = await db.execute(q)
    drafts = result.scalars().all()
    return [_draft_to_dict(d) for d in drafts]


@router.patch("/drafts/{draft_id}", response_model=DraftOut)
async def edit_draft(
    draft_id: int,
    body: DraftEdit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    draft = await _fetch_draft(draft_id, current_user, db)
    if body.subject is not None:
        draft.subject = body.subject
    if body.body is not None:
        draft.body = body.body
    await db.commit()
    await db.refresh(draft, ["customer"])
    return _draft_to_dict(draft)


@router.post("/drafts/{draft_id}/approve", response_model=DraftOut)
async def approve_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    draft = await _fetch_draft(draft_id, current_user, db)
    if draft.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Draft is already {draft.status}",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    draft.status = "approved"
    draft.approved_at = now

    customer_result = await db.execute(
        select(Customer).where(Customer.id == draft.customer_id)
    )
    customer = customer_result.scalar_one_or_none()
    if customer:
        customer.last_contacted_at = now

    interaction = Interaction(
        customer_id=draft.customer_id,
        sales_id=current_user.id,
        channel="email",
        summary=f"Outreach email approved: {draft.subject}",
        contacted_at=now,
    )
    db.add(interaction)

    await db.commit()
    await db.refresh(draft, ["customer"])
    return _draft_to_dict(draft)


@router.post("/drafts/{draft_id}/dismiss", response_model=DraftOut)
async def dismiss_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    draft = await _fetch_draft(draft_id, current_user, db)
    if draft.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Draft is already {draft.status}",
        )
    draft.status = "dismissed"
    await db.commit()
    await db.refresh(draft, ["customer"])
    return _draft_to_dict(draft)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _rule_to_dict(rule: OutreachRule) -> dict:
    base = RuleOut.model_validate(rule).model_dump()
    if rule.compiled_filter:
        base["sql_preview"] = preview_sql(rule.compiled_filter)
    return base


async def _parse_rule(rule_text: str, llm: LLMClient) -> dict:
    try:
        return await run_rule_parser(rule_text, llm)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse rule: {exc}",
        )


async def _fetch_rule(rule_id: int, current_user: User, db: AsyncSession) -> OutreachRule:
    result = await db.execute(select(OutreachRule).where(OutreachRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if rule.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return rule


async def _fetch_draft(draft_id: int, current_user: User, db: AsyncSession) -> EmailDraft:
    result = await db.execute(
        select(EmailDraft)
        .options(selectinload(EmailDraft.customer))
        .where(EmailDraft.id == draft_id)
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if draft.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return draft


def _draft_to_dict(draft: EmailDraft) -> dict:
    return {
        "id": draft.id,
        "customer_id": draft.customer_id,
        "customer_name": draft.customer.full_name if draft.customer else "",
        "customer_email": draft.customer.email if draft.customer else None,
        "rule_id": draft.rule_id,
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
        "created_at": draft.created_at,
        "approved_at": draft.approved_at,
    }


async def _match_customers(
    rule: OutreachRule, sales_id: int, db: AsyncSession
) -> list[Customer]:
    where_clause = compile_filter(rule.compiled_filter)
    cadence_cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=rule.cadence_days)
        if rule.cadence_days
        else None
    )
    q = (
        select(Customer)
        .options(selectinload(Customer.cars))
        .where(Customer.assigned_sales_id == sales_id)
        .where(where_clause)
    )
    if cadence_cutoff is not None:
        q = q.where(
            or_(
                Customer.last_contacted_at.is_(None),
                Customer.last_contacted_at < cadence_cutoff,
            )
        )
    result = await db.execute(q)
    return list(result.scalars().all())


async def _check_style_active(sales_id: int, db: AsyncSession) -> bool:
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.sales_id == sales_id,
            StyleProfile.channel == "email",
        )
    )
    profile = result.scalar_one_or_none()
    return bool(profile and profile.style_md)


async def _fetch_style_md(sales_id: int, db: AsyncSession) -> str:
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.sales_id == sales_id,
            StyleProfile.channel == "email",
        )
    )
    profile = result.scalar_one_or_none()
    return profile.style_md if profile else ""


async def _fetch_style_extra_rules(sales_id: int, db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(StyleExtraRule)
        .where(StyleExtraRule.sales_id == sales_id)
        .where(StyleExtraRule.active.is_(True))
        .where(StyleExtraRule.channel.in_(("email", "both")))
        .order_by(StyleExtraRule.created_at.asc())
    )
    return [r.rule_text.strip() for r in result.scalars().all() if (r.rule_text or "").strip()]


def _customer_to_matched(customer: Customer) -> MatchedCustomer:
    return MatchedCustomer(
        id=customer.id,
        full_name=customer.full_name,
        note=customer.note,
        last_contacted_at=customer.last_contacted_at,
        cars=[
            MatchedCarInfo(
                make=car.make,
                model=car.model,
                year=car.year,
                ownership_type=car.ownership_type,
                lease_end_date=str(car.lease_end_date) if car.lease_end_date else None,
            )
            for car in customer.cars
        ],
    )


def _match_inventory(
    customer: dict,
    inventory: list[dict],
) -> list[dict]:
    customer_makes = {
        (car.get("make") or "").lower()
        for car in customer.get("cars", [])
        if car.get("make")
    }
    if customer_makes:
        matched = [i for i in inventory if (i.get("make") or "").lower() in customer_makes]
        if matched:
            return matched[:3]
    return inventory[:3]
