# Implementation Plan: Settings Page

## Overview

Add a `/settings` route with three sections:
- **Account** (all users): Change password
- **Users** (manager only): View all users, create new sales/manager accounts
- **LLM** (manager only): Update LLM_BASE_URL, LLM_API_KEY, LLM_MODEL at runtime

---

## Technical Solution

### LLM Config Persistence Strategy

The current `LLMClient` is a module-level singleton that reads `settings.*` once at import time. To support runtime updates that survive restarts, store LLM settings in a new `app_settings` DB table (key/value pairs). On startup, load from DB into a mutable in-memory config object. The settings endpoint writes to DB and updates the in-memory config. `LLMClient.chat()` reads from the mutable config at call time — no change to agent files required.

### Password Change

Verify current password with argon2, hash new password, update DB, clear `must_change_password` flag.

### User Creation (manager only)

Create user with hashed password and `must_change_password=True` so new sales reps are forced to set their own password on first login.

---

## Implementation Steps

### Step 1 — Alembic migration: `app_settings` table

**File**: `backend/alembic/versions/0007_app_settings.py`

```python
# Creates app_settings table and seeds LLM defaults from env
# key VARCHAR(50) PK, value TEXT NOT NULL, updated_at TIMESTAMP server_default now()
# Seed rows: llm_base_url, llm_api_key, llm_model
```

- `upgrade()`: CREATE TABLE + INSERT default rows (read from env via `os.getenv`, fallback to hardcoded defaults)
- `downgrade()`: DROP TABLE

---

### Step 2 — LLM config service

**File**: `backend/app/services/llm_config.py` (new)

```python
from dataclasses import dataclass

@dataclass
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str

_config: LLMRuntimeConfig | None = None  # populated at startup

def get_llm_runtime_config() -> LLMRuntimeConfig:
    """Returns in-memory config, falls back to settings if not yet loaded."""

def set_llm_runtime_config(base_url: str, api_key: str, model: str) -> None:
    """Updates in-memory config (call after persisting to DB)."""
```

**Modify**: `backend/app/llm/client.py`

Remove `self._base_url / self._api_key / self._model` caching in `__init__`. In `chat()`, call `get_llm_runtime_config()` at call time:

```python
async def chat(self, messages, tools=None, tool_choice="auto"):
    cfg = get_llm_runtime_config()
    # use cfg.base_url, cfg.api_key, cfg.model
```

**Modify**: `backend/app/main.py`

Add `@app.on_event("startup")` (or lifespan) to load LLM config from `app_settings` table into `set_llm_runtime_config(...)`.

---

### Step 3 — Pydantic schemas

**File**: `backend/app/schemas/settings.py` (new)

```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str  # min length 8

class CreateUserRequest(BaseModel):
    email: str
    name: str
    role: str          # "sales" | "manager"
    password: str      # min length 8

class UserListItem(BaseModel):
    id: int
    email: str
    name: str
    role: str
    must_change_password: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class LLMConfigOut(BaseModel):
    base_url: str
    api_key_masked: str   # last 4 chars visible, rest replaced with ***
    model: str

class LLMConfigUpdate(BaseModel):
    base_url: str
    api_key: str          # empty string = keep existing key
    model: str
```

---

### Step 4 — Settings API router

**File**: `backend/app/api/settings.py` (new)

```
POST /api/settings/change-password   → any authenticated user
GET  /api/settings/users             → manager only
POST /api/settings/users             → manager only
GET  /api/settings/llm               → manager only
PUT  /api/settings/llm               → manager only
```

**`POST /api/settings/change-password`**
1. `verify_password(body.current_password, user.password_hash)` → 400 if wrong
2. Validate `len(body.new_password) >= 8` → 422 if too short
3. `user.password_hash = hash_password(body.new_password)`
4. `user.must_change_password = False`
5. `db.commit()`
6. Return `{"message": "Password changed"}`

**`GET /api/settings/users`**
1. `SELECT * FROM users ORDER BY created_at`
2. Return list of `UserListItem`

**`POST /api/settings/users`**
1. Validate role in `{"sales", "manager"}`
2. Check email uniqueness → 409 if exists
3. `hash_password(body.password)`
4. `INSERT INTO users ... must_change_password=True`
5. Return created `UserListItem` with 201

**`GET /api/settings/llm`**
1. Read from `app_settings` table (or fallback to in-memory config)
2. Mask api_key: `"***" + key[-4:]` if len > 4 else `"****"`
3. Return `LLMConfigOut`

**`PUT /api/settings/llm`**
1. Read existing api_key from DB (for keep-existing logic)
2. Resolve final api_key: use body.api_key if non-empty, else keep existing
3. `UPDATE app_settings SET value=?, updated_at=now() WHERE key=?` for each field
4. Call `set_llm_runtime_config(...)` to update in-memory
5. Return `{"message": "LLM settings updated"}`

---

### Step 5 — Register router in main.py

**Modify**: `backend/app/main.py`

```python
from app.api.settings import router as settings_router
app.include_router(settings_router, prefix="/api/settings")
```

