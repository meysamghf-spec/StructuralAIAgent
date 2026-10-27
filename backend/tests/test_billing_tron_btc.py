"""USDT on Tron (TRC20) and Bitcoin on-chain: address validation, contracts, quotes, unique tags, detection with
mocked chain APIs, confirmations, claim-by-txid, and no confusion with the EVM chains."""
from __future__ import annotations

import time
from decimal import Decimal

import httpx
import pytest

from app.application.billing import btc, crypto, evm, service, store, tron, watcher
from app.application.exceptions import ApplicationError

EVM_ADDR = "0x17F5FC2fC7ca5066bBF96d0E1687122553410022"
TRON_ADDR = "TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwf"
BTC_ADDR = "bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd3"
OTHER_TRON = "TNXoiAJ3dct8Fjg4M9fkLFh9S2v9TXc32G"
SENDER_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
SENDER_BTC = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
USDT_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ALL = ["usdt-bep20", "usdc-bep20", "usdt-polygon", "usdc-polygon", "usdt-erc20", "usdc-erc20", "usdt-trc20", "btc-onchain"]
BTC_PRICE = 65000.0


class TronChain:
    """In-memory Tron node with the RpcPool interface (Ethereum-style JSON-RPC)."""

    def __init__(self, head: int = 87_000_000) -> None:
        self.head, self.logs, self.receipts, self.down, self._n, self.windows = head, [], {}, False, 0, []

    def send(self, value: int, *, to: str = TRON_ADDR, contract: str = USDT_TRON, block: int | None = None, sender: str = SENDER_TRON) -> str:
        self._n += 1
        h = f"{self._n:064x}"
        lg = {"address": tron.hex_contract(contract), "removed": False, "transactionHash": "0x" + h, "logIndex": "0x0",
              "blockNumber": hex(block if block is not None else self.head),
              "topics": [crypto.TRANSFER_TOPIC, tron.topic_for_address(sender), tron.topic_for_address(to)], "data": hex(value)}
        self.logs.append(lg)
        self.receipts["0x" + h] = {"status": "0x1", "logs": [lg]}
        return h

    def block_number(self) -> int:
        if self.down:
            raise evm.RpcError("tron down")
        return self.head

    def get_logs(self, flt: dict) -> list[dict]:
        if self.down:
            raise evm.RpcError("tron down")
        lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
        assert hi - lo + 1 <= 1000
        self.windows.append(hi - lo + 1)
        return [lg for lg in self.logs if lo <= int(lg["blockNumber"], 16) <= hi and lg["address"] == flt["address"].lower()
                and lg["topics"][2] == flt["topics"][2]]

    def receipt(self, tx: str):
        return self.receipts.get(tx.lower())

    def block_timestamp(self, number: int) -> int:
        return int(time.time())


