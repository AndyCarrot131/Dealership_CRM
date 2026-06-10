# Implementation Plan: Agent Picker in Sidebar

## Task Type
- [x] Frontend only

---

## Summary

The full `/assistant` page already has an agent picker and 5 panels. The sidebar
chat (the `✦` floating button in `App.tsx`) currently only runs `AgentChat` with
no way to choose an agent. This plan adds the same picker UX to the sidebar.

---

## Technical Solution

Extract the shared components from `AssistantPage.tsx` into a new
`AgentPanels.tsx` file, then reuse them in a sidebar state machine added to
`App.tsx`.

**Sidebar header behavior:**
- At picker level: `✦ AI Assistant` title + `×` closes sidebar entirely
- Inside an agent panel: `← Back` to picker + `×` closes sidebar entirely
- `AgentChat` for intake/update passes `onClose={handleSidebarBack}` so its own
  `×` navigates back to picker (the user can still click `×` header outside)

**Sidebar picker layout:** Single-column list (not 2-column grid) to fit the
narrow 260–380 px sidebar without horizontal crowding.

---

## Implementation Steps

### Step 1 — Create `frontend/src/components/AgentPanels.tsx`

Move from `AssistantPage.tsx` to this new file:

**Types:**
```typescript
export type AgentKey = "intake" | "update" | "style" | "rule" | "email";
export interface SimpleCustomer { id: number; full_name: string; }
interface OutreachRule { id: number; name: string; active: boolean; }
interface RuleOut { id: number; name: string; rule_text: string; }
interface RunResult { drafts_created: number; customer_ids: number[]; }
```

**Constants:**
```typescript
export const AGENTS = [
  { key: "intake", icon: "＋", title: "Add Customer",   desc: "..." },
  { key: "update", icon: "✎",  title: "Edit Customer",  desc: "..." },
  { key: "style",  icon: "✦",  title: "Analyze Style",  desc: "..." },
  { key: "rule",   icon: "⚙",  title: "Outreach Rule",  desc: "..." },
  { key: "email",  icon: "✉",  title: "Draft Emails",   desc: "..." },
];
```

**Components (all exported):**

```typescript
// compact = single column (sidebar); default = 2-column grid (page)
export function AgentPicker({ onSelect, compact }: {
  onSelect: (key: AgentKey) => void;
  compact?: boolean;
}) { ... }

export function CustomerSearch({ onSelect, onBack }: {
  onSelect: (c: SimpleCustomer) => void;
  onBack: () => void;
}) { ... }

export function StylePanel({ onBack }: { onBack: () => void }) { ... }

export function RulePanel({ onBack }: { onBack: () => void }) { ... }

export function EmailPanel({ onBack }: { onBack: () => void }) { ... }
```

`AgentPicker` compact mode uses:
```css
gridTemplateColumns: "1fr"   /* single column */
padding: "16px 12px"         /* full width, less padding */
flexDirection: "row"         /* icon + text side-by-side */
```

Page mode (existing): 2-column grid, stacked icon/text.

---

### Step 2 — Update `AssistantPage.tsx`

Remove the extracted components and types, import from `AgentPanels.tsx`.
Keep only what's page-specific:
- `PageShell` (page layout wrapper)
- `PanelHeader` (← Back + title — page version; sidebar has its own header)
- `AssistantPage` default export (state machine)

```typescript
import { AgentKey, SimpleCustomer, AgentPicker, CustomerSearch, StylePanel, RulePanel, EmailPanel } from "../components/AgentPanels";
```

Everything else in `AssistantPage.tsx` remains identical.

---

### Step 3 — Update `App.tsx`

Add sidebar agent state:

```typescript
const [sidebarAgent, setSidebarAgent] = useState<AgentKey | null>(null);
const [sidebarCustomer, setSidebarCustomer] = useState<SimpleCustomer | null>(null);

function handleSidebarBack() {
  setSidebarAgent(null);
  setSidebarCustomer(null);
}

function handleSidebarClose() {
  setShowChat(false);
  setSidebarAgent(null);
  setSidebarCustomer(null);
}
```

