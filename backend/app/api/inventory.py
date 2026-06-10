from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.inventory import Inventory
from app.models.user import User

router = APIRouter(tags=["inventory"])


class InventoryOut(BaseModel):
    id: int
    make: str
    model: str
    year: int
    trim: Optional[str]
    mileage: Optional[int]
    price: Optional[Decimal]
    vin: Optional[str]
    status: str
    features: Optional[str]
    notes: Optional[str]
    added_at: datetime

    model_config = {"from_attributes": True}


class InventoryCreate(BaseModel):
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    mileage: Optional[int] = None
    price: Optional[Decimal] = None
    vin: Optional[str] = None
    status: str = "available"
    features: Optional[str] = None
    notes: Optional[str] = None


class InventoryUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    trim: Optional[str] = None
    mileage: Optional[int] = None
    price: Optional[Decimal] = None
    vin: Optional[str] = None
    status: Optional[str] = None
    features: Optional[str] = None
    notes: Optional[str] = None


@router.get("", response_model=list[InventoryOut])
async def list_inventory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Inventory]:
    result = await db.execute(select(Inventory).order_by(Inventory.added_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    body: InventoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Inventory:
    item = Inventory(
        make=body.make,
        model=body.model,
        year=body.year,
        trim=body.trim,
        mileage=body.mileage,
        price=body.price,
        vin=body.vin or None,
        status=body.status,
        features=body.features or None,
        notes=body.notes or None,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=InventoryOut)
async def update_inventory_item(
    item_id: int,
    body: InventoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Inventory:
    result = await db.execute(select(Inventory).where(Inventory.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Inventory).where(Inventory.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    await db.delete(item)
    await db.commit()
