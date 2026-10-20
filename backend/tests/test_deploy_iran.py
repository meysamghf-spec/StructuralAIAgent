"""Production settings for the Iran free-launch deployment and migration tracking helpers."""

from __future__ import annotations

import pytest

from app.infrastructure.config import Settings
from app.infrastructure.database.migrations import pending_migrations

BASE = dict(
    app_env="production", auth_required=True, project_access_enforced=True, auth_allow_legacy_actor=False,
    auth_jwt_secret="x" * 48, file_storage_root="/data/files", cors_origins="https://sazeh.example.ir",
    database_url="postgresql://app:pw@db:5432/structuralaiaagent", trust_proxy_headers=True, trusted_proxy_hosts="172.16.0.0/12",
)


def test_iran_free_launch_settings_pass_validation():
    s = Settings(**BASE, payments_enabled=False, entitlement_enforcement_enabled=False,
                 ai_provider="stub", ai_allow_deterministic_in_production=True)
    s.validate_security_configuration()


def test_production_still_rejects_insecure_or_unflagged_settings():
    from app.application.exceptions import SecurityConfigurationError

    with pytest.raises(SecurityConfigurationError):
        Settings(**BASE, ai_provider="stub").validate_security_configuration()
    with pytest.raises(SecurityConfigurationError):
        Settings(**{**BASE, "auth_jwt_secret": "dev-only-auth-secret-change-me"}, payments_enabled=False,
                 ai_allow_deterministic_in_production=True).validate_security_configuration()
    with pytest.raises(SecurityConfigurationError):
        Settings(**{**BASE, "cors_origins": "*"}, payments_enabled=False,
                 ai_allow_deterministic_in_production=True).validate_security_configuration()


def test_pending_migrations_in_order_and_skips_applied():
    files = ["010_b.sql", "001_a.sql", "002_c.sql"]
    assert pending_migrations(files, set()) == ["001_a.sql", "002_c.sql", "010_b.sql"]
    assert pending_migrations(files, {"001_a.sql"}) == ["002_c.sql", "010_b.sql"]
