# Đặc tả hệ thống: Quản lý Đề cương – Giáo trình – Ngân hàng câu hỏi – Đề thi (chuẩn OBE / AUN-QA)

> Tài liệu này là bản mô tả (spec/PRD) để dùng làm ngữ cảnh nền cho Claude Code khi xây dựng ứng dụng.
> Hãy đưa nguyên file này vào repo (ví dụ `docs/SPEC.md` hoặc tham chiếu trong `CLAUDE.md`) trước khi bắt đầu code.

---

## 1. Tổng quan

Hệ thống web giúp các trường/khoa **xây dựng và quản lý toàn bộ chuỗi sản phẩm học thuật theo chuẩn OBE (Outcome-Based Education) và kiểm định AUN-QA**, bắt đầu từ **đề án mở ngành/chương trình đào tạo (CTĐT)** và đi xuống tới từng **đề thi**.

Luồng nghiệp vụ cốt lõi (đảm bảo "constructive alignment" – tính nhất quán dọc):

```
Đề án mở ngành (PDF/DOCX)
   │  (upload + trích xuất bằng AI)
   ▼
Chương trình đào tạo  →  PLO  →  PI (chỉ báo)  →  Danh mục học phần
   │
   ▼
Đề cương học phần  →  CLO  →  Ma trận CLO↔PLO  →  Phương pháp dạy-học  →  Phương pháp đánh giá
   │
   ▼
Giáo trình / tài liệu học phần (gắn theo CLO, theo chương/buổi)
   │
   ▼
Ngân hàng câu hỏi (gắn CLO + mức Bloom + độ khó)  →  Ma trận đề thi
   │
   ▼
Đề thi (sinh từ ma trận, đáp ứng tiêu chí kiểm định)
   │
   ▼
Lưu trữ minh chứng phục vụ kiểm định & đảm bảo chất lượng (ĐBCL)
```

### Nguyên tắc thiết kế bắt buộc (OBE/AUN-QA)
- **Truy vết hai chiều (alignment matrix) phải xuyên suốt:** mỗi PI thuộc một PLO; mỗi CLO ánh xạ tới một hoặc nhiều PLO kèm **mức đóng góp** (ví dụ thang I–R–M: Introduce / Reinforce / Master, hoặc 1–2–3); mỗi cấu phần đánh giá ánh xạ tới CLO; mỗi câu hỏi gắn tới CLO + mức nhận thức Bloom.
- **Mọi sản phẩm sinh ra phải kiểm tra được "độ phủ":** không có PLO/CLO nào bị bỏ sót khi đánh giá; cảnh báo khi câu hỏi hoặc đánh giá không phủ hết CLO.
- **Có quy trình duyệt và phiên bản (versioning):** đề cương, ngân hàng câu hỏi, đề thi đều có vòng đời trạng thái và lịch sử phiên bản để làm minh chứng kiểm định.
- **Mọi thao tác quan trọng được ghi nhật ký (audit log)** vì đây là dữ liệu phục vụ kiểm định.
- **Ngôn ngữ chính: tiếng Việt** (tài liệu đầu vào là tiếng Việt). Giao diện hỗ trợ Việt/Anh.

---

## 2. Khái niệm nghiệp vụ (glossary cho người triển khai)

| Thuật ngữ | Viết tắt | Ý nghĩa |
|---|---|---|
| Program Learning Outcome | PLO | Chuẩn đầu ra của **chương trình đào tạo** |
| Performance Indicator | PI | Chỉ báo/chỉ số đánh giá cụ thể hóa một PLO (PI thuộc về PLO) |
| Course Learning Outcome | CLO | Chuẩn đầu ra của **học phần** |
| Học phần / Môn học | — | Đơn vị học có số tín chỉ, thuộc một CTĐT |
| Đề cương học phần | — | Tài liệu mô tả mục tiêu, CLO, nội dung, dạy-học, đánh giá của học phần |
| Constructive Alignment | — | Sự nhất quán giữa CLO ↔ hoạt động dạy-học ↔ hình thức đánh giá |
| Ma trận CLO–PLO | — | Bảng ánh xạ mức độ đóng góp của từng CLO vào từng PLO |
| Thang Bloom | — | 6 mức nhận thức: Nhớ, Hiểu, Vận dụng, Phân tích, Đánh giá, Sáng tạo |
| Ma trận đề thi | — | Bảng phân bố câu hỏi theo (CLO × mức Bloom × độ khó), gắn trọng số điểm |
| Rubric | — | Bảng tiêu chí chấm điểm cho cấu phần đánh giá (đặc biệt tự luận/dự án) |

