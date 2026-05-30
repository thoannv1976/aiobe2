"""Ghi nhật ký thao tác (audit log) — SPEC 1, 4.7."""
from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    user_id: int | None,
    entity: str,
    entity_id: int | None,
    action: str,
    diff: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            diff_json=diff or {},
        )
    )
    db.commit()
