import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import (
    Assessment,
    AssessmentClo,
    Clo,
    CloPlo,
    Course,
    CourseOutline,
    Document,
    LessonPlan,
    LessonPlanClo,
    OutlineStatus,
    Pi,
    Plo,
    Program,
    Role,
    User,
)
from app.schemas.outline import (
    AssessmentCreate,
    AssessmentOut,
    CloCreate,
    CloOut,
    CloPloIn,
    CloPloOut,
    LessonPlanCreate,
    LessonPlanOut,
    OutlineBase,
    OutlineCreate,
    OutlineOut,
)
from app.schemas.outline_gen import GeneratedOutline
from app.services.alignment import check_outline_alignment
from app.services.audit import log_action
from app.services.diff import diff_outlines
from app.services.exports import outline_to_docx
from app.services.extraction import extract_text_from_file
from app.services.outline_ai import (
    generate_outline_ai,
    improve_outline_ai,
    parse_outline_from_text,
)

router = APIRouter(prefix="/api", tags=["outline"])

LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)
APPROVER = require_roles(Role.PROGRAM_MANAGER)

# Chuyển trạng thái hợp lệ (SPEC 4.3)
TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"approved", "draft"},
    "approved": {"published", "draft"},
    "published": {"archived"},
    "archived": set(),
}


def _outline_out(o: CourseOutline) -> OutlineOut:
    return OutlineOut.model_validate(o)


@router.get("/courses/{course_id}/outlines", response_model=list[OutlineOut])
def list_outlines(course_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .all()
    )