---

## 3. Người dùng & phân quyền (RBAC)

| Vai trò | Quyền chính |
|---|---|
| **Admin hệ thống** | Quản trị người dùng, danh mục, cấu hình, sao lưu |
| **Quản lý CTĐT (Trưởng khoa/Trưởng bộ môn)** | Tạo/duyệt CTĐT, PLO, PI; phân công phụ trách học phần; duyệt đề cương |
| **Giảng viên** | Xây dựng đề cương, giáo trình, câu hỏi, đề thi cho học phần được phân công |
| **Cán bộ ĐBCL / Kiểm định** | Xem toàn bộ minh chứng, xuất báo cáo phủ chuẩn, theo dõi phiên bản (chỉ đọc + bình luận) |
| **Khách (read-only)** | Xem các tài liệu đã ban hành (tùy cấu hình) |

Yêu cầu: phân quyền theo cả **vai trò** lẫn **phạm vi** (chỉ thao tác trên CTĐT/học phần được gán).

---

## 4. Các module & yêu cầu chức năng

### 4.1 Module Upload & Trích xuất đề án mở ngành (AI extraction)
Đây là module quan trọng và rủi ro nhất – cần làm kỹ.

**Chức năng:**
1. Upload file đề án mở ngành/CTĐT (PDF, DOCX; hỗ trợ file scan qua OCR).
2. Trích xuất văn bản: PDF số dùng PyMuPDF/pdfplumber, DOCX dùng python-docx; PDF scan dùng OCR (Tesseract tiếng Việt / dịch vụ OCR).
3. Chunk văn bản + gọi **LLM (Claude API)** để trích xuất có cấu trúc theo schema JSON cố định:
   - Thông tin CTĐT (tên ngành, mã ngành, trình độ, năm ban hành, đơn vị).
   - Danh sách **PLO** (mã, nội dung, phân loại kiến thức/kỹ năng/thái độ, mức Bloom nếu suy luận được).
   - Danh sách **PI** gắn với từng PLO.
   - **Danh mục học phần** (mã, tên, số tín chỉ, học kỳ, bắt buộc/tự chọn, học phần tiên quyết nếu có).
   - Ma trận học phần–PLO nếu đề án có sẵn.
4. **Bắt buộc có bước con người rà soát/xác nhận (human-in-the-loop):** hiển thị kết quả trích xuất bên cạnh đoạn văn bản gốc để giảng viên/quản lý sửa và xác nhận trước khi lưu vào CSDL. Không tự động ghi đè.
5. Lưu lại file gốc + ánh xạ vị trí trích xuất (làm minh chứng).

**Schema JSON mẫu cho output trích xuất:**
```json
{
  "program": { "name": "", "code": "", "level": "", "year": 0, "faculty": "" },
  "plos": [
    { "code": "PLO1", "description": "", "category": "knowledge|skill|attitude", "bloom_level": "" }
  ],
  "pis": [
    { "code": "PI1.1", "plo_code": "PLO1", "description": "" }
  ],
  "courses": [
    { "code": "", "name": "", "credits": 0, "semester": 0, "type": "core|elective", "prerequisites": [] }
  ],
  "course_plo_matrix": [
    { "course_code": "", "plo_code": "", "level": "I|R|M" }
  ]
}
```
> Yêu cầu Claude khi gọi LLM: ép trả về **đúng JSON, không kèm văn bản thừa**, có validate bằng schema (zod/pydantic) trước khi dùng.

