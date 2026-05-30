from pydantic import BaseModel, Field


class CloBase(BaseModel):
    code: str
    description: str
    bloom_level: str | None = None


class CloCreate(CloBase):
    pass


class CloOut(CloBase):
    id: int
    outline_id: int

    class Config:
        from_attributes = True


class CloPloIn(BaseModel):
    clo_id: int
    plo_id: int
    contribution_level: str  # I|R|M


class CloPloOut(CloPloIn):
    id: int

    class Config:
        from_attributes = True


class AssessmentBase(BaseModel):
    name: str
    type: str | None = None
    weight_percent: float = 0
    rubric_json: dict = Field(default_factory=dict)


class AssessmentCreate(AssessmentBase):
    clo_ids: list[int] = Field(default_factory=list)


class AssessmentOut(AssessmentBase):
    id: int
    outline_id: int
    clo_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True


class LessonPlanBase(BaseModel):
    week: int = 1
    topic: str
    activities_json: dict = Field(default_factory=dict)


class LessonPlanCreate(LessonPlanBase):
    clo_ids: list[int] = Field(default_factory=list)


class LessonPlanOut(LessonPlanBase):
    id: int
    outline_id: int
    clo_ids: list[int] = Field(default_factory=list)

    class Config:
        from_attributes = True


class OutlineBase(BaseModel):
    description: str | None = None
    general_info_json: dict = Field(default_factory=dict)
    teaching_methods_json: list = Field(default_factory=list)
    references_json: list = Field(default_factory=list)


class OutlineCreate(OutlineBase):
    course_id: int


class OutlineOut(OutlineBase):
    id: int
    course_id: int
    version: int
    status: str

    class Config:
        from_attributes = True
