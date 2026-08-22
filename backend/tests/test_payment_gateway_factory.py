"""Payment gateway factory and environment boundary tests."""

import pytest

from app.application.exceptions import PaymentConfigurationError
from app.infrastructure.config import Settings
from app.infrastructure.payments.mock_crypto_gateway import MockCryptoPaymentGateway
from app.infrastructure.payments.payment_factory import (
    create_crypto_payment_gateway,
    validate_payment_configuration,
)


def test_development_allows_mock_gateway() -> None:
    settings = Settings(
        app_env="development",
        crypto_payment_gateway="mock",
    )
    gateway = create_crypto_payment_gateway(settings)
    assert isinstance(gateway, MockCryptoPaymentGateway)


def test_production_rejects_mock_without_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        app_env="production",
        crypto_payment_gateway="mock",
        crypto_payment_allow_mock_in_production=False,
        auth_required=True,
        project_access_enforced=True,
        auth_allow_legacy_actor=False,
        entitlement_enforcement_enabled=True,
        auth_jwt_secret="production-test-secret-value",
        crypto_payment_webhook_secret="webhook-secret",
    )
    with pytest.raises(PaymentConfigurationError) as exc_info:
        validate_payment_configuration(settings)
    assert "Mock crypto payment gateway is not allowed in production" in str(exc_info.value)


def test_production_requires_btcpay_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        app_env="production",
        crypto_payment_gateway="btcpay",
        auth_required=True,
        project_access_enforced=True,
        auth_allow_legacy_actor=False,
        entitlement_enforcement_enabled=True,
        auth_jwt_secret="production-test-secret-value",
        file_storage_root="/tmp/structuralai-test-storage",
        crypto_payment_webhook_secret="webhook-secret",
    )
    with pytest.raises(PaymentConfigurationError) as exc_info:
        validate_payment_configuration(settings)
    assert "BTCPAY_SERVER_URL" in str(exc_info.value)


def test_unsupported_gateway_rejected() -> None:
    settings = Settings(
        app_env="development",
        crypto_payment_gateway="unknown-provider",
    )
    with pytest.raises(PaymentConfigurationError):
        create_crypto_payment_gateway(settings)
