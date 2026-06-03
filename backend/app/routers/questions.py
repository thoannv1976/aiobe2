import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
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
    ExamMatrix,
    Question,
    Role,
    Textbook,
    User,
)
from app.schemas.exam import (
    ExamMatrixCreate,
    ExamMatrixOut,
    MatrixCell,
    QuestionCreate,
    QuestionOut,
)
from app.schemas.question_gen import QuestionGenRequest
from app.services.audit import log_action
from app.services.question_ai import generate_questions_ai, improve_questions_ai
from app.services.reports import question_bank_stats

router = APIRouter(prefix="/api", tags=["questions"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


@router.get("/courses/{course_id}/questions", response_model=list[QuestionOut])
def list_questions(
    course_id: int,
    clo_id: int | None = None,
    bloom_level: str | None = None,
    difficulty: str | None = None,
    type: str | None = None,
    review_status: str | None = None,
    q: str | None = None,  # tìm theo nội dung
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Liệt kê câu hỏi, hỗ trợ lọc theo CLO/Bloom/độ khó/dạng/trạng thái + tìm nội dung."""
    query = db.query(Question).filter(
        Question.course_id == course_id, Question.is_deleted == False  # noqa: E712
    )
    if clo_id is not None:
        query = query.filter(Question.clo_id == clo_id)
    if bloom_level:
        query = query.filter(Question.bloom_level == bloom_level)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if type:
        query = query.filter(Question.type == type)
    if review_status:
        query = query.filter(Question.review_status == review_status)
    if q:
        query = query.filter(Question.content.ilike(f"%{q}%"))
    return query.all()


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


# Giới hạn ký tự nội dung giáo trình gom cho mỗi CLO (an toàn độ dài prompt).
_MAX_MATERIAL_PER_CLO = 12000


def _gather_clo_materials(db: Session, course_id: int, clos: list[Clo]) -> dict[str, str]:
    """Gom nội dung các chương giáo trình gắn với từng CLO -> {clo_code: text}.

    Tìm qua bảng nối chapter_clo (Chapter n—n CLO) trên các giáo trình của học phần.
    """
    clo_ids = [c.id for c in clos]
    if not clo_ids:
        return {}
    tb_ids = [t.id for t in db.query(Textbook).filter(Textbook.course_id == course_id).all()]
    if not tb_ids:
        return {}
    id_to_code = {c.id: c.code for c in clos}
    by_code: dict[str, list[str]] = {c.code: [] for c in clos}

    rows = (
        db.query(ChapterClo, Chapter)
        .join(Chapter, Chapter.id == ChapterClo.chapter_id)
        .filter(ChapterClo.clo_id.in_(clo_ids), Chapter.textbook_id.in_(tb_ids))
        .order_by(Chapter.order)
        .all()
    )
    for cc, ch in rows:
        code = id_to_code.get(cc.clo_id)
        content = (ch.content_richtext or "").strip()
        if code and content:
            by_code[code].append(f"### Chương: {ch.title}\n{content}")

    out: dict[str, str] = {}
    for code, parts in by_code.items():
        if parts:
            out[code] = "\n\n".join(parts)[:_MAX_MATERIAL_PER_CLO]
    return out


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

    # Gom nội dung các chương giáo trình gắn với mỗi CLO làm ngữ liệu ra đề (SPEC 4.4/4.5).
    clo_materials = _gather_clo_materials(db, course_id, clos)

    try:
        gen = generate_questions_ai(
            course={"code": course.code, "name": course.name},
            clos=[{"code": c.code, "description": c.description, "bloom_level": c.bloom_level or ""} for c in clos],
            num_per_clo=payload.num_per_clo,
            bloom_levels=payload.bloom_levels or None,
            difficulties=payload.difficulties or None,
            question_type=payload.question_type,
            clo_materials=clo_materials,
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
                learning_resource=gq.source or None,  # nguồn chương/bài giảng
                rubric_json={"criteria": [c.model_dump() for c in gq.rubric]} if gq.rubric else {},
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


@router.post("/questions/{qid}/duplicate", response_model=QuestionOut, status_code=201)
def duplicate_question(qid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    src = db.get(Question, qid)
    if not src or src.is_deleted:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    dup = Question(
        course_id=src.course_id, clo_id=src.clo_id, bloom_level=src.bloom_level,
        difficulty=src.difficulty, type=src.type, content=f"{src.content} (bản sao)",
        options_json=list(src.options_json or []), answer=src.answer, points=src.points,
        explanation=src.explanation, tags_json=list(src.tags_json or []),
        chapter=src.chapter, learning_resource=src.learning_resource,
        review_status="draft",
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    log_action(db, user.id, "question", dup.id, "duplicate", {"from": qid})
    return dup


# Quy trình thẩm định câu hỏi (SPEC ngân hàng đề thi)
QUESTION_REVIEW_FLOW = {
    "draft": {"review"},
    "review": {"approved", "revise"},
    "revise": {"review", "draft"},
    "approved": {"retired", "revise"},
    "retired": {"draft"},
}


def _approve_reason(q: Question) -> str | None:
    """Trả lý do KHÔNG thể duyệt câu hỏi, hoặc None nếu hợp lệ (SPEC validation)."""
    if q.type in ("mcq_single", "mcq_multi") and not (q.answer or "").strip():
        return "Câu trắc nghiệm thiếu đáp án đúng"
    if q.type in ("essay", "exercise", "short_answer") and not (q.answer or "").strip():
        return "Câu tự luận/bài tập thiếu đáp án/thang điểm"
    # Tự luận/bài tập cần rubric chấm (SPEC ngân hàng đề thi).
    if q.type in ("essay", "exercise") and not ((q.rubric_json or {}).get("criteria")):
        return "Câu tự luận/bài tập thiếu rubric chấm điểm"
    return None


@router.post("/questions/{qid}/review", response_model=QuestionOut)
def review_question(
    qid: int, to: str, note: str | None = None,
    db: Session = Depends(get_db), user: User = Depends(LECTURER),
):
    """Chuyển trạng thái thẩm định câu hỏi: draft→review→approved/revise→retired."""
    obj = db.get(Question, qid)
    if not obj or obj.is_deleted:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    if to not in QUESTION_REVIEW_FLOW.get(obj.review_status, set()):
        raise HTTPException(400, f"Không thể chuyển {obj.review_status} → {to}")
    if to == "approved":
        if user.role not in (Role.PROGRAM_MANAGER.value, Role.ADMIN.value):
            raise HTTPException(403, "Chỉ quản lý/trưởng bộ môn mới được duyệt câu hỏi")
        reason = _approve_reason(obj)
        if reason:
            raise HTTPException(400, f"{reason} — không thể duyệt")
        obj.reviewed_by = user.id
    prev = obj.review_status
    obj.review_status = to
    if note is not None:
        obj.review_note = note
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "question", qid, "review", {"from": prev, "to": to})
    return obj


@router.post("/courses/{course_id}/questions/approve-all")
def approve_all_questions(
    course_id: int,
    only_ai: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Duyệt HÀNG LOẠT câu hỏi chưa duyệt của học phần (SPEC ngân hàng đề thi).

    Đưa thẳng các câu draft/review/revise lên 'approved'. Bỏ qua câu không hợp lệ
    (thiếu đáp án...) và trả về danh sách bỏ qua. only_ai=true: chỉ duyệt câu do AI tạo
    (tag 'ai-generated').
    """
    if user.role not in (Role.PROGRAM_MANAGER.value, Role.ADMIN.value):
        raise HTTPException(403, "Chỉ quản lý/trưởng bộ môn mới được duyệt câu hỏi")
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")

    candidates = (
        db.query(Question)
        .filter(
            Question.course_id == course_id,
            Question.is_deleted == False,  # noqa: E712
            Question.review_status.in_(["draft", "review", "revise"]),
        )
        .all()
    )
    approved = 0
    skipped: list[dict] = []
    for q in candidates:
        if only_ai and "ai-generated" not in (q.tags_json or []):
            continue
        reason = _approve_reason(q)
        if reason:
            skipped.append({"id": q.id, "reason": reason})
            continue
        q.review_status = "approved"
        q.reviewed_by = user.id
        approved += 1
    db.commit()
    log_action(db, user.id, "question", None, "approve_all", {"course_id": course_id, "approved": approved})
    return {"approved": approved, "skipped": skipped, "skipped_count": len(skipped)}


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


def _question_clo_codes(db: Session, course_id: int) -> dict[int, str]:
    """Map clo_id -> code cho mọi CLO mà câu hỏi của học phần đang tham chiếu."""
    qids = [q.clo_id for q in db.query(Question.clo_id).filter(
        Question.course_id == course_id, Question.is_deleted == False  # noqa: E712
    ).all() if q.clo_id is not None]
    if not qids:
        return {}
    return {c.id: c.code for c in db.query(Clo).filter(Clo.id.in_(set(qids))).all()}


def _question_payload(q: Question, code_by_id: dict[int, str]) -> dict:
    return {
        "id": q.id, "clo_code": code_by_id.get(q.clo_id, f"CLO#{q.clo_id}"),
        "bloom_level": q.bloom_level or "", "difficulty": q.difficulty or "",
        "type": q.type or "", "content": q.content or "",
        "options": list(q.options_json or []), "answer": q.answer or "",
        "explanation": q.explanation or "",
        "has_rubric": bool((q.rubric_json or {}).get("criteria")),
    }


@router.get("/courses/{course_id}/questions/qa-review")
def questions_qa_review(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI đánh giá chất lượng ngân hàng câu hỏi: gắn CLO/Bloom, đáp án, rubric, độ phủ (SPEC 4.5)."""
    from app.services.qa_review import review_questions_ai

    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    qs = db.query(Question).filter(
        Question.course_id == course_id, Question.is_deleted == False  # noqa: E712
    ).all()
    if not qs:
        raise HTTPException(400, "Ngân hàng câu hỏi đang trống — chưa có câu để đánh giá.")
    code_by_id = _question_clo_codes(db, course_id)
    try:
        return review_questions_ai(
            {"code": course.code, "name": course.name},
            [_question_payload(q, code_by_id) for q in qs],
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Đánh giá ngân hàng câu hỏi thất bại: {e}")


class QuestionsImproveIn(BaseModel):
    """Tham số nâng cấp câu hỏi bằng AI.

    qa: kết quả đánh giá đã chạy (nếu trống, backend tự chạy đánh giá trước).
    ids: giới hạn câu cần nâng cấp; nếu trống, nâng cấp các câu bị gắn lỗi/cảnh báo (chưa duyệt).
    """
    qa: dict | None = None
    ids: list[int] = []


# Tối đa số câu nâng cấp trong một lần (an toàn độ dài prompt).
_MAX_IMPROVE = 40


@router.post("/courses/{course_id}/questions/improve")
def improve_questions(
    course_id: int,
    payload: QuestionsImproveIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Nâng cấp câu hỏi bằng AI dựa trên kết quả đánh giá chất lượng (SPEC 4.5).

    Viết lại các câu CHƯA DUYỆT có vấn đề (sửa Bloom sai, bổ sung đáp án/phương án/rubric/giải thích),
    cập nhật tại chỗ và đặt lại trạng thái 'draft' để thẩm định lại. Câu Đã duyệt KHÔNG bị thay đổi.
    """
    from app.services.qa_review import review_questions_ai

    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    payload = payload or QuestionsImproveIn()
    # Chỉ nâng cấp câu chưa duyệt (không đụng câu Đã duyệt/đang dùng).
    candidates = db.query(Question).filter(
        Question.course_id == course_id, Question.is_deleted == False,  # noqa: E712
        Question.review_status != "approved",
    ).all()
    if not candidates:
        raise HTTPException(400, "Không có câu chưa duyệt nào để nâng cấp (câu Đã duyệt không bị thay đổi).")
    by_id = {q.id: q for q in candidates}
    code_by_id = _question_clo_codes(db, course_id)

    qa = payload.qa
    if not qa and not payload.ids:
        # Tự đánh giá để biết câu nào có vấn đề.
        try:
            qa = review_questions_ai(
                {"code": course.code, "name": course.name},
                [_question_payload(q, code_by_id) for q in candidates],
            )
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Đánh giá trước khi nâng cấp thất bại: {e}")

    # Xác định danh sách câu cần nâng cấp.
    if payload.ids:
        target_ids = [i for i in payload.ids if i in by_id]
    else:
        target_ids = [int(r["id"]) for r in (qa or {}).get("question_reviews", [])
                      if r.get("id") is not None and int(r["id"]) in by_id]
    target_ids = target_ids[:_MAX_IMPROVE]
    if not target_ids:
        raise HTTPException(400, "Không có câu chưa duyệt nào bị gắn vấn đề để nâng cấp.")

    targets = [by_id[i] for i in target_ids]
    try:
        improved = improve_questions_ai(
            {"code": course.code, "name": course.name},
            [_question_payload(q, code_by_id) for q in targets],
            qa,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Nâng cấp câu hỏi thất bại: {e}")

    updated: list[int] = []
    for iq in improved.questions:
        q = by_id.get(iq.id)
        if not q:
            continue
        if iq.content:
            q.content = iq.content
        q.options_json = iq.options or []
        if iq.answer:
            q.answer = iq.answer
        if iq.explanation:
            q.explanation = iq.explanation
        if iq.bloom_level:
            q.bloom_level = iq.bloom_level
        if iq.difficulty:
            q.difficulty = iq.difficulty
        if iq.type:
            q.type = iq.type
        if iq.rubric:
            q.rubric_json = {"criteria": [c.model_dump() for c in iq.rubric]}
        q.review_status = "draft"  # nội dung đổi → cần thẩm định lại
        tags = list(q.tags_json or [])
        if "ai-improved" not in tags:
            tags.append("ai-improved")
        q.tags_json = tags
        updated.append(q.id)
    db.commit()
    log_action(db, user.id, "question", None, "improve_ai",
               {"course_id": course_id, "count": len(updated), "ids": updated})
    return {"improved": len(updated), "ids": updated}


@router.get("/matrices/{mid}/coverage")
def matrix_bank_coverage(mid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Độ phủ ngân hàng theo từng ô ma trận: số câu Approved sẵn có vs cần lấy (SPEC mục 12).

    Cảnh báo nếu nhóm có câu Approved < 3 lần số câu cần (an toàn để random).
    """
    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    # Đếm câu Approved theo tổ hợp (clo_id, bloom, difficulty)
    avail: dict[tuple, int] = {}
    for q in db.query(Question).filter(
        Question.course_id == m.course_id, Question.is_deleted == False,  # noqa: E712
        Question.review_status == "approved",
    ).all():
        key = (q.clo_id, q.bloom_level, q.difficulty)
        avail[key] = avail.get(key, 0) + 1
    clo_codes = {c.id: c.code for c in db.query(Clo).all()}

    rows = []
    ok = True
    for cell in m.cells_json:
        need = int(cell.get("count", 0) or 0)
        key = (cell.get("clo_id"), cell.get("bloom_level"), cell.get("difficulty"))
        have = avail.get(key, 0)
        status = "ok"
        if have < need:
            status = "thiếu"
            ok = False
        elif have < need * 3:
            status = "ít"  # cảnh báo: dưới 3× số cần
        rows.append({
            "clo": clo_codes.get(cell.get("clo_id"), f"CLO#{cell.get('clo_id')}"),
            "bloom_level": cell.get("bloom_level"), "difficulty": cell.get("difficulty"),
            "need": need, "have_approved": have, "status": status,
        })
    return {"matrix_id": mid, "matrix_name": m.name, "ok": ok, "rows": rows}


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
MATRIX_TRANSITIONS = {
    "draft": {"review"},
    "review": {"approved", "draft"},
    "approved": {"archived", "draft"},
    "archived": set(),
}


def _matrix_out(m: ExamMatrix) -> ExamMatrixOut:
    return ExamMatrixOut(
        id=m.id, course_id=m.course_id, name=m.name, cells=m.cells_json,
        status=m.status, total_points=m.total_points, assessment_id=m.assessment_id,
    )


def _assessment_clo_ids(db: Session, assessment_id: int) -> set[int]:
    """CLO id mà một cấu phần đánh giá phụ trách (constructive alignment)."""
    from app.models import AssessmentClo

    return {
        ac.clo_id
        for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == assessment_id).all()
    }


@router.get("/courses/{course_id}/matrices", response_model=list[ExamMatrixOut])
def list_matrices(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_matrix_out(m) for m in db.query(ExamMatrix).filter(ExamMatrix.course_id == course_id).all()]


@router.post("/courses/{course_id}/matrices", response_model=ExamMatrixOut, status_code=201)
def create_matrix(
    course_id: int, payload: ExamMatrixCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(Course, course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = ExamMatrix(
        course_id=course_id, name=payload.name,
        cells_json=[c.model_dump() for c in payload.cells],
        total_points=payload.total_points, created_by=user.id,
        assessment_id=payload.assessment_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "exam_matrix", obj.id, "create")
    return _matrix_out(obj)


@router.get("/matrices/{mid}/summary")
def matrix_summary_endpoint(mid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Tỷ trọng CLO/Bloom + cảnh báo của ma trận."""
    from app.services.matrix_summary import matrix_summary

    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    res = matrix_summary(m.cells_json, m.total_points)

    # Kiểm tra liên kết với cấu phần đánh giá của đề cương (constructive alignment).
    if m.assessment_id:
        from app.models import Assessment, Clo

        a = db.get(Assessment, m.assessment_id)
        if a:
            res["assessment_name"] = a.name
            res["assessment_weight"] = a.weight_percent
            target_clos = _assessment_clo_ids(db, m.assessment_id)
            target_codes = {c.code for c in db.query(Clo).filter(Clo.id.in_(target_clos or [-1])).all()}
            matrix_clo_ids = {c.get("clo_id") for c in m.cells_json if c.get("clo_id")}
            matrix_codes = {c.code for c in db.query(Clo).filter(Clo.id.in_(matrix_clo_ids or [-1])).all()}
            # CLO mà cấu phần cần đo nhưng ma trận chưa có
            missing = target_codes - matrix_codes
            # CLO ma trận đo nhưng không thuộc cấu phần
            extra = matrix_codes - target_codes
            if missing:
                res.setdefault("warnings", []).append(
                    f"Cấu phần \"{a.name}\" đánh giá CLO {', '.join(sorted(missing))} nhưng ma trận chưa có."
                )
            if extra:
                res.setdefault("warnings", []).append(
                    f"Ma trận đo CLO {', '.join(sorted(extra))} không nằm trong cấu phần \"{a.name}\"."
                )
    return res


def _matrix_review_payload(db: Session, m: ExamMatrix) -> dict:
    """Gom dữ liệu ma trận (ô + ngân hàng Đã duyệt + cấu phần đánh giá) để AI đánh giá/tối ưu."""
    course = db.get(Course, m.course_id)
    clo_ids = {c.get("clo_id") for c in m.cells_json if c.get("clo_id")}
    code_by_id = {c.id: c.code for c in db.query(Clo).filter(Clo.id.in_(clo_ids or [-1])).all()}
    # Ngân hàng câu Đã duyệt theo tổ hợp.
    avail: dict[tuple, int] = {}
    for q in db.query(Question).filter(
        Question.course_id == m.course_id, Question.is_deleted == False,  # noqa: E712
        Question.review_status == "approved",
    ).all():
        if q.clo_id in code_by_id:
            key = (code_by_id[q.clo_id], q.bloom_level, q.difficulty)
            avail[key] = avail.get(key, 0) + 1
    bank_cells = [
        {"clo_code": k[0], "bloom_level": k[1], "difficulty": k[2], "available": v}
        for k, v in avail.items()
    ]
    cells = [
        {"clo_code": code_by_id.get(c.get("clo_id"), f"CLO#{c.get('clo_id')}"),
         "bloom_level": c.get("bloom_level"), "difficulty": c.get("difficulty"),
         "count": c.get("count"), "points_each": c.get("points_each")}
        for c in m.cells_json
    ]
    assessment = None
    if m.assessment_id:
        from app.models import Assessment

        a = db.get(Assessment, m.assessment_id)
        if a:
            target = _assessment_clo_ids(db, m.assessment_id)
            target_codes = [c.code for c in db.query(Clo).filter(Clo.id.in_(target or [-1])).all()]
            assessment = {"name": a.name, "clo_codes": target_codes}
    return {
        "course": {"code": course.code if course else "", "name": course.name if course else ""},
        "name": m.name, "total_points": m.total_points,
        "cells": cells, "bank_cells": bank_cells, "assessment": assessment,
    }


@router.get("/matrices/{mid}/qa-review")
def matrix_qa_review(mid: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI đánh giá ma trận đề thi theo AUN-QA: tổng điểm, độ phủ CLO, cân đối Bloom, khả thi."""
    from app.services.qa_review import review_matrix_ai

    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    if not m.cells_json:
        raise HTTPException(400, "Ma trận chưa có ô nào để đánh giá.")
    try:
        return review_matrix_ai(_matrix_review_payload(db, m))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Đánh giá ma trận thất bại: {e}")


@router.put("/matrices/{mid}", response_model=ExamMatrixOut)
def update_matrix(mid: int, payload: ExamMatrixCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    if m.status in ("approved", "archived"):
        raise HTTPException(400, "Ma trận đã duyệt/lưu trữ — không sửa được. Hãy nhân bản để chỉnh.")
    m.name = payload.name
    m.cells_json = [c.model_dump() for c in payload.cells]
    m.total_points = payload.total_points
    if payload.assessment_id is not None:
        m.assessment_id = payload.assessment_id or None
    db.commit()
    db.refresh(m)
    log_action(db, user.id, "exam_matrix", mid, "update")
    return _matrix_out(m)


class MatrixOptimizeIn(BaseModel):
    """qa: kết quả đánh giá AUN-QA (nếu có) để AI bám vào mà khắc phục khi tối ưu."""
    qa: dict | None = None


@router.post("/matrices/{mid}/optimize")
def optimize_matrix(
    mid: int,
    payload: MatrixOptimizeIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """AI tối ưu/nâng cấp ma trận (cân tổng điểm, cân đối Bloom, bám ngân hàng Đã duyệt) + giải thích AUN-QA.

    Nếu truyền kèm kết quả đánh giá (qa), AI sẽ bám vào các lỗi/cảnh báo/đề xuất đó để khắc phục.
    """
    from app.services.matrix_ai import optimize_exam_matrix_ai

    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    if m.status in ("approved", "archived"):
        raise HTTPException(400, "Ma trận đã duyệt/lưu trữ — hãy nhân bản để tối ưu bản nháp.")
    course = db.get(Course, m.course_id)
    clos = _latest_clos(db, m.course_id)
    if not clos:
        raise HTTPException(400, "Học phần chưa có CLO.")
    # Nếu ma trận gắn cấu phần đánh giá: chỉ tối ưu trong phạm vi CLO của cấu phần đó.
    if m.assessment_id:
        target = _assessment_clo_ids(db, m.assessment_id)
        scoped = [c for c in clos if c.id in target]
        if scoped:
            clos = scoped
    code_by_id = {c.id: c.code for c in clos}
    id_by_code = {c.code: c.id for c in clos}

    # Ngân hàng câu Đã duyệt theo tổ hợp
    avail: dict[tuple, int] = {}
    for q in db.query(Question).filter(
        Question.course_id == m.course_id, Question.is_deleted == False,  # noqa: E712
        Question.review_status == "approved",
    ).all():
        if q.clo_id in code_by_id:
            key = (code_by_id[q.clo_id], q.bloom_level, q.difficulty)
            avail[key] = avail.get(key, 0) + 1
    bank_cells = [
        {"clo_code": k[0], "bloom_level": k[1], "difficulty": k[2], "available": v}
        for k, v in avail.items()
    ]
    current = [
        {"clo_code": code_by_id.get(c.get("clo_id")), "bloom_level": c.get("bloom_level"),
         "difficulty": c.get("difficulty"), "count": c.get("count"), "points_each": c.get("points_each")}
        for c in m.cells_json
    ]

    try:
        res = optimize_exam_matrix_ai(
            course={"code": course.code, "name": course.name},
            clos=[{"code": c.code, "description": c.description} for c in clos],
            bank_cells=bank_cells,
            current_cells=current,
            total_points=m.total_points,
            qa=payload.qa if payload else None,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Tối ưu ma trận thất bại: {e}")

    # Áp kết quả: ánh xạ code→id, clamp theo ngân hàng, bỏ ô không khả thi.
    cells = []
    for cell in res["cells"]:
        cid = id_by_code.get(cell.get("clo_code"))
        if cid is None:
            continue
        key = (cell.get("clo_code"), cell.get("bloom_level"), cell.get("difficulty"))
        count = min(int(cell.get("count", 0) or 0), avail.get(key, 0))
        if count <= 0:
            continue
        cells.append({
            "clo_id": cid, "bloom_level": cell.get("bloom_level"),
            "difficulty": cell.get("difficulty"), "count": count,
            "points_each": cell.get("points_each"),
        })
    if not cells:
        raise HTTPException(400, "AI không tạo được ô khả thi từ ngân hàng Đã duyệt.")
    # LLM hay tính sai số học -> CÂN LẠI điểm/câu để tổng = đúng thang điểm (deterministic).
    from app.services.matrix_summary import rebalance_points

    cells = rebalance_points(cells, m.total_points)
    m.cells_json = cells
    if res.get("name"):
        m.name = res["name"]
    db.commit()
    db.refresh(m)
    log_action(db, user.id, "exam_matrix", mid, "optimize")
    out = _matrix_out(m).model_dump()
    out["rationale"] = res.get("rationale", "")
    return out


@router.post("/matrices/{mid}/status", response_model=ExamMatrixOut)
def matrix_change_status(mid: int, to: str, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Chuyển vòng đời ma trận: draft→review→approved→archived."""
    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    if to not in MATRIX_TRANSITIONS.get(m.status, set()):
        raise HTTPException(400, f"Không thể chuyển {m.status} → {to}")
    if to == "approved":
        if user.role not in (Role.PROGRAM_MANAGER.value, Role.ADMIN.value):
            raise HTTPException(403, "Chỉ quản lý mới được duyệt ma trận")
        from app.services.matrix_summary import matrix_summary

        res = matrix_summary(m.cells_json, m.total_points)
        if not res["ok"]:
            raise HTTPException(400, f"Ma trận chưa hợp lệ để duyệt: {res['errors']}")
        m.approved_by = user.id
    prev = m.status
    m.status = to
    db.commit()
    db.refresh(m)
    log_action(db, user.id, "exam_matrix", mid, "status", {"from": prev, "to": to})
    return _matrix_out(m)


@router.post("/matrices/{mid}/duplicate", response_model=ExamMatrixOut, status_code=201)
def duplicate_matrix(mid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    m = db.get(ExamMatrix, mid)
    if not m:
        raise HTTPException(404, "Không tìm thấy ma trận")
    dup = ExamMatrix(
        course_id=m.course_id, name=f"{m.name} (bản sao)",
        cells_json=list(m.cells_json), total_points=m.total_points,
        status="draft", created_by=user.id,
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    log_action(db, user.id, "exam_matrix", dup.id, "duplicate", {"from": mid})
    return _matrix_out(dup)


@router.delete("/matrices/{mid}", status_code=204)
def delete_matrix(mid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    m = db.get(ExamMatrix, mid)
    if not m:
        return
    if m.status == "approved":
        raise HTTPException(400, "Ma trận đã duyệt — hãy chuyển về nháp hoặc lưu trữ trước khi xóa.")
    db.delete(m)
    db.commit()
    log_action(db, user.id, "exam_matrix", mid, "delete")


class MatrixGenIn(BaseModel):
    total_points: float = 100
    name: str = ""
    assessment_id: int | None = None  # gắn cấu phần đánh giá của đề cương


@router.post("/courses/{course_id}/matrices/generate", response_model=ExamMatrixOut, status_code=201)
def generate_matrix(
    course_id: int, payload: MatrixGenIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    """AI tạo ma trận đề thi bám sát ngân hàng câu hỏi hiện có (SPEC mục 11).

    Nếu có assessment_id: chỉ dùng CLO mà cấu phần đánh giá đó phụ trách (constructive alignment).
    """
    from app.services.matrix_ai import generate_exam_matrix_ai

    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    clos = _latest_clos(db, course_id)
    if not clos:
        raise HTTPException(400, "Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")
    # Lọc CLO theo cấu phần đánh giá nếu được gắn.
    if payload.assessment_id:
        target = _assessment_clo_ids(db, payload.assessment_id)
        scoped = [c for c in clos if c.id in target]
        if scoped:
            clos = scoped
    code_by_id = {c.id: c.code for c in clos}

    # Thống kê ngân hàng theo tổ hợp (CLO×Bloom×độ khó) để ma trận khả thi.
    avail: dict[tuple, int] = {}
    for q in db.query(Question).filter(
        Question.course_id == course_id, Question.is_deleted == False  # noqa: E712
    ).all():
        if q.clo_id in code_by_id:
            key = (code_by_id[q.clo_id], q.bloom_level, q.difficulty)
            avail[key] = avail.get(key, 0) + 1
    bank_cells = [
        {"clo_code": k[0], "bloom_level": k[1], "difficulty": k[2], "available": v}
        for k, v in avail.items()
    ]

    try:
        gen = generate_exam_matrix_ai(
            course={"code": course.code, "name": course.name},
            clos=[{"code": c.code, "description": c.description} for c in clos],
            bank_cells=bank_cells,
            total_points=payload.total_points,
            name_hint=payload.name,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Sinh ma trận thất bại: {e}")

    # Ánh xạ clo_code -> clo_id; chỉ giữ ô có câu sẵn (clamp số câu theo ngân hàng).
    id_by_code = {c.code: c.id for c in clos}
    cells = []
    for cell in gen["cells"]:
        code = cell.get("clo_code")
        cid = id_by_code.get(code)
        if cid is None:
            continue
        key = (code, cell.get("bloom_level"), cell.get("difficulty"))
        available = avail.get(key, 0)
        count = min(int(cell.get("count", 0) or 0), available)
        if count <= 0:
            continue
        cells.append({
            "clo_id": cid, "bloom_level": cell.get("bloom_level"),
            "difficulty": cell.get("difficulty"), "count": count,
            "points_each": cell.get("points_each"),
        })
    if not cells:
        raise HTTPException(400, "AI không tạo được ô khả thi từ ngân hàng hiện có.")
    # Cân lại điểm/câu để tổng = đúng thang điểm khai báo.
    from app.services.matrix_summary import rebalance_points

    cells = rebalance_points(cells, payload.total_points)

    obj = ExamMatrix(
        course_id=course_id, name=gen["name"], cells_json=cells,
        total_points=payload.total_points, created_by=user.id,
        assessment_id=payload.assessment_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "exam_matrix", obj.id, "generate_ai")
    return _matrix_out(obj)
