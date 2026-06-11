import React, { useEffect, useState, useMemo } from "react";
import { api } from "../api/client";

interface Interaction {
  id: number;
  customer_id: number;
  customer_name: string;
  channel: string;
  summary: string;
  contacted_at: string;
}

interface Customer {
  id: number;
  full_name: string;
}

const CHANNELS: { value: string; label: string; color: string; bg: string }[] = [
  { value: "call", label: "Call", color: "#16a34a", bg: "#dcfce7" },
  { value: "text", label: "Text", color: "#2563eb", bg: "#dbeafe" },
  { value: "email", label: "Email", color: "#ea580c", bg: "#ffedd5" },
  { value: "in-person", label: "In-Person", color: "#7c3aed", bg: "#ede9fe" },
];

function SummaryCell({
  interaction,
  expandedSummaries,
  toggle,
}: {
  interaction: Interaction;
  expandedSummaries: Set<number>;
  toggle: (id: number) => void;
}) {
  const expanded = expandedSummaries.has(interaction.id);
  const long = interaction.summary.length > 100;
  return (
    <td style={{ padding: "8px 12px", color: "#444", maxWidth: 420 }}>
      <div
        style={
          expanded
            ? undefined
            : {
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }
        }
      >
        {interaction.summary}
      </div>
      {long && (
        <button
          onClick={() => toggle(interaction.id)}
          style={{
            background: "none",
            border: "none",
            color: "#2563eb",
            cursor: "pointer",
            fontSize: 11,
            padding: "2px 0 0",
          }}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </td>
  );
}

function ChannelBadge({ channel }: { channel: string }) {
  const ch = CHANNELS.find((c) => c.value === channel) ?? { label: channel, color: "#666", bg: "#e5e7eb" };
  return (
    <span
      style={{
        fontSize: 11,
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: 10,
        color: ch.color,
        background: ch.bg,
        whiteSpace: "nowrap",
      }}
    >
      {ch.label}
    </span>
  );
}

interface LogForm {
  customer_id: string;
  channel: string;
  summary: string;
  contacted_at: string;
}

const todayISO = () => new Date().toISOString().slice(0, 10);
const EMPTY_FORM: LogForm = { customer_id: "", channel: "call", summary: "", contacted_at: todayISO() };

export default function ContactsPage() {
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<LogForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState("");

  const [expandedCustomers, setExpandedCustomers] = useState<Set<number>>(new Set());
  const [expandedSummaries, setExpandedSummaries] = useState<Set<number>>(new Set());

  useEffect(() => {
    Promise.all([
      api.get<Interaction[]>("/interactions"),
      api.get<Customer[]>("/customers"),
    ])
      .then(([ints, custs]) => {
        setInteractions(ints);
        setCustomers(custs);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await api.post<Interaction>("/interactions", {
        customer_id: Number(form.customer_id),
        channel: form.channel,
        summary: form.summary,
        contacted_at: form.contacted_at ? `${form.contacted_at}T12:00:00` : undefined,
      });
      setInteractions((prev) => [created, ...prev]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this contact log?")) return;
    try {
      await api.delete(`/interactions/${id}`);
      setInteractions((prev) => prev.filter((i) => i.id !== id));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const q = search.trim().toLowerCase();
  const visible = interactions.filter((i) => {
    if (channelFilter && i.channel !== channelFilter) return false;
    if (q && !i.customer_name.toLowerCase().includes(q) && !i.summary.toLowerCase().includes(q)) return false;
    return true;
  });

  const groups = useMemo(() => {
    const map = new Map<number, { customer_id: number; customer_name: string; interactions: Interaction[] }>();
    for (const i of visible) {
      if (!map.has(i.customer_id)) {
        map.set(i.customer_id, { customer_id: i.customer_id, customer_name: i.customer_name, interactions: [] });
      }
      map.get(i.customer_id)!.interactions.push(i);
    }
    return Array.from(map.values());
  }, [visible]);

  function toggleSummary(id: number) {
    setExpandedSummaries((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const cell: React.CSSProperties = { padding: "8px 12px" };
  const inputStyle: React.CSSProperties = {
    padding: "7px 10px",
    fontSize: 14,
    borderRadius: 6,
    border: "1px solid #d1d5db",
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "inherit",
  };

  return (
    <div style={{ overflowY: "auto", height: "100%", padding: 24 }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h1 style={{ margin: 0 }}>Contact Log</h1>
          <button onClick={() => { setShowForm(!showForm); setFormError(null); }}>
            {showForm ? "Cancel" : "+ Log Contact"}
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleCreate}
            style={{
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              padding: 20,
              borderRadius: 10,
              marginBottom: 24,
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 16,
            }}
          >
            <h3 style={{ margin: 0, gridColumn: "1 / -1", fontSize: 15 }}>New Contact Log</h3>

            <div>
              <label style={{ fontSize: 12, color: "#666", display: "block", marginBottom: 5 }}>Customer *</label>
              <select
                style={inputStyle}
                value={form.customer_id}
                onChange={(e) => setForm({ ...form, customer_id: e.target.value })}
                required
              >
                <option value="">Select customer…</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>{c.full_name}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, color: "#666", display: "block", marginBottom: 5 }}>Date</label>
              <input
                type="date"
                style={inputStyle}
                value={form.contacted_at}
                onChange={(e) => setForm({ ...form, contacted_at: e.target.value })}
              />
            </div>

            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ fontSize: 12, color: "#666", display: "block", marginBottom: 5 }}>Channel *</label>
              <div style={{ display: "flex", gap: 8 }}>
                {CHANNELS.map((ch) => (
                  <button
                    key={ch.value}
                    type="button"
                    onClick={() => setForm({ ...form, channel: ch.value })}
                    style={{
                      flex: 1,
                      padding: "8px 4px",
                      fontSize: 13,
                      fontWeight: 600,
                      borderRadius: 6,
                      cursor: "pointer",
                      border: form.channel === ch.value ? `2px solid ${ch.color}` : "1px solid #d1d5db",
                      color: form.channel === ch.value ? ch.color : "#555",
                      background: form.channel === ch.value ? ch.bg : "#fff",
                    }}
                  >
                    {ch.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ gridColumn: "1 / -1" }}>
              <label style={{ fontSize: 12, color: "#666", display: "block", marginBottom: 5 }}>Summary *</label>
              <textarea
                style={{ ...inputStyle, resize: "vertical", minHeight: 80 }}
                placeholder="What was discussed…"
                value={form.summary}
                onChange={(e) => setForm({ ...form, summary: e.target.value })}
                rows={3}
                required
              />
            </div>

            {formError && (
              <p style={{ color: "red", margin: 0, fontSize: 13, gridColumn: "1 / -1" }}>{formError}</p>
            )}

            <div style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "flex-end" }}>
              <button type="submit" disabled={submitting} style={{ minWidth: 80 }}>
                {submitting ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        )}

        <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
          <input
            type="search"
            placeholder="Search by customer or summary…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: "7px 12px", fontSize: 14, borderRadius: 6, border: "1px solid #d1d5db", width: 280 }}
          />
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            style={{ padding: "7px 10px", fontSize: 14, borderRadius: 6, border: "1px solid #d1d5db" }}
          >
            <option value="">All channels</option>
            {CHANNELS.map((ch) => (
              <option key={ch.value} value={ch.value}>{ch.label}</option>
            ))}
          </select>
          {(search || channelFilter) && (
            <span style={{ fontSize: 13, color: "#888" }}>{groups.length} customers, {visible.length} of {interactions.length} logs</span>
          )}
        </div>

        {loading && <p>Loading…</p>}
        {error && <p style={{ color: "red" }}>{error}</p>}
        {!loading && !error && interactions.length === 0 && (
          <p style={{ color: "#888" }}>No contact logs yet. Click "+ Log Contact" to add one.</p>
        )}
        {!loading && !error && interactions.length > 0 && visible.length === 0 && (
          <p style={{ color: "#888" }}>No results match your filters.</p>
        )}

        {groups.length > 0 && (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", color: "#555" }}>
                <th style={cell}>Date</th>
                <th style={cell}>Channel</th>
                <th style={cell}>Customer</th>
                <th style={cell}>Summary</th>
                <th style={cell}></th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => {
                const [latest, ...rest] = group.interactions;
                const isOpen = expandedCustomers.has(group.customer_id);
                const hasMore = rest.length > 0;

                function toggleGroup() {
                  setExpandedCustomers((prev) => {
                    const next = new Set(prev);
                    next.has(group.customer_id) ? next.delete(group.customer_id) : next.add(group.customer_id);
                    return next;
                  });
                }

                return (
                  <React.Fragment key={group.customer_id}>
                    <tr style={{ borderBottom: isOpen ? "none" : "1px solid #f0f0f0" }}>
                      <td style={{ ...cell, color: "#666", whiteSpace: "nowrap" }}>
                        <span
                          onClick={hasMore ? toggleGroup : undefined}
                          style={{ cursor: hasMore ? "pointer" : "default", userSelect: "none", marginRight: 6, display: "inline-block", width: 12 }}
                        >
                          {hasMore ? (isOpen ? "▾" : "▸") : ""}
                        </span>
                        {new Date(latest.contacted_at).toLocaleDateString()}
                      </td>
                      <td style={cell}><ChannelBadge channel={latest.channel} /></td>
                      <td style={{ ...cell, fontWeight: 500 }}>
                        {group.customer_name}
                        {hasMore && !isOpen && (
                          <span style={{ fontSize: 11, color: "#888", fontWeight: 400, marginLeft: 6 }}>
                            +{rest.length} more
                          </span>
                        )}
                      </td>
                      <SummaryCell interaction={latest} expandedSummaries={expandedSummaries} toggle={toggleSummary} />
                      <td style={cell}>
                        <button
                          onClick={() => handleDelete(latest.id)}
                          style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", fontSize: 12, padding: 0 }}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                    {isOpen && rest.map((i, idx) => (
                      <tr key={i.id} style={{ borderBottom: idx === rest.length - 1 ? "1px solid #f0f0f0" : "none", background: "#fafafa" }}>
                        <td style={{ ...cell, color: "#888", whiteSpace: "nowrap", paddingLeft: 28 }}>
                          {new Date(i.contacted_at).toLocaleDateString()}
                        </td>
                        <td style={cell}><ChannelBadge channel={i.channel} /></td>
                        <td style={cell} />
                        <SummaryCell interaction={i} expandedSummaries={expandedSummaries} toggle={toggleSummary} />
                        <td style={cell}>
                          <button
                            onClick={() => handleDelete(i.id)}
                            style={{ background: "none", border: "none", color: "#dc2626", cursor: "pointer", fontSize: 12, padding: 0 }}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
