# Implementation Plan: Contacts Page

## Task Type
- [x] Fullstack (→ Parallel Codex + Gemini)

## Summary

Add a `/contacts` page for logging and browsing all customer interactions (calls, texts, emails, in-person). The `interactions` table already exists in the DB. We need to add a `contacted_at` timestamp column (so sales can backdate entries), build a full CRUD API, and create the frontend page.

---

## Technical Solution

### Data model change
The existing `interactions` table has: `id, customer_id, sales_id, channel, summary, created_at`.
Missing: a user-controlled **`contacted_at`** datetime so sales can log a call that happened yesterday.

Add via Alembic migration: `contacted_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

### Backend
- New router `backend/app/api/interactions.py` under prefix `/api/interactions`
- Auth guard identical to customers: sales sees only their own rows, manager sees all
- Also update `customers.last_contacted_at` when a new interaction is logged (touch via UPDATE)

### Frontend
- New route `/contacts` → `frontend/src/routes/ContactsPage.tsx`
- Simple top nav in `App.tsx` to link Customers ↔ Contacts ↔ Inventory
- Log form: customer picker (dropdown from `/api/customers`), channel radio/select, date field, summary textarea
- Table: Date | Channel | Customer | Summary | Delete

---

## Implementation Steps

### Step 1 — Alembic migration `0003_interactions_contacted_at.py`
- Add `contacted_at` column to `interactions` table (`TIMESTAMPTZ NOT NULL DEFAULT now()`)
- Apply via `alembic upgrade head` inside Docker backend container

**File**: `backend/alembic/versions/0003_interactions_contacted_at.py`

```python
revision = "0003"
down_revision = "0002"

def upgrade():
    op.add_column(
        "interactions",
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_column("interactions", "contacted_at")
```

### Step 2 — Update `Interaction` ORM model
**File**: `backend/app/models/interaction.py`

Add:
```python
contacted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
customer: Mapped["Customer"] = relationship("Customer")
```

Also update `Customer` model to accept back-populate if desired (optional).

### Step 3 — New API router `backend/app/api/interactions.py`

Schemas:
```python
class InteractionCreate(BaseModel):
    customer_id: int
    channel: str          # "call" | "text" | "email" | "in-person"
    summary: str
    contacted_at: Optional[datetime] = None   # defaults to now() if omitted

class InteractionOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str    # joined from Customer
    channel: str
    summary: str
    contacted_at: datetime
    created_at: datetime
```

Endpoints:
- `GET /api/interactions` — list (optional `?customer_id=N` filter)
  - Sales: WHERE sales_id = me; Manager: all
  - JOIN customers to get `customer_name`
- `POST /api/interactions` — create
  - validate channel in {"call","text","email","in-person"}
  - set `sales_id = current_user.id`
  - after insert, UPDATE customers SET last_contacted_at = now() WHERE id = customer_id
- `DELETE /api/interactions/{id}` — delete own; manager can delete any

### Step 4 — Wire router in `main.py`
```python
from app.api.interactions import router as interactions_router
app.include_router(interactions_router, prefix="/api/interactions")
```

### Step 5 — Frontend `ContactsPage.tsx`

**File**: `frontend/src/routes/ContactsPage.tsx`

Structure:
```
ContactsPage
├── Log Contact form (collapsible with "+ Log Contact" toggle)
│   ├── Customer selector (searchable <select> from /api/customers)
│   ├── Channel selector: Call | Text | Email | In-Person (button group or <select>)
│   ├── Date input (type="date", defaults to today)
│   └── Summary textarea
├── Filter bar (search by customer name, channel filter dropdown)
└── Table
    ├── Date (formatted, sorted newest first)
    ├── Channel (colored badge)
    ├── Customer name
    ├── Summary (truncated, click to expand)
    └── Delete button
```

Channel badge colors:
- call → green
- text → blue  
- email → orange
- in-person → purple

### Step 6 — App routing + nav

**File**: `frontend/src/App.tsx`

Add route:
```tsx
<Route path="/contacts" element={<ProtectedRoute><ContactsPage /></ProtectedRoute>} />
```

**Add a simple top navigation bar** shared between pages:

```tsx
// Nav component (inline in App.tsx or extracted)
// Links: Customers (/customers) | Contacts (/contacts) | Inventory (/inventory)
// Active link gets underline/bold
// Sign out button on far right
```

Move the "Sign out" button from CustomersPage into the shared nav.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/alembic/versions/0003_interactions_contacted_at.py` | Create | Add `contacted_at` column |
| `backend/app/models/interaction.py` | Modify | Add `contacted_at` field + Customer relationship |
| `backend/app/api/interactions.py` | Create | CRUD router for interactions |
| `backend/app/main.py` | Modify | Register interactions router |
| `frontend/src/routes/ContactsPage.tsx` | Create | Full contacts UI |
| `frontend/src/App.tsx` | Modify | Add /contacts route + nav bar |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `contacted_at` migration fails if backend already running | Run `alembic upgrade head` in backend container with advisory lock (already in startup logic) |
| Customer selector performance with many customers | Load once on mount, local filter in JS |
| `last_contacted_at` update race condition | Single-row UPDATE inside the same transaction as INSERT |
| Channel validation | Whitelist enum check on backend, matching button group on frontend |

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: none
- GEMINI_SESSION: none
