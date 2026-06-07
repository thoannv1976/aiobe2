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


def test_llm_usage_endpoint(client):
    """GET /llm-usage: chỉ Admin; trả tổng token/chi phí + phân rã theo chương trình."""
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    if not db.query(User).filter(User.email == "admin2@t.vn").first():
        db.add(User(name="A2", email="admin2@t.vn", password_hash=hash_password("pw"), role="admin"))
        db.commit()
    db.close()

    # Quản lý CTĐT (không phải admin) bị từ chối.
    mh = {"Authorization": f"Bearer {_token(client)}"}
    assert client.get("/api/llm-usage", headers=mh).status_code == 403

    tok = client.post("/api/auth/login", data={"username": "admin2@t.vn", "password": "pw"}).json()["access_token"]
    r = client.get("/api/llm-usage?days=30", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"days", "calls", "total_tokens", "est_cost_usd", "by_program"} <= set(body)


def test_delete_program(client):
    """Xóa CTĐT (soft-delete) → biến mất khỏi danh sách."""
    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "Tạm", "code": "DELME"}, headers=h).json()["id"]
    assert any(p["id"] == pid for p in client.get("/api/programs", headers=h).json())
    r = client.delete(f"/api/programs/{pid}", headers=h)
    assert r.status_code == 204, r.text
    assert all(p["id"] != pid for p in client.get("/api/programs", headers=h).json())


def test_llm_retry_and_usage(client, monkeypatch):
    """LLM: thử lại khi lỗi tạm thời + ghi nhận token/chi phí (LlmUsage)."""
    from app.database import SessionLocal
    from app.models import LlmUsage
    from app.services import llm as llm_mod

    monkeypatch.setattr(llm_mod.settings, "llm_retry_base_delay", 0.0)
    monkeypatch.setattr(llm_mod.settings, "llm_max_retries", 3)
    monkeypatch.setattr(llm_mod, "_resolve", lambda: ("anthropic", "k", "claude-opus-4-8"))

    class RateLimitError(Exception):
        pass

    calls = {"n": 0}

    def flaky(provider, api_key, model, system, user, max_tokens):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("429 rate limit, please retry")
        return "KETQUA", {"prompt": 100, "completion": 20, "total": 120}

    monkeypatch.setattr(llm_mod, "_raw_complete", flaky)
    db = SessionLocal()
    before = db.query(LlmUsage).count()
    db.close()

    out = llm_mod.llm_complete("sys", "usr")
    assert out == "KETQUA"
    assert calls["n"] == 3  # 2 lần lỗi + 1 lần thành công

    db = SessionLocal()
    assert db.query(LlmUsage).count() == before + 1
    last = db.query(LlmUsage).order_by(LlmUsage.id.desc()).first()
    assert last.total_tokens == 120 and last.est_cost_usd > 0
    db.close()


def test_llm_quota_blocks(client, monkeypatch):
    """Vượt hạn mức token/ngày của chương trình → chặn (LLMQuotaExceeded)."""
    from app.core.llm_context import llm_scope
    from app.database import SessionLocal
    from app.models import LlmUsage
    from app.services import llm as llm_mod

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PQuota", "code": "PQ9"}, headers=h).json()["id"]
    monkeypatch.setattr(llm_mod.settings, "llm_daily_token_quota_per_program", 50)
    monkeypatch.setattr(llm_mod, "_resolve", lambda: ("anthropic", "k", "claude-opus-4-8"))
    monkeypatch.setattr(llm_mod, "_raw_complete",
                        lambda *a, **k: ("x", {"prompt": 1, "completion": 1, "total": 2}))

    db = SessionLocal()
    db.add(LlmUsage(provider="anthropic", model="m", total_tokens=60, program_id=pid))
    db.commit()
    db.close()

    import pytest
    with llm_scope(program_id=pid):
        with pytest.raises(llm_mod.LLMQuotaExceeded):
            llm_mod.llm_complete("s", "u")


