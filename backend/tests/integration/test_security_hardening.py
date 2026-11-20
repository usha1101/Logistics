import time
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.rate_limiter import rate_limiter
from app.models.token import RefreshToken
from app.models.user import User, UserRole


def test_login_issues_access_and_refresh_tokens(client: TestClient, analyst_user: User):
    """Verify login issues both a short-lived access token and a refresh token."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert len(data["refresh_token"]) > 30


def test_refresh_token_rotation_success(client: TestClient, analyst_user: User):
    """Verify valid refresh token can be rotated to obtain a new token pair."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    orig_refresh = login_data["refresh_token"]

    # Rotate refresh token
    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": orig_refresh},
    )
    assert refresh_res.status_code == 200
    refresh_data = refresh_res.json()
    assert "access_token" in refresh_data
    assert "refresh_token" in refresh_data
    assert refresh_data["refresh_token"] != orig_refresh

    # Verify newly minted access token is valid
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "test_analyst"


def test_token_reuse_detection_and_family_revocation(client: TestClient, analyst_user: User):
    """
    CRITICAL SECURITY TEST:
    Attempting to reuse an already-rotated refresh token MUST detect compromise
    and invalidate all active tokens in that family.
    """
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    token_1 = login_res.json()["refresh_token"]

    # 2. Legitimate rotation (token_1 -> token_2)
    refresh_res_1 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert refresh_res_1.status_code == 200
    token_2 = refresh_res_1.json()["refresh_token"]

    # 3. Attacker reuses token_1 (replay attack / stolen token scenario)
    replay_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert replay_res.status_code == 401
    assert "reuse detected" in replay_res.json()["error"]["message"].lower()

    # 4. Now token_2 MUST also be revoked due to whole-family invalidation
    subsequent_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_2},
    )
    assert subsequent_res.status_code == 401


def test_expired_refresh_token_rejected(client: TestClient, db_session: Session, analyst_user: User):
    """Verify expired refresh tokens are rejected with 401."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Manually expire the token in the database
    from app.services.token_service import hash_token
    token_h = hash_token(refresh_token)
    record = db_session.query(RefreshToken).filter(RefreshToken.token_hash == token_h).first()
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 401
    assert "expired" in res.json()["error"]["message"].lower()


def test_logout_revokes_access_token_blacklist(client: TestClient, analyst_user: User):
    """Verify access tokens are added to revocation blacklist upon logout."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Verify access token works initially
    me_res_1 = client.get("/api/v1/auth/me", headers=headers)
    assert me_res_1.status_code == 200

    # Logout with refresh token payload
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token}, headers=headers)
    assert logout_res.status_code == 200

    # Access token must now be rejected as revoked
    me_res_2 = client.get("/api/v1/auth/me", headers=headers)
    assert me_res_2.status_code == 401
    assert "revoked" in me_res_2.json()["error"]["message"].lower()

    # Refresh token must also be revoked
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401


def test_rate_limiting_enforcement_on_login(client: TestClient, analyst_user: User):
    """Verify rate limiter blocks login requests exceeding configured threshold with 429."""
    rate_limiter.reset()
    limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE  # 10 requests / minute

    statuses = []
    for _ in range(limit + 2):
        res = client.post(
            "/api/v1/auth/login",
            json={"username": "test_analyst", "password": "AnalystPass#123"},
        )
        statuses.append(res.status_code)

    # First `limit` calls should succeed (200), subsequent should be rate-limited (429)
    assert statuses[:limit] == [200] * limit
    assert 429 in statuses[limit:]


def test_health_probes_liveness_and_readiness(client: TestClient):
    """Verify container orchestration health probes (/health/live, /health/ready)."""
    # Root probes
    live_res = client.get("/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"
    assert ready_res.json()["database"] == "connected"

    # API v1 prefixed probes
    live_v1 = client.get("/api/v1/health/live")
    assert live_v1.status_code == 200

    ready_v1 = client.get("/api/v1/health/ready")
    assert ready_v1.status_code == 200


def test_prometheus_metrics_endpoint(client: TestClient, analyst_user: User):
    """Verify /metrics exports valid Prometheus text exposition format."""
    # Generate some HTTP traffic
    client.get("/health/live")
    client.post(
        "/api/v1/auth/login",
        json={"username": "test_analyst", "password": "AnalystPass#123"},
    )

    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert "text/plain" in metrics_res.headers["content-type"]
    body = metrics_res.text
    assert "logipulse_http_requests_total" in body
    assert "logipulse_app_info" in body


def test_production_config_validation():
    """Verify production security validation rejects weak secrets, sqlite, and wildcard origins."""
    # 1. Insecure default secret rejected
    with pytest.raises(ValueError, match="JWT_SECRET_KEY must be a cryptographically secure string"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="dev-insecure-jwt-secret-key-change-in-production-logipulse-2026",
            DATABASE_URL="postgresql://user:pass@localhost:5432/logipulse",
            ALLOWED_ORIGINS=["https://app.logipulse.io"],
        )

    # 2. Too-short secret rejected
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="short-secret-under-32-chars",
            DATABASE_URL="postgresql://user:pass@localhost:5432/logipulse",
            ALLOWED_ORIGINS=["https://app.logipulse.io"],
        )

    # 3. SQLite in production rejected
    with pytest.raises(ValueError, match="Production environment cannot use SQLite"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="super-secure-production-jwt-secret-key-32-chars-long",
            DATABASE_URL="sqlite:///./prod.db",
            ALLOWED_ORIGINS=["https://app.logipulse.io"],
        )

    # 4. Wildcard origin in production rejected
    with pytest.raises(ValueError, match="Wildcard '\\*' is strictly forbidden"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="super-secure-production-jwt-secret-key-32-chars-long",
            DATABASE_URL="postgresql://user:pass@localhost:5432/logipulse",
            ALLOWED_ORIGINS=["*"],
        )

