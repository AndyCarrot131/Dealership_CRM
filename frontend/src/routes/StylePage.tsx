import { useEffect, useState } from "react";
import { MarkdownView } from "../components/MarkdownView";
import { api } from "../api/client";

interface SampleMessage {
  id: number;
  channel: string;
  subject?: string | null;
  raw_content: string;
  label: string;
}

interface StyleProfile {
  channel: string;
  style_md: string;
}

interface Category {
  id: number;
  channel: string;
  name: string;
}

interface StyleRule {
  id: number;
  channel: string;
  category: string;
  rule_text: string;
  active: boolean;
}

type Channel = "email" | "text";

const CHANNELS: Channel[] = ["email", "text"];

export default function StylePage() {
  const [activeChannel, setActiveChannel] = useState<Channel>("email");
  const [samples, setSamples] = useState<SampleMessage[]>([]);
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [summaryMsg, setSummaryMsg] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [adding, setAdding] = useState(false);
  const [newCatName, setNewCatName] = useState("");
  const [addingCat, setAddingCat] = useState(false);
  const [catError, setCatError] = useState("");
  const [catLoadError, setCatLoadError] = useState("");
  const [importingCats, setImportingCats] = useState(false);
  const [expandedSamples, setExpandedSamples] = useState<Set<number>>(new Set());

  // Extra rules state
  const [rules, setRules] = useState<StyleRule[]>([]);
  const [newRuleChannel, setNewRuleChannel] = useState<string>("email");
  const [newRuleCategory, setNewRuleCategory] = useState("");
  const [newRuleText, setNewRuleText] = useState("");
  const [addingRule, setAddingRule] = useState(false);
  const [ruleError, setRuleError] = useState("");

  // Profile edit state
  const [editingProfile, setEditingProfile] = useState(false);
  const [editDraft, setEditDraft] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    fetchCategories();
    fetchSamples();
    fetchProfile();
    fetchRules();
  }, [activeChannel]);

  async function fetchCategories() {
    setCatLoadError("");
    try {
      const data = await api.get<Category[]>(`/style/categories?channel=${activeChannel}`);
      setCategories(data);
    } catch (e) {
      setCategories([]);
      setCatLoadError(e instanceof Error ? e.message : "Failed to load categories");
    }
  }

  async function fetchSamples() {
    setLoadingSamples(true);
    try {
      const data = await api.get<SampleMessage[]>(`/style/samples?channel=${activeChannel}`);
      setSamples(data);
    } catch {
      setSamples([]);
    } finally {
      setLoadingSamples(false);
    }
  }

  async function fetchProfile() {
    try {
      const data = await api.get<StyleProfile>(`/style/profile/${activeChannel}`);
      setProfile(data);
    } catch {
      setProfile(null);
    }
  }

  async function fetchRules() {
    try {
      const data = await api.get<StyleRule[]>("/style/rules");
      setRules(data);
    } catch {
      setRules([]);
    }
  }

  async function handleAddRule() {
    const text = newRuleText.trim();
    if (!text || addingRule) return;
    setAddingRule(true);
    setRuleError("");
    try {
      const created = await api.post<StyleRule>("/style/rules", {
        channel: newRuleChannel,
        category: newRuleCategory.trim(),
        rule_text: text,
      });
      setRules((prev) => [...prev, created]);
      setNewRuleText("");
      setNewRuleCategory("");
    } catch (e) {
      setRuleError(e instanceof Error ? e.message : "Failed to add rule");
    } finally {
      setAddingRule(false);
    }
  }

  async function handleToggleRule(rule: StyleRule) {
    try {
      const updated = await api.patch<StyleRule>(`/style/rules/${rule.id}`, {
        active: !rule.active,
      });
      setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to update rule");
    }
  }

  async function handleDeleteRule(id: number) {
    try {
      await api.delete(`/style/rules/${id}`);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete rule");
    }
  }

  function handleEditProfile() {
    setEditDraft(profile?.style_md ?? "");
    setEditingProfile(true);
  }

  async function handleSaveProfile() {
    if (savingProfile) return;
    setSavingProfile(true);
    try {
      const updated = await api.patch<StyleProfile>(`/style/profile/${activeChannel}`, {
        style_md: editDraft,
      });
      setProfile(updated);
      setEditingProfile(false);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to save profile");
    } finally {
      setSavingProfile(false);
    }
  }

  async function handleImportFromLabels() {
    if (importingCats) return;
    setImportingCats(true);
    setCatError("");
    try {
      const imported = await api.post<Category[]>(
        `/style/categories/import?channel=${activeChannel}`,
        {}
      );
      setCategories(imported);
    } catch (e) {
      setCatError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setImportingCats(false);
    }
  }

  async function handleAddCategory() {
    const name = newCatName.trim();
    if (!name || addingCat) return;
    setAddingCat(true);
    setCatError("");
    try {
      const created = await api.post<Category>("/style/categories", {
        channel: activeChannel,
        name,
      });
      setCategories((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewCatName("");
    } catch (e) {
      setCatError(e instanceof Error ? e.message : "Failed to add category");
    } finally {
      setAddingCat(false);
    }
  }

  async function handleDeleteCategory(id: number) {
    try {
      await api.delete(`/style/categories/${id}`);
      setCategories((prev) => prev.filter((c) => c.id !== id));
      if (newLabel) {
        const deleted = categories.find((c) => c.id === id);
        if (deleted && newLabel === deleted.name) setNewLabel("");
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete category");
    }
  }

  function toggleExpand(id: number) {
    setExpandedSamples((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleRelabel(sampleId: number, newCat: string) {
    try {
      const updated = await api.patch<SampleMessage>(`/style/samples/${sampleId}`, {
        label: newCat,
      });
      setSamples((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to update category");
    }
  }

  async function handleAdd() {
    const content = newContent.trim();
    if (!content || adding) return;
    setAdding(true);
    try {
      const created = await api.post<SampleMessage>("/style/samples", {
        channel: activeChannel,
        subject: activeChannel === "email" ? newSubject.trim() : "",
        raw_content: content,
        label: newLabel,
      });
      setSamples((prev) => [created, ...prev]);
      setNewSubject("");
      setNewContent("");
      setNewLabel("");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to add sample");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.delete(`/style/samples/${id}`);
      setSamples((prev) => prev.filter((s) => s.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to delete");
    }
  }

  async function handleSummarize() {
    if (summarizing) return;
    setSummarizing(true);
    setSummaryMsg("");
    try {
      const updated = await api.post<StyleProfile>(`/style/summarize/${activeChannel}`, {});
      setProfile(updated);
      setSummaryMsg("Style profile updated.");
    } catch (e) {
      setSummaryMsg(e instanceof Error ? e.message : "Failed to summarize");
    } finally {
      setSummarizing(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 960, margin: "0 auto" }}>
      <div className="page-header">
        <h2 className="page-title">Style Learning</h2>
      </div>

      {/* Channel tabs */}
      <div className="tab-group">
        {CHANNELS.map((ch) => (
          <button
            key={ch}
            onClick={() => setActiveChannel(ch)}
            className={`tab-btn${activeChannel === ch ? " active" : ""}`}
          >
            {ch === "email" ? "Email" : "Text / SMS"}
          </button>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28 }}>
        {/* Left: Categories + Samples */}
        <div>
          {/* Categories panel */}
          <div className="card" style={{ padding: 14, marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 600, color: "var(--color-primary)" }}>
              Categories
            </h3>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
              {catLoadError ? (
                <span style={{ fontSize: 12, color: "var(--color-danger)" }}>{catLoadError}</span>
              ) : categories.length === 0 ? (
                <span style={{ fontSize: 12, color: "var(--color-text-3)" }}>
                  No categories yet.
                  {samples.some((s) => s.label.trim()) && (
                    <button
                      onClick={handleImportFromLabels}
                      disabled={importingCats}
                      style={{
                        marginLeft: 8,
                        background: "none",
                        border: "none",
                        color: "var(--color-primary)",
                        cursor: importingCats ? "default" : "pointer",
                        fontSize: 12,
                        padding: 0,
                        textDecoration: "underline",
                        fontFamily: "var(--font)",
                      }}
                    >
                      {importingCats ? "Importing…" : "Import from existing labels"}
                    </button>
                  )}
                </span>
              ) : (
                categories.map((cat) => (
                  <span
                    key={cat.id}
                    className="badge badge-blue"
                    style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 10px" }}
                  >
                    {cat.name}
                    <button
                      onClick={() => handleDeleteCategory(cat.id)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "inherit",
                        padding: 0,
                        fontSize: 14,
                        lineHeight: 1,
                      }}
                      title="Remove category"
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
            </div>

            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input
                className="input"
                placeholder="New category name…"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddCategory()}
                style={{ flex: 1 }}
              />
              <button
                onClick={handleAddCategory}
                disabled={addingCat || !newCatName.trim()}
                className="btn btn-secondary"
                style={{ whiteSpace: "nowrap" }}
              >
                {addingCat ? "Adding…" : "Add"}
              </button>
            </div>
            {catError && (
              <p style={{ fontSize: 12, color: "var(--color-danger)", margin: "6px 0 0" }}>{catError}</p>
            )}
          </div>

          {/* Extra Rules panel */}
          <div className="card" style={{ padding: 14, marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 600, color: "var(--color-primary)" }}>
              Extra Rules
            </h3>

            {rules.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--color-text-3)", margin: "0 0 10px" }}>
                No extra rules yet.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 10 }}>
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 8,
                      padding: "7px 10px",
                      background: rule.active ? "var(--color-bg)" : "var(--color-bg-2)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      opacity: rule.active ? 1 : 0.55,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 3 }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            padding: "2px 7px",
                            borderRadius: 4,
                            background: rule.channel === "email" ? "#e0f2fe" : rule.channel === "text" ? "#dcfce7" : "#f3e8ff",
                            color: rule.channel === "email" ? "#0369a1" : rule.channel === "text" ? "#15803d" : "#7e22ce",
                          }}
                        >
                          {rule.channel === "both" ? "Both" : rule.channel === "email" ? "Email" : "Text"}
                        </span>
                        {rule.category && (
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 500,
                              padding: "2px 7px",
                              borderRadius: 4,
                              background: "var(--color-bg-3)",
                              color: "var(--color-text-3)",
                            }}
                          >
                            {rule.category}
                          </span>
                        )}
                      </div>
                      <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-2)", wordBreak: "break-word" }}>
                        {rule.rule_text}
                      </p>
                    </div>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
                      <button
                        onClick={() => handleToggleRule(rule)}
                        className={`btn ${rule.active ? "btn-secondary" : "btn-ghost"}`}
                        style={{ fontSize: 11, padding: "3px 8px" }}
                        title={rule.active ? "Disable rule" : "Enable rule"}
                      >
                        {rule.active ? "On" : "Off"}
                      </button>
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="btn btn-danger-ghost"
                        style={{ fontSize: 11, padding: "3px 8px" }}
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Add rule form */}
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", gap: 6 }}>
                <select
                  className="select"
                  value={newRuleChannel}
                  onChange={(e) => setNewRuleChannel(e.target.value)}
                  style={{ width: 90, flexShrink: 0 }}
                >
                  <option value="email">Email</option>
                  <option value="text">Text</option>
                  <option value="both">Both</option>
                </select>
                <select
                  className="select"
                  value={newRuleCategory}
                  onChange={(e) => setNewRuleCategory(e.target.value)}
                  style={{ flex: 1 }}
                >
                  <option value="">— No category —</option>
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.name}>{cat.name}</option>
                  ))}
                  <option value="Others">Others</option>
                </select>
              </div>
              <textarea
                className="textarea"
                placeholder="e.g. Don't generate an email ending, sales name is John Smith…"
                value={newRuleText}
                onChange={(e) => setNewRuleText(e.target.value)}
                rows={2}
              />
              <div>
                <button
                  onClick={handleAddRule}
                  disabled={addingRule || !newRuleText.trim()}
                  className="btn btn-primary"
                  style={{ fontSize: 13 }}
                >
                  {addingRule ? "Adding…" : "Add Rule"}
                </button>
              </div>
              {ruleError && (
                <p style={{ fontSize: 12, color: "var(--color-danger)", margin: 0 }}>{ruleError}</p>
              )}
            </div>
          </div>

          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 600, color: "var(--color-text)" }}>
            Sample messages ({samples.length})
          </h3>

          {/* Add sample form */}
          <div className="card card-body" style={{ marginBottom: 16 }}>
            <select
              className="select"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
            >
              <option value="">— No category —</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.name}>{cat.name}</option>
              ))}
            </select>
            {activeChannel === "email" && (
              <input
                className="input"
                placeholder="Subject line…"
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
              />
            )}
            <textarea
              className="textarea"
              placeholder={`Paste a sample ${activeChannel} here…`}
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              rows={5}
            />
            <div>
              <button
                onClick={handleAdd}
                disabled={adding || !newContent.trim()}
                className="btn btn-primary"
              >
                {adding ? "Adding…" : "Add Sample"}
              </button>
            </div>
          </div>

          {/* Sample list */}
          {loadingSamples ? (
            <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>Loading…</p>
          ) : samples.length === 0 ? (
            <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>No samples yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {samples.map((s) => (
                <div key={s.id} className="card" style={{ padding: "10px 12px", fontSize: 13 }}>
                  <div style={{ marginBottom: 6 }}>
                    <select
                      value={s.label}
                      onChange={(e) => handleRelabel(s.id, e.target.value)}
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: s.label ? "#0369a1" : "var(--color-text-4)",
                        background: s.label ? "#e0f2fe" : "var(--color-bg)",
                        border: "1px solid",
                        borderColor: s.label ? "#bae6fd" : "var(--color-border)",
                        borderRadius: 6,
                        padding: "3px 6px",
                        cursor: "pointer",
                        maxWidth: "100%",
                        fontFamily: "var(--font)",
                      }}
                    >
                      <option value="">— No category —</option>
                      {categories.map((cat) => (
                        <option key={cat.id} value={cat.name}>{cat.name}</option>
                      ))}
                      {s.label && !categories.some((c) => c.name === s.label) && (
                        <option value={s.label}>{s.label}</option>
                      )}
                    </select>
                  </div>
                  {s.subject && (
                    <div style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>Subject:</span> {s.subject}
                    </div>
                  )}
                  <div
                    style={{
                      color: "var(--color-text-2)",
                      whiteSpace: "pre-wrap",
                      maxHeight: expandedSamples.has(s.id) ? undefined : 80,
                      overflow: expandedSamples.has(s.id) ? "visible" : "hidden",
                    }}
                  >
                    {s.raw_content}
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 8, alignItems: "center" }}>
                    {s.raw_content.length > 200 && (
                      <button
                        onClick={() => toggleExpand(s.id)}
                        className="btn btn-ghost"
                        style={{ fontSize: 12, padding: 0 }}
                      >
                        {expandedSamples.has(s.id) ? "Show less ▴" : "Show more ▾"}
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="btn btn-danger-ghost"
                      style={{ fontSize: 12, padding: 0 }}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Style Profile */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--color-text)" }}>
              {activeChannel === "email" ? "Email" : "Text"} Style Profile
            </h3>
            {!editingProfile && (
              <>
                <button
                  onClick={handleSummarize}
                  disabled={summarizing || samples.length === 0}
                  className="btn btn-primary"
                >
                  {summarizing ? "Summarizing…" : "Summarize"}
                </button>
                <button
                  onClick={handleEditProfile}
                  className="btn btn-secondary"
                >
                  Edit
                </button>
              </>
            )}
            {editingProfile && (
              <>
                <button
                  onClick={handleSaveProfile}
                  disabled={savingProfile}
                  className="btn btn-primary"
                >
                  {savingProfile ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={() => setEditingProfile(false)}
                  className="btn btn-ghost"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
          {categories.length > 0 && !editingProfile && (
            <p style={{ fontSize: 12, color: "var(--color-text-3)", marginBottom: 10 }}>
              LLM will produce one section per category that has samples.
            </p>
          )}
          {summaryMsg && !editingProfile && (
            <p
              style={{
                fontSize: 12,
                color: summaryMsg.startsWith("Style") ? "var(--color-success)" : "var(--color-danger)",
                marginBottom: 8,
              }}
            >
              {summaryMsg}
            </p>
          )}
          {editingProfile ? (
            <textarea
              className="textarea"
              value={editDraft}
              onChange={(e) => setEditDraft(e.target.value)}
              rows={22}
              style={{ width: "100%", fontFamily: "var(--font-mono, monospace)", fontSize: 13 }}
            />
          ) : profile?.style_md ? (
            <div className="card" style={{ padding: "14px 18px", overflowY: "auto", maxHeight: 520 }}>
              <MarkdownView md={profile.style_md} />
            </div>
          ) : (
            <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>
              No style profile yet. Add samples and click Summarize, or click Edit to write one manually.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
