"""AI kiểm tra chất lượng (QA Reviewer Agent) & chuẩn hóa PLO (SPEC mục 14, bước 2).

Dùng LLM rà soát PLO/CLO/alignment/câu hỏi, phát hiện lỗi và gợi ý sửa.
Output validate Pydantic; con người quyết định cuối.
"""
from __future__ import annotations

import json

from app.services.llm import llm_complete


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    a, b = t.find("{"), t.rfind("}")
    return t[a : b + 1] if a != -1 and b != -1 else t


# ---------------------------------------------------------------------------
# Chuẩn hóa PLO (SPEC bước 2): nhận xét từng PLO, đề xuất viết lại theo Bloom
# ---------------------------------------------------------------------------
PLO_REVIEW_PROMPT = """Bạn là chuyên gia thiết kế chương trình đào tạo theo OBE và kiểm định AUN-QA. \
Hãy rà soát danh sách PLO (chuẩn đầu ra chương trình) của một chương trình đào tạo.

Với MỖI PLO, đánh giá:
- measurable: PLO có ĐO LƯỜNG ĐƯỢC không (true/false).
- bloom_level: mức Bloom phù hợp (remember/understand/apply/analyze/evaluate/create).
- category: knowledge | skill | attitude.
- issues: danh sách vấn đề (quá rộng, mơ hồ, không có động từ hành động, không đo được, trùng lặp…).
- suggestion: bản viết lại PLO tốt hơn theo Bloom (giữ nguyên ý, rõ ràng, đo được).

Ngoài ra:
- overall_issues: cảnh báo cấp chương trình (PLO trùng nhau, thiếu năng lực quan trọng…).

Chỉ trả về DUY NHẤT JSON:
{
  "plos": [{"code":"PLO1","measurable":true,"bloom_level":"apply","category":"knowledge",
            "issues":["..."],"suggestion":"..."}],
  "overall_issues": ["..."]
}"""


def review_plos_ai(plos: list[dict]) -> dict:
    """plos: [{code, description, category, bloom_level}]."""
    if not plos:
        raise ValueError("Chương trình chưa có PLO để rà soát.")
    lines = "\n".join(
        f"- {p['code']} [{p.get('category','')}/{p.get('bloom_level','')}]: {p['description']}"
        for p in plos
    )
    raw = llm_complete(PLO_REVIEW_PROMPT, f"Danh sách PLO:\n{lines}", max_tokens=6000)
    return json.loads(_strip_to_json(raw))


# ---------------------------------------------------------------------------
# QA Reviewer tổng thể đề cương (SPEC mục 14): rà CLO/alignment/đánh giá
# ---------------------------------------------------------------------------
OUTLINE_QA_PROMPT = """Bạn là chuyên gia kiểm định chất lượng đào tạo theo AUN-QA. \
Hãy rà soát chất lượng một ĐỀ CƯƠNG HỌC PHẦN dựa trên dữ liệu được cung cấp (CLO, ma trận CLO–PLO, \
các cấu phần đánh giá, kế hoạch giảng dạy).

Kiểm tra và CHỈ RA LỖI (nếu có) theo các tiêu chí:
- CLO có dùng động từ hành động, đo lường được không.
- CLO có liên kết PLO/PI không.
- Mỗi CLO có được phủ bởi nội dung giảng dạy và phương pháp đánh giá không.
- Hình thức đánh giá có phù hợp mức Bloom của CLO không.
- Tổng trọng số đánh giá có = 100% không.
- CLO viết quá rộng/mơ hồ/chỉ mô tả nội dung dạy học.

Chỉ trả về DUY NHẤT JSON:
{
  "score": 0-100,
  "summary": "nhận xét tổng quan ngắn gọn",
  "errors": ["lỗi nghiêm trọng cần sửa"],
  "warnings": ["cảnh báo nên xem lại"],
  "clo_reviews": [{"code":"CLO1","measurable":true,"issues":["..."],"suggestion":"..."}]
}"""


