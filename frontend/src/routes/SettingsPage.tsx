import { useState, useEffect, FormEvent } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";

type Tab = "account" | "users" | "llm";

interface UserItem {
  id: number;
  email: string;
  name: string;
  role: string;
  must_change_password: boolean;
  created_at: string;
}

interface LLMProfile {
  id: number;
  name: string;
  base_url: string;
  api_key_masked: string;
  model: string;
  is_active: boolean;
  is_local: boolean;
  created_at: string;
}

interface ProfileForm {
  name: string;
  base_url: string;
  api_key: string;
  model: string;
  is_local: boolean;
}

interface TestResult {
  ok: boolean;
  message: string;
  response_ms: number | null;
}

interface NewUserForm {
  email: string;
  name: string;
  role: string;
  password: string;
}

const EMPTY_NEW_USER: NewUserForm = { email: "", name: "", role: "sales", password: "" };
const EMPTY_PROFILE_FORM: ProfileForm = { name: "", base_url: "", api_key: "", model: "", is_local: false };

export default function SettingsPage() {
  const { role, mustChangePassword, updateMustChange } = useAuth();
  const isManager = role === "manager";
  const [tab, setTab] = useState<Tab>("account");

  // Account tab
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState(false);
  const [pwdLoading, setPwdLoading] = useState(false);

  // Users tab
  const [users, setUsers] = useState<UserItem[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState<NewUserForm>(EMPTY_NEW_USER);
  const [addUserError, setAddUserError] = useState<string | null>(null);
  const [addUserLoading, setAddUserLoading] = useState(false);

  // LLM tab
  const [profiles, setProfiles] = useState<LLMProfile[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);
  const [addTestResult, setAddTestResult] = useState<TestResult | null>(null);
  const [addTesting, setAddTesting] = useState(false);

  // Per-profile edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [editError, setEditError] = useState<string | null>(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editTestResult, setEditTestResult] = useState<TestResult | null>(null);
  const [editTesting, setEditTesting] = useState(false);

  // Per-profile test result (for list-card test buttons)
  const [cardTestResults, setCardTestResults] = useState<Record<number, TestResult>>({});
  const [cardTesting, setCardTesting] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (tab === "users" && isManager) loadUsers();
    if (tab === "llm") loadProfiles();
  }, [tab]);

  async function loadUsers() {
    setUsersLoading(true);
    try {
      const data = await api.get<UserItem[]>("/settings/users");
      setUsers(data);
    } catch {
      // table stays empty
    } finally {
      setUsersLoading(false);
    }
  }

  async function loadProfiles() {
    setProfilesLoading(true);
    try {
      const data = await api.get<LLMProfile[]>("/settings/llm/profiles");
      setProfiles(data);
    } catch {
      // list stays empty
    } finally {
      setProfilesLoading(false);
    }
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwdError(null);
    setPwdSuccess(false);
    if (newPwd !== confirmPwd) {
      setPwdError("Passwords do not match");
      return;
    }
    setPwdLoading(true);
    try {
      await api.post("/settings/change-password", {
        current_password: currentPwd,
        new_password: newPwd,
      });
      setPwdSuccess(true);
      setCurrentPwd("");
      setNewPwd("");
      setConfirmPwd("");
      updateMustChange(false);
    } catch (err) {
      setPwdError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setPwdLoading(false);
    }
  }

  async function handleAddUser(e: FormEvent) {
    e.preventDefault();
    setAddUserError(null);
    setAddUserLoading(true);
    try {
      await api.post("/settings/users", newUser);
      setNewUser(EMPTY_NEW_USER);
      setShowAddUser(false);
      await loadUsers();
    } catch (err) {
      setAddUserError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setAddUserLoading(false);
    }
  }

  async function handleAddProfile(e: FormEvent) {
    e.preventDefault();
    setAddError(null);
    setAddLoading(true);
    try {
      await api.post("/settings/llm/profiles", addForm);
      setAddForm(EMPTY_PROFILE_FORM);
      setShowAddForm(false);
      setAddTestResult(null);
      await loadProfiles();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to create profile");
    } finally {
      setAddLoading(false);
    }
  }

  async function handleTestInline(form: ProfileForm, setResult: (r: TestResult | null) => void, setLoading: (b: boolean) => void) {
    setResult(null);
    setLoading(true);
    try {
      const result = await api.post<TestResult>("/settings/llm/test", {
        base_url: form.base_url,
        api_key: form.api_key,
        model: form.model,
        is_local: form.is_local,
      });
      setResult(result);
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Request failed", response_ms: null });
    } finally {
      setLoading(false);
    }
  }

  async function handleTestProfile(profileId: number) {
    setCardTesting((prev) => ({ ...prev, [profileId]: true }));
    setCardTestResults((prev) => { const n = { ...prev }; delete n[profileId]; return n; });
    try {
      const result = await api.post<TestResult>(`/settings/llm/profiles/${profileId}/test`, {});
      setCardTestResults((prev) => ({ ...prev, [profileId]: result }));
    } catch (err) {
      setCardTestResults((prev) => ({
        ...prev,
        [profileId]: { ok: false, message: err instanceof Error ? err.message : "Request failed", response_ms: null },
      }));
    } finally {
      setCardTesting((prev) => ({ ...prev, [profileId]: false }));
    }
  }

  async function handleActivate(profileId: number) {
    try {
      await api.post(`/settings/llm/profiles/${profileId}/activate`, {});
      await loadProfiles();
    } catch {
      // ignore
    }
  }

  async function handleDelete(profileId: number) {
    try {
      await api.delete(`/settings/llm/profiles/${profileId}`);
      if (editingId === profileId) setEditingId(null);
      setCardTestResults((prev) => { const n = { ...prev }; delete n[profileId]; return n; });
      await loadProfiles();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete profile");
    }
  }

  function startEdit(p: LLMProfile) {
    setEditingId(p.id);
    setEditForm({ name: p.name, base_url: p.base_url, api_key: "", model: p.model, is_local: p.is_local });
    setEditError(null);
    setEditTestResult(null);
  }

  async function handleSaveEdit(e: FormEvent, profileId: number) {
    e.preventDefault();
    setEditError(null);
    setEditLoading(true);
    try {
      await api.put(`/settings/llm/profiles/${profileId}`, editForm);
      setEditingId(null);
      setEditTestResult(null);
      await loadProfiles();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setEditLoading(false);
    }
  }

  const tabs: Tab[] = ["account", ...(isManager ? (["users"] as Tab[]) : []), "llm"];

  return (
    <div style={{ padding: "32px 40px", maxWidth: 760 }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--color-text)", marginBottom: 24 }}>
        Settings
      </h2>

      {mustChangePassword && (
        <div className="notice notice-warning" style={{ marginBottom: 20 }}>
          You must change your password before continuing.
        </div>
      )}

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid var(--color-border)",
          marginBottom: 28,
        }}
      >
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 20px",
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? "var(--color-primary)" : "var(--color-text-3)",
              background: "none",
              border: "none",
              borderBottom: tab === t ? "2px solid var(--color-primary)" : "2px solid transparent",
              cursor: "pointer",
              fontSize: 14,
              marginBottom: -1,
            }}
          >
            {t === "llm" ? "LLM" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Account tab */}
      {tab === "account" && (
        <div className="card" style={{ padding: 24, maxWidth: 400 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 20 }}>Change Password</h3>
          <form
            onSubmit={handleChangePassword}
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            <div>
              <label className="form-label">Current Password</label>
              <input
                className="input"
                type="password"
                value={currentPwd}
                onChange={(e) => setCurrentPwd(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>
            <div>
              <label className="form-label">New Password</label>
              <input
                className="input"
                type="password"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
                required
                autoComplete="new-password"
                placeholder="Min 8 characters"
              />
            </div>
            <div>
              <label className="form-label">Confirm New Password</label>
              <input
                className="input"
                type="password"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            {pwdError && <div className="notice notice-danger">{pwdError}</div>}
            {pwdSuccess && (
              <div className="notice notice-success">Password changed successfully.</div>
            )}
            <button
              type="submit"
              disabled={pwdLoading}
              className="btn btn-primary"
              style={{ marginTop: 4 }}
            >
              {pwdLoading ? "Saving…" : "Change Password"}
            </button>
          </form>
        </div>
      )}

      {/* Users tab */}
      {tab === "users" && isManager && (
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 600 }}>Users</h3>
            <button
              className="btn btn-primary"
              style={{ fontSize: 13 }}
              onClick={() => {
                setShowAddUser((v) => !v);
                setAddUserError(null);
              }}
            >
              {showAddUser ? "Cancel" : "+ Add User"}
            </button>
          </div>

          {showAddUser && (
            <form
              onSubmit={handleAddUser}
              className="card"
              style={{ padding: 20, marginBottom: 20, display: "flex", flexDirection: "column", gap: 14 }}
            >
              <h4 style={{ fontSize: 14, fontWeight: 600 }}>New User</h4>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label className="form-label">Name</label>
                  <input
                    className="input"
                    value={newUser.name}
                    onChange={(e) => setNewUser((u) => ({ ...u, name: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Email</label>
                  <input
                    className="input"
                    type="email"
                    value={newUser.email}
                    onChange={(e) => setNewUser((u) => ({ ...u, email: e.target.value }))}
                    required
                  />
                </div>
                <div>
                  <label className="form-label">Role</label>
                  <select
                    className="input"
                    value={newUser.role}
                    onChange={(e) => setNewUser((u) => ({ ...u, role: e.target.value }))}
                  >
                    <option value="sales">Sales</option>
                    <option value="manager">Manager</option>
                  </select>
                </div>
                <div>
                  <label className="form-label">Password</label>
                  <input
                    className="input"
                    type="password"
                    value={newUser.password}
                    onChange={(e) => setNewUser((u) => ({ ...u, password: e.target.value }))}
                    required
                    placeholder="Min 8 characters"
                  />
                </div>
              </div>
              {addUserError && <div className="notice notice-danger">{addUserError}</div>}
              <div>
                <button
                  type="submit"
                  disabled={addUserLoading}
                  className="btn btn-primary"
                  style={{ fontSize: 13 }}
                >
                  {addUserLoading ? "Creating…" : "Create User"}
                </button>
              </div>
            </form>
          )}

          {usersLoading ? (
            <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>Loading…</p>
          ) : (
            <div className="card" style={{ overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                    {["Name", "Email", "Role", "Status"].map((h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: "left",
                          padding: "10px 16px",
                          fontWeight: 600,
                          color: "var(--color-text-3)",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                      <td style={{ padding: "10px 16px" }}>{u.name}</td>
                      <td style={{ padding: "10px 16px", color: "var(--color-text-3)" }}>
                        {u.email}
                      </td>
                      <td style={{ padding: "10px 16px" }}>
                        <span
                          className={`badge ${u.role === "manager" ? "badge-warning" : "badge-muted"}`}
                          style={{ textTransform: "capitalize" }}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td style={{ padding: "10px 16px" }}>
                        {u.must_change_password && (
                          <span className="badge badge-warning">Must change pw</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td
                        colSpan={4}
                        style={{
                          padding: "20px 16px",
                          color: "var(--color-text-3)",
                          textAlign: "center",
                        }}
                      >
                        No users found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* LLM tab */}
      {tab === "llm" && (
        <div style={{ maxWidth: 560 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 2 }}>LLM Profiles</h3>
              <p style={{ fontSize: 13, color: "var(--color-text-3)" }}>
                These settings apply to your account only. One profile is active at a time.
              </p>
            </div>
            <button
              className="btn btn-primary"
              style={{ fontSize: 13, whiteSpace: "nowrap" }}
              onClick={() => {
                setShowAddForm((v) => !v);
                setAddError(null);
                setAddTestResult(null);
                setAddForm(EMPTY_PROFILE_FORM);
              }}
            >
              {showAddForm ? "Cancel" : "+ Add Profile"}
            </button>
          </div>

          {/* Add profile form */}
          {showAddForm && (
            <form
              onSubmit={handleAddProfile}
              className="card"
              style={{ padding: 20, marginBottom: 16, display: "flex", flexDirection: "column", gap: 12 }}
            >
              <h4 style={{ fontSize: 13, fontWeight: 600 }}>New Profile</h4>
              <div>
                <label className="form-label">Name</label>
                <input
                  className="input"
                  value={addForm.name}
                  onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                  required
                  placeholder="e.g. OpenAI GPT-4"
                />
              </div>
              <div>
                <label className="form-label">Base URL</label>
                <input
                  className="input"
                  value={addForm.base_url}
                  onChange={(e) => setAddForm((f) => ({ ...f, base_url: e.target.value }))}
                  required
                  placeholder={addForm.is_local ? "http://127.0.0.1:8080/v1" : "https://api.openai.com/v1"}
                />
                <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, cursor: "pointer", fontSize: 13, color: "var(--color-text-3)" }}>
                  <input
                    type="checkbox"
                    checked={addForm.is_local}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setAddForm((f) => ({
                        ...f,
                        is_local: checked,
                        base_url: checked && !f.base_url ? "http://127.0.0.1:8080/v1" : f.base_url,
                        api_key: checked && !f.api_key ? "no-key-needed" : f.api_key,
                      }));
                    }}
                  />
                  Local server
                </label>
              </div>
              <div>
                <label className="form-label">API Key</label>
                <input
                  className="input"
                  type="password"
                  value={addForm.api_key}
                  onChange={(e) => setAddForm((f) => ({ ...f, api_key: e.target.value }))}
                  required
                  autoComplete="off"
                  placeholder={addForm.is_local ? "no-key-needed" : "sk-..."}
                />
              </div>
              <div>
                <label className="form-label">Model</label>
                <input
                  className="input"
                  value={addForm.model}
                  onChange={(e) => setAddForm((f) => ({ ...f, model: e.target.value }))}
                  required
                  placeholder="gpt-4o"
                />
              </div>
              {addError && <div className="notice notice-danger">{addError}</div>}
              {addTestResult && (
                <div className={`notice ${addTestResult.ok ? "notice-success" : "notice-danger"}`}>
                  {addTestResult.ok
                    ? `Connected (${addTestResult.response_ms}ms)`
                    : addTestResult.message}
                </div>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  disabled={addTesting || !addForm.base_url || !addForm.api_key || !addForm.model}
                  className="btn"
                  style={{ fontSize: 13 }}
                  onClick={() => handleTestInline(addForm, setAddTestResult, setAddTesting)}
                >
                  {addTesting ? "Testing…" : "Test Connection"}
                </button>
                <button
                  type="submit"
                  disabled={addLoading}
                  className="btn btn-primary"
                  style={{ fontSize: 13 }}
                >
                  {addLoading ? "Saving…" : "Save Profile"}
                </button>
              </div>
            </form>
          )}

          {/* Profile list */}
          {profilesLoading ? (
            <p style={{ color: "var(--color-text-3)", fontSize: 13 }}>Loading…</p>
          ) : profiles.length === 0 ? (
            <div className="card" style={{ padding: 24, textAlign: "center", color: "var(--color-text-3)", fontSize: 13 }}>
              No profiles yet. Add one to configure LLM access.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {profiles.map((p) => (
                <div key={p.id} className="card" style={{ padding: 0, overflow: "hidden" }}>
                  {/* Card header */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "14px 16px",
                      borderBottom: editingId === p.id ? "1px solid var(--color-border)" : "none",
                    }}
                  >
                    <span style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>{p.name}</span>
                    {p.is_local && (
                      <span className="badge badge-muted" style={{ fontSize: 11 }}>Local</span>
                    )}
                    {p.is_active && (
                      <span className="badge badge-success" style={{ fontSize: 11 }}>Active</span>
                    )}
                    {!p.is_active && (
                      <button
                        className="btn"
                        style={{ fontSize: 12, padding: "3px 10px" }}
                        onClick={() => handleActivate(p.id)}
                      >
                        Set Active
                      </button>
                    )}
                    <button
                      className="btn"
                      style={{ fontSize: 12, padding: "3px 10px" }}
                      disabled={cardTesting[p.id]}
                      onClick={() => handleTestProfile(p.id)}
                    >
                      {cardTesting[p.id] ? "Testing…" : "Test"}
                    </button>
                    <button
                      className="btn"
                      style={{ fontSize: 12, padding: "3px 10px" }}
                      onClick={() => {
                        if (editingId === p.id) {
                          setEditingId(null);
                        } else {
                          startEdit(p);
                        }
                      }}
                    >
                      {editingId === p.id ? "Cancel" : "Edit"}
                    </button>
                    {profiles.length > 1 && (
                      <button
                        className="btn btn-danger-ghost"
                        style={{ fontSize: 12, padding: "3px 10px" }}
                        onClick={() => {
                          if (confirm(`Delete profile "${p.name}"?`)) handleDelete(p.id);
                        }}
                      >
                        Delete
                      </button>
                    )}
                  </div>

                  {/* Subtitle row */}
                  {editingId !== p.id && (
                    <div style={{ padding: "6px 16px 12px", fontSize: 12, color: "var(--color-text-3)" }}>
                      {p.base_url} · {p.model} · key: {p.api_key_masked}
                      {cardTestResults[p.id] && (
                        <span
                          style={{
                            marginLeft: 12,
                            color: cardTestResults[p.id].ok ? "var(--color-success)" : "var(--color-danger)",
                          }}
                        >
                          {cardTestResults[p.id].ok
                            ? `Connected (${cardTestResults[p.id].response_ms}ms)`
                            : cardTestResults[p.id].message}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Inline edit form */}
                  {editingId === p.id && (
                    <form
                      onSubmit={(e) => handleSaveEdit(e, p.id)}
                      style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}
                    >
                      <div>
                        <label className="form-label">Name</label>
                        <input
                          className="input"
                          value={editForm.name}
                          onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                          required
                        />
                      </div>
                      <div>
                        <label className="form-label">Base URL</label>
                        <input
                          className="input"
                          value={editForm.base_url}
                          onChange={(e) => setEditForm((f) => ({ ...f, base_url: e.target.value }))}
                          required
                        />
                        <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6, cursor: "pointer", fontSize: 13, color: "var(--color-text-3)" }}>
                          <input
                            type="checkbox"
                            checked={editForm.is_local}
                            onChange={(e) => setEditForm((f) => ({ ...f, is_local: e.target.checked }))}
                          />
                          Local server
                        </label>
                      </div>
                      <div>
                        <label className="form-label">API Key</label>
                        <input
                          className="input"
                          type="password"
                          value={editForm.api_key}
                          onChange={(e) => setEditForm((f) => ({ ...f, api_key: e.target.value }))}
                          autoComplete="off"
                          placeholder={`Current: ${p.api_key_masked} — leave blank to keep`}
                        />
                      </div>
                      <div>
                        <label className="form-label">Model</label>
                        <input
                          className="input"
                          value={editForm.model}
                          onChange={(e) => setEditForm((f) => ({ ...f, model: e.target.value }))}
                          required
                        />
                      </div>
                      {editError && <div className="notice notice-danger">{editError}</div>}
                      {editTestResult && (
                        <div className={`notice ${editTestResult.ok ? "notice-success" : "notice-danger"}`}>
                          {editTestResult.ok
                            ? `Connected (${editTestResult.response_ms}ms)`
                            : editTestResult.message}
                        </div>
                      )}
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          type="button"
                          disabled={editTesting || !editForm.base_url || !editForm.model}
                          className="btn"
                          style={{ fontSize: 13 }}
                          onClick={() => {
                            const form = { ...editForm, api_key: editForm.api_key || p.api_key_masked };
                            handleTestInline(form, setEditTestResult, setEditTesting);
                          }}
                        >
                          {editTesting ? "Testing…" : "Test Connection"}
                        </button>
                        <button
                          type="submit"
                          disabled={editLoading}
                          className="btn btn-primary"
                          style={{ fontSize: 13 }}
                        >
                          {editLoading ? "Saving…" : "Save"}
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
