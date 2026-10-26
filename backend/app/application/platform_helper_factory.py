"""Process-wide HelperService wired to the Postgres issue store (lazy; tests can reset)."""

from __future__ import annotations

import threading

from app.infrastructure.repositories.postgres_platform_issue_repository import PostgresPlatformIssueRepository
from app.platform_helper.service import HelperService

_lock = threading.Lock()


def knowledge_hooks() -> dict:
    """Product knowledge injected into the (product-agnostic) helper: generated prompt block + static FAQ fallback."""
    from app.application import platform_knowledge as pk

    return {"knowledge_provider": lambda fa, message="": pk.build_platform_knowledge(fa, message),
            "faq_provider": lambda message, fa, ctx, allow_overview: pk.answer_faq(message, fa, ctx, allow_overview=allow_overview)}

_service: HelperService | None = None


def get_helper_service() -> HelperService:
    global _service
    with _lock:
        if _service is None:
            _service = HelperService(store=PostgresPlatformIssueRepository(), **knowledge_hooks())
        return _service


def reset_helper_service(service: HelperService | None = None) -> None:
    global _service
    with _lock:
        _service = service
