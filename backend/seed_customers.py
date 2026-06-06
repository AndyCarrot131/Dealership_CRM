"""Seed 10 sample customers: 5 with existing car, 3 who bought from dealership, 2 no car."""
import asyncio
from datetime import UTC, date, datetime, timedelta

from app.db import AsyncSessionLocal
from app.models.customer import Customer, CustomerCar
from app.models.user import User  # noqa: F401 — required to resolve FK metadata

ADMIN_ID = 1

customers_data = [
    # --- 5 customers with an existing car (own / lease / finance) ---
    {
        "full_name": "Liam Nguyen",
        "email": "liam.nguyen@email.com",
        "phone": "416-555-0101",
        "note": "Interested in upgrading SUV. Currently leasing a RAV4.",
        "car": {"make": "Toyota", "model": "RAV4", "year": 2021, "ownership_type": "lease",
                "lease_end_date": date(2025, 9, 30), "is_primary": True},
    },
    {
        "full_name": "Sofia Martínez",
        "email": "sofia.m@gmail.com",
        "phone": "647-555-0182",
        "note": "Looking to trade in her Civic for a pickup.",
        "car": {"make": "Honda", "model": "Civic", "year": 2019, "ownership_type": "own",
                "lease_end_date": None, "is_primary": True},
    },
    {
        "full_name": "James Okafor",
        "email": "j.okafor@work.ca",
        "phone": "905-555-0244",
        "note": "Fleet buyer. Finances multiple vehicles for small business.",
        "car": {"make": "Ford", "model": "F-150", "year": 2020, "ownership_type": "finance",
                "lease_end_date": None, "is_primary": True},
    },
    {
        "full_name": "Emily Chen",
        "email": "emily.chen@hotmail.com",
        "phone": "416-555-0367",
        "note": "Lease ending soon, wants to explore EVs.",
        "car": {"make": "Mazda", "model": "CX-5", "year": 2022, "ownership_type": "lease",
                "lease_end_date": date(2025, 12, 31), "is_primary": True},
    },
    {
        "full_name": "Daniel Tremblay",
        "email": "d.tremblay@videotron.ca",
        "phone": "514-555-0459",
        "note": "Owns a truck, now looking for a family sedan.",
        "car": {"make": "Ram", "model": "1500", "year": 2018, "ownership_type": "own",
                "lease_end_date": None, "is_primary": True},
    },

    # --- 3 customers who bought from this dealership ---
    {
        "full_name": "Priya Sharma",
        "email": "priya.sharma@outlook.com",
        "phone": "416-555-0521",
        "note": "Purchased last spring. Very satisfied. Potential referral source.",
        "car": {"make": "Hyundai", "model": "Tucson", "year": 2024, "ownership_type": "own",
                "lease_end_date": None, "is_primary": True},
    },
    {
        "full_name": "Marcus Webb",
        "email": "marcwebb@gmail.com",
        "phone": "647-555-0613",
        "note": "Financed a Camry here 8 months ago. May be ready for add-ons.",
        "car": {"make": "Toyota", "model": "Camry", "year": 2023, "ownership_type": "finance",
                "lease_end_date": None, "is_primary": True},
    },
    {
        "full_name": "Aisha Kowalski",
        "email": "aisha.k@rogers.ca",
        "phone": "905-555-0788",
        "note": "Bought an Escape outright. Looking at winter tires package.",
        "car": {"make": "Ford", "model": "Escape", "year": 2023, "ownership_type": "own",
                "lease_end_date": None, "is_primary": True},
    },

    # --- 2 prospects with no car ---
    {
        "full_name": "Tyler Brooks",
        "email": "tyler.brooks@live.ca",
        "phone": "613-555-0831",
        "note": "First-time buyer. Looking for something under $30k.",
        "car": None,
    },
    {
        "full_name": "Nadia Johansson",
        "email": "nadia.j@gmail.com",
        "phone": "416-555-0994",
        "note": "Relocating from Sweden. Needs a reliable commuter car.",
        "car": None,
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for i, data in enumerate(customers_data):
            created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90 - i * 8)
            customer = Customer(
                assigned_sales_id=ADMIN_ID,
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                note=data["note"],
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(customer)
            await db.flush()  # get customer.id

            if data["car"]:
                car_data = data["car"]
                car = CustomerCar(
                    customer_id=customer.id,
                    make=car_data["make"],
                    model=car_data["model"],
                    year=car_data["year"],
                    ownership_type=car_data["ownership_type"],
                    lease_end_date=car_data.get("lease_end_date"),
                    is_primary=car_data["is_primary"],
                )
                db.add(car)

        await db.commit()
        print(f"Seeded {len(customers_data)} customers.")
        print("  - 5 with existing car (own/lease/finance)")
        print("  - 3 who bought from this dealership")
        print("  - 2 prospects with no car")


if __name__ == "__main__":
    asyncio.run(main())
