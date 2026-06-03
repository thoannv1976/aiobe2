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
  // Import đề cương đã có
  const [importBusy, setImportBusy] = useState(false);
  const [importParsed, setImportParsed] = useState<any>(null);
  const [importDraft, setImportDraft] = useState<any>(null);

  async function load() {
    // Mỗi phần load độc lập: một API lỗi không làm trắng cả trang.
    const safe = async (fn: () => Promise<void>) => {
      try {
        await fn();
      } catch (e: any) {
        setErr((prev) => prev || e.message);
      }
    };
    await safe(async () => {
      const ol = await api(`/api/courses/${id}/outlines`);
      setOutlines(ol);
      const al: Record<number, any> = {};
      for (const o of ol) {
        try {
          al[o.id] = await api(`/api/outlines/${o.id}/alignment`);
        } catch {
          /* bỏ qua alignment lỗi của 1 phiên bản */
        }
      }
      setAlignment(al);
    });
    await safe(async () => setQuestions(await api(`/api/courses/${id}/questions`)));
    await safe(async () => setStats(await api(`/api/courses/${id}/questions/stats`)));
    await safe(async () => setMatrices(await api(`/api/courses/${id}/matrices`)));
    await safe(async () => setExams(await api(`/api/courses/${id}/exams`)));
    await safe(async () => setTemplates(await api(`/api/documents?type=outline_template`)));
    await safe(async () => setAunqaDocs(await api(`/api/documents?type=aunqa_standard`)));
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

  // ----- Import đề cương ĐÃ CÓ (Phase 1): upload → AI bóc tách → rà soát → lưu draft -----
  async function importOutlineFile(file: File) {
    setErr("");
    setImportBusy(true);
    setImportParsed(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiUpload(`/api/courses/${id}/parse-outline`, fd);
      setImportParsed(res);
      setImportDraft(JSON.parse(JSON.stringify(res.outline))); // bản chỉnh tay
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setImportBusy(false);
    }
  }

  function setCloPlos(idx: number, codesText: string) {
    setImportDraft((d: any) => {
      const next = { ...d, clos: [...d.clos] };
      const codes = codesText.split(",").map((s) => s.trim()).filter(Boolean);
      const old = next.clos[idx].plos || [];
      const lvl: Record<string, string> = {};
      for (const m of old) lvl[m.plo_code] = m.level || "R";
      next.clos[idx] = { ...next.clos[idx], plos: codes.map((c) => ({ plo_code: c, level: lvl[c] || "R" })) };
      return next;
    });
  }

  function setCloField(idx: number, key: string, val: string) {
    setImportDraft((d: any) => {
      const next = { ...d, clos: [...d.clos] };
      next.clos[idx] = { ...next.clos[idx], [key]: val };
      return next;
    });
  }

  async function saveImport() {
    setErr("");
    setImportBusy(true);
    try {
      const o = await api(`/api/courses/${id}/import-outline`, {
        method: "POST",
        body: JSON.stringify({ outline: importDraft, source_name: importParsed?.original_name || "" }),
      });
      // Sang trang đề cương và tự chạy đánh giá chất lượng (Phase 2).
      window.location.href = `/outlines/${o.id}?review=1`;
    } catch (e: any) {
      setErr(e.message);
      setImportBusy(false);
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
            <label className={`cursor-pointer rounded bg-amber-500 px-3 py-1 text-white ${importBusy ? "opacity-50" : ""}`}
              title="Tải lên đề cương đã có (PDF/DOCX) để AI bóc tách, đánh giá và hoàn thiện">
              {importBusy ? "Đang xử lý..." : "⬆ Import đề cương đã có"}
              <input type="file" accept=".pdf,.docx,.txt" className="hidden" disabled={importBusy}
                onChange={(e) => e.target.files?.[0] && importOutlineFile(e.target.files[0])} />
            </label>
          </div>
        </div>

        {/* Màn hình rà soát kết quả bóc tách đề cương đã có (Phase 1) */}
        {importParsed && importDraft && (
          <div className="mb-4 rounded border border-amber-300 bg-amber-50 p-4 text-sm">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <b>Rà soát đề cương vừa bóc tách: {importParsed.original_name}</b>
              <span className="text-xs text-slate-500">
                Mã học phần phát hiện: {importParsed.detected_course_code || "—"}
              </span>
            </div>
            {(importParsed.unmatched_plos?.length > 0 || importParsed.clos_without_plo?.length > 0) && (
              <div className="mb-2 rounded border border-amber-400 bg-amber-100 p-2 text-xs text-amber-900">
                {importParsed.unmatched_plos?.length > 0 && (
                  <div>⚠ Mã PLO không thuộc chương trình (đã bỏ, hãy gán lại): {importParsed.unmatched_plos.join(", ")}</div>
                )}
                {importParsed.clos_without_plo?.length > 0 && (
                  <div>⚠ CLO chưa ánh xạ PLO: {importParsed.clos_without_plo.join(", ")} — hãy nhập mã PLO bên dưới.</div>
                )}
              </div>
            )}
            <label className="block text-xs font-medium">Mô tả học phần</label>
            <textarea value={importDraft.description || ""} rows={2}
              onChange={(e) => setImportDraft((d: any) => ({ ...d, description: e.target.value }))}
              className="mb-3 w-full rounded border p-2 text-xs" />
            <table className="w-full border bg-white text-xs">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1">CLO</th>
                  <th className="border p-1 text-left">Mô tả</th>
                  <th className="border p-1">Bloom</th>
                  <th className="border p-1">PLO (mã, cách nhau dấu phẩy)</th>
                </tr>
              </thead>
              <tbody>
                {importDraft.clos.map((c: any, i: number) => (
                  <tr key={i}>
                    <td className="border p-1 text-center font-medium">{c.code}</td>
                    <td className="border p-1">
                      <input value={c.description || ""} onChange={(e) => setCloField(i, "description", e.target.value)}
                        className="w-full rounded border p-1" />
                    </td>
                    <td className="border p-1">
                      <select value={c.bloom_level || ""} onChange={(e) => setCloField(i, "bloom_level", e.target.value)}
                        className="rounded border p-1">
                        {["", "remember", "understand", "apply", "analyze", "evaluate", "create"].map((b) => (
                          <option key={b} value={b}>{b || "—"}</option>
                        ))}
                      </select>
                    </td>
                    <td className="border p-1">
                      <input
                        defaultValue={(c.plos || []).map((m: any) => m.plo_code).join(", ")}
                        onBlur={(e) => setCloPlos(i, e.target.value)}
                        placeholder="VD: PLO1, PLO3"
                        className={`w-full rounded border p-1 ${(c.plos || []).length === 0 ? "border-amber-400 bg-amber-50" : ""}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-2 text-xs text-slate-600">
              Bóc tách được <b>{importDraft.clos.length}</b> CLO ·{" "}
              <b>{(importDraft.assessments || []).length}</b> cấu phần đánh giá ·{" "}
              <b>{(importDraft.lessons || []).length}</b> buổi/tuần. Các phần này sẽ được lưu kèm.
            </div>
            <div className="mt-3 flex gap-2">
              <button onClick={saveImport} disabled={importBusy}
                className="rounded bg-amber-600 px-4 py-2 font-medium text-white disabled:opacity-50">
                {importBusy ? "Đang lưu..." : "Lưu thành đề cương draft & đánh giá"}
              </button>
              <button onClick={() => { setImportParsed(null); setImportDraft(null); }}
                className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200">Huỷ</button>
            </div>
          </div>
        )}
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
