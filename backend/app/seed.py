"""Seed dữ liệu mẫu: 1 CTĐT có 3 PLO và 5 học phần + 1 đề cương đầy đủ + ngân hàng câu hỏi.

Chạy: DATABASE_URL=sqlite:///./dev.db python -m app.seed
"""
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    Assessment,
    AssessmentClo,
    Clo,
    CloPlo,
    Course,
    CourseOutline,
    CoursePlo,
    Exam,
    ExamMatrix,
    LessonPlan,
    LessonPlanClo,
    Pi,
    Plo,
    Program,
    Question,
    User,
)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta

        from app.core.tenant import set_default_tenant_id
        from app.models import Tenant

        existing_data = db.query(User).count() > 0

        # --- Tenant mặc định (LUÔN đảm bảo tồn tại, kể cả khi DB đã có dữ liệu) ---
        tenant = db.query(Tenant).filter(Tenant.code == "default").execution_options(skip_tenant=True).first()
        if not tenant:
            now = datetime.utcnow()
            tenant = Tenant(
                code="default", name="Trường mặc định", is_enabled=True,
                activated_at=now, valid_until=now + timedelta(days=365),
            )
            db.add(tenant)
            db.flush()
        db.info["tenant_id"] = tenant.id
        set_default_tenant_id(tenant.id)

        # --- Super-Admin nền tảng (LUÔN đảm bảo tồn tại để vận hành đa trường) ---
        if not db.query(User).filter(User.email == "super@obe.vn").execution_options(skip_tenant=True).first():
            db.add(User(name="Super Admin", email="super@obe.vn",
                        password_hash=hash_password("super123"), role="super_admin",
                        tenant_id=tenant.id))

        # Nếu DB đã có dữ liệu (production) → chỉ bổ sung tenant mặc định + super-admin rồi dừng.
        if existing_data:
            db.commit()
            print("Đã có dữ liệu — đảm bảo tenant mặc định + super-admin (super@obe.vn/super123).")
            return

        # --- Người dùng mẫu (chỉ khi seed lần đầu) ---
        users = [
            User(name="Quản trị", email="admin@obe.vn", password_hash=hash_password("admin123"), role="admin"),
            User(name="Trưởng khoa", email="manager@obe.vn", password_hash=hash_password("manager123"), role="program_manager"),
            User(name="Giảng viên A", email="lecturer@obe.vn", password_hash=hash_password("lecturer123"), role="lecturer"),
            User(name="Cán bộ ĐBCL", email="qa@obe.vn", password_hash=hash_password("qa123"), role="qa"),
        ]
        db.add_all(users)
        db.flush()

        # --- CTĐT ---
        prog = Program(
            name="Cử nhân Công nghệ Thông tin", code="CNTT2024",
            level="Đại học", year=2024, faculty="Khoa CNTT",
        )
        db.add(prog)
        db.flush()

        # --- 3 PLO ---
        plos = [
            Plo(program_id=prog.id, code="PLO1", description="Áp dụng kiến thức nền tảng toán và khoa học máy tính.", category="knowledge", bloom_level="apply"),
            Plo(program_id=prog.id, code="PLO2", description="Thiết kế và phát triển giải pháp phần mềm.", category="skill", bloom_level="create"),
            Plo(program_id=prog.id, code="PLO3", description="Làm việc nhóm và giao tiếp chuyên nghiệp, có đạo đức nghề nghiệp.", category="attitude", bloom_level="evaluate"),
        ]
        db.add_all(plos)
        db.flush()

        # --- PI ---
        db.add_all([
            Pi(plo_id=plos[0].id, code="PI1.1", description="Vận dụng cấu trúc dữ liệu và giải thuật."),
            Pi(plo_id=plos[0].id, code="PI1.2", description="Áp dụng toán rời rạc vào bài toán máy tính."),
            Pi(plo_id=plos[1].id, code="PI2.1", description="Phân tích yêu cầu và thiết kế hệ thống."),
            Pi(plo_id=plos[2].id, code="PI3.1", description="Trình bày và bảo vệ giải pháp trước nhóm."),
        ])

        # --- 5 học phần ---
        courses = [
            Course(program_id=prog.id, code="IT101", name="Nhập môn Lập trình", credits=3, semester=1, type="core"),
            Course(program_id=prog.id, code="IT102", name="Cấu trúc dữ liệu & Giải thuật", credits=4, semester=2, type="core"),
            Course(program_id=prog.id, code="IT201", name="Cơ sở dữ liệu", credits=3, semester=3, type="core"),
            Course(program_id=prog.id, code="IT202", name="Công nghệ phần mềm", credits=3, semester=4, type="core"),
            Course(program_id=prog.id, code="IT301", name="Trí tuệ nhân tạo", credits=3, semester=5, type="elective"),
        ]
        db.add_all(courses)
        db.flush()

        # --- Ma trận Học phần × PLO ---
        matrix = [
            (courses[0], plos[0], "I"), (courses[1], plos[0], "M"), (courses[1], plos[1], "R"),
            (courses[2], plos[0], "R"), (courses[2], plos[1], "M"), (courses[3], plos[1], "M"),
            (courses[3], plos[2], "R"), (courses[4], plos[0], "R"), (courses[4], plos[2], "M"),
        ]
        for c, p, lv in matrix:
            db.add(CoursePlo(course_id=c.id, plo_id=p.id, level=lv))

        # --- Đề cương cho IT102 ---
        outline = CourseOutline(
            course_id=courses[1].id, version=1, status="draft",
            description="Học phần trang bị kiến thức về cấu trúc dữ liệu và phân tích giải thuật.",
            general_info_json={"language": "vi", "prerequisite": "IT101"},
            teaching_methods_json=["Thuyết giảng", "Thực hành lab", "Dự án nhóm"],
            references_json=["Cormen, Introduction to Algorithms"],
            created_by=users[2].id,
        )
        db.add(outline)
        db.flush()

        clos = [
            Clo(outline_id=outline.id, code="CLO1", description="Mô tả các cấu trúc dữ liệu cơ bản.", bloom_level="understand"),
            Clo(outline_id=outline.id, code="CLO2", description="Cài đặt giải thuật sắp xếp/tìm kiếm.", bloom_level="apply"),
            Clo(outline_id=outline.id, code="CLO3", description="Phân tích độ phức tạp giải thuật.", bloom_level="analyze"),
        ]
        db.add_all(clos)
        db.flush()

        # CLO × PLO
        db.add_all([
            CloPlo(clo_id=clos[0].id, plo_id=plos[0].id, contribution_level="I"),
            CloPlo(clo_id=clos[1].id, plo_id=plos[0].id, contribution_level="M"),
            CloPlo(clo_id=clos[2].id, plo_id=plos[1].id, contribution_level="R"),
        ])

        # Đánh giá (tổng 100%)
        a1 = Assessment(outline_id=outline.id, name="Bài tập lab", type="lab", weight_percent=30)
        a2 = Assessment(outline_id=outline.id, name="Giữa kỳ", type="exam", weight_percent=30)
        a3 = Assessment(outline_id=outline.id, name="Cuối kỳ", type="exam", weight_percent=40)
        db.add_all([a1, a2, a3])
        db.flush()
        db.add_all([
            AssessmentClo(assessment_id=a1.id, clo_id=clos[1].id),
            AssessmentClo(assessment_id=a2.id, clo_id=clos[0].id),
            AssessmentClo(assessment_id=a2.id, clo_id=clos[1].id),
            AssessmentClo(assessment_id=a3.id, clo_id=clos[2].id),
            AssessmentClo(assessment_id=a3.id, clo_id=clos[1].id),
        ])

        # Buổi dạy
        for wk, (topic, clo) in enumerate(
            [("Mảng & danh sách liên kết", clos[0]), ("Ngăn xếp & hàng đợi", clos[0]),
             ("Sắp xếp", clos[1]), ("Tìm kiếm & cây", clos[1]), ("Phân tích độ phức tạp", clos[2])],
            start=1,
        ):
            lp = LessonPlan(outline_id=outline.id, week=wk, topic=topic, activities_json={"type": "lecture+lab"})
            db.add(lp)
            db.flush()
            db.add(LessonPlanClo(lesson_plan_id=lp.id, clo_id=clo.id))

        # --- Ngân hàng câu hỏi cho IT102 ---
        bloom_diff = [
            ("CLO1", clos[0].id, "understand"), ("CLO2", clos[1].id, "apply"), ("CLO3", clos[2].id, "analyze"),
        ]
        qid = 0
        for _, clo_id, bloom in bloom_diff:
            for diff in ("easy", "medium", "hard"):
                for _ in range(4):  # 4 câu mỗi (clo×độ khó)
                    qid += 1
                    db.add(Question(
                        course_id=courses[1].id, clo_id=clo_id, bloom_level=bloom,
                        difficulty=diff, type="mcq_single",
                        content=f"Câu hỏi mẫu #{qid} ({bloom}/{diff})",
                        options_json=["A", "B", "C", "D"], answer="A", points=1,
                        review_status="approved",
                    ))

        # --- Ma trận đề thi ---
        db.add(ExamMatrix(
            course_id=courses[1].id, name="Ma trận cuối kỳ IT102",
            cells_json=[
                {"clo_id": clos[0].id, "bloom_level": "understand", "difficulty": "easy", "count": 3, "points_each": 0.5},
                {"clo_id": clos[1].id, "bloom_level": "apply", "difficulty": "medium", "count": 3, "points_each": 1.0},
                {"clo_id": clos[2].id, "bloom_level": "analyze", "difficulty": "hard", "count": 2, "points_each": 1.5},
            ],
        ))

        db.commit()
        print("Seed thành công.")
        print("Tài khoản: admin@obe.vn/admin123, manager@obe.vn/manager123, lecturer@obe.vn/lecturer123, qa@obe.vn/qa123")
    finally:
        db.close()


if __name__ == "__main__":
    run()
