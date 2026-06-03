"""Module viết bài giảng (SPEC mục 10): CRUD + AI sinh bài giảng + xuất DOCX/PPTX."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import (
    Chapter,
    ChapterClo,
    Clo,
    Course,
    CourseOutline,
    Lecture,
    Role,
    Textbook,
    User,
)
from app.services.audit import log_action
from app.services.exports import lecture_to_docx, lecture_to_pptx
from app.services.lecture_ai import generate_lecture_ai, improve_lecture_ai, review_lecture_ai

router = APIRouter(prefix="/api", tags=["lectures"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


class LectureIn(BaseModel):
    session_no: int = 1
    title: str
    content_richtext: str | None = None
    slides_json: list = []
    clo_codes_json: list = []


class LectureGenIn(BaseModel):
    session_no: int = 1
    title: str
    clo_codes: list[str] = []


def _latest_clos(db: Session, course_id: int) -> list[Clo]:
    outline = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    return db.query(Clo).filter(Clo.outline_id == outline.id).all() if outline else []


def _material_for_clos(db: Session, course_id: int, clo_codes: list[str]) -> str:
    """Gom nội dung chương giáo trình gắn các CLO này (ngữ liệu cho bài giảng)."""
    clos = [c for c in _latest_clos(db, course_id) if c.code in set(clo_codes)]
    if not clos:
        return ""
    tb_ids = [t.id for t in db.query(Textbook).filter(Textbook.course_id == course_id).all()]
    if not tb_ids:
        return ""
    clo_ids = {c.id for c in clos}
    parts = []
    rows = (
        db.query(ChapterClo, Chapter)
        .join(Chapter, Chapter.id == ChapterClo.chapter_id)
        .filter(ChapterClo.clo_id.in_(clo_ids), Chapter.textbook_id.in_(tb_ids))
        .order_by(Chapter.order)
        .all()
    )
    for _cc, ch in rows:
        if ch.content_richtext:
            parts.append(f"### {ch.title}\n{ch.content_richtext}")
    return "\n\n".join(parts)[:15000]


@router.get("/courses/{course_id}/lectures")
def list_lectures(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(Lecture).filter(Lecture.course_id == course_id).order_by(Lecture.session_no).all()
    )
    return [
        {"id": l.id, "session_no": l.session_no, "title": l.title,
         "clo_codes": l.clo_codes_json, "has_content": bool((l.content_richtext or "").strip()),
         "slides_count": len(l.slides_json or [])}
        for l in rows
    ]


@router.get("/lectures/{lid}")
def get_lecture(lid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    l = db.get(Lecture, lid)
    if not l:
        raise HTTPException(404, "Không tìm thấy bài giảng")
    return {
        "id": l.id, "course_id": l.course_id, "session_no": l.session_no, "title": l.title,
        "content_richtext": l.content_richtext, "slides_json": l.slides_json,
        "clo_codes": l.clo_codes_json,
    }


@router.post("/courses/{course_id}/lectures", status_code=201)
def create_lecture(course_id: int, payload: LectureIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = Lecture(
        course_id=course_id, session_no=payload.session_no, title=payload.title,
        content_richtext=payload.content_richtext, slides_json=payload.slides_json,
        clo_codes_json=payload.clo_codes_json,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "lecture", obj.id, "create")
    return {"id": obj.id}


@router.patch("/lectures/{lid}")
def update_lecture(lid: int, payload: LectureIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    l = db.get(Lecture, lid)
    if not l:
        raise HTTPException(404, "Không tìm thấy bài giảng")
    l.session_no = payload.session_no
    l.title = payload.title
    l.content_richtext = payload.content_richtext
    l.slides_json = payload.slides_json
    l.clo_codes_json = payload.clo_codes_json
    db.commit()
    log_action(db, user.id, "lecture", lid, "update")
    return {"id": lid}


@router.delete("/lectures/{lid}", status_code=204)
def delete_lecture(lid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    l = db.get(Lecture, lid)
    if l:
        db.delete(l)
        db.commit()
        log_action(db, user.id, "lecture", lid, "delete")


@router.post("/courses/{course_id}/lectures/generate", status_code=201)
def generate_lecture(course_id: int, payload: LectureGenIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """AI soạn bài giảng cho một buổi, bám CLO + giáo trình (SPEC mục 10)."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    clos = [c for c in _latest_clos(db, course_id) if not payload.clo_codes or c.code in set(payload.clo_codes)]
    material = _material_for_clos(db, course_id, payload.clo_codes or [c.code for c in clos])
    try:
        gen = generate_lecture_ai(
            {"code": course.code, "name": course.name},
            payload.title,
            [{"code": c.code, "description": c.description} for c in clos],
            material,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Soạn bài giảng thất bại: {e}")
    obj = Lecture(
        course_id=course_id, session_no=payload.session_no, title=payload.title,
        content_richtext=gen["content_markdown"], slides_json=gen["slides"],
        clo_codes_json=payload.clo_codes or [c.code for c in clos],
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "lecture", obj.id, "generate_ai")
    return {"id": obj.id, "slides": len(gen["slides"])}


def _lecture_clos(db: Session, l: Lecture) -> list[dict]:
    """CLO dicts cho bài giảng (theo clo_codes_json + đề cương mới nhất)."""
    codes = set(l.clo_codes_json or [])
    clos = [c for c in _latest_clos(db, l.course_id) if not codes or c.code in codes]
    return [{"code": c.code, "description": c.description} for c in clos]


@router.get("/lectures/{lid}/qa-review")
def lecture_qa_review(lid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI đánh giá chất lượng bài giảng (mục tiêu gắn CLO, cấu trúc sư phạm, slide)."""
    l = db.get(Lecture, lid)
    if not l:
        raise HTTPException(404, "Không tìm thấy bài giảng")
    if not (l.content_richtext or "").strip():
        raise HTTPException(400, "Bài giảng chưa có nội dung để đánh giá.")
    course = db.get(Course, l.course_id)
    try:
        return review_lecture_ai(
            {"code": course.code if course else "", "name": course.name if course else ""},
            l.title, _lecture_clos(db, l), l.content_richtext or "", len(l.slides_json or []),
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Đánh giá bài giảng thất bại: {e}")


class LectureImproveIn(BaseModel):
    qa: dict | None = None


@router.post("/lectures/{lid}/improve")
def improve_lecture(
    lid: int,
    payload: LectureImproveIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Nâng cấp bài giảng bằng AI dựa trên kết quả đánh giá (cập nhật nội dung + slide tại chỗ)."""
    l = db.get(Lecture, lid)
    if not l:
        raise HTTPException(404, "Không tìm thấy bài giảng")
    if not (l.content_richtext or "").strip():
        raise HTTPException(400, "Bài giảng chưa có nội dung để nâng cấp.")
    course = db.get(Course, l.course_id)
    try:
        gen = improve_lecture_ai(
            {"code": course.code if course else "", "name": course.name if course else ""},
            l.title, _lecture_clos(db, l), l.content_richtext or "",
            l.slides_json or [], payload.qa if payload else None,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Nâng cấp bài giảng thất bại: {e}")
    if gen["content_markdown"]:
        l.content_richtext = gen["content_markdown"]
    if gen["slides"]:
        l.slides_json = gen["slides"]
    db.commit()
    log_action(db, user.id, "lecture", lid, "improve_ai")
    return {"id": lid, "slides": len(l.slides_json or [])}


@router.get("/lectures/{lid}/export")
def export_lecture(lid: int, format: str = "docx", db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Xuất bài giảng: docx (nội dung) hoặc pptx (slide) — SPEC mục 21."""
    try:
        if format == "pptx":
            data = lecture_to_pptx(db, lid)
            media = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            fname = f"bai_giang_{lid}.pptx"
        else:
            data = lecture_to_docx(db, lid)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            fname = f"bai_giang_{lid}.docx"
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(
        iter([data]), media_type=media,
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
