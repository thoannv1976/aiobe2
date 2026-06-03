"""Test nâng cấp đề cương bằng AI (improve_outline_ai) — mock LLM, kiểm prompt + validate."""
import json

from app.schemas.outline_gen import GeneratedOutline
from app.services import outline_ai

COURSE = {"code": "IT101", "name": "Nhập môn CNTT", "credits": 3, "type": "core", "program_name": "CNTT"}
PLOS = [{"code": "PLO1", "category": "knowledge", "description": "Áp dụng kiến thức nền tảng"}]
PIS = []
COURSE_PLO = [{"plo_code": "PLO1", "level": "M"}]
CURRENT = {
    "description": "Học phần cơ sở",
    "teaching_methods": ["Thuyết giảng"],
    "references": ["Giáo trình A"],
    "clos": [
        {"code": "CLO4", "description": "Thể hiện thái độ trách nhiệm", "description_en": "",
         "bloom_level": "understand", "plos": [{"plo_code": "PLO1", "level": "M"}]},
    ],
    "assessments": [{"name": "Cuối kỳ", "type": "exam", "weight_percent": 100, "clo_codes": ["CLO4"]}],
    "lessons": [{"week": 1, "topic": "Giới thiệu", "clo_codes": ["CLO4"]}],
}
QA = {
    "score": 78,
    "summary": "Cấu trúc tốt nhưng sai mức Bloom ở CLO4.",
    "errors": [],
    "warnings": ["CLO4 là thái độ nhưng gán mức 'understand'."],
    "clo_reviews": [{"code": "CLO4", "measurable": False,
                     "issues": ["động từ thái độ gán Bloom nhận thức"],
                     "suggestion": "Dùng thang Krathwohl cho CLO thái độ."}],
}

GEN_JSON = {
    "description": "Học phần cơ sở (đã nâng cấp)",
    "teaching_methods": ["Thuyết giảng", "Dự án nhóm"],
    "references": ["Giáo trình A"],
    "clos": [
        {"code": "CLO4", "description": "Thể hiện (Respond) thái độ trách nhiệm",
         "description_en": "Demonstrate responsible attitude", "bloom_level": "understand",
         "plos": [{"plo_code": "PLO1", "level": "M"}]},
    ],
    "assessments": [
        {"name": "Đánh giá quá trình", "type": "rubric", "weight_percent": 40, "clo_codes": ["CLO4"],
         "rubric": [{"name": "Thái độ", "weight_percent": 100, "levels": ["Tốt", "Khá", "Đạt", "Chưa đạt"]}]},
        {"name": "Cuối kỳ", "type": "exam", "weight_percent": 60, "clo_codes": ["CLO4"],
         "rubric": [{"name": "Nội dung", "weight_percent": 100, "levels": ["Tốt", "Khá", "Đạt", "Chưa đạt"]}]},
    ],
    "lessons": [{"week": 1, "topic": "Giới thiệu", "clo_codes": ["CLO4"]}],
}


def test_improve_outline_ai_builds_prompt_and_validates(monkeypatch):
    captured = {}

    def fake_llm(system, user, max_tokens=12000):
        captured["system"] = system
        captured["user"] = user
        return json.dumps(GEN_JSON, ensure_ascii=False)

    monkeypatch.setattr(outline_ai, "llm_complete", fake_llm)
    result = outline_ai.improve_outline_ai(COURSE, PLOS, PIS, COURSE_PLO, CURRENT, QA)

    # Trả về GeneratedOutline hợp lệ với nội dung đã nâng cấp.
    assert isinstance(result, GeneratedOutline)
    assert "nâng cấp" in result.description.lower()
    # Tổng trọng số đánh giá = 100 (đã thêm cấu phần quá trình).
    assert sum(a.weight_percent for a in result.assessments) == 100

    # Prompt phải chứa dữ liệu đề cương hiện tại + kết quả kiểm tra chất lượng.
    u = captured["user"]
    assert "CLO4" in u
    assert "ĐỀ CƯƠNG HIỆN TẠI" in u
    assert "KIỂM TRA CHẤT LƯỢNG" in u
    assert "Krathwohl" in u  # gợi ý sửa từ clo_reviews được đưa vào prompt
    assert "78/100" in u     # điểm hiện tại


def test_improve_outline_ai_without_qa_still_works(monkeypatch):
    monkeypatch.setattr(outline_ai, "llm_complete",
                        lambda system, user, max_tokens=12000: json.dumps(GEN_JSON, ensure_ascii=False))
    result = outline_ai.improve_outline_ai(COURSE, PLOS, PIS, COURSE_PLO, CURRENT, {})
    assert isinstance(result, GeneratedOutline)
    assert len(result.clos) == 1
