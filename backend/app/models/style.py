from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SampleMessage(Base):
    __tablename__ = "sample_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # "email" | "text"
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    raw_content: Mapped[str] = mapped_column(nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # "email" | "text"
    style_md: Mapped[str] = mapped_column(nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("sales_id", "channel", name="uq_style_sales_channel"),)


class StyleCategory(Base):
    __tablename__ = "style_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("sales_id", "channel", "name", name="uq_style_category"),)


class StyleExtraRule(Base):
    __tablename__ = "style_extra_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # "email"|"text"|"both"
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
