"""Toàn bộ bảng dữ liệu (SQLAlchemy 2.0 ORM).

Bám theo SPEC mục 5. JSON dùng kiểu SQLAlchemy JSON (portable SQLite/Postgres).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Người dùng & phân quyền (RBAC theo vai trò + phạm vi)
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="lecturer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Assignment(Base):
    """Phạm vi phụ trách: gán user vào program hoặc course."""
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id"), nullable=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(50))

    user: Mapped[User] = relationship(back_populates="assignments")


# ---------------------------------------------------------------------------
# CTĐT & chuẩn đầu ra
# ---------------------------------------------------------------------------
class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(500))
    code: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    faculty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    plos: Mapped[list[Plo]] = relationship(back_populates="program", cascade="all, delete-orphan")
    courses: Mapped[list[Course]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class Plo(Base):
    __tablename__ = "plos"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bloom_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    program: Mapped[Program] = relationship(back_populates="plos")
    pis: Mapped[list[Pi]] = relationship(back_populates="plo", cascade="all, delete-orphan")


class Pi(Base):
    __tablename__ = "pis"

    id: Mapped[int] = mapped_column(primary_key=True)
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)

    plo: Mapped[Plo] = relationship(back_populates="pis")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(500))
    credits: Mapped[int] = mapped_column(Integer, default=3)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="core")
    prerequisites_json: Mapped[list] = mapped_column(JSON, default=list)

    program: Mapped[Program] = relationship(back_populates="courses")
    course_plos: Mapped[list[CoursePlo]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    outlines: Mapped[list[CourseOutline]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class CoursePlo(Base):
    """Ma trận Học phần × PLO (mức I/R/M)."""
    __tablename__ = "course_plo"
    __table_args__ = (UniqueConstraint("course_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id", ondelete="CASCADE"))
    level: Mapped[str] = mapped_column(String(10))  # I|R|M

    course: Mapped[Course] = relationship(back_populates="course_plos")


# ---------------------------------------------------------------------------
# Đề cương học phần
# ---------------------------------------------------------------------------
class CourseOutline(Base):
    __tablename__ = "course_outlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    general_info_json: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    teaching_methods_json: Mapped[list] = mapped_column(JSON, default=list)
    references_json: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    course: Mapped[Course] = relationship(back_populates="outlines")
    clos: Mapped[list[Clo]] = relationship(back_populates="outline", cascade="all, delete-orphan")
    assessments: Mapped[list[Assessment]] = relationship(
        back_populates="outline", cascade="all, delete-orphan"
    )
    lesson_plans: Mapped[list[LessonPlan]] = relationship(
        back_populates="outline", cascade="all, delete-orphan"
    )


class Clo(Base):
    __tablename__ = "clos"

    id: Mapped[int] = mapped_column(primary_key=True)
    outline_id: Mapped[int] = mapped_column(ForeignKey("course_outlines.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    bloom_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    outline: Mapped[CourseOutline] = relationship(back_populates="clos")
    clo_plos: Mapped[list[CloPlo]] = relationship(
        back_populates="clo", cascade="all, delete-orphan"
    )


class CloPlo(Base):
    """Ma trận CLO × PLO kèm mức đóng góp."""
    __tablename__ = "clo_plo"
    __table_args__ = (UniqueConstraint("clo_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"))
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id", ondelete="CASCADE"))
    contribution_level: Mapped[str] = mapped_column(String(10))  # I|R|M

    clo: Mapped[Clo] = relationship(back_populates="clo_plos")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    outline_id: Mapped[int] = mapped_column(ForeignKey("course_outlines.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_percent: Mapped[float] = mapped_column(Float, default=0)
    rubric_json: Mapped[dict] = mapped_column(JSON, default=dict)

    outline: Mapped[CourseOutline] = relationship(back_populates="assessments")
    assessment_clos: Mapped[list[AssessmentClo]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentClo(Base):
    __tablename__ = "assessment_clo"
    __table_args__ = (UniqueConstraint("assessment_id", "clo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"))

    assessment: Mapped[Assessment] = relationship(back_populates="assessment_clos")


class LessonPlan(Base):
    __tablename__ = "lesson_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    outline_id: Mapped[int] = mapped_column(ForeignKey("course_outlines.id", ondelete="CASCADE"))
    week: Mapped[int] = mapped_column(Integer, default=1)
    topic: Mapped[str] = mapped_column(String(500))
    activities_json: Mapped[dict] = mapped_column(JSON, default=dict)

    outline: Mapped[CourseOutline] = relationship(back_populates="lesson_plans")
    lesson_plan_clos: Mapped[list[LessonPlanClo]] = relationship(
        back_populates="lesson_plan", cascade="all, delete-orphan"
    )


class LessonPlanClo(Base):
    __tablename__ = "lesson_plan_clo"
    __table_args__ = (UniqueConstraint("lesson_plan_id", "clo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_plan_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_plans.id", ondelete="CASCADE")
    )
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"))

    lesson_plan: Mapped[LessonPlan] = relationship(back_populates="lesson_plan_clos")


# ---------------------------------------------------------------------------
# Giáo trình / tài liệu học phần
# ---------------------------------------------------------------------------
class Textbook(Base):
    __tablename__ = "textbooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="textbook", cascade="all, delete-orphan"
    )


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    textbook_id: Mapped[int] = mapped_column(ForeignKey("textbooks.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(500))
    content_richtext: Mapped[str | None] = mapped_column(Text, nullable=True)

    textbook: Mapped[Textbook] = relationship(back_populates="chapters")
    chapter_clos: Mapped[list[ChapterClo]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )


class ChapterClo(Base):
    __tablename__ = "chapter_clo"
    __table_args__ = (UniqueConstraint("chapter_id", "clo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"))

    chapter: Mapped[Chapter] = relationship(back_populates="chapter_clos")


# ---------------------------------------------------------------------------
# Ngân hàng câu hỏi & đề thi
# ---------------------------------------------------------------------------
class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    clo_id: Mapped[int | None] = mapped_column(ForeignKey("clos.id"), nullable=True)
    bloom_level: Mapped[str] = mapped_column(String(50))
    difficulty: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    options_json: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=1)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    course: Mapped[Course] = relationship(back_populates="questions")


class ExamMatrix(Base):
    __tablename__ = "exam_matrices"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    # cells: [{clo_id, bloom_level, difficulty, count, points_each}]
    cells_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft|review|approved|archived
    total_points: Mapped[float] = mapped_column(Float, default=10)  # thang điểm khai báo
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    exams: Mapped[list[Exam]] = relationship(
        back_populates="matrix", cascade="all, delete-orphan"
    )


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    matrix_id: Mapped[int | None] = mapped_column(ForeignKey("exam_matrices.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="Đề thi")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    total_points: Mapped[float] = mapped_column(Float, default=0)
    duration_min: Mapped[int] = mapped_column(Integer, default=90)
    variant_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    matrix: Mapped[ExamMatrix | None] = relationship(back_populates="exams")
    exam_questions: Mapped[list[ExamQuestion]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )


class ExamQuestion(Base):
    __tablename__ = "exam_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    order: Mapped[int] = mapped_column(Integer, default=1)
    variant: Mapped[int] = mapped_column(Integer, default=1)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    exam: Mapped[Exam] = relationship(back_populates="exam_questions")
    question: Mapped[Question] = relationship()


# ---------------------------------------------------------------------------
# Minh chứng / tài liệu gốc & audit
# ---------------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(1000))
    mime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Extraction(Base):
    """Kết quả trích xuất AI (chờ con người rà soát trước khi ghi vào CSDL)."""
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending|confirmed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    diff_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class ApiKey(Base):
    """Khóa API AI do admin cấu hình, dùng chung cho toàn hệ thống (SPEC vận hành).

    provider: 'anthropic' (Claude) hoặc 'openai'. Chỉ một khóa active tại một thời điểm.
    """
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50))  # anthropic | openai
    name: Mapped[str] = mapped_column(String(255), default="")
    api_key: Mapped[str] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Lecture(Base):
    """Bài giảng theo buổi, gắn học phần (SPEC mục 10). Nội dung Markdown do AI/giảng viên soạn."""
    __tablename__ = "lectures"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    session_no: Mapped[int] = mapped_column(Integer, default=1)  # buổi học
    title: Mapped[str] = mapped_column(String(500))
    content_richtext: Mapped[str | None] = mapped_column(Text, nullable=True)  # nội dung bài giảng
    slides_json: Mapped[list] = mapped_column(JSON, default=list)  # danh sách slide [{title, bullets}]
    clo_codes_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

