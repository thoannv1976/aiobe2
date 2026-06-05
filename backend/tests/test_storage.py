"""Test lớp lưu trữ trừu tượng (backend cục bộ)."""
from app.services import storage


def test_local_put_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "gcs_bucket", "")  # ép dùng cục bộ
    monkeypatch.setattr(storage.settings, "storage_dir", str(tmp_path))

    key = storage.put_file(b"xin chao", "de_cuong.txt")
    assert not storage.is_gcs_key(key)
    assert key.endswith(".txt")
    assert storage.get_bytes(key) == b"xin chao"
    with storage.local_path(key) as p:
        assert open(p, "rb").read() == b"xin chao"
