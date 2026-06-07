"""Quản trị tenant (trường) — chỉ Super-Admin nền tảng (Nhóm C / C3).

Cấp phát, gia hạn (renew sau thanh toán), tạm ngừng, cập nhật branding. Kèm endpoint
công khai /tenant/branding để frontend hiển thị logo/tên theo subdomain.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import hash_password
from app.core.tenant import resolve_request_tenant
from app.database import get_db
from app.models import Role, Tenant, User

router = APIRouter(prefix="/api", tags=["tenants"])
SUPER = require_roles(Role.SUPER_ADMIN)


def _out(t: Tenant) -> dict:
    return {
        "id": t.id, "code": t.code, "name": t.name, "status": t.status, "plan": t.plan,
        "contact_email": t.contact_email, "is_enabled": t.is_enabled,
        "activated_at": t.activated_at.isoformat() if t.activated_at else None,
        "valid_until": t.valid_until.isoformat() if t.valid_until else None,
        "settings": t.settings_json or {},
    }


class TenantCreate(BaseModel):
    code: str
    name: str
    contact_email: str | None = None
    valid_days: int = 365
    admin_email: str
    admin_password: str
    admin_name: str = "Quản trị trường"


class TenantUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    contact_email: str | None = None
    settings: dict | None = None   # branding: {logo_url, color, ...}


class EnableIn(BaseModel):
    valid_days: int = 365


@router.get("/tenants")
def list_tenants(db: Session = Depends(get_db), _: User = Depends(SUPER)):
    rows = db.query(Tenant).execution_options(skip_tenant=True).order_by(Tenant.id.desc()).all()
    return [_out(t) for t in rows]


@router.post("/tenants", status_code=201)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db), user: User = Depends(SUPER)):
    code = payload.code.strip().lower()
    if db.query(Tenant).filter(Tenant.code == code).execution_options(skip_tenant=True).first():
        raise HTTPException(400, "Mã trường (subdomain) đã tồn tại")
    now = datetime.utcnow()
    t = Tenant(
        code=code, name=payload.name, status="active", plan="standard",
        contact_email=payload.contact_email, is_enabled=True,
        activated_at=now, valid_until=now + timedelta(days=payload.valid_days),
        settings_json={},
    )
    db.add(t)
    db.flush()
    # Tạo admin đầu tiên của trường (gắn tenant tường minh).
    db.add(User(
        name=payload.admin_name, email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role=Role.ADMIN.value, tenant_id=t.id,
    ))
    db.commit()
    db.refresh(t)
    return _out(t)


@router.get("/tenants/{tid}")
def get_tenant(tid: int, db: Session = Depends(get_db), _: User = Depends(SUPER)):
    t = db.query(Tenant).filter(Tenant.id == tid).execution_options(skip_tenant=True).first()
    if not t:
        raise HTTPException(404, "Không tìm thấy trường")
    return _out(t)


@router.patch("/tenants/{tid}")
def update_tenant(tid: int, payload: TenantUpdate, db: Session = Depends(get_db), _: User = Depends(SUPER)):
    t = db.query(Tenant).filter(Tenant.id == tid).execution_options(skip_tenant=True).first()
    if not t:
        raise HTTPException(404, "Không tìm thấy trường")
    if payload.name is not None:
        t.name = payload.name
    if payload.status is not None:
        t.status = payload.status
    if payload.contact_email is not None:
        t.contact_email = payload.contact_email
    if payload.settings is not None:
        t.settings_json = payload.settings
    db.commit()
    db.refresh(t)
    return _out(t)


@router.post("/tenants/{tid}/enable")
def enable_tenant(tid: int, payload: EnableIn, db: Session = Depends(get_db), _: User = Depends(SUPER)):
    """Bật lại + GIA HẠN sau khi trường thanh toán (billing theo thời gian)."""
    t = db.query(Tenant).filter(Tenant.id == tid).execution_options(skip_tenant=True).first()
    if not t:
        raise HTTPException(404, "Không tìm thấy trường")
    now = datetime.utcnow()
    base = t.valid_until if (t.valid_until and t.valid_until > now) else now
    t.valid_until = base + timedelta(days=payload.valid_days)
    t.is_enabled = True
    t.status = "active"
    if not t.activated_at:
        t.activated_at = now
    db.commit()
    db.refresh(t)
    return _out(t)


@router.post("/tenants/{tid}/suspend")
def suspend_tenant(tid: int, db: Session = Depends(get_db), _: User = Depends(SUPER)):
    t = db.query(Tenant).filter(Tenant.id == tid).execution_options(skip_tenant=True).first()
    if not t:
        raise HTTPException(404, "Không tìm thấy trường")
    t.is_enabled = False
    t.status = "suspended"
    db.commit()
    db.refresh(t)
    return _out(t)


@router.get("/tenant/branding")
def branding(request: Request, db: Session = Depends(get_db)):
    """Công khai: trả thông tin nhận diện theo subdomain (logo/tên/màu) cho frontend."""
    t = resolve_request_tenant(db, request.headers.get("host"), request.headers.get("x-tenant"))
    if not t:
        return {"tenant": None, "name": "OBE / AUN-QA", "logo_url": None, "color": None}
    s = t.settings_json or {}
    return {
        "tenant": t.code, "name": s.get("display_name") or t.name,
        "logo_url": s.get("logo_url"), "color": s.get("color"),
        "active": t.is_enabled, "valid_until": t.valid_until.isoformat() if t.valid_until else None,
    }
