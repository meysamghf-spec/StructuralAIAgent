"""Payment gateway adapters. Secrets come only from env; never logged.

Rial (Shetab card): zarinpal | zibal | idpay | mock  (BILLING_CARD_GATEWAY)
Crypto:             btcpay | mock                   (auto: btcpay when BTCPAY_* configured)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx


class GatewayError(Exception):
    pass


@dataclass
class StartResult:
    authority: str
    redirect_url: str


@dataclass
class VerifyResult:
    ok: bool
    ref_id: str = ""
    card: str = ""
    message: str = ""


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


class MockGateway:
    """Simulated bank page hosted by the frontend; never moves money."""

    def __init__(self, name: str, frontend_base: str) -> None:
        self.name, self._fb = name, frontend_base

    def start(self, *, invoice_id: str, amount: float, description: str, callback_url: str) -> StartResult:
        authority = f"MOCK-{invoice_id[:12]}"
        q = urlencode({"invoice": invoice_id, "authority": authority, "gateway": self.name,
                       "amount": amount, "callback": callback_url})
        return StartResult(authority, f"{self._fb}/workspace/upgrades/mock-pay?{q}")

    def verify(self, *, authority: str, amount: float, params: dict[str, str]) -> VerifyResult:
        ok = params.get("Status", params.get("status", "")).upper() in ("OK", "1", "PAID")
        return VerifyResult(ok, ref_id=f"MOCKREF-{authority[-6:]}" if ok else "", card="6037-99**-****-1234" if ok else "",
                            message="Mock payment" + (" approved" if ok else " cancelled"))


class ZarinpalGateway:
    """Zarinpal Payment Gateway v4 (amount in rial). BILLING_ZARINPAL_SANDBOX=1 uses sandbox.zarinpal.com."""

    def __init__(self) -> None:
        self.name = "zarinpal"
        self._mid = _env("ZARINPAL_MERCHANT_ID")
        sandbox = _env("BILLING_ZARINPAL_SANDBOX", "1") == "1"
        host = "sandbox.zarinpal.com" if sandbox else "payment.zarinpal.com"
        self._api = f"https://{host}/pg/v4/payment"
        self._start = f"https://{host}/pg/StartPay/"
        if not self._mid:
            raise GatewayError("ZARINPAL_MERCHANT_ID is not set")

    def start(self, *, invoice_id, amount, description, callback_url) -> StartResult:
        r = httpx.post(f"{self._api}/request.json", timeout=20, json={
            "merchant_id": self._mid, "amount": int(amount), "currency": "IRR",
            "description": description[:250], "callback_url": callback_url, "metadata": {"order_id": invoice_id}})
        data = (r.json() or {}).get("data") or {}
        if data.get("code") != 100:
            raise GatewayError(f"Zarinpal request failed: {(r.json() or {}).get('errors')}")
        return StartResult(data["authority"], self._start + data["authority"])

    def verify(self, *, authority, amount, params) -> VerifyResult:
        if params.get("Status") != "OK":
            return VerifyResult(False, message="Cancelled by user")
        r = httpx.post(f"{self._api}/verify.json", timeout=20,
                       json={"merchant_id": self._mid, "amount": int(amount), "authority": authority})
        data = (r.json() or {}).get("data") or {}
        if data.get("code") in (100, 101):
            return VerifyResult(True, ref_id=str(data.get("ref_id", "")), card=str(data.get("card_pan", "")))
        return VerifyResult(False, message=f"Verify failed: {(r.json() or {}).get('errors')}")


class ZibalGateway:
    """Zibal (amount in rial). Merchant 'zibal' is Zibal's public test merchant."""

    def __init__(self) -> None:
        self.name = "zibal"
        self._mid = _env("ZIBAL_MERCHANT", "zibal")

    def start(self, *, invoice_id, amount, description, callback_url) -> StartResult:
        r = httpx.post("https://gateway.zibal.ir/v1/request", timeout=20, json={
            "merchant": self._mid, "amount": int(amount), "callbackUrl": callback_url,
            "orderId": invoice_id, "description": description[:250]})
        data = r.json() or {}
        if data.get("result") != 100:
            raise GatewayError(f"Zibal request failed: {data.get('message')}")
        tid = str(data["trackId"])
        return StartResult(tid, f"https://gateway.zibal.ir/start/{tid}")

    def verify(self, *, authority, amount, params) -> VerifyResult:
        if str(params.get("success", "")) != "1":
            return VerifyResult(False, message="Cancelled by user")
        r = httpx.post("https://gateway.zibal.ir/v1/verify", timeout=20, json={"merchant": self._mid, "trackId": int(authority)})
        data = r.json() or {}
        if data.get("result") in (100, 201) and int(data.get("amount", amount)) == int(amount):
            return VerifyResult(True, ref_id=str(data.get("refNumber", "")), card=str(data.get("cardNumber", "")))
        return VerifyResult(False, message=f"Verify failed: {data.get('message')}")


