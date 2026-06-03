"""Sinh ngân hàng câu hỏi bằng AI theo CLO + Bloom + độ khó (SPEC 4.5).

Câu hỏi gắn CLO + mức Bloom + độ khó, ép trả JSON, validate Pydantic trước khi ghi.
"""
from __future__ import annotations

import json

from app.schemas.question_gen import GeneratedQuestions, ImprovedQuestions
from app.services.llm import llm_complete

QUESTION_SYSTEM_PROMPT = """Bạn là chuyên gia khảo thí theo chuẩn OBE. Nhiệm vụ: soạn CÂU HỎI \
cho ngân hàng đề thi của một học phần, bám sát CHUẨN ĐẦU RA HỌC PHẦN (CLO) và mức nhận thức Bloom.

Yêu cầu bắt buộc:
- MỖI câu hỏi gắn với đúng một CLO (dùng mã CLO được cung cấp) và một mức Bloom phù hợp nội dung CLO.
- BÁM SÁT NỘI DUNG GIÁO TRÌNH được cung cấp cho từng CLO (nếu có): câu hỏi phải kiểm tra \
kiến thức/kỹ năng thực sự xuất hiện trong nội dung giáo trình đó, KHÔNG hỏi ngoài phạm vi.
- Độ khó (easy/medium/hard) và loại câu hỏi theo yêu cầu.
- Với câu trắc nghiệm (mcq_single/mcq_multi): cung cấp 4 phương án trong "options"; \
"answer" ghi rõ phương án đúng (vd "A" hoặc "A,C" cho nhiều đáp án).
- Với tự luận/điền khuyết/bài tập: "options" để rỗng, "answer" là đáp án/gợi ý chấm.
- MỖI câu có "explanation" GIẢI THÍCH đáp án (vì sao đúng/sai) ngắn gọn nhưng đầy đủ.
- MỖI câu có "source": NGUỒN kiến thức — ghi rõ chương/mục giáo trình hoặc buổi bài giảng \
liên quan (dựa trên ngữ liệu giáo trình được cung cấp; nếu không rõ thì ghi chủ đề CLO).
- VỚI CÂU TỰ LUẬN, BÀI TẬP (essay/exercise): BẮT BUỘC kèm "rubric" gồm 2–4 tiêu chí chấm điểm, \
mỗi tiêu chí có trọng số (%) và 3–4 mức chất lượng (Giỏi/Khá/Đạt/Chưa đạt) mô tả cụ thể.
- Nội dung chính xác về học thuật, rõ ràng, không mơ hồ, KHÔNG trùng lặp.

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{
  "questions": [
    {"clo_code":"CLO1","bloom_level":"remember|understand|apply|analyze|evaluate|create",
     "difficulty":"easy|medium|hard","type":"mcq_single|mcq_multi|fill_blank|short_answer|essay|exercise",
     "content":"","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"","points":1,
     "explanation":"giải thích đáp án","source":"Chương/mục giáo trình hoặc buổi bài giảng liên quan",
     "rubric":[{"name":"tiêu chí","weight_percent":50,"levels":["Giỏi: ...","Khá: ...","Đạt: ...","Chưa đạt: ..."]}]}
  ]
}
Lưu ý: "rubric" chỉ cần cho tự luận/bài tập; câu trắc nghiệm để "rubric" là mảng rỗng.
Chỉ dùng các mã CLO có trong dữ liệu được cung cấp."""


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


# Giới hạn ký tự ngữ liệu giáo trình nhúng cho mỗi CLO (tránh prompt quá dài).
MAX_MATERIAL_CHARS_PER_CLO = 12000


def generate_questions_ai(
    course: dict,
    clos: list[dict],            # [{code, description, bloom_level}]
    num_per_clo: int = 3,
    bloom_levels: list[str] | None = None,
    difficulties: list[str] | None = None,
    question_type: str = "mcq_single",
    clo_materials: dict[str, str] | None = None,  # {clo_code: nội dung giáo trình}
) -> GeneratedQuestions:
    """Gọi Claude sinh câu hỏi; validate Pydantic. Cần ANTHROPIC_API_KEY.

    clo_materials: nội dung các chương giáo trình gắn với từng CLO, dùng làm ngữ liệu
    để câu hỏi bám sát giáo trình thực tế (SPEC 4.4/4.5).
    """
    if not clos:
        raise ValueError("Học phần chưa có CLO để sinh câu hỏi.")
    materials = clo_materials or {}
    clo_blocks = []
    for c in clos:
        block = f"- {c['code']} ({c.get('bloom_level','')}): {c['description']}"
        mat = (materials.get(c["code"]) or "").strip()
        if mat:
            block += (
                f"\n  NỘI DUNG GIÁO TRÌNH gắn với {c['code']} (dùng làm ngữ liệu ra đề):\n"
                f"\"\"\"\n{mat[:MAX_MATERIAL_CHARS_PER_CLO]}\n\"\"\""
            )
        clo_blocks.append(block)
    clo_lines = "\n".join(clo_blocks)

    bloom_txt = ", ".join(bloom_levels) if bloom_levels else "phù hợp với từng CLO"
    diff_txt = ", ".join(difficulties) if difficulties else "đa dạng (dễ/trung bình/khó)"
    has_material = any((materials.get(c["code"]) or "").strip() for c in clos)

    user_content = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CÁC CLO:\n{clo_lines}\n\n"
        f"Hãy soạn {num_per_clo} câu hỏi CHO MỖI CLO ở trên.\n"
        f"- Loại câu hỏi: {question_type}.\n"
        f"- Mức Bloom: {bloom_txt}.\n"
        f"- Độ khó: {diff_txt}.\n"
        + ("- BÁM SÁT phần NỘI DUNG GIÁO TRÌNH cung cấp cho mỗi CLO; chỉ ra đề trong phạm vi đó.\n"
           if has_material else "")
        + "Phân bổ đều, tránh trùng lặp nội dung."
    )

    raw = llm_complete(QUESTION_SYSTEM_PROMPT, user_content, max_tokens=12000)
    data = json.loads(_strip_to_json(raw))
    return GeneratedQuestions.model_validate(data)


