"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

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
  const router = useRouter();

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
    <div className="mx-auto mt-10 max-w-md rounded-lg border bg-white p-8 shadow-sm">
      <h1 className="mb-6 text-2xl font-bold">Đăng nhập</h1>
      <form onSubmit={submit} className="space-y-4">
        <input
          className="w-full rounded border p-2"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email"
        />
        <input
          className="w-full rounded border p-2"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Mật khẩu"
        />
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button className="w-full rounded bg-indigo-600 p-2 text-white">Đăng nhập</button>
      </form>
      <div className="mt-6 text-xs text-slate-500">
        <p className="mb-1 font-semibold">Tài khoản mẫu (bấm để điền):</p>
        {ACCOUNTS.map(([e, p, label]) => (
          <button
            key={e}
            onClick={() => {
              setEmail(e);
              setPassword(p);
            }}
            className="mr-2 mb-1 rounded bg-slate-100 px-2 py-1 hover:bg-slate-200"
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
