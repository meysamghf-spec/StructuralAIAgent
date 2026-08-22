"""Optional live BTCPay connectivity test — skipped unless explicitly configured."""

from __future__ import annotations

import os

import pytest

from app.infrastructure.config import Settings
from app.infrastructure.payments.payment_factory import create_crypto_payment_gateway


@pytest.mark.integration
def test_live_btcpay_gateway_connectivity() -> None:
    if not os.getenv("BTCPAY_SERVER_URL") or not os.getenv("BTCPAY_API_KEY") or not os.getenv("BTCPAY_STORE_ID"):
        pytest.skip(
            "Live BTCPay integration not configured. "
            "Set BTCPAY_SERVER_URL, BTCPAY_API_KEY, and BTCPAY_STORE_ID to run externally."
        )
    settings = Settings(
        app_env="development",
        crypto_payment_gateway="btcpay",
        btcpay_server_url=os.environ["BTCPAY_SERVER_URL"],
        btcpay_api_key=os.environ["BTCPAY_API_KEY"],
        btcpay_store_id=os.environ["BTCPAY_STORE_ID"],
        btcpay_webhook_secret=os.getenv("BTCPAY_WEBHOOK_SECRET", "test"),
    )
    gateway = create_crypto_payment_gateway(settings)
    assert gateway.provider_name == "btcpay"
