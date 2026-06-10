# Implementation Plan: Style Categories

## Summary

Sales can manage a named list of categories per channel (e.g., "Lease/Finance Expiration",
"Test Drive Follow-Up", "Tire Sales"). When adding a sample message they pick a category from
the list. When summarizing, the LLM is **forced** to produce one style section per category
that has samples — rather than inferring structure from whatever free-text labels happen to exist.

---

## Technical Solution

Keep `SampleMessage.label` as a plain string (no FK). Categories are stored in a new
`style_categories` table. The label on a sample IS the category name (string match). This is
backward-compatible and avoids a nullable FK migration on `sample_messages`.

The style summarizer is enhanced to accept an explicit category list and restructure its
system prompt to mandate one section per category.

---

## Implementation Steps

### Step 1 — DB Migration `0006_style_categories.py`

New file: `backend/alembic/versions/0006_style_categories.py`

```
revision = "0006"
down_revision = "0005"

upgrade():
  op.create_table(
    "style_categories",
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("sales_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("channel", sa.String(10), nullable=False),
    sa.Column("name", sa.String(100), nullable=False),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("sales_id", "channel", "name", name="uq_style_category"),
  )

downgrade():
  op.drop_table("style_categories")
```

---

### Step 2 — ORM Model (`backend/app/models/style.py`)

Add `StyleCategory` class after the existing models:

```python
class StyleCategory(Base):
    __tablename__ = "style_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("sales_id", "channel", "name", name="uq_style_category"),
    )
```

---

### Step 3 — API Endpoints (`backend/app/api/style.py`)

**New schemas:**
```python
class CategoryCreate(BaseModel):
    channel: str
    name: str

class CategoryOut(BaseModel):
    id: int
    channel: str
    name: str
    model_config = {"from_attributes": True}
```

**New routes:**

`GET /style/categories?channel=email`
- Filter by `sales_id == current_user.id`
- Filter by `channel` if provided
- Return `list[CategoryOut]` ordered by `name`

`POST /style/categories`
- Body: `CategoryCreate`
- Validate channel
- Strip and validate name (non-empty, max 100 chars)
- Insert, handle unique constraint → 409 if duplicate
- Return `CategoryOut` (201)

`DELETE /style/categories/{category_id}`
- Load row, verify `sales_id` ownership
- Delete row (does NOT cascade to samples — label strings stay on samples)
- Return 204

**Modify `POST /style/summarize/{channel}`:**
- After fetching samples, also fetch all `StyleCategory` rows for `(current_user.id, channel)`
- Extract `category_names = [c.name for c in categories]`
- Pass `category_names` to `run_style_summarizer`

---

### Step 4 — Style Summarizer (`backend/app/agents/style_summarizer.py`)

**Change signature:**
```python
async def run_style_summarizer(
    samples: list[tuple[str, str]],   # (label, raw_content)
    channel: str,
    llm: LLMClient,
    categories: list[str] | None = None,   # NEW: managed category names
) -> str:
```

**New grouping logic:**
- Build `groups` as before (group by label, empty label → "General")
- If `categories` is provided and non-empty:
  - Build `ordered_keys`: start with matching categories (in order), then append any
    leftover group keys (samples whose label isn't in the category list)
  - Only include groups that have at least one sample

**New system prompt section when categories provided:**
Replace the current generic prompt with one that names the categories explicitly:

```
The writer's samples are organized into the following categories:
{category_list}

Produce one ## section for each category that has samples provided.
Use the exact category name as the ## heading.
If a sample's label does not match any category, place it under ## General.
```

The rest of the prompt (### Format / ### Style sub-sections) stays the same.

---

### Step 5 — Frontend (`frontend/src/routes/StylePage.tsx`)

**New state:**
```typescript
const [categories, setCategories] = useState<Category[]>([]);
const [newCatName, setNewCatName] = useState("");
const [addingCat, setAddingCat] = useState(false);
```

**New interface:**
```typescript
interface Category { id: number; channel: string; name: string; }
```

**Data loading:**
- `fetchCategories()` called in the same `useEffect` as `fetchSamples` and `fetchProfile`
- `GET /style/categories?channel={activeChannel}`

**Category management panel** (add to left column, above the add-sample form):
- Section header: "Categories"
- List of category pills/chips with a "×" delete button each
- "Add category" inline form: text input + "Add" button
- On add: `POST /style/categories` → push to `categories` state
- On delete: `DELETE /style/categories/{id}` → filter from state

**Sample add form:**
- Replace the free-text `<input placeholder="Label (optional)">` with a `<select>` + optional fallback:
  ```
  <select value={newLabel} onChange={...}>
    <option value="">— No category —</option>
    {categories.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
  </select>
  ```
  Keep the text input hidden but populated from the select, OR just use the select value as the label.
  If user picks "— No category —", `label` is sent as empty string.

- No custom free-text for label on this form — category must come from the managed list.
  (Existing samples with old free-text labels are still shown correctly, just not editable to new category names.)

**Sample list display:**
- Show the category pill/badge on each sample card more prominently (already works via `s.label`)

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/alembic/versions/0006_style_categories.py` | Create | New migration for style_categories table |
| `backend/app/models/style.py` | Modify | Add StyleCategory ORM model |
| `backend/app/api/style.py` | Modify | Add 3 category CRUD endpoints; pass categories to summarizer |
| `backend/app/agents/style_summarizer.py` | Modify | Accept categories param; update system prompt |
| `frontend/src/routes/StylePage.tsx` | Modify | Category management UI + dropdown in sample add form |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Existing samples have free-text labels that don't match new categories | They still display and get grouped under their label name; user can re-categorize by deleting and re-adding |
| Unique constraint violation on duplicate category name | API returns 409 with clear message; frontend shows it as inline error |
| LLM ignores explicit category list | System prompt uses hard directive "Produce one ## section for EACH category"; already tested to work with label grouping |
| Category deleted but samples still reference label string | Fine — samples keep their label string, just lose the category pill highlight; label still groups correctly in summarizer |

---

## SESSION_ID
- CODEX_SESSION: N/A (Claude-native plan, no external model calls)
- GEMINI_SESSION: N/A
