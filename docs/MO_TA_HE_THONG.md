# EduOBE / AIOBE — Mô tả hệ thống (kỹ thuật)
## Nền tảng Quản lý Đào tạo theo Chuẩn đầu ra (OBE) & Kiểm định AUN-QA

> Phiên bản: **v1.5.0**. Tài liệu mô tả đầy đủ kiến trúc, hạ tầng vận hành, mô hình dữ liệu, các phân hệ chức năng, lớp AI, đa người thuê (multi-tenant), bảo mật, triển khai và vận hành.

---

## 1. Tổng quan

EduOBE là **hệ thống quản trị học thuật chuyên biệt cho OBE/AUN-QA**, số hóa toàn bộ chuỗi: **Đề án mở ngành → CTĐT → PLO → PI → Đề cương/CLO → Giáo trình → Bài giảng → Ngân hàng câu hỏi → Ma trận đề thi → Đề thi → Minh chứng kiểm định**. Trí tuệ nhân tạo (AI) tham gia ở mọi khâu: **vừa tạo nội dung, vừa thẩm định & nâng cấp chất lượng**. Hệ thống **đa người thuê (multi-tenant)**: một codebase phục vụ nhiều trường đại học, cô lập dữ liệu chặt chẽ.

**Quy mô hiện tại:** 16 màn hình · 139 API endpoint · 29 bảng dữ liệu · 12 migration · 66 test tự động.

---

## 2. Kiến trúc tổng thể

Monorepo gồm 2 thành phần chính + cơ sở hạ tầng:

```
┌──────────────┐     HTTPS      ┌─────────────────────────┐     ┌──────────────┐
│  Frontend    │ ─────────────► │  Backend API (FastAPI)  │ ──► │ PostgreSQL    │
│  Next.js 14  │   JSON/REST    │  - REST API + RBAC      │     │ (Cloud SQL)   │
│  (Cloud Run) │ ◄───────────── │  - Logic OBE thuần      │     └──────────────┘
└──────────────┘                │  - Lớp AI (LLM)         │ ──► GCS (file)
                                │  - Job nền              │ ──► Cloud Tasks (worker)
                                └─────────────────────────┘ ──► Anthropic/OpenAI (AI)
```

- **Backend** chứa toàn bộ **logic nghiệp vụ OBE** (alignment, coverage, sinh đề, đánh giá AI) và REST API. Tách lớp rõ ràng: `models / schemas / services / routers / core`.
- **Frontend** là giao diện các màn hình; gọi backend qua REST; suy "trường" (tenant) theo subdomain.
- **Nguyên tắc**: output AI luôn được **validate bằng Pydantic** trước khi ghi; **human-in-the-loop** (người quyết định cuối); soft-delete + versioning + audit log.

---

## 3. Công nghệ sử dụng

| Lớp | Công nghệ |
|---|---|
| Backend / API | Python 3.11, **FastAPI**, Uvicorn |
| ORM / Migration | **SQLAlchemy 2.0**, **Alembic** |
| CSDL | **PostgreSQL** (Cloud SQL) · SQLite (dev/test) |
| Frontend | **Next.js 14** (App Router, TypeScript) + Tailwind CSS |
| AI / LLM | **Anthropic Claude** & **OpenAI** (lớp thống nhất, key theo trường) |
| Đọc tài liệu | PyMuPDF (PDF), python-docx (DOCX), Tesseract OCR (`vie`) |
| Xuất file | python-docx (DOCX), fpdf2 (PDF), python-pptx (PPTX), openpyxl (Excel) |
| Lưu file | **Google Cloud Storage** (prod) · ổ đĩa cục bộ (dev) |
| Job nền | **Cloud Tasks** (prod) · thread/inline (dev) |
| Bảo mật | JWT (python-jose), bcrypt, Fernet (mã hóa key), RBAC, Postgres RLS |
| Triển khai | Docker, **Google Cloud Run** + Cloud SQL |

---

## 4. Hạ tầng đang chạy (Google Cloud)