def review_outline_ai(payload: dict) -> dict:
    """payload: {course, clos:[{code,description,bloom_level,plos:[...]}],
    assessments:[{name,weight,clos:[...]}], lessons:[{topic,clos:[...]}]}."""
    clos = payload.get("clos", [])
    if not clos:
        raise ValueError("Đề cương chưa có CLO để rà soát.")
    clo_lines = "\n".join(
        f"- {c['code']} ({c.get('bloom_level','')}): {c['description']} "
        f"[PLO: {', '.join(c.get('plos', [])) or 'CHƯA ÁNH XẠ'}]"
        for c in clos
    )
    a_lines = "\n".join(
        f"- {a['name']} ({a.get('weight',0)}%) → CLO: {', '.join(a.get('clos', [])) or 'KHÔNG'}"
        for a in payload.get("assessments", [])
    ) or "(chưa có)"
    l_lines = "\n".join(
        f"- {l['topic']} → CLO: {', '.join(l.get('clos', [])) or 'KHÔNG'}"
        for l in payload.get("lessons", [])
    ) or "(chưa có)"
    course = payload.get("course", {})
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CLO:\n{clo_lines}\n\nĐÁNH GIÁ:\n{a_lines}\n\nKẾ HOẠCH DẠY:\n{l_lines}"
    )
    raw = llm_complete(OUTLINE_QA_PROMPT, user, max_tokens=8000)
    return json.loads(_strip_to_json(raw))


# ---------------------------------------------------------------------------
# QA Reviewer NGÂN HÀNG CÂU HỎI (SPEC 4.5): rà chất lượng từng câu + tổng thể
# ---------------------------------------------------------------------------
QUESTION_QA_PROMPT = """Bạn là chuyên gia khảo thí theo chuẩn OBE/AUN-QA. Hãy rà soát chất lượng \
NGÂN HÀNG CÂU HỎI của một học phần.

Kiểm tra và CHỈ RA LỖI (nếu có) theo các tiêu chí:
- Câu hỏi có gắn ĐÚNG CLO và mức Bloom có khớp nội dung câu hỏi không (vd câu chỉ "nhớ" mà gán "analyze").
- Trắc nghiệm: đủ phương án, có đáp án đúng rõ ràng, các phương án nhiễu hợp lý, KHÔNG lộ đáp án/đáp án trùng.
- Tự luận/bài tập: có đáp án/thang điểm và RUBRIC chấm điểm.
- Nội dung chính xác học thuật, rõ ràng, KHÔNG mơ hồ, KHÔNG trùng lặp với câu khác.
- Có giải thích đáp án (explanation) và nguồn (source) hợp lý.
- Tổng thể: độ phủ CLO và cân đối mức Bloom/độ khó của ngân hàng (không dồn hết vào Nhớ/Hiểu/dễ).

Với mỗi câu có vấn đề, nêu severity ("error" nếu nghiêm trọng phải sửa, "warning" nếu nên xem lại), \
liệt kê issues và một suggestion sửa ngắn gọn. Câu đạt thì KHÔNG cần liệt kê (để giảm độ dài).

Chỉ trả về DUY NHẤT JSON:
{
  "score": 0-100,
  "summary": "nhận xét tổng quan ngắn gọn (độ phủ CLO, cân đối Bloom, chất lượng chung)",
  "errors": ["lỗi cấp ngân hàng cần sửa"],
  "warnings": ["cảnh báo cấp ngân hàng"],
  "question_reviews": [{"id": 12, "severity":"error|warning", "issues":["..."], "suggestion":"..."}]
}"""

# Giới hạn số câu đưa vào một lần rà soát (an toàn độ dài prompt).
MAX_QUESTIONS_REVIEW = 60


def _question_line(q: dict) -> str:
    opts = q.get("options") or []
    opt_txt = (" | PA: " + " / ".join(str(o) for o in opts)) if opts else ""
    rub = "có rubric" if q.get("has_rubric") else "KHÔNG rubric"
    return (
        f"[id={q['id']}] CLO {q.get('clo_code','?')} | {q.get('type','')} | "
        f"Bloom={q.get('bloom_level','')} | độ khó={q.get('difficulty','')} | {rub}\n"
        f"  Nội dung: {q.get('content','')}{opt_txt}\n"
        f"  Đáp án: {q.get('answer','') or '(trống)'} | Giải thích: {q.get('explanation','') or '(trống)'}"
    )


