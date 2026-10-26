"""Project-level approval state derived from the real approval items (never hard-coded).

A project is "approved" when it has at least one engineering run and the latest revision of
every run chain is approved. Otherwise the blockers explain, in English and Persian, exactly
what is still needed.
"""
from __future__ import annotations

from typing import Any, Iterable


def _chains(requests: Iterable[Any]) -> list[list[Any]]:
    by_root: dict[str, list[Any]] = {}
    for req in requests:
        meta = getattr(req, "metadata", None) or {}
        if meta.get("module_kind") is None and getattr(req, "target_action", "") != "engineering_run":
            root = str(req.id)
        else:
            root = str(meta.get("root_approval_id") or req.id)
        by_root.setdefault(root, []).append(req)
    chains = []
    for items in by_root.values():
        items.sort(key=lambda r: int((getattr(r, "metadata", None) or {}).get("revision") or 1))
        chains.append(items)
    return chains


def _status(req: Any) -> str:
    value = getattr(req, "status", "")
    return str(getattr(value, "value", value))


def summarize(requests: list[Any]) -> dict[str, Any]:
    counts = {"pending": 0, "approved": 0, "rejected": 0, "cancelled": 0}
    for req in requests:
        key = _status(req).lower()
        if key in counts:
            counts[key] += 1
    blockers: list[dict[str, str]] = []
    chains = _chains(requests)
    if not chains:
        blockers.append({
            "code": "no_runs",
            "en": "No engineering run exists yet. Run an analysis or design in the chat; it creates an approval item automatically.",
            "fa": "هنوز هیچ تحلیل یا طراحی انجام نشده است. در چت یک تحلیل/طراحی اجرا کنید؛ مورد تأیید به‌صورت خودکار ساخته می‌شود.",
        })
    pending_chains = rejected_chains = approved_chains = 0
    for chain in chains:
        latest = _status(chain[-1])
        if latest == "APPROVED":
            approved_chains += 1
        elif latest == "PENDING":
            pending_chains += 1
        elif latest in ("REJECTED", "CANCELLED"):
            rejected_chains += 1
    if pending_chains:
        blockers.append({
            "code": "pending",
            "en": f"{pending_chains} item(s) are waiting for your approve/reject decision on the Approvals page.",
            "fa": f"{pending_chains} مورد منتظر تصمیم شما (تأیید یا رد) در صفحه تأییدها است.",
        })
    if rejected_chains:
        blockers.append({
            "code": "rejected",
            "en": f"{rejected_chains} run(s) were rejected and have no newer approved revision. Say what to change in chat and re-run.",
            "fa": f"{rejected_chains} اجرا رد شده و نسخه تأییدشده‌ی جدیدتری ندارد. در چت بگویید چه چیزی تغییر کند تا دوباره اجرا شود.",
        })
    if not blockers:
        state = "approved"
    elif counts["pending"] or pending_chains:
        state = "pending"
    elif rejected_chains:
        state = "needs_revision"
    else:
        state = "no_runs"
    return {
        "state": state,
        "project_approved": state == "approved",
        "counts": {**counts, "total": len(requests), "chains": len(chains)},
        "blockers": blockers,
    }
