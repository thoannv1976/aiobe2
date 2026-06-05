from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Chapter, ChapterClo, Clo, Course, CourseOutline, Role, Textbook, User
from app.schemas.content import ChapterCreate, ChapterOut, TextbookCreate, TextbookOut
from app.services.audit import log_action
from app.services.exports import textbook_to_docx, textbook_to_pdf
from app.services.extraction import suggest_chapter_outline
from app.services.textbook_ai import (
    generate_chapter_content_ai,
    generate_chapter_content_deep_ai,
    generate_chapter_outline_ai,
    improve_chapter_ai,
    review_chapter_ai,
)

router = APIRouter(prefix="/api", tags=["textbooks"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


def _course_clos(db: Session, course_id: int) -> list[Clo]:
    outline = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    return db.query(Clo).filter(Clo.outline_id == outline.id).all() if outline else []


@router.get("/courses/{course_id}/textbooks", response_model=list[TextbookOut])
def list_textbooks(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Textbook).filter(Textbook.course_id == course_id).all()


@router.post("/textbooks", response_model=TextbookOut, status_code=201)
def create_textbook(payload: TextbookCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    if not db.get(Course, payload.course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = Textbook(course_id=payload.course_id, title=payload.title, version=1, status="draft")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "textbook", obj.id, "create")
    return obj


@router.get("/textbooks/{tid}/chapters", response_model=list[ChapterOut])
def list_chapters(tid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for c in db.query(Chapter).filter(Chapter.textbook_id == tid).order_by(Chapter.order).all():
        d = ChapterOut.model_validate(c)
        d.clo_ids = [cc.clo_id for cc in c.chapter_clos]
        out.append(d)
    return out


@router.post("/textbooks/{tid}/chapters", response_model=ChapterOut, status_code=201)
def create_chapter(tid: int, payload: ChapterCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    if not db.get(Textbook, tid):
        raise HTTPException(404, "Không tìm thấy giáo trình")
    obj = Chapter(
        textbook_id=tid, order=payload.order, title=payload.title,
        content_richtext=payload.content_richtext,
    )
    db.add(obj)
    db.flush()
    for cid in payload.clo_ids:
        db.add(ChapterClo(chapter_id=obj.id, clo_id=cid))
    db.commit()
    db.refresh(obj)
    res = ChapterOut.model_validate(obj)
    res.clo_ids = payload.clo_ids
    log_action(db, user.id, "chapter", obj.id, "create")
    return res


@router.patch("/chapters/{cid}", response_model=ChapterOut)
def update_chapter(cid: int, payload: ChapterCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Chapter, cid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy chương")
    obj.order = payload.order
    obj.title = payload.title
    obj.content_richtext = payload.content_richtext
    db.query(ChapterClo).filter(ChapterClo.chapter_id == cid).delete()
    for clo_id in payload.clo_ids:
        db.add(ChapterClo(chapter_id=cid, clo_id=clo_id))
    db.commit()
    db.refresh(obj)
    res = ChapterOut.model_validate(obj)
    res.clo_ids = payload.clo_ids
    log_action(db, user.id, "chapter", cid, "update")
    return res


@router.delete("/chapters/{cid}", status_code=204)
def delete_chapter(cid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Chapter, cid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "chapter", cid, "delete")


@router.get("/courses/{course_id}/chapter-suggestions")
def chapter_suggestions(course_id: int, db: Session = Depends(get_db), _: User = Depends(LECTURER)):
    """Gợi ý đề mục giáo trình bằng AI dựa trên CLO của đề cương mới nhất (SPEC 4.4)."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    outline = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    if not outline:
        raise HTTPException(400, "Học phần chưa có đề cương/CLO để gợi ý")
    clos = [
        {"code": c.code, "description": c.description}
        for c in db.query(Clo).filter(Clo.outline_id == outline.id).all()
    ]
    if not clos:
        raise HTTPException(400, "Đề cương chưa có CLO")
    try:
        suggestions = suggest_chapter_outline(clos, course.name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Gợi ý thất bại: {e}")
    return {"suggestions": suggestions}


# --------------------------- AI sinh giáo trình (SPEC 4.4) ---------------------------
class GenTextbookIn(BaseModel):
    title: str = ""
    num_chapters: int = 0
    with_content: bool = True  # sinh luôn nội dung từng chương hay chỉ dàn ý


class GenTextbookAsyncIn(GenTextbookIn):
    deep: bool = False          # chương dài 25–40 trang
    target_pages: int = 30


@router.post("/courses/{course_id}/textbooks/generate-async", status_code=202)
def generate_textbook_async(
    course_id: int, payload: GenTextbookAsyncIn,
    db: Session = Depends(get_db), user: User = Depends(LECTURER),
):
    """Đặt việc sinh CẢ giáo trình bằng AI chạy NỀN (tránh timeout với nhiều chương).

    Trả về job_id; frontend poll GET /api/jobs/{job_id} để xem tiến độ.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    if not _course_clos(db, course_id):
        raise HTTPException(400, "Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")
    from app.services.jobs import create_job, enqueue

    job = create_job(
        db, "generate_textbook",
        params={"course_id": course_id, "title": payload.title, "num_chapters": payload.num_chapters,
                "with_content": payload.with_content, "deep": payload.deep,
                "target_pages": payload.target_pages},
        user_id=user.id, program_id=course.program_id, course_id=course_id,
    )
    log_action(db, user.id, "job", job.id, "create", {"type": "generate_textbook"})
    enqueue(job.id)
    return {"job_id": job.id, "status": job.status}


@router.post("/courses/{course_id}/textbooks/generate")
def generate_textbook(
    course_id: int, payload: GenTextbookIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    """Sinh CẢ giáo trình bằng AI: tạo textbook + các chương (dàn ý, tùy chọn nội dung)."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    clos = _course_clos(db, course_id)
    if not clos:
        raise HTTPException(400, "Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")
    clo_by_code = {c.code: c for c in clos}
    clo_dicts = [{"code": c.code, "description": c.description} for c in clos]

    try:
        outline = generate_chapter_outline_ai(
            {"code": course.code, "name": course.name}, clo_dicts, payload.num_chapters
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Sinh giáo trình thất bại: {e}")

    tb = Textbook(course_id=course_id, title=payload.title or f"Giáo trình {course.name}", version=1, status="draft")
    db.add(tb)
    db.flush()

    for gc in outline.chapters:
        content = ""
        if payload.with_content:
            ch_clos = [{"code": code, "description": clo_by_code[code].description}
                       for code in gc.clo_codes if code in clo_by_code]
            try:
                content = generate_chapter_content_ai(
                    {"code": course.code, "name": course.name}, gc.title, ch_clos, gc.summary
                )
            except Exception:  # noqa: BLE001
                content = gc.summary or ""
        ch = Chapter(textbook_id=tb.id, order=gc.order, title=gc.title, content_richtext=content)
        db.add(ch)
        db.flush()
        for code in gc.clo_codes:
            if code in clo_by_code:
                db.add(ChapterClo(chapter_id=ch.id, clo_id=clo_by_code[code].id))

    db.commit()
    db.refresh(tb)
    log_action(db, user.id, "textbook", tb.id, "generate_ai", {"chapters": len(outline.chapters)})
    return {"textbook_id": tb.id, "chapters": len(outline.chapters)}


@router.post("/chapters/{cid}/generate-content", response_model=ChapterOut)
def generate_chapter_content(
    cid: int,
    deep: bool = False,
    target_pages: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Sinh/viết lại nội dung MỘT chương bằng AI (theo tiêu đề + CLO gắn của chương).

    deep=true: sinh chương DÀI (~25-40 trang) bằng cách viết từng mục rồi ghép —
    có thể mất vài phút (cần Cloud Run timeout cao). deep=false: bản nhanh ~10-12 trang.
    """
    ch = db.get(Chapter, cid)
    if not ch:
        raise HTTPException(404, "Không tìm thấy chương")
    tb = db.get(Textbook, ch.textbook_id)
    course = db.get(Course, tb.course_id) if tb else None
    clo_ids = [cc.clo_id for cc in db.query(ChapterClo).filter(ChapterClo.chapter_id == cid).all()]
    clos = db.query(Clo).filter(Clo.id.in_(clo_ids or [-1])).all()
    course_d = {"code": course.code if course else "", "name": course.name if course else ""}
    clo_d = [{"code": c.code, "description": c.description} for c in clos]
    try:
        if deep:
            content = generate_chapter_content_deep_ai(
                course_d, ch.title, clo_d, ch.content_richtext or "", target_pages=target_pages
            )
        else:
            content = generate_chapter_content_ai(course_d, ch.title, clo_d)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Sinh nội dung thất bại: {e}")
    ch.content_richtext = content
    db.commit()
    db.refresh(ch)
    log_action(db, user.id, "chapter", cid, "generate_content_ai")
    res = ChapterOut.model_validate(ch)
    res.clo_ids = clo_ids
    return res


def _chapter_course_clos(db: Session, cid: int):
    """Trả (chapter, course_dict, clo_dicts, clo_ids) cho một chương."""
    ch = db.get(Chapter, cid)
    if not ch:
        raise HTTPException(404, "Không tìm thấy chương")
    tb = db.get(Textbook, ch.textbook_id)
    course = db.get(Course, tb.course_id) if tb else None
    clo_ids = [cc.clo_id for cc in db.query(ChapterClo).filter(ChapterClo.chapter_id == cid).all()]
    clos = db.query(Clo).filter(Clo.id.in_(clo_ids or [-1])).all()
    course_d = {"code": course.code if course else "", "name": course.name if course else ""}
    clo_d = [{"code": c.code, "description": c.description} for c in clos]
    return ch, course_d, clo_d, clo_ids


@router.get("/chapters/{cid}/qa-review")
def chapter_qa_review(cid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI đánh giá chất lượng nội dung một chương giáo trình (độ phủ CLO, chiều sâu, cấu trúc)."""
    ch, course_d, clo_d, _ids = _chapter_course_clos(db, cid)
    if not (ch.content_richtext or "").strip():
        raise HTTPException(400, "Chương chưa có nội dung để đánh giá.")
    try:
        return review_chapter_ai(course_d, ch.title, clo_d, ch.content_richtext or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Đánh giá chương thất bại: {e}")


class ChapterImproveIn(BaseModel):
    qa: dict | None = None


@router.post("/chapters/{cid}/improve", response_model=ChapterOut)
def improve_chapter(
    cid: int,
    payload: ChapterImproveIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Nâng cấp nội dung chương bằng AI dựa trên kết quả đánh giá (cập nhật tại chỗ)."""
    ch, course_d, clo_d, clo_ids = _chapter_course_clos(db, cid)
    if not (ch.content_richtext or "").strip():
        raise HTTPException(400, "Chương chưa có nội dung để nâng cấp.")
    try:
        content = improve_chapter_ai(
            course_d, ch.title, clo_d, ch.content_richtext or "",
            payload.qa if payload else None,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Nâng cấp chương thất bại: {e}")
    if content:
        ch.content_richtext = content
    db.commit()
    db.refresh(ch)
    log_action(db, user.id, "chapter", cid, "improve_ai")
    res = ChapterOut.model_validate(ch)
    res.clo_ids = clo_ids
    return res


# --------------------------- Xuất file giáo trình ---------------------------
@router.get("/textbooks/{tid}/export")
def export_textbook(tid: int, format: str = "docx", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Xuất giáo trình ra DOCX hoặc PDF (SPEC 4.4)."""
    try:
        if format == "pdf":
            data = textbook_to_pdf(db, tid)
            media = "application/pdf"
            fname = f"giao_trinh_{tid}.pdf"
        else:
            data = textbook_to_docx(db, tid)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fname = f"giao_trinh_{tid}.docx"
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(
        iter([data]), media_type=media,
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
