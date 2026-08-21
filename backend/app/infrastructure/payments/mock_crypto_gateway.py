"""Mock non-custodial crypto payment gateway for CI and local development."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.domain.models.payments import GatewayInvoiceRequest, GatewayPaymentStatus, PaymentStatus


class MockCryptoPaymentGateway:
    """Simulates a payment processor without storing or exposing private keys."""

    provider_name = "mock-gateway"

    def __init__(self, *, webhook_secret: str = "test-webhook-secret") -> None:
        self._webhook_secret = webhook_secret
        self._invoices: dict[str, dict[str, Any]] = {}
        self._transactions: dict[str, dict[str, Any]] = {}

    def create_invoice(self, request: GatewayInvoiceRequest) -> dict[str, Any]:
        address_seed = f"{request.invoice_id}:{request.currency}:{request.network}"
        payment_address = f"mock_{request.network}_{hashlib.sha256(address_seed.encode()).hexdigest()[:24]}"
        payment_uri = (
            f"{request.currency.lower()}:{payment_address}"
            f"?amount={request.crypto_amount:.8f}&label={request.invoice_id}"
        )
        record = {
            "invoice_id": request.invoice_id,
            "payment_id": str(request.payment_id),
            "payment_address": payment_address,
            "currency": request.currency,
            "network": request.network,
            "expected_amount": request.crypto_amount,
            "received_amount": None,
            "transaction_hash": None,
            "confirmations": 0,
        }
        self._invoices[payment_address] = record
        self._invoices[request.invoice_id] = record
        return {
            "payment_address": payment_address,
            "payment_uri": payment_uri,
            "provider": self.provider_name,
        }

    def simulate_payment(
        self,
        *,
        payment_address: str,
        amount: float,
        transaction_hash: str,
        confirmations: int = 3,
    ) -> None:
        record = self._invoices.get(payment_address)
        if record is None:
            raise ValueError(f"Unknown payment address: {payment_address}")
        record["received_amount"] = amount
        record["transaction_hash"] = transaction_hash
        record["confirmations"] = confirmations
        self._transactions[transaction_hash] = record

    def get_payment_status(
        self,
        *,
        payment_address: str,
        currency: str,
        network: str,
        expected_amount: float,
        invoice_id: str,
    ) -> GatewayPaymentStatus:
        record = self._invoices.get(payment_address) or self._invoices.get(invoice_id)
        if record is None:
            return GatewayPaymentStatus(detected=False)
        return self._status_from_record(record, expected_amount=expected_amount)

    def verify_transaction(
        self,
        *,
        transaction_hash: str,
        currency: str,
        network: str,
        destination_address: str,
        expected_amount: float,
    ) -> GatewayPaymentStatus:
        record = self._transactions.get(transaction_hash)
        if record is None:
            return GatewayPaymentStatus(detected=False)
        if record.get("payment_address") != destination_address:
            return GatewayPaymentStatus(
                detected=True,
                status_hint=PaymentStatus.FAILED,
                metadata={"reason": "wrong_destination"},
            )
        if record.get("currency", "").upper() != currency.upper():
            return GatewayPaymentStatus(
                detected=True,
                status_hint=PaymentStatus.FAILED,
                metadata={"reason": "wrong_currency"},
            )
        if record.get("network", "").lower() != network.lower():
            return GatewayPaymentStatus(
                detected=True,
                status_hint=PaymentStatus.FAILED,
                metadata={"reason": "wrong_network"},
            )
        return self._status_from_record(record, expected_amount=expected_amount)

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        digest = hmac.new(
            self._webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, signature)

    def parse_webhook(self, payload: dict[str, Any]) -> GatewayPaymentStatus:
        transaction_hash = payload.get("transaction_hash")
        if not isinstance(transaction_hash, str):
            return GatewayPaymentStatus(detected=False)
        record = self._transactions.get(transaction_hash)
        if record is None:
            return GatewayPaymentStatus(detected=False, transaction_hash=transaction_hash)
        expected = float(record.get("expected_amount", 0))
        return self._status_from_record(record, expected_amount=expected)

    def _status_from_record(
        self,
        record: dict[str, Any],
        *,
        expected_amount: float,
    ) -> GatewayPaymentStatus:
        received = record.get("received_amount")
        if received is None:
            return GatewayPaymentStatus(detected=False)
        confirmations = int(record.get("confirmations", 0))
        status_hint = PaymentStatus.PAYMENT_DETECTED
        if confirmations > 0 and confirmations < 3:
            status_hint = PaymentStatus.CONFIRMING
        elif confirmations >= 3:
            if received + 1e-12 < expected_amount:
                status_hint = PaymentStatus.UNDERPAID
            elif received > expected_amount * 1.01:
                status_hint = PaymentStatus.OVERPAID
            else:
                status_hint = PaymentStatus.PAID
        return GatewayPaymentStatus(
            detected=True,
            transaction_hash=record.get("transaction_hash"),
            received_amount=float(received),
            confirmations=confirmations,
            destination_address=record.get("payment_address"),
            currency=record.get("currency"),
            network=record.get("network"),
            status_hint=status_hint,
        )

    def sign_webhook_payload(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True).encode()
        return hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
