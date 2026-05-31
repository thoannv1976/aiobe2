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
    Chapter,
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
    Textbook,
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
        if c.description_en:
            en = doc.add_paragraph(f"    {c.code} (EN): {c.description_en}")
            if en.runs:
                en.runs[0].italic = True

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

        # Rubric chi tiết cho từng cấu phần (nếu có).
        for a in assessments:
            criteria = (a.rubric_json or {}).get("criteria") or []
            if not criteria:
                continue
            doc.add_heading(f"Rubric — {a.name}", level=3)
            rt = doc.add_table(rows=1, cols=3)
            rt.style = "Light Grid Accent 1"
            h = rt.rows[0].cells
            h[0].text, h[1].text, h[2].text = "Tiêu chí", "Trọng số (%)", "Các mức chất lượng"
            for cr in criteria:
                row = rt.add_row().cells
                row[0].text = str(cr.get("name", ""))
                row[1].text = str(cr.get("weight_percent", ""))
                row[2].text = "\n".join(str(lv) for lv in (cr.get("levels") or []))

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


# ---------------------------------------------------------------------------
# Giáo trình (SPEC 4.4): xuất DOCX và PDF, hỗ trợ nội dung Markdown đơn giản.
# ---------------------------------------------------------------------------
def _gather_textbook(db: Session, textbook_id: int):
    tb = db.get(Textbook, textbook_id)
    if not tb:
        raise ValueError("Không tìm thấy giáo trình")
    course = db.get(Course, tb.course_id)
    chapters = (
        db.query(Chapter).filter(Chapter.textbook_id == textbook_id).order_by(Chapter.order).all()
    )
    return tb, course, chapters


def _md_lines(text: str):
    """Tách Markdown thành các khối (kind, text) đơn giản: h2/h3/bullet/para."""
    for raw in (text or "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            yield ("h3", line[4:].strip())
        elif line.startswith("## "):
            yield ("h2", line[3:].strip())
        elif line.startswith("# "):
            yield ("h2", line[2:].strip())
        elif line.lstrip().startswith(("- ", "* ")):
            yield ("bullet", line.lstrip()[2:].strip())
        else:
            yield ("para", line.strip())


def textbook_to_docx(db: Session, textbook_id: int) -> bytes:
    tb, course, chapters = _gather_textbook(db, textbook_id)
    doc = _new_doc()
    doc.add_heading(tb.title, level=0)
    if course:
        doc.add_paragraph(f"Học phần: {course.code} — {course.name}")
    doc.add_paragraph(f"Phiên bản: v{tb.version} · Trạng thái: {tb.status}")

    for ch in chapters:
        doc.add_heading(f"Chương {ch.order}. {ch.title}", level=1)
        for kind, txt in _md_lines(ch.content_richtext or ""):
            if kind == "h2":
                doc.add_heading(txt, level=2)
            elif kind == "h3":
                doc.add_heading(txt, level=3)
            elif kind == "bullet":
                doc.add_paragraph(txt, style="List Bullet")
            else:
                doc.add_paragraph(txt)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


# Dò font DejaVu ở các vị trí phổ biến (khác nhau giữa các base image Linux).
_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
]


def _find_font(name: str) -> str | None:
    import os

    for d in _FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


def textbook_to_pdf(db: Session, textbook_id: int) -> bytes:
    """Xuất giáo trình ra PDF (fpdf2 + font DejaVu hỗ trợ tiếng Việt)."""
    from fpdf import FPDF

    regular = _find_font("DejaVuSans.ttf")
    bold = _find_font("DejaVuSans-Bold.ttf")
    if not regular:
        raise ValueError(
            "Thiếu font DejaVu để xuất PDF tiếng Việt. Cài gói 'fonts-dejavu-core'."
        )

    tb, course, chapters = _gather_textbook(db, textbook_id)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("DejaVu", "", regular)
    pdf.add_font("DejaVu", "B", bold or regular)
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(pdf.epw, 10, tb.title)
    pdf.set_font("DejaVu", "", 11)
    if course:
        pdf.multi_cell(pdf.epw, 7, f"Học phần: {course.code} — {course.name}")
    pdf.multi_cell(pdf.epw, 7, f"Phiên bản: v{tb.version} · Trạng thái: {tb.status}")
    pdf.ln(4)

    for ch in chapters:
        pdf.set_font("DejaVu", "B", 15)
        pdf.multi_cell(pdf.epw, 9, f"Chương {ch.order}. {ch.title}")
        pdf.ln(1)
        for kind, txt in _md_lines(ch.content_richtext or ""):
            if kind == "h2":
                pdf.set_font("DejaVu", "B", 13)
                pdf.multi_cell(pdf.epw, 8, txt)
            elif kind == "h3":
                pdf.set_font("DejaVu", "B", 12)
                pdf.multi_cell(pdf.epw, 7, txt)
            elif kind == "bullet":
                pdf.set_font("DejaVu", "", 11)
                pdf.multi_cell(pdf.epw, 6, f"  • {txt}")
            else:
                pdf.set_font("DejaVu", "", 11)
                pdf.multi_cell(pdf.epw, 6, txt)
        pdf.ln(3)

    out = pdf.output()
    return bytes(out)
