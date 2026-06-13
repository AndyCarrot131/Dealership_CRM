import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { AGENTS, AgentKey } from "./AgentPanels";

interface CustomerCar {
  id: number;
  make: string | null;
  model: string | null;
  year: number | null;
  ownership_type: string | null;
  lease_end_date: string | null;
  is_primary: boolean;
}

interface Customer {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  note: string | null;
  created_at: string;
  cars: CustomerCar[];
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface PendingIntake {
  full_name: string;
  email?: string;
  phone?: string;
  note?: string;
  car_make?: string;
  car_model?: string;
  car_year?: number;
  car_ownership_type?: string;
}

interface PendingDiff {
  full_name?: string;
  email?: string;
  phone?: string;
  note?: string;
  car_id?: number;
  car_make?: string;
  car_model?: string;
  car_year?: number;
  car_ownership_type?: string;
  car_lease_end_date?: string;
}

interface PendingDraft {
  customer_id: number;
  customer_name: string;
  subject: string;
  body: string;
}

interface PendingLog {
  customer_id: number;
  customer_name: string;
  channel: string;
  summary: string;
  contacted_at: string | null;
}

interface AgentChatProps {
  mode?: "sidebar" | "page";
  chatMode?: "intake" | "update" | "assistant";
  customerId?: number;
  customerName?: string;
  onClose?: () => void;
  onCustomerCreated?: (customer: Customer) => void;
  onCustomerUpdated?: (customer: Customer) => void;
  onSwitchAgent?: (key: AgentKey) => void;
  currentAgent?: AgentKey;
}

const OWNERSHIP_LABELS: Record<string, string> = {
  own: "Owned",
  lease: "Lease",
  finance: "Financed",
};

const DIFF_FIELD_LABELS: Record<string, string> = {
  full_name: "Name",
  email: "Email",
  phone: "Phone",
  note: "Note",
  car_make: "Car make",
  car_model: "Car model",
  car_year: "Car year",
  car_ownership_type: "Ownership",
  car_lease_end_date: "Lease end",
};

function PendingConfirm({
  fields,
  onConfirm,
  onCancel,
  loading,
}: {
  fields: PendingIntake;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const carParts = [
    fields.car_year?.toString(),
    fields.car_make,
    fields.car_model,
  ].filter(Boolean);
  const carStr = carParts.join(" ");
  const ownershipLabel = fields.car_ownership_type
    ? OWNERSHIP_LABELS[fields.car_ownership_type] ?? fields.car_ownership_type
    : null;

  return (
    <div
      style={{
        margin: "8px 12px",
        padding: "10px 14px",
        background: "#f0fdf4",
        border: "1px solid #86efac",
        borderRadius: 8,
        fontSize: 13,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: "#166534" }}>
        Ready to add:
      </div>
      <div style={{ color: "#1a1a1a", lineHeight: 1.8 }}>
        <div>
          <strong>{fields.full_name}</strong>
        </div>
        {fields.phone && <div>Phone: {fields.phone}</div>}
        {fields.email && <div>Email: {fields.email}</div>}
        {carStr && (
          <div>
            Vehicle: {carStr}
            {ownershipLabel && (
              <span
                style={{
                  marginLeft: 6,
                  fontSize: 11,
                  background: "#e8f0fe",
                  color: "#1a56db",
                  padding: "1px 6px",
                  borderRadius: 8,
                }}
              >
                {ownershipLabel}
              </span>
            )}
          </div>
        )}
      </div>
      <ConfirmButtons onConfirm={onConfirm} onCancel={onCancel} loading={loading} label="Confirm Add" />
    </div>
  );
}

function DiffConfirm({
  diff,
  onConfirm,
  onCancel,
  loading,
}: {
  diff: PendingDiff;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const customerChanges = Object.entries(diff).filter(
    ([k]) => !k.startsWith("car_") && k !== "car_id"
  );
  const carChanges = Object.entries(diff).filter(
    ([k]) => k.startsWith("car_") && k !== "car_id"
  );

  return (
    <div
      style={{
        margin: "8px 12px",
        padding: "10px 14px",
        background: "#fffbeb",
        border: "1px solid #fcd34d",
        borderRadius: 8,
        fontSize: 13,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: "#92400e" }}>
        Changes to apply:
      </div>
      <div style={{ color: "#1a1a1a", lineHeight: 1.8 }}>
        {customerChanges.map(([k, v]) => (
          <div key={k}>
            {DIFF_FIELD_LABELS[k] ?? k}: <strong>{String(v)}</strong>
          </div>
        ))}
        {carChanges.length > 0 && (
          <>
            <div style={{ marginTop: 4, color: "#555" }}>
              Car {diff.car_id ? `(id=${diff.car_id})` : ""}:
            </div>
            {carChanges.map(([k, v]) => (
              <div key={k} style={{ paddingLeft: 12 }}>
                {DIFF_FIELD_LABELS[k] ?? k}: <strong>{String(v)}</strong>
              </div>
            ))}
          </>
        )}
      </div>
      <ConfirmButtons onConfirm={onConfirm} onCancel={onCancel} loading={loading} label="Apply Changes" />
    </div>
  );
}

function ConfirmButtons({
  onConfirm,
  onCancel,
  loading,
  label,
}: {
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  label: string;
}) {
  return (
    <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
      <button
        onClick={onConfirm}
        disabled={loading}
        style={{
          flex: 1,
          padding: "6px 0",
          background: loading ? "#86efac" : "#16a34a",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          cursor: loading ? "default" : "pointer",
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        {loading ? "Saving…" : label}
      </button>
      <button
        onClick={onCancel}
        disabled={loading}
        style={{
          flex: 1,
          padding: "6px 0",
          background: "none",
          border: "1px solid #ccc",
          borderRadius: 6,
          cursor: "pointer",
          fontSize: 13,
        }}
      >
        Cancel
      </button>
    </div>
  );
}

function DraftPreview({
  draft,
  onSave,
  onCancel,
  loading,
}: {
  draft: PendingDraft;
  onSave: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div
      style={{
        margin: "8px 12px",
        padding: "10px 14px",
        background: "#eff6ff",
        border: "1px solid #93c5fd",
        borderRadius: 8,
        fontSize: 13,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: "#1e40af" }}>
        Draft for {draft.customer_name}:
      </div>
      <div style={{ color: "#374151", lineHeight: 1.6 }}>
        <div style={{ fontWeight: 500, marginBottom: 6 }}>
          Subject: {draft.subject}
        </div>
        <div
          style={{
            whiteSpace: "pre-wrap",
            maxHeight: 200,
            overflowY: "auto",
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: 6,
            padding: "8px 10px",
            fontSize: 12,
          }}
        >
          {draft.body}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
        <button
          onClick={onSave}
          disabled={loading}
          style={{
            flex: 1,
            padding: "6px 0",
            background: loading ? "#93c5fd" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: loading ? "default" : "pointer",
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          {loading ? "Saving…" : "Save to Inbox"}
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          style={{
            flex: 1,
            padding: "6px 0",
            background: "none",
            border: "1px solid #ccc",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

const CHANNEL_LABELS: Record<string, string> = {
  call: "Call",
  text: "Text",
  email: "Email",
  "in-person": "In-Person",
};

function LogPreview({
  log,
  onSave,
  onCancel,
  loading,
}: {
  log: PendingLog;
  onSave: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const dateStr = log.contacted_at
    ? new Date(log.contacted_at).toLocaleDateString()
    : "Today";
  return (
    <div
      style={{
        margin: "8px 12px",
        padding: "10px 14px",
        background: "#fdf4ff",
        border: "1px solid #d8b4fe",
        borderRadius: 8,
        fontSize: 13,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 6, color: "#6b21a8" }}>
        Contact log for {log.customer_name}:
      </div>
      <div style={{ color: "#374151", lineHeight: 1.6 }}>
        <div>
          <span style={{ color: "#555" }}>Channel:</span>{" "}
          <strong>{CHANNEL_LABELS[log.channel] ?? log.channel}</strong>
        </div>
        <div>
          <span style={{ color: "#555" }}>Date:</span> <strong>{dateStr}</strong>
        </div>
        <div style={{ marginTop: 6 }}>
          <span style={{ color: "#555" }}>Summary:</span>
          <div
            style={{
              marginTop: 4,
              whiteSpace: "pre-wrap",
              maxHeight: 140,
              overflowY: "auto",
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 6,
              padding: "6px 10px",
              fontSize: 12,
            }}
          >
            {log.summary}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
        <button
          onClick={onSave}
          disabled={loading}
          style={{
            flex: 1,
            padding: "6px 0",
            background: loading ? "#d8b4fe" : "#7c3aed",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: loading ? "default" : "pointer",
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          {loading ? "Saving…" : "Save to Contact Log"}
        </button>
        <button
          onClick={onCancel}
          disabled={loading}
          style={{
            flex: 1,
            padding: "6px 0",
            background: "none",
            border: "1px solid #ccc",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function AgentChat({
  mode = "sidebar",
  chatMode = "intake",
  customerId,
  customerName,
  onClose,
  onCustomerCreated,
  onCustomerUpdated,
  onSwitchAgent,
  currentAgent,
}: AgentChatProps) {
  const isUpdate = chatMode === "update";
  const isAssistant = chatMode === "assistant";

  const initialMessage = isAssistant
    ? 'Hi! Ask me anything about your CRM data — or ask me to write an email or log a conversation.\n\nExamples:\n• "How many customers haven\'t been contacted in 60 days?"\n• "Which leases end in the next 3 months?"\n• "What Toyotas do we have in stock under $30k?"\n• "Write an email to Sunny Cook reminding her about her lease"\n• "Log this for Sarah Jones: [paste email thread]"'
    : isUpdate
    ? `I'm ready to update ${customerName ?? "this customer"}. Describe what changed.`
    : 'Hi! Describe a new customer and I\'ll add them for you.\n\nExample: "Add Sarah Lee, 604-555-0199, she owns a 2021 Honda Civic"';

  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: initialMessage },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pendingIntake, setPendingIntake] = useState<PendingIntake | null>(null);
  const [pendingDiff, setPendingDiff] = useState<PendingDiff | null>(null);
  const [pendingDraft, setPendingDraft] = useState<PendingDraft | null>(null);
  const [pendingLog, setPendingLog] = useState<PendingLog | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pendingIntake, pendingDiff, pendingDraft, pendingLog]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setPendingIntake(null);
    setPendingDiff(null);
    setPendingDraft(null);
    setPendingLog(null);

    try {
      const apiHistory = nextMessages.slice(0, -1).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await api.post<{
        reply: string;
        intent: string;
        pending_fields: Record<string, unknown> | null;
        pending_draft: PendingDraft | null;
        pending_log: PendingLog | null;
      }>("/chat", {
        message: text,
        history: apiHistory,
        mode: chatMode,
        customer_id: customerId ?? null,
      });

      setMessages([...nextMessages, { role: "assistant", content: res.reply }]);

      if (res.intent === "create_customer" && res.pending_fields) {
        setPendingIntake(res.pending_fields as unknown as PendingIntake);
      } else if (res.intent === "update_customer" && res.pending_fields) {
        setPendingDiff(res.pending_fields as PendingDiff);
      } else if (res.intent === "compose_draft" && res.pending_draft) {
        setPendingDraft(res.pending_draft);
      } else if (res.intent === "log_contact" && res.pending_log) {
        setPendingLog(res.pending_log);
      }
    } catch (e) {
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Something went wrong. Try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmIntake() {
    if (!pendingIntake || confirming) return;
    setConfirming(true);
    try {
      const created = await api.post<Customer>("/chat/confirm", {
        mode: "intake",
        fields: pendingIntake,
      });
      onCustomerCreated?.(created);
      setPendingIntake(null);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Done! ${created.full_name} has been added.` },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Failed to save. Try again.",
        },
      ]);
    } finally {
      setConfirming(false);
    }
  }

  async function handleConfirmUpdate() {
    if (!pendingDiff || confirming) return;
    setConfirming(true);
    try {
      const updated = await api.post<Customer>("/chat/confirm", {
        mode: "update",
        customer_id: customerId,
        diff: pendingDiff,
      });
      onCustomerUpdated?.(updated);
      setPendingDiff(null);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Updated! What else can I help with?` },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Failed to update. Try again.",
        },
      ]);
    } finally {
      setConfirming(false);
    }
  }

  async function handleSaveDraft() {
    if (!pendingDraft || confirming) return;
    setConfirming(true);
    const draft = pendingDraft;
    try {
      await api.post("/outreach/drafts", {
        customer_id: draft.customer_id,
        subject: draft.subject,
        body: draft.body,
      });
      setPendingDraft(null);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Done! The draft for ${draft.customer_name} has been saved to your Inbox.`,
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Failed to save draft. Try again.",
        },
      ]);
    } finally {
      setConfirming(false);
    }
  }

  async function handleSaveLog() {
    if (!pendingLog || confirming) return;
    setConfirming(true);
    const log = pendingLog;
    try {
      await api.post("/interactions", {
        customer_id: log.customer_id,
        channel: log.channel,
        summary: log.summary,
        contacted_at: log.contacted_at ?? undefined,
      });
      setPendingLog(null);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Done! The contact log for ${log.customer_name} has been saved.`,
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: e instanceof Error ? e.message : "Failed to save contact log. Try again.",
        },
      ]);
    } finally {
      setConfirming(false);
    }
  }

  function handleCancel() {
    setPendingIntake(null);
    setPendingDiff(null);
    setPendingDraft(null);
    setPendingLog(null);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Cancelled. What else can I help with?" },
    ]);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const wrapperStyle: React.CSSProperties =
    mode === "page"
      ? {
          display: "flex",
          flexDirection: "column",
          background: "#fafafa",
          height: "100%",
          width: "100%",
        }
      : {
          width: "25%",
          minWidth: 260,
          maxWidth: 380,
          display: "flex",
          flexDirection: "column",
          borderLeft: "1px solid #e5e7eb",
          background: "#fafafa",
          height: "100%",
        };

  const headerLabel = isAssistant
    ? "💬 Ask Anything"
    : isUpdate
    ? `✦ Update${customerName ? `: ${customerName}` : ""}`
    : "✦ AI Assistant";

  const placeholder = isAssistant
    ? "Ask about your customers, inventory, outreach…"
    : isUpdate
    ? "Describe what changed…"
    : "Describe a customer…";

  return (
    <div style={wrapperStyle}>
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid #e5e7eb",
          fontWeight: 600,
          fontSize: 14,
          color: "#111",
          background: "#fff",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexShrink: 0,
        }}
      >
        <span style={{ flex: 1 }}>{headerLabel}</span>
        {onClose && (
          <button
            onClick={onClose}
            title="Close"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: 18,
              color: "#9ca3af",
              lineHeight: 1,
              padding: "0 2px",
            }}
          >
            ×
          </button>
        )}
      </div>

      {onSwitchAgent && (
        <div
          style={{
            display: "flex",
            gap: 6,
            padding: "6px 12px",
            overflowX: "auto",
            background: "#fff",
            borderBottom: "1px solid #e5e7eb",
            flexShrink: 0,
          }}
        >
          {AGENTS.map((a) => {
            const active = currentAgent === a.key;
            return (
              <button
                key={a.key}
                onClick={() => onSwitchAgent(a.key)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "3px 10px",
                  borderRadius: 999,
                  border: "none",
                  cursor: "pointer",
                  fontSize: 12,
                  whiteSpace: "nowrap",
                  background: active ? "#2563eb" : "#f3f4f6",
                  color: active ? "#fff" : "#374151",
                  fontWeight: active ? 600 : 400,
                }}
              >
                <span>{a.icon}</span>
                <span>{a.title}</span>
              </button>
            );
          })}
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", padding: "12px 0" }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              padding: "4px 12px",
            }}
          >
            <div
              style={{
                maxWidth: "85%",
                padding: "8px 12px",
                borderRadius:
                  msg.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
                background: msg.role === "user" ? "#2563eb" : "#fff",
                color: msg.role === "user" ? "#fff" : "#1a1a1a",
                fontSize: 13,
                lineHeight: 1.55,
                whiteSpace: "pre-wrap",
                boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
                border: msg.role === "assistant" ? "1px solid #e5e7eb" : "none",
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ padding: "4px 12px" }}>
            <div
              style={{
                display: "inline-block",
                padding: "8px 14px",
                background: "#fff",
                border: "1px solid #e5e7eb",
                borderRadius: "14px 14px 14px 4px",
                fontSize: 13,
                color: "#888",
              }}
            >
              Thinking…
            </div>
          </div>
        )}

        {pendingIntake && !loading && (
          <PendingConfirm
            fields={pendingIntake}
            onConfirm={handleConfirmIntake}
            onCancel={handleCancel}
            loading={confirming}
          />
        )}

        {pendingDiff && !loading && (
          <DiffConfirm
            diff={pendingDiff}
            onConfirm={handleConfirmUpdate}
            onCancel={handleCancel}
            loading={confirming}
          />
        )}

        {pendingDraft && !loading && (
          <DraftPreview
            draft={pendingDraft}
            onSave={handleSaveDraft}
            onCancel={handleCancel}
            loading={confirming}
          />
        )}

        {pendingLog && !loading && (
          <LogPreview
            log={pendingLog}
            onSave={handleSaveLog}
            onCancel={handleCancel}
            loading={confirming}
          />
        )}

        <div ref={bottomRef} />
      </div>

      <div
        style={{
          padding: "10px 12px",
          borderTop: "1px solid #e5e7eb",
          background: "#fff",
          display: "flex",
          gap: 8,
          alignItems: "flex-end",
          flexShrink: 0,
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={2}
          style={{
            flex: 1,
            resize: "none",
            padding: "8px 10px",
            fontSize: 13,
            borderRadius: 8,
            border: "1px solid #d1d5db",
            outline: "none",
            lineHeight: 1.5,
            fontFamily: "inherit",
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim()}
          style={{
            padding: "8px 14px",
            background: loading || !input.trim() ? "#93c5fd" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: loading || !input.trim() ? "default" : "pointer",
            fontSize: 13,
            fontWeight: 500,
            alignSelf: "flex-end",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
