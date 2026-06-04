"""Phân trang dùng chung cho các endpoint danh sách (limit/offset + tổng số).

Giữ tương thích ngược: vẫn TRẢ VỀ MẢNG như cũ, nhưng:
- nhận tham số query `limit` (1..MAX) và `offset` (>=0);
- đặt tổng số bản ghi vào header `X-Total-Count` để client phân trang.

Nhờ đó tránh `query.all()` không giới hạn (nguy cơ OOM/timeout khi dữ liệu lớn).
"""
from __future__ import annotations

from fastapi import Query, Response

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def limit_param(default: int = DEFAULT_LIMIT, max_: int = MAX_LIMIT):
    return Query(default, ge=1, le=max_, description="Số bản ghi tối đa mỗi trang")


def offset_param():
    return Query(0, ge=0, description="Vị trí bắt đầu (phân trang)")


def paginate(query, response: Response, limit: int, offset: int):
    """Đếm tổng (X-Total-Count) rồi trả về trang dữ liệu theo limit/offset."""
    total = query.order_by(None).count()
    response.headers["X-Total-Count"] = str(total)
    # Cho phép JS phía frontend đọc được header này qua CORS.
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return query.offset(offset).limit(limit).all()
