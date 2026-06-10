from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.customer import Customer


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # "call" | "text" | "email" | "in-person"
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    contacted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    customer: Mapped["Customer"] = relationship("Customer", lazy="select")
