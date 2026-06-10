# Plan: Outreach Rule — Email Type Selection + Custom Template

## Overview

Split each outreach rule's configuration into two logical sections:

1. **Select Customers** — existing filter/cadence (rule_text, cadence_days, compiled_filter)
2. **Write Email** — new: email-type pill selector with three options

Email types:
| Type | Value | Behaviour |
|------|-------|-----------|
| Test-drive Follow Up | `test_drive_followup` | AI writes a follow-up after a recent test drive |
| Lease/Finance Ending | `lease_finance_ending` | AI writes an upgrade offer (current default) |
| Customize | `custom` | Dealer writes a topic/template; AI personalises it |

When **Customize** is selected the dealer can type a template (e.g. "Snow tires on sale this week!") directly on the same Outreach page. That text is stored on the rule and passed to the email composer as the email topic.

---

## Task Type
- [x] Backend — model, migration, schema, email composer
- [x] Frontend — OutreachPage two-section form + rule cards with type picker + inline template editor

---

## Technical Solution

### Data model change

Add two columns to `outreach_rules`:

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `email_type` | `VARCHAR(30)` | `'lease_finance_ending'` | one of the three values above |
| `custom_template` | `TEXT` | NULL | only used when `email_type = 'custom'` |

### Email composer change

`compose_email` gains `email_type` and `custom_template` parameters.
A short "Email purpose" block is prepended to the user message:

- `test_drive_followup`: "The customer recently test-drove a vehicle. Write a warm follow-up email thanking them and keeping them engaged, referencing the test drive."
- `lease_finance_ending`: (current behaviour — no extra instruction needed)
- `custom`: "Use the following dealer-provided topic/template as the theme of this email: `{custom_template}`"

The AI still applies the style guide and personalises for the specific customer.

### Frontend layout (new rule form + rule cards)

```
┌── New Outreach Rule ─────────────────────────────────────────────┐
│ ── Select Customers ──────────────────────────────────────────    │
│  Rule name: [_______________]                                     │
│  Description: [___________________________]                       │
│  Min days since last contact: [30]                                │
│                                                                   │
│ ── Write Email ───────────────────────────────────────────────    │
│  [Test-drive Follow Up] [Lease/Finance Ending ✓] [Customize]      │
│  (when Customize selected:)                                       │
│  Template: [___________________________________]                  │
│   e.g. "Snow tires on sale this week!"                            │
│                                                                   │
│  [Save Rule]  [Cancel]                                            │
└──────────────────────────────────────────────────────────────────┘
```

Rule cards get a second row showing:
- Email type badge (coloured chip)
- For `custom`: collapsible template preview + "Edit" button

---

## Implementation Steps

### Step 1 — Migration

**File**: `backend/alembic/versions/0005_outreach_email_type.py`

```python
def upgrade() -> None:
    op.add_column(
        "outreach_rules",
        sa.Column("email_type", sa.String(30), nullable=False, server_default="lease_finance_ending"),
    )
    op.add_column(
        "outreach_rules",
        sa.Column("custom_template", sa.Text, nullable=True),
    )

def downgrade() -> None:
    op.drop_column("outreach_rules", "custom_template")
    op.drop_column("outreach_rules", "email_type")
```

**Expected deliverable**: `alembic upgrade head` applies cleanly.

---

### Step 2 — ORM Model

**File**: `backend/app/models/outreach.py`

Add to `OutreachRule` class after `active`:

```python
email_type: Mapped[str] = mapped_column(String(30), nullable=False, default="lease_finance_ending")
custom_template: Mapped[Optional[str]] = mapped_column(nullable=True)
```

**Expected deliverable**: Model reflects the two new columns.

---

### Step 3 — API Schemas + Endpoints

**File**: `backend/app/api/outreach.py`

3a. Extend `RuleCreate`:
```python
class RuleCreate(BaseModel):
    name: str
    rule_text: str
    cadence_days: Optional[int] = 30
    email_type: str = "lease_finance_ending"          # new
    custom_template: Optional[str] = None             # new
```

3b. Extend `RuleUpdate`:
```python
class RuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_text: Optional[str] = None
    cadence_days: Optional[int] = None
    active: Optional[bool] = None
    email_type: Optional[str] = None                  # new
    custom_template: Optional[str] = None             # new
```

3c. Extend `RuleOut`:
```python
class RuleOut(BaseModel):
    ...
    email_type: str
    custom_template: Optional[str] = None
```

3d. In `create_rule`: copy `email_type` and `custom_template` from `body` to the ORM object.

