"""Platform health and readiness probes for deployment."""

from __future__ import annotations

from app.infrastructure.config import get_settings
from app.infrastructure.database.connection import get_connection


def get_health_status() -> dict[str, str]:
    """Liveness probe — process is running."""
    return {"status": "ok"}


def get_readiness_status() -> dict[str, object]:
    """Readiness probe — dependencies required to serve traffic."""
    settings = get_settings()
    checks: dict[str, object] = {
        "database": _check_database(),
        "payment_gateway": settings.crypto_payment_gateway,
        "app_env": settings.app_env,
    }
    ready = checks["database"] == "ok"
    if settings.is_production:
        ready = ready and settings.crypto_payment_gateway.strip().lower() == "btcpay"
    return {
        "status": "ready" if ready else "not_ready",
        "checks": checks,
    }


def _check_database() -> str:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return "ok"
    except Exception as exc:
        return f"error:{exc.__class__.__name__}"