def review_questions_ai(course: dict, questions: list[dict]) -> dict:
    """Rà soát chất lượng ngân hàng câu hỏi. questions: [{id,clo_code,bloom_level,
    difficulty,type,content,options,answer,explanation,has_rubric}]."""
    if not questions:
        raise ValueError("Ngân hàng câu hỏi đang trống — chưa có câu để rà soát.")
    lines = "\n".join(_question_line(q) for q in questions[:MAX_QUESTIONS_REVIEW])
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"DANH SÁCH CÂU HỎI ({min(len(questions), MAX_QUESTIONS_REVIEW)} câu):\n{lines}"
    )
    raw = llm_complete(QUESTION_QA_PROMPT, user, max_tokens=8000)
    return json.loads(_strip_to_json(raw))


# ---------------------------------------------------------------------------
# QA Reviewer MA TRẬN ĐỀ THI (SPEC mục 11/12): đánh giá blueprint theo AUN-QA
# ---------------------------------------------------------------------------
MATRIX_QA_PROMPT = """Bạn là chuyên gia khảo thí và kiểm định AUN-QA (Criterion 4 - Student Assessment). \
Hãy ĐÁNH GIÁ một MA TRẬN ĐỀ THI (test blueprint) của học phần.

Kiểm tra theo tiêu chí:
- TỔNG ĐIỂM có bằng đúng thang điểm khai báo không.
- Độ phủ CLO: ma trận có đo đủ các CLO trọng yếu (đặc biệt CLO của cấu phần đánh giá gắn kèm) không.
- Cân đối mức Bloom: có tỷ lệ hợp lý cho mức bậc cao (Vận dụng/Phân tích/Đánh giá), không dồn hết vào Nhớ/Hiểu.
- Tính khả thi với ngân hàng: số câu mỗi ô không vượt số câu Đã duyệt sẵn có.
- Constructive alignment với cấu phần đánh giá của đề cương (nếu có).

Chỉ trả về DUY NHẤT JSON:
{
  "score": 0-100,
  "summary": "nhận xét tổng quan ngắn gọn",
  "errors": ["lỗi nghiêm trọng cần sửa"],
  "warnings": ["cảnh báo nên xem lại"],
  "suggestions": ["đề xuất cải thiện cụ thể"]
}"""


def review_matrix_ai(payload: dict) -> dict:
    """payload: {course, name, total_points, cells:[{clo_code,bloom_level,difficulty,count,points_each}],
    bank_cells:[{clo_code,bloom_level,difficulty,available}], assessment:{name,clo_codes}}."""
    cells = payload.get("cells", [])
    if not cells:
        raise ValueError("Ma trận chưa có ô nào để đánh giá.")
    cur = "\n".join(
        f"- {c.get('clo_code')} × {c.get('bloom_level')} × {c.get('difficulty')}: "
        f"{c.get('count')} câu × {c.get('points_each')}đ"
        for c in cells
    )
    bank = "\n".join(
        f"- {b['clo_code']} × {b['bloom_level']} × {b['difficulty']}: có {b.get('available',0)} câu Đã duyệt"
        for b in payload.get("bank_cells", []) if b.get("available", 0) > 0
    ) or "(không có dữ liệu ngân hàng)"
    a = payload.get("assessment") or {}
    a_txt = (
        f"\nCẤU PHẦN ĐÁNH GIÁ GẮN KÈM: {a.get('name','')} — cần đo CLO: "
        f"{', '.join(a.get('clo_codes', [])) or '(không rõ)'}." if a else ""
    )
    course = payload.get("course", {})
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"MA TRẬN '{payload.get('name','')}' — thang điểm khai báo: {payload.get('total_points')}.\n"
        f"CÁC Ô (CLO×Bloom×độ khó):\n{cur}\n\n"
        f"NGÂN HÀNG (câu Đã duyệt theo tổ hợp):\n{bank}{a_txt}"
    )
    raw = llm_complete(MATRIX_QA_PROMPT, user, max_tokens=4000)
    return json.loads(_strip_to_json(raw))
