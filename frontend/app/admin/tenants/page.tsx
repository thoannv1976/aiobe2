"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken, getUser } from "@/lib/api";

interface Tenant {
  id: number;
  code: string;
  name: string;
  status: string;
  is_enabled: boolean;
  valid_until: string | null;
  contact_email: string | null;
}

const empty = { code: "", name: "", contact_email: "", admin_email: "", admin_password: "", valid_days: 365 };

function daysLeft(valid_until: string | null): number | null {
  if (!valid_until) return null;
  return Math.ceil((new Date(valid_until).getTime() - Date.now()) / 86400000);
}

export default function AdminTenantsPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [form, setForm] = useState({ ...empty });
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    setErr("");
    try {
      setTenants(await api("/api/tenants"));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    if (getUser()?.role !== "super_admin") {
      setErr("Chỉ Super-Admin nền tảng mới được truy cập trang này.");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    try {
      await api("/api/tenants", { method: "POST", body: JSON.stringify(form) });
      setMsg(`Đã tạo trường "${form.name}" (${form.code}.eduobe.vn) + tài khoản admin.`);
      setForm({ ...empty });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function enable(t: Tenant) {
    setErr("");
    try {
      await api(`/api/tenants/${t.id}/enable`, { method: "POST", body: JSON.stringify({ valid_days: 365 }) });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function suspend(t: Tenant) {
    if (!confirm(`Tạm ngừng trường "${t.name}"? Người dùng của trường sẽ không truy cập được.`)) return;
    setErr("");
    try {
      await api(`/api/tenants/${t.id}/suspend`, { method: "POST" });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Quản trị nền tảng — Trường (tenant)</h1>
        <Link href="/admin" className="text-sm text-indigo-600 hover:underline">← Về Quản trị</Link>
      </div>
      {err && <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</p>}
      {msg && <p className="rounded border border-green-300 bg-green-50 p-3 text-sm text-green-700">{msg}</p>}

      {/* Tạo trường mới */}
      <form onSubmit={create} className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Cấp phát trường mới</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Mã (subdomain)
            <input required value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
              placeholder="vd: neu" className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm">Tên trường
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm">Email liên hệ
            <input value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm">Email admin trường
            <input required type="email" value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm">Mật khẩu admin
            <input required value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm">Số ngày sử dụng
            <input type="number" value={form.valid_days} onChange={(e) => setForm({ ...form, valid_days: Number(e.target.value) || 365 })}
              className="mt-1 block w-full rounded border p-2" />
          </label>
        </div>
        <button className="mt-3 rounded bg-indigo-600 px-4 py-2 text-sm text-white">Tạo trường</button>
      </form>

      {/* Danh sách trường */}
      <div className="overflow-x-auto rounded border bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-slate-100">
              <th className="p-2 text-center">STT</th>
              <th className="p-2 text-left">Trường</th>
              <th className="p-2">Subdomain</th>
              <th className="p-2">Trạng thái</th>
              <th className="p-2">Hết hạn</th>
              <th className="p-2">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t, i) => {
              const dl = daysLeft(t.valid_until);
              const expired = dl != null && dl < 0;
              return (
                <tr key={t.id} className="border-t">
                  <td className="p-2 text-center text-slate-500">{i + 1}</td>
                  <td className="p-2">{t.name} {t.contact_email && <span className="text-xs text-slate-400">· {t.contact_email}</span>}</td>
                  <td className="p-2 text-center">{t.code}.eduobe.vn</td>
                  <td className="p-2 text-center">
                    <span className={`rounded px-2 py-0.5 text-xs ${
                      t.is_enabled && !expired ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {t.is_enabled && !expired ? "Đang hoạt động" : (expired ? "Hết hạn" : "Tạm ngừng")}
                    </span>
                  </td>
                  <td className="p-2 text-center text-xs">
                    {t.valid_until ? t.valid_until.slice(0, 10) : "—"}
                    {dl != null && <span className={dl < 30 ? "ml-1 text-red-600" : "ml-1 text-slate-400"}>({dl} ngày)</span>}
                  </td>
                  <td className="p-2 text-center whitespace-nowrap">
                    <button onClick={() => enable(t)} className="mr-2 rounded bg-green-600 px-2 py-1 text-xs text-white">
                      Gia hạn 365 ngày
                    </button>
                    {t.is_enabled && (
                      <button onClick={() => suspend(t)} className="rounded bg-red-100 px-2 py-1 text-xs text-red-700">
                        Tạm ngừng
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {tenants.length === 0 && (
              <tr><td colSpan={6} className="p-3 text-center text-slate-500">Chưa có trường nào.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
