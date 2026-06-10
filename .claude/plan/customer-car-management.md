# Implementation Plan: Customer Car Management (Add & Edit)

## Task Type
- [x] Fullstack (Backend + Frontend)

## Problem Statement
The `EditModal` in `CustomersPage.tsx` currently shows customer vehicles as read-only with
the message "Vehicle records are managed separately." There are no API endpoints for creating
or updating `CustomerCar` records. This plan adds full add/edit/delete capability for cars
within the Edit Customer modal.

---

## Technical Solution

### Backend
Add 3 new endpoints to `backend/app/api/customers.py` under the existing customers router.
They nest under `/api/customers/{customer_id}/cars/...` so access control reuses the
existing pattern (check `assigned_sales_id` or manager role).

New Pydantic schemas:
- `CarCreate` — all optional except nothing required (all fields are optional on the model)
- `CarUpdate` — same fields, all optional

New endpoints:
- `POST   /customers/{customer_id}/cars`             → create car, return updated CustomerOut
- `PUT    /customers/{customer_id}/cars/{car_id}`    → update car, return updated CustomerOut
- `DELETE /customers/{customer_id}/cars/{car_id}`    → delete car, return updated CustomerOut

Returning the full `CustomerOut` (with refreshed cars) on every mutation simplifies the
frontend: one response replaces the whole customer record in local state.

### Frontend
Replace the static vehicle section in `EditModal` with an inline car manager:

1. **Car list** — each car row shows label + ownership badge + "Edit" + "Remove" buttons.
2. **Inline car form** — appears below the list when "Add Vehicle" is clicked or "Edit" is
   clicked on an existing car. Fields: make, model, year, ownership_type (select), lease_end_date
   (only when ownership_type === "lease"), is_primary (checkbox).
3. On save the form calls the appropriate backend endpoint and updates the customer in local
   state via `onSave(updatedCustomer)`.
4. "Remove" calls DELETE endpoint with a confirm dialog, then calls `onSave(updatedCustomer)`.

---

## Implementation Steps

### Step 1 — Backend: Add schemas and car endpoints to `customers.py`

**File**: `backend/app/api/customers.py`

Add after `CustomerUpdate`:

```python
class CarCreate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership_type: Optional[str] = None   # "own" | "lease" | "finance"
    lease_end_date: Optional[date] = None
    is_primary: bool = True

class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    ownership_type: Optional[str] = None
    lease_end_date: Optional[date] = None
    is_primary: Optional[bool] = None
```

Add helper to load+authorize a customer:

```python
async def _get_authorized_customer(
    customer_id: int, current_user: User, db: AsyncSession
) -> Customer:
    result = await db.execute(
        select(Customer).options(_with_cars()).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if current_user.role != "manager" and customer.assigned_sales_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return customer
```

Add 3 endpoints:

```python
@router.post("/{customer_id}/cars", response_model=CustomerOut, status_code=201)
async def add_car(...):
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car = CustomerCar(customer_id=customer_id, **body.model_dump())
    db.add(car)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer

@router.put("/{customer_id}/cars/{car_id}", response_model=CustomerOut)
async def update_car(...):
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car_result = await db.execute(
        select(CustomerCar).where(CustomerCar.id == car_id, CustomerCar.customer_id == customer_id)
    )
    car = car_result.scalar_one_or_none()
    if car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(car, field, val)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer

@router.delete("/{customer_id}/cars/{car_id}", response_model=CustomerOut)
async def delete_car(...):
    customer = await _get_authorized_customer(customer_id, current_user, db)
    car_result = await db.execute(
        select(CustomerCar).where(CustomerCar.id == car_id, CustomerCar.customer_id == customer_id)
    )
    car = car_result.scalar_one_or_none()
    if car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    await db.delete(car)
    await db.commit()
    await db.refresh(customer, ["cars"])
    return customer
```

### Step 2 — Frontend: Add car form state types and constants to `CustomersPage.tsx`

Add near the top with existing interfaces:

