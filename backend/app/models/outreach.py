from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, String, Boolean, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OutreachRule(Base):
    __tablename__ = "outreach_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    rule_text: Mapped[str] = mapped_column(nullable=False)
    compiled_filter: Mapped[Optional[dict]] = mapped_column(JSON)
    cadence_days: Mapped[Optional[int]] = mapped_column()
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outreach_rules.id", ondelete="SET NULL"))
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # "pending" | "approved" | "dismissed"
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column()