- **Cloud Run** chạy 2 dịch vụ: `obe-web` (frontend) và `obe-api` (backend) — tự co giãn (autoscale), không trạng thái (stateless).
- **Cloud SQL (PostgreSQL)**: CSDL chính; backend kết nối qua DATABASE_URL (unix socket `/cloudsql/...`) hoặc **Cloud SQL Python Connector** (tùy chọn). Pool kết nối cấu hình được (pool_size/overflow/recycle/timeout).
- **GCS**: lưu file upload (đề án, đề cương gốc, minh chứng) — bền vững & chia sẻ giữa nhiều instance.
- **Cloud Tasks**: hàng đợi tác vụ AI nặng; worker là chính API (`POST /api/jobs/{id}/run`).
- **Tự migrate khi khởi động**: backend chạy `alembic upgrade head` lúc startup (idempotent) → schema luôn khớp code.
- **Định tuyến đa trường**: DNS wildcard `*.eduobe.vn` → mỗi trường một subdomain (`<mã>.eduobe.vn`).

> URL hiện tại (Cloud Run): web `https://obe-web-….run.app`. API có tài liệu Swagger tại `/docs`.

---

## 5. Cấu trúc mã nguồn

```
backend/
  app/
    main.py            # khởi tạo FastAPI, đăng ký router, auto-migrate, cache tenant
    config.py          # cấu hình (env-driven)
    database.py        # engine/session, pool, Cloud SQL connector
    core/              # deps (RBAC), security (JWT), tenant (cô lập), crypto, pagination, llm_context
    models/            # tables.py (29 bảng), enums.py
    schemas/           # Pydantic I/O
    services/          # logic OBE + AI (xem mục 8–9)
    routers/           # REST endpoints (14 nhóm)
  alembic/versions/    # 12 migration
  scripts/             # md_to_files (xuất tài liệu), verify_rls (pen-test RLS)
  tests/               # 66 test
frontend/app/          # 16 màn hình (Next.js App Router)
docs/                  # SPEC, kế hoạch multi-tenant, tài liệu marketing
```

**Nhóm router (14):** auth, programs, outlines, textbooks, lectures, questions, exams, extraction, reports, assignments, apikeys, jobs, tenants, (health).

**Service (logic):** alignment, audit, diff, exam_generation, exports, extraction, llm, qa_review, outline_ai, question_ai, matrix_ai, matrix_summary, textbook_ai, lecture_ai, jobs, job_handlers, storage, reports.

---

## 6. Mô hình dữ liệu (29 bảng)

- **Người dùng & phân quyền:** `users`, `assignments` (phạm vi phụ trách).
- **CTĐT & chuẩn đầu ra:** `programs`, `plos`, `pis`, `courses`, `course_plo` (ma trận Học phần×PLO I/R/M).
- **Đề cương:** `course_outlines`, `clos`, `clo_plo`, `assessments`, `assessment_clo`, `lesson_plans`, `lesson_plan_clo`.
- **Giáo trình & bài giảng:** `textbooks`, `chapters`, `chapter_clo`, `lectures`.
- **Ngân hàng câu hỏi & đề thi:** `questions`, `exam_matrices`, `exams`, `exam_question`.
- **Minh chứng & vận hành:** `documents`, `extractions`, `audit_logs`, `api_keys`, `jobs`, `llm_usage`.
- **Đa người thuê:** `tenants` (trường) — mọi bảng nghiệp vụ có cột **`tenant_id`** trỏ về đây.

Đặc điểm: index trên các cột lọc/khóa ngoại trọng yếu + composite `(tenant_id, …)`; soft-delete cho tài liệu ban hành; versioning đề cương/giáo trình/đề thi; truy vết hai chiều PLO↔PI↔CLO↔đánh giá↔câu hỏi.

---

## 7. Các phân hệ chức năng

### 7.1. Trích xuất Đề án mở ngành (AI)
Upload PDF/DOCX/TXT (kể cả **bản scan** nhờ OCR tiếng Việt, đọc cả bảng biểu) → AI bóc tách **PLO, PI, danh mục học phần, ma trận học phần–PLO** → người dùng rà soát & xác nhận.

### 7.2. CTĐT & Chuẩn đầu ra
CRUD Chương trình/PLO/PI/Học phần; **ma trận Học phần×PLO (I/R/M)** (kèm cột STT); **kiểm tra độ phủ** (cảnh báo PLO chưa đạt Master); **AI chuẩn hóa PLO**; **xóa/dọn** chương trình; báo cáo phủ chuẩn.