def test_generate_textbook_job_inline(client, monkeypatch):
    """Job sinh giáo trình chạy nền (inline): đặt việc → poll job → done + giáo trình tạo ra."""
    import json as _json

    from app.config import settings as app_settings
    from app.services import textbook_ai

    monkeypatch.setattr(app_settings, "jobs_inline", True)  # chạy đồng bộ để test xác định

    def fake_tb_llm(system, user, max_tokens=4000):
        if "CẤU TRÚC CHƯƠNG" in system:
            return _json.dumps({"chapters": [
                {"order": 1, "title": "Chương 1", "clo_codes": ["CLO1"], "summary": "x"},
                {"order": 2, "title": "Chương 2", "clo_codes": ["CLO1"], "summary": "y"},
            ]}, ensure_ascii=False)
        return "## Nội dung\nChi tiết chương."

    monkeypatch.setattr(textbook_ai, "llm_complete", fake_tb_llm)

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PTB", "code": "PTB"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CTB", "name": "Course TB"}, headers=h).json()["id"]
    oid = client.post("/api/outlines", json={"course_id": cid}, headers=h).json()["id"]
    client.post(f"/api/outlines/{oid}/clos",
                json={"code": "CLO1", "description": "x", "bloom_level": "understand"}, headers=h)

    r = client.post(f"/api/courses/{cid}/textbooks/generate-async",
                    json={"with_content": True}, headers=h)
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]

    j = client.get(f"/api/jobs/{jid}", headers=h).json()
    assert j["status"] == "done", j
    assert j["progress"] == 100 and j["result"]["chapters"] == 2
    tbs = client.get(f"/api/courses/{cid}/textbooks", headers=h).json()
    assert len(tbs) == 1


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