### 4.2 Module Quản lý CTĐT & Chuẩn đầu ra
- CRUD chương trình đào tạo.
- CRUD PLO và PI (PI luôn thuộc một PLO).
- CRUD học phần và gán vào CTĐT.
- Ma trận **Học phần × PLO** (mức I/R/M) – chỉnh sửa dạng bảng tương tác.
- Kiểm tra ràng buộc: mỗi PLO phải được ít nhất một học phần "Master (M)"; cảnh báo PLO chưa được phủ.

### 4.3 Module Đề cương học phần
- Tạo đề cương gắn với một học phần (kế thừa thông tin từ CTĐT).
- Các phần của đề cương: thông tin chung; mô tả học phần; **CLO**; **ma trận CLO × PLO** (mức đóng góp); nội dung theo chương/buổi (kế hoạch giảng dạy, gắn mỗi buổi với CLO); **phương pháp dạy-học**; **phương pháp đánh giá** (mỗi cấu phần có trọng số % và ánh xạ tới CLO, kèm rubric); tài liệu tham khảo.
- **Kiểm tra alignment tự động:**
  - Mỗi CLO phải ánh xạ ít nhất một PLO.
  - Mỗi CLO phải được phủ bởi ít nhất một cấu phần đánh giá.
  - Tổng trọng số đánh giá = 100%.
  - Cảnh báo CLO không xuất hiện trong bất kỳ buổi dạy nào.
- Vòng đời trạng thái: `Draft → Submitted → Approved → Published → Archived`. Có versioning, so sánh phiên bản (diff), nhật ký duyệt.
- Xuất đề cương ra DOCX/PDF theo mẫu của trường (dùng skill docx/pdf).
- Hỗ trợ template đề cương theo từng trường.

### 4.4 Module Giáo trình / Tài liệu học phần
- Soạn giáo trình theo cấu trúc chương → mục, gắn mỗi chương/mục với CLO tương ứng.
- Trình soạn thảo rich-text (có công thức toán, hình ảnh, bảng, chèn file đính kèm).
- Quản lý phiên bản giáo trình; liên kết với đề cương học phần.
- Có thể gợi ý nội dung/đề mục bằng AI dựa trên CLO (tùy chọn, vẫn cần người duyệt).
- Xuất giáo trình ra PDF/DOCX.

### 4.5 Module Ngân hàng câu hỏi & Ma trận đề thi
- CRUD câu hỏi, mỗi câu gắn: học phần, **CLO**, **mức Bloom**, **độ khó** (dễ/TB/khó), **loại** (trắc nghiệm 1 đáp án / nhiều đáp án / điền khuyết / tự luận ngắn / tự luận / bài tập), nội dung, đáp án, điểm, ghi chú/đáp án giải thích, tags.
- Hỗ trợ import/export câu hỏi (CSV/Excel; cân nhắc định dạng tương thích để in trộn đề).
- **Ma trận đề thi:** bảng phân bố số câu/điểm theo (CLO × mức Bloom × độ khó); kiểm tra tổng điểm và độ phủ CLO.
- Thống kê ngân hàng: số câu theo CLO/Bloom/độ khó để phát hiện "lỗ hổng" (ví dụ thiếu câu mức Vận dụng cho CLO3).

### 4.6 Module Tạo đề thi
- Tạo đề thi từ một **ma trận đề thi**: hệ thống tự động bốc câu hỏi từ ngân hàng thỏa ràng buộc ma trận (đúng số câu mỗi ô CLO×Bloom×độ khó), tránh trùng, có thể sinh nhiều mã đề (đảo câu/đảo phương án).
- Cho phép chỉnh tay (thay câu, khóa câu) sau khi sinh tự động.
- Tự sinh **đáp án/barem chấm** và **bảng đặc tả đề thi** (test blueprint) làm minh chứng.
- Kiểm tra hợp lệ: tổng điểm đúng, độ phủ CLO đạt yêu cầu của ma trận.
- Vòng đời: `Draft → Reviewed → Approved → Published`. Versioning + audit log.
- Xuất đề thi + đáp án + bảng đặc tả ra PDF/DOCX.

