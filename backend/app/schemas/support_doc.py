import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class SupportDocIn(BaseModel):
    category: str
    title: str
    content: str
    checks: str
    effective_from: date
    effective_to: Optional[date] = None

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("category must not be blank")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class SupportDocOut(BaseModel):
    id: uuid.UUID
    category: str
    title: str
    content: str
    checks: str
    effective_from: date
    effective_to: Optional[date]
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_active(cls, obj: object) -> "SupportDocOut":
        today = date.today()
        effective_to = getattr(obj, "effective_to", None)
        is_active = effective_to is None or effective_to >= today
        return cls(
            id=obj.id,  # type: ignore[attr-defined]
            category=obj.category,  # type: ignore[attr-defined]
            title=obj.title,  # type: ignore[attr-defined]
            content=obj.content,  # type: ignore[attr-defined]
            checks=obj.checks,  # type: ignore[attr-defined]
            effective_from=obj.effective_from,  # type: ignore[attr-defined]
            effective_to=effective_to,
            created_at=obj.created_at,  # type: ignore[attr-defined]
            is_active=is_active,
        )
