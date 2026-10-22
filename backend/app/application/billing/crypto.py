"""Crypto-only payments: coin + network catalog, per-invoice quotes, and watch-only payment detection.

Design (works for Iran under sanctions, no custodial processor, no KYC):
* Stablecoins and native coins on Tron / BSC / Ethereum / Polygon / TON are paid to the owner's OWN
  receiving address (env, watch-only - no private key on the server). Each invoice gets a unique amount
  (a small "cents tag") so a transfer can be matched to its invoice, and we watch the chain through
  public endpoints (TronGrid, any EVM JSON-RPC, toncenter).
* BTC (on-chain + Lightning) and LTC go through a self-hosted BTCPay Server (Greenfield API).
* When an asset's address / BTCPay is not configured the invoice is a MOCK: a test address is shown and
  the "Simulate payment" button confirms it. Mock invoices never touch a chain.
"""
from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from typing import Any

import httpx

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass(frozen=True)
class Asset:
    id: str
    coin: str          # USDT, USDC, BTC, ETH, TRX, BNB, TON, LTC
    network: str       # human label
    chain: str         # tron | bsc | eth | polygon | btcpay | ton
    standard: str      # TRC20, BEP20, ERC20, Polygon, native, Lightning
    decimals: int
    contract: str = ""  # token contract; "" = native coin
    stable: bool = False
    optional: bool = False


ASSETS: list[Asset] = [
    Asset("usdt-trc20", "USDT", "Tron (TRC20)", "tron", "TRC20", 6, "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", True),
    Asset("usdt-bep20", "USDT", "BNB Smart Chain (BEP20)", "bsc", "BEP20", 18, "0x55d398326f99059fF775485246999027B3197955", True),
    Asset("usdt-erc20", "USDT", "Ethereum (ERC20)", "eth", "ERC20", 6, "0xdAC17F958D2ee523a2206206994597C13D831ec7", True),
    Asset("usdt-polygon", "USDT", "Polygon (PoS)", "polygon", "Polygon", 6, "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", True),
    Asset("usdc-erc20", "USDC", "Ethereum (ERC20)", "eth", "ERC20", 6, "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", True),
    Asset("usdc-bep20", "USDC", "BNB Smart Chain (BEP20)", "bsc", "BEP20", 18, "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", True),
    Asset("usdc-polygon", "USDC", "Polygon (PoS)", "polygon", "Polygon", 6, "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", True),
    Asset("btc-onchain", "BTC", "Bitcoin (on-chain)", "btcpay", "native", 8),
    Asset("btc-lightning", "BTC", "Bitcoin Lightning", "btcpay", "Lightning", 8),
    Asset("eth", "ETH", "Ethereum", "eth", "native", 18),
    Asset("trx", "TRX", "Tron", "tron", "native", 6),
    Asset("bnb", "BNB", "BNB Smart Chain (BEP20)", "bsc", "native", 18),
    Asset("ton", "TON", "TON", "ton", "native", 9, optional=True),
    Asset("ltc", "LTC", "Litecoin", "btcpay", "native", 8, optional=True),
]
BY_ID = {a.id: a for a in ASSETS}
COINGECKO = {"BTC": "bitcoin", "ETH": "ethereum", "TRX": "tron", "BNB": "binancecoin", "TON": "the-open-network", "LTC": "litecoin"}
# Fallback reference prices (USD) used only in mock mode / when the price feed is unreachable.
FALLBACK_USD = {"BTC": 65000, "ETH": 3000, "TRX": 0.12, "BNB": 550, "TON": 5, "LTC": 70}
EXPIRY_MIN = int(os.environ.get("CRYPTO_INVOICE_MINUTES", "30"))


def _env(k: str, d: str = "") -> str:
    return (os.environ.get(k) or d).strip()


def receive_address(a: Asset) -> str:
    if a.chain == "tron":
        return _env("CRYPTO_TRON_ADDRESS")
    if a.chain in ("bsc", "eth", "polygon"):
        return _env(f"CRYPTO_{a.chain.upper()}_ADDRESS") or _env("CRYPTO_EVM_ADDRESS")
    if a.chain == "ton":
        return _env("CRYPTO_TON_ADDRESS")
    return ""


