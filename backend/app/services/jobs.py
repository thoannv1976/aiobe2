"""Hạ tầng tác vụ nền (job): request chỉ 'đặt việc', việc nặng chạy nền.

Chế độ chạy (enqueue):
- Cloud Tasks (prod nhiều instance): nếu đặt cloud_tasks_queue + worker_base_url → tạo task
  gọi lại POST /api/jobs/{id}/run (worker).
- Inline (test/dev/single-instance): nếu jobs_inline=True → chạy ngay, đồng bộ.
- Mặc định: chạy trong một thread daemon của tiến trình hiện tại.

Handler đăng ký qua @register("job_type"); nhận (db, job) và cập nhật tiến độ bằng set_progress().
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from app.config import settings
from app.core.llm_context import llm_scope
from app.database import SessionLocal
from app.models import Job

_log = logging.getLogger("uvicorn.error")

HANDLERS: dict[str, Callable] = {}


def register(job_type: str):
    def deco(fn: Callable):
        HANDLERS[job_type] = fn
        return fn
    return deco


def create_job(db, job_type: str, params: dict, user_id=None,
               program_id=None, course_id=None, total: int = 0) -> Job:
    job = Job(
        type=job_type, status="pending", params_json=params or {},
        total=total, created_by=user_id, program_id=program_id, course_id=course_id,
        message="Đã tiếp nhận, chờ xử lý...",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def set_progress(db, job: Job, done: int, total: int, message: str | None = None) -> None:
    job.done = done
    job.total = total
    job.progress = int(done * 100 / total) if total else 0
    if message is not None:
        job.message = message[:500]
    db.commit()


def run_job(job_id: int) -> None:
    """Thực thi job trong session riêng (an toàn cho thread/worker)."""
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or job.status in ("running", "done"):
            return
        # Cô lập dữ liệu theo tenant của job (worker chạy ngoài request HTTP).
        if job.tenant_id is not None:
            db.info["tenant_id"] = job.tenant_id
        job.status = "running"
        job.message = "Đang xử lý..."
        db.commit()
        handler = HANDLERS.get(job.type)
        if not handler:
            job.status = "error"
            job.error = f"Không có handler cho job '{job.type}'"
            db.commit()
            return
        with llm_scope(user_id=job.created_by, program_id=job.program_id,
                       course_id=job.course_id, job_id=job.id, tenant_id=job.tenant_id):
            result = handler(db, job)
        job.status = "done"
        job.progress = 100
        job.result_json = result or {}
        job.message = "Hoàn tất"
        db.commit()
    except Exception as e:  # noqa: BLE001
        _log.warning("Job %s lỗi: %s", job_id, e)
        db.rollback()
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "error"
                job.error = str(e)[:2000]
                job.message = "Lỗi"
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def _create_cloud_task(job_id: int) -> None:
    from google.cloud import tasks_v2  # import lười

    client = tasks_v2.CloudTasksClient()
    url = f"{settings.worker_base_url.rstrip('/')}/api/jobs/{job_id}/run"
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"X-Job-Token": settings.job_worker_token},
        }
    }
    client.create_task(parent=settings.cloud_tasks_queue, task=task)


def enqueue(job_id: int) -> None:
    """Đưa job vào hàng đợi xử lý theo chế độ cấu hình."""
    if settings.jobs_inline:
        run_job(job_id)
        return
    if settings.cloud_tasks_queue and settings.worker_base_url:
        try:
            _create_cloud_task(job_id)
            return
        except Exception as e:  # noqa: BLE001
            _log.warning("Tạo Cloud Task thất bại (%s) → chạy nền bằng thread.", e)
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()


# Đăng ký các handler (import để nạp vào HANDLERS).
from app.services import job_handlers  # noqa: E402,F401
