from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.customer import Customer
from app.models.interaction import Interaction
from app.models.user import User

router = APIRouter(tags=["interactions"])

VALID_CHANNELS = frozenset({"call", "text", "email", "in-person"})


class InteractionCreate(BaseModel):
    customer_id: int
    channel: str
    summary: str
    contacted_at: Optional[datetime] = None


class InteractionOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    sales_id: int
    channel: str
    summary: str
    contacted_at: datetime
    created_at: datetime


def _normalize_dt(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_dict(r: Interaction) -> dict[str, Any]:
    return {
        "id": r.id,
        "customer_id": r.customer_id,
        "customer_name": r.customer.full_name,
        "sales_id": r.sales_id,
        "channel": r.channel,
        "summary": r.summary,
        "contacted_at": r.contacted_at,
        "created_at": r.created_at,
    }


@router.get("", response_model=list[InteractionOut])
async def list_interactions(
    customer_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = (
        select(Interaction)
        .options(selectinload(Interaction.customer))
        .order_by(Interaction.contacted_at.desc())
    )
    if current_user.role != "manager":
        q = q.where(Interaction.sales_id == current_user.id)
    if customer_id is not None:
        q = q.where(Interaction.customer_id == customer_id)

    result = await db.execute(q)
    return [_row_to_dict(r) for r in result.scalars().all()]


@router.post("", response_model=InteractionOut, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    body: InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    if body.channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"channel must be one of: {', '.join(sorted(VALID_CHANNELS))}",
        )

    result = await db.execute(select(Customer).where(Customer.id == body.customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    contacted_at = _normalize_dt(body.contacted_at)
    interaction = Interaction(
        customer_id=body.customer_id,
        sales_id=current_user.id,
        channel=body.channel,
        summary=body.summary,
        contacted_at=contacted_at,
    )
    db.add(interaction)
    customer.last_contacted_at = contacted_at
    await db.commit()
    await db.refresh(interaction, ["customer"])
    return _row_to_dict(interaction)


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interaction(
    interaction_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Interaction).where(Interaction.id == interaction_id))
    interaction = result.scalar_one_or_none()
    if interaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found")
    if current_user.role != "manager" and interaction.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    customer_id = interaction.customer_id
    await db.delete(interaction)
    await db.flush()

    # Recalculate last_contacted_at from remaining interactions so the outreach
    # cadence filter stays accurate after a log entry is removed.
    latest_result = await db.execute(
        select(func.max(Interaction.contacted_at)).where(Interaction.customer_id == customer_id)
    )
    latest_contacted_at = latest_result.scalar_one_or_none()

    customer_result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = customer_result.scalar_one_or_none()
    if customer is not None:
        customer.last_contacted_at = latest_contacted_at

    await db.commit()