def btcpay_configured() -> bool:
    return all(_env(k) for k in ("BTCPAY_SERVER_URL", "BTCPAY_API_KEY", "BTCPAY_STORE_ID"))


def is_live(a: Asset) -> bool:
    return btcpay_configured() if a.chain == "btcpay" else bool(receive_address(a))


def rpc_url(chain: str) -> str:
    return _env(f"CRYPTO_{chain.upper()}_RPC", {"eth": "https://ethereum-rpc.publicnode.com",
                                              "bsc": "https://bsc-rpc.publicnode.com",
                                              "polygon": "https://polygon-bor-rpc.publicnode.com"}.get(chain, ""))


def asset_catalog() -> list[dict[str, Any]]:
    out = []
    for a in ASSETS:
        out.append({"id": a.id, "coin": a.coin, "network": a.network, "standard": a.standard, "stable": a.stable,
                    "optional": a.optional, "live": is_live(a), "contract": a.contract,
                    "processor": "BTCPay Server (self-hosted)" if a.chain == "btcpay" else "Direct to wallet (watch-only)"})
    return out


def usd_price(coin: str) -> tuple[float, str]:
    if coin in ("USDT", "USDC"):
        return 1.0, "peg"
    fixed = json.loads(_env("CRYPTO_RATES_JSON", "{}") or "{}")
    if coin in fixed:
        return float(fixed[coin]), "config"
    try:
        r = httpx.get("https://api.coingecko.com/api/v3/simple/price",
                      params={"ids": COINGECKO[coin], "vs_currencies": "usd"}, timeout=6)
        r.raise_for_status()
        return float(r.json()[COINGECKO[coin]]["usd"]), "coingecko"
    except Exception:  # noqa: BLE001 - offline / blocked: reference price, flagged
        return float(FALLBACK_USD[coin]), "fallback"


def quote_crypto(a: Asset, usdt: float) -> dict[str, Any]:
    price, src = usd_price(a.coin)
    if a.stable:
        # unique "cents tag" (0.001-0.999) so a payment to a shared address maps to exactly one invoice
        amt = Decimal(str(usdt)) + Decimal(random.randint(1, 999)) / Decimal(1000)
        amt = amt.quantize(Decimal("0.001"))
    else:
        places = Decimal(1).scaleb(-min(a.decimals, 8))
        amt = (Decimal(str(usdt)) / Decimal(str(price))).quantize(places, rounding=ROUND_UP)
        # tag the last digits too so concurrent invoices differ
        amt += Decimal(random.randint(1, 99)) * places
    return {"amount_crypto": format(amt.normalize(), "f"), "rate_usd": price, "rate_source": src}


def payment_uri(a: Asset, address: str, amount: str) -> str:
    if a.chain == "tron":
        return address
    if a.chain in ("eth", "bsc", "polygon"):
        cid = {"eth": 1, "bsc": 56, "polygon": 137}[a.chain]
        if a.contract:
            units = int(Decimal(amount).scaleb(a.decimals))
            return f"ethereum:{a.contract}@{cid}/transfer?address={address}&uint256={units}"
        return f"ethereum:{address}@{cid}?value={int(Decimal(amount).scaleb(18))}"
    if a.chain == "ton":
        return f"ton://transfer/{address}?amount={int(Decimal(amount).scaleb(9))}"
    return address


def qr_svg(data: str) -> str:
    try:
        import segno
        return segno.make(data, error="m").svg_inline(scale=4, border=2)
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------- watchers
def _units(amount: str, decimals: int) -> int:
    return int(Decimal(amount).scaleb(decimals))


