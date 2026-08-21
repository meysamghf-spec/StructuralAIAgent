"""Payment orchestration, verification, and entitlement activation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg.errors

from app.application.exceptions import (
    DuplicatePaymentTransactionError,
    PaymentAuthorizationError,
    PaymentNotFoundError,
    PaymentStateError,
)
from app.application.upgrade_catalog import (
    get_crypto_option,
    get_upgrade_product,
    list_upgrade_products,
    SUPPORTED_CRYPTO_OPTIONS,
)
from app.domain.contracts.crypto_payment_gateway import CryptoPaymentGateway
from app.domain.contracts.exchange_rate_provider import ExchangeRateProvider
from app.domain.models.payments import (
    CryptoPayment,
    EntitlementStatus,
    GatewayInvoiceRequest,
    PaymentStatus,
    TERMINAL_PAYMENT_STATUSES,
    UpgradeEntitlement,
    UpgradeProduct,
)
from app.infrastructure.repositories.postgres_payment_repository import PostgresPaymentRepository

INVOICE_TTL_MINUTES = 60


class PaymentService:
    def __init__(
        self,
        *,
        repository: PostgresPaymentRepository,
        gateway: CryptoPaymentGateway,
        exchange_rates: ExchangeRateProvider,
    ) -> None:
        self._repo = repository
        self._gateway = gateway
        self._exchange_rates = exchange_rates

    def list_products(self) -> list[UpgradeProduct]:
        return list_upgrade_products()

    def list_supported_crypto(self) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in SUPPORTED_CRYPTO_OPTIONS]

    def create_invoice(
        self,
        *,
        account_id: str,
        upgrade_product_id: str,
        currency: str,
        network: str,
        idempotency_key: str | None = None,
    ) -> CryptoPayment:
        if idempotency_key:
            existing = self._repo.get_payment_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        product = get_upgrade_product(upgrade_product_id)
        option = get_crypto_option(currency, network)
        rate = self._exchange_rates.get_rate_usd(currency)
        crypto_amount = round(product.fiat_price_usd / rate.rate_usd, option.decimals)
        invoice_id = f"inv_{uuid4().hex[:16]}"
        expires_at = datetime.now(UTC) + timedelta(minutes=INVOICE_TTL_MINUTES)
        payment_id = uuid4()

        gateway_result = self._gateway.create_invoice(
            GatewayInvoiceRequest(
                payment_id=payment_id,
                invoice_id=invoice_id,
                account_id=account_id,
                upgrade_product_id=upgrade_product_id,
                currency=currency.upper(),
                network=network.lower(),
                crypto_amount=crypto_amount,
                fiat_amount_usd=product.fiat_price_usd,
                expires_at=expires_at,
            )
        )

        payment = self._repo.create_payment(
            account_id=account_id,
            upgrade_product_id=upgrade_product_id,
            invoice_id=invoice_id,
            currency=currency.upper(),
            network=network.lower(),
            fiat_amount_usd=product.fiat_price_usd,
            crypto_amount=crypto_amount,
            payment_address=gateway_result["payment_address"],
            payment_uri=gateway_result.get("payment_uri"),
            status=PaymentStatus.AWAITING_PAYMENT,
            provider=self._gateway.provider_name,
            exchange_rate_source=rate.source,
            exchange_rate=rate.rate_usd,
            exchange_rate_at=rate.captured_at,
            required_confirmations=option.required_confirmations,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            metadata={"product_name": product.name},
        )
        self._audit(payment.id, "INVOICE_CREATED", "Upgrade invoice created", {"invoice_id": invoice_id})
        return payment

    def get_payment(self, payment_id: UUID, *, account_id: str | None = None) -> CryptoPayment:
        payment = self._repo.get_payment(payment_id)
        if payment is None:
            raise PaymentNotFoundError(payment_id)
        if account_id is not None and payment.account_id != account_id:
            raise PaymentAuthorizationError(payment_id)
        return payment

    def list_entitlements(self, account_id: str) -> list[UpgradeEntitlement]:
        return self._repo.list_entitlements_for_account(account_id)

    def reconcile_payment(self, payment_id: UUID, *, account_id: str | None = None) -> dict[str, Any]:
        payment = self.get_payment(payment_id, account_id=account_id)
        if payment.status in TERMINAL_PAYMENT_STATUSES:
            entitlement = self._repo.get_active_entitlement(payment.account_id, payment.upgrade_product_id)
            return self._build_status_response(payment, entitlement)

        if datetime.now(UTC) > payment.expires_at and payment.status == PaymentStatus.AWAITING_PAYMENT:
            payment = self._transition(
                payment,
                PaymentStatus.EXPIRED,
                message="Invoice expired before payment was detected",
            )
            return self._build_status_response(payment, None)

        gateway_status = self._gateway.get_payment_status(
            payment_address=payment.payment_address,
            currency=payment.currency,
            network=payment.network,
            expected_amount=payment.crypto_amount,
            invoice_id=payment.invoice_id,
        )
        return self._apply_gateway_status(payment, gateway_status)

    def verify_and_reconcile_transaction(
        self,
        payment_id: UUID,
        *,
        transaction_hash: str,
        account_id: str | None = None,
    ) -> dict[str, Any]:
        payment = self.get_payment(payment_id, account_id=account_id)
        if payment.status in TERMINAL_PAYMENT_STATUSES:
            entitlement = self._repo.get_active_entitlement(payment.account_id, payment.upgrade_product_id)
            return self._build_status_response(payment, entitlement)

        existing = self._repo.find_by_transaction(transaction_hash, payment.network)
        if existing is not None and existing.id != payment.id:
            raise DuplicatePaymentTransactionError(transaction_hash, payment.network)

        gateway_status = self._gateway.verify_transaction(
            transaction_hash=transaction_hash,
            currency=payment.currency,
            network=payment.network,
            destination_address=payment.payment_address,
            expected_amount=payment.crypto_amount,
        )
        if not gateway_status.detected:
            self._audit(
                payment.id,
                "VERIFICATION_FAILED",
                "Transaction could not be verified by the payment gateway",
                {"transaction_hash": transaction_hash},
            )
            return self._build_status_response(payment, None)

        return self._apply_gateway_status(payment, gateway_status, transaction_hash=transaction_hash)

    def process_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not self._gateway.verify_webhook(payload, signature):
            from app.application.exceptions import InvalidWebhookSignatureError

            raise InvalidWebhookSignatureError()

        import json

        data = json.loads(payload.decode())
        gateway_status = self._gateway.parse_webhook(data)
        invoice_id = data.get("invoice_id")
        payment = None
        if isinstance(invoice_id, str):
            payment = self._repo.get_payment_by_invoice(invoice_id)
        if payment is None and gateway_status.transaction_hash:
            payment = self._repo.find_by_transaction(
                gateway_status.transaction_hash,
                str(data.get("network", "")),
            )
        if payment is None:
            return {"processed": False, "reason": "payment_not_found"}

        if payment.status in TERMINAL_PAYMENT_STATUSES:
            return self._build_status_response(payment, self._repo.get_active_entitlement(
                payment.account_id, payment.upgrade_product_id
            ))

        result = self._apply_gateway_status(
            payment,
            gateway_status,
            transaction_hash=gateway_status.transaction_hash,
        )
        result["processed"] = True
        return result

    def _apply_gateway_status(
        self,
        payment: CryptoPayment,
        gateway_status,
        *,
        transaction_hash: str | None = None,
    ) -> dict[str, Any]:
        if not gateway_status.detected:
            return self._build_status_response(payment, None)

        tx_hash = transaction_hash or gateway_status.transaction_hash
        if tx_hash:
            duplicate = self._repo.find_by_transaction(tx_hash, payment.network)
            if duplicate is not None and duplicate.id != payment.id:
                payment = self._transition(
                    payment,
                    PaymentStatus.MANUAL_REVIEW,
                    message="Duplicate transaction hash detected",
                    metadata={"duplicate_payment_id": str(duplicate.id)},
                )
                return self._build_status_response(payment, None)

        if datetime.now(UTC) > payment.expires_at and payment.status == PaymentStatus.AWAITING_PAYMENT:
            payment = self._transition(
                payment,
                PaymentStatus.EXPIRED,
                message="Payment detected after invoice expiration",
            )
            return self._build_status_response(payment, None)

        if gateway_status.destination_address and gateway_status.destination_address != payment.payment_address:
            payment = self._transition(
                payment,
                PaymentStatus.FAILED,
                message="Payment sent to wrong destination address",
            )
            return self._build_status_response(payment, None)

        new_status = gateway_status.status_hint or PaymentStatus.PAYMENT_DETECTED
        received = gateway_status.received_amount
        confirmations = gateway_status.confirmations

        payment = self._repo.update_payment(
            payment.id,
            status=new_status,
            received_amount=received,
            transaction_hash=tx_hash,
            current_confirmations=confirmations,
            paid_at=datetime.now(UTC) if new_status == PaymentStatus.PAID else payment.paid_at,
            verified_at=datetime.now(UTC),
        )
        assert payment is not None
        self._audit(
            payment.id,
            "PAYMENT_STATUS_UPDATED",
            f"Payment status updated to {new_status.value}",
            {"confirmations": confirmations, "received_amount": received},
        )

        entitlement = None
        if new_status == PaymentStatus.PAID:
            entitlement = self._activate_entitlement(payment)
        elif new_status in {PaymentStatus.UNDERPAID, PaymentStatus.OVERPAID}:
            self._audit(payment.id, "PAYMENT_AMOUNT_MISMATCH", f"Payment marked {new_status.value}")

        return self._build_status_response(payment, entitlement)

    def _activate_entitlement(self, payment: CryptoPayment) -> UpgradeEntitlement | None:
        existing = self._repo.get_active_entitlement(payment.account_id, payment.upgrade_product_id)
        if existing is not None:
            self._audit(
                payment.id,
                "ENTITLEMENT_ALREADY_ACTIVE",
                "Upgrade entitlement already active; skipping duplicate activation",
                {"entitlement_id": str(existing.id)},
            )
            return existing

        product = get_upgrade_product(payment.upgrade_product_id)
        activated_at = datetime.now(UTC)
        expires_at = None
        if product.billing_period_days:
            expires_at = activated_at + timedelta(days=product.billing_period_days)

        try:
            entitlement = self._repo.create_entitlement(
                account_id=payment.account_id,
                upgrade_product_id=payment.upgrade_product_id,
                payment_id=payment.id,
                status=EntitlementStatus.ACTIVE,
                activated_at=activated_at,
                expires_at=expires_at,
                metadata={"product_name": product.name},
            )
        except psycopg.errors.UniqueViolation:
            existing = self._repo.get_active_entitlement(payment.account_id, payment.upgrade_product_id)
            if existing is None:
                raise
            self._audit(
                payment.id,
                "ENTITLEMENT_ALREADY_ACTIVE",
                "Concurrent entitlement activation resolved to existing active entitlement",
                {"entitlement_id": str(existing.id)},
            )
            return existing

        self._audit(
            payment.id,
            "ENTITLEMENT_ACTIVATED",
            "Upgrade entitlement activated after verified payment",
            {"entitlement_id": str(entitlement.id)},
        )
        return entitlement

    def _transition(
        self,
        payment: CryptoPayment,
        status: PaymentStatus,
        *,
        message: str,
        metadata: dict | None = None,
    ) -> CryptoPayment:
        updated = self._repo.update_payment(payment.id, status=status, metadata={**payment.metadata, **(metadata or {})})
        assert updated is not None
        self._audit(updated.id, "PAYMENT_TRANSITION", message, metadata or {})
        return updated

    def _audit(
        self,
        payment_id: UUID,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        self._repo.create_audit_event(
            payment_id,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )

    def _build_status_response(
        self,
        payment: CryptoPayment,
        entitlement: UpgradeEntitlement | None,
    ) -> dict[str, Any]:
        return {
            "payment": payment.model_dump(mode="json"),
            "entitlement": entitlement.model_dump(mode="json") if entitlement else None,
            "upgrade_activated": entitlement is not None and entitlement.status == EntitlementStatus.ACTIVE,
        }
