"""Readiness endpoint tests."""

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "status" in body
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["file_storage"] == "ok"


def test_readiness_endpoint_returns_503_when_not_ready(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.get_readiness_status",
        lambda: {"status": "not_ready", "checks": {"database": "error:OperationalError"}},
    )
    response = api_client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
