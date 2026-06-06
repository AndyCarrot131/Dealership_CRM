import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

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

interface EditState {
  full_name: string;
  email: string;
  phone: string;
  note: string;
}

interface CreateForm {
  full_name: string;
  email: string;
  phone: string;
  note: string;
}

const EMPTY_FORM: CreateForm = { full_name: "", email: "", phone: "", note: "" };

const OWNERSHIP_LABELS: Record<string, string> = {
  own: "Owned",
  lease: "Lease",
  finance: "Financed",
};

function carSummary(cars: CustomerCar[]): string {
  if (cars.length === 0) return "—";
  return cars
    .map((c) => [c.year, c.make, c.model].filter(Boolean).join(" "))
    .join(", ");
}

function CarBadge({ car }: { car: CustomerCar }) {
  const label = car.ownership_type ? OWNERSHIP_LABELS[car.ownership_type] ?? car.ownership_type : null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 0", borderBottom: "1px solid #f0f0f0" }}>
      <div style={{ flex: 1 }}>
        <span style={{ fontWeight: 500 }}>
          {[car.year, car.make, car.model].filter(Boolean).join(" ") || "Unknown vehicle"}
        </span>
        {label && (
          <span style={{ marginLeft: 8, fontSize: 11, background: "#e8f0fe", color: "#1a56db", padding: "2px 7px", borderRadius: 10, fontWeight: 500 }}>
            {label}
          </span>
        )}
        {car.lease_end_date && (
          <span style={{ marginLeft: 6, fontSize: 11, color: "#888" }}>
            ends {new Date(car.lease_end_date).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  );
}

function NoteModal({ name, note, onClose }: { name: string; note: string; onClose: () => void }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 12, padding: 28, width: 460, maxHeight: "70vh", display: "flex", flexDirection: "column", boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <h3 style={{ margin: 0, fontSize: 15, color: "#333" }}>Note — {name}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#999", lineHeight: 1 }}>×</button>
        </div>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "#444", whiteSpace: "pre-wrap", overflowY: "auto" }}>{note}</p>
      </div>
    </div>
  );
}

function toEditState(c: Customer): EditState {
  return { full_name: c.full_name, email: c.email ?? "", phone: c.phone ?? "", note: c.note ?? "" };
}