class BtcChain:
    """In-memory Bitcoin explorer (Esplora-shaped transactions) with the EsploraPool interface."""

    def __init__(self, head: int = 900_000) -> None:
        self.head, self.txs, self.down, self._n = head, {}, False, 0

    def send(self, sats: int, *, to: str = BTC_ADDR, height: int | None = None, sender: str = SENDER_BTC, extra: list[tuple[str, int]] | None = None) -> str:
        """height=None -> unconfirmed (mempool)."""
        self._n += 1
        txid = f"{0xb7c0000 + self._n:064x}"
        vout = [{"scriptpubkey_address": to, "value": sats}] + [{"scriptpubkey_address": a, "value": v} for a, v in (extra or [])]
        self.txs[txid] = {"txid": txid, "vin": [{"prevout": {"scriptpubkey_address": sender}}], "vout": vout,
                          "status": {"confirmed": True, "block_height": height} if height is not None else {"confirmed": False}}
        return txid

    def drop(self, txid: str) -> None:   # replaced-by-fee / evicted
        self.txs.pop(txid)

    def block_number(self) -> int:
        if self.down:
            raise btc.EsploraError("btc down")
        return self.head

    def address_txs(self, address: str, stop_height: int, max_pages: int = 6):
        if self.down:
            raise btc.EsploraError("btc down")
        return [t for t in self.txs.values() if any(v["scriptpubkey_address"] == address for v in t["vout"])]

    def tx(self, txid: str):
        return self.txs.get(txid)

    def block_timestamp(self, number: int) -> int:
        return int(time.time())


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_root", lambda: (tmp_path / "accounts").mkdir(exist_ok=True) or tmp_path)
    monkeypatch.setattr(watcher, "_last_run_mem", 0.0)
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    monkeypatch.setenv("CRYPTO_EVM_ADDRESS", EVM_ADDR)
    monkeypatch.setenv("CRYPTO_TRON_ADDRESS", TRON_ADDR)
    monkeypatch.setenv("CRYPTO_BTC_ADDRESS", BTC_ADDR)
    monkeypatch.setenv("CRYPTO_LIVE_ASSETS", ",".join(ALL))
    for k in ("CRYPTO_CONFIRMATIONS", "CRYPTO_TRON_CONFIRMATIONS", "CRYPTO_BTC_CONFIRMATIONS", "BTCPAY_SERVER_URL",
              "BILLING_COMPLIMENTARY_ACCOUNTS", "CRYPTO_RATES_JSON", "TRONGRID_API_KEY", "CRYPTO_BTC_API", "CRYPTO_BTC_API_URLS"):
        monkeypatch.delenv(k, raising=False)
    fakes = {"tron": TronChain(), "btc": BtcChain()}
    monkeypatch.setattr(crypto, "start_marker", lambda a: {"from_block": fakes[a.chain].head - (5 if a.chain == "tron" else 2)} if a.chain in fakes else {})
    monkeypatch.setattr(crypto, "usd_price", lambda coin: (1.0, "peg") if coin in ("USDT", "USDC") else (BTC_PRICE, "coingecko"))
    watcher.set_pool_factory(lambda c: fakes[c])
    yield fakes
    watcher.set_pool_factory(None)


def buy(asset, acc="u1", plan="pro", dur="1m"):
    return service.create_checkout(acc, plan, dur, asset)["invoice"]


def units(inv) -> int:
    return int(Decimal(inv["amount_crypto"]).scaleb(6 if inv["asset_id"] == "usdt-trc20" else 8))


def status(acc, inv):
    return next(i for i in store.load(acc)["invoices"] if i["id"] == inv["id"])["status"]


def scan():
    return watcher.run_once(force=True)


# ------------------------------------------------------------------ addresses and catalog
def test_owner_addresses_pass_their_checksums():
    assert tron.normalize_address(TRON_ADDR) == TRON_ADDR
    assert btc.normalize_address(BTC_ADDR) == BTC_ADDR
    assert tron.bytes_to_address(tron.address_to_bytes(TRON_ADDR)) == TRON_ADDR


