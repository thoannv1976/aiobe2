"""Dependencies: lấy user hiện tại + kiểm tra vai trò (RBAC)."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.core.tenant import set_session_tenant
from app.database import get_db
from app.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không xác thực được",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise creds_exc
    # Tra cứu user KHÔNG lọc tenant (chưa biết tenant); email đang là duy nhất toàn cục.
    user = (
        db.query(User)
        .filter(User.email == payload["sub"])
        .execution_options(skip_tenant=True)
        .first()
    )
    if not user or not user.is_active:
        raise creds_exc
    # Super-Admin nền tảng: KHÔNG gắn tenant → thao tác xuyên trường (quản trị tenant).
    if user.role == Role.SUPER_ADMIN.value:
        return user
    # Người dùng của một trường: kiểm tra hiệu lực (hạn dùng) + cô lập theo tenant.
    if user.tenant_id is not None:
        from app.core.tenant import tenant_active
        from app.models import Tenant

        tenant = (
            db.query(Tenant).filter(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant=True).first()
        )
        if not tenant_active(tenant):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Trường đã hết hạn sử dụng hoặc bị tạm ngừng. Vui lòng gia hạn để tiếp tục.",
            )
    # Từ đây, MỌI truy vấn trên session này tự cô lập theo tenant của user.
    set_session_tenant(db, user.tenant_id)
    return user


def require_roles(*roles: Role) -> Callable:
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role in (Role.ADMIN.value, Role.SUPER_ADMIN.value):
            return user  # admin trường / super-admin nền tảng: toàn quyền
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không đủ quyền cho thao tác này",
            )
        return user

    return checker
