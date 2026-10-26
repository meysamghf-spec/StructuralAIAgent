"""SSE contract for incremental agent-run progress.

Events are a view of existing AgentExecutionRecord transitions.
They are not a second persistence model or orchestration pipeline.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

EVENT_STARTED = "agent_run.started"
EVENT_STEP = "agent_run.step"
EVENT_TOOL = "agent_run.tool"
EVENT_CONTEXT = "agent_run.context"
EVENT_VALIDATION = "agent_run.validation"
EVENT_APPROVAL_REQUIRED = "agent_run.approval_required"
EVENT_COMPLETED = "agent_run.completed"
EVENT_FAILED = "agent_run.failed"
EVENT_TOKEN = "agent_run.token"  # token-by-token text delta of a conversational (helper) reply: {"delta": "..."}

TERMINAL_EVENTS = frozenset({EVENT_COMPLETED, EVENT_FAILED, EVENT_APPROVAL_REQUIRED})


class AgentRunProgressSink(Protocol):
    def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...


class NoopAgentRunProgressSink:
    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        return None


def emit_progress(
    sink: AgentRunProgressSink | None,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    if sink is None:
        return
    sink.emit(event_type, payload)


def encode_sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def parse_sse_stream(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type = None
    data_lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.rstrip("\r")
        if line == "":
            if event_type and data_lines:
                raw = "\n".join(data_lines)
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    event_type = None
                    data_lines = []
                    continue
                if isinstance(parsed, dict):
                    events.append((event_type, parsed))
            event_type = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if event_type and data_lines:
        raw = "\n".join(data_lines)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return events
        if isinstance(parsed, dict):
            events.append((event_type, parsed))
    return events


def safe_stream_error(*, title: str, reason: str) -> dict[str, str]:
    cleaned = " ".join(reason.split())
    lowered = cleaned.lower()
    if "traceback" in lowered or "password" in lowered or "secret" in lowered or "token" in lowered:
        cleaned = "The agent could not complete this engineering step."
    return {"title": title, "reason": cleaned[:400]}