@pytest.mark.parametrize("bad", ["TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwg", "TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSw", "0x17F5FC2fC7ca5066bBF96d0E1687122553410022",
                                 "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "", "TOuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwf"])
def test_bad_tron_addresses_rejected(bad):
    with pytest.raises(ValueError):
        tron.normalize_address(bad)


@pytest.mark.parametrize("bad", ["bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd4", "bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpD3",
                                 "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx", TRON_ADDR, "", "bc1"])
def test_bad_bitcoin_addresses_rejected(bad):
    with pytest.raises(ValueError):
        btc.normalize_address(bad)


def test_bitcoin_address_formats_accepted():
    assert btc.normalize_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")           # legacy P2PKH
    assert btc.normalize_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")           # P2SH
    assert btc.normalize_address("bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297")  # taproot (bech32m)
    assert btc.normalize_address(BTC_ADDR.upper()) == BTC_ADDR


def test_usdt_tron_contract_and_decimals():
    a = crypto.BY_ID["usdt-trc20"]
    assert (a.contract, a.decimals, a.chain) == ("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", 6, "tron")
    assert tron.hex_contract(a.contract) == "0xa614f803b6fd780986a42c78ec9c7f77e6ded13c"   # as seen in eth_getLogs results


def test_eight_assets_live_and_nothing_else(world):
    cat = {a["id"]: a for a in crypto.asset_catalog()}
    assert {i for i, a in cat.items() if a["live"]} == set(ALL)
    assert cat["usdt-trc20"]["address"] == TRON_ADDR and cat["usdt-trc20"]["confirmations"] == 20
    assert cat["btc-onchain"]["address"] == BTC_ADDR and cat["btc-onchain"]["confirmations"] == 3
    assert all(cat[i]["auto_detect"] for i in ALL)
    for i in ("btc-lightning", "ltc", "ton", "trx", "eth", "bnb"):
        assert not cat[i]["live"]


def test_even_without_allowlist_lightning_ltc_ton_native_stay_off(world, monkeypatch):
    monkeypatch.delenv("CRYPTO_LIVE_ASSETS")
    assert {a["id"] for a in crypto.asset_catalog() if a["live"]} == set(ALL)


def test_production_hides_everything_not_live(world, monkeypatch):
    monkeypatch.setattr(crypto, "mock_allowed", lambda: False)
    assert {a["id"] for a in crypto.asset_catalog() if a["available"]} == set(ALL)
    for hidden in ("btc-lightning", "ltc", "ton", "trx"):
        with pytest.raises(ApplicationError) as e:
            service.create_checkout("u1", "pro", "1m", hidden)
        assert e.value.status_code == 503


def test_invalid_configured_addresses_never_go_live(world, monkeypatch):
    monkeypatch.setenv("CRYPTO_TRON_ADDRESS", "TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwg")
    monkeypatch.setenv("CRYPTO_BTC_ADDRESS", "bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd4")
    assert not crypto.is_live(crypto.BY_ID["usdt-trc20"]) and not crypto.is_live(crypto.BY_ID["btc-onchain"])
    assert "checksum" in crypto.address_error(crypto.BY_ID["usdt-trc20"])
    assert crypto.address_error(crypto.BY_ID["btc-onchain"])


def test_without_btc_address_bitcoin_stays_off_even_with_btcpay_configured(world, monkeypatch):
    monkeypatch.delenv("CRYPTO_BTC_ADDRESS")
    monkeypatch.setenv("BTCPAY_SERVER_URL", "https://pay.example.com")
    monkeypatch.setenv("BTCPAY_API_KEY", "k")
    monkeypatch.setenv("BTCPAY_STORE_ID", "s")
    assert not crypto.is_live(crypto.BY_ID["btc-onchain"])


def test_config_urls_and_trongrid_key_only_for_trongrid(monkeypatch):
    monkeypatch.setenv("CRYPTO_TRON_RPC_URLS", "https://my-node.example/jsonrpc")
    assert crypto.rpc_urls("tron")[0] == "https://my-node.example/jsonrpc" and "https://api.trongrid.io/jsonrpc" in crypto.rpc_urls("tron")
    monkeypatch.setenv("CRYPTO_BTC_API_URLS", "https://esplora.example/api/")
    monkeypatch.setenv("CRYPTO_BTC_API", "https://blockstream.info/api")
    assert crypto.btc_api_urls()[0] == "https://esplora.example/api" and crypto.btc_api_urls().count("https://blockstream.info/api") == 1
    monkeypatch.delenv("TRONGRID_API_KEY", raising=False)
    assert crypto.rpc_headers() == {}
    monkeypatch.setenv("TRONGRID_API_KEY", "secret")
    assert crypto.rpc_headers() == {"api.trongrid.io": {"TRON-PRO-API-KEY": "secret"}}


def test_rpcpool_sends_key_header_to_that_host_only(monkeypatch):
    seen = []

    def fake_post(url, json=None, timeout=None, headers=None):
        seen.append((url, headers))
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x2b6653dc" if json["method"] == "eth_chainId" else "0x10"},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(evm.httpx, "post", fake_post)
    pool = evm.RpcPool(["https://api.trongrid.io/jsonrpc", "https://tron-rpc.publicnode.com/jsonrpc"], tron.TRON_CHAIN_ID,
                       headers={"api.trongrid.io": {"TRON-PRO-API-KEY": "k"}})
    assert pool.block_number() == 16
    assert all(h == {"TRON-PRO-API-KEY": "k"} for u, h in seen if "trongrid" in u)
    pool2 = evm.RpcPool(["https://tron-rpc.publicnode.com/jsonrpc"], tron.TRON_CHAIN_ID, headers={"api.trongrid.io": {"TRON-PRO-API-KEY": "k"}})
    seen.clear()
    pool2.block_number()
    assert all(h is None for _, h in seen)


# ------------------------------------------------------------------ Tron USDT
def test_tron_invoice_shape_and_unique_tags(world):
    invs = [buy("usdt-trc20", f"u{i}") for i in range(25)]
    assert len({i["amount_crypto"] for i in invs}) == 25
    i = invs[0]
    assert i["pay_address"] == TRON_ADDR and i["contract"] == USDT_TRON and i["chain"] == "tron" and i["confirmations_required"] == 20
    assert i["chain_id"] is None and i["auto_detect"] and not i["mock"] and "qr_svg" in i
    assert "qr_address_svg" not in i   # a Tron QR is the plain address, so there is no separate address-only QR
    assert Decimal(i["amount_crypto"]) > Decimal(str(i["amount_usdt"])) and Decimal(i["amount_crypto"]) - Decimal(str(i["amount_usdt"])) < 1


def test_tron_exact_payment_settles_after_confirmations(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    h = t.send(units(inv), block=t.head + 1)
    t.head += 5
    scan()
    assert status("u1", inv) == "pending"
    seen = watcher.seen(inv["id"])["detected"]
    assert seen["tx"] == h and seen["required"] == 20 and seen["confirmations"] < 20
    t.head += 30
    scan()
    done = next(i for i in store.load("u1")["invoices"] if i["id"] == inv["id"])
    assert done["status"] == "paid" and done["tx"] == h and not h.startswith("0x") and done["paid_via"] == "auto"
    assert done["received"] == inv["amount_crypto"]
    scan()   # idempotent
    assert status("u1", inv) == "paid"


def test_tron_ignores_other_token_other_recipient_and_dust(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    t.send(units(inv), contract="TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8")   # a different TRC20 token, same amount
    t.send(units(inv), to=OTHER_TRON)
    t.send(0)
    t.head += 40
    scan()
    assert status("u1", inv) == "pending" and not watcher.admin_overview()["needs_review"]


def test_tron_underpaid_and_unmatched_go_to_review(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    t.send(units(inv) - 500_000)
    t.head += 40
    scan()
    assert status("u1", inv) == "pending"
    assert watcher.admin_overview()["needs_review"][0]["reason"] == "underpaid"
    assert watcher.seen(inv["id"])["underpaid"]["missing"]


def test_tron_sender_is_base58_and_self_transfer_is_review(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    t.send(units(inv), sender=TRON_ADDR)
    t.head += 40
    scan()
    assert status("u1", inv) == "pending"
    assert watcher.admin_overview()["needs_review"][0]["reason"] == "self_transfer"
    inv2 = buy("usdt-trc20", "u2")
    t.send(units(inv2), sender=SENDER_TRON)
    t.head += 40
    scan()
    paid = next(i for i in store.load("u2")["invoices"] if i["id"] == inv2["id"])
    assert paid["status"] == "paid" and paid.get("sender") == SENDER_TRON


def test_tron_window_is_1000_blocks_and_outage_does_not_lose_payments(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    t.down = True
    scan()
    assert status("u1", inv) == "pending"
    t.down = False
    t.send(units(inv))
    t.head += 3500
    scan()
    assert max(t.windows) <= 1000 and status("u1", inv) == "paid"


def test_tron_claim_by_txid_with_and_without_0x(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    h = t.send(units(inv))
    t.head += 30
    out = watcher.claim_tx("u1", inv["id"], "0x" + h.upper().replace("0X", "0x"))
    assert out["status"] == "paid" and out["tx"] == h
    again = watcher.claim_tx("u1", inv["id"], h)
    assert again["status"] == "paid"


def test_tron_claim_errors(world):
    t = world["tron"]
    inv = buy("usdt-trc20")
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], "not-a-hash")
    assert e.value.code == "BAD_TX"
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], "ab" * 32)
    assert e.value.code == "TX_NOT_FOUND"
    h = t.send(units(inv) + 7_000_000)   # +7 USDT: unmatched
    t.head += 30
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], h)
    assert e.value.code == "AMOUNT_MISMATCH"
    h2 = t.send(units(inv), to=OTHER_TRON)
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], h2)
    assert e.value.code == "NO_TRANSFER"
    # an EVM-style hash with 0x is tolerated, an EVM transaction on Tron is simply not found
    assert status("u1", inv) == "pending"


