from pydantic import BaseModel, Field, field_validator


# ---- Question ----
class QuestionBase(BaseModel):
    clo_id: int | None = None
    bloom_level: str = ""
    difficulty: str = ""
    type: str = ""
    content: str = ""
    options_json: list = Field(default_factory=list)
    answer: str | None = None
    points: float = 1
    explanation: str | None = None
    tags_json: list = Field(default_factory=list)
    chapter: str | None = None
    learning_resource: str | None = None
    rubric_json: dict = Field(default_factory=dict)

    # Dữ liệu cũ có thể có JSON = NULL trong DB → chuyển None về default để serialize OK.
    @field_validator("options_json", "tags_json", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v if isinstance(v, list) else []

    @field_validator("rubric_json", mode="before")
    @classmethod
    def _none_to_dict(cls, v):
        return v if isinstance(v, dict) else {}

    @field_validator("bloom_level", "difficulty", "type", "content", mode="before")
    @classmethod
    def _none_to_str(cls, v):
        return v if isinstance(v, str) else ("" if v is None else str(v))


class QuestionCreate(QuestionBase):
    pass


class QuestionOut(QuestionBase):
    id: int
    course_id: int
    review_status: str = "draft"
    review_note: str | None = None

    @field_validator("review_status", mode="before")
    @classmethod
    def _status_default(cls, v):
        return v if isinstance(v, str) and v else "draft"

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
    assessment_id: int | None = None


class ExamMatrixOut(BaseModel):
    id: int
    course_id: int
    name: str
    cells: list[MatrixCell] = Field(default_factory=list)
    status: str = "draft"
    total_points: float = 10
    assessment_id: int | None = None

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
