"""Quản lý API key AI dùng chung toàn hệ thống — chỉ Admin (SPEC vận hành).

Admin nhập/sửa/xóa key Claude (anthropic) hoặc OpenAI; kích hoạt một key để
toàn hệ thống dùng. Người dùng kiểm tra trạng thái qua /api/ai-status.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
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


def _deactivate_others(db: Session, tenant_id) -> None:
    """Tắt mọi key đang active CỦA TRƯỜNG này (bulk UPDATE không tự lọc tenant → lọc tường minh)."""
    db.query(ApiKey).filter(ApiKey.tenant_id == tenant_id).update(
        {ApiKey.is_active: False}, synchronize_session=False
    )


def _out(k: ApiKey) -> dict:
    return {
        "id": k.id, "provider": k.provider, "name": k.name,
        "api_key_masked": _mask(decrypt_secret(k.api_key)),
        "model": k.model or DEFAULT_MODELS.get(k.provider, ""),
        "is_active": k.is_active,
        "created_at": k.created_at.isoformat() if k.created_at else None,
    }


# ---- Trạng thái AI: ai cũng gọi được (để cảnh báo khi chưa cấu hình) ----
@router.get("/ai-status")
def get_ai_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return ai_status(db)


# ---- Thống kê dùng AI (token + chi phí ước tính) — Admin ----
@router.get("/llm-usage")
def llm_usage(days: int = 30, db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    """Tổng token + chi phí ước tính trong N ngày, kèm phân rã theo chương trình."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    from app.models import LlmUsage, Program

    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    base = db.query(LlmUsage).filter(LlmUsage.created_at >= since)
    total_tokens = base.with_entities(func.coalesce(func.sum(LlmUsage.total_tokens), 0)).scalar() or 0
    total_cost = base.with_entities(func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0)).scalar() or 0.0
    calls = base.count()

    rows = (
        db.query(
            LlmUsage.program_id,
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0),
            func.count(LlmUsage.id),
        )
        .filter(LlmUsage.created_at >= since)
        .group_by(LlmUsage.program_id)
        .all()
    )
    prog_names = {p.id: p.name for p in db.query(Program).all()}
    by_program = [
        {"program_id": pid, "program_name": prog_names.get(pid, "(không gắn)"),
         "tokens": int(tok), "est_cost_usd": round(float(cost), 4), "calls": int(c)}
        for pid, tok, cost, c in rows
    ]
    by_program.sort(key=lambda x: -x["tokens"])

    # Phân rã theo TRƯỜNG (hữu ích cho Super-Admin; tenant-admin chỉ thấy trường mình do auto-filter).
    from app.models import Tenant

    trows = (
        db.query(LlmUsage.tenant_id,
                 func.coalesce(func.sum(LlmUsage.total_tokens), 0),
                 func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0),
                 func.count(LlmUsage.id))
        .filter(LlmUsage.created_at >= since)
        .group_by(LlmUsage.tenant_id).all()
    )
    tnames = {t.id: t.name for t in db.query(Tenant).execution_options(skip_tenant=True).all()}
    by_tenant = sorted(
        [{"tenant_id": tid, "tenant_name": tnames.get(tid, "(không gắn)"),
          "tokens": int(tok), "est_cost_usd": round(float(cost), 4), "calls": int(c)}
         for tid, tok, cost, c in trows],
        key=lambda x: -x["tokens"],
    )
    return {
        "days": days, "calls": calls, "total_tokens": int(total_tokens),
        "est_cost_usd": round(float(total_cost), 4),
        "by_program": by_program, "by_tenant": by_tenant,
    }


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
        api_key=encrypt_secret(payload.api_key.strip()),
        model=payload.model or DEFAULT_MODELS.get(payload.provider),
        is_active=payload.is_active, created_by=user.id,
    )
    if payload.is_active:
        # chỉ một key active tại một thời điểm — TRONG PHẠM VI TRƯỜNG
        _deactivate_others(db, user.tenant_id)
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
        obj.api_key = encrypt_secret(payload.api_key.strip())
    if payload.is_active is not None:
        if payload.is_active:
            _deactivate_others(db, user.tenant_id)
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
    _deactivate_others(db, user.tenant_id)
    obj.is_active = True
    db.commit()
    log_action(db, user.id, "api_key", kid, "activate")
    return _out(obj)


@router.post("/api-keys/{kid}/test")
def test_key(kid: int, db: Session = Depends(get_db), _: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if not obj:
        raise HTTPException(404, "Không tìm thấy API key")
    ok, msg = verify_key(obj.provider, decrypt_secret(obj.api_key), obj.model)
    return {"ok": ok, "message": msg}


@router.delete("/api-keys/{kid}", status_code=204)
def delete_key(kid: int, db: Session = Depends(get_db), user: User = Depends(ADMIN)):
    obj = db.get(ApiKey, kid)
    if obj:
        db.delete(obj)
        db.commit()
        log_action(db, user.id, "api_key", kid, "delete")
