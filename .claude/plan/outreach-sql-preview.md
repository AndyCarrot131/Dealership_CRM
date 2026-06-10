# Plan: Show SQL Preview in Outreach Rules

## Overview

When the AI translates a natural-language outreach rule into a compiled filter, show the
resulting SQL WHERE clause in the UI so the sales rep can verify what the AI understood.

**Current state:**  
- User writes English → `rule_parser.py` produces a JSON predicate tree → stored in `compiled_filter`  
- Frontend shows "Parsed ✓" but nothing more  

**Target state:**  
- Backend exposes a `sql_preview` string alongside each rule  
- Frontend shows the SQL in a collapsible monospace block under each rule card  

---

## Technical Solution

### Backend

`filter_compiler.py` already has `compile_filter()` which returns a SQLAlchemy WHERE clause.
We add a thin `preview_sql(filter_tree)` wrapper that compiles that clause to a SQL string
using `clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})`.

`outreach.py` adds `sql_preview: Optional[str] = None` to `RuleOut`, and a `_rule_to_dict()`
helper that populates it. All three endpoints that return rules (`list_rules`, `create_rule`,
`update_rule`) switch from returning ORM objects directly to returning `_rule_to_dict()` output.

### Frontend

`OutreachPage.tsx` adds `sql_preview?: string | null` to the `OutreachRule` interface.
Under each rule card's metadata line, renders a `<details>` / `<summary>` collapsible block
containing the SQL in a dark `<pre><code>` box.

---

## Implementation Steps

### Step 1 — `backend/app/services/filter_compiler.py`

Add `preview_sql()` after the existing `compile_filter()` function:

```python
from sqlalchemy.dialects import postgresql

def preview_sql(filter_tree: dict[str, Any]) -> str:
    """Compile filter_tree to a human-readable SQL WHERE string for UI display."""
    try:
        clause = compile_filter(filter_tree)
        compiled = clause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        return str(compiled)
    except Exception:
        return ""
```

### Step 2 — `backend/app/api/outreach.py`

**2a. Update `RuleOut` schema** — add `sql_preview` field:

```python
class RuleOut(BaseModel):
    id: int
    name: str
    rule_text: str
    compiled_filter: Optional[dict]
    sql_preview: Optional[str] = None   # ← new
    cadence_days: Optional[int]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

**2b. Add `_rule_to_dict()` helper** at the bottom of the Helpers section:

```python
def _rule_to_dict(rule: OutreachRule) -> dict:
    base = RuleOut.model_validate(rule).model_dump()
    if rule.compiled_filter:
        base["sql_preview"] = preview_sql(rule.compiled_filter)
    return base
```

(Import `preview_sql` from `app.services.filter_compiler`.)

**2c. Update three endpoints** to return `_rule_to_dict()` output instead of bare ORM objects:

- `list_rules` → `return [_rule_to_dict(r) for r in result.scalars().all()]`
- `create_rule` → `return _rule_to_dict(rule)` (change `response_model` to accept dict)
- `update_rule` → `return _rule_to_dict(rule)`

Because `_rule_to_dict` returns a plain dict that matches `RuleOut`, FastAPI will still
validate/serialize it correctly — no `response_model` change required.

### Step 3 — `frontend/src/routes/OutreachPage.tsx`

**3a. Extend interface:**

```ts
interface OutreachRule {
  ...
  sql_preview: string | null;   // ← new
}
```

**3b. Add SQL block inside each rule card**, below the "Cadence / Parsed" line:

```tsx
{rule.sql_preview && (
  <details style={{ marginTop: 6 }}>
    <summary style={{ fontSize: 11, color: "#6b7280", cursor: "pointer", userSelect: "none" }}>
      SQL preview
    </summary>
    <pre
      style={{
        marginTop: 6,
        padding: "8px 12px",
        background: "#1e293b",
        color: "#e2e8f0",
        borderRadius: 6,
        fontSize: 11,
        overflowX: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        lineHeight: 1.5,
      }}
    >
      <code>{rule.sql_preview}</code>
    </pre>
  </details>
)}
```

---

## Key Files

| File | Operation | Change |
|------|-----------|--------|
| [backend/app/services/filter_compiler.py](../../backend/app/services/filter_compiler.py) | Modify | Add `preview_sql()` function |
| [backend/app/api/outreach.py](../../backend/app/api/outreach.py) | Modify | Add `sql_preview` to `RuleOut`, add `_rule_to_dict()`, update 3 endpoints |
| [frontend/src/routes/OutreachPage.tsx](../../frontend/src/routes/OutreachPage.tsx) | Modify | Add `sql_preview` to interface, render `<details>` SQL block in rule card |

---

## Example Output

For the rule text:  
> "customers who lease a Toyota and haven't been contacted in 60 days"

The `sql_preview` field would render as:
```sql
EXISTS (SELECT customer_car.id FROM customer_car WHERE customer_car.customer_id = customers.id
AND customer_car.ownership_type = 'lease' AND customer_car.make = 'Toyota')
AND (customers.last_contacted_at IS NULL OR customers.last_contacted_at <= '2026-04-09 00:00:00')
```

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `literal_binds` fails for certain column types (e.g. DateTime) | Wrap in try/except → return `""` silently; frontend hides block when empty |
| Compiled SQL is too verbose / confusing | Collapse via `<details>` — not shown by default |
| PostgreSQL dialect not installed | `sqlalchemy[postgresql]` is already in requirements via psycopg2 usage |
