# Implementation Plan: Outreach Run — Email Type Selection at Run Time

## Objective

Move email type selection from rule creation/rule card to the "Run" flow.
When sales clicks Run, a modal appears showing matched customers. The right panel
of that modal contains the email type selector. Sales picks a type and clicks
"Generate Drafts" to create email drafts for all listed customers.

---

## Task Type
- [x] Fullstack (frontend modal + backend preview endpoint)

---

## Current State

- Email type is set when creating a rule (right panel in form)
- Email type is also editable on each rule card (EmailTypeSelector)
- Clicking "Run" immediately generates drafts with no preview step

## Target State

1. Rule creation form: **no email type panel** — only rule name, description, cadence
2. Rule cards: **no email type section** — just SELECT CUSTOMERS info + action buttons
3. Run button → opens `RunModal`:
   - Left: scrollable list of matched customers (fetched from new preview endpoint)
   - Right panel: email type selector (same built-in types + user-defined custom types)
   - Bottom-right: "Generate Drafts" button
4. "Generate Drafts" → calls `/run` with the selected email type override

---

## Backend Changes

### 1. New preview endpoint

**File**: `backend/app/api/outreach.py`

Add new Pydantic schemas before the routes:

```python
class MatchedCarInfo(BaseModel):
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    ownership_type: Optional[str]
    lease_end_date: Optional[str]

class MatchedCustomer(BaseModel):
    id: int
    full_name: str
    note: Optional[str]
    last_contacted_at: Optional[datetime]
    cars: list[MatchedCarInfo]

class PreviewResult(BaseModel):
    customers: list[MatchedCustomer]
    style_guide_active: bool
```

Add endpoint (extract the filter/query logic from `run_rule` into a shared helper):

```python
@router.get("/rules/{rule_id}/preview", response_model=PreviewResult)
async def preview_rule(rule_id, current_user, db) -> PreviewResult:
    rule = await _fetch_rule(rule_id, current_user, db)
    if rule.compiled_filter is None:
        raise HTTPException(422, "Rule not parsed yet")
    customers = await _match_customers(rule, current_user.id, db)
    style_active = await _check_style_active(current_user.id, db)
    return PreviewResult(
        customers=[_customer_to_matched(c) for c in customers],
        style_guide_active=style_active,
    )
```

### 2. Add optional email_type override to run endpoint

Modify `run_rule` to accept a request body:

```python
class RunRequest(BaseModel):
    email_type: Optional[str] = None
    custom_template: Optional[str] = None

@router.post("/rules/{rule_id}/run", response_model=RunResult)
async def run_rule(rule_id, body: RunRequest = Body(RunRequest()), ...):
    effective_email_type = body.email_type or rule.email_type
    effective_template = body.custom_template or rule.custom_template
    # use effective_email_type in compose_email calls
```

### 3. Refactor shared helpers

Extract from `run_rule` into private helpers:
- `_match_customers(rule, sales_id, db) → list[Customer]`
- `_check_style_active(sales_id, db) → bool`
- `_customer_to_matched(c: Customer) → MatchedCustomer`

This avoids duplicating the cadence + filter logic between run and preview.

---

## Frontend Changes

### File: `frontend/src/routes/OutreachPage.tsx`

#### Step 1 — Remove email type from rule creation form

- Delete the right panel (`EmailTypePanel`) from the `{showForm && ...}` block
- The form becomes single-column again (just left panel content)
- Remove state: `emailType`, `customTemplate`, `selectedCustomId`
- Keep `customEmailTypes` (still needed by RunModal)
- `handleCreate` body: remove `email_type` and `custom_template` fields
  (backend defaults to "lease_finance_ending"; value is overridden at run time)

#### Step 2 — Remove email type from rule cards

- Delete the "EMAIL TYPE" label, `EmailTypeSelector`, and `CustomTemplateEditor`
  from the rule card render
- Remove `EmailTypeSelector` and `CustomTemplateEditor` component definitions
- Keep `EmailTypePanel` (reused inside RunModal)

#### Step 3 — Replace direct run handler with modal

Change `handleRun(rule)` to open the modal instead of calling the API directly:

```typescript
const [runModalRule, setRunModalRule] = useState<OutreachRule | null>(null);

// Run button onClick:
onClick={() => setRunModalRule(rule)}
```

#### Step 4 — New `RunModal` component

