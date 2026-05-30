"""Logic OBE: kiểm tra alignment & độ phủ (SPEC 4.2, 4.3, 4.7).

Các hàm `*_pure` nhận cấu trúc dữ liệu đơn giản để dễ unit test, không phụ thuộc DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


# ---------------------------------------------------------------------------
# Đề cương: kiểm tra constructive alignment (SPEC 4.3)
# ---------------------------------------------------------------------------
def check_outline_alignment_pure(
    clo_codes: list[str],
    clo_to_plos: dict[str, list[str]],
    assessments: list[dict],           # [{name, weight, clos: [clo_code]}]
    lesson_clo_sets: list[list[str]],  # mỗi buổi -> list clo_code
) -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Mỗi CLO phải ánh xạ ít nhất một PLO.
    for clo in clo_codes:
        if not clo_to_plos.get(clo):
            errors.append(f"CLO {clo} chưa ánh xạ tới PLO nào.")

    # 2. Mỗi CLO phải được phủ bởi ít nhất một cấu phần đánh giá.
    assessed = {c for a in assessments for c in a.get("clos", [])}
    for clo in clo_codes:
        if clo not in assessed:
            errors.append(f"CLO {clo} không được phủ bởi cấu phần đánh giá nào.")

    # 3. Tổng trọng số đánh giá = 100%.
    total_weight = round(sum(a.get("weight", 0) for a in assessments), 4)
    if assessments and total_weight != 100:
        errors.append(f"Tổng trọng số đánh giá = {total_weight}%, phải bằng 100%.")

    # 4. Cảnh báo CLO không xuất hiện trong bất kỳ buổi dạy nào.
    taught = {c for s in lesson_clo_sets for c in s}
    for clo in clo_codes:
        if clo not in taught:
            warnings.append(f"CLO {clo} không xuất hiện trong buổi dạy nào.")

    return CheckResult(ok=not errors, errors=errors, warnings=warnings)


def check_outline_alignment(db, outline_id: int) -> CheckResult:
    """Phiên bản dùng DB, trích dữ liệu rồi gọi hàm thuần."""
    from app.models import (
        Assessment,
        AssessmentClo,
        Clo,
        CloPlo,
        LessonPlan,
        LessonPlanClo,
        Plo,
    )

    clos = db.query(Clo).filter(Clo.outline_id == outline_id).all()
    clo_by_id = {c.id: c.code for c in clos}
    clo_codes = [c.code for c in clos]

    clo_to_plos: dict[str, list[str]] = {c.code: [] for c in clos}
    for cp in db.query(CloPlo).filter(CloPlo.clo_id.in_(clo_by_id.keys() or [-1])).all():
        plo = db.query(Plo).get(cp.plo_id)
        if cp.clo_id in clo_by_id and plo:
            clo_to_plos[clo_by_id[cp.clo_id]].append(plo.code)

    assessments = []
    for a in db.query(Assessment).filter(Assessment.outline_id == outline_id).all():
        clo_codes_a = [
            clo_by_id[ac.clo_id]
            for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all()
            if ac.clo_id in clo_by_id
        ]
        assessments.append({"name": a.name, "weight": a.weight_percent, "clos": clo_codes_a})

    lesson_clo_sets = []
    for lp in db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).all():
        codes = [
            clo_by_id[lc.clo_id]
            for lc in db.query(LessonPlanClo)
            .filter(LessonPlanClo.lesson_plan_id == lp.id)
            .all()
            if lc.clo_id in clo_by_id
        ]
        lesson_clo_sets.append(codes)

    return check_outline_alignment_pure(clo_codes, clo_to_plos, assessments, lesson_clo_sets)


# ---------------------------------------------------------------------------
# CTĐT: mỗi PLO phải có ít nhất một học phần Master (SPEC 4.2)
# ---------------------------------------------------------------------------
def check_program_plo_coverage_pure(
    plo_codes: list[str],
    course_plo: list[dict],  # [{course_code, plo_code, level}]
) -> CheckResult:
    warnings: list[str] = []
    errors: list[str] = []

    mastered = {cp["plo_code"] for cp in course_plo if cp.get("level") == "M"}
    covered = {cp["plo_code"] for cp in course_plo}

    for plo in plo_codes:
        if plo not in covered:
            errors.append(f"PLO {plo} chưa được học phần nào phụ trách.")
        elif plo not in mastered:
            warnings.append(f"PLO {plo} chưa có học phần ở mức Master (M).")

    return CheckResult(ok=not errors, errors=errors, warnings=warnings)


def check_program_plo_coverage(db, program_id: int) -> CheckResult:
    from app.models import Course, CoursePlo, Plo

    plos = db.query(Plo).filter(Plo.program_id == program_id).all()
    plo_by_id = {p.id: p.code for p in plos}
    plo_codes = [p.code for p in plos]

    courses = db.query(Course).filter(Course.program_id == program_id).all()
    course_by_id = {c.id: c.code for c in courses}

    cp_rows = []
    for cp in db.query(CoursePlo).filter(CoursePlo.course_id.in_(course_by_id or [-1])).all():
        if cp.course_id in course_by_id and cp.plo_id in plo_by_id:
            cp_rows.append(
                {
                    "course_code": course_by_id[cp.course_id],
                    "plo_code": plo_by_id[cp.plo_id],
                    "level": cp.level,
                }
            )

    return check_program_plo_coverage_pure(plo_codes, cp_rows)
