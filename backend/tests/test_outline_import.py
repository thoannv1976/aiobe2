"""Test import đề cương đã có: parse bằng AI + lưu draft + bảng sức khỏe (mock LLM)."""
import json

from app.schemas.outline_gen import GeneratedOutline
from app.services import outline_ai

COURSE = {"code": "IT101", "name": "Nhập môn CNTT"}
PLOS = [{"code": "PLO1", "category": "knowledge", "description": "Áp dụng nền tảng"}]
TEXT = """ĐỀ CƯƠNG HỌC PHẦN IT101 — Nhập môn CNTT
Mô tả: Học phần cơ sở.
CLO1: Hiểu khái niệm cơ bản (PLO1).
CLO2: Vận dụng công cụ.
Đánh giá: Cuối kỳ 100%.
"""

PARSED = {
    "detected_course_code": "IT101",
    "description": "Học phần cơ sở.",
    "teaching_methods": ["Thuyết giảng"],
    "references": [],
    "clos": [
        {"code": "CLO1", "description": "Hiểu khái niệm", "description_en": "Understand",
         "bloom_level": "understand", "plos": [{"plo_code": "PLO1", "level": "R"}]},
        # CLO2 ánh xạ PLO99 không tồn tại → phải bị loại + cảnh báo
        {"code": "CLO2", "description": "Vận dụng công cụ", "description_en": "Apply",
         "bloom_level": "apply", "plos": [{"plo_code": "PLO99", "level": "M"}]},
    ],
    "assessments": [{"name": "Cuối kỳ", "type": "exam", "weight_percent": 100,
                     "clo_codes": ["CLO1", "CLO2"], "rubric": []}],
    "lessons": [{"week": 1, "topic": "Giới thiệu", "clo_codes": ["CLO1"]}],
}


def test_parse_outline_from_text(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=12000):
        captured["user"] = user
        return json.dumps(PARSED, ensure_ascii=False)

    monkeypatch.setattr(outline_ai, "llm_complete", fake)
    gen, detected = outline_ai.parse_outline_from_text(COURSE, PLOS, [], TEXT)
    assert isinstance(gen, GeneratedOutline)
    assert detected == "IT101"
    assert len(gen.clos) == 2
    # Văn bản gốc được đưa vào prompt + chỉ liệt kê PLO của chương trình.
    assert "IT101" in captured["user"]
    assert "PLO1" in captured["user"]


def test_parse_empty_text_raises(monkeypatch):
    monkeypatch.setattr(outline_ai, "llm_complete", lambda *a, **k: "{}")
    try:
        outline_ai.parse_outline_from_text(COURSE, PLOS, [], "   ")
        assert False, "phải báo lỗi văn bản rỗng"
    except ValueError:
        pass