### 4.7 Module Lưu trữ & Kiểm định / ĐBCL
- Kho minh chứng: lưu mọi phiên bản đề cương, giáo trình, ngân hàng, đề thi, file đề án gốc.
- **Báo cáo phủ chuẩn (coverage report):** ma trận tổng hợp PLO → PI → CLO → đánh giá → câu hỏi; chỉ ra điểm thiếu để chuẩn bị kiểm định.
- Bộ lọc/tìm kiếm minh chứng theo CTĐT, học phần, năm học, trạng thái.
- Xuất gói minh chứng (zip) và báo cáo phục vụ AUN-QA.
- Audit log đầy đủ: ai – làm gì – khi nào – phiên bản nào.

---

## 5. Mô hình dữ liệu (gợi ý)

Quan hệ chính:
- `Program 1—n PLO`, `PLO 1—n PI`, `Program 1—n Course`
- `Course 1—n CourseOutline` (nhiều phiên bản), `CourseOutline 1—n CLO`
- `CLO n—n PLO` (bảng nối `clo_plo` có `contribution_level`)
- `CourseOutline 1—n Assessment`, `Assessment n—n CLO`
- `CourseOutline 1—n LessonPlan` (buổi/chương), `LessonPlan n—n CLO`
- `Course 1—n Question`, `Question n—1 CLO`
- `Course 1—n ExamMatrix`, `ExamMatrix 1—n Exam`, `Exam n—n Question` (qua `exam_question` có `order`, `variant`)
- `Course 1—n Textbook`, `Textbook 1—n Chapter`, `Chapter n—n CLO`
- `AuditLog`, `Attachment`, `User`, `Role`, `Assignment(user–program/course)`

Các bảng cốt lõi (rút gọn):
```
programs(id, name, code, level, year, faculty_id, source_document_id, created_at)
plos(id, program_id, code, description, category, bloom_level)
pis(id, plo_id, code, description)
courses(id, program_id, code, name, credits, semester, type, prerequisites_json)
course_outlines(id, course_id, version, status, general_info_json, teaching_methods_json, created_by, approved_by, created_at)
clos(id, outline_id, code, description, bloom_level)
clo_plo(clo_id, plo_id, contribution_level)        -- I|R|M hoặc 1|2|3
assessments(id, outline_id, name, type, weight_percent)
assessment_clo(assessment_id, clo_id)
lesson_plans(id, outline_id, week, topic, activities_json)
lesson_plan_clo(lesson_plan_id, clo_id)
textbooks(id, course_id, title, version, status)
chapters(id, textbook_id, order, title, content_richtext)
chapter_clo(chapter_id, clo_id)
questions(id, course_id, clo_id, bloom_level, difficulty, type, content, options_json, answer, points, explanation, tags_json)
exam_matrices(id, course_id, name, cells_json)      -- phân bố CLO×Bloom×độ khó
exams(id, course_id, matrix_id, version, status, total_points, duration_min, variant_count)
exam_question(exam_id, question_id, order, variant)
documents(id, type, file_path, mime, uploaded_by, original_name)   -- file gốc/minh chứng
audit_logs(id, user_id, entity, entity_id, action, diff_json, created_at)
users(id, name, email, password_hash, ...) / roles / assignments
```

---

## 6. Tech stack đề xuất (DỄ THAY ĐỔI – nói nếu bạn muốn stack khác)

> Đây là khuyến nghị để Claude Code có điểm khởi đầu thống nhất. Nếu trường bạn đã có chuẩn công nghệ, hãy thay phần này.

