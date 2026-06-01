"""AI tạo ma trận đề thi từ CLO + thống kê ngân hàng câu hỏi (SPEC mục 11).

Bám sát ngân hàng hiện có để ma trận khả thi (không yêu cầu nhiều hơn số câu đang có).
Output validate Pydantic; con người rà soát trước khi dùng.
"""
from __future__ import annotations

import json

from app.services.llm import llm_complete


def _strip_to_json(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
    a, b = t.find("{"), t.rfind("}")
    return t[a : b + 1] if a != -1 and b != -1 else t


MATRIX_PROMPT = """Bạn là chuyên gia khảo thí theo chuẩn OBE/AUN-QA. Hãy thiết kế MA TRẬN ĐỀ THI \
(test blueprint) cho một học phần, phân bổ câu hỏi theo (CLO × mức Bloom × độ khó).

Nguyên tắc bắt buộc:
- Mỗi ô = một tổ hợp (CLO, Bloom, độ khó) với số câu và điểm mỗi câu.
- BÁM SÁT SỐ CÂU SẴN CÓ trong ngân hàng: số câu yêu cầu mỗi ô KHÔNG vượt quá số câu hiện có \
của đúng tổ hợp (CLO×Bloom×độ khó) đó. Nếu một tổ hợp có 0 câu, KHÔNG đưa vào ma trận.
- Phủ càng nhiều CLO càng tốt; phân bổ cân đối theo Bloom (mức thấp nhiều câu dễ, mức cao ít câu khó).
- Tổng điểm = tổng (số câu × điểm mỗi câu) nên xấp xỉ tổng điểm mục tiêu.

Chỉ trả về DUY NHẤT JSON:
{
  "name": "Tên ma trận gợi ý",
  "cells": [{"clo_code":"CLO1","bloom_level":"remember","difficulty":"easy","count":3,"points_each":0.5}]
}
Dùng đúng mã CLO và các mức Bloom/độ khó được cung cấp."""


def generate_exam_matrix_ai(
    course: dict,
    clos: list[dict],                 # [{code, description}]
    bank_cells: list[dict],           # [{clo_code, bloom_level, difficulty, available}]
    total_points: float = 100,
    name_hint: str = "",
) -> dict:
    """Trả về {name, cells:[{clo_code,bloom_level,difficulty,count,points_each}]}."""
    if not clos:
        raise ValueError("Học phần chưa có CLO.")
    if not any(c.get("available", 0) > 0 for c in bank_cells):
        raise ValueError("Ngân hàng câu hỏi đang trống. Hãy tạo câu hỏi trước khi sinh ma trận.")

    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos)
    bank_lines = "\n".join(
        f"- {b['clo_code']} × {b['bloom_level']} × {b['difficulty']}: có {b['available']} câu"
        for b in bank_cells if b.get("available", 0) > 0
    )
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CÁC CLO:\n{clo_lines}\n\n"
        f"SỐ CÂU SẴN CÓ TRONG NGÂN HÀNG (theo tổ hợp CLO×Bloom×độ khó):\n{bank_lines}\n\n"
        f"Tổng điểm mục tiêu: {total_points}.\n"
        + (f"Gợi ý tên: {name_hint}\n" if name_hint else "")
        + "Hãy thiết kế ma trận đề thi khả thi với ngân hàng trên."
    )
    raw = llm_complete(MATRIX_PROMPT, user, max_tokens=4000)
    data = json.loads(_strip_to_json(raw))
    cells = data.get("cells", []) if isinstance(data, dict) else []
    return {"name": str(data.get("name", name_hint or "Ma trận đề thi")), "cells": cells}
