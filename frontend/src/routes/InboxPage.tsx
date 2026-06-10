import { useEffect, useState } from "react";
import { api } from "../api/client";

interface EmailDraft {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_email?: string;
  rule_id: number | null;
  subject: string;
  body: string;
  status: "pending" | "approved" | "dismissed";
  created_at: string;
  approved_at: string | null;
}

type Filter = "pending" | "approved" | "dismissed" | "all";

const STATUS_COLORS: Record<string, string> = {
  pending: "#2563eb",
  approved: "#16a34a",
  dismissed: "#9ca3af",
};

export default function InboxPage() {
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [filter, setFilter] = useState<Filter>("pending");
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editSubject, setEditSubject] = useState<Record<number, string>>({});
  const [editBody, setEditBody] = useState<Record<number, string>>({});
  const [actioning, setActioning] = useState<number | null>(null);

  useEffect(() => {
    fetchDrafts();
  }, [filter]);

  async function fetchDrafts() {
    setLoading(true);
    try {
      const url =
        filter === "all"
          ? "/outreach/drafts"
          : `/outreach/drafts?draft_status=${filter}`;
      const data = await api.get<EmailDraft[]>(url);
      setDrafts(data);
    } catch {
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  }

  function toggleExpand(draft: EmailDraft) {
    if (expandedId === draft.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(draft.id);
    setEditSubject((prev) => ({ ...prev, [draft.id]: draft.subject }));
    setEditBody((prev) => ({ ...prev, [draft.id]: draft.body }));
  }

  async function handleSaveEdits(id: number) {
    try {
      const updated = await api.patch<EmailDraft>(`/outreach/drafts/${id}`, {
        subject: editSubject[id],
        body: editBody[id],
      });
      setDrafts((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to save edits");
    }
  }

  async function handleApprove(id: number) {
    if (actioning !== null) return;
    setActioning(id);
    try {
      if (editSubject[id] || editBody[id]) {
        await handleSaveEdits(id);
      }
      const updated = await api.post<EmailDraft>(`/outreach/drafts/${id}/approve`, {});
      setDrafts((prev) => prev.map((d) => (d.id === id ? updated : d)));
      setExpandedId(null);
      if (updated.customer_email) {
        const subject = encodeURIComponent(updated.subject);
        const body = encodeURIComponent(updated.body);
        window.open(`mailto:${updated.customer_email}?subject=${subject}&body=${body}`);
      }
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to approve");
    } finally {
      setActioning(null);
    }
  }

  async function handleDismiss(id: number) {
    if (actioning !== null) return;
    setActioning(id);
    try {
      const updated = await api.post<EmailDraft>(`/outreach/drafts/${id}/dismiss`, {});
      setDrafts((prev) => prev.map((d) => (d.id === id ? updated : d)));
      setExpandedId(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed to dismiss");
    } finally {
      setActioning(null);
    }
  }

  const pendingCount = drafts.filter((d) => d.status === "pending").length;

  return (
    <div style={{ padding: "24px 32px", maxWidth: 800, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>
          Outreach Inbox
        </h2>
        {filter === "pending" && pendingCount > 0 && (
          <span
            style={{
              background: "#2563eb",
              color: "#fff",
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
              padding: "2px 8px",
            }}
          >
            {pendingCount}
          </span>
        )}
      </div>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {(["pending", "approved", "dismissed", "all"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            style={{
              padding: "5px 14px",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              background: filter === f ? "#2563eb" : "#fff",
              color: filter === f ? "#fff" : "#374151",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: 500,
              textTransform: "capitalize",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ color: "#888", fontSize: 13 }}>Loading…</p>
      ) : drafts.length === 0 ? (
        <p style={{ color: "#888", fontSize: 13 }}>
          {filter === "pending"
            ? "No pending drafts. Run an outreach rule to generate some."
            : "No drafts."}
        </p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {drafts.map((draft) => (
            <div
              key={draft.id}
              style={{
                background: "#fff",
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                overflow: "hidden",
              }}
            >
              {/* Header row */}
              <div
                onClick={() => toggleExpand(draft)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 14px",
                  cursor: "pointer",
                  userSelect: "none",
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: STATUS_COLORS[draft.status] ?? "#ccc",
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: "#111" }}>
                    {draft.customer_name}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#6b7280",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {draft.subject}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: "#9ca3af", flexShrink: 0 }}>
                  {new Date(draft.created_at).toLocaleDateString()}
                </div>
                <span style={{ color: "#9ca3af", fontSize: 16 }}>
                  {expandedId === draft.id ? "▲" : "▼"}
                </span>
              </div>

              {/* Expanded body */}
              {expandedId === draft.id && (
                <div style={{ padding: "0 14px 14px", borderTop: "1px solid #f3f4f6" }}>
                  <label style={labelStyle}>Subject</label>
                  <input
                    value={editSubject[draft.id] ?? draft.subject}
                    onChange={(e) =>
                      setEditSubject((prev) => ({ ...prev, [draft.id]: e.target.value }))
                    }
                    disabled={draft.status !== "pending"}
                    style={inputStyle}
                  />
                  <label style={labelStyle}>Body</label>
                  <textarea
                    value={editBody[draft.id] ?? draft.body}
                    onChange={(e) =>
                      setEditBody((prev) => ({ ...prev, [draft.id]: e.target.value }))
                    }
                    disabled={draft.status !== "pending"}
                    rows={8}
                    style={{ ...inputStyle, resize: "vertical" }}
                  />

                  {draft.status === "pending" && (
                    <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                      <button
                        onClick={() => handleApprove(draft.id)}
                        disabled={actioning !== null}
                        style={{
                          padding: "6px 16px",
                          background: actioning !== null ? "#86efac" : "#16a34a",
                          color: "#fff",
                          border: "none",
                          borderRadius: 6,
                          cursor: actioning !== null ? "default" : "pointer",
                          fontSize: 13,
                          fontWeight: 500,
                        }}
                      >
                        {actioning === draft.id ? "Approving…" : "Approve"}
                      </button>
                      <button
                        onClick={() => handleDismiss(draft.id)}
                        disabled={actioning !== null}
                        style={{
                          padding: "6px 16px",
                          background: "none",
                          border: "1px solid #d1d5db",
                          borderRadius: 6,
                          cursor: actioning !== null ? "default" : "pointer",
                          fontSize: 13,
                          color: "#374151",
                        }}
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={() => handleSaveEdits(draft.id)}
                        disabled={actioning !== null}
                        style={{
                          padding: "6px 14px",
                          background: "none",
                          border: "1px solid #93c5fd",
                          borderRadius: 6,
                          cursor: actioning !== null ? "default" : "pointer",
                          fontSize: 13,
                          color: "#2563eb",
                        }}
                      >
                        Save edits
                      </button>
                    </div>
                  )}

                  {draft.status !== "pending" && (
                    <p
                      style={{
                        fontSize: 12,
                        color: STATUS_COLORS[draft.status],
                        margin: "8px 0 0",
                        fontWeight: 500,
                        textTransform: "capitalize",
                      }}
                    >
                      {draft.status}
                      {draft.approved_at &&
                        ` on ${new Date(draft.approved_at).toLocaleDateString()}`}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 500,
  color: "#374151",
  marginBottom: 4,
  marginTop: 10,
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "7px 10px",
  borderRadius: 6,
  border: "1px solid #d1d5db",
  fontSize: 13,
  boxSizing: "border-box",
  fontFamily: "inherit",
};
