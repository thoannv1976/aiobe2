"""Thêm index hiệu năng cho các cột lọc/khóa ngoại trọng yếu (Nhóm A — chịu tải).

Idempotent: chỉ tạo index nào CHƯA tồn tại (an toàn khi DB đã có dữ liệu/đã chạy).

Revision ID: 7a1c9f2b3d4e
Revises: 6f032688d4ee
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a1c9f2b3d4e"
down_revision: Union[str, None] = "6f032688d4ee"
branch_labels = None
depends_on = None

# (tên index, bảng, [cột]) — tên khớp quy ước SQLAlchemy ix_<bảng>_<cột>.
INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_assignments_user_id", "assignments", ["user_id"]),
    ("ix_plos_program_id", "plos", ["program_id"]),
    ("ix_pis_plo_id", "pis", ["plo_id"]),
    ("ix_courses_program_id", "courses", ["program_id"]),
    ("ix_course_outlines_course_id", "course_outlines", ["course_id"]),
    ("ix_clos_outline_id", "clos", ["outline_id"]),
    ("ix_assessments_outline_id", "assessments", ["outline_id"]),
    ("ix_lesson_plans_outline_id", "lesson_plans", ["outline_id"]),
    ("ix_textbooks_course_id", "textbooks", ["course_id"]),
    ("ix_chapters_textbook_id", "chapters", ["textbook_id"]),
    ("ix_chapter_clo_clo_id", "chapter_clo", ["clo_id"]),
    ("ix_questions_course_id", "questions", ["course_id"]),
    ("ix_questions_clo_id", "questions", ["clo_id"]),
    ("ix_questions_review_status", "questions", ["review_status"]),
    ("ix_questions_course_review", "questions", ["course_id", "review_status"]),
    ("ix_questions_course_deleted", "questions", ["course_id", "is_deleted"]),
    ("ix_exam_matrices_course_id", "exam_matrices", ["course_id"]),
    ("ix_exams_course_id", "exams", ["course_id"]),
    ("ix_exams_matrix_id", "exams", ["matrix_id"]),
    ("ix_exam_question_exam_id", "exam_question", ["exam_id"]),
    ("ix_exam_question_question_id", "exam_question", ["question_id"]),
    ("ix_documents_type", "documents", ["type"]),
    ("ix_extractions_document_id", "extractions", ["document_id"]),
    ("ix_audit_logs_user_id", "audit_logs", ["user_id"]),
    ("ix_audit_logs_entity", "audit_logs", ["entity"]),
    ("ix_lectures_course_id", "lectures", ["course_id"]),
]


def _existing(insp, table: str) -> set[str]:
    try:
        return {ix["name"] for ix in insp.get_indexes(table)}
    except Exception:  # bảng có thể chưa tồn tại trên DB cũ
        return set()


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for name, table, cols in INDEXES:
        if name not in _existing(insp, table):
            op.create_index(name, table, cols)


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    for name, table, _cols in reversed(INDEXES):
        if name in _existing(insp, table):
            op.drop_index(name, table_name=table)
