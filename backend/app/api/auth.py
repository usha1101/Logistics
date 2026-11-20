from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_token_payload, get_current_user, require_roles
from app.core.config import settings
from app.core.security import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    TokenRefreshResponse,
    TokenResponse,
    UserCreate,
    UserRead,
)
from app.services.token_service import (
    blacklist_access_token,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and obtain JWT access token pair",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    identifier = payload.identifier

    stmt = select(User).where(
        or_(
            User.username == identifier,
            User.email == identifier,
        )
    )
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, expires_in = issue_token_pair(db, user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Rotate refresh token and obtain a new access token",
)
def refresh_access_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    new_access, new_refresh, user, expires_in = rotate_refresh_token(db, payload.refresh_token)
    return TokenRefreshResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get authenticated user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post(
    "/logout",
    summary="Invalidate active token session",
)
def logout(
    payload: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    token_payload: dict = Depends(get_current_token_payload),
    db: Session = Depends(get_db),
) -> dict:
    # 1. Invalidate active access token in blacklist
    jti = token_payload.get("jti")
    exp = token_payload.get("exp")
    if jti and exp:
        blacklist_access_token(db, jti=jti, user_id=current_user.id, exp_timestamp=exp)

    # 2. Invalidate refresh token if provided
    if payload and payload.refresh_token:
        revoke_refresh_token(db, payload.refresh_token)

    return {
        "message": "Successfully logged out. Stateless token must be discarded by client. Tokens have been revoked.",
        "user_id": current_user.id,
    }


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account (Admin only)",
)
def register_user(
    payload: UserCreate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> UserRead:
    # 1. Validate password strength
    pwd_err = validate_password_strength(payload.password)
    if pwd_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=pwd_err,
        )

    # 2. Check duplicate username
    stmt_uname = select(User).where(User.username == payload.username)
    if db.execute(stmt_uname).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already registered",
        )

    # 3. Check duplicate email
    stmt_email = select(User).where(User.email == payload.email)
    if db.execute(stmt_email).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{payload.email}' is already registered",
        )

    # 4. Create and persist user
    new_user = User(
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role.value if isinstance(payload.role, UserRole) else str(payload.role),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserRead.model_validate(new_user)