def test_questions_pagination(client):
    """Phân trang ngân hàng câu hỏi: limit/offset + tổng số ở header X-Total-Count."""
    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PP", "code": "PP"}, headers=h).json()["id"]
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CP", "name": "Course P"}, headers=h).json()["id"]
    for i in range(5):
        client.post(f"/api/courses/{cid}/questions", json={
            "bloom_level": "remember", "difficulty": "easy", "type": "mcq_single",
            "content": f"Câu {i}", "answer": "A",
        }, headers=h)

    r = client.get(f"/api/courses/{cid}/questions?limit=2&offset=0", headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2
    assert r.headers["X-Total-Count"] == "5"          # tổng số đúng dù trang chỉ 2

    r2 = client.get(f"/api/courses/{cid}/questions?limit=2&offset=4", headers=h)
    assert len(r2.json()) == 1                          # trang cuối còn 1
    # limit vượt trần bị từ chối (bảo vệ khỏi truy vấn không giới hạn)
    assert client.get(f"/api/courses/{cid}/questions?limit=99999", headers=h).status_code == 422


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


def test_bulk_import_two_step(client, monkeypatch):
    """Phase 3 (2 bước): parse → gợi ý học phần → người dùng XÁC NHẬN course_id → lưu + chấm."""
    import json as _json

    from app.services import outline_ai, qa_review

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PB", "code": "PB"}, headers=h).json()["id"]
    client.post(f"/api/programs/{pid}/plos", json={"code": "PLO1", "description": "x"}, headers=h)
    cid = client.post(f"/api/programs/{pid}/courses",
                      json={"code": "CS100", "name": "A"}, headers=h).json()["id"]

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

    # Bước 1: parse (chưa lưu) → gợi ý đúng học phần.
    r = client.post(f"/api/programs/{pid}/parse-outlines", headers=h,
                    files=[("files", ("a.txt", b"De cuong CS100", "text/plain"))])
    assert r.status_code == 200, r.text
    body = r.json()
    assert any(c["id"] == cid for c in body["courses"])
    row = body["rows"][0]
    assert row["detected_course_code"] == "CS100"
    assert row["suggested_course_id"] == cid and row["clos_count"] == 1
    assert row["outline"] and row["error"] is None

    # Bước 2: người dùng xác nhận course_id tường minh → lưu + chấm.
    r = client.post(f"/api/programs/{pid}/import-outlines-confirm", headers=h, json={
        "items": [{"course_id": cid, "outline": row["outline"], "source_name": "a.txt"}],
        "run_qa": True,
    })
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["course_code"] == "CS100" and res["outline_id"] and res["score"] == 80


def test_bulk_import_confirm_rejects_wrong_program_course(client, monkeypatch):
    """Xác nhận import từ chối học phần KHÔNG thuộc chương trình (đảm bảo gắn đúng)."""
    import json as _json

    h = {"Authorization": f"Bearer {_token(client)}"}
    pid = client.post("/api/programs", json={"name": "PX", "code": "PX"}, headers=h).json()["id"]
    other_pid = client.post("/api/programs", json={"name": "PY", "code": "PY"}, headers=h).json()["id"]
    other_cid = client.post(f"/api/programs/{other_pid}/courses",
                            json={"code": "ZZ9", "name": "Z"}, headers=h).json()["id"]

    outline = {"description": "d", "teaching_methods": [], "references": [],
               "clos": [{"code": "CLO1", "description": "x", "description_en": "", "bloom_level": "understand", "plos": []}],
               "assessments": [], "lessons": []}
    # Gán course của chương trình khác → phải bị từ chối.
    r = client.post(f"/api/programs/{pid}/import-outlines-confirm", headers=h, json={
        "items": [{"course_id": other_cid, "outline": outline}], "run_qa": False,
    })
    assert r.status_code == 200, r.text
    res = r.json()["results"][0]
    assert res["outline_id"] is None and "không hợp lệ" in res["message"].lower()


def test_cross_tenant_isolation(client):
    """Pha C1: trường A KHÔNG thấy/đụng được dữ liệu trường B (cô lập theo tenant)."""
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import Tenant, User

    db = SessionLocal()
    ta = Tenant(code="truong-a", name="Trường A")
    tb = Tenant(code="truong-b", name="Trường B")
    db.add_all([ta, tb])
    db.commit()
    taid, tbid = ta.id, tb.id
    db.add(User(name="A", email="mgrA@t.vn", password_hash=hash_password("pw"),
                role="program_manager", tenant_id=taid))
    db.add(User(name="B", email="mgrB@t.vn", password_hash=hash_password("pw"),
                role="program_manager", tenant_id=tbid))
    db.commit()
    db.close()

    def tok(email):
        r = client.post("/api/auth/login", data={"username": email, "password": "pw"})
        assert r.status_code == 200, r.text
        # JWT mang tenant_id
        return r.json()["access_token"]

    ha = {"Authorization": f"Bearer {tok('mgrA@t.vn')}"}
    hb = {"Authorization": f"Bearer {tok('mgrB@t.vn')}"}

    pa = client.post("/api/programs", json={"name": "PA", "code": "PA"}, headers=ha).json()["id"]
    pb = client.post("/api/programs", json={"name": "PB", "code": "PB"}, headers=hb).json()["id"]

    # A chỉ thấy CTĐT của A; B chỉ thấy của B.
    a_ids = {p["id"] for p in client.get("/api/programs", headers=ha).json()}
    b_ids = {p["id"] for p in client.get("/api/programs", headers=hb).json()}
    assert pa in a_ids and pb not in a_ids
    assert pb in b_ids and pa not in b_ids

    # Truy cập chéo theo id → 404 (không lộ tồn tại).
    assert client.get(f"/api/programs/{pb}", headers=ha).status_code == 404
    assert client.get(f"/api/programs/{pa}", headers=hb).status_code == 404

    # Dữ liệu con (PLO) cũng cô lập: A tạo PLO; B dù dò đúng program id vẫn KHÔNG thấy (không rò rỉ).
    client.post(f"/api/programs/{pa}/plos", json={"code": "PLO1", "description": "x"}, headers=ha)
    assert len(client.get(f"/api/programs/{pa}/plos", headers=ha).json()) == 1
    assert client.get(f"/api/programs/{pa}/plos", headers=hb).json() == []


def test_c2_create_user_inherits_tenant_and_email_per_tenant(client):
    """C2: user mới kế thừa tenant của admin; cùng email dùng được ở 2 tenant khác nhau."""
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import Tenant, User

    db = SessionLocal()
    tA = Tenant(code="c2a", name="C2 A"); tB = Tenant(code="c2b", name="C2 B")
    db.add_all([tA, tB]); db.commit()
    aid, bid = tA.id, tB.id
    db.add(User(name="AdmA", email="adm@c2a.vn", password_hash=hash_password("pw"), role="admin", tenant_id=aid))
    db.add(User(name="AdmB", email="adm@c2b.vn", password_hash=hash_password("pw"), role="admin", tenant_id=bid))
    db.commit(); db.close()

    def tok(e):
        return client.post("/api/auth/login", data={"username": e, "password": "pw"}).json()["access_token"]

    # Admin A tạo giảng viên email "lec@dup.vn" → kế thừa tenant A.
    rA = client.post("/api/auth/users", headers={"Authorization": f"Bearer {tok('adm@c2a.vn')}"},
                     json={"name": "L", "email": "lec@dup.vn", "password": "pw", "role": "lecturer"})
    assert rA.status_code == 201, rA.text
    # Admin B tạo user CÙNG email "lec@dup.vn" → vẫn được (unique theo tenant).
    rB = client.post("/api/auth/users", headers={"Authorization": f"Bearer {tok('adm@c2b.vn')}"},
                     json={"name": "L", "email": "lec@dup.vn", "password": "pw", "role": "lecturer"})
    assert rB.status_code == 201, rB.text

    db = SessionLocal()
    rows = db.query(User).filter(User.email == "lec@dup.vn").execution_options(skip_tenant=True).all()
    tenants = sorted(u.tenant_id for u in rows)
    db.close()
    assert tenants == sorted([aid, bid])  # mỗi tenant một bản ghi, gắn đúng tenant


def test_c2_write_fallback_default_tenant(client):
    """C2: ghi ngoài ngữ cảnh request (info không có tenant) → fallback tenant mặc định (tránh NULL)."""
    from app.core import tenant as tmod
    from app.database import SessionLocal
    from app.models import Program

    tmod.set_default_tenant_id(987654)  # tenant_id là Integer thường (không FK) → giá trị giả OK
    try:
        db = SessionLocal()
        p = Program(name="Fallback", code="FB", is_deleted=False)
        db.add(p)
        db.commit()
        pid = p.id
        db.close()
        db = SessionLocal()
        tid = db.query(Program.tenant_id).filter(Program.id == pid)\
            .execution_options(skip_tenant=True).scalar()
        db.close()
        assert tid == 987654
    finally:
        tmod.set_default_tenant_id(None)  # tránh ảnh hưởng test khác


def test_c3_provisioning_branding_and_subscription(client):
    """C3: Super-Admin cấp phát trường + admin trường scoped; branding; suspend/enable theo hạn dùng."""
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    if not db.query(User).filter(User.email == "super@c3.vn").first():
        db.add(User(name="S", email="super@c3.vn", password_hash=hash_password("pw"), role="super_admin"))
        db.commit()
    db.close()

    def login(email, pw, headers=None):
        r = client.post("/api/auth/login", data={"username": email, "password": pw}, headers=headers or {})
        return r

    sh = {"Authorization": f"Bearer {login('super@c3.vn', 'pw').json()['access_token']}"}

    # Không phải Super-Admin → 403 khi quản trị tenant.
    assert client.get("/api/tenants", headers={"Authorization": f"Bearer {_token(client)}"}).status_code == 403

    # Super tạo trường + admin đầu tiên.
    r = client.post("/api/tenants", headers=sh, json={
        "code": "truongx", "name": "Trường X", "admin_email": "admin@x.vn", "admin_password": "pw"})
    assert r.status_code == 201, r.text
    txid = r.json()["id"]

    # Admin trường đăng nhập qua subdomain (X-Tenant) → dữ liệu scoped.
    ah = {"Authorization": f"Bearer {login('admin@x.vn', 'pw', {'X-Tenant': 'truongx'}).json()['access_token']}"}
    pa = client.post("/api/programs", json={"name": "PX", "code": "PX"}, headers=ah).json()["id"]
    assert pa in {p["id"] for p in client.get("/api/programs", headers=ah).json()}

    # Branding theo subdomain.
    b = client.get("/api/tenant/branding", headers={"X-Tenant": "truongx"}).json()
    assert b["tenant"] == "truongx" and b["name"] == "Trường X"

    # Tạm ngừng → admin trường bị chặn (kể cả token còn hạn) + không đăng nhập lại được.
    assert client.post(f"/api/tenants/{txid}/suspend", headers=sh).status_code == 200
    assert client.get("/api/programs", headers=ah).status_code == 403
    assert login("admin@x.vn", "pw", {"X-Tenant": "truongx"}).status_code == 403

    # Gia hạn (renew sau thanh toán) → dùng lại được.
    assert client.post(f"/api/tenants/{txid}/enable", headers=sh, json={"valid_days": 365}).status_code == 200
    ah2 = {"Authorization": f"Bearer {login('admin@x.vn', 'pw', {'X-Tenant': 'truongx'}).json()['access_token']}"}
    assert client.get("/api/programs", headers=ah2).status_code == 200


def test_c3_tenant_scoped_login_same_email(client):
    """C3: cùng email ở 2 trường → đăng nhập theo subdomain chọn đúng trường."""
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    if not db.query(User).filter(User.email == "super@c3.vn").first():
        db.add(User(name="S", email="super@c3.vn", password_hash=hash_password("pw"), role="super_admin"))
        db.commit()
    db.close()
    sh = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username':'super@c3.vn','password':'pw'}).json()['access_token']}"}
    client.post("/api/tenants", headers=sh, json={"code": "tr1", "name": "T1", "admin_email": "dup@same.vn", "admin_password": "pw"})
    client.post("/api/tenants", headers=sh, json={"code": "tr2", "name": "T2", "admin_email": "dup@same.vn", "admin_password": "pw"})
    # Đăng nhập cùng email nhưng khác subdomain → đều thành công (chọn đúng user theo tenant).
    assert client.post("/api/auth/login", data={"username": "dup@same.vn", "password": "pw"}, headers={"X-Tenant": "tr1"}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "dup@same.vn", "password": "pw"}, headers={"X-Tenant": "tr2"}).status_code == 200


