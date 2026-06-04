"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, apiUpload } from "@/lib/api";

const LEVELS = ["", "I", "R", "M"];

export default function ProgramDetail() {
  const { id } = useParams<{ id: string }>();
  const [program, setProgram] = useState<any>(null);
  const [plos, setPlos] = useState<any[]>([]);
  const [pisByPlo, setPisByPlo] = useState<Record<number, any[]>>({});
  const [courses, setCourses] = useState<any[]>([]);
  const [matrix, setMatrix] = useState<any[]>([]);
  const [coverage, setCoverage] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [ploReview, setPloReview] = useState<any>(null);
  const [ploReviewBusy, setPloReviewBusy] = useState(false);
  const [err, setErr] = useState("");
  // Phase 3: import hàng loạt + bảng sức khỏe đề cương
  const [health, setHealth] = useState<any>(null);
  const [healthBusy, setHealthBusy] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResults, setBulkResults] = useState<any[] | null>(null);
  // Import 2 bước: parse → gán học phần → xác nhận lưu
  const [bulkParsed, setBulkParsed] = useState<any>(null); // {courses, rows}
  const [rowCourse, setRowCourse] = useState<Record<number, string>>({}); // index → course_id (chuỗi)

  async function loadHealth() {
    setErr("");
    setHealthBusy(true);
    try {
      setHealth(await api(`/api/programs/${id}/outline-health`));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setHealthBusy(false);
    }
  }

  // Bước 1: bóc tách (chưa lưu) → gợi ý học phần để người dùng xác nhận.
  async function parseFiles(files: FileList) {
    setErr("");
    setBulkResults(null);
    setBulkParsed(null);
    if (files.length > 15 &&
        !confirm(`Bạn chọn ${files.length} file. Xử lý nhiều file cùng lúc có thể lâu. ` +
                 `Nên làm theo từng mẻ ~10-15 file. Vẫn tiếp tục?`)) {
      return;
    }
    setBulkBusy(true);
    try {
      const fd = new FormData();
      Array.from(files).forEach((f) => fd.append("files", f));
      const res = await apiUpload(`/api/programs/${id}/parse-outlines`, fd);
      setBulkParsed(res);
      // Khởi tạo lựa chọn học phần = gợi ý của AI (người dùng có thể đổi).
      const init: Record<number, string> = {};
      (res.rows || []).forEach((r: any, i: number) => {
        init[i] = r.suggested_course_id ? String(r.suggested_course_id) : "";
      });
      setRowCourse(init);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBulkBusy(false);
    }
  }

  // Bước 2: lưu theo ĐÚNG học phần đã chọn cho từng file.
  async function confirmImport() {
    setErr("");
    const items = (bulkParsed.rows || [])
      .map((r: any, i: number) => ({ r, cid: rowCourse[i] }))
      .filter((x: any) => x.r.outline && x.cid)
      .map((x: any) => ({ course_id: Number(x.cid), outline: x.r.outline, source_name: x.r.filename }));
    if (items.length === 0) {
      setErr("Hãy chọn học phần cho ít nhất một file bóc tách thành công.");
      return;
    }
    setBulkBusy(true);
    try {
      const res = await api(`/api/programs/${id}/import-outlines-confirm`, {
        method: "POST",
        body: JSON.stringify({ items, run_qa: true }),
      });
      setBulkResults(res.results || []);
      setBulkParsed(null);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      await loadHealth();
      setBulkBusy(false);
    }
  }

  async function reviewPlos() {
    setErr("");
    setPloReview(null);
    setPloReviewBusy(true);
    try {
      setPloReview(await api(`/api/programs/${id}/review-plos`, { method: "POST" }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setPloReviewBusy(false);
    }
  }

  async function load() {
    try {
      setProgram(await api(`/api/programs/${id}`));
      const ploList = await api(`/api/programs/${id}/plos`);
      setPlos(ploList);
      // Lấy PI của từng PLO để hiển thị dưới mỗi PLO.
      const piMap: Record<number, any[]> = {};
      for (const p of ploList) {
        piMap[p.id] = await api(`/api/plos/${p.id}/pis`);
      }
      setPisByPlo(piMap);
      setCourses(await api(`/api/programs/${id}/courses`));
      setMatrix(await api(`/api/programs/${id}/course-plo`));
      setCoverage(await api(`/api/programs/${id}/coverage`));
    } catch (e: any) {
      setErr(e.message);
    }
  }
  useEffect(() => {
    load();
  }, [id]);

  function levelOf(courseId: number, ploId: number) {
    return matrix.find((m) => m.course_id === courseId && m.plo_id === ploId)?.level || "";
  }

  async function setLevel(courseId: number, ploId: number, level: string) {
    try {
      const cur = matrix.find((m) => m.course_id === courseId && m.plo_id === ploId);
      if (!level && cur) {
        await api(`/api/course-plo/${cur.id}`, { method: "DELETE" });
      } else if (level) {
        await api(`/api/course-plo`, {
          method: "PUT",
          body: JSON.stringify({ course_id: courseId, plo_id: ploId, level }),
        });
      }
      setMatrix(await api(`/api/programs/${id}/course-plo`));
      setCoverage(await api(`/api/programs/${id}/coverage`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  if (!program) return <p>{err || "Đang tải..."}</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold">
        {program.name} <span className="text-slate-400">({program.code})</span>
      </h1>
      {err && <p className="mt-2 text-sm text-red-600">{err}</p>}

      {/* Coverage banner */}
      {coverage && (
        <div
          className={`mt-4 rounded border p-3 text-sm ${
            coverage.ok ? "border-green-300 bg-green-50" : "border-red-300 bg-red-50"
          }`}
        >
          <b>Kiểm tra độ phủ PLO:</b> {coverage.ok ? "Đạt" : "Có lỗi"}
          {coverage.errors?.map((e: string) => (
            <div key={e} className="text-red-700">• {e}</div>
          ))}
          {coverage.warnings?.map((w: string) => (
            <div key={w} className="text-amber-700">⚠ {w}</div>
          ))}
        </div>
      )}

      <section className="mt-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Chuẩn đầu ra (PLO) & Chỉ báo (PI)</h2>
          <button
            onClick={reviewPlos}
            disabled={ploReviewBusy}
            className="rounded bg-green-600 px-3 py-1 text-sm text-white disabled:opacity-50"
          >
            {ploReviewBusy ? "AI đang rà soát..." : "✨ Chuẩn hóa PLO bằng AI"}
          </button>
        </div>
        {ploReview && (
          <div className="mb-3 rounded border border-indigo-300 bg-indigo-50 p-3 text-sm">
            <b>Kết quả rà soát PLO (AI)</b>
            {(ploReview.overall_issues || []).map((x: string) => (
              <div key={x} className="text-amber-700">⚠ {x}</div>
            ))}
            <table className="mt-2 w-full border bg-white text-xs">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1">PLO</th>
                  <th className="border p-1">Đo được</th>
                  <th className="border p-1">Bloom</th>
                  <th className="border p-1 text-left">Vấn đề</th>
                  <th className="border p-1 text-left">Gợi ý viết lại</th>
                </tr>
              </thead>
              <tbody>
                {(ploReview.plos || []).map((r: any) => (
                  <tr key={r.code}>
                    <td className="border p-1 text-center">{r.code}</td>
                    <td className="border p-1 text-center">{r.measurable ? "✓" : "✗"}</td>
                    <td className="border p-1 text-center">{r.bloom_level}</td>
                    <td className="border p-1">{(r.issues || []).join("; ") || "—"}</td>
                    <td className="border p-1">{r.suggestion || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-slate-500">Gợi ý của AI — cần người duyệt xác nhận.</p>
          </div>
        )}
        <ul className="space-y-2">
          {plos.map((p) => (
            <li key={p.id} className="rounded border bg-white p-3 text-sm">
              <div>
                <b>{p.code}</b> — {p.description}{" "}
                <span className="text-slate-400">[{p.category}]</span>
              </div>
              {pisByPlo[p.id] && pisByPlo[p.id].length > 0 && (
                <ul className="mt-2 space-y-1 border-l-2 border-indigo-100 pl-3">
                  {pisByPlo[p.id].map((pi) => (
                    <li key={pi.id} className="text-slate-600">
                      <b className="text-indigo-700">{pi.code}</b> — {pi.description}
                    </li>
                  ))}
                </ul>
              )}
              {(!pisByPlo[p.id] || pisByPlo[p.id].length === 0) && (
                <p className="mt-1 text-xs text-slate-400">(Chưa có PI)</p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-lg font-semibold">Ma trận Học phần × PLO (I/R/M)</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border bg-white text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2 text-center">STT</th>
                <th className="border p-2 text-left">Học phần</th>
                {plos.map((p) => (
                  <th key={p.id} className="border p-2">{p.code}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {courses.map((c, idx) => (
                <tr key={c.id}>
                  <td className="border p-2 text-center text-slate-500">{idx + 1}</td>
                  <td className="border p-2">
                    <Link href={`/courses/${c.id}`} className="text-indigo-700">
                      {c.code} — {c.name}
                    </Link>
                  </td>
                  {plos.map((p) => (
                    <td key={p.id} className="border p-1 text-center">
                      <select
                        value={levelOf(c.id, p.id)}
                        onChange={(e) => setLevel(c.id, p.id, e.target.value)}
                        className="rounded border bg-white p-1"
                      >
                        {LEVELS.map((l) => (
                          <option key={l} value={l}>{l || "–"}</option>
                        ))}
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Phase 3: Import hàng loạt đề cương + Bảng sức khỏe đề cương toàn ngành */}
      <section className="mt-6 rounded border border-amber-200 bg-amber-50/40 p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Sức khỏe đề cương toàn ngành</h2>
          <div className="flex flex-wrap gap-2">
            <label className={`cursor-pointer rounded bg-amber-500 px-3 py-1.5 text-sm text-white ${bulkBusy ? "opacity-50" : ""}`}
              title="Tải lên nhiều đề cương đã có (PDF/DOCX). AI bóc tách + GỢI Ý học phần; bạn xác nhận đúng học phần rồi mới lưu.">
              {bulkBusy ? "Đang xử lý..." : "⬆ Import hàng loạt (chọn nhiều file)"}
              <input type="file" multiple accept=".pdf,.docx,.txt" className="hidden" disabled={bulkBusy}
                onChange={(e) => e.target.files?.length && parseFiles(e.target.files)} />
            </label>
            <button onClick={loadHealth} disabled={healthBusy}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
              {healthBusy ? "Đang tải..." : "Xem bảng sức khỏe"}
            </button>
          </div>
        </div>

        {/* Bước rà soát: gán đúng học phần cho từng file trước khi lưu */}
        {bulkParsed && (
          <div className="mb-3 rounded border border-amber-400 bg-white p-3 text-xs">
            <div className="mb-2 font-semibold">
              Xác nhận học phần cho từng đề cương ({bulkParsed.rows.length} file) — kiểm tra/đổi học phần nếu AI gợi ý sai, rồi bấm Lưu.
            </div>
            <table className="w-full border">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1 text-left">File</th>
                  <th className="border p-1">Mã AI đọc</th>
                  <th className="border p-1">CLO</th>
                  <th className="border p-1 text-left">Gán vào học phần</th>
                  <th className="border p-1 text-left">Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                {bulkParsed.rows.map((r: any, i: number) => (
                  <tr key={i} className={r.error ? "bg-red-50" : ""}>
                    <td className="border p-1">{r.filename}</td>
                    <td className="border p-1 text-center">{r.detected_course_code || "—"}</td>
                    <td className="border p-1 text-center">{r.error ? "—" : r.clos_count}</td>
                    <td className="border p-1">
                      {r.error ? (
                        <span className="text-red-600">không lưu được</span>
                      ) : (
                        <select value={rowCourse[i] || ""}
                          onChange={(e) => setRowCourse((p) => ({ ...p, [i]: e.target.value }))}
                          className={`w-full rounded border p-1 ${!rowCourse[i] ? "border-amber-500 bg-amber-50" : ""}`}>
                          <option value="">— Chọn học phần —</option>
                          {bulkParsed.courses.map((c: any) => (
                            <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="border p-1 text-amber-700">
                      {r.error
                        ? r.error
                        : !r.suggested_course_id
                        ? "AI không chắc — hãy chọn thủ công"
                        : (r.unmatched_plos?.length ? `PLO bỏ: ${r.unmatched_plos.join(", ")}` : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-2 flex gap-2">
              <button onClick={confirmImport} disabled={bulkBusy}
                className="rounded bg-amber-600 px-4 py-2 font-medium text-white disabled:opacity-50">
                {bulkBusy ? "Đang lưu..." : "Lưu các đề cương đã gán & chấm điểm"}
              </button>
              <button onClick={() => { setBulkParsed(null); setRowCourse({}); }}
                className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200">Huỷ</button>
            </div>
          </div>
        )}

        {bulkResults && (
          <div className="mb-3 rounded border bg-white p-2 text-xs">
            <b>Kết quả lưu {bulkResults.length} đề cương:</b>
            {bulkResults.map((r, i) => (
              <div key={i} className={r.outline_id ? "text-green-700" : "text-amber-700"}>
                {r.outline_id ? "✓" : "⚠"} {r.course_code || "(học phần?)"}
                {r.score != null ? ` · điểm ${r.score}/100` : ""} · {r.message}
              </div>
            ))}
          </div>
        )}

        {health && (
          <div className="overflow-x-auto">
            <table className="min-w-full border bg-white text-sm">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-2 text-center">STT</th>
                  <th className="border p-2 text-left">Học phần</th>
                  <th className="border p-2">Đề cương</th>
                  <th className="border p-2">Trạng thái</th>
                  <th className="border p-2">Điểm AI</th>
                  <th className="border p-2">Lỗi</th>
                  <th className="border p-2">Cảnh báo</th>
                </tr>
              </thead>
              <tbody>
                {health.rows.map((r: any, i: number) => (
                  <tr key={r.course_id}>
                    <td className="border p-2 text-center text-slate-500">{i + 1}</td>
                    <td className="border p-2">
                      {r.outline_id ? (
                        <Link href={`/outlines/${r.outline_id}`} className="text-indigo-700">
                          {r.course_code} — {r.course_name}
                        </Link>
                      ) : (
                        <span>{r.course_code} — {r.course_name}</span>
                      )}
                      {r.imported && <span className="ml-1 text-xs text-amber-600">(import)</span>}
                    </td>
                    <td className="border p-2 text-center">
                      {r.has_outline ? `v${r.version}` : <span className="text-red-600">chưa có</span>}
                    </td>
                    <td className="border p-2 text-center text-xs">{r.status || "—"}</td>
                    <td className="border p-2 text-center">
                      {r.qa_score != null ? (
                        <span className={`rounded px-2 py-0.5 text-xs text-white ${
                          r.qa_score >= 80 ? "bg-green-600" : r.qa_score >= 60 ? "bg-amber-500" : "bg-red-600"}`}>
                          {r.qa_score}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="border p-2 text-center">{r.qa_errors ?? "—"}</td>
                    <td className="border p-2 text-center">{r.qa_warnings ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-slate-500">
              Điểm AI là kết quả lần chấm chất lượng gần nhất của mỗi đề cương. Mở từng đề cương để chấm/nâng cấp.
            </p>
          </div>
        )}
      </section>

      <section className="mt-6">
        <button
          onClick={async () =>
            setReport(await api(`/api/programs/${id}/coverage-report`))
          }
          className="rounded bg-indigo-600 px-4 py-2 text-white"
        >
          Báo cáo phủ chuẩn (AUN-QA)
        </button>
        {report && (
          <div className="mt-3 rounded border bg-white p-4 text-sm">
            <p>
              <b>Học phần:</b> {report.courses} ·{" "}
              <b className={report.ok ? "text-green-700" : "text-red-700"}>
                {report.ok ? "Không có lỗ hổng" : `${report.gaps.length} lỗ hổng`}
              </b>
            </p>
            {report.gaps.map((g: string) => (
              <div key={g} className="text-red-700">• {g}</div>
            ))}
            <ul className="mt-2 space-y-1">
              {report.plos.map((p: any) => (
                <li key={p.plo_code}>
                  <b>{p.plo_code}</b>: {p.clos.length} CLO ánh xạ,{" "}
                  {p.clos.filter((c: any) => c.assessed).length} được đánh giá; {p.pis.length} PI
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
