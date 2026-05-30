from pydantic import BaseModel, Field


class ChapterBase(BaseModel):
    order: int = 1
    title: str
    content_richtext: str | None = None


class ChapterCreate(ChapterBase):
    clo_ids: list[int] = Field(default_factory=list)


class ChapterOut(ChapterBase):
    id: int
    textbook_id: int
    clo_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TextbookBase(BaseModel):
    title: str


class TextbookCreate(TextbookBase):
    course_id: int


class TextbookOut(TextbookBase):
    id: int
    course_id: int
    version: int
    status: str

    class Config:
        from_attributes = True
