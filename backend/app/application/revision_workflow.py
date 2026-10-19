"""Shared approval / revision workflow for every engineering module (see engineering_modules.ModuleAdapter).

1. create_run_approval: after a completed run (chat or manual), create a pending approval item (revision 1).
2. handle_rejection: the (required) reject reason is parsed with the shared assumptions parser + the module's
   design-change intents; changes are applied, the module is re-run and a NEW approval (revision N+1) is created
   that links to the rejected one, with a diff summary. Unparseable reasons -> a clarification question.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application import engineering_modules as em
from app.domain.models.human_approval import ApprovalTargetType

TARGET_ACTION = "engineering_run.approval"


def create_run_approval(approval_service: Any, project_id: UUID, requester: str, payload: dict[str, Any], *,
                        revision: int = 1, parent_id: str | None = None, root_id: str | None = None,
                        changes: list[dict[str, Any]] | None = None, reason: str | None = None,
                        conversation_id: str | None = None) -> Any | None:
    adapter = em.adapter_for(payload.get("kind"))
    if adapter is None or not adapter.completed(payload):
        return None
    inputs = {k: v for k, v in (payload.get("inputs") or {}).items() if k not in ("provided",)}
    summary = adapter.summary(payload)
    if revision > 1:
        summary = f"Rev {revision}: {summary}"
    return approval_service.create_request(
        project_id, requester=requester, target_type=ApprovalTargetType.DESIGN_DECISION, target_action=TARGET_ACTION,
        summary=summary,
        metadata={"module_kind": adapter.kind, "module_label": adapter.label, "inputs": inputs, "revision": revision,
                  "parent_approval_id": parent_id, "root_approval_id": root_id, "changes": changes or [],
                  "change_reason": reason, "conversation_id": conversation_id, "status_of_run": payload.get("status")},
    )


def handle_rejection(approval_service: Any, project_id: UUID, rejected: Any, reason: str, actor: str) -> dict[str, Any]:
    """-> {"outcome": "revised", "approval": new} | {"outcome": "clarify", "message": ...} | {"outcome": "not_applicable"}."""
    meta = dict(getattr(rejected, "metadata", None) or {})
    adapter = em.adapter_for(meta.get("module_kind"))
    if adapter is None or getattr(rejected, "target_action", None) != TARGET_ACTION:
        return {"outcome": "not_applicable"}
    inputs = dict(meta.get("inputs") or {})
    inp, a, errors = em.parse_changes(adapter, reason, inputs)
    if not inp and not a:
        keys = ", ".join(s.label_en or s.key for m in adapter.assumption_modules for s in __import__(
            "app.application.assumptions_registry", fromlist=["specs"]).specs(m))[:400]
        msg = ("I could not turn the rejection reason into a change. Please say what to change, e.g. "
               "'increase column size', 'column 50x50', 'use Φ20', 'drift too high', 'cover 50 mm', or any of: " + keys
               + "\n— دلیل رد را به تغییر مشخصی تبدیل نکردم؛ لطفاً بنویسید چه چیزی تغییر کند (مثلاً «ابعاد ستون را افزایش بده»، «ستون ۵۰×۵۰»، «با Φ20»، «پوشش ۵۰ میلی‌متر»).")
        if errors:
            msg = "\n".join(errors) + "\n" + msg
        return {"outcome": "clarify", "message": msg}
    new_inputs = em.apply_changes(inputs, inp, a)
    payload = adapter.run(new_inputs)
    changes = em.diff(inputs, new_inputs)
    revision = int(meta.get("revision") or 1) + 1
    new = create_run_approval(approval_service, project_id, actor, payload, revision=revision,
                              parent_id=str(rejected.id), root_id=meta.get("root_approval_id") or str(rejected.id),
                              changes=changes, reason=reason, conversation_id=meta.get("conversation_id"))
    if new is None:
        return {"outcome": "clarify", "message": f"The revised run did not complete ({payload.get('status')}): {payload.get('message', '')}"}
    return {"outcome": "revised", "approval": new, "changes": changes, "warnings": errors}
