"""Subscriptions, invoices and quota enforcement."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.exceptions import ApplicationError

from . import crypto, store, watcher
from .plans import get_plan, load_config, quote
from . import test_plan  # TEST PLAN (temporary)

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
    if not account_id:
        return
    if not enforcement_enabled():
        return
    plan = current_plan(account_id)
    lim = plan["limits"].get(metric)
    ok = lim is None or lim is True or (isinstance(lim, list) and item in lim)
    if not ok:
        raise QuotaExceededError(metric, plan=plan, limit=lim, upgrade_to=_upgrade_for(metric, plan, item))


def consume(account_id: str, metric: str, n: int = 1) -> None:
    """Monthly metered quota: check then increment."""
    if not account_id:
        return
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
        "payments": payment_status(), "enforcement": enforcement_enabled(),
        "test_plan": test_plan.plan() if test_plan.is_allowed(account_id) else None,  # TEST PLAN
    }


def payment_status() -> dict[str, Any]:
    assets = crypto.asset_catalog()
    return {"methods": ["crypto"], "mock": not any(a["live"] for a in assets) and crypto.mock_allowed(),
            "live_assets": [a["id"] for a in assets if a["live"]], "btcpay": crypto.btcpay_configured(),
            "mock_allowed": crypto.mock_allowed()}


MOCK_ADDR = {"tron": "TMockStructuralAiTestAddrDoNotPay01", "bsc": "0x000000000000000000000000000000000000dEaD",
             "eth": "0x000000000000000000000000000000000000dEaD", "polygon": "0x000000000000000000000000000000000000dEaD",
             "ton": "UQMockStructuralAiTestAddressDoNotPay0000000000000", "btcpay": "bc1qmockstructuralaitestaddressdonotpay0",
             "btc": "bc1qmockstructuralaitestaddressdonotpay0"}


def create_checkout(account_id: str, plan_id: str, duration_id: str, asset_id: str, *, frontend_base: str = "") -> dict:
    is_test = plan_id == test_plan.TEST_PLAN_ID  # TEST PLAN
    if is_test and not test_plan.is_allowed(account_id):
        raise ApplicationError("PLAN_NOT_PURCHASABLE", "This plan cannot be purchased.", status_code=422)
    plan = test_plan.plan() if is_test else get_plan(plan_id)
    if not plan.get("purchasable"):
        raise ApplicationError("PLAN_NOT_PURCHASABLE", "This plan cannot be purchased.", status_code=422)
    a = crypto.BY_ID.get(asset_id)
    if not a:
        raise ApplicationError("BAD_ASSET", "Pick a supported coin and network.", status_code=422)
    q = test_plan.quote() if is_test else quote(plan_id, duration_id)
    if not crypto.is_live(a) and not crypto.mock_allowed():
        raise ApplicationError("PAYMENT_UNAVAILABLE", "This payment method is not available yet. Choose another coin or network.", status_code=503)
    inv_id = uuid.uuid4().hex
    number = f"SA-{_now():%Y%m%d}-{inv_id[:6].upper()}"
    live = crypto.is_live(a)
    pay: dict[str, Any] = {"asset_id": a.id, "coin": a.coin, "network": a.network, "standard": a.standard,
                           "contract": a.contract, "mock": not live, "tx": "", "checkout_url": ""}
    try:
        if a.chain == "btcpay" and live:
            bp = crypto.btcpay_create(inv_id, q["amount_usdt"], a, f"SAIA {plan['name']} {q['months']}m",
                                      f"{frontend_base}/workspace/upgrades/pay?invoice={inv_id}")
            pay.update(bp, pay_address="", amount_crypto="", rate_usd=None, rate_source="btcpay")
        else:
            addr = crypto.receive_address(a) if live else MOCK_ADDR[a.chain]
            taken = watcher.pending_amounts(a.id, addr) if (live and crypto.is_watched(a)) else set()
            cq = crypto.quote_crypto(a, q["amount_usdt"], taken, live=live)
            pay.update(cq, pay_address=addr, **(crypto.start_marker(a) if live else {}))
            pay["payment_uri"] = crypto.payment_uri(a, addr, cq["amount_crypto"])
    except Exception as exc:  # noqa: BLE001
        raise ApplicationError("GATEWAY_ERROR", f"Could not create the crypto invoice: {exc}", status_code=502) from exc
    ts = crypto.now_ts()
    invoice = {"id": inv_id, "number": number, "plan_id": plan_id, "plan_name": plan["name"],
               "duration_id": duration_id, "months": q["months"], "discount_pct": q["discount_pct"], "method": "crypto",
               "gateway": "btcpay" if a.chain == "btcpay" else f"watch-{a.chain}", **pay,
               "amount_usdt": q["amount_usdt"], "amount_toman": q["amount_toman"],
               "amount": pay.get("amount_crypto") or q["amount_usdt"], "currency": a.coin,
               "status": "pending", "created_at": _now().isoformat(), "created_ts": ts,
               "expires_at": datetime.fromtimestamp(ts + crypto.EXPIRY_MIN * 60, UTC).isoformat(),
               "paid_at": None, "ref_id": ""}
    if is_test:  # TEST PLAN
        invoice.update(test_plan=True, test_days=q["days"], grants_plan_id=test_plan.GRANTS_PLAN_ID)
    with store.edit(account_id) as data:
        data.setdefault("invoices", []).append(invoice)
    store.index_invoice(inv_id, account_id)
    watcher.register(invoice, account_id)
    return {"invoice": public_invoice(invoice)}


def public_invoice(inv: dict) -> dict:
    out = {k: v for k, v in inv.items() if k not in ("from_block",)}
    if inv.get("pay_address") and inv["status"] == "pending":
        out["qr_svg"] = crypto.qr_svg(inv.get("payment_uri") or inv["pay_address"])
        if inv.get("payment_uri") != inv["pay_address"] and not inv.get("mock"):
            out["qr_address_svg"] = crypto.qr_svg(inv["pay_address"])  # plain-address QR for wallets without EIP-681
    a = crypto.BY_ID.get(inv.get("asset_id", ""))
    if a and a.chain in crypto.WATCHED_CHAINS:
        out["chain"] = a.chain
        out["chain_id"] = crypto.EVM_CHAINS.get(a.chain)
        out["explorer"] = crypto.EXPLORER.get(a.chain, "")
        out["confirmations_required"] = crypto.confirmations(a.chain)
        out["auto_detect"] = crypto.is_watched(a) and not inv.get("mock")
        out["decimals"] = a.decimals
        if inv["status"] == "pending":
            out.update(watcher.seen(inv["id"]))
    out["window_open"] = inv["status"] == "pending" and crypto.now_ts() < inv["created_ts"] + 24 * 3600
    return out


def _owned(account_id: str, invoice_id: str) -> dict:
    if store.account_for_invoice(invoice_id) != account_id:
        raise ApplicationError("INVOICE_NOT_FOUND", "Invoice not found", status_code=404)
    return next(i for i in store.load(account_id)["invoices"] if i["id"] == invoice_id)


def refresh_invoice(account_id: str, invoice_id: str) -> dict:
    """Poll the chain / BTCPay for a pending invoice; mark paid or expired."""
    inv = _owned(account_id, invoice_id)
    if inv["status"] != "pending" or inv.get("mock"):
        if inv["status"] == "pending" and crypto.now_ts() > inv["created_ts"] + crypto.EXPIRY_MIN * 60:
            return public_invoice(_settle(account_id, invoice_id, ok=False, status="expired"))
        return public_invoice(inv)
    if watcher.is_token_invoice(inv):
        if crypto.now_ts() > inv["created_ts"] + 24 * 3600:
            return public_invoice(settle_expired(account_id, invoice_id))
        try:
            watcher.run_once()  # throttled; the background watcher normally does this
        except Exception:  # noqa: BLE001 - RPC hiccup: stay pending
            pass
        return public_invoice(_owned(account_id, invoice_id))
    found = None
    try:
        if inv.get("btcpay_id"):
            st = crypto.btcpay_status(inv["btcpay_id"])
            if st == "Settled":
                found = {"tx": inv["btcpay_id"]}
            elif st in ("Expired", "Invalid"):
                return public_invoice(_settle(account_id, invoice_id, ok=False, status="expired"))
        else:
            found = crypto.find_payment(inv)
    except Exception:  # noqa: BLE001 - RPC hiccup: stay pending, try next poll
        found = None
    if found:
        return public_invoice(_settle(account_id, invoice_id, ok=True, tx=found["tx"]))
    # grace: late payments are still matched for 24h after expiry
    if crypto.now_ts() > inv["created_ts"] + 24 * 3600:
        return public_invoice(_settle(account_id, invoice_id, ok=False, status="expired"))
    return public_invoice(inv)


def mock_confirm(account_id: str, invoice_id: str, ok: bool = True) -> dict:
    inv = _owned(account_id, invoice_id)
    if not inv.get("mock") or not crypto.mock_allowed():
        raise ApplicationError("NOT_MOCK", "Only test invoices can be simulated (and never in production).", status_code=409)
    return public_invoice(_settle(account_id, invoice_id, ok=ok, tx="mock-" + invoice_id[:10], status="cancelled"))


def _settle(account_id: str, invoice_id: str, *, ok: bool, tx: str = "", status: str = "failed") -> dict:
    if ok:
        return settle_paid(account_id, invoice_id, tx=tx, via="legacy")[0]
    with store.edit(account_id) as data:
        inv = next(i for i in data["invoices"] if i["id"] == invoice_id)
        if inv["status"] == "pending":
            inv.update(status=status)
        return inv


def settle_expired(account_id: str, invoice_id: str) -> dict:
    return _settle(account_id, invoice_id, ok=False, status="expired")


def settle_paid(account_id: str, invoice_id: str, *, tx: str = "", via: str = "auto", received: str = "",
                confirmations: int | None = None, note: str = "", late: bool = False, sender: str = "",
                admin: str = "", allow_expired: bool = False) -> tuple[dict, bool]:
    """Mark an invoice paid and activate/extend the subscription. Idempotent: returns (invoice, applied)."""
    with store.edit(account_id) as data:
        inv = next(i for i in data["invoices"] if i["id"] == invoice_id)
        if inv["status"] != "pending" and not (allow_expired and inv["status"] in ("expired", "failed", "cancelled")):
            return inv, False
        inv.update(status="paid", paid_at=_now().isoformat(), ref_id=tx, tx=tx, paid_via=via)
        if received:
            inv["received"] = received
        if confirmations is not None:
            inv["confirmations"] = confirmations
        if note:
            inv["paid_note"] = note
        if late:
            inv["paid_late"] = True
        if sender:
            inv["sender"] = sender
        if admin:
            inv["confirmed_by"] = admin
        sub = active_subscription(data)
        if inv.get("test_plan"):  # TEST PLAN: Pro-equivalent for N days; never shortens an existing subscription
            add = timedelta(days=int(inv.get("test_days") or 1))
            if sub:
                expires = datetime.fromisoformat(sub["expires_at"]) + add
                data["subscription"] = {**sub, "expires_at": expires.isoformat()}
                action = "test_extended"
            else:
                expires = _now() + add
                data["subscription"] = {"plan_id": inv.get("grants_plan_id") or "pro", "plan_name": inv["plan_name"],
                                        "started_at": _now().isoformat(), "expires_at": expires.isoformat(),
                                        "last_invoice": inv["number"], "auto_renew": False, "test": True}
                action = "test_activated"
            data.setdefault("history", []).append({"at": _now().isoformat(), "action": action, "plan_id": inv["plan_id"],
                                                   "invoice": inv["number"], "expires_at": expires.isoformat(), "via": via})
            return inv, True
        if sub and sub["plan_id"] == inv["plan_id"]:
            start = datetime.fromisoformat(sub["expires_at"]); action = "renewed"
        else:
            start = _now(); action = "activated" if not sub else "changed"
        expires = start + timedelta(days=30 * inv["months"] + (5 if inv["months"] == 12 else 0))
        data["subscription"] = {"plan_id": inv["plan_id"], "plan_name": inv["plan_name"],
                                "started_at": (sub or {}).get("started_at") if action == "renewed" else _now().isoformat(),
                                "expires_at": expires.isoformat(), "last_invoice": inv["number"], "auto_renew": False}
        data.setdefault("history", []).append({"at": _now().isoformat(), "action": action, "plan_id": inv["plan_id"],
                                               "invoice": inv["number"], "expires_at": expires.isoformat(), "via": via})
        return inv, True


# ---------------- tx-hash claim (user) and admin ----------------

def claim_tx(account_id: str, invoice_id: str, tx: str) -> dict:
    _owned(account_id, invoice_id)
    return watcher.claim_tx(account_id, invoice_id, tx)


def admin_ids() -> set[str]:
    return {x.strip().lower() for x in (os.environ.get("BILLING_ADMIN_ACCOUNTS") or "").split(",") if x.strip()}


def is_admin(account_id: str, email: str | None = None) -> bool:
    ids = admin_ids()
    return bool(ids) and (account_id.lower() in ids or bool(email and email.lower() in ids))


def admin_confirm(admin: str, invoice_id: str, tx: str = "", note: str = "") -> dict:
    """Manual confirmation. With a tx hash the transfer is verified on-chain; without one the note is mandatory."""
    account_id = store.account_for_invoice(invoice_id)
    if not account_id:
        raise ApplicationError("INVOICE_NOT_FOUND", "Invoice not found", status_code=404)
    if tx:
        return watcher.claim_tx(account_id, invoice_id, tx, admin=admin, note=note)
    if not note.strip():
        raise ApplicationError("NOTE_REQUIRED", "Give a reason (e.g. the payment reference) for a manual confirmation.", status_code=422)
    inv, applied = settle_paid(account_id, invoice_id, tx="manual-" + invoice_id[:10], via="admin", note=note.strip(),
                               admin=admin, allow_expired=True)
    if applied:
        watcher.watch_update(remove=[invoice_id])
    return public_invoice(inv)


def check_frame_size(account_id: str, inputs: dict) -> None:
    if not account_id:
        return
    def _i(k):
        try:
            return int((inputs or {}).get(k) or 0)
        except (TypeError, ValueError):
            return 0
    require_max(account_id, "frame_max_storeys", _i("storeys"))
    require_max(account_id, "frame_max_bays", max(_i("bays_x"), _i("bays_y")))
