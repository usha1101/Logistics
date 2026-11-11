from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.main import create_app


class SamplePayload(BaseModel):
    name: str = Field(..., min_length=3)
    count: int = Field(..., gt=0)


def test_404_error_envelope_shape():
    app = create_app()
    client = TestClient(app)

    response = client.get("/nonexistent/endpoint/route")
    assert response.status_code == 404
    data = response.json()

    assert "error" in data
    assert "request_id" in data
    error = data["error"]
    assert error["code"] == "NOT_FOUND"
    assert "message" in error
    assert "traceback" not in data
    assert "traceback" not in error


def test_422_validation_error_envelope_shape():
    app = create_app()
    test_router = APIRouter()

    @test_router.post("/test-validation")
    def sample_endpoint(payload: SamplePayload):
        return {"status": "success"}

    app.include_router(test_router)
    client = TestClient(app)

    # Missing required field 'count' and invalid 'name' length
    response = client.post("/test-validation", json={"name": "x"})
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert "request_id" in data
    error = data["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    assert isinstance(error["details"], list)
    assert len(error["details"]) > 0
    assert "traceback" not in data

