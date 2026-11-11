from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database.session import get_db
from app.main import create_app


def test_health_endpoints_ok(client: TestClient):
    for endpoint in ["/api/v1/health", "/health"]:
        response = client.get(endpoint)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"]["connected"] is True
        assert data["data_source"] == "SIMULATED"
        assert data["app"] == "LOGIPULSE Backend API"
        assert "version" in data
        assert "environment" in data
        assert "server_time_utc" in data


def test_health_endpoint_degraded_when_database_fails():
    app = create_app()

    def failing_get_db():
        mock_session = MagicMock()
        mock_session.execute.side_effect = OperationalError(
            "statement", {}, Exception("Database connection refused")
        )
        yield mock_session

    app.dependency_overrides[get_db] = failing_get_db
    client = TestClient(app)

    for endpoint in ["/api/v1/health", "/health"]:
        response = client.get(endpoint)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"]["connected"] is False
        assert data["data_source"] == "SIMULATED"

