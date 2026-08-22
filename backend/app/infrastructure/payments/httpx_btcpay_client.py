"""Live BTCPay Greenfield API client — non-custodial; uses store API key only."""

from __future__ import annotations

from typing import Any

import httpx


class HttpxBtcpayClient:
    """Calls BTCPay Server Greenfield REST API. Never handles private keys or seeds."""

    def __init__(
        self,
        *,
        server_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        base = server_url.rstrip("/")
        self._client = httpx.Client(
            base_url=f"{base}/api/v1",
            headers={
                "Authorization": f"token {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
        )

    def create_invoice(
        self,
        *,
        store_id: str,
        amount: str,
        currency: str,
        metadata: dict[str, Any],
        expiration_minutes: int,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/stores/{store_id}/invoices",
            json={
                "amount": amount,
                "currency": currency,
                "metadata": metadata,
                "checkout": {"expirationMinutes": expiration_minutes},
            },
        )
        response.raise_for_status()
        return response.json()

    def get_invoice(self, *, store_id: str, invoice_id: str) -> dict[str, Any]:
        response = self._client.get(f"/stores/{store_id}/invoices/{invoice_id}")
        response.raise_for_status()
        return response.json()

    def get_invoice_payment_methods(
        self, *, store_id: str, invoice_id: str
    ) -> list[dict[str, Any]]:
        response = self._client.get(
            f"/stores/{store_id}/invoices/{invoice_id}/payment-methods"
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return []

    def close(self) -> None:
        self._client.close()
