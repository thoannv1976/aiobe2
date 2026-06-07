"""Mã hóa secret (API key AI của trường) khi lưu DB — Nhóm C / C4.

- Nếu `settings.encryption_key` trống → trả nguyên bản (dev/tương thích ngược).
- Nếu có → mã hóa Fernet (AES); ciphertext có tiền tố "enc:v1:" để phân biệt với dữ liệu cũ.
- Đọc: tự nhận biết tiền tố; chuỗi cũ (không tiền tố) coi như plaintext (legacy).

Có thể thay bằng Cloud KMS (envelope encryption) sau mà không đổi giao diện encrypt/decrypt.
"""
from __future__ import annotations

import base64
import hashlib

from app.config import settings

_PREFIX = "enc:v1:"


def _fernet():
    if not settings.encryption_key:
        return None
    from cryptography.fernet import Fernet  # phụ thuộc 'cryptography' (đã có qua python-jose)

    # Suy ra khóa Fernet hợp lệ (32 byte url-safe base64) từ chuỗi cấu hình tùy ý.
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.encryption_key.encode()).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if not plain:
        return plain
    f = _fernet()
    if f is None:
        return plain  # dev: lưu nguyên bản
    return _PREFIX + f.encrypt(plain.encode()).decode()


def decrypt_secret(stored: str) -> str:
    if not stored or not stored.startswith(_PREFIX):
        return stored  # plaintext legacy hoặc chưa mã hóa
    f = _fernet()
    if f is None:
        return stored  # không có khóa để giải (cấu hình sai) — trả nguyên trạng
    return f.decrypt(stored[len(_PREFIX):].encode()).decode()
