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
import logging
import os
import random
import time
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from typing import Any

import httpx

from . import btc, evm, tron

log = logging.getLogger(__name__)

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass(frozen=True)
class Asset:
    id: str
    coin: str          # USDT, USDC, BTC, ETH, TRX, BNB, TON, LTC
    network: str       # human label
    chain: str         # tron | bsc | eth | polygon | btc | btcpay | ton
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
    Asset("btc-onchain", "BTC", "Bitcoin (on-chain)", "btc", "native", 8),
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


EVM_CHAINS = {"eth": 1, "bsc": 56, "polygon": 137}
# Chains read through an Ethereum-style JSON-RPC (eth_getLogs): the EVM chains plus Tron (its /jsonrpc is EVM-compatible).
RPC_CHAINS = {**EVM_CHAINS, "tron": tron.TRON_CHAIN_ID}
# Chains whose payments are detected automatically and watch-only (RPC logs, or the Esplora API for Bitcoin).
WATCHED_CHAINS = {*RPC_CHAINS, "btc"}
# Average seconds per block (used only to estimate a start block when the RPC was unreachable at checkout).
BLOCK_SECONDS = {"eth": 12.0, "bsc": 0.45, "polygon": 2.1, "tron": 3.0, "btc": 600.0}
EXPLORER = {"bsc": "https://bscscan.com", "eth": "https://etherscan.io", "polygon": "https://polygonscan.com",
            "tron": "https://tronscan.org/#", "ton": "https://tonviewer.com", "btc": "https://mempool.space"}
# Public, key-less BSC JSON-RPC endpoints, in preference order (all reachable from Germany, none sanction-blocked).
# They differ in eth_getLogs limits, so the watcher scans in <=1000-block windows, which all of them accept.
DEFAULT_RPC = {
    "bsc": ["https://bsc-rpc.publicnode.com", "https://public-bsc.nownodes.io", "https://rpc-bsc.48.club",
            "https://bsc.rpc.blxrbdn.com", "https://bsc.drpc.org"],
    # Ethereum / Polygon: probed live (key-less, 1000-block eth_getLogs accepted). drpc, llamarpc, 1rpc, ankr and
    # polygon-rpc.com were rejected / rate-limited / key-gated in the probe, so they are not defaults.
    "eth": ["https://ethereum-rpc.publicnode.com", "https://gateway.tenderly.co/public/mainnet",
            "https://rpc.mevblocker.io", "https://rpc.flashbots.net"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://gateway.tenderly.co/public/polygon",
                "https://rpc-mainnet.matic.quiknode.pro"],
    # Tron: the nodes' Ethereum-compatible JSON-RPC (probed live: 1000-block eth_getLogs filtered by recipient works
    # key-less on both). TronGrid is rate-limited without a key (optional TRONGRID_API_KEY raises the limit).
    "tron": ["https://api.trongrid.io/jsonrpc", "https://tron-rpc.publicnode.com/jsonrpc"],
}
# Bitcoin: Esplora REST API base URLs (mempool.space and blockstream.info serve the same API), tried in order.
DEFAULT_BTC_API = ["https://mempool.space/api", "https://blockstream.info/api"]
# Confirmations before a transfer activates a plan (override: CRYPTO_<CHAIN>_CONFIRMATIONS, or CRYPTO_CONFIRMATIONS for all).
# BSC 0.45 s blocks -> 30 = ~14 s; Polygon 2.1 s blocks -> 64 = ~2.2 min (reorgs are a few blocks deep);
# Ethereum 12 s blocks -> 12 = ~2.4 min (the usual exchange-deposit rule).
# Tron 3 s blocks -> 20 = ~1 min (a block is irreversible after ~19); Bitcoin 3 confirmations = ~30 min.
DEFAULT_CONFIRMATIONS = {"bsc": 30, "polygon": 64, "eth": 12, "tron": 20, "btc": 3}
# How far back (blocks) one scan may reach if the watcher was down; older payments need a tx-hash claim / admin confirm.
MAX_LOOKBACK_BLOCKS = {"bsc": 20000, "polygon": 6000, "eth": 1500, "tron": 6000, "btc": 150}   # ~2.5 h / 3.5 h / 5 h / 5 h / 25 h
CHAIN_LABEL = {"bsc": "BNB Smart Chain", "eth": "Ethereum", "polygon": "Polygon", "tron": "Tron", "btc": "Bitcoin"}
EXPLORER_NAME = {"bsc": "BscScan", "eth": "Etherscan", "polygon": "PolygonScan", "tron": "Tronscan", "btc": "mempool.space"}


def _env(k: str, d: str = "") -> str:
    return (os.environ.get(k) or d).strip()


def _csv(k: str) -> list[str]:
    return [x.strip() for x in _env(k).split(",") if x.strip()]


