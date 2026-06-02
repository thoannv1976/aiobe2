# Nhật ký phiên bản — AIOBE / OBE-AUN-QA

## v1.0.0 — 2026-06-02

Phiên bản đầu tiên hoàn chỉnh: nền tảng quản lý đào tạo theo chuẩn OBE & kiểm định AUN-QA,
tích hợp AI (Claude/OpenAI) ở toàn bộ chuỗi nghiệp vụ.

**Quy mô:** 14 màn hình · 112 API endpoint · 26 bảng dữ liệu · 8 migration · 27 test.

### Tính năng chính
- **Nền tảng & vận hành:** xác thực JWT, RBAC 5 vai trò (theo vai trò + phạm vi); admin
  quản lý API key AI dùng chung (Claude/OpenAI); audit log; soft-delete; versioning + diff.
- **Trích xuất đề án bằng AI (4.1):** upload PDF/DOCX/TXT (đọc cả bảng, OCR PDF scan) →
  AI trích CTĐT/PLO/PI/học phần/ma trận → human-in-the-loop xác nhận.
- **CTĐT & chuẩn đầu ra (4.2):** CRUD Program/PLO/PI/Course; ma trận Học phần×PLO (I/R/M);
  kiểm tra độ phủ; AI chuẩn hóa PLO.
- **Đề cương học phần (4.3):** AI soạn đề cương (theo PLO + mẫu trường + chuẩn AUN-QA);
  CLO song ngữ; ma trận CLO×PLO; đánh giá + rubric; alignment; QA Reviewer AI; vòng đời
  + diff; xuất DOCX (kèm 3 ma trận).
- **Giáo trình (4.4):** AI tạo cả giáo trình/từng chương (25–40 trang); xuất DOCX & PDF.
- **Bài giảng (mục 10):** AI soạn bài giảng theo buổi; xuất DOCX & PPTX slide.
- **Ngân hàng câu hỏi (4.5):** CRUD + AI sinh câu hỏi (bám giáo trình theo CLO, kèm giải
  thích/nguồn/rubric); thẩm định 5 trạng thái + duyệt hàng loạt; import/export CSV+Excel;
  dashboard độ phủ.
- **Ma trận đề thi (mục 11):** AI tạo/tối ưu ma trận bám ngân hàng + cân điểm chính xác về
  thang điểm; gắn cấu phần đánh giá của đề cương (constructive alignment); tỷ trọng CLO/Bloom
  + cảnh báo; vòng đời + duyệt; sửa/duplicate; giải thích AUN-QA.
- **Tạo đề thi (4.6):** sinh đề chỉ từ câu Đã duyệt, nhiều mã đề, chỉnh tay; sắp xếp theo
  nhóm loại để in; bảng đặc tả + mapping CLO–PLO/PI; xuất DOCX.
- **Kiểm định & ĐBCL (4.7):** báo cáo phủ chuẩn PLO→PI→CLO→đánh giá; kho minh chứng;
  audit log; gói minh chứng (zip).

### Hạ tầng
- Backend FastAPI + SQLAlchemy + PostgreSQL; Frontend Next.js 14 + Tailwind.
- Docker + Google Cloud Run + Cloud SQL; auto-migrate khi khởi động.
- Tài liệu marketing (brochure/bảng giá) + script xuất DOCX/PDF.

### Lưu ý vận hành
- Cần cấu hình API key AI tại `/admin/ai` (Claude hoặc OpenAI) để dùng tính năng AI.
- Backend tự chạy `alembic upgrade head` khi khởi động (Postgres) — tránh lệch schema.
