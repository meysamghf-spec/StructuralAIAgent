"""Plans, subscription account, checkout and gateway callbacks."""
from __future__ import annotations

import os
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import get_current_account
from app.application.billing import service
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
    method: Literal["card", "crypto"]


@router.get("/plans")
def plans():
    return catalog()


@router.get("/account")
def account(acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    return service.account_summary(acc.account_id)


@router.post("/checkout")
def checkout(body: CheckoutBody, request: Request, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]):
    base = _base(request)
    return service.create_checkout(acc.account_id, body.plan_id, body.duration_id, body.method, api_base=base, frontend_base=base)


@router.api_route("/callback/{gateway}", methods=["GET", "POST"])
async def callback(gateway: str, request: Request):
    params = dict(request.query_params)
    if request.method == "POST":
        try:
            params.update({k: str(v) for k, v in (await request.form()).items()})
        except Exception:  # noqa: BLE001
            pass
    base = _base(request)
    invoice_id = params.get("invoice", "")
    try:
        _, inv = service.complete(invoice_id, params, frontend_base=base)
        q = {"invoice": inv["number"], "status": inv["status"]}
    except Exception:  # noqa: BLE001
        q = {"status": "error"}
    return RedirectResponse(f"{base}/workspace/upgrades?{urlencode(q)}", status_code=303)
