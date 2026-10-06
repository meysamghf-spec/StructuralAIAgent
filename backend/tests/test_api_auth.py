"""Authentication and project authorization API tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.password_service import verify_password
from app.infrastructure.config import get_settings
from app.infrastructure.database.connection import get_connection


@pytest.fixture
def enforced_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()


def test_register_and_login_issue_bearer_token(api_client: TestClient) -> None:
    register = api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "engineer@example.com",
            "password": "secure-password",
            "display_name": "Engineer",
        },
    )
    assert register.status_code == 201
    body = register.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "engineer@example.com"

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "secure-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["account_id"] == login.json()["user"]["account_id"]


def test_register_persists_password_hash_and_login_me_features_succeed(
    api_client: TestClient,
) -> None:
    email = f"auth-regression-{uuid.uuid4().hex}@example.com"
    password = "secure-password"

    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Regression User"},
    )
    assert register.status_code == 201

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email, password_hash, account_id FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
    assert row is not None
    assert row["email"] == email
    assert row["password_hash"].startswith("scrypt$")
    assert verify_password(password, row["password_hash"]) is True

    login = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token

    auth_headers = {"Authorization": f"Bearer {token}"}
    me = api_client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["account_id"] == row["account_id"]

    features = api_client.get("/api/v1/auth/me/features", headers=auth_headers)
    assert features.status_code == 200
    assert isinstance(features.json()["features"], dict)

    wrong_password = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"

    unknown_email = api_client.post(
        "/api/v1/auth/login",
        json={"email": f"missing-{uuid.uuid4().hex}@example.com", "password": password},
    )
    assert unknown_email.status_code == 401
    assert unknown_email.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_project_owner_can_access_project(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    owner_headers = {"X-Actor-Id": "owner-user"}
    created = api_client.post(
        "/api/v1/projects",
        json={"name": "Owned Project"},
        headers=owner_headers,
    )
    assert created.status_code == 201
    project_id = created.json()["project"]["id"]

    fetched = api_client.get(f"/api/v1/projects/{project_id}", headers=owner_headers)
    assert fetched.status_code == 200


def test_non_owner_cannot_access_project(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    owner_headers = {"X-Actor-Id": "owner-user"}
    other_headers = {"X-Actor-Id": "other-user"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Private Project"},
        headers=owner_headers,
    ).json()["project"]["id"]

    denied = api_client.get(f"/api/v1/projects/{project_id}", headers=other_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PROJECT_FORBIDDEN"


def test_bearer_token_resolves_to_owned_projects(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": "token-owner@example.com", "password": "secure-password"},
    )
    token = register.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Token Project"},
        headers=auth_headers,
    ).json()["project"]["id"]

    listed = api_client.get("/api/v1/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()["projects"]) == 1

    denied = api_client.get(f"/api/v1/projects/{project_id}")
    assert denied.status_code == 403
