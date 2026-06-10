# Plan: Inventory Features, Notes & Duplicate Button

## Summary

Three additions to the Inventory module:

1. **`features` field** — free-text area for vehicle options (e.g. "blind spot monitoring, back camera, heated seats")
2. **`notes` field** — free-text dealer note (e.g. "can be put on sale", "needs detail before delivery")
3. **Duplicate button** — copies a row into the Add Vehicle form (VIN cleared) so the dealer can quickly add similar cars

---

## Affected Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/alembic/versions/0004_inventory_features_notes.py` | Create | Migration: add `features` and `notes` TEXT columns |
| `backend/app/models/inventory.py` | Modify | Add ORM columns `features`, `notes` |
| `backend/app/api/inventory.py` | Modify | Add fields to Pydantic schemas + create/update logic |
| `frontend/src/routes/InventoryPage.tsx` | Modify | Types, form fields, table display, duplicate button |

---

## Step-by-Step Implementation

### Step 1 — Alembic Migration

Create `backend/alembic/versions/0004_inventory_features_notes.py`:

```python
"""add features and notes to inventory

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("inventory", sa.Column("features", sa.Text(), nullable=True))
    op.add_column("inventory", sa.Column("notes", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("inventory", "notes")
    op.drop_column("inventory", "features")
```

> Note: check `down_revision` against the actual revision ID of `0003_interactions_contacted_at.py`.

---

### Step 2 — SQLAlchemy Model

In `backend/app/models/inventory.py`, add after the `status` column:

```python
from sqlalchemy import Text  # add to existing import

features: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
notes: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
```

---

### Step 3 — Pydantic Schemas & API Endpoints

In `backend/app/api/inventory.py`:

**`InventoryOut`** — add:
```python
features: Optional[str]
notes: Optional[str]
```

**`InventoryCreate`** — add:
```python
features: Optional[str] = None
notes: Optional[str] = None
```

**`InventoryUpdate`** — add:
```python
features: Optional[str] = None
notes: Optional[str] = None
```

**`create_inventory_item`** — add `features=body.features, notes=body.notes` to the `Inventory(...)` constructor call.

The `update_inventory_item` endpoint uses `model_dump(exclude_unset=True)` with `setattr`, so no changes needed there — it picks up new fields automatically.

---

### Step 4 — Frontend: Type Definitions & Form State

In `frontend/src/routes/InventoryPage.tsx`:

**`InventoryItem` interface** — add:
```ts
features: string | null;
notes: string | null;
```

**`ItemForm` interface** — add:
```ts
features: string;
notes: string;
```

**`EMPTY_FORM`** — add:
```ts
features: "",
notes: "",
```

**`toEditForm(item)`** — add:
```ts
features: item.features ?? "",
notes: item.notes ?? "",
```

**`parseForm(form)`** — add:
```ts
features: form.features || null,
notes: form.notes || null,
```

---

### Step 5 — Form Fields UI

Add to `VehicleFormFields` (below the VIN/Status row), full-width textareas:

```tsx
<div>
  <label style={labelStyle}>Features</label>
  <textarea
    style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
    placeholder="e.g. blind spot monitoring, back camera, heated seats"
    value={form.features}
    onChange={(e) => setForm({ ...form, features: e.target.value })}
  />
</div>
<div>
  <label style={labelStyle}>Notes</label>
  <textarea
    style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
    placeholder="e.g. can be put on sale, needs detail before delivery"
    value={form.notes}
    onChange={(e) => setForm({ ...form, notes: e.target.value })}
  />
</div>
```

---

### Step 6 — Table Display

In the table row's "Vehicle" cell, add features and notes as secondary lines:

```tsx
<td style={{ ...cell, fontWeight: 500 }}>
  {it.year} {it.make} {it.model}
  {it.trim && (
    <span style={{ marginLeft: 6, fontWeight: 400, color: "#888", fontSize: 12 }}>{it.trim}</span>
  )}
  {it.features && (
    <div
      style={{ fontWeight: 400, fontSize: 11, color: "#666", marginTop: 2 }}
      title={it.features}  // full text on hover
    >
      {it.features.length > 55 ? it.features.slice(0, 55) + "…" : it.features}
    </div>
  )}
  {it.notes && (
    <div style={{ fontWeight: 400, fontSize: 11, color: "#b45309", fontStyle: "italic", marginTop: 1 }}>
      📝 {it.notes.length > 50 ? it.notes.slice(0, 50) + "…" : it.notes}
    </div>
  )}
</td>
```

---

### Step 7 — Duplicate Button

Add `handleDuplicate` function inside `InventoryPage`:

```tsx
function handleDuplicate(it: InventoryItem) {
  setForm({
    make: it.make,
    model: it.model,
    year: String(it.year),
    trim: it.trim ?? "",
    mileage: it.mileage != null ? String(it.mileage) : "",
    price: it.price != null ? String(it.price) : "",
    vin: "",                    // VINs are unique — always clear
    status: "available",        // reset to available
    features: it.features ?? "",
    notes: it.notes ?? "",
  });
  setShowForm(true);
  setFormError(null);
}
```

Add "Duplicate" button in the actions cell (between Edit and Delete):

```tsx
<button
  onClick={() => handleDuplicate(it)}
  style={{ fontSize: 12, marginRight: 6, color: "#2563eb" }}
>
  Duplicate
</button>
```

---

## Edge Cases & Risks

| Risk | Mitigation |
|------|------------|
| VIN uniqueness violation on duplicate | Duplicate always clears VIN — enforced in `handleDuplicate` |
| Long features text overflows table | Truncate at 55 chars; full text exposed via `title` tooltip |
| `down_revision` mismatch | Verify actual revision ID in `0003_interactions_contacted_at.py` before creating migration |
| `Text()` import in model | Add `Text` to the existing `sqlalchemy` import in `inventory.py` |

---

## SESSION_ID
- CODEX_SESSION: N/A (Claude-only plan)
- GEMINI_SESSION: N/A (Claude-only plan)
