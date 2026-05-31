"""Schema cho đề cương sinh bằng AI (SPEC 4.3, chuẩn AUN-QA constructive alignment).

AI trả JSON khớp schema này; validate bằng Pydantic trước khi ghi CSDL (human-in-the-loop).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenCloPlo(BaseModel):
    plo_code: str
    level: str = "R"  # I|R|M


class GenClo(BaseModel):
    code: str
    description: str  # tiếng Việt
    description_en: str = ""  # bản dịch tiếng Anh đầy đủ (song ngữ AUN-QA)
    bloom_level: str = ""
    plos: list[GenCloPlo] = Field(default_factory=list)


class GenRubricCriterion(BaseModel):
    """Một tiêu chí trong rubric chấm điểm."""
    name: str  # tên tiêu chí
    weight_percent: float = 0  # trọng số trong cấu phần
    levels: list[str] = Field(default_factory=list)  # mô tả các mức (giỏi→kém)


class GenAssessment(BaseModel):
    name: str
    type: str = ""
    weight_percent: float = 0
    clo_codes: list[str] = Field(default_factory=list)
    rubric: list[GenRubricCriterion] = Field(default_factory=list)


class GenLesson(BaseModel):
    week: int = 1
    topic: str = ""
    clo_codes: list[str] = Field(default_factory=list)


class GeneratedOutline(BaseModel):
    description: str = ""
    teaching_methods: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    clos: list[GenClo] = Field(default_factory=list)
    assessments: list[GenAssessment] = Field(default_factory=list)
    lessons: list[GenLesson] = Field(default_factory=list)
