import { useEffect, useState } from "react";
import { api } from "../api/client";
import { MarkdownView } from "../components/MarkdownView";

// ─── Types ────────────────────────────────────────────────────────────────────

interface OutreachRule {
  id: number;
  name: string;
  rule_text: string;
  compiled_filter: Record<string, unknown> | null;
  sql_preview: string | null;
  cadence_days: number | null;
  active: boolean;
  email_type: string;
  custom_template: string | null;
  created_at: string;
}

interface RunResult {
  drafts_created: number;
  customer_ids: number[];
  customers_matched: number;
  style_guide_active: boolean;
}

interface StyleProfile {
  channel: string;
  style_md: string;
}

type CustomEmailType = { id: string; label: string };

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

interface PreviewResult {
  customers: MatchedCustomer[];
  style_guide_active: boolean;
}

// ─── Built-in email types ─────────────────────────────────────────────────────

const BUILTIN_TYPES = [
  { value: "test_drive_followup", label: "Test-drive Follow Up" },
  { value: "lease_finance_ending", label: "Lease/Finance Ending" },
] as const;

// ─── localStorage helpers ─────────────────────────────────────────────────────

const STORAGE_KEY = "outreach_custom_email_types";

function loadCustomTypes(): CustomEmailType[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function persistCustomTypes(types: CustomEmailType[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(types));
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function OutreachPage() {
  const [rules, setRules] = useState<OutreachRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [emailStyle, setEmailStyle] = useState<StyleProfile | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [name, setName] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [cadenceDays, setCadenceDays] = useState("30");

  const [saving, setSaving] = useState(false);
  const [runModalRule, setRunModalRule] = useState<OutreachRule | null>(null);
  const [toast, setToast] = useState<{ id: number; msg: string } | null>(null);

  useEffect(() => {
    fetchRules();
    fetchEmailStyle();
  }, []);

  async function fetchRules() {
    setLoading(true);
    try {
      const data = await api.get<OutreachRule[]>("/outreach/rules");
      setRules(data);
    } catch {
      setRules([]);
    } finally {
      setLoading(false);
    }
  }

  async function fetchEmailStyle() {
    try {
      const data = await api.get<StyleProfile>("/style/profile/email");
      setEmailStyle(data);
    } catch {
      setEmailStyle(null);
    }
  }

  async function handleCreate() {
    if (!name.trim() || !ruleText.trim() || saving) return;
    setSaving(true);
    try {
      const created = await api.post<OutreachRule>("/outreach/rules", {
        name: name.trim(),
        rule_text: ruleText.trim(),
        cadence_days: parseInt(cadenceDays) || 30,
      });
      setRules((prev) => [created, ...prev]);
      setName("");
      setRuleText("");
      setCadenceDays("30");
      setShowForm(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to create rule");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(rule: OutreachRule) {
    try {
      const updated = await api.put<OutreachRule>(`/outreach/rules/${rule.id}`, {
        active: !rule.active,
      });
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to update rule");
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this rule?")) return;
    try {
      await api.delete(`/outreach/rules/${id}`);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete rule");
    }
  }

  const hasStyleGuide = Boolean(emailStyle?.style_md);

  return (
    <div className="page" style={{ maxWidth: 760, margin: "0 auto" }}>
      {toast && <div className="toast">{toast.msg}</div>}

      <div className="page-header">
        <h2 className="page-title">Outreach Rules</h2>
        <button onClick={() => setShowForm((v) => !v)} className="btn btn-primary">
          + New Rule
        </button>
      </div>

      {hasStyleGuide ? (
        <details className="notice notice-success" style={{ marginBottom: 20 }}>
          <summary
            style={{
              cursor: "pointer",
              fontWeight: 500,
              listStyle: "none",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span>✓ Email style guide active</span>
            <span style={{ fontSize: 11, marginLeft: "auto" }}>Preview ▾</span>
          </summary>
          <div
            style={{
              marginTop: 10,
              paddingTop: 10,
              borderTop: "1px solid #a7f3d0",
              maxHeight: 240,
              overflowY: "auto",
            }}
          >
            <MarkdownView md={emailStyle!.style_md} />
          </div>
        </details>
      ) : (
        <div className="notice notice-warning" style={{ marginBottom: 20 }}>
          ⚠ No email style guide — emails will be written generically.{" "}
          <a href="/style" style={{ color: "#92400e", fontWeight: 500 }}>
            Set one up in Style Learning →
          </a>
        </div>
      )}

      {/* ── Create form ── */}
      {showForm && (
        <div className="card card-body" style={{ marginBottom: 24 }}>
          <div className="section-label">Select Customers</div>

          <div>
            <label className="form-label">Rule name</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Lease Expiring Soon"
            />
          </div>

          <div>
            <label className="form-label">Rule description (natural language)</label>
            <textarea
              className="textarea"
              value={ruleText}
              onChange={(e) => setRuleText(e.target.value)}
              placeholder="e.g., customers with a lease ending within 6 months who I haven't contacted in 30 days"
              rows={3}
            />
          </div>

          <div>
            <label className="form-label">Minimum days since last contact</label>
            <input
              className="input"
              type="number"
              value={cadenceDays}
              onChange={(e) => setCadenceDays(e.target.value)}
              style={{ width: 100 }}
            />
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleCreate}
              disabled={saving || !name.trim() || !ruleText.trim()}
              className="btn btn-primary"
            >
              {saving ? "Saving & Parsing…" : "Save Rule"}
            </button>
            <button onClick={() => setShowForm(false)} className="btn btn-secondary">
              Cancel
            </button>
          </div>
          <p style={{ fontSize: 12, color: "var(--color-text-3)", margin: 0 }}>
            The AI will parse your customer rule into a structured filter when you save.
          </p>
        </div>
      )}

      {/* ── Rules list ── */}
      {loading ? (
        <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>Loading…</p>
      ) : rules.length === 0 ? (
        <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>No rules yet. Create one to get started.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {rules.map((rule) => (
            <div key={rule.id} className="card" style={{ padding: "14px 16px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div className="section-label">Select Customers</div>
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4, color: "var(--color-text)" }}>
                    {rule.name}
                    {!rule.active && (
                      <span className="badge badge-muted" style={{ marginLeft: 8 }}>Inactive</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--color-text-3)", marginBottom: 4 }}>
                    {rule.rule_text}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--color-text-4)" }}>
                    Cadence: {rule.cadence_days ?? 30} days
                    {rule.compiled_filter ? " · Parsed ✓" : " · Not yet parsed"}
                  </div>
                  {rule.sql_preview && (
                    <details style={{ marginTop: 6 }}>
                      <summary style={{ fontSize: 11, color: "var(--color-text-3)", cursor: "pointer", userSelect: "none" }}>
                        SQL preview
                      </summary>
                      <pre className="code-block">
                        <code>{rule.sql_preview}</code>
                      </pre>
                    </details>
                  )}
                </div>

                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => setRunModalRule(rule)}
                    disabled={!rule.active || !rule.compiled_filter}
                    className="btn btn-primary"
                    style={{ padding: "5px 12px" }}
                    title={!rule.compiled_filter ? "Rule not parsed yet" : undefined}
                  >
                    Run
                  </button>
                  <button onClick={() => handleToggleActive(rule)} className="btn btn-secondary" style={{ padding: "5px 10px", fontSize: 12 }}>
                    {rule.active ? "Pause" : "Activate"}
                  </button>
                  <button onClick={() => handleDelete(rule.id)} className="btn btn-danger-ghost" style={{ padding: "5px 10px", fontSize: 12 }}>
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Run modal ── */}
      {runModalRule && (
        <RunModal
          rule={runModalRule}
          onClose={() => setRunModalRule(null)}
          onComplete={(count) => {
            setRunModalRule(null);
            if (count > 0) {
              const msg = `${count} draft${count === 1 ? "" : "s"} created — check your Inbox.`;
              setToast({ id: Date.now(), msg });
              setTimeout(() => setToast(null), 5000);
            }
          }}
        />
      )}
    </div>
  );
}

// ─── Run modal ────────────────────────────────────────────────────────────────

function RunModal({
  rule,
  onClose,
  onComplete,
}: {
  rule: OutreachRule;
  onClose: () => void;
  onComplete: (count: number) => void;
}) {
  const [step, setStep] = useState<"loading" | "ready" | "generating" | "done">("loading");
  const [customers, setCustomers] = useState<MatchedCustomer[]>([]);
  const [styleGuideActive, setStyleGuideActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftsCreated, setDraftsCreated] = useState(0);

  const [emailType, setEmailType] = useState(rule.email_type || "lease_finance_ending");
  const [customTemplate, setCustomTemplate] = useState(rule.custom_template || "");
  const [selectedCustomId, setSelectedCustomId] = useState<string | null>(null);
  const [customEmailTypes, setCustomEmailTypes] = useState<CustomEmailType[]>(loadCustomTypes);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    api
      .get<PreviewResult>(`/outreach/rules/${rule.id}/preview`)
      .then((data) => {
        if (!cancelled) {
          setCustomers(data.customers);
          setStyleGuideActive(data.style_guide_active);
          setStep("ready");
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load matched customers");
          setStep("ready");
        }
      });
    return () => { cancelled = true; };
  }, [rule.id]);

  function selectBuiltinType(value: string) {
    setEmailType(value);
    setSelectedCustomId(null);
    setCustomTemplate("");
  }

  function selectCustomType(ct: CustomEmailType) {
    setEmailType("custom");
    setSelectedCustomId(ct.id);
    if (!customTemplate) setCustomTemplate(ct.label);
  }

  function addCustomType(label: string) {
    const ct: CustomEmailType = { id: crypto.randomUUID(), label };
    const updated = [...customEmailTypes, ct];
    setCustomEmailTypes(updated);
    persistCustomTypes(updated);
    selectCustomType(ct);
  }

  function renameCustomType(id: string, newLabel: string) {
    const updated = customEmailTypes.map((t) => (t.id === id ? { ...t, label: newLabel } : t));
    setCustomEmailTypes(updated);
    persistCustomTypes(updated);
  }

  function deleteCustomType(id: string) {
    const updated = customEmailTypes.filter((t) => t.id !== id);
    setCustomEmailTypes(updated);
    persistCustomTypes(updated);
    if (selectedCustomId === id) {
      setEmailType("lease_finance_ending");
      setSelectedCustomId(null);
      setCustomTemplate("");
    }
  }

  async function handleGenerate() {
    setStep("generating");
    setError(null);
    try {
      const result = await api.post<RunResult>(`/outreach/rules/${rule.id}/run`, {
        email_type: emailType,
        custom_template: emailType === "custom" ? customTemplate.trim() || null : null,
      });
      setDraftsCreated(result.drafts_created);
      setStep("done");
      onComplete(result.drafts_created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate drafts");
      setStep("ready");
    }
  }

  const isReady = step === "ready" || step === "generating";
  const isGenerating = step === "generating";

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="modal-panel"
        style={{ width: 760, maxWidth: "95vw", maxHeight: "85vh" }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)" }}>{rule.name}</div>
            {styleGuideActive && step !== "loading" && (
              <div style={{ fontSize: 11, color: "var(--color-success)", marginTop: 2 }}>
                ✓ Style guide active
              </div>
            )}
          </div>
          <button onClick={onClose} className="modal-close">×</button>
        </div>

        {/* Loading */}
        {step === "loading" && (
          <div style={{ padding: 40, textAlign: "center", color: "var(--color-text-3)", fontSize: 13 }}>
            Matching customers…
          </div>
        )}

        {/* Done */}
        {step === "done" && (
          <div style={{ padding: 40, textAlign: "center" }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6, color: "var(--color-text)" }}>
              {draftsCreated} draft{draftsCreated !== 1 ? "s" : ""} created
            </div>
            <div style={{ fontSize: 13, color: "var(--color-text-3)", marginBottom: 20 }}>
              Check your Inbox to review and approve.
            </div>
            <button onClick={onClose} className="btn btn-primary">Close</button>
          </div>
        )}

        {/* Ready / Generating */}
        {isReady && (
          <div style={{ display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
            {/* Left: customer list */}
            <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
              {error && (
                <div className="notice notice-danger" style={{ marginBottom: 12 }}>{error}</div>
              )}
              {customers.length === 0 && !error ? (
                <div style={{ color: "var(--color-text-3)", fontSize: 13 }}>
                  No customers matched this rule.
                </div>
              ) : (
                <>
                  <div className="section-label">
                    {customers.length} customer{customers.length !== 1 ? "s" : ""} matched
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {customers.map((c) => (
                      <MatchedCustomerRow key={c.id} customer={c} />
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Right: email type + generate */}
            <div
              style={{
                width: 260,
                flexShrink: 0,
                borderLeft: "1px solid var(--color-border)",
                padding: 20,
                display: "flex",
                flexDirection: "column",
                overflowY: "auto",
              }}
            >
              <EmailTypePanel
                emailType={emailType}
                selectedCustomId={selectedCustomId}
                customTemplate={customTemplate}
                customEmailTypes={customEmailTypes}
                onBuiltinSelect={selectBuiltinType}
                onCustomTypeSelect={selectCustomType}
                onTemplateChange={setCustomTemplate}
                onAddCustomType={addCustomType}
                onRenameCustomType={renameCustomType}
                onDeleteCustomType={deleteCustomType}
              />
              {customers.length > 0 && (
                <div style={{ marginTop: "auto", paddingTop: 16 }}>
                  <button
                    onClick={handleGenerate}
                    disabled={isGenerating}
                    className="btn btn-primary"
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    {isGenerating
                      ? "Generating…"
                      : `Generate ${customers.length} Draft${customers.length !== 1 ? "s" : ""}`}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Matched customer row ─────────────────────────────────────────────────────

function MatchedCustomerRow({ customer }: { customer: MatchedCustomer }) {
  const primaryCar = customer.cars[0] ?? null;
  const carLabel = primaryCar
    ? [primaryCar.year, primaryCar.make, primaryCar.model].filter(Boolean).join(" ")
    : null;
  const ownershipLabel =
    primaryCar?.ownership_type === "lease"
      ? `Lease${primaryCar.lease_end_date ? ` · ends ${primaryCar.lease_end_date}` : ""}`
      : primaryCar?.ownership_type === "finance"
      ? "Finance"
      : (primaryCar?.ownership_type ?? null);

  return (
    <div className="card" style={{ padding: "10px 12px" }}>
      <div style={{ fontWeight: 600, fontSize: 13, color: "var(--color-text)" }}>{customer.full_name}</div>
      {carLabel && (
        <div style={{ fontSize: 12, color: "var(--color-text-3)", marginTop: 2 }}>
          {carLabel}
          {ownershipLabel ? ` · ${ownershipLabel}` : ""}
        </div>
      )}
      {customer.last_contacted_at ? (
        <div style={{ fontSize: 11, color: "var(--color-text-4)", marginTop: 2 }}>
          Last contact: {new Date(customer.last_contacted_at).toLocaleDateString()}
        </div>
      ) : (
        <div style={{ fontSize: 11, color: "var(--color-text-4)", marginTop: 2 }}>Never contacted</div>
      )}
    </div>
  );
}

// ─── Email type panel ─────────────────────────────────────────────────────────

function EmailTypePanel({
  emailType,
  selectedCustomId,
  customTemplate,
  customEmailTypes,
  onBuiltinSelect,
  onCustomTypeSelect,
  onTemplateChange,
  onAddCustomType,
  onRenameCustomType,
  onDeleteCustomType,
}: {
  emailType: string;
  selectedCustomId: string | null;
  customTemplate: string;
  customEmailTypes: CustomEmailType[];
  onBuiltinSelect: (value: string) => void;
  onCustomTypeSelect: (ct: CustomEmailType) => void;
  onTemplateChange: (t: string) => void;
  onAddCustomType: (label: string) => void;
  onRenameCustomType: (id: string, label: string) => void;
  onDeleteCustomType: (id: string) => void;
}) {
  const [addingNew, setAddingNew] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState("");

  function commitAdd() {
    if (!newLabel.trim()) return;
    onAddCustomType(newLabel.trim());
    setNewLabel("");
    setAddingNew(false);
  }

  function commitRename() {
    if (!editLabel.trim() || !editingId) return;
    onRenameCustomType(editingId, editLabel.trim());
    setEditingId(null);
  }

  const isCustom = emailType === "custom";

  return (
    <>
      <div className="section-label">Email Type</div>

      {/* Built-in types */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        {BUILTIN_TYPES.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onBuiltinSelect(value)}
            className={`type-pill${emailType === value ? " active" : ""}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* User-defined custom types */}
      {customEmailTypes.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8, alignItems: "center" }}>
          {customEmailTypes.map((ct) =>
            editingId === ct.id ? (
              <div key={ct.id} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <input
                  className="input"
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename();
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  style={{ marginBottom: 0, fontSize: 12, padding: "3px 8px", width: 110 }}
                  autoFocus
                />
                <button onClick={commitRename} style={iconBtn("#2563eb")}>✓</button>
                <button onClick={() => setEditingId(null)} style={iconBtn("#9ca3af")}>✕</button>
              </div>
            ) : (
              <div key={ct.id} style={{ display: "flex", alignItems: "center", gap: 1 }}>
                <button
                  onClick={() => onCustomTypeSelect(ct)}
                  className={`type-pill${isCustom && selectedCustomId === ct.id ? " active" : ""}`}
                >
                  {ct.label}
                </button>
                <button
                  onClick={() => { setEditingId(ct.id); setEditLabel(ct.label); }}
                  title="Rename"
                  style={{ fontSize: 11, color: "var(--color-text-4)", background: "none", border: "none", cursor: "pointer", padding: "2px 3px", lineHeight: 1 }}
                >
                  ✎
                </button>
                <button
                  onClick={() => onDeleteCustomType(ct.id)}
                  title="Remove"
                  style={{ fontSize: 13, color: "var(--color-text-4)", background: "none", border: "none", cursor: "pointer", padding: "2px 3px", lineHeight: 1 }}
                >
                  ×
                </button>
              </div>
            )
          )}
        </div>
      )}

      {/* Add new type */}
      {addingNew ? (
        <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 12 }}>
          <input
            className="input"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitAdd();
              if (e.key === "Escape") { setAddingNew(false); setNewLabel(""); }
            }}
            placeholder="e.g., Winter Promotion"
            style={{ marginBottom: 0, fontSize: 12, padding: "4px 8px", flex: 1 }}
            autoFocus
          />
          <button onClick={commitAdd} style={{ ...iconBtn("#2563eb"), padding: "4px 10px", fontSize: 12 }}>
            Add
          </button>
          <button
            onClick={() => { setAddingNew(false); setNewLabel(""); }}
            style={{ ...iconBtn("#9ca3af"), padding: "4px 8px", fontSize: 12 }}
          >
            ✕
          </button>
        </div>
      ) : (
        <button
          onClick={() => setAddingNew(true)}
          style={{
            fontSize: 12,
            color: "var(--color-text-3)",
            background: "none",
            border: "1px dashed var(--color-border-2)",
            borderRadius: 20,
            padding: "4px 12px",
            cursor: "pointer",
            marginBottom: 12,
            fontFamily: "var(--font)",
          }}
        >
          + Add Type
        </button>
      )}

      {/* Template textarea — shown when a custom type is selected */}
      {isCustom && (
        <div>
          <label className="form-label">Email topic / template</label>
          <textarea
            className="textarea"
            value={customTemplate}
            onChange={(e) => onTemplateChange(e.target.value)}
            placeholder="e.g., Snow tires are on sale this week — perfect timing for winter!"
            rows={4}
          />
        </div>
      )}
    </>
  );
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function iconBtn(color: string): React.CSSProperties {
  return {
    background: color === "#2563eb" ? color : "none",
    color: color === "#2563eb" ? "#fff" : color,
    border: color === "#2563eb" ? "none" : "1px solid var(--color-border-2)",
    borderRadius: 4,
    cursor: "pointer",
    padding: "2px 6px",
    fontSize: 11,
    lineHeight: 1.5,
    fontFamily: "var(--font)",
  };
}
