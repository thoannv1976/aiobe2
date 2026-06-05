"""Lớp LLM thống nhất: đọc API key active từ DB (do admin cấu hình),
hỗ trợ cả Claude (Anthropic) lẫn OpenAI. Mọi service AI gọi qua đây.

Ưu tiên: key active trong DB. Nếu DB chưa có, fallback về biến môi trường
ANTHROPIC_API_KEY (tương thích ngược).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.llm_context import current_scope
from app.database import SessionLocal
from app.models import ApiKey, LlmUsage

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
}

# Giá tham khảo USD / 1 triệu token (input, output) — để ƯỚC TÍNH chi phí.
_PRICING = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (0.8, 4.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gpt-4.1": (2.0, 8.0),
}

# Giới hạn số lời gọi LLM đồng thời mỗi instance (tránh quá tải/rate limit provider).
_sem = threading.Semaphore(max(1, settings.llm_max_concurrency))
_log = logging.getLogger("uvicorn.error")


class LLMNotConfigured(RuntimeError):
    """Chưa có API key AI nào được kích hoạt."""


class LLMQuotaExceeded(RuntimeError):
    """Vượt hạn mức token AI (theo chương trình)."""


def get_active_key(db: Session | None = None) -> ApiKey | None:
    """Lấy khóa API đang active. Tự mở session nếu không truyền."""
    own = db is None
    db = db or SessionLocal()
    try:
        return db.execute(
            select(ApiKey).where(ApiKey.is_active == True)  # noqa: E712
        ).scalars().first()
    finally:
        if own:
            db.close()


def ai_status(db: Session | None = None) -> dict:
    """Trạng thái cấu hình AI cho frontend kiểm tra."""
    key = get_active_key(db)
    if key:
        return {
            "configured": True,
            "provider": key.provider,
            "model": key.model or DEFAULT_MODELS.get(key.provider, ""),
            "source": "db",
        }
    if settings.anthropic_api_key:
        return {
            "configured": True,
            "provider": "anthropic",
            "model": settings.anthropic_model,
            "source": "env",
        }
    return {"configured": False, "provider": None, "model": None, "source": None}


def _resolve() -> tuple[str, str, str]:
    """Trả (provider, api_key, model). Raise nếu chưa cấu hình."""
    key = get_active_key()
    if key:
        return key.provider, key.api_key, key.model or DEFAULT_MODELS.get(key.provider, "")
    if settings.anthropic_api_key:
        return "anthropic", settings.anthropic_api_key, settings.anthropic_model
    raise LLMNotConfigured(
        "Chưa có API key AI nào được kích hoạt. Vui lòng liên hệ quản trị viên cấu hình API."
    )


def _estimate_cost(model: str, prompt: int, completion: int) -> float:
    m = (model or "").lower()
    for key, (pin, pout) in _PRICING.items():
        if key in m:
            return (prompt * pin + completion * pout) / 1_000_000
    return 0.0


def _raw_complete(provider, api_key, model, system, user, max_tokens) -> tuple[str, dict]:
    """Gọi provider thật, trả (text, usage={prompt,completion,total})."""
    if provider == "openai":
        import openai

        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model or DEFAULT_MODELS["openai"],
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        u = getattr(resp, "usage", None)
        usage = {
            "prompt": getattr(u, "prompt_tokens", 0) or 0,
            "completion": getattr(u, "completion_tokens", 0) or 0,
        }
        usage["total"] = usage["prompt"] + usage["completion"]
        return (resp.choices[0].message.content or ""), usage

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model or DEFAULT_MODELS["anthropic"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    u = getattr(msg, "usage", None)
    usage = {
        "prompt": getattr(u, "input_tokens", 0) or 0,
        "completion": getattr(u, "output_tokens", 0) or 0,
    }
    usage["total"] = usage["prompt"] + usage["completion"]
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return text, usage


def _is_transient(e: Exception) -> bool:
    """Lỗi tạm thời nên thử lại: rate limit / quá tải / timeout / lỗi mạng 5xx."""
    n = type(e).__name__.lower()
    s = str(e).lower()
    if any(k in n for k in ("ratelimit", "overloaded", "timeout", "apiconnection", "internalserver", "serviceunavailable")):
        return True
    return any(k in s for k in ("rate limit", "429", "overloaded", "timeout", "temporarily", "502", "503", "529"))


def _record_usage(provider: str, model: str, usage: dict) -> None:
    """Ghi LlmUsage theo scope hiện tại (best-effort, không chặn luồng chính)."""
    scope = current_scope()
    db = SessionLocal()
    try:
        db.add(LlmUsage(
            provider=provider, model=model,
            prompt_tokens=usage.get("prompt", 0),
            completion_tokens=usage.get("completion", 0),
            total_tokens=usage.get("total", 0),
            est_cost_usd=_estimate_cost(model, usage.get("prompt", 0), usage.get("completion", 0)),
            user_id=scope.get("user_id"), program_id=scope.get("program_id"),
            course_id=scope.get("course_id"), job_id=scope.get("job_id"),
        ))
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        _log.warning("Ghi LlmUsage thất bại: %s", e)
    finally:
        db.close()


def _check_quota() -> None:
    """Chặn nếu chương trình đã vượt hạn mức token trong ngày (nếu có cấu hình)."""
    quota = settings.llm_daily_token_quota_per_program
    scope = current_scope()
    pid = scope.get("program_id")
    if not quota or not pid:
        return
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    db = SessionLocal()
    try:
        used = db.query(func.coalesce(func.sum(LlmUsage.total_tokens), 0)).filter(
            LlmUsage.program_id == pid, LlmUsage.created_at >= start
        ).scalar() or 0
        if used >= quota:
            raise LLMQuotaExceeded(
                f"Chương trình đã dùng {used:,}/{quota:,} token AI trong ngày. "
                "Vui lòng thử lại ngày mai hoặc liên hệ quản trị tăng hạn mức."
            )
    finally:
        db.close()


def llm_complete(system: str, user: str, max_tokens: int = 4000) -> str:
    """Gọi LLM có kiểm soát: hạn mức → giới hạn đồng thời → retry/backoff → ghi usage."""
    provider, api_key, model = _resolve()
    model = model or DEFAULT_MODELS.get(provider, "")
    _check_quota()

    last_err: Exception | None = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            with _sem:
                text, usage = _raw_complete(provider, api_key, model, system, user, max_tokens)
            _record_usage(provider, model, usage)
            return text
        except Exception as e:  # noqa: BLE001
            last_err = e
            if not _is_transient(e) or attempt >= settings.llm_max_retries:
                raise
            delay = settings.llm_retry_base_delay * (2 ** attempt)
            _log.warning("LLM lỗi tạm thời (%s), thử lại sau %.1fs (lần %d)", e, delay, attempt + 1)
            time.sleep(delay)
    raise last_err  # type: ignore[misc]


def verify_key(provider: str, api_key: str, model: str | None = None) -> tuple[bool, str]:
    """Gọi thử một request rất ngắn để xác minh key dùng được."""
    try:
        if provider == "openai":
            import openai

            client = openai.OpenAI(api_key=api_key)
            client.chat.completions.create(
                model=model or DEFAULT_MODELS["openai"],
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model=model or DEFAULT_MODELS["anthropic"],
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
        return True, "OK"
    except Exception as e:  # noqa: BLE001
        return False, str(e)
