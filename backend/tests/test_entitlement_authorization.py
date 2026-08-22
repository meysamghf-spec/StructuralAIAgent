"""Entitlement-backed feature authorization tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.service_factory import build_digital_payment_agent, get_crypto_payment_gateway
from app.domain.models.payments import EntitlementStatus, PaymentStatus
from app.domain.models.optimization import OptimizationMode
from app.infrastructure.config import get_settings
from app.infrastructure.repositories.postgres_payment_repository import PostgresPaymentRepository


@pytest.fixture
def enforced_entitlements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture
def enforced_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_payment_gateway() -> None:
    gateway = get_crypto_payment_gateway()
    gateway._invoices.clear()
    gateway._transactions.clear()


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


def _create_project(api_client: TestClient, token: str) -> str:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": "Entitlement Project"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]


def _activate_product(account_id: str, product_id: str) -> None:
    payment_agent = build_digital_payment_agent()
    payment = payment_agent.create_upgrade_invoice(
        account_id=account_id,
        upgrade_product_id=product_id,
        currency="BTC",
        network="bitcoin",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount,
        transaction_hash=f"0x{uuid4().hex}",
        confirmations=3,
    )
    result = payment_agent.reconcile_payment(payment.id, account_id=account_id)
    assert result["payment"]["status"] == PaymentStatus.PAID.value


def test_feature_summary_reports_unpaid_capabilities(api_client: TestClient) -> None:
    token, _ = _register(api_client, "features-unpaid@example.com")
    response = api_client.get("/api/v1/auth/me/features", headers=_auth_headers(token))
    assert response.status_code == 200
    features = response.json()["features"]
    assert features["csi_deep_extraction"]["available"] is False
    assert features["csi_deep_extraction"]["reason"] == "no_entitlement"


def test_unpaid_csi_extract_is_denied_when_enforced(
    api_client: TestClient,
    enforced_entitlements: None,
    enforced_project_access: None,
) -> None:
    token, _ = _register(api_client, "csi-unpaid@example.com")
    project_id = _create_project(api_client, token)
    response = api_client.post(
        f"/api/v1/integrations/{project_id}/extract/ETABS",
        headers=_auth_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FEATURE_ACCESS_DENIED"


def test_paid_solver_plus_allows_csi_extract_when_enforced(
    api_client: TestClient,
    enforced_entitlements: None,
    enforced_project_access: None,
) -> None:
    token, account_id = _register(api_client, "csi-paid@example.com")
    _activate_product(account_id, "solver-plus")
    project_id = _create_project(api_client, token)
    response = api_client.post(
        f"/api/v1/integrations/{project_id}/extract/ETABS",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200


def test_expired_entitlement_denies_paid_feature(
    api_client: TestClient,
    enforced_entitlements: None,
    enforced_project_access: None,
) -> None:
    token, account_id = _register(api_client, "csi-expired@example.com")
    _activate_product(account_id, "solver-plus")
    repo = PostgresPaymentRepository()
    entitlement = repo.get_active_entitlement(account_id, "solver-plus")
    assert entitlement is not None
    repo.update_entitlement(
        entitlement.id,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    project_id = _create_project(api_client, token)
    response = api_client.post(
        f"/api/v1/integrations/{project_id}/extract/ETABS",
        headers=_auth_headers(token),
    )
    assert response.status_code == 403


def test_revoked_entitlement_denies_paid_feature(
    api_client: TestClient,
    enforced_entitlements: None,
) -> None:
    token, account_id = _register(api_client, "revoked@example.com")
    _activate_product(account_id, "solver-plus")
    repo = PostgresPaymentRepository()
    entitlement = repo.get_active_entitlement(account_id, "solver-plus")
    assert entitlement is not None
    repo.update_entitlement(entitlement.id, status=EntitlementStatus.REVOKED)
    response = api_client.get("/api/v1/auth/me/features", headers=_auth_headers(token))
    assert response.json()["features"]["csi_deep_extraction"]["available"] is False
    assert response.json()["features"]["csi_deep_extraction"]["reason"] == "revoked"


def test_multi_member_optimization_requires_pro_workspace_when_enforced(
    api_client: TestClient,
    enforced_entitlements: None,
    enforced_project_access: None,
) -> None:
    token, _ = _register(api_client, "opt-unpaid@example.com")
    project_id = _create_project(api_client, token)
    response = api_client.post(
        "/api/v1/engineering/optimization/run",
        headers=_auth_headers(token),
        json={
            "project_id": project_id,
            "optimization_type": "member_sizing",
            "objective": "minimize_weight",
            "parameters": {
                "optimization_mode": OptimizationMode.SHARED_SECTION.value,
                "member_ids": ["mbr-1", "mbr-2"],
            },
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FEATURE_ACCESS_DENIED"


def test_authorized_pro_workspace_allows_multi_member_optimization(
    api_client: TestClient,
    enforced_entitlements: None,
    enforced_project_access: None,
) -> None:
    token, account_id = _register(api_client, "opt-paid@example.com")
    _activate_product(account_id, "pro-workspace")
    project_id = _create_project(api_client, token)
    response = api_client.post(
        "/api/v1/engineering/optimization/run",
        headers=_auth_headers(token),
        json={
            "project_id": project_id,
            "optimization_type": "member_sizing",
            "objective": "minimize_weight",
            "parameters": {
                "optimization_mode": OptimizationMode.SHARED_SECTION.value,
                "member_ids": ["mbr-1", "mbr-2"],
            },
        },
    )
    assert response.status_code == 200
