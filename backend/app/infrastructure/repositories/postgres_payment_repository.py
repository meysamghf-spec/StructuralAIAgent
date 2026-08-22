"""PostgreSQL persistence for crypto payments and entitlements."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.models.payments import (
    CryptoPayment,
    EntitlementStatus,
    PaymentAuditEvent,
    PaymentStatus,
    UpgradeEntitlement,
)
from app.infrastructure.database.connection import get_connection


class PostgresPaymentRepository:
    def create_payment(
        self,
        *,
        account_id: str,
        upgrade_product_id: str,
        invoice_id: str,
        currency: str,
        network: str,
        fiat_amount_usd: float,
        crypto_amount: float,
        payment_address: str,
        payment_uri: str | None,
        status: PaymentStatus,
        provider: str,
        exchange_rate_source: str | None,
        exchange_rate: float | None,
        exchange_rate_at: datetime | None,
        required_confirmations: int,
        expires_at: datetime,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> CryptoPayment:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO crypto_payments (
                        account_id, upgrade_product_id, invoice_id, currency, network,
                        fiat_amount_usd, crypto_amount, payment_address, payment_uri,
                        status, provider, exchange_rate_source, exchange_rate,
                        exchange_rate_at, required_confirmations, expires_at,
                        idempotency_key, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING *
                    """,
                    (
                        account_id,
                        upgrade_product_id,
                        invoice_id,
                        currency,
                        network,
                        fiat_amount_usd,
                        crypto_amount,
                        payment_address,
                        payment_uri,
                        status.value,
                        provider,
                        exchange_rate_source,
                        exchange_rate,
                        exchange_rate_at,
                        required_confirmations,
                        expires_at,
                        idempotency_key,
                        json.dumps(metadata or {}),
                    ),
                )
                row = cur.fetchone()
        return _payment_from_row(row)

    def get_payment(self, payment_id: UUID) -> CryptoPayment | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM crypto_payments WHERE id = %s", (payment_id,))
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def get_payment_by_invoice(self, invoice_id: str) -> CryptoPayment | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM crypto_payments WHERE invoice_id = %s", (invoice_id,))
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def get_payment_by_provider_invoice(self, provider_invoice_id: str) -> CryptoPayment | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM crypto_payments
                    WHERE metadata->>'provider_invoice_id' = %s
                    LIMIT 1
                    """,
                    (provider_invoice_id,),
                )
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def get_payment_by_idempotency_key(self, idempotency_key: str) -> CryptoPayment | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM crypto_payments WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def find_by_transaction(self, transaction_hash: str, network: str) -> CryptoPayment | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM crypto_payments
                    WHERE transaction_hash = %s AND network = %s
                    LIMIT 1
                    """,
                    (transaction_hash, network),
                )
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def update_payment(
        self,
        payment_id: UUID,
        *,
        status: PaymentStatus | None = None,
        received_amount: float | None = None,
        transaction_hash: str | None = None,
        current_confirmations: int | None = None,
        paid_at: datetime | None = None,
        verified_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> CryptoPayment | None:
        fields: list[str] = ["updated_at = NOW()"]
        values: list[object] = []
        if status is not None:
            fields.append("status = %s")
            values.append(status.value)
        if received_amount is not None:
            fields.append("received_amount = %s")
            values.append(received_amount)
        if transaction_hash is not None:
            fields.append("transaction_hash = %s")
            values.append(transaction_hash)
        if current_confirmations is not None:
            fields.append("current_confirmations = %s")
            values.append(current_confirmations)
        if paid_at is not None:
            fields.append("paid_at = %s")
            values.append(paid_at)
        if verified_at is not None:
            fields.append("verified_at = %s")
            values.append(verified_at)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            values.append(json.dumps(metadata))

        values.append(payment_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE crypto_payments SET {', '.join(fields)} WHERE id = %s RETURNING *",
                    tuple(values),
                )
                row = cur.fetchone()
        return _payment_from_row(row) if row else None

    def list_payments_for_account(self, account_id: str, *, limit: int = 50) -> list[CryptoPayment]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM crypto_payments
                    WHERE account_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (account_id, limit),
                )
                rows = cur.fetchall()
        return [_payment_from_row(row) for row in rows]

    def create_audit_event(
        self,
        payment_id: UUID,
        *,
        event_type: str,
        message: str,
        metadata: dict | None = None,
    ) -> PaymentAuditEvent:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payment_audit_events (payment_id, event_type, message, metadata)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id, payment_id, event_type, message, metadata, created_at
                    """,
                    (payment_id, event_type, message, json.dumps(metadata or {})),
                )
                row = cur.fetchone()
        return PaymentAuditEvent(
            id=row["id"],
            payment_id=row["payment_id"],
            event_type=row["event_type"],
            message=row["message"],
            metadata=row["metadata"] or {},
            created_at=row["created_at"],
        )

    def create_entitlement(
        self,
        *,
        account_id: str,
        upgrade_product_id: str,
        payment_id: UUID,
        status: EntitlementStatus,
        activated_at: datetime | None = None,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> UpgradeEntitlement:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO upgrade_entitlements (
                        account_id, upgrade_product_id, payment_id, status,
                        activated_at, expires_at, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING *
                    """,
                    (
                        account_id,
                        upgrade_product_id,
                        payment_id,
                        status.value,
                        activated_at,
                        expires_at,
                        json.dumps(metadata or {}),
                    ),
                )
                row = cur.fetchone()
        return _entitlement_from_row(row)

    def get_entitlement(self, entitlement_id: UUID) -> UpgradeEntitlement | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM upgrade_entitlements WHERE id = %s", (entitlement_id,))
                row = cur.fetchone()
        return _entitlement_from_row(row) if row else None

    def get_active_entitlement(
        self,
        account_id: str,
        upgrade_product_id: str,
    ) -> UpgradeEntitlement | None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM upgrade_entitlements
                    WHERE account_id = %s
                      AND upgrade_product_id = %s
                      AND status = 'ACTIVE'
                    LIMIT 1
                    """,
                    (account_id, upgrade_product_id),
                )
                row = cur.fetchone()
        return _entitlement_from_row(row) if row else None

    def list_entitlements_for_account(self, account_id: str) -> list[UpgradeEntitlement]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM upgrade_entitlements
                    WHERE account_id = %s
                    ORDER BY created_at DESC
                    """,
                    (account_id,),
                )
                rows = cur.fetchall()
        return [_entitlement_from_row(row) for row in rows]

    def update_entitlement(
        self,
        entitlement_id: UUID,
        *,
        status: EntitlementStatus | None = None,
        activated_at: datetime | None = None,
        expires_at: datetime | None = None,
        metadata: dict | None = None,
    ) -> UpgradeEntitlement | None:
        fields: list[str] = []
        values: list[object] = []
        if status is not None:
            fields.append("status = %s")
            values.append(status.value)
        if activated_at is not None:
            fields.append("activated_at = %s")
            values.append(activated_at)
        if expires_at is not None:
            fields.append("expires_at = %s")
            values.append(expires_at)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            values.append(json.dumps(metadata))
        if not fields:
            return self.get_entitlement(entitlement_id)
        values.append(entitlement_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE upgrade_entitlements SET {', '.join(fields)} WHERE id = %s RETURNING *",
                    tuple(values),
                )
                row = cur.fetchone()
        return _entitlement_from_row(row) if row else None


