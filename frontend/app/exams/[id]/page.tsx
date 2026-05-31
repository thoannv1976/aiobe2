"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, API_BASE, getToken } from "@/lib/api";

const BLOOM_VI: Record<string, string> = {
  remember: "Nhớ",
  understand: "Hiểu",
  apply: "Vận dụng",
  analyze: "Phân tích",
  evaluate: "Đánh giá",
  create: "Sáng tạo",
};
const DIFF_VI: Record<string, string> = {
  easy: "Dễ",
  medium: "TB",
  hard: "Khó",
};
const bloomVi = (b: string) => BLOOM_VI[b] || b;
const diffVi = (d: string) => DIFF_VI[d] || d;

interface BlueprintItem {
  order: number;
  question_id: number;
  clo_id: number;
  bloom_level: string;
  difficulty: string;
  points: number;
  answer: string;
}
interface Blueprint {
  exam_id: number;
  total_points: number;
  items: BlueprintItem[];
  clo_distribution: Record<string, number>;
  bloom_distribution: Record<string, number>;
}
interface ExamQuestion {
  exam_question_id: number;
  order: number;
  locked: boolean;
  question_id: number;
  content: string;
  clo_id: number;
  bloom_level: string;
  difficulty: string;
  points: number;
}

export default function ExamDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [questions, setQuestions] = useState<ExamQuestion[]>([]);
  const [replaceIds, setReplaceIds] = useState<Record<number, string>>({});
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function load() {
    try {
      const bp: Blueprint = await api(`/api/exams/${id}/blueprint`);
      setBlueprint(bp);
      const qs: ExamQuestion[] = await api(`/api/exams/${id}/questions?variant=1`);
      setQuestions(qs);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function toggleLock(eq: ExamQuestion) {
    setErr("");
    setMsg("");
    try {
      await api(`/api/exam-questions/${eq.exam_question_id}/lock?locked=${!eq.locked}`, {
        method: "POST",
      });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function replace(eq: ExamQuestion) {
    setErr("");
    setMsg("");
    const qid = replaceIds[eq.exam_question_id];
    if (!qid) {
      setErr("Nhập ID câu hỏi thay thế.");
      return;
    }
    try {
      await api(
        `/api/exam-questions/${eq.exam_question_id}/replace?question_id=${qid}`,
        { method: "PUT" }
      );
      setReplaceIds((p) => ({ ...p, [eq.exam_question_id]: "" }));
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function changeStatus(to: string) {
    setErr("");
    setMsg("");
    try {
      await api(`/api/exams/${id}/status?to=${to}`, { method: "POST" });
      setMsg(`Đã chuyển trạng thái sang "${to}".`);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function exportDocx(answers: boolean) {
    setErr("");
    try {
      const url = `${API_BASE}/api/exams/${id}/export?variant=1${
        answers ? "&answers=true" : ""
      }`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          detail = (await res.json()).detail;
        } catch {}
        throw new Error(detail);
      }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = answers ? `de_thi_${id}_dapan.docx` : `de_thi_${id}_ma1.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">
          Đề thi #{id}
          {blueprint && (
            <span className="ml-2 text-base font-normal text-slate-600">
              — {blueprint.total_points} điểm
            </span>
          )}
        </h1>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => exportDocx(false)}
            className="rounded bg-indigo-600 px-4 py-2 text-white"
          >
            Export đề (DOCX)
          </button>
          <button
            onClick={() => exportDocx(true)}
            className="rounded bg-indigo-600 px-4 py-2 text-white"
          >
            Export kèm đáp án (DOCX)
          </button>
        </div>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}
      {msg && <p className="text-sm text-green-700">{msg}</p>}

      {/* Chuyển trạng thái */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Vòng đời trạng thái</h2>
        <div className="flex flex-wrap gap-2">
          {["draft", "reviewed", "approved", "published"].map((s) => (
            <button
              key={s}
              onClick={() => changeStatus(s)}
              className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200"
            >
              Chuyển: {s}
            </button>
          ))}
        </div>
      </section>

      {/* Phân bố */}
      <section className="grid gap-3 sm:grid-cols-2">
        <div className="rounded border bg-white p-4 text-sm shadow-sm">
          <b>Phân bố theo CLO</b>
          {blueprint &&
            Object.entries(blueprint.clo_distribution).map(([k, v]) => (
              <div key={k}>
                CLO id {k}: {v} câu
              </div>
            ))}
          {blueprint &&
            Object.keys(blueprint.clo_distribution).length === 0 && (
              <div className="text-slate-500">Không có dữ liệu.</div>
            )}
        </div>
        <div className="rounded border bg-white p-4 text-sm shadow-sm">
          <b>Phân bố theo Bloom</b>
          {blueprint &&
            Object.entries(blueprint.bloom_distribution).map(([k, v]) => (
              <div key={k}>
                {bloomVi(k)}: {v} câu
              </div>
            ))}
          {blueprint &&
            Object.keys(blueprint.bloom_distribution).length === 0 && (
              <div className="text-slate-500">Không có dữ liệu.</div>
            )}
        </div>
      </section>

      {/* Danh sách câu hỏi (chỉnh tay) */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">
          Danh sách câu hỏi ({questions.length})
        </h2>
        <div className="rounded border bg-white p-4 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">#</th>
                <th className="border p-2">Nội dung</th>
                <th className="border p-2">CLO</th>
                <th className="border p-2">Bloom</th>
                <th className="border p-2">Độ khó</th>
                <th className="border p-2">Điểm</th>
                <th className="border p-2">Khóa</th>
                <th className="border p-2">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {questions.map((q) => (
                <tr key={q.exam_question_id}>
                  <td className="border p-2 text-center">{q.order}</td>
                  <td className="border p-2">
                    {q.content && q.content.length > 80
                      ? q.content.slice(0, 80) + "…"
                      : q.content}
                  </td>
                  <td className="border p-2 text-center">{q.clo_id}</td>
                  <td className="border p-2 text-center">{bloomVi(q.bloom_level)}</td>
                  <td className="border p-2 text-center">{diffVi(q.difficulty)}</td>
                  <td className="border p-2 text-center">{q.points}</td>
                  <td className="border p-2 text-center">{q.locked ? "🔒" : "mở"}</td>
                  <td className="border p-2">
                    <div className="flex flex-wrap items-center gap-1">
                      <button
                        onClick={() => toggleLock(q)}
                        className="rounded bg-slate-100 px-2 py-1 hover:bg-slate-200"
                      >
                        {q.locked ? "Mở" : "Khóa"}
                      </button>
                      {!q.locked && (
                        <>
                          <input
                            type="number"
                            placeholder="question_id"
                            value={replaceIds[q.exam_question_id] ?? ""}
                            onChange={(e) =>
                              setReplaceIds((p) => ({
                                ...p,
                                [q.exam_question_id]: e.target.value,
                              }))
                            }
                            className="w-24 rounded border p-1"
                          />
                          <button
                            onClick={() => replace(q)}
                            className="rounded bg-indigo-600 px-2 py-1 text-white"
                          >
                            Thay
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {questions.length === 0 && (
                <tr>
                  <td className="border p-2 text-center text-slate-500" colSpan={8}>
                    Chưa có câu hỏi.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bảng đặc tả */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Bảng đặc tả</h2>
        <div className="rounded border bg-white p-4 shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">#</th>
                <th className="border p-2">Mã câu</th>
                <th className="border p-2">CLO</th>
                <th className="border p-2">Bloom</th>
                <th className="border p-2">Độ khó</th>
                <th className="border p-2">Điểm</th>
                <th className="border p-2">Đáp án</th>
              </tr>
            </thead>
            <tbody>
              {blueprint?.items.map((it) => (
                <tr key={it.order}>
                  <td className="border p-2 text-center">{it.order}</td>
                  <td className="border p-2 text-center">{it.question_id}</td>
                  <td className="border p-2 text-center">{it.clo_id}</td>
                  <td className="border p-2 text-center">{bloomVi(it.bloom_level)}</td>
                  <td className="border p-2 text-center">{diffVi(it.difficulty)}</td>
                  <td className="border p-2 text-center">{it.points}</td>
                  <td className="border p-2 text-center">{it.answer}</td>
                </tr>
              ))}
              {(!blueprint || blueprint.items.length === 0) && (
                <tr>
                  <td className="border p-2 text-center text-slate-500" colSpan={7}>
                    Chưa có dữ liệu.
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
