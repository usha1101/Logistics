from fastapi.testclient import TestClient


def test_openapi_spec_served(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "LOGIPULSE Backend API"
    assert "/api/v1/health" in spec["paths"]
    assert "/health" in spec["paths"]
    assert "get" in spec["paths"]["/api/v1/health"]

