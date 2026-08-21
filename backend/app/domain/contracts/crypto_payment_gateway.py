"""Provider-agnostic crypto payment gateway contract."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models.payments import GatewayInvoiceRequest, GatewayPaymentStatus


class CryptoPaymentGateway(Protocol):
    provider_name: str

    def create_invoice(self, request: GatewayInvoiceRequest) -> dict[str, Any]:
        """Return payment_address, payment_uri, and provider metadata. Never return private keys."""

    def get_payment_status(
        self,
        *,
        payment_address: str,
        currency: str,
        network: str,
        expected_amount: float,
        invoice_id: str,
    ) -> GatewayPaymentStatus:
        """Poll provider/blockchain for payment status."""

    def verify_transaction(
        self,
        *,
        transaction_hash: str,
        currency: str,
        network: str,
        destination_address: str,
        expected_amount: float,
    ) -> GatewayPaymentStatus:
        """Independently verify a transaction."""

    def verify_webhook(self, payload: bytes, signature: str | None) -> bool:
        """Verify webhook authenticity."""

    def parse_webhook(self, payload: dict[str, Any]) -> GatewayPaymentStatus:
        """Parse provider webhook payload into normalized status."""
