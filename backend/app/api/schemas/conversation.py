"""Conversation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.conversation import (
    Conversation,
    ConversationMessage,
    MessageAttachment,
    MessageRole,
)


class MessageAttachmentResponse(BaseModel):
    file_id: UUID
    filename: str
    file_type: str | None = None
    content_type: str | None = None
    status: str
    parsing_status: str | None = None
    extraction_status: str | None = None

    @classmethod
    def from_domain(cls, attachment: MessageAttachment) -> MessageAttachmentResponse:
        return cls(
            file_id=attachment.file_id,
            filename=attachment.filename,
            file_type=attachment.file_type,
            content_type=attachment.content_type,
            status=attachment.status.value,
            parsing_status=attachment.parsing_status,
            extraction_status=attachment.extraction_status,
        )


class ConversationResponse(BaseModel):
    id: UUID
    account_id: str
    project_id: UUID | None = None
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> ConversationResponse:
        return cls.model_validate(conversation.model_dump())


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=500)
    project_id: UUID | None = None


class ConversationMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    attachments: list[MessageAttachmentResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, message: ConversationMessage) -> ConversationMessageResponse:
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            attachments=[MessageAttachmentResponse.from_domain(item) for item in message.attachments],
            metadata=message.metadata,
            created_at=message.created_at,
        )


class ConversationMessageListResponse(BaseModel):
    messages: list[ConversationMessageResponse]


class SendConversationMessageRequest(BaseModel):
    content: str = Field(default="", max_length=20000)
    attachment_file_ids: list[UUID] = Field(default_factory=list)


class SendConversationMessageResponse(BaseModel):
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse


class UploadConversationAttachmentResponse(BaseModel):
    attachment: MessageAttachmentResponse
    project_id: UUID
