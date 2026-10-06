"""OpenAI-compatible provider error handling without live network calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.application.exceptions import AIProviderRequestError
from app.domain.models.ai_gateway import AICompletionRequest, AIMessage, AIMessageRole
from app.infrastructure.ai.openai_compatible_provider import OpenAICompatibleProvider


def _request() -> AICompletionRequest:
    return AICompletionRequest(
        model="gpt-4o-mini",
        messages=[AIMessage(role=AIMessageRole.USER, content="extract the plot size")],
    )


def test_openai_compatible_provider_parses_usage() -> None:
    provider = OpenAICompatibleProvider(api_key="sk-test", max_retries=0)
    payload = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": "plot 12 by 22"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
    }
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    with patch("app.infrastructure.ai.openai_compatible_provider.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = response
        result = provider.complete(_request())
    assert result.content == "plot 12 by 22"
    assert result.metadata["total_tokens"] == 15
    assert result.provider.value == "OPENAI"


def test_openai_compatible_provider_timeout_raises() -> None:
    provider = OpenAICompatibleProvider(api_key="sk-test", max_retries=0, timeout_seconds=0.1)
    with patch("app.infrastructure.ai.openai_compatible_provider.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException(
            "timeout"
        )
        try:
            provider.complete(_request())
            raise AssertionError("expected timeout error")
        except AIProviderRequestError as exc:
            assert exc.status_code == 504