### 7.3. Đề cương học phần (chuẩn AUN-QA)
- **AI soạn đề cương**: CLO song ngữ Việt–Anh, ma trận CLO×PLO, đánh giá **kèm rubric**, kế hoạch dạy.
- **Import đề cương đã có** vào đúng học phần: AI bóc tách → rà soát/sửa ánh xạ CLO–PLO → lưu.
- **AI kiểm tra chất lượng** (chấm điểm + lỗ hổng) và **AI nâng cấp** → phiên bản mới (giữ bản gốc, có diff).
- Kiểm tra **alignment** bắt buộc trước khi duyệt; vòng đời trạng thái; **xuất DOCX**.
- **Bảng "sức khỏe đề cương toàn ngành"**: điểm chất lượng AI từng học phần.

### 7.4. Giáo trình
**AI tạo cả giáo trình/từng chương** (chương sâu 25–40 trang, chạy **nền có thanh tiến độ**); **AI đánh giá + nâng cấp** chương; xuất **DOCX & PDF**.

### 7.5. Bài giảng
**AI soạn bài giảng theo buổi** (bám giáo trình + CLO); **AI đánh giá + nâng cấp** (nội dung + slide); xuất **DOCX & PPTX**.

### 7.6. Ngân hàng câu hỏi
**AI sinh câu hỏi** bám giáo trình theo CLO, **kèm giải thích/nguồn/rubric**; thẩm định 5 trạng thái + duyệt hàng loạt; **AI đánh giá + nâng cấp**; import/export **CSV & Excel**; dashboard độ phủ; phân trang.

### 7.7. Ma trận đề thi & Tạo đề
**AI tạo/tối ưu ma trận** (CLO×Bloom×độ khó), **cân điểm chính xác** về thang, **gắn cấu phần đánh giá**; **AI đánh giá AUN-QA + nâng cấp**. Sinh đề **chỉ từ câu Đã duyệt**, **nhiều mã đề**, **bảng đặc tả + mapping CLO–PLO/PI**, xuất DOCX.

### 7.8. Kiểm định & Đảm bảo chất lượng
**Báo cáo phủ chuẩn PLO→PI→CLO→đánh giá**; kho minh chứng; **audit log**; **đóng gói minh chứng (zip)**.

### 7.9. Quản trị & vận hành
Phân quyền **RBAC theo vai trò & phạm vi**; Admin trường quản lý **API key AI** của trường; **trang Chi phí AI** (token/chi phí theo chương trình & theo trường); versioning; song ngữ Việt/Anh.

---

## 8. Lớp AI (LLM) — tạo, thẩm định & kiểm soát

- **Lớp thống nhất** (`services/llm.py`): hỗ trợ **Claude (Anthropic)** và **OpenAI**; **mỗi trường tự nạp API key của mình** (chi phí về đúng trường); chọn đúng key theo tenant hiện tại.
- **Tạo nội dung**: đề cương, giáo trình, bài giảng, câu hỏi, ma trận — output ép JSON & validate Pydantic.
- **Thẩm định & nâng cấp ở MỌI khâu**: AI chấm điểm /100, chỉ lỗi theo AUN-QA, **nâng cấp tự động** (đề cương, câu hỏi, ma trận, chương giáo trình, bài giảng).
- **Kiểm soát chi phí & độ tin cậy**: **retry/backoff** khi lỗi tạm thời (429/quá tải/timeout); **giới hạn gọi đồng thời**; **ghi nhận token + chi phí ước tính** (`llm_usage`); **hạn mức token/ngày theo trường**.
- **Mã hóa key** khi lưu DB (Fernet/AES, bật bằng `ENCRYPTION_KEY`).

---

## 9. Tác vụ nền (job)

- Tác vụ AI nặng (sinh cả giáo trình…) **chạy nền**: request chỉ "đặt việc" và trả `job_id`; frontend **poll tiến độ** (%).
- Cơ chế chạy linh hoạt: **Cloud Tasks** (prod) / **thread** / **inline** (test).
- **Công bằng tài nguyên (fairness)**: giới hạn số job đồng thời **mỗi trường**.

---

## 10. Đa người thuê (Multi-tenant) — Nhóm C (C0–C5)

Một codebase phục vụ nhiều trường (mô hình **shared-schema + `tenant_id` + RLS**):

