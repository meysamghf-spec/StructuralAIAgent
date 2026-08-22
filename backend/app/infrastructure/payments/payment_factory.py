"""Payment gateway and exchange-rate factory with environment boundary enforcement."""

from __future__ import annotations

from app.application.exceptions import PaymentConfigurationError
from app.domain.contracts.crypto_payment_gateway import CryptoPaymentGateway
from app.domain.contracts.exchange_rate_provider import ExchangeRateProvider
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.payments.btcpay_crypto_gateway import BtcpayCryptoPaymentGateway
from app.infrastructure.payments.coingecko_exchange_rate_provider import CoinGeckoExchangeRateProvider
from app.infrastructure.payments.httpx_btcpay_client import HttpxBtcpayClient
from app.infrastructure.payments.mock_crypto_gateway import MockCryptoPaymentGateway
from app.infrastructure.payments.stub_exchange_rate_provider import StubExchangeRateProvider


def validate_payment_configuration(settings: Settings | None = None) -> None:
    """Fail fast when production payment settings are unsafe or incomplete."""
    settings = settings or get_settings()
    gateway = settings.crypto_payment_gateway.strip().lower()
    env = settings.app_env.strip().lower()

    if env == "production":
        if gateway == "mock" and not settings.crypto_payment_allow_mock_in_production:
            raise PaymentConfigurationError(
                "Mock crypto payment gateway is not allowed in production. "
                "Set CRYPTO_PAYMENT_GATEWAY=btcpay and configure BTCPay credentials."
            )
        if gateway == "btcpay":
            _require_btcpay_settings(settings, production=True)
        if settings.crypto_payment_webhook_secret is None:
            raise PaymentConfigurationError(
                "CRYPTO_PAYMENT_WEBHOOK_SECRET must be configured in production."
            )
        return

    if gateway == "btcpay":
        _require_btcpay_settings(settings, production=False)


def _require_btcpay_settings(settings: Settings, *, production: bool) -> None:
    missing: list[str] = []
    if not settings.btcpay_server_url.strip():
        missing.append("BTCPAY_SERVER_URL")
    if settings.btcpay_api_key is None:
        missing.append("BTCPAY_API_KEY")
    if not settings.btcpay_store_id.strip():
        missing.append("BTCPAY_STORE_ID")
    if production and settings.btcpay_webhook_secret is None:
        missing.append("BTCPAY_WEBHOOK_SECRET")
    if missing:
        raise PaymentConfigurationError(
            "BTCPay payment gateway requires configuration: " + ", ".join(missing)
        )


def create_crypto_payment_gateway(settings: Settings | None = None) -> CryptoPaymentGateway:
    settings = settings or get_settings()
    validate_payment_configuration(settings)
    gateway_name = settings.crypto_payment_gateway.strip().lower()

    if gateway_name == "mock":
        webhook_secret = "test-webhook-secret"
        if settings.crypto_payment_webhook_secret is not None:
            webhook_secret = settings.crypto_payment_webhook_secret.get_secret_value()
        return MockCryptoPaymentGateway(webhook_secret=webhook_secret)

    if gateway_name == "btcpay":
        assert settings.btcpay_api_key is not None
        webhook_secret = "unset"
        if settings.btcpay_webhook_secret is not None:
            webhook_secret = settings.btcpay_webhook_secret.get_secret_value()
        elif settings.crypto_payment_webhook_secret is not None:
            webhook_secret = settings.crypto_payment_webhook_secret.get_secret_value()
        client = HttpxBtcpayClient(
            server_url=settings.btcpay_server_url,
            api_key=settings.btcpay_api_key.get_secret_value(),
        )
        return BtcpayCryptoPaymentGateway(
            client=client,
            store_id=settings.btcpay_store_id,
            webhook_secret=webhook_secret,
        )

    raise PaymentConfigurationError(
        f"Unsupported CRYPTO_PAYMENT_GATEWAY '{settings.crypto_payment_gateway}'. "
        "Use 'mock' for development/test or 'btcpay' for production."
    )


def create_exchange_rate_provider(settings: Settings | None = None) -> ExchangeRateProvider:
    settings = settings or get_settings()
    provider = settings.exchange_rate_provider.strip().lower()
    if provider == "coingecko":
        return CoinGeckoExchangeRateProvider()
    return StubExchangeRateProvider()
