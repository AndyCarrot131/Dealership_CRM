import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

export type AgentKey = "assistant" | "intake" | "update" | "style" | "rule" | "email" | "pre_visit";

export interface SimpleCustomer {
  id: number;
  full_name: string;
}

interface OutreachRule {
  id: number;
  name: string;
  active: boolean;
}

interface RuleOut {
  id: number;
  name: string;
  rule_text: string;
}

interface RunResult {
  drafts_created: number;
  customer_ids: number[];
}

export const AGENTS: { key: AgentKey; icon: string; title: string; desc: string }[] = [
  { key: "assistant", icon: "💬", title: "Ask Anything",    desc: "Ask questions about your customers, cars, inventory and outreach — I'll look it up." },
  { key: "intake",    icon: "＋", title: "Add Customer",    desc: "Describe a new customer in plain English and I'll create the record." },
  { key: "update",    icon: "✎",  title: "Edit Customer",   desc: "Find a customer and tell me what changed — I'll update the record." },
  { key: "pre_visit", icon: "📋", title: "Pre-Visit Brief", desc: "Pick a customer and get an AI briefing with alerts and talking points before their appointment." },
  { key: "style",     icon: "✦",  title: "Analyze Style",   desc: "Regenerate your writing style guide from saved sample messages." },
  { key: "rule",      icon: "⚙",  title: "Outreach Rule",   desc: "Describe a rule in plain English — I'll parse and save it." },
  { key: "email",     icon: "✉",  title: "Draft Emails",    desc: "Pick an outreach rule and generate personalised email drafts." },
];

// ─── Panel header (used by all one-shot panels + customer search) ──────────────

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
      <button
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: 13,
          color: "#6b7280",
          padding: "2px 0",
          marginRight: 4,
        }}
      >
        ← Back
      </button>
      <span style={{ flex: 1 }}>{title}</span>
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
  );
}

// ─── Agent picker ─────────────────────────────────────────────────────────────

