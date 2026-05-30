"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

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
  }
  useEffect(() => {
    load();
  }, [id]);

  async function generate(matrixId: number) {
    setErr("");
    try {
      await api(`/api/exams/generate`, {
        method: "POST",
        body: JSON.stringify({ matrix_id: matrixId, name: "Đề thi", seed: 1 }),
      });
      setExams(await api(`/api/courses/${id}/exams`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Học phần #{id}</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* Đề cương + alignment */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Đề cương & kiểm tra Alignment</h2>
        {outlines.map((o) => {
          const a = alignment[o.id];
          return (
            <div key={o.id} className="mb-2 rounded border bg-white p-3 text-sm">
              <b>Phiên bản v{o.version}</b> — trạng thái: {o.status}
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
              <button
                onClick={async () => setBlueprint(await api(`/api/exams/${e.id}/blueprint`))}
                className="rounded bg-slate-100 px-3 py-1 hover:bg-slate-200"
              >
                Bảng đặc tả
              </button>
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