- **Frontend:** Next.js (React + TypeScript) + Tailwind CSS + shadcn/ui. Bảng/ma trận tương tác dùng TanStack Table; rich-text editor dùng Tiptap.
- **Backend:** Python **FastAPI** (thuận lợi cho trích xuất tài liệu + gọi LLM) HOẶC Node.js (NestJS) nếu muốn 1 ngôn ngữ. *Khuyến nghị FastAPI cho module trích xuất.*
- **CSDL:** PostgreSQL (quan hệ chặt, phù hợp truy vết ma trận). ORM: Prisma (Node) / SQLAlchemy + Alembic (Python).
- **Xử lý tài liệu:** PyMuPDF/pdfplumber, python-docx, Tesseract OCR (vie).
- **AI:** Anthropic Claude API cho trích xuất có cấu trúc và gợi ý nội dung (validate output bằng pydantic/zod).
- **Xuất file:** dùng các skill docx/pdf/xlsx để xuất đề cương, đề thi, báo cáo.
- **Auth:** JWT + RBAC; lưu mật khẩu băm (argon2/bcrypt).
- **Lưu file:** S3-compatible (MinIO cho self-host) hoặc lưu cục bộ giai đoạn đầu.
- **Triển khai:** Docker Compose (web + api + postgres + minio).

---

## 7. Yêu cầu phi chức năng
- **Tiếng Việt** chuẩn cho dữ liệu và OCR; UI song ngữ Việt/Anh.
- **Bảo mật:** RBAC theo vai trò + phạm vi; mã hóa khi truyền; nhật ký truy cập.
- **Tính toàn vẹn minh chứng:** không xóa cứng tài liệu đã ban hành (soft delete + archive).
- **Versioning & diff** cho đề cương/đề thi/giáo trình.
- **Khả năng kiểm thử:** logic alignment và sinh đề phải có unit test.
- **Hiệu năng:** sinh đề từ ngân hàng vài nghìn câu trong vài giây.
- **Sao lưu/khôi phục** CSDL và kho file.

---

## 8. Lộ trình triển khai theo giai đoạn (gợi ý cho Claude Code)

**Phase 0 – Khởi tạo:** dựng monorepo, Docker Compose, schema CSDL + migration, auth + RBAC, layout cơ bản.

**Phase 1 – CTĐT & chuẩn đầu ra:** CRUD Program/PLO/PI/Course + ma trận Học phần×PLO + kiểm tra độ phủ.

**Phase 2 – Trích xuất đề án (AI):** upload → trích xuất văn bản/OCR → LLM ra JSON theo schema → màn hình rà soát/xác nhận → ghi vào CSDL.

**Phase 3 – Đề cương học phần:** soạn đề cương, CLO, ma trận CLO×PLO, đánh giá + rubric, kế hoạch giảng dạy; kiểm tra alignment; duyệt + versioning; xuất DOCX/PDF.

**Phase 4 – Giáo trình:** soạn thảo theo chương gắn CLO; phiên bản; xuất file.

**Phase 5 – Ngân hàng câu hỏi & ma trận đề thi:** CRUD câu hỏi, import/export, ma trận, thống kê phủ.

**Phase 6 – Tạo đề thi:** sinh đề từ ma trận, nhiều mã đề, đáp án + bảng đặc tả, duyệt, xuất file.

**Phase 7 – Lưu trữ & kiểm định:** kho minh chứng, báo cáo phủ chuẩn, xuất gói AUN-QA, audit log đầy đủ.

> Mỗi phase nên kết thúc bằng: migration ổn định, seed dữ liệu mẫu, test cho phần logic OBE (alignment, sinh đề), và README cập nhật.

---

## 9. Gợi ý cách dùng tài liệu này với Claude Code
1. Đặt file vào `docs/SPEC.md`, tạo `CLAUDE.md` tham chiếu tới nó và liệt kê quy ước code.
2. Yêu cầu Claude làm **lần lượt theo từng Phase**, không làm tất cả cùng lúc.
3. Bắt đầu bằng: *"Đọc docs/SPEC.md. Thực hiện Phase 0 và Phase 1. Sinh schema, migration, seed dữ liệu mẫu cho 1 CTĐT có 3 PLO và 5 học phần."*
4. Với Phase 2 (trích xuất), cung cấp cho Claude một file đề án mở ngành mẫu để kiểm thử thực tế.
