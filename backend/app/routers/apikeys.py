"""Quản lý API key AI dùng chung toàn hệ thống — chỉ Admin (SPEC vận hành).

Admin nhập/sửa/xóa key Claude (anthropic) hoặc OpenAI; kích hoạt một key để
toàn hệ thống dùng. Người dùng kiểm tra trạng thái qua /api/ai-status.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import ApiKey, Role, User
from app.services.audit import log_action
from app.services.llm import DEFAULT_MODELS, ai_status, verify_key

router = APIRouter(prefix="/api", tags=["apikeys"])
ADMIN = require_roles(Role.ADMIN)

PROVIDERS = {"anthropic", "openai"}


class ApiKeyIn(BaseModel):
    provider: str  # anthropic | openai
    name: str = ""
    api_key: str
    model: str | None = None
    is_active: bool = True


class ApiKeyUpdate(BaseModel):
    name: str | None = None
    api_key: str | None = None  # chỉ cập nhật nếu truyền (tránh ghi đè bằng giá trị mask)
    model: str | None = None
    is_active: bool | None = None


def _mask(key: str) -> str:
    if not key:
        return ""
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "••••"


def _out(k: ApiKey) -> dict:
    return {
        "id": k.id, "provider": k.provider, "name": k.name,
        "api_key_masked": _mask(k.api_key),
        "model": k.model or DEFAULT_MODELS.get(k.provider, ""),
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


# ---- Trạng thái AI: ai cũng gọi được (để cảnh báo khi chưa cấu hình) ----
@router.get("/ai-status")
def get_ai_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return ai_status(db)


# ---- CRUD: chỉ Admin ----
@router.get("/api-keys")
def list_keys(db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    return [_out(k) for k in db.query(ApiKey).order_by(ApiKey.id.desc()).all()]


@router.post("/api-keys", status_code=201)
def create_key(payload: ApiKeyIn, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    if payload.provider not in PROVIDERS:
        raise HTTPException(400, "Nhà cung cấp không hợp lệ (anthropic | openai)")
    if not payload.api_key.strip():
        raise HTTPException(400, "Thiếu API key")
    obj = ApiKey(
        provider=payload.provider, name=payload.name,
        api_key=payload.api_key.strip(),
        model=payload.model or DEFAULT_MODELS.get(payload.provider),
        is_active=payload.is_active, created_by=user.id,
    )
    if payload.is_active:
        # chỉ một key active tại một thời điểm
        db.query(ApiKey).update({ApiKey.is_active: False})
    db.add(obj)
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "api_key", obj.id, "create", {"provider": obj.provider})
    return _out(obj)


@router.patch("/api-keys/{kid}")
def update_key(kid: int, payload: ApiKeyUpdate, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy API key")
    if payload.name is not None:
        obj.name = payload.name
    if payload.model is not None:
        obj.model = payload.model
    if payload.api_key:  # chỉ đổi khi có giá trị thực
        obj.api_key = payload.api_key.strip()
    if payload.is_active is not None:
        if payload.is_active:
            db.query(ApiKey).update({ApiKey.is_active: False})
        obj.is_active = payload.is_active
    db.commit()
    db.refresh(obj)
    log_action(db, user.id, "api_key", kid, "update")
    return _out(obj)


@router.post("/api-keys/{kid}/activate")
def activate_key(kid: int, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy API key")
    db.query(ApiKey).update({ApiKey.is_active: False})
    obj.is_active = True
    db.commit()
    log_action(db, user.id, "api_key", kid, "activate")
    return _out(obj)


@router.post("/api-keys/{kid}/test")
def test_key(kid: int, db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy API key")
    ok, msg = verify_key(obj.provider, obj.api_key, obj.model)
    return {"ok": ok, "message": msg}


@router.delete("/api-keys/{kid}", status_code=204)
def delete_key(kid: int, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "api_key", kid, "delete")
