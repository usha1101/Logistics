import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.token import RefreshToken, TokenBlacklist
from app.models.user import User

logger = logging.getLogger("app.services.token")


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw token string."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_token_pair(
    db: Session,
    user: User,
    family_id: Optional[str] = None,
) -> Tuple[str, str, int]:
    """
    Issues a new access token (short-lived) and a refresh token (persisted in DB).
    Returns (access_token, raw_refresh_token, expires_in_seconds).
    """
    access_jti = str(uuid.uuid4())
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        jti=access_jti,
    )

    raw_refresh = secrets.token_urlsafe(48)
    token_h = hash_token(raw_refresh)
    refresh_jti = str(uuid.uuid4())
    family = family_id or str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_record = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_h,
        jti=refresh_jti,
        family_id=family,
        is_revoked=False,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(refresh_record)
    db.commit()

    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return access_token, raw_refresh, expires_in


def rotate_refresh_token(
    db: Session,
    raw_token: str,
) -> Tuple[str, str, User, int]:
    """
    Validates a refresh token and rotates it:
    - If the token is already revoked: DETECTS COMPROMISE, revokes the entire token family, and rejects.
    - If valid: invalidates the current token, issues a new token pair in the same family.
    Returns (new_access_token, new_refresh_token, user, expires_in_seconds).
    """
    token_h = hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_h)
    record = db.execute(stmt).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Compromise Detection: Token reuse
    if record.is_revoked:
        logger.warning(
            "SECURITY ALERT: Revoked refresh token reuse detected for family %s, user %s. "
            "Invalidating entire token family to mitigate token theft.",
            record.family_id,
            record.user_id,
        )
        # Revoke entire token family
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == record.family_id)
            .values(is_revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Revoked refresh token reuse detected. All active sessions in this family have been terminated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Check expiration
    now = datetime.now(timezone.utc)
    record_expires = record.expires_at
    if record_expires.tzinfo is None:
        record_expires = record_expires.replace(tzinfo=timezone.utc)

    if record_expires < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Verify user
    user_stmt = select(User).where(User.id == record.user_id)
    user = db.execute(user_stmt).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Invalidate old token and issue new token pair within same family
    record.is_revoked = True
    record.revoked_at = now

    new_raw_refresh = secrets.token_urlsafe(48)
    new_token_h = hash_token(new_raw_refresh)
    new_refresh_jti = str(uuid.uuid4())
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_record_id = str(uuid.uuid4())

    new_record = RefreshToken(
        id=new_record_id,
        user_id=user.id,
        token_hash=new_token_h,
        jti=new_refresh_jti,
        family_id=record.family_id,
        is_revoked=False,
        expires_at=new_expires_at,
        created_at=now,
    )
    record.replaced_by_token_id = new_record_id

    db.add(new_record)
    db.commit()

    # Issue new access token
    new_access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        jti=str(uuid.uuid4()),
    )
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return new_access_token, new_raw_refresh, user, expires_in


def blacklist_access_token(
    db: Session,
    jti: str,
    user_id: str,
    exp_timestamp: int,
) -> None:
    """Records an access token's JTI in the token blacklist until its expiration."""
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    # Check if already blacklisted
    stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
    existing = db.execute(stmt).scalar_one_or_none()
    if not existing:
        blacklist_item = TokenBlacklist(
            id=str(uuid.uuid4()),
            jti=jti,
            token_type="access",
            user_id=user_id,
            expires_at=expires_at,
            created_at=now,
        )
        db.add(blacklist_item)
        db.commit()


def is_token_blacklisted(db: Session, jti: str) -> bool:
    """Checks whether a token's JTI has been revoked/blacklisted."""
    stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
    return db.execute(stmt).scalar_one_or_none() is not None


def revoke_refresh_token(db: Session, raw_token: str) -> bool:
    """Revokes a specific refresh token."""
    token_h = hash_token(raw_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_h)
    record = db.execute(stmt).scalar_one_or_none()
    if record and not record.is_revoked:
        record.is_revoked = True
        record.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False
