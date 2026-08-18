"""API integration tests — error envelope and validation."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_invalid_uuid_returns_422(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/projects/not-a-uuid")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "errors" in body["error"]["details"]


def test_error_envelope_shape_on_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "details" in body["error"]
