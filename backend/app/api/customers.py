from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.briefing import run_briefing
from app.auth.dependencies import get_current_user
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.models.customer import Customer, CustomerCar
from app.models.user import User

router = APIRouter(tags=["customers"])


class CustomerCarOut(BaseModel):
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
    last_contacted_at: Optional[datetime]
    created_at: datetime
    cars: list[CustomerCarOut] = []

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    note: Optional[str] = None


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    note: Optional[str] = None


class CarCreate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership_type: Optional[str] = None
    lease_end_date: Optional[date] = None
    is_primary: bool = True


class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership_type: Optional[str] = None
    lease_end_date: Optional[date] = None
    is_primary: Optional[bool] = None


def _with_cars():
    return selectinload(Customer.cars)


@router.get("", response_model=list[CustomerOut])
async def list_customers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Customer]:
    if current_user.role == "manager":
        result = await db.execute(
            select(Customer).options(_with_cars()).order_by(Customer.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Customer)
            .options(_with_cars())
            .where(Customer.assigned_sales_id == current_user.id)
            .order_by(Customer.created_at.desc())
        )
    return list(result.scalars().all())


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = Customer(
        assigned_sales_id=current_user.id,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        note=body.note,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    result = await db.execute(
        select(Customer).options(_with_cars()).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if body.full_name is not None:
        customer.full_name = body.full_name
    if body.email is not None:
        customer.email = body.email
    if body.phone is not None:
        customer.phone = body.phone
    if body.note is not None:
        customer.note = body.note
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.delete(customer)
    await db.commit()


async def _get_authorized_customer(
    customer_id: int, current_user: User, db: AsyncSession
) -> Customer:
    result = await db.execute(
        select(Customer).options(_with_cars()).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return customer


@router.post("/{customer_id}/cars", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def add_car(
    customer_id: int,
    body: CarCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car = CustomerCar(customer_id=customer_id, **body.model_dump())
    db.add(car)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


@router.put("/{customer_id}/cars/{car_id}", response_model=CustomerOut)
async def update_car(
    customer_id: int,
    car_id: int,
    body: CarUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car_result = await db.execute(
        select(CustomerCar).where(CustomerCar.id == car_id, CustomerCar.customer_id == customer_id)
    )
    car = car_result.scalar_one_or_none()
    if car is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(car, field, val)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


@router.delete("/{customer_id}/cars/{car_id}", response_model=CustomerOut)
async def delete_car(
    customer_id: int,
    car_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Customer:
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car_result = await db.execute(
        select(CustomerCar).where(CustomerCar.id == car_id, CustomerCar.customer_id == customer_id)
    )
    car = car_result.scalar_one_or_none()
    if car is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found")
    await db.delete(car)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer


@router.post("/{customer_id}/briefing")
async def generate_briefing(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> Any:
    """Generate a pre-appointment AI briefing for the given customer."""
    # Ownership check — reuse existing helper
    await _get_authorized_customer(customer_id, current_user, db)
    try:
        result = await run_briefing(customer_id, db, llm)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {exc}",
        )
    return result
