const BASE = "/api";

async function request<T>(path: string, init?: RequestInit, json = true): Promise<T> {
  const token = sessionStorage.getItem("crm_token");
  const headers: Record<string, string> = {
    // FormData bodies must omit Content-Type so the browser sets the multipart boundary
    ...(json ? { "Content-Type": "application/json" } : {}),
    ...(init?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = error.detail;
    const message = Array.isArray(detail)
      ? detail.map((e: { msg: string }) => e.msg).join(", ")
      : (detail ?? "Request failed");
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  get: <T>(path: string) => request<T>(path),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }, false),
};