@router.post("/outlines", response_model=OutlineOut, status_code=201)
def create_outline(payload: OutlineCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    if not db.get(Course, payload.course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = CourseOutline(
        course_id=payload.course_id,
        version=1,
        status="draft",
        description=payload.description,
        general_info_json=payload.general_info_json,
        teaching_methods_json=payload.teaching_methods_json,
        references_json=payload.references_json,
        created_by=user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "outline", obj.id, "create")
    return obj


@router.post("/courses/{course_id}/generate-outline", response_model=OutlineOut, status_code=201)
def generate_outline(
    course_id: int,
    template_doc_id: int | None = None,
    aunqa_doc_id: int | None = None,
    num_clos: str = "4–6",
    num_weeks: int = 15,
    assessment_scheme: str = "10-30-60",
    bilingual: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Sinh đề cương bằng AI từ CTĐT + PLO + PI + ma trận Học phần×PLO (SPEC 4.3).

    Tùy chọn truyền template_doc_id (mẫu đề cương) và aunqa_doc_id (chuẩn AUN-QA) đã upload.
    Tham số tinh chỉnh: num_clos, num_weeks, assessment_scheme (10-30-60|10-40-50|20-30-50|auto),
    bilingual (CLO song ngữ Việt-Anh).
    Ghi ra một đề cương DRAFT (CLO, ma trận CLO×PLO, đánh giá, kế hoạch dạy) để người dùng rà soát.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    program = db.get(Program, course.program_id)
    plos = db.query(Plo).filter(Plo.program_id == course.program_id).all()
    plo_by_code = {p.code: p for p in plos}
    pis = (
        db.query(Pi).filter(Pi.plo_id.in_([p.id for p in plos] or [-1])).all() if plos else []
    )
    plo_code_by_id = {p.id: p.code for p in plos}

    # Ma trận Học phần×PLO (bảng course_plo).
    from app.models import CoursePlo

    course_plo = [
        {"plo_code": plo_code_by_id[cp.plo_id], "level": cp.level}
        for cp in db.query(CoursePlo).filter(CoursePlo.course_id == course_id).all()
        if cp.plo_id in plo_code_by_id
    ]

    def _doc_text(doc_id: int | None) -> str:
        if not doc_id:
            return ""
        d = db.get(Document, doc_id)
        return d.extracted_text or "" if d else ""

    try:
        gen = generate_outline_ai(
            course={
                "code": course.code, "name": course.name, "credits": course.credits,
                "semester": course.semester, "type": course.type,
                "program_name": program.name if program else "",
            },
            plos=[{"code": p.code, "category": p.category or "", "description": p.description} for p in plos],
            pis=[{"code": pi.code, "plo_code": plo_code_by_id.get(pi.plo_id, ""), "description": pi.description} for pi in pis],
            course_plo=course_plo,
            template_text=_doc_text(template_doc_id),
            aunqa_text=_doc_text(aunqa_doc_id),
            num_clos=num_clos,
            num_weeks=num_weeks,
            assessment_scheme=assessment_scheme,
            bilingual=bilingual,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Sinh đề cương thất bại: {e}")

    outline = _write_generated_outline(db, course_id, gen, plo_by_code, user, {"generated_by_ai": True})
    log_action(db, user.id, "outline", outline.id, "generate_ai", {"course_id": course_id})
    return outline


def _write_generated_outline(db, course_id, gen, plo_by_code, user, info_json):
    """Ghi một GeneratedOutline (AI sinh/nâng cấp) thành đề cương DRAFT phiên bản mới."""
    latest = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    outline = CourseOutline(
        course_id=course_id,
        version=(latest.version + 1) if latest else 1,
        status="draft",
        description=gen.description,
        general_info_json=info_json,
        teaching_methods_json=gen.teaching_methods,
        references_json=gen.references,
        created_by=user.id,
    )
    db.add(outline)
    db.flush()

    clo_by_code: dict[str, Clo] = {}
    for gc in gen.clos:
        clo = Clo(
            outline_id=outline.id, code=gc.code, description=gc.description,
            description_en=gc.description_en or None, bloom_level=gc.bloom_level or None,
        )
        db.add(clo)
        db.flush()
        clo_by_code[gc.code] = clo
        for cp in gc.plos:
            plo = plo_by_code.get(cp.plo_code)
            if plo:
                db.add(CloPlo(clo_id=clo.id, plo_id=plo.id, contribution_level=cp.level or "R"))

    for ga in gen.assessments:
        a = Assessment(
            outline_id=outline.id, name=ga.name, type=ga.type or None,
            weight_percent=ga.weight_percent,
            rubric_json={"criteria": [c.model_dump() for c in ga.rubric]} if ga.rubric else {},
        )
        db.add(a)
        db.flush()
        for code in ga.clo_codes:
            if code in clo_by_code:
                db.add(AssessmentClo(assessment_id=a.id, clo_id=clo_by_code[code].id))

    for gl in gen.lessons:
        lp = LessonPlan(outline_id=outline.id, week=gl.week, topic=gl.topic, activities_json={})
        db.add(lp)
        db.flush()
        for code in gl.clo_codes:
            if code in clo_by_code:
                db.add(LessonPlanClo(lesson_plan_id=lp.id, clo_id=clo_by_code[code].id))

    db.commit()
    db.refresh(outline)
    return outline


@router.get("/outlines/{outline_id}", response_model=OutlineOut)
def get_outline(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    obj = db.get(CourseOutline, outline_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy đề cương")
    return obj


@router.post("/outlines/{outline_id}/new-version", response_model=OutlineOut, status_code=201)
def new_version(outline_id: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Tạo phiên bản mới từ đề cương hiện tại (versioning - SPEC 4.3)."""
    src = db.get(CourseOutline, outline_id)
    if not src:
        raise HTTPException(404, "Không tìm thấy đề cương")
    latest = (
        db.query(CourseOutline)
        .filter(CourseOutline.course_id == src.course_id)
        .order_by(CourseOutline.version.desc())
        .first()
    )
    new = CourseOutline(
        course_id=src.course_id,
        version=latest.version + 1,
        status="draft",
        description=src.description,
        general_info_json=src.general_info_json,
        teaching_methods_json=src.teaching_methods_json,
        references_json=src.references_json,
        created_by=user.id,
    )
    db.add(new)
    db.flush()
    # sao chép CLO + ma trận + đánh giá + buổi học
    clo_map = {}
    for c in src.clos:
        nc = Clo(outline_id=new.id, code=c.code, description=c.description, bloom_level=c.bloom_level)
        db.add(nc)
        db.flush()
        clo_map[c.id] = nc.id
        for cp in c.clo_plos:
            db.add(CloPlo(clo_id=nc.id, plo_id=cp.plo_id, contribution_level=cp.contribution_level))
    for a in src.assessments:
        na = Assessment(
            outline_id=new.id, name=a.name, type=a.type,
            weight_percent=a.weight_percent, rubric_json=a.rubric_json,
        )
        db.add(na)
        db.flush()
        for ac in a.assessment_clos:
            if ac.clo_id in clo_map:
                db.add(AssessmentClo(assessment_id=na.id, clo_id=clo_map[ac.clo_id]))
    for lp in src.lesson_plans:
        nlp = LessonPlan(outline_id=new.id, week=lp.week, topic=lp.topic, activities_json=lp.activities_json)
        db.add(nlp)
        db.flush()
        for lc in lp.lesson_plan_clos:
            if lc.clo_id in clo_map:
                db.add(LessonPlanClo(lesson_plan_id=nlp.id, clo_id=clo_map[lc.clo_id]))
    db.commit()
    db.refresh(new)
    log_action(db, user.id, "outline", new.id, "new_version", {"from": outline_id})
    return new


@router.post("/outlines/{outline_id}/status", response_model=OutlineOut)
def change_status(
    outline_id: int, to: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    obj = db.get(CourseOutline, outline_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy đề cương")
    if to not in TRANSITIONS.get(obj.status, set()):
        raise HTTPException(400, f"Không thể chuyển {obj.status} → {to}")
    # Duyệt (approve) chỉ dành cho quản lý
    if to == "approved":
        if user.role not in (Role.PROGRAM_MANAGER.value, Role.ADMIN.value):
            raise HTTPException(403, "Chỉ quản lý CTĐT mới được duyệt")
        # Yêu cầu alignment hợp lệ trước khi duyệt
        res = check_outline_alignment(db, outline_id)
        if not res.ok:
            raise HTTPException(400, f"Đề cương chưa đạt alignment: {res.errors}")
        obj.approved_by = user.id
    prev = obj.status
    obj.status = to
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "outline", outline_id, "status", {"from": prev, "to": to})
    return obj


@router.get("/outlines/{outline_id}/alignment")
def alignment(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return check_outline_alignment(db, outline_id).to_dict()


# --------------------------- CLO ---------------------------
@router.get("/outlines/{outline_id}/clos", response_model=list[CloOut])
def list_clos(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Clo).filter(Clo.outline_id == outline_id).all()


@router.post("/outlines/{outline_id}/clos", response_model=CloOut, status_code=201)
def create_clo(outline_id: int, payload: CloCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    if not db.get(CourseOutline, outline_id):
        raise HTTPException(404, "Không tìm thấy đề cương")
    obj = Clo(outline_id=outline_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "clo", obj.id, "create")
    return obj


@router.delete("/clos/{clo_id}", status_code=204)
def delete_clo(clo_id: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Clo, clo_id)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "clo", clo_id, "delete")


# --------------------------- CLO x PLO ---------------------------
@router.put("/clo-plo", response_model=CloPloOut)
def upsert_clo_plo(payload: CloPloIn, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = (
        db.query(CloPlo)
        .filter(CloPlo.clo_id == payload.clo_id, CloPlo.plo_id == payload.plo_id)
        .first()
    )
    if obj:
        obj.contribution_level = payload.contribution_level
    else:
        obj = CloPlo(**payload.model_dump())
        db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "clo_plo", obj.id, "upsert")
    return obj


@router.get("/outlines/{outline_id}/clo-plo", response_model=list[CloPloOut])
def list_clo_plo(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    clo_ids = [c.id for c in db.query(Clo).filter(Clo.outline_id == outline_id).all()]
    if not clo_ids:
        return []
    return db.query(CloPlo).filter(CloPlo.clo_id.in_(clo_ids)).all()


# --------------------------- Assessments ---------------------------
@router.get("/outlines/{outline_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for a in db.query(Assessment).filter(Assessment.outline_id == outline_id).all():
        d = AssessmentOut.model_validate(a)
        d.clo_ids = [ac.clo_id for ac in a.assessment_clos]
        out.append(d)
    return out


@router.post("/outlines/{outline_id}/assessments", response_model=AssessmentOut, status_code=201)
def create_assessment(
    outline_id: int, payload: AssessmentCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(CourseOutline, outline_id):
        raise HTTPException(404, "Không tìm thấy đề cương")
    obj = Assessment(
        outline_id=outline_id, name=payload.name, type=payload.type,
        weight_percent=payload.weight_percent, rubric_json=payload.rubric_json,
    )
    db.add(obj)
    db.flush()
    for cid in payload.clo_ids:
        db.add(AssessmentClo(assessment_id=obj.id, clo_id=cid))
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "assessment", obj.id, "create")
    res = AssessmentOut.model_validate(obj)
    res.clo_ids = payload.clo_ids
    return res


# --------------------------- Lesson plans ---------------------------
@router.get("/outlines/{outline_id}/lessons", response_model=list[LessonPlanOut])
def list_lessons(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    out = []
    for lp in db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).order_by(LessonPlan.week).all():
        d = LessonPlanOut.model_validate(lp)
        d.clo_ids = [lc.clo_id for lc in lp.lesson_plan_clos]
        out.append(d)
    return out


@router.post("/outlines/{outline_id}/lessons", response_model=LessonPlanOut, status_code=201)
def create_lesson(
    outline_id: int, payload: LessonPlanCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    if not db.get(CourseOutline, outline_id):
        raise HTTPException(404, "Không tìm thấy đề cương")
    obj = LessonPlan(
        outline_id=outline_id, week=payload.week, topic=payload.topic,
        activities_json=payload.activities_json,
    )
    db.add(obj)
    db.flush()
    for cid in payload.clo_ids:
        db.add(LessonPlanClo(lesson_plan_id=obj.id, clo_id=cid))
    db.commit()
    db.refresh(obj)
    res = LessonPlanOut.model_validate(obj)
    res.clo_ids = payload.clo_ids
    return res


@router.patch("/assessments/{aid}", response_model=AssessmentOut)
def update_assessment(
    aid: int, payload: AssessmentCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)
):
    """Cập nhật cấu phần đánh giá, gồm rubric (SPEC 4.3)."""
    obj = db.get(Assessment, aid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy cấu phần đánh giá")
    obj.name = payload.name
    obj.type = payload.type
    obj.weight_percent = payload.weight_percent
    obj.rubric_json = payload.rubric_json
    # Cập nhật ánh xạ CLO nếu được truyền.
    db.query(AssessmentClo).filter(AssessmentClo.assessment_id == aid).delete()
    for cid in payload.clo_ids:
        db.add(AssessmentClo(assessment_id=aid, clo_id=cid))
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "assessment", aid, "update")
    res = AssessmentOut.model_validate(obj)
    res.clo_ids = payload.clo_ids
    return res


@router.delete("/assessments/{aid}", status_code=204)
def delete_assessment(aid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(Assessment, aid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "assessment", aid, "delete")


@router.delete("/lessons/{lid}", status_code=204)
def delete_lesson(lid: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.get(LessonPlan, lid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "lesson_plan", lid, "delete")


@router.delete("/clo-plo", status_code=204)
def delete_clo_plo(clo_id: int, plo_id: int, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    obj = db.query(CloPlo).filter(CloPlo.clo_id == clo_id, CloPlo.plo_id == plo_id).first()
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "clo_plo", obj.id, "delete")


@router.patch("/outlines/{outline_id}", response_model=OutlineOut)
def update_outline(outline_id: int, payload: OutlineBase, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Cập nhật thông tin chung đề cương (chỉ khi chưa Published).

    Dùng OutlineBase (không cần course_id) vì đề cương đã được xác định bằng outline_id trên URL.
    """
    obj = db.get(CourseOutline, outline_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy đề cương")
    if obj.status in ("published", "archived"):
        raise HTTPException(400, "Không sửa được đề cương đã ban hành")
    obj.description = payload.description
    obj.general_info_json = payload.general_info_json
    obj.teaching_methods_json = payload.teaching_methods_json
    obj.references_json = payload.references_json
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "outline", outline_id, "update")
    return obj


@router.get("/outlines/{from_id}/diff/{to_id}")
def outline_diff(from_id: int, to_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """So sánh hai phiên bản đề cương (SPEC 4.3)."""
    return diff_outlines(db, from_id, to_id)


@router.get("/outlines/{outline_id}/export")
def export_outline(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Xuất đề cương ra DOCX (SPEC 4.3)."""
    try:
        data = outline_to_docx(db, outline_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=de_cuong_{outline_id}.docx"},
    )


def _run_outline_qa(db: Session, outline_id: int) -> dict:
    """Chạy AI kiểm tra chất lượng đề cương + LƯU snapshot điểm vào general_info_json
    (để dựng bảng 'sức khỏe đề cương toàn ngành' mà không phải gọi lại LLM)."""
    from datetime import datetime, timezone

    from app.services.qa_review import review_outline_ai

    outline = db.get(CourseOutline, outline_id)
    if not outline:
        raise HTTPException(404, "Không tìm thấy đề cương")
    course = db.get(Course, outline.course_id)
    clos = db.query(Clo).filter(Clo.outline_id == outline_id).all()
    clo_by_id = {c.id: c for c in clos}
    plo_map: dict[int, list[str]] = {c.id: [] for c in clos}
    for cp in db.query(CloPlo).filter(CloPlo.clo_id.in_([c.id for c in clos] or [-1])).all():
        plo = db.get(Plo, cp.plo_id)
        if cp.clo_id in plo_map and plo:
            plo_map[cp.clo_id].append(plo.code)
    clo_payload = [
        {"code": c.code, "description": c.description, "bloom_level": c.bloom_level or "",
         "plos": plo_map.get(c.id, [])}
        for c in clos
    ]
    assessments = []
    for a in db.query(Assessment).filter(Assessment.outline_id == outline_id).all():
        codes = [clo_by_id[ac.clo_id].code
                 for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all()
                 if ac.clo_id in clo_by_id]
        assessments.append({"name": a.name, "weight": a.weight_percent, "clos": codes})
    lessons = []
    for lp in db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).all():
        codes = [clo_by_id[lc.clo_id].code
                 for lc in db.query(LessonPlanClo).filter(LessonPlanClo.lesson_plan_id == lp.id).all()
                 if lc.clo_id in clo_by_id]
        lessons.append({"topic": lp.topic, "clos": codes})
    res = review_outline_ai({
        "course": {"code": course.code if course else "", "name": course.name if course else ""},
        "clos": clo_payload, "assessments": assessments, "lessons": lessons,
    })
    info = dict(outline.general_info_json or {})
    info["qa_score"] = res.get("score")
    info["qa_errors"] = len(res.get("errors") or [])
    info["qa_warnings"] = len(res.get("warnings") or [])
    info["qa_at"] = datetime.now(timezone.utc).isoformat()
    outline.general_info_json = info
    db.commit()
    return res


@router.get("/outlines/{outline_id}/qa-review")
def qa_review_outline(outline_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """AI kiểm tra chất lượng đề cương: CLO đo được, alignment, đánh giá (SPEC mục 14)."""
    try:
        return _run_outline_qa(db, outline_id)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Kiểm tra chất lượng thất bại: {e}")


# ---------------------------------------------------------------------------
# Import đề cương ĐÃ CÓ (PDF/DOCX) → bóc tách bằng AI → rà soát → lưu draft (SPEC 4.3)
# ---------------------------------------------------------------------------
def _plo_by_code(db: Session, course: Course) -> dict[str, Plo]:
    return {p.code: p for p in db.query(Plo).filter(Plo.program_id == course.program_id).all()}


def _program_plo_context(db: Session, program_id: int):
    """Ngữ cảnh PLO/PI dùng chung cho cả chương trình (PLO không phụ thuộc từng học phần)."""
    plos = db.query(Plo).filter(Plo.program_id == program_id).all()
    plo_code_by_id = {p.id: p.code for p in plos}
    pis = db.query(Pi).filter(Pi.plo_id.in_([p.id for p in plos] or [-1])).all() if plos else []
    plo_dicts = [{"code": p.code, "category": p.category or "", "description": p.description} for p in plos]
    pi_dicts = [{"code": pi.code, "plo_code": plo_code_by_id.get(pi.plo_id, ""), "description": pi.description} for pi in pis]
    return plo_dicts, pi_dicts, {p.code for p in plos}, {p.code: p for p in plos}


def _clean_parsed_plos(gen, plo_codes: set[str]) -> list[str]:
    """Bỏ ánh xạ PLO không thuộc chương trình; trả danh sách mã PLO bị loại (để cảnh báo)."""
    unmatched: set[str] = set()
    for clo in gen.clos:
        kept = []
        for m in clo.plos:
            if m.plo_code in plo_codes:
                kept.append(m)
            else:
                unmatched.add(m.plo_code)
        clo.plos = kept
    return sorted(unmatched)


def _parse_uploaded_outline(db: Session, course: Course, text: str) -> dict:
    """Bóc tách văn bản đề cương → dict {outline, detected_course_code, unmatched_plos}."""
    plo_dicts, pi_dicts, plo_codes, _ = _program_plo_context(db, course.program_id)
    gen, detected = parse_outline_from_text(
        course={"code": course.code, "name": course.name},
        plos=plo_dicts, pis=pi_dicts, text=text,
    )
    unmatched = _clean_parsed_plos(gen, plo_codes)
    return {
        "outline": gen.model_dump(),
        "detected_course_code": detected,
        "unmatched_plos": unmatched,
        "clos_without_plo": [c.code for c in gen.clos if not c.plos],
    }


@router.post("/courses/{course_id}/parse-outline")
async def parse_outline_upload(
    course_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Upload đề cương ĐÃ CÓ (PDF/DOCX/TXT) → AI bóc tách thành cấu trúc để RÀ SOÁT (chưa lưu).

    Lưu file gốc làm minh chứng; trả về cấu trúc đề cương + cảnh báo PLO chưa khớp.
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    os.makedirs(settings.storage_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    saved = os.path.join(settings.storage_dir, f"{uuid.uuid4().hex}{ext}")
    with open(saved, "wb") as f:
        f.write(await file.read())
    try:
        text = extract_text_from_file(saved, file.content_type)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Không đọc được nội dung file: {e}")
    doc = Document(
        type="outline_template", file_path=saved, mime=file.content_type,
        uploaded_by=user.id, original_name=file.filename, extracted_text=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    try:
        res = _parse_uploaded_outline(db, course, text)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Bóc tách đề cương thất bại: {e}")
    res["document_id"] = doc.id
    res["original_name"] = doc.original_name
    log_action(db, user.id, "outline", None, "parse_upload", {"course_id": course_id})
    return res


class ImportOutlineIn(BaseModel):
    """Đề cương đã rà soát (có thể đã chỉnh tay) để lưu thành draft."""
    outline: GeneratedOutline
    source_name: str = ""


@router.post("/courses/{course_id}/import-outline", response_model=OutlineOut, status_code=201)
def import_outline(
    course_id: int,
    payload: ImportOutlineIn,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Lưu đề cương đã bóc tách/rà soát thành một phiên bản draft trong hệ thống (SPEC 4.3)."""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    if not payload.outline.clos:
        raise HTTPException(400, "Đề cương chưa có CLO để lưu.")
    plo_by_code = _plo_by_code(db, course)
    info = {"imported": True, "source_name": payload.source_name or None}
    outline = _write_generated_outline(db, course_id, payload.outline, plo_by_code, user, info)
    log_action(db, user.id, "outline", outline.id, "import", {"course_id": course_id})
    return outline


class ImproveOutlineIn(BaseModel):
    """Tham số nâng cấp đề cương bằng AI.

    qa: kết quả kiểm tra chất lượng đã chạy ở frontend (score/summary/errors/warnings/clo_reviews).
    Nếu để trống, backend tự chạy lại kiểm tra chất lượng trước khi nâng cấp.
    """
    qa: dict | None = None


@router.post("/outlines/{outline_id}/improve", response_model=OutlineOut, status_code=201)
def improve_outline(
    outline_id: int,
    payload: ImproveOutlineIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Nâng cấp đề cương bằng AI dựa trên kết quả kiểm tra chất lượng (SPEC mục 14).

    Đọc đề cương hiện tại + kết quả kiểm tra chất lượng (AI), sinh ra một PHIÊN BẢN MỚI (draft)
    đã khắc phục các lỗi/cảnh báo — giữ nguyên phiên bản gốc để đối chiếu (diff).
    """
    from app.models import CoursePlo
    from app.services.qa_review import review_outline_ai

    outline = db.get(CourseOutline, outline_id)
    if not outline:
        raise HTTPException(404, "Không tìm thấy đề cương")
    course = db.get(Course, outline.course_id)
    if not course:
        raise HTTPException(404, "Không tìm thấy học phần")
    program = db.get(Program, course.program_id)
    plos = db.query(Plo).filter(Plo.program_id == course.program_id).all()
    plo_by_code = {p.code: p for p in plos}
    plo_code_by_id = {p.id: p.code for p in plos}
    pis = db.query(Pi).filter(Pi.plo_id.in_([p.id for p in plos] or [-1])).all() if plos else []
    course_plo = [
        {"plo_code": plo_code_by_id[cp.plo_id], "level": cp.level}
        for cp in db.query(CoursePlo).filter(CoursePlo.course_id == course.id).all()
        if cp.plo_id in plo_code_by_id
    ]

    # Dữ liệu đề cương hiện tại
    clos = db.query(Clo).filter(Clo.outline_id == outline_id).all()
    clo_by_id = {c.id: c for c in clos}
    clo_plos: dict[int, list[dict]] = {c.id: [] for c in clos}
    for cp in db.query(CloPlo).filter(CloPlo.clo_id.in_([c.id for c in clos] or [-1])).all():
        if cp.clo_id in clo_plos and cp.plo_id in plo_code_by_id:
            clo_plos[cp.clo_id].append({"plo_code": plo_code_by_id[cp.plo_id], "level": cp.contribution_level})
    cur_clos = [
        {"code": c.code, "description": c.description, "description_en": c.description_en or "",
         "bloom_level": c.bloom_level or "", "plos": clo_plos.get(c.id, [])}
        for c in clos
    ]
    cur_assessments = []
    qa_assessments = []
    for a in db.query(Assessment).filter(Assessment.outline_id == outline_id).all():
        codes = [clo_by_id[ac.clo_id].code
                 for ac in db.query(AssessmentClo).filter(AssessmentClo.assessment_id == a.id).all()
                 if ac.clo_id in clo_by_id]
        cur_assessments.append({"name": a.name, "type": a.type or "",
                                "weight_percent": a.weight_percent, "clo_codes": codes})
        qa_assessments.append({"name": a.name, "weight": a.weight_percent, "clos": codes})
    cur_lessons = []
    qa_lessons = []
    for lp in db.query(LessonPlan).filter(LessonPlan.outline_id == outline_id).all():
        codes = [clo_by_id[lc.clo_id].code
                 for lc in db.query(LessonPlanClo).filter(LessonPlanClo.lesson_plan_id == lp.id).all()
                 if lc.clo_id in clo_by_id]
        cur_lessons.append({"week": lp.week, "topic": lp.topic, "clo_codes": codes})
        qa_lessons.append({"topic": lp.topic, "clos": codes})
    if not cur_clos:
        raise HTTPException(400, "Đề cương chưa có CLO để nâng cấp")

    # Kết quả kiểm tra chất lượng: dùng kết quả truyền vào, nếu không có thì tự chạy.
    qa = payload.qa if payload and payload.qa else None
    if not qa:
        try:
            qa = review_outline_ai({
                "course": {"code": course.code, "name": course.name},
                "clos": [{"code": c["code"], "description": c["description"],
                          "bloom_level": c["bloom_level"],
                          "plos": [m["plo_code"] for m in c["plos"]]} for c in cur_clos],
                "assessments": qa_assessments, "lessons": qa_lessons,
            })
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Kiểm tra chất lượng trước khi nâng cấp thất bại: {e}")

    try:
        gen = improve_outline_ai(
            course={
                "code": course.code, "name": course.name, "credits": course.credits,
                "semester": course.semester, "type": course.type,
                "program_name": program.name if program else "",
            },
            plos=[{"code": p.code, "category": p.category or "", "description": p.description} for p in plos],
            pis=[{"code": pi.code, "plo_code": plo_code_by_id.get(pi.plo_id, ""), "description": pi.description} for pi in pis],
            course_plo=course_plo,
            current={
                "description": outline.description or "",
                "teaching_methods": outline.teaching_methods_json or [],
                "references": outline.references_json or [],
                "clos": cur_clos, "assessments": cur_assessments, "lessons": cur_lessons,
            },
            qa=qa,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Nâng cấp đề cương thất bại: {e}")

    new = _write_generated_outline(
        db, course.id, gen, plo_by_code, user,
        {"generated_by_ai": True, "improved_from": outline_id, "qa_score": qa.get("score")},
    )
    log_action(db, user.id, "outline", new.id, "improve_ai",
               {"from": outline_id, "qa_score": qa.get("score")})
    return new


# ---------------------------------------------------------------------------
# Phase 3: Import HÀNG LOẠT đề cương cho cả chương trình + bảng "sức khỏe đề cương"
# ---------------------------------------------------------------------------
def _latest_outline_by_course(db: Session, program_id: int) -> dict[int, CourseOutline]:
    """Đề cương phiên bản mới nhất của mỗi học phần trong chương trình."""
    courses = db.query(Course).filter(Course.program_id == program_id).all()
    out: dict[int, CourseOutline] = {}
    for c in courses:
        latest = (
            db.query(CourseOutline)
            .filter(CourseOutline.course_id == c.id)
            .order_by(CourseOutline.version.desc())
            .first()
        )
        if latest:
            out[c.id] = latest
    return out


@router.post("/programs/{program_id}/import-outlines")
async def bulk_import_outlines(
    program_id: int,
    files: list[UploadFile],
    run_qa: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(LECTURER),
):
    """Import nhiều đề cương cùng lúc cho một chương trình (SPEC 4.3, Phase 3).

    Mỗi file: bóc tách bằng AI → ghép với học phần (theo mã học phần phát hiện được hoặc
    có trong tên file) → lưu draft → (tùy chọn) tự chấm chất lượng. Trả bảng kết quả.
    """
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(404, "Không tìm thấy chương trình")
    courses = db.query(Course).filter(Course.program_id == program_id).all()
    if not courses:
        raise HTTPException(400, "Chương trình chưa có học phần nào để ghép đề cương.")
    if not files:
        raise HTTPException(400, "Chưa chọn file nào.")
    by_code = {c.code.upper(): c for c in courses}
    # PLO/PI dùng chung toàn chương trình → chỉ tính một lần, bóc tách 1 lần/ file.
    plo_dicts, pi_dicts, plo_codes, plo_by_code = _program_plo_context(db, program_id)
    os.makedirs(settings.storage_dir, exist_ok=True)

    results = []
    for file in files:
        row = {"filename": file.filename, "matched": False, "course_code": None,
               "outline_id": None, "score": None, "errors": 0, "warnings": 0, "message": ""}
        try:
            ext = os.path.splitext(file.filename or "")[1]
            saved = os.path.join(settings.storage_dir, f"{uuid.uuid4().hex}{ext}")
            with open(saved, "wb") as f:
                f.write(await file.read())
            text = extract_text_from_file(saved, file.content_type)
            if not (text or "").strip():
                row["message"] = "Không đọc được nội dung file (rỗng/scan không OCR được)."
                results.append(row); continue
            doc = Document(type="outline_template", file_path=saved, mime=file.content_type,
                           uploaded_by=user.id, original_name=file.filename, extracted_text=text)
            db.add(doc)
            db.commit()

            # Bóc tách 1 lần (không phụ thuộc học phần — PLO là của cả chương trình).
            gen, detected = parse_outline_from_text(
                course={"code": "", "name": ""}, plos=plo_dicts, pis=pi_dicts, text=text,
            )
            _clean_parsed_plos(gen, plo_codes)
            detected_up = (detected or "").upper()
            fname_up = (file.filename or "").upper()
            match = by_code.get(detected_up)
            if not match:
                # khớp theo mã học phần xuất hiện trong tên file (ưu tiên mã dài để tránh nhầm)
                match = next((c for code, c in sorted(by_code.items(), key=lambda kv: -len(kv[0]))
                              if code and code in fname_up), None)
            if not match:
                row["message"] = f"Không khớp học phần (mã phát hiện: {detected or '—'})."
                results.append(row); continue
            row["matched"] = True
            row["course_code"] = match.code

            if not gen.clos:
                row["message"] = "Không bóc tách được CLO từ file."
                results.append(row); continue
            outline = _write_generated_outline(
                db, match.id, gen, plo_by_code, user,
                {"imported": True, "source_name": file.filename},
            )
            row["outline_id"] = outline.id
            if run_qa:
                try:
                    qa = _run_outline_qa(db, outline.id)
                    row["score"] = qa.get("score")
                    row["errors"] = len(qa.get("errors") or [])
                    row["warnings"] = len(qa.get("warnings") or [])
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    row["message"] = f"Đã lưu nhưng chấm chất lượng lỗi: {e}"
            row["message"] = row["message"] or "OK"
        except Exception as e:  # noqa: BLE001
            # Quan trọng: rollback để 1 file lỗi KHÔNG làm hỏng session của các file sau.
            db.rollback()
            row["message"] = f"Lỗi: {e}"
        results.append(row)

    log_action(db, user.id, "outline", None, "bulk_import",
               {"program_id": program_id, "count": len(files)})
    return {"program_id": program_id, "results": results}


@router.get("/programs/{program_id}/outline-health")
def outline_health(program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Bảng 'sức khỏe đề cương toàn ngành': mỗi học phần + đề cương mới nhất + điểm chất lượng đã chấm."""
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(404, "Không tìm thấy chương trình")
    latest = _latest_outline_by_course(db, program_id)
    rows = []
    for c in db.query(Course).filter(Course.program_id == program_id).order_by(Course.id).all():
        o = latest.get(c.id)
        info = (o.general_info_json or {}) if o else {}
        rows.append({
            "course_id": c.id, "course_code": c.code, "course_name": c.name,
            "has_outline": o is not None,
            "outline_id": o.id if o else None,
            "version": o.version if o else None,
            "status": o.status if o else None,
            "qa_score": info.get("qa_score"),
            "qa_errors": info.get("qa_errors"),
            "qa_warnings": info.get("qa_warnings"),
            "qa_at": info.get("qa_at"),
            "imported": bool(info.get("imported")),
        })
    return {"program_id": program_id, "rows": rows}
