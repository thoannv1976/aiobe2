"""Nhóm C — Pha C2: NOT NULL tenant_id + Row-Level Security + email unique theo tenant.

CHỈ áp dụng trên PostgreSQL (production). Trên SQLite (dev/test) → BỎ QUA (no-op),
vì test dùng create_all theo model và SQLite không hỗ trợ RLS.

RLS dùng chính sách "permissive-when-unset": khi chưa SET app.tenant_id (vd lúc đăng nhập/
bootstrap/migration) thì cho phép; khi đã set (request đã xác thực) thì chặn chéo tenant.
=> Lớp chặn cuối ở tầng DB, kết hợp auto-filter ở tầng app (C1).

⚠️ Cần kiểm thử trên Postgres staging trước khi tin dùng (môi trường dev hiện tại là SQLite).

Revision ID: a1f2e3d4c5b6
Revises: 9c3e5a7b1d2f
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f2e3d4c5b6"
down_revision: Union[str, None] = "9c3e5a7b1d2f"
branch_labels = None
depends_on = None

TABLES = [
    "users", "assignments", "programs", "plos", "pis", "courses", "course_plo",
    "course_outlines", "clos", "clo_plo", "assessments", "assessment_clo",
    "lesson_plans", "lesson_plan_clo", "textbooks", "chapters", "chapter_clo",
    "questions", "exam_matrices", "exams", "exam_question", "documents",
    "extractions", "audit_logs", "api_keys", "lectures", "llm_usage", "jobs",
]

_POLICY = """
DO $$
BEGIN
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', '{t}');
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', '{t}');
  EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', '{t}');
  EXECUTE format(
    'CREATE POLICY tenant_isolation ON %I USING (%s) WITH CHECK (%s)', '{t}',
    'current_setting(''app.tenant_id'', true) IS NULL OR current_setting(''app.tenant_id'', true) = '''' OR tenant_id = current_setting(''app.tenant_id'', true)::int',
    'current_setting(''app.tenant_id'', true) IS NULL OR current_setting(''app.tenant_id'', true) = '''' OR tenant_id = current_setting(''app.tenant_id'', true)::int'
  );
END $$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite/dev: bỏ qua (dùng create_all theo model)

    default_id = bind.execute(sa.text("SELECT id FROM tenants WHERE code='default'")).scalar() or 1

    for t in TABLES:
        # 1) Vá nốt mọi tenant_id còn NULL → tenant mặc định, rồi đặt NOT NULL.
        op.execute(sa.text(f"UPDATE {t} SET tenant_id = :d WHERE tenant_id IS NULL")
                   .bindparams(d=default_id))
        op.execute(f"ALTER TABLE {t} ALTER COLUMN tenant_id SET NOT NULL")
        # 2) Bật RLS + policy cô lập tenant.
        op.execute(_POLICY.format(t=t))

    # 3) Email duy nhất theo (tenant_id, email) thay vì toàn cục.
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    op.execute(
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_tenant_email; "
        "ALTER TABLE users ADD CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_tenant_email")
    for t in TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {t}")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} ALTER COLUMN tenant_id DROP NOT NULL")
