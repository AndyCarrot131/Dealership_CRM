# Implementation Plan: Dealer CRM MVP — Phase 1 & 2 Foundation

## Task Type
- [x] Fullstack (Backend + Frontend scaffold + Docker dev stack)

## Source Documents
- ARCHITECTURE.md — deployment topology, packaging, security, migration path
- PROJECT.md — MVP scope, data model, AI agent design
- PLAN.md — phased execution order
- CLAUDE.md — monorepo layout and conventions

---

## Technical Solution

Scaffold the complete monorepo skeleton with a working local dev stack. This phase produces **no AI agents and no business logic** — only the runtime foundation that all later features depend on:

1. Monorepo directory structure (`backend/`, `frontend/`, `desktop/`, `database_app/`)
2. FastAPI app wired to PostgreSQL via SQLAlchemy + Alembic
3. All nine database tables created via Alembic migration
4. JWT auth middleware with sales/manager role enforcement
5. React + Vite frontend scaffold (SPA, relative `/api` paths only)
6. `docker-compose.yml` for local dev (Postgres container + backend hot reload)
7. Config loading that supports zero hardcoding (env vars / `config.json` / `keyring`)

---

## Implementation Steps

### Step 1 — Monorepo Skeleton
Create directory tree and empty placeholder files.

```
dealer-crm/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── auth/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   ├── services/
│   │   ├── agents/
│   │   └── llm/
│   ├── alembic/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── (Vite scaffold — see Step 6)
├── desktop/
│   ├── shell.py
│   └── crm.spec
├── database_app/
│   ├── launcher.py
│   └── database.spec
└── docker-compose.yml
```

**Deliverable**: All directories and empty `__init__.py` / placeholder files exist.

---

### Step 2 — Docker Compose Dev Stack

`docker-compose.yml`:

```yaml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: dealer_crm
      POSTGRES_USER: crm_app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8756
    environment:
      DATABASE_URL: postgresql+asyncpg://crm_app:${DB_PASSWORD}@db:5432/dealer_crm
      JWT_SECRET: ${JWT_SECRET}
      LLM_BASE_URL: ${LLM_BASE_URL}
      LLM_API_KEY: ${LLM_API_KEY}
      LLM_MODEL: ${LLM_MODEL}
    ports:
      - "8756:8756"
    volumes:
      - ./backend:/app
    depends_on:
      - db

volumes:
  pgdata:
```

`.env.example`:
```
DB_PASSWORD=changeme
JWT_SECRET=changeme
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

**Deliverable**: `docker-compose up` starts Postgres + backend with hot reload.

---

### Step 3 — Config Loading (`backend/app/config.py`)

All runtime values from environment variables. Zero hardcoding.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    listen_host: str = "127.0.0.1"
    listen_port: int = 8756

    class Config:
        env_file = ".env"

settings = Settings()
```

**Deliverable**: `settings` importable everywhere; no value is hardcoded.

---

### Step 4 — SQLAlchemy + Async DB (`backend/app/db.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

**Deliverable**: Async SQLAlchemy engine wired to config URL; `get_db` dependency injector ready.

---

### Step 5 — ORM Models (`backend/app/models/`)

Nine tables from PROJECT.md §5. All inherit `Base` from `db.py`.

**`models/user.py`**:
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)  # "sales" | "manager"
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

**`models/customer.py`**:
```python
class Customer(Base):
    __tablename__ = "customers"
    id, assigned_sales_id (FK users), full_name, email, phone, note, last_contacted_at, created_at, updated_at
    # Relationship: cars = relationship("CustomerCar", back_populates="customer")

class CustomerCar(Base):
    __tablename__ = "customer_car"
    id, customer_id (FK customers), make, model, year,
    ownership_type ("own"|"lease"|"finance"), lease_end_date, is_primary, created_at, updated_at
```

**`models/interaction.py`** — `interactions` table (id, customer_id, sales_id, channel, summary, created_at)

**`models/inventory.py`** — `inventory` table (id, make, model, year, trim, mileage, price, vin, status, added_at)

**`models/style.py`**:
```python
class SampleMessage(Base):
    __tablename__ = "sample_messages"
    id, sales_id (FK users), channel ("email"|"text"), raw_content, label, created_at

class StyleProfile(Base):
    __tablename__ = "style_profiles"
    id, sales_id (FK users), channel, style_md, updated_at
    # UniqueConstraint("sales_id", "channel")
```

**`models/outreach.py`**:
```python
class OutreachRule(Base):
    __tablename__ = "outreach_rules"
    id, sales_id (FK users), name, rule_text, compiled_filter (JSON), cadence_days, active, created_at

class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id, sales_id (FK users), customer_id (FK customers), rule_id (FK outreach_rules, nullable),
    subject, body, status ("pending"|"approved"|"dismissed"), created_at, approved_at
```

**Deliverable**: All nine tables defined as ORM models with correct FK relationships.

---

### Step 6 — Alembic Initial Migration

```bash
cd backend
alembic init alembic
# Edit alembic/env.py to use async engine and import all models
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

`alembic/env.py` key changes:
- Import `Base` and all models so autogenerate detects them
- Use `run_async_migrations()` pattern for asyncpg compatibility

**Deliverable**: Running `alembic upgrade head` creates all nine tables in Postgres.

---

### Step 7 — Auth (`backend/app/auth/`)

**`auth/hashing.py`**: argon2-cffi `PasswordHasher` — `hash_password(plain)` / `verify_password(plain, hashed)`

**`auth/jwt.py`**:
```python
def create_access_token(user_id: int, role: str) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": now + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> dict: ...
```

**`auth/dependencies.py`**:
```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    # decode JWT → load user from DB → raise 401 if invalid

