"""Bảng jobs (tác vụ AI nền) + llm_usage (token/chi phí) — Nhóm B.

Idempotent: chỉ tạo bảng/index nếu chưa tồn tại.

Revision ID: 8b2d4f6a1c3e
Revises: 7a1c9f2b3d4e
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b2d4f6a1c3e"
down_revision: Union[str, None] = "7a1c9f2b3d4e"
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    if not _has_table(insp, "jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("type", sa.String(100), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
            sa.Column("total", sa.Integer, nullable=False, server_default="0"),
            sa.Column("done", sa.Integer, nullable=False, server_default="0"),
            sa.Column("message", sa.String(500), nullable=True),
            sa.Column("params_json", sa.JSON, nullable=True),
            sa.Column("result_json", sa.JSON, nullable=True),
            sa.Column("error", sa.Text, nullable=True),
            sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id"), nullable=True),
            sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id"), nullable=True),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_jobs_type", "jobs", ["type"])
        op.create_index("ix_jobs_status", "jobs", ["status"])
        op.create_index("ix_jobs_program_status", "jobs", ["program_id", "status"])

    if not _has_table(insp, "llm_usage"):
        op.create_table(
            "llm_usage",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("provider", sa.String(50), nullable=False),
            sa.Column("model", sa.String(150), nullable=True),
            sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("est_cost_usd", sa.Float, nullable=False, server_default="0"),
            sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("program_id", sa.Integer, sa.ForeignKey("programs.id"), nullable=True),
            sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id"), nullable=True),
            sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_llm_usage_program_id", "llm_usage", ["program_id"])
        op.create_index("ix_llm_usage_created_at", "llm_usage", ["created_at"])
        op.create_index("ix_llm_usage_program_created", "llm_usage", ["program_id", "created_at"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if _has_table(insp, "llm_usage"):
        op.drop_table("llm_usage")
    if _has_table(insp, "jobs"):
        op.drop_table("jobs")
