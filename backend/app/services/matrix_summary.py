"""Tính tỷ trọng & cảnh báo cho ma trận đề thi (OBE/AUN-QA).

Hàm thuần để dễ unit test.
"""
from __future__ import annotations

# Mức Bloom bậc thấp (nhận biết/thông hiểu) — cảnh báo nếu chiếm quá nhiều.
LOW_BLOOM = {"remember", "understand"}


def rebalance_points(cells: list[dict], target_points: float, decimals: int = 2) -> list[dict]:
    """Cân lại điểm/câu để TỔNG ĐIỂM = đúng target_points (deterministic).

    LLM thường tính sai số học, nên sau khi AI trả ma trận ta tự cân lại:
    giữ nguyên TỶ LỆ điểm tương đối giữa các ô, scale để tổng khớp thang điểm,
    rồi bù phần dư làm tròn vào ô có nhiều câu nhất.
    """
    rows = [c for c in cells if int(c.get("count", 0) or 0) > 0]
    if not rows or target_points <= 0:
        return cells

    total_q = sum(int(c["count"]) for c in rows)
    cur_total = sum(int(c["count"]) * float(c.get("points_each") or 0) for c in rows)

    if cur_total > 0:
        scale = target_points / cur_total
        for c in rows:
            c["points_each"] = round(float(c.get("points_each") or 0) * scale, decimals)
    else:
        # chưa có điểm — chia đều theo số câu
        per = round(target_points / total_q, decimals)
        for c in rows:
            c["points_each"] = per

    # Bù phần lệch để TỔNG khớp CHÍNH XÁC: chọn một ô "điều chỉnh" và đặt điểm/câu của
    # nó = (target − tổng các ô còn lại) / count, KHÔNG làm tròn ô này -> tổng khớp tuyệt đối.
    # Ưu tiên ô count=1 (điểm/câu vẫn đẹp); nếu không có thì chọn ô count nhỏ nhất.
    adj_cell = min(
        rows, key=lambda c: (int(c["count"]) != 1, int(c["count"]))
    )
    others = round(
        sum(int(c["count"]) * c["points_each"] for c in rows if c is not adj_cell), decimals
    )
    adj_cell["points_each"] = round((target_points - others) / int(adj_cell["count"]), decimals + 2)
    return cells


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