async def require_manager(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "manager":
        raise HTTPException(403)
    return current_user
```

**`api/auth.py`** — `POST /api/auth/login`:
```python
# 1. Load user by email
# 2. verify_password(plain, user.password_hash)
# 3. create_access_token(user.id, user.role)
# 4. Return {"access_token": token, "token_type": "bearer"}
```

**Deliverable**: Login endpoint works; JWT decoded and user injected in all protected routes.

---

### Step 8 — FastAPI App Entry (`backend/app/main.py`)

```python
app = FastAPI(title="Dealer CRM")

# Mount API routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(customers_router, prefix="/api/customers")
app.include_router(inventory_router, prefix="/api/inventory")
# ... (intake, outreach, style routers added in later phases)

# Serve React SPA (production / desktop mode)
if Path("../frontend/dist").exists():
    app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

**Deliverable**: App starts; `/api/auth/login` returns JWT; SPA served when `dist/` exists.

---

### Step 9 — Frontend Scaffold (`frontend/`)

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

Key conventions to set up now:
- `src/api/client.ts` — axios/fetch wrapper that always uses relative `/api` base (never `localhost`)
- `src/types/` — TypeScript interfaces matching Pydantic schemas
- `src/routes/` — React Router layout: `/login`, `/customers`, `/inventory`, `/outreach`, `/settings`
- Auth token stored in memory (`useState`/context), not `localStorage`

**Deliverable**: `npm run dev` starts frontend dev server; `npm run build` produces `dist/`.

---

### Step 10 — Seeding Initial Manager Account

On first migration, seed one default manager so the system isn't locked out:

```python
# alembic/versions/xxxx_seed_initial_manager.py (second migration)
def upgrade():
    op.execute("""
        INSERT INTO users (email, password_hash, name, role, created_at)
        VALUES ('admin@dealer.local', '<argon2_hash_of_changeme>', 'Admin', 'manager', now())
        ON CONFLICT DO NOTHING
    """)
```

Force password change on first login (add `must_change_password: bool` column to `users`).

**Deliverable**: `alembic upgrade head` leaves a usable manager account.

---

### Step 11 — Desktop Shell Stub (`desktop/shell.py`)

Minimal working stub (full packaging is Phase 4):

```python
import threading, time, webview, uvicorn
from app.main import app

def start_backend():
    uvicorn.run(app, host="127.0.0.1", port=8756, log_level="warning")

if __name__ == "__main__":
    t = threading.Thread(target=start_backend, daemon=True)
    t.start()
    time.sleep(1.5)  # wait for uvicorn to be ready
    webview.create_window("Dealer CRM", "http://127.0.0.1:8756", width=1280, height=800)
    webview.start()
```

**Deliverable**: Running `python desktop/shell.py` opens the app in a native window (when frontend dist/ exists).

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `docker-compose.yml` | Create | Dev stack: Postgres + hot-reload backend |
| `backend/requirements.txt` | Create | fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, python-jose, argon2-cffi, pywebview |
| `backend/app/config.py` | Create | Pydantic Settings — all env vars, zero hardcoding |
| `backend/app/db.py` | Create | Async SQLAlchemy engine + session + Base |
| `backend/app/models/*.py` | Create | Nine ORM tables |
| `backend/alembic/` | Create | Migrations: initial schema + manager seed |
| `backend/app/auth/` | Create | JWT creation/decode + argon2 hashing + FastAPI dependencies |
| `backend/app/main.py` | Create | FastAPI app, router mounts, StaticFiles |
| `backend/app/api/auth.py` | Create | `POST /api/auth/login` endpoint |
| `frontend/` | Create | Vite + React + TypeScript scaffold |
| `frontend/src/api/client.ts` | Create | API client using relative `/api` |
| `desktop/shell.py` | Create | pywebview + uvicorn launcher stub |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| asyncpg + Alembic async migration complexity | Use `run_async_migrations()` pattern from Alembic docs; test migration on clean DB before proceeding |
| pgdata persistence in docker volume lost on `docker-compose down -v` | Document: use `docker-compose down` (no `-v`) during dev; `-v` only for full reset |
| WebView2 absent on target Windows machine | Desktop shell is a stub in Phase 1; full packaging + WebView2 bootstrapper added in Phase 4 |
| JWT secret in `.env` committed by accident | `.env` in `.gitignore`; only `.env.example` committed |
| Sales/manager isolation not enforced at DB query level yet | Auth middleware injects current user in Phase 1; query filters applied per-endpoint in Phase 3 |

---

## Success Criteria for Phase 1 & 2

- [ ] `docker-compose up` starts Postgres + backend with no errors
- [ ] `alembic upgrade head` creates all nine tables
- [ ] `POST /api/auth/login` returns a valid JWT for seeded manager account
- [ ] `npm run build` in `frontend/` produces `dist/` without errors
- [ ] No hardcoded DB credentials, LLM keys, or hostnames anywhere in source

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A (no external model available in this environment)
- GEMINI_SESSION: N/A (no external model available in this environment)
