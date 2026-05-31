"use client";
import { Fragment, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, API_BASE, getToken } from "@/lib/api";

const BLOOM_LEVELS = [
  "remember",
  "understand",
  "apply",
  "analyze",
  "evaluate",
  "create",
];
const PLO_LEVELS = ["", "I", "R", "M"];

// Các bước chuyển trạng thái hợp lệ kèm nhãn tiếng Việt.
const STATUS_FLOW: Record<string, { to: string; label: string }> = {
  draft: { to: "submitted", label: "Nộp duyệt" },
  submitted: { to: "approved", label: "Duyệt" },
  approved: { to: "published", label: "Ban hành" },
  published: { to: "archived", label: "Lưu trữ" },
};

export default function OutlineEditor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [outline, setOutline] = useState<any>(null);
  const [alignment, setAlignment] = useState<any>(null);
  const [clos, setClos] = useState<any[]>([]);
  const [cloPlo, setCloPlo] = useState<any[]>([]);
  const [plos, setPlos] = useState<any[]>([]);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [lessons, setLessons] = useState<any[]>([]);
  const [err, setErr] = useState("");

  // Form: thông tin chung
  const [description, setDescription] = useState("");
  const [teachingMethods, setTeachingMethods] = useState("");
  const [references, setReferences] = useState("");

  // Form: CLO
  const [cloCode, setCloCode] = useState("");
  const [cloDesc, setCloDesc] = useState("");
  const [cloBloom, setCloBloom] = useState("understand");

  // Form: đánh giá
  const [asName, setAsName] = useState("");
  const [asType, setAsType] = useState("");
  const [asWeight, setAsWeight] = useState<number>(0);
  const [asClos, setAsClos] = useState<number[]>([]);

  // Form: kế hoạch giảng dạy
  const [lsWeek, setLsWeek] = useState<number>(1);
  const [lsTopic, setLsTopic] = useState("");
  const [lsClos, setLsClos] = useState<number[]>([]);

  const editable =
    outline && outline.status !== "published" && outline.status !== "archived";

  async function load() {
    setErr("");
    try {
      const o = await api(`/api/outlines/${id}`);
      setOutline(o);
      setDescription(o.description || "");
      setTeachingMethods((o.teaching_methods_json || []).join("\n"));
      setReferences((o.references_json || []).join("\n"));

      setAlignment(await api(`/api/outlines/${id}/alignment`));
      setClos(await api(`/api/outlines/${id}/clos`));
      setCloPlo(await api(`/api/outlines/${id}/clo-plo`));
      setAssessments(await api(`/api/outlines/${id}/assessments`));
      setLessons(await api(`/api/outlines/${id}/lessons`));

      // Tìm program chứa course để lấy danh sách PLO cho ma trận CLO×PLO.
      try {
        const programs = await api(`/api/programs`);
        for (const p of programs) {
          const courses = await api(`/api/programs/${p.id}/courses`);
          if (courses.some((c: any) => c.id === o.course_id)) {
            setPlos(await api(`/api/programs/${p.id}/plos`));
            break;
          }
        }
      } catch {
        // Không lấy được PLO thì để ma trận trống.
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

  // ----- Thông tin chung -----
  async function saveGeneral() {
    setErr("");
    try {
      await api(`/api/outlines/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          description,
          general_info_json: outline?.general_info_json || {},
          teaching_methods_json: teachingMethods
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
          references_json: references
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Trạng thái / phiên bản / export -----
  async function changeStatus(to: string) {
    setErr("");
    try {
      await api(`/api/outlines/${id}/status?to=${to}`, { method: "POST" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function newVersion() {
    setErr("");
    try {
      const created = await api(`/api/outlines/${id}/new-version`, {
        method: "POST",
      });
      if (created?.id) router.push(`/outlines/${created.id}`);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function downloadDocx() {
    setErr("");
    try {
      const res = await fetch(`${API_BASE}/api/outlines/${id}/export`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!res.ok) throw new Error("Không xuất được DOCX");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `de_cuong_${id}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- CLO -----
  async function addClo() {
    setErr("");
    try {
      await api(`/api/outlines/${id}/clos`, {
        method: "POST",
        body: JSON.stringify({
          code: cloCode,
          description: cloDesc,
          bloom_level: cloBloom,
        }),
      });
      setCloCode("");
      setCloDesc("");
      setCloBloom("understand");
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteClo(cloId: number) {
    setErr("");
    try {
      await api(`/api/clos/${cloId}`, { method: "DELETE" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Ma trận CLO×PLO -----
  function levelOf(cloId: number, ploId: number) {
    return (
      cloPlo.find((m) => m.clo_id === cloId && m.plo_id === ploId)
        ?.contribution_level || ""
    );
  }

  async function setCloPloLevel(cloId: number, ploId: number, level: string) {
    setErr("");
    try {
      if (!level) {
        await api(`/api/clo-plo?clo_id=${cloId}&plo_id=${ploId}`, {
          method: "DELETE",
        });
      } else {
        await api(`/api/clo-plo`, {
          method: "PUT",
          body: JSON.stringify({
            clo_id: cloId,
            plo_id: ploId,
            contribution_level: level,
          }),
        });
      }
      setCloPlo(await api(`/api/outlines/${id}/clo-plo`));
      setAlignment(await api(`/api/outlines/${id}/alignment`));
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Đánh giá -----
  async function addAssessment() {
    setErr("");
    try {
      await api(`/api/outlines/${id}/assessments`, {
        method: "POST",
        body: JSON.stringify({
          name: asName,
          type: asType,
          weight_percent: asWeight,
          rubric_json: {},
          clo_ids: asClos,
        }),
      });
      setAsName("");
      setAsType("");
      setAsWeight(0);
      setAsClos([]);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteAssessment(aid: number) {
    setErr("");
    try {
      await api(`/api/assessments/${aid}`, { method: "DELETE" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Sửa rubric -----
  // editingRubric: id cấu phần đang sửa; draftCriteria: danh sách tiêu chí nháp.
  const [editingRubric, setEditingRubric] = useState<number | null>(null);
  const [draftCriteria, setDraftCriteria] = useState<any[]>([]);

  function openRubricEditor(a: any) {
    setEditingRubric(a.id);
    setDraftCriteria((a.rubric_json?.criteria || []).map((c: any) => ({
      name: c.name || "",
      weight_percent: c.weight_percent || 0,
      levels: (c.levels || []).join("\n"),
    })));
  }

  async function saveRubric(a: any) {
    setErr("");
    try {
      const criteria = draftCriteria.map((c) => ({
        name: c.name,
        weight_percent: Number(c.weight_percent) || 0,
        levels: String(c.levels).split("\n").map((s) => s.trim()).filter(Boolean),
      }));
      await api(`/api/assessments/${a.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: a.name,
          type: a.type || "",
          weight_percent: a.weight_percent,
          clo_ids: a.clo_ids || [],
          rubric_json: { criteria },
        }),
      });
      setEditingRubric(null);
      setDraftCriteria([]);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  // ----- Kế hoạch giảng dạy -----
  async function addLesson() {
    setErr("");
    try {
      await api(`/api/outlines/${id}/lessons`, {
        method: "POST",
        body: JSON.stringify({
          week: lsWeek,
          topic: lsTopic,
          activities_json: {},
          clo_ids: lsClos,
        }),
      });
      setLsWeek(1);
      setLsTopic("");
      setLsClos([]);
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteLesson(lid: number) {
    setErr("");
    try {
      await api(`/api/lessons/${lid}`, { method: "DELETE" });
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  function toggleIn(list: number[], value: number): number[] {
    return list.includes(value)
      ? list.filter((x) => x !== value)
      : [...list, value];
  }

  function cloLabel(cloId: number) {
    const c = clos.find((x) => x.id === cloId);
    return c ? c.code : `CLO #${cloId}`;
  }

  if (!outline) return <p>{err || "Đang tải..."}</p>;

  const totalWeight = assessments.reduce(
    (s, a) => s + (Number(a.weight_percent) || 0),
    0
  );
  const flow = STATUS_FLOW[outline.status];

  return (
    <div className="space-y-8">
      {/* 1. Header */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold">
            Đề cương #{outline.id}{" "}
            <span className="text-slate-400">v{outline.version}</span>{" "}
            <span className="text-sm font-normal text-slate-500">
              ({outline.status})
            </span>
          </h1>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={downloadDocx}
              className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200"
            >
              Xuất DOCX
            </button>
            <button
              onClick={newVersion}
              className="rounded bg-slate-100 px-4 py-2 hover:bg-slate-200"
            >
              Tạo phiên bản mới
            </button>
            {flow && (
              <button
                onClick={() => changeStatus(flow.to)}
                className="rounded bg-indigo-600 px-4 py-2 text-white"
              >
                {flow.label}
              </button>
            )}
          </div>
        </div>
      </section>

      {err && <p className="text-sm text-red-600">{err}</p>}

      {/* 2. Banner Alignment */}
      {alignment && (
        <section
          className={`rounded border p-4 text-sm shadow-sm ${
            alignment.ok
              ? "border-green-300 bg-green-50"
              : "border-red-300 bg-red-50"
          }`}
        >
          <b>Kiểm tra Alignment:</b>{" "}
          {alignment.ok ? "Đạt" : "Chưa đạt"}
          {alignment.errors?.map((e: string) => (
            <div key={e} className="text-red-700">
              • {e}
            </div>
          ))}
          {alignment.warnings?.map((w: string) => (
            <div key={w} className="text-amber-700">
              ⚠ {w}
            </div>
          ))}
        </section>
      )}

      {/* 3. Thông tin chung */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Thông tin chung</h2>
        <label className="mb-1 block text-sm font-medium">Mô tả học phần</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={!editable}
          className="mb-3 w-full rounded border p-2 text-sm"
          rows={3}
        />
        <label className="mb-1 block text-sm font-medium">
          Phương pháp giảng dạy (mỗi dòng một phương pháp)
        </label>
        <textarea
          value={teachingMethods}
          onChange={(e) => setTeachingMethods(e.target.value)}
          disabled={!editable}
          className="mb-3 w-full rounded border p-2 text-sm"
          rows={3}
        />
        <label className="mb-1 block text-sm font-medium">
          Tài liệu tham khảo (mỗi dòng một tài liệu)
        </label>
        <textarea
          value={references}
          onChange={(e) => setReferences(e.target.value)}
          disabled={!editable}
          className="mb-3 w-full rounded border p-2 text-sm"
          rows={3}
        />
        <button
          onClick={saveGeneral}
          disabled={!editable}
          className="rounded bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
        >
          Lưu
        </button>
      </section>

      {/* 4. CLO */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Chuẩn đầu ra học phần (CLO)</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border bg-white text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">Mã</th>
                <th className="border p-2 text-left">Mô tả</th>
                <th className="border p-2">Bloom</th>
                <th className="border p-2"></th>
              </tr>
            </thead>
            <tbody>
              {clos.map((c) => (
                <tr key={c.id}>
                  <td className="border p-2 text-center">{c.code}</td>
                  <td className="border p-2">
                    {c.description}
                    {c.description_en && (
                      <div className="mt-1 text-xs italic text-slate-500">{c.description_en}</div>
                    )}
                  </td>
                  <td className="border p-2 text-center">{c.bloom_level}</td>
                  <td className="border p-2 text-center">
                    {editable && (
                      <button
                        onClick={() => deleteClo(c.id)}
                        className="text-red-600 hover:underline"
                      >
                        Xóa
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {clos.length === 0 && (
                <tr>
                  <td colSpan={4} className="border p-2 text-center text-slate-500">
                    Chưa có CLO.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {editable && (
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <input
              value={cloCode}
              onChange={(e) => setCloCode(e.target.value)}
              placeholder="Mã (CLO1)"
              className="rounded border p-2 text-sm"
            />
            <input
              value={cloDesc}
              onChange={(e) => setCloDesc(e.target.value)}
              placeholder="Mô tả"
              className="flex-1 rounded border p-2 text-sm"
            />
            <select
              value={cloBloom}
              onChange={(e) => setCloBloom(e.target.value)}
              className="rounded border bg-white p-2 text-sm"
            >
              {BLOOM_LEVELS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
            <button
              onClick={addClo}
              className="rounded bg-indigo-600 px-4 py-2 text-white"
            >
              Thêm CLO
            </button>
          </div>
        )}
      </section>

      {/* 5. Ma trận CLO×PLO */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Ma trận CLO × PLO (I/R/M)</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border bg-white text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2 text-left">CLO</th>
                {plos.map((p) => (
                  <th key={p.id} className="border p-2">
                    {p.code}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {clos.map((c) => (
                <tr key={c.id}>
                  <td className="border p-2">{c.code}</td>
                  {plos.map((p) => (
                    <td key={p.id} className="border p-1 text-center">
                      <select
                        value={levelOf(c.id, p.id)}
                        onChange={(e) =>
                          setCloPloLevel(c.id, p.id, e.target.value)
                        }
                        disabled={!editable}
                        className="rounded border bg-white p-1"
                      >
                        {PLO_LEVELS.map((l) => (
                          <option key={l} value={l}>
                            {l || "–"}
                          </option>
                        ))}
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
              {(clos.length === 0 || plos.length === 0) && (
                <tr>
                  <td
                    colSpan={Math.max(plos.length + 1, 2)}
                    className="border p-2 text-center text-slate-500"
                  >
                    Cần có CLO và PLO để lập ma trận.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 6. Đánh giá */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Đánh giá</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border bg-white text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2 text-left">Tên</th>
                <th className="border p-2">Loại</th>
                <th className="border p-2">Trọng số (%)</th>
                <th className="border p-2">CLO</th>
                <th className="border p-2"></th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => {
                const criteria = a.rubric_json?.criteria || [];
                return (
                  <Fragment key={a.id}>
                    <tr>
                      <td className="border p-2">{a.name}</td>
                      <td className="border p-2 text-center">{a.type}</td>
                      <td className="border p-2 text-center">{a.weight_percent}</td>
                      <td className="border p-2 text-center">
                        {(a.clo_ids || []).map(cloLabel).join(", ")}
                      </td>
                      <td className="border p-2 text-center">
                        {editable && (
                          <div className="flex flex-col gap-1">
                            <button
                              onClick={() => openRubricEditor(a)}
                              className="text-indigo-600 hover:underline"
                            >
                              {criteria.length > 0 ? "Sửa rubric" : "+ Rubric"}
                            </button>
                            <button
                              onClick={() => deleteAssessment(a.id)}
                              className="text-red-600 hover:underline"
                            >
                              Xóa
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {/* Chế độ SỬA rubric */}
                    {editingRubric === a.id ? (
                      <tr>
                        <td colSpan={5} className="border bg-indigo-50/50 p-3">
                          <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-600">
                              Sửa rubric — {a.name}
                            </span>
                            <button
                              onClick={() =>
                                setDraftCriteria([...draftCriteria, { name: "", weight_percent: 0, levels: "" }])
                              }
                              className="text-xs text-indigo-600 hover:underline"
                            >
                              + Thêm tiêu chí
                            </button>
                          </div>
                          {draftCriteria.map((cr, i) => (
                            <div key={i} className="mb-2 grid grid-cols-12 gap-2">
                              <input
                                className="col-span-4 rounded border p-1 text-xs"
                                placeholder="Tên tiêu chí"
                                value={cr.name}
                                onChange={(e) => {
                                  const d = [...draftCriteria];
                                  d[i] = { ...cr, name: e.target.value };
                                  setDraftCriteria(d);
                                }}
                              />
                              <input
                                type="number"
                                className="col-span-2 rounded border p-1 text-xs"
                                placeholder="Trọng số %"
                                value={cr.weight_percent}
                                onChange={(e) => {
                                  const d = [...draftCriteria];
                                  d[i] = { ...cr, weight_percent: e.target.value };
                                  setDraftCriteria(d);
                                }}
                              />
                              <textarea
                                className="col-span-5 rounded border p-1 text-xs"
                                placeholder="Các mức chất lượng (mỗi dòng một mức, vd: Giỏi: ...)"
                                rows={2}
                                value={cr.levels}
                                onChange={(e) => {
                                  const d = [...draftCriteria];
                                  d[i] = { ...cr, levels: e.target.value };
                                  setDraftCriteria(d);
                                }}
                              />
                              <button
                                onClick={() => setDraftCriteria(draftCriteria.filter((_, j) => j !== i))}
                                className="col-span-1 text-xs text-red-600 hover:underline"
                              >
                                Xóa
                              </button>
                            </div>
                          ))}
                          <div className="mt-2 flex gap-2">
                            <button
                              onClick={() => saveRubric(a)}
                              className="rounded bg-green-600 px-3 py-1 text-xs text-white"
                            >
                              Lưu rubric
                            </button>
                            <button
                              onClick={() => {
                                setEditingRubric(null);
                                setDraftCriteria([]);
                              }}
                              className="rounded bg-slate-100 px-3 py-1 text-xs"
                            >
                              Hủy
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      criteria.length > 0 && (
                        <tr>
                          <td colSpan={5} className="border bg-slate-50 p-2">
                            <div className="text-xs font-semibold text-slate-600">
                              Rubric chấm điểm — {a.name}
                            </div>
                            <table className="mt-1 w-full text-xs">
                              <thead>
                                <tr className="text-slate-500">
                                  <th className="p-1 text-left">Tiêu chí</th>
                                  <th className="p-1">Trọng số</th>
                                  <th className="p-1 text-left">Các mức chất lượng</th>
                                </tr>
                              </thead>
                              <tbody>
                                {criteria.map((cr: any, i: number) => (
                                  <tr key={i} className="align-top">
                                    <td className="p-1">{cr.name}</td>
                                    <td className="p-1 text-center">{cr.weight_percent}%</td>
                                    <td className="p-1">
                                      <ul className="list-disc pl-4">
                                        {(cr.levels || []).map((lv: string, j: number) => (
                                          <li key={j}>{lv}</li>
                                        ))}
                                      </ul>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )
                    )}
                  </Fragment>
                );
              })}
              {assessments.length === 0 && (
                <tr>
                  <td colSpan={5} className="border p-2 text-center text-slate-500">
                    Chưa có đánh giá.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p
          className={`mt-2 text-sm ${
            totalWeight === 100 ? "text-slate-600" : "text-red-600"
          }`}
        >
          Tổng trọng số: {totalWeight}%
          {totalWeight !== 100 && " (cần bằng 100%)"}
        </p>
        {editable && (
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <input
                value={asName}
                onChange={(e) => setAsName(e.target.value)}
                placeholder="Tên"
                className="rounded border p-2 text-sm"
              />
              <input
                value={asType}
                onChange={(e) => setAsType(e.target.value)}
                placeholder="Loại (giữa kỳ...)"
                className="rounded border p-2 text-sm"
              />
              <input
                type="number"
                value={asWeight}
                onChange={(e) => setAsWeight(Number(e.target.value))}
                placeholder="Trọng số %"
                className="w-28 rounded border p-2 text-sm"
              />
              <button
                onClick={addAssessment}
                className="rounded bg-indigo-600 px-4 py-2 text-white"
              >
                Thêm đánh giá
              </button>
            </div>
            <div className="flex flex-wrap gap-3 text-sm">
              {clos.map((c) => (
                <label key={c.id} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={asClos.includes(c.id)}
                    onChange={() => setAsClos((cur) => toggleIn(cur, c.id))}
                  />
                  {c.code}
                </label>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 7. Kế hoạch giảng dạy */}
      <section className="rounded border bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold">Kế hoạch giảng dạy</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full border bg-white text-sm">
            <thead>
              <tr className="bg-slate-100">
                <th className="border p-2">Tuần</th>
                <th className="border p-2 text-left">Chủ đề</th>
                <th className="border p-2">CLO</th>
                <th className="border p-2"></th>
              </tr>
            </thead>
            <tbody>
              {lessons.map((l) => (
                <tr key={l.id}>
                  <td className="border p-2 text-center">{l.week}</td>
                  <td className="border p-2">{l.topic}</td>
                  <td className="border p-2 text-center">
                    {(l.clo_ids || []).map(cloLabel).join(", ")}
                  </td>
                  <td className="border p-2 text-center">
                    {editable && (
                      <button
                        onClick={() => deleteLesson(l.id)}
                        className="text-red-600 hover:underline"
                      >
                        Xóa
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {lessons.length === 0 && (
                <tr>
                  <td colSpan={4} className="border p-2 text-center text-slate-500">
                    Chưa có kế hoạch.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {editable && (
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <input
                type="number"
                value={lsWeek}
                onChange={(e) => setLsWeek(Number(e.target.value))}
                placeholder="Tuần"
                className="w-24 rounded border p-2 text-sm"
              />
              <input
                value={lsTopic}
                onChange={(e) => setLsTopic(e.target.value)}
                placeholder="Chủ đề"
                className="flex-1 rounded border p-2 text-sm"
              />
              <button
                onClick={addLesson}
                className="rounded bg-indigo-600 px-4 py-2 text-white"
              >
                Thêm buổi học
              </button>
            </div>
            <div className="flex flex-wrap gap-3 text-sm">
              {clos.map((c) => (
                <label key={c.id} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={lsClos.includes(c.id)}
                    onChange={() => setLsClos((cur) => toggleIn(cur, c.id))}
                  />
                  {c.code}
                </label>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
