"""USDT / BNB Smart Chain (BEP20) payments: address validation, unique amounts, mocked-RPC detection,
confirmations, idempotency, underpay / overpay / late / duplicate / expiry, tx claims and admin confirmation."""
from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.application.billing import crypto, evm, plans, service, store, watcher
from app.application.exceptions import ApplicationError

ADDR = "0x17F5FC2fC7ca5066bBF96d0E1687122553410022"
USDT = "0x55d398326f99059fF775485246999027B3197955"
SENDER = "0x1111111111111111111111111111111111111111"
CONF = 30


def units(x) -> int:
    return int(Decimal(str(x)).scaleb(18))


class FakeChain:
    """In-memory BSC: serves eth_blockNumber / eth_getLogs / receipts like evm.RpcPool."""

    def __init__(self, head: int = 1_000_000) -> None:
        self.head = head
        self.logs: list[dict] = []
        self.receipts: dict[str, dict] = {}
        self.log_calls: list[tuple[int, int]] = []
        self.down = False
        self.ts: int | None = None
        self._n = 0

    def send(self, value, *, block: int | None = None, to: str = ADDR, sender: str = SENDER, removed: bool = False,
             contract: str = USDT, status: str = "0x1") -> str:
        self._n += 1
        tx = "0x" + f"{self._n:064x}"
        lg = {"address": contract.lower(), "removed": removed, "transactionHash": tx, "logIndex": "0x0",
              "blockNumber": hex(block if block is not None else self.head),
              "topics": [crypto.TRANSFER_TOPIC, evm.topic_for_address(sender), evm.topic_for_address(to)],
              "data": hex(value)}
        self.logs.append(lg)
        self.receipts[tx] = {"status": status, "logs": [lg], "blockNumber": lg["blockNumber"]}
        return tx

    def mine(self, n: int) -> None:
        self.head += n

    # --- RpcPool interface
    def block_number(self) -> int:
        if self.down:
            raise evm.RpcError("down")
        return self.head

    def get_logs(self, flt: dict) -> list[dict]:
        if self.down:
            raise evm.RpcError("down")
        lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
        self.log_calls.append((lo, hi))
        assert hi - lo + 1 <= 1000, "window too large for public RPCs"
        t_to = flt["topics"][2]
        return [lg for lg in self.logs if lo <= int(lg["blockNumber"], 16) <= hi and lg["address"] == flt["address"].lower()
                and lg["topics"][2] == t_to]

    def receipt(self, tx: str):
        return self.receipts.get(tx.lower())

    def block_timestamp(self, number: int) -> int:
        return self.ts if self.ts is not None else int(time.time())


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_root", lambda: (tmp_path / "accounts").mkdir(exist_ok=True) or tmp_path)
    monkeypatch.setattr(watcher, "_last_run_mem", 0.0)
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    monkeypatch.setenv("CRYPTO_BSC_ADDRESS", ADDR)
    monkeypatch.setenv("CRYPTO_LIVE_ASSETS", "usdt-bep20")
    monkeypatch.setenv("CRYPTO_CONFIRMATIONS", str(CONF))
    for k in ("CRYPTO_EVM_ADDRESS", "CRYPTO_TRON_ADDRESS", "CRYPTO_TON_ADDRESS", "BTCPAY_SERVER_URL", "BILLING_COMPLIMENTARY_ACCOUNTS"):
        monkeypatch.delenv(k, raising=False)
    fc = FakeChain()
    monkeypatch.setattr(crypto, "start_marker", lambda a: {"from_block": fc.head - 5})
    watcher.set_pool_factory(lambda c: fc)
    yield fc
    watcher.set_pool_factory(None)


def buy(acc="u1", plan="pro", dur="1m"):
    return service.create_checkout(acc, plan, dur, "usdt-bep20")["invoice"]


def scan(now=None):
    return watcher.run_once(force=True, now=now)


def paid(acc, inv_id):
    return next(i for i in store.load(acc)["invoices"] if i["id"] == inv_id)


# ------------------------------------------------------------------ address / config
def test_keccak_and_eip55():
    assert evm.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert evm.keccak256(b"abc").hex() == "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
    assert evm.normalize_address(ADDR) == ADDR
    assert evm.normalize_address(ADDR.lower()) == ADDR
    assert evm.to_checksum(USDT.lower()) == USDT
    for a in ("0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed", "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359"):
        assert evm.normalize_address(a) == a


@pytest.mark.parametrize("bad", ["", "17F5FC2fC7ca5066bBF96d0E1687122553410022", "0x123", "0x" + "g" * 40,
                                 "0x17F5FC2fC7ca5066bBF96d0E1687122553410023".replace("c", "C", 1),  # wrong checksum
                                 "0x" + "0" * 40])
