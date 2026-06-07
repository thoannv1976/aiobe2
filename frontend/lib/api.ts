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

// Mã trường (tenant) để gửi header X-Tenant — cho phép test trường con không cần subdomain thật.
// Ưu tiên ?tenant=<mã> trên URL (ghi nhớ vào localStorage); ?tenant= rỗng để bỏ chọn.
export function getTenantCode(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.has("tenant")) {
      const q = (params.get("tenant") || "").trim().toLowerCase();
      if (q) localStorage.setItem("obe_tenant", q);
      else localStorage.removeItem("obe_tenant");
    }
    return localStorage.getItem("obe_tenant");
  } catch {
    return null;
  }
}

export function setTenantCode(code: string | null) {
  if (typeof window === "undefined") return;
  if (code) localStorage.setItem("obe_tenant", code.trim().toLowerCase());
  else localStorage.removeItem("obe_tenant");
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  const tenant = getTenantCode();
  if (tenant) h["X-Tenant"] = tenant;
  return h;
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

async function safeFetch(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (e: any) {
    // Lỗi mạng (CORS / sai URL API / backend down) → nêu rõ URL để dễ chẩn đoán.
    throw new Error(`Không kết nối được API (${url}). Kiểm tra NEXT_PUBLIC_API_BASE / CORS. [${e?.message || "network error"}]`);
  }
}

export async function api(path: string, opts: RequestInit = {}) {
  const headers = authHeaders({
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  });
  const res = await safeFetch(`${API_BASE}${path}`, { ...opts, headers });
  return handle(res);
}

// GET có phân trang: trả {items, total} (đọc tổng từ header X-Total-Count).
export async function apiPaged<T = any>(
  path: string,
): Promise<{ items: T[]; total: number }> {
  const res = await safeFetch(`${API_BASE}${path}`, { headers: authHeaders() });
  const items = await handle(res);
  const total = Number(res.headers.get("X-Total-Count") ?? (Array.isArray(items) ? items.length : 0));
  return { items, total };
}

// Upload multipart/form-data: KHÔNG set Content-Type để browser tự thêm boundary.
export async function apiUpload(path: string, formData: FormData) {
  const res = await safeFetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return handle(res);
}

export async function login(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const tenant = getTenantCode();
  const headers: Record<string, string> = { "Content-Type": "application/x-www-form-urlencoded" };
  if (tenant) headers["X-Tenant"] = tenant;
  const res = await safeFetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers,
    body,
  });
  const data = await handle(res);
  setToken(data.access_token);
  localStorage.setItem("obe_user", JSON.stringify(data.user));
  return data;
}
