"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getTenantCode, login, setTenantCode } from "@/lib/api";

const ACCOUNTS = [
  ["admin@obe.vn", "admin123", "Admin"],
  ["manager@obe.vn", "manager123", "Trưởng khoa"],
  ["lecturer@obe.vn", "lecturer123", "Giảng viên"],
  ["qa@obe.vn", "qa123", "ĐBCL"],
];

export default function LoginPage() {
  const [email, setEmail] = useState("manager@obe.vn");
  const [password, setPassword] = useState("manager123");
  const [err, setErr] = useState("");
  const [tenant, setTenant] = useState<string | null>(null);
  const router = useRouter();

  // Đọc ?tenant=<mã> (ghi nhớ) để đăng nhập đúng trường con khi chưa có subdomain thật.
  useEffect(() => setTenant(getTenantCode()), []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await login(email, password);
      router.push("/programs");
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="mx-auto mt-10 max-w-md">
      <div className="mb-6 flex flex-col items-center text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-500 text-lg font-bold text-white shadow-soft">
          OB
        </span>
        <h1 className="mt-3">Đăng nhập EduOBE</h1>
        <p className="mt-1 text-sm text-slate-500">Nền tảng OBE / AUN-QA</p>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-soft">
        {tenant ? (
          <div className="mb-4 flex items-center justify-between gap-2 rounded-lg border border-indigo-200 bg-indigo-50 p-2.5 text-xs text-indigo-800">
            <span>Đăng nhập vào trường: <b>{tenant}</b></span>
            <button
              onClick={() => { setTenantCode(null); setTenant(null); }}
              className="shrink-0 rounded bg-white px-2 py-0.5 underline hover:bg-indigo-100"
            >
              Bỏ chọn
            </button>
          </div>
        ) : (
          <p className="mb-4 text-xs text-slate-400">
            Mẹo: thêm <code className="rounded bg-slate-100 px-1">?tenant=&lt;mã&gt;</code> vào URL để vào đúng trường con.
          </p>
        )}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
            <input
              className="w-full"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email@truong.edu.vn"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Mật khẩu</label>
            <input
              className="w-full"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {err && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-2 text-sm text-red-600">{err}</p>
          )}
          <button className="btn btn-primary w-full">Đăng nhập</button>
        </form>
        <div className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-500">
          <p className="mb-2 font-semibold text-slate-600">Tài khoản mẫu (bấm để điền):</p>
          <div className="flex flex-wrap gap-2">
            {ACCOUNTS.map(([e, p, label]) => (
              <button
                key={e}
                type="button"
                onClick={() => { setEmail(e); setPassword(p); }}
                className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 hover:bg-slate-100"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
