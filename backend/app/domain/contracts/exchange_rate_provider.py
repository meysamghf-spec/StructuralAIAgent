"""Exchange rate provider contract for fiat-to-crypto pricing snapshots."""

from __future__ import annotations

from typing import Protocol

from app.domain.models.payments import ExchangeRateSnapshot


class ExchangeRateProvider(Protocol):
    source_name: str

    def get_rate_usd(self, currency: str) -> ExchangeRateSnapshot:
        """Return USD price for one unit of the cryptocurrency."""
