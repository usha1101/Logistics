import logging
import sys
from pathlib import Path
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo_users")

DEMO_ACCOUNTS = [
    {
        "username": "admin",
        "email": "admin@logipulse.io",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN.value,
    },
    {
        "username": "ops_manager",
        "email": "ops@logipulse.io",
        "full_name": "Operations Manager",
        "role": UserRole.OPERATIONS_MANAGER.value,
    },
    {
        "username": "fleet_manager",
        "email": "fleet@logipulse.io",
        "full_name": "Fleet Manager",
        "role": UserRole.FLEET_MANAGER.value,
    },
    {
        "username": "warehouse_manager",
        "email": "warehouse@logipulse.io",
        "full_name": "Warehouse Manager",
        "role": UserRole.WAREHOUSE_MANAGER.value,
    },
    {
        "username": "analyst",
        "email": "analyst@logipulse.io",
        "full_name": "Data Analyst",
        "role": UserRole.ANALYST.value,
    },
]


def seed_demo_users(db: Session = None) -> int:
    """
    Idempotently seeds the 5 demo accounts.
    Never overwrites or deletes existing users.
    Returns count of newly created users.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    created_count = 0
    try:
        password = settings.DEMO_PASSWORD
        hashed_pwd = hash_password(password)

        for account in DEMO_ACCOUNTS:
            stmt = select(User).where(
                or_(
                    User.username == account["username"],
                    User.email == account["email"],
                )
            )
            existing = db.execute(stmt).scalar_one_or_none()
            if existing:
                logger.info(
                    f"Account '{account['username']}' already exists (ID: {existing.id}, Role: {existing.role}). Skipping."
                )
                continue

            user = User(
                username=account["username"],
                email=account["email"],
                full_name=account["full_name"],
                role=account["role"],
                hashed_password=hashed_pwd,
                is_active=True,
            )
            db.add(user)
            created_count += 1
            logger.info(f"Created demo account: '{account['username']}' ({account['role']})")

        db.commit()
        logger.info(f"Seeding completed. {created_count} new demo accounts created.")
        return created_count
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    seed_demo_users()

