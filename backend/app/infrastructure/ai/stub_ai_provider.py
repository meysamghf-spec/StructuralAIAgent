"""Stub AI provider for development and tests."""

from __future__ import annotations

import json

from app.domain.models.ai_gateway import (
    AICompletionRequest,
    AICompletionResponse,
    AIProviderKind,
)


class StubAIProvider:
    @property
    def provider_kind(self) -> AIProviderKind:
        return AIProviderKind.STUB

    def supports_model(self, model: str) -> bool:
        return bool(model)

    def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        last_user = next(
            (message.content for message in reversed(request.messages) if message.role.value == "user"),
            "",
        )
        structured = {
            "task_acknowledged": True,
            "model": request.model,
            "context_keys": sorted(request.context.keys()),
            "user_message_preview": last_user[:200],
        }
        return AICompletionResponse(
            provider=self.provider_kind,
            model=request.model,
            content=json.dumps(structured),
            structured_output=structured,
            metadata={"provider": "stub", "response_format": request.response_format},
        )
