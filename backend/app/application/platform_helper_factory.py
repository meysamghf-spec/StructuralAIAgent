"""Process-wide HelperService wired to the Postgres issue store (lazy; tests can reset)."""

from __future__ import annotations

import threading

from app.infrastructure.repositories.postgres_platform_issue_repository import PostgresPlatformIssueRepository
from app.platform_helper.service import HelperService

_lock = threading.Lock()
_service: HelperService | None = None


def get_helper_service() -> HelperService:
    global _service
    with _lock:
        if _service is None:
            _service = HelperService(store=PostgresPlatformIssueRepository())
        return _service


def reset_helper_service(service: HelperService | None = None) -> None:
    global _service
    with _lock:
        _service = service
