"""The real PlatformPort: ConversationService + the current conversation + the authenticated account.

Ownership is enforced here: only projects ``list_accessible_projects(account)`` returns can be listed or opened, and every
engineering operation works on the chat's own conversation/project."""

from __future__ import annotations

import logging
from typing import Any

from app.application.billing import service as billing

logger = logging.getLogger(__name__)


class ConversationPort:
    def __init__(self, service: Any, conversation: Any, account: Any, user_message: str = "") -> None:
        self._svc, self.conversation, self._account, self._user_message = service, conversation, account, user_message
        self.account_id = str(account.account_id)
        self.conversation_id = str(conversation.id)
        self.project: dict[str, str] | None = None
        if conversation.project_id is not None:
            name = next((p.name for p in self._accessible() if str(p.id) == str(conversation.project_id)), "")
            self.project = {"id": str(conversation.project_id), "name": name or "selected"}

    def _accessible(self) -> list[Any]:
        return list(self._svc._project_access.list_accessible_projects(self._account))

    # ------------------------------------------------------------------ projects
    def list_projects(self) -> list[dict[str, str]]:
        return [{"id": str(p.id), "name": p.name} for p in self._accessible()]

    def open_project(self, project_id: str) -> dict[str, str]:
        hit = next((p for p in self._accessible() if str(p.id) == str(project_id)), None)
        if hit is None:  # ownership check: never open something that is not in the account's accessible list
            raise PermissionError("project is not accessible to this account")
        conv = self._svc._repo.set_project(self.conversation.id, hit.id)
        self.conversation = conv or self.conversation.model_copy(update={"project_id": hit.id})
        self.project = {"id": str(hit.id), "name": hit.name}
        return dict(self.project)

    def create_project(self, name: str) -> dict[str, str]:
        from app.application.service_factory import build_project_service

        projects = self._accessible()
        owned = sum(1 for p in projects if str(getattr(p, "owner_account_id", "")) == self.account_id)
        billing.require_count(self.account_id, "projects", owned)
        result = build_project_service().create_project(name=name, description=None, created_by=self.account_id, owner_account_id=self.account_id)
        conv = self._svc._repo.set_project(self.conversation.id, result.project.id)
        self.conversation = conv or self.conversation.model_copy(update={"project_id": result.project.id})
        self.project = {"id": str(result.project.id), "name": result.project.name}
        return dict(self.project)

    # ------------------------------------------------------------------ model / plan
    def latest_frame_inputs(self) -> dict[str, Any] | None:
        newest: tuple[str, dict[str, Any]] | None = None
        try:  # a compound turn (analyze + optimize) keeps its model in orchestrator metadata, newest message wins
            for m in reversed(self._svc._repo.list_messages(self.conversation.id)):
                model = (m.metadata.get("orchestrator") or {}).get("model") if isinstance(m.metadata, dict) else None
                if isinstance(model, dict) and model:
                    newest = (m.created_at.isoformat(), model)
                    break
        except Exception:  # noqa: BLE001
            logger.debug("orchestrator model lookup failed", exc_info=True)
        base = self._svc._latest_frame_inputs(self.conversation, self._account)
        if newest is None:
            return base
        if base is None:
            return newest[1]
        # _latest_frame_inputs does not expose its timestamp; the orchestrator model is the newer one when it is in the latest messages
        return newest[1] if self._orchestrator_is_latest() else base

    def _orchestrator_is_latest(self) -> bool:
        for m in reversed(self._svc._repo.list_messages(self.conversation.id)):
            md = m.metadata if isinstance(m.metadata, dict) else {}
            if (md.get("orchestrator") or {}).get("model"):
                return True
            res = md.get("engineering_results")
            if isinstance(res, dict) and res.get("kind") == "frame3d_analysis":
                return False
        return False

    def plan_exports(self) -> Any:
        return self._svc._plan_exports(self._account)

    def check_frame_size(self, inputs: dict[str, Any]) -> None:
        billing.check_frame_size(self.account_id, inputs)

    def consume_analysis(self) -> None:
        billing.consume(self.account_id, "analyses_per_month")

    def require_optimization(self) -> None:
        billing.require_feature(self.account_id, "optimization")

    def usage_snapshot(self) -> dict[str, Any]:
        try:
            from app.application.platform_knowledge import user_context

            return user_context(self.account_id, project=(self.project or {}).get("name"))
        except Exception:  # noqa: BLE001
            return {}

    def pending_approvals(self) -> list[str]:
        if self.project is None:
            return []
        try:
            from uuid import UUID

            from app.application.service_factory import build_human_approval_service

            return [str(r.summary)[:160] for r in build_human_approval_service().list_pending(UUID(self.project["id"]))][:10]
        except Exception:  # noqa: BLE001
            return []

    def report_failure(self, exc: BaseException) -> None:
        from app.application.platform_helper_factory import report_engine_failure

        report_engine_failure(exc, account_id=self.account_id, project_id=(self.project or {}).get("id", ""),
                              conversation_id=self.conversation_id, user_message=self._user_message[:500], page="chat/orchestrator")

    # ------------------------------------------------------------------ pending confirmation (previous assistant message)
    def pending_confirmation(self) -> dict[str, Any] | None:
        """The destructive call the LAST assistant message asked the user to confirm (only if it is the very last message)."""
        try:
            msgs = [m for m in self._svc._repo.list_messages(self.conversation.id) if getattr(m.role, "value", m.role) != "system"]
        except Exception:  # noqa: BLE001
            return None
        # the new user message may already be stored: skip trailing user messages, look at the assistant one before it
        for m in reversed(msgs):
            if getattr(m.role, "value", m.role) == "user":
                continue
            md = m.metadata if isinstance(m.metadata, dict) else {}
            pend = (md.get("orchestrator") or {}).get("pending")
            return pend if isinstance(pend, dict) and pend.get("tool") else None
        return None
