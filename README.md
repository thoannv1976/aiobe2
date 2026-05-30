# Hệ thống Quản lý OBE / AUN-QA

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
| 1 | CTĐT & chuẩn đầu ra: CRUD Program/PLO/PI/Course, ma trận Học phần×PLO, kiểm tra độ phủ | ✅ |
| 2 | Trích xuất đề án (AI): upload → trích văn bản → Claude ra JSON → rà soát/xác nhận → ghi CSDL | ✅ API (human-in-the-loop) |
| 3 | Đề cương: CLO, ma trận CLO×PLO, đánh giá+rubric, kế hoạch dạy, alignment, versioning, vòng đời | ✅ |
| 4 | Giáo trình: chương gắn CLO, phiên bản | ✅ API |
| 5 | Ngân hàng câu hỏi & ma trận: CRUD, import/export CSV, thống kê phủ | ✅ |
| 6 | Tạo đề thi: sinh từ ma trận, nhiều mã đề, bảng đặc tả + đáp án, vòng đời duyệt | ✅ |
| 7 | Lưu trữ & kiểm định: báo cáo phủ chuẩn, audit log, gói minh chứng (zip) | ✅ |

### Các điểm OBE đã hiện thực & có test
- **Alignment đề cương**: mỗi CLO ánh xạ ≥1 PLO; mỗi CLO được ≥1 cấu phần đánh giá; tổng trọng số = 100%; cảnh báo CLO không được dạy. Bắt buộc đạt trước khi *Approve*.
- **Độ phủ CTĐT**: mỗi PLO cần ≥1 học phần mức *Master (M)*; cảnh báo PLO chưa phủ.
- **Sinh đề từ ma trận**: bốc đúng số câu mỗi ô CLO×Bloom×độ khó, tránh trùng, deterministic theo seed, nhiều mã đề; báo lỗi khi ngân hàng thiếu câu.
- **Báo cáo phủ chuẩn**: PLO→PI→CLO→đánh giá, liệt kê lỗ hổng.

## Hướng phát triển tiếp
- OCR Tesseract cho PDF scan; màn hình rà soát trích xuất song song văn bản gốc (Phase 2 UI).
- Rich-text editor (Tiptap) cho giáo trình; xuất DOCX/PDF (skill docx/pdf).
- Lưu file lên MinIO thay vì cục bộ; diff phiên bản trực quan.
