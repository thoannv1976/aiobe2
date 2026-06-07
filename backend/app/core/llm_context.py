"""Ngữ cảnh gọi LLM (contextvars) để gắn usage/chi phí vào đúng phạm vi.

Endpoint nặng bọc lời gọi AI bằng `with llm_scope(program_id=..., course_id=..., user_id=...):`
để hệ thống ghi nhận token/chi phí theo chương trình/học phần và áp hạn mức.
"""
from __future__ import annotations

import contextlib
import contextvars

_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("llm_ctx", default={})


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
