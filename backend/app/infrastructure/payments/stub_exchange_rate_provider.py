"""Deterministic exchange rates for tests and offline development."""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.exceptions import UnsupportedPaymentCurrencyError
from app.domain.models.payments import ExchangeRateSnapshot

_FIXED_RATES_USD: dict[str, float] = {
    "BTC": 50_000.0,
    "ETH": 3_000.0,
    "USDT": 1.0,
}


class StubExchangeRateProvider:
    source_name = "stub-fixed-rates"

    def get_rate_usd(self, currency: str) -> ExchangeRateSnapshot:
        normalized = currency.upper()
        rate = _FIXED_RATES_USD.get(normalized)
        if rate is None:
            raise UnsupportedPaymentCurrencyError(normalized)
        return ExchangeRateSnapshot(
            source=self.source_name,
            currency=normalized,
            rate_usd=rate,
            captured_at=datetime.now(UTC),
        )