def _payment_from_row(row) -> CryptoPayment:
    return CryptoPayment(
        id=row["id"],
        account_id=row["account_id"],
        upgrade_product_id=row["upgrade_product_id"],
        invoice_id=row["invoice_id"],
        currency=row["currency"],
        network=row["network"],
        fiat_amount_usd=float(row["fiat_amount_usd"]),
        crypto_amount=float(row["crypto_amount"]),
        received_amount=float(row["received_amount"]) if row["received_amount"] is not None else None,
        payment_address=row["payment_address"],
        payment_uri=row["payment_uri"],
        transaction_hash=row["transaction_hash"],
        required_confirmations=row["required_confirmations"],
        current_confirmations=row["current_confirmations"],
        status=PaymentStatus(row["status"]),
        provider=row["provider"],
        exchange_rate_source=row["exchange_rate_source"],
        exchange_rate=float(row["exchange_rate"]) if row["exchange_rate"] is not None else None,
        exchange_rate_at=row["exchange_rate_at"],
        expires_at=row["expires_at"],
        paid_at=row["paid_at"],
        verified_at=row["verified_at"],
        idempotency_key=row["idempotency_key"],
        metadata=row["metadata"] or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _entitlement_from_row(row) -> UpgradeEntitlement:
    return UpgradeEntitlement(
        id=row["id"],
        account_id=row["account_id"],
        upgrade_product_id=row["upgrade_product_id"],
        payment_id=row["payment_id"],
        status=EntitlementStatus(row["status"]),
        activated_at=row["activated_at"],
        expires_at=row["expires_at"],
        metadata=row["metadata"] or {},
        created_at=row["created_at"],
    )
