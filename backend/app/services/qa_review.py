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
