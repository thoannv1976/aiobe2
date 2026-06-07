"""Ngữ cảnh gọi LLM (contextvars) để gắn usage/chi phí vào đúng phạm vi.

Endpoint nặng bọc lời gọi AI bằng `with llm_scope(program_id=..., course_id=..., user_id=...):`
để hệ thống ghi nhận token/chi phí theo chương trình/học phần và áp hạn mức.
"""
from __future__ import annotations

import contextlib
import contextvars

_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("llm_ctx", default={})
# Tenant của REQUEST hiện tại (đặt trong get_current_user) — để lớp LLM chọn ĐÚNG key/quota
# của trường cho cả những lời gọi không bọc llm_scope. Job nền dùng llm_scope(tenant_id=...).
_request_tenant: contextvars.ContextVar[int | None] = contextvars.ContextVar("req_tenant", default=None)


def set_request_tenant(tenant_id: int | None) -> None:
    _request_tenant.set(tenant_id)


def current_tenant() -> int | None:
    """Tenant áp dụng cho lời gọi LLM: ưu tiên llm_scope, sau đó tenant của request."""
    return _ctx.get().get("tenant_id") or _request_tenant.get()


@contextlib.contextmanager
def llm_scope(user_id=None, program_id=None, course_id=None, job_id=None, tenant_id=None):
    token = _ctx.set({
        "user_id": user_id, "program_id": program_id,
        "course_id": course_id, "job_id": job_id, "tenant_id": tenant_id,
    })
    try:
        yield
    finally:
        _ctx.reset(token)


def current_scope() -> dict:
    return dict(_ctx.get())