function EditModal({ customer, onSave, onClose }: { customer: Customer; onSave: (updated: Customer) => void; onClose: () => void }) {
  const [state, setState] = useState<EditState>(toEditState(customer));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.put<Customer>(`/customers/${customer.id}`, {
        full_name: state.full_name,
        email: state.email || null,
        phone: state.phone || null,
        note: state.note || null,
      });
      onSave(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const labelStyle: React.CSSProperties = { fontSize: 12, color: "#666", marginBottom: 4, display: "block" };
  const inputStyle: React.CSSProperties = { width: "100%", boxSizing: "border-box", padding: "8px 10px", fontSize: 14, borderRadius: 6, border: "1px solid #ccc" };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 12, padding: 32, width: 500, maxHeight: "90vh", overflowY: "auto", boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>Edit Customer</h2>
            <span style={{ fontSize: 12, color: "#999", fontFamily: "monospace" }}>#{customer.id}</span>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "#999", lineHeight: 1 }}>×</button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <label style={labelStyle}>Full name *</label>
            <input style={inputStyle} value={state.full_name} onChange={(e) => setState({ ...state, full_name: e.target.value })} required />
          </div>
          <div>
            <label style={labelStyle}>Phone</label>
            <input style={inputStyle} value={state.phone} onChange={(e) => setState({ ...state, phone: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>Email</label>
            <input style={inputStyle} type="email" value={state.email} onChange={(e) => setState({ ...state, email: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>Notes</label>
            <textarea style={{ ...inputStyle, resize: "vertical", minHeight: 120 }} value={state.note} onChange={(e) => setState({ ...state, note: e.target.value })} rows={6} />
          </div>

          {customer.cars.length > 0 && (
            <div>
              <label style={labelStyle}>Vehicles ({customer.cars.length})</label>
              <div style={{ border: "1px solid #eee", borderRadius: 6, padding: "4px 12px" }}>
                {customer.cars.map((car) => <CarBadge key={car.id} car={car} />)}
              </div>
              <p style={{ fontSize: 11, color: "#aaa", margin: "6px 0 0" }}>Vehicle records are managed separately.</p>
            </div>
          )}

          {error && <p style={{ color: "red", margin: 0, fontSize: 13 }}>{error}</p>}

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", paddingTop: 8 }}>
            <button type="button" onClick={onClose} style={{ padding: "8px 20px", background: "none", border: "1px solid #ccc", borderRadius: 6, cursor: "pointer" }}>Cancel</button>
            <button type="submit" disabled={saving} style={{ padding: "8px 20px", borderRadius: 6, cursor: "pointer" }}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const { logout } = useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [noteCustomer, setNoteCustomer] = useState<Customer | null>(null);
  const [search, setSearch] = useState("");

  async function fetchCustomers() {
    try {
      const data = await api.get<Customer[]>("/customers");
      setCustomers(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load customers");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchCustomers(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await api.post<Customer>("/customers", {
        full_name: form.full_name,
        email: form.email || null,
        phone: form.phone || null,
        note: form.note || null,
      });
      setCustomers([created, ...customers]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Failed to create customer");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this customer?")) return;
    try {
      await api.delete(`/customers/${id}`);
      setCustomers(customers.filter((c) => c.id !== id));
      if (editingCustomer?.id === id) setEditingCustomer(null);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    }
  }

  const cell: React.CSSProperties = { padding: "8px 12px" };

  const query = search.trim().toLowerCase();
  const visible = query
    ? customers.filter(
        (c) =>
          c.full_name.toLowerCase().includes(query) ||
          (c.note ?? "").toLowerCase().includes(query)
      )
    : customers;

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      {noteCustomer?.note && (
        <NoteModal name={noteCustomer.full_name} note={noteCustomer.note} onClose={() => setNoteCustomer(null)} />
      )}
      {editingCustomer && (
        <EditModal
          customer={editingCustomer}
          onSave={(updated) => { setCustomers(customers.map((c) => (c.id === updated.id ? updated : c))); setEditingCustomer(null); }}
          onClose={() => setEditingCustomer(null)}
        />
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Customers</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => { setShowForm(!showForm); setFormError(null); }}>{showForm ? "Cancel" : "+ Add Customer"}</button>
          <button onClick={logout} style={{ background: "none", border: "1px solid #ccc" }}>Sign out</button>
        </div>
      </div>
      <div style={{ marginBottom: 20, display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="search"
          placeholder="Search by name or note…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ padding: "7px 12px", fontSize: 14, borderRadius: 6, border: "1px solid #ccc", width: 280 }}
        />
        {query && (
          <span style={{ fontSize: 13, color: "#888" }}>
            {visible.length} of {customers.length} customers
          </span>
        )}
      </div>

      {showForm && (
        <form onSubmit={handleCreate} style={{ background: "#f5f5f5", padding: 16, borderRadius: 8, marginBottom: 24, display: "flex", flexDirection: "column", gap: 10 }}>
          <h3 style={{ margin: "0 0 8px" }}>New Customer</h3>
          <input placeholder="Full name *" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          <input placeholder="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <textarea placeholder="Notes" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} rows={3} />
          {formError && <p style={{ color: "red", margin: 0, fontSize: 13 }}>{formError}</p>}
          <button type="submit" disabled={submitting} style={{ alignSelf: "flex-start" }}>{submitting ? "Saving…" : "Save Customer"}</button>
        </form>
      )}

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: "red" }}>{error}</p>}
      {!loading && !error && customers.length === 0 && <p style={{ color: "#888" }}>No customers yet. Add one above.</p>}
      {!loading && !error && customers.length > 0 && visible.length === 0 && (
        <p style={{ color: "#888" }}>No customers match "{search}".</p>
      )}

      {visible.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #eee", textAlign: "left", color: "#555" }}>
              <th style={cell}>ID</th>
              <th style={cell}>Name</th>
              <th style={cell}>Phone</th>
              <th style={cell}>Email</th>
              <th style={cell}>Cars</th>
              <th style={cell}>Note</th>
              <th style={cell}>Added</th>
              <th style={cell}></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((c) => (
              <tr key={c.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ ...cell, color: "#999", fontFamily: "monospace" }}>#{c.id}</td>
                <td style={{ ...cell, fontWeight: 500 }}>{c.full_name}</td>
                <td style={{ ...cell, color: "#555" }}>{c.phone ?? "—"}</td>
                <td style={{ ...cell, color: "#555" }}>{c.email ?? "—"}</td>
                <td style={{ ...cell, maxWidth: 200 }}>
                  {c.cars.length === 0 ? (
                    <span style={{ color: "#bbb" }}>—</span>
                  ) : (
                    c.cars.map((car) => (
                      <div key={car.id} style={{ whiteSpace: "nowrap" }}>
                        <span>{[car.year, car.make, car.model].filter(Boolean).join(" ") || "Unknown"}</span>
                        {car.ownership_type && (
                          <span style={{ marginLeft: 5, fontSize: 11, background: "#e8f0fe", color: "#1a56db", padding: "1px 6px", borderRadius: 8 }}>
                            {OWNERSHIP_LABELS[car.ownership_type] ?? car.ownership_type}
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </td>
                <td style={{ ...cell, color: "#555", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.note ?? "—"}</td>
                <td style={{ ...cell, color: "#999", whiteSpace: "nowrap" }}>{new Date(c.created_at).toLocaleDateString()}</td>
                <td style={{ ...cell, whiteSpace: "nowrap" }}>
                  <button onClick={() => setEditingCustomer(c)} style={{ fontSize: 12, marginRight: 6 }}>Edit</button>
                  {c.note && (
                    <button onClick={() => setNoteCustomer(c)} style={{ fontSize: 12, marginRight: 6, background: "none", border: "1px solid #ccc", cursor: "pointer" }} title="View full note">⤢</button>
                  )}
                  <button onClick={() => handleDelete(c.id)} style={{ background: "none", border: "none", color: "#c00", cursor: "pointer", fontSize: 12 }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
