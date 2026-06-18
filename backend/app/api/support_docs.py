import uuid
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.support_doc import SupportDoc
from app.models.user import User
from app.schemas.support_doc import SupportDocIn, SupportDocOut

router = APIRouter(tags=["support_docs"])


def _to_out(doc: SupportDoc) -> SupportDocOut:
    return SupportDocOut.from_orm_with_active(doc)


@router.get("/active", response_model=list[SupportDocOut])
async def list_active_support_docs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    today = date.today()
    q = select(SupportDoc).where(
        (SupportDoc.effective_to.is_(None)) | (SupportDoc.effective_to >= today)
    ).order_by(SupportDoc.category, SupportDoc.created_at.desc())
    result = await db.execute(q)
    return [_to_out(d) for d in result.scalars().all()]


@router.get("", response_model=list[SupportDocOut])
async def list_support_docs(
    category: Optional[str] = None,
    active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = select(SupportDoc).order_by(SupportDoc.category, SupportDoc.created_at.desc())
    if category:
        q = q.where(SupportDoc.category == category)
    if active is True:
        today = date.today()
        q = q.where(
            (SupportDoc.effective_to.is_(None)) | (SupportDoc.effective_to >= today)
        )
    elif active is False:
        today = date.today()
        q = q.where(SupportDoc.effective_to < today)
    result = await db.execute(q)
    return [_to_out(d) for d in result.scalars().all()]


@router.post("", response_model=SupportDocOut, status_code=status.HTTP_201_CREATED)
async def create_support_doc(
    body: SupportDocIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    doc = SupportDoc(**body.model_dump())
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _to_out(doc)


@router.put("/{doc_id}", response_model=SupportDocOut)
async def update_support_doc(
    doc_id: uuid.UUID,
    body: SupportDocIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    result = await db.execute(select(SupportDoc).where(SupportDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support doc not found")
    for field, value in body.model_dump().items():
        setattr(doc, field, value)
    await db.commit()
    await db.refresh(doc)
    return _to_out(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_support_doc(
    doc_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(SupportDoc).where(SupportDoc.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support doc not found")
    await db.delete(doc)
    await db.commit()
