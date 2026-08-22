"""Authorization foundation tests — auth hardening, production config, cross-user access."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.exceptions import SecurityConfigurationError
from app.application.token_service import create_access_token
from app.infrastructure.config import Settings, get_settings


@pytest.fixture
def enforced_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()


def _register(api_client: TestClient, email: str) -> tuple[str, str]:
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["access_token"], body["user"]["account_id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_owned_project(api_client: TestClient, token: str, name: str = "Owned") -> str:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": name},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_expired_bearer_token_is_rejected(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()

    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": "expired@example.com", "password": "secure-password"},
    )
    user = register.json()["user"]
    expired_token = create_access_token(
        secret="dev-only-auth-secret-change-me",
        account_id=user["account_id"],
        user_id=UUID(user["id"]),
        email=user["email"],
        display_name=user.get("display_name"),
        expires_in_hours=-1,
    )
    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_invalid_bearer_token_signature_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()

    user_id = uuid4()
    token = create_access_token(
        secret="dev-only-auth-secret-change-me",
        account_id=str(user_id),
        user_id=user_id,
        email="invalid@example.com",
        display_name=None,
        expires_in_hours=1,
    )
    tampered = f"{token}invalid"
    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert response.status_code == 401


def test_malformed_bearer_token_is_rejected(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    response = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


def test_production_requires_explicit_secure_auth_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "false")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "true")
    monkeypatch.delenv("AUTH_JWT_SECRET", raising=False)
    with pytest.raises(SecurityConfigurationError) as exc_info:
        Settings().validate_security_configuration()
    issues = exc_info.value.details["issues"]
    assert "AUTH_REQUIRED must be true in production" in issues
    assert "PROJECT_ACCESS_ENFORCED must be true in production" in issues
    assert "AUTH_ALLOW_LEGACY_ACTOR must be false in production" in issues
    assert "AUTH_JWT_SECRET must be configured in production" in issues
    assert "ENTITLEMENT_ENFORCEMENT_ENABLED must be true in production" in issues
    assert "FILE_STORAGE_ROOT must be configured in production" in issues


def test_production_requires_entitlement_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "false")
    monkeypatch.setenv("AUTH_JWT_SECRET", "production-test-secret-value")
    monkeypatch.setenv("FILE_STORAGE_ROOT", "/tmp/structuralai-test-storage")
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "false")
    with pytest.raises(SecurityConfigurationError) as exc_info:
        Settings().validate_security_configuration()
    assert "ENTITLEMENT_ENFORCEMENT_ENABLED must be true in production" in exc_info.value.details["issues"]


def test_production_rejects_development_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "false")
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("FILE_STORAGE_ROOT", "/tmp/structuralai-test-storage")
    monkeypatch.setenv("AUTH_JWT_SECRET", "dev-only-auth-secret-change-me")
    with pytest.raises(SecurityConfigurationError):
        Settings().validate_security_configuration()


def test_legacy_actor_disabled_when_auth_required(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "false")
    get_settings.cache_clear()
    response = api_client.get("/api/v1/projects", headers={"X-Actor-Id": "legacy-user"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path_template"),
    [
        ("get", "/api/v1/projects/{project_id}/revisions"),
        ("get", "/api/v1/projects/{project_id}/memory"),
        ("post", "/api/v1/projects/{project_id}/validate"),
        ("get", "/api/v1/traceability/graph?project_id={project_id}"),
        ("get", "/api/v1/reports?project_id={project_id}"),
        ("get", "/api/v1/integrations/{project_id}/executions"),
        ("get", "/api/v1/agent-executions?project_id={project_id}"),
        ("get", "/api/v1/approvals?project_id={project_id}"),
    ],
)
def test_non_owner_cannot_access_project_scoped_resources(
    api_client: TestClient,
    enforced_project_access: None,
    method: str,
    path_template: str,
) -> None:
    owner_token, _ = _register(api_client, "owner-resources@example.com")
    other_token, _ = _register(api_client, "other-resources@example.com")
    project_id = _create_owned_project(api_client, owner_token)
    path = path_template.format(project_id=project_id)
    request = getattr(api_client, method)
    response = request(path, headers=_auth_headers(other_token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PROJECT_FORBIDDEN"


def test_owner_can_access_project_memory(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    token, _ = _register(api_client, "memory-owner@example.com")
    project_id = _create_owned_project(api_client, token)
    response = api_client.get(
        f"/api/v1/projects/{project_id}/memory",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
