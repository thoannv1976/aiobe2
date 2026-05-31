"""Test trích xuất: đọc DOCX có bảng + vá JSON cắt cụt (SPEC 4.1)."""
import json

from app.services.extraction import _repair_truncated_json, _strip_to_json


def test_repair_truncated_object():
    # JSON bị cắt giữa chuỗi & thiếu ngoặc đóng.
    broken = '{"program":{"name":"X"},"plos":[{"code":"PLO1","description":"Vận dụng'
    fixed = _repair_truncated_json(broken)
    data = json.loads(fixed)
    assert data["program"]["name"] == "X"
    assert data["plos"][0]["code"] == "PLO1"


def test_repair_truncated_after_comma():
    broken = '{"courses":[{"code":"IT101"},{"code":"IT102"},'
    data = json.loads(_repair_truncated_json(broken))
    assert isinstance(data["courses"], list)
    assert data["courses"][0]["code"] == "IT101"


def test_repair_keeps_valid_json_unchanged():
    good = '{"a":[1,2,3],"b":{"c":"d"}}'
    assert json.loads(_repair_truncated_json(good)) == {"a": [1, 2, 3], "b": {"c": "d"}}


def test_strip_to_json_handles_code_fence():
    raw = '```json\n{"x": 1}\n```'
    assert json.loads(_strip_to_json(raw)) == {"x": 1}


def test_strip_to_json_handles_prose_wrapper():
    raw = 'Đây là kết quả:\n{"x": 1, "y": 2}\nHết.'
    assert json.loads(_strip_to_json(raw)) == {"x": 1, "y": 2}
