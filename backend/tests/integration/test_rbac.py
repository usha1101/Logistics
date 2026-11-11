from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def test_admin_can_list_users(client: TestClient, admin_headers: dict, admin_user: User):
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(u["username"] == admin_user.username for u in data)
    # Verify hashed_password is NOT exposed
    for u in data:
        assert "hashed_password" not in u
        assert "password" not in u


def test_non_admin_denied_admin_list_users(client: TestClient, analyst_headers: dict):
    response = client.get("/api/v1/admin/users", headers=analyst_headers)
    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FORBIDDEN"
    assert "lacks required permissions" in data["error"]["message"]


def test_admin_can_create_user(client: TestClient, admin_headers: dict):
    new_user_payload = {
        "username": "new_fleet_lead",
        "email": "fleet_lead@logipulse.io",
        "full_name": "Fleet Commander",
        "role": UserRole.FLEET_MANAGER.value,
        "password": "SecureFleetPass#1",
    }
    response = client.post(
        "/api/v1/auth/register",
        json=new_user_payload,
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "new_fleet_lead"
    assert data["email"] == "fleet_lead@logipulse.io"
    assert data["role"] == UserRole.FLEET_MANAGER.value
    assert "hashed_password" not in data


def test_non_admin_denied_user_registration(client: TestClient, analyst_headers: dict):
    new_user_payload = {
        "username": "unauthorized_user",
        "email": "unauth@logipulse.io",
        "full_name": "Unauthorized Attempt",
        "role": UserRole.ANALYST.value,
        "password": "ValidPassword#123",
    }
    response = client.post(
        "/api/v1/auth/register",
        json=new_user_payload,
        headers=analyst_headers,
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "FORBIDDEN"


def test_register_duplicate_username_rejected(client: TestClient, admin_headers: dict, admin_user: User):
    duplicate_payload = {
        "username": admin_user.username,  # already exists
        "email": "different_email@logipulse.io",
        "full_name": "Duplicate User",
        "role": UserRole.ANALYST.value,
        "password": "ValidPassword#123",
    }
    response = client.post(
        "/api/v1/auth/register",
        json=duplicate_payload,
        headers=admin_headers,
    )
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "CONFLICT"
    assert "already registered" in data["error"]["message"]


def test_register_duplicate_email_rejected(client: TestClient, admin_headers: dict, admin_user: User):
    duplicate_payload = {
        "username": "unique_username_99",
        "email": admin_user.email,  # already exists
        "full_name": "Duplicate Email User",
        "role": UserRole.ANALYST.value,
        "password": "ValidPassword#123",
    }
    response = client.post(
        "/api/v1/auth/register",
        json=duplicate_payload,
        headers=admin_headers,
    )
    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "CONFLICT"
    assert "already registered" in data["error"]["message"]


def test_register_weak_password_rejected(client: TestClient, admin_headers: dict):
    weak_payload = {
        "username": "weak_pwd_user",
        "email": "weak@logipulse.io",
        "full_name": "Weak Pwd",
        "role": UserRole.ANALYST.value,
        "password": "short",  # under 8 chars
    }
    response = client.post(
        "/api/v1/auth/register",
        json=weak_payload,
        headers=admin_headers,
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_admin_can_update_user_role(client: TestClient, admin_headers: dict, analyst_user: User):
    patch_payload = {"role": UserRole.OPERATIONS_MANAGER.value}
    response = client.patch(
        f"/api/v1/admin/users/{analyst_user.id}/role",
        json=patch_payload,
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == analyst_user.id
    assert data["role"] == UserRole.OPERATIONS_MANAGER.value


def test_admin_cannot_demote_last_active_admin(client: TestClient, admin_headers: dict, admin_user: User):
    # Demoting oneself when there is only 1 active admin
    demote_payload = {"role": UserRole.ANALYST.value}
    response = client.patch(
        f"/api/v1/admin/users/{admin_user.id}/role",
        json=demote_payload,
        headers=admin_headers,
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "BAD_REQUEST"
    assert "Cannot demote the last remaining active administrator" in data["error"]["message"]


def test_update_role_user_not_found(client: TestClient, admin_headers: dict):
    response = client.patch(
        "/api/v1/admin/users/non-existent-user-id/role",
        json={"role": UserRole.OPERATIONS_MANAGER.value},
        headers=admin_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NOT_FOUND"

