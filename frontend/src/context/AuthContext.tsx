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
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({
    token: sessionStorage.getItem("crm_token"),
    role: sessionStorage.getItem("crm_role"),
    mustChangePassword: false,
  });

  async function login(email: string, password: string) {
    const res = await api.post<{ access_token: string; role: string; must_change_password: boolean }>(
      "/auth/login",
      { email, password }
    );
    sessionStorage.setItem("crm_token", res.access_token);
    sessionStorage.setItem("crm_role", res.role);
    setAuth({ token: res.access_token, role: res.role, mustChangePassword: res.must_change_password });
  }

  function logout() {
    sessionStorage.removeItem("crm_token");
    sessionStorage.removeItem("crm_role");
    setAuth({ token: null, role: null, mustChangePassword: false });
  }

  return <AuthContext.Provider value={{ ...auth, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
