"""Sinh giáo trình bằng AI gắn với CLO của đề cương (SPEC 4.4).

Gọi LLM qua lớp thống nhất app.services.llm (Claude/OpenAI tùy key admin cấu hình).
"""
from __future__ import annotations

import json

from app.schemas.textbook_gen import GeneratedChapterOutline
from app.services.llm import llm_complete


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    return t[start : end + 1] if start != -1 and end != -1 else t


OUTLINE_PROMPT = """Bạn là chuyên gia biên soạn giáo trình đại học theo chuẩn OBE. \
Hãy đề xuất CẤU TRÚC CHƯƠNG cho giáo trình một học phần, bám sát các CLO (chuẩn đầu ra học phần). \
Mỗi chương gắn với (các) CLO liên quan; toàn bộ CLO phải được phủ.

Chỉ trả về DUY NHẤT một JSON hợp lệ (không markdown, không văn bản thừa):
{
  "chapters": [
    {"order":1,"title":"Tên chương","clo_codes":["CLO1"],"summary":"tóm tắt nội dung chương"}
  ]
}
Chỉ dùng các mã CLO được cung cấp."""


def generate_chapter_outline_ai(
    course: dict, clos: list[dict], num_chapters: int = 0
) -> GeneratedChapterOutline:
    """Sinh dàn ý chương giáo trình."""
    if not clos:
        raise ValueError("Học phần chưa có CLO để sinh giáo trình.")
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos)
    n_txt = f"khoảng {num_chapters} chương" if num_chapters else "số chương hợp lý"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CÁC CLO:\n{clo_lines}\n\n"
        f"Đề xuất {n_txt} cho giáo trình, phủ hết các CLO trên."
    )
    raw = llm_complete(OUTLINE_PROMPT, user, max_tokens=4000)
    data = json.loads(_strip_to_json(raw))
    return GeneratedChapterOutline.model_validate(data)


# ---------------------------------------------------------------------------
# Sinh nội dung chương (SPEC 4.4)
# ---------------------------------------------------------------------------
CONTENT_PROMPT = """Bạn là tác giả giáo trình đại học. Hãy soạn NỘI DUNG CHI TIẾT cho một chương \
giáo trình tiếng Việt, học thuật, mạch lạc, có cấu trúc rõ ràng (mở đầu, các mục, ví dụ, tóm tắt, \
câu hỏi ôn tập). Bám sát các CLO liên quan. Định dạng Markdown (dùng ##, ###, danh sách, bảng nếu cần). \
Chỉ trả về NỘI DUNG chương (Markdown thuần), KHÔNG kèm lời dẫn."""


def generate_chapter_content_ai(
    course: dict, chapter_title: str, clos: list[dict], chapter_summary: str = ""
) -> str:
    """Soạn nội dung Markdown một chương (NGẮN — 1 lần gọi, ~10-12 trang)."""
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CHƯƠNG: {chapter_title}\n"
        f"CLO liên quan:\n{clo_lines}\n"
        + (f"Gợi ý nội dung: {chapter_summary}\n" if chapter_summary else "")
        + "\nHãy soạn nội dung chi tiết cho chương này."
    )
    return llm_complete(CONTENT_PROMPT, user, max_tokens=8000).strip()


# --- Sinh SÂU: chương dài 25-40 trang bằng cách viết từng mục rồi ghép ---
SECTION_OUTLINE_PROMPT = """Bạn là tác giả giáo trình đại học. Hãy lập DÀN Ý CÁC MỤC (sections) \
cho một chương giáo trình, đủ chi tiết để khi viết ra đạt độ dài yêu cầu. \
Chỉ trả về DUY NHẤT JSON: {"sections":[{"title":"Tên mục","points":"các ý chính cần trình bày"}]}."""

SECTION_CONTENT_PROMPT = """Bạn là tác giả giáo trình đại học. Hãy viết NỘI DUNG CHI TIẾT, học thuật, \
đầy đủ cho MỘT MỤC của chương giáo trình tiếng Việt: giải thích cặn kẽ, có ví dụ minh họa, \
bảng/sơ đồ mô tả bằng lời nếu cần. Định dạng Markdown (bắt đầu bằng '## ' cho tên mục). \
Viết dài, sâu. Chỉ trả về nội dung mục (Markdown thuần), KHÔNG kèm lời dẫn."""


def _chapter_section_outline(course: dict, chapter_title: str, clos: list[dict],
                             summary: str, target_pages: int, max_sections: int) -> list[dict]:
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CHƯƠNG: {chapter_title}\nCLO:\n{clo_lines}\n"
        + (f"Tóm tắt: {summary}\n" if summary else "")
        + f"\nMục tiêu độ dài chương: khoảng {target_pages} trang A4. "
        f"Hãy chia thành {max_sections} mục lớn, cân đối."
    )
    raw = llm_complete(SECTION_OUTLINE_PROMPT, user, max_tokens=2000)
    data = json.loads(_strip_to_json(raw))
    secs = data.get("sections", []) if isinstance(data, dict) else []
    return secs[:max_sections]


