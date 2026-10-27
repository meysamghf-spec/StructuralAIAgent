"""USDT/USDC on BNB Smart Chain, Polygon and Ethereum with the SAME receiving address: per-chain contracts,
decimals, confirmations, scan windows, unique tags and (above all) no cross-chain / cross-token confusion."""
from __future__ import annotations

import time
from decimal import Decimal

import pytest

from app.application.billing import crypto, evm, service, store, watcher
from app.application.exceptions import ApplicationError

ADDR = "0x17F5FC2fC7ca5066bBF96d0E1687122553410022"
SENDER = "0x2222222222222222222222222222222222222222"
SIX = ["usdt-bep20", "usdc-bep20", "usdt-polygon", "usdc-polygon", "usdt-erc20", "usdc-erc20"]
# (contract, decimals, chain, chain id) - verified on-chain by scripts/check_evm_live.py
SPEC = {
    "usdt-bep20": ("0x55d398326f99059fF775485246999027B3197955", 18, "bsc", 56),
    "usdc-bep20": ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18, "bsc", 56),
    "usdt-polygon": ("0xc2132D05D31c914a87C6611C10748AEb04B58e8F", 6, "polygon", 137),
    "usdc-polygon": ("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6, "polygon", 137),
    "usdt-erc20": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6, "eth", 1),
    "usdc-erc20": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6, "eth", 1),
}


class Chain:
    """In-memory EVM chain with the RpcPool interface used by the watcher."""

    def __init__(self, name: str, head: int = 1_000_000) -> None:
        self.name, self.head, self.logs, self.receipts, self.down, self._n = name, head, [], {}, False, 0
        self.windows: list[int] = []

    def send(self, contract: str, value: int, *, to: str = ADDR, block: int | None = None) -> str:
        self._n += 1
        tx = "0x" + self.name[:3].encode().hex().ljust(12, "0") + f"{self._n:052x}"
        lg = {"address": contract.lower(), "removed": False, "transactionHash": tx, "logIndex": "0x0",
              "blockNumber": hex(block if block is not None else self.head),
              "topics": [crypto.TRANSFER_TOPIC, evm.topic_for_address(SENDER), evm.topic_for_address(to)], "data": hex(value)}
        self.logs.append(lg)
        self.receipts[tx] = {"status": "0x1", "logs": [lg], "blockNumber": lg["blockNumber"]}
        return tx

    def block_number(self) -> int:
        if self.down:
            raise evm.RpcError(f"{self.name} down")
        return self.head

    def get_logs(self, flt: dict) -> list[dict]:
        if self.down:
            raise evm.RpcError(f"{self.name} down")
        lo, hi = int(flt["fromBlock"], 16), int(flt["toBlock"], 16)
        assert hi - lo + 1 <= 1000, "window too large for public RPCs"
        self.windows.append(hi - lo + 1)
        return [lg for lg in self.logs if lo <= int(lg["blockNumber"], 16) <= hi and lg["address"] == flt["address"].lower()
                and lg["topics"][2] == flt["topics"][2]]

    def receipt(self, tx: str):
        return self.receipts.get(tx.lower())

    def block_timestamp(self, number: int) -> int:
        return int(time.time())


