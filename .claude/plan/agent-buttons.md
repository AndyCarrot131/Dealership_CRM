# Implementation Plan: Agent Selection Buttons in AI Assistant

## Task Type
- [x] Frontend (primary: AssistantPage + new agent sub-panels)

---

## Summary

Add a visual agent-picker to the AI Assistant page. The salesperson sees five
agent cards. Clicking one launches the appropriate panel for that agent.

Two agents (intake, update) already run as conversational chat via `AgentChat`.
Three agents (style_summarizer, rule_parser, email_composer) are one-shot: they
take structured input, call an existing API endpoint, and display the result —
they do NOT need the chat API.

No backend changes are required.

---

## All Five Agents and Their UI Pattern

| Card | Backend Agent | UI Pattern | API Used |
|------|--------------|------------|----------|
| Add Customer | `run_intake` | Chat (existing `AgentChat`) | `POST /api/chat` |
| Edit Customer | `run_update` | Customer search → Chat | `POST /api/chat` |
| Analyze Style | `run_style_summarizer` | Channel picker → Run → Markdown result | `POST /api/style/summarize/{channel}` |
| Outreach Rule | `run_rule_parser` | Text input → Create rule → Confirmation | `POST /api/outreach/rules` |
| Draft Emails | `compose_email` | Run existing rule → Confirmation + link | `POST /api/outreach/rules/{id}/run` |

---

## Current State

- `AssistantPage.tsx` renders `<AgentChat mode="page" />` with no agent choice.
- `AgentChat` supports `chatMode="intake"` and `chatMode="update"` with `onClose`.
- Backend agents are all live; their APIs are already registered.

---

## Technical Solution

```
AssistantPage
├── (no agent selected) → <AgentPicker onSelect={setSelectedAgent} />
│
├── selectedAgent === "intake"
│     └── <AgentChat mode="page" chatMode="intake" onClose={handleBack} />
│
├── selectedAgent === "update"
│   ├── (no customer) → <CustomerSearch onSelect={...} onBack={handleBack} />
│   └── (customer selected) → <AgentChat mode="page" chatMode="update"
│                               customerId={...} customerName={...} onClose={handleBack} />
│
├── selectedAgent === "style"
│     └── <StylePanel onBack={handleBack} />
│           ├── channel toggle (email | text)
│           ├── "Analyze Samples" button → POST /api/style/summarize/{channel}
│           └── result: rendered style_md markdown
│
├── selectedAgent === "rule"
│     └── <RulePanel onBack={handleBack} />
│           ├── rule name input
│           ├── rule description textarea
│           ├── cadence_days input (default 30)
│           ├── "Create Rule" button → POST /api/outreach/rules
│           └── success: "Rule saved. Go to Outreach page to run it."
│
└── selectedAgent === "email"
      └── <EmailPanel onBack={handleBack} />
            ├── list of active outreach rules (GET /api/outreach/rules)
            ├── select a rule → "Run" button → POST /api/outreach/rules/{id}/run
            └── success: "N email drafts created. Go to Inbox to review."
```

---

## Implementation Steps

### Step 1 — State + routing in `AssistantPage.tsx`

```typescript
type AgentKey = "intake" | "update" | "style" | "rule" | "email";

interface SimpleCustomer { id: number; full_name: string; }

export default function AssistantPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentKey | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<SimpleCustomer | null>(null);

  function handleBack() {
    setSelectedAgent(null);
    setSelectedCustomer(null);
  }

  if (!selectedAgent) return <Outer><AgentPicker onSelect={setSelectedAgent} /></Outer>;
  if (selectedAgent === "intake")
    return <Outer><AgentChat mode="page" chatMode="intake" onClose={handleBack} /></Outer>;
  if (selectedAgent === "update") {
    if (!selectedCustomer)
      return <Outer><CustomerSearch onSelect={setSelectedCustomer} onBack={handleBack} /></Outer>;
    return <Outer>
      <AgentChat mode="page" chatMode="update"
        customerId={selectedCustomer.id} customerName={selectedCustomer.full_name}
        onClose={handleBack} />
    </Outer>;
  }
  if (selectedAgent === "style")  return <Outer><StylePanel  onBack={handleBack} /></Outer>;
  if (selectedAgent === "rule")   return <Outer><RulePanel   onBack={handleBack} /></Outer>;
  if (selectedAgent === "email")  return <Outer><EmailPanel  onBack={handleBack} /></Outer>;
}
```

`<Outer>` is the existing page wrapper div (height 100%, centred column, border).

---

### Step 2 — `AgentPicker` (inline in AssistantPage.tsx)

Five cards in a 2-column grid (last card spans full width if count is odd).
Each card: large icon, bold title, short description, hover border highlight.

```typescript
const AGENTS = [
  { key: "intake", icon: "＋", title: "Add Customer",
    desc: "Describe a new customer and I'll create the record." },
  { key: "update", icon: "✎", title: "Edit Customer",
    desc: "Find a customer and describe what changed." },
  { key: "style",  icon: "✦", title: "Analyze Style",
    desc: "Regenerate your writing style guide from saved samples." },
  { key: "rule",   icon: "⚙", title: "Outreach Rule",
    desc: "Describe a rule in plain English — I'll parse and save it." },
  { key: "email",  icon: "✉", title: "Draft Emails",
    desc: "Pick an outreach rule and generate personalised email drafts." },
];
```

