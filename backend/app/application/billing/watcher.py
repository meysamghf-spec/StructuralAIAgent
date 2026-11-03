"""Automatic, watch-only detection of payments: USDT/USDC tokens on BNB Smart Chain, Polygon, Ethereum and Tron
(USDT TRC20), and Bitcoin on-chain.

How it works
* Every pending invoice is registered in a small ledger (``billing/evm_ledger.json``).
* A background thread (and, throttled, every invoice poll) scans token ``Transfer`` logs to the receiving
  address from a persisted block cursor, in <=1000-block windows (accepted by every public RPC), with
  automatic failover between endpoints (Tron uses its Ethereum-compatible JSON-RPC). Bitcoin reads the
  address's transactions from an Esplora API (mempool.space / blockstream.info), one output = one transfer.
  No private key, no API key.
* A transfer is only acted on once it has the chain's confirmations (BSC 30 ~14 s, Polygon 64 ~2 min, Ethereum 12 ~2.4 min,
  Tron 20 ~1 min, Bitcoin 3 ~30 min; env CRYPTO_<CHAIN>_CONFIRMATIONS).
* Matching: exact unique amount -> that invoice. Otherwise a single invoice whose price <= amount <= tagged
  amount + tolerance. Underpaid / ambiguous / unmatched / duplicate transfers are never auto-activated; they are
  recorded in the ledger for the admin to review (and confirm manually).
* Every transfer (tx hash + log index) is claimed at most once, so re-scans, duplicate polls and retries are
  idempotent. Invoice activation itself is idempotent per invoice.
"""
from __future__ import annotations

import fcntl
import json
import logging
import re
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import ROUND_UP, Decimal
from typing import Any, Callable, Iterator

from app.application.exceptions import ApplicationError

from . import btc, crypto, evm, store, tron

log = logging.getLogger(__name__)

WINDOW = 1000                 # eth_getLogs window (blocks) - accepted by all public BSC RPCs we tested
GRACE_SECONDS = 24 * 3600     # an invoice keeps being watched this long after creation
MIN_GAP_SECONDS = 4.0         # throttle for on-demand scans triggered by invoice polls
TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
TX_PLAIN_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")   # Tron / Bitcoin transaction ids (0x prefix tolerated)
_THREAD_LOCK = threading.RLock()
_pool_factory: Callable[[str], Any] | None = None
_last_run_mem = 0.0


def set_pool_factory(fn: Callable[[str], Any] | None) -> None:
    """Tests inject a fake RPC pool here."""
    global _pool_factory
    _pool_factory = fn


def get_pool(chain: str) -> Any:
    if _pool_factory:
        return _pool_factory(chain)
    if chain == "btc":
        return btc.EsploraPool(crypto.btc_api_urls(), timeout=10)
    return evm.RpcPool(crypto.rpc_urls(chain), crypto.RPC_CHAINS[chain], timeout=8, headers=crypto.rpc_headers())


# --------------------------------------------------------------------------- ledger
def _ledger_path():
    return store._root() / "evm_ledger.json"


def _empty() -> dict[str, Any]:
    return {"cursor": {}, "claimed": {}, "unmatched": {}, "seen": {}, "underpaid": {},
            "settled_units": {}, "gaps": [], "last_run": 0, "last_error": "", "last_ok": 0}


def _read() -> dict[str, Any]:
    p = _ledger_path()
    if not p.exists():
        return _empty()
    try:
        return {**_empty(), **json.loads(p.read_text("utf-8"))}
    except (OSError, ValueError):
        return _empty()


