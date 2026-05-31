"""Trích xuất văn bản từ PDF/DOCX + gọi Claude trả JSON có cấu trúc (SPEC 4.1).

- PDF số: PyMuPDF. DOCX: python-docx. (OCR scan: chỗ cắm Tesseract – TODO.)
- LLM bị ép trả JSON thuần, validate bằng Pydantic (ExtractionPayload).
- KHÔNG tự ghi vào CSDL: chỉ tạo bản nháp Extraction chờ con người xác nhận.
"""
from __future__ import annotations

import json

from app.config import settings
from app.schemas.extraction import ExtractionPayload

EXTRACTION_SYSTEM_PROMPT = """Bạn là trợ lý trích xuất dữ liệu học thuật từ đề án mở ngành/CTĐT \
tiếng Việt theo chuẩn OBE. Hãy đọc văn bản và trả về DUY NHẤT một đối tượng JSON hợp lệ \
(không kèm văn bản, không markdown, không giải thích) theo đúng schema sau:

{
  "program": {"name":"","code":"","level":"","year":0,"faculty":""},
  "plos": [{"code":"PLO1","description":"","category":"knowledge|skill|attitude","bloom_level":""}],
  "pis": [{"code":"PI1.1","plo_code":"PLO1","description":""}],
  "courses": [{"code":"","name":"","credits":0,"semester":0,"type":"core|elective","prerequisites":[]}],
  "course_plo_matrix": [{"course_code":"","plo_code":"","level":"I|R|M"}]
}

Quy tắc: giữ nguyên tiếng Việt; nếu không có dữ liệu để mục nào thì để mảng rỗng hoặc giá trị mặc định; \
KHÔNG bịa thông tin không có trong văn bản."""


def extract_text_from_file(path: str, mime: str | None = None) -> str:
    """Trích văn bản thô từ file PDF/DOCX. PDF scan (ít chữ) → OCR Tesseract (vie)."""
    lower = path.lower()
    if lower.endswith(".pdf"):
        import fitz  # PyMuPDF

        doc = fitz.open(path)
        text = "\n".join(page.get_text() for page in doc)
        # Nếu PDF gần như không có text (bản scan), thử OCR tiếng Việt.
        if len(text.strip()) < 50:
            ocr = _ocr_pdf(doc)
            if ocr:
                return ocr
        return text
    if lower.endswith(".docx"):
        from docx import Document as Docx

        d = Docx(path)
        return "\n".join(p.text for p in d.paragraphs)
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def _ocr_pdf(doc) -> str:
    """OCR từng trang PDF scan bằng Tesseract (vie). Trả "" nếu không cài được."""
    try:
        import pytesseract
        from PIL import Image
    except Exception:  # noqa: BLE001
        return ""
    import io as _io

    out = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(_io.BytesIO(pix.tobytes("png")))
        try:
            out.append(pytesseract.image_to_string(img, lang="vie"))
        except Exception:  # noqa: BLE001
            out.append(pytesseract.image_to_string(img))
    return "\n".join(out)


def _strip_to_json(text: str) -> str:
    """Lấy phần JSON nếu LLM lỡ kèm văn bản thừa."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        return text[start : end + 1]
    return text


def suggest_chapter_outline(clos: list[dict], course_name: str) -> list[dict]:
    """Gợi ý đề mục chương giáo trình dựa trên CLO (SPEC 4.4). Cần người duyệt.

    Trả về [{title, clo_codes:[...]}]. Validate dạng list[dict] trước khi dùng.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError("Chưa cấu hình ANTHROPIC_API_KEY.")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    clo_text = "\n".join(f"- {c['code']}: {c['description']}" for c in clos)
    prompt = (
        f"Học phần: {course_name}\nCác CLO:\n{clo_text}\n\n"
        "Đề xuất danh sách chương/mục giáo trình tiếng Việt phủ hết các CLO trên. "
        "Trả về DUY NHẤT JSON dạng: "
        '[{"title":"","clo_codes":["CLO1"]}] — không kèm văn bản thừa.'
    )
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1]
        if txt.startswith("json"):
            txt = txt[4:]
    start, end = txt.find("["), txt.rfind("]")
    data = json.loads(txt[start : end + 1] if start != -1 else txt)
    if not isinstance(data, list):
        raise ValueError("Kết quả gợi ý không phải danh sách")
    return [{"title": str(d.get("title", "")), "clo_codes": d.get("clo_codes", [])} for d in data]


def call_llm_extract(text: str) -> ExtractionPayload:
    """Gọi Claude trích xuất; validate bằng Pydantic. Không có API key -> lỗi rõ ràng."""
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "Chưa cấu hình ANTHROPIC_API_KEY. Đặt biến môi trường để dùng trích xuất AI."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    # Cắt bớt nếu quá dài (giữ phần đầu — thường chứa CTĐT/PLO).
    chunk = text[:120_000]
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": chunk}],
    )
    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(_strip_to_json(raw))
    return ExtractionPayload.model_validate(data)
