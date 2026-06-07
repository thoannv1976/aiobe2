"""Khởi tạo SQLAlchemy engine/session. Hỗ trợ SQLite (dev) và Postgres/Cloud SQL (prod).

Pool kết nối cấu hình cho tải lớn (nhiều instance Cloud Run × nhiều người dùng):
pool_size / max_overflow / pool_recycle / pool_timeout lấy từ settings.
Tùy chọn dùng Cloud SQL Python Connector khi đặt instance_connection_name.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")


def _make_engine():
    # SQLite (dev/test): giữ đơn giản, không cấu hình pool kiểu server.
    if _is_sqlite:
        return create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )

    pool_kwargs = dict(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
    )

    # Cloud SQL Python Connector (tùy chọn): kết nối an toàn không cần IP công khai.
    if settings.instance_connection_name:
        from google.cloud.sql.connector import Connector, IPTypes  # import lười

        ip_type = IPTypes.PRIVATE if settings.db_use_private_ip else IPTypes.PUBLIC
        connector = Connector()

        def _getconn():
            return connector.connect(
                settings.instance_connection_name,
                "pg8000",
                user=settings.db_user,
                password=settings.db_password,
                db=settings.db_name,
                ip_type=ip_type,
            )

        return create_engine("postgresql+pg8000://", creator=_getconn, **pool_kwargs)

    # Mặc định: dùng DATABASE_URL (vd Cloud SQL qua unix socket /cloudsql/INSTANCE).
    return create_engine(settings.database_url, **pool_kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Rollback để một lỗi không để lại transaction "aborted" trên connection dùng chung (pool).
        db.rollback()
        raise
    finally:
        db.close()