Add startup event:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with get_db() as db:  # or use engine directly
        # Load LLM config from app_settings into memory
        rows = await db.execute(select(AppSetting))
        cfg = {row.key: row.value for row in rows.scalars()}
        set_llm_runtime_config(
            base_url=cfg.get("llm_base_url", settings.llm_base_url),
            api_key=cfg.get("llm_api_key", settings.llm_api_key),
            model=cfg.get("llm_model", settings.llm_model),
        )
    yield
```

Add `AppSetting` ORM model (small, can live in `backend/app/models/app_setting.py`):

```python
class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())
```

---

### Step 6 — Frontend: SettingsPage

**File**: `frontend/src/routes/SettingsPage.tsx` (new)

Three-tab layout using simple tab state (`"account" | "users" | "llm"`).

```
┌─────────────────────────────────────────────────┐
│  Settings                                        │
│  [Account] [Users*] [LLM*]   (* manager only)   │
├─────────────────────────────────────────────────┤
│  Account tab:                                    │
│    Current Password: [__________]                │
│    New Password:     [__________]                │
│    Confirm:          [__________]                │
│    [Change Password]                             │
│                                                  │
│  Users tab (manager):                            │
│    Table: name | email | role | pwd status       │
│    [+ Add User] → inline form below table        │
│                                                  │
│  LLM tab (manager):                              │
│    Base URL: [________________________________]   │
│    API Key:  [__ leave blank to keep current __] │
│    Model:    [________________________________]   │
│    [Save LLM Settings]                           │
└─────────────────────────────────────────────────┘
```

TypeScript API call helpers (inline in file):
- `changePassword(current, next)` → `api.post("/settings/change-password", ...)`
- `listUsers()` → `api.get("/settings/users")`
- `createUser(data)` → `api.post("/settings/users", data)`
- `getLLM()` → `api.get("/settings/llm")`
- `saveLLM(data)` → `api.put("/settings/llm", data)`

State per section: loading, error, success message.

**Must-change-password enforcement**: After login, if `mustChangePassword === true`, redirect to `/settings` and show only the Account tab (no nav to other pages). This is already partially supported — `must_change_password` is in `TokenResponse` and `AuthContext` has it.

---

### Step 7 — Wire up route and nav

**Modify**: `frontend/src/App.tsx`

```tsx
import SettingsPage from "./routes/SettingsPage";
// Inside <Route element={<ProtectedLayout />}>:
<Route path="/settings" element={<SettingsPage />} />
```

**Modify**: `frontend/src/components/NavBar.tsx`

Add Settings link — visible to all users (everyone can change password):

```tsx
{ to: "/settings", label: "⚙ Settings" }
```

Place it after the last nav link, before `nav-spacer`.

**Modify**: `frontend/src/context/AuthContext.tsx`

Persist `mustChangePassword` in `sessionStorage` so it survives page refresh:

```tsx
// On login: sessionStorage.setItem("crm_must_change", res.must_change_password ? "1" : "0")
// On init:  mustChangePassword: sessionStorage.getItem("crm_must_change") === "1"
// On change-password success: call a new updateMustChange(false) method that clears it
```

Add `updateMustChange(val: boolean): void` to `AuthContextValue`.

**Modify**: `frontend/src/App.tsx` (ProtectedLayout)

If `mustChangePassword` is true, show only Settings page and redirect all other routes to `/settings`:

```tsx
const { mustChangePassword } = useAuth();
if (mustChangePassword && location.pathname !== "/settings") {
  return <Navigate to="/settings" replace />;
}
```

---

## Key Files Summary

| File | Operation | Notes |
|------|-----------|-------|
| `backend/alembic/versions/0007_app_settings.py` | Create | New migration |
| `backend/app/models/app_setting.py` | Create | ORM model for app_settings table |
| `backend/app/services/llm_config.py` | Create | Mutable in-memory LLM config |
| `backend/app/schemas/settings.py` | Create | All Pydantic I/O schemas |
| `backend/app/api/settings.py` | Create | 5 endpoints |
| `backend/app/llm/client.py` | Modify | Read config at call time, not init |
| `backend/app/main.py` | Modify | Register router + lifespan startup loader |
| `frontend/src/routes/SettingsPage.tsx` | Create | 3-tab settings UI |
| `frontend/src/App.tsx` | Modify | Add /settings route + must-change redirect |
| `frontend/src/components/NavBar.tsx` | Modify | Add Settings nav link |
| `frontend/src/context/AuthContext.tsx` | Modify | Persist mustChangePassword + updateMustChange() |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| LLM config lost on restart if DB not seeded | Migration 0007 seeds defaults from env; lifespan loader reads from DB |
| API key exposed in GET response | Always mask: show only last 4 chars |
| Empty api_key in PUT wipes the key | Server-side: empty string = keep existing value |
| Concurrent LLM config writes | Acceptable for this single-admin setup; no lock needed |
| `must_change_password` loop after password change | `updateMustChange(false)` clears both state and sessionStorage |

---

## SESSION_ID
- CODEX_SESSION: N/A (plan generated by Claude directly)
- GEMINI_SESSION: N/A