def test_same_raw_amount_on_tron_and_bsc_never_collides(world, monkeypatch):
    """A Tron payment can't settle a BSC invoice and vice versa, even when the tagged amounts are equal."""
    class Quiet:
        head = 1_000_000
        def block_number(self): return self.head
        def get_logs(self, flt): return []
        def receipt(self, tx): return None
        def block_timestamp(self, n): return int(time.time())
    pools = {"tron": world["tron"], "bsc": Quiet(), "btc": world["btc"]}
    watcher.set_pool_factory(lambda c: pools[c])
    monkeypatch.setattr(crypto, "start_marker", lambda a: {"from_block": 999_995} if a.chain == "bsc" else {"from_block": world["tron"].head - 5})
    monkeypatch.setattr(crypto.random, "choice", lambda seq: seq[0])
    tr, bs = buy("usdt-trc20", "u1"), buy("usdt-bep20", "u2")
    assert tr["amount_crypto"] == bs["amount_crypto"]
    world["tron"].send(units(tr))
    world["tron"].head += 30
    scan()
    assert status("u1", tr) == "paid" and status("u2", bs) == "pending"


# ------------------------------------------------------------------ Bitcoin
def test_btc_quote_sats_tag_uri_and_rate(world):
    inv = buy("btc-onchain")
    assert inv["pay_address"] == BTC_ADDR and inv["chain"] == "btc" and inv["confirmations_required"] == 3 and inv["auto_detect"]
    sats, base = units(inv), int(Decimal(inv["amount_crypto_base"]).scaleb(8))
    assert 1 <= sats - base <= 999
    plan_usd = Decimal(str(inv["amount_usdt"]))
    assert abs(Decimal(base) / Decimal(10) ** 8 * Decimal(BTC_PRICE) - plan_usd) < Decimal("0.001")
    assert inv["rate_usd"] == BTC_PRICE and inv["rate_source"] == "coingecko"
    assert inv["payment_uri"] == f"bitcoin:{BTC_ADDR}?amount={inv['amount_crypto']}"
    assert "e" not in inv["amount_crypto"].lower() and "qr_svg" in inv and "qr_address_svg" in inv


