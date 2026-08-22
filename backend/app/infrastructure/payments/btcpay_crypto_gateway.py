"""BTCPay Server crypto payment gateway — non-custodial production adapter."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from app.domain.models.payments import GatewayInvoiceRequest, GatewayPaymentStatus, PaymentStatus
from app.infrastructure.payments.btcpay_client import BtcpayClient

# Platform currency/network → BTCPay payment method id fragment
_CURRENCY_TO_BTCPAY: dict[tuple[str, str], str] = {
    ("BTC", "BITCOIN"): "BTC",
    ("ETH", "ETHEREUM"): "ETH",
    ("USDT", "ETHEREUM"): "USDT-ERC20",
}

_BTCPAY_STATUS_MAP: dict[str, PaymentStatus] = {
    "New": PaymentStatus.AWAITING_PAYMENT,
    "Processing": PaymentStatus.CONFIRMING,
    "Settled": PaymentStatus.PAID,
    "Expired": PaymentStatus.EXPIRED,
    "Invalid": PaymentStatus.FAILED,
}


class BtcpayCryptoPaymentGateway:
    """Production gateway via BTCPay Server. Addresses and signing remain with BTCPay."""

    provider_name = "btcpay"

    def __init__(
        self,
        *,
        client: BtcpayClient,
        store_id: str,
        webhook_secret: str,
        required_confirmations: int = 3,
    ) -> None:
        self._client = client
        self._store_id = store_id
        self._webhook_secret = webhook_secret
        self._required_confirmations = required_confirmations

    def create_invoice(self, request: GatewayInvoiceRequest) -> dict[str, Any]:
        btcpay_currency = _CURRENCY_TO_BTCPAY.get(
            (request.currency.upper(), request.network.upper()),
            request.currency.upper(),
        )
        from datetime import UTC, datetime

        delta = request.expires_at - datetime.now(UTC)
        expiration_minutes = max(1, int(delta.total_seconds() // 60))

        invoice = self._client.create_invoice(
            store_id=self._store_id,
            amount=f"{request.crypto_amount:.8f}".rstrip("0").rstrip("."),
            currency=btcpay_currency,
            metadata={
                "orderId": request.invoice_id,
                "accountId": request.account_id,
                "upgradeProductId": request.upgrade_product_id,
                "platformPaymentId": str(request.payment_id),
            },
            expiration_minutes=expiration_minutes,
        )
        provider_invoice_id = str(invoice["id"])
        payment_address, payment_uri = self._resolve_payment_destination(
            provider_invoice_id,
            request.currency,
            request.network,
            request.crypto_amount,
            request.invoice_id,
        )
        return {
            "payment_address": payment_address,
            "payment_uri": payment_uri,
            "provider": self.provider_name,
            "provider_invoice_id": provider_invoice_id,
            "checkout_link": invoice.get("checkoutLink"),
        }

    def get_payment_status(
        self,
        *,
        payment_address: str,
        currency: str,
        network: str,
        expected_amount: float,
        invoice_id: str,
    ) -> GatewayPaymentStatus:
        provider_invoice_id = self._provider_invoice_id_from_address(payment_address)
        if provider_invoice_id is None:
            return GatewayPaymentStatus(detected=False)
        return self._status_from_provider_invoice(
            provider_invoice_id,
            currency=currency,
            network=network,
            expected_amount=expected_amount,
            destination_address=payment_address,
        )

    def verify_transaction(
        self,
        *,
        transaction_hash: str,
        currency: str,
        network: str,
        destination_address: str,
        expected_amount: float,
    ) -> GatewayPaymentStatus:
        provider_invoice_id = self._provider_invoice_id_from_address(destination_address)
        if provider_invoice_id is None:
            return GatewayPaymentStatus(detected=False, transaction_hash=transaction_hash)
        status = self._status_from_provider_invoice(
            provider_invoice_id,
            currency=currency,
            network=network,
            expected_amount=expected_amount,
            destination_address=destination_address,
        )
        if status.detected and status.transaction_hash and status.transaction_hash != transaction_hash:
            return GatewayPaymentStatus(
                detected=True,
                transaction_hash=transaction_hash,
                status_hint=PaymentStatus.MANUAL_REVIEW,
                metadata={"reason": "transaction_hash_mismatch"},
            )
        if status.detected:
            return status.model_copy(update={"transaction_hash": transaction_hash})
        return GatewayPaymentStatus(detected=False, transaction_hash=transaction_hash)

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool:
        if not signature or not self._webhook_secret:
            return False
        digest = signature
        if digest.startswith("sha256="):
            digest = digest[7:]
        expected = hmac.new(
            self._webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, digest)

    def parse_webhook(self, payload: dict[str, Any]) -> GatewayPaymentStatus:
        provider_invoice_id = payload.get("invoiceId")
        if not isinstance(provider_invoice_id, str):
            metadata = payload.get("metadata")
            if isinstance(metadata, dict):
                order_id = metadata.get("orderId")
                if isinstance(order_id, str):
                    return GatewayPaymentStatus(
                        detected=True,
                        metadata={"invoice_id": order_id},
                        status_hint=_map_btcpay_event(str(payload.get("type", ""))),
                    )
            return GatewayPaymentStatus(detected=False)

        event_type = str(payload.get("type", ""))
        event_hint = _map_btcpay_event(event_type)
        if event_hint in {
            PaymentStatus.EXPIRED,
            PaymentStatus.FAILED,
            PaymentStatus.AWAITING_PAYMENT,
            PaymentStatus.PAYMENT_DETECTED,
            PaymentStatus.CONFIRMING,
            PaymentStatus.PAID,
        }:
            try:
                return self._status_from_provider_invoice(
                    provider_invoice_id,
                    currency=str(payload.get("currency") or "BTC"),
                    network=str(payload.get("network") or "bitcoin"),
                    expected_amount=float(payload.get("expected_amount") or 0),
                    destination_address=self._encode_address(provider_invoice_id, "webhook"),
                    event_type=event_type,
                )
            except Exception:
                if event_hint is not None:
                    return GatewayPaymentStatus(
                        detected=True,
                        status_hint=event_hint,
                        metadata={"provider_invoice_id": provider_invoice_id},
                    )
        return GatewayPaymentStatus(detected=False)

    def _resolve_payment_destination(
        self,
        provider_invoice_id: str,
        currency: str,
        network: str,
        amount: float,
        platform_invoice_id: str,
    ) -> tuple[str, str | None]:
        methods = self._client.get_invoice_payment_methods(
            store_id=self._store_id,
            invoice_id=provider_invoice_id,
        )
        target = _CURRENCY_TO_BTCPAY.get((currency.upper(), network.upper()))
        for method in methods:
            payment_method = str(method.get("paymentMethod", ""))
            if target and target not in payment_method.upper():
                continue
            address = method.get("destination") or method.get("address")
            if isinstance(address, str) and address.strip():
                payment_address = self._encode_address(provider_invoice_id, address.strip())
                uri = method.get("paymentLink") or (
                    f"{currency.lower()}:{address}?amount={amount:.8f}&label={platform_invoice_id}"
                )
                return payment_address, str(uri) if uri else None
        fallback = self._encode_address(provider_invoice_id, f"btcpay:{provider_invoice_id}")
        return fallback, None

    @staticmethod
    def _encode_address(provider_invoice_id: str, address: str) -> str:
        return f"btcpay:{provider_invoice_id}:{address}"

    @staticmethod
    def _provider_invoice_id_from_address(payment_address: str) -> str | None:
        if not payment_address.startswith("btcpay:"):
            return None
        parts = payment_address.split(":", 2)
        if len(parts) < 2:
            return None
        return parts[1]

    @staticmethod
    def _actual_address(payment_address: str) -> str:
        if payment_address.startswith("btcpay:"):
            parts = payment_address.split(":", 2)
            if len(parts) == 3:
                return parts[2]
        return payment_address

    def _status_from_provider_invoice(
        self,
        provider_invoice_id: str,
        *,
        currency: str,
        network: str,
        expected_amount: float,
        destination_address: str,
        event_type: str = "",
    ) -> GatewayPaymentStatus:
        invoice = self._client.get_invoice(
            store_id=self._store_id,
            invoice_id=provider_invoice_id,
        )
        raw_status = str(invoice.get("status", "New"))
        received = float(invoice.get("amount") or 0)
        additional = invoice.get("additionalStatus")
        tx_hash = None
        confirmations = 0
        if isinstance(invoice.get("payments"), list) and invoice["payments"]:
            payment = invoice["payments"][-1]
            tx_hash = payment.get("id") or payment.get("transactionHash")
            confirmations = int(payment.get("confirmations", 0) or 0)
            if payment.get("value"):
                received = float(payment["value"])

        status_hint = _BTCPAY_STATUS_MAP.get(raw_status, PaymentStatus.PAYMENT_DETECTED)
        event_hint = _map_btcpay_event(event_type)
        if event_hint is not None:
            status_hint = event_hint

        if raw_status in {"Processing", "Settled"} and confirmations >= self._required_confirmations:
            if received + 1e-12 < expected_amount:
                status_hint = PaymentStatus.UNDERPAID
            elif received > expected_amount * 1.01:
                status_hint = PaymentStatus.OVERPAID
            elif raw_status == "Settled" or event_type == "InvoiceSettled":
                status_hint = PaymentStatus.PAID
            else:
                status_hint = PaymentStatus.CONFIRMING
        elif raw_status == "Processing":
            status_hint = PaymentStatus.CONFIRMING if confirmations > 0 else PaymentStatus.PAYMENT_DETECTED

        detected = raw_status not in {"New"} or confirmations > 0 or event_hint is not None
        return GatewayPaymentStatus(
            detected=detected,
            transaction_hash=str(tx_hash) if tx_hash else None,
            received_amount=received if detected else None,
            confirmations=confirmations,
            destination_address=destination_address,
            currency=currency.upper(),
            network=network.lower(),
            status_hint=status_hint,
            metadata={
                "provider_status": raw_status,
                "additional_status": additional,
                "provider_invoice_id": provider_invoice_id,
            },
        )


def _map_btcpay_event(event_type: str) -> PaymentStatus | None:
    mapping = {
        "InvoiceCreated": PaymentStatus.AWAITING_PAYMENT,
        "InvoiceReceivedPayment": PaymentStatus.PAYMENT_DETECTED,
        "InvoiceProcessing": PaymentStatus.CONFIRMING,
        "InvoiceSettled": PaymentStatus.PAID,
        "InvoiceExpired": PaymentStatus.EXPIRED,
        "InvoiceInvalid": PaymentStatus.FAILED,
    }
    return mapping.get(event_type)
