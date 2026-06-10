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

interface LLMConfig {
  base_url: string;
  api_key_masked: string;
  model: string;
}

interface NewUserForm {
  email: string;
  name: string;
  role: string;
  password: string;
}

const EMPTY_NEW_USER: NewUserForm = { email: "", name: "", role: "sales", password: "" };

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
  const [llmConfig, setLLMConfig] = useState<LLMConfig | null>(null);
  const [llmForm, setLLMForm] = useState({ base_url: "", api_key: "", model: "" });
  const [llmLoading, setLLMLoading] = useState(false);
  const [llmError, setLLMError] = useState<string | null>(null);
  const [llmSuccess, setLLMSuccess] = useState(false);

  useEffect(() => {
    if (tab === "users" && isManager) loadUsers();
    if (tab === "llm") loadLLMConfig();
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

  async function loadLLMConfig() {
    try {
      const data = await api.get<LLMConfig>("/settings/llm");
      setLLMConfig(data);
      setLLMForm({ base_url: data.base_url, api_key: "", model: data.model });
    } catch {
      // form stays blank
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

  async function handleSaveLLM(e: FormEvent) {
    e.preventDefault();
    setLLMError(null);
    setLLMSuccess(false);
    setLLMLoading(true);
    try {
      await api.put("/settings/llm", llmForm);
      setLLMSuccess(true);
      setLLMForm((f) => ({ ...f, api_key: "" }));
      await loadLLMConfig();
    } catch (err) {
      setLLMError(err instanceof Error ? err.message : "Failed to update LLM settings");
    } finally {
      setLLMLoading(false);
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
        <div className="card" style={{ padding: 24, maxWidth: 480 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>LLM Configuration</h3>
          <p style={{ fontSize: 13, color: "var(--color-text-3)", marginBottom: 20 }}>
            These settings apply to your account only.
          </p>
          <form
            onSubmit={handleSaveLLM}
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            <div>
              <label className="form-label">Base URL</label>
              <input
                className="input"
                value={llmForm.base_url}
                onChange={(e) => setLLMForm((f) => ({ ...f, base_url: e.target.value }))}
                required
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <label className="form-label">API Key</label>
              <input
                className="input"
                type="password"
                value={llmForm.api_key}
                onChange={(e) => setLLMForm((f) => ({ ...f, api_key: e.target.value }))}
                autoComplete="off"
                placeholder={
                  llmConfig
                    ? `Current: ${llmConfig.api_key_masked} — leave blank to keep`
                    : "Enter API key"
                }
              />
            </div>
            <div>
              <label className="form-label">Model</label>
              <input
                className="input"
                value={llmForm.model}
                onChange={(e) => setLLMForm((f) => ({ ...f, model: e.target.value }))}
                required
                placeholder="gpt-4o"
              />
            </div>
            {llmError && <div className="notice notice-danger">{llmError}</div>}
            {llmSuccess && (
              <div className="notice notice-success">LLM settings updated.</div>
            )}
            <button
              type="submit"
              disabled={llmLoading}
              className="btn btn-primary"
              style={{ marginTop: 4 }}
            >
              {llmLoading ? "Saving…" : "Save LLM Settings"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
