"""Unit tests for BTCPay crypto payment gateway with fake HTTP client."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.models.payments import GatewayInvoiceRequest, PaymentStatus
from app.infrastructure.payments.btcpay_crypto_gateway import BtcpayCryptoPaymentGateway


class FakeBtcpayClient:
    def __init__(self) -> None:
        self.invoices: dict[str, dict] = {}
        self.methods: dict[str, list[dict]] = {}

    def create_invoice(
        self,
        *,
        store_id: str,
        amount: str,
        currency: str,
        metadata: dict,
        expiration_minutes: int,
    ) -> dict:
        invoice_id = f"btcpay_{uuid4().hex[:12]}"
        record = {
            "id": invoice_id,
            "amount": amount,
            "currency": currency,
            "status": "New",
            "metadata": metadata,
            "checkoutLink": f"https://btcpay.example/i/{invoice_id}",
            "payments": [],
        }
        self.invoices[invoice_id] = record
        self.methods[invoice_id] = [
            {
                "paymentMethod": f"{currency}-CHAIN",
                "destination": f"bc1q{invoice_id[:16]}",
                "paymentLink": f"bitcoin:bc1q{invoice_id[:16]}?amount={amount}",
            }
        ]
        return record

    def get_invoice(self, *, store_id: str, invoice_id: str) -> dict:
        return self.invoices[invoice_id]

    def get_invoice_payment_methods(self, *, store_id: str, invoice_id: str) -> list[dict]:
        return self.methods[invoice_id]


def _gateway(client: FakeBtcpayClient) -> BtcpayCryptoPaymentGateway:
    return BtcpayCryptoPaymentGateway(
        client=client,
        store_id="store-1",
        webhook_secret="test-webhook-secret",
    )


def test_btcpay_create_invoice_returns_encoded_address() -> None:
    client = FakeBtcpayClient()
    gateway = _gateway(client)
    request = GatewayInvoiceRequest(
        payment_id=uuid4(),
        invoice_id="inv_test123",
        account_id="user-1",
        upgrade_product_id="pro_monthly",
        currency="BTC",
        network="BITCOIN",
        crypto_amount=0.001,
        fiat_amount_usd=99.0,
        expires_at=datetime.now(UTC) + timedelta(minutes=60),
    )
    result = gateway.create_invoice(request)
    assert result["payment_address"].startswith("btcpay:")
    assert result["provider_invoice_id"] in client.invoices


def test_btcpay_settled_invoice_maps_to_paid() -> None:
    client = FakeBtcpayClient()
    gateway = _gateway(client)
    created = gateway.create_invoice(
        GatewayInvoiceRequest(
            payment_id=uuid4(),
            invoice_id="inv_paid",
            account_id="user-1",
            upgrade_product_id="pro_monthly",
            currency="BTC",
            network="BITCOIN",
            crypto_amount=0.001,
            fiat_amount_usd=99.0,
            expires_at=datetime.now(UTC) + timedelta(minutes=60),
        )
    )
    provider_id = created["provider_invoice_id"]
    client.invoices[provider_id]["status"] = "Settled"
    client.invoices[provider_id]["payments"] = [
        {"id": "txhash123", "value": 0.001, "confirmations": 3}
    ]
    status = gateway.get_payment_status(
        payment_address=created["payment_address"],
        currency="BTC",
        network="BITCOIN",
        expected_amount=0.001,
        invoice_id="inv_paid",
    )
    assert status.detected is True
    assert status.status_hint == PaymentStatus.PAID
    assert status.transaction_hash == "txhash123"


def test_btcpay_underpayment_detected() -> None:
    client = FakeBtcpayClient()
    gateway = _gateway(client)
    created = gateway.create_invoice(
        GatewayInvoiceRequest(
            payment_id=uuid4(),
            invoice_id="inv_under",
            account_id="user-1",
            upgrade_product_id="pro_monthly",
            currency="BTC",
            network="BITCOIN",
            crypto_amount=0.001,
            fiat_amount_usd=99.0,
            expires_at=datetime.now(UTC) + timedelta(minutes=60),
        )
    )
    provider_id = created["provider_invoice_id"]
    client.invoices[provider_id]["status"] = "Settled"
    client.invoices[provider_id]["payments"] = [
        {"id": "tx-under", "value": 0.0005, "confirmations": 3}
    ]
    status = gateway.get_payment_status(
        payment_address=created["payment_address"],
        currency="BTC",
        network="BITCOIN",
        expected_amount=0.001,
        invoice_id="inv_under",
    )
    assert status.status_hint == PaymentStatus.UNDERPAID


def test_btcpay_webhook_signature_and_parse() -> None:
    client = FakeBtcpayClient()
    gateway = _gateway(client)
    payload_dict = {"type": "InvoiceSettled", "invoiceId": "btcpay_abc123"}
    payload = json.dumps(payload_dict).encode()
    signature = "sha256=" + __import__("hmac").new(
        b"test-webhook-secret", payload, __import__("hashlib").sha256
    ).hexdigest()
    assert gateway.verify_webhook(payload, signature) is True
    client.invoices["btcpay_abc123"] = {
        "id": "btcpay_abc123",
        "status": "Settled",
        "amount": 0.001,
        "payments": [{"id": "tx-webhook", "value": 0.001, "confirmations": 3}],
    }
    client.methods["btcpay_abc123"] = [
        {"paymentMethod": "BTC-CHAIN", "destination": "bc1qwebhook", "paymentLink": ""}
    ]
    parsed = gateway.parse_webhook(payload_dict)
    assert parsed.detected is True
