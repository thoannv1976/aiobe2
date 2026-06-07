"""Hằng số/enum nghiệp vụ dùng chung (lưu dạng string để DB-portable)."""
from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"     # Quản trị NỀN TẢNG (đa trường) — vận hành tenant
    ADMIN = "admin"                 # Admin của MỘT trường (tenant)
    PROGRAM_MANAGER = "program_manager"  # Trưởng khoa/bộ môn
    LECTURER = "lecturer"           # Giảng viên
    QA = "qa"                       # Cán bộ ĐBCL / Kiểm định
    GUEST = "guest"                 # Khách read-only


class BloomLevel(str, Enum):
    REMEMBER = "remember"      # Nhớ
    UNDERSTAND = "understand"  # Hiểu
    APPLY = "apply"            # Vận dụng
    ANALYZE = "analyze"        # Phân tích
    EVALUATE = "evaluate"      # Đánh giá
    CREATE = "create"          # Sáng tạo


BLOOM_ORDER = [
    BloomLevel.REMEMBER,
    BloomLevel.UNDERSTAND,
    BloomLevel.APPLY,
    BloomLevel.ANALYZE,
    BloomLevel.EVALUATE,
    BloomLevel.CREATE,
]


class ContributionLevel(str, Enum):
    """Mức đóng góp CLO→PLO hoặc Course→PLO."""
    INTRODUCE = "I"
    REINFORCE = "R"
    MASTER = "M"


class PloCategory(str, Enum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ATTITUDE = "attitude"


class CourseType(str, Enum):
    CORE = "core"
    ELECTIVE = "elective"


class Difficulty(str, Enum):
    EASY = "easy"      # dễ
    MEDIUM = "medium"  # trung bình
    HARD = "hard"      # khó


class QuestionType(str, Enum):
    MCQ_SINGLE = "mcq_single"      # trắc nghiệm 1 đáp án
    MCQ_MULTI = "mcq_multi"        # trắc nghiệm nhiều đáp án
    FILL_BLANK = "fill_blank"      # điền khuyết
    SHORT_ANSWER = "short_answer"  # tự luận ngắn
    ESSAY = "essay"                # tự luận
    EXERCISE = "exercise"          # bài tập


class OutlineStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ExamStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"


class DocStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
