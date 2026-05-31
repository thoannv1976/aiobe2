"use client";
import { Fragment, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, API_BASE, getToken } from "@/lib/api";

type Textbook = {
  id: number;
  course_id: number;
  title: string;
  version: number;
  status: string;
};

type Chapter = {
  id: number;
  textbook_id: number;
  order: number;
  title: string;
  content_richtext: string;
  clo_ids: number[];
};

type Clo = { id: number; code: string; description: string };

type Suggestion = { title: string; clo_codes: string[] };

export default function TextbooksPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [textbooks, setTextbooks] = useState<Textbook[]>([]);
  const [selected, setSelected] = useState<Textbook | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [clos, setClos] = useState<Clo[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [err, setErr] = useState("");
  const [suggestMsg, setSuggestMsg] = useState("");

  // Form tạo giáo trình mới
  const [newTitle, setNewTitle] = useState("");
  const [genBusy, setGenBusy] = useState(false);
  const [genMsg, setGenMsg] = useState("");
  const [genNumChapters, setGenNumChapters] = useState<number>(0);
  const [deepPages, setDeepPages] = useState<number>(30);
  const [chapterBusy, setChapterBusy] = useState<number | null>(null);
  const [expandedChapter, setExpandedChapter] = useState<number | null>(null);

  // Form thêm/sửa chương
  const [editingId, setEditingId] = useState<number | null>(null);
  const [chOrder, setChOrder] = useState<number>(1);
  const [chTitle, setChTitle] = useState("");
  const [chContent, setChContent] = useState("");
  const [chCloIds, setChCloIds] = useState<number[]>([]);

  async function loadTextbooks() {
    try {
      const tbs: Textbook[] = await api(`/api/courses/${id}/textbooks`);
      setTextbooks(tbs);
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
    loadTextbooks();
    loadClos();
  }, [id]);

  async function loadChapters(tb: Textbook) {
    try {
      const chs: Chapter[] = await api(`/api/textbooks/${tb.id}/chapters`);
      setChapters(chs);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  function selectTextbook(tb: Textbook) {
    setErr("");
    setSuggestMsg("");
    setSuggestions([]);
    setSelected(tb);
    resetChapterForm();
    loadChapters(tb);
  }

  async function createTextbook() {
    setErr("");
    if (!newTitle.trim()) {
      setErr("Vui lòng nhập tiêu đề giáo trình.");
      return;
    }
    try {
      await api(`/api/textbooks`, {
        method: "POST",
        body: JSON.stringify({ course_id: Number(id), title: newTitle.trim() }),
      });
      setNewTitle("");
      loadTextbooks();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- AI sinh giáo trình -----
  // withContent=false: chỉ tạo dàn ý chương (nhanh).
  // withContent=true: tạo dàn ý rồi SINH SÂU từng chương tuần tự (resumable, có tiến độ).
  async function generateTextbookAI(withContent: boolean) {
    setErr("");
    setGenMsg("");
    setGenBusy(true);
    try {
      // Bước 1: luôn tạo dàn ý + chương rỗng trước (nhanh, không timeout).
      setGenMsg("Đang lập dàn ý các chương...");
      const r = await api(`/api/courses/${id}/textbooks/generate`, {
        method: "POST",
        body: JSON.stringify({
          title: newTitle.trim(),
          num_chapters: genNumChapters,
          with_content: false,
        }),
      });
      setNewTitle("");
      await loadTextbooks();
      const tbs: Textbook[] = await api(`/api/courses/${id}/textbooks`);
      const created = tbs.find((t) => t.id === r.textbook_id);
      if (created) selectTextbook(created);

      if (!withContent) {
        setGenMsg(`Đã tạo dàn ý ${r.chapters} chương. Bấm "AI nội dung" ở từng chương để soạn.`);
        return;
      }

      // Bước 2: sinh SÂU từng chương tuần tự — mỗi chương lưu ngay, lỗi 1 chương không mất các chương khác.
      const chs: Chapter[] = await api(`/api/textbooks/${r.textbook_id}/chapters`);
      const sorted = chs.slice().sort((a, b) => a.order - b.order);
      let ok = 0;
      const failed: number[] = [];
      for (let i = 0; i < sorted.length; i++) {
        const ch = sorted[i];
        setGenMsg(`Đang soạn nội dung chương ${i + 1}/${sorted.length}: "${ch.title}"... (có thể mất vài phút mỗi chương)`);
        try {
          await api(`/api/chapters/${ch.id}/generate-content?deep=true&target_pages=${deepPages}`, {
            method: "POST",
          });
          ok++;
        } catch {
          failed.push(ch.order);
        }
        if (created) await loadChapters(created);
      }
      setGenMsg(
        `Hoàn tất: ${ok}/${sorted.length} chương đã có nội dung` +
          (failed.length ? `. Chương lỗi: ${failed.join(", ")} — bấm "AI nội dung" để soạn lại.` : ".")
      );
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setGenBusy(false);
    }
  }

  async function generateChapterContentAI(ch: Chapter) {
    setErr("");
    setGenMsg("");
    setChapterBusy(ch.id);
    try {
      await api(`/api/chapters/${ch.id}/generate-content?deep=true&target_pages=${deepPages}`, {
        method: "POST",
      });
      if (selected) await loadChapters(selected);
      setExpandedChapter(ch.id);
      setGenMsg(`Đã soạn nội dung cho chương "${ch.title}". Xem bên dưới / chỉnh sửa nếu cần.`);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setChapterBusy(null);
    }
  }

  function downloadTextbook(tb: Textbook, format: "docx" | "pdf") {
    fetch(`${API_BASE}/api/textbooks/${tb.id}/export?format=${format}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `giao_trinh_${tb.id}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => setErr(String(e)));
  }

  function resetChapterForm() {
    setEditingId(null);
    setChOrder(chapters.length + 1);
    setChTitle("");
    setChContent("");
    setChCloIds([]);
  }

  function startEdit(ch: Chapter) {
    setEditingId(ch.id);
    setChOrder(ch.order);
    setChTitle(ch.title);
    setChContent(ch.content_richtext);
    setChCloIds(ch.clo_ids || []);
  }

  function toggleClo(cloId: number) {
    setChCloIds((prev) =>
      prev.includes(cloId) ? prev.filter((x) => x !== cloId) : [...prev, cloId]
    );
  }

  async function saveChapter() {
    if (!selected) return;
    setErr("");
    if (!chTitle.trim()) {
      setErr("Vui lòng nhập tiêu đề chương.");
      return;
    }
    const payload = {
      order: Number(chOrder),
      title: chTitle.trim(),
      content_richtext: chContent,
      clo_ids: chCloIds,
    };
    try {
      if (editingId == null) {
        await api(`/api/textbooks/${selected.id}/chapters`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/api/chapters/${editingId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      }
      await loadChapters(selected);
      resetChapterForm();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteChapter(ch: Chapter) {
    if (!selected) return;
    setErr("");
    try {
      await api(`/api/chapters/${ch.id}`, { method: "DELETE" });
      if (editingId === ch.id) resetChapterForm();
      await loadChapters(selected);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function loadSuggestions() {
    setErr("");
    setSuggestMsg("");
    setSuggestions([]);
    try {
      const res: { suggestions: Suggestion[] } = await api(
        `/api/courses/${id}/chapter-suggestions`
      );
      setSuggestions(res.suggestions || []);
      if (!res.suggestions || res.suggestions.length === 0) {
        setSuggestMsg("Chưa có gợi ý nào.");
      }
    } catch (e: any) {
      setSuggestMsg(
        e.message ||
          "Không lấy được gợi ý. Có thể chưa có CLO hoặc chưa cấu hình API key."
      );
    }
  }

  function applySuggestion(s: Suggestion) {
    setEditingId(null);
    setChTitle(s.title);
    setChOrder(chapters.length + 1);
    setChContent("");
    // Tích sẵn các CLO khớp clo_codes nếu tìm thấy
    const matched = clos
      .filter((c) => s.clo_codes.includes(c.code))
      .map((c) => c.id);
    setChCloIds(matched);
  }

  function cloLabel(cloId: number): string {
    const c = clos.find((x) => x.id === cloId);
    return c ? c.code : `#${cloId}`;
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold">Giáo trình — Học phần #{id}</h1>
      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* Danh sách giáo trình + tạo mới */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Danh sách giáo trình</h2>
        <div className="space-y-2">
          {textbooks.map((tb) => (
            <div
              key={tb.id}
              onClick={() => selectTextbook(tb)}
              className={`cursor-pointer rounded border p-3 text-sm ${
                selected?.id === tb.id
                  ? "border-indigo-500 bg-indigo-50"
                  : "bg-white hover:bg-slate-50"
              }`}
            >
              <b>{tb.title}</b> — v{tb.version} — {tb.status}
            </div>
          ))}
          {textbooks.length === 0 && (
            <p className="text-slate-500">Chưa có giáo trình.</p>
          )}
        </div>

        <div className="mt-3 flex items-end gap-2">
          <div className="flex-1">
            <label className="block text-sm font-medium">Tiêu đề giáo trình mới</label>
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="mt-1 w-full rounded border p-2 text-sm"
              placeholder="VD: Giáo trình Lập trình hướng đối tượng"
            />
          </div>
          <button
            onClick={createTextbook}
            className="rounded bg-indigo-600 px-3 py-2 text-sm text-white"
          >
            Tạo
          </button>
        </div>

        {/* Tạo giáo trình bằng AI */}
        <div className="mt-4 rounded-lg border border-green-200 bg-green-50/40 p-4">
          <h3 className="text-sm font-semibold">✨ Tạo giáo trình bằng AI</h3>
          <p className="mb-2 text-xs text-slate-600">
            AI tạo cả giáo trình (các chương gắn CLO của đề cương). Dùng tiêu đề ở ô trên (nếu để trống sẽ tự đặt tên).
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              Số chương
              <input
                type="number"
                min={0}
                max={30}
                value={genNumChapters}
                onChange={(e) => setGenNumChapters(Number(e.target.value) || 0)}
                className="mt-1 block w-24 rounded border p-1"
              />
              <span className="block text-xs text-slate-400">(0 = AI tự quyết)</span>
            </label>
            <button
              onClick={() => generateTextbookAI(true)}
              disabled={genBusy}
              className="rounded bg-green-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              {genBusy ? "AI đang soạn..." : "Tạo cả giáo trình (kèm nội dung)"}
            </button>
            <button
              onClick={() => generateTextbookAI(false)}
              disabled={genBusy}
              className="rounded border border-green-600 px-4 py-2 text-sm text-green-700 disabled:opacity-50"
            >
              Chỉ tạo dàn ý chương
            </button>
          </div>
          {genMsg && <p className="mt-2 text-sm text-green-700">{genMsg}</p>}
        </div>
      </section>

      {/* Khi chọn 1 giáo trình */}
      {selected && (
        <section className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">
              Chương của: {selected.title} (v{selected.version})
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => downloadTextbook(selected, "docx")}
                className="rounded bg-slate-100 px-3 py-1 text-sm hover:bg-slate-200"
              >
                Xuất DOCX
              </button>
              <button
                onClick={() => downloadTextbook(selected, "pdf")}
                className="rounded bg-slate-100 px-3 py-1 text-sm hover:bg-slate-200"
              >
                Xuất PDF
              </button>
            </div>
          </div>

          {/* Gợi ý AI */}
          <div className="rounded border bg-white p-3">
            <div className="flex items-center justify-between">
              <b className="text-sm">Gợi ý đề mục bằng AI</b>
              <button
                onClick={loadSuggestions}
                className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
              >
                Gợi ý đề mục bằng AI
              </button>
            </div>
            <p className="mt-1 text-xs italic text-slate-500">
              Gợi ý AI — cần người duyệt trước khi lưu.
            </p>
            {suggestMsg && (
              <p className="mt-2 text-sm text-amber-700">{suggestMsg}</p>
            )}
            {suggestions.length > 0 && (
              <ul className="mt-2 space-y-2">
                {suggestions.map((s, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between rounded bg-slate-50 p-2 text-sm"
                  >
                    <span>
                      <b>{s.title}</b>
                      {s.clo_codes.length > 0 && (
                        <span className="ml-2 text-xs text-slate-500">
                          [{s.clo_codes.join(", ")}]
                        </span>
                      )}
                    </span>
                    <button
                      onClick={() => applySuggestion(s)}
                      className="rounded bg-slate-200 px-2 py-1 text-xs hover:bg-slate-300"
                    >
                      Dùng
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Bảng chương */}
          <div>
            <h3 className="mb-2 text-sm font-semibold">Danh sách chương</h3>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-100">
                  <th className="border p-1">STT</th>
                  <th className="border p-1">Tiêu đề</th>
                  <th className="border p-1">CLO</th>
                  <th className="border p-1">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {chapters
                  .slice()
                  .sort((a, b) => a.order - b.order)
                  .map((ch) => {
                    const hasContent = !!(ch.content_richtext && ch.content_richtext.trim());
                    const busy = chapterBusy === ch.id;
                    return (
                      <Fragment key={ch.id}>
                        <tr>
                          <td className="border p-1 text-center">{ch.order}</td>
                          <td className="border p-1">
                            {ch.title}
                            <span className="ml-2 text-xs">
                              {hasContent ? (
                                <span className="text-green-600">● có nội dung</span>
                              ) : (
                                <span className="text-slate-400">○ trống</span>
                              )}
                            </span>
                          </td>
                          <td className="border p-1 text-xs">
                            {(ch.clo_ids || []).map((cid) => cloLabel(cid)).join(", ")}
                          </td>
                          <td className="border p-1 text-center whitespace-nowrap">
                            <button
                              onClick={() => generateChapterContentAI(ch)}
                              disabled={busy}
                              className="mr-2 rounded bg-green-100 px-2 py-1 text-xs text-green-700 hover:bg-green-200 disabled:opacity-50"
                              title="AI soạn/viết lại nội dung chương này"
                            >
                              {busy ? "⏳ Đang soạn..." : hasContent ? "✨ Viết lại" : "✨ AI nội dung"}
                            </button>
                            {hasContent && (
                              <button
                                onClick={() =>
                                  setExpandedChapter(expandedChapter === ch.id ? null : ch.id)
                                }
                                className="mr-2 rounded bg-indigo-100 px-2 py-1 text-xs text-indigo-700 hover:bg-indigo-200"
                              >
                                {expandedChapter === ch.id ? "Ẩn" : "Xem"}
                              </button>
                            )}
                            <button
                              onClick={() => startEdit(ch)}
                              className="mr-2 rounded bg-slate-100 px-2 py-1 text-xs hover:bg-slate-200"
                            >
                              Sửa
                            </button>
                            <button
                              onClick={() => deleteChapter(ch)}
                              className="rounded bg-red-100 px-2 py-1 text-xs text-red-700 hover:bg-red-200"
                            >
                              Xóa
                            </button>
                          </td>
                        </tr>
                        {expandedChapter === ch.id && hasContent && (
                          <tr>
                            <td colSpan={4} className="border bg-slate-50 p-3">
                              <pre className="max-h-96 overflow-auto whitespace-pre-wrap font-sans text-xs text-slate-700">
                                {ch.content_richtext}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                {chapters.length === 0 && (
                  <tr>
                    <td colSpan={4} className="border p-2 text-center text-slate-500">
                      Chưa có chương.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Form thêm/sửa chương */}
          <div className="rounded border bg-white p-3">
            <h3 className="mb-2 text-sm font-semibold">
              {editingId == null ? "Thêm chương mới" : `Sửa chương #${editingId}`}
            </h3>
            <div className="grid gap-3 sm:grid-cols-4">
              <div>
                <label className="block text-sm font-medium">Thứ tự</label>
                <input
                  type="number"
                  value={chOrder}
                  onChange={(e) => setChOrder(Number(e.target.value))}
                  className="mt-1 w-full rounded border p-2 text-sm"
                />
              </div>
              <div className="sm:col-span-3">
                <label className="block text-sm font-medium">Tiêu đề</label>
                <input
                  value={chTitle}
                  onChange={(e) => setChTitle(e.target.value)}
                  className="mt-1 w-full rounded border p-2 text-sm"
                />
              </div>
            </div>

            <div className="mt-3">
              <label className="block text-sm font-medium">Nội dung</label>
              <textarea
                value={chContent}
                onChange={(e) => setChContent(e.target.value)}
                rows={6}
                className="mt-1 w-full rounded border p-2 text-sm font-mono"
              />
              <p className="mt-1 text-xs text-slate-500">
                Hỗ trợ markdown / HTML đơn giản.
              </p>
            </div>

            <div className="mt-3">
              <label className="block text-sm font-medium">Gắn CLO</label>
              {clos.length === 0 ? (
                <p className="mt-1 text-xs text-slate-500">
                  Chưa có CLO cho học phần này.
                </p>
              ) : (
                <div className="mt-1 flex flex-wrap gap-3">
                  {clos.map((c) => (
                    <label key={c.id} className="flex items-center gap-1 text-sm">
                      <input
                        type="checkbox"
                        checked={chCloIds.includes(c.id)}
                        onChange={() => toggleClo(c.id)}
                      />
                      <span title={c.description}>{c.code}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-3 flex gap-2">
              <button
                onClick={saveChapter}
                className="rounded bg-indigo-600 px-3 py-2 text-sm text-white"
              >
                Lưu
              </button>
              <button
                onClick={resetChapterForm}
                className="rounded bg-slate-100 px-3 py-2 text-sm hover:bg-slate-200"
              >
                Hủy
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