3e. In `update_rule`: apply `body.email_type` and `body.custom_template` if provided.

3f. In `run_rule`: pass `rule.email_type` and `rule.custom_template` to `compose_email`.

**Expected deliverable**: Rule CRUD routes carry and persist the new fields; run passes them forward.

---

### Step 4 — Email Composer

**File**: `backend/app/agents/email_composer.py`

4a. Add email-type context map:

```python
_TYPE_CONTEXT: dict[str, str] = {
    "test_drive_followup": (
        "The customer recently test-drove a vehicle. "
        "Write a warm follow-up email thanking them for the test drive and keeping them engaged."
    ),
    "lease_finance_ending": (
        "The customer's lease or financing is ending soon. "
        "Write an email about upgrade options and next steps."
    ),
}
```

4b. Update `_build_user_message` signature:

```python
def _build_user_message(
    customer: dict[str, Any],
    inventory_matches: list[dict[str, Any]],
    style_md: str,
    email_type: str = "lease_finance_ending",
    custom_template: str | None = None,
) -> str:
```

4c. Add an "Email purpose:" block at the top of the message sections list:

```python
if email_type == "custom" and custom_template:
    purpose = f"Use the following dealer-provided topic as the theme of this email:\n{custom_template}"
else:
    purpose = _TYPE_CONTEXT.get(email_type, _TYPE_CONTEXT["lease_finance_ending"])

sections = [
    f"Email purpose: {purpose}",
    f"Customer: {customer['full_name']}",
    ...
]
```

4d. Update `compose_email` signature to accept and forward the two new params.

**Expected deliverable**: `compose_email` shapes the prompt differently for each email type.

---

### Step 5 — Frontend: OutreachPage

**File**: `frontend/src/routes/OutreachPage.tsx`

#### 5a. Extend interfaces

```ts
interface OutreachRule {
  // existing fields...
  email_type: string;
  custom_template: string | null;
}
```

Add state for new-rule form fields:
```ts
const [emailType, setEmailType] = useState<string>("lease_finance_ending");
const [customTemplate, setCustomTemplate] = useState<string>("");
```

#### 5b. Update `handleCreate`

Include `email_type` and `custom_template` in the POST body:
```ts
const created = await api.post<OutreachRule>("/outreach/rules", {
  name: name.trim(),
  rule_text: ruleText.trim(),
  cadence_days: parseInt(cadenceDays) || 30,
  email_type: emailType,
  custom_template: emailType === "custom" ? customTemplate.trim() || null : null,
});
```

Reset new state on success:
```ts
setEmailType("lease_finance_ending");
setCustomTemplate("");
```

#### 5c. Restructure the create form with two sections

Replace the current flat form layout with:

```tsx
{/* ── Select Customers ─────────────────────────── */}
<div style={sectionHeaderStyle}>Select Customers</div>
<label style={labelStyle}>Rule name</label>
<input .../>
<label style={labelStyle}>Description (natural language)</label>
<textarea .../>
<label style={labelStyle}>Min days since last contact</label>
<input type="number" .../>

{/* ── Write Email ───────────────────────────────── */}
<div style={{ ...sectionHeaderStyle, marginTop: 16 }}>Write Email</div>
<div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
  {EMAIL_TYPES.map(({ value, label }) => (
    <button
      key={value}
      onClick={() => setEmailType(value)}
      style={typePillStyle(emailType === value)}
    >
      {label}
    </button>
  ))}
</div>
{emailType === "custom" && (
  <>
    <label style={labelStyle}>Email topic / template</label>
    <textarea
      value={customTemplate}
      onChange={(e) => setCustomTemplate(e.target.value)}
      placeholder="e.g. Snow tires are on sale this week — perfect for the winter season!"
      rows={3}
      style={{ ...inputStyle, resize: "vertical" }}
    />
  </>
)}
```

Add the constant:
```ts
const EMAIL_TYPES = [
  { value: "test_drive_followup", label: "Test-drive Follow Up" },
  { value: "lease_finance_ending", label: "Lease/Finance Ending" },
  { value: "custom", label: "Customize" },
] as const;
```

Add style helpers:
```ts
function typePillStyle(active: boolean): React.CSSProperties {
  return {
    padding: "5px 12px",
    borderRadius: 20,
    border: active ? "none" : "1px solid #d1d5db",
    background: active ? "#2563eb" : "#fff",
    color: active ? "#fff" : "#374151",
    fontSize: 12,
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
  };
}

const sectionHeaderStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  color: "#6b7280",
  textTransform: "uppercase",
  letterSpacing: "0.07em",
  marginBottom: 10,
};
```

