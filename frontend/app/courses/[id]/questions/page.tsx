"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, apiUpload, API_BASE, getToken } from "@/lib/api";

const BLOOM: Record<string, string> = {
  remember: "Nhớ",
  understand: "Hiểu",
  apply: "Vận dụng",
  analyze: "Phân tích",
  evaluate: "Đánh giá",
  create: "Sáng tạo",
};
const DIFFICULTY: Record<string, string> = {
  easy: "Dễ",
  medium: "Trung bình",
  hard: "Khó",
};
const TYPE: Record<string, string> = {
  mcq_single: "TN 1 đáp án",
  mcq_multi: "TN nhiều đáp án",
  fill_blank: "Điền khuyết",
  short_answer: "Tự luận ngắn",
  essay: "Tự luận",
  exercise: "Bài tập",
};

interface Clo {
  id: number;
  code: string;
  description: string;
}

interface Question {
  id: number;
  course_id: number;
  clo_id: number | null;
  bloom_level: string;
  difficulty: string;
  type: string;
  content: string;
  options_json: string[];
  answer: string;
  points: number;
  explanation: string;
  tags_json: string[];
}

interface Stats {
  total: number;
  by_clo: Record<string, number>;
  by_bloom: Record<string, number>;
  by_difficulty: Record<string, number>;
  by_clo_bloom: Record<string, number>;
}

interface MatrixCell {
  clo_id: number | null;
  bloom_level: string;
  difficulty: string;
  count: number;
  points_each: number;
}

interface Matrix {
  id: number;
  course_id: number;
  name: string;
  cells: MatrixCell[];
}

interface QForm {
  clo_id: string;
  bloom_level: string;
  difficulty: string;
  type: string;
  content: string;
  answer: string;
  points: string;
  explanation: string;
  options: string;
}

const emptyForm: QForm = {
  clo_id: "",
  bloom_level: "remember",
  difficulty: "easy",
  type: "mcq_single",
  content: "",
  answer: "",
  points: "1",
  explanation: "",
  options: "",
};

const emptyCell: MatrixCell = {
  clo_id: null,
  bloom_level: "remember",
  difficulty: "easy",
  count: 1,
  points_each: 1,
};

