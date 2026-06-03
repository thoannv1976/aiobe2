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


# ---------------------------------------------------------------------------
# Đánh giá + nâng cấp bài giảng bằng AI (SPEC mục 10)
# ---------------------------------------------------------------------------
LECTURE_QA_PROMPT = """Bạn là chuyên gia thiết kế bài giảng đại học theo OBE. Hãy ĐÁNH GIÁ chất lượng \
một BÀI GIẢNG (một buổi học) dựa trên CLO liên quan.

Kiểm tra theo tiêu chí:
- Mục tiêu buổi học có gắn rõ CLO không; nội dung có phục vụ đạt CLO không.
- Cấu trúc sư phạm đầy đủ: mở đầu, giảng lý thuyết, VÍ DỤ thực tế, hoạt động thảo luận, \
bài tập vận dụng, câu hỏi kiểm tra nhanh, kết luận, nhiệm vụ tự học.
- Chiều sâu học thuật và tính thực tiễn; mạch lạc.
- Bộ slide cô đọng, bám nội dung, số lượng hợp lý (8–15).

Chỉ trả về DUY NHẤT JSON:
{
  "score": 0-100,
  "summary": "nhận xét tổng quan ngắn gọn",
  "errors": ["thiếu sót nghiêm trọng cần bổ sung"],
  "warnings": ["điểm nên cải thiện"],
  "suggestions": ["đề xuất cụ thể để nâng chất lượng bài giảng"]
}"""


def _format_qa(qa: dict | None) -> str:
    if not qa:
        return ""
    parts: list[str] = []
    if qa.get("summary"):
        parts.append(f"Nhận xét: {qa['summary']}")
    for key, label in (("errors", "LỖI cần khắc phục"), ("warnings", "CẢNH BÁO"),
                       ("suggestions", "ĐỀ XUẤT cải thiện")):
        items = qa.get(key) or []
        if items:
            parts.append(f"{label}:\n" + "\n".join(f"- {x}" for x in items))
    if not parts:
        return ""
    return "\n\nKẾT QUẢ ĐÁNH GIÁ CẦN KHẮC PHỤC:\n" + "\n\n".join(parts)


def review_lecture_ai(course: dict, session_title: str, clos: list[dict],
                      content: str, slides_count: int = 0) -> dict:
    """Đánh giá chất lượng bài giảng. Trả {score,summary,errors,warnings,suggestions}."""
    if not (content or "").strip():
        raise ValueError("Bài giảng chưa có nội dung để đánh giá.")
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"BUỔI HỌC: {session_title}\nSố slide hiện có: {slides_count}.\n"
        f"CLO liên quan:\n{clo_lines}\n\n"
        f"NỘI DUNG BÀI GIẢNG:\n\"\"\"\n{content[:25000]}\n\"\"\""
    )
    raw = llm_complete(LECTURE_QA_PROMPT, user, max_tokens=3000)
    return json.loads(_strip_to_json(raw))


LECTURE_IMPROVE_PROMPT = """Bạn là chuyên gia thiết kế bài giảng đại học theo OBE. Bạn được giao một \
BÀI GIẢNG kèm KẾT QUẢ ĐÁNH GIÁ chỉ ra điểm cần khắc phục. Hãy VIẾT LẠI (nâng cấp) bài giảng để khắc phục \
từng điểm: bổ sung phần còn thiếu (mục tiêu gắn CLO, ví dụ, thảo luận, bài tập, kiểm tra nhanh, tự học), \
làm sâu nội dung, cập nhật bộ slide cho cô đọng. GIỮ LẠI những phần đã tốt.

Chỉ trả về DUY NHẤT JSON:
{
  "content_markdown": "nội dung bài giảng đã nâng cấp (Markdown, ## cho từng phần)",
  "slides": [{"title":"Tiêu đề slide","bullets":["ý 1","ý 2","ý 3"]}]
}
Soạn 8-15 slide cô đọng. Nội dung tiếng Việt, học thuật, thực tiễn."""


def improve_lecture_ai(course: dict, session_title: str, clos: list[dict],
                       content: str, slides: list | None = None, qa: dict | None = None) -> dict:
    """Nâng cấp bài giảng dựa trên kết quả đánh giá. Trả {content_markdown, slides}."""
    if not (content or "").strip():
        raise ValueError("Bài giảng chưa có nội dung để nâng cấp.")
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"BUỔI HỌC: {session_title}\nSố slide hiện có: {len(slides or [])}.\n"
        f"CLO liên quan:\n{clo_lines}\n\n"
        f"NỘI DUNG HIỆN TẠI:\n\"\"\"\n{content[:25000]}\n\"\"\""
        + _format_qa(qa)
        + "\n\nHãy trả về bài giảng đã nâng cấp."
    )
    raw = llm_complete(LECTURE_IMPROVE_PROMPT, user, max_tokens=8000)
    data = json.loads(_strip_to_json(raw))
    return {
        "content_markdown": str(data.get("content_markdown", "")),
        "slides": data.get("slides", []) if isinstance(data.get("slides"), list) else [],
    }