```tsx
interface RunModalProps {
  rule: OutreachRule;
  customEmailTypes: CustomEmailType[];
  onClose: () => void;
  onComplete: (draftsCreated: number) => void;
}

function RunModal({ rule, customEmailTypes, onClose, onComplete }: RunModalProps) {
  // State
  const [step, setStep] = useState<"loading" | "ready" | "generating" | "done">("loading");
  const [customers, setCustomers] = useState<MatchedCustomer[]>([]);
  const [styleGuideActive, setStyleGuideActive] = useState(false);
  const [emailType, setEmailType] = useState("lease_finance_ending");
  const [selectedCustomId, setSelectedCustomId] = useState<string | null>(null);
  const [customTemplate, setCustomTemplate] = useState("");
  const [draftsCreated, setDraftsCreated] = useState(0);

  // On mount: fetch preview
  useEffect(() => {
    api.get(`/outreach/rules/${rule.id}/preview`)
      .then(data => {
        setCustomers(data.customers);
        setStyleGuideActive(data.style_guide_active);
        // default email type from rule
        setEmailType(rule.email_type || "lease_finance_ending");
        setStep("ready");
      })
      .catch(() => { /* show error */ });
  }, [rule.id]);

  async function handleGenerate() {
    setStep("generating");
    const result = await api.post(`/outreach/rules/${rule.id}/run`, {
      email_type: emailType,
      custom_template: emailType === "custom" ? customTemplate || null : null,
    });
    setDraftsCreated(result.drafts_created);
    setStep("done");
  }

  // Layout: overlay backdrop + centered modal card
  // Modal: 720px wide, two columns
  //   Left col (flex: 1): customer list
  //   Right col (260px): EmailTypePanel + Generate button
}
```

**Customer list item:**
```tsx
function MatchedCustomerRow({ customer }: { customer: MatchedCustomer }) {
  // Shows: name, primary car (make/model/year/ownership_type), last contacted
  // Compact, read-only — just for review before generating
}
```

**Modal states:**
- `loading`: spinner + "Matching customers…"
- `ready`: two-column layout, customer count in header
- `generating`: "Generating [N] drafts…" spinner, Generate button disabled
- `done`: "N drafts created — check your Inbox" + Close button
- No customers matched: "No customers matched this rule." + Close

#### Step 5 — Add `MatchedCustomer` TypeScript interface

```typescript
interface MatchedCustomerCar {
  make: string | null;
  model: string | null;
  year: number | null;
  ownership_type: string | null;
  lease_end_date: string | null;
}

interface MatchedCustomer {
  id: number;
  full_name: string;
  note: string | null;
  last_contacted_at: string | null;
  cars: MatchedCustomerCar[];
}
```

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/api/outreach.py` | Modify | Add preview endpoint, refactor shared helpers, add RunRequest body to run |
| `frontend/src/routes/OutreachPage.tsx` | Modify | Remove email type from form/cards, add RunModal, wire Run button |

---

## API Contract

### GET /outreach/rules/{id}/preview
Response:
```json
{
  "customers": [
    {
      "id": 42,
      "full_name": "John Smith",
      "note": "Interested in leasing",
      "last_contacted_at": "2026-04-10T12:00:00",
      "cars": [{"make": "Toyota", "model": "Camry", "year": 2022, "ownership_type": "lease", "lease_end_date": "2026-09-01"}]
    }
  ],
  "style_guide_active": true
}
```

### POST /outreach/rules/{id}/run  (updated)
Request body (now accepts optional overrides):
```json
{ "email_type": "test_drive_followup", "custom_template": null }
```
Response unchanged: `{drafts_created, customer_ids, customers_matched, style_guide_active}`

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Preview endpoint duplicates filter logic from run | Extract `_match_customers` helper shared by both |
| RunRequest body breaks existing callers that send no body | Use `Body(RunRequest())` default — empty body still works |
| Email type removed from rule form means existing rules lose their stored type | Keep `email_type` column on rule; the stored value becomes the default in RunModal |
| Modal is heavy for a quick run | Loading state shows immediately; preview call is fast (no LLM) |

---

## Implementation Order

1. Backend: extract `_match_customers` + `_check_style_active` helpers
2. Backend: add `GET /rules/{id}/preview` using those helpers
3. Backend: add `RunRequest` body to `POST /rules/{id}/run`
4. Frontend: add `MatchedCustomer` interface + update `api/client.ts` if needed
5. Frontend: add `RunModal` component (below main component in file)
6. Frontend: wire Run button → `setRunModalRule`
7. Frontend: remove email type from create form
8. Frontend: remove email type section from rule cards
9. TypeScript check: `npx tsc --noEmit`
