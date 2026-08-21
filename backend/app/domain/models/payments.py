"""Digital currency payment and upgrade entitlement domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAYMENT_DETECTED = "PAYMENT_DETECTED"
    CONFIRMING = "CONFIRMING"
    PAID = "PAID"
    UNDERPAID = "UNDERPAID"
    OVERPAID = "OVERPAID"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


TERMINAL_PAYMENT_STATUSES = frozenset(
    {
        PaymentStatus.PAID,
        PaymentStatus.EXPIRED,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.REFUNDED,
        PaymentStatus.UNDERPAID,
        PaymentStatus.MANUAL_REVIEW,
    }
)


class EntitlementStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class UpgradeProduct(BaseModel):
    id: str
    name: str
    description: str
    fiat_price_usd: float
    billing_period_days: int | None = None
    features: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SupportedCryptoOption(BaseModel):
    currency: str
    network: str
    display_name: str
    required_confirmations: int = 3
    decimals: int = 8


class ExchangeRateSnapshot(BaseModel):
    source: str
    currency: str
    rate_usd: float
    captured_at: datetime


class CryptoPayment(BaseModel):
    id: UUID
    account_id: str
    upgrade_product_id: str
    invoice_id: str
    currency: str
    network: str
    fiat_amount_usd: float
    crypto_amount: float
    received_amount: float | None = None
    payment_address: str
    payment_uri: str | None = None
    transaction_hash: str | None = None
    required_confirmations: int = 3
    current_confirmations: int = 0
    status: PaymentStatus
    provider: str
    exchange_rate_source: str | None = None
    exchange_rate: float | None = None
    exchange_rate_at: datetime | None = None
    expires_at: datetime
    paid_at: datetime | None = None
    verified_at: datetime | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UpgradeEntitlement(BaseModel):
    id: UUID
    account_id: str
    upgrade_product_id: str
    payment_id: UUID
    status: EntitlementStatus
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PaymentAuditEvent(BaseModel):
    id: UUID
    payment_id: UUID
    event_type: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GatewayInvoiceRequest(BaseModel):
    payment_id: UUID
    invoice_id: str
    account_id: str
    upgrade_product_id: str
    currency: str
    network: str
    crypto_amount: float
    fiat_amount_usd: float
    expires_at: datetime


class GatewayPaymentStatus(BaseModel):
    detected: bool = False
    transaction_hash: str | None = None
    received_amount: float | None = None
    confirmations: int = 0
    destination_address: str | None = None
    currency: str | None = None
    network: str | None = None
    status_hint: PaymentStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