Replace the sidebar div contents:

```tsx
<div style={{ display: showChat && !onAssistantPage ? "flex" : "none", height: "100%" }}>
  <SidebarShell agent={sidebarAgent} onClose={handleSidebarClose}>
    {sidebarAgent === null && (
      <AgentPicker onSelect={setSidebarAgent} compact />
    )}
    {sidebarAgent === "intake" && (
      <AgentChat mode="sidebar" chatMode="intake" onClose={handleSidebarBack} />
    )}
    {sidebarAgent === "update" && !sidebarCustomer && (
      <CustomerSearch onSelect={setSidebarCustomer} onBack={handleSidebarBack} />
    )}
    {sidebarAgent === "update" && sidebarCustomer && (
      <AgentChat mode="sidebar" chatMode="update"
        customerId={sidebarCustomer.id}
        customerName={sidebarCustomer.full_name}
        onClose={handleSidebarBack} />
    )}
    {sidebarAgent === "style" && <StylePanel onBack={handleSidebarBack} />}
    {sidebarAgent === "rule"  && <RulePanel  onBack={handleSidebarBack} />}
    {sidebarAgent === "email" && <EmailPanel onBack={handleSidebarBack} />}
  </SidebarShell>
</div>
```

**`SidebarShell` component** (inline in `App.tsx` or extracted):

```tsx
function SidebarShell({ agent, onClose, children }: {
  agent: AgentKey | null;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div style={{
      width: "25%", minWidth: 260, maxWidth: 380,
      display: "flex", flexDirection: "column",
      borderLeft: "1px solid #e5e7eb", background: "#fafafa", height: "100%"
    }}>
      {/* Header — shown for picker + one-shot panels; AgentChat renders its own */}
      {(agent === null || agent === "style" || agent === "rule" || agent === "email") && (
        <div style={{
          padding: "14px 16px", borderBottom: "1px solid #e5e7eb",
          fontWeight: 600, fontSize: 14, color: "#111",
          background: "#fff", display: "flex", alignItems: "center", gap: 8, flexShrink: 0
        }}>
          {agent !== null && (
            <button onClick={() => { /* handled by children onBack */ }}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 13, color: "#6b7280" }}>
              ← Back
            </button>
          )}
          <span style={{ flex: 1 }}>
            {agent === null ? "✦ AI Assistant"
             : agent === "style" ? "✦ Analyze Style"
             : agent === "rule"  ? "⚙ Outreach Rule"
             :                     "✉ Draft Emails"}
          </span>
          <button onClick={onClose} title="Close"
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "#9ca3af", lineHeight: 1, padding: "0 2px" }}>
            ×
          </button>
        </div>
      )}
      {children}
    </div>
  );
}
```

**Problem**: the Back button in `SidebarShell` is separate from the children's
`onBack`. Fix: remove the back button from `SidebarShell` header and let the
child panels render their own `← Back` inside them (already done in the current
panel implementations via `PanelHeader`). BUT the panel's `PanelHeader` renders
a header row that would conflict with `SidebarShell`'s header.

**Revised approach** — simpler, no `SidebarShell`:

Remove `PanelHeader` rendering from each panel when used in the sidebar by
passing the header row responsibility up. Instead:

The sidebar outer wrapper manages the header for picker + one-shot agents. For
intake/update, `AgentChat` manages its own header.

So the panels (`StylePanel`, `RulePanel`, `EmailPanel`, `CustomerSearch`)
currently render their own `PanelHeader`. This works fine in `AssistantPage`
(which uses `PageShell` as the outer frame but no header). In the sidebar, these
panels will render a header inside the sidebar's flex column — that's correct too.

Since the sidebar has no outer shared header for these panels (we let the panels
own their headers), we just need a header for the **picker only**.

**Final sidebar render** (no SidebarShell, inlined in App.tsx):