IMPROVE_SYSTEM_PROMPT = """Bạn là chuyên gia khảo thí theo chuẩn OBE/AUN-QA. Bạn được giao một số \
CÂU HỎI kèm KẾT QUẢ RÀ SOÁT CHẤT LƯỢNG chỉ ra vấn đề của từng câu.

Nhiệm vụ: VIẾT LẠI (nâng cấp) từng câu để khắc phục các vấn đề đã nêu, GIỮ NGUYÊN id và CLO của câu.
Yêu cầu bắt buộc cho mỗi câu sau nâng cấp:
- Mức Bloom ('bloom_level') phải khớp thực chất yêu cầu nhận thức của câu; chỉnh nếu bị gán sai.
- Trắc nghiệm (mcq_single/mcq_multi): đủ 4 phương án trong 'options', 'answer' ghi rõ phương án đúng \
(vd "A" hoặc "A,C"); các phương án nhiễu hợp lý, KHÔNG lộ đáp án, KHÔNG trùng.
- Tự luận/bài tập/điền khuyết: 'options' rỗng, 'answer' là đáp án/thang điểm; \
với essay/exercise BẮT BUỘC kèm 'rubric' 2–4 tiêu chí (mỗi tiêu chí có trọng số % và 3–4 mức chất lượng).
- 'explanation' giải thích đáp án rõ ràng, đầy đủ.
- Nội dung chính xác học thuật, rõ ràng, không mơ hồ.

Chỉ trả về DUY NHẤT JSON (không markdown, không văn bản thừa) theo schema:
{
  "questions": [
    {"id": 12, "content":"", "options":["A. ...","B. ...","C. ...","D. ..."], "answer":"",
     "explanation":"", "bloom_level":"remember|understand|apply|analyze|evaluate|create",
     "difficulty":"easy|medium|hard", "type":"mcq_single|mcq_multi|fill_blank|short_answer|essay|exercise",
     "rubric":[{"name":"tiêu chí","weight_percent":50,"levels":["Giỏi: ...","Khá: ...","Đạt: ...","Chưa đạt: ..."]}]}
  ]
}
Trả về ĐÚNG các id được yêu cầu nâng cấp."""


def improve_questions_ai(course: dict, questions: list[dict], qa: dict | None = None) -> ImprovedQuestions:
    """Nâng cấp các câu hỏi dựa trên kết quả rà soát chất lượng.

    questions: [{id,clo_code,bloom_level,difficulty,type,content,options,answer,explanation,has_rubric}].
    qa: kết quả review_questions_ai (dùng để biết vấn đề từng câu, key theo id).
    Trả về ImprovedQuestions (mỗi câu giữ id gốc) — caller cập nhật tại chỗ.
    """
    if not questions:
        raise ValueError("Không có câu hỏi nào để nâng cấp.")
    issues_by_id: dict[int, str] = {}
    for r in (qa or {}).get("question_reviews", []) or []:
        rid = r.get("id")
        if rid is None:
            continue
        parts = "; ".join(r.get("issues", []) or [])
        sug = r.get("suggestion", "") or ""
        issues_by_id[int(rid)] = (parts + (f" | gợi ý: {sug}" if sug else "")).strip()

    blocks = []
    for q in questions:
        opts = q.get("options") or []
        opt_txt = ("\n  PA: " + " / ".join(str(o) for o in opts)) if opts else ""
        problem = issues_by_id.get(int(q["id"]), "")
        blocks.append(
            f"[id={q['id']}] CLO {q.get('clo_code','?')} | {q.get('type','')} | "
            f"Bloom={q.get('bloom_level','')} | độ khó={q.get('difficulty','')}\n"
            f"  Nội dung: {q.get('content','')}{opt_txt}\n"
            f"  Đáp án: {q.get('answer','') or '(trống)'} | Giải thích: {q.get('explanation','') or '(trống)'}"
            + (f"\n  VẤN ĐỀ CẦN SỬA: {problem}" if problem else "\n  VẤN ĐỀ CẦN SỬA: rà soát và cải thiện tổng thể.")
        )
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        + (f"Nhận xét chung: {qa.get('summary','')}\n\n" if qa and qa.get("summary") else "\n")
        + "CÁC CÂU HỎI CẦN NÂNG CẤP:\n" + "\n\n".join(blocks)
    )
    raw = llm_complete(IMPROVE_SYSTEM_PROMPT, user, max_tokens=12000)
    data = json.loads(_strip_to_json(raw))
    return ImprovedQuestions.model_validate(data)