export function AgentPicker({
  onSelect,
  compact,
}: {
  onSelect: (key: AgentKey) => void;
  compact?: boolean;
}) {
  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: compact ? "20px 14px" : "40px 24px",
      }}
    >
      {!compact && (
        <>
          <div style={{ marginBottom: 8, fontWeight: 700, fontSize: 18, color: "#111" }}>
            AI Agents
          </div>
          <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 24 }}>
            Choose an agent to get started.
          </div>
        </>
      )}
      {compact && (
        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 14 }}>
          Choose an agent to get started.
        </div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: compact ? "1fr" : "1fr 1fr",
          gap: compact ? 8 : 12,
        }}
      >
        {AGENTS.map((a) => (
          <button
            key={a.key}
            onClick={() => onSelect(a.key)}
            style={{
              textAlign: "left",
              padding: compact ? "10px 12px" : "16px 14px",
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 10,
              cursor: "pointer",
              display: "flex",
              flexDirection: compact ? "row" : "column",
              alignItems: compact ? "flex-start" : undefined,
              gap: compact ? 10 : 6,
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = "#2563eb";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 0 2px #dbeafe";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = "#e5e7eb";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
            }}
          >
            <span style={{ fontSize: compact ? 18 : 22, lineHeight: 1, flexShrink: 0 }}>
              {a.icon}
            </span>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              <strong style={{ fontSize: 13, color: "#111" }}>{a.title}</strong>
              <span style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.5 }}>{a.desc}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Customer search (Edit Customer flow) ─────────────────────────────────────

export function CustomerSearch({
  onSelect,
  onBack,
  onClose,
}: {
  onSelect: (c: SimpleCustomer) => void;
  onBack: () => void;
  onClose?: () => void;
}) {
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<SimpleCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<SimpleCustomer[]>("/customers")
      .then(setCustomers)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = query.trim()
    ? customers.filter((c) => c.full_name.toLowerCase().includes(query.toLowerCase()))
    : customers;

  return (
    <>
      <PanelHeader title="✎ Edit Customer" onBack={onBack} onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px" }}>
        <input
          placeholder="Search by name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
          style={{
            width: "100%",
            padding: "8px 10px",
            fontSize: 13,
            borderRadius: 8,
            border: "1px solid #d1d5db",
            outline: "none",
            boxSizing: "border-box",
            marginBottom: 12,
          }}
        />
        {loading && <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading…</div>}
        {error && <div style={{ color: "#dc2626", fontSize: 13 }}>{error}</div>}
        {!loading && filtered.length === 0 && !error && (
          <div style={{ color: "#9ca3af", fontSize: 13 }}>No customers found.</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {filtered.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c)}
              style={{
                textAlign: "left",
                padding: "10px 12px",
                background: "#fff",
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 13,
                color: "#111",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "#2563eb";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "#e5e7eb";
              }}
            >
              {c.full_name}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

// ─── Style panel ──────────────────────────────────────────────────────────────

export function StylePanel({
  onBack,
  onClose,
}: {
  onBack: () => void;
  onClose?: () => void;
}) {
  const [channel, setChannel] = useState<"email" | "text">("email");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.post<{ channel: string; style_md: string }>(
        `/style/summarize/${channel}`,
        {}
      );
      setResult(r.style_md);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PanelHeader title="✦ Analyze Style" onBack={onBack} onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px" }}>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
          Analyze your saved sample messages and regenerate your writing style guide.
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {(["email", "text"] as const).map((ch) => (
            <button
              key={ch}
              onClick={() => {
                setChannel(ch);
                setResult(null);
                setError(null);
              }}
              style={{
                padding: "6px 16px",
                borderRadius: 20,
                border: `1px solid ${channel === ch ? "#2563eb" : "#d1d5db"}`,
                background: channel === ch ? "#2563eb" : "#fff",
                color: channel === ch ? "#fff" : "#374151",
                fontSize: 13,
                cursor: "pointer",
                fontWeight: 500,
              }}
            >
              {ch.charAt(0).toUpperCase() + ch.slice(1)}
            </button>
          ))}
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          style={{
            padding: "8px 20px",
            background: loading ? "#93c5fd" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: loading ? "default" : "pointer",
            fontSize: 13,
            fontWeight: 500,
            marginBottom: 16,
          }}
        >
          {loading ? "Analyzing…" : `Analyze my ${channel} samples`}
        </button>

        {error && (
          <div
            style={{
              padding: "10px 14px",
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: 8,
              fontSize: 13,
              color: "#dc2626",
            }}
          >
            {error}
          </div>
        )}

        {result && (
          <div
            style={{
              padding: "14px",
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              fontSize: 13,
              lineHeight: 1.7,
              whiteSpace: "pre-wrap",
              color: "#1a1a1a",
            }}
          >
            {result}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Rule panel ───────────────────────────────────────────────────────────────

export function RulePanel({
  onBack,
  onClose,
}: {
  onBack: () => void;
  onClose?: () => void;
}) {
  const [name, setName] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [cadence, setCadence] = useState("30");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<RuleOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate() {
    if (!name.trim() || !ruleText.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.post<RuleOut>("/outreach/rules", {
        name: name.trim(),
        rule_text: ruleText.trim(),
        cadence_days: parseInt(cadence) || 30,
      });
      setSaved(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setName("");
    setRuleText("");
    setCadence("30");
    setSaved(null);
    setError(null);
  }

  return (
    <>
      <PanelHeader title="⚙ Outreach Rule" onBack={onBack} onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px" }}>
        {saved ? (
          <div>
            <div
              style={{
                padding: "14px",
                background: "#f0fdf4",
                border: "1px solid #86efac",
                borderRadius: 8,
                fontSize: 13,
                color: "#166534",
                marginBottom: 16,
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Rule saved: {saved.name}</div>
              <div style={{ color: "#374151" }}>{saved.rule_text}</div>
            </div>
            <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
              Go to the <strong>Outreach</strong> page to run this rule and generate email drafts.
            </div>
            <button
              onClick={handleReset}
              style={{
                padding: "7px 16px",
                background: "#fff",
                border: "1px solid #d1d5db",
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Create another rule
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontSize: 13, color: "#6b7280" }}>
              Describe your outreach rule in plain English — the AI will parse it into a structured
              filter.
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 4,
                }}
              >
                Rule name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Lease ending soon"
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  fontSize: 13,
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 4,
                }}
              >
                Rule description
              </label>
              <textarea
                value={ruleText}
                onChange={(e) => setRuleText(e.target.value)}
                placeholder="e.g. Customers with a lease ending in the next 90 days"
                rows={3}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  fontSize: 13,
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  outline: "none",
                  resize: "vertical",
                  fontFamily: "inherit",
                  boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#374151",
                  marginBottom: 4,
                }}
              >
                Cadence (days between contacts)
              </label>
              <input
                type="number"
                value={cadence}
                onChange={(e) => setCadence(e.target.value)}
                min={1}
                style={{
                  width: 100,
                  padding: "8px 10px",
                  fontSize: 13,
                  borderRadius: 8,
                  border: "1px solid #d1d5db",
                  outline: "none",
                }}
              />
            </div>
            {error && (
              <div
                style={{
                  padding: "10px 14px",
                  background: "#fef2f2",
                  border: "1px solid #fca5a5",
                  borderRadius: 8,
                  fontSize: 13,
                  color: "#dc2626",
                }}
              >
                {error}
              </div>
            )}
            <button
              onClick={handleCreate}
              disabled={!name.trim() || !ruleText.trim() || loading}
              style={{
                alignSelf: "flex-start",
                padding: "8px 20px",
                background:
                  !name.trim() || !ruleText.trim() || loading ? "#93c5fd" : "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: !name.trim() || !ruleText.trim() || loading ? "default" : "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {loading ? "Saving…" : "Create Rule"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Email panel ──────────────────────────────────────────────────────────────

export function EmailPanel({
  onBack,
  onClose,
}: {
  onBack: () => void;
  onClose?: () => void;
}) {
  const [rules, setRules] = useState<OutreachRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [results, setResults] = useState<Record<number, RunResult>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<OutreachRule[]>("/outreach/rules")
      .then((rs) => setRules(rs.filter((r) => r.active)))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  async function handleRun(ruleId: number) {
    if (runningId !== null) return;
    setRunningId(ruleId);
    setError(null);
    try {
      const r = await api.post<RunResult>(`/outreach/rules/${ruleId}/run`, {});
      setResults((prev) => ({ ...prev, [ruleId]: r }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setRunningId(null);
    }
  }

  return (
    <>
      <PanelHeader title="✉ Draft Emails" onBack={onBack} onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 16px" }}>
        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
          Select an active outreach rule to generate personalised email drafts.
        </div>

        {loading && <div style={{ color: "#9ca3af", fontSize: 13 }}>Loading rules…</div>}

        {error && (
          <div
            style={{
              padding: "10px 14px",
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: 8,
              fontSize: 13,
              color: "#dc2626",
              marginBottom: 12,
            }}
          >
            {error}
          </div>
        )}

        {!loading && rules.length === 0 && !error && (
          <div
            style={{
              padding: "14px",
              background: "#fff",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              fontSize: 13,
              color: "#6b7280",
            }}
          >
            No active rules found. Create a rule first using the{" "}
            <strong>Outreach Rule</strong> agent.
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {rules.map((rule) => {
            const ran = results[rule.id];
            const isRunning = runningId === rule.id;
            return (
              <div
                key={rule.id}
                style={{
                  padding: "12px 14px",
                  background: "#fff",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ flex: 1, fontSize: 13, fontWeight: 500, color: "#111" }}>
                    {rule.name}
                  </span>
                  {!ran && (
                    <button
                      onClick={() => handleRun(rule.id)}
                      disabled={runningId !== null}
                      style={{
                        padding: "5px 14px",
                        background: runningId !== null ? "#93c5fd" : "#2563eb",
                        color: "#fff",
                        border: "none",
                        borderRadius: 6,
                        cursor: runningId !== null ? "default" : "pointer",
                        fontSize: 12,
                        fontWeight: 500,
                      }}
                    >
                      {isRunning ? "Running…" : "Run"}
                    </button>
                  )}
                </div>
                {ran && (
                  <div
                    style={{
                      marginTop: 8,
                      padding: "8px 10px",
                      background: "#f0fdf4",
                      border: "1px solid #86efac",
                      borderRadius: 6,
                      fontSize: 12,
                      color: "#166534",
                    }}
                  >
                    {ran.drafts_created === 0
                      ? "No matching customers found for this rule."
                      : `${ran.drafts_created} draft${ran.drafts_created !== 1 ? "s" : ""} created — review them in the Inbox.`}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ─── Pre-Visit Brief panel ─────────────────────────────────────────────────────

interface BriefingSection {
  doc_id: string;
  category: string;
  title: string;
  triggered: boolean;
  alert: string;
  suggestion: string;
}

interface BriefingResult {
  customer_name: string;
  generated_at: string;
  triggered_count: number;
  sections: BriefingSection[];
  summary: string;
}

const CATEGORY_ICONS: Record<string, string> = {
  trim_alert: "⚠️",
  competitor: "🏁",
  incentive: "💰",
  rate: "📊",
  inventory: "🚗",
  lease: "📋",
};

function catIcon(cat: string): string {
  return CATEGORY_ICONS[cat.toLowerCase()] ?? "📌";
}

export function PreVisitPanel({
  customer,
  onBack,
  onClose,
}: {
  customer: SimpleCustomer;
  onBack: () => void;
  onClose?: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BriefingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  async function generate() {
    setLoading(true);
    setError(null);
    abortRef.current = false;
    try {
      const data = await api.post<BriefingResult>(`/customers/${customer.id}/briefing`, {});
      if (!abortRef.current) setResult(data);
    } catch (err: unknown) {
      if (!abortRef.current)
        setError(err instanceof Error ? err.message : "Briefing generation failed");
    } finally {
      if (!abortRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    generate();
    return () => {
      abortRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customer.id]);

  return (
    <>
      <PanelHeader title={`📋 ${customer.full_name}`} onBack={onBack} onClose={onClose} />
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 14px", display: "flex", flexDirection: "column", gap: 12 }}>

        {loading && !result && (
          <div style={{ padding: "40px 0", textAlign: "center", color: "#9ca3af", fontSize: 13 }}>
            <div style={{ fontSize: 22, marginBottom: 8 }}>✦</div>
            Running checks against support docs…
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "10px 12px",
              background: "#fef2f2",
              border: "1px solid #fca5a5",
              borderRadius: 8,
              fontSize: 13,
              color: "#dc2626",
            }}
          >
            {error}
            <button
              onClick={generate}
              style={{
                marginLeft: 10,
                padding: "3px 10px",
                background: "#fff",
                border: "1px solid #d1d5db",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Retry
            </button>
          </div>
        )}

        {result && (
          <>
            {result.sections.length === 0 ? (
              <div
                style={{
                  padding: "20px 14px",
                  background: "#f9fafb",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  fontSize: 13,
                  color: "#6b7280",
                  textAlign: "center",
                }}
              >
                No alerts triggered based on current support docs.
              </div>
            ) : (
              result.sections.map((sec) => (
                <div
                  key={sec.doc_id}
                  style={{
                    background: "#fff",
                    border: "1px solid #e5e7eb",
                    borderRadius: 8,
                    padding: "12px 14px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      fontWeight: 700,
                      fontSize: 11,
                      color: "#374151",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                    }}
                  >
                    <span style={{ fontSize: 14 }}>{catIcon(sec.category)}</span>
                    {sec.title}
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: "#1f2937", lineHeight: 1.6 }}>
                    {sec.alert}
                  </p>
                  {sec.suggestion && (
                    <p style={{ margin: 0, fontSize: 12, color: "#2563eb", fontWeight: 500, lineHeight: 1.5 }}>
                      → {sec.suggestion}
                    </p>
                  )}
                </div>
              ))
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 4 }}>
              <span style={{ fontSize: 11, color: "#9ca3af" }}>Generated {result.generated_at}</span>
              <button
                onClick={generate}
                disabled={loading}
                style={{
                  padding: "5px 14px",
                  background: "#fff",
                  border: "1px solid #d1d5db",
                  borderRadius: 6,
                  cursor: loading ? "default" : "pointer",
                  fontSize: 12,
                  color: "#374151",
                }}
              >
                {loading ? "Regenerating…" : "Regenerate"}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
