"""Auth endpoint tests: login, token validation, /me."""
from tests.conftest import auth_header


async def test_login_success(client, sales_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "sales@test.com", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["role"] == "sales"


async def test_login_wrong_password(client, sales_user):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "sales@test.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@test.com", "password": "password123"},
    )
    assert resp.status_code == 401


async def test_me_returns_current_user(client, sales_user):
    resp = await client.get("/api/auth/me", headers=auth_header(sales_user))
    assert resp.status_code == 200
    assert resp.json()["email"] == "sales@test.com"


async def test_me_requires_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_rejects_garbage_token(client):
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
