"""Digital currency payment and upgrade REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_actor_id, get_digital_payment_agent
from app.infrastructure.config import get_settings
from app.api.schemas.payments import (
    CreateInvoiceRequest,
    CryptoPaymentResponse,
    EntitlementResponse,
    PaymentInstructionsResponse,
    PaymentStatusResponse,
    SupportedCryptoResponse,
    UpgradeCatalogResponse,
    UpgradeProductResponse,
    VerifyTransactionRequest,
)
from app.application.digital_payment_agent import DigitalPaymentAgent

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/catalog", response_model=UpgradeCatalogResponse)
def get_upgrade_catalog(
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
) -> UpgradeCatalogResponse:
    return UpgradeCatalogResponse(
        products=[UpgradeProductResponse.from_domain(item) for item in agent.list_available_upgrades()],
        supported_crypto=[
            SupportedCryptoResponse.model_validate(item) for item in agent.list_supported_currencies()
        ],
    )


@router.get("/upgrades", response_model=list[UpgradeProductResponse])
def list_upgrade_products(
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
) -> list[UpgradeProductResponse]:
    return [UpgradeProductResponse.from_domain(item) for item in agent.list_available_upgrades()]


@router.post("/invoices", response_model=PaymentInstructionsResponse)
def create_upgrade_invoice(
    body: CreateInvoiceRequest,
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> PaymentInstructionsResponse:
    payment = agent.create_upgrade_invoice(
        account_id=actor_id,
        upgrade_product_id=body.upgrade_product_id,
        currency=body.currency,
        network=body.network,
        idempotency_key=body.idempotency_key,
    )
    return PaymentInstructionsResponse(
        payment=CryptoPaymentResponse.from_domain(payment),
        instructions=agent.build_payment_instructions(payment),
    )


@router.get("/invoices/{payment_id}", response_model=PaymentStatusResponse)
def get_invoice_status(
    payment_id: UUID,
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> PaymentStatusResponse:
    result = agent.get_payment_status(payment_id, account_id=actor_id)
    return PaymentStatusResponse(
        payment=CryptoPaymentResponse.model_validate(result["payment"]),
        entitlement=result.get("entitlement"),
        upgrade_activated=bool(result.get("upgrade_activated")),
    )


@router.post("/invoices/{payment_id}/reconcile", response_model=PaymentStatusResponse)
def reconcile_invoice_payment(
    payment_id: UUID,
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> PaymentStatusResponse:
    result = agent.reconcile_payment(payment_id, account_id=actor_id)
    return PaymentStatusResponse(
        payment=CryptoPaymentResponse.model_validate(result["payment"]),
        entitlement=result.get("entitlement"),
        upgrade_activated=bool(result.get("upgrade_activated")),
    )


@router.post("/invoices/{payment_id}/verify", response_model=PaymentStatusResponse)
def verify_invoice_transaction(
    payment_id: UUID,
    body: VerifyTransactionRequest,
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> PaymentStatusResponse:
    result = agent.submit_transaction_for_verification(
        payment_id,
        account_id=actor_id,
        transaction_hash=body.transaction_hash,
    )
    return PaymentStatusResponse(
        payment=CryptoPaymentResponse.model_validate(result["payment"]),
        entitlement=result.get("entitlement"),
        upgrade_activated=bool(result.get("upgrade_activated")),
    )


@router.get("/entitlements", response_model=list[EntitlementResponse])
def list_entitlements(
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> list[EntitlementResponse]:
    return [
        EntitlementResponse.from_domain(item) for item in agent.list_account_entitlements(actor_id)
    ]


@router.post("/webhooks/{provider}")
async def payment_provider_webhook(
    provider: str,
    request: Request,
    agent: Annotated[DigitalPaymentAgent, Depends(get_digital_payment_agent)],
) -> dict:
    payload = await request.body()
    signature = (
        request.headers.get("X-Payment-Signature")
        or request.headers.get("BTCPay-Sig")
    )
    configured = get_settings().crypto_payment_gateway.strip().lower()
    if provider.strip().lower() not in {configured, "mock-gateway", "btcpay"}:
        return {"provider": provider, "processed": False, "reason": "provider_mismatch"}
    result = agent.process_provider_webhook(payload, signature)
    return {"provider": provider, **result}
