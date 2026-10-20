"""Chat flow for importing a plan drawing (PNG/JPG/PDF/DXF) as a DRAFT frame model.

1. Attach a plan + ask to import it  -> draft extracted, preview + confidence shown, approval 'Imported model review' (rev 1).
2. Chat edits while it is pending      -> the draft is revised, the old item is cancelled, a new revision is created.
   Rejecting the item with a reason    -> the shared revision_workflow applies the same edits (plan_import adapter).
3. Analysis requests are blocked while a draft is pending; after approval 'analyze the imported model' runs the
   existing 3D frame analysis / design / DXF pipeline on the imported grid (unequal spans supported).
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any
from uuid import UUID

from app.application import plan_import, revision_workflow
from app.domain.models.human_approval import ApprovalStatus

logger = logging.getLogger(__name__)

PLAN_EXT = ("png", "jpg", "jpeg", "pdf", "dxf")
_IMPORT_RE = re.compile(r"plan|grid|axis|axes|import|layout|extract|پلان|محور|نقشه|وارد|استخراج|مدل", re.I)
_ANALYZE_IMPORTED_RE = re.compile(
    r"(analy[sz]e|design|run|تحلیل|طراحی).{0,40}(imported|import|draft|وارد\s*شده|ایمپورت|پیش\s*‌?نویس)|"
    r"(imported|وارد\s*شده).{0,40}(analy[sz]e|design|تحلیل|طراحی)", re.I)


def _lang(text: str) -> str:
    return "fa" if re.search(r"[\u0600-\u06FF]", text or "") else "en"


def _plan_attachments(attachments: list[Any]) -> list[Any]:
    return [a for a in attachments or [] if str(getattr(a, "filename", "")).lower().rsplit(".", 1)[-1] in PLAN_EXT]


def wants_import(text: str, attachments: list[Any]) -> bool:
    return bool(_plan_attachments(attachments)) and bool(_IMPORT_RE.search(text or ""))


def _latest(approval_service: Any, project_id: UUID, status: ApprovalStatus | None) -> Any | None:
    items = [r for r in approval_service.list_requests(project_id, status=status)
             if (r.metadata or {}).get("module_kind") == "plan_import"
             and r.target_action == revision_workflow.TARGET_ACTION]
    return max(items, key=lambda r: r.created_at) if items else None


def _result(p: dict[str, Any], lang: str, approval: Any | None, extra: str = "") -> tuple[str, dict[str, Any]]:
    png = plan_import.preview_png(p["draft"])
    p = {**p, "preview_png": "data:image/png;base64," + base64.b64encode(png).decode()}
    meta: dict[str, Any] = {"mode": "plan_import", "engineering_results": p}
    if approval is not None:
        meta["run_approval_id"] = str(approval.id)
        meta["plan_import_approval_created"] = True
    return (extra + plan_import.markdown(p, lang)).strip(), meta


def handle_chat(*, project_id: UUID, conversation_id: UUID, actor: str, text: str, attachments: list[Any],
                read_file, approval_service: Any) -> tuple[str, dict[str, Any]] | None:
    """-> (assistant markdown, metadata) when the message is a plan-import step, else None (normal orchestration)."""
    lang = _lang(text)
    plans = _plan_attachments(attachments)
    if plans and wants_import(text, attachments):
        a = plans[0]
        try:
            data = read_file(a.file_id)
            draft = plan_import.extract(data, a.filename, text)
        except Exception as exc:  # noqa: BLE001 - tell the engineer instead of failing the chat
            logger.info("plan import failed: %s", exc)
            msg = (f"I could not extract a grid from **{a.filename}**: {exc}. Clear plans with straight grid lines work "
                   "best (vector PDF/DXF preferred). / استخراج محورها از این فایل ممکن نشد؛ فایل PDF یا DXF برداری بهتر است.")
            return msg, {"mode": "plan_import", "plan_import_error": str(exc)}
        old = _latest(approval_service, project_id, ApprovalStatus.PENDING)
        if old is not None:
            approval_service.cancel_request(project_id, old.id, actor=actor, reason="superseded by a new plan import")
        p = plan_import.payload(draft)
        approval = revision_workflow.create_run_approval(approval_service, project_id, actor, p,
                                                         conversation_id=str(conversation_id))
        return _result(p, lang, approval)

    pending = _latest(approval_service, project_id, ApprovalStatus.PENDING)
    if pending is not None and not plans and plan_import.is_edit(text):
        meta = pending.metadata or {}
        draft, done = plan_import.apply_edits((meta.get("inputs") or {})["draft"], text)
        if not done:
            return None
        rev = int(meta.get("revision") or 1) + 1
        p = plan_import.payload(draft, revision=rev, edits=done)
        approval_service.cancel_request(project_id, pending.id, actor=actor, reason="revised from chat: " + "; ".join(done))
        approval = revision_workflow.create_run_approval(
            approval_service, project_id, actor, p, revision=rev, parent_id=str(pending.id),
            root_id=meta.get("root_approval_id") or str(pending.id), reason=text, conversation_id=str(conversation_id),
            changes=[{"key": "edit", "old": None, "new": d} for d in done])
        return _result(p, lang, approval, f"Applied / اعمال شد: {'; '.join(done)} (revision {rev})\n\n")

    if _ANALYZE_IMPORTED_RE.search(text or "") and not plans:
        if pending is not None:
            return ("The imported model is still a **DRAFT**. Approve **Imported model review** on the Approvals page "
                    "(or edit it here) before analysis.\n— مدل وارد شده هنوز پیش‌نویس است؛ ابتدا آیتم «بررسی مدل وارد شده» "
                    "را در صفحه تأییدها تأیید کنید.", {"mode": "plan_import", "blocked": "imported model not approved",
                                                      "pending_approval_id": str(pending.id)})
        approved = _latest(approval_service, project_id, ApprovalStatus.APPROVED)
        if approved is None:
            return None
        from app.application.frame3d_chat_analysis import build_frame3d_payload, frame3d_markdown

        fi = plan_import.frame_inputs(((approved.metadata or {}).get("inputs") or {})["draft"])
        fi["lang"] = lang
        payload = build_frame3d_payload(text, manual_inputs=fi) or {}
        payload["imported_from_approval_id"] = str(approved.id)
        return frame3d_markdown(payload), {"mode": "plan_import_analysis", "engineering_results": payload}
    return None


def approved_message(approval: Any) -> str | None:
    """Chat note posted when an 'Imported model review' item is approved."""
    meta = approval.metadata or {}
    if meta.get("module_kind") != "plan_import":
        return None
    d = (meta.get("inputs") or {}).get("draft") or {}
    return (f"✅ Imported model approved (revision {meta.get('revision', 1)}): spans X {d.get('spans_x_m')} m, "
            f"Y {d.get('spans_y_m')} m, {d.get('storeys') or 1} storey(s). Ask **analyze the imported model** to run "
            "the 3D analysis, design and drawings.\n— مدل وارد شده تأیید شد؛ برای تحلیل، طراحی و نقشه‌ها بنویسید "
            "«مدل وارد شده را تحلیل کن».")
