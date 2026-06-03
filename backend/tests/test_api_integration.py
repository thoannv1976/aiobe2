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
