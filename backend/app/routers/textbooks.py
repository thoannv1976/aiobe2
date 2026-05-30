from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Chapter, ChapterClo, Course, Role, Textbook, User
from app.schemas.content import ChapterCreate, ChapterOut, TextbookCreate, TextbookOut
from app.services.audit import log_action

router = APIRouter(prefix="/api", tags=["textbooks"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


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
