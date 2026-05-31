"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken, getUser } from "@/lib/api";

interface ApiKey {
  id: number;
  provider: string;
  name: string;
  api_key_masked: string;
  model: string;
  is_active: boolean;
  created_at: string | null;
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Claude (Anthropic)",
  openai: "OpenAI",
};

const DEFAULT_MODELS: Record<string, string> = {
  anthropic: "claude-opus-4-8",
  openai: "gpt-4o",
};

export default function AdminAiPage() {
  const router = useRouter();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [testResults, setTestResults] = useState<Record<number, string>>({});

  const [form, setForm] = useState({
    provider: "anthropic",
    name: "",
    api_key: "",
    model: "",
    is_active: true,
  });

  async function load() {
    setErr("");
    try {
      setStatus(await api("/api/ai-status"));
      setKeys(await api("/api/api-keys"));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    const u = getUser();
    if (u?.role !== "admin") {
      setErr("Chỉ Quản trị hệ thống mới được truy cập trang này.");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createKey(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    if (!form.api_key.trim()) {
      setErr("Vui lòng nhập API key.");
      return;
    }
    try {
      await api("/api/api-keys", {
        method: "POST",
        body: JSON.stringify({
          provider: form.provider,
          name: form.name,
          api_key: form.api_key,
          model: form.model || null,
          is_active: form.is_active,
        }),
      });
      setMsg("Đã lưu API key.");
      setForm({ provider: "anthropic", name: "", api_key: "", model: "", is_active: true });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function activate(id: number) {
    try {
      await api(`/api/api-keys/${id}/activate`, { method: "POST" });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function testKey(id: number) {
    setTestResults((p) => ({ ...p, [id]: "Đang kiểm tra..." }));
    try {
      const r = await api(`/api/api-keys/${id}/test`, { method: "POST" });
      setTestResults((p) => ({ ...p, [id]: r.ok ? "✅ Hoạt động" : `❌ ${r.message}` }));
    } catch (e: any) {
      setTestResults((p) => ({ ...p, [id]: `❌ ${e.message}` }));
    }
  }

  async function remove(id: number) {
    if (!confirm("Xóa API key này?")) return;
    try {
      await api(`/api/api-keys/${id}`, { method: "DELETE" });
      load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Cấu hình API AI</h1>
        <Link href="/admin" className="text-sm text-indigo-600 hover:underline">
          ← Về Quản trị
        </Link>
      </div>

      {err && <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</p>}
      {msg && <p className="rounded border border-green-300 bg-green-50 p-3 text-sm text-green-700">{msg}</p>}

      {/* Trạng thái hiện tại */}
      {status && (
        <div
          className={`rounded border p-3 text-sm ${
            status.configured
              ? "border-green-300 bg-green-50 text-green-800"
              : "border-amber-300 bg-amber-50 text-amber-800"
          }`}
        >
          {status.configured ? (
            <>
              ✅ <b>AI đang hoạt động</b> — nhà cung cấp: {PROVIDER_LABELS[status.provider] ?? status.provider},
              model: <code>{status.model}</code>
              {status.source === "env" && " (cấu hình qua biến môi trường)"}
            </>
          ) : (
            <>⚠ <b>Chưa có API key nào được kích hoạt.</b> Hãy thêm và kích hoạt một key bên dưới.</>
          )}
        </div>
      )}

      {/* Form thêm key */}
      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Thêm API key</h2>
        <form onSubmit={createKey} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            Nhà cung cấp
            <select
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
              className="mt-1 block w-full rounded border p-2"
            >
              <option value="anthropic">Claude (Anthropic)</option>
              <option value="openai">OpenAI</option>
            </select>
          </label>
          <label className="text-sm">
            Tên gợi nhớ (tùy chọn)
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="mt-1 block w-full rounded border p-2"
              placeholder="VD: Key chính của trường"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            API Key
            <input
              type="password"
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              className="mt-1 block w-full rounded border p-2 font-mono"
              placeholder={form.provider === "openai" ? "sk-..." : "sk-ant-..."}
            />
          </label>
          <label className="text-sm">
            Model (tùy chọn)
            <input
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              className="mt-1 block w-full rounded border p-2 font-mono"
              placeholder={DEFAULT_MODELS[form.provider]}
            />
          </label>
          <label className="flex items-end gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Kích hoạt ngay (tắt các key khác)
          </label>
          <div className="sm:col-span-2">
            <button className="rounded bg-indigo-600 px-4 py-2 text-white">Lưu API key</button>
          </div>
        </form>
        <p className="mt-2 text-xs text-slate-500">
          Key được lưu phía máy chủ và chỉ hiển thị dạng che. Hệ thống dùng key đang kích hoạt cho
          mọi người dùng.
        </p>
      </section>

      {/* Danh sách key */}
      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Danh sách API key</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2 text-left">Nhà cung cấp</th>
                <th className="border p-2 text-left">Tên</th>
                <th className="border p-2 text-left">Key</th>
                <th className="border p-2 text-left">Model</th>
                <th className="border p-2">Trạng thái</th>
                <th className="border p-2">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td className="border p-2">{PROVIDER_LABELS[k.provider] ?? k.provider}</td>
                  <td className="border p-2">{k.name || "—"}</td>
                  <td className="border p-2 font-mono text-xs">{k.api_key_masked}</td>
                  <td className="border p-2 font-mono text-xs">{k.model}</td>
                  <td className="border p-2 text-center">
                    {k.is_active ? (
                      <span className="rounded bg-green-100 px-2 py-1 text-xs text-green-700">
                        Đang dùng
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">Tắt</span>
                    )}
                  </td>
                  <td className="border p-2 text-center whitespace-nowrap">
                    {!k.is_active && (
                      <button
                        onClick={() => activate(k.id)}
                        className="mr-1 rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200"
                      >
                        Kích hoạt
                      </button>
                    )}
                    <button
                      onClick={() => testKey(k.id)}
                      className="mr-1 rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
                    >
                      Kiểm tra
                    </button>
                    <button
                      onClick={() => remove(k.id)}
                      className="rounded bg-red-100 px-2 py-1 text-xs text-red-700 hover:bg-red-200"
                    >
                      Xóa
                    </button>
                    {testResults[k.id] && (
                      <div className="mt-1 text-xs text-slate-600">{testResults[k.id]}</div>
                    )}
                  </td>
                </tr>
              ))}
              {keys.length === 0 && (
                <tr>
                  <td colSpan={6} className="border p-3 text-center text-slate-500">
                    Chưa có API key nào.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
