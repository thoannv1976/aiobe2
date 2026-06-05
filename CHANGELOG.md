# Nhật ký phiên bản — AIOBE / OBE-AUN-QA

## v1.3.0 — 2026-06-05 — Hạ tầng (Nhóm B)

### Hạ tầng quy mô lớn
- **Lưu file qua lớp trừu tượng (GCS hoặc cục bộ)** — `app/services/storage.py`. Khi đặt `GCS_BUCKET`,
  file upload (đề án, đề cương gốc, minh chứng) lưu lên **Google Cloud Storage** (bền vững trên Cloud Run
  đa-instance); không đặt → lưu cục bộ (dev/test). Mọi điểm upload + gói minh chứng đã chuyển sang lớp này.
- **Tác vụ AI nặng chạy nền (job)** — `app/services/jobs.py` + bảng `jobs`. Request chỉ "đặt việc" và trả
  `job_id`; frontend **poll tiến độ** (thanh %). Sinh cả giáo trình có endpoint nền
  `POST /api/courses/{id}/textbooks/generate-async`. Cơ chế chạy: **Cloud Tasks** (khi cấu hình) /
  thread nền / inline (test) — `GET /api/jobs/{id}`, `POST /api/jobs/{id}/run` (worker).
- **Kiểm soát LLM (rate-limit/chi phí)**: `llm_complete` nay có **retry/backoff** khi lỗi tạm thời (429/quá
  tải/timeout), **giới hạn số gọi đồng thời**, **ghi nhận token + chi phí ước tính** (bảng `llm_usage`,
  theo chương trình/học phần), và **hạn mức token/ngày theo chương trình** (chặn khi vượt). Thống kê:
  `GET /api/llm-usage` (Admin).

## v1.2.0 — 2026-06-05 — Chịu tải (Nhóm A)

### Hiệu năng & quy mô
- **Đánh index** các cột lọc/khóa ngoại trọng yếu (course_id, outline_id, clo_id, review_status,
  program_id…) + composite `(course_id, review_status)` và `(course_id, is_deleted)` cho bảng câu hỏi.
  Migration `7a1c9f2b3d4e` chạy idempotent (chỉ tạo index còn thiếu) — an toàn cho DB đang có dữ liệu.
- **Phân trang** các endpoint danh sách (câu hỏi, đề thi, đề cương, audit log): tham số `limit`/`offset`,
  tổng số ở header `X-Total-Count`; tránh `query.all()` không giới hạn. Frontend ngân hàng câu hỏi có
  nút Trước/Sau + hiển thị "X–Y / tổng".
- **Cấu hình pool kết nối DB** cho Postgres/Cloud SQL (pool_size, max_overflow, pool_recycle 30',
  pool_timeout, pre_ping) — env-driven; tùy chọn **Cloud SQL Python Connector** khi đặt
  `INSTANCE_CONNECTION_NAME`.

## v1.1.0 — 2026-06-03

### Thêm mới
- **Import đề cương ĐÃ CÓ + đánh giá/hoàn thiện bằng AI** (4.3) — 3 phase:
  - *Phase 1:* upload đề cương sẵn có (PDF/DOCX/TXT, kể cả scan có OCR) → AI bóc tách thành cấu trúc
    chuẩn (mô tả, CLO song ngữ, ma trận CLO×PLO, đánh giá + rubric, kế hoạch dạy) → **màn hình rà
    soát/sửa** (đặc biệt ánh xạ CLO–PLO; mã PLO lạ bị loại + cảnh báo) → lưu thành đề cương draft.
    File gốc được lưu làm minh chứng. Endpoint `POST /api/courses/{id}/parse-outline`,
    `POST /api/courses/{id}/import-outline`.
  - *Phase 2:* sau khi import, tự động chạy kiểm tra chất lượng (qa-review) và hiện điểm + lỗ hổng,
    kèm nút ⚡ Nâng cấp. Mỗi lần chấm lưu snapshot điểm vào đề cương.
  - *Phase 3:* **import hàng loạt** cho cả chương trình theo quy trình **2 bước có xác nhận**: AI
    bóc tách + GỢI Ý học phần (không tự lưu) → người dùng **gán đúng học phần cho từng file** → mới
    lưu (đảm bảo gắn chính xác đề cương–học phần, tránh map sai). Kèm **bảng "sức khỏe đề cương toàn
    ngành"** (điểm AI, số lỗi/cảnh báo từng học phần). Endpoint `POST /api/programs/{id}/parse-outlines`,
    `POST /api/programs/{id}/import-outlines-confirm`, `GET /api/programs/{id}/outline-health`.
