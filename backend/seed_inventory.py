"""Seed 10 new VW vehicles into inventory."""
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.db import AsyncSessionLocal
from app.models.inventory import Inventory

VEHICLES = [
    {
        "make": "Volkswagen",
        "model": "Jetta",
        "year": 2025,
        "trim": "S",
        "mileage": 0,
        "price": Decimal("21990"),
        "vin": "1VWFE7A35PC000001",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Golf",
        "year": 2025,
        "trim": "Base",
        "mileage": 0,
        "price": Decimal("25990"),
        "vin": "1VWBC7AJXPC000002",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Tiguan",
        "year": 2025,
        "trim": "S",
        "mileage": 0,
        "price": Decimal("29495"),
        "vin": "1V2WR2CA3PC000003",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Atlas",
        "year": 2025,
        "trim": "S",
        "mileage": 0,
        "price": Decimal("36995"),
        "vin": "1V2LR2CA5PC000004",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "GTI",
        "year": 2025,
        "trim": "S",
        "mileage": 0,
        "price": Decimal("32895"),
        "vin": "1VWGF7A34PC000005",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Taos",
        "year": 2025,
        "trim": "S",
        "mileage": 0,
        "price": Decimal("24995"),
        "vin": "1V2WR2CA7PC000006",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "ID.4",
        "year": 2025,
        "trim": "Standard",
        "mileage": 0,
        "price": Decimal("38995"),
        "vin": "1V2WRPE85PC000007",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Atlas Cross Sport",
        "year": 2025,
        "trim": "SE",
        "mileage": 0,
        "price": Decimal("42995"),
        "vin": "1V2LR2CA9PC000008",
        "status": "reserved",
    },
    {
        "make": "Volkswagen",
        "model": "Arteon",
        "year": 2025,
        "trim": "2.0T",
        "mileage": 0,
        "price": Decimal("45995"),
        "vin": "WVWSR7AN0PE000009",
        "status": "available",
    },
    {
        "make": "Volkswagen",
        "model": "Golf R",
        "year": 2025,
        "trim": "Base",
        "mileage": 0,
        "price": Decimal("45640"),
        "vin": "1VWGF7A38PC000010",
        "status": "available",
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for i, data in enumerate(VEHICLES):
            added_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30 - i * 3)
            item = Inventory(
                make=data["make"],
                model=data["model"],
                year=data["year"],
                trim=data["trim"],
                mileage=data["mileage"],
                price=data["price"],
                vin=data["vin"],
                status=data["status"],
                added_at=added_at,
            )
            db.add(item)
        await db.commit()
        print(f"Seeded {len(VEHICLES)} VW vehicles into inventory.")
        for v in VEHICLES:
            status_str = f"[{v['status']}]"
            print(f"  {v['year']} {v['make']} {v['model']} {v['trim'] or ''} {status_str}")


if __name__ == "__main__":
    asyncio.run(main())
