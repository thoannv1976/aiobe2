"""Test đánh giá + nâng cấp bằng AI cho giáo trình (chương) và bài giảng (mock LLM)."""
import json

from app.services import lecture_ai, textbook_ai

COURSE = {"code": "IT101", "name": "Nhập môn CNTT"}
CLOS = [{"code": "CLO1", "description": "Áp dụng X"}]
CONTENT = "## Mở đầu\nNội dung chương sơ sài."


def test_review_chapter_ai(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=3000):
        captured["user"] = user
        return json.dumps({"score": 60, "summary": "Sơ sài", "errors": ["Thiếu ví dụ"],
                           "warnings": ["Chưa có câu hỏi ôn tập"], "suggestions": ["Thêm ví dụ"]},
                          ensure_ascii=False)

    monkeypatch.setattr(textbook_ai, "llm_complete", fake)
    res = textbook_ai.review_chapter_ai(COURSE, "Chương 1", CLOS, CONTENT)
    assert res["score"] == 60
    assert "CLO1" in captured["user"]
    assert "NỘI DUNG CHƯƠNG" in captured["user"]


def test_improve_chapter_ai_includes_qa(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=8000):
        captured["user"] = user
        return "## Mở đầu\nNội dung đã nâng cấp, có ví dụ và câu hỏi ôn tập."

    monkeypatch.setattr(textbook_ai, "llm_complete", fake)
    qa = {"summary": "Sơ sài", "errors": ["Thiếu ví dụ"], "suggestions": ["Thêm ví dụ minh họa"]}
    out = textbook_ai.improve_chapter_ai(COURSE, "Chương 1", CLOS, CONTENT, qa)
    assert "nâng cấp" in out
    assert "Thiếu ví dụ" in captured["user"]
    assert "Thêm ví dụ minh họa" in captured["user"]


def test_review_lecture_ai(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=3000):
        captured["user"] = user
        return json.dumps({"score": 72, "summary": "ổn", "errors": [],
                           "warnings": ["Thiếu hoạt động thảo luận"], "suggestions": ["Thêm bài tập"]},
                          ensure_ascii=False)

    monkeypatch.setattr(lecture_ai, "llm_complete", fake)
    res = lecture_ai.review_lecture_ai(COURSE, "Buổi 1", CLOS, "## Mục tiêu\n...", 5)
    assert res["score"] == 72
    assert "Số slide hiện có: 5" in captured["user"]


def test_improve_lecture_ai_includes_qa(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=8000):
        captured["user"] = user
        return json.dumps({"content_markdown": "## Mục tiêu\nĐã nâng cấp",
                           "slides": [{"title": "S1", "bullets": ["a", "b"]}]}, ensure_ascii=False)

    monkeypatch.setattr(lecture_ai, "llm_complete", fake)
    qa = {"warnings": ["Thiếu hoạt động thảo luận"], "suggestions": ["Thêm bài tập vận dụng"]}
    out = lecture_ai.improve_lecture_ai(COURSE, "Buổi 1", CLOS, "## Mục tiêu\ncũ", [], qa)
    assert out["content_markdown"] == "## Mục tiêu\nĐã nâng cấp"
    assert len(out["slides"]) == 1
    assert "Thiếu hoạt động thảo luận" in captured["user"]
    assert "Thêm bài tập vận dụng" in captured["user"]
