"""Test tích hợp end-to-end: auth -> tạo CTĐT -> PLO -> coverage."""
import os
import tempfile

import pytest

# Dùng DB sqlite tạm cho test, đặt TRƯỚC khi import app.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(User(name="M", email="m@t.vn", password_hash=hash_password("pw"), role="program_manager"))
    db.commit()
    db.close()
    yield TestClient(app)


def _token(client):
    r = client.post("/api/auth/login", data={"username": "m@t.vn", "password": "pw"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_program_flow(client):
    h = {"Authorization": f"Bearer {_token(client)}"}
    r = client.post("/api/programs", json={"name": "Test", "code": "T1"}, headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.post(f"/api/programs/{pid}/plos", json={"code": "PLO1", "description": "x"}, headers=h)
    assert r.status_code == 201
    plo_id = r.json()["id"]

    r = client.post(f"/api/programs/{pid}/courses", json={"code": "C1", "name": "Course 1"}, headers=h)
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.put("/api/course-plo", json={"course_id": cid, "plo_id": plo_id, "level": "M"}, headers=h)
    assert r.status_code == 200

    r = client.get(f"/api/programs/{pid}/coverage", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_requires_auth(client):
    assert client.get("/api/programs").status_code == 401


def test_improve_outline_endpoint(client, monkeypatch):
    """Nâng cấp đề cương bằng AI tạo phiên bản mới (draft) từ kết quả kiểm tra chất lượng."""
    import json as _json

    from app.services import outline_ai

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "P", "code": "PV"}, headers=h).json()["id"]
    client.post(f"/api/programs/{pid}/plos",
                json={"code": "PLO1", "description": "Áp dụng"}, headers=h)
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CV", "name": "Course"}, headers=h).json()["id"]
    oid = client.post("/api/outlines", json={"course_id": cid}, headers=h).json()["id"]
    client.post(f"/api/outlines/{oid}/clos",
                json={"code": "CLO1", "description": "Hiểu khái niệm", "bloom_level": "understand"},
                headers=h)

    gen = {
        "description": "Đã nâng cấp", "teaching_methods": ["Dự án"], "references": [],
        "clos": [{"code": "CLO1", "description": "Phân tích (Analyze) vấn đề",
                  "description_en": "Analyze", "bloom_level": "analyze",
                  "plos": [{"plo_code": "PLO1", "level": "M"}]}],
        "assessments": [{"name": "Cuối kỳ", "type": "exam", "weight_percent": 100,
                         "clo_codes": ["CLO1"], "rubric": []}],
        "lessons": [{"week": 1, "topic": "T", "clo_codes": ["CLO1"]}],
    }
    monkeypatch.setattr(outline_ai, "llm_complete",
                        lambda system, user, max_tokens=12000: _json.dumps(gen, ensure_ascii=False))

    qa = {"score": 70, "summary": "x", "errors": ["CLO1 chưa đo được mức cao"],
          "warnings": [], "clo_reviews": []}
    r = client.post(f"/api/outlines/{oid}/improve", json={"qa": qa}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] != oid              # tạo phiên bản MỚI, giữ bản gốc
    assert body["version"] == 2
    assert body["status"] == "draft"

    # Phiên bản mới có CLO đã nâng cấp + ánh xạ PLO.
    clos = client.get(f"/api/outlines/{body['id']}/clos", headers=h).json()
    assert any(c["bloom_level"] == "analyze" for c in clos)


def test_improve_questions_endpoint(client, monkeypatch):
    """Đánh giá + nâng cấp ngân hàng câu hỏi bằng AI: viết lại câu lỗi, đặt lại trạng thái draft."""
    import json as _json

    from app.services import question_ai

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PQ", "code": "PQ"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CQ", "name": "Course Q"}, headers=h).json()["id"]
    oid = client.post("/api/outlines", json={"course_id": cid}, headers=h).json()["id"]
    clo_id = client.post(f"/api/outlines/{oid}/clos",
                         json={"code": "CLO1", "description": "x", "bloom_level": "understand"},
                         headers=h).json()["id"]
    # Câu trắc nghiệm thiếu đáp án (lỗi) — chưa duyệt.
    qid = client.post(f"/api/courses/{cid}/questions", json={
        "clo_id": clo_id, "bloom_level": "analyze", "difficulty": "easy",
        "type": "mcq_single", "content": "2+2=?", "options_json": ["A.3", "B.4"], "answer": "",
    }, headers=h).json()["id"]

    monkeypatch.setattr(question_ai, "llm_complete",
                        lambda system, user, max_tokens=12000: _json.dumps({"questions": [
                            {"id": qid, "content": "2+2=?", "options": ["A.3", "B.4", "C.5", "D.6"],
                             "answer": "B", "explanation": "4 đúng", "bloom_level": "remember",
                             "difficulty": "easy", "type": "mcq_single", "rubric": []}]}, ensure_ascii=False))

    qa = {"summary": "x", "errors": ["Câu thiếu đáp án"], "warnings": [],
          "question_reviews": [{"id": qid, "severity": "error", "issues": ["thiếu đáp án"],
                                "suggestion": "thêm đáp án"}]}
    r = client.post(f"/api/courses/{cid}/questions/improve", json={"qa": qa}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["improved"] == 1

    got = client.get(f"/api/courses/{cid}/questions", headers=h).json()
    q = next(x for x in got if x["id"] == qid)
    assert q["answer"] == "B"               # đã bổ sung đáp án
    assert q["bloom_level"] == "remember"   # đã sửa Bloom
    assert q["review_status"] == "draft"    # đặt lại để thẩm định


def test_matrix_qa_review_endpoint(client, monkeypatch):
    """AI đánh giá ma trận đề thi trả điểm + cảnh báo."""
    import json as _json

    from app.services import qa_review

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PM", "code": "PM"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CM", "name": "Course M"}, headers=h).json()["id"]
    oid = client.post("/api/outlines", json={"course_id": cid}, headers=h).json()["id"]
    clo_id = client.post(f"/api/outlines/{oid}/clos",
                         json={"code": "CLO1", "description": "x", "bloom_level": "remember"},
                         headers=h).json()["id"]
    mid = client.post(f"/api/courses/{cid}/matrices", json={
        "name": "MT", "total_points": 10,
        "cells": [{"clo_id": clo_id, "bloom_level": "remember", "difficulty": "easy",
                   "count": 3, "points_each": 1}],
    }, headers=h).json()["id"]

    monkeypatch.setattr(qa_review, "llm_complete",
                        lambda system, user, max_tokens=4000: _json.dumps({
                            "score": 72, "summary": "ổn", "errors": [], "warnings": ["Cân Bloom"],
                            "suggestions": ["Thêm câu khó"]}, ensure_ascii=False))
    r = client.get(f"/api/matrices/{mid}/qa-review", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 72
