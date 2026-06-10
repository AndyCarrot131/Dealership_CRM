"""AI intake/update confirmation flow — the human-approval write path."""
from sqlalchemy import select

from app.models.customer import Customer
from tests.conftest import auth_header


async def test_confirm_intake_creates_customer_with_car(client, sales_user, db_session):
    resp = await client.post(
        "/api/chat/confirm",
        json={
            "mode": "intake",
            "fields": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "phone": "555-0100",
                "car_make": "Toyota",
                "car_model": "Camry",
                "car_year": 2022,
                "car_ownership_type": "lease",
            },
        },
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Jane Doe"
    assert body["assigned_sales_id"] == sales_user.id
    assert len(body["cars"]) == 1
    assert body["cars"][0]["make"] == "Toyota"
    assert body["cars"][0]["ownership_type"] == "lease"


async def test_confirm_intake_requires_full_name(client, sales_headers):
    resp = await client.post(
        "/api/chat/confirm",
        json={"mode": "intake", "fields": {"email": "no-name@example.com"}},
        headers=sales_headers,
    )
    assert resp.status_code == 422


async def test_confirm_update_applies_diff(client, sales_user, db_session):
    customer = Customer(assigned_sales_id=sales_user.id, full_name="Old Name")
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    resp = await client.post(
        "/api/chat/confirm",
        json={
            "mode": "update",
            "customer_id": customer.id,
            "diff": {"full_name": "New Name", "phone": "555-0199"},
        },
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert body["phone"] == "555-0199"


async def test_confirm_update_denied_for_other_sales(
    client, sales_user, other_sales_user, db_session
):
    customer = Customer(assigned_sales_id=sales_user.id, full_name="Protected")
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    resp = await client.post(
        "/api/chat/confirm",
        json={"mode": "update", "customer_id": customer.id, "diff": {"full_name": "Hijacked"}},
        headers=auth_header(other_sales_user),
    )
    assert resp.status_code == 403

    result = await db_session.execute(select(Customer).where(Customer.id == customer.id))
    untouched = result.scalar_one()
    assert untouched.full_name == "Protected"


async def test_confirm_update_allowed_for_manager(client, sales_user, manager_user, db_session):
    customer = Customer(assigned_sales_id=sales_user.id, full_name="Managed")
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    resp = await client.post(
        "/api/chat/confirm",
        json={"mode": "update", "customer_id": customer.id, "diff": {"note": "manager note"}},
        headers=auth_header(manager_user),
    )
    assert resp.status_code == 201
    assert resp.json()["note"] == "manager note"
