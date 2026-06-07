"""Nhóm C — Pha C1: cô lập dữ liệu theo tenant ở tầng ứng dụng.

Cơ chế: gắn tenant vào `Session.info["tenant_id"]` (theo từng request — an toàn, không rò rỉ
contextvar/threadpool). Hai listener SQLAlchemy:
  - do_orm_execute  → TỰ LỌC mọi SELECT theo tenant_id (with_loader_criteria cho từng model có cột).
  - before_flush    → TỰ GÁN tenant_id cho bản ghi mới chưa có.

Khi chưa set tenant (test/dữ liệu cũ single-tenant) → lớp này TỰ TẮT (không đổi hành vi).
Truy vấn cần bỏ qua lọc (vd tra cứu user lúc đăng nhập, thao tác xuyên tenant của Super-Admin)
dùng execution_option `skip_tenant=True`.
"""
from __future__ import annotations

from sqlalchemy import event, text
from sqlalchemy.orm import Session, with_loader_criteria

from app.database import Base

_TENANT_MODELS: list | None = None
# Tenant mặc định dùng cho fallback khi GHI ngoài ngữ cảnh request (vd seed, ghi usage nền)
# để tránh tenant_id NULL trên Postgres (sau khi C2 đặt NOT NULL). None = chưa biết (test/sqlite).
_DEFAULT_TENANT_ID: int | None = None


def set_default_tenant_id(tid: int | None) -> None:
    global _DEFAULT_TENANT_ID
    _DEFAULT_TENANT_ID = tid


def set_session_tenant(db: Session, tenant_id: int | None) -> None:
    """Gắn tenant cho session hiện tại (gọi sau khi xác thực user).

    Trên Postgres còn đặt `app.tenant_id` để Row-Level Security (RLS) chặn ở tầng DB.
    """
    if tenant_id is None:
        return
    db.info["tenant_id"] = tenant_id
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # SET LOCAL áp cho transaction hiện tại; after_begin sẽ áp lại cho transaction sau.
        db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))


def _tenant_models() -> list:
    """Danh sách model nghiệp vụ có cột tenant_id (loại Tenant)."""
    global _TENANT_MODELS
    if _TENANT_MODELS is None:
        _TENANT_MODELS = [
            m.class_ for m in Base.registry.mappers if "tenant_id" in m.columns
        ]
    return _TENANT_MODELS


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state) -> None:  # noqa: ANN001
    if not state.is_select:
        return
    if state.execution_options.get("skip_tenant"):
        return
    tid = state.session.info.get("tenant_id")
    if tid is None:
        return
    # Dùng biểu thức trực tiếp (KHÔNG lambda) để tránh bẫy lambda-caching của SQLAlchemy
    # (lambda sẽ "đóng băng" giá trị tid của lần gọi đầu → rò rỉ tenant).
    opts = [
        with_loader_criteria(cls, cls.tenant_id == tid, include_aliases=True)
        for cls in _tenant_models()
    ]
    if opts:
        state.statement = state.statement.options(*opts)


@event.listens_for(Session, "before_flush")
def _assign_tenant_on_insert(session, _ctx, _instances) -> None:  # noqa: ANN001
    # Ưu tiên tenant của request; nếu không có (ghi nền/seed) → fallback tenant mặc định
    # (chỉ có giá trị trên Postgres sau khi đã cache; sqlite/test giữ None → không sao vì không NOT NULL).
    tid = session.info.get("tenant_id") or _DEFAULT_TENANT_ID
    if tid is None:
        return
    for obj in session.new:
        if hasattr(obj, "tenant_id") and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tid


@event.listens_for(Session, "after_begin")
def _set_rls_on_begin(session, _transaction, connection) -> None:  # noqa: ANN001
    """Mỗi transaction mới trên Postgres: áp lại app.tenant_id cho RLS (nếu đã biết tenant)."""
    if connection.dialect.name != "postgresql":
        return
    tid = session.info.get("tenant_id")
    if tid is not None:
        connection.exec_driver_sql(f"SET LOCAL app.tenant_id = {int(tid)}")

