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



def test_production_readiness_allows_mock_gateway_when_payments_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.application import health_service

    settings = SimpleNamespace(
        is_production=True,
        payments_enabled=False,
        crypto_payment_gateway="mock",
        app_env="production",
    )
    monkeypatch.setattr(health_service, "get_settings", lambda: settings)
    monkeypatch.setattr(health_service, "_check_database", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_file_storage", lambda _settings: "ok")

    assert health_service.get_readiness_status()["status"] == "ready"


def test_production_readiness_still_requires_btcpay_when_payments_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from app.application import health_service

    settings = SimpleNamespace(
        is_production=True,
        payments_enabled=True,
        crypto_payment_gateway="mock",
        app_env="production",
    )
    monkeypatch.setattr(health_service, "get_settings", lambda: settings)
    monkeypatch.setattr(health_service, "_check_database", lambda: "ok")
    monkeypatch.setattr(health_service, "_check_file_storage", lambda _settings: "ok")

    assert health_service.get_readiness_status()["status"] == "not_ready"
