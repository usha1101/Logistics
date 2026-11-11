from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole


def test_login_success_with_username(client: TestClient, analyst_user: User):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["username"] == "test_analyst"
    assert data["user"]["role"] == UserRole.ANALYST.value
    # Ensure password hash is NEVER exposed
    assert "hashed_password" not in data["user"]
    assert "password" not in data["user"]


def test_login_success_with_email(client: TestClient, analyst_user: User):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test_analyst@logipulse.io", "password": "AnalystPass#123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test_analyst@logipulse.io"


def test_login_incorrect_password(client: TestClient, analyst_user: User):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "WrongPassword#999"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert "request_id" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Invalid credentials"


def test_login_unknown_username(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user", "password": "SomePassword#123"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Invalid credentials"


def test_inactive_user_cannot_authenticate(client: TestClient, db_session: Session):
    inactive = User(
        username="inactive_user",
        email="inactive@logipulse.io",
        full_name="Inactive Person",
        role=UserRole.ANALYST.value,
        hashed_password=hash_password("InactivePass#123"),
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()

    # 1. Login attempt should fail with 401
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "inactive_user", "password": "InactivePass#123"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "User account is inactive"

    # 2. Even with a forged token, /auth/me should reject inactive user
    token = create_access_token(
        user_id=inactive.id,
        username=inactive.username,
        role=inactive.role,
    )
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 401
    assert me_resp.json()["error"]["message"] == "User account is deactivated"


def test_get_me_without_token(client: TestClient):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Authentication token required"


def test_get_me_with_valid_token(client: TestClient, analyst_user: User, analyst_headers: dict):
    response = client.get("/api/v1/auth/me", headers=analyst_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == analyst_user.id
    assert data["username"] == "test_analyst"
    assert data["email"] == "test_analyst@logipulse.io"
    assert data["role"] == UserRole.ANALYST.value
    assert data["is_active"] is True
    assert "hashed_password" not in data


def test_invalid_jwt_rejected(client: TestClient):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.malformed.token"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Invalid authentication token"


def test_expired_jwt_rejected(client: TestClient, analyst_user: User):
    expired_token = create_access_token(
        user_id=analyst_user.id,
        username=analyst_user.username,
        role=analyst_user.role,
        expires_delta=timedelta(seconds=-1),
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert data["error"]["message"] == "Authentication token has expired"


def test_logout_endpoint(client: TestClient, analyst_headers: dict):
    response = client.post("/api/v1/auth/logout", headers=analyst_headers)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Stateless token must be discarded by client" in data["message"]

