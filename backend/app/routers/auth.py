from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import Role, User
from app.schemas.auth import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # OAuth2 form dùng `username` cho email. Email DUY NHẤT THEO TENANT (C2) →
    # phân giải tenant theo subdomain/X-Tenant rồi tra user trong đúng trường (C3).
    from app.core.tenant import resolve_request_tenant, tenant_active
    from app.models import Tenant

    tenant = resolve_request_tenant(
        db, request.headers.get("host"), request.headers.get("x-tenant")
    )
    q = db.query(User).filter(User.email == form.username).execution_options(skip_tenant=True)
    if tenant is not None:
        q = q.filter(User.tenant_id == tenant.id)
    user = q.first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sai email hoặc mật khẩu")
    # Chặn đăng nhập nếu trường hết hạn/đình chỉ (trừ Super-Admin nền tảng).
    if user.role != Role.SUPER_ADMIN.value and user.tenant_id is not None:
        t = tenant or (
            db.query(Tenant).filter(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant=True).first()
        )
        if not tenant_active(t):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Trường đã hết hạn sử dụng hoặc bị tạm ngừng.")
    token = create_access_token(user.email, user.role, tenant_id=user.tenant_id)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email đã tồn tại")
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))):
    return db.query(User).all()
