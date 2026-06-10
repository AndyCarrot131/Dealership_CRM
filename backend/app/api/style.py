from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.style_summarizer import run_style_summarizer
from app.auth.dependencies import get_current_user
from app.db import get_db
from app.llm.client import LLMClient, get_llm_client
from app.models.style import SampleMessage, StyleCategory, StyleProfile
from app.models.user import User

router = APIRouter(tags=["style"])

VALID_CHANNELS = frozenset({"email", "text"})


class SampleCreate(BaseModel):
    channel: str
    raw_content: str
    label: str = ""


class SampleOut(BaseModel):
    id: int
    channel: str
    raw_content: str
    label: str

    model_config = {"from_attributes": True}


class StyleProfileOut(BaseModel):
    channel: str
    style_md: str

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    channel: str
    name: str


class CategoryOut(BaseModel):
    id: int
    channel: str
    name: str

    model_config = {"from_attributes": True}


def _check_channel(channel: str) -> None:
    if channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"channel must be one of: {', '.join(sorted(VALID_CHANNELS))}",
        )


@router.get("/samples", response_model=list[SampleOut])
async def list_samples(
    channel: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = select(SampleMessage).where(SampleMessage.sales_id == current_user.id)
    if channel is not None:
        _check_channel(channel)
        q = q.where(SampleMessage.channel == channel)
    q = q.order_by(SampleMessage.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/samples", response_model=SampleOut, status_code=status.HTTP_201_CREATED)
async def create_sample(
    body: SampleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SampleMessage:
    _check_channel(body.channel)
    sample = SampleMessage(
        sales_id=current_user.id,
        channel=body.channel,
        raw_content=body.raw_content.strip(),
        label=body.label.strip(),
    )
    db.add(sample)
    await db.commit()
    await db.refresh(sample)
    return sample


@router.patch("/samples/{sample_id}", response_model=SampleOut)
async def update_sample_label(
    sample_id: int,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SampleMessage:
    result = await db.execute(select(SampleMessage).where(SampleMessage.id == sample_id))
    sample = result.scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
    if sample.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    sample.label = body.get("label", "").strip()
    await db.commit()
    await db.refresh(sample)
    return sample


@router.delete("/samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    sample_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(SampleMessage).where(SampleMessage.id == sample_id))
    sample = result.scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")
    if sample.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.delete(sample)
    await db.commit()


@router.get("/profile/{channel}", response_model=StyleProfileOut)
async def get_profile(
    channel: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _check_channel(channel)
    result = await db.execute(
        select(StyleProfile).where(
            StyleProfile.sales_id == current_user.id,
            StyleProfile.channel == channel,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return {"channel": channel, "style_md": ""}
    return profile


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    channel: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    q = select(StyleCategory).where(StyleCategory.sales_id == current_user.id)
    if channel is not None:
        _check_channel(channel)
        q = q.where(StyleCategory.channel == channel)
    q = q.order_by(StyleCategory.name)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StyleCategory:
    _check_channel(body.channel)
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name cannot be empty.",
        )
    if len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name must be 100 characters or fewer.",
        )
    category = StyleCategory(sales_id=current_user.id, channel=body.channel, name=name)
    db.add(category)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{name}' already exists for {body.channel}.",
        )
    await db.refresh(category)
    return category


@router.post("/categories/import", response_model=list[CategoryOut])
async def import_categories_from_labels(
    channel: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    _check_channel(channel)
    labels_result = await db.execute(
        select(SampleMessage.label)
        .where(
            SampleMessage.sales_id == current_user.id,
            SampleMessage.channel == channel,
            SampleMessage.label != "",
        )
        .distinct()
    )
    distinct_labels = sorted({row[0].strip() for row in labels_result.all() if row[0].strip()})
    for name in distinct_labels:
        db.add(StyleCategory(sales_id=current_user.id, channel=channel, name=name))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
    result = await db.execute(
        select(StyleCategory)
        .where(StyleCategory.sales_id == current_user.id, StyleCategory.channel == channel)
        .order_by(StyleCategory.name)
    )
    return result.scalars().all()


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(StyleCategory).where(StyleCategory.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if category.sales_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    await db.delete(category)
    await db.commit()


@router.post("/summarize/{channel}", response_model=StyleProfileOut)
async def summarize(
    channel: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> Any:
    _check_channel(channel)

    samples_result = await db.execute(
        select(SampleMessage).where(
            SampleMessage.sales_id == current_user.id,
            SampleMessage.channel == channel,
        )
    )
    samples = samples_result.scalars().all()
    if not samples:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No {channel} samples found. Add some samples first.",
        )

    categories_result = await db.execute(
        select(StyleCategory).where(
            StyleCategory.sales_id == current_user.id,
            StyleCategory.channel == channel,
        ).order_by(StyleCategory.name)
    )
    category_names = [c.name for c in categories_result.scalars().all()]

    try:
        style_md = await run_style_summarizer(
            [(s.label, s.raw_content) for s in samples],
            channel,
            llm,
            categories=category_names if category_names else None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service unavailable: {exc}",
        )

    existing = await db.execute(
        select(StyleProfile).where(
            StyleProfile.sales_id == current_user.id,
            StyleProfile.channel == channel,
        )
    )
    profile = existing.scalar_one_or_none()
    if profile:
        profile.style_md = style_md
    else:
        profile = StyleProfile(sales_id=current_user.id, channel=channel, style_md=style_md)
        db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile
