import { useEffect, useState } from "react";
import { api } from "../api/client";

interface SupportDoc {
  id: string;
  category: string;
  title: string;
  content: string;
  checks: string;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
  is_active: boolean;
}

interface DocForm {
  category: string;
  title: string;
  content: string;
  checks: string;
  effective_from: string;
  effective_to: string;
}

const EMPTY_FORM: DocForm = {
  category: "",
  title: "",
  content: "",
  checks: "",
  effective_from: new Date().toISOString().slice(0, 10),
  effective_to: "",
};

function toEditForm(doc: SupportDoc): DocForm {
  return {
    category: doc.category,
    title: doc.title,
    content: doc.content,
    checks: doc.checks,
    effective_from: doc.effective_from,
    effective_to: doc.effective_to ?? "",
  };
}

function parseForm(form: DocForm) {
  return {
    category: form.category.trim(),
    title: form.title.trim(),
    content: form.content.trim(),
    checks: form.checks.trim(),
    effective_from: form.effective_from,
    effective_to: form.effective_to || null,
  };
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "var(--radius-sm)",
        background: "var(--color-primary-pale)",
        color: "var(--color-primary)",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.03em",
      }}
    >
      {category}
    </span>
  );
}

function StatusBadge({ isActive }: { isActive: boolean }) {
  return (
    <span className={isActive ? "badge badge-success" : "badge badge-muted"}>
      {isActive ? "Active" : "Expired"}
    </span>
  );
}

