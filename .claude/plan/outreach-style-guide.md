# Implementation Plan: Outreach Email Style Guide Integration

## Summary

The backend already fetches the sales rep's email `StyleProfile` and passes it as `style_md` to
`compose_email` when running an outreach rule (`outreach.py:188-195`). The `email_composer.py`
agent injects it under a "Style guide:" header in the LLM prompt. **No backend logic is missing.**

The gap is entirely in the frontend: `OutreachPage.tsx` has zero indication of whether a style
guide exists or will be applied, leaving the sales rep blind to a key input that controls email
tone. This plan adds a style guide status panel to the Outreach page and a `style_guide_active`
flag to the run result.

---

## Task Type
- [x] Frontend (primary)
- [x] Backend (minor — one field addition)

---

## Technical Solution

### Backend change (minimal)
Add `style_guide_active: bool` to `RunResult` so the toast/feedback after running a rule can
report whether the style guide was applied.

### Frontend change (main work)
Fetch `GET /style/profile/email` on mount of `OutreachPage`. Render a compact **"Email Style
Guide"** status banner above the rules list:
- **Profile exists** → green indicator + collapsible preview of `style_md` (using the existing
  `MarkdownView` pattern)
- **No profile** → amber warning with a `<a>` link to `/style` so the rep can set one up before
  running rules

After a rule runs, update the toast message to include "with your style guide" / "no style guide —
emails written professionally" based on the `style_guide_active` flag returned.

---

## Implementation Steps

### Step 1 — Backend: extend `RunResult` + return flag
**File**: `backend/app/api/outreach.py`

1a. Add `style_guide_active: bool` field to `RunResult` (line ~56):
```python
class RunResult(BaseModel):
    drafts_created: int
    customer_ids: list[int]
    customers_matched: int
    style_guide_active: bool = False   # ← new
```

1b. In `run_rule`, capture whether the profile was found and include it in the return value
(currently lines 188-195 and 248-252):
```python
style_guide_active = style_profile is not None and bool(style_profile.style_md)
...
return RunResult(
    drafts_created=len(created_ids),
    customer_ids=created_ids,
    customers_matched=len(customers),
    style_guide_active=style_guide_active,
)
```

**Expected deliverable**: `RunResult` JSON from `/outreach/rules/{id}/run` now includes
`style_guide_active: true|false`.

---

### Step 2 — Frontend: fetch email style profile in OutreachPage
**File**: `frontend/src/routes/OutreachPage.tsx`

2a. Add `StyleProfile` interface and state:
```ts
interface StyleProfile {
  channel: string;
  style_md: string;
}

// inside component:
const [emailStyleProfile, setEmailStyleProfile] = useState<StyleProfile | null>(null);
const [styleLoading, setStyleLoading] = useState(false);
```

2b. Add fetch on mount (parallel with `fetchRules`):
```ts
useEffect(() => {
  fetchRules();
  fetchEmailStyle();
}, []);

async function fetchEmailStyle() {
  setStyleLoading(true);
  try {
    const data = await api.get<StyleProfile>("/style/profile/email");
    setEmailStyleProfile(data);
  } catch {
    setEmailStyleProfile(null);
  } finally {
    setStyleLoading(false);
  }
}
```

**Expected deliverable**: Profile data available in component state on load.

---

### Step 3 — Frontend: render Style Guide status banner
**File**: `frontend/src/routes/OutreachPage.tsx`

Add a `<StyleGuideBanner>` inline component (or just JSX) rendered between the page header and
the "New Rule" button row.

**When profile exists and has content:**
```
┌─────────────────────────────────────────────────────┐
│ ✓ Email Style Guide active                    [▼ Preview] │
│   (collapsed by default; click Preview to expand)   │
│   <MarkdownView md={emailStyleProfile.style_md} />  │
└─────────────────────────────────────────────────────┘
```
- Border: `1px solid #bbf7d0`, background `#f0fdf4`, text `#15803d`
- Collapsible via `<details>/<summary>` or `useState(false)`

**When no profile (or empty style_md):**
```
┌───────────────────────────────────────────────────────────┐
│ ⚠ No email style guide — emails will be written           │
│   generically.  Set one up in Style Learning →            │
└───────────────────────────────────────────────────────────┘
```
- Border: `1px solid #fde68a`, background `#fffbeb`, text `#b45309`
- "Style Learning →" is a React Router `<Link to="/style">` (or `<a href="/style">`)

**Expected deliverable**: Banner visible above rules list showing style guide status.

---

### Step 4 — Frontend: update `RunResult` interface + toast message
**File**: `frontend/src/routes/OutreachPage.tsx`

4a. Update interface:
```ts
interface RunResult {
  drafts_created: number;
  customer_ids: number[];
  customers_matched: number;
  style_guide_active: boolean;    // ← new
}
```

4b. Update toast logic in `handleRun`:
```ts
const styleNote = result.style_guide_active
  ? " · Style guide applied."
  : " · No style guide set.";

if (result.drafts_created > 0) {
  msg = `${result.drafts_created} draft${result.drafts_created === 1 ? "" : "s"} created — check your Inbox.${styleNote}`;
} else if (result.customers_matched > 0) {
  msg = `Found ${result.customers_matched} customer${...} but could not compose emails.`;
} else {
  msg = "No matching customers found.";
}
```

**Expected deliverable**: Toast after run reports whether the style guide was applied.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/api/outreach.py:55-59` | Modify | Add `style_guide_active: bool` to `RunResult` |
| `backend/app/api/outreach.py:248-252` | Modify | Return `style_guide_active` in `run_rule` |
| `frontend/src/routes/OutreachPage.tsx:1-30` | Modify | Add `StyleProfile` interface + state |
| `frontend/src/routes/OutreachPage.tsx:32-46` | Modify | Fetch email style profile on mount |
| `frontend/src/routes/OutreachPage.tsx:112-155` | Modify | Add style guide banner above rules list |
| `frontend/src/routes/OutreachPage.tsx:14-19` | Modify | Add `style_guide_active` to `RunResult` interface |
| `frontend/src/routes/OutreachPage.tsx:90-110` | Modify | Update toast to include style guide note |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `MarkdownView` is defined in `StylePage.tsx` only | Copy the minimal renderer inline into `OutreachPage.tsx` (it's ~50 lines); or extract to a shared component `src/components/MarkdownView.tsx` — the shared extract is cleaner if StylePage is already using it |
| `/style/profile/email` returns 200 with empty `style_md` when no profile exists | Check `profile?.style_md` for truthiness (already how StylePage handles it) |
| Banner adds visual noise to a minimal page | Keep banner compact (one line when no preview open); use `<details>` for zero-impact collapse |

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: n/a (no external model called)
- GEMINI_SESSION: n/a (no external model called)
