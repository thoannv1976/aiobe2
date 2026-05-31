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
- BÁM SÁT NỘI DUNG GIÁO TRÌNH được cung cấp cho từng CLO (nếu có): câu hỏi phải kiểm tra \
kiến thức/kỹ năng thực sự xuất hiện trong nội dung giáo trình đó, KHÔNG hỏi ngoài phạm vi.
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
    if not settings.anthropic_api_key:
        raise RuntimeError("Chưa cấu hình ANTHROPIC_API_KEY.")
    if not clos:
        raise ValueError("Học phần chưa có CLO để sinh câu hỏi.")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
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

    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=12000,
        system=QUESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(_strip_to_json(raw))
    return GeneratedQuestions.model_validate(data)