def test_invalid_addresses_rejected(bad):
    with pytest.raises(ValueError):
        evm.normalize_address(bad)


def test_bad_configured_address_is_never_used(chain, monkeypatch):
    a = crypto.BY_ID["usdt-bep20"]
    assert crypto.receive_address(a) == ADDR and crypto.is_live(a)
    monkeypatch.setenv("CRYPTO_BSC_ADDRESS", ADDR[:-1] + "3")
    assert crypto.receive_address(a) == "" and not crypto.is_live(a) and "checksum" in crypto.address_error(a)


def test_only_allowlisted_asset_is_live(chain):
    live = {a["id"] for a in crypto.asset_catalog() if a["live"]}
    assert live == {"usdt-bep20"}
    cat = next(a for a in crypto.asset_catalog() if a["id"] == "usdt-bep20")
    assert cat["address"] == ADDR and cat["contract"] == USDT and cat["decimals"] == 18 and cat["chain_id"] == 56
    assert crypto.BY_ID["usdt-bep20"].contract == USDT


def test_invoice_shape_and_qr(chain):
    inv = buy()
    assert inv["pay_address"] == ADDR and inv["contract"] == USDT and not inv["mock"] and inv["auto_detect"]
    assert inv["payment_uri"] == f"ethereum:{USDT}@56/transfer?address={ADDR}&uint256={units(inv['amount_crypto'])}"
    assert "<svg" in inv["qr_svg"] and "<svg" in inv["qr_address_svg"]
    assert inv["confirmations_required"] == CONF and inv["chain_id"] == 56
    assert "from_block" not in inv
    base = plans.quote("pro", "1m")["amount_usdt"]
    assert base < float(inv["amount_crypto"]) < base + 1


def test_unique_amount_tags(chain):
    amounts = {buy(f"u{i}")["amount_crypto"] for i in range(60)}
    assert len(amounts) == 60


def test_no_mock_in_production(chain, monkeypatch):
    class S:
        is_production = True
        crypto_payment_allow_mock_in_production = False
    monkeypatch.setattr("app.infrastructure.config.get_settings", lambda: S())
    with pytest.raises(ApplicationError) as e:
        service.create_checkout("u1", "pro", "1m", "usdt-trc20")
    assert e.value.status_code == 503
    assert buy()["status"] == "pending"  # the live asset still works
    assert next(a for a in crypto.asset_catalog() if a["id"] == "usdt-trc20")["available"] is False


# ------------------------------------------------------------------ detection
def test_exact_payment_waits_for_confirmations_then_activates(chain):
    inv = buy()
    assert service.current_plan("u1")["id"] == "free"
    tx = chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(3)
    scan()
    cur = service.refresh_invoice("u1", inv["id"])
    assert cur["status"] == "pending" and cur["detected"]["tx"] == tx and cur["detected"]["confirmations"] == 3
    assert service.current_plan("u1")["id"] == "free"
    chain.mine(CONF)
    scan()
    done = paid("u1", inv["id"])
    assert done["status"] == "paid" and done["tx"] == tx and done["paid_via"] == "auto" and not done.get("paid_late")
    assert Decimal(done["received"]) == Decimal(inv["amount_crypto"])
    assert service.current_plan("u1")["id"] == "pro"
    assert watcher.watch_read() == {}


def test_idempotent_rescans_and_duplicate_transfer(chain):
    inv = buy()
    amt = units(inv["amount_crypto"])
    chain.send(amt, block=chain.head + 1)
    chain.mine(CONF + 5)
    for _ in range(4):
        scan()
    exp1 = store.load("u1")["subscription"]["expires_at"]
    assert len(store.load("u1")["history"]) == 1
    # the same amount arrives again (user paid twice): never extends automatically, goes to review as duplicate
    chain.send(amt)
    chain.mine(CONF + 1)
    buy("u2")  # some other invoice keeps the group alive
    for _ in range(3):
        scan()
    assert store.load("u1")["subscription"]["expires_at"] == exp1 and len(store.load("u1")["history"]) == 1
    review = watcher.admin_overview()["needs_review"]
    assert [r["reason"] for r in review] == ["duplicate"]


def test_underpaid_is_not_activated_and_flagged(chain):
    inv = buy()
    base = plans.quote("pro", "1m")["amount_usdt"]
    chain.send(units(base - 3), block=chain.head + 1)
    chain.mine(CONF + 2)
    scan()
    cur = service.refresh_invoice("u1", inv["id"])
    assert cur["status"] == "pending" and cur["underpaid"]["missing"] == "3"
    assert service.current_plan("u1")["id"] == "free"
    assert watcher.admin_overview()["needs_review"][0]["reason"] == "underpaid"


