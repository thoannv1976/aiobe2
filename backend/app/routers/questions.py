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
MATRIX_TRANSITIONS = {
    "draft": {"review"},
    "review": {"approved", "draft"},
    "approved": {"archived", "draft"},
    "archived": set(),
}


def _matrix_out(m: ExamMatrix) -> ExamMatrixOut:
    return ExamMatrixOut(
        id=m.id, course_id=m.course_id, name=m.name, cells=m.cells_json,
        status=m.status, total_points=m.total_points,
    )


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
    return matrix_summary(m.cells_json, m.total_points)


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
    db.commit()
    db.refresh(m)
    log_action(db, user.id, "exam_matrix", mid, "update")
    return _matrix_out(m)


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


@router.post("/courses/{course_id}/matrices/generate", response_model=ExamMatrixOut, status_code=201)
def generate_matrix(
    course_id: int, payload: MatrixGenIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    """AI tạo ma trận đề thi bám sát ngân hàng câu hỏi hiện có (SPEC mục 11)."""
    from app.services.matrix_ai import generate_exam_matrix_ai

    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    clos = _latest_clos(db, course_id)
    if not clos:
        raise HTTPException(400, "Học phần chưa có đề cương/CLO. Hãy tạo đề cương trước.")
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

    obj = ExamMatrix(
        course_id=course_id, name=gen["name"], cells_json=cells,
        total_points=payload.total_points, created_by=user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "exam_matrix", obj.id, "generate_ai")
    return _matrix_out(obj)
