"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";

export default function ProgramsPage() {
  const [programs, setPrograms] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ name: "", code: "" });
  const router = useRouter();

  async function load() {
    try {
      setPrograms(await api("/api/programs"));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      await api("/api/programs", { method: "POST", body: JSON.stringify(form) });
      setForm({ name: "", code: "" });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function remove(p: any) {
    if (!confirm(`Xóa chương trình "${p.name || p.code || "(không tên)"}"?\n` +
                 `Chương trình sẽ bị gỡ khỏi danh sách (cùng học phần/đề cương liên quan).`)) {
      return;
    }
    setErr("");
    try {
      await api(`/api/programs/${p.id}`, { method: "DELETE" });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Chương trình đào tạo</h1>
      {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
      <form onSubmit={create} className="mt-4 flex gap-2">
        <input
          className="rounded border p-2"
          placeholder="Tên CTĐT"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <input
          className="rounded border p-2"
          placeholder="Mã"
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value })}
        />
        <button className="rounded bg-indigo-600 px-4 text-white">Thêm</button>
      </form>
      <ul className="mt-6 space-y-2">
        {programs.map((p) => (
          <li key={p.id} className="flex items-center justify-between gap-3 rounded border bg-white p-4 shadow-sm">
            <div>
              <Link href={`/programs/${p.id}`} className="font-semibold text-indigo-700">
                {p.name || "(chưa đặt tên)"} <span className="text-slate-400">({p.code})</span>
              </Link>
              <span className="ml-2 text-sm text-slate-500">
                {p.level} {p.year ? `· ${p.year}` : ""} {p.faculty ? `· ${p.faculty}` : ""}
              </span>
            </div>
            <button
              onClick={() => remove(p)}
              className="shrink-0 rounded bg-red-100 px-3 py-1.5 text-sm text-red-700 hover:bg-red-200"
            >
              Xóa
            </button>
          </li>
        ))}
        {programs.length === 0 && <p className="text-slate-500">Chưa có CTĐT.</p>}
      </ul>
    </div>
  );
}