export default function QuestionsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [clos, setClos] = useState<Clo[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [matrices, setMatrices] = useState<Matrix[]>([]);
  const [err, setErr] = useState("");

  const [form, setForm] = useState<QForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [matrixName, setMatrixName] = useState("");
  const [cells, setCells] = useState<MatrixCell[]>([{ ...emptyCell }]);
  const [matrixGenBusy, setMatrixGenBusy] = useState(false);
  const [matrixGenMsg, setMatrixGenMsg] = useState("");
  const [matrixPoints, setMatrixPoints] = useState<number>(100);

  const [file, setFile] = useState<File | null>(null);

  // Sinh câu hỏi bằng AI
  const [genBusy, setGenBusy] = useState(false);
  const [genNum, setGenNum] = useState<number>(3);
  const [genType, setGenType] = useState<string>("mcq_single");
  const [genCloIds, setGenCloIds] = useState<number[]>([]);
  const [cloChapters, setCloChapters] = useState<Record<number, string[]>>({});
  const [genMsg, setGenMsg] = useState("");

  async function generateQuestions() {
    setErr("");
    setGenMsg("");
    setGenBusy(true);
    try {
      const r = await api(`/api/courses/${id}/questions/generate`, {
        method: "POST",
        body: JSON.stringify({
          clo_ids: genCloIds,
          num_per_clo: genNum,
          question_type: genType,
        }),
      });
      setGenMsg(`Đã tạo ${r.created} câu hỏi. Hãy rà soát/chỉnh sửa bên dưới.`);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  async function load() {
    try {
      const ol: any[] = await api(`/api/courses/${id}/outlines`);
      if (ol.length > 0) {
        const latest = ol.reduce((a, b) => (b.version > a.version ? b : a));
        setClos(await api(`/api/outlines/${latest.id}/clos`));
      } else {
        setClos([]);
      }
      setQuestions(await api(`/api/courses/${id}/questions`));
      setStats(await api(`/api/courses/${id}/questions/stats`));
      setMatrices(await api(`/api/courses/${id}/matrices`));
      // Gom các chương giáo trình gắn theo từng CLO (để hiển thị nguồn ngữ liệu).
      try {
        const tbs: any[] = await api(`/api/courses/${id}/textbooks`);
        const map: Record<number, string[]> = {};
        for (const tb of tbs) {
          const chs: any[] = await api(`/api/textbooks/${tb.id}/chapters`);
          for (const ch of chs) {
            for (const cid of ch.clo_ids || []) {
              (map[cid] = map[cid] || []).push(`${tb.title} › ${ch.title}`);
            }
          }
        }
        setCloChapters(map);
      } catch {
        setCloChapters({});
      }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function cloLabel(cloId: number | string | null): string {
    if (cloId === null || cloId === "") return "—";
    const c = clos.find((x) => String(x.id) === String(cloId));
    return c ? c.code : `CLO #${cloId}`;
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
  }

  function editQuestion(q: Question) {
    setEditingId(q.id);
    setForm({
      clo_id: q.clo_id != null ? String(q.clo_id) : "",
      bloom_level: q.bloom_level,
      difficulty: q.difficulty,
      type: q.type,
      content: q.content,
      answer: q.answer ?? "",
      points: String(q.points ?? 0),
      explanation: q.explanation ?? "",
      options: (q.options_json ?? []).join("\n"),
    });
  }

  async function saveQuestion() {
    setErr("");
    const payload = {
      clo_id: form.clo_id ? Number(form.clo_id) : null,
      bloom_level: form.bloom_level,
      difficulty: form.difficulty,
      type: form.type,
      content: form.content,
      options_json: form.options
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
      answer: form.answer,
      points: Number(form.points) || 0,
      explanation: form.explanation,
      tags_json: [] as string[],
    };
    try {
      if (editingId) {
        await api(`/api/questions/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/api/courses/${id}/questions`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      resetForm();
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteQuestion(qid: number) {
    setErr("");
    try {
      await api(`/api/questions/${qid}`, { method: "DELETE" });
      if (editingId === qid) resetForm();
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function importCsv() {
    setErr("");
    if (!file) {
      setErr("Vui lòng chọn file CSV.");
      return;
    }
    try {
      const fd = new FormData();
      fd.append("file", file);
      await apiUpload(`/api/courses/${id}/questions/import`, fd);
      setFile(null);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function downloadExport(path: string, filename: string) {
    setErr("");
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}${path}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Tải xuống thất bại");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  function updateCell(idx: number, patch: Partial<MatrixCell>) {
    setCells((prev) => prev.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }

  function addCell() {
    setCells((prev) => [...prev, { ...emptyCell }]);
  }

  function removeCell(idx: number) {
    setCells((prev) => prev.filter((_, i) => i !== idx));
  }

  async function generateMatrixAI() {
    setErr("");
    setMatrixGenMsg("");
    setMatrixGenBusy(true);
    try {
      await api(`/api/courses/${id}/matrices/generate`, {
        method: "POST",
        body: JSON.stringify({ total_points: matrixPoints, name: matrixName }),
      });
      setMatrixGenMsg("Đã tạo ma trận đề thi bằng AI (bám ngân hàng hiện có). Hãy rà soát bên trên.");
      setMatrices(await api(`/api/courses/${id}/matrices`));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setMatrixGenBusy(false);
    }
  }

  async function createMatrix() {
    setErr("");
    if (!matrixName.trim()) {
      setErr("Vui lòng nhập tên ma trận.");
      return;
    }
    try {
      await api(`/api/courses/${id}/matrices`, {
        method: "POST",
        body: JSON.stringify({
          name: matrixName,
          cells: cells.map((c) => ({
            clo_id: c.clo_id != null ? Number(c.clo_id) : null,
            bloom_level: c.bloom_level,
            difficulty: c.difficulty,
            count: Number(c.count) || 0,
            points_each: Number(c.points_each) || 0,
          })),
        }),
      });
      setMatrixName("");
      setCells([{ ...emptyCell }]);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Ngân hàng câu hỏi — Học phần #{id}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() =>
              downloadExport(
                `/api/courses/${id}/questions/export`,
                `questions_${id}.csv`
              )
            }
            className="rounded bg-slate-100 px-3 py-2 text-sm hover:bg-slate-200"
          >
            Export CSV
          </button>
          <button
            onClick={() =>
              downloadExport(
                `/api/courses/${id}/questions/export-xlsx`,
                `questions_${id}.xlsx`
              )
            }
            className="rounded bg-slate-100 px-3 py-2 text-sm hover:bg-slate-200"
          >
            Export Excel
          </button>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
          <button
            onClick={importCsv}
            className="rounded bg-indigo-600 px-4 py-2 text-sm text-white"
          >
            Import CSV
          </button>
        </div>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* Thống kê */}
      {stats && (
        <section className="grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded border bg-white p-4 shadow-sm">
            <b>Theo CLO (tổng {stats.total})</b>
            <div className="mt-2 space-y-1">
              {clos.map((c) => {
                const cnt = stats.by_clo[String(c.id)] ?? 0;
                return (
                  <div
                    key={c.id}
                    className={cnt === 0 ? "font-semibold text-red-600" : ""}
                  >
                    {c.code}: {cnt}
                    {cnt === 0 && " ⚠ (lỗ hổng)"}
                  </div>
                );
              })}
              {clos.length === 0 && (
                <div className="text-slate-500">Chưa có CLO.</div>
              )}
            </div>
          </div>
          <div className="rounded border bg-white p-4 shadow-sm">
            <b>Theo Bloom</b>
            <div className="mt-2 space-y-1">
              {Object.entries(stats.by_bloom).map(([k, v]) => (
                <div key={k}>
                  {BLOOM[k] ?? k}: {v}
                </div>
              ))}
              {Object.keys(stats.by_bloom).length === 0 && (
                <div className="text-slate-500">—</div>
              )}
            </div>
          </div>
          <div className="rounded border bg-white p-4 shadow-sm">
            <b>Theo độ khó</b>
            <div className="mt-2 space-y-1">
              {Object.entries(stats.by_difficulty).map(([k, v]) => (
                <div key={k}>
                  {DIFFICULTY[k] ?? k}: {v}
                </div>
              ))}
              {Object.keys(stats.by_difficulty).length === 0 && (
                <div className="text-slate-500">—</div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Sinh câu hỏi bằng AI */}
      <section className="rounded-lg border border-green-200 bg-green-50/40 p-4">
        <h2 className="mb-1 text-lg font-semibold">✨ Tạo câu hỏi bằng AI</h2>
        <p className="mb-3 text-sm text-slate-600">
          AI soạn câu hỏi bám theo CLO của đề cương (gắn CLO + Bloom + độ khó) và <b>nội dung
          các chương giáo trình gắn với CLO đó</b> (nếu có). Câu hỏi được ghi vào ngân hàng —
          hãy rà soát/chỉnh sửa sau khi tạo.
        </p>
        {clos.length === 0 ? (
          <p className="text-sm text-amber-700">
            ⚠ Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước khi dùng chức năng này.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Số câu / CLO
              <input
                type="number"
                min={1}
                max={20}
                value={genNum}
                onChange={(e) => setGenNum(Number(e.target.value) || 1)}
                className="mt-1 block w-24 rounded border p-1"
              />
            </label>
            <label className="text-sm">
              Loại câu hỏi
              <select
                value={genType}
                onChange={(e) => setGenType(e.target.value)}
                className="mt-1 block rounded border p-1"
              >
                {Object.entries(TYPE).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <div className="text-sm">
              <div className="mb-1">CLO áp dụng <span className="text-xs text-slate-400">(bỏ trống = tất cả CLO)</span></div>
              <div className="max-h-44 min-w-[20rem] space-y-1 overflow-auto rounded border bg-white p-2">
                {clos.map((c) => {
                  const chs = cloChapters[c.id] || [];
                  return (
                    <label key={c.id} className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={genCloIds.includes(c.id)}
                        onChange={(e) =>
                          setGenCloIds(
                            e.target.checked
                              ? [...genCloIds, c.id]
                              : genCloIds.filter((x) => x !== c.id)
                          )
                        }
                      />
                      <span>
                        <b>{c.code}</b>
                        {chs.length > 0 ? (
                          <span className="ml-1 text-xs text-green-700">
                            📚 {chs.length} chương: {chs.join("; ")}
                          </span>
                        ) : (
                          <span className="ml-1 text-xs text-amber-600">
                            ⚠ chưa có chương giáo trình gắn — AI ra đề theo mô tả CLO
                          </span>
                        )}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
            <button
              onClick={generateQuestions}
              disabled={genBusy}
              className="rounded bg-green-600 px-4 py-2 text-white disabled:opacity-50"
            >
              {genBusy ? "AI đang soạn..." : "Tạo câu hỏi bằng AI"}
            </button>
          </div>
        )}
        {genMsg && <p className="mt-2 text-sm text-green-700">{genMsg}</p>}
      </section>

      {/* Form thêm/sửa câu hỏi */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">
          {editingId ? `Sửa câu hỏi #${editingId}` : "Thêm câu hỏi"}
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            CLO
            <select
              value={form.clo_id}
              onChange={(e) => setForm({ ...form, clo_id: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            >
              <option value="">— Không gắn —</option>
              {clos.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Mức Bloom
            <select
              value={form.bloom_level}
              onChange={(e) => setForm({ ...form, bloom_level: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            >
              {Object.entries(BLOOM).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Độ khó
            <select
              value={form.difficulty}
              onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            >
              {Object.entries(DIFFICULTY).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Loại
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            >
              {Object.entries(TYPE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm sm:col-span-2">
            Nội dung
            <textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              rows={3}
              className="mt-1 w-full rounded border p-2"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            Phương án (mỗi dòng 1 phương án)
            <textarea
              value={form.options}
              onChange={(e) => setForm({ ...form, options: e.target.value })}
              rows={3}
              className="mt-1 w-full rounded border p-2"
            />
          </label>
          <label className="text-sm">
            Đáp án
            <input
              value={form.answer}
              onChange={(e) => setForm({ ...form, answer: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            />
          </label>
          <label className="text-sm">
            Điểm
            <input
              type="number"
              value={form.points}
              onChange={(e) => setForm({ ...form, points: e.target.value })}
              className="mt-1 w-full rounded border p-2"
            />
          </label>
          <label className="text-sm sm:col-span-2">
            Giải thích
            <textarea
              value={form.explanation}
              onChange={(e) =>
                setForm({ ...form, explanation: e.target.value })
              }
              rows={2}
              className="mt-1 w-full rounded border p-2"
            />
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={saveQuestion}
            className="rounded bg-indigo-600 px-4 py-2 text-white"
          >
            Lưu
          </button>
          {editingId && (
            <button
              onClick={resetForm}
              className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200"
            >
              Hủy
            </button>
          )}
        </div>
      </section>

      {/* Bảng câu hỏi */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">
          Danh sách câu hỏi ({questions.length})
        </h2>
        <div className="overflow-x-auto rounded border bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">#</th>
                <th className="border p-2 text-left">Nội dung</th>
                <th className="border p-2">CLO</th>
                <th className="border p-2">Bloom</th>
                <th className="border p-2">Độ khó</th>
                <th className="border p-2">Loại</th>
                <th className="border p-2">Điểm</th>
                <th className="border p-2">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.id}>
                  <td className="border p-2 text-center">{q.id}</td>
                  <td className="border p-2">
                    {q.content.length > 80
                      ? q.content.slice(0, 80) + "…"
                      : q.content}
                  </td>
                  <td className="border p-2 text-center">{cloLabel(q.clo_id)}</td>
                  <td className="border p-2 text-center">
                    {BLOOM[q.bloom_level] ?? q.bloom_level}
                  </td>
                  <td className="border p-2 text-center">
                    {DIFFICULTY[q.difficulty] ?? q.difficulty}
                  </td>
                  <td className="border p-2 text-center">
                    {TYPE[q.type] ?? q.type}
                  </td>
                  <td className="border p-2 text-center">{q.points}</td>
                  <td className="border p-2 text-center">
                    <div className="flex justify-center gap-2">
                      <button
                        onClick={() => editQuestion(q)}
                        className="rounded bg-slate-100 px-2 py-1 hover:bg-slate-200"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => deleteQuestion(q.id)}
                        className="rounded bg-red-100 px-2 py-1 text-red-700 hover:bg-red-200"
                      >
                        Xóa
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {questions.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="border p-4 text-center text-slate-500"
                  >
                    Chưa có câu hỏi.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Ma trận đề thi */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Ma trận đề thi</h2>

        {/* Tạo ma trận bằng AI (bám ngân hàng câu hỏi hiện có) */}
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50/40 p-4">
          <h3 className="text-sm font-semibold">✨ Tạo ma trận đề thi bằng AI</h3>
          <p className="mb-2 text-xs text-slate-600">
            AI thiết kế ma trận (CLO × Bloom × độ khó) <b>bám sát số câu sẵn có trong ngân hàng</b>,
            nên đề sinh ra sẽ đủ câu. Hãy rà soát/sửa sau khi tạo.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Tên ma trận (tùy chọn)
              <input
                value={matrixName}
                onChange={(e) => setMatrixName(e.target.value)}
                className="mt-1 block w-56 rounded border p-1"
                placeholder="VD: Ma trận cuối kỳ"
              />
            </label>
            <label className="text-sm">
              Tổng điểm
              <input
                type="number"
                value={matrixPoints}
                onChange={(e) => setMatrixPoints(Number(e.target.value) || 100)}
                className="mt-1 block w-24 rounded border p-1"
              />
            </label>
            <button
              onClick={generateMatrixAI}
              disabled={matrixGenBusy}
              className="rounded bg-green-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {matrixGenBusy ? "AI đang tạo..." : "Tạo ma trận bằng AI"}
            </button>
          </div>
          {matrixGenMsg && <p className="mt-2 text-sm text-green-700">{matrixGenMsg}</p>}
        </div>

        <div className="mb-4 space-y-2">
          {matrices.map((m) => (
            <div key={m.id} className="rounded border bg-white p-4 shadow-sm text-sm">
              <b>{m.name}</b> — {m.cells.length} ô
            </div>
          ))}
          {matrices.length === 0 && (
            <p className="text-slate-500">Chưa có ma trận.</p>
          )}
        </div>

        {/* Form tạo ma trận */}
        <div className="rounded border bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-semibold">Tạo ma trận mới</h3>
          <label className="text-sm">
            Tên ma trận
            <input
              value={matrixName}
              onChange={(e) => setMatrixName(e.target.value)}
              className="mt-1 w-full rounded border p-2 sm:w-1/2"
            />
          </label>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-2">CLO</th>
                  <th className="border p-2">Bloom</th>
                  <th className="border p-2">Độ khó</th>
                  <th className="border p-2">Số câu</th>
                  <th className="border p-2">Điểm/câu</th>
                  <th className="border p-2"></th>
                </tr>
              </thead>
              <tbody>
                {cells.map((c, i) => (
                  <tr key={i}>
                    <td className="border p-2">
                      <select
                        value={c.clo_id ?? ""}
                        onChange={(e) =>
                          updateCell(i, {
                            clo_id: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                        className="w-full rounded border p-1"
                      >
                        <option value="">— Không gắn —</option>
                        {clos.map((cl) => (
                          <option key={cl.id} value={cl.id}>
                            {cl.code}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="border p-2">
                      <select
                        value={c.bloom_level}
                        onChange={(e) =>
                          updateCell(i, { bloom_level: e.target.value })
                        }
                        className="w-full rounded border p-1"
                      >
                        {Object.entries(BLOOM).map(([k, v]) => (
                          <option key={k} value={k}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="border p-2">
                      <select
                        value={c.difficulty}
                        onChange={(e) =>
                          updateCell(i, { difficulty: e.target.value })
                        }
                        className="w-full rounded border p-1"
                      >
                        {Object.entries(DIFFICULTY).map(([k, v]) => (
                          <option key={k} value={k}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="border p-2">
                      <input
                        type="number"
                        value={c.count}
                        onChange={(e) =>
                          updateCell(i, { count: Number(e.target.value) })
                        }
                        className="w-20 rounded border p-1"
                      />
                    </td>
                    <td className="border p-2">
                      <input
                        type="number"
                        value={c.points_each}
                        onChange={(e) =>
                          updateCell(i, { points_each: Number(e.target.value) })
                        }
                        className="w-20 rounded border p-1"
                      />
                    </td>
                    <td className="border p-2 text-center">
                      <button
                        onClick={() => removeCell(i)}
                        className="rounded bg-red-100 px-2 py-1 text-red-700 hover:bg-red-200"
                      >
                        Bớt
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex gap-2">
            <button
              onClick={addCell}
              className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200"
            >
              + Thêm dòng
            </button>
            <button
              onClick={createMatrix}
              className="rounded bg-indigo-600 px-4 py-2 text-white"
            >
              Tạo ma trận
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