class IdpayGateway:
    """IDPay v1.1 (amount in rial). BILLING_IDPAY_SANDBOX=1 sends X-SANDBOX."""

    def __init__(self) -> None:
        self.name = "idpay"
        self._key = _env("IDPAY_API_KEY")
        if not self._key:
            raise GatewayError("IDPAY_API_KEY is not set")
        self._h = {"X-API-KEY": self._key, **({"X-SANDBOX": "1"} if _env("BILLING_IDPAY_SANDBOX", "1") == "1" else {})}

    def start(self, *, invoice_id, amount, description, callback_url) -> StartResult:
        r = httpx.post("https://api.idpay.ir/v1.1/payment", headers=self._h, timeout=20, json={
            "order_id": invoice_id, "amount": int(amount), "callback": callback_url, "desc": description[:250]})
        data = r.json() or {}
        if "id" not in data:
            raise GatewayError(f"IDPay request failed: {data.get('error_message')}")
        return StartResult(data["id"], data["link"])

    def verify(self, *, authority, amount, params) -> VerifyResult:
        if str(params.get("status")) not in ("10", "100"):
            return VerifyResult(False, message="Not paid")
        r = httpx.post("https://api.idpay.ir/v1.1/payment/verify", headers=self._h, timeout=20,
                       json={"id": authority, "order_id": params.get("order_id", "")})
        data = r.json() or {}
        if int(data.get("status", 0)) in (100, 101):
            return VerifyResult(True, ref_id=str((data.get("payment") or {}).get("track_id", "")),
                                card=str((data.get("payment") or {}).get("card_no", "")))
        return VerifyResult(False, message=f"Verify failed: {data.get('error_message')}")


class BtcpayGateway:
    """BTCPay Server Greenfield invoice priced in USDT->USD; buyer pays USDT/BTC on BTCPay checkout."""

    def __init__(self) -> None:
        self.name = "btcpay"
        self._url = _env("BTCPAY_SERVER_URL").rstrip("/")
        self._key = _env("BTCPAY_API_KEY")
        self._store = _env("BTCPAY_STORE_ID")
        if not (self._url and self._key and self._store):
            raise GatewayError("BTCPay is not configured")

    def _c(self):
        return httpx.Client(base_url=f"{self._url}/api/v1", timeout=20, headers={"Authorization": f"token {self._key}"})

    def start(self, *, invoice_id, amount, description, callback_url) -> StartResult:
        with self._c() as c:
            r = c.post(f"/stores/{self._store}/invoices", json={
                "amount": str(amount), "currency": "USD", "metadata": {"orderId": invoice_id, "itemDesc": description},
                "checkout": {"redirectURL": callback_url, "redirectAutomatically": True, "expirationMinutes": 60}})
            r.raise_for_status(); data = r.json()
        return StartResult(data["id"], data["checkoutLink"])

    def verify(self, *, authority, amount, params) -> VerifyResult:
        with self._c() as c:
            r = c.get(f"/stores/{self._store}/invoices/{authority}"); r.raise_for_status(); data = r.json()
        ok = data.get("status") == "Settled"
        return VerifyResult(ok, ref_id=authority if ok else "", message=f"BTCPay status {data.get('status')}")


def card_gateway(frontend_base: str):
    name = _env("BILLING_CARD_GATEWAY", "mock").lower()
    try:
        return {"zarinpal": ZarinpalGateway, "zibal": ZibalGateway, "idpay": IdpayGateway}[name]()
    except KeyError:
        return MockGateway("card-mock", frontend_base)


def crypto_gateway(frontend_base: str):
    try:
        return BtcpayGateway()
    except GatewayError:
        return MockGateway("crypto-mock", frontend_base)


def gateway_by_name(name: str, frontend_base: str):
    if name in ("card-mock", "crypto-mock"):
        return MockGateway(name, frontend_base)
    return {"zarinpal": ZarinpalGateway, "zibal": ZibalGateway, "idpay": IdpayGateway, "btcpay": BtcpayGateway}[name]()


def gateway_status() -> dict[str, Any]:
    card = _env("BILLING_CARD_GATEWAY", "mock").lower()
    crypto = "btcpay" if all(_env(k) for k in ("BTCPAY_SERVER_URL", "BTCPAY_API_KEY", "BTCPAY_STORE_ID")) else "crypto-mock"
    return {"card": card if card in ("zarinpal", "zibal", "idpay") else "card-mock", "crypto": crypto,
            "mock": card not in ("zarinpal", "zibal", "idpay") or crypto == "crypto-mock"}
