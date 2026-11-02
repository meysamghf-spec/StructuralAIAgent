"""Per-project chat memory: everything said in ALL conversations of one project, isolated per project.

The block built here is added to the model prompt (helper, orchestrator and general chat paths) for chats that belong to a
project. It has three parts, all bounded by a character budget (~4 chars per token):

1. Key facts: the project's structured memory items (model inputs, results, decisions, assumptions...).
2. Rolling summary: older turns of the project's other conversations, compressed into short lines. It is persisted as one
   project-memory item (source_type ``project_chat_summary``) and updated incrementally: only turns newer than the
   ``covered_until`` timestamp are appended; when it grows past its budget the oldest lines are dropped.
3. Recent turns of the project's other conversations, verbatim (newest first until the budget is used).

The current conversation's own recent messages are still passed as normal chat history by the caller.
General (no project) chats never get this block: they keep their own conversation history only.
Isolation: only conversations with the same ``project_id`` AND the same account are read, and only memory of that project.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.models.project_memory import MemoryType

logger = logging.getLogger(__name__)

SUMMARY_SOURCE = "project_chat_summary"
FACTS_BUDGET = 3000
SUMMARY_BUDGET = 6000
RECENT_BUDGET = 12000
TOTAL_BUDGET = FACTS_BUDGET + SUMMARY_BUDGET + RECENT_BUDGET  # ~21k chars ≈ 5-6k tokens
MAX_CONVERSATIONS = 200
MAX_MESSAGES_PER_CONVERSATION = 500
_FACT_TYPES = [t for t in MemoryType if t != MemoryType.CONVERSATION]


def _role(m) -> str:
    return str(getattr(m.role, "value", m.role)).lower()


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _ts(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")


def collect_project_turns(repo, account_id: str, project_id: UUID, *, exclude_conversation_id: UUID | None = None) -> list[dict]:
    """All user/assistant messages of the account's conversations in this project, oldest first."""
    turns: list[dict] = []
    for conv in repo.list_for_account(account_id, limit=MAX_CONVERSATIONS, project_id=project_id):
        if conv.project_id is None or str(conv.project_id) != str(project_id):
            continue  # defensive: never mix projects even if a repository ignores the filter
        if exclude_conversation_id is not None and str(conv.id) == str(exclude_conversation_id):
            continue
        for m in repo.list_messages(conv.id, limit=MAX_MESSAGES_PER_CONVERSATION):
            role = _role(m)
            if role not in ("user", "assistant") or not (m.content or "").strip():
                continue
            turns.append({"conversation_id": str(conv.id), "title": conv.title or "", "role": role,
                          "content": m.content, "created_at": m.created_at})
    turns.sort(key=lambda t: _ts(t["created_at"]))
    return turns


def _line(t: dict) -> str:
    who = "U" if t["role"] == "user" else "A"
    return f"[{_clip(t['title'], 40) or 'chat'}] {who}: {_clip(t['content'], 240 if who == 'U' else 160)}"


def _load_summary(memory, project_id: UUID):
    try:
        items = memory.retrieve_memories(project_id, source_type=SUMMARY_SOURCE)
    except Exception:  # noqa: BLE001
        logger.debug("summary lookup failed", exc_info=True)
        return None
    items = [i for i in items if str(i.project_id) == str(project_id)]
    return max(items, key=lambda i: _ts(i.updated_at or i.created_at)) if items else None


def update_rolling_summary(memory, project_id: UUID, older: list[dict], account_id: str | None = None) -> str:
    """Append turns newer than covered_until to the persisted summary; trim the oldest lines to the budget."""
    current = _load_summary(memory, project_id)
    text = current.content if current else ""
    covered = (current.metadata or {}).get("covered_until", "") if current else ""
    new = [t for t in older if _ts(t["created_at"]) > covered]
    if not new:
        return text
    lines = [ln for ln in text.splitlines() if ln.strip()] + [_line(t) for t in new]
    while lines and sum(len(ln) + 1 for ln in lines) > SUMMARY_BUDGET:
        lines.pop(0)
    text = "\n".join(lines)
    try:
        if current is not None:
            memory.delete_memory(project_id, current.id)
        memory.create_memory(project_id, MemoryType.CONVERSATION, text, source_type=SUMMARY_SOURCE,
                             metadata={"covered_until": _ts(new[-1]["created_at"]), "kind": SUMMARY_SOURCE},
                             created_by=account_id)
    except Exception:  # noqa: BLE001 - memory persistence is best effort
        logger.warning("could not persist project chat summary", exc_info=True)
    return text


def key_facts(memory, project_id: UUID) -> list[str]:
    try:
        items = [i for i in memory.list_memories(project_id)
                 if i.memory_type in _FACT_TYPES and str(i.project_id) == str(project_id)
                 and (i.source_type or "") != SUMMARY_SOURCE]
    except Exception:  # noqa: BLE001
        return []
    items.sort(key=lambda i: _ts(i.created_at), reverse=True)
    out: list[str] = []
    used = 0
    for i in items:
        line = f"- ({i.memory_type.value}) {_clip(i.content, 400)}"
        if used + len(line) > FACTS_BUDGET:
            break
        out.append(line)
        used += len(line) + 1
    return out


def build_project_memory(repo, memory, account_id: str, project_id: UUID, *, current_conversation_id: UUID | None = None,
                         project_name: str | None = None, current_history: int = 20) -> dict[str, Any]:
    """Return {"text": prompt block, "stats": {...}} for one project. Empty text when there is nothing to remember."""
    turns = collect_project_turns(repo, account_id, project_id)
    cur = str(current_conversation_id) if current_conversation_id is not None else None
    # the current chat's last messages already go to the model as normal history
    window = {id(t) for t in [t for t in turns if t["conversation_id"] == cur][-current_history:]}
    recent: list[dict] = []
    used = 0
    for t in reversed(turns):
        if t["conversation_id"] == cur:
            continue
        cost = len(t["content"]) + 60
        if used + cost > RECENT_BUDGET:
            break
        recent.append(t)
        used += cost
    recent.reverse()
    cutoff = _ts(recent[0]["created_at"]) if recent else None
    rids = {id(t) for t in recent}
    older = [t for t in turns if id(t) not in window and id(t) not in rids and (cutoff is None or _ts(t["created_at"]) < cutoff)]
    summary = update_rolling_summary(memory, project_id, older, account_id) if older else (
        (s.content if (s := _load_summary(memory, project_id)) else ""))
    facts = key_facts(memory, project_id)
    parts: list[str] = []
    if facts:
        parts.append("Key project facts (newest first):\n" + "\n".join(facts))
    if summary:
        parts.append("Summary of earlier conversations in this project:\n" + summary)
    if recent:
        parts.append("Recent messages from the project's other conversations (verbatim):\n" + "\n".join(
            f"[{_clip(t['title'], 40) or 'chat'}] {'User' if t['role'] == 'user' else 'Assistant'}: {t['content'][:2500]}"
            for t in recent))
    text = ""
    if parts:
        head = (f"PROJECT MEMORY for project “{project_name or project_id}”. Use it to remember what the user said in this "
                "project's other chats. It belongs only to this project; never mention it for another project.")
        text = (head + "\n\n" + "\n\n".join(parts))[:TOTAL_BUDGET]
    return {"text": text, "stats": {"conversations": len({t['conversation_id'] for t in turns if t['conversation_id'] != cur}), "messages": len(turns),
                                    "recent_verbatim": len(recent), "summarized": len(older), "facts": len(facts),
                                    "summary_chars": len(summary), "chars": len(text)}}
