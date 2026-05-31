from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

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
    OutlineCreate,
    OutlineOut,
)
from app.services.alignment import check_outline_alignment
from app.services.audit import log_action
from app.services.diff import diff_outlines
from app.services.exports import outline_to_docx
from app.services.outline_ai import generate_outline_ai

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

    # Ghi ra đề cương DRAFT (phiên bản mới nhất + 1).
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
        general_info_json={"generated_by_ai": True},
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
    log_action(db, user.id, "outline", outline.id, "generate_ai", {"course_id": course_id})
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
def update_outline(outline_id: int, payload: OutlineCreate, db: Session = Depends(get_db), user: User = Depends(LECTURER)):
    """Cập nhật thông tin chung đề cương (chỉ khi chưa Published)."""
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
