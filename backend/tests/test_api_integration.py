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


def test_update_outline_general_without_course_id(client):
    """Lưu 'Thông tin chung' đề cương KHÔNG cần course_id (xác định qua URL)."""
    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PU", "code": "PU"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CU", "name": "Course U"}, headers=h).json()["id"]
    oid = client.post("/api/outlines", json={"course_id": cid}, headers=h).json()["id"]
    # Payload giống saveGeneral của frontend (KHÔNG có course_id).
    r = client.patch(f"/api/outlines/{oid}", headers=h, json={
        "description": "Mô tả đã sửa",
        "general_info_json": {"generated_by_ai": True, "improved_from": 18, "qa_score": 82},
        "teaching_methods_json": ["Thuyết giảng"],
        "references_json": ["Tài liệu A"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["description"] == "Mô tả đã sửa"


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


def test_improve_chapter_endpoint(client, monkeypatch):
    """AI nâng cấp nội dung chương giáo trình tại chỗ."""
    from app.services import textbook_ai

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PT", "code": "PT"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CT", "name": "Course T"}, headers=h).json()["id"]
    tid = client.post("/api/textbooks", json={"course_id": cid, "title": "GT"}, headers=h).json()["id"]
    chid = client.post(f"/api/textbooks/{tid}/chapters", json={
        "order": 1, "title": "Chương 1", "content_richtext": "## Mở đầu\nsơ sài", "clo_ids": [],
    }, headers=h).json()["id"]

    monkeypatch.setattr(textbook_ai, "llm_complete",
                        lambda system, user, max_tokens=8000: "## Mở đầu\nNội dung đã nâng cấp đầy đủ.")
    qa = {"summary": "sơ sài", "errors": ["thiếu ví dụ"], "warnings": [], "suggestions": []}
    r = client.post(f"/api/chapters/{chid}/improve", json={"qa": qa}, headers=h)
    assert r.status_code == 200, r.text
    assert "nâng cấp" in r.json()["content_richtext"]


def test_improve_lecture_endpoint(client, monkeypatch):
    """AI nâng cấp bài giảng tại chỗ (nội dung + slide)."""
    import json as _json

    from app.services import lecture_ai

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PL", "code": "PL"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CL", "name": "Course L"}, headers=h).json()["id"]
    lid = client.post(f"/api/courses/{cid}/lectures", json={
        "session_no": 1, "title": "Buổi 1", "content_richtext": "## Mục tiêu\ncũ",
        "slides_json": [], "clo_codes_json": [],
    }, headers=h).json()["id"]

    monkeypatch.setattr(lecture_ai, "llm_complete",
                        lambda system, user, max_tokens=8000: _json.dumps({
                            "content_markdown": "## Mục tiêu\nĐã nâng cấp",
                            "slides": [{"title": "S1", "bullets": ["a"]}]}, ensure_ascii=False))
    r = client.post(f"/api/lectures/{lid}/improve", json={"qa": {"warnings": ["thiếu ví dụ"]}}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["slides"] == 1
    got = client.get(f"/api/lectures/{lid}", headers=h).json()
    assert "nâng cấp" in got["content_richtext"]


def test_import_existing_outline_flow(client, monkeypatch):
    """Phase 1+2: parse đề cương đã có (upload) → import draft → bảng sức khỏe có điểm."""
    import json as _json

    from app.services import outline_ai

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PI2", "code": "PI2"}, headers=h).json()["id"]
    client.post(f"/api/programs/{pid}/plos",
                json={"code": "PLO1", "description": "Áp dụng"}, headers=h)
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "IT101", "name": "Nhập môn"}, headers=h).json()["id"]

    parsed = {
        "detected_course_code": "IT101", "description": "Học phần cơ sở",
        "teaching_methods": [], "references": [],
        "clos": [
            {"code": "CLO1", "description": "Hiểu", "description_en": "Understand",
             "bloom_level": "understand", "plos": [{"plo_code": "PLO1", "level": "R"}]},
            {"code": "CLO2", "description": "Vận dụng", "description_en": "Apply",
             "bloom_level": "apply", "plos": [{"plo_code": "PLO99", "level": "M"}]},  # PLO sai → loại
        ],
        "assessments": [{"name": "Cuối kỳ", "type": "exam", "weight_percent": 100,
                         "clo_codes": ["CLO1"], "rubric": []}],
        "lessons": [{"week": 1, "topic": "GT", "clo_codes": ["CLO1"]}],
    }
    monkeypatch.setattr(outline_ai, "llm_complete",
                        lambda system, user, max_tokens=12000: _json.dumps(parsed, ensure_ascii=False))

    # 1) Parse upload (chưa lưu) → cảnh báo PLO chưa khớp.
    r = client.post(f"/api/courses/{cid}/parse-outline", headers=h,
                    files={"file": ("dc.txt", b"De cuong IT101 ...", "text/plain")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detected_course_code"] == "IT101"
    assert "PLO99" in body["unmatched_plos"]
    assert len(body["outline"]["clos"]) == 2

    # 2) Import (lưu draft) dùng cấu trúc đã rà soát.
    r = client.post(f"/api/courses/{cid}/import-outline", headers=h,
                    json={"outline": body["outline"], "source_name": "dc.txt"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert r.json()["status"] == "draft"

    # 3) Tự chấm chất lượng → lưu snapshot.
    from app.services import qa_review
    monkeypatch.setattr(qa_review, "llm_complete",
                        lambda system, user, max_tokens=8000: _json.dumps({
                            "score": 64, "summary": "ổn", "errors": ["x"], "warnings": ["y", "z"],
                            "clo_reviews": []}, ensure_ascii=False))
    r = client.get(f"/api/outlines/{oid}/qa-review", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["score"] == 64

    # 4) Bảng sức khỏe đề cương toàn ngành có điểm đã lưu.
    r = client.get(f"/api/programs/{pid}/outline-health", headers=h)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["rows"] if x["course_code"] == "IT101")
    assert row["has_outline"] and row["qa_score"] == 64 and row["qa_errors"] == 1 and row["qa_warnings"] == 2


def test_bulk_import_outlines(client, monkeypatch):
    """Phase 3: import hàng loạt → khớp học phần theo mã phát hiện → lưu + chấm."""
    import json as _json

    from app.services import outline_ai, qa_review

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PB", "code": "PB"}, headers=h).json()["id"]
    client.post(f"/api/programs/{pid}/plos", json={"code": "PLO1", "description": "x"}, headers=h)
    client.post(f"/api/programs/{pid}/courses", json={"code": "CS100", "name": "A"}, headers=h)

    parsed = {"detected_course_code": "CS100", "description": "d", "teaching_methods": [],
              "references": [], "clos": [{"code": "CLO1", "description": "Hiểu", "description_en": "U",
              "bloom_level": "understand", "plos": [{"plo_code": "PLO1", "level": "R"}]}],
              "assessments": [], "lessons": []}
    monkeypatch.setattr(outline_ai, "llm_complete",
                        lambda system, user, max_tokens=12000: _json.dumps(parsed, ensure_ascii=False))
    monkeypatch.setattr(qa_review, "llm_complete",
                        lambda system, user, max_tokens=8000: _json.dumps({
                            "score": 80, "summary": "s", "errors": [], "warnings": [], "clo_reviews": []},
                            ensure_ascii=False))

    r = client.post(f"/api/programs/{pid}/import-outlines", headers=h,
                    files=[("files", ("a.txt", b"De cuong CS100", "text/plain"))])
    assert r.status_code == 200, r.text
    rows = r.json()["results"]
    assert rows[0]["matched"] and rows[0]["course_code"] == "CS100"
    assert rows[0]["score"] == 80 and rows[0]["outline_id"]


def test_bulk_import_one_bad_file_does_not_break_others(client, monkeypatch):
    """Một file lỗi (parse raise) KHÔNG được làm hỏng các file sau trong cùng request."""
    import json as _json

    from app.services import outline_ai, qa_review

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PB2", "code": "PB2"}, headers=h).json()["id"]
    client.post(f"/api/programs/{pid}/plos", json={"code": "PLO1", "description": "x"}, headers=h)
    client.post(f"/api/programs/{pid}/courses", json={"code": "EE200", "name": "B"}, headers=h)

    good = {"detected_course_code": "EE200", "description": "d", "teaching_methods": [],
            "references": [], "clos": [{"code": "CLO1", "description": "Hiểu", "description_en": "U",
            "bloom_level": "understand", "plos": [{"plo_code": "PLO1", "level": "R"}]}],
            "assessments": [], "lessons": []}

    calls = {"n": 0}

    def flaky(system, user, max_tokens=12000):
        # File đầu: parse lỗi (JSON hỏng) → raise; file sau: trả JSON hợp lệ.
        calls["n"] += 1
        if calls["n"] == 1:
            return "KHÔNG PHẢI JSON"
        return _json.dumps(good, ensure_ascii=False)

    monkeypatch.setattr(outline_ai, "llm_complete", flaky)
    monkeypatch.setattr(qa_review, "llm_complete",
                        lambda system, user, max_tokens=8000: _json.dumps({
                            "score": 75, "summary": "s", "errors": [], "warnings": [], "clo_reviews": []},
                            ensure_ascii=False))

    r = client.post(f"/api/programs/{pid}/import-outlines", headers=h, files=[
        ("files", ("bad.txt", b"loi parse EE200", "text/plain")),
        ("files", ("ok.txt", b"De cuong EE200", "text/plain")),
    ])
    assert r.status_code == 200, r.text
    rows = r.json()["results"]
    assert rows[0]["message"].startswith("Lỗi")          # file đầu lỗi
    assert rows[0]["outline_id"] is None
    # File thứ 2 vẫn lưu + chấm thành công (session không bị hỏng).
    assert rows[1]["matched"] and rows[1]["outline_id"] and rows[1]["score"] == 75
