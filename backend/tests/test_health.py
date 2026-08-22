"""Readiness endpoint tests."""

from fastapi.testclient import TestClient


def test_health_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["checks"]["database"] == "ok"
