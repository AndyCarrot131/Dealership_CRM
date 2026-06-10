# Plan: Inbox Approve → mailto Popup

## Task Type
- [x] Fullstack (backend schema + frontend handler)

## Problem Statement
When a sales rep clicks **Approve** on an email draft in the Inbox, the app should immediately open the system email client (via a `mailto:` URL) pre-filled with the customer's email address, the draft subject, and the draft body — so the rep can send it with one more click.

## Technical Solution
1. The approve API response (`DraftOut`) must include `customer_email` — it is already stored on the `Customer` model (`email: Optional[str]`) but not exposed by `_draft_to_dict`.
2. The frontend `handleApprove` receives the enriched `updated` object and calls `window.open(mailtoUrl)` after the state update.
3. If the customer has no email on file, silently skip the popup (email is an optional field on the customer record).

---

## Implementation Steps

### Step 1 — Backend: expose `customer_email` in `DraftOut`

**File**: `backend/app/api/outreach.py`

Add the field to the `DraftOut` Pydantic model (around line 95):

```python
class DraftOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_email: Optional[str]          # ← add this
    rule_id: Optional[int]
    subject: str
    body: str
    status: str
    created_at: datetime
    approved_at: Optional[datetime]
```

### Step 2 — Backend: populate `customer_email` in `_draft_to_dict`

**File**: `backend/app/api/outreach.py`, function `_draft_to_dict` (around line 437)

```python
def _draft_to_dict(draft: EmailDraft) -> dict:
    return {
        "id": draft.id,
        "customer_id": draft.customer_id,
        "customer_name": draft.customer.full_name if draft.customer else "",
        "customer_email": draft.customer.email if draft.customer else None,   # ← add
        "rule_id": draft.rule_id,
        "subject": draft.subject,
        "body": draft.body,
        "status": draft.status,
        "created_at": draft.created_at,
        "approved_at": draft.approved_at,
    }
```

No migration needed — `customer.email` is already in the DB.

### Step 3 — Frontend: add `customer_email` to the TypeScript interface

**File**: `frontend/src/routes/InboxPage.tsx`, `EmailDraft` interface (line 4)

```ts
interface EmailDraft {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_email?: string;            // ← add
  rule_id: number | null;
  subject: string;
  body: string;
  status: "pending" | "approved" | "dismissed";
  created_at: string;
  approved_at: string | null;
}
```

### Step 4 — Frontend: open mailto after approve

**File**: `frontend/src/routes/InboxPage.tsx`, `handleApprove` function (line 75)

After `setExpandedId(null)`, insert:

```ts
if (updated.customer_email) {
  const subject = encodeURIComponent(updated.subject);
  const body = encodeURIComponent(updated.body);
  window.open(
    `mailto:${updated.customer_email}?subject=${subject}&body=${body}`
  );
}
```

Full updated `handleApprove`:

```ts
async function handleApprove(id: number) {
  if (actioning !== null) return;
  setActioning(id);
  try {
    if (editSubject[id] || editBody[id]) {
      await handleSaveEdits(id);
    }
    const updated = await api.post<EmailDraft>(`/outreach/drafts/${id}/approve`, {});
    setDrafts((prev) => prev.map((d) => (d.id === id ? updated : d)));
    setExpandedId(null);
    if (updated.customer_email) {
      const subject = encodeURIComponent(updated.subject);
      const body = encodeURIComponent(updated.body);
      window.open(
        `mailto:${updated.customer_email}?subject=${subject}&body=${body}`
      );
    }
  } catch (e) {
    alert(e instanceof Error ? e.message : "Failed to approve");
  } finally {
    setActioning(null);
  }
}
```

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/api/outreach.py:95-103` | Modify | Add `customer_email` to `DraftOut` schema |
| `backend/app/api/outreach.py:437-448` | Modify | Populate `customer_email` in `_draft_to_dict` |
| `frontend/src/routes/InboxPage.tsx:4-14` | Modify | Add `customer_email?` to `EmailDraft` interface |
| `frontend/src/routes/InboxPage.tsx:75-90` | Modify | Open `mailto:` URL after successful approve |

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Customer has no email | `customer_email` is `null`/`undefined`; mailto is silently skipped |
| User approves from browser without desktop email client configured | `window.open` opens a new tab/does nothing — acceptable, draft is still marked approved |
| Edits were pending before approve | `handleSaveEdits` runs first; the approve endpoint returns the saved subject/body, so the mailto pre-fill is up-to-date |

---

## SESSION_ID
- CODEX_SESSION: N/A (plan authored by Claude directly from codebase context)
- GEMINI_SESSION: N/A
