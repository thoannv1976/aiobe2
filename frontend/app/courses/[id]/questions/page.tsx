"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, apiPaged, apiUpload, API_BASE, getToken } from "@/lib/api";

const Q_PAGE_SIZE = 50;

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

const STATUS_VI: Record<string, string> = {
  draft: "Nháp",
  review: "Chờ duyệt",
  approved: "Đã duyệt",
  archived: "Lưu trữ",
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
  review_status?: string;
  review_note?: string | null;
  chapter?: string | null;
  learning_resource?: string | null;
  rubric_json?: { criteria?: any[] };
}

const QSTATUS_VI: Record<string, string> = {
  draft: "Nháp",
  review: "Chờ duyệt",
  approved: "Đã duyệt",
  revise: "Cần sửa",
  retired: "Ngừng dùng",
};

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
  status?: string;
  total_points?: number;
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
  const [qTotal, setQTotal] = useState(0);
  const [qOffset, setQOffset] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);

  async function loadQuestions(offset: number) {
    const { items, total } = await apiPaged<Question>(
      `/api/courses/${id}/questions?limit=${Q_PAGE_SIZE}&offset=${offset}`,
    );
    setQuestions(items);
    setQTotal(total);
    setQOffset(offset);
  }
  const [matrices, setMatrices] = useState<Matrix[]>([]);
  const [err, setErr] = useState("");

  const [form, setForm] = useState<QForm>(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [matrixName, setMatrixName] = useState("");
  const [cells, setCells] = useState<MatrixCell[]>([{ ...emptyCell }]);
  const [matrixGenBusy, setMatrixGenBusy] = useState(false);
  const [matrixGenMsg, setMatrixGenMsg] = useState("");
  const [matrixPoints, setMatrixPoints] = useState<number>(100);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [genAssessmentId, setGenAssessmentId] = useState<string>("");
  const [matrixSummaries, setMatrixSummaries] = useState<Record<number, any>>({});
  const [matrixCoverage, setMatrixCoverage] = useState<Record<number, any>>({});

  async function loadSummary(mid: number) {
    setErr("");
    try {
      const s = await api(`/api/matrices/${mid}/summary`);
      setMatrixSummaries((p) => ({ ...p, [mid]: s }));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function loadCoverage(mid: number) {
    setErr("");
    try {
      const c = await api(`/api/matrices/${mid}/coverage`);
      setMatrixCoverage((p) => ({ ...p, [mid]: c }));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  const [optimizeBusy, setOptimizeBusy] = useState<number | null>(null);
  const [matrixRationale, setMatrixRationale] = useState<Record<number, string>>({});
  // Đánh giá AUN-QA của ma trận (theo mid) + trạng thái bận khi đánh giá.
  const [matrixReviews, setMatrixReviews] = useState<Record<number, any>>({});
  const [matrixReviewBusy, setMatrixReviewBusy] = useState<number | null>(null);

  async function reviewMatrix(mid: number) {
    setErr("");
    setMatrixReviewBusy(mid);
    try {
      const r = await api(`/api/matrices/${mid}/qa-review`);
      setMatrixReviews((p) => ({ ...p, [mid]: r }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setMatrixReviewBusy(null);
    }
  }

  async function optimizeMatrix(mid: number) {
    setErr("");
    setOptimizeBusy(mid);
    try {
      // Bám kết quả đánh giá AUN-QA (nếu đã chạy) để AI khắc phục đúng điểm yếu.
      const r = await api(`/api/matrices/${mid}/optimize`, {
        method: "POST",
        body: JSON.stringify({ qa: matrixReviews[mid] || null }),
      });
      setMatrices(await api(`/api/courses/${id}/matrices`));
      // Tự mở tỷ trọng + giải thích để người dùng thấy kết quả tối ưu ngay.
      await loadSummary(mid);
      setMatrixRationale((p) => ({ ...p, [mid]: r.rationale || "" }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setOptimizeBusy(null);
    }
  }

  async function changeMatrixStatus(mid: number, to: string) {
    setErr("");
    try {
      await api(`/api/matrices/${mid}/status?to=${to}`, { method: "POST" });
      setMatrices(await api(`/api/courses/${id}/matrices`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function duplicateMatrix(mid: number) {
    setErr("");
    try {
      await api(`/api/matrices/${mid}/duplicate`, { method: "POST" });
      setMatrices(await api(`/api/courses/${id}/matrices`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteMatrix(mid: number) {
    if (!confirm("Xóa ma trận này?")) return;
    setErr("");
    try {
      await api(`/api/matrices/${mid}`, { method: "DELETE" });
      setMatrices(await api(`/api/courses/${id}/matrices`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Chỉnh sửa ma trận (kể cả ma trận do AI sinh) -----
  const [editMatrixId, setEditMatrixId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editPoints, setEditPoints] = useState<number>(10);
  const [editCells, setEditCells] = useState<MatrixCell[]>([]);

  function openMatrixEditor(m: Matrix) {
    setEditMatrixId(m.id);
    setEditName(m.name);
    setEditPoints(m.total_points ?? 10);
    setEditCells(
      m.cells.map((c) => ({
        clo_id: c.clo_id,
        bloom_level: c.bloom_level,
        difficulty: c.difficulty,
        count: c.count,
        points_each: c.points_each,
      }))
    );
  }

  async function saveMatrixEdit() {
    if (editMatrixId == null) return;
    setErr("");
    try {
      await api(`/api/matrices/${editMatrixId}`, {
        method: "PUT",
        body: JSON.stringify({
          name: editName,
          total_points: Number(editPoints) || 10,
          cells: editCells.map((c) => ({
            clo_id: c.clo_id != null ? Number(c.clo_id) : null,
            bloom_level: c.bloom_level,
            difficulty: c.difficulty,
            count: Number(c.count) || 0,
            points_each: Number(c.points_each) || 0,
          })),
        }),
      });
      setEditMatrixId(null);
      setMatrices(await api(`/api/courses/${id}/matrices`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

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

  // Đánh giá + nâng cấp ngân hàng câu hỏi bằng AI
  const [qbReview, setQbReview] = useState<any>(null);
  const [qbReviewBusy, setQbReviewBusy] = useState(false);
  const [qbImproveBusy, setQbImproveBusy] = useState(false);
  const [qbImproveMsg, setQbImproveMsg] = useState("");

  async function reviewQuestionBank() {
    setErr("");
    setQbImproveMsg("");
    setQbReview(null);
    setQbReviewBusy(true);
    try {
      setQbReview(await api(`/api/courses/${id}/questions/qa-review`));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setQbReviewBusy(false);
    }
  }

  async function improveQuestionBank() {
    setErr("");
    setQbImproveMsg("");
    setQbImproveBusy(true);
    try {
      // Truyền kết quả đánh giá để AI sửa đúng câu có vấn đề (chưa đánh giá thì backend tự chạy).
      const r = await api(`/api/courses/${id}/questions/improve`, {
        method: "POST",
        body: JSON.stringify({ qa: qbReview || null }),
      });
      setQbImproveMsg(
        `Đã nâng cấp ${r.improved} câu hỏi (đặt lại trạng thái nháp để thẩm định lại).`
      );
      setQbReview(null);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setQbImproveBusy(false);
    }
  }

  async function load() {
    try {
      const ol: any[] = await api(`/api/courses/${id}/outlines`);
      if (ol.length > 0) {
        const latest = ol.reduce((a, b) => (b.version > a.version ? b : a));
        setClos(await api(`/api/outlines/${latest.id}/clos`));
        try {
          setAssessments(await api(`/api/outlines/${latest.id}/assessments`));
        } catch {
          setAssessments([]);
        }
      } else {
        setClos([]);
        setAssessments([]);
      }
      await loadQuestions(0);
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

  // Bước thẩm định tiếp theo cho mỗi trạng thái câu hỏi.
  function reviewNext(status: string): string[] {
    const flow: Record<string, string[]> = {
      draft: ["review"],
      review: ["approved", "revise"],
      revise: ["review"],
      approved: ["retired"],
      retired: ["draft"],
    };
    return flow[status] || [];
  }

  async function reviewQuestion(qid: number, to: string) {
    setErr("");
    try {
      await api(`/api/questions/${qid}/review?to=${to}`, { method: "POST" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  const [approveBusy, setApproveBusy] = useState(false);
  const [approveMsg, setApproveMsg] = useState("");
  const [approveSkipped, setApproveSkipped] = useState<any[]>([]);

  async function approveAll(onlyAi: boolean) {
    setErr("");
    setApproveMsg("");
    setApproveSkipped([]);
    setApproveBusy(true);
    try {
      const r = await api(
        `/api/courses/${id}/questions/approve-all?only_ai=${onlyAi}`,
        { method: "POST" }
      );
      setApproveMsg(
        `Đã duyệt ${r.approved} câu hỏi.` +
          (r.skipped_count ? ` Bỏ qua ${r.skipped_count} câu cần sửa.` : "")
      );
      setApproveSkipped(r.skipped || []);
      await load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setApproveBusy(false);
    }
  }

  async function duplicateQuestion(qid: number) {
    setErr("");
    try {
      await api(`/api/questions/${qid}/duplicate`, { method: "POST" });
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
        body: JSON.stringify({
          total_points: matrixPoints,
          name: matrixName,
          assessment_id: genAssessmentId ? Number(genAssessmentId) : null,
        }),
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
          <div className="card">
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
          <div className="card">
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
          <div className="card">
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
                        {c.description && (
                          <span className="ml-1 text-slate-700">— {c.description}</span>
                        )}
                        {chs.length > 0 ? (
                          <span className="ml-1 block text-xs text-green-700">
                            📚 {chs.length} chương: {chs.join("; ")}
                          </span>
                        ) : (
                          <span className="ml-1 block text-xs text-amber-600">
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
      <section className="card">
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
            className="btn btn-primary"
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
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">
            Danh sách câu hỏi{" "}
            <span className="text-sm font-normal text-slate-500">
              ({qTotal > 0 ? `${qOffset + 1}–${qOffset + questions.length} / ${qTotal}` : questions.length})
            </span>
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            {qTotal > Q_PAGE_SIZE && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => loadQuestions(Math.max(0, qOffset - Q_PAGE_SIZE))}
                  disabled={qOffset === 0}
                  className="rounded border px-2 py-1 text-sm disabled:opacity-40"
                >
                  ‹ Trước
                </button>
                <button
                  onClick={() => loadQuestions(qOffset + Q_PAGE_SIZE)}
                  disabled={qOffset + Q_PAGE_SIZE >= qTotal}
                  className="rounded border px-2 py-1 text-sm disabled:opacity-40"
                >
                  Sau ›
                </button>
              </div>
            )}
            <button
              onClick={reviewQuestionBank}
              disabled={qbReviewBusy}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {qbReviewBusy ? "AI đang đánh giá..." : "✨ Đánh giá chất lượng (AI)"}
            </button>
            <button
              onClick={() => approveAll(true)}
              disabled={approveBusy}
              className="rounded bg-green-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {approveBusy ? "Đang duyệt..." : "✓ Duyệt tất cả câu AI tạo"}
            </button>
            <button
              onClick={() => approveAll(false)}
              disabled={approveBusy}
              className="rounded border border-green-600 px-3 py-1.5 text-sm text-green-700 disabled:opacity-50"
            >
              ✓ Duyệt tất cả câu chưa duyệt
            </button>
          </div>
        </div>
        {qbImproveMsg && <p className="mb-2 text-sm text-indigo-700">{qbImproveMsg}</p>}

        {/* Kết quả đánh giá chất lượng ngân hàng câu hỏi bằng AI */}
        {qbReview && (
          <div className="mb-3 rounded border border-indigo-300 bg-indigo-50 p-3 text-sm">
            <div className="mb-1 flex items-center justify-between">
              <b>Kết quả đánh giá ngân hàng câu hỏi (AI)</b>
              {typeof qbReview.score === "number" && (
                <span className="rounded bg-indigo-600 px-2 py-1 text-white">
                  Điểm: {qbReview.score}/100
                </span>
              )}
            </div>
            {qbReview.summary && <p className="mb-2 italic text-slate-700">{qbReview.summary}</p>}
            {(qbReview.errors || []).map((e: string) => (
              <div key={e} className="text-red-700">✗ {e}</div>
            ))}
            {(qbReview.warnings || []).map((w: string) => (
              <div key={w} className="text-amber-700">⚠ {w}</div>
            ))}
            {(qbReview.question_reviews || []).length > 0 && (
              <table className="mt-2 w-full border bg-white text-xs">
                <thead>
                  <tr className="bg-slate-100">
                    <th className="border p-1">Câu</th>
                    <th className="border p-1">Mức</th>
                    <th className="border p-1 text-left">Vấn đề</th>
                    <th className="border p-1 text-left">Gợi ý sửa</th>
                  </tr>
                </thead>
                <tbody>
                  {qbReview.question_reviews.map((r: any) => (
                    <tr key={r.id}>
                      <td className="border p-1 text-center">#{r.id}</td>
                      <td className="border p-1 text-center">
                        <span className={r.severity === "error" ? "text-red-700" : "text-amber-700"}>
                          {r.severity === "error" ? "Lỗi" : "Cảnh báo"}
                        </span>
                      </td>
                      <td className="border p-1">{(r.issues || []).join("; ") || "—"}</td>
                      <td className="border p-1">{r.suggestion || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-indigo-200 pt-3">
              <button
                onClick={improveQuestionBank}
                disabled={qbImproveBusy}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {qbImproveBusy ? "AI đang nâng cấp..." : "⚡ Nâng cấp câu hỏi bằng AI"}
              </button>
              <span className="text-xs text-slate-500">
                AI viết lại các câu <b>chưa duyệt</b> có vấn đề (bổ sung đáp án/phương án/rubric, sửa Bloom)
                và đặt lại trạng thái nháp để thẩm định lại. Câu <b>Đã duyệt</b> không bị thay đổi.
              </span>
            </div>
          </div>
        )}
        {approveMsg && <p className="mb-2 text-sm text-green-700">{approveMsg}</p>}
        {approveSkipped.length > 0 && (
          <div className="mb-2 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
            <b>Bỏ qua {approveSkipped.length} câu (cần sửa trước khi duyệt):</b>
            {approveSkipped.map((s: any) => (
              <div key={s.id}>• Câu #{s.id}: {s.reason}</div>
            ))}
          </div>
        )}
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
                <th className="border p-2">Trạng thái</th>
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
                    {q.learning_resource && (
                      <div className="mt-1 text-xs text-slate-500">📖 Nguồn: {q.learning_resource}</div>
                    )}
                    {q.rubric_json?.criteria && q.rubric_json.criteria.length > 0 && (
                      <div className="mt-1 text-xs text-green-700">
                        📋 Có rubric ({q.rubric_json.criteria.length} tiêu chí)
                      </div>
                    )}
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
                    {(() => {
                      const st = q.review_status || "draft";
                      const cls = st === "approved" ? "bg-green-100 text-green-700"
                        : st === "review" ? "bg-amber-100 text-amber-700"
                        : st === "revise" ? "bg-orange-100 text-orange-700"
                        : st === "retired" ? "bg-slate-200 text-slate-500"
                        : "bg-slate-100 text-slate-500";
                      return <span className={`rounded px-2 py-0.5 text-xs ${cls}`}>{QSTATUS_VI[st] ?? st}</span>;
                    })()}
                  </td>
                  <td className="border p-2 text-center">
                    <div className="flex flex-wrap justify-center gap-1">
                      {reviewNext(q.review_status || "draft").map((to) => (
                        <button
                          key={to}
                          onClick={() => reviewQuestion(q.id, to)}
                          className="rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200"
                        >
                          → {QSTATUS_VI[to]}
                        </button>
                      ))}
                      <button onClick={() => editQuestion(q)} className="rounded bg-slate-100 px-2 py-1 hover:bg-slate-200">Sửa</button>
                      <button onClick={() => duplicateQuestion(q.id)} className="rounded bg-slate-100 px-2 py-1 hover:bg-slate-200">Nhân bản</button>
                      <button onClick={() => deleteQuestion(q.id)} className="rounded bg-red-100 px-2 py-1 text-red-700 hover:bg-red-200">Xóa</button>
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
            <label className="text-sm">
              Gắn cấu phần đánh giá
              <select
                value={genAssessmentId}
                onChange={(e) => setGenAssessmentId(e.target.value)}
                className="mt-1 block rounded border p-1"
                title="Chỉ dùng CLO mà cấu phần này đánh giá (constructive alignment)"
              >
                <option value="">— Không gắn (toàn bộ CLO) —</option>
                {assessments.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.weight_percent}%)
                  </option>
                ))}
              </select>
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
          {matrices.map((m) => {
            const sm = matrixSummaries[m.id];
            const st = m.status || "draft";
            const next: Record<string, string> = {
              draft: "review", review: "approved", approved: "archived",
            };
            return (
              <div key={m.id} className="rounded border bg-white p-4 text-sm shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <b>{m.name}</b> — {m.cells.length} ô · {m.total_points ?? 10} điểm{" "}
                    <span className={`ml-1 rounded px-2 py-0.5 text-xs ${
                      st === "approved" ? "bg-green-100 text-green-700"
                      : st === "review" ? "bg-amber-100 text-amber-700"
                      : st === "archived" ? "bg-slate-200 text-slate-600"
                      : "bg-slate-100 text-slate-500"}`}>
                      {STATUS_VI[st] ?? st}
                    </span>
                  </span>
                  <div className="flex flex-wrap gap-1">
                    <button onClick={() => loadSummary(m.id)} className="rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200">Tỷ trọng & cảnh báo</button>
                    <button onClick={() => loadCoverage(m.id)} className="rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200">Độ phủ ngân hàng</button>
                    <button onClick={() => reviewMatrix(m.id)} disabled={matrixReviewBusy === m.id} className="rounded bg-indigo-600 px-2 py-1 text-xs text-white disabled:opacity-50">
                      {matrixReviewBusy === m.id ? "Đang đánh giá..." : "✨ Đánh giá (AI)"}
                    </button>
                    {st !== "approved" && st !== "archived" && (
                      <button onClick={() => openMatrixEditor(m)} className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-700 hover:bg-amber-200">Sửa</button>
                    )}
                    {st !== "approved" && st !== "archived" && (
                      <button onClick={() => optimizeMatrix(m.id)} disabled={optimizeBusy === m.id} className="rounded bg-green-600 px-2 py-1 text-xs text-white disabled:opacity-50">
                        {optimizeBusy === m.id ? "Đang tối ưu..." : "⚡ Nâng cấp/Tối ưu AI"}
                      </button>
                    )}
                    {next[st] && (
                      <button onClick={() => changeMatrixStatus(m.id, next[st])} className="rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200">
                        → {STATUS_VI[next[st]]}
                      </button>
                    )}
                    <button onClick={() => duplicateMatrix(m.id)} className="rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200">Nhân bản</button>
                    <button onClick={() => deleteMatrix(m.id)} className="rounded bg-red-100 px-2 py-1 text-xs text-red-700 hover:bg-red-200">Xóa</button>
                  </div>
                </div>

                {/* Kết quả đánh giá AUN-QA của ma trận bằng AI */}
                {matrixReviews[m.id] && (
                  <div className="mt-3 rounded border border-indigo-300 bg-indigo-50 p-3 text-xs">
                    <div className="mb-1 flex items-center justify-between">
                      <b>Đánh giá AUN-QA (AI)</b>
                      {typeof matrixReviews[m.id].score === "number" && (
                        <span className="rounded bg-indigo-600 px-2 py-0.5 text-white">
                          Điểm: {matrixReviews[m.id].score}/100
                        </span>
                      )}
                    </div>
                    {matrixReviews[m.id].summary && (
                      <p className="mb-1 italic text-slate-700">{matrixReviews[m.id].summary}</p>
                    )}
                    {(matrixReviews[m.id].errors || []).map((e: string) => (
                      <div key={e} className="text-red-700">✗ {e}</div>
                    ))}
                    {(matrixReviews[m.id].warnings || []).map((w: string) => (
                      <div key={w} className="text-amber-700">⚠ {w}</div>
                    ))}
                    {(matrixReviews[m.id].suggestions || []).map((s: string) => (
                      <div key={s} className="text-slate-600">• {s}</div>
                    ))}
                    {st !== "approved" && st !== "archived" && (
                      <div className="mt-2 border-t border-indigo-200 pt-2 text-slate-500">
                        Bấm <b>⚡ Nâng cấp/Tối ưu AI</b> ở trên để AI khắc phục các điểm này (cân điểm,
                        phủ CLO, cân đối Bloom — bám ngân hàng câu Đã duyệt).
                      </div>
                    )}
                  </div>
                )}

                {/* Trình sửa ma trận inline (kể cả ma trận do AI sinh) */}
                {editMatrixId === m.id && (
                  <div className="mt-3 rounded border border-amber-200 bg-amber-50/40 p-3 text-xs">
                    <div className="mb-2 flex flex-wrap items-end gap-2">
                      <label>Tên ma trận
                        <input value={editName} onChange={(e) => setEditName(e.target.value)} className="ml-1 rounded border p-1" />
                      </label>
                      <label>Tổng điểm
                        <input type="number" value={editPoints} onChange={(e) => setEditPoints(Number(e.target.value) || 10)} className="ml-1 w-20 rounded border p-1" />
                      </label>
                    </div>
                    <table className="w-full">
                      <thead>
                        <tr className="bg-slate-100">
                          <th className="border p-1">CLO</th><th className="border p-1">Bloom</th>
                          <th className="border p-1">Độ khó</th><th className="border p-1">Số câu</th>
                          <th className="border p-1">Điểm/câu</th><th className="border p-1"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {editCells.map((c, i) => (
                          <tr key={i}>
                            <td className="border p-1">
                              <select value={c.clo_id ?? ""} onChange={(e) => {
                                const v = [...editCells]; v[i] = { ...c, clo_id: e.target.value ? Number(e.target.value) : null }; setEditCells(v);
                              }} className="rounded border p-1">
                                <option value="">—</option>
                                {clos.map((cl) => <option key={cl.id} value={cl.id}>{cl.code}</option>)}
                              </select>
                            </td>
                            <td className="border p-1">
                              <select value={c.bloom_level} onChange={(e) => { const v = [...editCells]; v[i] = { ...c, bloom_level: e.target.value }; setEditCells(v); }} className="rounded border p-1">
                                {Object.entries(BLOOM).map(([k, vi]) => <option key={k} value={k}>{vi}</option>)}
                              </select>
                            </td>
                            <td className="border p-1">
                              <select value={c.difficulty} onChange={(e) => { const v = [...editCells]; v[i] = { ...c, difficulty: e.target.value }; setEditCells(v); }} className="rounded border p-1">
                                {Object.entries(DIFFICULTY).map(([k, vi]) => <option key={k} value={k}>{vi}</option>)}
                              </select>
                            </td>
                            <td className="border p-1">
                              <input type="number" value={c.count} onChange={(e) => { const v = [...editCells]; v[i] = { ...c, count: Number(e.target.value) || 0 }; setEditCells(v); }} className="w-16 rounded border p-1" />
                            </td>
                            <td className="border p-1">
                              <input type="number" value={c.points_each ?? 0} onChange={(e) => { const v = [...editCells]; v[i] = { ...c, points_each: Number(e.target.value) || 0 }; setEditCells(v); }} className="w-16 rounded border p-1" />
                            </td>
                            <td className="border p-1 text-center">
                              <button onClick={() => setEditCells(editCells.filter((_, j) => j !== i))} className="text-red-600 hover:underline">Bớt</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="mt-2 flex gap-2">
                      <button onClick={() => setEditCells([...editCells, { clo_id: null, bloom_level: "remember", difficulty: "easy", count: 1, points_each: 1 }])} className="rounded bg-slate-100 px-3 py-1 hover:bg-slate-200">+ Thêm dòng</button>
                      <button onClick={saveMatrixEdit} className="rounded bg-green-600 px-3 py-1 text-white">Lưu</button>
                      <button onClick={() => setEditMatrixId(null)} className="rounded bg-slate-100 px-3 py-1">Hủy</button>
                    </div>
                  </div>
                )}
                {sm && (
                  <div className="mt-3 rounded bg-slate-50 p-3 text-xs">
                    <div className="mb-1">
                      <b>Tổng:</b> {sm.total_questions} câu · {sm.total_points}/{sm.declared_points} điểm
                      {sm.ok ? <span className="ml-2 text-green-700">✓ hợp lệ</span> : <span className="ml-2 text-red-700">✗ chưa hợp lệ</span>}
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <b>Tỷ trọng theo CLO</b>
                        {Object.entries(sm.clo_weight).map(([k, v]: any) => {
                          const clo = clos.find((c) => String(c.id) === String(k));
                          return (
                            <div key={k}>{clo ? clo.code : `CLO id ${k}`}: {v.points}đ ({v.percent}%)</div>
                          );
                        })}
                      </div>
                      <div>
                        <b>Tỷ trọng theo Bloom</b>
                        {Object.entries(sm.bloom_weight).map(([k, v]: any) => (
                          <div key={k}>{BLOOM[k] ?? k}: {v.points}đ ({v.percent}%)</div>
                        ))}
                      </div>
                    </div>
                    {sm.errors.map((e: string) => <div key={e} className="mt-1 text-red-700">✗ {e}</div>)}
                    {sm.warnings.map((w: string) => <div key={w} className="mt-1 text-amber-700">⚠ {w}</div>)}
                  </div>
                )}
                {matrixCoverage[m.id] && (
                  <div className="mt-3 rounded bg-slate-50 p-3 text-xs">
                    <b>Độ phủ ngân hàng (chỉ tính câu Đã duyệt)</b>
                    {!matrixCoverage[m.id].ok && (
                      <span className="ml-2 text-red-700">✗ có ô thiếu câu — không sinh đủ đề</span>
                    )}
                    <table className="mt-1 w-full">
                      <thead>
                        <tr className="text-slate-500">
                          <th className="p-1 text-left">CLO</th><th className="p-1">Bloom</th>
                          <th className="p-1">Độ khó</th><th className="p-1">Cần</th>
                          <th className="p-1">Đã duyệt</th><th className="p-1">Tình trạng</th>
                        </tr>
                      </thead>
                      <tbody>
                        {matrixCoverage[m.id].rows.map((r: any, i: number) => (
                          <tr key={i} className={r.status === "thiếu" ? "text-red-700" : r.status === "ít" ? "text-amber-700" : ""}>
                            <td className="p-1">{r.clo}</td>
                            <td className="p-1 text-center">{BLOOM[r.bloom_level] ?? r.bloom_level}</td>
                            <td className="p-1 text-center">{DIFFICULTY[r.difficulty] ?? r.difficulty}</td>
                            <td className="p-1 text-center">{r.need}</td>
                            <td className="p-1 text-center">{r.have_approved}</td>
                            <td className="p-1 text-center">
                              {r.status === "ok" ? "✓ đủ" : r.status === "ít" ? "⚠ ít (<3×)" : "✗ thiếu"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {matrixRationale[m.id] && (
                  <div className="mt-3 rounded border border-green-300 bg-green-50 p-3 text-xs">
                    <b>✨ Vì sao ma trận sau tối ưu đáp ứng kiểm định AUN-QA:</b>
                    <div className="mt-1 whitespace-pre-line text-slate-700">{matrixRationale[m.id]}</div>
                  </div>
                )}
              </div>
            );
          })}
          {matrices.length === 0 && (
            <p className="text-slate-500">Chưa có ma trận.</p>
          )}
        </div>

        {/* Form tạo ma trận */}
        <div className="card">
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
              className="btn btn-primary"
            >
              Tạo ma trận
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
