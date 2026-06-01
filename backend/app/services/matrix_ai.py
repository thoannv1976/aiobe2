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


OPTIMIZE_PROMPT = """Bạn là chuyên gia khảo thí và kiểm định AUN-QA. Hãy TỐI ƯU HÓA một MA TRẬN ĐỀ THI \
đã có, để đáp ứng tốt kiểm định AUN-QA (Criterion 4 - Student Assessment).

Mục tiêu tối ưu:
- TỔNG ĐIỂM phải BẰNG ĐÚNG thang điểm khai báo (điều chỉnh điểm mỗi câu / số câu để đạt).
- BÁM SÁT ngân hàng: số câu mỗi ô KHÔNG vượt số câu Đã duyệt sẵn có; bỏ ô có 0 câu.
- Phủ đủ các CLO trọng yếu; cân đối tỷ trọng Bloom hợp lý (không dồn quá nhiều vào Nhớ/Hiểu — \
nên có tỷ lệ phù hợp cho Vận dụng/Phân tích/Đánh giá để đo năng lực bậc cao).
- Constructive alignment: mỗi ô gắn CLO rõ ràng, mức Bloom phù hợp độ khó.

Trả về DUY NHẤT JSON:
{
  "name": "Tên ma trận",
  "cells": [{"clo_code":"CLO1","bloom_level":"remember","difficulty":"easy","count":3,"points_each":0.5}],
  "rationale": "Giải thích NGẮN GỌN (3-6 gạch đầu dòng, tiếng Việt) vì sao ma trận sau tối ưu \
ĐÁP ỨNG KIỂM ĐỊNH AUN-QA: nêu rõ tổng điểm đúng thang, độ phủ CLO, cân đối Bloom, tính khả thi \
với ngân hàng, và liên kết CLO-PLO/đánh giá."
}
Dùng đúng mã CLO và các mức Bloom/độ khó được cung cấp."""


def optimize_exam_matrix_ai(
    course: dict,
    clos: list[dict],
    bank_cells: list[dict],            # [{clo_code, bloom_level, difficulty, available}] (Approved)
    current_cells: list[dict],         # ma trận hiện tại [{clo_code,bloom_level,difficulty,count,points_each}]
    total_points: float = 10,
) -> dict:
    """Tối ưu ma trận hiện có. Trả {name, cells, rationale}."""
    if not clos:
        raise ValueError("Học phần chưa có CLO.")
    if not any(c.get("available", 0) > 0 for c in bank_cells):
        raise ValueError("Ngân hàng chưa có câu Đã duyệt để tối ưu ma trận.")

    clo_lines = "\n".join(f"- {c['code']}: {c['description']}" for c in clos)
    bank_lines = "\n".join(
        f"- {b['clo_code']} × {b['bloom_level']} × {b['difficulty']}: có {b['available']} câu Đã duyệt"
        for b in bank_cells if b.get("available", 0) > 0
    )
    cur_lines = "\n".join(
        f"- {c.get('clo_code')} × {c.get('bloom_level')} × {c.get('difficulty')}: "
        f"{c.get('count')} câu × {c.get('points_each')}đ"
        for c in current_cells
    ) or "(trống)"
    user = (
        f"HỌC PHẦN: {course.get('code','')} — {course.get('name','')}.\n"
        f"CÁC CLO:\n{clo_lines}\n\n"
        f"NGÂN HÀNG (câu Đã duyệt theo tổ hợp):\n{bank_lines}\n\n"
        f"MA TRẬN HIỆN TẠI (cần tối ưu):\n{cur_lines}\n\n"
        f"Thang điểm khai báo: {total_points}.\n"
        "Hãy tối ưu ma trận này."
    )
    raw = llm_complete(OPTIMIZE_PROMPT, user, max_tokens=4000)
    data = json.loads(_strip_to_json(raw))
    return {
        "name": str(data.get("name", "Ma trận tối ưu")),
        "cells": data.get("cells", []) if isinstance(data, dict) else [],
        "rationale": str(data.get("rationale", "")),
    }
