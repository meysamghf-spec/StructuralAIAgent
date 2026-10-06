"""Conversation and chat message domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AttachmentStatus(StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class MessageAttachment(BaseModel):
    file_id: UUID
    filename: str
    file_type: str | None = None
    content_type: str | None = None
    status: AttachmentStatus = AttachmentStatus.READY
    parsing_status: str | None = None
    extraction_status: str | None = None


class Conversation(BaseModel):
    id: UUID
    account_id: str
    project_id: UUID | None = None
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationMessage(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str = ""
    attachments: list[MessageAttachment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
