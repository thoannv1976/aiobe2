"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, apiUpload } from "@/lib/api";

export default function CourseDetail() {
  const { id } = useParams<{ id: string }>();
  const [outlines, setOutlines] = useState<any[]>([]);
  const [alignment, setAlignment] = useState<Record<number, any>>({});
  const [questions, setQuestions] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [matrices, setMatrices] = useState<any[]>([]);
  const [exams, setExams] = useState<any[]>([]);
  const [blueprint, setBlueprint] = useState<any>(null);
  const [err, setErr] = useState("");
  const [genExamErr, setGenExamErr] = useState<{ matrixId: number; message: string } | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [templates, setTemplates] = useState<any[]>([]);
  const [aunqaDocs, setAunqaDocs] = useState<any[]>([]);
  const [templateId, setTemplateId] = useState<string>("");
  const [aunqaId, setAunqaId] = useState<string>("");
  const [scheme, setScheme] = useState<string>("10-30-60");
  const [numClos, setNumClos] = useState<string>("4–6");
  const [numWeeks, setNumWeeks] = useState<number>(15);
  const [bilingual, setBilingual] = useState<boolean>(true);

  async function load() {
    try {
      const ol = await api(`/api/courses/${id}/outlines`);
      setOutlines(ol);
      const al: Record<number, any> = {};
      for (const o of ol) al[o.id] = await api(`/api/outlines/${o.id}/alignment`);
      setAlignment(al);
      setQuestions(await api(`/api/courses/${id}/questions`));
      setStats(await api(`/api/courses/${id}/questions/stats`));
      setMatrices(await api(`/api/courses/${id}/matrices`));
      setExams(await api(`/api/courses/${id}/exams`));
    } catch (e: any) {
      setErr(e.message);
    }
    // Tài liệu tham chiếu load riêng (không chặn phần còn lại nếu thiếu quyền).
    try {
      setTemplates(await api(`/api/documents?type=outline_template`));
      setAunqaDocs(await api(`/api/documents?type=aunqa_standard`));
    } catch {
      /* bỏ qua */
    }
  }
  useEffect(() => {
    load();
  }, [id]);

  async function createOutline() {
    setErr("");
    try {
      const o = await api(`/api/outlines`, {
        method: "POST",
        body: JSON.stringify({ course_id: Number(id), description: "", general_info_json: {}, teaching_methods_json: [], references_json: [] }),
      });
      window.location.href = `/outlines/${o.id}`;
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function generateOutlineAI() {
    setErr("");
    setGenBusy(true);
    try {
      const qs = new URLSearchParams();
      if (templateId) qs.set("template_doc_id", templateId);
      if (aunqaId) qs.set("aunqa_doc_id", aunqaId);
      qs.set("assessment_scheme", scheme);
      qs.set("num_clos", numClos);
      qs.set("num_weeks", String(numWeeks));
      qs.set("bilingual", String(bilingual));
      const o = await api(`/api/courses/${id}/generate-outline?${qs.toString()}`, { method: "POST" });
      window.location.href = `/outlines/${o.id}`;
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  async function uploadRef(file: File, docType: string) {
    setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);
      await apiUpload(`/api/documents/upload`, fd);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function generate(matrixId: number, allowPartial = false) {
    setErr("");
    setGenExamErr(null);
    try {
      await api(`/api/exams/generate`, {
        method: "POST",
        body: JSON.stringify({
          matrix_id: matrixId,
          name: "Đề thi",
          seed: 1,
          allow_partial: allowPartial,
        }),
      });
      setExams(await api(`/api/courses/${id}/exams`));
    } catch (e: any) {
      // Hiển thị lỗi ngay tại ma trận + cho phép sinh một phần.
      setGenExamErr({ matrixId, message: e.message });
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Học phần #{id}</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* Điều hướng nhanh các module của học phần */}
      <div className="flex flex-wrap gap-2 text-sm">
        <Link href={`/courses/${id}/questions`} className="rounded bg-indigo-600 px-3 py-1.5 text-white">
          Ngân hàng câu hỏi & ma trận →
        </Link>
        <Link href={`/courses/${id}/textbooks`} className="rounded border border-indigo-600 px-3 py-1.5 text-indigo-700">
          Giáo trình →
        </Link>
        <Link href={`/courses/${id}/lectures`} className="rounded border border-indigo-600 px-3 py-1.5 text-indigo-700">
          Bài giảng →
        </Link>
      </div>

      {/* Tài liệu tham chiếu cho AI sinh đề cương */}
      <section className="rounded-lg border bg-indigo-50/40 p-4">
        <h2 className="mb-2 text-lg font-semibold">Tài liệu tham chiếu (cho AI sinh đề cương)</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-sm font-medium">Mẫu đề cương</p>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="mt-1 block w-full text-xs"
              onChange={(e) => e.target.files?.[0] && uploadRef(e.target.files[0], "outline_template")}
            />
            <ul className="mt-1 text-xs text-slate-600">
              {templates.map((d) => (
                <li key={d.id}>• {d.original_name}</li>
              ))}
              {templates.length === 0 && <li className="text-slate-400">(Chưa có)</li>}
            </ul>
          </div>
          <div>
            <p className="text-sm font-medium">Tài liệu chuẩn AUN-QA</p>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              className="mt-1 block w-full text-xs"
              onChange={(e) => e.target.files?.[0] && uploadRef(e.target.files[0], "aunqa_standard")}
            />
            <ul className="mt-1 text-xs text-slate-600">
              {aunqaDocs.map((d) => (
                <li key={d.id}>• {d.original_name}</li>
              ))}
              {aunqaDocs.length === 0 && <li className="text-slate-400">(Chưa có)</li>}
            </ul>
          </div>
        </div>
      </section>

      {/* Đề cương + alignment */}
      <section>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Đề cương & kiểm tra Alignment</h2>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="rounded border p-1">
              <option value="">— Mẫu đề cương (tùy chọn) —</option>
              {templates.map((d) => (
                <option key={d.id} value={d.id}>{d.original_name}</option>
              ))}
            </select>
            <select value={aunqaId} onChange={(e) => setAunqaId(e.target.value)} className="rounded border p-1">
              <option value="">— Chuẩn AUN-QA (tùy chọn) —</option>
              {aunqaDocs.map((d) => (
                <option key={d.id} value={d.id}>{d.original_name}</option>
              ))}
            </select>
            <select value={scheme} onChange={(e) => setScheme(e.target.value)} className="rounded border p-1" title="Cơ cấu đánh giá">
              <option value="10-30-60">CC10 / GK30 / CK60</option>
              <option value="10-40-50">CC10 / GK40 / CK50</option>
              <option value="20-30-50">QT20 / GK30 / CK50</option>
              <option value="auto">AI tự đề xuất</option>
            </select>
            <select value={numClos} onChange={(e) => setNumClos(e.target.value)} className="rounded border p-1" title="Số CLO">
              <option value="3–5">3–5 CLO</option>
              <option value="4–6">4–6 CLO</option>
              <option value="5–8">5–8 CLO</option>
            </select>
            <label className="flex items-center gap-1 text-slate-600" title="Số tuần giảng dạy">
              <input
                type="number"
                min={1}
                max={45}
                value={numWeeks}
                onChange={(e) => setNumWeeks(Number(e.target.value) || 15)}
                className="w-14 rounded border p-1"
              />
              tuần
            </label>
            <label className="flex items-center gap-1 text-slate-600" title="CLO song ngữ Việt-Anh">
              <input type="checkbox" checked={bilingual} onChange={(e) => setBilingual(e.target.checked)} />
              Song ngữ
            </label>
            <button
              onClick={generateOutlineAI}
              disabled={genBusy}
              className="rounded bg-green-600 px-3 py-1 text-white disabled:opacity-50"
            >
              {genBusy ? "AI đang soạn..." : "✨ Tạo đề cương bằng AI"}
            </button>
            <button onClick={createOutline} className="rounded bg-indigo-600 px-3 py-1 text-white">
              + Tạo đề cương trống
            </button>
          </div>
        </div>
        {outlines.map((o) => {
          const a = alignment[o.id];
          return (
            <div key={o.id} className="mb-2 rounded border bg-white p-3 text-sm">
              <Link href={`/outlines/${o.id}`} className="font-semibold text-indigo-700">
                Phiên bản v{o.version}
              </Link>{" "}
              — trạng thái: {o.status}
              {a && (
                <div
                  className={`mt-1 rounded p-2 ${
                    a.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                  }`}
                >
                  {a.ok ? "✓ Alignment đạt" : "✗ Alignment chưa đạt"}
                  {a.errors.map((e: string) => (
                    <div key={e}>• {e}</div>
                  ))}
                  {a.warnings.map((w: string) => (
                    <div key={w} className="text-amber-700">⚠ {w}</div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {outlines.length === 0 && <p className="text-slate-500">Chưa có đề cương.</p>}
      </section>

      {/* Thống kê ngân hàng câu hỏi */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">
          Ngân hàng câu hỏi ({questions.length})
        </h2>
        {stats && (
          <div className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="rounded border bg-white p-3">
              <b>Theo độ khó</b>
              {Object.entries(stats.by_difficulty).map(([k, v]: any) => (
                <div key={k}>{k}: {v}</div>
              ))}
            </div>
            <div className="rounded border bg-white p-3">
              <b>Theo Bloom</b>
              {Object.entries(stats.by_bloom).map(([k, v]: any) => (
                <div key={k}>{k}: {v}</div>
              ))}
            </div>
            <div className="rounded border bg-white p-3">
              <b>Theo CLO</b>
              {Object.entries(stats.by_clo).map(([k, v]: any) => (
                <div key={k}>CLO id {k}: {v}</div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Ma trận & sinh đề */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Ma trận đề thi & sinh đề</h2>
        {matrices.map((m) => (
          <div key={m.id} className="mb-2 rounded border bg-white p-3 text-sm">
            <div className="flex items-center justify-between">
              <b>{m.name}</b>
              <button
                onClick={() => generate(m.id)}
                className="rounded bg-indigo-600 px-3 py-1 text-white"
              >
                Sinh đề
              </button>
            </div>
            {genExamErr && genExamErr.matrixId === m.id && (
              <div className="my-2 rounded border border-red-300 bg-red-50 p-3 text-sm">
                <p className="whitespace-pre-line text-red-700">{genExamErr.message}</p>
                <button
                  onClick={() => generate(m.id, true)}
                  className="mt-2 rounded bg-amber-600 px-3 py-1 text-xs text-white hover:bg-amber-700"
                >
                  Vẫn sinh đề với câu có sẵn
                </button>
              </div>
            )}
            <table className="mt-2 w-full text-xs">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1">CLO</th>
                  <th className="border p-1">Bloom</th>
                  <th className="border p-1">Độ khó</th>
                  <th className="border p-1">Số câu</th>
                  <th className="border p-1">Điểm/câu</th>
                </tr>
              </thead>
              <tbody>
                {m.cells.map((c: any, i: number) => (
                  <tr key={i}>
                    <td className="border p-1 text-center">{c.clo_id}</td>
                    <td className="border p-1 text-center">{c.bloom_level}</td>
                    <td className="border p-1 text-center">{c.difficulty}</td>
                    <td className="border p-1 text-center">{c.count}</td>
                    <td className="border p-1 text-center">{c.points_each}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>

      {/* Đề thi đã sinh */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Đề thi đã tạo</h2>
        {exams.map((e) => (
          <div key={e.id} className="mb-2 rounded border bg-white p-3 text-sm">
            <div className="flex items-center justify-between">
              <span>
                <b>{e.name}</b> v{e.version} — {e.total_points} điểm — {e.status}
              </span>
              <div className="flex gap-2">
                <Link href={`/exams/${e.id}`} className="rounded bg-indigo-600 px-3 py-1 text-white">
                  Mở đề / chỉnh sửa →
                </Link>
                <button
                  onClick={async () => setBlueprint(await api(`/api/exams/${e.id}/blueprint`))}
                  className="rounded bg-slate-100 px-3 py-1 hover:bg-slate-200"
                >
                  Bảng đặc tả
                </button>
              </div>
            </div>
          </div>
        ))}
        {exams.length === 0 && <p className="text-slate-500">Chưa có đề thi.</p>}
        {blueprint && (
          <div className="mt-2 rounded border bg-white p-3 text-xs">
            <b>Bảng đặc tả đề #{blueprint.exam_id}</b> — {blueprint.total_points} điểm
            <table className="mt-2 w-full">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1">#</th>
                  <th className="border p-1">CLO</th>
                  <th className="border p-1">Bloom</th>
                  <th className="border p-1">Độ khó</th>
                  <th className="border p-1">Điểm</th>
                  <th className="border p-1">Đáp án</th>
                </tr>
              </thead>
              <tbody>
                {blueprint.items.map((it: any) => (
                  <tr key={it.order}>
                    <td className="border p-1 text-center">{it.order}</td>
                    <td className="border p-1 text-center">{it.clo_id}</td>
                    <td className="border p-1 text-center">{it.bloom_level}</td>
                    <td className="border p-1 text-center">{it.difficulty}</td>
                    <td className="border p-1 text-center">{it.points}</td>
                    <td className="border p-1 text-center">{it.answer}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
