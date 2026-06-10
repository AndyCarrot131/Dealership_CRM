# Implementation Plan: Remaining 4 Agents

## Context

Only the **Intake Agent** is currently implemented (`backend/app/agents/intake.py` + `backend/app/api/chat.py`). All five ORM models are in place (`SampleMessage`, `StyleProfile`, `OutreachRule`, `EmailDraft`, and existing `Customer`/`CustomerCar`/`Interaction`). The task is to implement the remaining 4 agents from PROJECT.md §7 and wire them end-to-end.

---

## Agents to Implement

| Agent | File | Trigger |
|---|---|---|
| Update Agent | `app/agents/update.py` | Chat in "update" mode with a customer_id in context |
| Style Summarizer | `app/agents/style_summarizer.py` | POST /api/style/summarize/{channel} |
| Rule Parser | `app/agents/rule_parser.py` | Called on save/run of an OutreachRule |
| Email Composer | `app/agents/email_composer.py` | Called per-customer inside outreach rule execution |

---

## Step-by-Step Plan

### Step 1 — Update Agent (`app/agents/update.py`)

**Responsibility:** Accept a conversational message describing changes to an existing customer and/or their car. Return a structured diff via tool-call.

**Tool definition:**

```python
_UPDATE_TOOL = {
    "type": "function",
    "function": {
        "name": "update_customer_fields",
        "description": "Produce a diff of fields to update on a customer and/or their primary car",
        "parameters": {
            "type": "object",
            "properties": {
                # customer fields — all optional
                "full_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "note": {"type": "string"},
                # car fields — all optional; applies to the car specified by car_id
                "car_id": {"type": "integer", "description": "ID of the car to update; omit to skip car update"},
                "car_make": {"type": "string"},
                "car_model": {"type": "string"},
                "car_year": {"type": "integer"},
                "car_ownership_type": {"type": "string", "enum": ["own", "lease", "finance"]},
                "car_lease_end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            },
            "required": [],
        },
    },
}
```

**Function signature:**

```python
async def run_update(
    history: list[dict],
    customer_snapshot: dict,   # current DB values to give LLM context
    llm: LLMClient,
) -> dict:
    # Returns: { intent: "update_customer", diff: {...}, reply: str }
    # OR:      { intent: "unknown", diff: None, reply: str }
```

**System prompt:** Tell the LLM it knows the current customer values (injected into system message) and to call `update_customer_fields` only with fields that should change.

---

### Step 2 — Style Summarizer (`app/agents/style_summarizer.py`)

**Responsibility:** Take a list of raw sample messages (all for one sales × channel), call LLM once (no tool-call, plain completion), return a `style_md` string.

**Function signature:**

```python
async def run_style_summarizer(
    samples: list[str],
    channel: str,          # "email" | "text"
    llm: LLMClient,
) -> str:
    # Returns style_md markdown string
```

**Prompt structure:**
- System: "You are a writing style analyst. Extract the writing style of the following {channel} samples into a concise markdown guide that another AI can use to write in the same style."
- User: joined sample texts
- No tools — pure text completion, return `choices[0].message.content`

---

### Step 3 — Rule Parser Agent (`app/agents/rule_parser.py`)

**Responsibility:** Convert natural-language outreach rule text into a validated JSON predicate tree.

**Whitelist columns (with table prefix):**

```python
ALLOWED_COLUMNS = frozenset({
    "customers.last_contacted_at",
    "customer_car.make",
    "customer_car.model",
    "customer_car.year",
    "customer_car.ownership_type",
    "customer_car.lease_end_date",
})
```

**Predicate tree schema:**

```json
{
  "op": "and",
  "conditions": [
    { "col": "customer_car.ownership_type", "cmp": "eq", "val": "lease" },
    { "col": "customer_car.lease_end_date", "cmp": "lte", "val": "2025-12-31" },
    { "col": "customers.last_contacted_at", "cmp": "days_ago_gte", "val": 30 }
  ]
}
```

Operators (whitelist): `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `days_ago_gte`, `days_ago_lte`.

**Tool definition:** `parse_outreach_rule` with the JSON schema of the predicate tree.

**Function signature:**

```python
async def run_rule_parser(
    rule_text: str,
    llm: LLMClient,
) -> dict:
    # Returns compiled_filter dict or raises ValueError on whitelist violation
