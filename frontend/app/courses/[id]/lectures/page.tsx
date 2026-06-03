"use client";
import { Fragment, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, API_BASE, getToken } from "@/lib/api";

type LectureRow = {
  id: number;
  session_no: number;
  title: string;
  clo_codes: string[];
  has_content: boolean;
  slides_count: number;
};

type Slide = { title: string; bullets: string[] };

type LectureDetail = {
  id: number;
  course_id: number;
  session_no: number;
  title: string;
  content_richtext: string;
  slides_json: Slide[];
  clo_codes: string[];
};

type Clo = { id: number; code: string; description: string };

export default function LecturesPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [lectures, setLectures] = useState<LectureRow[]>([]);
  const [clos, setClos] = useState<Clo[]>([]);
  const [err, setErr] = useState("");

  // Chi tiết đang xem (mở rộng)
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<LectureDetail | null>(null);

  // Form AI sinh bài giảng
  const [genSession, setGenSession] = useState<number>(1);
  const [genTitle, setGenTitle] = useState("");
  const [genCloCodes, setGenCloCodes] = useState<string[]>([]);
  const [genBusy, setGenBusy] = useState(false);
  const [genMsg, setGenMsg] = useState("");

  // Form thêm thủ công
  const [mSession, setMSession] = useState<number>(1);
  const [mTitle, setMTitle] = useState("");
  const [mContent, setMContent] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);

  async function loadLectures() {
    try {
      const rows: LectureRow[] = await api(`/api/courses/${id}/lectures`);
      setLectures(rows);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function loadClos() {
    try {
      const outlines: any[] = await api(`/api/courses/${id}/outlines`);
      if (!outlines.length) {
        setClos([]);
        return;
      }
      const top = outlines.reduce((a, b) => (a.version >= b.version ? a : b));
      const cl: Clo[] = await api(`/api/outlines/${top.id}/clos`);
      setClos(cl);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    loadLectures();
    loadClos();
  }, [id]);

  function toggleGenClo(code: string) {
    setGenCloCodes((prev) =>
      prev.includes(code) ? prev.filter((x) => x !== code) : [...prev, code]
    );
  }

  async function generateLectureAI() {
    setErr("");
    setGenMsg("");
    if (!genTitle.trim()) {
      setErr("Vui lòng nhập tiêu đề buổi.");
      return;
    }
    setGenBusy(true);
    try {
      await api(`/api/courses/${id}/lectures/generate`, {
        method: "POST",
        body: JSON.stringify({
          session_no: Number(genSession),
          title: genTitle.trim(),
          clo_codes: genCloCodes,
        }),
      });
      setGenMsg("Đã tạo bài giảng bằng AI.");
      setGenTitle("");
      setGenCloCodes([]);
      await loadLectures();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  async function viewLecture(lid: number) {
    setErr("");
    if (expandedId === lid) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    try {
      const d: LectureDetail = await api(`/api/lectures/${lid}`);
      setDetail(d);
      setExpandedId(lid);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // Đánh giá + nâng cấp bài giảng bằng AI
  const [lecReviews, setLecReviews] = useState<Record<number, any>>({});
  const [lecReviewBusy, setLecReviewBusy] = useState<number | null>(null);
  const [lecImproveBusy, setLecImproveBusy] = useState<number | null>(null);

  async function reviewLecture(lid: number) {
    setErr("");
    setLecReviewBusy(lid);
    try {
      const r = await api(`/api/lectures/${lid}/qa-review`);
      setLecReviews((p) => ({ ...p, [lid]: r }));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLecReviewBusy(null);
    }
  }

  async function improveLecture(lid: number) {
    setErr("");
    setGenMsg("");
    setLecImproveBusy(lid);
    try {
      await api(`/api/lectures/${lid}/improve`, {
        method: "POST",
        body: JSON.stringify({ qa: lecReviews[lid] || null }),
      });
      setLecReviews((p) => ({ ...p, [lid]: undefined }));
      await loadLectures();
      // Mở lại nội dung mới nâng cấp.
      const d: LectureDetail = await api(`/api/lectures/${lid}`);
      setDetail(d);
      setExpandedId(lid);
      setGenMsg("Đã nâng cấp bài giảng bằng AI.");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLecImproveBusy(null);
    }
  }

  function exportLecture(lid: number, format: "docx" | "pptx") {
    fetch(`${API_BASE}/api/lectures/${lid}/export?format=${format}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Xuất file thất bại.");
        return res.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `bai_giang_${lid}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => setErr(String(e.message || e)));
  }

  async function deleteLecture(lid: number) {
    setErr("");
    try {
      await api(`/api/lectures/${lid}`, { method: "DELETE" });
      if (expandedId === lid) {
        setExpandedId(null);
        setDetail(null);
      }
      await loadLectures();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function saveManual() {
    setErr("");
    if (!mTitle.trim()) {
      setErr("Vui lòng nhập tiêu đề buổi.");
      return;
    }
    setSaveBusy(true);
    try {
      await api(`/api/courses/${id}/lectures`, {
        method: "POST",
        body: JSON.stringify({
          session_no: Number(mSession),
          title: mTitle.trim(),
          content_richtext: mContent,
          slides_json: [],
          clo_codes_json: [],
        }),
      });
      setMTitle("");
      setMContent("");
      await loadLectures();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setSaveBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Bài giảng — Học phần #{id}</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* Tạo bài giảng bằng AI */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">✨ Tạo bài giảng bằng AI</h2>
        {clos.length === 0 && (
          <p className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-700">
            Học phần chưa có đề cương/CLO. Vẫn có thể tạo bài giảng nhưng sẽ không gắn được CLO.
          </p>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-sm font-medium">Số buổi</label>
            <input
              type="number"
              min={1}
              value={genSession}
              onChange={(e) => setGenSession(Number(e.target.value) || 1)}
              className="mt-1 w-24 rounded border p-2 text-sm"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium">Tiêu đề buổi</label>
            <input
              value={genTitle}
              onChange={(e) => setGenTitle(e.target.value)}
              className="mt-1 w-full rounded border p-2 text-sm"
              placeholder="VD: Giới thiệu lập trình hướng đối tượng"
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="block text-sm font-medium">
            CLO áp dụng <span className="text-xs text-slate-500">(bỏ trống = tất cả)</span>
          </label>
          {clos.length === 0 ? (
            <p className="mt-1 text-xs text-slate-500">Chưa có CLO cho học phần này.</p>
          ) : (
            <div className="mt-1 flex flex-wrap gap-3">
              {clos.map((c) => (
                <label key={c.id} className="flex items-center gap-1 text-sm">
                  <input
                    type="checkbox"
                    checked={genCloCodes.includes(c.code)}
                    onChange={() => toggleGenClo(c.code)}
                  />
                  <span title={c.description}>{c.code}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="mt-3">
          <button
            onClick={generateLectureAI}
            disabled={genBusy}
            className="rounded bg-green-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {genBusy ? "AI đang soạn..." : "Tạo bài giảng bằng AI"}
          </button>
          {genBusy && (
            <span className="ml-2 text-sm text-slate-500">
              Có thể mất 15-40 giây, vui lòng đợi...
            </span>
          )}
          {genMsg && <p className="mt-2 text-sm text-green-700">{genMsg}</p>}
        </div>
      </section>

      {/* Danh sách bài giảng */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">Danh sách bài giảng</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-100">
              <th className="border p-2">Buổi</th>
              <th className="border p-2">Tiêu đề</th>
              <th className="border p-2">CLO</th>
              <th className="border p-2">Slide</th>
              <th className="border p-2">Trạng thái</th>
              <th className="border p-2">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {lectures
              .slice()
              .sort((a, b) => a.session_no - b.session_no)
              .map((lec) => (
                <Fragment key={lec.id}>
                  <tr>
                    <td className="border p-2 text-center">{lec.session_no}</td>
                    <td className="border p-2">{lec.title}</td>
                    <td className="border p-2 text-xs">
                      {(lec.clo_codes || []).join(", ")}
                    </td>
                    <td className="border p-2 text-center">{lec.slides_count}</td>
                    <td className="border p-2 text-center">
                      {lec.has_content ? (
                        <span className="text-green-600">● có nội dung</span>
                      ) : (
                        <span className="text-slate-400">○ trống</span>
                      )}
                    </td>
                    <td className="border p-2 whitespace-nowrap text-center">
                      <button
                        onClick={() => viewLecture(lec.id)}
                        className="mr-2 rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200"
                      >
                        {expandedId === lec.id ? "Ẩn" : "Xem"}
                      </button>
                      {lec.has_content && (
                        <button
                          onClick={() => reviewLecture(lec.id)}
                          disabled={lecReviewBusy === lec.id}
                          className="mr-2 rounded bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-700 disabled:opacity-50"
                          title="AI đánh giá chất lượng bài giảng"
                        >
                          {lecReviewBusy === lec.id ? "⏳ Đánh giá..." : "✨ Đánh giá"}
                        </button>
                      )}
                      <button
                        onClick={() => exportLecture(lec.id, "docx")}
                        className="mr-2 rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
                      >
                        Xuất DOCX
                      </button>
                      <button
                        onClick={() => exportLecture(lec.id, "pptx")}
                        className="mr-2 rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
                      >
                        Xuất PPTX
                      </button>
                      <button
                        onClick={() => deleteLecture(lec.id)}
                        className="rounded bg-red-100 px-2 py-1 text-xs text-red-700 hover:bg-red-200"
                      >
                        Xóa
                      </button>
                    </td>
                  </tr>
                  {lecReviews[lec.id] && (
                    <tr>
                      <td colSpan={6} className="border bg-indigo-50 p-3 text-xs">
                        <div className="mb-1 flex items-center justify-between">
                          <b>Đánh giá chất lượng bài giảng (AI)</b>
                          {typeof lecReviews[lec.id].score === "number" && (
                            <span className="rounded bg-indigo-600 px-2 py-0.5 text-white">
                              Điểm: {lecReviews[lec.id].score}/100
                            </span>
                          )}
                        </div>
                        {lecReviews[lec.id].summary && (
                          <p className="mb-1 italic text-slate-700">{lecReviews[lec.id].summary}</p>
                        )}
                        {(lecReviews[lec.id].errors || []).map((e: string) => (
                          <div key={e} className="text-red-700">✗ {e}</div>
                        ))}
                        {(lecReviews[lec.id].warnings || []).map((w: string) => (
                          <div key={w} className="text-amber-700">⚠ {w}</div>
                        ))}
                        {(lecReviews[lec.id].suggestions || []).map((s: string) => (
                          <div key={s} className="text-slate-600">• {s}</div>
                        ))}
                        <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-indigo-200 pt-2">
                          <button
                            onClick={() => improveLecture(lec.id)}
                            disabled={lecImproveBusy === lec.id}
                            className="rounded bg-indigo-600 px-3 py-1.5 font-medium text-white disabled:opacity-50"
                          >
                            {lecImproveBusy === lec.id ? "AI đang nâng cấp..." : "⚡ Nâng cấp bài giảng bằng AI"}
                          </button>
                          <span className="text-slate-500">
                            AI viết lại bài giảng và cập nhật slide để khắc phục các điểm trên.
                          </span>
                        </div>
                      </td>
                    </tr>
                  )}
                  {expandedId === lec.id && detail && (
                    <tr>
                      <td colSpan={6} className="border bg-slate-50 p-3">
                        <div className="space-y-4">
                          <div>
                            <h4 className="mb-1 text-sm font-semibold">Nội dung</h4>
                            {detail.content_richtext ? (
                              <pre className="max-h-96 overflow-auto whitespace-pre-wrap font-sans text-xs text-slate-700">
                                {detail.content_richtext}
                              </pre>
                            ) : (
                              <p className="text-xs text-slate-400">Chưa có nội dung.</p>
                            )}
                          </div>
                          <div>
                            <h4 className="mb-1 text-sm font-semibold">
                              Slide ({(detail.slides_json || []).length})
                            </h4>
                            {(detail.slides_json || []).length === 0 ? (
                              <p className="text-xs text-slate-400">Chưa có slide.</p>
                            ) : (
                              <div className="space-y-3">
                                {detail.slides_json.map((s, i) => (
                                  <div
                                    key={i}
                                    className="rounded border bg-white p-2 text-xs"
                                  >
                                    <b>
                                      {i + 1}. {s.title}
                                    </b>
                                    {(s.bullets || []).length > 0 && (
                                      <ul className="ml-5 mt-1 list-disc">
                                        {s.bullets.map((b, j) => (
                                          <li key={j}>{b}</li>
                                        ))}
                                      </ul>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            {lectures.length === 0 && (
              <tr>
                <td colSpan={6} className="border p-2 text-center text-slate-500">
                  Chưa có bài giảng.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Thêm bài giảng thủ công */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">Thêm bài giảng thủ công</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-sm font-medium">Số buổi</label>
            <input
              type="number"
              min={1}
              value={mSession}
              onChange={(e) => setMSession(Number(e.target.value) || 1)}
              className="mt-1 w-24 rounded border p-2 text-sm"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium">Tiêu đề buổi</label>
            <input
              value={mTitle}
              onChange={(e) => setMTitle(e.target.value)}
              className="mt-1 w-full rounded border p-2 text-sm"
            />
          </div>
        </div>
        <div className="mt-3">
          <label className="block text-sm font-medium">Nội dung</label>
          <textarea
            value={mContent}
            onChange={(e) => setMContent(e.target.value)}
            rows={6}
            className="mt-1 w-full rounded border p-2 text-sm font-mono"
          />
        </div>
        <div className="mt-3">
          <button
            onClick={saveManual}
            disabled={saveBusy}
            className="rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {saveBusy ? "Đang lưu..." : "Lưu"}
          </button>
        </div>
      </section>
    </div>
  );
}
