"""Bind a run to files that already belong to its project.

Client-supplied attachment payloads are discarded. Only file ids that the
project file registry can resolve are stored on the execution.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.chat_attachment_context_service import ChatAttachmentContextService
from app.application.exceptions import InvalidExecutionAttachmentError


def bind_execution_attachments(
    project_id: UUID,
    parameters: dict[str, Any] | None,
    context_service: ChatAttachmentContextService,
) -> dict[str, Any]:
    cleaned = dict(parameters or {})
    cleaned.pop("attachment_context", None)
    raw_ids = cleaned.get("attachment_file_ids")
    if raw_ids in (None, []):
        cleaned.pop("attachment_file_ids", None)
        return cleaned
    if not isinstance(raw_ids, list):
        raise InvalidExecutionAttachmentError(
            "attachment_file_ids must be a list of project file ids.",
        )

    file_ids: list[UUID] = []
    for item in raw_ids:
        try:
            file_ids.append(UUID(str(item)))
        except (TypeError, ValueError) as exc:
            raise InvalidExecutionAttachmentError(
                "attachment_file_ids must be project file UUIDs.",
            ) from exc

    bundle = context_service.build(project_id, file_ids)
    cleaned["attachment_file_ids"] = bundle.file_ids
    cleaned["attachment_context"] = bundle.to_dict()
    return cleaned
