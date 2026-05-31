import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Clo, Course, CourseOutline, ExamMatrix, Question, Role, User
from app.schemas.exam import (
    ExamMatrixCreate,
    ExamMatrixOut,
    MatrixCell,
    QuestionCreate,
    QuestionOut,
)
from app.schemas.question_gen import QuestionGenRequest
from app.services.audit import log_action
from app.services.question_ai import generate_questions_ai
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


def _latest_clos(db: Session, course_id: int) -> list[Clo]:
    """CLO của đề cương mới nhất của học phần."""
    outline = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    if not outline:
        return []
    return db.query(Clo).filter(Clo.outline_id == outline.id).all()


@router.post("/courses/{course_id}/questions/generate")
def generate_questions(
    course_id: int,
    payload: QuestionGenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Sinh ngân hàng câu hỏi bằng AI theo CLO + Bloom + độ khó (SPEC 4.5).

    Câu hỏi được ghi thẳng vào ngân hàng (có thể sửa/xóa sau). Mỗi câu gắn CLO + Bloom.
    """
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    course = db.get(Course, course_id)
    clos = _latest_clos(db, course_id)
    if not clos:
        raise HTTPException(400, "Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")

    # Lọc CLO theo yêu cầu (nếu có).
    if payload.clo_ids:
        clos = [c for c in clos if c.id in set(payload.clo_ids)]
        if not clos:
            raise HTTPException(400, "Không có CLO hợp lệ trong danh sách đã chọn.")
    clo_by_code = {c.code: c for c in clos}

    try:
        gen = generate_questions_ai(
            course={"code": course.code, "name": course.name},
            clos=[{"code": c.code, "description": c.description, "bloom_level": c.bloom_level or ""} for c in clos],
            num_per_clo=payload.num_per_clo,
            bloom_levels=payload.bloom_levels or None,
            difficulties=payload.difficulties or None,
            question_type=payload.question_type,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Sinh câu hỏi thất bại: {e}")

    created = 0
    for gq in gen.questions:
        clo = clo_by_code.get(gq.clo_code)
        db.add(
            Question(
                course_id=course_id,
                clo_id=clo.id if clo else (clos[0].id if clos else None),
                bloom_level=gq.bloom_level or "remember",
                difficulty=gq.difficulty or "medium",
                type=gq.type or payload.question_type,
                content=gq.content,
                options_json=gq.options or [],
                answer=gq.answer or None,
                points=gq.points or 1,
                explanation=gq.explanation or None,
                tags_json=["ai-generated"],
            )
        )
        created += 1
    db.commit()
    log_action(db, user.id, "question", None, "generate_ai", {"course_id": course_id, "count": created})
    return {"created": created}


@router.put("/questions/{qid}", response_model=QuestionOut)
def update_question(qid: int, payload: QuestionCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Question, qid)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "question", qid, "update")
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


@router.get("/courses/{course_id}/questions/export-xlsx")
def export_xlsx(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Xuất ngân hàng câu hỏi ra Excel (SPEC 4.5)."""
    from openpyxl import Workbook

    qs = db.query(Question).filter(Question.course_id == course_id, Question.is_deleted == False).all()  # noqa: E712
    wb = Workbook()
    ws = wb.active
    ws.title = "Questions"
    ws.append(["id", "clo_id", "bloom_level", "difficulty", "type", "content", "answer", "points", "explanation"])
    for q in qs:
        ws.append([q.id, q.clo_id, q.bloom_level, q.difficulty, q.type, q.content, q.answer, q.points, q.explanation])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=questions_{course_id}.xlsx"},
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