def test_c4_per_tenant_key_and_encryption(client, monkeypatch):
    """C4: mỗi trường dùng ĐÚNG API key của mình; key được mã hóa khi lưu."""
    import app.config as cfg
    from app.core.crypto import decrypt_secret, encrypt_secret
    from app.core.llm_context import set_request_tenant
    from app.database import SessionLocal
    from app.models import ApiKey, Tenant
    from app.services import llm as llm_mod

    # Mã hóa khứ hồi (khi có encryption_key).
    monkeypatch.setattr(cfg.settings, "encryption_key", "test-secret-123")
    enc = encrypt_secret("sk-ABC")
    assert enc.startswith("enc:v1:") and decrypt_secret(enc) == "sk-ABC"

    db = SessionLocal()
    ta = Tenant(code="k4a", name="K4A"); tb = Tenant(code="k4b", name="K4B")
    db.add_all([ta, tb]); db.commit()
    aid, bid = ta.id, tb.id
    db.add(ApiKey(provider="anthropic", name="A", api_key=encrypt_secret("KEY_A"),
                  model="claude-opus-4-8", is_active=True, tenant_id=aid))
    db.add(ApiKey(provider="openai", name="B", api_key=encrypt_secret("KEY_B"),
                  model="gpt-4o", is_active=True, tenant_id=bid))
    db.commit(); db.close()

    set_request_tenant(aid)
    try:
        prov, key, _m = llm_mod._resolve()
        assert prov == "anthropic" and key == "KEY_A"      # đúng key trường A + đã giải mã
        set_request_tenant(bid)
        prov, key, _m = llm_mod._resolve()
        assert prov == "openai" and key == "KEY_B"          # đúng key trường B
    finally:
        set_request_tenant(None)


