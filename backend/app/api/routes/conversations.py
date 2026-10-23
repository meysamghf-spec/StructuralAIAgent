"""Conversation REST endpoints — /api/v1/conversations."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import (
    get_accessible_project,
    get_actor_id,
    get_conversation_service,
    get_current_account,
)
from app.api.schemas.conversation import (
    ConversationListResponse,
    ConversationMessageListResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
    MessageAttachmentResponse,
    SendConversationMessageRequest,
    SendConversationMessageResponse,
    UploadConversationAttachmentResponse,
)
from app.application.conversation_service import ConversationService
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConversationResponse)
def create_conversation(
    body: CreateConversationRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> ConversationResponse:
    conversation = service.create_conversation(
        account,
        title=body.title,
        project_id=body.project_id,
    )
    return ConversationResponse.from_domain(conversation)


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ConversationListResponse:
    conversations = service.list_conversations(account, limit=limit)
    return ConversationListResponse(
        conversations=[ConversationResponse.from_domain(item) for item in conversations]
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> ConversationResponse:
    conversation = service.get_conversation(conversation_id, account)
    return ConversationResponse.from_domain(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> None:
    service.delete_conversation(conversation_id, account)


@router.get("/{conversation_id}/messages", response_model=ConversationMessageListResponse)
def list_conversation_messages(
    conversation_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> ConversationMessageListResponse:
    messages = service.list_messages(conversation_id, account)
    return ConversationMessageListResponse(
        messages=[ConversationMessageResponse.from_domain(item) for item in messages]
    )


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=SendConversationMessageResponse,
)
def send_conversation_message(
    conversation_id: UUID,
    body: SendConversationMessageRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> SendConversationMessageResponse:
    user_message, assistant_message = service.send_message(
        conversation_id,
        account,
        content=body.content,
        attachment_file_ids=body.attachment_file_ids,
        actor_id=actor_id,
    )
    return SendConversationMessageResponse(
        user_message=ConversationMessageResponse.from_domain(user_message),
        assistant_message=ConversationMessageResponse.from_domain(assistant_message),
    )


@router.post(
    "/{conversation_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadConversationAttachmentResponse,
)
async def upload_conversation_attachment(
    conversation_id: UUID,
    file: Annotated[UploadFile, File(...)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    project_id: Annotated[UUID | None, Query()] = None,
) -> UploadConversationAttachmentResponse:
    content = await file.read()
    attachment = service.upload_attachment(
        conversation_id,
        account,
        filename=file.filename or "upload.bin",
        content=content,
        content_type=file.content_type,
        project_id=project_id,
    )
    conversation = service.get_conversation(conversation_id, account)
    assert conversation.project_id is not None
    return UploadConversationAttachmentResponse(
        attachment=MessageAttachmentResponse.from_domain(attachment),
        project_id=conversation.project_id,
    )


@router.get("/project-runs/{project_id}")
def list_project_chat_runs(
    project_id: UUID,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    _project=Depends(get_accessible_project),
) -> dict:
    """Runs produced in chat for a project (frame analysis, beam, optimization, AutoCAD drawings)."""
    return {"project_id": str(project_id), "runs": service.list_project_chat_runs(account, project_id)}
