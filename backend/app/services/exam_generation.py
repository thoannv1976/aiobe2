"""Logic sinh đề thi từ ma trận (SPEC 4.6).

Hàm thuần `generate_exam_pure` để dễ test; wrapper DB ở dưới.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class GenResult:
    ok: bool
    picked_ids: list[int] = field(default_factory=list)
    total_points: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    by_cell: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "picked_ids": self.picked_ids,
            "total_points": self.total_points,
            "errors": self.errors,
            "warnings": self.warnings,
            "by_cell": self.by_cell,
        }


def _cell_key(c: dict) -> tuple:
    return (c.get("clo_id"), c.get("bloom_level"), c.get("difficulty"))


def generate_exam_pure(
    cells: list[dict],       # [{clo_id, bloom_level, difficulty, count, points_each}]
    questions: list[dict],   # [{id, clo_id, bloom_level, difficulty, points}]
    seed: int | None = None,
) -> GenResult:
    """Bốc câu hỏi thỏa từng ô (CLO×Bloom×độ khó), tránh trùng."""
    rng = random.Random(seed)
    used: set[int] = set()
    picked: list[int] = []
    errors: list[str] = []
    by_cell: list[dict] = []
    total_points = 0.0

    for cell in cells:
        key = _cell_key(cell)
        count = int(cell.get("count", 0))
        pool = [
            q
            for q in questions
            if q["id"] not in used
            and q.get("clo_id") == cell.get("clo_id")
            and q.get("bloom_level") == cell.get("bloom_level")
            and q.get("difficulty") == cell.get("difficulty")
        ]
        rng.shuffle(pool)
        chosen = pool[:count]
        if len(chosen) < count:
            errors.append(
                f"Ô {key} cần {count} câu nhưng ngân hàng chỉ có {len(chosen)} câu phù hợp."
            )
        for q in chosen:
            used.add(q["id"])
            picked.append(q["id"])
            pts = cell.get("points_each")
            total_points += pts if pts is not None else q.get("points", 1)
        by_cell.append(
            {
                "clo_id": cell.get("clo_id"),
                "bloom_level": cell.get("bloom_level"),
                "difficulty": cell.get("difficulty"),
                "required": count,
                "picked": len(chosen),
            }
        )

    return GenResult(
        ok=not errors,
        picked_ids=picked,
        total_points=round(total_points, 2),
        errors=errors,
        by_cell=by_cell,
    )


def validate_matrix_coverage_pure(cells: list[dict], required_clos: set) -> list[str]:
    """Cảnh báo nếu ma trận không phủ hết các CLO yêu cầu (SPEC 4.5/4.6)."""
    covered = {c.get("clo_id") for c in cells if int(c.get("count", 0)) > 0}
    return [f"CLO id={clo} không được phủ trong ma trận đề." for clo in required_clos - covered]
