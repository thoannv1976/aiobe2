"""Điểm vào FastAPI cho hệ thống OBE/AUN-QA."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import (
    assignments,
    auth,
    exams,
    extraction,
    outlines,
    programs,
    questions,
    reports,
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

for r in (auth, programs, outlines, textbooks, questions, exams, extraction, reports, assignments):
    app.include_router(r.router)


@app.on_event("startup")
def on_startup() -> None:
    # Dev tiện lợi (SQLite): tạo bảng nếu chưa có.
    # Production (Postgres/Cloud SQL): schema do Alembic quản lý qua migrate job,
    # không create_all để tránh xung đột với migration.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}
