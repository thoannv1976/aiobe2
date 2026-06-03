"""Test đánh giá + nâng cấp bằng AI cho ngân hàng câu hỏi và ma trận đề thi (mock LLM)."""
import json

from app.schemas.question_gen import ImprovedQuestions
from app.services import matrix_ai, question_ai, qa_review

COURSE = {"code": "IT101", "name": "Nhập môn CNTT"}
QUESTIONS = [
    {"id": 1, "clo_code": "CLO1", "bloom_level": "analyze", "difficulty": "easy",
     "type": "mcq_single", "content": "2+2=?", "options": ["A.3", "B.4"], "answer": "",
     "explanation": "", "has_rubric": False},
    {"id": 2, "clo_code": "CLO2", "bloom_level": "understand", "difficulty": "medium",
     "type": "essay", "content": "Trình bày X", "options": [], "answer": "gợi ý",
     "explanation": "vì X", "has_rubric": False},
]


def test_review_questions_ai(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=8000):
        captured["user"] = user
        return json.dumps({
            "score": 65, "summary": "Cân đối Bloom kém",
            "errors": ["Câu id=1 thiếu đáp án đúng"],
            "warnings": ["Câu id=2 thiếu rubric"],
            "question_reviews": [
                {"id": 1, "severity": "error", "issues": ["thiếu đáp án", "Bloom sai"], "suggestion": "Thêm đáp án"},
                {"id": 2, "severity": "warning", "issues": ["thiếu rubric"], "suggestion": "Thêm rubric"},
            ],
        }, ensure_ascii=False)

    monkeypatch.setattr(qa_review, "llm_complete", fake)
    res = qa_review.review_questions_ai(COURSE, QUESTIONS)
    assert res["score"] == 65
    assert len(res["question_reviews"]) == 2
    # Prompt chứa id + nội dung câu để AI tham chiếu.
    assert "id=1" in captured["user"]
    assert "KHÔNG rubric" in captured["user"]


def test_improve_questions_ai_injects_issues(monkeypatch):
    captured = {}
    qa = {"summary": "x", "question_reviews": [
        {"id": 1, "issues": ["thiếu đáp án"], "suggestion": "thêm B đúng"},
    ]}

    def fake(system, user, max_tokens=12000):
        captured["user"] = user
        return json.dumps({"questions": [
            {"id": 1, "content": "2+2=?", "options": ["A.3", "B.4", "C.5", "D.6"],
             "answer": "B", "explanation": "4 đúng", "bloom_level": "remember",
             "difficulty": "easy", "type": "mcq_single", "rubric": []},
        ]}, ensure_ascii=False)

    monkeypatch.setattr(question_ai, "llm_complete", fake)
    res = question_ai.improve_questions_ai(COURSE, [QUESTIONS[0]], qa)
    assert isinstance(res, ImprovedQuestions)
    assert res.questions[0].answer == "B"
    # Vấn đề từng câu được nhúng vào prompt.
    assert "thiếu đáp án" in captured["user"]
    assert "thêm B đúng" in captured["user"]


def test_review_matrix_ai(monkeypatch):
    captured = {}
    payload = {
        "course": COURSE, "name": "Đề cuối kỳ", "total_points": 10,
        "cells": [{"clo_code": "CLO1", "bloom_level": "remember", "difficulty": "easy",
                   "count": 5, "points_each": 1}],
        "bank_cells": [{"clo_code": "CLO1", "bloom_level": "remember", "difficulty": "easy", "available": 8}],
        "assessment": {"name": "Cuối kỳ", "clo_codes": ["CLO1", "CLO2"]},
    }

    def fake(system, user, max_tokens=4000):
        captured["user"] = user
        return json.dumps({"score": 70, "summary": "Thiếu CLO2",
                           "errors": [], "warnings": ["Chưa đo CLO2"],
                           "suggestions": ["Thêm câu CLO2"]}, ensure_ascii=False)

    monkeypatch.setattr(qa_review, "llm_complete", fake)
    res = qa_review.review_matrix_ai(payload)
    assert res["score"] == 70
    assert "CLO2" in captured["user"]            # cấu phần đánh giá đưa vào prompt
    assert "Đã duyệt" in captured["user"]        # dữ liệu ngân hàng đưa vào prompt


def test_optimize_matrix_with_qa_includes_findings(monkeypatch):
    captured = {}

    def fake(system, user, max_tokens=4000):
        captured["user"] = user
        return json.dumps({"name": "Tối ưu", "cells": [
            {"clo_code": "CLO1", "bloom_level": "remember", "difficulty": "easy", "count": 2, "points_each": 5}],
            "rationale": "ok"}, ensure_ascii=False)

    monkeypatch.setattr(matrix_ai, "llm_complete", fake)
    qa = {"errors": ["Tổng điểm sai"], "warnings": [], "suggestions": ["Thêm mức Phân tích"]}
    res = matrix_ai.optimize_exam_matrix_ai(
        course=COURSE,
        clos=[{"code": "CLO1", "description": "x"}],
        bank_cells=[{"clo_code": "CLO1", "bloom_level": "remember", "difficulty": "easy", "available": 5}],
        current_cells=[{"clo_code": "CLO1", "bloom_level": "remember", "difficulty": "easy",
                        "count": 1, "points_each": 1}],
        total_points=10, qa=qa,
    )
    assert res["name"] == "Tối ưu"
    assert "KHẮC PHỤC THEO ĐÁNH GIÁ AUN-QA" in captured["user"]
    assert "Tổng điểm sai" in captured["user"]
    assert "Thêm mức Phân tích" in captured["user"]
