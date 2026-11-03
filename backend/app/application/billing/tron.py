"""Tron helpers for watch-only USDT (TRC20) detection: base58check addresses and the log-topic form.

Tron nodes expose an Ethereum-compatible JSON-RPC (``/jsonrpc``): eth_blockNumber, eth_getLogs,
eth_getTransactionReceipt, eth_getBlockByNumber. A Tron address is 0x41 + the same 20 bytes an EVM address has,
base58check encoded; in logs and topics only the 20 bytes appear. No private key and no API key are needed.
"""
from __future__ import annotations

import hashlib

TRON_CHAIN_ID = 0x2B6653DC          # eth_chainId of Tron mainnet (728126428)
_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        i = _ALPHABET.find(ch)
        if i < 0:
            raise ValueError("Invalid character in Tron address.")
        n = n * 58 + i
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + raw


def _b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _ALPHABET[r] + out
    return "1" * (len(b) - len(b.lstrip(b"\x00"))) + out


def _checksum(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]


def address_to_bytes(address: str) -> bytes:
    """The 20 account bytes of a valid Tron mainnet address (T...). Raises ValueError otherwise."""
    a = (address or "").strip()
    if len(a) != 34 or not a.startswith("T"):
        raise ValueError("A Tron address starts with T and has 34 characters.")
    raw = _b58decode(a)
    if len(raw) != 25 or raw[0] != 0x41:
        raise ValueError("Not a Tron mainnet address.")
    if _checksum(raw[:21]) != raw[21:]:
        raise ValueError("Invalid Tron address checksum: the address has a typo.")
    return raw[1:21]


def normalize_address(address: str) -> str:
    address_to_bytes(address)
    return address.strip()


def bytes_to_address(b20: bytes) -> str:
    payload = b"\x41" + b20
    return _b58encode(payload + _checksum(payload))


def hex_contract(address: str) -> str:
    """Contract address in the form JSON-RPC logs use: 0x + 20 bytes (lowercase)."""
    return "0x" + address_to_bytes(address).hex()


def topic_for_address(address: str) -> str:
    return "0x" + address_to_bytes(address).hex().rjust(64, "0")


def address_from_topic(topic: str) -> str:
    return bytes_to_address(bytes.fromhex(topic[-40:]))
