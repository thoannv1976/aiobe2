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
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1>Chương trình đào tạo</h1>
          <p className="mt-1 text-sm text-slate-500">
            Quản lý CTĐT, chuẩn đầu ra (PLO/PI), học phần và ma trận chuẩn đầu ra.
          </p>
        </div>
        <span className="badge bg-indigo-50 text-indigo-700">{programs.length} chương trình</span>
      </div>

      {err && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">{err}</p>
      )}

      {/* Thêm CTĐT */}
      <div className="card">
        <h2 className="mb-3">Thêm chương trình</h2>
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[16rem] flex-1">
            <label className="mb-1 block text-sm font-medium text-slate-700">Tên CTĐT</label>
            <input className="w-full" placeholder="vd: Cử nhân Công nghệ Thông tin"
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="w-40">
            <label className="mb-1 block text-sm font-medium text-slate-700">Mã</label>
            <input className="w-full" placeholder="vd: CNTT2024"
              value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </div>
          <button className="btn btn-primary">+ Thêm</button>
        </form>
      </div>

      {/* Danh sách */}
      <div className="space-y-3">
        {programs.map((p) => (
          <div key={p.id}
            className="group flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-card transition hover:border-indigo-300 hover:shadow-soft">
            <Link href={`/programs/${p.id}`} className="flex min-w-0 items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                🎓
              </span>
              <span className="min-w-0">
                <span className="block truncate font-semibold text-slate-900 group-hover:text-indigo-700">
                  {p.name || "(chưa đặt tên)"}{" "}
                  {p.code && <span className="font-normal text-slate-400">({p.code})</span>}
                </span>
                <span className="block truncate text-xs text-slate-500">
                  {[p.level, p.year, p.faculty].filter(Boolean).join(" · ") || "—"}
                </span>
              </span>
            </Link>
            <button
              onClick={() => remove(p)}
              className="shrink-0 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
            >
              Xóa
            </button>
          </div>
        ))}
        {programs.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-500">
            Chưa có chương trình đào tạo nào. Thêm mới ở trên hoặc dùng “Trích xuất AI” từ đề án.
          </div>
        )}
      </div>
    </div>
  );
}
