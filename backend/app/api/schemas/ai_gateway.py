"""AI Gateway API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.ai_gateway import (
    AICompletionRequest,
    AICompletionResponse,
    AIMessage,
    AIMessageRole,
    AIProviderKind,
)


class AIMessageRequest(BaseModel):
    role: AIMessageRole
    content: str


class AICompletionRequestBody(BaseModel):
    model: str
    messages: list[AIMessageRequest]
    context: dict[str, Any] = Field(default_factory=dict)
    response_format: str | None = None
    provider: AIProviderKind | None = None

    def to_domain(self) -> AICompletionRequest:
        return AICompletionRequest(
            model=self.model,
            messages=[AIMessage(role=message.role, content=message.content) for message in self.messages],
            context=self.context,
            response_format=self.response_format,
        )


class AICompletionResponseBody(BaseModel):
    provider: str
    model: str
    content: str
    structured_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, response: AICompletionResponse) -> AICompletionResponseBody:
        return cls(
            provider=response.provider.value,
            model=response.model,
            content=response.content,
            structured_output=response.structured_output,
            metadata=response.metadata,
        )
