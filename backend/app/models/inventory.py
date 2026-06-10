from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    make: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    trim: Mapped[Optional[str]] = mapped_column(String(60))
    mileage: Mapped[Optional[int]] = mapped_column()
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    vin: Mapped[Optional[str]] = mapped_column(String(17), unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")  # "available" | "sold" | "reserved"
    features: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    added_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