def generate_chapter_content_deep_ai(
    course: dict, chapter_title: str, clos: list[dict], chapter_summary: str = "",
    target_pages: int = 30,
) -> str:
    """Soạn chương DÀI (~25-40 trang): lập dàn ý mục -> viết từng mục -> ghép.

    Mỗi mục là một lần gọi LLM (bounded), nên tổng chương dài vẫn an toàn về token.
    """
    # Ước lượng số mục: ~6-7 trang/mục.
    max_sections = max(3, min(8, round(target_pages / 6)))
    try:
        sections = _chapter_section_outline(
            course, chapter_title, clos, chapter_summary, target_pages, max_sections
        )
    except Exception:  # noqa: BLE001
        sections = []
    if not sections:
        # fallback: dùng cách ngắn nếu không lập được dàn ý mục
        return generate_chapter_content_ai(course, chapter_title, clos, chapter_summary)

    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    parts = [f"# {chapter_title}\n"]
    for i, sec in enumerate(sections, start=1):
        user = (
            f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
            f"CHƯƠNG: {chapter_title}\nCLO:\n{clo_lines}\n"
            f"MỤC {i}/{len(sections)}: {sec.get('title','')}\n"
            f"Các ý cần trình bày: {sec.get('points','')}\n"
            "\nHãy viết nội dung chi tiết, sâu cho MỤC này."
        )
        txt = llm_complete(SECTION_CONTENT_PROMPT, user, max_tokens=8000).strip()
        if txt:
            parts.append(txt)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Đánh giá + nâng cấp nội dung chương bằng AI (SPEC 4.4)
# ---------------------------------------------------------------------------
CHAPTER_QA_PROMPT = """Bạn là biên tập viên giáo trình đại học theo chuẩn OBE. Hãy ĐÁNH GIÁ chất lượng \
NỘI DUNG MỘT CHƯƠNG giáo trình dựa trên các CLO liên quan.

Kiểm tra theo tiêu chí:
- Độ phủ CLO: nội dung có dạy đủ kiến thức/kỹ năng của các CLO gắn với chương không.
- Tính chính xác và chiều sâu học thuật; lập luận mạch lạc.
- Cấu trúc đầy đủ: mở đầu, các mục rõ ràng, VÍ DỤ minh họa, tóm tắt, câu hỏi ôn tập.
- Độ dài/độ chi tiết phù hợp giáo trình đại học (không sơ sài, không chỉ là dàn ý).
- Trình bày rõ ràng (Markdown: đề mục, danh sách, bảng nếu cần).

Chỉ trả về DUY NHẤT JSON:
{
  "score": 0-100,
  "summary": "nhận xét tổng quan ngắn gọn",
  "errors": ["thiếu sót nghiêm trọng cần bổ sung"],
  "warnings": ["điểm nên cải thiện"],
  "suggestions": ["đề xuất cụ thể để nâng chất lượng chương"]
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


def review_chapter_ai(course: dict, chapter_title: str, clos: list[dict], content: str) -> dict:
    """Đánh giá chất lượng nội dung một chương. Trả {score,summary,errors,warnings,suggestions}."""
    if not (content or "").strip():
        raise ValueError("Chương chưa có nội dung để đánh giá.")
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CHƯƠNG: {chapter_title}\nCLO liên quan:\n{clo_lines}\n\n"
        f"NỘI DUNG CHƯƠNG:\n\"\"\"\n{content[:30000]}\n\"\"\""
    )
    raw = llm_complete(CHAPTER_QA_PROMPT, user, max_tokens=3000)
    return json.loads(_strip_to_json(raw))


CHAPTER_IMPROVE_PROMPT = """Bạn là tác giả giáo trình đại học. Bạn được giao NỘI DUNG MỘT CHƯƠNG \
kèm KẾT QUẢ ĐÁNH GIÁ chỉ ra điểm cần khắc phục. Hãy VIẾT LẠI (nâng cấp) chương để khắc phục từng điểm: \
bổ sung phần còn thiếu, làm sâu nội dung học thuật, thêm ví dụ minh họa, đảm bảo phủ đủ CLO, \
hoàn thiện cấu trúc (mở đầu, các mục, tóm tắt, câu hỏi ôn tập). GIỮ LẠI những phần đã tốt. \
Định dạng Markdown (## cho mục). Chỉ trả về NỘI DUNG chương đã nâng cấp (Markdown thuần), KHÔNG kèm lời dẫn."""


def improve_chapter_ai(course: dict, chapter_title: str, clos: list[dict],
                       content: str, qa: dict | None = None) -> str:
    """Nâng cấp nội dung chương dựa trên kết quả đánh giá. Trả về Markdown."""
    if not (content or "").strip():
        raise ValueError("Chương chưa có nội dung để nâng cấp.")
    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos) or "(không có)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CHƯƠNG: {chapter_title}\nCLO liên quan:\n{clo_lines}\n\n"
        f"NỘI DUNG HIỆN TẠI:\n\"\"\"\n{content[:30000]}\n\"\"\""
        + _format_qa(qa)
        + "\n\nHãy viết lại chương đã nâng cấp."
    )
    return llm_complete(CHAPTER_IMPROVE_PROMPT, user, max_tokens=8000).strip()
