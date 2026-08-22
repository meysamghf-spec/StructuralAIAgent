"""CoinGecko exchange rate provider for live USD pricing snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.application.exceptions import PaymentConfigurationError
from app.domain.models.payments import ExchangeRateSnapshot

_COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
}


class CoinGeckoExchangeRateProvider:
    source_name = "coingecko"

    def __init__(self, *, api_base: str = "https://api.coingecko.com/api/v3", timeout_seconds: float = 15.0) -> None:
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout_seconds

    def get_rate_usd(self, currency: str) -> ExchangeRateSnapshot:
        coin_id = _COINGECKO_IDS.get(currency.upper())
        if coin_id is None:
            raise PaymentConfigurationError(f"Unsupported currency for live rates: {currency}")
        url = f"{self._api_base}/simple/price"
        response = httpx.get(
            url,
            params={"ids": coin_id, "vs_currencies": "usd"},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        rate = float(payload[coin_id]["usd"])
        return ExchangeRateSnapshot(
            source=self.source_name,
            currency=currency.upper(),
            rate_usd=rate,
            captured_at=datetime.now(UTC),
        )
