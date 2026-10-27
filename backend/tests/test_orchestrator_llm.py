"""LLMClient.chat_tools + the Gemini wrapper, against a mocked HTTP transport (no network)."""
from __future__ import annotations

import json

import httpx
import pytest

from app.application.orchestrator.config import OrchestratorSettings
from app.application.orchestrator.llm import GeminiToolLLM, OrchestratorUnavailable
from app.platform_helper.config import ProviderConfig
from app.platform_helper.llm import LLMClient, LLMUnavailableError

TOOL = {"type": "function", "function": {"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}}
MSG = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"},
                                                              "extra_content": {"google": {"thought_signature": "SIG"}}}]}


def client(handler, retries=0) -> LLMClient:
    p = ProviderConfig(name="gemini", base_url="https://example.test/v1beta/openai", model="m", api_key="k", keyless=False, timeout=5, max_tokens=100, temperature=0.2, extra_headers={})
    return LLMClient([p], transport=httpx.MockTransport(handler), sleep=lambda s: None, retries=retries)


def test_chat_tools_sends_tools_and_returns_the_message_verbatim() -> None:
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": MSG}], "usage": {"total_tokens": 5}})

    out = client(handler).chat_tools([{"role": "user", "content": "hi"}], [TOOL], tool_choice="auto")
    assert out["message"]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "SIG"
    assert seen["body"]["tools"] == [TOOL] and seen["body"]["tool_choice"] == "auto" and seen["body"]["stream"] is False
    assert seen["auth"] == "Bearer k"


def test_chat_tools_raises_when_the_provider_fails() -> None:
    with pytest.raises(LLMUnavailableError):
        client(lambda req: httpx.Response(500, json={"error": "x"})).chat_tools([{"role": "user", "content": "x"}], [TOOL])


def test_wrapper_converts_failures_and_opens_a_short_circuit_breaker() -> None:
    n = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(429, json={"error": {"message": "quota"}})

    llm = GeminiToolLLM(OrchestratorSettings(mode="always"), client=client(handler))
    with pytest.raises(OrchestratorUnavailable):
        llm.chat([{"role": "user", "content": "x"}], [TOOL])
    with pytest.raises(OrchestratorUnavailable):
        llm.chat([{"role": "user", "content": "x"}], [TOOL])
    assert n["calls"] == 1  # the second call is skipped while the breaker is open: no 25 s wait per message during an outage


def test_wrapper_without_a_key_is_unavailable_not_an_error() -> None:
    llm = GeminiToolLLM(OrchestratorSettings(mode="always"), env={})
    assert not llm.configured
    with pytest.raises(OrchestratorUnavailable):
        llm.chat([{"role": "user", "content": "x"}], [TOOL])
