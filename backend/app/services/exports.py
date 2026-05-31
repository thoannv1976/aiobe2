"""Xuất tài liệu ra DOCX/PDF (SPEC 4.3, 4.6): đề cương học phần và đề thi + đáp án + bảng đặc tả.

DOCX dùng python-docx. PDF: tạo HTML rồi để client in, hoặc trả DOCX là chính.
Ở đây tập trung DOCX (định dạng chuẩn của trường) — trả về bytes.
"""
from __future__ import annotations

import io

from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    AssessmentClo,
    Clo,
    CloPlo,
    Course,
    CourseOutline,
    Exam,
    ExamQuestion,
    LessonPlan,
    LessonPlanClo,
    Plo,
    Question,
)


def _new_doc():
    from docx import Document

    return Document()


def outline_to_docx(db: Session, outline_id: int) -> bytes:
    """Xuất đề cương học phần ra DOCX theo cấu trúc SPEC 4.3."""
    outline = db.get(CourseOutline, outline_id)
    if not outline:
        raise ValueError("Không tìm thấy đề cương")
    course = db.get(Course, outline.course_id)

    doc = _new_doc()
    doc.add_heading("ĐỀ CƯƠNG HỌC PHẦN", level=0)
    doc.add_heading(f"{course.code} — {course.name}", level=1)
    doc.add_paragraph(f"Phiên bản: v{outline.version} · Trạng thái: {outline.status}")
    doc.add_paragraph(f"Số tín chỉ: {course.credits}")

    if outline.description:
        doc.add_heading("1. Mô tả học phần", level=2)
        doc.add_paragraph(outline.description)

    # CLO
    clos = db.query(Clo).filter(Clo.outline_id == outline_id).all()
    clo_by_id = {c.id: c for c in clos}
    doc.add_heading("2. Chuẩn đầu ra học phần (CLO)", level=2)
    for c in clos:
        doc.add_paragraph(f"{c.code} ({c.bloom_level or '-'}): {c.description}", style="List Bullet")

    # Ma trận CLO × PLO
    doc.add_heading("3. Ma trận CLO × PLO", level=2)
    cps = db.query(CloPlo).filter(CloPlo.clo_id.in_([c.id for c in clos] or [-1])).all()
    if cps:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text = "CLO", "PLO", "Mức đóng góp"
        for cp in cps:
            plo = db.get(Plo, cp.plo_id)
            row = table.add_row().cells
            row[0].text = clo_by_id.get(cp.clo_id).code if cp.clo_id in clo_by_id else "?"
            row[1].text = plo.code if plo else "?"
            row[2].text = cp.contribution_level

    # Đánh giá
    doc.add_heading("4. Phương pháp đánh giá", level=2)
    assessments = db.query(Assessment).filter(Assessment.outline_id == outline_id).all()
    if assessments:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text = "Cấu phần", "Trọng số (%)", "CLO"
        for a in assessments:
            clo_codes = [
                clo_by_id[ac.clo_id].code
                for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all()
                if ac.clo_id in clo_by_id
            ]
            row = table.add_row().cells
            row[0].text = a.name
            row[1].text = str(a.weight_percent)
            row[2].text = ", ".join(clo_codes)

    # Kế hoạch giảng dạy
    doc.add_heading("5. Kế hoạch giảng dạy", level=2)
    lessons = db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).order_by(LessonPlan.week).all()
    if lessons:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text = "Tuần", "Nội dung", "CLO"
        for lp in lessons:
            clo_codes = [
                clo_by_id[lc.clo_id].code
                for lc in db.query(LessonPlanClo).filter(LessonPlanClo.lesson_plan_id == lp.id).all()
                if lc.clo_id in clo_by_id
            ]
            row = table.add_row().cells
            row[0].text = str(lp.week)
            row[1].text = lp.topic
            row[2].text = ", ".join(clo_codes)

    # Phương pháp dạy-học & tài liệu
    if outline.teaching_methods_json:
        doc.add_heading("6. Phương pháp dạy-học", level=2)
        for m in outline.teaching_methods_json:
            doc.add_paragraph(str(m), style="List Bullet")
    if outline.references_json:
        doc.add_heading("7. Tài liệu tham khảo", level=2)
        for r in outline.references_json:
            doc.add_paragraph(str(r), style="List Number")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def exam_to_docx(db: Session, exam_id: int, variant: int = 1, with_answers: bool = False) -> bytes:
    """Xuất đề thi (1 mã đề) ra DOCX; tùy chọn kèm đáp án/barem."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise ValueError("Không tìm thấy đề thi")
    course = db.get(Course, exam.course_id)

    doc = _new_doc()
    doc.add_heading(f"{exam.name.upper()} — Mã đề {variant}", level=0)
    doc.add_paragraph(f"Học phần: {course.code} — {course.name}")
    doc.add_paragraph(f"Thời gian: {exam.duration_min} phút · Tổng điểm: {exam.total_points}")
    doc.add_paragraph("")

    eqs = (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id, ExamQuestion.variant == variant)
        .order_by(ExamQuestion.order)
        .all()
    )
    for eq in eqs:
        q = db.get(Question, eq.question_id)
        if not q:
            continue
        doc.add_paragraph(f"Câu {eq.order} ({q.points} điểm): {q.content}")
        for i, opt in enumerate(q.options_json or []):
            doc.add_paragraph(f"   {chr(65 + i)}. {opt}")
        if with_answers:
            ans = doc.add_paragraph(f"   → Đáp án: {q.answer or '-'}")
            ans.runs[0].italic = True
            if q.explanation:
                doc.add_paragraph(f"   Giải thích: {q.explanation}")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
