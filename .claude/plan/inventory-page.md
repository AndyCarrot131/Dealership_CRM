# Implementation Plan: Inventory Page (Full CRUD)

## Summary

Replace the stub backend endpoint and placeholder frontend with a fully functional
Inventory page. All authenticated users (both `sales` and `manager` roles) have
unrestricted CRUD access — inventory is dealership-wide with no per-sales isolation.

---

## Current State

| File | State |
|------|-------|
| `backend/app/models/inventory.py` | Complete — model already defined |
| `backend/app/api/inventory.py` | **Stub** — returns `{"inventory": []}`, no DB, no schemas |
| `frontend/src/routes/InventoryPage.tsx` | **Stub** — static placeholder text |
| `backend/app/main.py` | Already mounts router at `/api/inventory` |

### Inventory Model Fields (from `models/inventory.py`)
```
id          int           PK
make        str(60)       required
model       str(60)       required
year        int           required
trim        str(60)?      optional
mileage     int?          optional
price       Numeric(12,2)?optional
vin         str(17)?      unique, optional
status      str(20)       default="available"  → "available"|"reserved"|"sold"
added_at    datetime      server_default=now()
```

---

## Task Type
- [x] Fullstack — backend + frontend in parallel conceptually, implement backend first

---

## Technical Solution

**Backend**: Full CRUD router following the exact `customers.py` pattern:
- Pydantic schemas: `InventoryOut`, `InventoryCreate`, `InventoryUpdate`
- All four routes require `get_current_user` only (no `require_manager`)
- `UPDATE` uses `model_dump(exclude_unset=True)` to allow partial patches

**Frontend**: Follow `CustomersPage.tsx` patterns exactly:
- State: `items`, `loading`, `error`, `showForm`, `form`, `submitting`, `formError`, `editingItem`, `search`, `statusFilter`
- Client-side search on make + model + trim + VIN + year
- Client-side status filter dropdown
- `EditModal` component matching the customer edit modal style
- Status badge pill colors: `available`=green, `reserved`=amber, `sold`=gray

---

## Implementation Steps

### Step 1 — Backend: `backend/app/api/inventory.py`

Replace the stub entirely with:

```python
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models.inventory import Inventory
from app.models.user import User

router = APIRouter(tags=["inventory"])


class InventoryOut(BaseModel):
    id: int
    make: str
    model: str
    year: int
    trim: Optional[str]
    mileage: Optional[int]
    price: Optional[Decimal]
    vin: Optional[str]
    status: str
    added_at: datetime

    model_config = {"from_attributes": True}


class InventoryCreate(BaseModel):
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    mileage: Optional[int] = None
    price: Optional[Decimal] = None
    vin: Optional[str] = None
    status: str = "available"


class InventoryUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    trim: Optional[str] = None
    mileage: Optional[int] = None
    price: Optional[Decimal] = None
    vin: Optional[str] = None
    status: Optional[str] = None


@router.get("", response_model=list[InventoryOut])
async def list_inventory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Inventory]:
    result = await db.execute(
        select(Inventory).order_by(Inventory.added_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=InventoryOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    body: InventoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Inventory:
    item = Inventory(
        make=body.make,
        model=body.model,
        year=body.year,
        trim=body.trim,
        mileage=body.mileage,
        price=body.price,
        vin=body.vin or None,
        status=body.status,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{item_id}", response_model=InventoryOut)
async def update_inventory_item(
    item_id: int,
    body: InventoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Inventory:
    result = await db.execute(select(Inventory).where(Inventory.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Inventory).where(Inventory.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    await db.delete(item)
    await db.commit()
```

**Key decisions:**
- `vin=body.vin or None` converts empty string to NULL (avoids unique constraint clash on `""`)
- No role restriction on any route — any authenticated user can do anything
- `model_dump(exclude_unset=True)` on UPDATE means unspecified fields are not touched

---

### Step 2 — Frontend: `frontend/src/routes/InventoryPage.tsx`

Full replacement following `CustomersPage.tsx` structure. Key design choices:

**Interfaces:**
```ts
interface InventoryItem {
  id: number;
  make: string;
  model: string;
  year: number;
  trim: string | null;
  mileage: number | null;
  price: number | null;   // Decimal comes through as number from JSON
  vin: string | null;
  status: string;         // "available" | "reserved" | "sold"
  added_at: string;
}

interface ItemForm {
  make: string;
  model: string;
  year: string;           // string for input, parse to int on submit
  trim: string;
  mileage: string;        // string for input, parse to int on submit
  price: string;          // string for input, parse to float on submit
  vin: string;
  status: string;
}
```

**Status badge styling:**
```ts
const STATUS_STYLES: Record<string, React.CSSProperties> = {
  available: { background: "#dcfce7", color: "#166534" },
  reserved:  { background: "#fef3c7", color: "#92400e" },
  sold:      { background: "#f3f4f6", color: "#6b7280" },
};
```

**Helpers:**
```ts
function fmtPrice(p: number | null): string {
  if (p == null) return "—";
  return "$" + p.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtMileage(m: number | null): string {
  if (m == null) return "—";
  return m.toLocaleString("en-US") + " mi";
}
```

**Filtering (client-side):**
```ts
// search: make, model, trim, VIN, year (string contains)
// statusFilter: "" means all
const query = search.trim().toLowerCase();
const visible = items.filter((it) => {
  const matchStatus = !statusFilter || it.status === statusFilter;
  const matchSearch = !query || [it.make, it.model, it.trim, it.vin, String(it.year)]
    .some((v) => v?.toLowerCase().includes(query));
  return matchStatus && matchSearch;
});
```

**Table columns:** ID | Year Make Model (+ Trim as muted) | VIN | Mileage | Price | Status | Added | Actions

**EditModal fields** (uses `<select>` for status):
- Make * (required)
- Model * (required)  
- Year * (required, number input)
- Trim (optional)
- Mileage (optional, number input)
- Price (optional, number input with `$` label)
- VIN (optional, max 17 chars)
- Status (select: available / reserved / sold)

**Add form** (inline below header, same style as customers):
Same fields as EditModal but inline collapsed form.

**API calls:**
```ts
// fetch
const data = await api.get<InventoryItem[]>("/inventory");

// create
const created = await api.post<InventoryItem>("/inventory", {
  make, model, year: parseInt(year), trim: trim || null,
  mileage: mileage ? parseInt(mileage) : null,
  price: price ? parseFloat(price) : null,
  vin: vin || null, status
});

// update
const updated = await api.put<InventoryItem>(`/inventory/${item.id}`, { ... });

// delete
await api.delete(`/inventory/${item.id}`);
```

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/api/inventory.py` | Full replace | Add Pydantic schemas + 4 CRUD routes with DB session |
| `frontend/src/routes/InventoryPage.tsx` | Full replace | Full CRUD UI: table, add form, edit modal, search, status filter |

No new files needed. No migration needed (table already exists from `0001_initial_schema.py`).

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| VIN unique constraint fails on empty string | Convert `""` to `None` before insert: `vin=body.vin or None` |
| Price `Decimal` → JSON serialization | Pydantic serializes `Decimal` to string by default; use `Optional[float]` in `InventoryOut` or set `json_encoders` — simpler: use `Optional[Decimal]` with `model_config = {"from_attributes": True}` which FastAPI handles |
| Year/mileage/price as string in form inputs | Parse in submit handler with `parseInt` / `parseFloat`; validate non-empty before calling API |

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A (plan generated by Claude directly from codebase analysis)
- GEMINI_SESSION: N/A
