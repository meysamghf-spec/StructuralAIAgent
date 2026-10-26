"""Unified chat API request/response schemas."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.conversation import ConversationMessageResponse


class ChatArtifactResponse(BaseModel):
    id: str
    name: str
    artifact_type: str
    description: str | None = None
    href: str | None = None


class ChatMode(StrEnum):
    AUTO = "auto"
    ANALYZE = "analyze"
    DESIGN = "design"
    CAD = "cad"
    DOCUMENTS = "documents"
    REPORTS = "reports"


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=20000)
    conversation_id: UUID | None = None
    project_id: UUID | None = None
    attachments: list[UUID] = Field(default_factory=list)
    mode: ChatMode = ChatMode.AUTO
    assistant: str | None = Field(default=None, max_length=64)


class ChatResponse(BaseModel):
    conversation_id: UUID
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
    execution_status: str | None = None
    selected_capability: str | None = None
    artifacts: list[ChatArtifactResponse] = Field(default_factory=list)
    status_events: list[str] = Field(default_factory=list)
