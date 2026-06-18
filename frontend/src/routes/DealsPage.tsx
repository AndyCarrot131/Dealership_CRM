import React, { useEffect, useRef, useState } from "react";
import { api } from "../api/client";

// ─── types ───────────────────────────────────────────────────────────────────

interface DealListItem {
  id: number;
  customer_id: number;
  customer_name: string;
  deal_type: string;
  contract_date: string;
  make: string;
  model: string;
  model_year: number;
  trim_base: string | null;
  trim_package: string | null;
  selling_price: string;
  payment_amount: string | null;
  payment_frequency: string | null;
  source: string;
  extraction_confidence: string | null;
  created_at: string;
}

interface LineItemRow {
  item_name: string;
  category: string;
  amount: string;
}

interface TradeRow {
  make: string;
  model: string;
  model_year: string;
  trim_base: string;
  vin: string;
  mileage: string;
  allocation: string;
  lien_payout: string;
}

interface DealDetail extends DealListItem {
  [key: string]: unknown;
  line_items: { id: number; item_name: string; category: string | null; amount: string }[];
  trades: {
    id: number;
    make: string | null;
    model: string | null;
    model_year: number | null;
    trim_base: string | null;
    vin: string | null;
    mileage: number | null;
    allocation: string | null;
    lien_payout: string | null;
  }[];
  source_image_path: string | null;
}

interface Candidate {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  matched_on: string;
}

interface ExtractResponse {
  extracted: Record<string, unknown>;
  raw: Record<string, unknown>;
  candidates: Candidate[];
  image_filename: string;
}

interface Customer {
  id: number;
  full_name: string;
}

interface LLMProfile {
  id: number;
  name: string;
  model: string;
  is_active: boolean;
  is_local: boolean;
}

const EXTRACT_PROFILE_KEY = "deals_extract_profile_id";

// ─── field metadata for the review form ─────────────────────────────────────

type FieldDef = { key: string; label: string; kind?: "date" | "select"; options?: string[] };

const FIELD_GROUPS: { title: string; leaseOnly?: boolean; fields: FieldDef[] }[] = [
  {
    title: "Deal",
    fields: [
      { key: "deal_type", label: "Type *", kind: "select", options: ["cash", "finance", "lease"] },
      { key: "contract_date", label: "Contract Date *", kind: "date" },
      { key: "delivery_date", label: "Delivery Date", kind: "date" },
      { key: "first_payment_date", label: "First Payment", kind: "date" },
      { key: "dealership", label: "Dealership" },
      { key: "rep_name_raw", label: "Rep (as printed)" },
    ],
  },
  {
    title: "Vehicle",
    fields: [
      { key: "make", label: "Make *" },
      { key: "model", label: "Model *" },
      { key: "model_year", label: "Year *" },
      { key: "trim_base", label: "Trim (base)" },
      { key: "trim_package", label: "Trim Package" },
      { key: "model_code", label: "Model Code" },
      { key: "vin", label: "VIN" },
      { key: "stock_number", label: "Stock #" },
      { key: "condition", label: "Condition", kind: "select", options: ["new", "used", "demo", "cpo"] },
      { key: "odometer_at_deal", label: "Odometer" },
      { key: "exterior_color", label: "Color" },
      { key: "engine", label: "Engine" },
      { key: "transmission", label: "Transmission" },
      { key: "drivetrain", label: "Drivetrain" },
    ],
  },
  {
    title: "Pricing",
    fields: [
      { key: "base_price", label: "Base Price" },
      { key: "options_adjustment", label: "Options Adj." },
      { key: "selling_price", label: "Selling Price *" },
      { key: "discount", label: "Discount Total" },
      { key: "fees_total", label: "Fees Total" },
      { key: "tax_total", label: "Tax Total" },
      { key: "capital_cost", label: "Capital Cost / Balance to Finance" },
      { key: "total_with_tax", label: "Total Incl. Tax" },
      { key: "cash_down", label: "Cash Down" },
      { key: "trade_equity", label: "Trade Equity" },
      { key: "cap_reduction", label: "Cap Reduction" },
      { key: "drive_off_total", label: "Drive-Off Total" },
    ],
  },
  {
    title: "Terms",
    fields: [
      { key: "lender", label: "Lender" },
      { key: "rate_pct", label: "Rate % (0 = 0% promo)" },
      { key: "term", label: "Term" },
      {
        key: "payment_frequency",
        label: "Frequency",
        kind: "select",
        options: ["", "weekly", "biweekly", "semimonthly", "monthly"],
      },
      { key: "num_payments", label: "# Payments" },
      { key: "base_payment", label: "Base Payment (pre-tax)" },
      { key: "payment_amount", label: "Payment Amount" },
    ],
  },
  {
    title: "Lease Terms",
    leaseOnly: true,
    fields: [
      { key: "residual_msrp", label: "Residual MSRP" },
      { key: "residual_pct", label: "Residual %" },
      { key: "residual_value", label: "Residual Value" },
      { key: "buy_option_price", label: "Buy Option Price" },
      { key: "km_per_year", label: "KM / Year" },
      { key: "excess_km_rate", label: "Excess KM Rate" },
      { key: "security_deposit", label: "Security Deposit" },
    ],
  },
];

