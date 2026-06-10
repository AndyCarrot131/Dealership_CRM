# Implementation Plan: Agent Chat Panel

## Task Type
- [x] Fullstack (Backend: intake agent + chat API → Frontend: chat panel UI)

---

## Summary

Add a 1/4-wide chat panel on the right side of the Customers page. A salesperson types natural language (e.g., "Add John Smith, phone 604-555-1234, he owns a 2019 Camry"), the backend LLM parses it into structured fields, returns a confirmation summary, and on user confirmation creates the customer + car record via existing ORM endpoints. Matches the "Intake Agent" + "human approval gate" architecture described in CLAUDE.md.

---

## Technical Solution

**Flow:**
```
Sales types → POST /api/chat (message + history)
  → IntakeAgent extracts fields via LLM tool-call
  → Returns {intent, extracted_fields, confirmation_message}
Sales clicks Confirm → POST /api/chat/confirm (extracted_fields)
  → ORM insert (same logic as POST /api/customers + POST /api/customers/{id}/cars)
  → Returns created customer → frontend refreshes list
```

**Key constraints from CLAUDE.md:**
- AI never writes to DB directly — human must confirm first
- LLM config (base_url, api_key, model) from env vars / config.py, never hardcoded
- Conversation history stays in frontend state (no DB persistence for MVP)

---

## Implementation Steps

### Step 1 — Backend: LLM Client (`backend/app/llm/client.py`)

Create a thin wrapper around the OpenAI-compatible chat completions API:

```python
class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str): ...
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
```

- Uses `httpx.AsyncClient` for async HTTP
- Passes `tools` for tool-calling support
- Reads config from `settings` (see Step 2)

### Step 2 — Backend: Config (`backend/app/config.py`)

Add LLM config fields (already has a config.py, extend it):

```python
LLM_BASE_URL: str = "http://localhost:11434/v1"  # Ollama default
LLM_API_KEY: str = "ollama"
LLM_MODEL: str = "llama3.1"
```

Read from environment variables `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.

### Step 3 — Backend: Intake Agent (`backend/app/agents/intake.py`)

```python
INTAKE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_customer_intake",
            "description": "Extract customer info from natural language",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "note": {"type": "string"},
                    "car_make": {"type": "string"},
                    "car_model": {"type": "string"},
                    "car_year": {"type": "integer"},
                    "car_ownership_type": {"type": "string", "enum": ["own", "lease", "finance"]},
                },
                "required": ["full_name"],
            },
        },
    }
]

async def run_intake(messages: list[dict], llm: LLMClient) -> dict:
    """
    Returns:
      {"intent": "create_customer", "fields": {...}, "reply": "confirmation text"}
    or
      {"intent": "unknown", "reply": "clarification message"}
    """
```

- Sends conversation history + INTAKE_TOOLS to LLM
- If LLM returns a tool_call → extract args → format human-readable confirmation
- If no tool_call → return clarification reply
- Never touches DB

### Step 4 — Backend: Chat API (`backend/app/api/chat.py`)

Two endpoints:

```python
# POST /api/chat
class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []   # [{role, content}] from frontend

class ChatResponse(BaseModel):
    reply: str
    intent: str                # "create_customer" | "unknown"
    pending_fields: dict | None = None  # extracted fields, held for confirmation

@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, current_user: User = Depends(get_current_user)):
    result = await run_intake(body.history + [{"role": "user", "content": body.message}], llm)
    return ChatResponse(reply=result["reply"], intent=result["intent"], pending_fields=result.get("fields"))


# POST /api/chat/confirm
class ConfirmRequest(BaseModel):
    fields: dict   # pending_fields from above

@router.post("/confirm", response_model=CustomerOut)
async def confirm_intake(body: ConfirmRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Create customer via ORM (same as customers.py:create_customer)
    # If car fields present, create customer_car record too
    # Return full CustomerOut
```

### Step 5 — Backend: Register Router (`backend/app/main.py`)

Add to existing main.py (currently lines 6-14):

```python
from app.api.chat import router as chat_router
app.include_router(chat_router, prefix="/api/chat")
```

### Step 6 — Frontend: AgentChat Component (`frontend/src/components/AgentChat.tsx`)

New component. Props:
```typescript
interface AgentChatProps {
  onCustomerCreated: (customer: Customer) => void;
}
```

State:
```typescript
messages: ChatMessage[]          // {role: "user"|"assistant", content: string}
input: string
loading: boolean
pendingFields: Record<string, unknown> | null   // awaiting confirmation
```

UI structure:
```
<div style={{ width: "25%", minWidth: 280, ... }}>  // 1/4 panel
  <div> message history (scrollable) </div>
  {pendingFields && <ConfirmBar fields={pendingFields} onConfirm={...} onCancel={...} />}
  <div> input + send button </div>
</div>
```

Flow:
1. User sends message → `POST /api/chat` with message + history
2. Append assistant reply to messages
3. If `intent === "create_customer"` → show ConfirmBar with field summary
4. User clicks Confirm → `POST /api/chat/confirm` → call `onCustomerCreated(result)` → prepend to customer list
5. User clicks Cancel → clear pendingFields, append "Cancelled." to chat

### Step 7 — Frontend: Layout Wrapper in `CustomersPage.tsx`

Modify the outer `<div>` (currently line 247):

```typescript
// Before: <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
// After: two-column flex layout

<div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
  {/* Main content — 75% */}
  <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
    {/* existing content unchanged */}
  </div>

  {/* Chat panel — 25% */}
  <AgentChat onCustomerCreated={(c) => setCustomers([c, ...customers])} />
</div>
```

Also remove `maxWidth: 1100, margin: "0 auto"` from inner div so full width is used.

---

## Key Files

| File | Operation | Description |
|------|-----------|-------------|
| `backend/app/config.py` | Modify | Add `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` env vars |
| `backend/app/llm/client.py` | Create | Async LLM client (httpx, OpenAI-compatible) |
| `backend/app/agents/intake.py` | Create | Intake agent: NL → tool-call → structured fields |
| `backend/app/api/chat.py` | Create | `POST /api/chat` + `POST /api/chat/confirm` |
| `backend/app/main.py:6-14` | Modify | Register chat router |
| `frontend/src/components/AgentChat.tsx` | Create | Chat panel component (1/4 wide, messages + confirm bar + input) |
| `frontend/src/routes/CustomersPage.tsx:246-247` | Modify | Two-column flex layout, import + render AgentChat |

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| LLM not configured / no Ollama running | Chat returns graceful error: "AI service unavailable"; chat panel still renders |
| LLM hallucinates required fields (e.g. no name) | Intake agent validates `full_name` is present before returning `create_customer` intent; otherwise returns clarification |
| Confirmation race condition (double-click Confirm) | Disable confirm button while `POST /api/chat/confirm` is in-flight |
| Car fields optional — partial car data | Only create `customer_car` record if at least `make` or `model` is present |
| Wide table + chat panel on small screens | Chat panel has `minWidth: 280`; main content scrolls horizontally if needed |

---

## SESSION_ID
- CODEX_SESSION: N/A (no codeagent-wrapper installed)
- GEMINI_SESSION: N/A (no codeagent-wrapper installed)
