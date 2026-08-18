"""AI Gateway domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AIProviderKind(StrEnum):
    STUB = "STUB"
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    LOCAL = "LOCAL"


class AIMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessage(BaseModel):
    role: AIMessageRole
    content: str


class AICompletionRequest(BaseModel):
    model: str
    messages: list[AIMessage]
    context: dict[str, Any] = Field(default_factory=dict)
    response_format: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AICompletionResponse(BaseModel):
    provider: AIProviderKind
    model: str
    content: str
    structured_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
