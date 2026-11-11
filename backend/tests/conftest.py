import os
import sys
from pathlib import Path
from typing import Generator
import pytest

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import create_app
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token
import app.models.simulation  # Register model metadata

# In-memory SQLite engine configured for thread-isolated test execution
TEST_DATABASE_URL = "sqlite:///:memory:"

engine_test = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    connection = engine_test.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app(db_session: Session):
    application = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_user(db_session: Session) -> User:
    user = User(
        username="test_admin",
        email="test_admin@logipulse.io",
        full_name="Test Administrator",
        role=UserRole.ADMIN.value,
        hashed_password=hash_password("AdminPass#123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token(
        user_id=admin_user.id,
        username=admin_user.username,
        role=admin_user.role,
    )


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def analyst_user(db_session: Session) -> User:
    user = User(
        username="test_analyst",
        email="test_analyst@logipulse.io",
        full_name="Test Analyst",
        role=UserRole.ANALYST.value,
        hashed_password=hash_password("AnalystPass#123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def analyst_token(analyst_user: User) -> str:
    return create_access_token(
        user_id=analyst_user.id,
        username=analyst_user.username,
        role=analyst_user.role,
    )


@pytest.fixture
def analyst_headers(analyst_token: str) -> dict:
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest.fixture
def warehouse_manager_user(db_session: Session) -> User:
    user = User(
        username="test_wh_manager",
        email="wh_mgr@logipulse.io",
        full_name="Test Warehouse Manager",
        role=UserRole.WAREHOUSE_MANAGER.value,
        hashed_password=hash_password("WarehousePass#123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def warehouse_manager_token(warehouse_manager_user: User) -> str:
    return create_access_token(
        user_id=warehouse_manager_user.id,
        username=warehouse_manager_user.username,
        role=warehouse_manager_user.role,
    )


@pytest.fixture
def warehouse_manager_headers(warehouse_manager_token: str) -> dict:
    return {"Authorization": f"Bearer {warehouse_manager_token}"}


@pytest.fixture
def fleet_manager_user(db_session: Session) -> User:
    user = User(
        username="test_fleet_manager",
        email="fleet_mgr@logipulse.io",
        full_name="Test Fleet Manager",
        role=UserRole.FLEET_MANAGER.value,
        hashed_password=hash_password("FleetPass#123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def fleet_manager_token(fleet_manager_user: User) -> str:
    return create_access_token(
        user_id=fleet_manager_user.id,
        username=fleet_manager_user.username,
        role=fleet_manager_user.role,
    )


@pytest.fixture
def fleet_manager_headers(fleet_manager_token: str) -> dict:
    return {"Authorization": f"Bearer {fleet_manager_token}"}


@pytest.fixture
def fleet_headers(fleet_manager_headers: dict) -> dict:
    return fleet_manager_headers


@pytest.fixture
def ops_manager_user(db_session: Session) -> User:
    user = User(
        username="test_ops_manager",
        email="ops_mgr@logipulse.io",
        full_name="Test Operations Manager",
        role=UserRole.OPERATIONS_MANAGER.value,
        hashed_password=hash_password("OpsPass#123"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def ops_manager_token(ops_manager_user: User) -> str:
    return create_access_token(
        user_id=ops_manager_user.id,
        username=ops_manager_user.username,
        role=ops_manager_user.role,
    )


@pytest.fixture
def ops_manager_headers(ops_manager_token: str) -> dict:
    return {"Authorization": f"Bearer {ops_manager_token}"}


@pytest.fixture
def ops_headers(ops_manager_headers: dict) -> dict:
    return ops_manager_headers