@pytest.fixture
def chains(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_root", lambda: (tmp_path / "accounts").mkdir(exist_ok=True) or tmp_path)
    monkeypatch.setattr(watcher, "_last_run_mem", 0.0)
    monkeypatch.setenv("BILLING_ENFORCEMENT", "1")
    monkeypatch.setenv("CRYPTO_EVM_ADDRESS", ADDR)
    monkeypatch.setenv("CRYPTO_LIVE_ASSETS", ",".join(SIX))
    for k in ("CRYPTO_CONFIRMATIONS", "CRYPTO_BSC_CONFIRMATIONS", "CRYPTO_POLYGON_CONFIRMATIONS", "CRYPTO_ETH_CONFIRMATIONS",
              "CRYPTO_BSC_ADDRESS", "CRYPTO_ETH_ADDRESS", "CRYPTO_POLYGON_ADDRESS", "CRYPTO_TRON_ADDRESS", "CRYPTO_BTC_ADDRESS", "CRYPTO_TON_ADDRESS",
              "BTCPAY_SERVER_URL", "BILLING_COMPLIMENTARY_ACCOUNTS"):
        monkeypatch.delenv(k, raising=False)
    fakes = {"bsc": Chain("bsc"), "polygon": Chain("polygon", 70_000_000), "eth": Chain("eth", 21_000_000)}
    monkeypatch.setattr(crypto, "start_marker", lambda a: {"from_block": fakes[a.chain].head - 5})
    watcher.set_pool_factory(lambda c: fakes[c])
    yield fakes
    watcher.set_pool_factory(None)


def buy(asset, acc="u1", plan="pro", dur="1m"):
    return service.create_checkout(acc, plan, dur, asset)["invoice"]


def units(inv) -> int:
    return int(Decimal(inv["amount_crypto"]).scaleb(SPEC[inv["asset_id"]][1]))


def status(acc, inv):
    return next(i for i in store.load(acc)["invoices"] if i["id"] == inv["id"])["status"]


def scan():
    return watcher.run_once(force=True)


# ------------------------------------------------------------------ catalog / config
@pytest.mark.parametrize("asset", SIX)
def test_contract_decimals_chain_are_exact(asset):
    a = crypto.BY_ID[asset]
    contract, dec, chain, cid = SPEC[asset]
    assert (a.contract, a.decimals, a.chain, crypto.EVM_CHAINS[a.chain]) == (contract, dec, chain, cid)
    assert evm.to_checksum(a.contract) == a.contract  # a typo in a contract would fail the EIP-55 checksum


def test_six_assets_live_and_nothing_else(chains):
    cat = {a["id"]: a for a in crypto.asset_catalog()}
    assert {i for i, a in cat.items() if a["live"]} == set(SIX)
    for i in SIX:
        assert cat[i]["address"] == ADDR and cat[i]["available"]
    for i in set(cat) - set(SIX):
        assert not cat[i]["live"]


def test_without_allowlist_only_erc20_tokens_go_live_from_the_generic_address(chains, monkeypatch):
    """Native ETH/BNB are never live, and Tron/TON/BTCPay assets need their own address / server."""
    monkeypatch.delenv("CRYPTO_LIVE_ASSETS")
    live = {a["id"] for a in crypto.asset_catalog() if a["live"]}
    assert live == set(SIX)
    assert not crypto.is_live(crypto.BY_ID["eth"]) and not crypto.is_live(crypto.BY_ID["bnb"])


def test_non_live_assets_are_hidden_in_production(chains, monkeypatch):
    monkeypatch.setattr(crypto, "mock_allowed", lambda: False)
    avail = {a["id"] for a in crypto.asset_catalog() if a["available"]}
    assert avail == set(SIX)
    with pytest.raises(ApplicationError) as e:
        service.create_checkout("u1", "pro", "1m", "usdt-trc20")
    assert e.value.status_code == 503


def test_per_chain_confirmations_and_overrides(monkeypatch):
    for k in ("CRYPTO_CONFIRMATIONS", "CRYPTO_BSC_CONFIRMATIONS", "CRYPTO_POLYGON_CONFIRMATIONS", "CRYPTO_ETH_CONFIRMATIONS"):
        monkeypatch.delenv(k, raising=False)
    assert (crypto.confirmations("bsc"), crypto.confirmations("polygon"), crypto.confirmations("eth")) == (30, 64, 12)
    monkeypatch.setenv("CRYPTO_CONFIRMATIONS", "5")
    assert {crypto.confirmations(c) for c in ("bsc", "polygon", "eth")} == {5}
    monkeypatch.setenv("CRYPTO_ETH_CONFIRMATIONS", "20")
    assert (crypto.confirmations("eth"), crypto.confirmations("bsc")) == (20, 5)


def test_default_rpc_lists_are_keyless_https_with_fallbacks():
    for chain in ("bsc", "polygon", "eth"):
        urls = crypto.DEFAULT_RPC[chain]
        assert len(urls) >= 3 and all(u.startswith("https://") for u in urls)
        assert not any(w in u.lower() for u in urls for w in ("apikey", "api_key", "key=", "/v2/", "token="))


def test_rpc_env_override_goes_first(monkeypatch):
    monkeypatch.setenv("CRYPTO_ETH_RPC_URLS", "https://my.node/eth")
    assert crypto.rpc_urls("eth")[0] == "https://my.node/eth" and len(crypto.rpc_urls("eth")) > 1


# ------------------------------------------------------------------ invoices
@pytest.mark.parametrize("asset", SIX)
def test_invoice_uses_right_contract_chain_and_decimals(chains, asset):
    contract, dec, chain, cid = SPEC[asset]
    inv = buy(asset)
    assert inv["pay_address"] == ADDR and inv["contract"] == contract and inv["chain_id"] == cid and not inv["mock"]
    assert inv["payment_uri"] == f"ethereum:{contract}@{cid}/transfer?address={ADDR}&uint256={units(inv)}"
    assert inv["confirmations_required"] == crypto.DEFAULT_CONFIRMATIONS[chain]
    assert inv["coin"] == asset.split("-")[0].upper()
    assert Decimal(inv["amount_crypto"]) > 15


@pytest.mark.parametrize("asset", SIX)
def test_pay_cycle_on_each_chain_with_its_own_confirmations(chains, asset):
    contract, dec, chain, _ = SPEC[asset]
    inv = buy(asset)
    need = crypto.DEFAULT_CONFIRMATIONS[chain]
    fake = chains[chain]
    fake.send(contract, units(inv))
    fake.head += need - 2                       # one short of the required confirmations
    scan()
    assert status("u1", inv) == "pending" and service.refresh_invoice("u1", inv["id"])["detected"]["required"] == need
    fake.head += 1
    scan()
    assert status("u1", inv) == "paid"
    scan()
    assert status("u1", inv) == "paid"          # idempotent


def test_unique_tag_is_per_asset_so_usdt_and_usdc_may_share_an_amount(chains, monkeypatch):
    monkeypatch.setattr(crypto.random, "choice", lambda seq: seq[0])
    a, b = buy("usdt-polygon", "u1"), buy("usdc-polygon", "u2")
    assert a["amount_crypto"] == b["amount_crypto"]
    c = buy("usdt-polygon", "u3")               # ... but two open invoices of the SAME asset never share an amount
    assert c["amount_crypto"] != a["amount_crypto"]


# ------------------------------------------------------------------ no cross-chain / cross-token confusion
def test_same_amount_on_other_token_or_chain_never_activates_the_wrong_invoice(chains, monkeypatch):
    monkeypatch.setattr(crypto.random, "choice", lambda seq: seq[0])
    inv_usdt_pol, inv_usdc_pol, inv_usdt_eth = buy("usdt-polygon", "u1"), buy("usdc-polygon", "u2"), buy("usdt-erc20", "u3")
    assert units(inv_usdt_pol) == units(inv_usdc_pol) == units(inv_usdt_eth)    # identical raw amounts on purpose
    pol, eth = chains["polygon"], chains["eth"]
    # 1) USDC sent on Polygon pays ONLY the USDC invoice
    pol.send(SPEC["usdc-polygon"][0], units(inv_usdc_pol))
    pol.head += 70
    eth.head += 20
    scan()
    assert (status("u1", inv_usdt_pol), status("u2", inv_usdc_pol), status("u3", inv_usdt_eth)) == ("pending", "paid", "pending")
    # 2) the identical raw amount of USDT on BSC (a chain with no matching invoice) activates nothing
    chains["bsc"].send(SPEC["usdt-bep20"][0], units(inv_usdt_pol))
    chains["bsc"].head += 40
    scan()
    assert (status("u1", inv_usdt_pol), status("u3", inv_usdt_eth)) == ("pending", "pending")
    # 3) USDT on Ethereum pays ONLY the Ethereum invoice, not the Polygon USDT one
    eth.send(SPEC["usdt-erc20"][0], units(inv_usdt_eth))
    eth.head += 14
    scan()
    assert (status("u1", inv_usdt_pol), status("u3", inv_usdt_eth)) == ("pending", "paid")
    # 4) and finally the Polygon USDT payment lands on its own invoice
    pol.send(SPEC["usdt-polygon"][0], units(inv_usdt_pol))
    pol.head += 70
    scan()
    assert status("u1", inv_usdt_pol) == "paid"


def test_wrong_token_contract_on_right_chain_is_ignored(chains):
    inv = buy("usdt-polygon")
    chains["polygon"].send(SPEC["usdc-polygon"][0], units(inv))      # USDC, not USDT
    chains["polygon"].send("0x" + "ab" * 20, units(inv))             # unknown token
    chains["polygon"].head += 70
    scan()
    assert status("u1", inv) == "pending"


def test_duplicate_detection_is_scoped_to_chain_and_token(chains):
    inv = buy("usdt-polygon")
    chains["polygon"].send(SPEC["usdt-polygon"][0], units(inv))
    chains["polygon"].head += 70
    scan()
    assert status("u1", inv) == "paid"
    settled = watcher._read()["settled_units"]
    assert len(settled) == 1 and next(iter(settled)).startswith("polygon:" + SPEC["usdt-polygon"][0].lower())
    t = watcher.Transfer(key="0x" + "9" * 64 + ":0", tx="0x" + "9" * 64, block=1, log_index=0, sender=SENDER, value=units(inv))
    scope = lambda a: f"{SPEC[a][2]}:{SPEC[a][0].lower()}"   # noqa: E731
    # same raw units on Ethereum USDT / Polygon USDC / BSC USDT with nothing open: just "no pending invoice"
    for other in ("usdt-erc20", "usdc-polygon", "usdt-bep20"):
        assert watcher.classify(t, [], 0, settled, ADDR, scope=scope(other))[2] == "no_pending_invoice"
    # only the very same chain+token is reported as a duplicate of the settled payment
    assert watcher.classify(t, [], 0, settled, ADDR, scope=scope("usdt-polygon"))[2] == "duplicate"


def test_underpay_overpay_use_each_tokens_own_decimals(chains):
    six = buy("usdt-erc20", "u1")
    eth = chains["eth"]
    eth.send(SPEC["usdt-erc20"][0], units(six) - 1_000_000)        # 1 USDT short (6 decimals): below the plan price
    eth.head += 14
    scan()
    assert status("u1", six) == "pending"
    eth.send(SPEC["usdt-erc20"][0], units(six) + 500_000)          # +0.5 USDT: within the 1 USDT tolerance
    eth.head += 14
    scan()
    assert status("u1", six) == "paid"
    big = buy("usdc-bep20", "u2")
    bsc = chains["bsc"]
    bsc.send(SPEC["usdc-bep20"][0], units(big) + 5 * 10**18)       # +5 USDC with 18 decimals: needs review
    bsc.head += 40
    scan()
    assert status("u2", big) == "pending"


def test_one_chain_down_does_not_block_the_others(chains):
    a, b = buy("usdt-bep20", "u1"), buy("usdt-polygon", "u2")
    chains["bsc"].down = True
    chains["polygon"].send(SPEC["usdt-polygon"][0], units(b))
    chains["polygon"].head += 70
    out = scan()
    assert status("u2", b) == "paid" and status("u1", a) == "pending" and out["errors"]
    chains["bsc"].down = False
    chains["bsc"].send(SPEC["usdt-bep20"][0], units(a))
    chains["bsc"].head += 40
    scan()
    assert status("u1", a) == "paid"


def test_windows_and_lookback_are_sized_per_chain(chains):
    invs = {c: buy(a, f"u{i}") for i, (c, a) in enumerate((("bsc", "usdt-bep20"), ("polygon", "usdt-polygon"), ("eth", "usdt-erc20")))}
    for c, fake in chains.items():
        fake.head += 200_000            # watcher "was down" for a long time
    scan()
    for c, fake in chains.items():
        back = crypto.MAX_LOOKBACK_BLOCKS[c]
        assert max(fake.windows) <= 1000 and sum(fake.windows) <= back + 1000
    assert {g["chain"] for g in watcher.admin_overview()["gaps"]} == {"bsc", "polygon", "eth"}
    assert crypto.MAX_LOOKBACK_BLOCKS["bsc"] > crypto.MAX_LOOKBACK_BLOCKS["polygon"] > crypto.MAX_LOOKBACK_BLOCKS["eth"]
    assert invs


def test_steady_state_scan_is_a_single_small_request_per_asset(chains):
    inv = buy("usdc-erc20")
    scan()
    chains["eth"].windows.clear()
    chains["eth"].head += 3
    scan()
    assert len(chains["eth"].windows) == 1 and chains["eth"].windows[0] <= 40
    assert inv


def test_zero_value_poisoning_transfer_is_ignored(chains):
    inv = buy("usdt-erc20")
    chains["eth"].send(SPEC["usdt-erc20"][0], 0)
    chains["eth"].head += 14
    scan()
    assert status("u1", inv) == "pending"
    assert not watcher.admin_overview()["needs_review"]


def test_tx_claim_from_the_wrong_chain_is_rejected(chains):
    inv = buy("usdt-polygon")
    tx = chains["eth"].send(SPEC["usdt-erc20"][0], units(inv))      # exists on Ethereum only
    with pytest.raises(ApplicationError) as e:
        service.claim_tx("u1", inv["id"], tx)
    assert e.value.status_code == 404
    assert status("u1", inv) == "pending"


def test_claim_tx_works_on_polygon_with_its_confirmations(chains):
    inv = buy("usdc-polygon")
    tx = chains["polygon"].send(SPEC["usdc-polygon"][0], units(inv))
    chains["polygon"].head += 10
    r = service.claim_tx("u1", inv["id"], tx)
    assert r["detected"]["required"] == 64 and status("u1", inv) == "pending"
    chains["polygon"].head += 60
    service.claim_tx("u1", inv["id"], tx)
    assert status("u1", inv) == "paid"
