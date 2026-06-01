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
    Lecture,
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

    # Ma trận 2: CLO – nội dung giảng dạy – đánh giá (SPEC 8.2)
    # (Nội dung/PPGD lấy từ các buổi dạy gắn CLO; đánh giá lấy từ cấu phần gắn CLO.)
    assess_by_clo: dict[int, list[str]] = {}
    for a in assessments:
        for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all():
            assess_by_clo.setdefault(ac.clo_id, []).append(a.name)
    topics_by_clo: dict[int, list[str]] = {}
    for lp in lessons:
        for lc in db.query(LessonPlanClo).filter(LessonPlanClo.lesson_plan_id == lp.id).all():
            topics_by_clo.setdefault(lc.clo_id, []).append(lp.topic)
    if clos:
        doc.add_heading("6. Ma trận CLO – Nội dung – Đánh giá", level=2)
        m2 = doc.add_table(rows=1, cols=3)
        m2.style = "Light Grid Accent 1"
        h = m2.rows[0].cells
        h[0].text, h[1].text, h[2].text = "CLO", "Nội dung giảng dạy", "Hình thức đánh giá"
        for c in clos:
            row = m2.add_row().cells
            row[0].text = c.code
            row[1].text = "; ".join(topics_by_clo.get(c.id, [])) or "—"
            row[2].text = ", ".join(assess_by_clo.get(c.id, [])) or "—"

    # Ma trận 3: CLO – thành phần đánh giá (tỷ trọng %) (SPEC 8.3)
    if clos and assessments:
        doc.add_heading("7. Ma trận CLO – Thành phần đánh giá (tỷ trọng %)", level=2)
        # phân bổ đều trọng số mỗi cấu phần cho các CLO mà nó đánh giá
        a_clos: dict[int, list[int]] = {}
        for a in assessments:
            ids = [ac.clo_id for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all()]
            a_clos[a.id] = ids
        m3 = doc.add_table(rows=1, cols=len(assessments) + 2)
        m3.style = "Light Grid Accent 1"
        hdr = m3.rows[0].cells
        hdr[0].text = "CLO"
        for j, a in enumerate(assessments):
            hdr[j + 1].text = f"{a.name} ({a.weight_percent}%)"
        hdr[-1].text = "Tổng"
        for c in clos:
            row = m3.add_row().cells
            row[0].text = c.code
            total = 0.0
            for j, a in enumerate(assessments):
                ids = a_clos.get(a.id, [])
                share = round(a.weight_percent / len(ids), 1) if (ids and c.id in ids) else 0
                row[j + 1].text = f"{share}%" if share else ""
                total += share
            row[-1].text = f"{round(total, 1)}%"

    # Phương pháp dạy-học & tài liệu
    if outline.teaching_methods_json:
        doc.add_heading("8. Phương pháp dạy-học", level=2)
        for m in outline.teaching_methods_json:
            doc.add_paragraph(str(m), style="List Bullet")
    if outline.references_json:
        doc.add_heading("9. Tài liệu tham khảo", level=2)
        for r in outline.references_json:
            doc.add_paragraph(str(r), style="List Number")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def exam_to_docx(db: Session, exam_id: int, variant: int = 1, with_answers: bool = False) -> bytes:
    """Xuất đề thi (1 mã đề) ra DOCX; tùy chọn kèm đáp án/barem.

    Câu hỏi được nhóm theo LOẠI (trắc nghiệm trước, tự luận sau) và chia phần có tiêu đề
    để thuận tiện in ấn.
    """
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

    # Gom câu theo nhóm loại để in thành các phần.
    # Nhóm 1: trắc nghiệm (mcq_single, mcq_multi); Nhóm 2: điền khuyết;
    # Nhóm 3: tự luận ngắn; Nhóm 4: tự luận; Nhóm 5: bài tập/khác.
    GROUPS = [
        ("Phần trắc nghiệm", {"mcq_single", "mcq_multi"}),
        ("Phần điền khuyết", {"fill_blank"}),
        ("Phần tự luận ngắn", {"short_answer"}),
        ("Phần tự luận", {"essay"}),
        ("Phần bài tập", {"exercise"}),
    ]
    items = [(eq, db.get(Question, eq.question_id)) for eq in eqs]
    items = [(eq, q) for eq, q in items if q is not None]

    num = 0
    roman = ["I", "II", "III", "IV", "V", "VI"]
    section_idx = 0
    used_ids: set[int] = set()
    for title, types in GROUPS:
        group = [(eq, q) for eq, q in items if q.type in types]
        if not group:
            continue
        section_idx += 1
        doc.add_heading(f"Phần {roman[section_idx - 1]}. {title}", level=1)
        for eq, q in group:
            used_ids.add(eq.id)
            num += 1
            doc.add_paragraph(f"Câu {num} ({q.points} điểm): {q.content}")
            for i, opt in enumerate(q.options_json or []):
                doc.add_paragraph(f"   {chr(65 + i)}. {opt}")
            if with_answers:
                ans = doc.add_paragraph(f"   → Đáp án: {q.answer or '-'}")
                if ans.runs:
                    ans.runs[0].italic = True
                if q.explanation:
                    doc.add_paragraph(f"   Giải thích: {q.explanation}")
    # Loại còn lại (nếu có loại lạ) — in nốt.
    rest = [(eq, q) for eq, q in items if eq.id not in used_ids]
    if rest:
        doc.add_heading("Phần khác", level=1)
        for eq, q in rest:
            num += 1
            doc.add_paragraph(f"Câu {num} ({q.points} điểm): {q.content}")
            if with_answers:
                doc.add_paragraph(f"   → Đáp án: {q.answer or '-'}")

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


