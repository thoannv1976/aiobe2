// Client API gọi backend FastAPI. Token lưu localStorage.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("obe_token");
}

export function setToken(t: string) {
  localStorage.setItem("obe_token", t);
}

export function clearToken() {
  localStorage.removeItem("obe_token");
  localStorage.removeItem("obe_user");
}

export function getUser(): any | null {
  if (typeof window === "undefined") return null;
  const u = localStorage.getItem("obe_user");
  return u ? JSON.parse(u) : null;
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail: any = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export async function api(path: string, opts: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  return handle(res);
}

// Upload multipart/form-data: KHÔNG set Content-Type để browser tự thêm boundary.
export async function apiUpload(path: string, formData: FormData) {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });
  return handle(res);
}

export async function login(email: string, password: string) {  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const data = await handle(res);
  setToken(data.access_token);
  localStorage.setItem("obe_user", JSON.stringify(data.user));
  return data;
}
