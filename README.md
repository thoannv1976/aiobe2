# Hệ thống Quản lý OBE / AUN-QA

> **Phiên bản hiện tại: v1.3.1** (2026-06-06) — xem [`CHANGELOG.md`](CHANGELOG.md).
> Quy mô: 15 màn hình · 130 API endpoint · 28 bảng dữ liệu · 10 migration · 55 test.
> Mới ở v1.1–v1.3: import đề cương + AI đánh giá/nâng cấp toàn chuỗi; chịu tải (index, phân trang, pool DB); hạ tầng (GCS, job nền, kiểm soát chi phí LLM); xóa CTĐT + trang chi phí AI.

Web app quản lý chuỗi sản phẩm học thuật theo chuẩn **OBE (Outcome-Based Education)** và kiểm định **AUN-QA**:

```
Đề án mở ngành (PDF/DOCX) → CTĐT → PLO → PI → Học phần
   → Đề cương → CLO → Ma trận CLO×PLO → Đánh giá → Kế hoạch dạy
   → Giáo trình (chương gắn CLO)
   → Ngân hàng câu hỏi (CLO+Bloom+độ khó) → Ma trận đề thi → Đề thi
   → Lưu trữ minh chứng & báo cáo phủ chuẩn (ĐBCL/kiểm định)
```

Đặc tả đầy đủ: [`docs/SPEC.md`](docs/SPEC.md). Quy ước phát triển: [`CLAUDE.md`](CLAUDE.md).

## Kiến trúc
| Thành phần | Công nghệ |
|---|---|
| Backend / API | FastAPI (Python 3.11), SQLAlchemy 2 + Alembic |
| CSDL | PostgreSQL (Docker) · SQLite (dev nhanh) |
| Frontend | Next.js 14 (App Router, TS) + Tailwind |
| AI trích xuất | Anthropic Claude API (output validate bằng Pydantic) |
| Xử lý tài liệu | PyMuPDF, python-docx, (Tesseract `vie` cho OCR) |
| Auth | JWT + RBAC theo vai trò & phạm vi |
| Lưu file / triển khai | MinIO (S3) + Docker Compose |

## Chạy nhanh (dev, SQLite)
```bash
# Backend
cd backend
pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db python -m app.seed          # seed dữ liệu mẫu
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload
# API: http://localhost:8000  · Docs: http://localhost:8000/docs

# Frontend (terminal khác)
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev       # http://localhost:3000
```

## Chạy toàn bộ stack (Postgres + MinIO + API + Web)
```bash
# (tùy chọn) export ANTHROPIC_API_KEY=sk-... để bật module trích xuất AI
docker compose up --build
# Web http://localhost:3000 · API http://localhost:8000 · MinIO http://localhost:9001
```
Container API tự chạy `alembic upgrade head` + seed dữ liệu mẫu.

## Tài khoản mẫu
| Vai trò | Email | Mật khẩu |
|---|---|---|
| Admin | admin@obe.vn | admin123 |
| Trưởng khoa (Quản lý CTĐT) | manager@obe.vn | manager123 |
| Giảng viên | lecturer@obe.vn | lecturer123 |
| ĐBCL / Kiểm định | qa@obe.vn | qa123 |

## Test
```bash
cd backend && pytest          # logic OBE: alignment, độ phủ PLO, sinh đề + API tích hợp
```

## Tiến độ theo Phase (SPEC mục 8)
| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Khởi tạo: monorepo, Docker Compose, schema + migration, auth + RBAC, layout | ✅ |
| 1 | CTĐT & chuẩn đầu ra: CRUD Program/PLO/PI/Course, ma trận Học phần×PLO, kiểm tra độ phủ | ✅ API + UI |
| 2 | Trích xuất đề án (AI): upload → trích văn bản (+OCR scan) → Claude ra JSON → rà soát/xác nhận → ghi CSDL | ✅ API + UI (human-in-the-loop) |
| 3 | Đề cương: CLO, ma trận CLO×PLO, đánh giá+rubric, kế hoạch dạy, alignment, versioning, diff, vòng đời, xuất DOCX | ✅ API + UI |
| 4 | Giáo trình: chương gắn CLO, phiên bản, gợi ý đề mục bằng AI | ✅ API + UI |
| 5 | Ngân hàng câu hỏi & ma trận: CRUD, import/export CSV+Excel, thống kê phủ, dựng ma trận | ✅ API + UI |
| 6 | Tạo đề thi: sinh từ ma trận, nhiều mã đề, chỉnh tay (khóa/thay câu), bảng đặc tả + đáp án, vòng đời, xuất DOCX | ✅ API + UI |
| 7 | Lưu trữ & kiểm định: báo cáo phủ chuẩn, kho minh chứng, audit log, gói minh chứng (zip) | ✅ API + UI |

### Màn hình frontend
`/` tổng quan · `/login` · `/extract` (trích xuất AI) · `/programs` + `/programs/[id]` (ma trận Học phần×PLO, báo cáo phủ chuẩn) · `/outlines/[id]` (soạn đề cương: CLO, ma trận CLO×PLO, đánh giá, kế hoạch dạy, alignment, vòng đời, xuất DOCX) · `/courses/[id]` · `/courses/[id]/questions` (ngân hàng câu hỏi + ma trận đề) · `/courses/[id]/textbooks` (giáo trình + gợi ý AI) · `/exams/[id]` (chỉnh tay đề, bảng đặc tả, xuất DOCX) · `/qa` (kiểm định/ĐBCL) · `/admin` (người dùng + phân công).

### Các điểm OBE đã hiện thực & có test
- **Alignment đề cương**: mỗi CLO ánh xạ ≥1 PLO; mỗi CLO được ≥1 cấu phần đánh giá; tổng trọng số = 100%; cảnh báo CLO không được dạy. Bắt buộc đạt trước khi *Approve*.
- **Độ phủ CTĐT**: mỗi PLO cần ≥1 học phần mức *Master (M)*; cảnh báo PLO chưa phủ.
- **Sinh đề từ ma trận**: bốc đúng số câu mỗi ô CLO×Bloom×độ khó, tránh trùng, deterministic theo seed, nhiều mã đề; báo lỗi khi ngân hàng thiếu câu.
- **Báo cáo phủ chuẩn**: PLO→PI→CLO→đánh giá, liệt kê lỗ hổng.

## Hướng phát triển tiếp
- Rich-text editor (Tiptap) thay textarea cho giáo trình; xuất PDF (hiện có DOCX).
- Lưu file upload lên MinIO/GCS thay vì cục bộ (bền vững trên Cloud Run); diff phiên bản trực quan hơn.
- UI rà soát trích xuất hiển thị ánh xạ vị trí trong văn bản gốc.
