"""Sinh ngân hàng câu hỏi bằng AI theo CLO + Bloom + độ khó (SPEC 4.5).

Câu hỏi gắn CLO + mức Bloom + độ khó, ép trả JSON, validate Pydantic trước khi ghi.
"""
from __future__ import annotations

import json

from app.config import settings
from app.schemas.question_gen import GeneratedQuestions

QUESTION_SYSTEM_PROMPT = """Bạn là chuyên gia khảo thí theo chuẩn OBE. Nhiệm vụ: soạn CÂU HỎI \
cho ngân hàng đề thi của một học phần, bám sát CHUẨN ĐẦU RA HỌC PHẦN (CLO) và mức nhận thức Bloom.

Yêu cầu bắt buộc:
- MỖI câu hỏi gắn với đúng một CLO (dùng mã CLO được cung cấp) và một mức Bloom phù hợp nội dung CLO.
- Độ khó (easy/medium/hard) và loại câu hỏi theo yêu cầu.
- Với câu trắc nghiệm (mcq_single/mcq_multi): cung cấp 4 phương án trong "options"; \
"answer" ghi rõ phương án đúng (vd "A" hoặc "A,C" cho nhiều đáp án).
- Với tự luận/điền khuyết/bài tập: "options" để rỗng, "answer" là đáp án/gợi ý chấm.
- Mỗi câu có "explanation" giải thích ngắn gọn.
- Nội dung chính xác về học thuật, rõ ràng, không mơ hồ, KHÔNG trùng lặp.

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{
  "questions": [
    {"clo_code":"CLO1","bloom_level":"remember|understand|apply|analyze|evaluate|create",
     "difficulty":"easy|medium|hard","type":"mcq_single|mcq_multi|fill_blank|short_answer|essay|exercise",
     "content":"","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"","points":1,"explanation":""}
  ]
}
Chỉ dùng các mã CLO có trong dữ liệu được cung cấp."""


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


def generate_questions_ai(
    course: dict,
    clos: list[dict],            # [{code, description, bloom_level}]
    num_per_clo: int = 3,
    bloom_levels: list[str] | None = None,
    difficulties: list[str] | None = None,
    question_type: str = "mcq_single",
) -> GeneratedQuestions:
    """Gọi Claude sinh câu hỏi; validate Pydantic. Cần ANTHROPIC_API_KEY."""
    if not settings.anthropic_api_key:
        raise RuntimeError("Chưa cấu hình ANTHROPIC_API_KEY.")
    if not clos:
        raise ValueError("Học phần chưa có CLO để sinh câu hỏi.")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    clo_lines = "\n".join(
        f"- {c['code']} ({c.get('bloom_level','')}): {c['description']}" for c in clos
    )
    bloom_txt = ", ".join(bloom_levels) if bloom_levels else "phù hợp với từng CLO"
    diff_txt = ", ".join(difficulties) if difficulties else "đa dạng (dễ/trung bình/khó)"

    user_content = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CÁC CLO:\n{clo_lines}\n\n"
        f"Hãy soạn {num_per_clo} câu hỏi CHO MỖI CLO ở trên.\n"
        f"- Loại câu hỏi: {question_type}.\n"
        f"- Mức Bloom: {bloom_txt}.\n"
        f"- Độ khó: {diff_txt}.\n"
        "Phân bổ đều, tránh trùng lặp nội dung."
    )

    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=12000,
        system=QUESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(_strip_to_json(raw))
    return GeneratedQuestions.model_validate(data)
