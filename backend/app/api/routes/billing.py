"""Plans, subscription account, checkout and gateway callbacks."""
from __future__ import annotations

import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from app.application.exceptions import ApplicationError
from pydantic import BaseModel

from app.api.deps import get_current_account
from app.application.billing import service
from app.application.billing.crypto import EXPIRY_MIN, asset_catalog
from app.application.billing.plans import catalog
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/billing", tags=["billing"])


def _base(request: Request) -> str:
    env = (os.environ.get("BILLING_PUBLIC_BASE_URL") or "").rstrip("/")
    if env:
        return env
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


class CheckoutBody(BaseModel):
    plan_id: str
    duration_id: Literal["1m", "3m", "12m"]
    asset_id: str


class MockBody(BaseModel):
    ok: bool = True


@router.get("/plans")
def plans():
    return {**catalog(), "assets": asset_catalog(), "invoice_minutes": EXPIRY_MIN}


@router.get("/account")
def account(acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return service.account_summary(acc.account_id)


@router.post("/checkout")
def checkout(body: CheckoutBody, request: Request, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return service.create_checkout(acc.account_id, body.plan_id, body.duration_id, body.asset_id, frontend_base=_base(request))


@router.get("/invoices/{invoice_id}")
def invoice(invoice_id: str, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return {"invoice": service.refresh_invoice(acc.account_id, invoice_id)}


@router.post("/invoices/{invoice_id}/mock-confirm")
def mock_confirm(invoice_id: str, body: MockBody, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return {"invoice": service.mock_confirm(acc.account_id, invoice_id, body.ok)}


class ClaimBody(BaseModel):
    tx: str


@router.post("/invoices/{invoice_id}/claim-tx")
def claim_tx(invoice_id: str, body: ClaimBody, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    """Paid but not detected yet (or window closed)? Submit the transaction hash; it is verified on-chain."""
    return {"invoice": service.claim_tx(acc.account_id, invoice_id, body.tx.strip())}


# ---------------- admin (BILLING_ADMIN_ACCOUNTS = comma list of account ids / emails) ----------------

def _admin(acc: AuthenticatedAccount) -> str:
    if not service.is_admin(acc.account_id, acc.email):
        raise ApplicationError("FORBIDDEN", "Admin only.", status_code=403)
    return acc.email or acc.account_id


class AdminConfirmBody(BaseModel):
    tx: str = ""
    note: str = ""


@router.get("/admin/payments")
def admin_payments(acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    from app.application.billing import watcher
    _admin(acc)
    return {**watcher.admin_overview(), "payments": service.payment_status()}


@router.post("/admin/invoices/{invoice_id}/confirm")
def admin_confirm(invoice_id: str, body: AdminConfirmBody, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return {"invoice": service.admin_confirm(_admin(acc), invoice_id, body.tx.strip(), body.note)}
