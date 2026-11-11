from fastapi.testclient import TestClient


def test_request_id_generated_and_returned_in_header(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) > 0


def test_custom_request_id_preserved_in_response(client: TestClient):
    custom_id = "test-custom-trace-id-12345"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id