const ALL_FIELD_KEYS = FIELD_GROUPS.flatMap((g) => g.fields.map((f) => f.key));
const INT_FIELDS = new Set(["model_year", "odometer_at_deal", "term", "num_payments", "km_per_year"]);
const CATEGORIES = ["admin", "gov_levy", "protection", "registration", "discount", "other"];

const DEAL_TYPE_BADGE: Record<string, { color: string; bg: string }> = {
  cash: { color: "#16a34a", bg: "#dcfce7" },
  finance: { color: "#2563eb", bg: "#dbeafe" },
  lease: { color: "#7c3aed", bg: "#ede9fe" },
};

const EMPTY_FORM: Record<string, string> = Object.fromEntries(
  ALL_FIELD_KEYS.map((k) => [k, k === "condition" ? "new" : ""])
);

const EMPTY_TRADE: TradeRow = {
  make: "", model: "", model_year: "", trim_base: "", vin: "", mileage: "",
  allocation: "", lien_payout: "0",
};

// ─── small helpers ───────────────────────────────────────────────────────────

function fmtMoney(v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("en-CA", { style: "currency", currency: "CAD" });
}

function vehicleLabel(d: { model_year: number; make: string; model: string; trim_base: string | null; trim_package: string | null }) {
  return [d.model_year, d.make, d.model, d.trim_base, d.trim_package].filter(Boolean).join(" ");
}

function str(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

function addMonths(isoDate: string, months: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  let month = m - 1 + months;
  const year = y + Math.floor(month / 12);
  month = (month % 12) + 1;
  const lastDay = new Date(year, month, 0).getDate();
  const day = Math.min(d, lastDay);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function computeContractEndDate(form: Record<string, string>): string {
  const dealType = form.deal_type;
  if (dealType !== "lease" && dealType !== "finance") return "";
  const start = form.contract_date || form.first_payment_date || form.delivery_date;
  if (!start) return "";
  const term = form.term.trim()
    ? Number(form.term)
    : form.num_payments.trim()
      ? Number(form.num_payments)
      : null;
  if (term === null || Number.isNaN(term) || term <= 0) return "";
  return addMonths(start, term);
}

function DealTypeBadge({ dealType }: { dealType: string }) {
  const s = DEAL_TYPE_BADGE[dealType] ?? { color: "#666", bg: "#e5e7eb" };
  return (
    <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 10, color: s.color, background: s.bg, textTransform: "capitalize" }}>
      {dealType}
    </span>
  );
}