def address_error(a: Asset) -> str:
    """Why the configured receiving address is unusable ('' when fine or not configured)."""
    if a.chain == "tron":
        raw = _env("CRYPTO_TRON_ADDRESS")
        check = tron.normalize_address
    elif a.chain == "btc":
        raw = _env("CRYPTO_BTC_ADDRESS")
        check = btc.normalize_address
    elif a.chain in EVM_CHAINS:
        raw = _env(f"CRYPTO_{a.chain.upper()}_ADDRESS") or _env("CRYPTO_EVM_ADDRESS")
        check = evm.normalize_address
    else:
        return ""
    if not raw:
        return ""
    try:
        check(raw)
        return ""
    except ValueError as exc:
        return str(exc)


def receive_address(a: Asset) -> str:
    if a.chain in ("tron", "btc"):
        raw = _env(f"CRYPTO_{a.chain.upper()}_ADDRESS")
        if not raw:
            return ""
        try:  # checksum-verified: a typo never becomes a payment address
            return (tron if a.chain == "tron" else btc).normalize_address(raw)
        except ValueError as exc:
            log.error("Ignoring invalid %s receiving address: %s", a.chain, exc)
            return ""
    if a.chain in EVM_CHAINS:
        raw = _env(f"CRYPTO_{a.chain.upper()}_ADDRESS") or _env("CRYPTO_EVM_ADDRESS")
        if not raw:
            return ""
        try:
            return evm.normalize_address(raw)  # EIP-55 checked; a typo never becomes a payment address
        except ValueError as exc:
            log.error("Ignoring invalid %s receiving address: %s", a.chain, exc)
            return ""
    if a.chain == "ton":
        return _env("CRYPTO_TON_ADDRESS")
    return ""


def btcpay_configured() -> bool:
    return all(_env(k) for k in ("BTCPAY_SERVER_URL", "BTCPAY_API_KEY", "BTCPAY_STORE_ID"))


def live_allowlist() -> set[str]:
    """Optional CRYPTO_LIVE_ASSETS=usdt-bep20,... restricts which assets are offered as real payments."""
    return {x.lower() for x in _csv("CRYPTO_LIVE_ASSETS")}


def is_live(a: Asset) -> bool:
    allow = live_allowlist()
    if allow and a.id not in allow:
        return False
    if a.chain in RPC_CHAINS and not a.contract:
        # Native ETH/BNB/TRX: the watcher only reads token Transfer logs and there is no key-less price feed we trust
        # for an exact-amount match, so native coins are never live (they stay hidden from users in production).
        return False
    return btcpay_configured() if a.chain == "btcpay" else bool(receive_address(a))


def mock_allowed() -> bool:
    """Test ('simulate payment') invoices are for development only: in production they would grant Pro for free."""
    from app.infrastructure.config import get_settings
    st = get_settings()
    return (not st.is_production) or bool(st.crypto_payment_allow_mock_in_production)


def rpc_urls(chain: str) -> list[str]:
    """CRYPTO_<CHAIN>_RPC_URLS (comma list, tried in order) + legacy CRYPTO_<CHAIN>_RPC + built-in public fallbacks."""
    out: list[str] = []
    for u in [*_csv(f"CRYPTO_{chain.upper()}_RPC_URLS"), _env(f"CRYPTO_{chain.upper()}_RPC"), *DEFAULT_RPC.get(chain, [])]:
        if u and u not in out:
            out.append(u)
    return out


def btc_api_urls() -> list[str]:
    """CRYPTO_BTC_API_URLS (comma list) + CRYPTO_BTC_API (one base URL) + built-in public Esplora endpoints."""
    out: list[str] = []
    for u in [*_csv("CRYPTO_BTC_API_URLS"), _env("CRYPTO_BTC_API"), *DEFAULT_BTC_API]:
        u = u.rstrip("/")
        if u and u not in out:
            out.append(u)
    return out


def is_watched(a: Asset) -> bool:
    """Asset whose payments the watcher detects automatically (ERC20/TRC20 tokens, Bitcoin on-chain)."""
    return (a.chain in RPC_CHAINS and bool(a.contract)) or a.chain == "btc"


def log_contract(chain: str, contract: str) -> str:
    """Token contract as it appears in eth_getLogs results (Tron: 0x + the 20 account bytes)."""
    return tron.hex_contract(contract) if chain == "tron" else contract


def rpc_url(chain: str) -> str:
    urls = rpc_urls(chain)
    return urls[0] if urls else ""


def rpc_headers() -> dict[str, dict[str, str]]:
    """Optional TronGrid API key (raises the rate limit); sent only to trongrid.io, never logged."""
    key = _env("TRONGRID_API_KEY")
    return {"api.trongrid.io": {"TRON-PRO-API-KEY": key}} if key else {}


