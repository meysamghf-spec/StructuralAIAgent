"""File-backed billing store (one JSON per account) under the file-storage volume."""
from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.infrastructure.config import get_settings

_LOCK = threading.RLock()


def _root() -> Path:
    p = get_settings().resolved_file_storage_root / "billing"
    (p / "accounts").mkdir(parents=True, exist_ok=True)
    return p


def _path(account_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.@-]", "_", account_id)[:120]
    return _root() / "accounts" / f"{safe}.json"


def _empty(account_id: str) -> dict[str, Any]:
    return {"account_id": account_id, "subscription": None, "history": [], "invoices": [], "usage": {}}


def load(account_id: str) -> dict[str, Any]:
    p = _path(account_id)
    if not p.exists():
        return _empty(account_id)
    return json.loads(p.read_text(encoding="utf-8"))


@contextmanager
def edit(account_id: str) -> Iterator[dict[str, Any]]:
    with _LOCK:
        data = load(account_id)
        yield data
        p = _path(account_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)


def index_invoice(invoice_id: str, account_id: str) -> None:
    with _LOCK:
        p = _root() / "invoice_index.json"
        idx = json.loads(p.read_text("utf-8")) if p.exists() else {}
        idx[invoice_id] = account_id
        p.write_text(json.dumps(idx), encoding="utf-8")


def account_for_invoice(invoice_id: str) -> str | None:
    p = _root() / "invoice_index.json"
    if not p.exists():
        return None
    return json.loads(p.read_text("utf-8")).get(invoice_id)
