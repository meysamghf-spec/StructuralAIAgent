"""API schemas for digital currency payments and upgrades."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.payments import CryptoPayment, UpgradeEntitlement, UpgradeProduct


class UpgradeProductResponse(BaseModel):
    id: str
    name: str
    description: str
    fiat_price_usd: float
    billing_period_days: int | None = None
    features: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, product: UpgradeProduct) -> UpgradeProductResponse:
        return cls.model_validate(product.model_dump())


class SupportedCryptoResponse(BaseModel):
    currency: str
    network: str
    display_name: str
    required_confirmations: int
    decimals: int


class CreateInvoiceRequest(BaseModel):
    upgrade_product_id: str
    currency: str
    network: str
    idempotency_key: str | None = None


class CryptoPaymentResponse(BaseModel):
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
    required_confirmations: int
    current_confirmations: int
    status: str
    provider: str
    exchange_rate_source: str | None = None
    exchange_rate: float | None = None
    exchange_rate_at: datetime | None = None
    expires_at: datetime
    paid_at: datetime | None = None
    verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, payment: CryptoPayment) -> CryptoPaymentResponse:
        payload = payment.model_dump(mode="json")
        payload["status"] = payment.status.value
        return cls.model_validate(payload)


class PaymentInstructionsResponse(BaseModel):
    payment: CryptoPaymentResponse
    instructions: dict[str, Any]


class PaymentStatusResponse(BaseModel):
    payment: CryptoPaymentResponse
    entitlement: dict[str, Any] | None = None
    upgrade_activated: bool = False


class EntitlementResponse(BaseModel):
    id: UUID
    account_id: str
    upgrade_product_id: str
    payment_id: UUID
    status: str
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, entitlement: UpgradeEntitlement) -> EntitlementResponse:
        payload = entitlement.model_dump(mode="json")
        payload["status"] = entitlement.status.value
        return cls.model_validate(payload)


class VerifyTransactionRequest(BaseModel):
    transaction_hash: str = Field(min_length=8, max_length=128)


class UpgradeCatalogResponse(BaseModel):
    products: list[UpgradeProductResponse]
    supported_crypto: list[SupportedCryptoResponse]
