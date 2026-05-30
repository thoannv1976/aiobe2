"""Báo cáo phủ chuẩn & thống kê ngân hàng câu hỏi (SPEC 4.5, 4.7)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    AssessmentClo,
    Clo,
    CloPlo,
    Course,
    CourseOutline,
    Pi,
    Plo,
    Question,
)


def question_bank_stats(db: Session, course_id: int) -> dict:
    """Thống kê số câu theo CLO / Bloom / độ khó để phát hiện lỗ hổng."""
    qs = (
        db.query(Question)
        .filter(Question.course_id == course_id, Question.is_deleted == False)  # noqa: E712
        .all()
    )
    by_clo: dict = defaultdict(int)
    by_bloom: dict = defaultdict(int)
    by_difficulty: dict = defaultdict(int)
    by_clo_bloom: dict = defaultdict(int)
    for q in qs:
        by_clo[q.clo_id] += 1
        by_bloom[q.bloom_level] += 1
        by_difficulty[q.difficulty] += 1
        by_clo_bloom[f"{q.clo_id}|{q.bloom_level}"] += 1
    return {
        "total": len(qs),
        "by_clo": dict(by_clo),
        "by_bloom": dict(by_bloom),
        "by_difficulty": dict(by_difficulty),
        "by_clo_bloom": dict(by_clo_bloom),
    }


def program_coverage_report(db: Session, program_id: int) -> dict:
    """Ma trận tổng hợp PLO → PI → CLO → đánh giá (SPEC 4.7).

    Chỉ ra điểm thiếu (PLO không có CLO nào ánh xạ, CLO không được đánh giá...).
    """
    plos = db.query(Plo).filter(Plo.program_id == program_id).all()
    courses = db.query(Course).filter(Course.program_id == program_id).all()
    course_ids = [c.id for c in courses]

    # outline mới nhất mỗi course
    outlines: list[CourseOutline] = []
    for c in courses:
        latest = (
            db.query(CourseOutline)
            .filter(CourseOutline.course_id == c.id)
            .order_by(CourseOutline.version.desc())
            .first()
        )
        if latest:
            outlines.append(latest)

    outline_ids = [o.id for o in outlines]
    clos = (
        db.query(Clo).filter(Clo.outline_id.in_(outline_ids or [-1])).all() if outline_ids else []
    )
    clo_by_id = {c.id: c for c in clos}

    # PLO -> set(clo_id)
    plo_to_clos: dict = defaultdict(set)
    for cp in db.query(CloPlo).filter(CloPlo.clo_id.in_(clo_by_id.keys() or [-1])).all():
        plo_to_clos[cp.plo_id].add(cp.clo_id)

    # clo -> assessed?
    assessed_clo_ids: set = set()
    if outline_ids:
        for ac in (
            db.query(AssessmentClo)
            .join(Assessment, Assessment.id == AssessmentClo.assessment_id)
            .filter(Assessment.outline_id.in_(outline_ids))
            .all()
        ):
            assessed_clo_ids.add(ac.clo_id)

    gaps: list[str] = []
    plo_rows = []
    for plo in plos:
        pis = db.query(Pi).filter(Pi.plo_id == plo.id).all()
        clo_ids = plo_to_clos.get(plo.id, set())
        if not clo_ids:
            gaps.append(f"PLO {plo.code} chưa có CLO nào ánh xạ tới.")
        clo_detail = []
        for cid in clo_ids:
            clo = clo_by_id.get(cid)
            if not clo:
                continue
            is_assessed = cid in assessed_clo_ids
            if not is_assessed:
                gaps.append(f"CLO {clo.code} (ánh xạ PLO {plo.code}) chưa được đánh giá.")
            clo_detail.append({"clo_code": clo.code, "assessed": is_assessed})
        plo_rows.append(
            {
                "plo_code": plo.code,
                "description": plo.description,
                "pis": [{"code": p.code, "description": p.description} for p in pis],
                "clos": clo_detail,
            }
        )

    return {
        "program_id": program_id,
        "courses": len(courses),
        "plos": plo_rows,
        "gaps": gaps,
        "ok": not gaps,
    }
