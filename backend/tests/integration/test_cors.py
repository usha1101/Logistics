from fastapi.testclient import TestClient
from app.main import create_app


def test_cors_preflight_allowed_origin():
    app = create_app()
    client = TestClient(app)

    allowed_origin = "http://localhost:5173"
    headers = {
        "Origin": allowed_origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "X-Request-ID",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_disallowed_origin():
    app = create_app()
    client = TestClient(app)

    disallowed_origin = "http://unauthorized-domain.com"
    headers = {
        "Origin": disallowed_origin,
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    # When an origin is not allowed, Access-Control-Allow-Origin header is omitted
    assert response.headers.get("access-control-allow-origin") is None