def test_overpay_within_tolerance_ok_large_overpay_reviewed(chain):
    a, b = buy("u1"), buy("u2", dur="12m")
    over = units(Decimal(a["amount_crypto"]) + Decimal("0.5"))
    chain.send(over, block=chain.head + 1)
    chain.mine(CONF + 2)
    scan()
    assert paid("u1", a["id"])["status"] == "paid" and paid("u1", a["id"])["paid_note"] == "overpaid"
    big = units(Decimal(b["amount_crypto"]) + Decimal("50"))
    chain.send(big)
    chain.mine(CONF + 2)
    scan()
    assert paid("u2", b["id"])["status"] == "pending"
    assert watcher.admin_overview()["needs_review"][-1]["reason"] == "overpaid_unmatched"


def test_amount_without_tag_is_accepted_when_unambiguous(chain):
    inv = buy()
    base = plans.quote("pro", "1m")["amount_usdt"]
    chain.send(units(base), block=chain.head + 1)
    chain.mine(CONF + 2)
    scan()
    assert paid("u1", inv["id"])["status"] == "paid" and paid("u1", inv["id"])["paid_note"] == "amount_below_tag"


def test_ambiguous_untagged_amount_goes_to_review(chain):
    a, b = buy("u1"), buy("u2")
    base = plans.quote("pro", "1m")["amount_usdt"]
    chain.send(units(base), block=chain.head + 1)
    chain.mine(CONF + 2)
    scan()
    assert paid("u1", a["id"])["status"] == "pending" and paid("u2", b["id"])["status"] == "pending"
    assert watcher.admin_overview()["needs_review"][0]["reason"] == "ambiguous"


def test_transfers_before_the_invoice_wrong_token_removed_and_self_ignored(chain):
    inv = buy()
    amt = units(inv["amount_crypto"])
    chain.send(amt, block=chain.head - 100)                       # older than the invoice
    chain.send(amt, block=chain.head + 1, removed=True)            # reorged out
    chain.send(amt, block=chain.head + 1, contract=crypto.BY_ID["usdc-bep20"].contract)  # other token
    chain.send(amt, block=chain.head + 1, sender=ADDR)             # from ourselves
    chain.send(amt, block=chain.head + 1, to=SENDER)               # to somebody else
    chain.mine(CONF + 2)
    scan()
    assert paid("u1", inv["id"])["status"] == "pending"


def test_late_payment_inside_grace_is_accepted_and_flagged(chain):
    inv = buy()
    created = paid("u1", inv["id"])["created_ts"]
    chain.ts = int(created + 3 * 3600)
    chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 2)
    scan(now=created + 3 * 3600)
    done = paid("u1", inv["id"])
    assert done["status"] == "paid" and done["paid_late"] is True


def test_invoice_expires_after_grace_and_stops_being_watched(chain):
    inv = buy()
    created = paid("u1", inv["id"])["created_ts"]
    scan(now=created + 25 * 3600)
    assert paid("u1", inv["id"])["status"] == "expired" and watcher.watch_read() == {}
    # a payment for an expired invoice is not applied automatically, admin can still confirm it with the hash
    tx = chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 2)
    out = service.admin_confirm("admin@x", inv["id"], tx=tx, note="late but real")
    assert out["status"] == "paid" and out["confirmed_by"] == "admin@x" and service.current_plan("u1")["id"] == "pro"


def test_scan_is_chunked_and_cursor_persists(chain):
    inv = buy()
    chain.mine(4500)
    scan()
    assert all(hi - lo + 1 <= 1000 for lo, hi in chain.log_calls) and len(chain.log_calls) >= 5
    chain.log_calls.clear()
    chain.mine(100)
    scan()
    assert len(chain.log_calls) == 1 and chain.log_calls[0][0] > chain.head - 100 - CONF - 5   # only the recent tail again
    chain.send(units(inv["amount_crypto"]), block=chain.head - 10)
    chain.mine(CONF)
    scan()
    assert paid("u1", inv["id"])["status"] == "paid"


def test_rpc_outage_keeps_invoice_pending_and_recovers(chain):
    inv = buy()
    chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 2)
    chain.down = True
    out = scan()
    assert out["errors"] and paid("u1", inv["id"])["status"] == "pending"
    assert watcher.admin_overview()["last_error"]
    chain.down = False
    scan()
    assert paid("u1", inv["id"])["status"] == "paid"


def test_refresh_endpoint_is_throttled_but_works(chain):
    inv = buy()
    chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 2)
    got = service.refresh_invoice("u1", inv["id"])
    assert got["status"] == "paid"
    n = len(chain.log_calls)
    service.refresh_invoice("u1", inv["id"])
    assert len(chain.log_calls) == n


