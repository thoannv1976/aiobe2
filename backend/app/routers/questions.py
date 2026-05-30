import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Course, ExamMatrix, Question, Role, User
from app.schemas.exam import (
    ExamMatrixCreate,
    ExamMatrixOut,
    MatrixCell,
    QuestionCreate,
    QuestionOut,
)
from app.services.audit import log_action
from app.services.reports import question_bank_stats

router = APIRouter(prefix="/api", tags=["questions"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


@router.get("/courses/{course_id}/questions", response_model=list[QuestionOut])
def list_questions(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (
        db.query(Question)
        .filter(Question.course_id == course_id, Question.is_deleted == False)  # noqa: E712
        .all()
    )


@router.post("/courses/{course_id}/questions", response_model=QuestionOut, status_code=201)
def create_question(
    course_id: int, payload: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = Question(course_id=course_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "question", obj.id, "create")
    return obj


@router.delete("/questions/{qid}", status_code=204)
def delete_question(qid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Question, qid)
    if obj:
        obj.is_deleted = True
        db.commit()
        log_action(db, user.id, "question", qid, "soft_delete")


@router.get("/courses/{course_id}/questions/stats")
def stats(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Thống kê ngân hàng theo CLO/Bloom/độ khó (SPEC 4.5)."""
    return question_bank_stats(db, course_id)


# --------------------------- Import / Export CSV ---------------------------
@router.get("/courses/{course_id}/questions/export")
def export_csv(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    qs = db.query(Question).filter(Question.course_id == course_id, Question.is_deleted == False).all()  # noqa: E712
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["clo_id", "bloom_level", "difficulty", "type", "content", "answer", "points"])
    for q in qs:
        w.writerow([q.clo_id, q.bloom_level, q.difficulty, q.type, q.content, q.answer, q.points])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=questions_{course_id}.csv"},
    )


@router.post("/courses/{course_id}/questions/import")
async def import_csv(
    course_id: int, file: UploadFile, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    count = 0
    for row in reader:
        db.add(
            Question(
                course_id=course_id,
                clo_id=int(row["clo_id"]) if row.get("clo_id") else None,
                bloom_level=row.get("bloom_level", "remember"),
                difficulty=row.get("difficulty", "medium"),
                type=row.get("type", "mcq_single"),
                content=row.get("content", ""),
                answer=row.get("answer"),
                points=float(row.get("points") or 1),
            )
        )
        count += 1
    db.commit()
    log_action(db, user.id, "question", None, "import", {"count": count})
    return {"imported": count}


# --------------------------- Exam matrices ---------------------------
@router.get("/courses/{course_id}/matrices", response_model=list[ExamMatrixOut])
def list_matrices(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for m in db.query(ExamMatrix).filter(ExamMatrix.course_id == course_id).all():
        out.append(ExamMatrixOut(id=m.id, course_id=m.course_id, name=m.name, cells=m.cells_json))
    return out


@router.post("/courses/{course_id}/matrices", response_model=ExamMatrixOut, status_code=201)
def create_matrix(
    course_id: int, payload: ExamMatrixCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = ExamMatrix(
        course_id=course_id, name=payload.name,
        cells_json=[c.model_dump() for c in payload.cells],
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "exam_matrix", obj.id, "create")
    return ExamMatrixOut(id=obj.id, course_id=course_id, name=obj.name, cells=obj.cells_json)
