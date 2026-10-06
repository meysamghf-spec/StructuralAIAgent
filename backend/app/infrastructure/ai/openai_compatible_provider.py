"""OpenAI-compatible chat completions provider. API keys come from settings only."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.application.exceptions import AIProviderRequestError
from app.domain.models.ai_gateway import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderKind,
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        api_base: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout_seconds
        self._max_retries = max(0, max_retries)

    @property
    def provider_kind(self) -> AIProviderKind:
        return AIProviderKind.OPENAI

    def supports_model(self, model: str) -> bool:
        return bool(model.strip())

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model.strip() or self._default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role.value, "content": message.content}
                for message in request.messages
            ],
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        last_error: str | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(
                        f"{self._api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                if response.status_code in {429, 500, 502, 503} and attempt < self._max_retries:
                    time.sleep(0.4 * (attempt + 1))
                    last_error = f"HTTP {response.status_code}"
                    continue
                if response.status_code >= 400:
                    raise AIProviderRequestError(
                        provider=self.provider_kind.value,
                        message=f"OpenAI-compatible provider returned HTTP {response.status_code}",
                        status_code=502,
                    )
                data = response.json()
                content = _extract_content(data)
                usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                structured = _try_parse_json(content) if request.response_format == "json" else None
                return AICompletionResponse(
                    provider=self.provider_kind,
                    model=str(data.get("model") or model),
                    content=content,
                    structured_output=structured,
                    metadata={
                        "provider": "openai_compatible",
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "attempts": attempt + 1,
                    },
                )
            except AIProviderRequestError:
                raise
            except httpx.TimeoutException as exc:
                last_error = str(exc)
                if attempt >= self._max_retries:
                    raise AIProviderRequestError(
                        provider=self.provider_kind.value,
                        message="OpenAI-compatible provider timed out",
                        status_code=504,
                    ) from exc
                time.sleep(0.4 * (attempt + 1))
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt >= self._max_retries:
                    raise AIProviderRequestError(
                        provider=self.provider_kind.value,
                        message="OpenAI-compatible provider request failed",
                        status_code=502,
                    ) from exc
                time.sleep(0.4 * (attempt + 1))

        raise AIProviderRequestError(
            provider=self.provider_kind.value,
            message=last_error or "OpenAI-compatible provider request failed",
            status_code=502,
        )


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "")


def _try_parse_json(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