---

### Step 3 — `CustomerSearch` (inline in AssistantPage.tsx)

Used by "Edit Customer". Fetches `GET /api/customers` once on mount, filters
client-side as the user types.

```typescript
function CustomerSearch({ onSelect, onBack }) {
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<SimpleCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<SimpleCustomer[]>("/customers")
      .then(setCustomers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = customers.filter((c) =>
    c.full_name.toLowerCase().includes(query.toLowerCase())
  );

  // Render: back button, search input, scrollable list of customer buttons
}
```

---

### Step 4 — `StylePanel` (inline in AssistantPage.tsx)

One-shot panel: pick channel, hit "Analyze", show markdown result.

```typescript
function StylePanel({ onBack }) {
  const [channel, setChannel] = useState<"email" | "text">("email");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await api.post<{ channel: string; style_md: string }>(
        `/style/summarize/${channel}`, {}
      );
      setResult(r.style_md);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  // Render:
  // - back button
  // - "✦ Analyze Style" header
  // - email / text toggle buttons
  // - "Analyze my [channel] samples" button (disabled while loading)
  // - result: <pre> or <div style={{whiteSpace: "pre-wrap"}}> showing style_md
  // - error message if failed
}
```

---

### Step 5 — `RulePanel` (inline in AssistantPage.tsx)

One-shot panel: enter rule details → `POST /api/outreach/rules`.

```typescript
interface RuleOut { id: number; name: string; rule_text: string; }

function RulePanel({ onBack }) {
  const [name, setName] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [cadence, setCadence] = useState(30);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<RuleOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim() || !ruleText.trim()) return;
    setLoading(true); setError(null);
    try {
      const r = await api.post<RuleOut>("/outreach/rules", {
        name: name.trim(),
        rule_text: ruleText.trim(),
        cadence_days: cadence,
      });
      setSaved(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  // Render (before save):
  // - back button
  // - "⚙ Create Outreach Rule" header
  // - Rule name input
  // - Rule description textarea ("e.g. Customers with a lease ending in 30 days")
  // - Cadence (days) number input
  // - "Create Rule" button

  // Render (after save):
  // - "✓ Rule saved: [name]" success box
  // - "Go to Outreach page to run it and generate email drafts."
  // - "Create another" button → reset state
}
```

---

### Step 6 — `EmailPanel` (inline in AssistantPage.tsx)

One-shot panel: list active rules → select one → run it → confirmation.

```typescript
interface RuleItem { id: number; name: string; active: boolean; }
interface RunResult { drafted: number; }

function EmailPanel({ onBack }) {
  const [rules, setRules] = useState<RuleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<number | null>(null);  // rule id being run
  const [results, setResults] = useState<Record<number, RunResult>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<RuleItem[]>("/outreach/rules")
      .then((rs) => setRules(rs.filter((r) => r.active)))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleRun(ruleId: number) {
    setRunning(ruleId); setError(null);
    try {
      const r = await api.post<RunResult>(`/outreach/rules/${ruleId}/run`, {});
      setResults((prev) => ({ ...prev, [ruleId]: r }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setRunning(null);
    }
  }

  // Render:
  // - back button
  // - "✉ Draft Emails" header
  // - loading spinner or empty state ("No active rules. Create one first.")
  // - list of rule cards:
  //     rule name | "Run" button
  //     after run: "✓ N drafts created — review in Inbox"
  // - global error message
}
```

**Note**: The outreach run endpoint may not exist yet (`POST /api/outreach/rules/{id}/run`).
Check `OutreachPage.tsx` to confirm — if it's already there in the frontend, the
endpoint exists. If not, backend work is needed (out of scope for this plan; in
that case, show "Go to Outreach page to run rules" instead).

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `frontend/src/routes/AssistantPage.tsx` | Rewrite | State, AgentPicker, CustomerSearch, StylePanel, RulePanel, EmailPanel |

All sub-components inline in `AssistantPage.tsx` since they are small and
page-specific. File will stay well under the 800-line limit.

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `POST /api/outreach/rules/{id}/run` endpoint missing | Check `OutreachPage.tsx` first; if absent, EmailPanel shows a static link to the Outreach page |
| Style Summarizer fails with "no samples" | Backend returns a 422 with that message; display it as the error string in StylePanel |
| Customer list is large (slow load) | Single fetch on mount; show spinner; client-side filter is instant after load |
| Rule Parser backend error (LLM down) | Backend returns 503; display the error message from the response |
| AssistantPage file gets large | All panels are concise (~40 lines each); total ~250 lines — well within 800-line limit |

---

## SESSION_ID
- CODEX_SESSION: N/A (codeagent-wrapper not installed)
- GEMINI_SESSION: N/A (codeagent-wrapper not installed)