# ---------------------------------------------------------------------------
# Bài giảng (SPEC mục 10): xuất DOCX nội dung + PPTX slide
# ---------------------------------------------------------------------------
def lecture_to_docx(db: Session, lecture_id: int) -> bytes:
    lec = db.get(Lecture, lecture_id)
    if not lec:
        raise ValueError("Không tìm thấy bài giảng")
    course = db.get(Course, lec.course_id)
    doc = _new_doc()
    doc.add_heading(f"Buổi {lec.session_no}. {lec.title}", level=0)
    if course:
        doc.add_paragraph(f"Học phần: {course.code} — {course.name}")
    if lec.clo_codes_json:
        doc.add_paragraph(f"CLO: {', '.join(lec.clo_codes_json)}")
    for kind, txt in _md_lines(lec.content_richtext or ""):
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


def lecture_to_pptx(db: Session, lecture_id: int) -> bytes:
    """Xuất slide bài giảng ra PowerPoint (SPEC 21 — đầu ra PowerPoint)."""
    from pptx import Presentation
    from pptx.util import Pt as PptPt

    lec = db.get(Lecture, lecture_id)
    if not lec:
        raise ValueError("Không tìm thấy bài giảng")
    course = db.get(Course, lec.course_id)

    prs = Presentation()
    # Slide tiêu đề
    title_layout = prs.slide_layouts[0]
    s = prs.slides.add_slide(title_layout)
    s.shapes.title.text = lec.title
    if s.placeholders and len(s.placeholders) > 1:
        s.placeholders[1].text = f"{course.code} — {course.name}" if course else ""

    bullet_layout = prs.slide_layouts[1]
    for sl in (lec.slides_json or []):
        slide = prs.slides.add_slide(bullet_layout)
        slide.shapes.title.text = str(sl.get("title", ""))
        body = slide.placeholders[1].text_frame
        body.clear()
        bullets = sl.get("bullets", []) or []
        for i, b in enumerate(bullets):
            p = body.paragraphs[0] if i == 0 else body.add_paragraph()
            p.text = str(b)
            p.font.size = PptPt(18)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()
