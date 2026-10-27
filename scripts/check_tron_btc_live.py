#!/usr/bin/env python
"""Read-only live check of USDT (TRC20) on Tron and Bitcoin on-chain. No keys, no transactions, no funds moved.

Run from the repo root:   python scripts/check_tron_btc_live.py
Addresses default to CRYPTO_TRON_ADDRESS / CRYPTO_BTC_ADDRESS (or the owner's public receive addresses).
Exit code 0 only if everything that must pass passed (an endpoint being down is reported, not fatal, while at least one works).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.application.billing import btc, crypto, evm, tron  # noqa: E402
from app.application.billing.watcher import parse_btc_txs, parse_logs  # noqa: E402

TRON_ADDR = os.environ.get("CRYPTO_TRON_ADDRESS", "TDuvB4k5foeTrUFFeDdnpCHVbn6M6QgSwf").strip()
BTC_ADDR = os.environ.get("CRYPTO_BTC_ADDRESS", "bc1qd3fyhu2a97hhgezd7sf7rk6h740w53xa6wwpd3").strip()


def _str(hexdata: str) -> str:
    b = bytes.fromhex(hexdata[2:])
    if len(b) >= 64:
        n = int.from_bytes(b[32:64], "big")
        return b[64:64 + n].decode()
    return b.rstrip(b"\0").decode()


def main() -> int:
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

    # ---------------------------------------------------------------- Tron
    print("== Tron (USDT TRC20)")
    try:
        check("Tron receiving address passes base58check", tron.normalize_address(TRON_ADDR) == TRON_ADDR, TRON_ADDR)
    except ValueError as exc:
        check("Tron receiving address passes base58check", False, str(exc))
        return 1
    a = crypto.BY_ID["usdt-trc20"]
    check("USDT contract passes base58check", tron.normalize_address(a.contract) == a.contract, a.contract)
    hexc = tron.hex_contract(a.contract)
    urls = crypto.rpc_urls("tron")
    topics = [crypto.TRANSFER_TOPIC, None, tron.topic_for_address(TRON_ADDR)]
    working = 0
    for u in urls:
        host = u.split("//")[1]
        try:
            pool = evm.RpcPool([u], tron.TRON_CHAIN_ID, timeout=12, headers=crypto.rpc_headers())
            head = pool.block_number()
            pool.get_logs({"fromBlock": hex(head - 999), "toBlock": hex(head), "address": hexc, "topics": topics})
            working += 1
            print(f"  [ok]   {host}: chain 0x{tron.TRON_CHAIN_ID:x}, head {head}, getLogs(1000 blocks) accepted")
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {host}: {str(exc)[:90]}")
    check("tron: at least one endpoint serves the Tron chain id + 1000-block getLogs", working >= 1, f"({working}/{len(urls)})")
    pool = evm.RpcPool(urls, tron.TRON_CHAIN_ID, timeout=12, headers=crypto.rpc_headers())
    head = pool.block_number()
    code = pool.call("eth_getCode", [hexc, "latest"])
    check("usdt-trc20: has contract code", code not in ("0x", ""))
    sym = _str(pool.eth_call(hexc, "0x95d89b41"))
    name = _str(pool.eth_call(hexc, "0x06fdde03"))
    dec = int(pool.eth_call(hexc, "0x313ce567"), 16)
    check("usdt-trc20: on-chain name/symbol/decimals match config", name.startswith("Tether USD") and sym == "USDT" and dec == 6 == a.decimals, f"({name!r}, {sym!r}, {dec})")
    bal = int(pool.eth_call(hexc, "0x70a08231" + tron.address_to_bytes(TRON_ADDR).hex().rjust(64, "0")), 16)
    print(f"      balance of the receiving address: {bal / 10**dec} {sym} (read-only)")
    logs: list = []
    for s in range(head - 5999, head + 1, 1000):
        logs += pool.get_logs({"fromBlock": hex(s), "toBlock": hex(min(s + 999, head)), "address": hexc, "topics": topics})
    print(f"      incoming USDT transfers in the last 6000 blocks (~{6000 * 3 // 3600} h): {len(logs)}")
    sample = pool.get_logs({"fromBlock": hex(head - 40), "toBlock": hex(head), "address": hexc, "topics": [crypto.TRANSFER_TOPIC]})
    good = False
    if sample:
        to_addr = tron.bytes_to_address(bytes.fromhex(sample[0]["topics"][2][2:])[-20:])
        got = parse_logs(sample, hexc, to_addr, "tron")
        good = bool(got) and got[0].value == int(sample[0]["data"], 16) and got[0].tx == sample[0]["transactionHash"][2:].lower()
        if got:
            print(f"      real transfer parsed: {got[0].value / 10**dec} USDT to {to_addr} (tx {got[0].tx[:12]}…)")
        rc = pool.receipt(sample[0]["transactionHash"])
        check("tron: receipt lookup by transaction id works", bool(rc and rc.get("logs")))
    check("usdt-trc20: log parser handles real Tron Transfer logs", good or not sample, f"({len(sample)} sample logs)")

    # ---------------------------------------------------------------- Bitcoin
    print("\n== Bitcoin on-chain")
    try:
        check("Bitcoin address passes bech32 checksum", btc.normalize_address(BTC_ADDR) == BTC_ADDR, BTC_ADDR)
    except ValueError as exc:
        check("Bitcoin address passes bech32 checksum", False, str(exc))
        return 1
    apis = crypto.btc_api_urls()
    up = 0
    for u in apis:
        try:
            tip = btc.EsploraPool([u], timeout=12).block_number()
            up += 1
            print(f"  [ok]   {u}: tip height {tip}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {u}: {str(exc)[:90]}")
    check("btc: at least one Esplora endpoint answers", up >= 1, f"({up}/{len(apis)})")
    ep = btc.EsploraPool(apis, timeout=12)
    tip = ep.block_number()
    txs = ep.address_txs(BTC_ADDR, tip - 150)
    print(f"      transactions of the receiving address in the last ~150 blocks (+ mempool): {len(txs)} (a fresh wallet has none)")
    # parser sanity against a real, busy transaction: the first tx of the newest block
    try:
        import httpx
        base = apis[0]
        h = httpx.get(f"{base}/blocks/tip/hash", timeout=12).text.strip()
        block_txs = httpx.get(f"{base}/block/{h}/txs/0", timeout=12).json()
        t = next(x for x in block_txs if len(x.get("vout", [])) >= 2 and x["vout"][0].get("scriptpubkey_address"))
        to = t["vout"][0]["scriptpubkey_address"]
        got = parse_btc_txs([ep.tx(t["txid"]) or t], to, tip)
        check("btc: output parser reads a real mainnet transaction", bool(got) and got[0].value == t["vout"][0]["value"] and got[0].tx == t["txid"], f"(tx {t['txid'][:12]}…, {got[0].value if got else '?'} sats)")
    except Exception as exc:  # noqa: BLE001
        print(f"  [skip] real-transaction parse check: {str(exc)[:100]}")
    try:
        price, src = crypto.usd_price("BTC")
        check("btc: live USD price available (not the offline fallback)", src != "fallback" and price > 1000, f"(1 BTC = {price} USD via {src})")
    except Exception as exc:  # noqa: BLE001
        check("btc: live USD price available (not the offline fallback)", False, str(exc)[:100])
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
