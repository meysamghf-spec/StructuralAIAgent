"""Bitcoin on-chain helpers for watch-only payment detection (no key, no node, no API key).

* Receiving-address validation: bech32 / bech32m (BIP-173/350) and legacy base58check, mainnet only.
* ``EsploraPool``: read-only client for the Esplora REST API that mempool.space and blockstream.info both serve,
  with automatic failover between base URLs (configurable, e.g. a self-hosted instance).
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if (top >> i) & 1 else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _convertbits(data: list[int], frm: int, to: int, pad: bool) -> list[int] | None:
    acc = bits = 0
    ret: list[int] = []
    maxv = (1 << to) - 1
    for v in data:
        if v < 0 or v >> frm:
            return None
        acc = (acc << frm) | v
        bits += frm
        while bits >= to:
            bits -= to
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to - bits)) & maxv)
    elif bits >= frm or ((acc << (to - bits)) & maxv):
        return None
    return ret


def _segwit_ok(addr: str) -> bool:
    if addr != addr.lower() and addr != addr.upper():
        return False
    a = addr.lower()
    if not a.startswith("bc1") or len(a) < 14 or len(a) > 90 or any(ord(c) < 33 or ord(c) > 126 for c in a):
        return False
    data_part = a[3:]
    if any(c not in _CHARSET for c in data_part):
        return False
    data = [_CHARSET.find(c) for c in data_part]
    const = _polymod(_hrp_expand("bc") + data)
    ver = data[0]
    if (ver == 0 and const != 1) or (ver != 0 and const != 0x2BC830A3):
        return False
    prog = _convertbits(data[1:-6], 5, 8, False)
    if prog is None or not 2 <= len(prog) <= 40 or ver > 16:
        return False
    return not (ver == 0 and len(prog) not in (20, 32))


def _base58_ok(addr: str) -> bool:
    n = 0
    for ch in addr:
        i = _B58.find(ch)
        if i < 0:
            return False
        n = n * 58 + i
    raw = n.to_bytes(25, "big") if n.bit_length() <= 200 else b""
    if len(raw) != 25 or raw[0] not in (0x00, 0x05):
        return False
    return hashlib.sha256(hashlib.sha256(raw[:21]).digest()).digest()[:4] == raw[21:]


def normalize_address(address: str) -> str:
    """Return the address in canonical form (bech32 lowercase); raises ValueError for anything that is not a valid mainnet address."""
    a = (address or "").strip()
    if a[:3].lower() == "bc1":
        if not _segwit_ok(a):
            raise ValueError("Invalid Bitcoin bech32 address (checksum or format error): the address has a typo.")
        return a.lower()
    if a[:1] in ("1", "3") and _base58_ok(a):
        return a
    raise ValueError("Not a valid Bitcoin mainnet address (expected bc1..., 1... or 3...).")


class EsploraError(RuntimeError):
    pass


class EsploraPool:
    """Esplora REST client with failover. Only read-only GETs. Base URLs look like https://mempool.space/api."""

    def __init__(self, urls: list[str], timeout: float = 10.0) -> None:
        if not urls:
            raise EsploraError("No Bitcoin explorer API endpoints configured.")
        self.urls = [u.rstrip("/") for u in urls]
        self.timeout = timeout
        self._good = 0
        self._lock = threading.Lock()

    def _get(self, path: str, *, text: bool = False) -> Any:
        errors: list[str] = []
        n = len(self.urls)
        for i in range(n):
            idx = (self._good + i) % n
            url = self.urls[idx]
            try:
                r = httpx.get(url + path, timeout=self.timeout, headers={"User-Agent": "structuralai-payments/1.0"})
                if r.status_code == 404:
                    raise LookupError(path)
                r.raise_for_status()
                with self._lock:
                    self._good = idx
                return r.text.strip() if text else r.json()
            except LookupError:
                raise
            except Exception as exc:  # noqa: BLE001 - fail over to the next endpoint
                errors.append(f"{url.split('//')[-1].split('/')[0]}: {str(exc)[:80]}")
        raise EsploraError("All Bitcoin API endpoints failed: " + " | ".join(errors))

    def block_number(self) -> int:
        return int(self._get("/blocks/tip/height", text=True))

    def address_txs(self, address: str, stop_height: int, max_pages: int = 6) -> list[dict[str, Any]]:
        """Unconfirmed + confirmed transactions touching the address, newest first, until older than stop_height."""
        out: list[dict[str, Any]] = []
        page = self._get(f"/address/{address}/txs")
        for _ in range(max_pages):
            out += page
            confirmed = [t for t in page if t.get("status", {}).get("confirmed")]
            if len(confirmed) < 25 or not confirmed:
                break
            last = confirmed[-1]
            if int(last["status"].get("block_height", 0)) < stop_height:
                break
            page = self._get(f"/address/{address}/txs/chain/{last['txid']}")
            if not page:
                break
        return out

    def tx(self, txid: str) -> dict[str, Any] | None:
        try:
            return self._get(f"/tx/{txid}")
        except LookupError:
            return None

    def block_timestamp(self, number: int) -> int:
        try:
            tip = self.block_number()
            if number > tip:
                return int(time.time())
            h = self._get(f"/block-height/{number}", text=True)
            return int(self._get(f"/block/{h}")["timestamp"])
        except LookupError:
            return 0
