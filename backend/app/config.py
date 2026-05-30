"""Cấu hình ứng dụng (env-driven)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "OBE/AUN-QA System"
    # SQLite mặc định để chạy nhanh; Docker Compose sẽ truyền Postgres URL.
    database_url: str = "sqlite:///./dev.db"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12

    # AI extraction
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # Storage
    storage_dir: str = "./storage"

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
