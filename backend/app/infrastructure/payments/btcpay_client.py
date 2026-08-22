"""HTTP client protocol for BTCPay Greenfield API — injectable for tests."""

from __future__ import annotations

from typing import Any, Protocol


class BtcpayClient(Protocol):
    def create_invoice(
        self,
        *,
        store_id: str,
        amount: str,
        currency: str,
        metadata: dict[str, Any],
        expiration_minutes: int,
    ) -> dict[str, Any]: ...

    def get_invoice(self, *, store_id: str, invoice_id: str) -> dict[str, Any]: ...

    def get_invoice_payment_methods(
        self, *, store_id: str, invoice_id: str
    ) -> list[dict[str, Any]]: ...