- **Cô lập 2 lớp**: (1) tầng ứng dụng tự lọc mọi truy vấn & tự gán `tenant_id` khi ghi theo trường của người đăng nhập; (2) **PostgreSQL Row-Level Security (RLS)** làm lớp chặn cuối ở tầng DB.
- **Định tuyến theo subdomain** `<mã>.eduobe.vn`; **đăng nhập theo trường**; email duy nhất theo `(tenant, email)`.
- **Super-Admin nền tảng**: cấp phát/tạm ngừng/gia hạn trường; **billing theo thời gian** (mặc định 365 ngày; hết hạn → chặn dùng; thanh toán → Super-Admin gia hạn).
- **Theo trường**: key AI, chi phí/hạn mức, branding (logo/tên/màu), fairness job.
- **Vận hành**: **export** toàn bộ dữ liệu trường (zip JSON), **offboarding** (xóa cứng có xác nhận), **pen-test RLS** (`scripts/verify_rls.py`), quan trắc gắn `tenant_id`.

---

## 11. Bảo mật & tuân thủ

- **JWT** + **RBAC** theo vai trò (Super-Admin / Admin trường / Trưởng khoa / Giảng viên / ĐBCL / Khách) và phạm vi.
- **Cô lập dữ liệu đa trường** 2 lớp (app + RLS); truy cập chéo → 404.
- **Mã hóa API key AI** khi lưu; mật khẩu băm bcrypt.
- **Audit log** mọi thao tác quan trọng; **soft-delete** tài liệu ban hành (không xóa cứng).
- **Human-in-the-loop**: AI hỗ trợ, con người duyệt cuối — dữ liệu thuộc về nhà trường.

---

## 12. Triển khai & cấu hình (biến môi trường)

| Nhóm | Biến |
|---|---|
| CSDL | `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT` |
| Cloud SQL Connector (tùy chọn) | `INSTANCE_CONNECTION_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_USE_PRIVATE_IP` |
| Bảo mật | `JWT_SECRET`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ENCRYPTION_KEY` |
| Đa trường | `BASE_DOMAIN` (mặc định `eduobe.vn`) |
| Lưu file | `GCS_BUCKET`, `GCS_PREFIX`, `STORAGE_DIR` |
| Job nền | `JOBS_INLINE`, `CLOUD_TASKS_QUEUE`, `WORKER_BASE_URL`, `JOB_WORKER_TOKEN`, `JOBS_MAX_CONCURRENCY_PER_TENANT` |
| Kiểm soát AI | `LLM_MAX_RETRIES`, `LLM_RETRY_BASE_DELAY`, `LLM_MAX_CONCURRENCY`, `LLM_DAILY_TOKEN_QUOTA_PER_PROGRAM` |
| CORS | `CORS_ORIGINS` |

**Chạy nhanh (dev, SQLite):**
```
cd backend && pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db python -m app.seed
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

**Toàn bộ stack:** `docker compose up --build` (db Postgres + MinIO + api + web).

---

## 13. Chất lượng & kiểm thử

- **66 test tự động** (pytest): logic OBE (alignment, độ phủ, sinh đề), AI (đánh giá/nâng cấp — mock LLM), import đề cương, hạ tầng (phân trang, job, chi phí), và **cô lập đa trường** (cross-tenant, key/chi phí/hạn mức theo trường, export/offboarding).
- **Migration** kiểm chứng chạy sạch; **RLS/NOT NULL** áp cho PostgreSQL (script `verify_rls.py` pen-test trên staging).
- Logic OBE thuần đặt ở `services/` và đều có unit test.

---

## 14. Tiến độ & lộ trình

- Đã hoàn thành: Phase 0–7 (nền tảng→kiểm định) · AI tạo + đánh giá/nâng cấp toàn chuỗi · import đề cương · chịu tải (index/phân trang/pool) · hạ tầng (GCS/job nền/kiểm soát LLM) · **multi-tenant (C0–C5)**.
- Trước khi mở bán đa trường: dựng **Postgres staging** → `alembic upgrade head` → `verify_rls.py`; cấu hình **DNS wildcard + chứng chỉ**; load test.
- Hướng phát triển: rich-text editor cho giáo trình; module thu & **chấm bài thi của sinh viên** (khối tải lớn, thiết kế bất đồng bộ + phân vùng); tích hợp SSO/LDAP theo trường; cổng thanh toán tự động.

---

*Tài liệu kỹ thuật EduOBE / AIOBE — v1.5.0. Liên hệ: [tên đầu mối] · [email] · [điện thoại] · [website].*
