"""Lớp lưu trữ file trừu tượng: GCS (prod, Cloud Run) hoặc cục bộ (dev/test).

Backend chọn theo settings.gcs_bucket. "Khóa lưu" (storage key) được lưu trong
Document.file_path:
- cục bộ: đường dẫn tệp (vd ./storage/abc.pdf)
- GCS:    gs://<bucket>/<prefix><name>

Lý do: trên Cloud Run ổ đĩa container là tạm thời và không chia sẻ giữa các instance,
nên file upload (đề án, đề cương gốc, minh chứng) PHẢI lưu ngoài (GCS) để bền vững.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
import uuid
from collections.abc import Iterator

from app.config import settings


def is_gcs_key(key: str) -> bool:
    return bool(key) and key.startswith("gs://")


def _split_gcs(key: str) -> tuple[str, str]:
    bucket, _, obj = key[len("gs://"):].partition("/")
    return bucket, obj


def put_file(data: bytes, filename: str = "") -> str:
    """Lưu nội dung file, trả về storage key (đường dẫn cục bộ hoặc gs://...)."""
    ext = os.path.splitext(filename or "")[1]
    name = f"{uuid.uuid4().hex}{ext}"
    if settings.gcs_bucket:
        from google.cloud import storage  # import lười (chỉ cần khi bật GCS)

        client = storage.Client()
        obj = f"{settings.gcs_prefix}{name}"
        client.bucket(settings.gcs_bucket).blob(obj).upload_from_string(data)
        return f"gs://{settings.gcs_bucket}/{obj}"
    os.makedirs(settings.storage_dir, exist_ok=True)
    path = os.path.join(settings.storage_dir, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def get_bytes(key: str) -> bytes:
    """Đọc lại nội dung file theo storage key."""
    if is_gcs_key(key):
        from google.cloud import storage

        bucket, obj = _split_gcs(key)
        return storage.Client().bucket(bucket).blob(obj).download_as_bytes()
    with open(key, "rb") as f:
        return f.read()


@contextlib.contextmanager
def local_path(key: str) -> Iterator[str]:
    """Cung cấp đường dẫn cục bộ để thư viện xử lý (PyMuPDF/python-docx) đọc trực tiếp.

    Với GCS: tải về tệp tạm và tự dọn sau khi dùng. Với cục bộ: trả nguyên đường dẫn.
    """
    if is_gcs_key(key):
        data = get_bytes(key)
        ext = os.path.splitext(key)[1]
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        try:
            tmp.write(data)
            tmp.close()
            yield tmp.name
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp.name)
    else:
        yield key
