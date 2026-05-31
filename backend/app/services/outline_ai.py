"""Sinh đề cương học phần bằng AI theo chuẩn OBE/AUN-QA (SPEC 4.3).

Căn cứ: thông tin học phần + CTĐT + PLO + PI + ma trận Học phần×PLO của học phần,
kèm (tùy chọn) mẫu đề cương và tài liệu chuẩn AUN-QA do người dùng upload.
Output JSON được validate bằng Pydantic (GeneratedOutline) — human-in-the-loop.
"""
from __future__ import annotations

import json

from app.config import settings
from app.schemas.outline_gen import GeneratedOutline

OUTLINE_SYSTEM_PROMPT = """Bạn là chuyên gia thiết kế chương trình đào tạo theo chuẩn OBE \
(Outcome-Based Education) và kiểm định AUN-QA. Nhiệm vụ: soạn ĐỀ CƯƠNG HỌC PHẦN tiếng Việt \
bảo đảm "constructive alignment" (nhất quán dọc CLO ↔ dạy-học ↔ đánh giá).

Yêu cầu bắt buộc về chất lượng (AUN-QA):
- CLO viết theo thang Bloom, đo lường được, phủ kiến thức/kỹ năng/thái độ phù hợp học phần.
- MỖI CLO phải ánh xạ tới ít nhất một PLO của chương trình (dùng đúng mã PLO được cung cấp), \
kèm mức đóng góp I (Introduce) / R (Reinforce) / M (Master) hợp lý với vai trò học phần.
- MỖI CLO phải được phủ bởi ít nhất một cấu phần đánh giá.
- Tổng trọng số các cấu phần đánh giá BẰNG ĐÚNG 100.
- Kế hoạch giảng dạy theo tuần, mỗi tuần gắn với CLO liên quan; phủ hết các CLO.

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa) theo schema:
{
  "description": "mô tả học phần",
  "teaching_methods": ["..."],
  "references": ["..."],
  "clos": [{"code":"CLO1","description":"","bloom_level":"remember|understand|apply|analyze|evaluate|create","plos":[{"plo_code":"PLO1","level":"I|R|M"}]}],
  "assessments": [{"name":"","type":"","weight_percent":0,"clo_codes":["CLO1"]}],
  "lessons": [{"week":1,"topic":"","clo_codes":["CLO1"]}]
}
Chỉ dùng các mã PLO có trong dữ liệu được cung cấp. KHÔNG bịa PLO không tồn tại."""


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


def generate_outline_ai(
    course: dict,
    plos: list[dict],
    pis: list[dict],
    course_plo: list[dict],
    template_text: str = "",
    aunqa_text: str = "",
) -> GeneratedOutline:
    """Gọi Claude sinh đề cương; validate Pydantic. Cần ANTHROPIC_API_KEY."""
    if not settings.anthropic_api_key:
        raise RuntimeError("Chưa cấu hình ANTHROPIC_API_KEY.")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    plo_lines = "\n".join(f"- {p['code']} [{p.get('category','')}]: {p['description']}" for p in plos)
    pi_lines = "\n".join(f"- {pi['code']} (thuộc {pi['plo_code']}): {pi['description']}" for pi in pis)
    cp_lines = "\n".join(f"- {cp['plo_code']}: mức {cp['level']}" for cp in course_plo) or "(chưa có)"

    parts = [
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')} "
        f"({course.get('credits','?')} tín chỉ, học kỳ {course.get('semester','?')}, loại {course.get('type','')}).",
        f"CHƯƠNG TRÌNH ĐÀO TẠO: {course.get('program_name','')}.",
        f"\nDANH SÁCH PLO CỦA CHƯƠNG TRÌNH:\n{plo_lines}",
        f"\nCHỈ BÁO PI:\n{pi_lines}" if pi_lines else "",
        f"\nMỨC ĐÓNG GÓP CỦA HỌC PHẦN NÀY VÀO PLO (ma trận Học phần×PLO):\n{cp_lines}",
    ]
    if template_text.strip():
        parts.append(f"\nMẪU ĐỀ CƯƠNG THAM KHẢO (bám cấu trúc/cách trình bày này):\n{template_text[:30000]}")
    if aunqa_text.strip():
        parts.append(f"\nTÀI LIỆU CHUẨN AUN-QA (đáp ứng các tiêu chí sau):\n{aunqa_text[:30000]}")
    parts.append(
        "\nHãy soạn đề cương cho học phần trên. Nếu ma trận Học phần×PLO có sẵn, "
        "ưu tiên ánh xạ CLO tới đúng các PLO đó với mức tương ứng."
    )
    user_content = "\n".join(p for p in parts if p)

    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=OUTLINE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(_strip_to_json(raw))
    return GeneratedOutline.model_validate(data)
