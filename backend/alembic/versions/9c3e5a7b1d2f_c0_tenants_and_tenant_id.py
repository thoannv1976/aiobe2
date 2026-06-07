"""Nhóm C — Pha C0: bảng tenants + cột tenant_id (nullable) cho mọi bảng + backfill tenant mặc định.

An toàn & idempotent: chỉ thêm cột/index/tenant nếu chưa có; KHÔNG đổi hành vi app (tenant_id còn nullable,
chưa enforce). Toàn bộ dữ liệu cũ được gán về 1 tenant mặc định.

Revision ID: 9c3e5a7b1d2f
Revises: 8b2d4f6a1c3e
Create Date: 2026-06-07
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c3e5a7b1d2f"
down_revision: Union[str, None] = "8b2d4f6a1c3e"
branch_labels = None
depends_on = None

# 28 bảng nghiệp vụ cần gắn tenant_id.
TABLES = [
    "users", "assignments", "programs", "plos", "pis", "courses", "course_plo",
    "course_outlines", "clos", "clo_plo", "assessments", "assessment_clo",
    "lesson_plans", "lesson_plan_clo", "textbooks", "chapters", "chapter_clo",
    "questions", "exam_matrices", "exams", "exam_question", "documents",
    "extractions", "audit_logs", "api_keys", "lectures", "llm_usage", "jobs",
]


def _cols(insp, t: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(t)} if insp.has_table(t) else set()


def _idx(insp, t: str) -> set[str]:
    return {i["name"] for i in insp.get_indexes(t)} if insp.has_table(t) else set()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Bảng tenants
    if not insp.has_table("tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("code", sa.String(50), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="active"),
            sa.Column("plan", sa.String(50), nullable=False, server_default="standard"),
            sa.Column("contact_email", sa.String(255), nullable=True),
            sa.Column("settings_json", sa.JSON, nullable=True),
            sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("activated_at", sa.DateTime, nullable=True),
            sa.Column("valid_until", sa.DateTime, nullable=True),
            sa.Column("max_programs", sa.Integer, nullable=True),
            sa.Column("max_users", sa.Integer, nullable=True),
            sa.Column("llm_daily_token_quota", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_tenants_code", "tenants", ["code"], unique=True)

    # 2) Tenant mặc định (chứa toàn bộ dữ liệu hiện có)
    default_id = bind.execute(
        sa.text("SELECT id FROM tenants WHERE code = 'default'")
    ).scalar()
    if not default_id:
        now = datetime.utcnow()
        bind.execute(
            sa.text(
                "INSERT INTO tenants (code, name, status, plan, is_enabled, "
                "activated_at, valid_until, created_at, updated_at) "
                "VALUES ('default', 'Trường mặc định', 'active', 'standard', :en, "
                ":act, :val, :now, :now)"
            ),
            {"en": True, "act": now, "val": now + timedelta(days=365), "now": now},
        )
        default_id = bind.execute(
            sa.text("SELECT id FROM tenants WHERE code = 'default'")
        ).scalar()

    # 3) Thêm tenant_id (nullable) + index + backfill cho từng bảng
    for t in TABLES:
        if not insp.has_table(t):
            continue
        if "tenant_id" not in _cols(insp, t):
            op.add_column(t, sa.Column("tenant_id", sa.Integer, nullable=True))
        ix = f"ix_{t}_tenant_id"
        if ix not in _idx(insp, t):
            op.create_index(ix, t, ["tenant_id"])
        # Gán toàn bộ dữ liệu cũ về tenant mặc định.
        op.execute(sa.text(f"UPDATE {t} SET tenant_id = :tid WHERE tenant_id IS NULL")
                   .bindparams(tid=default_id))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for t in TABLES:
        if "tenant_id" in _cols(insp, t):
            ix = f"ix_{t}_tenant_id"
            if ix in _idx(insp, t):
                op.drop_index(ix, table_name=t)
            op.drop_column(t, "tenant_id")
    if insp.has_table("tenants"):
        op.drop_table("tenants")
