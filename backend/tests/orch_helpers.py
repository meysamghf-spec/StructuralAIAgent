"""Scripted stand-in for Gemini: replays prepared assistant messages, no network."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.application.orchestrator.llm import OrchestratorUnavailable


def call(name: str, args: dict[str, Any] | None = None, cid: str | None = None) -> dict[str, Any]:
    return {"id": cid or f"call_{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args or {})}}


def tool_msg(*calls: dict[str, Any]) -> dict[str, Any]:
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def say(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": text}


Step = dict[str, Any] | Callable[[list[dict[str, Any]], str], dict[str, Any]] | Exception


class ScriptedLLM:
    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, tool_choice: str = "auto") -> dict[str, Any]:
        self.calls.append({"messages": json.loads(json.dumps(messages, default=str)), "tools": [t["function"]["name"] for t in tools], "tool_choice": tool_choice})
        if not self.steps:
            raise AssertionError("scripted model ran out of steps")
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        msg = step(messages, tool_choice) if callable(step) else step
        return {"message": msg, "provider": "scripted", "model": "scripted-1", "usage": {}}


def down() -> OrchestratorUnavailable:
    return OrchestratorUnavailable("scripted outage")


def tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m.get("role") == "tool":
            try:
                out.append(json.loads(m["content"]))
            except Exception:  # noqa: BLE001
                out.append({"raw": m["content"]})
    return out