```tsx
interface CarFormState {
  make: string;
  model: string;
  year: string;           // string for input, convert to int on submit
  ownership_type: string; // "" | "own" | "lease" | "finance"
  lease_end_date: string;
  is_primary: boolean;
}

const EMPTY_CAR_FORM: CarFormState = {
  make: "", model: "", year: "", ownership_type: "", lease_end_date: "", is_primary: true
};
```

### Step 3 — Frontend: Replace static vehicle section in `EditModal`

The existing vehicle display block (lines 143–151 of `CustomersPage.tsx`) gets replaced with
a `CarManager` inline section that tracks:
- `carFormMode: "hidden" | "add" | { editing: CustomerCar }` 
- `carForm: CarFormState`
- `carSaving: boolean`
- `carError: string | null`

**Car list rendering** (when `carFormMode === "hidden"` or showing form below list):
```tsx
{localCars.map(car => (
  <div key={car.id} style={{ display:"flex", alignItems:"center", gap:8, ... }}>
    <span>{label}</span>  {/* existing CarBadge-style display */}
    <button onClick={() => startEdit(car)}>Edit</button>
    <button onClick={() => removeCar(car.id)} style={{ color:"#c00" }}>Remove</button>
  </div>
))}
{carFormMode === "hidden" && (
  <button onClick={() => setCarFormMode("add")}>+ Add Vehicle</button>
)}
```

**Inline car form** (shown when `carFormMode !== "hidden"`):
```tsx
{carFormMode !== "hidden" && (
  <form onSubmit={handleCarSubmit}>
    <input placeholder="Make" value={carForm.make} ... />
    <input placeholder="Model" value={carForm.model} ... />
    <input placeholder="Year" type="number" ... />
    <select value={carForm.ownership_type} ...>
      <option value="">— ownership —</option>
      <option value="own">Owned</option>
      <option value="lease">Lease</option>
      <option value="finance">Financed</option>
    </select>
    {carForm.ownership_type === "lease" && (
      <input type="date" value={carForm.lease_end_date} ... />
    )}
    <label><input type="checkbox" checked={carForm.is_primary} ... /> Primary vehicle</label>
    {carError && <p style={{color:"red"}}>{carError}</p>}
    <button type="submit" disabled={carSaving}>{carSaving ? "Saving…" : "Save Vehicle"}</button>
    <button type="button" onClick={cancelCarForm}>Cancel</button>
  </form>
)}
```

**Handlers inside `EditModal`**:
- `startEdit(car)` — sets `carFormMode = { editing: car }`, fills `carForm` from car
- `cancelCarForm()` — resets to `"hidden"` + `EMPTY_CAR_FORM`
- `removeCar(carId)` — confirm → `api.delete(...)` → `onSave(updatedCustomer)`
- `handleCarSubmit(e)` — POST or PUT to `/customers/{id}/cars[/{carId}]` → `onSave(updatedCustomer)`

Note: `onSave` already updates the customer in the parent list and closes the modal. For car
operations we want to keep the modal open after save. Solution: add a separate `onCarUpdate`
callback (or pass a `setCustomer` setter) so the modal can refresh its local customer without
closing. Simplest approach: lift local `customer` state into `EditModal` as `localCustomer`
initialized from prop, update it after each car operation without calling `onSave`.

### Step 4 — Verify end-to-end

- Add a car → appears in list inside modal and in the customer table row
- Edit a car → fields pre-filled, save updates display  
- Remove a car → removed from list, confirm dialog shown
- Lease end date field shown only when ownership_type = "lease"
- Modal stays open after car add/edit/delete (only closes on customer Save/Cancel)

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/api/customers.py` | Modify | Add `CarCreate`, `CarUpdate` schemas + 3 car endpoints |
| `frontend/src/routes/CustomersPage.tsx` | Modify | Replace static vehicle section with inline car manager |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `db.refresh(customer, ["cars"])` may not reflect deleted car | Use `await db.refresh(customer, ["cars"])` after commit; SQLAlchemy async refresh reloads from DB |
| `lease_end_date` empty string → null on submit | Convert `""` → `null` before sending to API |
| Year input as string → number | `parseInt(carForm.year) || null` on submit |
| Modal closing after car save | Keep `localCustomer` state in `EditModal`, update it on car ops; only call `onSave` on customer field save |
