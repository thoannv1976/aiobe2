"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, apiUpload, getToken } from "@/lib/api";

// Kiểu payload trích xuất, khớp ExtractionPayload ở backend (SPEC 4.1).
type Program = { name: string; code: string; level: string; year: number; faculty: string };
type Plo = { code: string; description: string; category: string; bloom_level: string };
type Pi = { code: string; plo_code: string; description: string };
type Course = { code: string; name: string; credits: number; semester: number; type: string; prerequisites: string[] };
type CoursePlo = { course_code: string; plo_code: string; level: string };
type Payload = { program: Program; plos: Plo[]; pis: Pi[]; courses: Course[]; course_plo_matrix: CoursePlo[] };

const STEPS = ["1. Tải lên", "2. Trích xuất AI", "3. Rà soát & chỉnh sửa", "4. Hoàn tất"];

export default function ExtractPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<number | null>(null);
  const [docText, setDocText] = useState("");
  const [extId, setExtId] = useState<number | null>(null);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [result, setResult] = useState<{ program_id: number; plos: number; courses: number } | null>(null);

  useEffect(() => {
    if (!getToken()) router.push("/login");
  }, []);

  function fail(e: any) {
    setErr(typeof e?.message === "string" ? e.message : String(e));
    setBusy(false);
  }

  // Bước 1 → 2: upload file
  async function doUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setErr("");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await apiUpload("/api/documents/upload", fd);
      setDocId(up.document_id);
      const t = await api(`/api/documents/${up.document_id}/text`);
      setDocText(t.text || "");
      setStep(2);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  // Bước 2 → 3: chạy AI trích xuất
  async function doExtract() {
    if (!docId) return;
    setErr("");
    setBusy(true);
    try {
      const ex = await api(`/api/documents/${docId}/extract`, { method: "POST" });
      setExtId(ex.extraction_id);
      setPayload(normalize(ex.payload));
      setStep(3);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  // Bước 3 → 4: xác nhận (human-in-the-loop) → ghi CSDL
  async function doConfirm() {
    if (!extId || !payload) return;
    setErr("");
    setBusy(true);
    try {
      const r = await api(`/api/extractions/${extId}/confirm`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setResult(r);
      setStep(4);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trích xuất đề án mở ngành (AI)</h1>
        <p className="mt-1 text-sm text-slate-600">
          Tải lên đề án/CTĐT (PDF, DOCX, TXT) → AI trích xuất PLO/PI/học phần → bạn rà soát,
          chỉnh sửa rồi xác nhận để ghi vào hệ thống (SPEC 4.1, có bước người duyệt).
        </p>
      </div>

      {/* Stepper */}
      <ol className="flex flex-wrap gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={`rounded-full px-3 py-1 ${
              step === i + 1
                ? "bg-indigo-600 text-white"
                : step > i + 1
                ? "bg-green-100 text-green-800"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {step > i + 1 ? "✓ " : ""}
            {s}
          </li>
        ))}
      </ol>

      {err && <p className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</p>}

      {/* Bước 1: Upload */}
      {step === 1 && (
        <form onSubmit={doUpload} className="rounded-lg border bg-white p-6">
          <label className="block text-sm font-medium">Chọn file đề án (PDF / DOCX / TXT)</label>
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-2 block w-full text-sm"
          />
          {file && <p className="mt-2 text-xs text-slate-500">Đã chọn: {file.name}</p>}
          <button
            disabled={!file || busy}
            className="mt-4 rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {busy ? "Đang tải lên..." : "Tải lên & trích văn bản"}
          </button>
        </form>
      )}

      {/* Bước 2: Xem văn bản trích, chạy AI */}
      {step === 2 && (
        <div className="rounded-lg border bg-white p-6">
          <p className="text-sm text-slate-600">
            Đã trích {docText.length.toLocaleString("vi-VN")} ký tự từ tài liệu (mã #{docId}).
            Bấm để Claude phân tích và trích xuất có cấu trúc.
          </p>
          <pre className="mt-3 max-h-64 overflow-auto rounded bg-slate-50 p-3 text-xs whitespace-pre-wrap">
            {docText.slice(0, 4000) || "(không có văn bản)"}
            {docText.length > 4000 ? "\n…" : ""}
          </pre>
          <button
            onClick={doExtract}
            disabled={busy}
            className="mt-4 rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
          >
            {busy ? "AI đang trích xuất..." : "Chạy trích xuất bằng AI →"}
          </button>
        </div>
      )}

      {/* Bước 3: Rà soát + chỉnh sửa cạnh văn bản gốc */}
      {step === 3 && payload && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-4">
            <ReviewEditor payload={payload} onChange={setPayload} />
            <div className="flex gap-2">
              <button
                onClick={doConfirm}
                disabled={busy}
                className="rounded bg-green-600 px-4 py-2 text-white disabled:opacity-50"
              >
                {busy ? "Đang lưu..." : "Xác nhận & ghi vào hệ thống"}
              </button>
              <button onClick={() => setStep(2)} className="rounded bg-slate-100 px-4 py-2">
                ← Quay lại
              </button>
            </div>
          </div>
          <div className="rounded-lg border bg-white p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Văn bản gốc (đối chiếu)</h3>
            <pre className="max-h-[70vh] overflow-auto rounded bg-slate-50 p-3 text-xs whitespace-pre-wrap">
              {docText || "(không có văn bản)"}
            </pre>
          </div>
        </div>
      )}

      {/* Bước 4: Hoàn tất */}
      {step === 4 && result && (
        <div className="rounded-lg border border-green-300 bg-green-50 p-6">
          <h2 className="text-lg font-semibold text-green-800">✓ Đã ghi vào hệ thống</h2>
          <p className="mt-2 text-sm">
            Tạo CTĐT mới (id {result.program_id}) với {result.plos} PLO và {result.courses} học phần.
          </p>
          <div className="mt-4 flex gap-2">
            <Link href={`/programs/${result.program_id}`} className="rounded bg-indigo-600 px-4 py-2 text-white">
              Xem CTĐT vừa tạo →
            </Link>
            <button
              onClick={() => {
                setStep(1);
                setFile(null);
                setDocId(null);
                setDocText("");
                setExtId(null);
                setPayload(null);
                setResult(null);
              }}
              className="rounded bg-slate-100 px-4 py-2"
            >
              Trích xuất tài liệu khác
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Bảo đảm mọi mảng tồn tại để binding an toàn.
function normalize(p: any): Payload {
  return {
    program: { name: "", code: "", level: "", year: 0, faculty: "", ...(p?.program || {}) },
    plos: p?.plos || [],
    pis: p?.pis || [],
    courses: p?.courses || [],
    course_plo_matrix: p?.course_plo_matrix || [],
  };
}

// ----------------------- Editor con -----------------------
function ReviewEditor({ payload, onChange }: { payload: Payload; onChange: (p: Payload) => void }) {
  const set = (patch: Partial<Payload>) => onChange({ ...payload, ...patch });

  const inp = "w-full rounded border p-1 text-sm";
  const th = "border p-1 text-left text-xs font-medium bg-slate-100";
  const td = "border p-1";

  return (
    <div className="space-y-4">
      {/* Program */}
      <section className="rounded-lg border bg-white p-4">
        <h3 className="mb-2 text-sm font-semibold text-indigo-700">Thông tin CTĐT</h3>
        <div className="grid grid-cols-2 gap-2">
          <input className={inp} placeholder="Tên ngành" value={payload.program.name}
            onChange={(e) => set({ program: { ...payload.program, name: e.target.value } })} />
          <input className={inp} placeholder="Mã ngành" value={payload.program.code}
            onChange={(e) => set({ program: { ...payload.program, code: e.target.value } })} />
          <input className={inp} placeholder="Trình độ" value={payload.program.level}
            onChange={(e) => set({ program: { ...payload.program, level: e.target.value } })} />
          <input className={inp} type="number" placeholder="Năm" value={payload.program.year || ""}
            onChange={(e) => set({ program: { ...payload.program, year: Number(e.target.value) || 0 } })} />
          <input className={`${inp} col-span-2`} placeholder="Đơn vị/Khoa" value={payload.program.faculty}
            onChange={(e) => set({ program: { ...payload.program, faculty: e.target.value } })} />
        </div>
      </section>

      {/* PLOs */}
      <section className="rounded-lg border bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-indigo-700">PLO ({payload.plos.length})</h3>
          <button className="text-xs text-indigo-600"
            onClick={() => set({ plos: [...payload.plos, { code: "", description: "", category: "knowledge", bloom_level: "" }] })}>
            + Thêm PLO
          </button>
        </div>
        <table className="w-full">
          <thead><tr><th className={th}>Mã</th><th className={th}>Mô tả</th><th className={th}>Loại</th><th className={th}></th></tr></thead>
          <tbody>
            {payload.plos.map((p, i) => (
              <tr key={i}>
                <td className={td}><input className="w-16 rounded border p-1 text-sm" value={p.code}
                  onChange={(e) => { const a = [...payload.plos]; a[i] = { ...p, code: e.target.value }; set({ plos: a }); }} /></td>
                <td className={td}><input className={inp} value={p.description}
                  onChange={(e) => { const a = [...payload.plos]; a[i] = { ...p, description: e.target.value }; set({ plos: a }); }} /></td>
                <td className={td}>
                  <select className="rounded border p-1 text-sm" value={p.category}
                    onChange={(e) => { const a = [...payload.plos]; a[i] = { ...p, category: e.target.value }; set({ plos: a }); }}>
                    <option value="knowledge">knowledge</option>
                    <option value="skill">skill</option>
                    <option value="attitude">attitude</option>
                  </select>
                </td>
                <td className={td}><button className="text-xs text-red-600"
                  onClick={() => set({ plos: payload.plos.filter((_, j) => j !== i) })}>Xóa</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* PIs */}
      <section className="rounded-lg border bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-indigo-700">PI ({payload.pis.length})</h3>
          <button className="text-xs text-indigo-600"
            onClick={() => set({ pis: [...payload.pis, { code: "", plo_code: "", description: "" }] })}>
            + Thêm PI
          </button>
        </div>
        <table className="w-full">
          <thead><tr><th className={th}>Mã</th><th className={th}>Thuộc PLO</th><th className={th}>Mô tả</th><th className={th}></th></tr></thead>
          <tbody>
            {payload.pis.map((p, i) => (
              <tr key={i}>
                <td className={td}><input className="w-20 rounded border p-1 text-sm" value={p.code}
                  onChange={(e) => { const a = [...payload.pis]; a[i] = { ...p, code: e.target.value }; set({ pis: a }); }} /></td>
                <td className={td}><input className="w-20 rounded border p-1 text-sm" value={p.plo_code}
                  onChange={(e) => { const a = [...payload.pis]; a[i] = { ...p, plo_code: e.target.value }; set({ pis: a }); }} /></td>
                <td className={td}><input className={inp} value={p.description}
                  onChange={(e) => { const a = [...payload.pis]; a[i] = { ...p, description: e.target.value }; set({ pis: a }); }} /></td>
                <td className={td}><button className="text-xs text-red-600"
                  onClick={() => set({ pis: payload.pis.filter((_, j) => j !== i) })}>Xóa</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Courses */}
      <section className="rounded-lg border bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-indigo-700">Học phần ({payload.courses.length})</h3>
          <button className="text-xs text-indigo-600"
            onClick={() => set({ courses: [...payload.courses, { code: "", name: "", credits: 0, semester: 0, type: "core", prerequisites: [] }] })}>
            + Thêm học phần
          </button>
        </div>
        <table className="w-full">
          <thead><tr><th className={th}>Mã</th><th className={th}>Tên</th><th className={th}>TC</th><th className={th}>HK</th><th className={th}>Loại</th><th className={th}></th></tr></thead>
          <tbody>
            {payload.courses.map((c, i) => (
              <tr key={i}>
                <td className={td}><input className="w-16 rounded border p-1 text-sm" value={c.code}
                  onChange={(e) => { const a = [...payload.courses]; a[i] = { ...c, code: e.target.value }; set({ courses: a }); }} /></td>
                <td className={td}><input className={inp} value={c.name}
                  onChange={(e) => { const a = [...payload.courses]; a[i] = { ...c, name: e.target.value }; set({ courses: a }); }} /></td>
                <td className={td}><input className="w-12 rounded border p-1 text-sm" type="number" value={c.credits || ""}
                  onChange={(e) => { const a = [...payload.courses]; a[i] = { ...c, credits: Number(e.target.value) || 0 }; set({ courses: a }); }} /></td>
                <td className={td}><input className="w-12 rounded border p-1 text-sm" type="number" value={c.semester || ""}
                  onChange={(e) => { const a = [...payload.courses]; a[i] = { ...c, semester: Number(e.target.value) || 0 }; set({ courses: a }); }} /></td>
                <td className={td}>
                  <select className="rounded border p-1 text-sm" value={c.type}
                    onChange={(e) => { const a = [...payload.courses]; a[i] = { ...c, type: e.target.value }; set({ courses: a }); }}>
                    <option value="core">core</option>
                    <option value="elective">elective</option>
                  </select>
                </td>
                <td className={td}><button className="text-xs text-red-600"
                  onClick={() => set({ courses: payload.courses.filter((_, j) => j !== i) })}>Xóa</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {payload.course_plo_matrix.length > 0 && (
        <section className="rounded-lg border bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-indigo-700">
            Ma trận Học phần × PLO ({payload.course_plo_matrix.length} liên kết)
          </h3>
          <p className="text-xs text-slate-500">
            {payload.course_plo_matrix.map((m) => `${m.course_code}→${m.plo_code}(${m.level})`).join(", ")}
          </p>
        </section>
      )}
    </div>
  );
}
