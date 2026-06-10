import { useEffect, useState } from "react";
import { api } from "../api/client";

interface InventoryItem {
  id: number;
  make: string;
  model: string;
  year: number;
  trim: string | null;
  mileage: number | null;
  price: number | null;
  vin: string | null;
  status: string;
  features: string | null;
  notes: string | null;
  added_at: string;
}

interface ItemForm {
  make: string;
  model: string;
  year: string;
  trim: string;
  mileage: string;
  price: string;
  vin: string;
  status: string;
  features: string;
  notes: string;
}

const EMPTY_FORM: ItemForm = {
  make: "",
  model: "",
  year: "",
  trim: "",
  mileage: "",
  price: "",
  vin: "",
  status: "available",
  features: "",
  notes: "",
};

const STATUS_BADGE: Record<string, string> = {
  available: "badge badge-success",
  reserved: "badge badge-warning",
  sold: "badge badge-muted",
};

const STATUS_LABELS: Record<string, string> = {
  available: "Available",
  reserved: "Reserved",
  sold: "Sold",
};

function fmtPrice(p: number | null): string {
  if (p == null) return "—";
  return "$" + p.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtMileage(m: number | null): string {
  if (m == null) return "—";
  return m.toLocaleString("en-US") + " mi";
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_BADGE[status] ?? "badge badge-muted";
  return <span className={cls}>{STATUS_LABELS[status] ?? status}</span>;
}

function toEditForm(item: InventoryItem): ItemForm {
  return {
    make: item.make,
    model: item.model,
    year: String(item.year),
    trim: item.trim ?? "",
    mileage: item.mileage != null ? String(item.mileage) : "",
    price: item.price != null ? String(item.price) : "",
    vin: item.vin ?? "",
    status: item.status,
    features: item.features ?? "",
    notes: item.notes ?? "",
  };
}

function parseForm(form: ItemForm) {
  return {
    make: form.make,
    model: form.model,
    year: parseInt(form.year),
    trim: form.trim || null,
    mileage: form.mileage ? parseInt(form.mileage) : null,
    price: form.price ? parseFloat(form.price) : null,
    vin: form.vin || null,
    status: form.status,
    features: form.features || null,
    notes: form.notes || null,
  };
}

function VehicleFormFields({ form, setForm }: { form: ItemForm; setForm: (f: ItemForm) => void }) {
  const twoCol: React.CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 };

  return (
    <>
      <div style={twoCol}>
        <div>
          <label className="form-label">Make *</label>
          <input className="input" value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} required />
        </div>
        <div>
          <label className="form-label">Model *</label>
          <input className="input" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} required />
        </div>
      </div>
      <div style={twoCol}>
        <div>
          <label className="form-label">Year *</label>
          <input className="input" type="number" min={1900} max={2100} value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} required />
        </div>
        <div>
          <label className="form-label">Trim</label>
          <input className="input" value={form.trim} onChange={(e) => setForm({ ...form, trim: e.target.value })} />
        </div>
      </div>
      <div style={twoCol}>
        <div>
          <label className="form-label">Mileage</label>
          <input className="input" type="number" min={0} value={form.mileage} onChange={(e) => setForm({ ...form, mileage: e.target.value })} />
        </div>
        <div>
          <label className="form-label">Price ($)</label>
          <input className="input" type="number" min={0} step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
        </div>
      </div>
      <div style={twoCol}>
        <div>
          <label className="form-label">VIN</label>
          <input className="input" maxLength={17} value={form.vin} onChange={(e) => setForm({ ...form, vin: e.target.value })} />
        </div>
        <div>
          <label className="form-label">Status</label>
          <select className="select" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="available">Available</option>
            <option value="reserved">Reserved</option>
            <option value="sold">Sold</option>
          </select>
        </div>
      </div>
      <div>
        <label className="form-label">Features</label>
        <textarea
          className="textarea"
          style={{ minHeight: 64 }}
          placeholder="e.g. blind spot monitoring, back camera, heated seats"
          value={form.features}
          onChange={(e) => setForm({ ...form, features: e.target.value })}
        />
      </div>
      <div>
        <label className="form-label">Notes</label>
        <textarea
          className="textarea"
          style={{ minHeight: 64 }}
          placeholder="e.g. can be put on sale, needs detail before delivery"
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
      </div>
    </>
  );
}

