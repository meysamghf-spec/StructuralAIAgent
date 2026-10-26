"""System prompt assembly from the maintained knowledge file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DEFAULT = Path(__file__).parent / "knowledge" / "structuralai.md"


@lru_cache(maxsize=8)
def load_knowledge(path: str | None = None) -> str:
    p = Path(path) if path else _DEFAULT
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return "You are a helpful assistant for a structural engineering platform."


def build_system_prompt(*, knowledge_path: str | None = None, context: dict[str, str] | None = None, lang: str = "fa",
                        extra_knowledge: str = "") -> str:
    """Hand-written rules + (optional) generated product facts + the live per-user session context."""
    ctx = "\n".join(f"- {k}: {v}" for k, v in (context or {}).items() if v)
    head = "Reply in Persian (فارسی)." if lang == "fa" else "Reply in English."
    extra = f"\n\n{extra_knowledge.strip()}" if extra_knowledge and extra_knowledge.strip() else ""
    return f"{load_knowledge(knowledge_path)}{extra}\n\n## Current session (this user, live)\n{ctx or '- (no project selected)'}\n\n{head}"
