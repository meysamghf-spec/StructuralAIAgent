"""Unified chat endpoint — /api/v1/chat."""

from __future__ import annotations

from threading import Event
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_actor_id,
    get_conversation_service,
    get_current_account,
)
from app.api.schemas.chat import ChatArtifactResponse, ChatRequest, ChatResponse
from app.api.schemas.conversation import ConversationMessageResponse
from app.application.agent_run_events import encode_sse
from app.application.conversation_service import ConversationService
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/chat", tags=["chat"])


def _resolve_conversation_id(
    body: ChatRequest,
    service: ConversationService,
    account: AuthenticatedAccount,
) -> UUID:
    conversation_id = body.conversation_id
    if conversation_id is None:
        conversation = service.create_conversation(
            account,
            project_id=body.project_id,
        )
        return conversation.id
    existing = service.get_conversation(conversation_id, account)
    if body.project_id is not None and existing.project_id is None:
        service.assign_project(conversation_id, body.project_id, account)
    return conversation_id


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChatResponse)
def send_chat_message(
    body: ChatRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> ChatResponse:
    conversation_id = _resolve_conversation_id(body, service, account)

    user_message, assistant_message = service.send_message(
        conversation_id,
        account,
        content=body.message,
        attachment_file_ids=body.attachments,
        actor_id=actor_id,
        mode=body.mode.value,
        assistant=body.assistant,
    )

    metadata = assistant_message.metadata or {}
    artifacts_raw = metadata.get("artifacts")
    artifacts: list[ChatArtifactResponse] = []
    if isinstance(artifacts_raw, list):
        for item in artifacts_raw:
            if isinstance(item, dict):
                artifacts.append(ChatArtifactResponse.model_validate(item))

    status_events_raw = metadata.get("status_events")
    status_events = (
        [str(item) for item in status_events_raw if isinstance(item, str)]
        if isinstance(status_events_raw, list)
        else []
    )

    execution_status = metadata.get("execution_status")
    progress = metadata.get("progress")
    resolved_status = (
        execution_status if isinstance(execution_status, str)
        else progress if isinstance(progress, str)
        else None
    )
    selected_capability = metadata.get("selected_capability")

    return ChatResponse(
        conversation_id=conversation_id,
        user_message=ConversationMessageResponse.from_domain(user_message),
        assistant_message=ConversationMessageResponse.from_domain(assistant_message),
        execution_status=resolved_status,
        selected_capability=selected_capability if isinstance(selected_capability, str) else None,
        artifacts=artifacts,
        status_events=status_events,
    )


@router.post("/stream")
def stream_chat_message(
    body: ChatRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> StreamingResponse:
    conversation_id = _resolve_conversation_id(body, service, account)
    cancelled = Event()

    def generate():
        try:
            for event_type, payload in service.iter_send_events(
                conversation_id,
                account,
                content=body.message,
                attachment_file_ids=body.attachments,
                actor_id=actor_id,
                mode=body.mode.value,
                assistant=body.assistant,
                cancelled=cancelled,
            ):
                yield encode_sse(event_type, payload)
        except GeneratorExit:
            cancelled.set()
            raise
        finally:
            cancelled.set()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
