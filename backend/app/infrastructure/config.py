from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _env_files() -> tuple[str, ...]:
    root = _repo_root()
    return (
        str(root / ".env"),
        str(root / "backend" / ".env"),
    )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_port: int = 8000
    database_url: str = "postgresql://postgres@127.0.0.1:5432/structuralaiaagent"
    postgres_password: SecretStr | None = None
    test_database_url: str | None = None
    file_storage_root: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024
    auto_index_files: bool = False

    crypto_payment_gateway: str = "mock"
    crypto_payment_allow_mock_in_production: bool = False
    crypto_payment_webhook_secret: SecretStr | None = None
    exchange_rate_provider: str = "stub"
    btcpay_server_url: str = ""
    btcpay_api_key: SecretStr | None = None
    btcpay_store_id: str = ""
    btcpay_webhook_secret: SecretStr | None = None

    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    run_migrations_on_startup: bool = False
    trust_proxy_headers: bool = False

    auth_required: bool = False
    auth_allow_legacy_actor: bool = True
    auth_jwt_secret: SecretStr | None = None
    auth_token_expiry_hours: int = 24
    project_access_enforced: bool = False
    entitlement_enforcement_enabled: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def validate_security_configuration(self) -> None:
        """Reject insecure production configuration at startup."""
        if not self.is_production:
            return
        issues: list[str] = []
        if not self.auth_required:
            issues.append("AUTH_REQUIRED must be true in production")
        if not self.project_access_enforced:
            issues.append("PROJECT_ACCESS_ENFORCED must be true in production")
        if not self.entitlement_enforcement_enabled:
            issues.append("ENTITLEMENT_ENFORCEMENT_ENABLED must be true in production")
        if self.auth_allow_legacy_actor:
            issues.append("AUTH_ALLOW_LEGACY_ACTOR must be false in production")
        if self.auth_jwt_secret is None:
            issues.append("AUTH_JWT_SECRET must be configured in production")
        dev_secret = "dev-only-auth-secret-change-me"
        if self.auth_jwt_secret is not None and self.auth_jwt_secret.get_secret_value() == dev_secret:
            issues.append("AUTH_JWT_SECRET must not use the development default in production")
        if issues:
            from app.application.exceptions import SecurityConfigurationError

            raise SecurityConfigurationError(
                "Insecure production security configuration",
                issues=issues,
            )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return value

    @property
    def effective_test_database_url(self) -> str:
        return self.test_database_url or self.resolved_database_url

    @property
    def resolved_database_url(self) -> str:
        """Return DATABASE_URL with password supplied via POSTGRES_PASSWORD when needed."""
        if self.postgres_password is None:
            return self.database_url

        from urllib.parse import quote, urlparse, urlunparse

        password = quote(self.postgres_password.get_secret_value(), safe="")
        parsed = urlparse(self.database_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5432
        username = parsed.username or "postgres"
        netloc = f"{username}:{password}@{host}:{port}"
        return urlunparse(parsed._replace(netloc=netloc))

    @property
    def resolved_file_storage_root(self) -> Path:
        if self.file_storage_root.strip():
            return Path(self.file_storage_root).expanduser().resolve()
        return (_repo_root().parent / "structuralaiaagent_file_storage").resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_security_configuration()
    if settings.is_production:
        from app.infrastructure.payments.payment_factory import validate_payment_configuration

        validate_payment_configuration(settings)
    return settings
