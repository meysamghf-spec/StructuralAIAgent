"""Subscriptions, invoices and quota enforcement."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.exceptions import ApplicationError

from . import gateways, store
from .plans import get_plan, load_config, quote

METRIC_LABELS = {
    "projects": "projects", "analyses_per_month": "analyses this month",
    "autocad_imports_per_month": "AutoCAD imports this month", "frame_max_storeys": "storeys in a 3D frame",
    "frame_max_bays": "bays in a 3D frame", "exports": "export format", "design_sheets": "design sheet",
    "optimization": "optimization", "seats": "seats", "storage_mb": "storage (MB)",
}
MONTHLY = {"analyses_per_month": "analyses", "autocad_imports_per_month": "autocad_imports"}


class QuotaExceededError(ApplicationError):
    def __init__(self, metric: str, *, plan: dict, limit: Any, used: Any = None, upgrade_to: str | None) -> None:
        label = METRIC_LABELS.get(metric, metric)
        if isinstance(limit, bool) or isinstance(limit, list):
            msg = f"{label.capitalize()} is not included in the {plan['name']} plan."
        else:
            msg = f"The {plan['name']} plan allows {limit} {label}" + (f" (used {used})." if used is not None else ".")
        if upgrade_to:
            msg += f" Upgrade to {get_plan(upgrade_to)['name']} on the Upgrades page."
        super().__init__("QUOTA_EXCEEDED", msg, status_code=402,
                         details={"metric": metric, "limit": limit, "used": used, "plan": plan["id"],
                                  "upgrade_plan_id": upgrade_to, "upgrade_url": "/workspace/upgrades"})


def _now() -> datetime:
    return datetime.now(UTC)


def enforcement_enabled() -> bool:
    return (os.environ.get("BILLING_ENFORCEMENT") or "1").strip() != "0"


def _complimentary(account_id: str) -> bool:
    ids = {x.strip() for x in (os.environ.get("BILLING_COMPLIMENTARY_ACCOUNTS") or "").split(",") if x.strip()}
    return account_id in ids


def active_subscription(data: dict) -> dict | None:
    sub = data.get("subscription")
    if sub and datetime.fromisoformat(sub["expires_at"]) > _now():
        return sub
    return None


def current_plan(account_id: str) -> dict:
    if _complimentary(account_id):
        return get_plan("enterprise")
    sub = active_subscription(store.load(account_id))
    return get_plan(sub["plan_id"]) if sub else get_plan("free")


def _upgrade_for(metric: str, current: dict, need: Any = None) -> str | None:
    order = [p for p in load_config()["plans"] if p.get("purchasable")]
    ids = [p["id"] for p in load_config()["plans"]]
    for p in order:
        if ids.index(p["id"]) <= ids.index(current["id"]):
            continue
        lim = p["limits"].get(metric)
        if lim is None or lim is True:
            return p["id"]
        if isinstance(lim, list) and (need is None or need in lim):
            return p["id"]
        if isinstance(lim, (int, float)) and not isinstance(lim, bool) and (need is None or lim >= need):
            return p["id"]
    return None


def _month() -> str:
    return _now().strftime("%Y-%m")


def usage(account_id: str) -> dict[str, int]:
    return store.load(account_id).get("usage", {}).get(_month(), {})


# ---------------- enforcement API (call from routes) ----------------

def require_count(account_id: str, metric: str, current_count: int) -> None:
    """e.g. projects: block creating one more when current_count >= limit."""
    if not enforcement_enabled():
        return
    plan = current_plan(account_id)
    lim = plan["limits"].get(metric)
    if lim is not None and current_count >= lim:
        raise QuotaExceededError(metric, plan=plan, limit=lim, used=current_count, upgrade_to=_upgrade_for(metric, plan, current_count + 1))


def require_max(account_id: str, metric: str, value: int) -> None:
    if not enforcement_enabled():
        return
    plan = current_plan(account_id)
    lim = plan["limits"].get(metric)
    if lim is not None and value > lim:
        raise QuotaExceededError(metric, plan=plan, limit=lim, used=value, upgrade_to=_upgrade_for(metric, plan, value))


def require_feature(account_id: str, metric: str, item: str | None = None) -> None:
    if not enforcement_enabled():
        return
    plan = current_plan(account_id)
    lim = plan["limits"].get(metric)
    ok = lim is None or lim is True or (isinstance(lim, list) and item in lim)
    if not ok:
        raise QuotaExceededError(metric, plan=plan, limit=lim, upgrade_to=_upgrade_for(metric, plan, item))


def consume(account_id: str, metric: str, n: int = 1) -> None:
    """Monthly metered quota: check then increment."""
    key = MONTHLY[metric]
    plan = current_plan(account_id)
    lim = plan["limits"].get(metric)
    with store.edit(account_id) as data:
        month = data.setdefault("usage", {}).setdefault(_month(), {})
        used = month.get(key, 0)
        if enforcement_enabled() and lim is not None and used + n > lim:
            raise QuotaExceededError(metric, plan=plan, limit=lim, used=used, upgrade_to=_upgrade_for(metric, plan, used + n))
        month[key] = used + n


# ---------------- account / checkout ----------------

def account_summary(account_id: str) -> dict[str, Any]:
    data = store.load(account_id)
    plan = current_plan(account_id)
    sub = active_subscription(data)
    u = data.get("usage", {}).get(_month(), {})
    return {
        "plan": plan, "subscription": sub, "complimentary": _complimentary(account_id),
        "usage": {"analyses_per_month": u.get("analyses", 0), "autocad_imports_per_month": u.get("autocad_imports", 0)},
        "invoices": list(reversed(data.get("invoices", [])))[:50],
        "history": list(reversed(data.get("history", [])))[:50],
        "gateways": gateways.gateway_status(), "enforcement": enforcement_enabled(),
    }


def create_checkout(account_id: str, plan_id: str, duration_id: str, method: str, *, api_base: str, frontend_base: str) -> dict:
    plan = get_plan(plan_id)
    if not plan.get("purchasable"):
        raise ApplicationError("PLAN_NOT_PURCHASABLE", "This plan cannot be purchased.", status_code=422)
    q = quote(plan_id, duration_id)
    inv_id = uuid.uuid4().hex
    if method == "card":
        gw = gateways.card_gateway(frontend_base); amount, currency = q["amount_rial"], "IRR"
    elif method == "crypto":
        gw = gateways.crypto_gateway(frontend_base); amount, currency = q["amount_usdt"], "USDT"
    else:
        raise ApplicationError("BAD_METHOD", "Payment method must be card or crypto.", status_code=422)
    callback = f"{api_base}/api/v1/billing/callback/{gw.name}?invoice={inv_id}"
    try:
        start = gw.start(invoice_id=inv_id, amount=amount, description=f"StructuralAI {plan['name']} {q['months']} month(s)", callback_url=callback)
    except Exception as exc:  # gateway down / not configured
        raise ApplicationError("GATEWAY_ERROR", f"Payment gateway error: {exc}", status_code=502) from exc
    invoice = {"id": inv_id, "number": f"SA-{_now():%Y%m%d}-{inv_id[:6].upper()}", "plan_id": plan_id, "plan_name": plan["name"],
               "duration_id": duration_id, "months": q["months"], "discount_pct": q["discount_pct"], "method": method,
               "gateway": gw.name, "mock": gw.name.endswith("-mock"), "amount": amount, "currency": currency,
               "amount_toman": q["amount_toman"], "amount_usdt": q["amount_usdt"], "authority": start.authority,
               "status": "pending", "created_at": _now().isoformat(), "paid_at": None, "ref_id": "", "card": ""}
    with store.edit(account_id) as data:
        data.setdefault("invoices", []).append(invoice)
    store.index_invoice(inv_id, account_id)
    return {"invoice": invoice, "redirect_url": start.redirect_url}


def complete(invoice_id: str, params: dict[str, str], *, frontend_base: str) -> tuple[str, dict]:
    account_id = store.account_for_invoice(invoice_id)
    if not account_id:
        raise ApplicationError("INVOICE_NOT_FOUND", "Invoice not found", status_code=404)
    inv = next(i for i in store.load(account_id)["invoices"] if i["id"] == invoice_id)
    if inv["status"] != "pending":
        return account_id, inv  # idempotent
    gw = gateways.gateway_by_name(inv["gateway"], frontend_base)
    try:
        res = gw.verify(authority=params.get("Authority") or params.get("trackId") or params.get("id") or inv["authority"],
                        amount=inv["amount"], params=params)
    except Exception as exc:  # noqa: BLE001
        res = gateways.VerifyResult(False, message=f"Verify error: {exc}")
    with store.edit(account_id) as data:
        inv = next(i for i in data["invoices"] if i["id"] == invoice_id)
        if inv["status"] != "pending":
            return account_id, inv
        if not res.ok:
            inv.update(status="failed", note=res.message)
            return account_id, inv
        inv.update(status="paid", paid_at=_now().isoformat(), ref_id=res.ref_id, card=res.card)
        sub = active_subscription(data)
        if sub and sub["plan_id"] == inv["plan_id"]:
            start = datetime.fromisoformat(sub["expires_at"]); action = "renewed"
        else:
            start = _now(); action = "activated" if not sub else "changed"
        expires = start + timedelta(days=30 * inv["months"] + (5 if inv["months"] == 12 else 0))
        data["subscription"] = {"plan_id": inv["plan_id"], "plan_name": inv["plan_name"],
                                "started_at": (sub or {}).get("started_at") if action == "renewed" else _now().isoformat(),
                                "expires_at": expires.isoformat(), "last_invoice": inv["number"], "auto_renew": False}
        data.setdefault("history", []).append({"at": _now().isoformat(), "action": action, "plan_id": inv["plan_id"],
                                               "invoice": inv["number"], "expires_at": expires.isoformat()})
    return account_id, inv


def check_frame_size(account_id: str, inputs: dict) -> None:
    def _i(k):
        try:
            return int((inputs or {}).get(k) or 0)
        except (TypeError, ValueError):
            return 0
    require_max(account_id, "frame_max_storeys", _i("storeys"))
    require_max(account_id, "frame_max_bays", max(_i("bays_x"), _i("bays_y")))
