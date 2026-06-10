"""Customer data isolation: assigned_sales_id is the permission boundary."""
from app.models.customer import Customer
from tests.conftest import auth_header


async def _seed_customers(db_session, sales_user, other_sales_user) -> None:
    db_session.add_all(
        [
            Customer(assigned_sales_id=sales_user.id, full_name="Mine One"),
            Customer(assigned_sales_id=sales_user.id, full_name="Mine Two"),
            Customer(assigned_sales_id=other_sales_user.id, full_name="Theirs"),
        ]
    )
    await db_session.commit()


async def test_sales_sees_only_own_customers(client, sales_user, other_sales_user, db_session):
    await _seed_customers(db_session, sales_user, other_sales_user)

    resp = await client.get("/api/customers", headers=auth_header(sales_user))
    assert resp.status_code == 200
    names = {c["full_name"] for c in resp.json()}
    assert names == {"Mine One", "Mine Two"}


async def test_manager_sees_all_customers(
    client, sales_user, other_sales_user, manager_user, db_session
):
    await _seed_customers(db_session, sales_user, other_sales_user)

    resp = await client.get("/api/customers", headers=auth_header(manager_user))
    assert resp.status_code == 200
    names = {c["full_name"] for c in resp.json()}
    assert names == {"Mine One", "Mine Two", "Theirs"}


async def test_created_customer_is_assigned_to_creator(client, sales_user):
    resp = await client.post(
        "/api/customers",
        json={"full_name": "Fresh Lead"},
        headers=auth_header(sales_user),
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_sales_id"] == sales_user.id


async def test_sales_cannot_update_others_customer(
    client, sales_user, other_sales_user, db_session
):
    customer = Customer(assigned_sales_id=sales_user.id, full_name="Locked")
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)

    resp = await client.put(
        f"/api/customers/{customer.id}",
        json={"full_name": "Stolen"},
        headers=auth_header(other_sales_user),
    )
    assert resp.status_code == 403


async def test_customers_require_auth(client):
    resp = await client.get("/api/customers")
    assert resp.status_code == 401
