from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Course, CoursePlo, Pi, Plo, Program, Role, User
from app.schemas.program import (
    CourseCreate,
    CourseOut,
    CoursePloIn,
    CoursePloOut,
    PiCreate,
    PiOut,
    PloCreate,
    PloOut,
    ProgramCreate,
    ProgramOut,
)
from app.services.alignment import check_program_plo_coverage
from app.services.audit import log_action

router = APIRouter(prefix="/api", tags=["program"])

MANAGER = require_roles(Role.PROGRAM_MANAGER)


# --------------------------- Programs ---------------------------
@router.get("/programs", response_model=list[ProgramOut])
def list_programs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Program).filter(Program.is_deleted == False).all()  # noqa: E712


@router.post("/programs", response_model=ProgramOut, status_code=201)
def create_program(
    payload: ProgramCreate, db: Session = Depends(get_db), user: User = Depends(MANAGER)
):
    obj = Program(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "program", obj.id, "create")
    return obj


@router.get("/programs/{program_id}", response_model=ProgramOut)
def get_program(program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    obj = db.get(Program, program_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    return obj


@router.delete("/programs/{program_id}", status_code=204)
def delete_program(program_id: int, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    obj = db.get(Program, program_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy CTĐT")
    obj.is_deleted = True  # soft delete (SPEC 7)
    db.commit()
    log_action(db, user.id, "program", program_id, "soft_delete")


# --------------------------- PLO ---------------------------
@router.get("/programs/{program_id}/plos", response_model=list[PloOut])
def list_plos(program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Plo).filter(Plo.program_id == program_id).all()


@router.post("/programs/{program_id}/plos", response_model=PloOut, status_code=201)
def create_plo(
    program_id: int, payload: PloCreate, db: Session = Depends(get_db), user: User = Depends(MANAGER)
):
    if not db.get(Program, program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    obj = Plo(program_id=program_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "plo", obj.id, "create")
    return obj


@router.delete("/plos/{plo_id}", status_code=204)
def delete_plo(plo_id: int, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    obj = db.get(Plo, plo_id)
    if not obj:
        raise HTTPException(404, "Không tìm thấy PLO")
    db.delete(obj)
    db.commit()
    log_action(db, user.id, "plo", plo_id, "delete")


# --------------------------- PI ---------------------------
@router.get("/plos/{plo_id}/pis", response_model=list[PiOut])
def list_pis(plo_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Pi).filter(Pi.plo_id == plo_id).all()


@router.post("/pis", response_model=PiOut, status_code=201)
def create_pi(payload: PiCreate, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    if not db.get(Plo, payload.plo_id):
        raise HTTPException(404, "PI phải thuộc một PLO hợp lệ")
    obj = Pi(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "pi", obj.id, "create")
    return obj


# --------------------------- Courses ---------------------------
@router.get("/programs/{program_id}/courses", response_model=list[CourseOut])
def list_courses(program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Course).filter(Course.program_id == program_id).all()


@router.post("/programs/{program_id}/courses", response_model=CourseOut, status_code=201)
def create_course(
    program_id: int,
    payload: CourseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(MANAGER),
):
    if not db.get(Program, program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    obj = Course(program_id=program_id, **payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "course", obj.id, "create")
    return obj


# --------------------------- Course x PLO matrix ---------------------------
@router.get("/programs/{program_id}/course-plo", response_model=list[CoursePloOut])
def get_course_plo_matrix(
    program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    course_ids = [c.id for c in db.query(Course).filter(Course.program_id == program_id).all()]
    if not course_ids:
        return []
    return db.query(CoursePlo).filter(CoursePlo.course_id.in_(course_ids)).all()


@router.put("/course-plo", response_model=CoursePloOut)
def upsert_course_plo(
    payload: CoursePloIn, db: Session = Depends(get_db), user: User = Depends(MANAGER)
):
    obj = (
        db.query(CoursePlo)
        .filter(CoursePlo.course_id == payload.course_id, CoursePlo.plo_id == payload.plo_id)
        .first()
    )
    if obj:
        obj.level = payload.level
    else:
        obj = CoursePlo(**payload.model_dump())
        db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "course_plo", obj.id, "upsert", {"level": payload.level})
    return obj


@router.delete("/course-plo/{cp_id}", status_code=204)
def delete_course_plo(cp_id: int, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    obj = db.get(CoursePlo, cp_id)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "course_plo", cp_id, "delete")


# --------------------------- Coverage check ---------------------------
@router.get("/programs/{program_id}/coverage")
def program_coverage(
    program_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Kiểm tra mỗi PLO có học phần Master (M) — SPEC 4.2."""
    return check_program_plo_coverage(db, program_id).to_dict()


# --------------------------- AI: chuẩn hóa PLO (SPEC bước 2) ---------------------------
@router.post("/programs/{program_id}/review-plos")
def review_plos(program_id: int, db: Session = Depends(get_db), _: User = Depends(MANAGER)):
    """AI rà soát & chuẩn hóa PLO: đo được không, Bloom, gợi ý viết lại (SPEC mục 14)."""
    from app.services.qa_review import review_plos_ai

    if not db.get(Program, program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    plos = db.query(Plo).filter(Plo.program_id == program_id).all()
    if not plos:
        raise HTTPException(400, "Chương trình chưa có PLO để rà soát")
    try:
        return review_plos_ai(
            [{"code": p.code, "description": p.description,
              "category": p.category or "", "bloom_level": p.bloom_level or ""} for p in plos]
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Rà soát PLO thất bại: {e}")