async function openDealImage(dealId: number) {
  const token = sessionStorage.getItem("crm_token");
  const res = await fetch(`/api/deals/${dealId}/image`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Image not available");
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
}

// ─── page ────────────────────────────────────────────────────────────────────

type Step = "idle" | "pick" | "extracting" | "review" | "saving";

export default function DealsPage() {
  const [deals, setDeals] = useState<DealListItem[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DealDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // upload → extract → review flow
  const [step, setStep] = useState<Step>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [flowError, setFlowError] = useState<string | null>(null);

  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [lineItems, setLineItems] = useState<LineItemRow[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [customerMode, setCustomerMode] = useState<"existing" | "new">("new");
  const [customerId, setCustomerId] = useState<string>("");
  const [newCustomer, setNewCustomer] = useState({ full_name: "", phone: "", email: "" });
  const [imageFilename, setImageFilename] = useState<string | null>(null);
  const [extractionRaw, setExtractionRaw] = useState<Record<string, unknown> | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [llmProfiles, setLlmProfiles] = useState<LLMProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [profilesLoading, setProfilesLoading] = useState(false);

  useEffect(() => {
    Promise.all([api.get<DealListItem[]>("/deals"), api.get<Customer[]>("/customers")])
      .then(([ds, cs]) => {
        setDeals(ds);
        setCustomers(cs);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  async function toggleDetail(id: number) {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await api.get<DealDetail>(`/deals/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load deal");
    } finally {
      setDetailLoading(false);
    }
  }

  async function loadLlmProfiles() {
    setProfilesLoading(true);
    try {
      const profiles = await api.get<LLMProfile[]>("/settings/llm/profiles");
      setLlmProfiles(profiles);
      const saved = sessionStorage.getItem(EXTRACT_PROFILE_KEY);
      const savedId = saved && profiles.some((p) => p.id === Number(saved)) ? saved : null;
      const active = profiles.find((p) => p.is_active);
      const defaultId = savedId ?? (active ? String(active.id) : profiles[0] ? String(profiles[0].id) : "");
      setSelectedProfileId(defaultId);
    } catch {
      setLlmProfiles([]);
      setSelectedProfileId("");
    } finally {
      setProfilesLoading(false);
    }
  }

  function openExtractFlow() {
    resetFlow();
    setStep("pick");
    void loadLlmProfiles();
  }

  function resetFlow() {
    setStep("idle");
    setFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setFlowError(null);
    setForm(EMPTY_FORM);
    setLineItems([]);
    setTrades([]);
    setCandidates([]);
    setCustomerMode("new");
    setCustomerId("");
    setNewCustomer({ full_name: "", phone: "", email: "" });
    setImageFilename(null);
    setExtractionRaw(null);
    setConfidence(null);
  }

  function startManual() {
    resetFlow();
    setStep("review");
    setCustomerMode("existing");
  }

  function acceptFile(f: File | null) {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFile(e.target.files?.[0] ?? null);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && /^image\/(jpeg|png|webp)$/.test(f.type)) acceptFile(f);
  }

  async function handleExtract() {
    if (!file) return;
    setFlowError(null);
    setStep("extracting");
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (selectedProfileId) {
        fd.append("profile_id", selectedProfileId);
        sessionStorage.setItem(EXTRACT_PROFILE_KEY, selectedProfileId);
      }
      const res = await api.upload<ExtractResponse>("/deals/extract", fd);
      const ex = res.extracted;

      const next: Record<string, string> = { ...EMPTY_FORM };
      for (const key of ALL_FIELD_KEYS) next[key] = str(ex[key]) || next[key];
      setForm(next);

      setLineItems(
        ((ex.line_items as Record<string, unknown>[]) ?? []).map((li) => ({
          item_name: str(li.item_name),
          category: str(li.category) || "other",
          amount: str(li.amount),
        }))
      );
      setTrades(
        ((ex.trades as Record<string, unknown>[]) ?? []).map((tr) => ({
          make: str(tr.make),
          model: str(tr.model),
          model_year: str(tr.model_year),
          trim_base: str(tr.trim_base),
          vin: str(tr.vin),
          mileage: str(tr.mileage),
          allocation: str(tr.allocation),
          lien_payout: str(tr.lien_payout) || "0",
        }))
      );

      const cust = (ex.customer as Record<string, unknown>) ?? {};
      const rawCust = (res.raw?.customer as Record<string, unknown>) ?? {};
      const pick = (...vals: unknown[]) => {
        for (const v of vals) {
          const s = str(v).trim();
          if (s) return s;
        }
        return "";
      };
      setNewCustomer({
        full_name: pick(cust.name, cust.full_name, rawCust.name, rawCust.full_name, res.raw?.customer_name),
        phone: pick(cust.phone, cust.cell, rawCust.phone, rawCust.cell, res.raw?.phone, res.raw?.customer_phone),
        email: pick(cust.email, cust.email_address, rawCust.email, rawCust.email_address, res.raw?.email, res.raw?.customer_email),
      });
      setCandidates(res.candidates);
      if (res.candidates.length > 0) {
        setCustomerMode("existing");
        setCustomerId(String(res.candidates[0].id));
      } else {
        setCustomerMode("new");
      }
      setImageFilename(res.image_filename);
      setExtractionRaw(res.raw);
      setConfidence(typeof ex.confidence === "number" ? ex.confidence : null);
      setStep("review");
    } catch (e) {
      setFlowError(e instanceof Error ? e.message : "Extraction failed");
      setStep("pick");
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setFlowError(null);

    const deal: Record<string, unknown> = {};
    for (const key of ALL_FIELD_KEYS) {
      const v = form[key].trim();
      if (v === "") continue; // omitted → null server-side
      deal[key] = INT_FIELDS.has(key) ? Number(v) : v; // money stays string → Decimal
    }

    const payload = {
      customer:
        customerMode === "existing"
          ? { customer_id: Number(customerId) }
          : { new_customer: { full_name: newCustomer.full_name, phone: newCustomer.phone || null, email: newCustomer.email || null } },
      deal,
      line_items: lineItems
        .filter((li) => li.item_name.trim() && li.amount.trim())
        .map((li) => ({ item_name: li.item_name.trim(), category: li.category || null, amount: li.amount.trim() })),
      trades: trades
        .filter((tr) => Object.values(tr).some((v) => v.trim() !== "" && v !== "0"))
        .map((tr) => ({
          make: tr.make.trim() || null,
          model: tr.model.trim() || null,
          model_year: tr.model_year.trim() ? Number(tr.model_year) : null,
          trim_base: tr.trim_base.trim() || null,
          vin: tr.vin.trim() || null,
          mileage: tr.mileage.trim() ? Number(tr.mileage) : null,
          allocation: tr.allocation.trim() || null,
          lien_payout: tr.lien_payout.trim() || "0",
        })),
      image_filename: imageFilename,
      extraction_raw: extractionRaw,
      extraction_confidence: confidence,
    };

    setStep("saving");
    try {
      await api.post<DealDetail>("/deals", payload);
      const ds = await api.get<DealListItem[]>("/deals");
      setDeals(ds);
      resetFlow();
    } catch (err) {
      setFlowError(err instanceof Error ? err.message : "Failed to save deal");
      setStep("review");
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Delete this deal?")) return;
    try {
      await api.delete(`/deals/${id}`);
      setDeals((prev) => prev.filter((d) => d.id !== id));
      if (expandedId === id) {
        setExpandedId(null);
        setDetail(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  }

  const isLease = form.deal_type === "lease";
  const isFinanceOrLease = form.deal_type === "lease" || form.deal_type === "finance";
  const contractEndDate = computeContractEndDate(form);
  const endDateLabel = form.deal_type === "finance" ? "Finance end date" : "Lease end date";

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Deals</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={startManual}>
            Manual Entry
          </button>
          <button className="btn btn-primary" onClick={openExtractFlow}>
            📷 Extract from Photo
          </button>
        </div>
      </div>

      {error && <div style={{ color: "#dc2626", marginBottom: 12 }}>{error}</div>}

      {loading ? (
        <div>Loading…</div>
      ) : deals.length === 0 ? (
        <div style={{ color: "#64748b", padding: "40px 0", textAlign: "center" }}>
          No deals yet. Upload a photo of a signed deal sheet to get started.
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Contract Date</th>
              <th>Customer</th>
              <th>Vehicle</th>
              <th>Type</th>
              <th>Selling Price</th>
              <th>Payment</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <React.Fragment key={d.id}>
                <tr onClick={() => toggleDetail(d.id)} style={{ cursor: "pointer" }}>
                  <td>{d.contract_date}</td>
                  <td>{d.customer_name}</td>
                  <td>{vehicleLabel(d)}</td>
                  <td><DealTypeBadge dealType={d.deal_type} /></td>
                  <td>{fmtMoney(d.selling_price)}</td>
                  <td>
                    {d.payment_amount ? `${fmtMoney(d.payment_amount)}${d.payment_frequency ? ` / ${d.payment_frequency}` : ""}` : "—"}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger-ghost"
                      onClick={(e) => { e.stopPropagation(); handleDelete(d.id); }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {expandedId === d.id && (
                  <tr>
                    <td colSpan={7} style={{ background: "#f8fafc", padding: 16 }}>
                      {detailLoading || !detail ? (
                        <div>Loading…</div>
                      ) : (
                        <DealDetailView detail={detail} />
                      )}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}

      {step !== "idle" && (
        <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget && step !== "extracting" && step !== "saving") resetFlow(); }}>
          <div className="modal-panel" style={{
            maxWidth: step === "review" ? 1400 : 480,
            width: step === "review" ? "95vw" : "92%",
            height: step === "review" || step === "saving" ? "90vh" : undefined,
            maxHeight: "90vh",
            overflow: step === "review" || step === "saving" ? "hidden" : "auto",
            display: "flex",
            flexDirection: "column",
          }}>
            <div className="modal-header">
              <span>
                {step === "pick" && "Extract Deal from Photo"}
                {step === "extracting" && "Extracting…"}
                {(step === "review" || step === "saving") && (imageFilename ? "Review Extracted Deal" : "New Deal")}
              </span>
              {step !== "extracting" && step !== "saving" && (
                <button className="modal-close" onClick={resetFlow}>×</button>
              )}
            </div>
            <div
              className="modal-body"
              style={
                step === "review" || step === "saving"
                  ? {
                      padding: 0,
                      display: "flex",
                      flexDirection: "row",
                      flex: 1,
                      overflow: "hidden",
                      minHeight: 0,
                      gap: 0,
                    }
                  : undefined
              }
            >
              {flowError && (step === "pick" || step === "extracting") && (
                <div style={{ color: "#dc2626", marginBottom: 12, fontSize: 13 }}>{flowError}</div>
              )}

              {step === "pick" && (
                <div>
                  <p style={{ fontSize: 13, color: "#475569", marginTop: 0 }}>
                    Take a photo of the signed deal worksheet (lease, finance, or cash) and the AI
                    will extract the fields for your review.
                  </p>
                  <label style={{ display: "block", fontSize: 12, color: "#475569", marginBottom: 12 }}>
                    Vision model
                    <select
                      className="select"
                      value={selectedProfileId}
                      onChange={(e) => setSelectedProfileId(e.target.value)}
                      disabled={profilesLoading || llmProfiles.length === 0}
                      style={{ marginTop: 4 }}
                    >
                      {profilesLoading && <option value="">Loading models…</option>}
                      {!profilesLoading && llmProfiles.length === 0 && (
                        <option value="">No LLM profiles — add one in Settings</option>
                      )}
                      {llmProfiles.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.model}){p.is_active ? " · active for chat" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <p style={{ fontSize: 11, color: "#94a3b8", margin: "0 0 12px" }}>
                    Chat uses your active text model. Pick a vision-capable profile here for photo extraction.
                  </p>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    style={{
                      border: `2px dashed ${dragOver ? "#2563eb" : "#cbd5e1"}`,
                      borderRadius: 10,
                      padding: "28px 16px",
                      textAlign: "center",
                      cursor: "pointer",
                      background: dragOver ? "#eff6ff" : "#f8fafc",
                      transition: "border-color 0.15s, background 0.15s",
                      userSelect: "none",
                    }}
                  >
                    <div style={{ fontSize: 28, marginBottom: 6 }}>📁</div>
                    <div style={{ fontSize: 13, color: "#475569" }}>
                      {file ? file.name : "Drag & drop an image here, or click to browse"}
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 4 }}>JPEG, PNG, or WebP</div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      style={{ display: "none" }}
                    />
                  </div>
                  {previewUrl && (
                    <img
                      src={previewUrl}
                      alt="contract preview"
                      style={{ display: "block", maxWidth: "100%", maxHeight: 320, marginTop: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
                    />
                  )}
                  <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                    <button
                      className="btn btn-primary"
                      style={{ flex: 1 }}
                      disabled={!file || !selectedProfileId || profilesLoading}
                      onClick={handleExtract}
                    >
                      Extract
                    </button>
                    <button className="btn btn-secondary" style={{ flex: 1 }} onClick={resetFlow}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {step === "extracting" && (
                <div style={{ textAlign: "center", padding: "32px 0", color: "#475569" }}>
                  <div style={{ fontSize: 28, marginBottom: 12 }}>🔍</div>
                  Reading the contract… this can take a few minutes on local models.
                </div>
              )}

              {(step === "review" || step === "saving") && (
                <>
                  {previewUrl && (
                    <div style={{
                      width: "42%", minWidth: 260, maxWidth: 560,
                      borderRight: "1px solid #e2e8f0",
                      overflow: "auto",
                      padding: 12,
                      background: "#f8fafc",
                      flexShrink: 0,
                      alignSelf: "stretch",
                    }}>
                      <img
                        src={previewUrl}
                        alt="contract"
                        style={{ width: "100%", borderRadius: 6, display: "block" }}
                      />
                    </div>
                  )}
                  <div style={{ flex: 1, overflow: "auto", padding: 16, minWidth: 0 }}>
                <form onSubmit={handleSave}>
                  {flowError && (
                    <div style={{ color: "#dc2626", marginBottom: 12, fontSize: 13 }}>{flowError}</div>
                  )}
                  {confidence !== null && confidence < 0.8 && (
                    <div style={{ background: "#fffbeb", border: "1px solid #fcd34d", color: "#92400e", borderRadius: 8, padding: "8px 12px", fontSize: 13, marginBottom: 14 }}>
                      ⚠ Low extraction confidence ({Math.round(confidence * 100)}%) — verify every field against the photo.
                    </div>
                  )}

                  {/* customer */}
                  <h3 style={{ fontSize: 14, margin: "0 0 8px" }}>Customer</h3>
                  {candidates.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      {candidates.map((c) => (
                        <label key={c.id} style={{ display: "block", fontSize: 13, padding: "4px 0" }}>
                          <input
                            type="radio"
                            name="customer"
                            checked={customerMode === "existing" && customerId === String(c.id)}
                            onChange={() => { setCustomerMode("existing"); setCustomerId(String(c.id)); }}
                          />{" "}
                          <strong>{c.full_name}</strong>
                          {c.phone ? ` · ${c.phone}` : ""}
                          {c.email ? ` · ${c.email}` : ""}
                          <span style={{ color: "#64748b" }}> (matched by {c.matched_on})</span>
                        </label>
                      ))}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 16, marginBottom: 8, fontSize: 13 }}>
                    {candidates.length === 0 && (
                      <label>
                        <input
                          type="radio"
                          name="customer_mode"
                          checked={customerMode === "existing"}
                          onChange={() => setCustomerMode("existing")}
                        />{" "}
                        Existing customer
                      </label>
                    )}
                    <label>
                      <input
                        type="radio"
                        name="customer_mode"
                        checked={customerMode === "new"}
                        onChange={() => setCustomerMode("new")}
                      />{" "}
                      Create new customer
                    </label>
                  </div>
                  {customerMode === "existing" && (
                    <select
                      className="select"
                      value={customerId}
                      onChange={(e) => setCustomerId(e.target.value)}
                      required
                      style={{ marginBottom: 12 }}
                    >
                      <option value="">Select customer…</option>
                      {customers.map((c) => (
                        <option key={c.id} value={c.id}>{c.full_name}</option>
                      ))}
                    </select>
                  )}
                  {customerMode === "new" && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 12 }}>
                      <input className="input" placeholder="Full name *" required value={newCustomer.full_name}
                        onChange={(e) => setNewCustomer({ ...newCustomer, full_name: e.target.value })} />
                      <input className="input" placeholder="Phone" value={newCustomer.phone}
                        onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })} />
                      <input className="input" placeholder="Email" value={newCustomer.email}
                        onChange={(e) => setNewCustomer({ ...newCustomer, email: e.target.value })} />
                    </div>
                  )}

                  {/* deal fields */}
                  {FIELD_GROUPS.filter((g) => !g.leaseOnly || isLease).map((group) => (
                    <div key={group.title} style={{ marginBottom: 12 }}>
                      <h3 style={{ fontSize: 14, margin: "0 0 8px" }}>{group.title}</h3>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 8 }}>
                        {group.fields.map((f) => (
                          <label key={f.key} style={{ fontSize: 12, color: "#475569" }}>
                            {f.label}
                            {f.kind === "select" ? (
                              <select
                                className="select"
                                value={form[f.key]}
                                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                              >
                                {f.options!.map((o) => (
                                  <option key={o} value={o}>{o === "" ? "—" : o}</option>
                                ))}
                              </select>
                            ) : (
                              <input
                                className="input"
                                type={f.kind === "date" ? "date" : "text"}
                                required={f.label.endsWith("*")}
                                value={form[f.key]}
                                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                              />
                            )}
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}

                  {isFinanceOrLease && (
                    <div style={{ marginBottom: 12 }}>
                      <h3 style={{ fontSize: 14, margin: "0 0 8px" }}>Customer Vehicle</h3>
                      <p style={{ fontSize: 12, color: "#64748b", margin: "0 0 8px" }}>
                        Saving adds this vehicle to the customer profile with ownership and end date from the terms above.
                      </p>
                      <label style={{ fontSize: 12, color: "#475569", display: "block", maxWidth: 220 }}>
                        {endDateLabel}
                        <input
                          className="input"
                          type="date"
                          readOnly
                          value={contractEndDate}
                          style={{ background: "#f8fafc", color: contractEndDate ? "#0f172a" : "#94a3b8" }}
                          placeholder="Set contract date + term"
                        />
                      </label>
                      {!contractEndDate && (
                        <div style={{ fontSize: 11, color: "#92400e", marginTop: 4 }}>
                          Enter contract date and term to calculate the end date.
                        </div>
                      )}
                    </div>
                  )}

                  {/* line items */}
                  <h3 style={{ fontSize: 14, margin: "12px 0 8px" }}>
                    Fees & Discounts <span style={{ fontWeight: 400, color: "#64748b" }}>(discounts negative)</span>
                  </h3>
                  {lineItems.map((li, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: 8, marginBottom: 6 }}>
                      <input className="input" placeholder="Item (as printed)" value={li.item_name}
                        onChange={(e) => setLineItems(lineItems.map((x, j) => (j === i ? { ...x, item_name: e.target.value } : x)))} />
                      <select className="select" value={li.category}
                        onChange={(e) => setLineItems(lineItems.map((x, j) => (j === i ? { ...x, category: e.target.value } : x)))}>
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                      <input className="input" placeholder="Amount" value={li.amount}
                        onChange={(e) => setLineItems(lineItems.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))} />
                      <button type="button" className="btn btn-ghost" onClick={() => setLineItems(lineItems.filter((_, j) => j !== i))}>×</button>
                    </div>
                  ))}
                  <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }}
                    onClick={() => setLineItems([...lineItems, { item_name: "", category: "other", amount: "" }])}>
                    + Add line item
                  </button>

                  {/* trades */}
                  <h3 style={{ fontSize: 14, margin: "16px 0 8px" }}>Trade-In Vehicles</h3>
                  {trades.map((tr, i) => (
                    <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 10, marginBottom: 8 }}>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                        {([
                          ["make", "Make"], ["model", "Model"], ["model_year", "Year"], ["trim_base", "Trim"],
                          ["vin", "VIN"], ["mileage", "Mileage"], ["allocation", "Allocation $"], ["lien_payout", "Lien Payout $"],
                        ] as [keyof TradeRow, string][]).map(([key, label]) => (
                          <label key={key} style={{ fontSize: 12, color: "#475569" }}>
                            {label}
                            <input className="input" value={tr[key]}
                              onChange={(e) => setTrades(trades.map((x, j) => (j === i ? { ...x, [key]: e.target.value } : x)))} />
                          </label>
                        ))}
                      </div>
                      <button type="button" className="btn btn-danger-ghost" style={{ marginTop: 6, fontSize: 12 }}
                        onClick={() => setTrades(trades.filter((_, j) => j !== i))}>
                        Remove trade
                      </button>
                    </div>
                  ))}
                  <button type="button" className="btn btn-ghost" style={{ fontSize: 12 }}
                    onClick={() => setTrades([...trades, { ...EMPTY_TRADE }])}>
                    + Add trade-in
                  </button>

                  <div style={{ display: "flex", gap: 8, marginTop: 20 }}>
                    <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={step === "saving"}>
                      {step === "saving" ? "Saving…" : "Save Deal"}
                    </button>
                    <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={resetFlow} disabled={step === "saving"}>
                      Cancel
                    </button>
                  </div>
                </form>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── detail view ─────────────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "" || value === "—") return null;
  return (
    <div style={{ fontSize: 13 }}>
      <span style={{ color: "#64748b" }}>{label}: </span>
      <span style={{ color: "#0f172a" }}>{value}</span>
    </div>
  );
}

function DealDetailView({ detail }: { detail: DealDetail }) {
  const d = detail as Record<string, string | null>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 32 }}>
      <div style={{ minWidth: 220 }}>
        <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Vehicle</h4>
        <DetailRow label="VIN" value={d.vin} />
        <DetailRow label="Model Code" value={d.model_code} />
        <DetailRow label="Stock #" value={d.stock_number} />
        <DetailRow label="Condition" value={d.condition} />
        <DetailRow label="Odometer" value={d.odometer_at_deal} />
        <DetailRow label="Color" value={d.exterior_color} />
        <DetailRow label="Engine" value={d.engine} />
        <DetailRow label="Drivetrain" value={d.drivetrain} />
      </div>
      <div style={{ minWidth: 220 }}>
        <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Money</h4>
        <DetailRow label="Base Price" value={fmtMoney(d.base_price)} />
        <DetailRow label="Selling Price" value={fmtMoney(d.selling_price)} />
        <DetailRow label="Discount" value={fmtMoney(d.discount)} />
        <DetailRow label="Fees" value={fmtMoney(d.fees_total)} />
        <DetailRow label="Tax" value={fmtMoney(d.tax_total)} />
        <DetailRow label="Capital Cost" value={fmtMoney(d.capital_cost)} />
        <DetailRow label="Total Incl. Tax" value={fmtMoney(d.total_with_tax)} />
        <DetailRow label="Cash Down" value={fmtMoney(d.cash_down)} />
        <DetailRow label="Trade Equity" value={fmtMoney(d.trade_equity)} />
      </div>
      <div style={{ minWidth: 220 }}>
        <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Terms</h4>
        <DetailRow label="Lender" value={d.lender} />
        <DetailRow label="Rate" value={d.rate_pct !== null && d.rate_pct !== undefined ? `${Number(d.rate_pct)}%` : null} />
        <DetailRow label="Term" value={d.term ? String(d.term) : null} />
        <DetailRow label="Payments" value={d.num_payments ? `${d.num_payments} × ${fmtMoney(d.payment_amount)} ${d.payment_frequency ?? ""}` : null} />
        {detail.deal_type === "lease" && (
          <>
            <DetailRow label="Residual" value={d.residual_value ? `${fmtMoney(d.residual_value)} (${Number(d.residual_pct ?? 0)}%)` : null} />
            <DetailRow label="Buy Option" value={fmtMoney(d.buy_option_price)} />
            <DetailRow label="KM/yr" value={d.km_per_year} />
            <DetailRow label="Excess KM" value={d.excess_km_rate ? `$${d.excess_km_rate}/km` : null} />
          </>
        )}
        <DetailRow label="Rep" value={d.rep_name_raw} />
        <DetailRow label="Dealership" value={d.dealership} />
        {detail.source_image_path && (
          <button className="btn btn-ghost" style={{ marginTop: 8, fontSize: 12 }}
            onClick={() => openDealImage(detail.id).catch(() => alert("Image not available"))}>
            📷 View source photo
          </button>
        )}
      </div>
      {detail.line_items.length > 0 && (
        <div style={{ minWidth: 260 }}>
          <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Fees & Discounts</h4>
          {detail.line_items.map((li) => (
            <div key={li.id} style={{ fontSize: 13, display: "flex", justifyContent: "space-between", gap: 16 }}>
              <span style={{ color: Number(li.amount) < 0 ? "#16a34a" : "#0f172a" }}>{li.item_name}</span>
              <span>{fmtMoney(li.amount)}</span>
            </div>
          ))}
        </div>
      )}
      {detail.trades.length > 0 && (
        <div style={{ minWidth: 260 }}>
          <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Trade-In</h4>
          {detail.trades.map((tr) => (
            <div key={tr.id} style={{ fontSize: 13 }}>
              {[tr.model_year, tr.make, tr.model, tr.trim_base].filter(Boolean).join(" ")}
              {tr.vin ? ` · ${tr.vin}` : ""}
              {tr.mileage ? ` · ${tr.mileage.toLocaleString()} km` : ""}
              <div style={{ color: "#64748b" }}>
                Allocation {fmtMoney(tr.allocation)}
                {tr.lien_payout && Number(tr.lien_payout) !== 0 ? ` − lien ${fmtMoney(tr.lien_payout)}` : ""}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
