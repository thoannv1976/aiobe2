"""Phân công phụ trách: gán user vào CTĐT/học phần (SPEC 3 — RBAC theo phạm vi)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.database import get_db
from app.models import Assignment, Course, Program, Role, User
from app.services.audit import log_action

router = APIRouter(prefix="/api", tags=["assignments"])
MANAGER = require_roles(Role.PROGRAM_MANAGER)


class AssignmentIn(BaseModel):
    user_id: int
    program_id: int | None = None
    course_id: int | None = None
    role: str


class AssignmentOut(AssignmentIn):
    id: int

    class Config:
        from_attributes = True


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(
    user_id: int | None = None,
    program_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(MANAGER),
):
    q = db.query(Assignment)
    if user_id:
        q = q.filter(Assignment.user_id == user_id)
    if program_id:
        q = q.filter(Assignment.program_id == program_id)
    return q.all()


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def create_assignment(payload: AssignmentIn, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    if not db.get(User, payload.user_id):
        raise HTTPException(404, "Không tìm thấy người dùng")
    if payload.program_id and not db.get(Program, payload.program_id):
        raise HTTPException(404, "Không tìm thấy CTĐT")
    if payload.course_id and not db.get(Course, payload.course_id):
        raise HTTPException(404, "Không tìm thấy học phần")
    obj = Assignment(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "assignment", obj.id, "create", payload.model_dump())
    return obj


@router.delete("/assignments/{aid}", status_code=204)
def delete_assignment(aid: int, db: Session = Depends(get_db), user: User = Depends(MANAGER)):
    obj = db.get(Assignment, aid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "assignment", aid, "delete")
