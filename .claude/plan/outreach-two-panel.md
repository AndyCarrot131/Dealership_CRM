# Plan: Outreach Two-Panel Form

## Summary
Split the Outreach Rule creation form into two side-by-side panels within a single card.

## Layout

```
+────────────────────────────────+──────────────────────────+
│  SELECT CUSTOMERS              │  EMAIL TYPE              │
│                                │                          │
│  Rule name                     │  [Test-drive Follow Up]  │
│  Rule description              │  [Lease/Finance Ending]  │
│  Min days since last contact   │  [Custom: Snow Tires] ✎× │
│                                │  [+ Add Type]            │
│  [Save Rule] [Cancel]          │                          │
│  AI parses rule on save.       │  Email topic / template  │
│                                │  (when custom selected)  │
+────────────────────────────────+──────────────────────────+
```

## Email Type Management
- Built-in types: "Test-drive Follow Up", "Lease/Finance Ending" (fixed)
- User-defined custom types stored in `localStorage` under key `outreach_custom_email_types`
- Each custom type: `{ id: string (UUID), label: string }`
- Inline rename (✎) and delete (×) per custom type
- "+ Add Type" button: shows inline input, Enter to confirm, Escape to cancel
- Clicking a custom type pill: sets `email_type = "custom"`, pre-fills template with label if empty
- Template textarea appears below custom types when `email_type === "custom"`

## Data Sent to Backend (unchanged)
- `email_type`: "test_drive_followup" | "lease_finance_ending" | "custom"
- `custom_template`: template string when custom, null otherwise

## Rule Cards
- `EmailTypeSelector` updated to show builtin + user-defined custom types from localStorage
- Fallback "Custom" pill shown if no user-defined types exist
- `CustomTemplateEditor` unchanged
