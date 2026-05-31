"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, API_BASE, getToken } from "@/lib/api";

interface Program {
  id: number;
  name: string;
  code: string;
  level?: string;
  year?: number;
  faculty?: string;
}

interface Pi {
  code: string;
  description: string;
}

interface CloRow {
  clo_code: string;
  assessed: boolean;
}

interface PloRow {
  plo_code: string;
  description: string;
  pis: Pi[];
  clos: CloRow[];
}

interface CoverageReport {
  program_id: number;
  courses: any[];
  plos: PloRow[];
  gaps: string[];
  ok: boolean;
}

interface DocItem {
  id: number;
  type: string;
  original_name: string;
  mime: string;
  uploaded_by: number;
  created_at: string;
  text_length: number;
}

interface AuditLog {
  id: number;
  user_id: number;
  entity: string;
  entity_id: number;
  action: string;
  diff: any;
  created_at: string;
}

export default function QaPage() {
  const router = useRouter();

  const [programs, setPrograms] = useState<Program[]>([]);
  const [programsErr, setProgramsErr] = useState("");
  const [selectedPid, setSelectedPid] = useState<number | null>(null);

  const [report, setReport] = useState<CoverageReport | null>(null);
  const [reportErr, setReportErr] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadErr, setDownloadErr] = useState("");

  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [documentsErr, setDocumentsErr] = useState("");

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [logsErr, setLogsErr] = useState("");
  const [entityFilter, setEntityFilter] = useState("");

  function friendlyErr(e: any): string {
    const msg = String(e?.message || e || "");
    if (msg.includes("403") || /forbidden|permission|quyền/i.test(msg)) {
      return "Bạn không có quyền xem mục này";
    }
    return msg || "Có lỗi xảy ra";
  }

  async function loadPrograms() {
    setProgramsErr("");
    try {
      setPrograms(await api("/api/programs"));
    } catch (e: any) {
      setProgramsErr(friendlyErr(e));
    }
  }

  async function loadReport(pid: number) {
    setReportErr("");
    setReport(null);
    try {
      setReport(await api(`/api/programs/${pid}/coverage-report`));
    } catch (e: any) {
      setReportErr(friendlyErr(e));
    }
  }

  async function loadDocuments() {
    setDocumentsErr("");
    try {
      setDocuments(await api("/api/documents"));
    } catch (e: any) {
      setDocumentsErr(friendlyErr(e));
    }
  }

  async function loadLogs() {
    setLogsErr("");
    try {
      const qs = new URLSearchParams({ limit: "100" });
      if (entityFilter.trim()) qs.set("entity", entityFilter.trim());
      setLogs(await api(`/api/audit-logs?${qs.toString()}`));
    } catch (e: any) {
      setLogsErr(friendlyErr(e));
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    loadPrograms();
    loadDocuments();
    loadLogs();
  }, []);

  function onSelectProgram(e: React.ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value;
    if (!v) {
      setSelectedPid(null);
      setReport(null);
      return;
    }
    const pid = Number(v);
    setSelectedPid(pid);
    loadReport(pid);
  }

  async function downloadEvidence() {
    if (!selectedPid) return;
    setDownloading(true);
    setDownloadErr("");
    try {
      const res = await fetch(
        `${API_BASE}/api/programs/${selectedPid}/evidence-package`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `evidence_${selectedPid}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setDownloadErr(friendlyErr(e));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold">Lưu trữ &amp; Kiểm định (ĐBCL/AUN-QA)</h1>

      {/* Section: Báo cáo phủ chuẩn */}
      <div className="mt-4 rounded border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Báo cáo phủ chuẩn theo CTĐT</h2>
        {programsErr && <p className="mt-2 text-sm text-red-600">{programsErr}</p>}
        <div className="mt-3 flex items-center gap-2">
          <select
            className="rounded border p-2"
            value={selectedPid ?? ""}
            onChange={onSelectProgram}
          >
            <option value="">-- Chọn CTĐT --</option>
            {programs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.code})
              </option>
            ))}
          </select>
          {selectedPid && (
            <button
              className="rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
              onClick={downloadEvidence}
              disabled={downloading}
            >
              {downloading ? "Đang tải..." : "Tải gói minh chứng (zip)"}
            </button>
          )}
        </div>
        {downloadErr && <p className="mt-2 text-sm text-red-600">{downloadErr}</p>}
        {reportErr && <p className="mt-2 text-sm text-red-600">{reportErr}</p>}

        {report && (
          <div className="mt-4">
            <div
              className={`rounded border p-3 ${
                report.ok
                  ? "border-green-300 bg-green-50"
                  : "border-red-300 bg-red-50"
              }`}
            >
              <p className="font-semibold">
                {report.ok ? (
                  <span className="text-green-700">Đạt độ phủ chuẩn</span>
                ) : (
                  <span className="text-red-700">Còn thiếu sót độ phủ</span>
                )}
              </p>
              {report.gaps && report.gaps.length > 0 && (
                <ul className="mt-2 list-disc pl-6 text-sm text-red-700">
                  {report.gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-4 space-y-3">
              {report.plos.map((plo) => (
                <div key={plo.plo_code} className="rounded border p-3">
                  <p className="font-semibold text-indigo-700">
                    {plo.plo_code}{" "}
                    <span className="font-normal text-slate-600">
                      {plo.description}
                    </span>
                  </p>
                  <div className="mt-2">
                    <p className="text-sm font-medium text-slate-500">
                      Chỉ báo (PI)
                    </p>
                    {plo.pis.length > 0 ? (
                      <ul className="mt-1 list-disc pl-6 text-sm">
                        {plo.pis.map((pi) => (
                          <li key={pi.code}>
                            <span className="font-medium">{pi.code}</span>:{" "}
                            {pi.description}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-slate-400">Chưa có PI</p>
                    )}
                  </div>
                  <div className="mt-2">
                    <p className="text-sm font-medium text-slate-500">CLO</p>
                    {plo.clos.length > 0 ? (
                      <div className="mt-1 flex flex-wrap gap-2">
                        {plo.clos.map((c) => (
                          <span
                            key={c.clo_code}
                            className={`rounded px-2 py-1 text-xs ${
                              c.assessed
                                ? "bg-green-100 text-green-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {c.clo_code} ·{" "}
                            {c.assessed ? "đã đánh giá" : "chưa đánh giá"}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400">Chưa có CLO</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Section: Kho minh chứng */}
      <div className="mt-4 rounded border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Kho minh chứng / Tài liệu gốc</h2>
        {documentsErr && (
          <p className="mt-2 text-sm text-red-600">{documentsErr}</p>
        )}
        {!documentsErr && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="border p-2">ID</th>
                  <th className="border p-2">Tên</th>
                  <th className="border p-2">Loại</th>
                  <th className="border p-2">Kích thước (text)</th>
                  <th className="border p-2">Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id}>
                    <td className="border p-2">{d.id}</td>
                    <td className="border p-2">{d.original_name}</td>
                    <td className="border p-2">{d.type}</td>
                    <td className="border p-2">{d.text_length}</td>
                    <td className="border p-2">{d.created_at}</td>
                  </tr>
                ))}
                {documents.length === 0 && (
                  <tr>
                    <td className="border p-2 text-slate-500" colSpan={5}>
                      Chưa có tài liệu.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section: Nhật ký kiểm định */}
      <div className="mt-4 rounded border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Nhật ký kiểm định (Audit log)</h2>
        <div className="mt-3 flex items-center gap-2">
          <input
            className="rounded border p-2"
            placeholder="Lọc theo entity"
            value={entityFilter}
            onChange={(e) => setEntityFilter(e.target.value)}
          />
          <button
            className="rounded bg-indigo-600 px-4 py-2 text-white"
            onClick={loadLogs}
          >
            Lọc
          </button>
        </div>
        {logsErr && <p className="mt-2 text-sm text-red-600">{logsErr}</p>}
        {!logsErr && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="border p-2">Thời gian</th>
                  <th className="border p-2">User ID</th>
                  <th className="border p-2">Entity</th>
                  <th className="border p-2">Entity ID</th>
                  <th className="border p-2">Hành động</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="border p-2">{l.created_at}</td>
                    <td className="border p-2">{l.user_id}</td>
                    <td className="border p-2">{l.entity}</td>
                    <td className="border p-2">{l.entity_id}</td>
                    <td className="border p-2">{l.action}</td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td className="border p-2 text-slate-500" colSpan={5}>
                      Chưa có nhật ký.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
