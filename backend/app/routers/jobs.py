"""API tác vụ nền: theo dõi tiến độ + worker endpoint cho Cloud Tasks."""
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user, require_roles
from app.core.pagination import limit_param, offset_param, paginate
from app.database import get_db
from app.models import Job, Role, User
from app.services.jobs import run_job

router = APIRouter(prefix="/api", tags=["jobs"])
LECTURER = require_roles(Role.LECTURER, Role.PROGRAM_MANAGER)


def _job_out(j: Job) -> dict:
    return {
        "id": j.id, "type": j.type, "status": j.status, "progress": j.progress,
        "done": j.done, "total": j.total, "message": j.message,
        "result": j.result_json, "error": j.error,
        "program_id": j.program_id, "course_id": j.course_id,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "updated_at": j.updated_at.isoformat() if j.updated_at else None,
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Trạng thái + tiến độ một job (frontend poll để cập nhật thanh tiến độ)."""
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Không tìm thấy tác vụ")
    return _job_out(j)


@router.get("/jobs")
def list_jobs(
    response: Response,
    course_id: int | None = None,
    program_id: int | None = None,
    status: str | None = None,
    type: str | None = None,
    limit: int = limit_param(),
    offset: int = offset_param(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Liệt kê job (lọc theo học phần/chương trình/trạng thái/loại), phân trang."""
    q = db.query(Job)
    if course_id is not None:
        q = q.filter(Job.course_id == course_id)
    if program_id is not None:
        q = q.filter(Job.program_id == program_id)
    if status:
        q = q.filter(Job.status == status)
    if type:
        q = q.filter(Job.type == type)
    q = q.order_by(Job.id.desc())
    return [_job_out(j) for j in paginate(q, response, limit, offset)]


@router.post("/jobs/{job_id}/run")
def run_job_endpoint(
    job_id: int,
    x_job_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Worker endpoint do Cloud Tasks gọi lại để thực thi job.

    Bảo vệ bằng secret X-Job-Token (khớp settings.job_worker_token). Khi token chưa cấu hình,
    chỉ cho phép gọi nếu job đang ở trạng thái pending/running (tránh lạm dụng).
    """
    if settings.job_worker_token:
        if x_job_token != settings.job_worker_token:
            raise HTTPException(403, "Token worker không hợp lệ")
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Không tìm thấy tác vụ")
    run_job(job_id)
    db.refresh(j)
    return _job_out(j)
