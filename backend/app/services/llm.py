"""Lớp LLM thống nhất: đọc API key active từ DB (do admin cấu hình),
hỗ trợ cả Claude (Anthropic) lẫn OpenAI. Mọi service AI gọi qua đây.

Ưu tiên: key active trong DB. Nếu DB chưa có, fallback về biến môi trường
ANTHROPIC_API_KEY (tương thích ngược).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import ApiKey

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
}


class LLMNotConfigured(RuntimeError):
    """Chưa có API key AI nào được kích hoạt."""


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


def llm_complete(system: str, user: str, max_tokens: int = 4000) -> str:
    """Gọi LLM (Claude hoặc OpenAI tùy key active), trả về text thuần."""
    provider, api_key, model = _resolve()

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
        return resp.choices[0].message.content or ""

    # mặc định: anthropic
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model or DEFAULT_MODELS["anthropic"],
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


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
