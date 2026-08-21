"""Digital payment agent — orchestrates upgrade invoices and verification without key custody."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.payment_service import PaymentService
from app.domain.models.payments import CryptoPayment, UpgradeEntitlement, UpgradeProduct


class DigitalPaymentAgent:
    """
    Orchestrates crypto upgrade payments.

    The agent never stores or accesses private keys, seed phrases, or signing credentials.
    All blockchain verification is delegated to the configured CryptoPaymentGateway.
    """

    def __init__(self, *, payment_service: PaymentService) -> None:
        self._payments = payment_service

    def list_available_upgrades(self) -> list[UpgradeProduct]:
        return self._payments.list_products()

    def list_supported_currencies(self) -> list[dict[str, Any]]:
        return self._payments.list_supported_crypto()

    def create_upgrade_invoice(
        self,
        *,
        account_id: str,
        upgrade_product_id: str,
        currency: str,
        network: str,
        idempotency_key: str | None = None,
    ) -> CryptoPayment:
        return self._payments.create_invoice(
            account_id=account_id,
            upgrade_product_id=upgrade_product_id,
            currency=currency,
            network=network,
            idempotency_key=idempotency_key,
        )

    def get_payment_status(
        self,
        payment_id: UUID,
        *,
        account_id: str,
    ) -> dict[str, Any]:
        return self._payments.reconcile_payment(payment_id, account_id=account_id)

    def reconcile_payment(
        self,
        payment_id: UUID,
        *,
        account_id: str,
    ) -> dict[str, Any]:
        return self._payments.reconcile_payment(payment_id, account_id=account_id)

    def submit_transaction_for_verification(
        self,
        payment_id: UUID,
        *,
        account_id: str,
        transaction_hash: str,
    ) -> dict[str, Any]:
        return self._payments.verify_and_reconcile_transaction(
            payment_id,
            transaction_hash=transaction_hash,
            account_id=account_id,
        )

    def process_provider_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        return self._payments.process_webhook(payload, signature)

    def list_account_entitlements(self, account_id: str) -> list[UpgradeEntitlement]:
        return self._payments.list_entitlements(account_id)

    def build_payment_instructions(self, payment: CryptoPayment) -> dict[str, Any]:
        return {
            "payment_id": str(payment.id),
            "invoice_id": payment.invoice_id,
            "upgrade_product_id": payment.upgrade_product_id,
            "currency": payment.currency,
            "network": payment.network,
            "crypto_amount": payment.crypto_amount,
            "fiat_amount_usd": payment.fiat_amount_usd,
            "payment_address": payment.payment_address,
            "payment_uri": payment.payment_uri,
            "required_confirmations": payment.required_confirmations,
            "expires_at": payment.expires_at.isoformat(),
            "exchange_rate": payment.exchange_rate,
            "exchange_rate_source": payment.exchange_rate_source,
            "status": payment.status.value,
            "security_notice": (
                "Never share private keys or seed phrases. Send only the exact crypto amount "
                "to the payment address shown here."
            ),
        }
