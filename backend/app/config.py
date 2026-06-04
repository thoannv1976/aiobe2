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

    # Pool kết nối DB (Postgres/Cloud SQL). Bỏ qua với SQLite.
    db_pool_size: int = 5          # số kết nối thường trực mỗi instance
    db_max_overflow: int = 10      # kết nối tạm khi cao điểm
    db_pool_recycle: int = 1800    # tái tạo kết nối sau 30' (tránh kết nối chết của Cloud SQL)
    db_pool_timeout: int = 30      # giây chờ lấy kết nối từ pool

    # (Tùy chọn) Cloud SQL Python Connector — chỉ bật khi đặt instance_connection_name.
    # Không đặt → dùng database_url như thường (vd unix socket /cloudsql/...).
    instance_connection_name: str = ""   # project:region:instance
    db_user: str = ""
    db_password: str = ""
    db_name: str = ""
    db_use_private_ip: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
