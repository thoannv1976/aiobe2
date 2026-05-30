# CLAUDE.md

Tài liệu hướng dẫn cho Claude Code khi làm việc trong repo này.

## Bối cảnh
Đây là hệ thống **Quản lý Đề cương – Giáo trình – Ngân hàng câu hỏi – Đề thi theo chuẩn OBE / AUN-QA**.
Đặc tả đầy đủ nằm ở [`docs/SPEC.md`](docs/SPEC.md). **Luôn đọc SPEC trước khi thay đổi nghiệp vụ.**

Nguyên tắc nghiệp vụ bắt buộc (xem SPEC mục 1):
- Truy vết hai chiều xuyên suốt: PLO → PI; CLO ↔ PLO (kèm mức I/R/M); Assessment ↔ CLO; Question → CLO + Bloom.
- Kiểm tra "độ phủ": không PLO/CLO nào bị bỏ sót.
- Versioning + vòng đời trạng thái cho đề cương, ngân hàng, đề thi.
- Audit log cho mọi thao tác quan trọng.
- Ngôn ngữ chính: tiếng Việt. UI song ngữ Việt/Anh.

## Kiến trúc
Monorepo:
- `backend/` — FastAPI (Python 3.11), SQLAlchemy 2.x + Alembic, PostgreSQL. Chứa toàn bộ **logic OBE** (alignment, coverage, sinh đề) và REST API.
- `frontend/` — Next.js (App Router, TypeScript) + Tailwind. Giao diện các màn hình chính.
- `docker-compose.yml` — db (Postgres) + minio + api + web.
- `docs/SPEC.md` — đặc tả nguồn.

## Quy ước code
- Backend: type hints đầy đủ, Pydantic v2 cho schema I/O, tách `models / schemas / services / routers`.
- Logic OBE thuần (alignment, coverage, sinh đề) đặt ở `app/services/` và **phải có unit test** (`backend/tests`).
- LLM output phải validate bằng Pydantic trước khi dùng; ép trả JSON thuần.
- Soft-delete + archive cho tài liệu đã ban hành; không xóa cứng.
- Migration qua Alembic; mỗi thay đổi schema kèm migration.

## Lệnh thường dùng
```bash
# Backend (dev nhanh, SQLite)
cd backend && pip install -r requirements.txt
DATABASE_URL=sqlite:///./dev.db python -m app.seed      # seed dữ liệu mẫu
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload
pytest                                                   # chạy test logic OBE

# Toàn bộ stack (Postgres + MinIO + API + Web)
docker compose up --build

# Frontend
cd frontend && npm install && npm run dev
```

## Trạng thái triển khai
Xem `README.md` mục "Tiến độ theo Phase".
