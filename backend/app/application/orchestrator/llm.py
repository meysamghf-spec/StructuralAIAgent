"""Model access for the orchestrator: one tool-calling client (Gemini by default) with a tiny circuit breaker.

The client is injectable (``set_llm_for_tests``) so every test and replay runs with a scripted model and no network."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Mapping
from typing import Any, Protocol

from app.application.orchestrator.config import OrchestratorSettings
from app.platform_helper.config import _provider_from_preset
from app.platform_helper.llm import LLMClient, LLMError, LLMUnavailableError


class OrchestratorUnavailable(Exception):
    """The model could not be used (not configured / rate limited / down / circuit open). Callers fall back to the rule-based path."""


class ToolLLM(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, tool_choice: str = "auto") -> dict[str, Any]: ...


_BREAKER_SECONDS = 20.0
_RATE_LIMIT_SECONDS = 60.0


class GeminiToolLLM:
    """OpenAI-compatible function calling (Gemini's /v1beta/openai endpoint). The assistant message is returned verbatim
    (Gemini 3 needs its ``thought_signature`` echoed back with the tool results)."""

    def __init__(self, settings: OrchestratorSettings, env: Mapping[str, str] | None = None, client: LLMClient | None = None) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._blocked_until = 0.0
        if client is not None:
            self._client = client
            return
        env = env if env is not None else os.environ
        p = _provider_from_preset(settings.provider, env, timeout=settings.call_timeout_s, max_tokens=settings.max_tokens,
                                  temperature=0.2, model_override=settings.model)
        self._client = LLMClient([p] if p else [], retries=0)

    @property
    def configured(self) -> bool:
        return self._client.configured

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *, tool_choice: str = "auto") -> dict[str, Any]:
        if not self._client.configured:
            raise OrchestratorUnavailable("no API key configured for the orchestrator model")
        with self._lock:
            if time.monotonic() < self._blocked_until:
                raise OrchestratorUnavailable("model temporarily skipped after a recent failure")
        try:
            return self._client.chat_tools(messages, tools, tool_choice=tool_choice)
        except (LLMUnavailableError, LLMError) as exc:
            limited = any("429" in e or "rate" in e.lower() for e in self._client.last_errors)
            with self._lock:
                self._blocked_until = time.monotonic() + (_RATE_LIMIT_SECONDS if limited else _BREAKER_SECONDS)
            raise OrchestratorUnavailable(str(exc)[:200]) from exc


_llm: ToolLLM | None = None
_override: ToolLLM | None = None


def get_llm(settings: OrchestratorSettings) -> ToolLLM:
    global _llm
    if _override is not None:
        return _override
    if _llm is None or getattr(_llm, "_settings", settings) != settings:
        _llm = GeminiToolLLM(settings)
    return _llm


def set_llm_for_tests(llm: ToolLLM | None) -> None:
    global _override, _llm
    _override, _llm = llm, None