function DocModal({
  doc,
  categories,
  onSave,
  onClose,
}: {
  doc: SupportDoc | null;
  categories: string[];
  onSave: (saved: SupportDoc) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<DocForm>(doc ? toEditForm(doc) : EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEdit = doc !== null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = parseForm(form);
      const saved = isEdit
        ? await api.put<SupportDoc>(`/support-docs/${doc.id}`, payload)
        : await api.post<SupportDoc>("/support-docs", payload);
      onSave(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const labelStyle: React.CSSProperties = { display: "block", marginBottom: 4 };

  return (
    <div onClick={onClose} className="modal-overlay">
      <div
        onClick={(e) => e.stopPropagation()}
        className="modal-panel"
        style={{ width: 600, maxWidth: "95vw" }}
      >
        <div className="modal-header">
          <h2>{isEdit ? "Edit Doc" : "Add Doc"}</h2>
          <button onClick={onClose} className="modal-close">
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: 16 }}>
          {/* Row 1 — Category + Title */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
            <div>
              <label className="form-label" style={labelStyle}>
                Category *
              </label>
              <input
                className="input"
                list="category-options"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                placeholder="e.g. trim_alert"
                required
              />
              <datalist id="category-options">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="form-label" style={labelStyle}>
                Title *
              </label>
              <input
                className="input"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. VW Jetta Trim History 2019–2026"
                required
              />
            </div>
          </div>

          {/* Row 2 — Dates */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label className="form-label" style={labelStyle}>
                Effective From *
              </label>
              <input
                className="input"
                type="date"
                value={form.effective_from}
                onChange={(e) => setForm({ ...form, effective_from: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="form-label" style={labelStyle}>
                Effective To{" "}
                <span style={{ color: "var(--color-text-4)", fontWeight: 400 }}>
                  (leave blank = active)
                </span>
              </label>
              <input
                className="input"
                type="date"
                value={form.effective_to}
                onChange={(e) => setForm({ ...form, effective_to: e.target.value })}
              />
            </div>
          </div>

          {/* Row 3 — Content */}
          <div>
            <label className="form-label" style={labelStyle}>
              Content *
              <span style={{ color: "var(--color-text-4)", fontWeight: 400, marginLeft: 6 }}>
                (raw knowledge — paste from sales guide)
              </span>
            </label>
            <textarea
              className="textarea"
              style={{ minHeight: 140, fontFamily: "monospace", fontSize: 12 }}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="e.g. 2019: Trendline (base), Comfortline (mid), Highline (mid-high), Execline (top)&#10;2022: Trendline (base), Comfortline (mid), Highline (top)&#10;2026: Comfortline (base), Highline (top)"
              required
            />
          </div>

          {/* Row 4 — Checks */}
          <div>
            <label className="form-label" style={labelStyle}>
              AI Instruction (Checks) *
              <span style={{ color: "var(--color-text-4)", fontWeight: 400, marginLeft: 6 }}>
                (plain English — what should the AI look for?)
              </span>
            </label>
            <textarea
              className="textarea"
              style={{ minHeight: 100 }}
              value={form.checks}
              onChange={(e) => setForm({ ...form, checks: e.target.value })}
              placeholder="e.g. Compare the trim the customer purchased against the trim history in Content. Flag if the customer's trim has shifted rank since they bought it."
              required
            />
          </div>

          {error && (
            <div className="notice notice-danger" style={{ padding: "8px 12px", fontSize: 13 }}>
              {error}
            </div>
          )}

          <div className="modal-footer" style={{ padding: "8px 0 0", border: "none" }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="btn btn-primary">
              {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Doc"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DocCard({
  doc,
  onEdit,
  onDelete,
}: {
  doc: SupportDoc;
  onEdit: (doc: SupportDoc) => void;
  onDelete: (id: string) => void;
}) {
  const preview = doc.content.length > 140 ? doc.content.slice(0, 140) + "…" : doc.content;

  return (
    <div
      className="card card-body"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        cursor: "pointer",
        transition: "box-shadow 0.15s",
      }}
      onClick={() => onEdit(doc)}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: "var(--color-text)",
              marginBottom: 4,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {doc.title}
          </div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <CategoryBadge category={doc.category} />
            <StatusBadge isActive={doc.is_active} />
            <span style={{ fontSize: 11, color: "var(--color-text-4)" }}>
              {doc.effective_from}
              {doc.effective_to ? ` → ${doc.effective_to}` : " → active"}
            </span>
          </div>
        </div>
        <button
          className="btn btn-danger-ghost"
          style={{ fontSize: 12, flexShrink: 0 }}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(doc.id);
          }}
        >
          Delete
        </button>
      </div>

      <p
        style={{
          fontSize: 12,
          color: "var(--color-text-3)",
          lineHeight: 1.5,
          fontFamily: "monospace",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          margin: 0,
        }}
      >
        {preview}
      </p>

      {doc.checks && (
        <div
          style={{
            fontSize: 11,
            color: "var(--color-text-4)",
            borderTop: "1px solid var(--color-border)",
            paddingTop: 6,
            marginTop: 2,
          }}
        >
          <span style={{ fontWeight: 600, color: "var(--color-text-3)" }}>AI check: </span>
          {doc.checks.length > 100 ? doc.checks.slice(0, 100) + "…" : doc.checks}
        </div>
      )}
    </div>
  );
}

export default function SupportInfoPage() {
  const [docs, setDocs] = useState<SupportDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [modalDoc, setModalDoc] = useState<SupportDoc | "new" | null>(null);

  async function fetchDocs() {
    try {
      const data = await api.get<SupportDoc[]>("/support-docs");
      setDocs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load support docs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDocs();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this support doc?")) return;
    try {
      await api.delete(`/support-docs/${id}`);
      setDocs(docs.filter((d) => d.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function handleSave(saved: SupportDoc) {
    setDocs((prev) => {
      const idx = prev.findIndex((d) => d.id === saved.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = saved;
        return next;
      }
      return [saved, ...prev];
    });
    setModalDoc(null);
  }

  const categories = Array.from(new Set(docs.map((d) => d.category))).sort();

  const visible =
    selectedCategory === "all" ? docs : docs.filter((d) => d.category === selectedCategory);

  return (
    <div style={{ flex: 1, overflowY: "auto" }}>
      {modalDoc !== null && (
        <DocModal
          doc={modalDoc === "new" ? null : modalDoc}
          categories={categories}
          onSave={handleSave}
          onClose={() => setModalDoc(null)}
        />
      )}

      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Support Info</h1>
            <p style={{ fontSize: 13, color: "var(--color-text-3)", marginTop: 2 }}>
              Knowledge base for AI-powered sales briefings
            </p>
          </div>
          <button className="btn btn-primary" onClick={() => setModalDoc("new")}>
            + Add Doc
          </button>
        </div>

        {loading && <p style={{ color: "var(--color-text-3)" }}>Loading…</p>}
        {error && <div className="notice notice-danger">{error}</div>}

        {!loading && !error && (
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
            {/* Category sidebar */}
            <div
              style={{
                width: 160,
                flexShrink: 0,
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: 8,
                display: "flex",
                flexDirection: "column",
                gap: 2,
              }}
            >
              <button
                className={`btn ${selectedCategory === "all" ? "btn-primary" : "btn-ghost"}`}
                style={{ textAlign: "left", justifyContent: "flex-start", fontSize: 13 }}
                onClick={() => setSelectedCategory("all")}
              >
                All
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color:
                      selectedCategory === "all" ? "rgba(255,255,255,0.7)" : "var(--color-text-4)",
                  }}
                >
                  {docs.length}
                </span>
              </button>
              {categories.map((cat) => {
                const count = docs.filter((d) => d.category === cat).length;
                return (
                  <button
                    key={cat}
                    className={`btn ${selectedCategory === cat ? "btn-primary" : "btn-ghost"}`}
                    style={{ textAlign: "left", justifyContent: "flex-start", fontSize: 13 }}
                    onClick={() => setSelectedCategory(cat)}
                  >
                    {cat}
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 11,
                        color:
                          selectedCategory === cat
                            ? "rgba(255,255,255,0.7)"
                            : "var(--color-text-4)",
                      }}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Doc list */}
            <div style={{ flex: 1, minWidth: 0 }}>
              {visible.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "48px 24px",
                    color: "var(--color-text-3)",
                    background: "var(--color-surface)",
                    border: "1px dashed var(--color-border)",
                    borderRadius: "var(--radius-md)",
                  }}
                >
                  <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
                  <p style={{ fontWeight: 500, marginBottom: 4 }}>No support docs yet</p>
                  <p style={{ fontSize: 12 }}>
                    Add a doc to build your sales briefing knowledge base.
                  </p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {visible.map((doc) => (
                    <DocCard
                      key={doc.id}
                      doc={doc}
                      onEdit={(d) => setModalDoc(d)}
                      onDelete={handleDelete}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
