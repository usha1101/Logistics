from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.scripts.seed_demo_users import seed_demo_users


def test_seed_demo_users_creates_and_is_idempotent(db_session: Session):
    # First seed run
    created_count = seed_demo_users(db_session)
    assert created_count == 5

    users = db_session.execute(select(User)).scalars().all()
    assert len(users) == 5

    usernames = {u.username for u in users}
    assert usernames == {"admin", "ops_manager", "fleet_manager", "warehouse_manager", "analyst"}

    roles = {u.role for u in users}
    assert roles == {
        UserRole.ADMIN.value,
        UserRole.OPERATIONS_MANAGER.value,
        UserRole.FLEET_MANAGER.value,
        UserRole.WAREHOUSE_MANAGER.value,
        UserRole.ANALYST.value,
    }

    # Second seed run must be completely idempotent (0 newly created)
    second_run_count = seed_demo_users(db_session)
    assert second_run_count == 0

    total_users_after = db_session.execute(select(User)).scalars().all()
    assert len(total_users_after) == 5
