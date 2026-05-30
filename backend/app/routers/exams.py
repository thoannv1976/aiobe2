from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Exam, ExamMatrix, ExamQuestion, Question, Role, User
from app.schemas.exam import ExamGenerateIn, ExamOut
from app.services.audit import log_action
from app.services.exam_generation import generate_exam_pure

router = APIRouter(prefix="/api", tags=["exams"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)

EXAM_TRANSITIONS = {
    "draft": {"reviewed"},
    "reviewed": {"approved", "draft"},
    "approved": {"published", "draft"},
    "published": set(),
}


@router.post("/exams/generate", response_model=ExamOut, status_code=201)
def generate(payload: ExamGenerateIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Sinh đề thi tự động từ ma trận (SPEC 4.6)."""
    matrix = db.get(ExamMatrix, payload.matrix_id)
    if not matrix:
        raise HTTPException(404, "Không tìm thấy ma trận đề")
    questions = [
        {
            "id": q.id, "clo_id": q.clo_id, "bloom_level": q.bloom_level,
            "difficulty": q.difficulty, "points": q.points,
        }
        for q in db.query(Question)
        .filter(Question.course_id == matrix.course_id, Question.is_deleted == False)  # noqa: E712
        .all()
    ]
    res = generate_exam_pure(matrix.cells_json, questions, seed=payload.seed)
    if not res.ok:
        raise HTTPException(400, {"message": "Không sinh đủ đề", "errors": res.errors, "by_cell": res.by_cell})

    exam = Exam(
        course_id=matrix.course_id, matrix_id=matrix.id, name=payload.name,
        status="draft", total_points=res.total_points,
        duration_min=payload.duration_min, variant_count=payload.variant_count,
    )
    db.add(exam)
    db.flush()
    for variant in range(1, payload.variant_count + 1):
        for order, qid in enumerate(res.picked_ids, start=1):
            db.add(ExamQuestion(exam_id=exam.id, question_id=qid, order=order, variant=variant))
    db.commit()
    db.refresh(exam)
    log_action(db, user.id, "exam", exam.id, "generate", {"matrix_id": matrix.id})
    return exam


@router.get("/courses/{course_id}/exams", response_model=list[ExamOut])
def list_exams(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Exam).filter(Exam.course_id == course_id).all()


@router.get("/exams/{exam_id}/blueprint")
def blueprint(exam_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Bảng đặc tả đề thi (test blueprint) + đáp án/barem — minh chứng (SPEC 4.6)."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy đề thi")
    items = []
    clo_dist: dict = {}
    bloom_dist: dict = {}
    for eq in db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id, ExamQuestion.variant == 1).order_by(ExamQuestion.order).all():
        q = db.get(Question, eq.question_id)
        if not q:
            continue
        clo_dist[q.clo_id] = clo_dist.get(q.clo_id, 0) + 1
        bloom_dist[q.bloom_level] = bloom_dist.get(q.bloom_level, 0) + 1
        items.append({
            "order": eq.order, "question_id": q.id, "clo_id": q.clo_id,
            "bloom_level": q.bloom_level, "difficulty": q.difficulty,
            "points": q.points, "answer": q.answer,
        })
    return {
        "exam_id": exam_id, "total_points": exam.total_points,
        "items": items, "clo_distribution": clo_dist, "bloom_distribution": bloom_dist,
    }


@router.post("/exams/{exam_id}/status", response_model=ExamOut)
def change_status(exam_id: int, to: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy đề thi")
    if to not in EXAM_TRANSITIONS.get(exam.status, set()):
        raise HTTPException(400, f"Không thể chuyển {exam.status} → {to}")
    if to == "approved" and user.role not in (Role.PROGRAM_MANAGER.value, Role.ADMIN.value):
        raise HTTPException(403, "Chỉ quản lý mới được duyệt đề")
    prev = exam.status
    exam.status = to
    db.commit()
    db.refresh(exam)
    log_action(db, user.id, "exam", exam_id, "status", {"from": prev, "to": to})
    return exam
