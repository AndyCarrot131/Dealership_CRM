"""Shared test fixtures.

Uses an in-memory SQLite database (aiosqlite) with the app's get_db dependency
overridden, so no Postgres instance is needed to run the suite.
"""
import os

# Environment must be set before any app module import triggers Settings().
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("LLM_BASE_URL", "https://llm.test/v1")
os.environ.setdefault("LLM_API_KEY", "env-default-key")
os.environ.setdefault("LLM_MODEL", "env-default-model")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.hashing import hash_password
from app.auth.jwt import create_access_token
from app.db import Base, get_db
from app.main import app
from app.models import (  # noqa: F401 — register all tables on Base.metadata
    app_setting,
    customer,
    interaction,
    inventory,
    llm_log,
    outreach,
    style,
    user,
    user_setting,
)
from app.models.user import User


@pytest.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(engine):
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _create_user(db_session, email: str, role: str, password: str = "password123") -> User:
    user = User(
        email=email,
        name=email.split("@")[0],
        role=role,
        password_hash=hash_password(password),
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sales_user(db_session) -> User:
    return await _create_user(db_session, "sales@test.com", "sales")


@pytest.fixture
async def other_sales_user(db_session) -> User:
    return await _create_user(db_session, "sales2@test.com", "sales")


@pytest.fixture
async def manager_user(db_session) -> User:
    return await _create_user(db_session, "manager@test.com", "manager")


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sales_headers(sales_user) -> dict[str, str]:
    return auth_header(sales_user)


@pytest.fixture
def other_sales_headers(other_sales_user) -> dict[str, str]:
    return auth_header(other_sales_user)


@pytest.fixture
def manager_headers(manager_user) -> dict[str, str]:
    return auth_header(manager_user)