function EditModal({
  item,
  onSave,
  onClose,
}: {
  item: InventoryItem;
  onSave: (updated: InventoryItem) => void;
  onClose: () => void;
}) {
  const [form, setForm] = useState<ItemForm>(toEditForm(item));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await api.put<InventoryItem>(`/inventory/${item.id}`, parseForm(form));
      onSave(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div onClick={onClose} className="modal-overlay">
      <div onClick={(e) => e.stopPropagation()} className="modal-panel" style={{ width: 560 }}>
        <div className="modal-header">
          <div>
            <h2>Edit Vehicle</h2>
            <span style={{ fontSize: 11, color: "var(--color-text-4)", fontFamily: "monospace" }}>
              #{item.id}
            </span>
          </div>
          <button onClick={onClose} className="modal-close">×</button>
        </div>
        <form onSubmit={handleSubmit} className="modal-body" style={{ gap: 16 }}>
          <VehicleFormFields form={form} setForm={setForm} />
          {error && (
            <div className="notice notice-danger" style={{ padding: "8px 12px", fontSize: 13 }}>
              {error}
            </div>
          )}
          <div className="modal-footer" style={{ padding: "8px 0 0", border: "none" }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={saving} className="btn btn-primary">
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function InventoryPage() {
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ItemForm>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<InventoryItem | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  async function fetchInventory() {
    try {
      const data = await api.get<InventoryItem[]>("/inventory");
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchInventory(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await api.post<InventoryItem>("/inventory", parseForm(form));
      setItems([created, ...items]);
      setShowForm(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to add vehicle");
    } finally {
      setSubmitting(false);
    }
  }

  function handleDuplicate(it: InventoryItem) {
    setForm({
      make: it.make,
      model: it.model,
      year: String(it.year),
      trim: it.trim ?? "",
      mileage: it.mileage != null ? String(it.mileage) : "",
      price: it.price != null ? String(it.price) : "",
      vin: "",
      status: "available",
      features: it.features ?? "",
      notes: it.notes ?? "",
    });
    setShowForm(true);
    setFormError(null);
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this vehicle from inventory?")) return;
    try {
      await api.delete(`/inventory/${id}`);
      setItems(items.filter((it) => it.id !== id));
      if (editingItem?.id === id) setEditingItem(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const query = search.trim().toLowerCase();
  const visible = items.filter((it) => {
    const matchStatus = !statusFilter || it.status === statusFilter;
    const matchSearch =
      !query ||
      [it.make, it.model, it.trim, it.vin, String(it.year)].some((v) =>
        v?.toLowerCase().includes(query)
      );
    return matchStatus && matchSearch;
  });

  return (
    <div style={{ flex: 1, overflowY: "auto" }}>
      <div className="page">
        {editingItem && (
          <EditModal
            item={editingItem}
            onSave={(updated) => {
              setItems(items.map((it) => (it.id === updated.id ? updated : it)));
              setEditingItem(null);
            }}
            onClose={() => setEditingItem(null)}
          />
        )}

        <div className="page-header">
          <h1 className="page-title">Inventory</h1>
          <button
            className="btn btn-primary"
            onClick={() => { setShowForm(!showForm); setFormError(null); setForm(EMPTY_FORM); }}
          >
            {showForm ? "Cancel" : "+ Add Vehicle"}
          </button>
        </div>

        <div className="search-bar">
          <input
            type="search"
            placeholder="Search by make, model, trim, VIN, year…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input"
            style={{ width: 320 }}
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="select"
            style={{ width: "auto" }}
          >
            <option value="">All statuses</option>
            <option value="available">Available</option>
            <option value="reserved">Reserved</option>
            <option value="sold">Sold</option>
          </select>
          {(query || statusFilter) && (
            <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>
              {visible.length} of {items.length}
            </span>
          )}
        </div>

        {showForm && (
          <div className="card card-body" style={{ marginBottom: 24 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--color-text)" }}>
              New Vehicle
            </h3>
            <form
              onSubmit={handleCreate}
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <VehicleFormFields form={form} setForm={setForm} />
              {formError && (
                <div className="notice notice-danger" style={{ padding: "8px 12px", fontSize: 13 }}>
                  {formError}
                </div>
              )}
              <div>
                <button type="submit" disabled={submitting} className="btn btn-primary">
                  {submitting ? "Adding…" : "Add Vehicle"}
                </button>
              </div>
            </form>
          </div>
        )}

        {loading && <p style={{ color: "var(--color-text-3)" }}>Loading…</p>}
        {error && <div className="notice notice-danger">{error}</div>}
        {!loading && !error && items.length === 0 && (
          <p style={{ color: "var(--color-text-3)" }}>No vehicles in inventory. Add one above.</p>
        )}
        {!loading && !error && items.length > 0 && visible.length === 0 && (
          <p style={{ color: "var(--color-text-3)" }}>No vehicles match the current filters.</p>
        )}

        {visible.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Vehicle</th>
                <th>VIN</th>
                <th>Mileage</th>
                <th>Price</th>
                <th>Status</th>
                <th>Added</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((it) => (
                <tr key={it.id}>
                  <td style={{ color: "var(--color-text-4)", fontFamily: "monospace" }}>#{it.id}</td>
                  <td style={{ fontWeight: 500, color: "var(--color-text)" }}>
                    {it.year} {it.make} {it.model}
                    {it.trim && (
                      <span style={{ marginLeft: 6, fontWeight: 400, color: "var(--color-text-4)", fontSize: 12 }}>
                        {it.trim}
                      </span>
                    )}
                    {it.features && (
                      <div
                        style={{ fontWeight: 400, fontSize: 11, color: "var(--color-text-3)", marginTop: 2 }}
                        title={it.features}
                      >
                        {it.features.length > 55 ? it.features.slice(0, 55) + "…" : it.features}
                      </div>
                    )}
                    {it.notes && (
                      <div
                        style={{
                          fontWeight: 400,
                          fontSize: 11,
                          color: "var(--color-warning)",
                          fontStyle: "italic",
                          marginTop: 1,
                        }}
                        title={it.notes}
                      >
                        {it.notes.length > 50 ? it.notes.slice(0, 50) + "…" : it.notes}
                      </div>
                    )}
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{it.vin ?? "—"}</td>
                  <td>{fmtMileage(it.mileage)}</td>
                  <td>{fmtPrice(it.price)}</td>
                  <td><StatusBadge status={it.status} /></td>
                  <td style={{ whiteSpace: "nowrap", color: "var(--color-text-4)" }}>
                    {new Date(it.added_at).toLocaleDateString()}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button onClick={() => setEditingItem(it)} className="btn btn-ghost" style={{ fontSize: 12 }}>
                      Edit
                    </button>
                    <button
                      onClick={() => handleDuplicate(it)}
                      className="btn btn-ghost"
                      style={{ fontSize: 12, color: "var(--color-primary)" }}
                    >
                      Duplicate
                    </button>
                    <button
                      onClick={() => handleDelete(it.id)}
                      className="btn btn-danger-ghost"
                      style={{ fontSize: 12 }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
