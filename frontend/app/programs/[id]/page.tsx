"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

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
  // Bảng sức khỏe đề cương toàn ngành.
  const [health, setHealth] = useState<any>(null);
  const [healthBusy, setHealthBusy] = useState(false);

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

      {/* Bảng sức khỏe đề cương toàn ngành.
          (Đã ẩn Import hàng loạt do tốn thời gian & dễ map sai — dùng "Import đề cương đã có"
           trong từng học phần để gắn chính xác.) */}
      <section className="mt-6 rounded border border-amber-200 bg-amber-50/40 p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Sức khỏe đề cương toàn ngành</h2>
          <div className="flex flex-wrap gap-2">
            <button onClick={loadHealth} disabled={healthBusy}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50">
              {healthBusy ? "Đang tải..." : "Xem bảng sức khỏe"}
            </button>
          </div>
        </div>
        <p className="mb-2 text-xs text-slate-500">
          Mẹo: để gắn đề cương đã có vào đúng học phần, mở học phần và dùng nút
          “⬆ Import đề cương đã có”.
        </p>

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
