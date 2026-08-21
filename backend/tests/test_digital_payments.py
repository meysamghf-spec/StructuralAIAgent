"""Digital currency payment, verification, and entitlement tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.application.exceptions import DuplicatePaymentTransactionError, InvalidWebhookSignatureError
from app.application.service_factory import build_digital_payment_agent, get_crypto_payment_gateway
from app.domain.models.payments import PaymentStatus


@pytest.fixture(autouse=True)
def _reset_payment_gateway() -> None:
    gateway = get_crypto_payment_gateway()
    gateway._invoices.clear()
    gateway._transactions.clear()


@pytest.fixture
def payment_agent(db_session):
    return build_digital_payment_agent()


def test_invoice_creation_with_exchange_rate_snapshot(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="user-a",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
        idempotency_key="inv-key-1",
    )
    assert payment.status == PaymentStatus.AWAITING_PAYMENT
    assert payment.crypto_amount == pytest.approx(49.0 / 50_000.0, rel=1e-6)
    assert payment.exchange_rate == 50_000.0
    assert payment.payment_address.startswith("mock_bitcoin_")


def test_idempotent_invoice_creation(payment_agent) -> None:
    first = payment_agent.create_upgrade_invoice(
        account_id="user-a",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
        idempotency_key="same-key",
    )
    second = payment_agent.create_upgrade_invoice(
        account_id="user-a",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
        idempotency_key="same-key",
    )
    assert first.id == second.id


def test_upgrade_activates_only_after_paid_verification(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="user-b",
        upgrade_product_id="solver-plus",
        currency="USDT",
        network="ethereum",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount,
        transaction_hash="0xabc123paid",
        confirmations=3,
    )
    result = payment_agent.reconcile_payment(payment.id, account_id="user-b")
    assert result["payment"]["status"] == PaymentStatus.PAID.value
    assert result["upgrade_activated"] is True
    entitlements = payment_agent.list_account_entitlements("user-b")
    assert len(entitlements) == 1
    assert entitlements[0].upgrade_product_id == "solver-plus"


def test_underpayment_does_not_activate_upgrade(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="user-c",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount * 0.5,
        transaction_hash="0xunderpaid",
        confirmations=3,
    )
    result = payment_agent.reconcile_payment(payment.id, account_id="user-c")
    assert result["payment"]["status"] == PaymentStatus.UNDERPAID.value
    assert result["upgrade_activated"] is False


def test_duplicate_transaction_is_rejected(payment_agent) -> None:
    first = payment_agent.create_upgrade_invoice(
        account_id="user-d1",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
    )
    second = payment_agent.create_upgrade_invoice(
        account_id="user-d2",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=first.payment_address,
        amount=first.crypto_amount,
        transaction_hash="0xduphash",
        confirmations=3,
    )
    payment_agent.reconcile_payment(first.id, account_id="user-d1")
    with pytest.raises(DuplicatePaymentTransactionError):
        payment_agent.submit_transaction_for_verification(
            second.id,
            account_id="user-d2",
            transaction_hash="0xduphash",
        )


def test_webhook_idempotency(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="user-e",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount,
        transaction_hash="0xwebhooktx",
        confirmations=3,
    )
    payload = {"invoice_id": payment.invoice_id, "transaction_hash": "0xwebhooktx", "network": "ethereum"}
    body = json.dumps(payload, sort_keys=True).encode()
    signature = gateway.sign_webhook_payload(payload)
    first = payment_agent.process_provider_webhook(body, signature)
    second = payment_agent.process_provider_webhook(body, signature)
    assert first["upgrade_activated"] is True
    assert second["upgrade_activated"] is True
    assert len(payment_agent.list_account_entitlements("user-e")) == 1


def test_forged_webhook_rejected(payment_agent) -> None:
    payload = json.dumps({"invoice_id": "fake", "transaction_hash": "0xbad"}).encode()
    with pytest.raises(InvalidWebhookSignatureError):
        payment_agent.process_provider_webhook(payload, "invalid-signature")


def test_unauthorized_payment_lookup_rejected(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="owner",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
    )
    from app.application.exceptions import PaymentAuthorizationError

    with pytest.raises(PaymentAuthorizationError):
        payment_agent.get_payment_status(payment.id, account_id="other-user")


def test_api_payment_catalog_and_invoice(api_client: TestClient) -> None:
    headers = {"X-Actor-Id": "api-payer"}
    catalog = api_client.get("/api/v1/payments/catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["products"]) >= 2

    create = api_client.post(
        "/api/v1/payments/invoices",
        json={
            "upgrade_product_id": "pro-workspace",
            "currency": "BTC",
            "network": "bitcoin",
            "idempotency_key": "api-key-1",
        },
        headers=headers,
    )
    assert create.status_code == 200
    body = create.json()
    assert body["payment"]["status"] == "AWAITING_PAYMENT"
    assert "payment_address" in body["instructions"]

    payment_id = body["payment"]["id"]
    status = api_client.get(f"/api/v1/payments/invoices/{payment_id}", headers=headers)
    assert status.status_code == 200


def test_api_invalid_product_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/payments/invoices",
        json={
            "upgrade_product_id": "nonexistent-product",
            "currency": "BTC",
            "network": "bitcoin",
        },
        headers={"X-Actor-Id": "api-payer"},
    )
    assert response.status_code == 404


def test_api_unsupported_network_rejected(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/payments/invoices",
        json={
            "upgrade_product_id": "pro-workspace",
            "currency": "BTC",
            "network": "solana",
        },
        headers={"X-Actor-Id": "api-payer"},
    )
    assert response.status_code == 400