```

**Validation step (after tool-call):** Walk every node in returned JSON, verify every `col` is in `ALLOWED_COLUMNS` and every `cmp` is in the operator whitelist. Raise `ValueError` on any violation — never pass unvalidated output to SQL.

---

### Step 4 — Email Composer (`app/agents/email_composer.py`)

**Responsibility:** Given customer data, matched inventory items, and the sales style profile, produce a subject + body for one outreach email.

**Function signature:**

```python
async def compose_email(
    customer: dict,                  # full_name, note, cars list, etc.
    inventory_matches: list[dict],   # matching inventory rows (make/model/year/price)
    style_md: str,                   # sales person's email_style.md
    llm: LLMClient,
) -> dict:
    # Returns: { subject: str, body: str }
```

No tool-calls — plain completion. Parse output as `Subject: ...\n\n<body>` or use a structured prompt that asks for JSON output.

---

### Step 5 — Filter Compiler (`app/services/filter_compiler.py`)

**Responsibility:** Convert a validated `compiled_filter` JSON tree into a SQLAlchemy WHERE clause, with joins to `customer_car` when needed.

**Function:**

```python
def compile_filter(filter_tree: dict) -> sa.ColumnElement:
    # Recursively walks predicate tree
    # Returns SQLAlchemy expression
    # Uses join to customer_car for car-related columns
    # operators: eq → ==, gte → >=, etc.
    # days_ago_gte → customer_car.lease_end_date <= (now - timedelta(days=val))
```

This function is purely deterministic — no LLM, no SQL injection surface because column names come only from the whitelist-validated compiled_filter.

---

### Step 6 — `/api/chat` Extension (`app/api/chat.py`)

Add `mode` and `customer_id` to `ChatRequest`:

```python
class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    mode: str = "intake"          # "intake" | "update"
    customer_id: int | None = None
```

Route inside `POST /api/chat`:
- `mode == "intake"` → existing `run_intake()`
- `mode == "update"` → fetch customer snapshot from DB, call `run_update()`

Add `update_customer` intent handling in `POST /api/chat/confirm`:
- Accept `mode` + `customer_id` in `ConfirmRequest`
- Apply diff to `Customer` and/or `CustomerCar` via ORM

---

### Step 7 — `/api/style` Router (`app/api/style.py`)

```
GET  /api/style/samples            → list SampleMessage for current sales
POST /api/style/samples            → create SampleMessage
DELETE /api/style/samples/{id}     → delete
GET  /api/style/profile/{channel}  → get StyleProfile (email | text)
POST /api/style/summarize/{channel} → run Style Summarizer; upsert StyleProfile
```

---

### Step 8 — `/api/outreach` Router (`app/api/outreach.py`)

```
GET    /api/outreach/rules                → list my rules
POST   /api/outreach/rules                → create rule (auto-parse with Rule Parser)
PUT    /api/outreach/rules/{id}           → update rule (re-parse)
DELETE /api/outreach/rules/{id}           → delete
POST   /api/outreach/rules/{id}/run       → execute rule flow (see below)
```

**Rule run flow (POST /api/outreach/rules/{id}/run):**
1. Load rule → `compiled_filter`
2. Call `compile_filter()` to get SQLAlchemy expression
3. Query: `SELECT customers WHERE compiled_filter AND last_contacted_at < (now - cadence_days)`
4. Load sales `email_style.md` from `style_profiles`
5. For each matched customer: call `compose_email()` → insert `EmailDraft(status="pending")`
6. Return `{ drafts_created: N, customer_ids: [...] }`

---

### Step 9 — `/api/drafts` Router (add to `app/api/outreach.py` or new file)

```
GET   /api/drafts                  → list pending/all drafts for current sales
PATCH /api/drafts/{id}             → edit subject/body
POST  /api/drafts/{id}/approve     → approve: status=approved, update last_contacted_at, insert Interaction
POST  /api/drafts/{id}/dismiss     → dismiss: status=dismissed
```

---

### Step 10 — Register New Routers (`app/main.py`)

```python
from app.api.style import router as style_router
from app.api.outreach import router as outreach_router

