from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.pagination import limit_param, offset_param, paginate
from app.database import get_db
from app.models import Exam, ExamMatrix, ExamQuestion, Question, Role, User
from app.schemas.exam import ExamGenerateIn, ExamOut
from app.services.audit import log_action
from app.services.exam_generation import generate_exam_pure
from app.services.exports import exam_to_docx

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
    # Chỉ lấy câu hỏi ĐÃ DUYỆT (review_status=approved) để sinh đề (SPEC ngân hàng đề thi).
    questions = [
        {
            "id": q.id, "clo_id": q.clo_id, "bloom_level": q.bloom_level,
            "difficulty": q.difficulty, "points": q.points,
        }
        for q in db.query(Question)
        .filter(
            Question.course_id == matrix.course_id,
            Question.is_deleted == False,  # noqa: E712
            Question.review_status == "approved",
        )
        .all()
    ]
    res = generate_exam_pure(matrix.cells_json, questions, seed=payload.seed)
    if not res.ok and not payload.allow_partial:
        # Lập thông báo tiếng Việt dễ đọc, dùng mã CLO thay vì id.
        from app.models import Clo

        clo_codes = {
            c.id: c.code
            for c in db.query(Clo).filter(Clo.id.in_([cell.get("clo_id") for cell in res.by_cell] or [-1])).all()
        }
        bloom_vi = {
            "remember": "Nhớ", "understand": "Hiểu", "apply": "Vận dụng",
            "analyze": "Phân tích", "evaluate": "Đánh giá", "create": "Sáng tạo",
        }
        diff_vi = {"easy": "Dễ", "medium": "Trung bình", "hard": "Khó"}
        missing = []
        for c in res.by_cell:
            if c["picked"] < c["required"]:
                code = clo_codes.get(c["clo_id"], f"CLO#{c['clo_id']}")
                missing.append(
                    f"• {code} · {bloom_vi.get(c['bloom_level'], c['bloom_level'])} · "
                    f"{diff_vi.get(c['difficulty'], c['difficulty'])}: cần {c['required']} câu, "
                    f"ngân hàng chỉ có {c['picked']} câu."
                )
        detail = (
            "Ngân hàng câu hỏi chưa đủ để sinh đề theo ma trận này:\n"
            + "\n".join(missing)
            + "\n\nKhắc phục: bổ sung câu hỏi cho các ô trên (có thể dùng \"Tạo câu hỏi bằng AI\" "
            "ở Ngân hàng câu hỏi), hoặc chọn \"Vẫn sinh đề với câu có sẵn\"."
        )
        raise HTTPException(400, detail)

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
def list_exams(
    course_id: int,
    response: Response,
    limit: int = limit_param(),
    offset: int = offset_param(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Liệt kê đề thi của học phần (phân trang; tổng số ở header X-Total-Count)."""
    query = db.query(Exam).filter(Exam.course_id == course_id).order_by(Exam.id.desc())
    return paginate(query, response, limit, offset)


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


@router.get("/exams/{exam_id}/mapping")
def exam_mapping(exam_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Bảng mapping câu hỏi–CLO–PLO/PI + tỷ trọng CLO/Bloom theo điểm (SPEC mục 14)."""
    from app.models import Clo, CloPlo, Pi, Plo

    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy đề thi")

    # Tỷ trọng theo điểm
    clo_pts: dict = {}
    bloom_pts: dict = {}
    total = 0.0
    rows = []
    clo_cache: dict = {}

    def clo_info(clo_id):
        if clo_id in clo_cache:
            return clo_cache[clo_id]
        clo = db.get(Clo, clo_id) if clo_id else None
        plo_codes = []
        if clo:
            for cp in db.query(CloPlo).filter(CloPlo.clo_id == clo.id).all():
                plo = db.get(Plo, cp.plo_id)
                if plo:
                    pis = db.query(Pi).filter(Pi.plo_id == plo.id).all()
                    plo_codes.append({"plo": plo.code, "pis": [p.code for p in pis]})
        info = {"code": clo.code if clo else "?", "plos": plo_codes}
        clo_cache[clo_id] = info
        return info

    for eq in (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id, ExamQuestion.variant == 1)
        .order_by(ExamQuestion.order)
        .all()
    ):
        q = db.get(Question, eq.question_id)
        if not q:
            continue
        info = clo_info(q.clo_id)
        clo_pts[info["code"]] = clo_pts.get(info["code"], 0.0) + q.points
        bloom_pts[q.bloom_level] = bloom_pts.get(q.bloom_level, 0.0) + q.points
        total += q.points
        rows.append({
            "order": eq.order, "clo": info["code"], "plos": info["plos"],
            "bloom_level": q.bloom_level, "points": q.points,
        })

    def pct(x):
        return round(x / total * 100, 1) if total else 0.0

    return {
        "exam_id": exam_id,
        "rows": rows,
        "clo_weight": {k: {"points": round(v, 2), "percent": pct(v)} for k, v in clo_pts.items()},
        "bloom_weight": {k: {"points": round(v, 2), "percent": pct(v)} for k, v in bloom_pts.items()},
    }


@router.get("/exams/{exam_id}/questions")
def list_exam_questions(exam_id: int, variant: int = 1, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Danh sách câu trong đề (1 mã đề) — phục vụ chỉnh tay (SPEC 4.6)."""
    if not db.get(Exam, exam_id):
        raise HTTPException(404, "Không tìm thấy đề thi")
    out = []
    for eq in (
        db.query(ExamQuestion)
        .filter(ExamQuestion.exam_id == exam_id, ExamQuestion.variant == variant)
        .order_by(ExamQuestion.order)
        .all()
    ):
        q = db.get(Question, eq.question_id)
        out.append({
            "exam_question_id": eq.id, "order": eq.order, "locked": eq.locked,
            "question_id": eq.question_id,
            "content": q.content if q else None, "clo_id": q.clo_id if q else None,
            "bloom_level": q.bloom_level if q else None, "difficulty": q.difficulty if q else None,
            "points": q.points if q else None,
        })
    return out


# Thứ tự nhóm loại câu hỏi khi sắp xếp cho in ấn (trắc nghiệm trước, tự luận sau).
_TYPE_ORDER = {
    "mcq_single": 1, "mcq_multi": 1, "fill_blank": 2,
    "short_answer": 3, "essay": 4, "exercise": 5,
}


@router.post("/exams/{exam_id}/arrange-for-print")
def arrange_for_print(exam_id: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Sắp xếp câu hỏi trong đề theo NHÓM CÙNG LOẠI (trắc nghiệm → điền khuyết → tự luận
    ngắn → tự luận → bài tập) cho thuận tiện in ấn. Áp cho mọi mã đề."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "Không tìm thấy đề thi")
    variants = sorted({eq.variant for eq in db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).all()})
    total = 0
    for v in variants:
        eqs = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == exam_id, ExamQuestion.variant == v
        ).all()
        # sắp theo (nhóm loại, thứ tự cũ) để giữ thứ tự tương đối trong cùng nhóm
        def sort_key(eq):
            q = db.get(Question, eq.question_id)
            return (_TYPE_ORDER.get(q.type, 9) if q else 9, eq.order)
        for new_order, eq in enumerate(sorted(eqs, key=sort_key), start=1):
            eq.order = new_order
            total += 1
    db.commit()
    log_action(db, user.id, "exam", exam_id, "arrange_for_print", {"variants": len(variants)})
    return {"ok": True, "variants": len(variants), "questions": total}


@router.post("/exam-questions/{eq_id}/lock", response_model=dict)
def toggle_lock(eq_id: int, locked: bool = True, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Khóa/mở khóa một câu trong đề (SPEC 4.6)."""
    eq = db.get(ExamQuestion, eq_id)
    if not eq:
        raise HTTPException(404, "Không tìm thấy câu trong đề")
    eq.locked = locked
    db.commit()
    log_action(db, user.id, "exam_question", eq_id, "lock", {"locked": locked})
    return {"exam_question_id": eq_id, "locked": locked}


@router.put("/exam-questions/{eq_id}/replace", response_model=dict)
def replace_question(eq_id: int, question_id: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Thay câu trong đề bằng câu khác (không thay nếu đang khóa) — SPEC 4.6."""
    eq = db.get(ExamQuestion, eq_id)
    if not eq:
        raise HTTPException(404, "Không tìm thấy câu trong đề")
    if eq.locked:
        raise HTTPException(400, "Câu đang bị khóa, không thể thay")
    new_q = db.get(Question, question_id)
    if not new_q:
        raise HTTPException(404, "Không tìm thấy câu hỏi thay thế")
    exam = db.get(Exam, eq.exam_id)
    old_q = db.get(Question, eq.question_id)
    eq.question_id = question_id
    # cập nhật tổng điểm
    if exam and old_q and new_q:
        exam.total_points = round(exam.total_points - old_q.points + new_q.points, 2)
    db.commit()
    log_action(db, user.id, "exam_question", eq_id, "replace", {"to": question_id})
    return {"exam_question_id": eq_id, "question_id": question_id}


@router.get("/exams/{exam_id}/export")
def export_exam(exam_id: int, variant: int = 1, answers: bool = False, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Xuất đề thi (kèm/không kèm đáp án) ra DOCX (SPEC 4.6)."""
    try:
        data = exam_to_docx(db, exam_id, variant=variant, with_answers=answers)
    except ValueError as e:
        raise HTTPException(404, str(e))
    suffix = "_dapan" if answers else ""
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=de_thi_{exam_id}_ma{variant}{suffix}.docx"},
    )


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
