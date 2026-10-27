"""Minimal EVM helpers for watch-only payment detection: EIP-55 addresses and a failover JSON-RPC pool.

No private key, no web3 dependency. Only read-only JSON-RPC methods are ever called
(eth_chainId, eth_blockNumber, eth_getLogs, eth_getTransactionReceipt, eth_getBlockByNumber, eth_call).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- keccak-256 (pure python)
_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    n %= 64
    return ((x << n) | (x >> (64 - n))) & _M if n else x


def _f(a: list[list[int]]) -> None:
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x][y] ^= d[x]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rol(a[x][y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                a[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y])
        a[0][0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136
    msg = bytearray(data)
    msg.append(0x01)
    while len(msg) % rate:
        msg.append(0)
    msg[-1] |= 0x80
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        _f(a)
    out = b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out[:32]


# --------------------------------------------------------------------------- EIP-55 addresses
def to_checksum(address: str) -> str:
    h = address.lower().removeprefix("0x")
    if len(h) != 40 or any(c not in "0123456789abcdef" for c in h):
        raise ValueError("Not a 20-byte hex address (expected 0x + 40 hex characters).")
    digest = keccak256(h.encode("ascii")).hex()
    return "0x" + "".join(c.upper() if int(digest[i], 16) >= 8 else c for i, c in enumerate(h))


def normalize_address(address: str) -> str:
    """Return the EIP-55 checksummed address. All-lowercase / all-uppercase input is accepted;
    mixed case must carry a valid checksum (catches typos). Raises ValueError otherwise."""
    a = (address or "").strip()
    if not a.startswith(("0x", "0X")):
        raise ValueError("Address must start with 0x.")
    body = a[2:]
    checksummed = to_checksum(a)
    if body != body.lower() and body != body.upper() and "0x" + body != checksummed:
        raise ValueError("Invalid EIP-55 checksum: the address has a typo (or wrong capitalisation).")
    if int(body, 16) == 0:
        raise ValueError("The zero address cannot receive payments.")
    return checksummed


def topic_for_address(address: str) -> str:
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


def address_from_topic(topic: str) -> str:
    return to_checksum("0x" + topic[-40:])


# --------------------------------------------------------------------------- JSON-RPC pool
class RpcError(RuntimeError):
    pass


class RpcPool:
    """Tries each endpoint in order (starting at the last one that worked) and fails over on any
    transport error, HTTP error, JSON-RPC error or wrong chain id."""

    def __init__(self, urls: list[str], chain_id: int | None = None, timeout: float = 10.0) -> None:
        if not urls:
            raise RpcError("No RPC endpoints configured.")
        self.urls = urls
        self.chain_id = chain_id
        self.timeout = timeout
        self._good = 0
        self._lock = threading.Lock()
        self._checked: set[str] = set()

    def _post(self, url: str, method: str, params: list[Any]) -> Any:
        r = httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        if body.get("error"):
            raise RpcError(f"{method}: {body['error'].get('message', body['error'])}")
        if "result" not in body:
            raise RpcError(f"{method}: malformed response")
        return body["result"]

    def call(self, method: str, params: list[Any] | None = None) -> Any:
        params = params or []
        errors: list[str] = []
        n = len(self.urls)
        for i in range(n):
            idx = (self._good + i) % n
            url = self.urls[idx]
            try:
                if self.chain_id is not None and url not in self._checked:
                    cid = int(self._post(url, "eth_chainId", []), 16)
                    if cid != self.chain_id:
                        raise RpcError(f"wrong chain id {cid}")
                    self._checked.add(url)
                res = self._post(url, method, params)
                with self._lock:
                    self._good = idx
                return res
            except Exception as exc:  # noqa: BLE001 - fail over to the next endpoint
                errors.append(f"{url.split('//')[-1].split('/')[0]}: {str(exc)[:80]}")
                time.sleep(0)
        raise RpcError("All RPC endpoints failed: " + " | ".join(errors))

    # ---- convenience
    def block_number(self) -> int:
        return int(self.call("eth_blockNumber"), 16)

    def get_logs(self, flt: dict[str, Any]) -> list[dict[str, Any]]:
        return self.call("eth_getLogs", [flt])

    def receipt(self, tx_hash: str) -> dict[str, Any] | None:
        return self.call("eth_getTransactionReceipt", [tx_hash])

    def block_timestamp(self, number: int) -> int:
        blk = self.call("eth_getBlockByNumber", [hex(number), False]) or {}
        return int(blk.get("timestamp", "0x0"), 16)

    def eth_call(self, to: str, data: str) -> str:
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])
