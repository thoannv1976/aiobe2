"""Tính tỷ trọng & cảnh báo cho ma trận đề thi (OBE/AUN-QA).

Hàm thuần để dễ unit test.
"""
from __future__ import annotations

# Mức Bloom bậc thấp (nhận biết/thông hiểu) — cảnh báo nếu chiếm quá nhiều.
LOW_BLOOM = {"remember", "understand"}


def matrix_summary(cells: list[dict], declared_points: float = 10) -> dict:
    """Tính tổng câu/điểm, tỷ trọng theo CLO & Bloom, và cảnh báo.

    cells: [{clo_id, bloom_level, difficulty, count, points_each}]
    """
    total_q = 0
    total_pts = 0.0
    by_clo: dict = {}
    by_bloom: dict = {}
    for c in cells:
        cnt = int(c.get("count", 0) or 0)
        pe = float(c.get("points_each") or 0)
        pts = cnt * pe
        total_q += cnt
        total_pts += pts
        clo = c.get("clo_id")
        by_clo[clo] = by_clo.get(clo, 0.0) + pts
        bl = c.get("bloom_level") or "?"
        by_bloom[bl] = by_bloom.get(bl, 0.0) + pts

    total_pts = round(total_pts, 2)

    def pct(x: float) -> float:
        return round(x / total_pts * 100, 1) if total_pts else 0.0

    clo_weight = {str(k): {"points": round(v, 2), "percent": pct(v)} for k, v in by_clo.items()}
    bloom_weight = {k: {"points": round(v, 2), "percent": pct(v)} for k, v in by_bloom.items()}

    warnings: list[str] = []
    errors: list[str] = []

    if total_pts != declared_points:
        errors.append(
            f"Tổng điểm = {total_pts} khác thang điểm khai báo {declared_points}."
        )
    if total_q == 0:
        errors.append("Ma trận chưa có câu hỏi nào.")

    # Tỷ trọng Bloom bậc thấp
    low_pts = sum(by_bloom.get(b, 0.0) for b in LOW_BLOOM)
    if total_pts and low_pts / total_pts > 0.6:
        warnings.append(
            f"Đề tập trung quá nhiều vào mức Nhớ/Hiểu ({pct(low_pts)}% điểm) — nên tăng mức vận dụng trở lên."
        )

    # Dòng thiếu dữ liệu bắt buộc
    for i, c in enumerate(cells, start=1):
        if not c.get("clo_id"):
            errors.append(f"Dòng {i}: thiếu CLO.")
        if not c.get("bloom_level"):
            errors.append(f"Dòng {i}: thiếu mức Bloom.")
        if int(c.get("count", 0) or 0) <= 0:
            errors.append(f"Dòng {i}: số câu phải > 0.")

    return {
        "total_questions": total_q,
        "total_points": total_pts,
        "declared_points": declared_points,
        "clo_weight": clo_weight,
        "bloom_weight": bloom_weight,
        "warnings": warnings,
        "errors": errors,
        "ok": not errors,
    }