def test_c4_per_tenant_quota(client, monkeypatch):
    """C4: hạn mức token/ngày theo TRƯỜNG (tenants.llm_daily_token_quota)."""
    import pytest

    from app.core.llm_context import llm_scope
    from app.database import SessionLocal
    from app.models import LlmUsage, Tenant
    from app.services import llm as llm_mod

    db = SessionLocal()
    t = Tenant(code="q4", name="Q4", llm_daily_token_quota=10)
    db.add(t); db.commit(); tid = t.id
    db.add(LlmUsage(provider="anthropic", model="m", total_tokens=20, tenant_id=tid))
    db.commit(); db.close()

    monkeypatch.setattr(llm_mod, "_resolve", lambda: ("anthropic", "k", "claude-opus-4-8"))
    monkeypatch.setattr(llm_mod, "_raw_complete",
                        lambda *a, **k: ("x", {"prompt": 1, "completion": 1, "total": 2}))
    with llm_scope(tenant_id=tid):
        with pytest.raises(llm_mod.LLMQuotaExceeded):
            llm_mod.llm_complete("s", "u")


def test_c5_export_and_delete_tenant(client):
    """C5: Super-Admin export dữ liệu trường (zip JSON) + xóa cứng trường (cần confirm)."""
    import io as _io
    import json as _json
    import zipfile as _zip

    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    if not db.query(User).filter(User.email == "super5@c5.vn").first():
        db.add(User(name="S5", email="super5@c5.vn", password_hash=hash_password("pw"), role="super_admin"))
        db.commit()
    db.close()
    sh = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username':'super5@c5.vn','password':'pw'}).json()['access_token']}"}

    tid = client.post("/api/tenants", headers=sh, json={
        "code": "delme1", "name": "Del Me", "admin_email": "adm@delme1.vn", "admin_password": "pw"}).json()["id"]
    ah = {"Authorization": f"Bearer {client.post('/api/auth/login', data={'username':'adm@delme1.vn','password':'pw'}, headers={'X-Tenant':'delme1'}).json()['access_token']}"}
    client.post("/api/programs", json={"name": "PXDEL", "code": "PXDEL"}, headers=ah)

    # Export → zip có programs.json chứa CTĐT của trường.
    r = client.get(f"/api/tenants/{tid}/export", headers=sh)
    assert r.status_code == 200, r.text
    zf = _zip.ZipFile(_io.BytesIO(r.content))
    assert "programs.json" in zf.namelist() and "manifest.json" in zf.namelist()
    progs = _json.loads(zf.read("programs.json"))
    assert any(p["code"] == "PXDEL" for p in progs)

    # Xóa cần ?confirm=<mã trường>.
    assert client.delete(f"/api/tenants/{tid}", headers=sh).status_code == 400
    assert client.delete(f"/api/tenants/{tid}?confirm=delme1", headers=sh).status_code == 204
    # Trường biến mất + admin của trường không đăng nhập được nữa.
    assert client.get(f"/api/tenants/{tid}", headers=sh).status_code == 404
    assert client.post("/api/auth/login", data={"username": "adm@delme1.vn", "password": "pw"},
                       headers={"X-Tenant": "delme1"}).status_code == 401
