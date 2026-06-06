"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, getToken, getUser } from "@/lib/api";

interface ProgramRow {
  program_id: number | null;
  program_name: string;
  tokens: number;
  est_cost_usd: number;
  calls: number;
}

interface Usage {
  days: number;
  calls: number;
  total_tokens: number;
  est_cost_usd: number;
  by_program: ProgramRow[];
}

const RANGES = [
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
  { label: "90 ngày", value: 90 },
  { label: "365 ngày", value: 365 },
];

function fmtInt(n: number) {
  return (n ?? 0).toLocaleString("vi-VN");
}
function fmtUsd(n: number) {
  return `$${(n ?? 0).toFixed(2)}`;
}

export default function AdminLlmCostPage() {
  const router = useRouter();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Usage | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(d: number) {
    setErr("");
    setBusy(true);
    try {
      setData(await api(`/api/llm-usage?days=${d}`));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    if (getUser()?.role !== "admin") {
      setErr("Chỉ Quản trị hệ thống mới được truy cập trang này.");
      return;
    }
    load(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Chi phí AI (LLM)</h1>
        <Link href="/admin" className="text-sm text-indigo-600 hover:underline">
          ← Về Quản trị
        </Link>
      </div>

      {err && (
        <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-slate-600">Khoảng thời gian:</span>
        {RANGES.map((r) => (
          <button
            key={r.value}
            onClick={() => {
              setDays(r.value);
              load(r.value);
            }}
            className={`rounded border px-3 py-1.5 text-sm ${
              days === r.value
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "bg-white hover:bg-slate-50"
            }`}
          >
            {r.label}
          </button>
        ))}
        <button
          onClick={() => load(days)}
          disabled={busy}
          className="rounded bg-slate-100 px-3 py-1.5 text-sm hover:bg-slate-200 disabled:opacity-50"
        >
          {busy ? "Đang tải..." : "Làm mới"}
        </button>
      </div>

      {data && (
        <>
          {/* Thẻ tổng quan */}
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded border bg-white p-4 shadow-sm">
              <div className="text-xs text-slate-500">Chi phí ước tính ({data.days} ngày)</div>
              <div className="mt-1 text-2xl font-bold text-emerald-700">{fmtUsd(data.est_cost_usd)}</div>
            </div>
            <div className="rounded border bg-white p-4 shadow-sm">
              <div className="text-xs text-slate-500">Tổng token</div>
              <div className="mt-1 text-2xl font-bold">{fmtInt(data.total_tokens)}</div>
            </div>
            <div className="rounded border bg-white p-4 shadow-sm">
              <div className="text-xs text-slate-500">Số lượt gọi AI</div>
              <div className="mt-1 text-2xl font-bold">{fmtInt(data.calls)}</div>
            </div>
          </div>

          {/* Phân rã theo chương trình */}
          <div className="rounded border bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Theo chương trình đào tạo</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full border text-sm">
                <thead>
                  <tr className="bg-slate-100">
                    <th className="border p-2 text-center">STT</th>
                    <th className="border p-2 text-left">Chương trình</th>
                    <th className="border p-2 text-right">Lượt gọi</th>
                    <th className="border p-2 text-right">Token</th>
                    <th className="border p-2 text-right">Chi phí ước tính</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_program.map((r, i) => (
                    <tr key={r.program_id ?? `none-${i}`}>
                      <td className="border p-2 text-center text-slate-500">{i + 1}</td>
                      <td className="border p-2">{r.program_name}</td>
                      <td className="border p-2 text-right">{fmtInt(r.calls)}</td>
                      <td className="border p-2 text-right">{fmtInt(r.tokens)}</td>
                      <td className="border p-2 text-right font-medium text-emerald-700">
                        {fmtUsd(r.est_cost_usd)}
                      </td>
                    </tr>
                  ))}
                  {data.by_program.length === 0 && (
                    <tr>
                      <td colSpan={5} className="border p-3 text-center text-slate-500">
                        Chưa có lượt dùng AI nào trong khoảng thời gian này.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <p className="text-xs text-slate-500">
            * Chi phí là <b>ước tính</b> theo bảng giá token tham khảo của từng mô hình; con số thực
            tế trên hóa đơn nhà cung cấp có thể khác. Hạn mức token/ngày theo chương trình cấu hình
            qua biến môi trường <code>LLM_DAILY_TOKEN_QUOTA_PER_PROGRAM</code>.
          </p>
        </>
      )}
    </div>
  );
}
