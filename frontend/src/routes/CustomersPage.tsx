import { useEffect, useState } from "react";
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

interface CarFormState {
  make: string;
  model: string;
  year: string;
  ownership_type: string;
  lease_end_date: string;
  is_primary: boolean;
}

interface CreateForm {
  full_name: string;
  email: string;
  phone: string;
  note: string;
}

type CarMode = "hidden" | "add" | { car: CustomerCar };

const EMPTY_FORM: CreateForm = { full_name: "", email: "", phone: "", note: "" };
const EMPTY_CAR_FORM: CarFormState = {
  make: "", model: "", year: "", ownership_type: "", lease_end_date: "", is_primary: true,
};

const OWNERSHIP_LABELS: Record<string, string> = {
  own: "Owned",
  lease: "Lease",
  finance: "Financed",
};

function toEditState(c: Customer): EditState {
  return { full_name: c.full_name, email: c.email ?? "", phone: c.phone ?? "", note: c.note ?? "" };
}

function toCarForm(car: CustomerCar): CarFormState {
  return {
    make: car.make ?? "",
    model: car.model ?? "",
    year: car.year?.toString() ?? "",
    ownership_type: car.ownership_type ?? "",
    lease_end_date: car.lease_end_date ?? "",
    is_primary: car.is_primary,
  };
}

function NoteModal({ name, note, onClose }: { name: string; note: string; onClose: () => void }) {
  return (
    <div onClick={onClose} className="modal-overlay">
      <div onClick={(e) => e.stopPropagation()} className="modal-panel" style={{ width: 460 }}>
        <div className="modal-header">
          <h3>Note — {name}</h3>
          <button onClick={onClose} className="modal-close">×</button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 14, lineHeight: 1.7, color: "var(--color-text-2)", whiteSpace: "pre-wrap" }}>
            {note}
          </p>
        </div>
      </div>
    </div>
  );
}

