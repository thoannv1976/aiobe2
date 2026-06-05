"""Các handler tác vụ nền (job). Mỗi handler nhận (db, job) và trả dict kết quả."""
from __future__ import annotations

from app.models import Chapter, ChapterClo, Clo, Course, CourseOutline, Textbook
from app.services.jobs import register, set_progress
from app.services.textbook_ai import (
    generate_chapter_content_ai,
    generate_chapter_content_deep_ai,
    generate_chapter_outline_ai,
)


def _latest_outline_clos(db, course_id: int) -> list[Clo]:
    outline = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    return db.query(Clo).filter(Clo.outline_id == outline.id).all() if outline else []


@register("generate_textbook")
def generate_textbook_job(db, job) -> dict:
    """Sinh cả giáo trình (dàn ý + nội dung từng chương) — chạy nền, cập nhật tiến độ theo chương."""
    p = job.params_json or {}
    course = db.get(Course, p.get("course_id"))
    if not course:
        raise ValueError("Không tìm thấy học phần")
    clos = _latest_outline_clos(db, course.id)
    if not clos:
        raise ValueError("Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")
    clo_by_code = {c.code: c for c in clos}
    course_d = {"code": course.code, "name": course.name}
    clo_dicts = [{"code": c.code, "description": c.description} for c in clos]

    set_progress(db, job, 0, 1, "Đang lập dàn ý chương...")
    outline = generate_chapter_outline_ai(course_d, clo_dicts, p.get("num_chapters", 0))

    tb = Textbook(course_id=course.id, title=p.get("title") or f"Giáo trình {course.name}",
                  version=1, status="draft")
    db.add(tb)
    db.flush()

    chapters = outline.chapters
    total = max(1, len(chapters))
    set_progress(db, job, 0, total, f"Đã có dàn ý {len(chapters)} chương. Bắt đầu soạn nội dung...")

    with_content = bool(p.get("with_content", True))
    deep = bool(p.get("deep", False))
    target_pages = int(p.get("target_pages", 30))

    for i, gc in enumerate(chapters):
        content = ""
        if with_content:
            ch_clos = [{"code": code, "description": clo_by_code[code].description}
                       for code in gc.clo_codes if code in clo_by_code]
            try:
                if deep:
                    content = generate_chapter_content_deep_ai(
                        course_d, gc.title, ch_clos, gc.summary, target_pages=target_pages
                    )
                else:
                    content = generate_chapter_content_ai(course_d, gc.title, ch_clos, gc.summary)
            except Exception:  # noqa: BLE001
                content = gc.summary or ""
        ch = Chapter(textbook_id=tb.id, order=gc.order, title=gc.title, content_richtext=content)
        db.add(ch)
        db.flush()
        for code in gc.clo_codes:
            if code in clo_by_code:
                db.add(ChapterClo(chapter_id=ch.id, clo_id=clo_by_code[code].id))
        db.commit()
        set_progress(db, job, i + 1, total, f"Đã soạn chương {i + 1}/{total}: {gc.title}")

    return {"textbook_id": tb.id, "chapters": len(chapters)}
