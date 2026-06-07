"""Nhóm C — Pha C0: kiểm tra nền tảng dữ liệu multi-tenant (chưa enforce hành vi)."""
from app.database import Base
from app.models import Program, Question, Tenant, User


def test_tenants_table_exists():
    assert "tenants" in Base.metadata.tables


def test_all_business_tables_have_tenant_id():
    # Bảng nghiệp vụ phải có tenant_id; bảng tenants thì KHÔNG.
    for model in (User, Program, Question):
        assert "tenant_id" in model.__table__.columns, model.__tablename__
    assert "tenant_id" not in Tenant.__table__.columns


def test_tenant_has_lifecycle_fields():
    cols = Tenant.__table__.columns
    for f in ("code", "is_enabled", "activated_at", "valid_until"):
        assert f in cols
