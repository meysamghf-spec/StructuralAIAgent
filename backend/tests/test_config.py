import pytest

from app.infrastructure.config import Settings, get_settings


def test_settings_load_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@db.example:5432/testdb")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.database_url == "postgresql://user@db.example:5432/testdb"


def test_resolved_database_url_uses_postgres_password(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/structuralaiaagent")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-value")
    get_settings.cache_clear()
    settings = Settings()
    resolved = settings.resolved_database_url
    assert "secret-value" in resolved
    assert resolved.startswith("postgresql://postgres:")
    assert resolved.endswith("@127.0.0.1:5432/structuralaiaagent")


def test_effective_test_database_url_prefers_test_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/structuralaiaagent")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/structuralaiaagent_test")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.effective_test_database_url.endswith("/structuralaiaagent_test")


def test_effective_test_database_url_falls_back_to_resolved_database_url(monkeypatch) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/structuralaiaagent")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret-value")
    get_settings.cache_clear()
    settings = Settings()
    assert "secret-value" in settings.effective_test_database_url


def test_default_database_name_is_structuralaiaagent(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    settings = Settings()
    assert settings.database_url.endswith("/structuralaiaagent")


def test_settings_never_embeds_hardcoded_secrets_in_code() -> None:
    """Defaults omit password; production/local must override via env or .env."""
    settings = Settings(
        database_url="postgresql://postgres@127.0.0.1:5432/structuralaiaagent",
        postgres_password=None,
    )
    user_part = settings.database_url.split("//", 1)[1].split("@", 1)[0]
    assert user_part == "postgres"
    assert settings.postgres_password is None


def test_production_requires_file_storage_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "false")
    monkeypatch.setenv("AUTH_JWT_SECRET", "production-test-secret-value")
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "true")
    monkeypatch.delenv("FILE_STORAGE_ROOT", raising=False)
    get_settings.cache_clear()
    from app.application.exceptions import SecurityConfigurationError

    with pytest.raises(SecurityConfigurationError) as exc_info:
        get_settings()
    assert "FILE_STORAGE_ROOT must be configured in production" in exc_info.value.details["issues"]
    get_settings.cache_clear()


def test_production_rejects_mock_payment_gateway_without_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    monkeypatch.setenv("AUTH_ALLOW_LEGACY_ACTOR", "false")
    monkeypatch.setenv("AUTH_JWT_SECRET", "production-test-secret-value")
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("FILE_STORAGE_ROOT", "/tmp/structuralai-test-storage")
    monkeypatch.setenv("CRYPTO_PAYMENT_GATEWAY", "mock")
    monkeypatch.delenv("CRYPTO_PAYMENT_ALLOW_MOCK_IN_PRODUCTION", raising=False)
    get_settings.cache_clear()
    from app.application.exceptions import PaymentConfigurationError
    from app.application.service_factory import get_crypto_payment_gateway

    import app.application.service_factory as factory

    factory._payment_gateway_instance = None
    try:
        with pytest.raises(PaymentConfigurationError):
            get_crypto_payment_gateway()
    finally:
        factory._payment_gateway_instance = None
        get_settings.cache_clear()