- **Nâng cấp đề cương bằng AI** sau khi kiểm tra chất lượng (4.3 / mục 14): từ kết quả kiểm tra
  chất lượng (điểm, lỗi, cảnh báo, gợi ý từng CLO), AI soạn lại toàn bộ đề cương khắc phục từng
  điểm — thống nhất thang đo CLO nhận thức/thái độ, bổ sung cấu phần đánh giá quá trình, cân
  trọng số = 100%, ánh xạ PLO/PI. Kết quả ghi thành **phiên bản mới (draft)**, giữ nguyên bản
  gốc để đối chiếu (diff). Endpoint `POST /api/outlines/{id}/improve`; nút "⚡ Nâng cấp đề cương
  bằng AI" hiện ngay trong khung kết quả kiểm tra chất lượng.
- **Đánh giá + nâng cấp Ngân hàng câu hỏi bằng AI** (4.5): AI chấm điểm chất lượng ngân hàng
  (gắn CLO/Bloom đúng, đáp án, phương án nhiễu, rubric, độ phủ, cân đối Bloom), chỉ ra lỗi/cảnh
  báo từng câu; nút "⚡ Nâng cấp câu hỏi bằng AI" viết lại các câu **chưa duyệt** có vấn đề (bổ
  sung đáp án/phương án/rubric, sửa Bloom sai) và đặt lại trạng thái nháp để thẩm định lại — câu
  **Đã duyệt không bị thay đổi**. Endpoint `GET /api/courses/{id}/questions/qa-review`,
  `POST /api/courses/{id}/questions/improve`.
- **Đánh giá + nâng cấp Ma trận đề thi bằng AI** (mục 11/12): AI đánh giá blueprint theo AUN-QA
  (tổng điểm đúng thang, độ phủ CLO, cân đối Bloom, khả thi với ngân hàng Đã duyệt, alignment với
  cấu phần đánh giá) trả điểm + cảnh báo + đề xuất; nút "⚡ Nâng cấp/Tối ưu AI" nay **bám kết quả
  đánh giá** để khắc phục đúng điểm yếu. Endpoint `GET /api/matrices/{id}/qa-review`; `optimize`
  nhận thêm tham số `qa`.
- **Đánh giá + nâng cấp Giáo trình bằng AI** (4.4): với từng chương, AI chấm điểm chất lượng (độ
  phủ CLO, chiều sâu học thuật, cấu trúc, ví dụ, câu hỏi ôn tập) và nút "⚡ Nâng cấp chương bằng AI"
  viết lại nội dung khắc phục các điểm đó (cập nhật tại chỗ). Endpoint
  `GET /api/chapters/{id}/qa-review`, `POST /api/chapters/{id}/improve`.
- **Đánh giá + nâng cấp Bài giảng bằng AI** (mục 10): AI chấm điểm bài giảng (mục tiêu gắn CLO,
  cấu trúc sư phạm đầy đủ, ví dụ/thảo luận/bài tập/kiểm tra nhanh, slide cô đọng) và nút "⚡ Nâng
  cấp bài giảng bằng AI" viết lại nội dung + cập nhật slide. Endpoint
  `GET /api/lectures/{id}/qa-review`, `POST /api/lectures/{id}/improve`.

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