```tsx
<div style={{
  display: showChat && !onAssistantPage ? "flex" : "none",
  height: "100%"
}}>
  <div style={{
    width: "25%", minWidth: 260, maxWidth: 380,
    display: "flex", flexDirection: "column",
    borderLeft: "1px solid #e5e7eb", background: "#fafafa", height: "100%"
  }}>
    {sidebarAgent === null && (
      <>
        {/* Picker header */}
        <div style={{
          padding: "14px 16px", borderBottom: "1px solid #e5e7eb",
          fontWeight: 600, fontSize: 14, color: "#111",
          background: "#fff", display: "flex", alignItems: "center", flexShrink: 0
        }}>
          <span style={{ flex: 1 }}>✦ AI Assistant</span>
          <button onClick={handleSidebarClose} title="Close"
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "#9ca3af", lineHeight: 1, padding: "0 2px" }}>
            ×
          </button>
        </div>
        <AgentPicker onSelect={setSidebarAgent} compact />
      </>
    )}

    {sidebarAgent === "intake" && (
      <AgentChat mode="sidebar" chatMode="intake" onClose={handleSidebarBack} />
    )}

    {sidebarAgent === "update" && !sidebarCustomer && (
      <CustomerSearch onSelect={setSidebarCustomer} onBack={handleSidebarBack} />
    )}

    {sidebarAgent === "update" && sidebarCustomer && (
      <AgentChat mode="sidebar" chatMode="update"
        customerId={sidebarCustomer.id}
        customerName={sidebarCustomer.full_name}
        onClose={handleSidebarBack} />
    )}

    {sidebarAgent === "style" && <StylePanel onBack={handleSidebarBack} />}
    {sidebarAgent === "rule"  && <RulePanel  onBack={handleSidebarBack} />}
    {sidebarAgent === "email" && <EmailPanel onBack={handleSidebarBack} />}
  </div>
</div>
```

Panel `onBack` already renders `PanelHeader` which has `← Back`. That PanelHeader
also needs a × close button for the sidebar. **Solution**: add an optional
`onClose` prop to `PanelHeader` that shows a × button alongside the Back link.

```typescript
// In AgentPanels.tsx
export function PanelHeader({
  title,
  onBack,
  onClose,
}: {
  title: string;
  onBack: () => void;
  onClose?: () => void;
}) {
  return (
    <div style={{ ... }}>
      <button onClick={onBack} style={{ ... }}>← Back</button>
      <span style={{ flex: 1 }}>{title}</span>
      {onClose && (
        <button onClick={onClose} title="Close" style={{ ... }}>×</button>
      )}
    </div>
  );
}
```

Then each panel accepts optional `onClose?` and passes it through to
`PanelHeader`. In `AssistantPage.tsx` these panels are called without `onClose`.
In `App.tsx` sidebar, they're called with `onClose={handleSidebarClose}`.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `frontend/src/components/AgentPanels.tsx` | Create | Shared types, AGENTS, AgentPicker, CustomerSearch, StylePanel, RulePanel, EmailPanel, PanelHeader |
| `frontend/src/routes/AssistantPage.tsx` | Modify | Import from AgentPanels; remove duplicated components; keep PageShell + state machine |
| `frontend/src/App.tsx` | Modify | Add sidebarAgent + sidebarCustomer state; replace `<AgentChat>` sidebar with picker + panels |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `PanelHeader` used in page and sidebar — `onClose` must be optional | Type it as `onClose?: () => void` |
| Sidebar too narrow for Style panel's `<pre>` output | Already uses `whiteSpace: "pre-wrap"` + `overflowY: auto` — fine |
| `CustomerSearch` fetches on mount — wasted call if user goes back | Acceptable; customers list is small |
| AgentChat double-header if wrapped incorrectly | Only wrap picker/search/one-shot; AgentChat renders standalone in sidebar |
| `AgentChat` × goes to picker (not close sidebar) | `onClose={handleSidebarBack}` — ← back to picker. User closes sidebar with `×` at picker level or re-clicks the `✦` FAB |

---

## SESSION_ID
- CODEX_SESSION: N/A
- GEMINI_SESSION: N/A