app.include_router(style_router, prefix="/api/style")
app.include_router(outreach_router, prefix="/api/outreach")
```

---

### Step 11 — Frontend: AgentChat Update Mode

Extend `AgentChat.tsx`:
- Add props `mode?: "intake" | "update"` and `customerId?: number`
- Pass `mode` and `customer_id` in the `/api/chat` request body
- Placeholder text changes: "intake" → "Describe a new customer…", "update" → "Describe what changed…"
- Handle `update_customer` intent → show diff confirmation card (similar to `PendingConfirm`)

On `CustomersPage.tsx`: When a customer row is selected, an "Update with AI" button opens the sidebar `AgentChat` in update mode with `customerId` set.

---

### Step 12 — Frontend: StylePage (`routes/StylePage.tsx`)

- Two tabs: **Email Samples** and **Text Samples**
- List of sample messages (label + truncated preview + delete button)
- Add sample form: textarea + label input + channel selector
- "Summarize [channel]" button → POST /api/style/summarize/{channel}
- Read-only style profile markdown preview below the button

---

### Step 13 — Frontend: OutreachPage (`routes/OutreachPage.tsx`)

- List outreach rules (name, cadence_days, active toggle)
- Create rule form: name + rule_text textarea + cadence_days
- "Run Rule" button → POST /api/outreach/rules/{id}/run → shows toast with draft count

---

### Step 14 — Frontend: InboxPage (`routes/InboxPage.tsx`)

- List of pending `EmailDraft` rows (customer name, subject, created_at)
- Expand a row to see + edit subject/body inline
- Approve / Dismiss buttons
- After approve: show "Approved" badge, update list

---

### Step 15 — NavBar + Routing (`NavBar.tsx`, `App.tsx`)

Add nav links:
- `/style` → StylePage
- `/outreach` → OutreachPage
- `/inbox` → InboxPage (with pending count badge if possible)

---

## Key Files

| File | Operation | Description |
|---|---|---|
| `backend/app/agents/update.py` | Create | Update Agent — field diff via tool-call |
| `backend/app/agents/style_summarizer.py` | Create | Style Summarizer — plain completion |
| `backend/app/agents/rule_parser.py` | Create | Rule Parser — JSON predicate tree + whitelist validation |
| `backend/app/agents/email_composer.py` | Create | Email Composer — subject + body |
| `backend/app/services/filter_compiler.py` | Create | Predicate tree → SQLAlchemy expression |
| `backend/app/api/chat.py` | Modify | Add mode/customer_id routing; confirm for update intent |
| `backend/app/api/style.py` | Create | Sample messages + style profile CRUD + summarize trigger |
| `backend/app/api/outreach.py` | Create | Rules CRUD + run + drafts CRUD |
| `backend/app/main.py` | Modify | Register style + outreach routers |
| `frontend/src/components/AgentChat.tsx` | Modify | Support update mode + diff confirmation card |
| `frontend/src/routes/StylePage.tsx` | Create | Sample messages + style profile UI |
| `frontend/src/routes/OutreachPage.tsx` | Create | Outreach rules management + run |
| `frontend/src/routes/InboxPage.tsx` | Create | Email draft inbox approve/dismiss |
| `frontend/src/components/NavBar.tsx` | Modify | Add Style, Outreach, Inbox links |
| `frontend/src/App.tsx` | Modify | Add routes for new pages |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Rule Parser generates invalid column names | Strict whitelist check post-tool-call; reject entire rule if any column fails validation |
| filter_compiler joins produce fan-out duplicates | Use `EXISTS` subquery for customer_car conditions instead of direct JOIN |
| Email Composer output format inconsistent | Use a structured prompt asking for JSON `{subject, body}`, parse with fallback |
| Update Agent diff includes unchanged fields | Prompt explicitly says "only include fields that should change"; minimal diff |
| Style Summarizer called with 0 samples | Return empty string early; do not call LLM |

---

## Build Order

Implement backend-first (Steps 1–10), then frontend (Steps 11–15).

Within backend:
- Steps 1–4 are independent (each agent); can be done in parallel
- Step 5 (filter compiler) must precede Step 8 (outreach run endpoint)
- Steps 6–9 (API routers) depend on agents from Steps 1–4
- Step 10 is last (register routers)

Within frontend:
- Step 11 (AgentChat update mode) is independent
- Steps 12–14 (new pages) are independent of each other
- Step 15 (NavBar + routing) is last