#### 5d. Update rule cards to show email type + custom template

Inside each rule card, below the cadence/parsed line, add:

```tsx
{/* Email type badge */}
<div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
  <span style={emailTypeBadgeStyle(rule.email_type)}>
    {EMAIL_TYPES.find(t => t.value === rule.email_type)?.label ?? rule.email_type}
  </span>
</div>

{/* Custom template — show + inline edit */}
{rule.email_type === "custom" && (
  <CustomTemplateEditor
    ruleId={rule.id}
    template={rule.custom_template ?? ""}
    onSaved={(updated) =>
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)))
    }
  />
)}
```

Email type badge style function:
```ts
function emailTypeBadgeStyle(type: string): React.CSSProperties {
  const colours: Record<string, { bg: string; color: string }> = {
    test_drive_followup: { bg: "#ede9fe", color: "#6d28d9" },
    lease_finance_ending: { bg: "#dbeafe", color: "#1d4ed8" },
    custom: { bg: "#fef3c7", color: "#92400e" },
  };
  const c = colours[type] ?? { bg: "#f3f4f6", color: "#374151" };
  return {
    fontSize: 11,
    padding: "2px 8px",
    borderRadius: 12,
    background: c.bg,
    color: c.color,
    fontWeight: 500,
  };
}
```

#### 5e. Inline `CustomTemplateEditor` component

Add as a small local function component in the same file:

```tsx
function CustomTemplateEditor({
  ruleId,
  template,
  onSaved,
}: {
  ruleId: number;
  template: string;
  onSaved: (updated: OutreachRule) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(template);
  const [saving, setSaving] = useState(false);

  async function save() {
    if (saving) return;
    setSaving(true);
    try {
      const updated = await api.put<OutreachRule>(`/outreach/rules/${ruleId}`, {
        custom_template: draft.trim() || null,
      });
      onSaved(updated);
      setEditing(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to save template");
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <div style={{ marginTop: 6 }}>
        {template ? (
          <div style={{ fontSize: 12, color: "#6b7280", fontStyle: "italic" }}>
            "{template.length > 100 ? template.slice(0, 100) + "…" : template}"
          </div>
        ) : (
          <div style={{ fontSize: 12, color: "#9ca3af" }}>No template set.</div>
        )}
        <button
          onClick={() => { setDraft(template); setEditing(true); }}
          style={{ marginTop: 4, fontSize: 11, color: "#2563eb", background: "none",
            border: "none", cursor: "pointer", padding: 0 }}
        >
          {template ? "Edit template" : "Add template"}
        </button>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 8 }}>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={3}
        placeholder="e.g. Snow tires are on sale this week!"
        style={{ ...inputStyle, fontSize: 12 }}
      />
      <div style={{ display: "flex", gap: 6 }}>
        <button
          onClick={save}
          disabled={saving}
          style={primaryBtn(saving)}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={() => setEditing(false)}
          style={{ padding: "5px 10px", background: "none", border: "1px solid #d1d5db",
            borderRadius: 6, cursor: "pointer", fontSize: 12 }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
```

Note: `inputStyle` and `primaryBtn` are already defined at the bottom of `OutreachPage.tsx` — `CustomTemplateEditor` can reference them since they're in the same file.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/alembic/versions/0005_outreach_email_type.py` | Create | Migration: add `email_type` + `custom_template` columns |
| `backend/app/models/outreach.py` | Modify | Add two new mapped columns to `OutreachRule` |
| `backend/app/api/outreach.py` | Modify | Extend schemas, CRUD, run_rule to carry the new fields |
| `backend/app/agents/email_composer.py` | Modify | Add email-type context to prompt; accept new params |
| `frontend/src/routes/OutreachPage.tsx` | Modify | Two-section form, type pills, email type badge, inline template editor |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| Existing rules have no `email_type` in DB | Migration uses `server_default='lease_finance_ending'` so existing rows get the current behaviour |
| `compose_email` callers outside `run_rule` | Only one call site exists — easy to update |
| `CustomTemplateEditor` references `inputStyle`/`primaryBtn` before they're defined | In TSX files, hoisting isn't an issue for `const` declarations — move helpers above their first use if needed, or keep at bottom (they are already declared after the component in the file) |
| User selects "Customize" but leaves template blank | `custom_template` stored as NULL; composer falls back to `lease_finance_ending` context |
| Email type pill buttons inside rule card need PATCH | `update_rule` already handles partial updates — just send `{ email_type: value }` |

---

## SESSION_ID
- CODEX_SESSION: n/a
- GEMINI_SESSION: n/a
