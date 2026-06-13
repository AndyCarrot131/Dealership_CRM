from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.assistant import run_assistant
from app.agents.intake import run_intake
from app.agents.update import run_update
from app.auth.dependencies import get_current_user
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.models.customer import Customer, CustomerCar
from app.models.user import User

router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    mode: str = "intake"
    customer_id: Optional[int] = None


class PendingDraft(BaseModel):
    customer_id: int
    customer_name: str
    subject: str
    body: str


class PendingLog(BaseModel):
    customer_id: int
    customer_name: str
    channel: str
    summary: str
    contacted_at: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    intent: str
    pending_fields: Optional[dict[str, Any]] = None
    pending_draft: Optional[PendingDraft] = None
    pending_log: Optional[PendingLog] = None


class ConfirmRequest(BaseModel):
    mode: str = "intake"
    customer_id: Optional[int] = None
    fields: Optional[dict[str, Any]] = None
    diff: Optional[dict[str, Any]] = None


class CarOut(BaseModel):
    id: int
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    ownership_type: Optional[str]
    lease_end_date: Optional[date]
    is_primary: bool

    model_config = {"from_attributes": True}


class CustomerOut(BaseModel):
    id: int
    assigned_sales_id: int
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    note: Optional[str]
    cars: list[CarOut] = []

    model_config = {"from_attributes": True}


def _customer_snapshot(customer: Customer) -> dict[str, Any]:
    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "email": customer.email,
        "phone": customer.phone,
        "note": customer.note,
        "cars": [
            {
                "id": car.id,
                "make": car.make,
                "model": car.model,
                "year": car.year,
                "ownership_type": car.ownership_type,
                "lease_end_date": str(car.lease_end_date) if car.lease_end_date else None,
                "is_primary": car.is_primary,
            }
            for car in customer.cars
        ],
    }


async def _fetch_owned_customer(
    customer_id: int,
    current_user: User,
    db: AsyncSession,
) -> Customer:
    result = await db.execute(
        select(Customer).options(selectinload(Customer.cars)).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return customer


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
    history = [{"role": m.role, "content": m.content} for m in body.history]
    history.append({"role": "user", "content": body.message})

    try:
        if body.mode == "assistant":
            result = await run_assistant(history, current_user, db, llm)
            return ChatResponse(
                reply=result["reply"],
                intent=result["intent"],
                pending_draft=(
                    PendingDraft(**result["pending_draft"])
                    if result.get("pending_draft")
                    else None
                ),
                pending_log=(
                    PendingLog(**result["pending_log"])
                    if result.get("pending_log")
                    else None
                ),
            )
        elif body.mode == "update":
            if body.customer_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="customer_id is required for update mode",
                )
            customer = await _fetch_owned_customer(body.customer_id, current_user, db)
            snapshot = _customer_snapshot(customer)
            result = await run_update(history, snapshot, llm)
            return ChatResponse(
                reply=result["reply"],
                intent=result["intent"],
                pending_fields=result.get("diff"),
            )
        else:
            result = await run_intake(history, llm)
            return ChatResponse(
                reply=result["reply"],
                intent=result["intent"],
                pending_fields=result.get("fields"),
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {exc}",
        )


@router.post("/confirm", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def confirm(
    body: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    if body.mode == "update":
        return await _confirm_update(body, current_user, db)
    return await _confirm_intake(body, current_user, db)


async def _confirm_intake(
    body: ConfirmRequest,
    current_user: User,
    db: AsyncSession,
) -> Customer:
    fields = body.fields or {}
    if not fields.get("full_name"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="full_name is required",
        )

    customer = Customer(
        assigned_sales_id=current_user.id,
        full_name=fields["full_name"],
        email=fields.get("email") or None,
        phone=fields.get("phone") or None,
        note=fields.get("note") or None,
    )
    db.add(customer)
    await db.flush()

    if fields.get("car_make") or fields.get("car_model"):
        car = CustomerCar(
            customer_id=customer.id,
            make=fields.get("car_make"),
            model=fields.get("car_model"),
            year=fields.get("car_year"),
            ownership_type=fields.get("car_ownership_type") or "own",
            is_primary=True,
        )
        db.add(car)

    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


async def _confirm_update(
    body: ConfirmRequest,
    current_user: User,
    db: AsyncSession,
) -> Customer:
    if not body.customer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="customer_id is required for update confirm",
        )
    diff = body.diff or {}
    customer = await _fetch_owned_customer(body.customer_id, current_user, db)

    if "full_name" in diff:
        customer.full_name = diff["full_name"]
    if "email" in diff:
        customer.email = diff["email"] or None
    if "phone" in diff:
        customer.phone = diff["phone"] or None
    if "note" in diff:
        customer.note = diff["note"] or None

    car_id = diff.get("car_id")
    car_fields = {
        k: v
        for k, v in diff.items()
        if k in {"car_make", "car_model", "car_year", "car_ownership_type", "car_lease_end_date"}
    }
    if car_id and car_fields:
        result = await db.execute(
            select(CustomerCar).where(
                CustomerCar.id == car_id,
                CustomerCar.customer_id == customer.id,
            )
        )
        car = result.scalar_one_or_none()
        if car is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")
        if "car_make" in car_fields:
            car.make = car_fields["car_make"]
        if "car_model" in car_fields:
            car.model = car_fields["car_model"]
        if "car_year" in car_fields:
            car.year = car_fields["car_year"]
        if "car_ownership_type" in car_fields:
            car.ownership_type = car_fields["car_ownership_type"]
        if "car_lease_end_date" in car_fields:
            raw = car_fields["car_lease_end_date"]
            car.lease_end_date = date.fromisoformat(raw) if raw else None

    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer
