"""AI provider contract for provider-agnostic AI Gateway."""

from __future__ import annotations

from typing import Protocol

from app.domain.models.ai_gateway import AICompletionRequest, AICompletionResponse, AIProviderKind


class AIProvider(Protocol):
    @property
    def provider_kind(self) -> AIProviderKind: ...

    def complete(self, request: AICompletionRequest) -> AICompletionResponse: ...

    def supports_model(self, model: str) -> bool: ...
