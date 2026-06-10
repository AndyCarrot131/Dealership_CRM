import { createContext, useContext, useState, ReactNode } from "react";
import { api } from "../api/client";

interface AuthState {
  token: string | null;
  role: string | null;
  mustChangePassword: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  updateMustChange: (val: boolean) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({
    token: sessionStorage.getItem("crm_token"),
    role: sessionStorage.getItem("crm_role"),
    mustChangePassword: sessionStorage.getItem("crm_must_change") === "1",
  });

  async function login(email: string, password: string) {
    const res = await api.post<{ access_token: string; role: string; must_change_password: boolean }>(
      "/auth/login",
      { email, password }
    );
    sessionStorage.setItem("crm_token", res.access_token);
    sessionStorage.setItem("crm_role", res.role);
    sessionStorage.setItem("crm_must_change", res.must_change_password ? "1" : "0");
    setAuth({ token: res.access_token, role: res.role, mustChangePassword: res.must_change_password });
  }

  function logout() {
    sessionStorage.removeItem("crm_token");
    sessionStorage.removeItem("crm_role");
    sessionStorage.removeItem("crm_must_change");
    setAuth({ token: null, role: null, mustChangePassword: false });
  }

  function updateMustChange(val: boolean) {
    sessionStorage.setItem("crm_must_change", val ? "1" : "0");
    setAuth((prev) => ({ ...prev, mustChangePassword: val }));
  }

  return (
    <AuthContext.Provider value={{ ...auth, login, logout, updateMustChange }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