# ------------------------------------------------------------------ rpc pool failover
def test_rpc_pool_fails_over(monkeypatch):
    calls: list[str] = []
    pool = evm.RpcPool(["https://a.example", "https://b.example", "https://c.example"], chain_id=56)

    def fake_post(url, method, params):
        calls.append(url)
        if url.startswith("https://a"):
            raise OSError("timeout")
        if method == "eth_chainId":
            return "0x61" if "b.example" in url else "0x38"   # b is a testnet endpoint -> rejected
        return "0x10"
    monkeypatch.setattr(pool, "_post", fake_post)
    assert pool.block_number() == 16
    assert calls[-1].startswith("https://c")
    n = len(calls)
    assert pool.block_number() == 16 and calls[n:] == ["https://c.example"]   # sticks to the endpoint that worked
    bad = evm.RpcPool(["https://x.example"], 56)
    monkeypatch.setattr(bad, "_post", lambda *a: (_ for _ in ()).throw(OSError("nope")))
    with pytest.raises(evm.RpcError):
        bad.block_number()


# ------------------------------------------------------------------ tx-hash claim + admin
def test_claim_tx_happy_path_and_repeat(chain):
    inv = buy()
    tx = chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 1)
    out = service.claim_tx("u1", inv["id"], tx)
    assert out["status"] == "paid" and out["paid_via"] == "claim" and service.current_plan("u1")["id"] == "pro"
    assert service.claim_tx("u1", inv["id"], tx)["status"] == "paid"           # idempotent
    assert len(store.load("u1")["history"]) == 1


def test_claim_tx_rules(chain):
    a, b = buy("u1"), buy("u2")
    tx = chain.send(units(a["amount_crypto"]), block=chain.head + 1)
    chain.mine(CONF + 1)
    with pytest.raises(ApplicationError) as e:                                    # someone else's payment
        service.claim_tx("u2", b["id"], tx)
    assert e.value.status_code == 409
    service.claim_tx("u1", a["id"], tx)
    with pytest.raises(ApplicationError):                                         # already used
        service.claim_tx("u2", b["id"], tx)
    with pytest.raises(ApplicationError) as e:
        service.claim_tx("u2", b["id"], "0x1234")
    assert e.value.status_code == 422
    with pytest.raises(ApplicationError) as e:
        service.claim_tx("u2", b["id"], "0x" + "ab" * 32)
    assert e.value.status_code == 404
    failed = chain.send(units(b["amount_crypto"]), status="0x0")
    with pytest.raises(ApplicationError) as e:
        service.claim_tx("u2", b["id"], failed)
    assert e.value.status_code == 409
    notme = chain.send(units(b["amount_crypto"]), to=SENDER)
    with pytest.raises(ApplicationError):
        service.claim_tx("u2", b["id"], notme)
    with pytest.raises(ApplicationError):
        service.claim_tx("u1", b["id"], tx)                                       # not your invoice


def test_claim_tx_waits_for_confirmations(chain):
    inv = buy()
    tx = chain.send(units(inv["amount_crypto"]), block=chain.head + 1)
    chain.mine(2)
    out = service.claim_tx("u1", inv["id"], tx)
    assert out["status"] == "pending" and out["detected"]["confirmations"] == 2
    chain.mine(CONF)
    assert service.claim_tx("u1", inv["id"], tx)["status"] == "paid"


def test_admin_confirm_manual_and_gate(chain, monkeypatch):
    inv = buy()
    monkeypatch.setenv("BILLING_ADMIN_ACCOUNTS", "boss@example.com, root")
    assert service.is_admin("x", "Boss@Example.com") and service.is_admin("root") and not service.is_admin("u1", "u1@x.io")
    monkeypatch.delenv("BILLING_ADMIN_ACCOUNTS")
    assert not service.is_admin("root")
    with pytest.raises(ApplicationError):
        service.admin_confirm("root", inv["id"])                                  # note required
    out = service.admin_confirm("root", inv["id"], note="paid via support chat ref 123")
    assert out["status"] == "paid" and out["paid_via"] == "admin" and watcher.watch_read() == {}
    assert service.admin_confirm("root", inv["id"], note="again")["status"] == "paid"
    assert len(store.load("u1")["history"]) == 1


def test_admin_confirm_with_underpaying_tx_is_refused(chain):
    inv = buy()
    tx = chain.send(units(1), block=chain.head + 1)
    chain.mine(CONF + 1)
    with pytest.raises(ApplicationError):
        service.admin_confirm("root", inv["id"], tx=tx)
