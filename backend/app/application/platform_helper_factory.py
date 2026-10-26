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
            "faq_provider": lambda message, fa, ctx, allow_overview: pk.answer_faq(message, fa, ctx, allow_overview=allow_overview),
            "diagnose_provider": pk.diagnose_decision}

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


def report_engine_failure(exc: BaseException, *, account_id: str = "", project_id: str = "", conversation_id: str = "",
                          user_message: str = "", page: str = "chat") -> str | None:
    """Auto-file an unexpected engine exception (never an expected ApplicationError). Returns the issue id when it was filed
    (or already reported), else None. Never raises; records only, no code change."""
    try:
        import traceback

        frames = [f"{f.filename.split('backend/')[-1]}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__)[-3:]]
        issue = get_helper_service().auto_report(
            f"Unexpected engine failure: {type(exc).__name__}", error_text=f"{type(exc).__name__}: {exc}", page=page,
            account_id=account_id, project_id=project_id, conversation_id=conversation_id, user_message=user_message,
            severity="high", suspected_files=frames, codes=("ENGINE_FAILURE", type(exc).__name__))
        return issue.id if issue else None
    except Exception:  # noqa: BLE001 - reporting must never mask the original failure
        return None
