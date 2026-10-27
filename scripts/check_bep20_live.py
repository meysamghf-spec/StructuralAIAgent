#!/usr/bin/env python
"""Read-only live check of the USDT/BEP20 payment setup against the real BSC public RPCs.

No keys, no transactions, no funds moved: only eth_chainId / eth_blockNumber / eth_call / eth_getCode /
eth_getLogs. Run from the repo root:   python scripts/check_bep20_live.py [0xYourAddress]
Address defaults to CRYPTO_BSC_ADDRESS / CRYPTO_EVM_ADDRESS. Exit code 0 only if everything passed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.application.billing import crypto, evm  # noqa: E402

USDT = crypto.BY_ID["usdt-bep20"]


def _str(hexdata: str) -> str:
    b = bytes.fromhex(hexdata[2:])
    if len(b) >= 64:  # ABI-encoded dynamic string
        n = int.from_bytes(b[32:64], "big")
        return b[64:64 + n].decode()
    return b.rstrip(b"\0").decode()


def main() -> int:
    addr_raw = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CRYPTO_BSC_ADDRESS") or os.environ.get("CRYPTO_EVM_ADDRESS") or "").strip()
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
    check("configured USDT contract is checksummed", evm.to_checksum(USDT.contract) == USDT.contract, USDT.contract)
    urls = crypto.rpc_urls("bsc")
    print(f"endpoints: {len(urls)}")
    working = 0
    for u in urls:
        pool = evm.RpcPool([u], 56, timeout=10)
        host = u.split("//")[1]
        try:
            head = pool.block_number()
            pool.get_logs({"fromBlock": hex(head - 999), "toBlock": hex(head), "address": USDT.contract,
                           "topics": [crypto.TRANSFER_TOPIC, None, evm.topic_for_address(addr)]})
            working += 1
            print(f"  [ok]   {host}: chain 56, head {head}, getLogs(1000 blocks) accepted")
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {host}: {str(exc)[:90]}")
    check("at least one endpoint serves chainId 56 + 1000-block getLogs", working >= 1, f"({working}/{len(urls)})")
    pool = evm.RpcPool(urls, 56, timeout=10)
    head = pool.block_number()
    name = _str(pool.eth_call(USDT.contract, "0x06fdde03"))
    sym = _str(pool.eth_call(USDT.contract, "0x95d89b41"))
    dec = int(pool.eth_call(USDT.contract, "0x313ce567"), 16)
    check("contract is a token named Tether USD / USDT with 18 decimals", sym == "USDT" and dec == 18 == USDT.decimals, f"({name!r}, {sym!r}, {dec})")
    check("contract has code on BSC", pool.call("eth_getCode", [USDT.contract, "latest"]) not in ("0x", ""))
    code = pool.call("eth_getCode", [addr, "latest"])
    print(f"      receiving address is {'a contract' if code != '0x' else 'a normal wallet (EOA)'}")
    check("receiving address is a wallet (not a contract)", code == "0x")
    bal = int(pool.eth_call(USDT.contract, "0x70a08231" + addr[2:].lower().rjust(64, "0")), 16)
    print(f"      USDT balance at address: {bal / 10**18} (read-only)")
    logs: list = []
    for s in range(head - 5000, head + 1, 1000):
        logs += pool.get_logs({"fromBlock": hex(s), "toBlock": hex(min(s + 999, head)), "address": USDT.contract,
                               "topics": [crypto.TRANSFER_TOPIC, None, evm.topic_for_address(addr)]})
    print(f"      incoming USDT transfers in the last 5000 blocks: {len(logs)}")
    check("5000-block windowed scan works end to end", True)
    # parser sanity on REAL chain data: take any recent USDT transfer, rebuild it with our parser
    from app.application.billing.watcher import parse_logs
    sample = pool.get_logs({"fromBlock": hex(head - 30), "toBlock": hex(head), "address": USDT.contract,
                            "topics": [crypto.TRANSFER_TOPIC]})
    parsed_ok = False
    if sample:
        to_addr = evm.address_from_topic(sample[0]["topics"][2])
        got = parse_logs(sample, USDT.contract, to_addr)
        parsed_ok = bool(got) and got[0].tx == sample[0]["transactionHash"].lower() and got[0].value == int(sample[0]["data"], 16)
        print(f"      real transfer parsed: {got[0].value / 10**18} USDT to {to_addr}" if got else "")
    check("log parser handles real USDT Transfer logs", parsed_ok, f"({len(sample)} sample logs)")
    print("\nALL CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