def test_btc_tags_are_unique_among_open_invoices(world):
    invs = [buy("btc-onchain", f"u{i}") for i in range(40)]
    assert len({i["amount_crypto"] for i in invs}) == 40


def test_btc_never_uses_the_offline_reference_price(world, monkeypatch):
    monkeypatch.setattr(crypto, "usd_price", lambda coin: (65000.0, "fallback"))
    with pytest.raises(ApplicationError) as e:
        buy("btc-onchain")
    assert e.value.code == "GATEWAY_ERROR" and "price feed" in str(e.value)


def test_btc_second_price_source_is_used_when_coingecko_fails(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kw):
        if "coingecko" in url:
            raise httpx.ConnectError("blocked")
        return httpx.Response(200, json={"USD": 71234.0}, request=httpx.Request("GET", url))
    monkeypatch.delenv("CRYPTO_RATES_JSON", raising=False)
    monkeypatch.setattr(crypto.httpx, "get", fake_get)
    assert crypto.usd_price("BTC") == (71234.0, "mempool")


def test_btc_unconfirmed_is_seen_then_settles_at_three_confirmations(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    txid = b.send(units(inv))                    # in the mempool
    scan()
    seen = watcher.seen(inv["id"])["detected"]
    assert status("u1", inv) == "pending" and seen["tx"] == txid and seen["confirmations"] == 0 and seen["required"] == 3
    b.txs[txid]["status"] = {"confirmed": True, "block_height": b.head + 1}
    b.head += 1
    scan()
    assert status("u1", inv) == "pending" and watcher.seen(inv["id"])["detected"]["confirmations"] == 1
    b.head += 2
    scan()
    done = next(i for i in store.load("u1")["invoices"] if i["id"] == inv["id"])
    assert done["status"] == "paid" and done["tx"] == txid and done["paid_via"] == "auto" and done["received"] == inv["amount_crypto"]
    assert done["sender"] == SENDER_BTC
    scan()
    assert status("u1", inv) == "paid"


def test_btc_replaced_unconfirmed_transaction_never_activates(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    txid = b.send(units(inv))
    scan()
    b.drop(txid)    # RBF-replaced / evicted
    b.head += 10
    scan()
    assert status("u1", inv) == "pending" and "detected" not in watcher.seen(inv["id"])


def test_btc_wrong_address_and_dust_ignored(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    b.send(units(inv), to="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", height=b.head)
    b.send(0, height=b.head)
    b.head += 5
    scan()
    assert status("u1", inv) == "pending" and not watcher.admin_overview()["needs_review"]


def test_btc_output_among_many_and_change_back_to_us(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    other = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    b.send(units(inv), height=b.head, extra=[(other, 123456)])         # payment + another recipient in the same tx
    b.send(units(inv), height=b.head, sender=BTC_ADDR)                # our own wallet moving coins: never a customer payment
    b.head += 5
    scan()
    assert status("u1", inv) == "paid"
    assert any(r["reason"] == "self_transfer" for r in watcher.admin_overview()["needs_review"])


def test_btc_underpaid_goes_to_review_not_activation(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    base = int(Decimal(inv["amount_crypto_base"]).scaleb(8))
    b.send(base - 10_000, height=b.head)
    b.head += 5
    scan()
    assert status("u1", inv) == "pending"
    assert watcher.admin_overview()["needs_review"][0]["reason"] == "underpaid"
    assert watcher.seen(inv["id"])["underpaid"]["missing"]


def test_btc_between_untagged_and_tagged_amount_is_accepted(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    base = int(Decimal(inv["amount_crypto_base"]).scaleb(8))
    b.send(base, height=b.head)    # exactly the untagged price (e.g. wallet rounded the tag away)
    b.head += 5
    scan()
    assert status("u1", inv) == "paid"


def test_btc_overpay_tolerance_scales_with_the_locked_rate(world):
    inv = buy("btc-onchain")
    tol = watcher.tolerance_units(inv, 10**6)
    assert abs(tol - 1538) <= 2   # ~USD 1 in sats at 65k
    b = world["btc"]
    b.send(units(inv) + tol - 5, height=b.head)           # small overpay: accepted
    b.head += 5
    scan()
    assert status("u1", inv) == "paid"
    inv2 = buy("btc-onchain", "u2")
    b.send(units(inv2) + 50_000, height=b.head)            # ~USD 32 more: support reviews it
    b.head += 5
    scan()
    assert status("u2", inv2) == "pending"
    assert watcher.admin_overview()["needs_review"][-1]["reason"] == "overpaid_unmatched"


def test_btc_two_open_invoices_each_get_their_own_payment(world):
    b = world["btc"]
    a1, a2 = buy("btc-onchain", "u1"), buy("btc-onchain", "u2", plan="pro", dur="3m")
    b.send(units(a2), height=b.head)
    b.send(units(a1), height=b.head)
    b.head += 5
    scan()
    assert status("u1", a1) == "paid" and status("u2", a2) == "paid"


def test_btc_explorer_outage_keeps_invoice_pending_and_recovers(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    b.send(units(inv), height=b.head)
    b.down = True
    res = scan()
    assert res["errors"] and status("u1", inv) == "pending"
    b.down = False
    b.head += 5
    scan()
    assert status("u1", inv) == "paid"


def test_btc_claim_by_txid(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    txid = b.send(units(inv), height=b.head)
    b.head += 4
    out = watcher.claim_tx("u1", inv["id"], txid)
    assert out["status"] == "paid" and out["tx"] == txid
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], "zz")
    assert e.value.code == "BAD_TX"


def test_btc_claim_unconfirmed_reports_progress_and_errors(world):
    b = world["btc"]
    inv = buy("btc-onchain")
    txid = b.send(units(inv))
    out = watcher.claim_tx("u1", inv["id"], txid)
    assert out["status"] == "pending" and out["detected"]["confirmations"] == 0
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], "cd" * 32)
    assert e.value.code == "TX_NOT_FOUND"
    t2 = b.send(units(inv), to="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", height=b.head)
    with pytest.raises(ApplicationError) as e:
        watcher.claim_tx("u1", inv["id"], t2)
    assert e.value.code == "NO_TRANSFER"


def test_btc_and_tron_and_evm_do_not_share_state(world):
    b, t = world["btc"], world["tron"]
    ib, it = buy("btc-onchain", "u1"), buy("usdt-trc20", "u2")
    b.send(units(ib), height=b.head)
    t.send(units(it))
    b.head += 5
    t.head += 30
    scan()
    assert status("u1", ib) == "paid" and status("u2", it) == "paid"
    cur = watcher.admin_overview()["cursor"]
    assert any(k.startswith("btc::") for k in cur) and any(k.startswith("tron:") for k in cur)


# ------------------------------------------------------------------ Esplora client (HTTP mocked)
def _resp(url, data, status=200):
    if isinstance(data, str):
        return httpx.Response(status, text=data, request=httpx.Request("GET", url))
    return httpx.Response(status, json=data, request=httpx.Request("GET", url))


def test_esplora_failover_and_pagination(monkeypatch):
    calls = []
    page1 = [{"txid": f"{i:064x}", "status": {"confirmed": True, "block_height": 900_000 - i}} for i in range(25)]
    page2 = [{"txid": f"{100 + i:064x}", "status": {"confirmed": True, "block_height": 899_900 - i}} for i in range(3)]

    def fake_get(url, timeout=None, headers=None):
        calls.append(url)
        if url.startswith("https://bad.example"):
            raise httpx.ConnectError("down")
        if url.endswith("/blocks/tip/height"):
            return _resp(url, "900001")
        if "/txs/chain/" in url:
            return _resp(url, page2)
        if url.endswith("/txs"):
            return _resp(url, page1)
        if "/tx/" in url:
            return _resp(url, {}, 404)
        raise AssertionError(url)
    monkeypatch.setattr(btc.httpx, "get", fake_get)
    pool = btc.EsploraPool(["https://bad.example/api", "https://good.example/api/"])
    assert pool.block_number() == 900_001
    assert any(c.startswith("https://bad.example") for c in calls)
    txs = pool.address_txs(BTC_ADDR, 0)
    assert len(txs) == 28 and any("/txs/chain/" + page1[-1]["txid"] in c for c in calls)
    assert pool.tx("ab" * 32) is None
    with pytest.raises(btc.EsploraError):
        btc.EsploraPool(["https://bad.example/api"]).block_number()


def test_esplora_stops_paging_below_start_height(monkeypatch):
    page1 = [{"txid": f"{i:064x}", "status": {"confirmed": True, "block_height": 800_000 - i}} for i in range(25)]
    calls = []

    def fake_get(url, timeout=None, headers=None):
        calls.append(url)
        return _resp(url, page1)
    monkeypatch.setattr(btc.httpx, "get", fake_get)
    assert len(btc.EsploraPool(["https://x.example/api"]).address_txs(BTC_ADDR, 850_000)) == 25
    assert len(calls) == 1


def test_parse_btc_txs_outputs_and_heights():
    txs = [{"txid": "aa" * 32, "vin": [{"prevout": {"scriptpubkey_address": SENDER_BTC}}], "status": {"confirmed": False},
            "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 1000}, {"scriptpubkey_address": BTC_ADDR, "value": 2000}, {"scriptpubkey_address": "x", "value": 5}]},
           {"txid": "bb" * 32, "vin": [], "status": {"confirmed": True, "block_height": 10}, "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 7}]},
           {"txid": "not-hex", "vin": [], "status": {"confirmed": False}, "vout": [{"scriptpubkey_address": BTC_ADDR, "value": 7}]}]
    out = watcher.parse_btc_txs(txs, BTC_ADDR, tip=500, since_height=100)
    assert [(t.key.split(":")[1], t.value, t.block) for t in out] == [("0", 1000, 501), ("1", 2000, 501)]
    assert out[0].sender == SENDER_BTC
