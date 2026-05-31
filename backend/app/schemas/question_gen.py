"""Schema cho câu hỏi sinh bằng AI (SPEC 4.5).

AI trả JSON khớp schema này; validate bằng Pydantic trước khi ghi CSDL.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenQuestion(BaseModel):
    clo_code: str = ""           # mã CLO (ánh xạ sang clo_id khi ghi)
    bloom_level: str = "remember"
    difficulty: str = "medium"
    type: str = "mcq_single"
    content: str = ""
    options: list[str] = Field(default_factory=list)
    answer: str = ""
    points: float = 1
    explanation: str = ""


class GeneratedQuestions(BaseModel):
    questions: list[GenQuestion] = Field(default_factory=list)


class QuestionGenRequest(BaseModel):
    """Yêu cầu sinh câu hỏi: số lượng theo từng CLO×Bloom×độ khó hoặc tự do."""
    clo_ids: list[int] = Field(default_factory=list)   # giới hạn theo CLO; rỗng = mọi CLO
    num_per_clo: int = 3
    bloom_levels: list[str] = Field(default_factory=list)  # rỗng = AI tự chọn phù hợp
    difficulties: list[str] = Field(default_factory=list)  # rỗng = đa dạng
    question_type: str = "mcq_single"
    language: str = "vi"
