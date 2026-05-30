from pydantic import BaseModel, Field


# ---- Program ----
class ProgramBase(BaseModel):
    name: str
    code: str
    level: str | None = None
    year: int | None = None
    faculty: str | None = None


class ProgramCreate(ProgramBase):
    pass


class ProgramOut(ProgramBase):
    id: int

    class Config:
        from_attributes = True


# ---- PLO ----
class PloBase(BaseModel):
    code: str
    description: str
    category: str | None = None
    bloom_level: str | None = None


class PloCreate(PloBase):
    pass


class PloOut(PloBase):
    id: int
    program_id: int

    class Config:
        from_attributes = True


# ---- PI ----
class PiBase(BaseModel):
    code: str
    description: str


class PiCreate(PiBase):
    plo_id: int


class PiOut(PiBase):
    id: int
    plo_id: int

    class Config:
        from_attributes = True


# ---- Course ----
class CourseBase(BaseModel):
    code: str
    name: str
    credits: int = 3
    semester: int | None = None
    type: str = "core"
    prerequisites_json: list[str] = Field(default_factory=list)


class CourseCreate(CourseBase):
    pass


class CourseOut(CourseBase):
    id: int
    program_id: int

    class Config:
        from_attributes = True


# ---- Course x PLO matrix ----
class CoursePloIn(BaseModel):
    course_id: int
    plo_id: int
    level: str  # I|R|M


class CoursePloOut(CoursePloIn):
    id: int

    class Config:
        from_attributes = True
