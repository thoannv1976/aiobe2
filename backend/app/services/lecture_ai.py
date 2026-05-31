"""AI viết bài giảng theo buổi từ giáo trình + CLO (SPEC mục 10 — Lecture Agent)."""
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


LECTURE_PROMPT = """Bạn là chuyên gia thiết kế bài giảng đại học theo OBE. Hãy soạn BÀI GIẢNG cho \
MỘT BUỔI HỌC, bám sát CLO và nội dung học phần/giáo trình.

Bài giảng cần có cấu trúc: mục tiêu buổi học (gắn CLO), hoạt động mở đầu, phần giảng lý thuyết, \
ví dụ thực tế, hoạt động thảo luận, bài tập vận dụng, câu hỏi kiểm tra nhanh, kết luận, nhiệm vụ tự học.

Chỉ trả về DUY NHẤT JSON:
{
  "content_markdown": "nội dung bài giảng đầy đủ dạng Markdown (## cho từng phần)",
  "slides": [{"title":"Tiêu đề slide","bullets":["ý 1","ý 2","ý 3"]}]
}
Soạn 8-15 slide cô đọng. Nội dung tiếng Việt, học thuật, thực tiễn."""


def generate_lecture_ai(
    course: dict, session_title: str, clos: list[dict], material: str = ""
) -> dict:
    """Trả về {content_markdown, slides:[{title,bullets}]}."""
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"BUỔI HỌC: {session_title}\n"
        f"CLO liên quan:\n{clo_lines}\n"
        + (f"\nNGỮ LIỆU TỪ GIÁO TRÌNH (bám sát):\n\"\"\"\n{material[:15000]}\n\"\"\"\n" if material.strip() else "")
        + "\nHãy soạn bài giảng cho buổi học này."
    )
    raw = llm_complete(LECTURE_PROMPT, user, max_tokens=8000)
    data = json.loads(_strip_to_json(raw))
    return {
        "content_markdown": str(data.get("content_markdown", "")),
        "slides": data.get("slides", []) if isinstance(data.get("slides"), list) else [],
    }
