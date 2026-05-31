"""Schema cho giáo trình sinh bằng AI (SPEC 4.4)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenChapter(BaseModel):
    order: int = 1
    title: str = ""
    clo_codes: list[str] = Field(default_factory=list)
    summary: str = ""


class GeneratedChapterOutline(BaseModel):
    chapters: list[GenChapter] = Field(default_factory=list)