def start_marker(a: Asset) -> dict[str, Any]:
    """Where to start looking (EVM block number); best effort."""
    if a.chain in ("eth", "bsc", "polygon"):
        try:
            r = httpx.post(rpc_url(a.chain), json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber"}, timeout=8)
            return {"from_block": int(r.json()["result"], 16) - 5}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def find_payment(inv: dict[str, Any]) -> dict[str, Any] | None:
    """Return {"tx": hash} when a matching transfer (>= exact tagged amount) reached the address."""
    a = BY_ID[inv["asset_id"]]
    addr, want = inv["pay_address"], _units(inv["amount_crypto"], a.decimals)
    since_ms = int(inv["created_ts"] * 1000) - 60_000
    if a.chain == "tron":
        h = {"TRON-PRO-API-KEY": _env("TRONGRID_API_KEY")} if _env("TRONGRID_API_KEY") else {}
        base = _env("CRYPTO_TRON_API", "https://api.trongrid.io")
        if a.contract:
            r = httpx.get(f"{base}/v1/accounts/{addr}/transactions/trc20", headers=h, timeout=10,
                          params={"only_to": "true", "contract_address": a.contract, "min_timestamp": since_ms, "limit": 50})
            for t in r.json().get("data", []):
                if t.get("to") == addr and int(t.get("value", 0)) == want:
                    return {"tx": t["transaction_id"]}
        else:
            r = httpx.get(f"{base}/v1/accounts/{addr}/transactions", headers=h, timeout=10,
                          params={"only_to": "true", "min_timestamp": since_ms, "limit": 50})
            for t in r.json().get("data", []):
                v = t.get("raw_data", {}).get("contract", [{}])[0].get("parameter", {}).get("value", {})
                if v.get("amount") == want:
                    return {"tx": t["txID"]}
        return None
    if a.chain in ("eth", "bsc", "polygon"):
        url = rpc_url(a.chain)

        def call(method, params):
            return httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=15).json()["result"]
        head = int(call("eth_blockNumber", []), 16)
        frm = int(inv.get("from_block") or head - 300)
        frm = max(frm, head - 2000)
        if a.contract:
            topic_to = "0x" + addr.lower().replace("0x", "").rjust(64, "0")
            logs = call("eth_getLogs", [{"fromBlock": hex(frm), "toBlock": hex(head), "address": a.contract,
                                         "topics": [TRANSFER_TOPIC, None, topic_to]}])
            for lg in logs:
                if int(lg["data"], 16) == want:
                    return {"tx": lg["transactionHash"]}
            return None
        for n in range(max(frm, head - 150), head + 1):  # native coin: scan recent blocks (bounded)
            blk = call("eth_getBlockByNumber", [hex(n), True]) or {}
            for tx in blk.get("transactions", []):
                if (tx.get("to") or "").lower() == addr.lower() and int(tx["value"], 16) == want:
                    return {"tx": tx["hash"]}
        return None
    if a.chain == "ton":
        r = httpx.get(_env("CRYPTO_TON_API", "https://toncenter.com/api/v2") + "/getTransactions",
                      params={"address": addr, "limit": 50}, timeout=10)
        for t in r.json().get("result", []):
            m = t.get("in_msg", {})
            if int(m.get("value", 0)) == want and t.get("utime", 0) * 1000 >= since_ms:
                return {"tx": t.get("transaction_id", {}).get("hash", "")}
        return None
    return None


# ---------------------------------------------------------------- BTCPay (BTC on-chain/Lightning, LTC)
def _btcpay():
    return httpx.Client(base_url=f"{_env('BTCPAY_SERVER_URL').rstrip('/')}/api/v1", timeout=20,
                        headers={"Authorization": f"token {_env('BTCPAY_API_KEY')}"})


def btcpay_create(inv_id: str, usdt: float, a: Asset, description: str, redirect: str) -> dict[str, str]:
    method = {"btc-onchain": "BTC-CHAIN", "btc-lightning": "BTC-LN", "ltc": "LTC-CHAIN"}[a.id]
    with _btcpay() as c:
        r = c.post(f"/stores/{_env('BTCPAY_STORE_ID')}/invoices", json={
            "amount": str(usdt), "currency": "USD", "metadata": {"orderId": inv_id, "itemDesc": description},
            "checkout": {"paymentMethods": [method], "defaultPaymentMethod": method, "redirectURL": redirect,
                         "expirationMinutes": EXPIRY_MIN}})
        r.raise_for_status()
        d = r.json()
    return {"btcpay_id": d["id"], "checkout_url": d["checkoutLink"]}


def btcpay_status(btcpay_id: str) -> str:
    with _btcpay() as c:
        r = c.get(f"/stores/{_env('BTCPAY_STORE_ID')}/invoices/{btcpay_id}")
        r.raise_for_status()
        return r.json().get("status", "")


def now_ts() -> float:
    return time.time()
