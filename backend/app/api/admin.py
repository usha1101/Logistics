from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserRoleUpdate

router = APIRouter(prefix="/admin", tags=["Admin User Management"])


@router.get(
    "/users",
    response_model=List[UserRead],
    summary="List all users (Admin only)",
)
def list_users(
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> List[UserRead]:
    stmt = select(User).order_by(User.created_at.asc())
    users = db.execute(stmt).scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.patch(
    "/users/{user_id}/role",
    response_model=UserRead,
    summary="Update a user's role (Admin only)",
)
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    target_user = db.execute(stmt).scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found",
        )

    new_role_value = payload.role.value if isinstance(payload.role, UserRole) else str(payload.role)

    # Protection: Prevent admin from removing their own admin status if they are the last active admin
    if target_user.id == current_admin.id and new_role_value != UserRole.ADMIN.value:
        active_admin_count = db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
        ).scalar() or 0

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining active administrator",
            )

    target_user.role = new_role_value
    db.commit()
    db.refresh(target_user)

    return UserRead.model_validate(target_user)