@contextmanager
def ledger(blocking: bool = True) -> Iterator[dict[str, Any] | None]:
    """Process-wide + cross-process (flock) exclusive access to the ledger; saved on clean exit."""
    with _THREAD_LOCK:
        lockf = open(_ledger_path().with_suffix(".lock"), "a+")
        try:
            try:
                fcntl.flock(lockf, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except OSError:
                yield None
                return
            led = _read()
            yield led
            for k in ("unmatched", "claimed", "settled_units"):
                if len(led[k]) > 1000:
                    led[k] = dict(list(led[k].items())[-1000:])
            led["gaps"] = led["gaps"][-50:]
            p = _ledger_path()
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(led, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(p)
        finally:
            try:
                fcntl.flock(lockf, fcntl.LOCK_UN)
            finally:
                lockf.close()


# --------------------------------------------------------------------------- watch list (own short lock, never held during RPC)
def _watch_path():
    return store._root() / "evm_watch.json"


def watch_read() -> dict[str, str]:
    try:
        return json.loads(_watch_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def watch_update(add: dict[str, str] | None = None, remove: list[str] | None = None) -> None:
    with _THREAD_LOCK:
        lockf = open(_watch_path().with_suffix(".lock"), "a+")
        try:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            w = watch_read()
            w.update(add or {})
            for k in remove or []:
                w.pop(k, None)
            tmp = _watch_path().with_suffix(".tmp")
            tmp.write_text(json.dumps(w), encoding="utf-8")
            tmp.replace(_watch_path())
        finally:
            lockf.close()


# --------------------------------------------------------------------------- helpers
@dataclass
class Transfer:
    key: str
    tx: str
    block: int
    log_index: int
    sender: str
    value: int

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "tx": self.tx, "block": self.block, "from": self.sender, "value": str(self.value)}


def is_token_invoice(inv: dict[str, Any]) -> bool:
    a = crypto.BY_ID.get(inv.get("asset_id", ""))
    return bool(a and crypto.is_watched(a) and not inv.get("mock") and inv.get("pay_address"))


def expected_units(inv: dict[str, Any]) -> int:
    a = crypto.BY_ID[inv["asset_id"]]
    return int(Decimal(inv["amount_crypto"]).scaleb(a.decimals))


def base_units(inv: dict[str, Any]) -> int:
    """Smallest amount that still counts for the invoice: the plan price (stablecoins) or the untagged quote (BTC)."""
    a = crypto.BY_ID[inv["asset_id"]]
    if a.chain == "btc" and inv.get("amount_crypto_base"):
        return int(Decimal(inv["amount_crypto_base"]).scaleb(a.decimals))
    return int(Decimal(str(inv["amount_usdt"])).scaleb(a.decimals))


def tolerance_units(inv: dict[str, Any], default: int) -> int:
    """Largest overpay still accepted automatically: ~1 USD. For BTC that is converted to sats at the invoice's locked rate."""
    a = crypto.BY_ID[inv["asset_id"]]
    if a.chain == "btc" and inv.get("rate_usd"):
        usd = Decimal(crypto._env("CRYPTO_OVERPAY_TOLERANCE_USDT", "1"))
        return int((usd / Decimal(str(inv["rate_usd"])) * Decimal(10) ** a.decimals).to_integral_value(rounding=ROUND_UP))
    return default


def _fmt(units: int, decimals: int) -> str:
    return format((Decimal(units).scaleb(-decimals)).normalize(), "f")


def register(inv: dict[str, Any], account_id: str) -> None:
    if not is_token_invoice(inv):
        return
    watch_update(add={inv["id"]: account_id})


def pending_amounts(asset_id: str, address: str) -> set[str]:
    """Tagged amounts of invoices still being watched on this asset (to keep new tags unique)."""
    out: set[str] = set()
    for inv_id, acc in watch_read().items():
        inv = _invoice(acc, inv_id)
        if inv and inv["status"] == "pending" and inv.get("asset_id") == asset_id and inv.get("pay_address") == address:
            out.add(inv["amount_crypto"])
    return out


def _invoice(account_id: str, invoice_id: str) -> dict[str, Any] | None:
    return next((i for i in store.load(account_id).get("invoices", []) if i["id"] == invoice_id), None)


def norm_tx(chain: str, tx: str) -> str:
    """Canonical transaction id: EVM 0x-prefixed lowercase; Tron / Bitcoin 64 lowercase hex without prefix."""
    t = (tx or "").strip().lower()
    return t.removeprefix("0x") if chain in ("tron", "btc") else t


def parse_logs(logs: list[dict[str, Any]], contract: str, to_addr: str, chain: str = "") -> list[Transfer]:
    """Transfer events to ``to_addr`` from a token contract (``contract`` in log form: Tron = 0x + 20 bytes)."""
    out: list[Transfer] = []
    is_tron = chain == "tron"
    want_to = tron.topic_for_address(to_addr) if is_tron else evm.topic_for_address(to_addr)
    for lg in logs:
        topics = [t.lower() for t in lg.get("topics", [])]
        if (lg.get("removed") or len(topics) != 3 or topics[0] != crypto.TRANSFER_TOPIC or topics[2] != want_to
                or (lg.get("address") or "").lower() != contract.lower()):
            continue
        try:
            if int(lg["data"], 16) == 0:   # zero-value "address poisoning" transfers are noise, never a payment
                continue
            idx = int(lg.get("logIndex", "0x0"), 16)
            txh = norm_tx(chain, lg["transactionHash"])
            out.append(Transfer(key=f"{txh}:{idx}", tx=txh, block=int(lg["blockNumber"], 16), log_index=idx,
                                sender=(tron if is_tron else evm).address_from_topic(topics[1]), value=int(lg["data"], 16)))
        except (KeyError, ValueError):
            continue
    out.sort(key=lambda t: (t.block, t.log_index))
    return out


def parse_btc_txs(txs: list[dict[str, Any]], address: str, tip: int, since_height: int = 0) -> list[Transfer]:
    """One Transfer per output paying ``address``. Unconfirmed transactions get block = tip + 1 (0 confirmations)."""
    out: list[Transfer] = []
    for t in txs:
        st = t.get("status", {})
        height = int(st["block_height"]) if st.get("confirmed") else tip + 1
        if st.get("confirmed") and height < since_height:
            continue
        txid = (t.get("txid") or "").lower()
        if not TX_PLAIN_RE.match(txid):
            continue
        vin = (t.get("vin") or [{}])[0]
        sender = ((vin.get("prevout") or {}).get("scriptpubkey_address")) or ""
        for n, vo in enumerate(t.get("vout", [])):
            if vo.get("scriptpubkey_address") != address or int(vo.get("value", 0)) <= 0:
                continue
            out.append(Transfer(key=f"{txid}:{n}", tx=txid, block=height, log_index=n, sender=sender, value=int(vo["value"])))
    out.sort(key=lambda t: (t.block, t.log_index))
    return out


def unit_key(scope: str, value: int) -> str:
    """Duplicate-detection key; scoped by chain+token so the same raw amount on another chain/token never collides."""
    return f"{scope}:{value}"


def classify(t: Transfer, invs: list[dict[str, Any]], tol: int, settled_units: dict[str, str] | None = None,
             to_addr: str = "", scope: str = "") -> tuple[str, dict[str, Any] | None, str]:
    """Pure matching rule. Returns (decision, invoice|None, reason); decision is 'match' or 'review'."""
    if to_addr and t.sender.lower() == to_addr.lower():
        return "review", None, "self_transfer"
    eligible = [i for i in invs if t.block >= int(i.get("from_block") or 0)]
    exact = [i for i in eligible if expected_units(i) == t.value]
    if len(exact) == 1:
        return "match", exact[0], "exact"
    if len(exact) > 1:
        return "review", None, "ambiguous"
    ranged = [i for i in eligible if base_units(i) <= t.value <= expected_units(i) + tolerance_units(i, tol)]
    if len(ranged) == 1:
        return "match", ranged[0], "overpaid" if t.value > expected_units(ranged[0]) else "amount_below_tag"
    if len(ranged) > 1:
        return "review", None, "ambiguous"
    if not eligible:
        return "review", None, "duplicate" if unit_key(scope, t.value) in (settled_units or {}) else "no_pending_invoice"
    if t.value < min(base_units(i) for i in eligible):
        return "review", None, "underpaid"
    return "review", None, "overpaid_unmatched"


def _service():
    from . import service  # lazy: service imports this module
    return service


# --------------------------------------------------------------------------- scanning
def _scan_group(led: dict[str, Any], chain: str, contract: str, address: str, invs: list[dict[str, Any]],
                now: float) -> dict[str, int]:
    pool = get_pool(chain)
    conf = crypto.confirmations(chain)
    a_dec = crypto.BY_ID[invs[0]["asset_id"]].decimals
    tol = crypto.overpay_tolerance_units(a_dec)
    head = pool.block_number()
    key = f"{chain}:{contract.lower()}:{address.lower()}"

    def est_from(i: dict[str, Any]) -> int:
        if i.get("from_block"):
            return int(i["from_block"])
        return head - int((now - i["created_ts"]) / crypto.BLOCK_SECONDS.get(chain, 3.0)) - 200

    cursor = led["cursor"].get(key)
    start = (cursor + 1) if cursor is not None else min(est_from(i) for i in invs)
    max_back = crypto.MAX_LOOKBACK_BLOCKS.get(chain, 5000)
    if start < head - max_back:
        led["gaps"].append({"chain": chain, "from": start, "to": head - max_back, "at": now})
        start = head - max_back
    if chain == "btc":
        transfers = [t for t in parse_btc_txs(pool.address_txs(address, start), address, head, start)]
    else:
        logs: list[dict[str, Any]] = []
        logc = crypto.log_contract(chain, contract)
        topic_to = tron.topic_for_address(address) if chain == "tron" else evm.topic_for_address(address)
        s = start
        while s <= head:
            e = min(s + WINDOW - 1, head)
            logs += pool.get_logs({"fromBlock": hex(s), "toBlock": hex(e), "address": logc,
                                   "topics": [crypto.TRANSFER_TOPIC, None, topic_to]})
            s = e + 1
        transfers = parse_logs(logs, logc, address, chain)
    svc = _service()
    stats = {"scanned": len(transfers), "matched": 0, "review": 0, "confirming": 0}
    for i in invs:
        led["seen"].pop(i["id"], None)
    live = {i["id"]: i for i in invs}
    for t in transfers:
        if t.key in led["claimed"] or t.key in led["unmatched"]:
            continue
        confs = head - t.block + 1
        open_invs = [i for i in live.values() if i["status"] == "pending"]
        if confs < conf:
            _, inv, why = classify(t, open_invs, tol, led["settled_units"], address, scope=f"{chain}:{contract.lower()}")
            if inv:
                led["seen"][inv["id"]] = {"tx": t.tx, "block": t.block, "confirmations": confs, "required": conf}
            stats["confirming"] += 1
            continue
        decision, inv, reason = classify(t, open_invs, tol, led["settled_units"], address, scope=f"{chain}:{contract.lower()}")
        if decision == "match" and inv:
            late = False
            if now > _expires_ts(inv):
                try:
                    late = pool.block_timestamp(t.block) > _expires_ts(inv)
                except Exception:  # noqa: BLE001
                    late = True
            settled, applied = svc.settle_paid(inv["account_id"], inv["id"], tx=t.tx, via="auto", received=_fmt(t.value, a_dec),
                                               confirmations=confs, note=reason, late=late, sender=t.sender)
            if applied:
                led["claimed"][t.key] = {"invoice_id": inv["id"], "tx": t.tx, "value": str(t.value), "at": now, "via": "auto"}
                led["settled_units"][unit_key(f"{chain}:{contract.lower()}", t.value)] = inv["id"]
                live.pop(inv["id"], None)
                watch_update(remove=[inv["id"]])
                stats["matched"] += 1
                continue
            decision, reason = "review", "invoice_already_settled"
        rec = {**t.as_dict(), "reason": reason, "at": now, "token": invs[0]["coin"],
               "amount": _fmt(t.value, a_dec), "confirmations": confs}
        led["unmatched"][t.key] = rec
        if reason == "underpaid":
            pend = [i for i in open_invs if t.block >= int(i.get("from_block") or 0)]
            if len(pend) == 1:
                led["underpaid"][pend[0]["id"]] = {"tx": t.tx, "received": _fmt(t.value, a_dec),
                                                   "missing": _fmt(base_units(pend[0]) - t.value, a_dec)}
        log.warning("%s transfer needs review: %s reason=%s amount=%s", chain, t.tx, reason, rec["amount"])
        stats["review"] += 1
    led["cursor"][key] = max(cursor or 0, head - conf)
    return stats


def _expires_ts(inv: dict[str, Any]) -> float:
    return inv["created_ts"] + crypto.EXPIRY_MIN * 60


def run_once(*, force: bool = False, blocking: bool = False, now: float | None = None) -> dict[str, Any]:
    """One reconcile pass over every watched token invoice. Safe to call from anywhere, any number of times."""
    global _last_run_mem
    t_now = now if now is not None else time.time()
    if not force and t_now - _last_run_mem < MIN_GAP_SECONDS:
        return {"skipped": "throttled"}
    with ledger(blocking=blocking) as led:
        if led is None:
            return {"skipped": "busy"}
        if not force and t_now - led["last_run"] < MIN_GAP_SECONDS:
            return {"skipped": "throttled"}
        _last_run_mem = t_now
        led["last_run"] = t_now
        svc = _service()
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for inv_id, acc in list(watch_read().items()):
            inv = _invoice(acc, inv_id)
            if not inv or inv["status"] != "pending":
                watch_update(remove=[inv_id])
                continue
            if t_now > inv["created_ts"] + GRACE_SECONDS:
                svc.settle_expired(acc, inv_id)
                watch_update(remove=[inv_id])
                continue
            a = crypto.BY_ID[inv["asset_id"]]
            groups[(a.chain, a.contract, inv["pay_address"])].append({**inv, "account_id": acc})
        summary: dict[str, Any] = {"groups": len(groups), "errors": []}
        for (chain, contract, address), invs in groups.items():
            try:
                summary[f"{chain}"] = _scan_group(led, chain, contract, address, invs, t_now)
                led["last_ok"] = t_now
                led["last_error"] = ""
            except Exception as exc:  # noqa: BLE001 - RPC outage: try again next tick, cursor not advanced
                led["last_error"] = str(exc)[:300]
                summary["errors"].append(str(exc)[:200])
                log.warning("Payment scan failed (%s): %s", chain, exc)
        return summary


# --------------------------------------------------------------------------- user / admin claims
def _receipt_transfers(tx: str, contract: str, address: str, chain: str) -> tuple[list[Transfer], int]:
    pool = get_pool(chain)
    label = crypto.CHAIN_LABEL.get(chain, chain)
    if chain == "btc":
        if not TX_PLAIN_RE.match(tx or ""):
            raise ApplicationError("BAD_TX", "That does not look like a Bitcoin transaction id (64 hex characters).", status_code=422)
        raw = pool.tx(norm_tx(chain, tx))
        if not raw:
            raise ApplicationError("TX_NOT_FOUND", "This transaction was not found on Bitcoin yet. Check the transaction id, wait a minute and try again.", status_code=404)
        head = pool.block_number()
        ts = parse_btc_txs([raw], address, head)
        if not ts:
            raise ApplicationError("NO_TRANSFER", "This transaction does not pay our Bitcoin address.", status_code=409)
        return ts, head
    if chain == "tron":
        if not TX_PLAIN_RE.match(tx or ""):
            raise ApplicationError("BAD_TX", "That does not look like a Tron transaction id (64 hex characters).", status_code=422)
        txq = "0x" + norm_tx(chain, tx)
    else:
        if not TX_RE.match(tx or ""):
            raise ApplicationError("BAD_TX", "That does not look like a transaction hash (0x + 64 hex characters).", status_code=422)
        txq = tx.lower()
    rc = pool.receipt(txq)
    if not rc:
        raise ApplicationError("TX_NOT_FOUND", f"This transaction was not found on {crypto.CHAIN_LABEL.get(chain, chain)} yet. Check that you sent on that network, wait a minute and try again.", status_code=404)
    if rc.get("status") != "0x1":
        raise ApplicationError("TX_FAILED", "That transaction failed on-chain, so nothing was paid.", status_code=409)
    ts = parse_logs(rc.get("logs", []), crypto.log_contract(chain, contract), address, chain)
    if not ts:
        raise ApplicationError("NO_TRANSFER", f"This transaction contains no transfer of this token to our address on {crypto.CHAIN_LABEL.get(chain, chain)}.", status_code=409)
    return ts, pool.block_number()


def claim_tx(account_id: str, invoice_id: str, tx: str, *, admin: str = "", note: str = "") -> dict[str, Any]:
    """Settle an invoice from a transaction hash after verifying it on-chain.

    User flow (admin == ''): the transfer must classify as a match for THIS invoice by the normal rules.
    Admin flow: any transfer to our address worth at least the plan price is accepted; amount mismatch is the
    admin's call. Idempotent; a transfer can settle only one invoice.
    """
    svc = _service()
    inv = _invoice(account_id, invoice_id)
    if not inv:
        raise ApplicationError("INVOICE_NOT_FOUND", "Invoice not found", status_code=404)
    if not is_token_invoice(inv):
        raise ApplicationError("NOT_TOKEN_INVOICE", "Transaction claims only apply to on-chain token invoices.", status_code=409)
    a = crypto.BY_ID[inv["asset_id"]]
    ts, head = _receipt_transfers(tx, a.contract, inv["pay_address"], a.chain)
    tx = norm_tx(a.chain, tx)
    conf = crypto.confirmations(a.chain)
    tol = crypto.overpay_tolerance_units(a.decimals)
    now = time.time()
    with ledger() as led:
        if inv["status"] == "paid":
            if inv.get("tx", "").lower() == tx.lower():
                return svc.public_invoice(inv)  # idempotent repeat
            raise ApplicationError("ALREADY_PAID", "This invoice is already paid.", status_code=409)
        if inv["status"] != "pending" and not admin:
            raise ApplicationError("INVOICE_CLOSED", "This payment window is closed; contact support with your transaction hash.", status_code=409)
        used = [t for t in ts if t.key in led["claimed"]]
        if used and all(t.key in led["claimed"] for t in ts):
            raise ApplicationError("TX_ALREADY_USED", "This transaction has already been applied to a payment.", status_code=409)
        free = [t for t in ts if t.key not in led["claimed"]]
        others = []
        for iid, acc in watch_read().items():
            oi = _invoice(acc, iid)
            if oi and oi["status"] == "pending" and oi.get("asset_id") == inv["asset_id"] and oi.get("pay_address") == inv["pay_address"]:
                others.append(oi)
        if inv["id"] not in {o["id"] for o in others}:
            others.append(inv)
        chosen: Transfer | None = None
        reason = ""
        for t in free:
            if admin:
                if t.value >= base_units(inv) and t.block >= int(inv.get("from_block") or 0) - 50:
                    chosen, reason = t, "admin_tx"
                    break
                continue
            decision, mi, why = classify(t, others, tol, led["settled_units"], inv["pay_address"], scope=f"{a.chain}:{a.contract.lower()}")
            if decision == "match" and mi and mi["id"] == inv["id"]:
                chosen, reason = t, why
                break
            reason = why
        if not chosen:
            raise ApplicationError("AMOUNT_MISMATCH", _mismatch_text(reason), status_code=409, details={"reason": reason})
        confs = head - chosen.block + 1
        if confs < conf:
            led["seen"][inv["id"]] = {"tx": chosen.tx, "block": chosen.block, "confirmations": confs, "required": conf}
            return {**svc.public_invoice(inv), "detected": led["seen"][inv["id"]]}
        late = False
        if now > _expires_ts(inv):
            try:
                late = get_pool(a.chain).block_timestamp(chosen.block) > _expires_ts(inv)
            except Exception:  # noqa: BLE001
                late = True
        done, applied = svc.settle_paid(account_id, inv["id"], tx=chosen.tx, via="admin" if admin else "claim",
                                        received=_fmt(chosen.value, a.decimals), confirmations=confs, note=note or reason,
                                        late=late, sender=chosen.sender, admin=admin, allow_expired=bool(admin))
        if applied:
            led["claimed"][chosen.key] = {"invoice_id": inv["id"], "tx": chosen.tx, "value": str(chosen.value), "at": now,
                                         "via": "admin" if admin else "claim"}
            led["settled_units"][unit_key(f"{a.chain}:{a.contract.lower()}", chosen.value)] = inv["id"]
            watch_update(remove=[inv["id"]])
            led["unmatched"].pop(chosen.key, None)
        return svc.public_invoice(done)


def _mismatch_text(reason: str) -> str:
    return {
        "underpaid": "The amount sent is lower than the invoice amount. Send the missing difference, or contact support with the hash.",
        "overpaid_unmatched": "The amount sent is much higher than the invoice amount; support will review it. Contact support with the hash.",
        "ambiguous": "This transfer matches more than one open payment; support will review it.",
        "duplicate": "A payment with this amount was already applied.",
        "no_pending_invoice": "This transfer does not match this invoice (wrong amount, or it was sent before the invoice was created).",
        "self_transfer": "This is a transfer from our own address.",
    }.get(reason, "This transfer does not match this invoice's amount. Contact support with the hash.")


def seen(invoice_id: str) -> dict[str, Any]:
    led = _read()
    out: dict[str, Any] = {}
    if invoice_id in led["seen"]:
        out["detected"] = led["seen"][invoice_id]
    if invoice_id in led["underpaid"]:
        out["underpaid"] = led["underpaid"][invoice_id]
    return out


def admin_overview() -> dict[str, Any]:
    led = _read()
    pend = []
    for inv_id, acc in watch_read().items():
        inv = _invoice(acc, inv_id)
        if inv and inv["status"] == "pending":
            pend.append({"invoice_id": inv_id, "number": inv["number"], "account_id": acc, "plan": inv["plan_id"],
                         "expected": inv["amount_crypto"], "created_at": inv["created_at"], "expires_at": inv["expires_at"]})
    return {"watching": pend, "needs_review": list(led["unmatched"].values())[-100:],
            "settled": len(led["claimed"]), "gaps": led["gaps"][-10:], "cursor": led["cursor"],
            "last_ok": led["last_ok"], "last_error": led["last_error"], "last_run": led["last_run"]}


# --------------------------------------------------------------------------- background thread
class Watcher:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, name="payment-watcher", daemon=True)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                if watch_read():
                    run_once(force=True)
            except Exception:  # noqa: BLE001
                log.exception("payment watcher tick failed")

    def start(self) -> None:
        self._t.start()

    def stop(self) -> None:
        self._stop.set()


def start_background() -> Watcher | None:
    import os
    if (os.environ.get("CRYPTO_WATCHER") or "1").strip() == "0":
        return None
    if not any(crypto.is_live(a) for a in crypto.ASSETS if crypto.is_watched(a)):
        return None
    try:
        interval = max(5.0, float(os.environ.get("CRYPTO_WATCH_SECONDS") or 20))
    except ValueError:
        interval = 20.0
    w = Watcher(interval)
    w.start()
    log.info("Payment watcher started (every %ss)", interval)
    return w
