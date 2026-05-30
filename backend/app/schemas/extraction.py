"""Schema cho output trích xuất AI (SPEC 4.1). Ép & validate JSON từ LLM."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedProgram(BaseModel):
    name: str = ""
    code: str = ""
    level: str = ""
    year: int = 0
    faculty: str = ""


class ExtractedPlo(BaseModel):
    code: str
    description: str = ""
    category: str = ""  # knowledge|skill|attitude
    bloom_level: str = ""


class ExtractedPi(BaseModel):
    code: str
    plo_code: str
    description: str = ""


class ExtractedCourse(BaseModel):
    code: str = ""
    name: str = ""
    credits: int = 0
    semester: int = 0
    type: str = "core"  # core|elective
    prerequisites: list[str] = Field(default_factory=list)


class ExtractedCoursePlo(BaseModel):
    course_code: str = ""
    plo_code: str = ""
    level: str = ""  # I|R|M


class ExtractionPayload(BaseModel):
    """Schema cố định khớp với SPEC 4.1."""
    program: ExtractedProgram = Field(default_factory=ExtractedProgram)
    plos: list[ExtractedPlo] = Field(default_factory=list)
    pis: list[ExtractedPi] = Field(default_factory=list)
    courses: list[ExtractedCourse] = Field(default_factory=list)
    course_plo_matrix: list[ExtractedCoursePlo] = Field(default_factory=list)


class ExtractionOut(BaseModel):
    id: int
    document_id: int
    payload: ExtractionPayload
    status: str

    class Config:
        from_attributes = True