function CarForm({
  carForm,
  setCarForm,
  carSaving,
  carError,
  onSubmit,
  onCancel,
  isEdit,
}: {
  carForm: CarFormState;
  setCarForm: (f: CarFormState) => void;
  carSaving: boolean;
  carError: string | null;
  onSubmit: () => void;
  onCancel: () => void;
  isEdit: boolean;
}) {
  return (
    <div
      style={{
        background: "var(--color-bg)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        padding: 14,
        marginTop: 8,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div>
          <label className="form-label">Make</label>
          <input
            className="input"
            style={{ fontSize: 13 }}
            placeholder="Toyota"
            value={carForm.make}
            onChange={(e) => setCarForm({ ...carForm, make: e.target.value })}
          />
        </div>
        <div>
          <label className="form-label">Model</label>
          <input
            className="input"
            style={{ fontSize: 13 }}
            placeholder="Camry"
            value={carForm.model}
            onChange={(e) => setCarForm({ ...carForm, model: e.target.value })}
          />
        </div>
        <div>
          <label className="form-label">Year</label>
          <input
            className="input"
            style={{ fontSize: 13 }}
            type="number"
            placeholder="2021"
            min="1900"
            max="2100"
            value={carForm.year}
            onChange={(e) => setCarForm({ ...carForm, year: e.target.value })}
          />
        </div>
        <div>
          <label className="form-label">Ownership</label>
          <select
            className="select"
            style={{ fontSize: 13 }}
            value={carForm.ownership_type}
            onChange={(e) =>
              setCarForm({
                ...carForm,
                ownership_type: e.target.value,
                lease_end_date: e.target.value !== "lease" ? "" : carForm.lease_end_date,
              })
            }
          >
            <option value="">— select —</option>
            <option value="own">Owned</option>
            <option value="lease">Lease</option>
            <option value="finance">Financed</option>
          </select>
        </div>
      </div>

      {carForm.ownership_type === "lease" && (
        <div>
          <label className="form-label">Lease end date</label>
          <input
            className="input"
            style={{ width: "auto" }}
            type="date"
            value={carForm.lease_end_date}
            onChange={(e) => setCarForm({ ...carForm, lease_end_date: e.target.value })}
          />
        </div>
      )}

      <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={carForm.is_primary}
          onChange={(e) => setCarForm({ ...carForm, is_primary: e.target.checked })}
        />
        Primary vehicle
      </label>

      {carError && <p style={{ color: "var(--color-danger)", margin: 0, fontSize: 12 }}>{carError}</p>}

      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" disabled={carSaving} onClick={onSubmit} className="btn btn-primary" style={{ padding: "5px 14px" }}>
          {carSaving ? "Saving…" : isEdit ? "Update Vehicle" : "Add Vehicle"}
        </button>
        <button type="button" onClick={onCancel} className="btn btn-secondary" style={{ padding: "5px 12px" }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function EditModal({ customer, onSave, onClose }: { customer: Customer; onSave: (updated: Customer) => void; onClose: () => void }) {
  const [state, setState] = useState<EditState>(toEditState(customer));
  const [localCustomer, setLocalCustomer] = useState<Customer>(customer);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [carMode, setCarMode] = useState<CarMode>("hidden");
  const [carForm, setCarForm] = useState<CarFormState>(EMPTY_CAR_FORM);
  const [carSaving, setCarSaving] = useState(false);
  const [carError, setCarError] = useState<string | null>(null);

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

  function startAddCar() {
    setCarMode("add");
    setCarForm(EMPTY_CAR_FORM);
    setCarError(null);
  }

  function startEditCar(car: CustomerCar) {
    setCarMode({ car });
    setCarForm(toCarForm(car));
    setCarError(null);
  }

  function cancelCarForm() {
    setCarMode("hidden");
    setCarError(null);
  }

  async function handleCarSubmit() {
    setCarSaving(true);
    setCarError(null);
    const payload = {
      make: carForm.make || null,
      model: carForm.model || null,
      year: carForm.year ? parseInt(carForm.year) : null,
      ownership_type: carForm.ownership_type || null,
      lease_end_date: carForm.lease_end_date || null,
      is_primary: carForm.is_primary,
    };
    try {
      let updated: Customer;
      if (carMode === "add") {
        updated = await api.post<Customer>(`/customers/${localCustomer.id}/cars`, payload);
      } else {
        const { car } = carMode as { car: CustomerCar };
        updated = await api.put<Customer>(`/customers/${localCustomer.id}/cars/${car.id}`, payload);
      }
      setLocalCustomer(updated);
      cancelCarForm();
    } catch (err) {
      setCarError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setCarSaving(false);
    }
  }

  async function handleRemoveCar(carId: number) {
    if (!confirm("Remove this vehicle?")) return;
    try {
      const updated = await api.delete<Customer>(`/customers/${localCustomer.id}/cars/${carId}`);
      setLocalCustomer(updated);
      if (carMode !== "hidden" && typeof carMode === "object" && carMode.car.id === carId) {
        cancelCarForm();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Remove failed");
    }
  }

  return (
    <div onClick={onClose} className="modal-overlay">
      <div onClick={(e) => e.stopPropagation()} className="modal-panel" style={{ width: 520, overflowY: "auto" }}>
        <div className="modal-header">
          <div>
            <h2>Edit Customer</h2>
            <span style={{ fontSize: 11, color: "var(--color-text-4)", fontFamily: "monospace" }}>
              #{customer.id}
            </span>
          </div>
          <button onClick={onClose} className="modal-close">×</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div>
            <label className="form-label">Full name *</label>
            <input
              className="input"
              value={state.full_name}
              onChange={(e) => setState({ ...state, full_name: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="form-label">Phone</label>
            <input
              className="input"
              value={state.phone}
              onChange={(e) => setState({ ...state, phone: e.target.value })}
            />
          </div>
          <div>
            <label className="form-label">Email</label>
            <input
              className="input"
              type="email"
              value={state.email}
              onChange={(e) => setState({ ...state, email: e.target.value })}
            />
          </div>
          <div>
            <label className="form-label">Notes</label>
            <textarea
              className="textarea"
              style={{ minHeight: 120 }}
              value={state.note}
              onChange={(e) => setState({ ...state, note: e.target.value })}
              rows={6}
            />
          </div>

          <div>
            <label className="form-label">Vehicles ({localCustomer.cars.length})</label>

            {localCustomer.cars.length > 0 && (
              <div
                style={{
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  overflow: "hidden",
                  marginBottom: 8,
                }}
              >
                {localCustomer.cars.map((car) => {
                  const label = car.ownership_type
                    ? OWNERSHIP_LABELS[car.ownership_type] ?? car.ownership_type
                    : null;
                  const isEditing = typeof carMode === "object" && carMode.car.id === car.id;
                  return (
                    <div key={car.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px" }}>
                        <span style={{ flex: 1, fontWeight: 500, fontSize: 13, color: "var(--color-text)" }}>
                          {[car.year, car.make, car.model].filter(Boolean).join(" ") || "Unknown vehicle"}
                        </span>
                        {label && <span className="badge badge-blue">{label}</span>}
                        {car.lease_end_date && (
                          <span style={{ fontSize: 11, color: "var(--color-text-4)" }}>
                            ends {new Date(car.lease_end_date).toLocaleDateString()}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => (isEditing ? cancelCarForm() : startEditCar(car))}
                          className="btn btn-ghost"
                          style={{ fontSize: 11, padding: "2px 8px" }}
                        >
                          {isEditing ? "Cancel" : "Edit"}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRemoveCar(car.id)}
                          className="btn btn-danger-ghost"
                          style={{ fontSize: 11, padding: "2px 8px" }}
                        >
                          Remove
                        </button>
                      </div>
                      {isEditing && (
                        <div style={{ padding: "0 12px 12px" }}>
                          <CarForm
                            carForm={carForm}
                            setCarForm={setCarForm}
                            carSaving={carSaving}
                            carError={carError}
                            onSubmit={handleCarSubmit}
                            onCancel={cancelCarForm}
                            isEdit={true}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {carMode === "add" ? (
              <CarForm
                carForm={carForm}
                setCarForm={setCarForm}
                carSaving={carSaving}
                carError={carError}
                onSubmit={handleCarSubmit}
                onCancel={cancelCarForm}
                isEdit={false}
              />
            ) : (
              <button
                type="button"
                onClick={startAddCar}
                style={{
                  fontSize: 12,
                  padding: "5px 12px",
                  borderRadius: 6,
                  cursor: "pointer",
                  background: "none",
                  border: "1px dashed var(--color-border-2)",
                  color: "var(--color-text-3)",
                  width: "100%",
                  fontFamily: "var(--font)",
                }}
              >
                + Add Vehicle
              </button>
            )}
          </div>

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

export default function CustomersPage() {
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

  const query = search.trim().toLowerCase();
  const visible = query
    ? customers.filter(
        (c) =>
          c.full_name.toLowerCase().includes(query) ||
          (c.note ?? "").toLowerCase().includes(query)
      )
    : customers;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ flex: 1, overflowY: "auto" }}>
        <div className="page">
          {noteCustomer?.note && (
            <NoteModal
              name={noteCustomer.full_name}
              note={noteCustomer.note}
              onClose={() => setNoteCustomer(null)}
            />
          )}
          {editingCustomer && (
            <EditModal
              customer={editingCustomer}
              onSave={(updated) => {
                setCustomers(customers.map((c) => (c.id === updated.id ? updated : c)));
                setEditingCustomer(null);
              }}
              onClose={() => setEditingCustomer(null)}
            />
          )}

          <div className="page-header">
            <h1 className="page-title">Customers</h1>
            <button
              className="btn btn-primary"
              onClick={() => { setShowForm(!showForm); setFormError(null); }}
            >
              {showForm ? "Cancel" : "+ Add Customer"}
            </button>
          </div>

          <div className="search-bar">
            <input
              type="search"
              placeholder="Search by name or note…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input"
              style={{ width: 280 }}
            />
            {query && (
              <span style={{ fontSize: 13, color: "var(--color-text-3)" }}>
                {visible.length} of {customers.length} customers
              </span>
            )}
          </div>

          {showForm && (
            <div className="card card-body" style={{ marginBottom: 24 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--color-text)" }}>
                New Customer
              </h3>
              <form
                onSubmit={handleCreate}
                style={{ display: "flex", flexDirection: "column", gap: 10 }}
              >
                <div>
                  <label className="form-label">Full name *</label>
                  <input
                    className="input"
                    placeholder="Full name"
                    value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Email</label>
                  <input
                    className="input"
                    placeholder="Email"
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="form-label">Phone</label>
                  <input
                    className="input"
                    placeholder="Phone"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  />
                </div>
                <div>
                  <label className="form-label">Notes</label>
                  <textarea
                    className="textarea"
                    placeholder="Notes"
                    value={form.note}
                    onChange={(e) => setForm({ ...form, note: e.target.value })}
                    rows={3}
                  />
                </div>
                {formError && (
                  <div className="notice notice-danger" style={{ padding: "8px 12px", fontSize: 13 }}>
                    {formError}
                  </div>
                )}
                <div>
                  <button type="submit" disabled={submitting} className="btn btn-primary">
                    {submitting ? "Saving…" : "Save Customer"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {loading && <p style={{ color: "var(--color-text-3)" }}>Loading…</p>}
          {error && <div className="notice notice-danger">{error}</div>}
          {!loading && !error && customers.length === 0 && (
            <p style={{ color: "var(--color-text-3)" }}>No customers yet. Add one above.</p>
          )}
          {!loading && !error && customers.length > 0 && visible.length === 0 && (
            <p style={{ color: "var(--color-text-3)" }}>No customers match "{search}".</p>
          )}

          {visible.length > 0 && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Cars</th>
                  <th>Note</th>
                  <th>Added</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.id}>
                    <td style={{ color: "var(--color-text-4)", fontFamily: "monospace" }}>#{c.id}</td>
                    <td style={{ fontWeight: 500, color: "var(--color-text)" }}>{c.full_name}</td>
                    <td>{c.phone ?? "—"}</td>
                    <td>{c.email ?? "—"}</td>
                    <td style={{ maxWidth: 200 }}>
                      {c.cars.length === 0 ? (
                        <span style={{ color: "var(--color-text-4)" }}>—</span>
                      ) : (
                        c.cars.map((car) => (
                          <div key={car.id} style={{ whiteSpace: "nowrap" }}>
                            <span>
                              {[car.year, car.make, car.model].filter(Boolean).join(" ") || "Unknown"}
                            </span>
                            {car.ownership_type && (
                              <span className="badge badge-blue" style={{ marginLeft: 5 }}>
                                {OWNERSHIP_LABELS[car.ownership_type] ?? car.ownership_type}
                              </span>
                            )}
                          </div>
                        ))
                      )}
                    </td>
                    <td
                      style={{
                        maxWidth: 180,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {c.note ?? "—"}
                    </td>
                    <td style={{ whiteSpace: "nowrap", color: "var(--color-text-4)" }}>
                      {new Date(c.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button onClick={() => setEditingCustomer(c)} className="btn btn-ghost" style={{ fontSize: 12 }}>
                        Edit
                      </button>
                      {c.note && (
                        <button
                          onClick={() => setNoteCustomer(c)}
                          className="btn btn-ghost"
                          style={{ fontSize: 12 }}
                          title="View full note"
                        >
                          ⤢
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(c.id)}
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
    </div>
  );
}
