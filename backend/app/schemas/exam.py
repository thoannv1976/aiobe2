from pydantic import BaseModel, Field


# ---- Question ----
class QuestionBase(BaseModel):
    clo_id: int | None = None
    bloom_level: str
    difficulty: str
    type: str
    content: str
    options_json: list = Field(default_factory=list)
    answer: str | None = None
    points: float = 1
    explanation: str | None = None
    tags_json: list = Field(default_factory=list)


class QuestionCreate(QuestionBase):
    pass


class QuestionOut(QuestionBase):
    id: int
    course_id: int

    class Config:
        from_attributes = True


# ---- Exam matrix ----
class MatrixCell(BaseModel):
    clo_id: int | None = None
    bloom_level: str
    difficulty: str
    count: int = 0
    points_each: float | None = None


class ExamMatrixCreate(BaseModel):
    name: str
    cells: list[MatrixCell] = Field(default_factory=list)
    total_points: float = 10


class ExamMatrixOut(BaseModel):
    id: int
    course_id: int
    name: str
    cells: list[MatrixCell] = Field(default_factory=list)
    status: str = "draft"
    total_points: float = 10

    class Config:
        from_attributes = True


# ---- Exam ----
class ExamGenerateIn(BaseModel):
    matrix_id: int
    name: str = "Đề thi"
    duration_min: int = 90
    variant_count: int = 1
    seed: int | None = None
    # Cho phép sinh đề với số câu bốc được khi ngân hàng thiếu (best-effort).
    allow_partial: bool = False


class ExamOut(BaseModel):
    id: int
    course_id: int
    matrix_id: int | None
    name: str
    version: int
    status: str
    total_points: float
    duration_min: int
    variant_count: int

    class Config:
        from_attributes = True