def confirmations(chain: str = "bsc") -> int:
    """Required confirmations for a chain: CRYPTO_<CHAIN>_CONFIRMATIONS > CRYPTO_CONFIRMATIONS > per-chain default."""
    for key in (f"CRYPTO_{chain.upper()}_CONFIRMATIONS", "CRYPTO_CONFIRMATIONS"):
        raw = _env(key)
        if raw:
            try:
                return max(1, int(raw))
            except ValueError:
                log.warning("Ignoring non-numeric %s", key)
    return DEFAULT_CONFIRMATIONS.get(chain, 30)


def overpay_tolerance_units(decimals: int) -> int:
    """Largest overpay (in USDT) over the tagged amount that is still accepted automatically."""
    return int(Decimal(_env("CRYPTO_OVERPAY_TOLERANCE_USDT", "1")).scaleb(decimals))


def asset_catalog() -> list[dict[str, Any]]:
    out = []
    for a in ASSETS:
        live = is_live(a)
        out.append({"id": a.id, "coin": a.coin, "network": a.network, "standard": a.standard, "stable": a.stable,
                    "optional": a.optional, "live": live, "available": live or mock_allowed(), "contract": a.contract,
                    "decimals": a.decimals, "chain": a.chain, "chain_id": EVM_CHAINS.get(a.chain), "auto_detect": is_watched(a),
                    "address": receive_address(a) if live and a.chain != "btcpay" else "",
                    "explorer": EXPLORER.get(a.chain, ""), "confirmations": confirmations(a.chain) if a.chain in WATCHED_CHAINS else None,
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
    except Exception:  # noqa: BLE001 - blocked / rate-limited: try the second key-less source
        pass
    if coin == "BTC":
        try:
            r = httpx.get(f"{btc_api_urls()[0].removesuffix('/api')}/api/v1/prices", timeout=6)
            r.raise_for_status()
            return float(r.json()["USD"]), "mempool"
        except Exception:  # noqa: BLE001
            pass
    return float(FALLBACK_USD[coin]), "fallback"   # offline: reference price, flagged (never used for live invoices)


def btc_sats(usdt: float, price: float) -> int:
    return int((Decimal(str(usdt)) / Decimal(str(price)) * Decimal(10) ** 8).to_integral_value(rounding=ROUND_UP))


def _quote_btc(a: Asset, usdt: float, taken: set[str]) -> dict[str, Any]:
    """Live Bitcoin quote: price from a real market source (never the offline reference), the rate is locked in the
    invoice; the payable amount is the plan price in sats plus a unique 1-999 sat tag (< ~$1)."""
    price, src = usd_price("BTC")
    if src == "fallback":
        raise RuntimeError("The Bitcoin price feed is unreachable right now; please try again in a minute.")
    base = btc_sats(usdt, price)
    used = set()
    for t in taken:
        try:
            used.add(int(Decimal(t).scaleb(8)))
        except Exception:  # noqa: BLE001
            continue
    tags = [t for t in range(1, 1000) if base + t not in used]
    if not tags:
        raise RuntimeError("Too many open payments right now; try again in a few minutes.")
    sats = base + random.choice(tags)
    fmt = lambda n: format(Decimal(n).scaleb(-8).normalize(), "f")  # noqa: E731
    return {"amount_crypto": fmt(sats), "amount_crypto_base": fmt(base), "rate_usd": price, "rate_source": src}


def quote_crypto(a: Asset, usdt: float, taken: set[str] | None = None, *, live: bool = False) -> dict[str, Any]:
    if live and a.chain == "btc":
        return _quote_btc(a, usdt, taken or set())
    price, src = usd_price(a.coin)
    if a.stable:
        # unique "cents tag" (0.001-0.999) so a payment to a shared address maps to exactly one invoice;
        # `taken` = amounts of other pending invoices on the same asset, never reused.
        taken = taken or set()
        tags = [t for t in range(1, 1000) if format((Decimal(str(usdt)) + Decimal(t) / 1000).quantize(Decimal("0.001")).normalize(), "f") not in taken]
        if not tags:
            raise RuntimeError("Too many open payments right now; try again in a few minutes.")
        amt = (Decimal(str(usdt)) + Decimal(random.choice(tags)) / Decimal(1000)).quantize(Decimal("0.001"))
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
    if a.chain == "btc":
        return f"bitcoin:{address}?amount={format(Decimal(amount), 'f')}"   # BIP-21
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
    """Where to start looking (EVM block number); best effort (the watcher estimates it if this fails)."""
    try:
        if a.chain in RPC_CHAINS:
            return {"from_block": evm.RpcPool(rpc_urls(a.chain), RPC_CHAINS[a.chain], timeout=6, headers=rpc_headers()).block_number() - 5}
        if a.chain == "btc":
            return {"from_block": btc.EsploraPool(btc_api_urls(), timeout=6).block_number() - 2}
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
