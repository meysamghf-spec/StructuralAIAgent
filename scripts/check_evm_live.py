#!/usr/bin/env python
"""Read-only live check of the USDT/USDC payment setup on BNB Smart Chain, Polygon and Ethereum.

No keys, no transactions, no funds moved: only eth_chainId / eth_blockNumber / eth_call / eth_getCode / eth_getLogs.
Run from the repo root:   python scripts/check_evm_live.py [0xYourAddress]
Address defaults to CRYPTO_EVM_ADDRESS / CRYPTO_BSC_ADDRESS. Exit code 0 only if everything passed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.application.billing import crypto, evm  # noqa: E402
from app.application.billing.watcher import parse_logs  # noqa: E402

LIVE = ["usdt-bep20", "usdc-bep20", "usdt-polygon", "usdc-polygon", "usdt-erc20", "usdc-erc20"]
# What the contract itself must report (name prefix, symbol, decimals) - guards against typos and look-alike tokens
# (Polygon USDT is the canonical Tether token, upgraded in place to USDT0 in Aug 2025, same address) and look-alikes such as bridged USDC.e on Polygon (name "USD Coin (PoS)") which we deliberately do not accept.
EXPECT = {
    "usdt-bep20": ("Tether USD", "USDT", 18), "usdc-bep20": ("USD Coin", "USDC", 18),
    "usdt-polygon": ("USDT0", "USDT0", 6), "usdc-polygon": ("USD Coin", "USDC", 6),
    "usdt-erc20": ("Tether USD", "USDT", 6), "usdc-erc20": ("USD Coin", "USDC", 6),
}


def _str(hexdata: str) -> str:
    b = bytes.fromhex(hexdata[2:])
    if len(b) >= 64:  # ABI-encoded dynamic string
        n = int.from_bytes(b[32:64], "big")
        return b[64:64 + n].decode()
    return b.rstrip(b"\0").decode()


def main() -> int:
    addr_raw = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CRYPTO_EVM_ADDRESS") or os.environ.get("CRYPTO_BSC_ADDRESS") or "").strip()
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")

    try:
        addr = evm.normalize_address(addr_raw)
        check("receiving address has a valid EIP-55 checksum", True, addr)
    except ValueError as exc:
        check("receiving address has a valid EIP-55 checksum", False, str(exc))
        return 1
    topics = [crypto.TRANSFER_TOPIC, None, evm.topic_for_address(addr)]
    pools: dict[str, evm.RpcPool] = {}
    for chain in ("bsc", "polygon", "eth"):
        cid = crypto.EVM_CHAINS[chain]
        urls = crypto.rpc_urls(chain)
        print(f"\n== {crypto.CHAIN_LABEL[chain]} (chain id {cid}), {len(urls)} endpoints, "
              f"{crypto.confirmations(chain)} confirmations, ~{crypto.BLOCK_SECONDS[chain]} s blocks")
        contracts = [crypto.BY_ID[i].contract for i in LIVE if crypto.BY_ID[i].chain == chain]
        working = 0
        for u in urls:
            host = u.split("//")[1]
            try:
                pool = evm.RpcPool([u], cid, timeout=10)
                head = pool.block_number()
                pool.get_logs({"fromBlock": hex(head - 999), "toBlock": hex(head), "address": contracts[0], "topics": topics})
                working += 1
                print(f"  [ok]   {host}: chain {cid}, head {head}, getLogs(1000 blocks) accepted")
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {host}: {str(exc)[:90]}")
        check(f"{chain}: at least one endpoint serves chainId {cid} + 1000-block getLogs", working >= 1, f"({working}/{len(urls)})")
        pools[chain] = evm.RpcPool(urls, cid, timeout=10)

    for aid in LIVE:
        a = crypto.BY_ID[aid]
        pool = pools[a.chain]
        head = pool.block_number()
        want_name, want_sym, want_dec = EXPECT[aid]
        print(f"\n-- {aid}: {a.contract}")
        check(f"{aid}: contract address is EIP-55 checksummed", evm.to_checksum(a.contract) == a.contract)
        check(f"{aid}: has code on {a.chain}", pool.call("eth_getCode", [a.contract, "latest"]) not in ("0x", ""))
        name = _str(pool.eth_call(a.contract, "0x06fdde03"))
        sym = _str(pool.eth_call(a.contract, "0x95d89b41"))
        dec = int(pool.eth_call(a.contract, "0x313ce567"), 16)
        check(f"{aid}: on-chain name/symbol/decimals match expectation and config",
              name.startswith(want_name) and sym == want_sym and dec == want_dec == a.decimals, f"({name!r}, {sym!r}, {dec})")
        bal = int(pool.eth_call(a.contract, "0x70a08231" + addr[2:].lower().rjust(64, "0")), 16)
        print(f"      balance of the receiving address: {bal / 10**dec} {sym} (read-only)")
        windows = 6 if a.chain != "eth" else 2
        logs: list = []
        for s in range(head - windows * 1000 + 1, head + 1, 1000):
            logs += pool.get_logs({"fromBlock": hex(s), "toBlock": hex(min(s + 999, head)), "address": a.contract, "topics": topics})
        print(f"      incoming {sym} transfers in the last {windows * 1000} blocks: {len(logs)}")
        sample = pool.get_logs({"fromBlock": hex(head - 60), "toBlock": hex(head), "address": a.contract, "topics": [crypto.TRANSFER_TOPIC]})
        parsed_ok = False
        if sample:
            to_addr = evm.address_from_topic(sample[0]["topics"][2])
            got = parse_logs(sample, a.contract, to_addr)
            parsed_ok = bool(got) and got[0].tx == sample[0]["transactionHash"].lower() and got[0].value == int(sample[0]["data"], 16)
            print(f"      real transfer parsed: {got[0].value / 10**dec} {sym} to {to_addr}" if got else "")
        check(f"{aid}: log parser handles real Transfer logs", parsed_ok or not sample, f"({len(sample)} sample logs)")

    print("\n== the receiving address on each chain")
    for chain, pool in pools.items():
        code = pool.call("eth_getCode", [addr, "latest"])
        check(f"{chain}: address is a normal wallet (EOA), not a contract", code == "0x")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
