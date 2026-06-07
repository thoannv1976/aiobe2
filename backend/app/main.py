"""Điểm vào FastAPI cho hệ thống OBE/AUN-QA."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core import tenant as _tenant  # noqa: F401  (đăng ký listener cô lập tenant)
from app.database import Base, engine
from app.routers import (
    apikeys,
    assignments,
    auth,
    exams,
    extraction,
    jobs,
    lectures,
    outlines,
    programs,
    questions,
    reports,
    tenants,
    textbooks,
)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, programs, outlines, textbooks, questions, exams, extraction, reports, assignments, apikeys, lectures, jobs, tenants):
    app.include_router(r.router)


@app.on_event("startup")
def on_startup() -> None:
    # Dev tiện lợi (SQLite): tạo bảng nếu chưa có.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        _cache_default_tenant()
        return
    # Production (Postgres/Cloud SQL): tự chạy migration khi khởi động để schema luôn
    # khớp code, tránh lỗi 500 khi container deploy trước migrate job (idempotent, an toàn).
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
    except Exception as e:  # noqa: BLE001
        # Không chặn app khởi động nếu migrate lỗi (vd quyền) — log để theo dõi.
        import logging

        logging.getLogger("uvicorn.error").warning("Auto-migrate khi startup thất bại: %s", e)
    _cache_default_tenant()


def _cache_default_tenant() -> None:
    """Nạp id tenant mặc định vào bộ nhớ để fallback khi GHI ngoài ngữ cảnh request."""
    try:
        from sqlalchemy import text

        from app.core.tenant import set_default_tenant_id

        with engine.connect() as c:
            tid = c.execute(text("SELECT id FROM tenants WHERE code = 'default'")).scalar()
        if tid:
            set_default_tenant_id(int(tid))
    except Exception:  # noqa: BLE001
        pass  # bảng tenants có thể chưa tồn tại (fresh dev) — bỏ qua


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}
